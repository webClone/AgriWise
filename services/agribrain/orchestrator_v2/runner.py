
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
import hashlib
import json
import logging
import math
import os
import time
from dataclasses import asdict, replace
from types import SimpleNamespace

from services.agribrain.orchestrator_v2.serialization import to_plain_data

logger = logging.getLogger(__name__)


def _freeze_reintegration_input(inputs: Any) -> Dict[str, Any]:
    """Serialize an orchestrator input without changing hash-bound contracts."""
    payload = to_plain_data(inputs)
    crop_cycle_context = getattr(inputs, "crop_cycle_context", None)
    if crop_cycle_context is not None:
        to_dict = getattr(crop_cycle_context, "to_dict", None)
        if not callable(to_dict):
            raise ValueError(
                "crop_cycle_context cannot be frozen for ASMAE reintegration"
            )
        payload["crop_cycle_context"] = to_dict()
    return payload


def _propagate_intelligence_snapshot_id(
    results: Dict[Any, Any],
) -> Optional[str]:
    """Put one canonical ASMAE snapshot ID on every downstream layer."""
    l1_result = results.get(LayerId.L1) if "LayerId" in globals() else None
    l1_output = getattr(l1_result, "output", None) if l1_result else None
    asmae_output = getattr(l1_output, "asmae_output", None)
    if asmae_output is None and l1_output is not None:
        context_package = getattr(l1_output, "_context_package", None)
        asmae_output = getattr(context_package, "asmae_output", None)
    if isinstance(asmae_output, dict):
        snapshot_id = (
            asmae_output.get("snapshot_id")
            or asmae_output.get("intelligence_snapshot_id")
        )
    else:
        snapshot_id = (
            getattr(asmae_output, "snapshot_id", None)
            or getattr(asmae_output, "intelligence_snapshot_id", None)
        )
    if not snapshot_id:
        return None
    snapshot_id = str(snapshot_id)
    for layer_result in results.values():
        output = getattr(layer_result, "output", None)
        if output is None:
            continue
        try:
            setattr(output, "intelligence_snapshot_id", snapshot_id)
        except Exception:
            pass
        provenance = getattr(output, "provenance", None)
        if isinstance(provenance, dict):
            provenance["intelligence_snapshot_id"] = snapshot_id
        context_package = getattr(output, "_context_package", None)
        if context_package is not None:
            try:
                setattr(
                    context_package,
                    "intelligence_snapshot_id",
                    snapshot_id,
                )
            except Exception:
                pass
    return snapshot_id


def _object_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            key: item for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _canonical_crop_temporal_records(
    layer0_output: Any,
    *,
    plot_geometry: Any = None,
    geometry_hash: str = "",
    plot_geometry_crs: Any = None,
    plot_namespace: Any = None,
    crop_cycle_id: Optional[str] = None,
    weather_records: Optional[List[Any]] = None,
    season_start: Any = None,
) -> List[Dict[str, Any]]:
    """Extract only evidence-bearing L0 packets for crop inference.

    Layer 1 daily interpolation is deliberately excluded: crop identity must
    see content-distinct admitted observations, not a filled daily curve that
    can multiply one acquisition into many apparent observations.
    """
    source_packages = (
        getattr(layer0_output, "layer0_source_packages", {}) or {}
        if layer0_output is not None else {}
    )
    from services.agribrain.layer2_veg_int.crop_observations import (
        build_canonical_crop_observations,
    )

    return build_canonical_crop_observations(
        source_packages,
        plot_geometry=plot_geometry,
        geometry_hash=geometry_hash,
        plot_geometry_crs=plot_geometry_crs,
        plot_namespace=plot_namespace,
        crop_cycle_id=crop_cycle_id,
        weather_records=weather_records or [],
        season_start=season_start,
    )


def _crop_influence_evidence_ids(
    records: List[Dict[str, Any]], *, independent_only: bool,
) -> Tuple[str, ...]:
    """Return the physical IDs shared by crop inference and ASMAE.

    ASMAE receives the same Layer-0 scene stack.  Using the physical
    acquisition key (and never a processing-product hash) makes reprocessed
    copies collapse to the same dependency identity.
    """
    values = set()
    for record in records or []:
        if not isinstance(record, dict):
            continue
        if independent_only:
            explicitly_independent = record.get("independent_evidence") is True
            legacy_independent = int(
                record.get("independent_observation_count") or 0
            ) > 0
            admitted = (
                record.get("admission_status") == "admitted"
                or record.get("quality_admitted") is True
                or record.get("usable") is True
            )
            if not ((explicitly_independent or legacy_independent) and admitted):
                continue
        identity = str(
            record.get("physical_acquisition_key")
            or record.get("independence_cluster_id")
            or record.get("observation_id")
            or ""
        ).strip()
        if identity:
            values.add(identity)
    return tuple(sorted(values))


def _crop_ledger_independent_evidence_ids(
    ledger_payload: Dict[str, Any],
) -> Tuple[str, ...]:
    """Return exactly the admitted physical clusters authorized by the ledger.

    The raw temporal record collection also contains provider daily statistics.
    Those records may retain legacy ``usable`` or
    ``independent_observation_count`` flags for non-crop consumers, but the
    canonical crop ledger deliberately rejects them when they cannot prove a
    physical acquisition identity.  Building the influence manifest from the
    raw collection therefore gives ASMAE a different evidence set from the
    ledger it is bound to and causes strict ASMAEInput validation to fail.

    The ledger is the authority for independence.  Keep this derivation small
    and fail closed on malformed rows; ASMAEInput independently rehydrates and
    verifies the complete ledger and manifest hashes.
    """
    values = {
        str(cluster.get("cluster_id") or "").strip()
        for cluster in (ledger_payload or {}).get("independence_clusters", [])
        if isinstance(cluster, dict)
        and cluster.get("independence_eligible") is True
        and cluster.get("admitted") is True
        and str(cluster.get("cluster_id") or "").strip()
    }
    return tuple(sorted(values))


def _crop_operational_context(
    operational_context: Dict[str, Any],
    *,
    weather_records: List[Any],
    soil_context: Any,
) -> Dict[str, Any]:
    result = dict(operational_context or {})
    if soil_context:
        result.setdefault("soil_context", soil_context)
    weather = [
        _object_mapping(item) for item in (weather_records or [])
        if _object_mapping(item)
    ]
    temperatures = []
    gdd = []
    for row in weather:
        value = row.get("tmean", row.get("temp_mean"))
        if value is None:
            tmin, tmax = row.get("temp_min"), row.get("temp_max")
            if isinstance(tmin, (int, float)) and isinstance(tmax, (int, float)):
                value = (float(tmin) + float(tmax)) / 2.0
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value)
            if math.isfinite(value):
                temperatures.append(value)
        raw_gdd = row.get("gdd")
        if isinstance(raw_gdd, (int, float)) and not isinstance(raw_gdd, bool):
            raw_gdd = float(raw_gdd)
            if math.isfinite(raw_gdd):
                gdd.append(raw_gdd)
    if temperatures:
        result["mean_temp_c"] = sum(temperatures) / len(temperatures)
    if gdd:
        result["gdd_accumulated"] = sum(gdd)
    return result

def _is_affirmatively_real_temporal_record(
    record: dict, *, value_keys: tuple[str, ...]
) -> bool:
    """Default-deny admission for dated provider observations."""
    from layer0.temporal_evidence import is_admitted_temporal_record
    return is_admitted_temporal_record(record, value_keys=value_keys)


def _parse_provider_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _freeze_previous_phenology_event(
    event: Dict[str, Any], *, as_of: Any,
) -> Dict[str, Any]:
    """Bind the latest as-of phenology receipt when no new evidence is admitted."""
    if not isinstance(event, dict):
        raise ValueError("previous phenology event is unavailable")
    event_id = str(event.get("event_id") or "").strip()
    event_time = _parse_provider_datetime(
        event.get("observation_or_valid_time") or event.get("effective_at")
    )
    as_of_time = _parse_provider_datetime(as_of)
    if not event_id or event_time is None or as_of_time is None:
        raise ValueError("previous phenology event has incomplete temporal identity")
    if event_time.date() > as_of_time.date():
        raise ValueError("previous phenology event is later than the run as-of date")
    payload = event.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    posterior = payload.get("phenology_posterior")
    posterior = dict(posterior) if isinstance(posterior, dict) else {}
    posterior_hash = str(posterior.get("content_hash") or "").strip()
    if not posterior or not posterior_hash:
        raise ValueError("previous phenology event has no hashed posterior")
    return {
        "pre_asmae_layer2a_status": "available",
        "pre_asmae_layer2a_reason": (
            "latest_canonical_event_no_new_admitted_physical_evidence"
        ),
        "phenology_posterior": posterior,
        "phenology_posterior_hash": posterior_hash,
        "phenology_worldline_event_id": event_id,
        "phenology_evidence_reuse": "exact_as_of_worldline_event",
    }


def _is_affirmatively_real_raster_record(
    record: dict, *, required_all: tuple[str, ...] = (),
    required_any: tuple[str, ...] = (),
) -> bool:
    """Validate a provider raster independently of plot-statistic fields."""
    if not isinstance(record, dict):
        return False
    if record.get("source_reality") != "real_raster":
        return False
    if record.get("real_provider_product") is not True:
        return False
    if record.get("production_usable") is not True:
        return False
    transform = record.get("transform")
    if not (
        isinstance(transform, (list, tuple))
        and len(transform) == 6
        and all(isinstance(value, (int, float)) for value in transform)
    ):
        return False
    if not str(record.get("crs") or "").strip():
        return False
    if not (
        isinstance(record.get("width"), int) and record["width"] > 0
        and isinstance(record.get("height"), int) and record["height"] > 0
    ):
        return False
    if not (record.get("provider_product_id") or record.get("content_hash")):
        return False
    available = {
        str(name).strip().upper()
        for mapping in (record.get("band_refs"), record.get("band_arrays"))
        if isinstance(mapping, dict)
        for name, value in mapping.items()
        if value is not None
    }
    if required_all and not set(required_all).issubset(available):
        return False
    if required_any and not set(required_any).intersection(available):
        return False
    return True

# Centralized Raw-Data to Layer 0 Package Conversion Adapters
def to_layer0_sentinel2_package(raw: dict) -> List[Any]:
    if not raw:
        return []
    records = (
        raw.get("data")
        or raw.get("observations")
        or raw.get("records")
        or raw.get("timeseries")
        or []
    )
    packages = []
    for rec in records:
        raw_datetime = rec.get("acquisition_datetime") or rec.get("date")
        dt = _parse_provider_datetime(raw_datetime)
        if dt is None:
            logger.warning("Skipping Sentinel-2 record without a valid acquisition date: %r", raw_datetime)
            continue
        dt_str = dt.date().isoformat()
        
        metadata = SimpleNamespace(
            scene_id=rec.get("scene_id", f"s2_{dt_str}"),
            acquisition_datetime=dt,
            plot_geometry_hash=(
                rec.get("plot_geometry_hash")
                or rec.get("geometry_hash")
                or raw.get("plot_geometry_hash", "")
            ),
            plot_geometry=(
                rec.get("plot_geometry")
                or raw.get("plot_geometry")
                or raw.get("polygon_geojson")
                or raw.get("polygon_coords")
            ),
            plot_geometry_crs=(
                rec.get("plot_geometry_crs")
                or raw.get("plot_geometry_crs")
                or raw.get("polygon_crs")
            ),
            tenant_id=str(rec.get("tenant_id") or raw.get("tenant_id") or ""),
            farm_id=str(rec.get("farm_id") or raw.get("farm_id") or ""),
            plot_id=str(rec.get("plot_id") or raw.get("plot_id") or ""),
            source_family="sentinel2",
            provider="copernicus",
            # Raster coordinates have no safe implicit CRS.  Crop-observation
            # admission will reject real arrays when the gateway did not
            # declare this field.
            crs=rec.get("crs"),
            band_list=sorted(
                str(name) for name in (
                    (rec.get("band_refs") or rec.get("band_arrays") or {}).keys()
                )
            ) or ["B02", "B03", "B04", "B08"],
        )
        metadata.width = rec.get("width")
        metadata.height = rec.get("height")
        metadata.transform = rec.get("transform")
        
        is_real_temporal_observation = _is_affirmatively_real_temporal_record(
            rec,
            value_keys=("ndvi", "ndvi_mean", "evi", "evi_mean", "ndmi", "ndmi_mean"),
        )
        is_real_raster_observation = _is_affirmatively_real_raster_record(
            rec, required_all=("B04", "B08"),
        )
        is_admitted_observation = (
            is_real_temporal_observation or is_real_raster_observation
        )

        if not is_admitted_observation:
            data_status = "fallback"
            production_usable = False
            real_provider_product = False
            diagnostic_only = True
            state_update_allowed = False
        else:
            data_status = rec.get("data_status", "observed")
            production_usable = True
            real_provider_product = rec.get("real_provider_product") is True
            diagnostic_only = False
            state_update_allowed = True

        source_reality = rec.get("source_reality") if is_admitted_observation else "unknown_provider_observation"
        metadata.source_reality = source_reality
        metadata.content_hash = rec.get("content_hash")
        metadata.provider_product_id = rec.get("provider_product_id", rec.get("scene_id"))
        metadata.catalog_item_id = rec.get("catalog_item_id")
        metadata.provider_tile_id = rec.get("provider_tile_id")
        metadata.provider_orbit_id = rec.get("provider_orbit_id")
        metadata.provider_orbit_pass = rec.get("provider_orbit_pass")
        metadata.relative_orbit = rec.get("relative_orbit")
        metadata.sensing_timestamp = rec.get("sensing_timestamp")
        metadata.mgrs_tile_id = rec.get("mgrs_tile_id")
        metadata.processing_baseline = rec.get("processing_baseline")
        metadata.process_request_hash = rec.get("process_request_hash")
        metadata.provider_response_hash = rec.get("provider_response_hash")
        metadata.product_binding = rec.get("product_binding")
        metadata.binding_proof = rec.get("binding_proof") or {}
        temporal_basis = rec.get("temporal_basis") or (
            "daily_plot_statistic"
            if source_reality == "provider_daily_statistical_aggregate"
            else "scene_observation"
        )
        metadata.temporal_basis = temporal_basis
        metadata.production_usable = production_usable
        metadata.real_provider_product = real_provider_product
        metadata.diagnostic_only = diagnostic_only
        metadata.state_update_allowed = state_update_allowed
        metadata.data_status = data_status

        packet = {
            "timestamp": dt.isoformat(),
            "date": dt_str,
            "ndvi_mean": rec.get("ndvi", rec.get("ndvi_mean")),
            "evi_mean": rec.get("evi", rec.get("evi_mean")),
            "ndmi_mean": rec.get("ndmi", rec.get("ndmi_mean")),
            "ndre_mean": rec.get("ndre", rec.get("ndre_mean")),
            "bsi_mean": rec.get("bsi", rec.get("bsi_mean")),
            "cloud_cover": rec.get("cloud_cover", 0.0),
            "clear_fraction": rec.get("clear_fraction", rec.get("valid_fraction")),
            "content_hash": rec.get("content_hash"),
            "provider_product_id": rec.get("provider_product_id", rec.get("scene_id")),
            "observation_id": rec.get("observation_id"),
            "request_hash": rec.get("request_hash"),
            "geometry_hash": rec.get("geometry_hash", raw.get("plot_geometry_hash")),
            "temporal_basis": temporal_basis,
            "independent_observation_count": 0 if temporal_basis == "daily_plot_statistic" else 1,
            "vegetation_fraction_scl": rec.get("vegetation_fraction_scl", 0.0),
            "bare_soil_fraction_scl": rec.get("bare_soil_fraction_scl", 0.0),
            "usable": rec.get("usable") is True,
            "quality_class": rec.get("quality_class"),
            "quality_admitted": rec.get("quality_admitted") is True,
            "valid_pixel_count": rec.get("valid_pixel_count"),
            "sample_count": rec.get("sample_count"),
            "uncertainty": rec.get("uncertainty"),
            "reading_reliability": max(
                0.05,
                min(0.95, float(rec.get("clear_fraction") or rec.get("valid_fraction") or 0.0)),
            ),
            "data_status": data_status,
            "source_reality": source_reality,
            "production_usable": production_usable,
            "real_provider_product": real_provider_product,
            "diagnostic_only": diagnostic_only,
            "state_update_allowed": state_update_allowed,
        }
        
        quality = rec.get("quality") if isinstance(rec.get("quality"), dict) else {}
        raster_usable = bool(
            rec.get("usable") is True
            or quality.get("usable") is True
            or is_real_raster_observation
        )
        qa = SimpleNamespace(
            usable=raster_usable,
            quality_class=SimpleNamespace(value=(
                rec.get("quality_class") or quality.get("quality_class") or "unknown"
            )),
            valid_fraction=float(
                rec.get("valid_fraction")
                if rec.get("valid_fraction") is not None
                else quality.get("valid_fraction", 0.0)
            ),
        )
        
        pkg = SimpleNamespace(
            plot_id=raw.get("plot_id", ""),
            source_family="sentinel2",
            metadata=metadata,
            packets=[packet],
            qa=qa,
            kalman_observations=[],
            provenance_report={},
            diagnostics={},
            source_reality=source_reality,
            test_override=rec.get("test_override", False),
            production_usable=production_usable,
            real_provider_product=real_provider_product,
            diagnostic_only=diagnostic_only,
            state_update_allowed=state_update_allowed,
        )
        pkg.band_arrays = rec.get("band_arrays")
        pkg.local_cache_refs = rec.get("band_refs", {})
        pkg.mask_refs = rec.get("mask_refs", {})
        pkg.band_units = rec.get("band_units", {})
        metadata.band_units = pkg.band_units
        packages.append(pkg)
    return packages

