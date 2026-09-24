import datetime
import hashlib
import json
import logging
import math
import os
from typing import Any, Dict, List, Mapping, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _attr(value: Any, name: str, default: Any = None) -> Any:
    """Read dataclasses, normal mappings and frozen-manifest object wrappers."""
    if isinstance(value, Mapping):
        mapped = value
        if (
            mapped.get("__asmae_manifest_type__") == "object_v1"
            and isinstance(mapped.get("fields"), Mapping)
        ):
            mapped = mapped["fields"]
        return mapped.get(name, default)
    return getattr(value, name, default)

@dataclass
class ASMAESceneCandidate:
    source: str  # "sentinel2" or "sentinel1"
    reality: str  # "real_raster" | "mean_only" | "raster_composite_proxy" | "unavailable"
    scene_id: Optional[str] = None
    acquisition_datetime: Optional[datetime.datetime] = None
    crs: Optional[str] = None
    transform: Optional[Tuple] = None
    width: Optional[int] = None
    height: Optional[int] = None
    band_refs: Optional[Dict[str, str]] = None
    band_arrays: Optional[Dict[str, Any]] = None
    mask_refs: Optional[Dict[str, str]] = None
    band_units: Optional[Dict[str, str]] = None
    scalar_observations: Optional[Dict[str, float]] = None
    qa_metrics: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    test_override: bool = False
    production_usable: bool = False
    real_provider_product: bool = False
    diagnostic_only: bool = True
    provider_product_id: Optional[str] = None
    catalog_item_id: Optional[str] = None
    provider_tile_id: Optional[str] = None
    provider_orbit_id: Optional[str] = None
    provider_orbit_pass: Optional[str] = None
    product_binding: str = "unknown"
    binding_proof: Optional[Dict[str, Any]] = None
    holdout_proof: Optional[Dict[str, Any]] = None
    registration_proof: Optional[Dict[str, Any]] = None
    field_approval: Optional[Any] = None

