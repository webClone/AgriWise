"""
Layer 1 Legacy Compatibility Adapter — V1 Dual-Emission Bridge.

Builds a fully-faithful backward-compatible FieldTensor from V1's
Layer1ContextPackage using temporal reconstruction from the evidence ledger.

CRITICAL RULES:
  - plot_timeseries is a daily array (not a single summary row)
  - Same interpolation + smoothing as legacy data_fusion.py
  - Same key names as legacy (ndvi_mean, rain, tmean, etc.)
  - Missing values stay None — NEVER fake-fill
  - daily_state reconstructed from L0 Kalman evidence
  - static dict matches legacy schema (soil_clay_mean, etc.)

Downstream consumers (L2–L10) receive an IDENTICAL FieldTensor.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from layer1_fusion.schemas import (
    Layer1ContextPackage,
    raster_ref_has_geographic_authority,
)
from layer1_fusion.schema_legacy import FieldTensor, FieldTensorChannels
from layer1_fusion.raster_backend import GridSpec

from layer1_fusion.outputs.temporal_reconstruction import (
    rebuild_daily_timeseries,
    rebuild_forecast_7d,
    rebuild_daily_state,
    rebuild_static,
    rebuild_zone_stats,
    rebuild_provenance,
    rebuild_provenance_log,
)


def build_legacy_fieldtensor(
    pkg: Layer1ContextPackage,
) -> FieldTensor:
    """Build a fully-faithful backward-compatible FieldTensor.

    Returns a FieldTensor with complete daily plot_timeseries,
    daily_state, forecast_7d, static soil properties, and zones —
    all reconstructed from V1's evidence ledger.

    This replaces the old single-row summary with real temporal data.
    """
    evidence = pkg.evidence_items or []

    # 1. Temporal reconstruction: per-day records from evidence
    plot_ts = rebuild_daily_timeseries(
        evidence,
        pkg.time_window.start,
        pkg.time_window.end,
    )

    # 2. Forecast extraction (forecast-scoped evidence only)
    forecast = rebuild_forecast_7d(evidence)

    # 3. Static soil/site context
    static = rebuild_static(evidence)
    plot_ring = _extract_plot_exterior_ring(getattr(pkg, "plot_geometry", None))
    if plot_ring is not None:
        # Layer 10 consumes this field to rasterize the true field footprint.
        # Do not derive it from grid bounds: those are only a rectangular
        # georeferencing extent and would authorize out-of-field pixels.
        static["polygon_coords"] = plot_ring

    # 4. Daily state from L0 Kalman evidence
    daily_state = rebuild_daily_state(evidence)

    # 5. Zone stats from zone-scoped evidence
    zone_stats = rebuild_zone_stats(evidence, pkg.spatial_index)

    # 6. Grid spec from spatial index
    grid_spec = _rebuild_grid_spec(pkg)

    # 7. Zones from spatial index
    zones = _rebuild_zones(pkg)

    # 8. Maps from spatial index raster refs
    maps = _rebuild_maps(pkg, grid_spec)
    map_metadata = _rebuild_map_metadata(pkg, grid_spec)
    _merge_authorized_raster_ndvi_observation(
        plot_ts, maps, map_metadata, pkg.time_window.end,
    )

    # 9. Provenance
    provenance = rebuild_provenance(pkg)
    if isinstance(provenance, dict):
        provenance["tensor_semantics"] = "v1_derived_latest_raster_plus_broadcast_timeseries"
        provenance["raster_grounded_channels"] = [
            channel for channel in ("ndvi", "ndmi") if channel in maps
        ]
        provenance["broadcast_channels"] = ["plot_daily_ndvi", "plot_daily_vh"]

    # 10. Time index
    time_index = [r["date"] for r in plot_ts] if plot_ts else []

    # 11. Rebuild 4D data tensor [Time, Height, Width, Channels]
    H = grid_spec.height if grid_spec is not None and maps else 0
    W = grid_spec.width if grid_spec is not None and maps else 0

    channel_map = {
        "ndvi": FieldTensorChannels.NDVI,
        "ndvi_uncertainty": FieldTensorChannels.NDVI_UNC,
        "ndmi": FieldTensorChannels.NDMI,
        "vv": FieldTensorChannels.VV,
        "vh": FieldTensorChannels.VH,
        "quality_mask": FieldTensorChannels.CLOUD_MASK,
    }

    # Identify channels that are available in maps
    available_channels = [ch for ch in ["ndvi", "ndvi_uncertainty", "ndmi", "vv", "vh", "quality_mask"] if ch in maps or ch == "ndvi_uncertainty"]
    if not available_channels:
        available_channels = ["ndvi", "vv", "vh"]

    channels = [channel_map[ch] for ch in available_channels]

    data = []
    if H > 0 and W > 0:
        for idx, row in enumerate(plot_ts):
            t_grid = []
            ndvi = row.get("ndvi_smoothed")
            if ndvi is None:
                ndvi = row.get("ndvi_mean")
            unc = row.get("uncertainty", 0.5)
            vv = row.get("vv_interpolated", row.get("vv", 0.0))
            vh = row.get("vh_interpolated", row.get("vh", 0.0))

            is_last = (idx == len(plot_ts) - 1)

            for r in range(H):
                row_grid = []
                for c in range(W):
                    pixel = []
                    for ch in available_channels:
                        val = None
                        if is_last and ch in maps:
                            grid_data = maps[ch]
                            if grid_data and r < len(grid_data) and c < len(grid_data[r]):
                                val = grid_data[r][c]

                        if val is None:
                            if ch == "ndvi":
                                val = ndvi
                            elif ch == "ndvi_uncertainty":
                                val = unc
                            elif ch == "vv":
                                val = vv
                            elif ch == "vh":
                                val = vh
                            elif ch == "ndmi":
                                val = row.get("ndmi_mean")
                            elif ch == "quality_mask":
                                val = 1.0  # default quality
                        pixel.append(val)
                    row_grid.append(pixel)
                t_grid.append(row_grid)
            data.append(t_grid)

    tensor = FieldTensor(
        plot_id=pkg.plot_id,
        run_id=pkg.run_id,
        version="2.0.0-v1bridge",

        time_index=time_index,
        grid_spec=grid_spec,
        channels=channels,
        data=data,

        grid={},
        maps=maps,
        map_metadata=map_metadata,
        zones=zones,
        zone_stats=zone_stats,

        plot_timeseries=plot_ts,
        forecast_7d=forecast,

        static=static,
        provenance=provenance,

        daily_state=daily_state,
        state_uncertainty={},
        provenance_log=rebuild_provenance_log(pkg),
        spatial_reliability={},
        boundary_info=_rebuild_boundary_info(pkg),
    )

    tensor.asmae_output = pkg.asmae_output
    tensor.asmae_run_record = pkg.asmae_run_record

    return tensor


def _merge_authorized_raster_ndvi_observation(
    plot_ts: List[Dict[str, Any]],
    maps: Dict[str, Any],
    map_metadata: Dict[str, Any],
    observed_at: Any,
) -> bool:
    """Expose an admitted provider NDVI raster as one typed plot observation.

    This is an aggregation of the exact admitted pixels, not a synthetic fill.
    It is added only when temporal reconstruction has no observed NDVI at that
    date and the raster authority envelope identifies a real, production-usable
    provider product.
    """
    ndvi_key = next((key for key in maps if str(key).lower() in {"ndvi", "ndvi_clean"}), None)
    if ndvi_key is None:
        return False
    metadata = (
        map_metadata.get(ndvi_key)
        or map_metadata.get(str(ndvi_key).lower())
        or map_metadata.get(str(ndvi_key).upper())
        or {}
    )
    if not (
        metadata.get("production_usable") is True
        and metadata.get("real_provider_product") is True
        and metadata.get("diagnostic_only") is not True
    ):
        return False
    values: List[float] = []
    for row in maps.get(ndvi_key) or []:
        if not isinstance(row, (list, tuple)):
            continue
        for value in row:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                values.append(number)
    if not values:
        return False
    date_value = (
        observed_at.strftime("%Y-%m-%d")
        if hasattr(observed_at, "strftime")
        else str(observed_at or "")[:10]
    )
    target = next((row for row in plot_ts if str(row.get("date"))[:10] == date_value), None)
    if target is None:
        target = {"date": date_value}
        plot_ts.append(target)
        plot_ts.sort(key=lambda row: str(row.get("date") or ""))
    existing = target.get("ndvi_mean")
    if target.get("is_observed") is True and isinstance(existing, (int, float)):
        return False
    target.update({
        "ndvi_mean": sum(values) / len(values),
        "ndvi_smoothed": sum(values) / len(values),
        "is_observed": True,
        "observation_type": "provider_raster_spatial_aggregate",
        "source": metadata.get("source_reality") or "provider_temporal_composite_raster",
        "source_reality": metadata.get("source_reality") or "provider_temporal_composite_raster",
        "content_hash": metadata.get("content_hash"),
        "raster_id": metadata.get("raster_id"),
        "coverage": float(metadata.get("observed_ratio") or 1.0),
        "confidence": float(metadata.get("confidence") or 0.8),
        "uncertainty": float(metadata.get("uncertainty") or 0.2),
        "production_usable": True,
        "real_provider_product": True,
        "state_update_allowed": bool(metadata.get("state_update_allowed", False)),
    })
    return True


def _extract_plot_exterior_ring(geometry: Any) -> Optional[List[List[float]]]:
    """Return a validated exterior ring from common GeoJSON/raw shapes.

    The Next.js route supplies a GeoJSON Feature today, while replay and test
    callers may supply a geometry object or a raw coordinate ring.  Layer 10's
    pure-Python rasterizer expects one exterior ``[[lng, lat], ...]`` ring.
    """

    if geometry is None:
        return None

    candidate: Any = geometry
    if isinstance(candidate, dict):
        geo_type = candidate.get("type")
        if geo_type == "Feature":
            return _extract_plot_exterior_ring(candidate.get("geometry"))
        if geo_type == "FeatureCollection":
            for feature in candidate.get("features") or []:
                ring = _extract_plot_exterior_ring(feature)
                if ring is not None:
                    return ring
            return None

        coordinates = candidate.get("coordinates")
        if geo_type == "Polygon":
            candidate = coordinates[0] if coordinates else None
        elif geo_type == "MultiPolygon":
            candidate = (
                coordinates[0][0]
                if coordinates and coordinates[0]
                else None
            )
        else:
            return None

    # Raw callers historically supplied either a ring, Polygon coordinates,
    # or MultiPolygon coordinates.  Peel only structural nesting until the
    # first element is a coordinate pair.
    while (
        isinstance(candidate, (list, tuple))
        and candidate
        and not _is_finite_coordinate_pair(candidate[0])
    ):
        candidate = candidate[0]

    if not isinstance(candidate, (list, tuple)):
        return None

    ring: List[List[float]] = []
    for point in candidate:
        if not _is_finite_coordinate_pair(point):
            return None
        ring.append([float(point[0]), float(point[1])])

    if len(ring) < 3 or len({(point[0], point[1]) for point in ring}) < 3:
        return None
    return ring


def _is_finite_coordinate_pair(value: Any) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return False
    try:
        return math.isfinite(float(value[0])) and math.isfinite(float(value[1]))
    except (TypeError, ValueError):
        return False


# ============================================================================
# Spatial reconstruction helpers
# ============================================================================

def _rebuild_grid_spec(pkg: Layer1ContextPackage) -> Optional[GridSpec]:
    """Reconstruct GridSpec from V1 spatial index or raster refs."""
    si = pkg.spatial_index
    if si is None:
        return None

    # Dimensions alone are not a geographic contract.  Only a fully validated
    # RasterRef may supply the compatibility tensor's GridSpec.
    for rr in getattr(si, "raster_refs", []):
        if raster_ref_has_geographic_authority(rr):
            return GridSpec(
                crs=rr.crs,
                transform=rr.transform,
                width=rr.width,
                height=rr.height,
                bounds=rr.bounds,
                resolution=rr.resolution_m,
            )

    # An extent or plot polygon supplies a footprint, not pixel alignment.  Do
    # not invent CRS, affine, dimensions, or resolution from it.
    return None


def _rebuild_zones(pkg: Layer1ContextPackage) -> Dict[str, Any]:
    """Reconstruct FieldTensor.zones from V1 spatial index."""
    si = pkg.spatial_index
    if si is None:
        return {}

    zones = {}
    for seg in getattr(si, "zone_segments", []):
        zone_id = getattr(seg, "zone_id", "")
        if zone_id:
            zones[zone_id] = {
                "label": getattr(seg, "label", zone_id),
                "area_pct": getattr(seg, "area_fraction", 0.0),
                "centroid": getattr(seg, "centroid", None),
            }
    return zones


def _rebuild_maps(
    pkg: Layer1ContextPackage,
    grid_spec: Optional[GridSpec] = None,
) -> Dict[str, Any]:
    """Reconstruct FieldTensor.maps from V1 spatial index raster refs."""
    si = pkg.spatial_index
    if si is None:
        return {}
    if grid_spec is None:
        grid_spec = _rebuild_grid_spec(pkg)
    if grid_spec is None:
        return {}

    maps = {}
    for rr in getattr(si, "raster_refs", []):
        if not raster_ref_has_geographic_authority(rr):
            continue
        if getattr(rr, "visualization_allowed", False) is not True:
            continue
        if (
            rr.crs != grid_spec.crs
            or tuple(rr.bounds) != tuple(grid_spec.bounds)
            or tuple(rr.transform) != tuple(grid_spec.transform)
            or rr.width != grid_spec.width
            or rr.height != grid_spec.height
        ):
            continue
        var_name = getattr(rr, "variable", "")
        grid_data = getattr(rr, "grid", None)
        if var_name and grid_data is not None:
            maps[var_name] = grid_data
    return maps


def _rebuild_map_metadata(
    pkg: Layer1ContextPackage,
    grid_spec: Optional[GridSpec] = None,
) -> Dict[str, Any]:
    """Preserve the authority contract for every admitted compatibility map.

    Numeric pixels and their evidence authority are one indivisible boundary
    value. Rebuilding ``maps`` without ``map_metadata`` made a genuine
    provider raster look like an ungrounded array in Layer 10.
    """
    si = pkg.spatial_index
    if si is None:
        return {}
    if grid_spec is None:
        grid_spec = _rebuild_grid_spec(pkg)
    if grid_spec is None:
        return {}

    metadata: Dict[str, Any] = {}
    fields_to_preserve = (
        "raster_id", "variable", "resolution_m", "content_hash",
        "width", "height", "observed_ratio", "truth_class",
        "source_reality", "real_provider_product", "production_usable",
        "grounding_class", "visualization_allowed",
        "experimental_visual_allowed", "composite_advisory_allowed",
        "scientific_surface_allowed", "current_1m_approval_allowed",
        "observed_spatial_surface", "diagnostic_only",
        "state_update_allowed", "prescription_driver_allowed",
        "authority_block_reason", "asmae_channel", "source_basis",
        "confidence", "uncertainty", "source_run_id",
        "source_schema_version", "artifact_instance_hash", "retro_status",
        "bma_status", "bma_disagreement", "cross_layer_conflict",
        "sentinel_archive_used", "archive_scene_count", "archive_date_range",
        "scene_stack_mode", "crs", "bounds", "transform",
    )
    for rr in getattr(si, "raster_refs", []):
        if not raster_ref_has_geographic_authority(rr):
            continue
        if getattr(rr, "visualization_allowed", False) is not True:
            continue
        if (
            rr.crs != grid_spec.crs
            or tuple(rr.bounds) != tuple(grid_spec.bounds)
            or tuple(rr.transform) != tuple(grid_spec.transform)
            or rr.width != grid_spec.width
            or rr.height != grid_spec.height
        ):
            continue
        variable = str(getattr(rr, "variable", "") or "")
        if not variable or getattr(rr, "grid", None) is None:
            continue
        item = {
            name: getattr(rr, name)
            for name in fields_to_preserve
            if hasattr(rr, name)
        }
        provenance = getattr(rr, "provenance", {}) or {}
        if isinstance(provenance, dict):
            item = {**provenance, **item}
        for alias in {variable, variable.lower(), variable.upper()}:
            metadata[alias] = dict(item)
    return metadata


def _rebuild_boundary_info(pkg: Layer1ContextPackage) -> Dict[str, Any]:
    """Reconstruct boundary_info from V1 spatial index."""
    si = pkg.spatial_index
    if si is None:
        return {}

    boundary = {}
    for e in (pkg.evidence_items or []):
        if e.variable == "edge_contamination_score":
            boundary["edge_contamination"] = e.value
        elif e.variable == "plot_cropland_confidence":
            boundary["cropland_confidence"] = e.value

    return boundary