def to_layer0_sentinel1_package(raw: dict) -> List[Any]:
    if not raw:
        return []
    records = raw.get("timeseries", []) or raw.get("data", []) or []
    packages = []
    for rec in records:
        provider_relative_orbit = (
            rec.get("provider_relative_orbit")
            or rec.get("relative_orbit")
            or rec.get("relative_orbit_number")
        )
        provider_absolute_orbit = (
            rec.get("provider_absolute_orbit")
            or rec.get("absolute_orbit")
            or rec.get("orbit_number")
        )
        process_metadata = (
            rec.get("process_metadata")
            or rec.get("process_api_metadata")
            or {}
        )
        catalog_metadata = (
            rec.get("catalog_metadata")
            or rec.get("stac_metadata")
            or rec.get("catalog_properties")
            or {}
        )
        process_metadata = (
            process_metadata if isinstance(process_metadata, dict) else {}
        )
        catalog_metadata = (
            catalog_metadata if isinstance(catalog_metadata, dict) else {}
        )
        raw_datetime = rec.get("acquisition_datetime") or rec.get("date")
        dt = _parse_provider_datetime(raw_datetime)
        if dt is None:
            logger.warning("Skipping Sentinel-1 record without a valid acquisition date: %r", raw_datetime)
            continue
        dt_str = dt.date().isoformat()
        
        metadata = SimpleNamespace(
            scene_id=rec.get("scene_id", f"s1_{dt_str}"),
            acquisition_datetime=dt,
            sensing_timestamp=rec.get("sensing_timestamp") or dt.isoformat(),
            plot_geometry_hash=(
                rec.get("plot_geometry_hash")
                or rec.get("geometry_hash")
                or raw.get("plot_geometry_hash", "")
            ),
            plot_geometry=(
                rec.get("plot_geometry")
                or raw.get("plot_geometry")
                or raw.get("polygon_geojson")
                or raw.get("polygon_coords")
            ),
            plot_geometry_crs=(
                rec.get("plot_geometry_crs")
                or raw.get("plot_geometry_crs")
                or raw.get("polygon_crs")
            ),
            tenant_id=str(rec.get("tenant_id") or raw.get("tenant_id") or ""),
            farm_id=str(rec.get("farm_id") or raw.get("farm_id") or ""),
            plot_id=str(rec.get("plot_id") or raw.get("plot_id") or ""),
            source_family="sentinel1",
            provider=str(rec.get("provider") or "copernicus"),
            sensor=str(rec.get("sensor") or "C-SAR"),
            mission=rec.get("mission") or rec.get("platform"),
            # Raster coordinates have no safe implicit CRS.
            crs=rec.get("crs"),
            band_list=["VV", "VH"],
        )
        metadata.width = rec.get("width")
        metadata.height = rec.get("height")
        metadata.transform = rec.get("transform")
        metadata.catalog_item_id = rec.get("catalog_item_id")
        metadata.provider_tile_id = rec.get("provider_tile_id")
        metadata.provider_orbit_id = rec.get("provider_orbit_id")
        metadata.provider_orbit_pass = (
            rec.get("provider_orbit_pass")
            or rec.get("orbit_pass")
            or rec.get("orbit_direction")
        )
        metadata.provider_relative_orbit = provider_relative_orbit
        metadata.provider_absolute_orbit = provider_absolute_orbit
        metadata.relative_orbit = provider_relative_orbit
        metadata.orbit_number = provider_absolute_orbit
        metadata.process_metadata = process_metadata
        metadata.catalog_metadata = catalog_metadata
        metadata.processing_timestamp = rec.get("processing_timestamp")
        metadata.processing_baseline = rec.get("processing_baseline")
        metadata.process_request_hash = (
            rec.get("process_request_hash") or rec.get("request_hash")
        )
        metadata.provider_response_hash = rec.get("provider_response_hash")
        metadata.product_binding = rec.get("product_binding")
        metadata.binding_proof = rec.get("binding_proof") or {}
        
        is_real_temporal_observation = _is_affirmatively_real_temporal_record(
            rec,
            value_keys=("vv", "vv_db", "vv_db_mean", "vh", "vh_db", "vh_db_mean", "vv_vh_ratio", "rvi", "rvi_mean"),
        )
        is_real_raster_observation = _is_affirmatively_real_raster_record(
            rec, required_any=("VV", "VH"),
        )
        is_admitted_observation = (
            is_real_temporal_observation or is_real_raster_observation
        )

        if not is_admitted_observation:
            data_status = "fallback"
            production_usable = False
            real_provider_product = False
            diagnostic_only = True
            state_update_allowed = False
        else:
            data_status = rec.get("data_status", "observed")
            production_usable = True
            real_provider_product = rec.get("real_provider_product") is True
            diagnostic_only = False
            state_update_allowed = True

        source_reality = rec.get("source_reality") if is_admitted_observation else "unknown_provider_observation"
        metadata.source_reality = source_reality
        metadata.content_hash = rec.get("content_hash")
        metadata.provider_product_id = rec.get("provider_product_id", rec.get("scene_id"))
        temporal_basis = rec.get("temporal_basis") or (
            "daily_plot_statistic"
            if source_reality == "provider_daily_statistical_aggregate"
            else "scene_observation"
        )
        metadata.temporal_basis = temporal_basis
        metadata.production_usable = production_usable
        metadata.real_provider_product = real_provider_product
        metadata.diagnostic_only = diagnostic_only
        metadata.state_update_allowed = state_update_allowed
        metadata.data_status = data_status

        packet = {
            "timestamp": dt.isoformat(),
            "date": dt_str,
            "vv_db_mean": rec.get("vv_db_mean", rec.get("vv_db", rec.get("vv"))),
            "vh_db_mean": rec.get("vh_db_mean", rec.get("vh_db", rec.get("vh"))),
            "vv_vh_ratio_mean": rec.get("vv_vh_ratio_mean", rec.get("vv_vh_ratio")),
            "rvi_mean": rec.get("rvi_mean", rec.get("rvi")),
            "surface_wetness_proxy_mean": rec.get("surface_wetness_proxy_mean"),
            "content_hash": rec.get("content_hash"),
            "provider_product_id": rec.get("provider_product_id", rec.get("scene_id")),
            "catalog_item_id": rec.get("catalog_item_id"),
            "observation_id": rec.get("observation_id"),
            "request_hash": rec.get("request_hash"),
            "process_request_hash": rec.get("process_request_hash"),
            "provider_response_hash": rec.get("provider_response_hash"),
            "provider_orbit_id": rec.get("provider_orbit_id"),
            "provider_orbit_pass": (
                rec.get("provider_orbit_pass")
                or rec.get("orbit_pass")
                or rec.get("orbit_direction")
            ),
            "provider_relative_orbit": provider_relative_orbit,
            "provider_absolute_orbit": provider_absolute_orbit,
            "relative_orbit": provider_relative_orbit,
            "process_metadata": process_metadata,
            "catalog_metadata": catalog_metadata,
            "geometry_hash": rec.get("geometry_hash", raw.get("plot_geometry_hash")),
            "temporal_basis": temporal_basis,
            "quality_admitted": rec.get("quality_admitted") is True,
            "valid_pixel_count": rec.get("valid_pixel_count"),
            "sample_count": rec.get("sample_count"),
            "uncertainty": rec.get("uncertainty"),
            "reading_reliability": max(
                0.05,
                min(0.95, float(rec.get("valid_fraction") or 0.0)),
            ),
            "usable": rec.get("usable") is True,
            "quality_class": rec.get("quality_class"),
            "data_status": data_status,
            "source_reality": source_reality,
            "production_usable": production_usable,
            "real_provider_product": real_provider_product,
            "diagnostic_only": diagnostic_only,
            "state_update_allowed": state_update_allowed,
        }
        
        quality = rec.get("quality") if isinstance(rec.get("quality"), dict) else {}
        raster_usable = bool(
            rec.get("usable") is True
            or quality.get("usable") is True
            or is_real_raster_observation
        )
        qa = SimpleNamespace(
            usable=raster_usable,
            quality_class=SimpleNamespace(value=(
                rec.get("quality_class") or quality.get("quality_class") or "unknown"
            )),
            valid_fraction=float(
                rec.get("valid_fraction")
                if rec.get("valid_fraction") is not None
                else quality.get("valid_fraction", 0.0)
            ),
        )

        raw_provenance = (
            raw.get("provenance")
            if isinstance(raw.get("provenance"), dict)
            else {}
        )
        record_provenance = (
            rec.get("provenance")
            if isinstance(rec.get("provenance"), dict)
            else {}
        )
        provenance = {
            **raw_provenance,
            **record_provenance,
            "source_reality": source_reality,
            "provider_product_id": metadata.provider_product_id,
            "content_hash": metadata.content_hash,
            "process_request_hash": metadata.process_request_hash,
            "provider_response_hash": metadata.provider_response_hash,
            "provider_orbit_id": metadata.provider_orbit_id,
            "provider_orbit_pass": metadata.provider_orbit_pass,
            "provider_relative_orbit": metadata.provider_relative_orbit,
            "provider_absolute_orbit": metadata.provider_absolute_orbit,
            "relative_orbit": metadata.relative_orbit,
            "process_metadata": metadata.process_metadata,
            "catalog_metadata": metadata.catalog_metadata,
        }
        
        pkg = SimpleNamespace(
            plot_id=raw.get("plot_id", ""),
            source_family="sentinel1",
            metadata=metadata,
            packets=[packet],
            qa=qa,
            kalman_observations=[],
            provenance=provenance,
            provenance_report=provenance,
            diagnostics={},
            source_reality=source_reality,
            test_override=rec.get("test_override", False),
            production_usable=production_usable,
            real_provider_product=real_provider_product,
            diagnostic_only=diagnostic_only,
            state_update_allowed=state_update_allowed,
        )
        pkg.band_arrays = rec.get("band_arrays")
        pkg.local_cache_refs = rec.get("band_refs", {})
        pkg.mask_refs = rec.get("mask_refs", {})
        pkg.band_units = rec.get("band_units", {})
        metadata.band_units = pkg.band_units
        packages.append(pkg)
    return packages

def to_layer0_sensor_package(raw: dict) -> Any:
    if not raw:
        raw = {}
    raw_readings = raw.get("readings", []) or []
    sensor_field_map = {
        "soilMoisture": ("soil_moisture_vwc", "%"),
        "temperature": ("air_temperature_c", "C"),
        "humidity": ("humidity_mean_pct", "%"),
        "rainfall": ("precipitation_mm", "mm"),
        "ec": ("soil_ec_ds_m", "dS/m"),
        "windSpeed": ("wind_speed_m_s", "m/s"),
        "battery": ("battery_level_pct", "%"),
        "rssi": ("signal_rssi_dbm", "dBm"),
    }

    def canonicalize_sensor_readings(items):
        canonical = []
        for item in items:
            if not isinstance(item, dict):
                canonical.append(item)
                continue
            device_id = item.get("device_id") or item.get("deviceId") or item.get("id") or item.get("sensorId")
            timestamp = item.get("timestamp") or item.get("lastSync") or item.get("observedAt")
            if item.get("variable") is not None and item.get("value") is not None:
                canonical.append(SimpleNamespace(
                    device_id=device_id,
                    variable=item.get("variable"),
                    value=item.get("value"),
                    unit=item.get("unit", ""),
                    timestamp=timestamp,
                    diagnostic_only=bool(item.get("diagnostic_only", True)),
                    state_update_allowed=bool(item.get("state_update_allowed", False)),
                    raw=item,
                ))
                continue
            for field, (variable, unit) in sensor_field_map.items():
                value = item.get(field)
                if value is None:
                    continue
                canonical.append(SimpleNamespace(
                    device_id=device_id,
                    variable=variable,
                    value=value,
                    unit=unit,
                    timestamp=timestamp,
                    diagnostic_only=True,
                    state_update_allowed=False,
                    raw=item,
                ))
        return canonical

    readings = canonicalize_sensor_readings(raw_readings)
    packets = canonicalize_sensor_readings(raw.get("observation_packets", []) or raw.get("packets", []) or raw_readings)
    
    window_start = raw.get("window_start")
    if isinstance(window_start, str):
        window_start = datetime.fromisoformat(window_start.replace("Z", "+00:00"))
    elif not window_start:
        window_start = datetime.now(timezone.utc)
        
    window_end = raw.get("window_end")
    if isinstance(window_end, str):
        window_end = datetime.fromisoformat(window_end.replace("Z", "+00:00"))
    elif not window_end:
        window_end = datetime.now(timezone.utc)
        
    pkg = SimpleNamespace(
        plot_id=raw.get("plot_id", ""),
        readings=readings,
        window_start=window_start,
        window_end=window_end,
        observation_packets=packets,
        devices=raw.get("devices", []),
        aggregates=raw.get("aggregates", []),
        process_forcing_events=raw.get("process_forcing_events", []),
        kalman_observations=raw.get("kalman_observations", []),
        diagnostics=raw.get("diagnostics", {}),
        provenance=raw.get("provenance", {})
    )
    return pkg

def to_layer0_environment_package(raw: dict) -> Any:
    if not raw:
        raw = {}
    records = raw.get("weather_consensus", []) or raw.get("records", [])
    if not records and "daily" in raw:
        d = raw.get("daily", {})
        times = d.get("time", [])
        for i, t in enumerate(times):
            records.append({
                "date": t,
                "temp_max": d.get("temperature_2m_max")[i] if (d.get("temperature_2m_max") and i < len(d["temperature_2m_max"])) else None,
                "temp_min": d.get("temperature_2m_min")[i] if (d.get("temperature_2m_min") and i < len(d["temperature_2m_min"])) else None,
                "precipitation": d.get("precipitation_sum")[i] if (d.get("precipitation_sum") and i < len(d["precipitation_sum"])) else None,
                "et0": d.get("et0_fao_evapotranspiration")[i] if (d.get("et0_fao_evapotranspiration") and i < len(d["et0_fao_evapotranspiration"])) else None,
            })
            
    packets = []
    for rec in records:
        d_str = rec.get("date", "")
        try:
            dt = datetime.fromisoformat(d_str).replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
        packets.append({
            "timestamp": dt.isoformat(),
            "date": d_str,
            "packet_type": "WEATHER_REANALYSIS",
            "temp_max": rec.get("temp_max"),
            "temp_min": rec.get("temp_min"),
            "precipitation": rec.get("precipitation"),
            "et0": rec.get("et0"),
            "humidity": rec.get("humidity_mean_pct", rec.get("humidity")),
            "wind_speed": rec.get("wind_speed_m_s", rec.get("wind_speed")),
            "data_status": "estimated",
        })
        
    pkg = SimpleNamespace(
        plot_id=raw.get("plot_id", ""),
        soilgrids_profile=raw.get("soilgrids", {}),
        fao_context=raw.get("fao_context", {}),
        weather_consensus=records,
        timestamp_window=raw.get("timestamp_window", {}),
        packets=packets,
        weak_kalman_observations=[],
        process_forcing=[],
        diagnostics=raw.get("diagnostics", {}),
        provenance=raw.get("provenance", {}),
        qa=SimpleNamespace(quality_class=SimpleNamespace(value="good"))
    )
    return pkg


def _weather_records_from_source_package(package: Any) -> List[Any]:
    """Read the canonical Layer 0 evidence transport without native-shape loss.

    A wrapped v2 package always owns ``evidence_records``.  Native consensus is
    accepted only for unwrapped compatibility fixtures; an empty canonical
    collection must not fall through to a different representation.
    """
    if package is None:
        return []
    if isinstance(package, dict) and "evidence_records" in package:
        return list(package.get("evidence_records") or [])
    if hasattr(package, "evidence_records"):
        return list(getattr(package, "evidence_records") or [])
    if isinstance(package, dict):
        return list(package.get("weather_consensus") or [])
    return list(getattr(package, "weather_consensus", None) or [])


_REPLAY_WEATHER_KEYS = (
    "temp_max", "temp_min", "temp_mean", "precipitation", "et0",
    "humidity", "wind_speed",
)