def adapt_layer0_package_to_scene_candidate(
    pkg: Any,
    source: str,
    raster_composites: Optional[Dict[str, Any]] = None
) -> ASMAESceneCandidate:
    """
    Converts a Layer0SourcePackage (or raw package) into an ASMAE-readable scene candidate.
    """
    prov = _attr(pkg, "provenance", {}) or {}
    meta = _attr(pkg, "metadata", None) or pkg
    
    # 1. Recover metadata either from direct attribute or provenance
    asmae_meta = prov.get("asmae_scene_metadata", {}) or {}
    incoming_scene_id = _attr(meta, "scene_id", asmae_meta.get("scene_id"))
    prov_pid = (
        _attr(pkg, "provider_product_id", None)
        or asmae_meta.get("provider_product_id")
        or prov.get("provider_product_id")
        or _attr(pkg, "catalog_item_id", None)
        or prov.get("catalog_item_id")
        or _attr(pkg, "product_id", None)
        or prov.get("product_id")
        or _attr(pkg, "source_content_hash", None)
        or prov.get("source_content_hash")
    )
    
    acq_dt = _attr(meta, "acquisition_datetime", None) or _attr(meta, "acquisition_time", None)
    if isinstance(acq_dt, dict):
        acq_str = acq_dt.get("value") or acq_dt.get("iso") or acq_dt.get("datetime") or acq_dt.get("$date")
        if isinstance(acq_str, str):
            try:
                acq_dt = datetime.datetime.fromisoformat(acq_str.replace('Z', '+00:00'))
            except Exception:
                acq_dt = None
        else:
            acq_dt = None
    elif isinstance(acq_dt, str):
        try:
            acq_dt = datetime.datetime.fromisoformat(acq_dt.replace('Z', '+00:00'))
        except Exception:
            acq_dt = None
    if not acq_dt and asmae_meta.get("acquisition_datetime"):
        try:
            acq_dt = datetime.datetime.fromisoformat(str(asmae_meta["acquisition_datetime"]).replace('Z', '+00:00'))
        except Exception:
            acq_dt = None

    crs = _attr(meta, "crs", asmae_meta.get("crs"))
    transform = _attr(meta, "transform", asmae_meta.get("transform"))
    width = _attr(meta, "width", asmae_meta.get("width"))
    height = _attr(meta, "height", asmae_meta.get("height"))
    orbit_pass = _attr(meta, "orbit_pass", asmae_meta.get("orbit_pass")) or prov.get("orbit_pass") or "unknown"
    polarization = _attr(meta, "polarization", asmae_meta.get("polarization")) or prov.get("polarization") or "unknown"

    acq_iso = acq_dt.isoformat() if hasattr(acq_dt, "isoformat") else "unknown"
    scene_identity_v2 = {
        "version": "scene_identity_v2",
        "source_sensor": source,
        "provider_product_id": str(prov_pid or ""),
        "acquisition_datetime_iso": acq_iso,
        "orbit_pass": str(orbit_pass),
        "polarization": str(polarization),
        "crs": str(crs or ""),
        "transform_digest": str(transform or ""),
    }
    canonical_scene_id = f"{source}_{hashlib.sha256(json.dumps(scene_identity_v2, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()}"
    scene_id = canonical_scene_id
    if incoming_scene_id and incoming_scene_id != canonical_scene_id:
        prov["legacy_ordinal_scene_id"] = incoming_scene_id
    
    def normalize_band_key(key: str) -> str:
        k = key.lower().strip()
        if k in ("b04", "red"):
            return "B04"
        if k in ("b08", "nir"):
            return "B08"
        if k in ("b02", "blue"):
            return "B02"
        if k in ("b03", "green"):
            return "B03"
        if k in ("b05", "rededge1"):
            return "B05"
        if k in ("b06", "rededge2"):
            return "B06"
        if k in ("b07", "rededge3"):
            return "B07"
        if k in ("b8a", "b8a"):
            return "B8A"
        if k in ("b11", "swir1"):
            return "B11"
        if k in ("b12", "swir2"):
            return "B12"
        if k in ("vv", "sar_vv"):
            return "VV"
        if k in ("vh", "sar_vh"):
            return "VH"
        if k in ("scl", "qa"):
            return "SCL"
        if k in ("datamask", "data_mask", "data-mask"):
            return "DATAMASK"
        return key

    # Extract band references and arrays from package
    band_refs = {}
    raw_band_arrays = _attr(pkg, "band_arrays", {}) or {}
    if not isinstance(raw_band_arrays, dict):
        raw_band_arrays = {}
    # BC.10.13 P2d: normalize band_arrays keys the same way band_refs keys are normalized.
    band_arrays = {normalize_band_key(k): v for k, v in raw_band_arrays.items()}

    def _resolve_ref_path(v: Any) -> Any:
        if isinstance(v, Mapping):
            rel = v.get("relative_path") or v.get("path") or v.get("portable_uri")
            if rel and isinstance(rel, str):
                if os.path.exists(rel):
                    return rel
                job_p = os.path.join("services", "agribrain", "artifacts", "asmae_jobs", rel)
                if os.path.exists(job_p):
                    return job_p
                norm_rel = rel.replace("\\", "/")
                for candidate_base in ("services/agribrain/artifacts/asmae_jobs", "artifacts/asmae_jobs"):
                    cand = os.path.join(candidate_base, norm_rel)
                    if os.path.exists(cand):
                        return cand
        return v

    pkg_band_refs = _attr(pkg, "local_cache_refs", {}) or _attr(pkg, "band_refs", {}) or {}
    if isinstance(pkg_band_refs, dict):
        for k, v in pkg_band_refs.items():
            band_refs[normalize_band_key(k)] = _resolve_ref_path(v)

    raw_band_units = (
        _attr(pkg, "band_units", {})
        or _attr(meta, "band_units", {})
        or asmae_meta.get("band_units", {})
        or {}
    )
    band_units = {
        normalize_band_key(k): str(v).strip().lower()
        for k, v in raw_band_units.items()
        if v is not None
    } if isinstance(raw_band_units, dict) else {}

    # Extract scalar observations (e.g. from telemetry metrics packets)
    scalar_obs = {}
    packets = _attr(pkg, "packets", []) or []
    if packets:
        # Sort packages chronologically
        first_pkt = packets[0]
        payload_dict = {}
        if isinstance(first_pkt, dict):
            payload_dict = first_pkt
        else:
            payload_dict = getattr(first_pkt, "payload", {}) or {}
            if not isinstance(payload_dict, dict):
                payload_dict = {}

        def _get_field(key: str) -> Any:
            if isinstance(first_pkt, dict):
                return first_pkt.get(key)
            val = _attr(first_pkt, key, None)
            if val is not None:
                return val
            return payload_dict.get(key)

        scalar_obs["ndvi_mean"] = _get_field("ndvi_mean")
        scalar_obs["evi_mean"] = _get_field("evi_mean")
        scalar_obs["ndmi_mean"] = _get_field("ndmi_mean")
        scalar_obs["ndre_mean"] = _get_field("ndre_mean")
        scalar_obs["bsi_mean"] = _get_field("bsi_mean")
        scalar_obs["vv_db_mean"] = _get_field("vv_db_mean")
        scalar_obs["vh_db_mean"] = _get_field("vh_db_mean")
        scalar_obs = {
            key: float(value)
            for key, value in scalar_obs.items()
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        }

    def _has_loadable_source(band_name: str, refs: dict, arrays: dict) -> bool:
        if band_name in arrays and arrays[band_name] is not None:
            return True
        if band_name in refs and refs[band_name]:
            return True
        return False

    def _is_valid_transform(t: Any) -> bool:
        if not t or not isinstance(t, (list, tuple)) or len(t) != 6:
            return False
        try:
            return all(isinstance(x, (int, float)) for x in t)
        except Exception:
            return False

    # 2. Classify reality
    is_synthetic_proxy = False
    pkg_source_reality = _attr(pkg, "source_reality", None)
    if pkg_source_reality in ("synthetic_visual_proxy", "raster_composite_proxy"):
        is_synthetic_proxy = True

    if packets:
        for p in packets:
            p_data = p
            if isinstance(p, dict):
                p_data = p.get("data") or p.get("payload") or p
            if isinstance(p_data, dict):
                sr = p_data.get("source_reality")
                if sr in ("synthetic_visual_proxy", "raster_composite_proxy"):
                    is_synthetic_proxy = True
                    break
            else:
                sr = _attr(p_data, "source_reality", None)
                if sr in ("synthetic_visual_proxy", "raster_composite_proxy"):
                    is_synthetic_proxy = True
                    break

    if os.environ.get("ASMAE_TEST_OVERRIDE") == "true" and pkg_source_reality != "raster_composite_proxy":
        is_synthetic_proxy = False

    has_real_raster = False
    
    if not is_synthetic_proxy and (acq_dt is not None 
        and crs 
        and _is_valid_transform(transform) 
        and isinstance(width, int) and width > 0 
        and isinstance(height, int) and height > 0):
        
        if source == "sentinel2":
            if (_has_loadable_source("B04", band_refs, band_arrays) 
                and _has_loadable_source("B08", band_refs, band_arrays)):
                has_real_raster = True
        elif source == "sentinel1":
            if (_has_loadable_source("VV", band_refs, band_arrays) 
                or _has_loadable_source("VH", band_refs, band_arrays)):
                has_real_raster = True
                
    has_mean_only = False
    if not has_real_raster:
        if acq_dt and scalar_obs:
            has_mean_only = True
        
    reality = "unavailable"
    if is_synthetic_proxy:
        reality = "raster_composite_proxy"
    elif has_real_raster:
        reality = "real_raster"
    elif has_mean_only:
        reality = "mean_only"
    
    # 3. Check for proxy fallback
    if reality in ("unavailable", "mean_only") and raster_composites:
        # Check if we have valid raster composites that could act as a proxy
        valid_comp = False
        for k in ["NDVI", "NDVI_CLEAN", "SAR", "ndmi"]:
            if k in raster_composites and isinstance(raster_composites[k], dict):
                grid = raster_composites[k].get("values", [])
                if grid and isinstance(grid, list) and len(grid) > 0 and isinstance(grid[0], list):
                    valid_comp = True
                    break
        if valid_comp:
            reality = "raster_composite_proxy"

    if os.environ.get("ASMAE_TEST_OVERRIDE") == "true" and reality == "real_raster":
        reality = "test_fixture_raster"

    # Extract QA
    qa_metrics = {}
    scalar_usable = True
    if packets:
        first = packets[0]
        if isinstance(first, dict):
            data = first.get("data") or first.get("payload") or first
        else:
            data = _attr(first, "payload", None) or _attr(first, "data", None) or {}
            
        if isinstance(data, dict):
            qa_metrics["cloud_cover"] = data.get("cloud_cover", _attr(pkg, "cloud_cover", None))
            qa_metrics["data_status"] = data.get("data_status", "observed")
            scalar_usable = data.get("usable", True)
            qa_metrics["scalar_summary_usable"] = scalar_usable
            qa_metrics["orbit_direction"] = data.get("orbit_direction")

    qa_obj = _attr(pkg, "qa", None)
    if qa_obj:
        qc = _attr(qa_obj, "quality_class", None)
        qa_metrics["quality_class"] = _attr(qc, "value", "good") if qc else "good"
        qa_metrics["valid_fraction"] = _attr(qa_obj, "valid_fraction", 1.0)
        qa_metrics["usable"] = bool(_attr(qa_obj, "usable", True))
        qa_metrics["raster_scene_usable"] = qa_metrics["usable"]
    else:
        quality = _attr(pkg, "quality", {}) or {}
        qa_metrics["quality_class"] = quality.get("quality_class", "good") if isinstance(quality, dict) else "good"
        qa_metrics["valid_fraction"] = quality.get("valid_fraction", 1.0) if isinstance(quality, dict) else 1.0
        qa_metrics["usable"] = bool(quality.get("usable", True)) if isinstance(quality, dict) else True
        qa_metrics["raster_scene_usable"] = qa_metrics["usable"]

    return ASMAESceneCandidate(
        source=source,
        reality=reality,
        scene_id=scene_id,
        acquisition_datetime=acq_dt,
        crs=crs,
        transform=transform,
        width=width,
        height=height,
        band_refs=band_refs,
        band_arrays=band_arrays,
        # BC.10.13 P2d: preserve mask_refs from SceneProduct (SCL/cloud masks) instead of
        # always emitting an empty dict, which was silently discarding cloud/data masks.
        mask_refs={normalize_band_key(k): _resolve_ref_path(v) for k, v in (_attr(pkg, "mask_refs", {}) or {}).items()},
        band_units=band_units,
        scalar_observations=scalar_obs,
        qa_metrics=qa_metrics,
        provenance=prov,
        test_override=_attr(pkg, "test_override", False),
        production_usable=_attr(pkg, "production_usable", False),
        real_provider_product=_attr(pkg, "real_provider_product", False),
        diagnostic_only=_attr(pkg, "diagnostic_only", True),
        provider_product_id=_attr(pkg, "provider_product_id", None),
        catalog_item_id=_attr(pkg, "catalog_item_id", None),
        provider_tile_id=_attr(pkg, "provider_tile_id", None),
        provider_orbit_id=_attr(pkg, "provider_orbit_id", None),
        provider_orbit_pass=_attr(pkg, "provider_orbit_pass", None),
        product_binding=_attr(pkg, "product_binding", "unknown"),
        binding_proof=dict(_attr(pkg, "binding_proof", {}) or {}),
        holdout_proof=_attr(pkg, "holdout_proof", None) or _attr(_attr(pkg, "metadata", {}), "holdout_proof", None),
        registration_proof=_attr(pkg, "registration_proof", None) or _attr(_attr(pkg, "metadata", {}), "registration_proof", None),
        field_approval=_attr(pkg, "field_approval", None) or _attr(_attr(pkg, "metadata", {}), "field_approval", None),
    )