def _weather_records_from_reintegration_context(
    operational_context: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Recover frozen, admitted process forcings for worker reintegration.

    This path is deliberately enabled only for the completion-triggered worker
    replay.  It never upgrades authority and never treats a forcing as a direct
    crop-state observation.
    """
    context = operational_context or {}
    if context.get("asmae_worker_reintegration") is not True:
        return []
    result: List[Dict[str, Any]] = []
    for raw in context.get("asmae_replay_plot_timeseries") or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("observation_role") not in (None, "process_forcing"):
            continue
        values = {key: raw.get(key) for key in _REPLAY_WEATHER_KEYS}
        if not any(value is not None for value in values.values()):
            continue
        timestamp = str(raw.get("timestamp") or raw.get("date") or "")
        record = {
            "date": timestamp[:10],
            **values,
            "data_status": raw.get("data_status") or "estimated",
            "source": raw.get("source") or "frozen_asmae_process_forcing",
            "content_hash": raw.get("content_hash"),
            "observation_role": "process_forcing",
            "direct_observation": False,
            "capability_plan_hash": context.get(
                "asmae_replay_capability_plan_hash"
            ),
        }
        result.append(record)
    return result


def _load_frozen_reintegration_event(
    service: Any,
    *,
    inputs: Any,
    event_id: str,
    event_type: str,
    payload_key: str,
    expected_content_hash: str,
    rehydrate_generated_at: bool = False,
) -> Dict[str, Any]:
    """Load one exact job-frozen crop/phenology event, or fail closed.

    Looking up the latest event is intentionally forbidden here: a worker may
    finish after another request has advanced the worldline.  Reintegration is
    a replay of its admitted evidence, not a new crop-inference observation.
    """
    event_id = str(event_id or "").strip()
    expected_content_hash = str(expected_content_hash or "").strip()
    if not event_id or not expected_content_hash:
        raise ValueError(f"frozen {event_type} identity is unavailable")
    event = service.load_event(
        plot_id=inputs.plot_id,
        event_id=event_id,
        tenant_id=inputs.tenant_id,
        namespace=inputs.farm_id,
    )
    if not event or str(event.get("event_id") or "") != event_id:
        raise ValueError(f"frozen {event_type} event was not found")
    if (
        event.get("event_type") != event_type
        or event.get("tenant_id") != inputs.tenant_id
        or event.get("namespace") != inputs.farm_id
        or event.get("plot_id") != inputs.plot_id
    ):
        raise ValueError(f"frozen {event_type} namespace/type mismatch")
    payload = event.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    declared_namespace = payload.get("plot_namespace")
    expected_namespace = {
        "tenant_id": inputs.tenant_id,
        "farm_id": inputs.farm_id,
        "plot_id": inputs.plot_id,
    }
    if declared_namespace != expected_namespace:
        raise ValueError(f"frozen {event_type} payload namespace mismatch")
    scientific = payload.get(payload_key)
    if not isinstance(scientific, dict):
        raise ValueError(f"frozen {event_type} scientific payload is missing")
    if str(scientific.get("content_hash") or "") != expected_content_hash:
        raise ValueError(f"frozen {event_type} content hash mismatch")
    result = dict(scientific)
    if rehydrate_generated_at:
        effective_at = str(
            event.get("effective_at")
            or event.get("observation_or_valid_time")
            or ""
        ).strip()
        if not effective_at:
            raise ValueError(f"frozen {event_type} effective time is unavailable")
        result["generated_at"] = effective_at
    return result


def _worldline_scientific_payload_matches(
    declared: Any, persisted: Any,
) -> bool:
    """Compare scientific payloads using canonical worldline persistence rules."""
    from services.agribrain.world_model.canonical_worldline import (
        VOLATILE_IDENTITY_KEYS,
    )

    def canonical(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): canonical(item)
                for key, item in value.items()
                if str(key) not in VOLATILE_IDENTITY_KEYS
            }
        if isinstance(value, (list, tuple)):
            return [canonical(item) for item in value]
        return value

    return canonical(declared) == canonical(persisted)

from services.agribrain.orchestrator_v2.schema import (
    OrchestratorInput, RunArtifact, RunMeta, LayerResult, LayerStatus, GlobalQuality
)
from services.agribrain.orchestrator_v2.registry import LAYER_REGISTRY, LayerId, get_layer_versions
from services.agribrain.orchestrator_v2.hashing import generate_orchestrator_run_id
from services.agribrain.orchestrator_v2.gating import merge_execution_plans, evaluate_global_quality, filter_unsafe_actions
from services.agribrain.orchestrator_v2.storage import LocalJsonStore
from services.agribrain.orchestrator_v2.chat_adapter import ChatPayload, build_chat_payload
from services.agribrain.layer10_sire.schema import Layer10Input
from services.agribrain.layer8_prescriptive.schema import Layer8Input
from services.agribrain.common.plot_namespace import namespace_payload

ORCHESTRATOR_VERSION = "2.1.0"

def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)

from services.agribrain.orchestrator_v2.intents import Intent, detect_intent, resolve_time_window

# Human-readable stage names for progress reporting
_LAYER_STAGE_NAMES = {
    "L1": "Fusing satellite & weather data",
    "L2": "Analyzing crop health",
    "L3": "Evaluating water & stress models",
    "L4": "Assessing soil nutrients",
    "L5": "Scanning disease & pest risk",
    "L6": "Computing execution state",
    "L7": "Building season plan",
    "L8": "Generating prescriptions",
    "L9": "Composing narrative",
    "L10": "Rendering spatial intelligence map",
}

def run_orchestrator(
    inputs: OrchestratorInput,
    store: Optional[LocalJsonStore] = None,
    intent: Intent = Intent.DECISION,
    user_query: Optional[str] = None,
    skip_l9: bool = False,
    progress_cb=None,
) -> RunArtifact:
    """
    Main Entrypoint for AgriBrain V2.1 (Hardened).
    Supports Intent-Based Routing to skip unnecessary layers.
    """
    ts_now = datetime.now(timezone.utc).isoformat() + "Z"
    request_started = time.perf_counter()
    stage_timings_ms: Dict[str, float] = {}
    
    # 1. Generate Deterministic ID
    layer_versions = get_layer_versions()
    run_id = generate_orchestrator_run_id(inputs, layer_versions, ORCHESTRATOR_VERSION, intent=intent)
    
    results: Dict[LayerId, LayerResult] = {}
    
    # 2. Execution Sequence
    
    # --- Intent Gating (Early Exit) ---
    if intent in [Intent.GREETING, Intent.GENERAL]:
        return _finalize_artifact(run_id, ts_now, inputs, results, store, primary_acquisition="layer0")

    primary_acquisition = "layer0"
    fallback_used = False
    fallback_reason = None
    l0_output = None
    s2_packages = []
    s1_packages = []

    # Run Layer0Runner inside orchestrator
    try:
        from layer0.data_gateway import broker
        from layer0.runner import Layer0Runner, Layer0RunnerInput
        
        plot_id = inputs.plot_id
        lat = float(inputs.operational_context.get("lat", 0.0)) if inputs.operational_context else 0.0
        lng = float(inputs.operational_context.get("lng", 0.0)) if inputs.operational_context else 0.0
        polygon_coords = inputs.operational_context.get("polygon_coords") if inputs.operational_context else None
        start_date = inputs.date_range.get("start", "")
        end_date = inputs.date_range.get("end", "")

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            sar_days = max(1, (end_dt - start_dt).days + 1)
        except Exception:
            sar_days = 30

        # Fetch raster composites early for modern path and ASMAE
        stage_started = time.perf_counter()
        try:
            from layer1_fusion.runner import _fetch_raster_composites_for_v1
            raster_composites = _fetch_raster_composites_for_v1(
                plot_id=plot_id, lat=lat, lng=lng,
                start_date=start_date, end_date=end_date,
                polygon_coords=polygon_coords
            )
        except Exception as e:
            logger.warning(f"Failed to fetch raster composites: {e}")
            raster_composites = {}
        stage_timings_ms["raster_composite_resolution"] = round((time.perf_counter() - stage_started) * 1000.0, 3)

        from layer05_asmae.runner import ASMAERunner
        asmae_runner = ASMAERunner()
        asmae_enabled = asmae_runner.is_enabled(plot_id)

        stage_started = time.perf_counter()
        raw_s2 = broker.get("sentinel2_ndvi_ts", plot_id, lat, lng, days=180, polygon_coords=polygon_coords) or {}
        stage_timings_ms["gateway_s2_temporal"] = round((time.perf_counter() - stage_started) * 1000.0, 3)
        stage_started = time.perf_counter()
        raw_s1 = broker.get("sentinel1_sar_ts", plot_id, lat, lng, days=sar_days, polygon_coords=polygon_coords) or {}
        stage_timings_ms["gateway_s1_temporal"] = round((time.perf_counter() - stage_started) * 1000.0, 3)

        s2_res = None
        s1_res = None
        s2_err_reason = None
        s1_err_reason = None
        if asmae_enabled:
            try:
                from layer0.providers.asmae_scene_fetcher import (
                    fetch_asmae_s2_scene_stack,
                    fetch_asmae_s1_scene_stack
                )
                try:
                    s2_res = fetch_asmae_s2_scene_stack(plot_id, run_id, (start_date, end_date), raster_composites, lat=lat, lng=lng, polygon_coords=polygon_coords)
                except Exception as e:
                    logger.error(f"Failed to fetch real ASMAE S2 scenes: {e}", exc_info=True)
                    s2_err_reason = "provider_error"
                
                try:
                    s1_res = fetch_asmae_s1_scene_stack(plot_id, run_id, (start_date, end_date), raster_composites, lat=lat, lng=lng, polygon_coords=polygon_coords)
                except Exception as e:
                    logger.error(f"Failed to fetch real ASMAE S1 scenes: {e}", exc_info=True)
                    s1_err_reason = "provider_error"
            except Exception as e:
                logger.error(f"Failed to initialize scene fetchers: {e}", exc_info=True)
                s2_err_reason = "provider_error"
                s1_err_reason = "provider_error"

        stage_started = time.perf_counter()
        raw_env = broker.get("open_meteo_archive", plot_id, lat, lng, start_date=start_date, end_date=end_date) or {}
        stage_timings_ms["gateway_environment"] = round((time.perf_counter() - stage_started) * 1000.0, 3)
        stage_started = time.perf_counter()
        raw_soil = broker.get("soilgrids", plot_id, lat, lng) or {}
        stage_timings_ms["gateway_soil"] = round((time.perf_counter() - stage_started) * 1000.0, 3)

        replay_weather = _weather_records_from_reintegration_context(
            inputs.operational_context
        )
        if replay_weather:
            raw_env = dict(raw_env)
            raw_env["weather_consensus"] = replay_weather
            raw_env["provenance"] = {
                **dict(raw_env.get("provenance") or {}),
                "replay_source": "frozen_asmae_process_forcing",
                "capability_plan_hash": (inputs.operational_context or {}).get(
                    "asmae_replay_capability_plan_hash"
                ),
            }

        # Merge soil and forecast into raw_env
        raw_env["soilgrids"] = raw_soil
        raw_env["fao_context"] = {}
        raw_env["timestamp_window"] = {"window_start": start_date + "T00:00:00+00:00", "window_end": end_date + "T23:59:59+00:00"}

        # Convert raw data via adapters
        stage_started = time.perf_counter()
        s2_packages = to_layer0_sentinel2_package(raw_s2)
        s1_packages = to_layer0_sentinel1_package(raw_s1)
        env_package = to_layer0_environment_package(raw_env)
        stage_timings_ms["observation_admission_and_conversion"] = round((time.perf_counter() - stage_started) * 1000.0, 3)

        # Construct sensor package
        sensor_data = inputs.operational_context or {}
        sensor_package = to_layer0_sensor_package({
            "plot_id": plot_id,
            "readings": sensor_data.get("sensors", []),
            "observation_packets": sensor_data.get("sensors", []),
            "devices": list(set(
                s.get("device_id") or s.get("deviceId") or s.get("id")
                for s in sensor_data.get("sensors", [])
                if isinstance(s, dict) and (s.get("device_id") or s.get("deviceId") or s.get("id"))
            )),
            "window_start": start_date + "T00:00:00+00:00",
            "window_end": end_date + "T23:59:59+00:00",
        })

        l0_input = Layer0RunnerInput(
            plot_id=plot_id,
            geometry_hash=inputs.geometry_hash,
            geometry_version=1,
            start_date=start_date,
            end_date=end_date,
            sentinel2_packages=s2_packages,
            sentinel1_packages=s1_packages,
            environment_package=env_package,
            sensor_package=sensor_package,
        )

        stage_started = time.perf_counter()
        l0_runner = Layer0Runner()
        l0_output = l0_runner.run(l0_input)
        stage_timings_ms["layer0_state_construction"] = round((time.perf_counter() - stage_started) * 1000.0, 3)

        if l0_output is not None:
            # Default everything to empty list
            l0_output.layer0_source_packages["asmae_sentinel2_real"] = []
            l0_output.layer0_source_packages["experimental_s2_proxy"] = []
            l0_output.layer0_source_packages["asmae_sentinel1_real"] = []
            l0_output.layer0_source_packages["experimental_s1_proxy"] = []

            s2_telemetry_status = "ok"
            s2_telemetry_reason = None
            s1_telemetry_status = "ok"
            s1_telemetry_reason = None

            if asmae_enabled:
                from layer0.providers.asmae_scene_fetcher import (
                    fetch_experimental_composite_s2_stack,
                    fetch_experimental_composite_s1_stack
                )
                
                # Sentinel-2 injection
                if s2_res is not None:
                    if isinstance(s2_res, dict) and s2_res.get("status") == "unavailable":
                        s2_telemetry_status = "unavailable"
                        s2_telemetry_reason = s2_res.get("reason", "no_scene_found")
                        s2_scenes = fetch_experimental_composite_s2_stack(plot_id, run_id, (start_date, end_date), raster_composites)
                        l0_output.layer0_source_packages["experimental_s2_proxy"] = to_layer0_sentinel2_package({
                            "plot_id": plot_id,
                            "plot_geometry_hash": inputs.geometry_hash or "",
                            "data": [s.to_dict() for s in s2_scenes]
                        })
                    else:
                        l0_output.layer0_source_packages["asmae_sentinel2_real"] = to_layer0_sentinel2_package({
                            "plot_id": plot_id,
                            "plot_geometry_hash": inputs.geometry_hash or "",
                            "data": [s.to_dict() for s in s2_res]
                        })
                else:
                    s2_telemetry_status = "unavailable"
                    s2_telemetry_reason = s2_err_reason or "provider_error"
                    s2_scenes = fetch_experimental_composite_s2_stack(plot_id, run_id, (start_date, end_date), raster_composites)
                    l0_output.layer0_source_packages["experimental_s2_proxy"] = to_layer0_sentinel2_package({
                        "plot_id": plot_id,
                        "plot_geometry_hash": inputs.geometry_hash or "",
                        "data": [s.to_dict() for s in s2_scenes]
                    })

                # Sentinel-1 injection
                if s1_res is not None:
                    if isinstance(s1_res, dict) and s1_res.get("status") == "unavailable":
                        s1_telemetry_status = "unavailable"
                        s1_telemetry_reason = s1_res.get("reason", "no_scene_found")
                        s1_scenes = fetch_experimental_composite_s1_stack(plot_id, run_id, (start_date, end_date), raster_composites)
                        l0_output.layer0_source_packages["experimental_s1_proxy"] = to_layer0_sentinel1_package({
                            "plot_id": plot_id,
                            "plot_geometry_hash": inputs.geometry_hash or "",
                            "data": [s.to_dict() for s in s1_scenes]
                        })
                    else:
                        l0_output.layer0_source_packages["asmae_sentinel1_real"] = to_layer0_sentinel1_package({
                            "plot_id": plot_id,
                            "plot_geometry_hash": inputs.geometry_hash or "",
                            "data": [s.to_dict() for s in s1_res]
                        })
                else:
                    s1_telemetry_status = "unavailable"
                    s1_telemetry_reason = s1_err_reason or "provider_error"
                    s1_scenes = fetch_experimental_composite_s1_stack(plot_id, run_id, (start_date, end_date), raster_composites)
                    l0_output.layer0_source_packages["experimental_s1_proxy"] = to_layer0_sentinel1_package({
                        "plot_id": plot_id,
                        "plot_geometry_hash": inputs.geometry_hash or "",
                        "data": [s.to_dict() for s in s1_scenes]
                    })

            # Ensure all values inside layer0_source_packages are strictly lists
            if l0_output.layer0_source_packages:
                for k, v in list(l0_output.layer0_source_packages.items()):
                    if v is None:
                        l0_output.layer0_source_packages[k] = []
                    elif not isinstance(v, list):
                        l0_output.layer0_source_packages[k] = [v]

            l0_output.metadata["asmae_scene_fetch_telemetry"] = {
                "contract_version": "asmae_scene_fetch_telemetry_v2",
                "requested_window": {
                    "start": str(start_date), "end": str(end_date),
                },
                "s2": {
                    "status": (
                        "available" if isinstance(s2_res, list) and len(s2_res) >= 3
                        else "partial" if isinstance(s2_res, list) and s2_res
                        else s2_telemetry_status
                    ),
                    "reason": (
                        "insufficient_independent_scenes"
                        if isinstance(s2_res, list) and 0 < len(s2_res) < 3
                        else s2_telemetry_reason
                    ),
                    "real_scene_count": len(s2_res) if isinstance(s2_res, list) else 0,
                    "minimum_scene_count": 3,
                    "credentials_configured": bool(
                        os.environ.get("SENTINEL_HUB_CLIENT_ID")
                        and os.environ.get("SENTINEL_HUB_CLIENT_SECRET")
                    ),
                },
                "s1": {
                    "status": (
                        "available" if isinstance(s1_res, list) and len(s1_res) >= 2
                        else "partial" if isinstance(s1_res, list) and s1_res
                        else s1_telemetry_status
                    ),
                    "reason": (
                        "insufficient_independent_scenes"
                        if isinstance(s1_res, list) and 0 < len(s1_res) < 2
                        else s1_telemetry_reason
                    ),
                    "real_scene_count": len(s1_res) if isinstance(s1_res, list) else 0,
                    "minimum_scene_count": 2,
                    "credentials_configured": bool(
                        os.environ.get("SENTINEL_HUB_CLIENT_ID")
                        and os.environ.get("SENTINEL_HUB_CLIENT_SECRET")
                    ),
                },
            }
            stage_timings_ms["pre_layer1_total"] = round((time.perf_counter() - request_started) * 1000.0, 3)
            l0_output.metadata["stage_timings_ms"] = stage_timings_ms
    except Exception as e:
        primary_acquisition = "legacy_fallback"
        fallback_used = True
        fallback_reason = f"Layer0Runner failed: {str(e)}"
        logger.warning(f"Layer0Runner execution failed: {e}. Falling back to legacy data fusion.")
        l0_output = None
        raster_composites = {}
        
    # --- Layer 1 coarse pass (ASMAE input contract) ---
    # ASMAE consumes coarse evidence; the refined Layer 1 pass still runs
    # below after ASMAE and is the only pass published in `results`.
    op_ctx = inputs.operational_context or {}
    l1_coarse_context = None
    l1_coarse_output = None
    coarse_evidence_priors = {}
    coarse_weather: List[Any] = []
    try:
        l1_coarse_record = {
            "requested": False,
            "status": "skipped",
            "reason": "coarse_pass_before_asmae",
            "mode": "coarse_pass",
            "run_id": None,
            "error": None,
        }
        l1_coarse_res = _safe_run(
            LayerId.L1,
            inputs,
            l0_output,
            raster_composites,
            None,
            l1_coarse_record,
            progress_cb=None,
        )
        if l1_coarse_res.status == LayerStatus.OK and l1_coarse_res.output:
            l1_coarse_output = l1_coarse_res.output
            l1_coarse_context = getattr(l1_coarse_res.output, "_context_package", None)
            from layer05_asmae.priors.coarse_context import build_coarse_layer_outputs
            coarse_env_pkg = (
                (l0_output.layer0_source_packages.get("environment") or [None])[0]
                if l0_output else None
            )
            coarse_weather = _weather_records_from_source_package(coarse_env_pkg)
            coarse_evidence_priors = build_coarse_layer_outputs(
                l1_coarse_output,
                crop_context=inputs.crop_config or {},
                weather_records=coarse_weather,
                management_events=op_ctx.get("management_events", []),
            )
            coarse_evidence_priors.update(
                op_ctx.get("coarse_evidence_priors")
                or op_ctx.get("coarse_layer_outputs", {})
            )
    except Exception as coarse_exc:
        logger.warning("Layer 1 coarse pass unavailable before ASMAE: %s", coarse_exc)

    # --- Canonical crop posterior pass A (pre-ASMAE) ---
    # This pass consumes only admitted, content-distinct L0 observations. The
    # filled Layer 1 daily curve is intentionally not treated as new evidence.
    coarse_soil = (
        getattr(l1_coarse_output, "static", {})
        if l1_coarse_output is not None else {}
    ) or op_ctx.get("soil_context", {})
    crop_pre_posterior: Dict[str, Any] = {}
    crop_worldline_event_id = None
    phenology_worldline_event_id = None
    canonical_worldline = None
    asmae_scientific_run_id = run_id
    crop_influence_manifest: Dict[str, Any] = {}
    crop_config_for_observations = inputs.crop_config or {}
    reintegration_evidence_replay = (
        op_ctx.get("asmae_worker_reintegration") is True
    )
    canonical_temporal_records = _canonical_crop_temporal_records(
        l0_output,
        plot_geometry=(
            op_ctx.get("polygon_geojson")
            or op_ctx.get("polygon_coords")
            or op_ctx.get("geometry")
        ),
        geometry_hash=inputs.geometry_hash or "",
        # Operational plot polygons are stored as RFC 7946/WGS84 coordinates.
        # Passing the declaration explicitly also covers the legacy bare-ring
        # representation, which carries no embedded CRS metadata.
        plot_geometry_crs=(
            op_ctx.get("polygon_crs")
            or op_ctx.get("geometry_crs")
            or "EPSG:4326"
        ),
        plot_namespace={
            "tenant_id": inputs.tenant_id,
            "farm_id": inputs.farm_id,
            "plot_id": inputs.plot_id,
        },
        crop_cycle_id=(
            crop_config_for_observations.get("crop_cycle_id")
            or op_ctx.get("crop_cycle_id")
        ),
        weather_records=coarse_weather,
        season_start=(
            crop_config_for_observations.get("planting_date")
            or crop_config_for_observations.get("plantingDate")
            or crop_config_for_observations.get("start_date")
            or crop_config_for_observations.get("startDate")
        ),
    )
    crop_evidence_ledger_payload: Dict[str, Any] = {}
    try:
        from services.agribrain.layer2_veg_int.crop_observations import (
            build_crop_evidence_ledger,
        )
        crop_evidence_ledger_payload = build_crop_evidence_ledger(
            canonical_temporal_records,
            plot_namespace=inputs.plot_namespace,
        ).to_dict()
        crop_config_for_observations = {
            **crop_config_for_observations,
            "crop_evidence_ledger": crop_evidence_ledger_payload,
            "crop_evidence_ledger_hash": crop_evidence_ledger_payload.get(
                "ledger_hash"
            ),
        }
        inputs = replace(
            inputs,
            crop_config=crop_config_for_observations,
        )
    except Exception as crop_ledger_exc:
        # Crop inference can still publish an unavailable/prior-only state, but
        # it cannot claim physical EO support without a verified ledger.
        logger.exception(
            "Canonical crop evidence ledger construction failed: %s",
            crop_ledger_exc,
        )
    try:
        from services.agribrain.layer2_veg_int.crop_posterior import (
            condition_crop_context,
            infer_crop_posterior,
        )
        from services.agribrain.orchestrator_v2.pre_asmae_layer2a import (
            commit_crop_posterior_worldline,
            load_latest_crop_posterior,
        )
        from services.agribrain.world_model.canonical_worldline import (
            CanonicalWorldlineService,
        )

        canonical_worldline = CanonicalWorldlineService()
        if reintegration_evidence_replay:
            replay_lineage = str(
                op_ctx.get("asmae_replay_crop_posterior_lineage") or ""
            )
            crop_pre_posterior = _load_frozen_reintegration_event(
                canonical_worldline,
                inputs=inputs,
                event_id=str(
                    op_ctx.get("asmae_replay_crop_worldline_event_id") or ""
                ),
                event_type="CROP_POSTERIOR",
                payload_key="crop_posterior",
                expected_content_hash=replay_lineage,
                rehydrate_generated_at=True,
            )
            declared_replay = op_ctx.get("asmae_replay_crop_posterior")
            if (
                not isinstance(declared_replay, dict)
                or not _worldline_scientific_payload_matches(
                    declared_replay, crop_pre_posterior
                )
            ):
                raise ValueError("frozen crop posterior payload mismatch")
            replay_lineage_id = str(
                op_ctx.get("asmae_replay_crop_lineage_id") or ""
            )
            if (
                replay_lineage_id
                and str(crop_pre_posterior.get("lineage_id") or "")
                != replay_lineage_id
            ):
                raise ValueError("frozen crop posterior lineage ID mismatch")
            crop_worldline_event_id = str(
                op_ctx.get("asmae_replay_crop_worldline_event_id") or ""
            )
            replay_ledger = op_ctx.get("asmae_replay_crop_evidence_ledger")
            replay_ledger = (
                dict(replay_ledger) if isinstance(replay_ledger, dict) else {}
            )
            expected_ledger_hash = str(
                op_ctx.get("asmae_replay_crop_evidence_ledger_hash") or ""
            )
            if (
                not replay_ledger
                or str(replay_ledger.get("ledger_hash") or "")
                != expected_ledger_hash
                or str(crop_pre_posterior.get("crop_evidence_ledger_hash") or "")
                != expected_ledger_hash
            ):
                raise ValueError("frozen crop evidence ledger mismatch")
            crop_evidence_ledger_payload = replay_ledger
            crop_config_for_observations = {
                **(inputs.crop_config or {}),
                "crop_evidence_ledger": replay_ledger,
                "crop_evidence_ledger_hash": expected_ledger_hash,
            }
            inputs = replace(
                inputs,
                crop_config=crop_config_for_observations,
            )
        else:
            previous_crop_posterior = load_latest_crop_posterior(
                canonical_worldline,
                plot_namespace=inputs.plot_namespace,
            )
            crop_operational = _crop_operational_context(
                op_ctx,
                weather_records=coarse_weather,
                soil_context=coarse_soil,
            )
            crop_operational.update({
                "crop_evidence_ledger": crop_evidence_ledger_payload,
                "crop_evidence_ledger_hash": crop_evidence_ledger_payload.get(
                    "ledger_hash"
                ),
            })
            crop_pre_posterior = infer_crop_posterior(
                plot_id=inputs.plot_id,
                run_id=run_id,
                plot_timeseries=canonical_temporal_records,
                crop_config=inputs.crop_config or {},
                operational_context=crop_operational,
                archive_context={
                    **dict(op_ctx.get("crop_archive_context") or {}),
                    "previous_crop_posterior": previous_crop_posterior or {},
                    "previous_crops": (
                        op_ctx.get("previous_crops")
                        or op_ctx.get("crop_rotation")
                        or []
                    ),
                },
            )
        conditioned_crop = condition_crop_context(
            inputs.crop_config or {}, crop_pre_posterior
        )
        inputs = replace(inputs, crop_config=conditioned_crop)
        crop_pre_time = str(
            crop_pre_posterior.get("generated_at") or ""
        ).strip()
        crop_pre_authority = str(
            crop_pre_posterior.get("authority") or ""
        ).strip()
        if not crop_pre_time:
            raise ValueError("pre-ASMAE crop posterior has no generated_at")
        if not crop_pre_authority:
            raise ValueError("pre-ASMAE crop posterior has no authority")
        if not reintegration_evidence_replay:
            crop_event = commit_crop_posterior_worldline(
                canonical_worldline,
                plot_namespace=inputs.plot_namespace,
                crop_posterior=crop_pre_posterior,
                geometry_version=inputs.geometry_hash or "UNKNOWN_GEO",
                effective_at=crop_pre_time,
                observation_or_valid_time=(
                    crop_pre_posterior.get("observation_or_valid_time")
                    or crop_pre_posterior.get("as_of")
                    or crop_pre_time
                ),
                parent_orchestrator_run_id=run_id,
                pass_name="PRE_ASMAE",
            )
            crop_worldline_event_id = crop_event.get("event_id")
        asmae_scientific_run_id = "AGB2-ASMAE-" + hashlib.sha256(
            (
                run_id
                + ":" + str(crop_pre_posterior.get("content_hash", ""))
            ).encode("utf-8")
        ).hexdigest()[:24]
        from services.agribrain.scientific_contracts.crop_governance import (
            CropInfluenceManifestV1,
        )
        if reintegration_evidence_replay:
            replay_manifest = op_ctx.get(
                "asmae_replay_crop_influence_manifest"
            )
            crop_influence_manifest = (
                dict(replay_manifest)
                if isinstance(replay_manifest, dict) else {}
            )
            expected_manifest_hash = str(
                op_ctx.get("asmae_replay_crop_influence_manifest_hash") or ""
            )
            if (
                not crop_influence_manifest
                or crop_influence_manifest.get("content_hash")
                != expected_manifest_hash
                or crop_influence_manifest.get("crop_posterior_parent_hash")
                != crop_pre_posterior.get("content_hash")
            ):
                raise ValueError("frozen crop influence manifest mismatch")
        else:
            crop_source_ids = _crop_influence_evidence_ids(
                canonical_temporal_records, independent_only=False,
            )
            # Independence is owned by the verified crop-evidence ledger.  Do not
            # reconstruct it from legacy temporal flags: provider daily statistics
            # can be usable by temporal consumers without representing independent
            # physical acquisitions.
            crop_independent_ids = _crop_ledger_independent_evidence_ids(
                crop_evidence_ledger_payload
            )
            crop_influence_manifest = CropInfluenceManifestV1(
                namespace=inputs.plot_namespace,
                crop_cycle_id=(
                    crop_config_for_observations.get("crop_cycle_id")
                    or op_ctx.get("crop_cycle_id")
                ),
                independent_evidence_ids=crop_independent_ids,
                # These are the physical observations in the Layer-0 stack being
                # handed to ASMAE, not a second independent evidence collection.
                asmae_source_observation_ids=crop_source_ids,
                dependent_refinement_features=(),
                maximum_allowed_posterior_influence=0.15,
                actual_posterior_change=0.0,
                lineage_parent_id=str(
                    crop_pre_posterior.get("lineage_id")
                    or crop_pre_posterior.get("content_hash")
                ),
                lineage_child_id=None,
                crop_posterior_parent_hash=str(
                    crop_pre_posterior.get("content_hash") or ""
                ),
                crop_posterior_child_hash="",
                asmae_run_id=asmae_scientific_run_id,
                child_asmae_run_scheduled=False,
                refinement_iteration=0,
            ).to_dict()
    except Exception as crop_exc:
        if reintegration_evidence_replay:
            raise RuntimeError(
                "exact crop evidence replay failed"
            ) from crop_exc
        logger.exception(
            "Canonical pre-ASMAE crop posterior failed: %s", crop_exc
        )

    # --- Canonical Layer 2A crop/phenology pass (pre-ASMAE) ---
    # This pass is deliberately built from the verified ledger's selected
    # physical representatives. Generic/fill-interpolated Layer 1 rows cannot
    # become additional crop evidence through this seam.
    pre_asmae_layer2a_context: Dict[str, Any] = {
        "pre_asmae_layer2a_status": "unavailable",
        "pre_asmae_layer2a_reason": "not_attempted",
    }
    previous_phenology_event = None
    try:
        if l1_coarse_output is None:
            raise ValueError("coarse Layer 1 tensor is unavailable")
        from services.agribrain.orchestrator_v2.pre_asmae_layer2a import (
            build_pre_asmae_layer2a_input,
            commit_phenology_posterior_worldline,
            load_latest_crop_phenology_event,
            run_pre_asmae_layer2a,
            PHENOLOGY_POSTERIOR_EVENT_TYPE,
        )
        from services.agribrain.world_model.canonical_worldline import (
            CanonicalWorldlineService,
        )

        canonical_worldline = canonical_worldline or CanonicalWorldlineService()
        if reintegration_evidence_replay:
            phenology_worldline_event_id = str(
                op_ctx.get("asmae_replay_phenology_worldline_event_id") or ""
            )
            expected_phenology_hash = str(
                op_ctx.get("asmae_replay_phenology_posterior_hash") or ""
            )
            canonical_phenology = _load_frozen_reintegration_event(
                canonical_worldline,
                inputs=inputs,
                event_id=phenology_worldline_event_id,
                event_type=PHENOLOGY_POSTERIOR_EVENT_TYPE,
                payload_key="phenology_posterior",
                expected_content_hash=expected_phenology_hash,
            )
            declared_phenology = op_ctx.get(
                "asmae_replay_phenology_posterior"
            )
            if (
                not isinstance(declared_phenology, dict)
                or not _worldline_scientific_payload_matches(
                    declared_phenology, canonical_phenology
                )
            ):
                raise ValueError("frozen phenology posterior payload mismatch")
            inputs = replace(
                inputs,
                crop_config={
                    **(inputs.crop_config or {}),
                    "previous_phenology_event_id": phenology_worldline_event_id,
                },
            )
            replay_layer2a = op_ctx.get(
                "asmae_replay_pre_asmae_layer2a_context"
            )
            pre_asmae_layer2a_context = (
                dict(replay_layer2a)
                if isinstance(replay_layer2a, dict) else {}
            )
            pre_asmae_layer2a_context.update({
                "pre_asmae_layer2a_status": (
                    pre_asmae_layer2a_context.get(
                        "pre_asmae_layer2a_status"
                    ) or "available"
                ),
                "phenology_posterior": canonical_phenology,
                "phenology_posterior_hash": expected_phenology_hash,
                "phenology_worldline_event_id": phenology_worldline_event_id,
                "evidence_replay": "exact_frozen_worldline_event",
            })
        else:
            previous_phenology_event = load_latest_crop_phenology_event(
                canonical_worldline,
                plot_namespace=inputs.plot_namespace,
                event_type=PHENOLOGY_POSTERIOR_EVENT_TYPE,
            )
            if previous_phenology_event:
                inputs = replace(
                    inputs,
                    crop_config={
                        **(inputs.crop_config or {}),
                        "previous_phenology_event_id": previous_phenology_event.get(
                            "event_id"
                        ),
                    },
                )
            layer2a_bundle = build_pre_asmae_layer2a_input(
                inputs,
                l1_coarse_output,
                weather_records=coarse_weather,
            )
            layer2a_result = run_pre_asmae_layer2a(layer2a_bundle)
            inputs = layer2a_result.bundle.inputs
            pre_asmae_layer2a_context = dict(layer2a_result.asmae_context)
            canonical_phenology = pre_asmae_layer2a_context.get(
                "phenology_posterior"
            )
            if isinstance(canonical_phenology, dict) and canonical_phenology.get(
                "content_hash"
            ):
                phenology_time = str(
                    canonical_phenology.get("effective_at")
                    or canonical_phenology.get("generated_at")
                    or ""
                ).strip()
                if not phenology_time:
                    raise ValueError(
                        "pre-ASMAE phenology posterior has no effective_at"
                    )
                phenology_event = commit_phenology_posterior_worldline(
                    canonical_worldline,
                    plot_namespace=inputs.plot_namespace,
                    phenology_posterior=canonical_phenology,
                    geometry_version=inputs.geometry_hash or "UNKNOWN_GEO",
                    effective_at=phenology_time,
                    observation_or_valid_time=phenology_time,
                    parent_event_ids=(
                        (crop_worldline_event_id,)
                        if crop_worldline_event_id else ()
                    ),
                    parent_orchestrator_run_id=run_id,
                )
                phenology_worldline_event_id = phenology_event.get("event_id")
                pre_asmae_layer2a_context[
                    "phenology_worldline_event_id"
                ] = phenology_worldline_event_id
    except Exception as layer2a_exc:
        if reintegration_evidence_replay:
            raise RuntimeError(
                "exact phenology evidence replay failed"
            ) from layer2a_exc
        can_reuse_as_of = (
            previous_phenology_event is not None
            and "requires admitted physical evidence" in str(layer2a_exc)
        )
        if can_reuse_as_of:
            try:
                pre_asmae_layer2a_context = _freeze_previous_phenology_event(
                    previous_phenology_event,
                    as_of=(inputs.date_range or {}).get("end"),
                )
                phenology_worldline_event_id = pre_asmae_layer2a_context[
                    "phenology_worldline_event_id"
                ]
                logger.info(
                    "Pre-ASMAE Layer 2A reused exact canonical phenology event %s",
                    phenology_worldline_event_id,
                )
            except Exception as reuse_exc:
                pre_asmae_layer2a_context = {
                    "pre_asmae_layer2a_status": "unavailable",
                    "pre_asmae_layer2a_reason": str(reuse_exc),
                }
                logger.exception(
                    "Canonical phenology fallback failed: %s", reuse_exc
                )
        else:
            pre_asmae_layer2a_context = {
                "pre_asmae_layer2a_status": "unavailable",
                "pre_asmae_layer2a_reason": str(layer2a_exc),
            }
            logger.exception(
                "Canonical pre-ASMAE Layer 2A pass failed: %s", layer2a_exc
            )

    # --- ASMAE Execution ---
    asmae_output = None
    asmae_submission_context = None
    asmae_run_record = {
        "requested": True,
        "status": "skipped",
        "reason": "not_started",
        "mode": "quick_visual",
        "run_id": None,
        "error": None
    }
    
    asmae_mode = op_ctx.get("asmae_mode", "quick_visual")
    if asmae_mode not in ("quick_visual", "standard"):
        asmae_mode = "quick_visual"
        
    try:
        from layer05_asmae.runner import ASMAERunner
        from layer05_asmae.reintegration import REINTEGRATION_CONTRACT_VERSION
        asmae_runner = ASMAERunner()

        if not str(crop_worldline_event_id or "").strip():
            raise ValueError(
                "ASMAE submission requires an exact crop worldline event"
            )
        if not str(phenology_worldline_event_id or "").strip():
            raise ValueError(
                "ASMAE submission requires an exact phenology worldline event"
            )
        
        if asmae_runner.is_enabled(inputs.plot_id):
            if asmae_mode == "quick_visual":
                # Build strict ASMAEInput context structure
                s2_pkgs = l0_output.layer0_source_packages.get("sentinel2", []) if l0_output else []
                archive_refs = [getattr(pkg.metadata, "scene_id", "") for pkg in s2_pkgs if hasattr(pkg, "metadata")]
                env_pkg = (l0_output.layer0_source_packages.get("environment") or [None])[0] if l0_output else None
                weather_context = _weather_records_from_source_package(env_pkg)

                from layer05_asmae.history.archive_metrics_store import ArchiveMetricsStore
                metrics_store = ArchiveMetricsStore()
                info = metrics_store.get_latest_metrics_info(inputs.plot_id)
                
                archive_metrics = {}
                archive_baselines = {}
                archive_bma = {}
                retrovalidation_residuals = {}
                phenology_envelopes = {}
                archive_metrics_hash = None
                archive_metrics_status = "unavailable"
                archive_posterior = {}
                
                if info is not None:
                    data = info.get("data", {})
                    archive_metrics = data.get("historical_metrics", {})
                    archive_baselines = data.get("baseline_metrics", {})
                    archive_bma = data.get("archive_bma_metrics", {})
                    retrovalidation_residuals = data.get("retrovalidation_metrics", {})
                    phenology_envelopes = archive_baselines.get("phenology_envelopes", {}) or archive_metrics.get("phenology_envelopes", {})
                    archive_metrics_hash = info.get("archive_metrics_hash")
                    archive_metrics_status = "available"
                    archive_posterior = data.get("archive_posterior", {})

                coarse_timeseries = (
                    canonical_temporal_records
                    or op_ctx.get("plot_timeseries", [])
                )

                def _to_date_str(d) -> str:
                    if isinstance(d, str):
                        return d
                    if hasattr(d, "isoformat"):
                        return d.isoformat()
                    return str(d)

                asmae_context = {
                    "plot_namespace": namespace_payload(inputs.plot_namespace),
                    "tenant_id": inputs.tenant_id,
                    "farm_id": inputs.farm_id,
                    "plot_id": inputs.plot_id,
                    "worldline_namespace": inputs.farm_id,
                    "polygon_geojson": op_ctx.get("polygon_coords") or {},
                    "geometry_hash": inputs.geometry_hash or "",
                    "start_date": _to_date_str(start_date),
                    "end_date": _to_date_str(end_date),
                    "layer0_source_packages": {
                        **(l0_output.layer0_source_packages if l0_output else {}),
                        "asmae_sentinel2_raw": s2_packages,
                        "asmae_sentinel1_raw": s1_packages,
                    },
                    "layer0_state_package": l0_output.layer0_state_package if l0_output else None,
                    "raster_composites": raster_composites,
                    "layer1_context_package": l1_coarse_context,
                    "plot_timeseries": coarse_timeseries,
                    "soil_context": coarse_soil,
                    "coarse_evidence_priors": coarse_evidence_priors,
                    # Compatibility alias for the current ASMAE schema.
                    "coarse_layer_outputs": coarse_evidence_priors,
                    "crop_context": inputs.crop_config or {},
                    "crop_posterior": crop_pre_posterior,
                    "crop_evidence_ledger": crop_evidence_ledger_payload,
                    "crop_evidence_ledger_hash": crop_evidence_ledger_payload.get(
                        "ledger_hash"
                    ),
                    "crop_posterior_lineage": crop_pre_posterior.get(
                        "content_hash"
                    ),
                    "crop_lineage_id": crop_pre_posterior.get(
                        "lineage_id"
                    ),
                    "crop_worldline_event_id": crop_worldline_event_id,
                    "phenology_worldline_event_id": phenology_worldline_event_id,
                    **pre_asmae_layer2a_context,
                    "crop_influence_manifest": crop_influence_manifest,
                    "crop_influence_manifest_hash": crop_influence_manifest.get(
                        "content_hash"
                    ),
                    "orchestrator_parent_run_id": run_id,
                    "management_events": op_ctx.get("management_events", []),
                    "user_observations": op_ctx.get("user_observations", []),
                    "historical_scene_refs": archive_refs,
                    "historical_scene_records": op_ctx.get(
                        "historical_scene_records", []
                    ),
                    "weather_archive": weather_context,
                    "archive_metrics": archive_metrics,
                    "archive_baselines": archive_baselines,
                    "archive_bma": archive_bma,
                    "retrovalidation_residuals": retrovalidation_residuals,
                    "phenology_envelopes": phenology_envelopes,
                    "archive_metrics_status": archive_metrics_status,
                    "archive_status": archive_metrics_status,
                    "archive_metrics_hash": archive_metrics_hash,
                    "archive_posterior": archive_posterior,
                    "source_policy": op_ctx.get("source_policy"),
                    "asmae_worker_reintegration": bool(
                        op_ctx.get("asmae_worker_reintegration", False)
                    ),
                    "expected_asmae_snapshot_id": op_ctx.get(
                        "expected_asmae_snapshot_id"
                    ),
                    "asmae_scene_fetch_telemetry": (
                        l0_output.metadata.get("asmae_scene_fetch_telemetry")
                        if l0_output and hasattr(l0_output, "metadata") else None
                    ),
                    "orchestrator_reintegration": {
                        "contract_version": REINTEGRATION_CONTRACT_VERSION,
                        "input": _freeze_reintegration_input(inputs),
                        "intent": "UNKNOWN",
                    },
                }
                
                # Execute ASMAERunner
                asmae_submission_context = asmae_context
                asmae_output = asmae_runner.execute(
                    plot_id=inputs.plot_id,
                    run_id=asmae_scientific_run_id,
                    context=asmae_context,
                    mode="quick_visual"
                )
                
                status_val = asmae_output.get("status")
                if status_val == "disabled":
                    asmae_run_record = {
                        "requested": True,
                        "status": "skipped",
                        "reason": asmae_output.get("skip_reason", "rollout_disabled"),
                        "mode": "quick_visual",
                        "run_id": None,
                        "error": None
                    }
                elif status_val == "error":
                    asmae_failure_code = str(
                        asmae_output.get("failure_code") or "execution_error"
                    )
                    asmae_run_record = {
                        "requested": True,
                        "status": "failed",
                        "reason": asmae_failure_code,
                        "failure_code": asmae_failure_code,
                        "error": asmae_output.get("reason", "unknown error"),
                        "error_type": asmae_output.get("error_type"),
                    }
                else:
                    cache_key = asmae_output.get("cache_key") or ""
                    asmae_run_record = {
                        "requested": True,
                        "status": "completed",
                        "mode": "quick_visual",
                        "run_id": (
                            asmae_output.get("run_id")
                            or asmae_scientific_run_id
                        ),
                        "output_ref": f"asmae_rasters/raster_{cache_key}.npz" if cache_key else None,
                        "error": None
                    }
            else:
                # Standard mode creates a real durable job record and worker.
                env_pkg = (l0_output.layer0_source_packages.get("environment") or [None])[0] if l0_output else None
                weather_archive = _weather_records_from_source_package(env_pkg)
                from layer05_asmae.history.archive_metrics_store import ArchiveMetricsStore
                info = ArchiveMetricsStore().get_latest_metrics_info(inputs.plot_id)
                archive_data = info.get("data", {}) if info else {}
                coarse_timeseries = (
                    canonical_temporal_records
                    or op_ctx.get("plot_timeseries", [])
                )
                standard_context = {
                    "plot_namespace": namespace_payload(inputs.plot_namespace),
                    "tenant_id": inputs.tenant_id,
                    "farm_id": inputs.farm_id,
                    "plot_id": inputs.plot_id,
                    "worldline_namespace": inputs.farm_id,
                    "polygon_geojson": op_ctx.get("polygon_coords") or {},
                    "geometry_hash": inputs.geometry_hash or "",
                    "start_date": start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date),
                    "end_date": end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date),
                    "layer0_source_packages": l0_output.layer0_source_packages if l0_output else {},
                    "layer0_state_package": l0_output.layer0_state_package if l0_output else None,
                    "raster_composites": raster_composites,
                    "layer1_context_package": l1_coarse_context,
                    "plot_timeseries": coarse_timeseries,
                    "soil_context": coarse_soil,
                    "coarse_evidence_priors": coarse_evidence_priors,
                    # Compatibility alias for the current ASMAE schema.
                    "coarse_layer_outputs": coarse_evidence_priors,
                    "crop_context": inputs.crop_config or {},
                    "crop_posterior": crop_pre_posterior,
                    "crop_evidence_ledger": crop_evidence_ledger_payload,
                    "crop_evidence_ledger_hash": crop_evidence_ledger_payload.get(
                        "ledger_hash"
                    ),
                    "crop_posterior_lineage": crop_pre_posterior.get(
                        "content_hash"
                    ),
                    "crop_lineage_id": crop_pre_posterior.get(
                        "lineage_id"
                    ),
                    "crop_worldline_event_id": crop_worldline_event_id,
                    "phenology_worldline_event_id": phenology_worldline_event_id,
                    **pre_asmae_layer2a_context,
                    "crop_influence_manifest": crop_influence_manifest,
                    "crop_influence_manifest_hash": crop_influence_manifest.get(
                        "content_hash"
                    ),
                    "orchestrator_parent_run_id": run_id,
                    "management_events": op_ctx.get("management_events", []),
                    "user_observations": op_ctx.get("user_observations", []),
                    "weather_archive": weather_archive,
                    "archive_metrics": archive_data.get("historical_metrics", {}),
                    "archive_baselines": archive_data.get("baseline_metrics", {}),
                    "archive_bma": archive_data.get("archive_bma_metrics", {}),
                    "retrovalidation_residuals": archive_data.get("retrovalidation_metrics", {}),
                    "archive_metrics_status": "available" if info else "unavailable",
                    "archive_metrics_hash": info.get("archive_metrics_hash") if info else None,
                    "archive_posterior": archive_data.get("archive_posterior", {}),
                    "historical_scene_records": op_ctx.get(
                        "historical_scene_records", []
                    ),
                    "source_policy": op_ctx.get("source_policy"),
                    "asmae_worker_reintegration": bool(
                        op_ctx.get("asmae_worker_reintegration", False)
                    ),
                    "expected_asmae_snapshot_id": op_ctx.get(
                        "expected_asmae_snapshot_id"
                    ),
                    "asmae_scene_fetch_telemetry": (
                        l0_output.metadata.get("asmae_scene_fetch_telemetry")
                        if l0_output and hasattr(l0_output, "metadata") else None
                    ),
                    "orchestrator_reintegration": {
                        "contract_version": REINTEGRATION_CONTRACT_VERSION,
                        "input": _freeze_reintegration_input(inputs),
                        "intent": "UNKNOWN",
                    },
                }
                asmae_submission_context = standard_context
                job = asmae_runner._run_background_standard_asmae(
                    inputs.plot_namespace, asmae_scientific_run_id, standard_context
                )
                asmae_run_record = {
                    "requested": True,
                    "status": "queued",
                    "reason": None,
                    "mode": "standard",
                    "run_id": job.get("run_id") or asmae_scientific_run_id,
                    "request_lineage_id": job.get("request_lineage_id") or asmae_scientific_run_id,
                    "job_id": job.get("job_id"),
                    "output_ref": job.get("job_ref"),
                    "error": None
                }
        else:
            permissions = asmae_runner.execution_permissions(inputs.plot_id)
            if not inputs.plot_id or not str(inputs.plot_id).strip():
                asmae_skip_reason = "empty_or_missing_plot_id"
            elif permissions.get("emergency_kill_active"):
                asmae_skip_reason = "global_emergency_kill_switch"
            else:
                asmae_skip_reason = "compute_permission_denied"
            asmae_run_record = {
                "requested": True,
                "status": "skipped",
                "reason": asmae_skip_reason,
                "mode": "quick_visual",
                "run_id": None,
                "error": None
            }
    except Exception as e:
        logger.error(f"Error running ASMAERunner in orchestrator: {e}", exc_info=True)
        asmae_run_record = {
            "requested": True,
            "status": "failed",
            "reason": "execution_error",
            "error": str(e)
        }

    # --- Layer 1 ---
    # Pass l0_output, raster_composites, asmae_output, and asmae_run_record into run_layer1_fusion
    l1_res = _safe_run(
        LayerId.L1,
        inputs,
        l0_output,
        raster_composites,
        asmae_output,
        asmae_run_record,
        progress_cb=progress_cb
    )
    results[LayerId.L1] = l1_res

    # Check if modern Layer 1 was active and succeeded
    v1_active = False
    if l1_res.status == LayerStatus.OK and l1_res.output:
        v1_active = hasattr(l1_res.output, "_context_package") and l1_res.output._context_package is not None

    if not v1_active or fallback_used:
        primary_acquisition = "legacy_fallback"
        fallback_used = True
        if not fallback_reason:
            fallback_reason = "Layer 1 V1 engine execution failed internally."
    else:
        # Modern path succeeded! Run downstream validations / assertions
        l1_context = getattr(l1_res.output, "_context_package", None)
        if l1_context is None:
            raise RuntimeError("l1_context is None on successful modern path!")
        if getattr(l1_context, "evidence_items", None) is None:
            raise RuntimeError("l1_context.evidence_items is None on successful modern path!")
    
    if l1_res.status == LayerStatus.FAILED:
        return _finalize_artifact(run_id, ts_now, inputs, results, store, primary_acquisition="legacy_fallback", fallback_used=True, fallback_reason="Layer 1 execution failed completely.")

    # --- Intent Gating ---
    # If DATA_QUERY, skip everything else (L2-L6). 
    # L1 contains Weather, NDVI, SAR Raw Data which is sufficient for "How much rain?" or "Show me NDVI".
    if intent == Intent.DATA_QUERY:
        return _finalize_artifact(run_id, ts_now, inputs, results, store, primary_acquisition=primary_acquisition, fallback_used=fallback_used, fallback_reason=fallback_reason)

    # --- Canonical crop posterior pass B (post-ASMAE) ---
    # ASMAE feedback is dependent on pass-A evidence, so refinement is bounded
    # and allowed only when the ASMAE artifact carries the same crop lineage.
    crop_final_posterior = crop_pre_posterior
    crop_refinement_status = (
        "skipped_exact_reintegration_replay"
        if reintegration_evidence_replay else "not_attempted"
    )
    if crop_pre_posterior and not reintegration_evidence_replay:
        try:
            from services.agribrain.layer2_veg_int.crop_posterior import (
                condition_crop_context,
                refine_crop_posterior,
            )
            from services.agribrain.orchestrator_v2.pre_asmae_layer2a import (
                commit_crop_posterior_worldline,
            )
            from services.agribrain.world_model.canonical_worldline import (
                CanonicalWorldlineService,
            )
            plot_state = (
                dict(asmae_output.get("plot_state_artifact") or {})
                if isinstance(asmae_output, dict) else {}
            )
            output_crop_lineage = (
                asmae_output.get("crop_posterior_lineage")
                if isinstance(asmae_output, dict) else None
            )
            output_influence_hash = (
                asmae_output.get("crop_influence_manifest_hash")
                if isinstance(asmae_output, dict) else None
            )
            lineage_matches = (
                bool(plot_state)
                and output_crop_lineage
                == crop_pre_posterior.get("content_hash")
                and bool(crop_influence_manifest.get("content_hash"))
                and output_influence_hash
                == crop_influence_manifest.get("content_hash")
            )
            if lineage_matches:
                crop_final_posterior = refine_crop_posterior(
                    crop_pre_posterior,
                    plot_state,
                    parent_run_id=run_id,
                    material_change_threshold=float(
                        op_ctx.get(
                            "crop_refinement_material_threshold", 0.10
                        )
                    ),
                )
                crop_refinement_status = str(
                    crop_final_posterior.get(
                        "refinement_status", "completed"
                    )
                )
            else:
                # A skipped pass must not mutate a scientific object after its
                # content hash was calculated. Keep the pass-A posterior
                # byte-for-byte authoritative and report evaluation status in
                # the orchestration envelope instead.
                crop_refinement_status = (
                    "skipped_no_plot_state"
                    if not plot_state
                    else "skipped_crop_lineage_mismatch"
                )
            inputs = replace(
                inputs,
                crop_config=condition_crop_context(
                    inputs.crop_config or {}, crop_final_posterior
                ),
            )
            canonical_worldline = (
                canonical_worldline or CanonicalWorldlineService()
            )
            crop_final_time = str(
                crop_final_posterior.get("generated_at") or ""
            ).strip()
            crop_final_authority = str(
                crop_final_posterior.get("authority") or ""
            ).strip()
            if not crop_final_time:
                raise ValueError(
                    "post-ASMAE crop posterior has no generated_at"
                )
            if not crop_final_authority:
                raise ValueError(
                    "post-ASMAE crop posterior has no authority"
                )
            from services.agribrain.scientific_contracts.crop_governance import (
                CropInfluenceManifestV1,
            )
            dependent_features = tuple(
                key for key in ("structure", "phenology_progress", "vigor")
                if isinstance(
                    dict(plot_state.get("posterior") or {}).get(key), dict
                )
            ) if lineage_matches else ()
            parent_posterior_hash = str(
                crop_pre_posterior.get("content_hash") or ""
            )
            final_posterior_hash = str(
                crop_final_posterior.get("content_hash") or ""
            )
            crop_influence_manifest = CropInfluenceManifestV1(
                namespace=inputs.plot_namespace,
                crop_cycle_id=(
                    crop_config_for_observations.get("crop_cycle_id")
                    or op_ctx.get("crop_cycle_id")
                ),
                independent_evidence_ids=tuple(
                    crop_influence_manifest.get(
                        "independent_evidence_ids", ()
                    )
                ),
                asmae_source_observation_ids=tuple(
                    crop_influence_manifest.get(
                        "asmae_source_observation_ids", ()
                    )
                ),
                dependent_refinement_features=dependent_features,
                maximum_allowed_posterior_influence=float(
                    crop_final_posterior.get(
                        "dependent_feedback_weight_cap", 0.15
                    )
                ),
                actual_posterior_change=float(
                    crop_final_posterior.get(
                        "posterior_change_total_variation", 0.0
                    )
                ),
                lineage_parent_id=parent_posterior_hash,
                lineage_child_id=(
                    final_posterior_hash
                    if final_posterior_hash != parent_posterior_hash
                    else None
                ),
                crop_posterior_parent_hash=parent_posterior_hash,
                crop_posterior_child_hash=(
                    final_posterior_hash
                    if final_posterior_hash != parent_posterior_hash
                    else ""
                ),
                asmae_run_id=(
                    asmae_run_record.get("run_id")
                    or asmae_scientific_run_id
                ),
                child_asmae_run_scheduled=False,
                refinement_iteration=0,
            ).to_dict()
            # An evaluation with no independently materialized posterior must
            # not advance the scientific CROP_POSTERIOR head. Only a verified
            # lineage-changing refinement is committed canonically.
            if lineage_matches and final_posterior_hash != parent_posterior_hash:
                final_crop_event = commit_crop_posterior_worldline(
                    canonical_worldline,
                    plot_namespace=inputs.plot_namespace,
                    crop_posterior=crop_final_posterior,
                    geometry_version=inputs.geometry_hash or "UNKNOWN_GEO",
                    effective_at=crop_final_time,
                    observation_or_valid_time=(
                        crop_final_posterior.get("observation_or_valid_time")
                        or crop_final_posterior.get("as_of")
                        or crop_final_time
                    ),
                    parent_event_ids=(
                        (crop_worldline_event_id,)
                        if crop_worldline_event_id else ()
                    ),
                    parent_orchestrator_run_id=run_id,
                    pass_name=str(
                        crop_final_posterior.get("pass") or "POST_ASMAE"
                    ),
                )
                crop_worldline_event_id = final_crop_event.get("event_id")
            if isinstance(asmae_output, dict):
                asmae_output["refined_crop_posterior"] = (
                    crop_final_posterior
                )
                asmae_output["refined_crop_posterior_lineage"] = (
                    crop_final_posterior.get("content_hash")
                )
                asmae_output["refined_crop_lineage_id"] = (
                    crop_final_posterior.get("lineage_id")
                )
                asmae_output["crop_refinement_status"] = (
                    crop_refinement_status
                )
                asmae_output["crop_context_compatible"] = (
                    lineage_matches
                    and crop_final_posterior.get("lineage_id")
                    == crop_pre_posterior.get("lineage_id")
                )
                asmae_output["crop_influence_manifest"] = (
                    crop_influence_manifest
                )
            if (
                crop_final_posterior.get("material_change") is True
                and crop_final_posterior.get("child_run_id")
                and isinstance(asmae_submission_context, dict)
                and not op_ctx.get(
                    "disable_crop_refinement_reschedule", False
                )
            ):
                scheduled_manifest = CropInfluenceManifestV1(
                    namespace=inputs.plot_namespace,
                    crop_cycle_id=crop_influence_manifest.get(
                        "crop_cycle_id"
                    ),
                    independent_evidence_ids=tuple(
                        crop_influence_manifest.get(
                            "independent_evidence_ids", ()
                        )
                    ),
                    asmae_source_observation_ids=tuple(
                        crop_influence_manifest.get(
                            "asmae_source_observation_ids", ()
                        )
                    ),
                    dependent_refinement_features=tuple(
                        crop_influence_manifest.get(
                            "dependent_refinement_features", ()
                        )
                    ),
                    maximum_allowed_posterior_influence=float(
                        crop_influence_manifest[
                            "maximum_allowed_posterior_influence"
                        ]
                    ),
                    actual_posterior_change=float(
                        crop_influence_manifest["actual_posterior_change"]
                    ),
                    lineage_parent_id=str(
                        crop_influence_manifest["lineage_parent_id"]
                    ),
                    lineage_child_id=str(
                        crop_influence_manifest.get("lineage_child_id")
                        or crop_final_posterior["child_run_id"]
                    ),
                    crop_posterior_parent_hash=str(
                        crop_influence_manifest.get(
                            "crop_posterior_parent_hash", ""
                        )
                    ),
                    crop_posterior_child_hash=str(
                        crop_influence_manifest.get(
                            "crop_posterior_child_hash", ""
                        )
                    ),
                    asmae_run_id=str(
                        crop_influence_manifest.get("asmae_run_id") or ""
                    ),
                    child_asmae_run_scheduled=True,
                    refinement_iteration=1,
                ).to_dict()
                refinement_context = dict(asmae_submission_context)
                refinement_context.update({
                    "crop_context": inputs.crop_config or {},
                    "crop_posterior": crop_final_posterior,
                    "crop_posterior_lineage": crop_final_posterior.get(
                        "content_hash"
                    ),
                    "crop_lineage_id": crop_final_posterior.get(
                        "lineage_id"
                    ),
                    "crop_refinement_parent_run_id": (
                        asmae_run_record.get("run_id")
                    ),
                    "is_crop_refinement": True,
                    "crop_influence_manifest": scheduled_manifest,
                    "crop_influence_manifest_hash": scheduled_manifest.get(
                        "content_hash"
                    ),
                })
                refinement_job = (
                    asmae_runner._run_background_standard_asmae(
                        inputs.plot_namespace,
                        crop_final_posterior["child_run_id"],
                        refinement_context,
                    )
                )
                crop_influence_manifest = scheduled_manifest
                if isinstance(asmae_output, dict):
                    asmae_output["crop_influence_manifest"] = (
                        crop_influence_manifest
                    )
                # Job scheduling is operational state. It is deliberately not
                # written as a scientific worldline event before the child
                # run produces and validates a new posterior.
        except Exception as crop_refine_exc:
            logger.exception(
                "Canonical post-ASMAE crop refinement failed: %s",
                crop_refine_exc,
            )
    # --- Layer 2 ---
    l2_res = _safe_run(LayerId.L2, inputs, l1_res.output, progress_cb=progress_cb)
    results[LayerId.L2] = l2_res
    
    if l2_res.status == LayerStatus.FAILED:
        return _finalize_artifact(run_id, ts_now, inputs, results, store, primary_acquisition=primary_acquisition, fallback_used=fallback_used, fallback_reason=fallback_reason)

    # --- Intent Gating (DIAGNOSIS Special Path) ---
    if intent == Intent.DIAGNOSIS:
        # User requested Diagnosis (Pest/Disease/Stress).
        # We Run L1 -> L2 -> L3 -> L4 -> L5. Skip L6/L7/L8.
        l3_res = _safe_run(LayerId.L3, inputs, l1_res.output, l2_res.output, progress_cb=progress_cb)
        results[LayerId.L3] = l3_res
        
        l4_res = _safe_run(LayerId.L4, inputs, l1_res.output, l2_res.output, l3_res.output, progress_cb=progress_cb)
        results[LayerId.L4] = l4_res
        
        l5_res = _safe_run(LayerId.L5, inputs, l1_res.output, l2_res.output, l3_res.output, l4_res.output, progress_cb=progress_cb)
        results[LayerId.L5] = l5_res
        
        # L3-L5 are diagnostic/state contributors on the canonical path.
        # Their legacy action-shaped fields are ignored; L8 is the sole action
        # owner after a full contribution tribunal.
        unified_plan = merge_execution_plans(None, None, None)
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan, primary_acquisition=primary_acquisition, fallback_used=fallback_used, fallback_reason=fallback_reason)

    # --- Layer 3 ---
    l3_res = _safe_run(LayerId.L3, inputs, l1_res.output, l2_res.output, progress_cb=progress_cb)
    results[LayerId.L3] = l3_res
    
    # --- Intent Gating (DECISION) ---
    if intent == Intent.DECISION:
        # User requested Decision (Irrigation/General).
        # L1 -> L2 -> L3 -> L4 -> L5 -> L6. Skip L7/L8.
        l4_res = _safe_run(LayerId.L4, inputs, l1_res.output, l2_res.output, l3_res.output, progress_cb=progress_cb)
        results[LayerId.L4] = l4_res
        
        l5_res = _safe_run(LayerId.L5, inputs, l1_res.output, l2_res.output, l3_res.output, l4_res.output, progress_cb=progress_cb)
        results[LayerId.L5] = l5_res
        
        unified_plan = merge_execution_plans(None, None, None)
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        try:
            from services.agribrain.diagnostic_integration import InfluenceUse
            decision_manifest = _build_diagnostic_integration(
                results, run_id, ts_now, InfluenceUse.PRESCRIPTION_DRIVER,
            )
            decision_entries = (
                decision_manifest.get("influence_manifest", {}).get("entries", [])
            )
        except Exception:
            decision_entries = []
        if decision_entries:
            l6_res = _safe_run(LayerId.L6, inputs, l1_res.output, l2_res.output, l3_res.output, l4_res.output, l5_res.output, progress_cb=progress_cb)
        else:
            l6_res = LayerResult(
                layer_id="L6", status=LayerStatus.DEGRADED, output=None,
                errors=["execution_blocked:prescription_influence_manifest_unavailable"],
            )
        results[LayerId.L6] = l6_res
        
        if l3_res.output: l3_res.output.execution_plan = unified_plan
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan, primary_acquisition=primary_acquisition, fallback_used=fallback_used, fallback_reason=fallback_reason)

    # --- Layer 4 (Nutrients) ---
    l4_res = _safe_run(LayerId.L4, inputs, l1_res.output, l2_res.output, l3_res.output, progress_cb=progress_cb)
    results[LayerId.L4] = l4_res
    
    # --- Intent Gating (NUTRIENT) ---
    if intent == Intent.NUTRIENT:
        # L1 -> L2 -> L3 -> L4.
        unified_plan = merge_execution_plans(None, None, None)
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan, primary_acquisition=primary_acquisition, fallback_used=fallback_used, fallback_reason=fallback_reason)
    
    # --- Intent Gating (PLANNING) ---
    if intent == Intent.PLANNING:
        # User requested season planning / crop suitability
        # Run L1 -> L7. Run L5 ONLY if explicitly asked about disease/risk.
        l5_res = None
        if user_query and any(k in user_query.lower() for k in ["disease", "risk", "fungal", "pest"]):
            l5_res = _safe_run(LayerId.L5, inputs, l1_res.output, None, None, None, progress_cb=progress_cb)
            results[LayerId.L5] = l5_res
        
        # Load chat memory if needed by L7
        from services.agribrain.orchestrator_v2.chat_memory import load_memory
        mem = load_memory(inputs.plot_id)
        
        try:
            from services.agribrain.diagnostic_integration import InfluenceUse
            planning_manifest = _build_diagnostic_integration(
                results, run_id, ts_now, InfluenceUse.PRESCRIPTION_DRIVER,
            )
            planning_entries = (
                planning_manifest.get("influence_manifest", {}).get("entries", [])
            )
        except Exception:
            planning_entries = []
        if planning_entries:
            l7_res = _safe_run(LayerId.L7, inputs, l1_res.output, l5_res.output if l5_res else None, mem, progress_cb=progress_cb)
        else:
            l7_res = LayerResult(
                layer_id="L7", status=LayerStatus.DEGRADED, output=None,
                errors=["planning_blocked:prescription_influence_manifest_unavailable"],
            )
        results[LayerId.L7] = l7_res

        unified_plan = merge_execution_plans(None, None, None)
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan, primary_acquisition=primary_acquisition, fallback_used=fallback_used, fallback_reason=fallback_reason)

    # --- Layer 5 ---
    l5_res = _safe_run(LayerId.L5, inputs, l1_res.output, l2_res.output, l3_res.output, l4_res.output, progress_cb=progress_cb)
    results[LayerId.L5] = l5_res
    
    # --- Full diagnostic ledger and tribunal, before any action consumer ---
    try:
        from services.agribrain.diagnostic_integration import InfluenceUse
        pre_action_diagnostic = _build_diagnostic_integration(
            results, run_id, ts_now, InfluenceUse.PRESCRIPTION_DRIVER,
        )
        pre_action_manifest = pre_action_diagnostic.get("influence_manifest", {})
        pre_action_entries = pre_action_manifest.get("entries", [])
        action_manifest_allowed = bool(
            pre_action_diagnostic.get("status") == "completed"
            and pre_action_manifest.get("requested_use") == "PRESCRIPTION_DRIVER"
            and pre_action_entries
        )
    except Exception as diagnostic_exc:
        logger.warning("Pre-action diagnostic integration failed closed: %s", diagnostic_exc)
        pre_action_diagnostic = {
            "status": "failed_closed",
            "errors": [{"layer_id": "L2-L5", "error": str(diagnostic_exc)}],
        }
        action_manifest_allowed = False

    # Legacy L3/L4/L5 plans are never canonical action inputs.  Keep an empty
    # plan for compatibility while L8 remains gated by the influence manifest.
    unified_plan = merge_execution_plans(None, None, None)
    
    # --- Safety Gating ---
    prov_gq = evaluate_global_quality(results)
    unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
    
    # Patching L3 output for L6 consumption
    if l3_res.output:
        l3_res.output.execution_plan = unified_plan
    
    # --- Layer 6 ---
    # EXECUTION or DEFAULT run includes L6
    if action_manifest_allowed:
        l6_res = _safe_run(LayerId.L6, inputs, l1_res.output, l2_res.output, l3_res.output, l4_res.output, l5_res.output, progress_cb=progress_cb)
    else:
        l6_res = LayerResult(
            layer_id="L6", status=LayerStatus.DEGRADED, output=None,
            errors=["execution_blocked:prescription_influence_manifest_unavailable"],
        )
    results[LayerId.L6] = l6_res
    
    # --- Pre-Decision Governance Tribunal ---
    try:
        from services.agribrain.diagnostic_integration import pre_decision_tribunal
        tribunal_ctx = {
            "authority_level": getattr(l1_res.output, "authority_level", "none") if l1_res.output else "none",
            "evidence_tier": getattr(l1_res.output, "evidence_tier", "unknown") if l1_res.output else "unknown",
            "plot_id": inputs.plot_id,
        }
        pre_verdict, pre_findings = pre_decision_tribunal(run_id, tribunal_ctx)
        logger.info("Pre-decision tribunal verdict for %s: %d findings, blocked=%s", run_id, len(pre_findings), pre_verdict.blocked_contribution_ids)
    except Exception as tribunal_exc:
        logger.warning("Pre-decision tribunal execution warning: %s", tribunal_exc)

    # --- Layer 7 (Planning) ---
    # GAP 10+15: pass L3 decisions and L6 execution state to avoid plan conflicts
    tribunal_blocked = set(pre_verdict.blocked_contribution_ids) if 'pre_verdict' in locals() else set()
    full_verdict = pre_action_diagnostic.get("tribunal_verdict", {})
    tribunal_blocked.update(full_verdict.get("blocked_contribution_ids", []))
    tier0_degraded = (
        l1_res.status in (LayerStatus.DEGRADED, LayerStatus.FAILED)
        or l2_res.status in (LayerStatus.DEGRADED, LayerStatus.FAILED)
        or "l7_planning" in tribunal_blocked
        or not action_manifest_allowed
    )
    if tier0_degraded:
        l7_res = LayerResult(
            layer_id="L7", status=LayerStatus.DEGRADED, output=None,
            errors=["planning_blocked:degraded_tier0_or_tribunal_block"],
        )
    else:
        l7_res = _safe_run(LayerId.L7, inputs, l1_res,
                           l5_res.output if l5_res else None, None,
                           l3_res.output if l3_res else None,
                           l6_res.output if l6_res else None, progress_cb=progress_cb)
    results[LayerId.L7] = l7_res

    # --- Layer 8 (Prescriptive) ---
    # Use only a real forecast.  Historical observations are evidence about
    # the past and must never be relabelled as a future forecast.
    l1_forecast_7d = getattr(l1_res.output, "forecast_7d", []) if l1_res and l1_res.output else []
    l8_forecast = l1_forecast_7d
    
    # Resolve the canonical Layer-2 crop/phenology receipts.  The registered
    # crop remains useful as a planning label but never authorizes L8 rates or
    # timing by itself.
    crop_cfg = inputs.crop_config if isinstance(inputs.crop_config, dict) else {}
    from services.agribrain.common.downstream_crop_context import (
        resolve_downstream_crop_phenology,
    )
    crop_semantics = resolve_downstream_crop_phenology(
        inputs=inputs,
        l2_output=l2_res.output if l2_res else None,
    )
    declared_crop = str(
        crop_cfg.get("crop") or crop_cfg.get("crop_type") or ""
    ).strip()
    real_crop = str(
        crop_semantics.selected_crop or declared_crop or "unknown"
    ).strip()
    
    # Extract real soil static from L1 tensor (instead of hardcoded defaults)
    real_soil_static = {}
    if l1_res and l1_res.output:
        l1_static = getattr(l1_res.output, "static", {}) or {}
        if isinstance(l1_static, dict):
            for key in ("soil_clay", "soil_ph", "soil_org_carbon", "soil_sand", "texture_class"):
                val = l1_static.get(key)
                if val is not None and isinstance(val, (int, float)):
                    real_soil_static[key] = float(val)
    
    # GAP 12: Enrich soil_static from L4 SoilWaterBalance when L1.static is sparse
    # L4's SWB engine extracts/refines soil clay/pH/OC from SAR + soil APIs.
    if l4_res and l4_res.output:
        l4_soil = getattr(l4_res.output, "soil_props", {}) or {}
        if isinstance(l4_soil, dict):
            _l4_to_l8_soil = {
                "clay_pct": "soil_clay",
                "ph": "soil_ph",
            }
            for l4_key, l8_key in _l4_to_l8_soil.items():
                v = l4_soil.get(l4_key)
                if v is not None and isinstance(v, (int, float)):
                    # Don't overwrite real L1 values, only fill gaps
                    if l8_key not in real_soil_static:
                        real_soil_static[l8_key] = round(float(v), 3)
            # Soil organic carbon is not interchangeable with organic matter.
            # Use the conventional van Bemmelen conversion only when the L4
            # value explicitly represents organic matter percentage.
            om_pct = l4_soil.get("organic_matter_pct")
            if (
                "soil_org_carbon" not in real_soil_static
                and isinstance(om_pct, (int, float))
            ):
                real_soil_static["soil_org_carbon"] = round(
                    max(0.0, float(om_pct)) / 1.724, 3
                )

    l8_input = Layer8Input(
        diagnoses=getattr(l3_res.output, "diagnoses", []) if l3_res.output else [],
        nutrient_states=_normalize_nutrient_states(l4_res.output),
        bio_threats=_normalize_threat_states(l5_res.output),
        weather_forecast=l8_forecast,
        zone_ids=_extract_zone_ids(l1_res),
        audit_grade=_derive_audit_grade_from_provenance(l1_res),
        source_reliability=_derive_source_reliability_from_provenance(l1_res),
        conflicts=_extract_conflicts_from_provenance(l1_res),
        phenology_stage=crop_semantics.stage_for_discrete_engine,
        horizon_days=7,
        crop=real_crop,
        crop_posterior_hash=crop_semantics.crop_posterior_hash,
        phenology_posterior_hash=crop_semantics.phenology_posterior_hash,
        crop_resolution=crop_semantics.crop_resolution,
        crop_authority=crop_semantics.crop_authority,
        phenology_authority=crop_semantics.phenology_authority,
        crop_evidence_class=(
            "canonical_species_posterior"
            if crop_semantics.species_specific_allowed
            else "canonical_group_mixture"
            if crop_semantics.crop_resolution == "group_only"
            else "unresolved"
        ),
        phenology_evidence_class=(
            "canonical_stage_posterior"
            if crop_semantics.stage_specific_allowed
            else "unresolved"
        ),
        species_specific_allowed=crop_semantics.species_specific_allowed,
        stage_specific_allowed=crop_semantics.stage_specific_allowed,
        crop_mixture=dict(crop_semantics.crop_mixture),
        stage_posterior=dict(crop_semantics.stage_posterior),
        semantic_demotion_reasons=list(crop_semantics.demotion_reasons),
        input_belief_id=str(pre_action_diagnostic.get("input_belief_id") or ""),
        tribunal_content_hash=str(
            pre_action_diagnostic.get("tribunal_verdict", {}).get("content_hash") or ""
        ),
        prescription_manifest_hash=str(pre_action_manifest.get("content_hash") or ""),
        prescription_manifest_entry_ids=[
            str(entry.get("contribution_id") or "")
            for entry in pre_action_entries
            if isinstance(entry, dict) and entry.get("contribution_id")
        ],
        policy_snapshot_hash=hashlib.sha256(
            _canonical_json(inputs.policy_snapshot).encode("utf-8")
        ).hexdigest(),
        soil_static=real_soil_static,
    )
    # GAP 17 NOTE: L8 uses non-standard call convention:
    # _safe_run(L8, Layer8Input, forecast, None) where forecast is positional arg 2.
    # run_layer8(l8_input, forecast=None, start_date=None) handles this correctly.
    live_forecast = any(
        isinstance(day, dict)
        and day.get("source") not in (None, "", "persistence_forecast")
        and all(isinstance(day.get(key), (int, float)) for key in ("temp_max", "temp_min", "precipitation"))
        for day in l8_forecast
    )
    l8_blockers = []
    if tier0_degraded or not l7_res or l7_res.status != LayerStatus.OK:
        l8_blockers.append("upstream_planning_or_tier0_degraded")
    if "l8_prescriptive" in tribunal_blocked:
        l8_blockers.append("tribunal_blocked_l8_prescriptive")
    if not action_manifest_allowed:
        l8_blockers.append("prescription_influence_manifest_unavailable")
    if not live_forecast:
        l8_blockers.append("weather_unavailable")
    if not all(isinstance(real_soil_static.get(key), (int, float)) for key in ("soil_clay", "soil_ph", "soil_org_carbon")):
        l8_blockers.append("soil_evidence_incomplete")
    if l8_blockers:
        l8_res = LayerResult(
            layer_id="L8", status=LayerStatus.DEGRADED, output=None,
            errors=["prescriptions_blocked:" + ",".join(l8_blockers)],
        )
    else:
        l8_res = _safe_run(LayerId.L8, l8_input, l8_forecast, None, progress_cb=progress_cb)
    results[LayerId.L8] = l8_res
    # --- Layer 10 (SIRE — Spatial Intelligence & Rendering) ---
    import sys as _sys
    import time as _time_l10
    _t_l10 = _time_l10.perf_counter()
    try:
        ft = l1_res.output
        vi = l2_res.output
        grid_h = getattr(getattr(ft, 'grid_spec', None), 'height', 10)
        grid_w = getattr(getattr(ft, 'grid_spec', None), 'width', 10)
        res_m = getattr(getattr(ft, 'grid_spec', None), 'resolution', 10.0)

        # Gating Layer 10 rendering on Layer 1 health/provenance
        l1_unusable = False
        if l1_res:
            if l1_res.status == LayerStatus.FAILED:
                l1_unusable = True
            elif l1_res.output:
                prov = getattr(l1_res.output, "provenance", {}) or {}
                prov_dict = prov if isinstance(prov, dict) else {
                    "data_health_status": getattr(prov, "data_health_status", None),
                    "data_health_overall": getattr(prov, "data_health_overall", None),
                    "evidence_count": getattr(prov, "evidence_count", None),
                    "v1_data_health": getattr(prov, "v1_data_health", None),
                    "v1_evidence_count": getattr(prov, "v1_evidence_count", None),
                }
                dh = getattr(l1_res.output, "data_health", None)
                status = (
                    getattr(dh, "status", None)
                    or prov_dict.get("data_health_status")
                    or prov_dict.get("v1_data_health")
                )
                health = (
                    getattr(dh, "overall", None)
                    if dh is not None else prov_dict.get("data_health_overall")
                )
                evidence_count = prov_dict.get(
                    "evidence_count", prov_dict.get("v1_evidence_count", None)
                )
                if status == "unusable" or evidence_count == 0 or (isinstance(health, (int, float)) and health < 0.25):
                    l1_unusable = True

        if l1_unusable:
            from layer10_sire.terminal_publication import (
                build_terminal_no_data_output,
            )
            l10_output = build_terminal_no_data_output(
                run_id=f"L10-terminal-{run_id}",
                request_run_id=run_id,
                timestamp=ts,
                reason="INSUFFICIENT_EVIDENCE",
                geometry_hash=inputs.geometry_hash,
                input_run_ids={
                    "L1": l1_res.run_id,
                    "L2": l2_res.run_id,
                },
                core_asmae_evidence_state=dict(
                    getattr(l1_res.output, "asmae_evidence_state", {}) or {}
                ) if l1_res.output else {},
            )
            l10_result = LayerResult(
                layer_id="L10", status=LayerStatus.DEGRADED, output=l10_output,
                run_id=l10_output.run_id
            )
        else:
            # Wire ForecastContext (daily weather forecast metrics)
            from layer10_sire.schema import ForecastContext
            fc_list = getattr(ft, "forecast_7d", []) or []
            
            enhanced_vars = ["precipitation", "temp_max", "temp_min", "humidity", "wind_speed", "et0"]
            core_vars = ["precipitation", "temp_max", "temp_min", "et0"]
            
            missing_vars_set = set()
            has_any_data = False
            
            var_keys = {
                "precipitation": ["precipitation", "rain", "precipitation_mm"],
                "temp_max": ["temp_max", "temp_mean", "temperature"],
                "temp_min": ["temp_min", "temp_mean", "temperature"],
                "humidity": ["humidity", "rh"],
                "wind_speed": ["wind_speed", "wind"],
                "et0": ["et0", "evapotranspiration"]
            }
            
            days_count = len(fc_list)
            for day in fc_list:
                if isinstance(day, dict):
                    has_any_data = True
                    for var_name, keys in var_keys.items():
                        has_var = any(k in day and day[k] is not None for k in keys)
                        if not has_var:
                            missing_vars_set.add(var_name)
                else:
                    for var_name in enhanced_vars:
                        missing_vars_set.add(var_name)
            
            missing_variables = sorted(list(missing_vars_set))
            
            # Determine Tier
            has_core_missing = any(cv in missing_variables for cv in core_vars)
            
            precip_fc = []
            tmax_fc = []
            tmin_fc = []
            hum_fc = []
            wind_fc = []
            et0_fc = []
            
            if not has_any_data or days_count < 5 or has_core_missing:
                completeness_status = "missing"
                fc_source = "MISSING_OR_PARTIAL"
                fc_conf = 0.10
                
                # Fill with Nones
                precip_fc = [None] * max(1, days_count)
                tmax_fc = [None] * max(1, days_count)
                tmin_fc = [None] * max(1, days_count)
                hum_fc = [None] * max(1, days_count)
                wind_fc = [None] * max(1, days_count)
                et0_fc = [None] * max(1, days_count)
            else:
                for day in fc_list:
                    if isinstance(day, dict):
                        # Precip
                        p_val = None
                        for k in ["precipitation", "rain", "precipitation_mm"]:
                            if k in day:
                                p_val = day[k]
                                break
                        precip_fc.append(float(p_val) if p_val is not None else None)
                        
                        # Temp Max
                        tmax_val = None
                        for k in ["temp_max", "temp_mean", "temperature"]:
                            if k in day:
                                tmax_val = day[k]
                                break
                        tmax_fc.append(float(tmax_val) if tmax_val is not None else None)
                        
                        # Temp Min
                        tmin_val = None
                        for k in ["temp_min", "temp_mean", "temperature"]:
                            if k in day:
                                tmin_val = day[k]
                                break
                        tmin_fc.append(float(tmin_val) if tmin_val is not None else None)
                        
                        # Humidity
                        h_val = day.get("humidity") or day.get("rh")
                        hum_fc.append(float(h_val) if h_val is not None else None)
                        
                        # Wind
                        w_val = day.get("wind_speed") or day.get("wind")
                        wind_fc.append(float(w_val) if w_val is not None else None)
                        
                        # ET0
                        e_val = day.get("et0") or day.get("evapotranspiration")
                        et0_fc.append(float(e_val) if e_val is not None else None)
                
                if any(ev in missing_variables for ev in enhanced_vars):
                    completeness_status = "partial"
                    fc_source = "L1_FORECAST_CORE"
                    fc_conf = 0.70
                else:
                    completeness_status = "complete"
                    fc_source = "L1_FORECAST_ENHANCED"
                    fc_conf = 0.80

            fc = ForecastContext(
                precipitation_forecast=precip_fc,
                temperature_max_forecast=tmax_fc,
                temperature_min_forecast=tmin_fc,
                humidity_forecast=hum_fc,
                wind_speed_forecast=wind_fc,
                evapotranspiration_forecast=et0_fc,
                forecast_source=fc_source,
                forecast_confidence=fc_conf,
                completeness_status=completeness_status,
                missing_variables=missing_variables,
            )
            from geometry.canonicalizer import canonicalize_geometry
            op_context = inputs.operational_context or {}
            geom_context = (
                getattr(inputs, "field_geometry", None)
                or getattr(inputs, "polygon_geojson", None)
                or op_context.get("field_geometry")
                or op_context.get("polygon_coords")
                or op_context.get("polygon")
            )
            geom_canon = canonicalize_geometry(geom_context)

            l10_input = Layer10Input(
                plot_namespace=getattr(inputs, "plot_namespace", None),
                tenant_id=getattr(inputs, "tenant_id", ""),
                farm_id=getattr(inputs, "farm_id", ""),
                field_tensor=ft, veg_int=vi,
                decision=l3_res.output,
                nutrients=l4_res.output,
                bio=l5_res.output,
                exec_state=l6_res.output,
                planning=l7_res.output if l7_res else None,
                prescriptive=l8_res.output if l8_res else None,
                plot_id=inputs.plot_id,
                grid_height=grid_h, grid_width=grid_w,
                resolution_m=res_m,
                crop=real_crop,
                forecast_context=fc,
                ground_truth_context=(inputs.operational_context or {}).get('ground_truth_context', {}),
                visual_intensity=float((inputs.operational_context or {}).get('visual_intensity', 0.40)),
                user_mode=str((inputs.operational_context or {}).get('user_mode', 'farmer')),
                source_policy=(inputs.operational_context or {}).get('source_policy'),
                raster_composites=raster_composites,
                field_geometry=geom_canon.get("canonical_geojson") or geom_context,
                canonical_geometry_hash=geom_canon.get("canonical_geometry_hash"),
                source_geometry_hash=geom_canon.get("source_geometry_hash"),
            )
            l10_output = LAYER_REGISTRY[LayerId.L10].runner(l10_input)
            if l10_output is not None:
                l10_output.forecast_context = fc
            _elapsed_l10 = _time_l10.perf_counter() - _t_l10
            l10_budget_exceeded = (
                getattr(l10_output, "provenance", {}).get("budget_status") == "exceeded"
                if l10_output is not None else False
            )
            l10_status = LayerStatus.DEGRADED if l10_budget_exceeded else LayerStatus.OK
            perf_label = "BUDGET_EXCEEDED" if l10_budget_exceeded else "OK"
            print(f"[PERF] L10: {_elapsed_l10:.2f}s ({perf_label})", file=_sys.stderr, flush=True)
            l10_result = LayerResult(
                layer_id="L10", status=l10_status, output=l10_output,
                run_id=getattr(l10_output, 'run_id', ''),
                errors=["layer10_budget_exceeded"] if l10_budget_exceeded else [],
            )
    except Exception as e:
        import traceback
        _elapsed_l10 = _time_l10.perf_counter() - _t_l10
        print(f"[PERF] L10: {_elapsed_l10:.2f}s (FAILED)", file=_sys.stderr, flush=True)
        print(f"[L10 FATAL ERROR] {type(e).__name__}: {e}", file=_sys.stderr, flush=True)
        traceback.print_exc(file=_sys.stderr)
        l10_result = LayerResult(
            layer_id="L10",
            status=LayerStatus.FAILED,
            output=None,
            errors=[f"{type(e).__name__}: {e}"],
        )
    results[LayerId.L10] = l10_result

    # --- Layer 9 (Interface) ---
    # Skip in surfaces mode — L9 uses LLM calls for narrative text
    # and adds 10-30s of latency. The surfaces pipeline doesn't use L9 output.
    if not skip_l9:
        # Pass L1 conflicts directly — L8Output does not expose conflicts,
        # so we pass them from the orchestrator's L1 extraction.
        # GAP 14: also pass L4 nutrient output so advisory/coach engines can
        # narrate WHY a nutrition prescription was made (confidence, deficiency driver).
        l1_conflicts = _extract_conflicts_from_provenance(l1_res)
        l9_res = _safe_run(LayerId.L9, inputs,
                           l8_res.output if l8_res else None,
                           l3_res.output, l6_res.output,
                           l10_result.output if l10_result else None,
                           l1_conflicts,
                           l1_res.output if l1_res else None,
                           l2_res.output if l2_res else None,
                           l4_res.output if l4_res else None,
                           l5_res.output if l5_res else None,
                           l7_res.output if l7_res else None,
                           progress_cb=progress_cb)
        results[LayerId.L9] = l9_res
    else:
        print("[PERF] Skipping L9 (surfaces mode — no narrative needed)", file=_sys.stderr, flush=True)
    
    # 3. Finalize
    return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan, primary_acquisition=primary_acquisition, fallback_used=fallback_used, fallback_reason=fallback_reason)


def _structured_output_status(output) -> tuple[LayerStatus, list[str]]:
    """Promote an engine's structured degradation into orchestrator health."""
    if output is None:
        return LayerStatus.DEGRADED, ["structured_output_missing"]

    candidates = [
        getattr(output, "status", None),
        getattr(output, "degradation_mode", None),
    ]

    # 1. Inspect run_meta if present
    run_meta = getattr(output, "run_meta", None)
    if run_meta is not None:
        candidates.extend([
            getattr(run_meta, "status", None),
            getattr(run_meta, "degradation_mode", None),
        ])

    # 2. Inspect data_health if present
    data_health = getattr(output, "data_health", None)
    if data_health is not None:
        candidates.extend([
            getattr(data_health, "status", None),
            getattr(data_health, "health_status", None),
        ])

    # 3. Inspect provenance (dict or object)
    prov = getattr(output, "provenance", None)
    provenance_dict = {}
    if prov is not None:
        if isinstance(prov, dict):
            provenance_dict = prov
            candidates.extend([prov.get("status"), prov.get("degradation_mode")])
        else:
            candidates.extend([getattr(prov, "status", None), getattr(prov, "degradation_mode", None)])

    # 4. Inspect quality_report or quality_metrics
    qm = getattr(output, "quality_metrics", None) or getattr(output, "quality_report", None)
    if qm is not None:
        candidates.extend([
            getattr(qm, "status", None),
            getattr(qm, "degradation_mode", None),
        ])
        reliability = getattr(qm, "decision_reliability", None)
        if reliability is not None and isinstance(reliability, (int, float)) and reliability < 0.50:
            return LayerStatus.DEGRADED, [f"low_decision_reliability_{reliability:.2f}"]

    # 5. Inspect stage_receipt or receipt if present
    receipt = getattr(output, "stage_receipt", None) or getattr(output, "receipt", None)
    if receipt is not None:
        candidates.extend([
            getattr(receipt, "execution_status", None),
            getattr(receipt, "scientific_usability", None),
        ])

    normalized = {
        str(value.value if hasattr(value, "value") else value).strip().lower()
        for value in candidates
        if value is not None
    }
    run_id = str(
        getattr(output, "run_id", "")
        or getattr(getattr(output, "run_meta", None), "run_id", "")
        or getattr(output, "run_id_l3", "")
        or ""
    ).lower()

    explicitly_failed = any(
        value in {"failed", "error", "critical_failure", "unusable"}
        for value in normalized
    )
    if explicitly_failed:
        return LayerStatus.FAILED, ["structured_output_failed"]

    explicitly_degraded = (
        provenance_dict.get("degraded") is True
        or run_id.endswith("_degraded")
        or any(
            value in {"degraded", "data_gap", "partial_data", "degraded_usable"}
            for value in normalized
        )
    )
    if explicitly_degraded:
        return LayerStatus.DEGRADED, ["structured_output_degraded"]

    return LayerStatus.OK, []


def _safe_run(lid: LayerId, *args, progress_cb=None) -> LayerResult:
    import sys
    import time as _time
    _t0 = _time.perf_counter()
    spec = LAYER_REGISTRY[lid]
    stage_name = _LAYER_STAGE_NAMES.get(lid.value, lid.value)
    if progress_cb:
        try:
            progress_cb(stage_name, "running")
        except Exception:
            pass
    try:
        output = spec.runner(*args)
        status, structured_errors = _structured_output_status(output)
        _elapsed = _time.perf_counter() - _t0
        # Use stderr to bypass redirect_stdout in run_surfaces_mode
        print(f"[PERF] {lid.value}: {_elapsed:.2f}s ({status.value})", file=sys.stderr, flush=True)
        if progress_cb:
            try:
                progress_cb(stage_name, "done", _elapsed)
            except Exception:
                pass
        
        return LayerResult(
            layer_id=lid.value,
            status=status,
            output=output,
            run_id=getattr(output, "run_id", "") or getattr(getattr(output, "run_meta", None), "run_id", "") or getattr(output, "run_id_l3", ""),
            errors=structured_errors,
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        _elapsed = _time.perf_counter() - _t0
        status = LayerStatus.FAILED if spec.required else LayerStatus.DEGRADED
        print(f"[PERF] {lid.value}: {_elapsed:.2f}s ({status.value})", file=sys.stderr, flush=True)
        if progress_cb:
            try:
                progress_cb(stage_name, "error", _elapsed)
            except Exception:
                pass
        return LayerResult(
            layer_id=lid.value,
            status=status,
            output=None,
            errors=[str(e)]
        )


# ============================================================================
# L8 Input Helpers — upstream trust, normalization, zone extraction
# ============================================================================

def _normalize_nutrient_states(l4_output) -> Dict[str, Any]:
    """
    Convert L4's Dict[Nutrient, NutrientState] dataclasses into the
    Dict[str, dict] shape that action_ranker actually reads:
    { "N": {"probability_deficient": 0.6, "confidence": 0.8, "severity": "HIGH"}, ... }
    """
    if not l4_output:
        return {}
    raw = getattr(l4_output, "nutrient_states", {})
    if not raw:
        return {}
    result = {}
    for key, state in raw.items():
        k = key.value if hasattr(key, "value") else str(key)
        if hasattr(state, "probability_deficient"):
            # Dataclass → dict
            result[k] = {
                "probability_deficient": getattr(state, "probability_deficient", 0.0),
                "confidence": getattr(state, "confidence", 0.5),
                "severity": getattr(state, "severity", "LOW"),
                "state_index": getattr(state, "state_index", 0.0),
                "drivers_used": [str(d) for d in getattr(state, "drivers_used", [])],
            }
        elif isinstance(state, dict):
            result[k] = state
        else:
            result[k] = {"probability_deficient": 0.0, "confidence": 0.5}
    return result


def _normalize_threat_states(l5_output) -> Dict[str, Any]:
    """
    Convert L5's Dict[str, BioThreatState] dataclasses into the
    Dict[str, dict] shape that action_ranker actually reads:
    { "FUNGAL_LEAF_SPOT": {"probability": 0.7, "confidence": 0.6, "severity": "HIGH"}, ... }
    """
    if not l5_output:
        return {}
    raw = getattr(l5_output, "threat_states", {})
    if not raw:
        return {}
    result = {}
    for key, state in raw.items():
        k = key.value if hasattr(key, "value") else str(key)
        if hasattr(state, "probability"):
            # Dataclass → dict
            result[k] = {
                "probability": getattr(state, "probability", 0.0),
                "confidence": getattr(state, "confidence", 0.5),
                "severity": getattr(getattr(state, "severity", "LOW"), "value", getattr(state, "severity", "LOW")),
                "spread_pattern": getattr(getattr(state, "spread_pattern", "UNKNOWN"), "value", getattr(state, "spread_pattern", "UNKNOWN")),
                "threat_class": getattr(getattr(state, "threat_class", ""), "value", getattr(state, "threat_class", "")),
            }
        elif isinstance(state, dict):
            result[k] = state
        else:
            result[k] = {"probability": 0.0, "confidence": 0.5}
    return result


def _extract_zone_ids(l1_res) -> List[str]:
    """
    Pull canonical zone IDs from FieldTensor.zones (L1 spatial layer).
    Fallback to ["plot"] if no zones defined.
    """
    if not l1_res or not l1_res.output:
        return ["plot"]
    tensor_zones = getattr(l1_res.output, "zones", {})
    if tensor_zones and isinstance(tensor_zones, dict) and len(tensor_zones) > 0:
        return list(tensor_zones.keys())
    return ["plot"]


def _derive_audit_grade_from_provenance(l1_res) -> str:
    """
    Read audit grade from L1 provenance upstream trust channel.
    Source: tensor.provenance["audit"]["trust_report"]["health_grade"]
    or tensor.provenance["layer0_reliability"] mapped to letter grade.
    Fallback: "B" (conservative default).
    """
    if not l1_res or not l1_res.output:
        return "B"
    prov = getattr(l1_res.output, "provenance", {})
    if not isinstance(prov, dict):
        return "B"
    # Try structured audit path first
    audit = prov.get("audit", {})
    if isinstance(audit, dict):
        trust_report = audit.get("trust_report", {})
        if isinstance(trust_report, dict):
            grade = trust_report.get("health_grade")
            if grade and isinstance(grade, str) and grade.upper() in ("A", "B", "C", "D", "F"):
                return grade.upper()
    # Fall back to layer0_reliability score → letter grade
    l0_rel = prov.get("layer0_reliability")
    if isinstance(l0_rel, (int, float)):
        if l0_rel >= 0.8:
            return "A"
        if l0_rel >= 0.6:
            return "B"
        if l0_rel >= 0.4:
            return "C"
        return "D"
    return "B"


def _derive_source_reliability_from_provenance(l1_res) -> Dict[str, float]:
    """
    Read source-level reliability from L1 provenance + derive zone-level
    reliability from zone_stats observation density.

    Returns a merged dict with both source-scoped keys (sentinel2, weather)
    AND zone-scoped keys (zone_a, zone_b, ...) so L8's ZonePrioritizer
    can access per-zone reliability directly.

    Zone reliability = weighted average of:
      - Source reliability mean (50%)
      - Zone NDVI observation density (50%) — fraction of non-null values
    """
    if not l1_res or not l1_res.output:
        return {}
    prov = getattr(l1_res.output, "provenance", {})
    if not isinstance(prov, dict):
        prov = {}

    result: Dict[str, float] = {}

    # Source-scoped reliability from L0
    l0_rel = prov.get("layer0_reliability", {})
    if isinstance(l0_rel, dict):
        for k, v in l0_rel.items():
            if isinstance(v, (int, float)):
                result[str(k)] = float(v)

    # Source reliability mean (for zone blending)
    source_values = [v for v in result.values() if isinstance(v, (int, float))]
    source_mean = sum(source_values) / len(source_values) if source_values else 0.6

    # Zone-scoped reliability from zone_stats observation density
    tensor = l1_res.output
    zone_stats = getattr(tensor, "zone_stats", {})
    if isinstance(zone_stats, dict) and "ndvi" in zone_stats:
        ndvi_zone_data = zone_stats["ndvi"]
        if isinstance(ndvi_zone_data, dict):
            for zone_id, zone_ts in ndvi_zone_data.items():
                if isinstance(zone_ts, list) and zone_ts:
                    # Compute observation density: fraction of non-null values
                    total = len(zone_ts)
                    non_null = sum(1 for v in zone_ts if v is not None)
                    obs_density = non_null / total if total > 0 else 0.0

                    # Blend: 50% source reliability + 50% observation density
                    zone_reliability = (source_mean * 0.5) + (obs_density * 0.5)
                    result[str(zone_id)] = round(zone_reliability, 3)

    return result


def _extract_conflicts_from_provenance(l1_res) -> List[Dict[str, Any]]:
    """
    Extract cross-source conflicts from L1 provenance.
    Source: tensor.provenance["layer0_conflicts"]
    These flow into L8 (for degradation mode) and must also be passed
    directly to L9 (for disclaimers and conflict icons).
    """
    if not l1_res or not l1_res.output:
        return []
    prov = getattr(l1_res.output, "provenance", {})
    if not isinstance(prov, dict):
        return []
    conflicts = prov.get("layer0_conflicts", [])
    if isinstance(conflicts, list):
        return conflicts
    return []


def _legacy_derive_phenology_stage_for_migration(l2_res, inputs) -> str:
    """
    Removed migration-only phenology inference path.

    Layer 2 is the sole biological phenology owner.  Keeping this symbol makes
    accidental legacy callers fail loudly during migration instead of silently
    manufacturing a stage from NDVI or CropCycle administrative status.

    Algorithm:
    1. Extract Kalman best-estimate NDVI from L2 ndvi_records (NOT raw raster NDVI)
    2. Extract crop-type classification from inputs
    3. Build crop-specific NDVI-phenology lookup table (literature-grounded)
    4. Derive L2's declared stage (stage_by_day or crop_config)
    5. RECONCILE: if declared stage contradicts Kalman NDVI for the crop type,
       the physically-derived stage from the NDVI-envelope takes precedence.
       This prevents BARE_SOIL being shown when Kalman NDVI = 0.41 (a crop is clearly growing).

    NDVI thresholds by crop type are derived from:
    - Becker-Reshef et al. (2010): wheat phenology from MODIS NDVI
    - Wardlow & Egbert (2008): crop type classification from temporal NDVI
    - Bolton & Friedl (2013): MODIS phenology for global croplands
    - Tucker et al. (1979): original NDVI-LAI relationships
    """
    # ── Step 1: Extract Kalman NDVI (best estimate, cloud-corrected) ──────────
    del l2_res, inputs
    raise RuntimeError(
        "legacy downstream phenology inference is disabled; consume the "
        "canonical Layer 2 phenology receipt"
    )

    # Historical implementation retained below temporarily for source-level
    # migration archaeology; it is unreachable by construction.
    kalman_ndvi: float | None = None

    if l2_res and l2_res.output:
        veg = l2_res.output

        # Primary: read from ndvi_records (Kalman state estimates per day)
        # These are post-assimilation values — physically consistent with SAR + weather
        ndvi_records = getattr(veg, "ndvi_records", None) or getattr(veg, "plot_timeseries", None)
        if ndvi_records and isinstance(ndvi_records, list):
            # Scan backward for the most recent observed (not interpolated) estimate
            for rec in reversed(ndvi_records):
                if isinstance(rec, dict):
                    # Prefer Kalman state estimate over raw observation
                    for key in ("ndvi_smoothed", "ndvi_kalman", "ndvi_interpolated", "ndvi_mean"):
                        v = rec.get(key)
                        if v is not None and isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0:
                            kalman_ndvi = float(v)
                            break
                if kalman_ndvi is not None:
                    break

        # Fallback: use VegIntOutput's field-level summary if records are absent
        if kalman_ndvi is None:
            for attr in ("ndvi_mean", "mean_ndvi", "ndvi"):
                v = getattr(veg, attr, None)
                if v is not None and isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0:
                    kalman_ndvi = float(v)
                    break

    # ── Step 2: Classify crop architecture ───────────────────────────────────
    cfg = inputs.crop_config if isinstance(inputs.crop_config, dict) else {}
    crop_raw = str(cfg.get("crop", cfg.get("crop_type", "cereal"))).lower()

    # Use the centralized 209-crop registry instead of stale hardcoded keywords
    from crop_database import get_architecture_class
    _arch_raw = get_architecture_class(crop_raw)
    # Map registry architecture to the phenology classifier labels
    _ARCH_MAP = {
        "cereal": "CEREAL", "maize": "CEREAL", "rice": "CEREAL",
        "legume": "LEGUME", "cotton": "FIBER",
        "vegetable": "VEGETABLE",
        "perennial": "TREE", "tropical_tree": "TREE",
    }
    arch = _ARCH_MAP.get(_arch_raw, "CEREAL")

    # ── Step 3: Crop-specific NDVI-phenology thresholds ──────────────────────
    # Format: {stage: (ndvi_min, ndvi_max)}
    # Thresholds derived from Becker-Reshef (2010), Bolton&Friedl (2013), FAO crop calendars.
    # These are CONSERVATIVE — biased toward avoiding false positives on bare soil.
    NDVI_PHENOLOGY: dict = {
        "CEREAL": {
            "BARE_SOIL":    (0.00, 0.18),   # Pre-planting / post-harvest
            "EMERGENCE":    (0.15, 0.35),   # BBCH 09-19: seedling emerging
            "VEGETATIVE":   (0.30, 0.70),   # BBCH 20-49: tillering to stem extension
            "REPRODUCTIVE": (0.50, 0.85),   # BBCH 50-79: heading to milk ripeness
            "SENESCENCE":   (0.15, 0.55),   # BBCH 80-99: doughy to ripe (yellowing)
            "HARVESTED":    (0.00, 0.20),   # Post-harvest
        },
        "LEGUME": {
            "BARE_SOIL":    (0.00, 0.18),
            "EMERGENCE":    (0.15, 0.35),
            "VEGETATIVE":   (0.30, 0.65),
            "REPRODUCTIVE": (0.45, 0.80),
            "SENESCENCE":   (0.10, 0.50),
            "HARVESTED":    (0.00, 0.20),
        },
        "TREE": {
            # Tree/orchard crops: NDVI stays elevated year-round (evergreen)
            # or has a minimum at leaf-off (deciduous). Bare soil is very rare.
            "BARE_SOIL":    (0.00, 0.12),   # Only valid for newly planted / cleared orchard
            "EMERGENCE":    (0.10, 0.35),   # Bud-break / early canopy
            "VEGETATIVE":   (0.35, 0.75),   # Full canopy development
            "REPRODUCTIVE": (0.40, 0.75),   # Flowering + fruit set (canopy intact)
            "SENESCENCE":   (0.20, 0.55),   # Leaf senescence (deciduous) or fruit maturity
            "HARVESTED":    (0.15, 0.60),   # Post-harvest: canopy still present in most trees
        },
        "VEGETABLE": {
            "BARE_SOIL":    (0.00, 0.20),
            "EMERGENCE":    (0.15, 0.38),
            "VEGETATIVE":   (0.30, 0.70),
            "REPRODUCTIVE": (0.40, 0.75),
            "SENESCENCE":   (0.10, 0.50),
            "HARVESTED":    (0.00, 0.25),
        },
        "FIBER": {
            "BARE_SOIL":    (0.00, 0.18),
            "EMERGENCE":    (0.15, 0.38),
            "VEGETATIVE":   (0.30, 0.72),
            "REPRODUCTIVE": (0.50, 0.80),
            "SENESCENCE":   (0.20, 0.60),
            "HARVESTED":    (0.00, 0.20),
        },
    }

    thresholds = NDVI_PHENOLOGY.get(arch, NDVI_PHENOLOGY["CEREAL"])

    # ── Step 4: Get declared stage from L2 / crop_config ─────────────────────
    declared_stage: str = "UNKNOWN"

    if l2_res and l2_res.output:
        phenology = getattr(l2_res.output, "phenology", None)
        if phenology:
            stage_by_day = getattr(phenology, "stage_by_day", [])
            if stage_by_day and isinstance(stage_by_day, list):
                for i in range(len(stage_by_day) - 1, -1, -1):
                    entry = stage_by_day[i]
                    if isinstance(entry, str) and entry.upper() != "UNKNOWN":
                        declared_stage = entry.upper()
                        break
                    val = getattr(entry, "value", None)
                    if val and isinstance(val, str) and val.upper() != "UNKNOWN":
                        declared_stage = val.upper()
                        break

    if declared_stage == "UNKNOWN":
        for key in ("stage", "crop_stage"):
            val = cfg.get(key)
            if val and isinstance(val, str) and val.upper() != "UNKNOWN":
                declared_stage = val.upper()
                break

    # ── Step 5: NDVI-Phenology Reconciliation ────────────────────────────────
    # If we have a Kalman NDVI and a declared stage, check if the declared stage
    # is physically consistent with the NDVI envelope for this crop type.
    # If not, derive a corrected stage from the NDVI directly.

    if kalman_ndvi is not None:
        ndvi_min_declared, ndvi_max_declared = thresholds.get(declared_stage, (0.0, 1.0))
        is_consistent = (ndvi_min_declared <= kalman_ndvi <= ndvi_max_declared)

        if not is_consistent or declared_stage == "UNKNOWN":
            # The declared stage is physically inconsistent with Kalman NDVI.
            # Derive the most likely stage from the NDVI envelope.
            # Prefer stages where Kalman NDVI is in the center of the range,
            # weighted by agronomic plausibility (avoid extreme stages unless clearly indicated).
            STAGE_PRIORITY = ["VEGETATIVE", "REPRODUCTIVE", "EMERGENCE", "SENESCENCE", "BARE_SOIL", "HARVESTED"]
            best_stage = "VEGETATIVE"  # safe default
            best_overlap = -1.0

            for stage in STAGE_PRIORITY:
                lo, hi = thresholds.get(stage, (0.0, 1.0))
                if lo <= kalman_ndvi <= hi:
                    # Prefer stage where NDVI is most centered in the range
                    center = (lo + hi) / 2.0
                    overlap = 1.0 - abs(kalman_ndvi - center) / max((hi - lo) / 2.0, 0.01)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_stage = stage

            corrected_stage = best_stage

            # Log the reconciliation for observability
            import sys as _pheno_sys
            print(
                f"[PHENO] Stage reconciled: declared='{declared_stage}' "
                f"kalman_ndvi={kalman_ndvi:.3f} arch={arch} "
                f"→ corrected='{corrected_stage}' "
                f"(declared range {thresholds.get(declared_stage, '?')} was {'OK' if is_consistent else 'INCONSISTENT'})",
                file=_pheno_sys.stderr, flush=True
            )

            return corrected_stage

    # No Kalman NDVI available — return declared stage or safe fallback
    if declared_stage != "UNKNOWN":
        return declared_stage

    return "VEGETATIVE"


def _derive_phenology_stage(l2_res, inputs) -> str:
    """Consume Layer 2's stage; never infer a replacement downstream.

    CropCycle administrative status and NDVI envelopes are intentionally not
    consulted here.  The canonical posterior is authoritative.  A legacy
    Layer-2 Viterbi output may be consumed during migration, but remains owned
    by Layer 2 and is never reclassified by the orchestrator.
    """
    if not l2_res or not getattr(l2_res, "output", None):
        return "UNKNOWN"

    del inputs  # Administrative crop-cycle status is never stage evidence.
    from services.agribrain.scientific_contracts.crop_phenology import (
        consume_canonical_phenology_output,
    )
    return str(
        consume_canonical_phenology_output(l2_res.output).get(
            "resolved_crop_stage", "UNKNOWN"
        )
    )


def _build_diagnostic_integration(
    results: Dict[LayerId, LayerResult],
    orchestrator_run_id: str,
    timestamp: str,
    requested_use: Any = None,
) -> Dict[str, Any]:
    """Adapt every completed L2-L8 result into one immutable belief ledger."""
    from services.agribrain.diagnostic_integration import (
        AdapterContext,
        InfluenceUse,
        build_default_runtime,
    )
    from services.agribrain.scientific_contracts.authority import AuthorityVector

    requested_use = requested_use or InfluenceUse.DIAGNOSIS

    l1_result = results.get(LayerId.L1)
    l1_output = getattr(l1_result, "output", None) if l1_result else None
    l2_result = results.get(LayerId.L2)
    l2_output = getattr(l2_result, "output", None) if l2_result else None
    l5_result = results.get(LayerId.L5)
    l5_output = getattr(l5_result, "output", None) if l5_result else None
    asmae_snapshot_id = (
        getattr(l5_output, "snapshot_id", None)
        or getattr(l5_output, "intelligence_snapshot_id", None)
        or (l5_output.get("snapshot_id") if isinstance(l5_output, dict) else None)
        or (l5_output.get("intelligence_snapshot_id") if isinstance(l5_output, dict) else None)
    )
    belief_id = str(
        getattr(l2_output, "belief_id", None)
        or asmae_snapshot_id
        or getattr(l1_output, "intelligence_snapshot_id", None)
        or getattr(l1_output, "run_id", None)
        or getattr(l1_result, "run_id", None)
        or orchestrator_run_id
    )
    l1_provenance = getattr(l1_output, "provenance", {}) or {}
    evidence_count = (
        l1_provenance.get("evidence_count")
        if isinstance(l1_provenance, dict) else None
    )
    health_status = (
        l1_provenance.get("data_health_status")
        if isinstance(l1_provenance, dict) else None
    )
    l1_usable = bool(
        l1_result
        and l1_result.status in (LayerStatus.OK, LayerStatus.DEGRADED)
        and l1_output is not None
        and evidence_count != 0
        and health_status != "unusable"
    )
    authority = AuthorityVector(
        visualization_allowed=bool(l1_output),
        diagnosis_allowed=l1_usable,
    )
    dependency_layers = {
        LayerId.L2: (LayerId.L1,),
        LayerId.L3: (LayerId.L2,),
        LayerId.L4: (LayerId.L2, LayerId.L3),
        LayerId.L5: (LayerId.L2, LayerId.L3),
        LayerId.L6: (LayerId.L3, LayerId.L4, LayerId.L5),
        LayerId.L7: (
            LayerId.L2, LayerId.L3, LayerId.L4,
            LayerId.L5, LayerId.L6,
        ),
        LayerId.L8: (
            LayerId.L3, LayerId.L4, LayerId.L5,
            LayerId.L6, LayerId.L7,
        ),
    }
    runtime = build_default_runtime()
    contributions_by_layer: Dict[LayerId, Tuple[str, ...]] = {}
    adapter_errors: List[Dict[str, str]] = []
    for layer_id in (
        LayerId.L2, LayerId.L3, LayerId.L4, LayerId.L5,
        LayerId.L6, LayerId.L7, LayerId.L8,
    ):
        layer_result = results.get(layer_id)
        if layer_result is None or layer_result.output is None:
            continue
        dependencies = dependency_layers[layer_id]
        parent_ids = tuple(sorted({
            contribution_id
            for dependency in dependencies
            for contribution_id in contributions_by_layer.get(dependency, ())
        }))
        evidence_ids = tuple(sorted({
            f"run:{results[dependency].run_id}"
            for dependency in dependencies
            if results.get(dependency) is not None
            and results[dependency].run_id
        }))
        if not evidence_ids and not parent_ids:
            evidence_ids = (f"belief:{belief_id}",)
        context = AdapterContext(
            input_belief_id=belief_id,
            authority=authority,
            input_evidence_ids=evidence_ids,
            input_contribution_ids=parent_ids,
            dependency_families=tuple(
                f"upstream:{dependency.value}" for dependency in dependencies
            ),
            confounders=(
                ("degraded_upstream_output",)
                if layer_result.status == LayerStatus.DEGRADED else ()
            ),
            block_reasons=(
                ("INPUT_BELIEF_DIAGNOSIS_AUTHORITY_DENIED",)
                if not l1_usable else ()
            ),
            generated_at=timestamp,
        )
        try:
            contributions = runtime.ingest_layer(
                layer_id.value, layer_result.output, context,
            )
            contributions_by_layer[layer_id] = tuple(
                item.contribution_id for item in contributions
            )
        except Exception as exc:
            adapter_errors.append({
                "layer_id": layer_id.value,
                "error": str(exc),
            })

    if not runtime.ledger.entries():
        return {
            "status": "failed_closed",
            "input_belief_id": belief_id,
            "errors": adapter_errors or [{
                "layer_id": "L2-L8",
                "error": "no diagnostic contributions were emitted",
            }],
            "diagnosis_allowed": False,
        }
    result = runtime.finalize(belief_id, requested_use)
    payload = result.to_dict()
    payload.update({
        "status": (
            "completed_with_adapter_failures"
            if adapter_errors else "completed"
        ),
        "errors": adapter_errors,
        "contribution_count": len(runtime.ledger.entries()),
        "contribution_ledger": runtime.ledger.to_dict(),
        "dependency_graph": runtime.graph.to_dict(),
        "diagnosis_allowed": l1_usable,
        "state_mutation_performed": False,
    })
    return payload

def _finalize_artifact(
    run_id: str,
    ts: str,
    inputs: OrchestratorInput,
    results: Dict[LayerId, LayerResult],
    store: Optional[LocalJsonStore],
    final_plan: Optional[Any] = None,
    primary_acquisition: str = "layer0",
    fallback_used: bool = False,
    fallback_reason: Optional[str] = None
) -> RunArtifact:
    # Ensure Layer 10 (SIRE) is run if we have L1 and L2 but L10 is missing.
    # This ensures early exits (DIAGNOSIS, DECISION, NUTRIENT, PLANNING) 
    # still produce spatial maps for the frontend!
    if LayerId.L1 in results and LayerId.L2 in results and LayerId.L10 not in results:
        l1_res = results[LayerId.L1]
        l2_res = results[LayerId.L2]

        l1_unusable = False
        if l1_res:
            if l1_res.status == LayerStatus.FAILED:
                l1_unusable = True
            elif l1_res.output:
                prov = getattr(l1_res.output, "provenance", {}) or {}
                prov_dict = prov if isinstance(prov, dict) else {
                    "data_health_status": getattr(prov, "data_health_status", None),
                    "data_health_overall": getattr(prov, "data_health_overall", None),
                    "evidence_count": getattr(prov, "evidence_count", None),
                    "v1_data_health": getattr(prov, "v1_data_health", None),
                    "v1_evidence_count": getattr(prov, "v1_evidence_count", None),
                }
                dh = getattr(l1_res.output, "data_health", None)
                status = (
                    getattr(dh, "status", None)
                    or prov_dict.get("data_health_status")
                    or prov_dict.get("v1_data_health")
                )
                health = (
                    getattr(dh, "overall", None)
                    if dh is not None else prov_dict.get("data_health_overall")
                )
                evidence_count = prov_dict.get(
                    "evidence_count", prov_dict.get("v1_evidence_count", None)
                )
                if status == "unusable" or evidence_count == 0 or (isinstance(health, (int, float)) and health < 0.25):
                    l1_unusable = True

        if l1_unusable:
            from layer10_sire.terminal_publication import (
                build_terminal_no_data_output,
            )
            l10_output = build_terminal_no_data_output(
                run_id=f"L10-terminal-{run_id}",
                request_run_id=run_id,
                timestamp=ts,
                reason="INSUFFICIENT_EVIDENCE",
                geometry_hash=inputs.geometry_hash,
                input_run_ids={
                    "L1": l1_res.run_id,
                    "L2": l2_res.run_id,
                },
                core_asmae_evidence_state=dict(
                    getattr(l1_res.output, "asmae_evidence_state", {}) or {}
                ) if l1_res.output else {},
            )
            l10_result = LayerResult(
                layer_id="L10", status=LayerStatus.DEGRADED, output=l10_output,
                run_id=l10_output.run_id
            )
            results[LayerId.L10] = l10_result
        elif l1_res.status in (LayerStatus.OK, LayerStatus.DEGRADED) and l2_res.status in (LayerStatus.OK, LayerStatus.DEGRADED):
            try:
                import sys as _sys
                import time as _time_l10
                _t_l10 = _time_l10.perf_counter()
                
                ft = l1_res.output
                vi = l2_res.output
                grid_h = getattr(getattr(ft, 'grid_spec', None), 'height', 10)
                grid_w = getattr(getattr(ft, 'grid_spec', None), 'width', 10)
                res_m = getattr(getattr(ft, 'grid_spec', None), 'resolution', 10.0)

                # Extract crop config
                crop_cfg = inputs.crop_config if isinstance(inputs.crop_config, dict) else {}
                real_crop = crop_cfg.get("crop", crop_cfg.get("crop_type", "corn"))

                # Wire ForecastContext (daily weather forecast metrics)
                from layer10_sire.schema import ForecastContext
                fc_list = getattr(ft, "forecast_7d", []) or []
                
                enhanced_vars = ["precipitation", "temp_max", "temp_min", "humidity", "wind_speed", "et0"]
                core_vars = ["precipitation", "temp_max", "temp_min", "et0"]
                
                missing_vars_set = set()
                has_any_data = False
                
                var_keys = {
                    "precipitation": ["precipitation", "rain", "precipitation_mm"],
                    "temp_max": ["temp_max", "temp_mean", "temperature"],
                    "temp_min": ["temp_min", "temp_mean", "temperature"],
                    "humidity": ["humidity", "rh"],
                    "wind_speed": ["wind_speed", "wind"],
                    "et0": ["et0", "evapotranspiration"]
                }
                
                days_count = len(fc_list)
                for day in fc_list:
                    if isinstance(day, dict):
                        has_any_data = True
                        for var_name, keys in var_keys.items():
                            has_var = any(k in day and day[k] is not None for k in keys)
                            if not has_var:
                                missing_vars_set.add(var_name)
                    else:
                        for var_name in enhanced_vars:
                            missing_vars_set.add(var_name)
                
                missing_variables = sorted(list(missing_vars_set))
                has_core_missing = any(cv in missing_variables for cv in core_vars)
                
                precip_fc = []
                tmax_fc = []
                tmin_fc = []
                hum_fc = []
                wind_fc = []
                et0_fc = []
                
                if not has_any_data or days_count < 5 or has_core_missing:
                    completeness_status = "missing"
                    fc_source = "MISSING_OR_PARTIAL"
                    fc_conf = 0.10
                    
                    precip_fc = [None] * max(1, days_count)
                    tmax_fc = [None] * max(1, days_count)
                    tmin_fc = [None] * max(1, days_count)
                    hum_fc = [None] * max(1, days_count)
                    wind_fc = [None] * max(1, days_count)
                    et0_fc = [None] * max(1, days_count)
                else:
                    for day in fc_list:
                        if isinstance(day, dict):
                            # Precip
                            p_val = None
                            for k in ["precipitation", "rain", "precipitation_mm"]:
                                if k in day:
                                    p_val = day[k]
                                    break
                            precip_fc.append(float(p_val) if p_val is not None else None)
                            
                            # Temp Max
                            tmax_val = None
                            for k in ["temp_max", "temp_mean", "temperature"]:
                                if k in day:
                                    tmax_val = day[k]
                                    break
                            tmax_fc.append(float(tmax_val) if tmax_val is not None else None)
                            
                            # Temp Min
                            tmin_val = None
                            for k in ["temp_min", "temp_mean", "temperature"]:
                                if k in day:
                                    tmin_val = day[k]
                                    break
                            tmin_fc.append(float(tmin_val) if tmin_val is not None else None)
                            
                            # Humidity
                            h_val = day.get("humidity") or day.get("rh")
                            hum_fc.append(float(h_val) if h_val is not None else None)
                            
                            # Wind
                            w_val = day.get("wind_speed") or day.get("wind")
                            wind_fc.append(float(w_val) if w_val is not None else None)
                            
                            # ET0
                            e_val = day.get("et0") or day.get("evapotranspiration")
                            et0_fc.append(float(e_val) if e_val is not None else None)
                    
                    if any(ev in missing_variables for ev in enhanced_vars):
                        completeness_status = "partial"
                        fc_source = "L1_FORECAST_CORE"
                        fc_conf = 0.70
                    else:
                        completeness_status = "complete"
                        fc_source = "L1_FORECAST_ENHANCED"
                        fc_conf = 0.80

                fc = ForecastContext(
                    precipitation_forecast=precip_fc,
                    temperature_max_forecast=tmax_fc,
                    temperature_min_forecast=tmin_fc,
                    humidity_forecast=hum_fc,
                    wind_speed_forecast=wind_fc,
                    evapotranspiration_forecast=et0_fc,
                    forecast_source=fc_source,
                    forecast_confidence=fc_conf,
                    completeness_status=completeness_status,
                    missing_variables=missing_variables
                )

                from geometry.canonicalizer import canonicalize_geometry
                geom_context = inputs.polygon_geojson or (inputs.operational_context or {}).get("polygon")
                geom_canon = canonicalize_geometry(geom_context)

                l10_input = Layer10Input(
                    plot_namespace=getattr(inputs, "plot_namespace", None),
                    tenant_id=getattr(inputs, "tenant_id", ""),
                    farm_id=getattr(inputs, "farm_id", ""),
                    field_tensor=ft, veg_int=vi,
                    decision=results.get(LayerId.L3).output if results.get(LayerId.L3) else None,
                    nutrients=results.get(LayerId.L4).output if results.get(LayerId.L4) else None,
                    bio=results.get(LayerId.L5).output if results.get(LayerId.L5) else None,
                    exec_state=results.get(LayerId.L6).output if results.get(LayerId.L6) else None,
                    planning=results.get(LayerId.L7).output if results.get(LayerId.L7) else None,
                    prescriptive=results.get(LayerId.L8).output if results.get(LayerId.L8) else None,
                    plot_id=inputs.plot_id,
                    grid_height=grid_h, grid_width=grid_w,
                    resolution_m=res_m,
                    crop=real_crop,
                    forecast_context=fc,
                    ground_truth_context=(inputs.operational_context or {}).get('ground_truth_context', {}),
                    visual_intensity=float((inputs.operational_context or {}).get('visual_intensity', 0.40)),
                    user_mode=str((inputs.operational_context or {}).get('user_mode', 'farmer')),
                    source_policy=(inputs.operational_context or {}).get('source_policy'),
                    field_geometry=geom_canon.get("canonical_geojson") or geom_context,
                    canonical_geometry_hash=geom_canon.get("canonical_geometry_hash"),
                    source_geometry_hash=geom_canon.get("source_geometry_hash"),
                )
                l10_output = LAYER_REGISTRY[LayerId.L10].runner(l10_input)
                if l10_output is not None:
                    l10_output.forecast_context = fc
                _elapsed_l10 = _time_l10.perf_counter() - _t_l10
                l10_budget_exceeded = (
                    getattr(l10_output, "provenance", {}).get("budget_status") == "exceeded"
                    if l10_output is not None else False
                )
                l10_status = LayerStatus.DEGRADED if l10_budget_exceeded else LayerStatus.OK
                perf_label = "BUDGET_EXCEEDED" if l10_budget_exceeded else "OK"
                print(f"[PERF] L10 (Intercepted in finalize): {_elapsed_l10:.2f}s ({perf_label})", file=_sys.stderr, flush=True)
                l10_result = LayerResult(
                    layer_id="L10", status=l10_status, output=l10_output,
                    run_id=getattr(l10_output, 'run_id', ''),
                    errors=["layer10_budget_exceeded"] if l10_budget_exceeded else [],
                )
            except Exception as e:
                _elapsed_l10 = _time_l10.perf_counter() - _t_l10
                print(f"[PERF] L10 (Intercepted in finalize): {_elapsed_l10:.2f}s (DEGRADED): {e}", file=_sys.stderr, flush=True)
                l10_result = LayerResult(
                    layer_id="L10", status=LayerStatus.DEGRADED, output=None,
                    errors=[str(e)]
                )
            results[LayerId.L10] = l10_result

    # One content-addressed ASMAE snapshot must be visible under the same ID
    # in L1, L2, L10, map serialization, crop status, and health summaries.
    _propagate_intelligence_snapshot_id(results)

    # Quality
    gq = evaluate_global_quality(results)
    try:
        diagnostic_integration = _build_diagnostic_integration(
            results, run_id, ts,
        )
        from services.agribrain.diagnostic_integration import InfluenceUse
        diagnostic_integration["prescription_gate"] = _build_diagnostic_integration(
            results, run_id, ts, InfluenceUse.PRESCRIPTION_DRIVER,
        )
    except Exception as exc:
        diagnostic_integration = {
            "status": "failed_closed",
            "input_belief_id": run_id,
            "errors": [{"layer_id": "L2-L8", "error": str(exc)}],
            "diagnosis_allowed": False,
            "state_mutation_performed": False,
        }
    
    # Collect Parents
    parents_map = {lid.value: res.run_id for lid, res in results.items() if res.output}
    
    # Construct Meta
    meta = RunMeta(
        orchestrator_run_id=run_id,
        artifact_hash="", # Set after hash calc
        timestamp_utc=ts,
        orchestrator_version=ORCHESTRATOR_VERSION,
        layer_versions=get_layer_versions(),
        parents=parents_map,
        replay_uri="",
        primary_acquisition=primary_acquisition,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason
    )
    
    art = RunArtifact(
        meta=meta,
        inputs=inputs,
        global_quality=gq,
        layer_1=results.get(LayerId.L1),
        layer_2=results.get(LayerId.L2),
        layer_3=results.get(LayerId.L3),
        layer_4=results.get(LayerId.L4),
        layer_5=results.get(LayerId.L5),
        layer_6=results.get(LayerId.L6),
        layer_7=results.get(LayerId.L7),
        layer_8=results.get(LayerId.L8),
        layer_10=results.get(LayerId.L10),
        layer_9=results.get(LayerId.L9),
        final_execution_plan=final_plan,
        top_findings=_extract_top_findings(results, gq),
        diagnostic_integration=diagnostic_integration,
        lineage_map=parents_map,
    )
    
    # Calculate Artifact Hash (Pure Content)
    # We exclude meta.timestamp, meta.orchestrator_run_id (circular), meta.replay_uri
    # Only hashing inputs + layers content
    content_payload = {
        "inputs": _freeze_reintegration_input(inputs),
        "layers": {
            k: to_plain_data(v) for k, v in results.items() if v
        },
        "plan": to_plain_data(final_plan) if final_plan else None,
        "diagnostic_integration": to_plain_data(diagnostic_integration),
    }
    art_hash = hashlib.sha256(_canonical_json(content_payload).encode("utf-8")).hexdigest()
    art.meta.artifact_hash = art_hash
    
    if store:
        uri = store.save(art)
        art.meta.replay_uri = uri
        
    return art

def run_for_chat(
    inputs: OrchestratorInput,
    store: Optional[LocalJsonStore] = None,
    user_query: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
    user_mode: str = "farmer",
    progress_cb=None,
) -> Tuple[ChatPayload, RunArtifact]:
    """
    Optimized entrypoint for Chat/LLM interactions.
    Runs full pipeline -> Compresses to ChatPayload.
    """
    # 2. Date Resolution
    if user_query:
        # Detect Intent
        intent = detect_intent(user_query, has_context=True)
        
        try:
            # Assume inputs.date_range['end'] is a valid reference date string
            ref_date = datetime.strptime(inputs.date_range['end'], "%Y-%m-%d")
            start, end = resolve_time_window(user_query, ref_date)
            
            # Use replace() for frozen dataclass
            from dataclasses import replace
            inputs = replace(inputs, date_range={
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d")
            })
            
        except Exception as e:
            # Fallback to default inputs if parsing fails
            print(f"Date resolution failed: {e}")
            pass
    
    # 3. Run Pipeline with Intent Routing
    artifact = run_orchestrator(inputs, store, intent=intent, user_query=user_query, progress_cb=progress_cb)
    
    # 4. Safety Assertion (Hard Check)
    if intent == Intent.DATA_QUERY:
        if artifact.layer_3 or artifact.layer_5:
            # This should effectively never happen due to gating above, 
            # but creates a hard invariant for the future.
            pass 
        if artifact.final_execution_plan and artifact.final_execution_plan.tasks:
             # Ensure no INTERVENE
             if any(t.type == "INTERVENE" for t in artifact.final_execution_plan.tasks):
                 raise RuntimeError("SAFETY VIOLATION: DATA_QUERY intent produced INTERVENE tasks.")
                 
    return build_chat_payload(artifact, user_query, intent=intent, history=history, user_mode=user_mode), artifact


def _extract_top_findings(results: Dict, gq) -> list:
    """
    Extract headline findings from layer outputs.
    Grounded in actual data — no hallucination.
    """
    findings = []

    # L1: Weather/soil summary
    l1 = results.get(LayerId.L1)
    if l1 and l1.output:
        ts = getattr(l1.output, "plot_timeseries", [])
        if ts and isinstance(ts, list):
            # Rainfall — plot_timeseries entries are dicts with FieldTensorChannels keys
            rain_vals = []
            temp_maxes = []
            temp_mins = []
            for t in ts:
                if isinstance(t, dict):
                    p = t.get("precipitation") or t.get("rainfall_mm") or t.get("rain")
                    if p is not None:
                        rain_vals.append(float(p))
                    tmax = t.get("temp_max") or t.get("temperature_max") or t.get("tmax") or t.get("tmean")
                    tmin = t.get("temp_min") or t.get("temperature_min") or t.get("tmin") or t.get("tmean")
                    if tmax is not None:
                        temp_maxes.append(float(tmax))
                    if tmin is not None:
                        temp_mins.append(float(tmin))

            if rain_vals:
                total = sum(rain_vals)
                wet_days = sum(1 for v in rain_vals if v > 0.1)
                if total < 5:
                    findings.append(f"Very low rainfall ({total:.1f}mm) \u2014 potential dryness.")
                elif total > 50:
                    findings.append(f"Significant rainfall ({total:.1f}mm over {wet_days} days).")
                else:
                    findings.append(f"Moderate rainfall ({total:.1f}mm over {wet_days} days).")

            # Temperature extremes
            if temp_maxes or temp_mins:
                t_max = max(temp_maxes) if temp_maxes else None
                t_min = min(temp_mins) if temp_mins else None
                if t_max and t_max > 40:
                    findings.append(f"Heat stress risk: peak temperature {t_max:.0f}°C.")
                elif t_min is not None and t_min < 2:
                    findings.append(f"Frost risk: minimum temperature {t_min:.1f}°C.")

        # Soil moisture
        static = getattr(l1.output, "static", {})
        if isinstance(static, dict):
            sm = static.get("soil_moisture")
            if sm and isinstance(sm, dict):
                for depth, val in sm.items():
                    if val is not None and val < 0.15:
                        findings.append(f"Low soil moisture at {depth} ({val:.2f} m³/m³).")
                        break

    # L3: Diagnoses (canonical schema: problem_id, severity 0-1, confidence 0-1)
    l3 = results.get(LayerId.L3)
    if l3 and l3.output:
        for diag in getattr(l3.output, "diagnoses", [])[:3]:
            pid = getattr(diag, "problem_id", "")
            sev = getattr(diag, "severity", 0.0)
            conf = getattr(diag, "confidence", 0.0)
            prob = getattr(diag, "probability", 0.0)
            if pid and prob >= 0.5:
                findings.append(f"Diagnosis: {pid} (severity {sev:.0%}, confidence {conf:.0%}).")

    # L5: Bio threats
    l5 = results.get(LayerId.L5)
    if l5 and l5.output:
        for threat in getattr(l5.output, "threats", [])[:2]:
            name = getattr(threat, "name", "")
            risk = getattr(threat, "risk_level", "")
            if name and risk in ("HIGH", "CRITICAL"):
                findings.append(f"Bio threat: {name} ({risk} risk).")

    # Degradation warnings
    if gq.critical_failure:
        findings.insert(0, "[WARN] Critical data failure — results may be unreliable.")
    elif gq.missing_drivers:
        drivers = ", ".join(gq.missing_drivers[:3])
        findings.append(f"Data gaps: {drivers}.")

    return findings[:5]  # Cap at 5

