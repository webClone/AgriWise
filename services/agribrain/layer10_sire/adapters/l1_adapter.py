"""
L1 Adapter — Extract spatial data from FieldTensor (v2 Temporal)
=================================================================

Normalizes L1 FieldTensor into Layer 10 internal structures.
Now extracts FULL temporal history (all time steps from 4D tensor)
for 14-day temporal awareness (T-7 retrospective + T+7 forecast).

Handles: 4D tensor data, maps, zones, zone_stats, daily_state,
         provenance_log, spatial_reliability, grid_spec,
         raster_composites, observation_products, forecast context.
"""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class L1SpatialData:
    """Normalized L1 spatial extraction for Layer 10 (v2 — Temporal)."""
    # Grid dimensions (from grid_spec or tensor shape)
    height: int = 10
    width: int = 10
    resolution_m: float = 10.0
    grid_spec: Optional[Dict[str, Any]] = None

    # Raster maps — variable→2D array [H][W] (LATEST time step)
    raster_maps: Dict[str, List[List[Optional[float]]]] = field(default_factory=dict)

    # Raster metadata — variable→dict of metadata properties (V82)
    raster_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # === TEMPORAL EXTRACTION (14-day window) ===
    # Full temporal raster history: date→variable→2D grid [H][W]
    temporal_rasters: Dict[str, Dict[str, List[List[Optional[float]]]]] = field(default_factory=dict)
    # Ordered date index from FieldTensor.time_index
    time_index: List[str] = field(default_factory=list)
    # Per-date metadata (source, quality, cloud cover)
    temporal_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Zone structure — zone_id→cell mask
    zone_masks: Dict[str, List[Tuple[int, int]]] = field(default_factory=dict)
    zone_areas: Dict[str, float] = field(default_factory=dict)  # fraction
    zone_labels: Dict[str, str] = field(default_factory=dict)

    # Per-zone time series — variable→zone_id→list of values
    zone_timeseries: Dict[str, Dict[str, List[float]]] = field(default_factory=dict)

    # Field-level time series (last values) — variable→float
    last_values: Dict[str, float] = field(default_factory=dict)

    # Source provenance — per-day source contributions
    source_contributions: List[Dict[str, Any]] = field(default_factory=list)

    # Spatial reliability raster [H][W]
    reliability_map: Optional[List[List[float]]] = None

    # === WEATHER / FORECAST CONTEXT ===
    # Daily weather observations (from daily_state or plot_timeseries)
    weather_history: List[Dict[str, Any]] = field(default_factory=list)
    # {date, precipitation_mm, temp_max, temp_min, humidity, et0, ...}

    # Run ID
    run_id: str = ""

    # Observed satellite ratios per channel (raw non-None pixels / total cells)
    observed_ratios: Dict[str, float] = field(default_factory=dict)

    # Pre-backfill observed masks per channel (True where raw pixels were observed)
    observed_masks: Dict[str, List[List[bool]]] = field(default_factory=dict)
    
    # ASMAE run record (V92.4-BC.6)
    asmae_run_record: Optional[Dict[str, Any]] = None
    asmae_evidence_state: Optional[Dict[str, Any]] = None
    real_asmae_evidence: bool = False
    asmae_feature_pack: Optional[Dict[str, Any]] = None


def _extract_temporal_rasters(
    tensor_data: list, channels: list, time_index: list,
    H: int, W: int
) -> Tuple[
    Dict[str, Dict[str, List[List[Optional[float]]]]],
    Dict[str, List[List[Optional[float]]]]
]:
    """
    Extract ALL time-step rasters from 4D tensor [T, H, W, C].

    Returns:
        temporal_rasters: date→channel→[H][W] grid
        latest_rasters: channel→[H][W] grid (last time step)
    """
    temporal = {}
    latest = {}
    n_steps = len(tensor_data)

    for t_idx in range(n_steps):
        t_slice = tensor_data[t_idx]
        if not isinstance(t_slice, list) or len(t_slice) == 0:
            continue

        # Use time_index date or synthesize one
        date_key = time_index[t_idx] if t_idx < len(time_index) else f"T{t_idx}"
        actual_h = len(t_slice)
        actual_w = len(t_slice[0]) if t_slice[0] else 0

        date_rasters = {}
        for ci, ch in enumerate(channels):
            ch_name = ch.value if hasattr(ch, 'value') else str(ch)
            raster = [[None] * W for _ in range(H)]
            for r in range(min(H, actual_h)):
                for c in range(min(W, actual_w)):
                    try:
                        val = t_slice[r][c][ci]
                        raster[r][c] = float(val) if val is not None else None
                    except (IndexError, TypeError):
                        pass
                    except Exception:
                        pass
            date_rasters[ch_name] = raster

            # Keep track of latest
            if t_idx == n_steps - 1:
                latest[ch_name] = raster

        temporal[date_key] = date_rasters

    return temporal, latest


def _extract_weather_history(field_tensor: Any) -> List[Dict[str, Any]]:
    """Extract daily weather observations from daily_state or plot_timeseries."""
    weather = []

    # Try daily_state first
    ds = getattr(field_tensor, 'daily_state', {}) or {}
    if isinstance(ds, dict):
        # Look for weather-related keys in daily state
        weather_keys = {
            'precipitation', 'precipitation_mm', 'rain_mm',
            'temp_max', 'temp_min', 'temperature',
            'humidity', 'rh', 'et0', 'evapotranspiration',
            'wind_speed', 'solar_radiation',
        }
        # Try to reconstruct daily weather from per-variable daily_state
        daily_map = {}  # date → {var: val}
        for var_name, values in ds.items():
            if isinstance(values, list):
                for i, entry in enumerate(values):
                    if isinstance(entry, dict):
                        day = entry.get('day', entry.get('date', f'day_{i}'))
                        if day not in daily_map:
                            daily_map[day] = {'date': day}
                        for k, v in entry.items():
                            if k not in ('day', 'date') and isinstance(v, (int, float)):
                                daily_map[day][k] = float(v)
        weather = list(daily_map.values())

    # Supplement from plot_timeseries
    if not weather:
        pts = getattr(field_tensor, 'plot_timeseries', []) or []
        for entry in pts:
            if isinstance(entry, dict):
                weather.append({
                    k: float(v) if isinstance(v, (int, float)) else v
                    for k, v in entry.items()
                })

    return weather


def adapt_l1(field_tensor: Any, target_h: int = 10, target_w: int = 10, skip_idw: bool = False) -> L1SpatialData:
    """
    Extract all spatial intelligence from FieldTensor (v2 — Full Temporal).

    Now extracts ALL time steps for 14-day temporal awareness.

    Priority:
      1. Real 4D tensor data (spatial truth) — ALL time steps
      2. maps dict (raster refs)
      3. zone_stats (per-zone timeseries)
      4. daily_state (per-zone daily state + weather)
      5. plot_timeseries (field-level fallback)
    """
    if field_tensor is None:
        return L1SpatialData(height=target_h, width=target_w)

    result = L1SpatialData(
        height=target_h,
        width=target_w,
        run_id=getattr(field_tensor, 'run_id', ''),
    )

    # --- Extract grid dimensions from grid_spec ---
    gs = getattr(field_tensor, 'grid_spec', None)
    if isinstance(gs, dict):
        result.grid_spec = gs
        h = gs.get("height", target_h)
        w = gs.get("width", target_w)
        res = gs.get("resolution", gs.get("resolution_m", 10.0))
        if h > 0 and w > 0:
            result.height = h
            result.width = w
            result.resolution_m = res
    elif gs is not None:
        h = getattr(gs, 'height', target_h)
        w = getattr(gs, 'width', target_w)
        res = getattr(gs, 'resolution', getattr(gs, 'resolution_m', 10.0))
        if h > 0 and w > 0:
            result.height = h
            result.width = w
            result.resolution_m = res
        result.grid_spec = {
            "crs": getattr(gs, "crs", None),
            "transform": getattr(gs, "transform", None),
            "bounds": getattr(gs, "bounds", None),
            "width": getattr(gs, "width", result.width),
            "height": getattr(gs, "height", result.height),
            "resolution_m": getattr(gs, "resolution_m", result.resolution_m),
        }

    H, W = result.height, result.width

    # --- Extract time index ---
    time_index = getattr(field_tensor, 'time_index', []) or []
    result.time_index = [str(t) for t in time_index]

    def _load_raster_from_ref_if_needed(grid_data: Any) -> Any:
        if isinstance(grid_data, str) and (grid_data.startswith("asmae_rasters/") or grid_data.endswith(".npz")):
            import os
            import numpy as np
            from common.safe_npz import safe_np_load
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            full_path = os.path.join(base_dir, "artifacts", grid_data)
            if os.path.exists(full_path):
                try:
                    with safe_np_load(full_path) as data:
                        for key in data.files:
                            arr = data[key]
                            grid_list = []
                            for row in arr.tolist():
                                grid_list.append([None if np.isnan(val) else val for val in row])
                            return grid_list
                except Exception:
                    pass
        return grid_data

    # --- Strategy 1: Extract from maps dict (highest priority for real maps) ---
    maps = getattr(field_tensor, 'maps', {}) or {}
    map_metadata = getattr(field_tensor, 'map_metadata', {}) or {}
    for var_name, raw_data in maps.items():
        metadata = {}
        if isinstance(raw_data, dict):
            raster_data = raw_data.get("data")
            metadata.update({k: v for k, v in raw_data.items() if k != "data"})
        else:
            raster_data = raw_data
        
        if var_name in map_metadata:
            meta_val = map_metadata[var_name]
            if isinstance(meta_val, dict):
                metadata.update(meta_val)

        raster_data = _load_raster_from_ref_if_needed(raster_data)
        if hasattr(raster_data, "tolist"):
            raster_data = raster_data.tolist()

        if isinstance(raster_data, list) and len(raster_data) > 0:
            raster = [[None]*W for _ in range(H)]
            for r in range(min(H, len(raster_data))):
                row = raster_data[r]
                if hasattr(row, "tolist"):
                    row = row.tolist()
                if isinstance(row, list):
                    for c in range(min(W, len(row))):
                        raster[r][c] = float(row[c]) if row[c] is not None else None
            result.raster_maps[var_name] = raster
            if metadata:
                keys_to_store = {var_name, var_name.upper(), var_name.lower()}
                if var_name.lower().startswith("asmae_"):
                    suffix = var_name[6:]
                    keys_to_store.add(f"ASMAE_{suffix.upper()}")
                    keys_to_store.add(f"asmae_{suffix.lower()}")
                else:
                    keys_to_store.add(f"ASMAE_{var_name.upper()}")
                    keys_to_store.add(f"asmae_{var_name.lower()}")
                for k in keys_to_store:
                    result.raster_metadata[k] = metadata

    # --- Strategy 2: Extract from RasterRef.grid in V1 context package (next priority) ---
    ctx_pkg = getattr(field_tensor, "_context_package", None)
    if ctx_pkg and hasattr(ctx_pkg, "spatial_index") and ctx_pkg.spatial_index:
        for rr in getattr(ctx_pkg.spatial_index, "raster_refs", []):
            var_name = getattr(rr, "variable", "")
            if var_name:
                import json
                prov = getattr(rr, "provenance", {}) or {}
                if not isinstance(prov, dict):
                    prov = {}
                meta_dict = {
                    "raster_id": getattr(rr, "raster_id", ""),
                    "variable": getattr(rr, "variable", ""),
                    "resolution_m": getattr(rr, "resolution_m", 10.0),
                    "content_hash": getattr(rr, "content_hash", None),
                    "width": getattr(rr, "width", 0),
                    "height": getattr(rr, "height", 0),
                    "observed_ratio": getattr(rr, "observed_ratio", 0.0),
                    "state_update_allowed": getattr(rr, "state_update_allowed", False),
                    "diagnostic_only": getattr(rr, "diagnostic_only", True),
                    "asmae_channel": getattr(rr, "asmae_channel", "diagnostic"),
                    "source_basis": getattr(rr, "source_basis", ""),
                    "confidence": getattr(rr, "confidence", 0.0),
                    "uncertainty": getattr(rr, "uncertainty", 0.0),
                    "source_run_id": getattr(rr, "source_run_id", None),
                    "source_schema_version": getattr(rr, "source_schema_version", None),
                    "artifact_instance_hash": getattr(rr, "artifact_instance_hash", None),
                    "retro_status": getattr(rr, "retro_status", None),
                    "bma_status": getattr(rr, "bma_status", None),
                    "bma_disagreement": getattr(rr, "bma_disagreement", 0.0),
                    "cross_layer_conflict": getattr(rr, "cross_layer_conflict", 0.0),
                    "sentinel_archive_used": getattr(rr, "sentinel_archive_used", False),
                    "archive_scene_count": getattr(rr, "archive_scene_count", 0),
                    "archive_date_range": getattr(rr, "archive_date_range", None),
                    "scene_stack_mode": getattr(rr, "scene_stack_mode", None),
                    # Preserve the Layer-1 truth/authority contract verbatim.
                    # Layer 10 must not infer provider reality merely because a
                    # finite raster happened to arrive on a valid grid.
                    "truth_class": getattr(rr, "truth_class", "unknown"),
                    "source_reality": getattr(rr, "source_reality", "unknown"),
                    "real_provider_product": getattr(rr, "real_provider_product", False),
                    "production_usable": getattr(rr, "production_usable", False),
                    "grounding_class": getattr(rr, "grounding_class", None),
                    "visualization_allowed": getattr(rr, "visualization_allowed", False),
                    "experimental_visual_allowed": getattr(rr, "experimental_visual_allowed", False),
                    "composite_advisory_allowed": getattr(rr, "composite_advisory_allowed", False),
                    "scientific_surface_allowed": getattr(rr, "scientific_surface_allowed", False),
                    "current_1m_approval_allowed": getattr(rr, "current_1m_approval_allowed", False),
                    "observed_spatial_surface": getattr(rr, "observed_spatial_surface", False),
                    "prescription_driver_allowed": getattr(rr, "prescription_driver_allowed", False),
                    "authority_block_reason": getattr(rr, "authority_block_reason", None),
                    "crs": getattr(rr, "crs", None),
                    "bounds": getattr(rr, "bounds", None),
                    "transform": getattr(rr, "transform", None),
                }
                meta_dict.update(prov)
                
                # Check for global ASMAE_DIAGNOSTICS values from context package if retro/bma is missing
                diag_dict = {}
                f_features = getattr(ctx_pkg, "fused_features", None)
                if f_features:
                    for g in [
                        getattr(f_features, "water_context", []),
                        getattr(f_features, "vegetation_context", []),
                        getattr(f_features, "stress_evidence_context", []),
                        getattr(f_features, "data_quality_context", []),
                    ]:
                        for ff in g:
                            if ff.name == "ASMAE_DIAGNOSTICS":
                                val = ff.value
                                if val and isinstance(val, str):
                                    try:
                                        diag_dict = json.loads(val)
                                    except Exception:
                                        pass
                                break
                if not meta_dict.get("retro_status"):
                    meta_dict["retro_status"] = diag_dict.get("retro_status")
                if not meta_dict.get("bma_status"):
                    meta_dict["bma_status"] = diag_dict.get("bma_status")
                if not meta_dict.get("bma_disagreement") or meta_dict["bma_disagreement"] == 0.0:
                    meta_dict["bma_disagreement"] = diag_dict.get("bma_mean_disagreement", diag_dict.get("bma_disagreement", 0.0))
                if not meta_dict.get("cross_layer_conflict") or meta_dict["cross_layer_conflict"] == 0.0:
                    meta_dict["cross_layer_conflict"] = diag_dict.get("cross_layer_conflict", 0.0)

                keys_to_store = {var_name, var_name.upper(), var_name.lower()}
                if var_name.lower().startswith("asmae_"):
                    suffix = var_name[6:]
                    keys_to_store.add(f"ASMAE_{suffix.upper()}")
                    keys_to_store.add(f"asmae_{suffix.lower()}")
                else:
                    keys_to_store.add(f"ASMAE_{var_name.upper()}")
                    keys_to_store.add(f"asmae_{var_name.lower()}")

                for k in keys_to_store:
                    result.raster_metadata[k] = meta_dict

            grid_data = getattr(rr, "grid", None)
            grid_data = _load_raster_from_ref_if_needed(grid_data)
            if var_name and grid_data is not None:
                if var_name not in result.raster_maps:
                    raster = [[None]*W for _ in range(H)]
                    if isinstance(grid_data, list) and len(grid_data) > 0:
                        for r in range(min(H, len(grid_data))):
                            row = grid_data[r]
                            if isinstance(row, list):
                                for c in range(min(W, len(row))):
                                    raster[r][c] = float(row[c]) if row[c] is not None else None
                        result.raster_maps[var_name] = raster

    # --- Strategy 3: Extract from 4D tensor data [T, H, W, C] — ALL TIME STEPS ---
    tensor_data = getattr(field_tensor, 'data', [])
    channels = getattr(field_tensor, 'channels', [])
    try:
        import numpy as np
        if isinstance(tensor_data, np.ndarray):
            tensor_data = tensor_data.tolist()
    except ImportError:
        pass

    if tensor_data and isinstance(tensor_data, list) and len(tensor_data) > 0:
        try:
            temporal, latest = _extract_temporal_rasters(
                tensor_data, channels, result.time_index, H, W
            )
            result.temporal_rasters = temporal
            
            # Check provenance for tensor semantics
            prov = getattr(field_tensor, 'provenance', {}) or {}
            is_compat_tensor = False
            grounded_channels = []
            if isinstance(prov, dict):
                is_compat_tensor = (prov.get("tensor_semantics") == "v1_derived_latest_raster_plus_broadcast_timeseries")
                grounded_channels = prov.get("raster_grounded_channels", [])

            for ch_name, raster in latest.items():
                if is_compat_tensor:
                    # Only allow grounded channels to populate raster_maps
                    if ch_name in grounded_channels and ch_name not in result.raster_maps:
                        result.raster_maps[ch_name] = raster
                else:
                    if ch_name not in result.raster_maps:
                        result.raster_maps[ch_name] = raster
        except (IndexError, TypeError):
            # Fallback to last-only extraction
            try:
                last_t = tensor_data[-1]
                if isinstance(last_t, list) and len(last_t) > 0:
                    actual_h = len(last_t)
                    actual_w = len(last_t[0]) if last_t[0] else 0
                    
                    prov = getattr(field_tensor, 'provenance', {}) or {}
                    is_compat_tensor = False
                    grounded_channels = []
                    if isinstance(prov, dict):
                        is_compat_tensor = (prov.get("tensor_semantics") == "v1_derived_latest_raster_plus_broadcast_timeseries")
                        grounded_channels = prov.get("raster_grounded_channels", [])

                    for ci, ch in enumerate(channels):
                        ch_name = ch.value if hasattr(ch, 'value') else str(ch)
                        if is_compat_tensor and ch_name not in grounded_channels:
                            continue
                        if ch_name in result.raster_maps:
                            continue
                            
                        raster = [[None]*W for _ in range(H)]
                        for r in range(min(H, actual_h)):
                            for c in range(min(W, actual_w)):
                                try:
                                    raster[r][c] = float(last_t[r][c][ci])
                                except (IndexError, TypeError):
                                    pass
                        result.raster_maps[ch_name] = raster
            except (IndexError, TypeError):
                pass

    # --- Strategy 4: Extract raw raster composites directly (Fix C) ---
    rcs = getattr(field_tensor, 'raster_composites', {}) or {}
    for rc_key, rc_data in rcs.items():
        target_keys = []
        if rc_key == 'NDVI': target_keys = ['ndvi', 'NDVI']
        elif rc_key == 'NDMI': target_keys = ['ndmi', 'NDMI']
        elif rc_key == 'QUALITY': target_keys = ['quality_mask']
        elif rc_key == 'SAR': target_keys = ['vv', 'vh', 'VV', 'VH']

        for ch_key in target_keys:
            if ch_key not in result.raster_maps and "values" in rc_data:
                grid_to_use = rc_data.get(ch_key.lower()) or rc_data["values"]
                rc_h, rc_w = rc_data.get("height", 0), rc_data.get("width", 0)
                raster = [[None]*W for _ in range(H)]
                for r in range(min(H, rc_h)):
                    for c in range(min(W, rc_w)):
                        raster[r][c] = grid_to_use[r][c]
                result.raster_maps[ch_key] = raster

    # --- Strategy 3: Extract zone structure ---
    zones = getattr(field_tensor, 'zones', {}) or {}
    for zone_id, zone_data in zones.items():
        if isinstance(zone_data, dict):
            mask = zone_data.get('mask', [])
            area = zone_data.get('area_pct', 0.0)
            label = zone_data.get('label', zone_id)
            # Convert mask to cell indices
            cells = []
            if isinstance(mask, list):
                for r in range(min(H, len(mask))):
                    row = mask[r]
                    if isinstance(row, list):
                        for c in range(min(W, len(row))):
                            if row[c]:
                                cells.append((r, c))
            result.zone_masks[zone_id] = cells
            result.zone_areas[zone_id] = area
            result.zone_labels[zone_id] = label

    # --- Strategy 4: Extract zone_stats ---
    zs = getattr(field_tensor, 'zone_stats', {}) or {}
    for var_name, zone_data in zs.items():
        if isinstance(zone_data, dict):
            result.zone_timeseries[var_name] = {}
            for z_id, ts in zone_data.items():
                if isinstance(ts, list):
                    parsed_ts = []
                    for v in ts:
                        if isinstance(v, (int, float)):
                            parsed_ts.append(float(v))
                        elif isinstance(v, dict) and "mean" in v and v["mean"] is not None:
                            parsed_ts.append(float(v["mean"]))
                    result.zone_timeseries[var_name][z_id] = parsed_ts

    # --- Strategy 5: Field-level fallback from daily_state/plot_timeseries ---
    ds = getattr(field_tensor, 'daily_state', {}) or {}
    for var_name, values in ds.items():
        if isinstance(values, dict):
            # Per-zone daily state: {zone_id: [{day: ..., var: val}, ...]}
            for z_id, day_list in values.items():
                if isinstance(day_list, list) and day_list:
                    last_day = day_list[-1]
                    if isinstance(last_day, dict):
                        for k, v in last_day.items():
                            if k != 'day' and isinstance(v, (int, float)):
                                result.last_values[f"{k}_{z_id}"] = float(v)
        elif isinstance(values, list) and values:
            # Flat timeseries
            last_v = values[-1]
            if isinstance(last_v, (int, float)):
                result.last_values[var_name] = float(last_v)

    # plot_timeseries fallback
    pts = getattr(field_tensor, 'plot_timeseries', []) or []
    if pts:
        last = pts[-1] if isinstance(pts[-1], dict) else {}
        for k, v in last.items():
            # Specifically hydrate important fallback keys even if some daily_state exists
            if k != 'date' and isinstance(v, (int, float)):
                if k not in result.last_values:
                    result.last_values[k] = float(v)

    # --- Extract provenance ---
    result.source_contributions = getattr(field_tensor, 'provenance_log', []) or []

    # --- Extract spatial reliability ---
    sr = getattr(field_tensor, 'spatial_reliability', {}) or {}
    rel_raster = sr.get('reliability')
    if rel_raster and isinstance(rel_raster, list):
        rmap = [[0.8]*W for _ in range(H)]
        for r in range(min(H, len(rel_raster))):
            if isinstance(rel_raster[r], list):
                for c in range(min(W, len(rel_raster[r]))):
                    rmap[r][c] = float(rel_raster[r][c])
        result.reliability_map = rmap

    # --- Extract weather history ---
    result.weather_history = _extract_weather_history(field_tensor)

    # --- Extract temporal metadata (per-date quality) ---
    prov_log = getattr(field_tensor, 'provenance_log', []) or []
    for entry in prov_log:
        if isinstance(entry, dict):
            date = entry.get('date', '')
            if date:
                result.temporal_metadata[date] = {
                    'source': entry.get('source', 'UNKNOWN'),
                    'cloud_pct': entry.get('cloud_pct', 0.0),
                    'quality': entry.get('quality', 1.0),
                }

    # --- Broadcast field-level values to raster if no spatial data exists ---
    # Fix C: Stop L1 contradiction, we no longer broadcast fake spatial rasters.
    # _broadcast_missing(result, H, W)

    # --- Perform Spatial IDW Backfilling for raw Sentinel-2 composite grids ---
    # Downstream engines expect a continuous, organic raster.
    try:
        import numpy as np

        # Provider channels from the same composite share an observation mask.
        # Cache only the geometry-dependent IDW weights for this adaptation;
        # channel values remain independent and use the exact same weighted
        # sum as before.  This avoids rebuilding the ~17M-distance matrix once
        # per NDVI/NDMI/SAR/quality channel without changing interpolated data.
        idw_geometry_cache = {}

        def _spatial_idw_backfill(grid, H_val, W_val, p=2.0):
            arr = np.array(grid, dtype=float)
            mask_nan = np.isnan(arr)
            valid_mask = ~mask_nan

            total_cells = H_val * W_val
            n_valid = np.sum(valid_mask)
            if total_cells == 0:
                return grid, 1.0

            observed_ratio = float(n_valid / total_cells)
            if n_valid == total_cells:
                return grid, observed_ratio
            if n_valid == 0:
                return [[None] * W_val for _ in range(H_val)], observed_ratio

            valid_vals = arr[valid_mask]
            geometry_key = (arr.shape, float(p), valid_mask.tobytes())
            cached_geometry = idw_geometry_cache.get(geometry_key)
            if cached_geometry is None:
                valid_coords = np.argwhere(valid_mask)
                missing_coords = np.argwhere(mask_nan)
                diff = missing_coords[:, None, :] - valid_coords[None, :, :]
                dists = np.linalg.norm(diff, axis=2)
                dists = np.maximum(dists, 1e-9)
                weights = 1.0 / (dists ** p)
                weights_sum = np.sum(weights, axis=1, keepdims=True)
                weights_sum = np.maximum(weights_sum, 1e-9)
                cached_geometry = (weights, weights_sum)
                idw_geometry_cache[geometry_key] = cached_geometry
            else:
                weights, weights_sum = cached_geometry

            interpolated = np.sum(weights * valid_vals, axis=1, keepdims=True) / weights_sum
            arr[mask_nan] = interpolated.squeeze()

            backfilled_grid = [[None if np.isnan(val) else float(val) for val in row] for row in arr]
            return backfilled_grid, observed_ratio

        result.observed_ratios = {}
        result.observed_masks = {}
        for key, rmap in list(result.raster_maps.items()):
            if not rmap or not isinstance(rmap, list) or not isinstance(rmap[0], list):
                continue
            native_h = len(rmap)
            native_w = len(rmap[0])
            if native_h == 0 or native_w == 0 or not all(len(row) == native_w for row in rmap):
                continue

            # Compute the raw provider mask before IDW backfilling. Raster
            # composites may retain their native dimensions while L10 renders
            # on HxW, so align the mask with nearest-neighbour sampling.
            arr = np.array(rmap, dtype=float)
            observed_native = ~np.isnan(arr)
            if (native_h, native_w) == (H, W):
                observed_aligned = observed_native
            else:
                row_idx = np.linspace(0, native_h - 1, H).astype(int)
                col_idx = np.linspace(0, native_w - 1, W).astype(int)
                observed_aligned = observed_native[np.ix_(row_idx, col_idx)]
            result.observed_masks[key] = observed_aligned.tolist()

            if skip_idw:
                result.observed_ratios[key] = float(np.mean(observed_native))
            else:
                backfilled, ratio = _spatial_idw_backfill(rmap, native_h, native_w)
                result.raster_maps[key] = backfilled
                result.observed_ratios[key] = ratio

        if not skip_idw:
            for date, channels_dict in result.temporal_rasters.items():
                for ch, rmap in list(channels_dict.items()):
                    if rmap and len(rmap) == H and all(len(row) == W for row in rmap):
                        backfilled, _ = _spatial_idw_backfill(rmap, H, W)
                        channels_dict[ch] = backfilled
    except ImportError:
        import sys
        print("[L1_ADAPTER] numpy not available — skipping IDW backfill", file=sys.stderr)
        result.observed_ratios = {}
    
    # Prune empty rasters so downstream broadcast fallbacks can trigger
    empty_keys = []
    for k, rmap in result.raster_maps.items():
        if not rmap:
            empty_keys.append(k)
            continue
        has_val = False
        for r in range(min(H, len(rmap))):
            if rmap[r]:
                for c in range(min(W, len(rmap[r]))):
                    if rmap[r][c] is not None:
                        has_val = True
                        break
            if has_val: break
        if not has_val:
            empty_keys.append(k)
            
    for k in empty_keys:
        del result.raster_maps[k]

    # Extract ASMAE run record from FieldTensor context package or attribute
    ctx_pkg = getattr(field_tensor, "_context_package", None)
    if ctx_pkg and hasattr(ctx_pkg, "asmae_run_record"):
        result.asmae_run_record = ctx_pkg.asmae_run_record
    elif hasattr(field_tensor, "asmae_run_record"):
        result.asmae_run_record = field_tensor.asmae_run_record

    # Extract ASMAE raster maps directly from asmae_output if present (e.g. mock package in tests)
    asmae_out = None
    if ctx_pkg and hasattr(ctx_pkg, "asmae_output"):
        asmae_out = ctx_pkg.asmae_output
    elif hasattr(field_tensor, "asmae_output"):
        asmae_out = field_tensor.asmae_output

    if ctx_pkg and hasattr(ctx_pkg, "asmae_evidence_state"):
        result.asmae_evidence_state = ctx_pkg.asmae_evidence_state
    elif hasattr(field_tensor, "asmae_evidence_state"):
        result.asmae_evidence_state = field_tensor.asmae_evidence_state
    elif isinstance(asmae_out, dict) and "asmae_evidence_state" in asmae_out:
        result.asmae_evidence_state = asmae_out["asmae_evidence_state"]

    if result.asmae_evidence_state:
        result.real_asmae_evidence = result.asmae_evidence_state.get("real_asmae_evidence", False)

    # Helper to get attribute or key from object or dict
    def get_attr_or_key(obj, key, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    if asmae_out is not None:
        result.asmae_feature_pack = get_attr_or_key(asmae_out, "asmae_feature_pack")
        result.asmae_proof = get_attr_or_key(asmae_out, "asmae_proof") or {}
        
        res_decision = get_attr_or_key(asmae_out, "resolution_decision") or {}
        if isinstance(res_decision, dict):
            res_m = float(res_decision.get("selected_effective_resolution_m", 10.0))
        else:
            res_m = float(getattr(res_decision, "selected_effective_resolution_m", 10.0))
            
        c_hash = get_attr_or_key(asmae_out, "content_hash")
        if callable(c_hash):
            c_hash = c_hash()
        inst_hash = get_attr_or_key(asmae_out, "artifact_instance_hash")
        if callable(inst_hash):
            inst_hash = inst_hash()
        asmae_schema_version = get_attr_or_key(asmae_out, "schema_version")
        asmae_plot_id = get_attr_or_key(asmae_out, "plot_id")
        asmae_generated_at = get_attr_or_key(asmae_out, "generated_at")
        if hasattr(asmae_generated_at, "isoformat"):
            asmae_generated_at = asmae_generated_at.isoformat()
            
        scene_mode = get_attr_or_key(asmae_out, "diagnostics", {}).get("scene_stack_mode")
        state_update_allowed = get_attr_or_key(asmae_out, "state_update_allowed", False)
        diagnostic_only = get_attr_or_key(asmae_out, "diagnostic_only", True)

        # 1. State/Raster maps
        r_maps = get_attr_or_key(asmae_out, "raster_maps", {}) or {}
        for var, grid in r_maps.items():
            if grid:
                var_name = var if var.lower().startswith("asmae_") else f"asmae_{var}"
                if var_name not in result.raster_maps:
                    result.raster_maps[var_name] = grid
                    result.raster_maps[var_name.upper()] = grid
                    result.raster_maps[var_name.lower()] = grid
                    
                    # Compute observed mask
                    arr_val = np.array(grid, dtype=float)
                    obs_mask = (~np.isnan(arr_val)).tolist()
                    result.observed_masks[var_name] = obs_mask
                    result.observed_masks[var_name.upper()] = obs_mask
                    result.observed_masks[var_name.lower()] = obs_mask
                    
                    meta_dict = {
                        "resolution_m": res_m,
                        "content_hash": c_hash,
                        "artifact_instance_hash": inst_hash,
                        "source_schema_version": asmae_schema_version,
                        "source_plot_id": asmae_plot_id,
                        "source_generated_at": asmae_generated_at,
                        "scene_stack_mode": scene_mode,
                        "state_update_allowed": state_update_allowed,
                        "diagnostic_only": diagnostic_only,
                    }
                    result.raster_metadata[var_name] = meta_dict
                    result.raster_metadata[var_name.upper()] = meta_dict
                    result.raster_metadata[var_name.lower()] = meta_dict

        # 2. Support maps
        other_maps = [
            ("uncertainty_maps", "uncertainty"),
            ("confidence_maps", "confidence"),
            ("retrovalidation_maps", "retrovalidation_score"),
            ("bma_maps", "bma_disagreement"),
            ("ml_maps", "ml_agreement"),
            ("archive_maps", "archive_support"),
        ]
        for key_name, suffix in other_maps:
            map_grids = get_attr_or_key(asmae_out, key_name, {}) or {}
            for var, grid in map_grids.items():
                if grid:
                    if var == f"ASMAE_{suffix.upper()}":
                        var_name = f"asmae_{suffix.lower()}"
                    else:
                        var_name = var if var.lower().startswith("asmae_") else f"asmae_{var}_{suffix.lower()}"
                    if var_name not in result.raster_maps:
                        result.raster_maps[var_name] = grid
                        result.raster_maps[var_name.upper()] = grid
                        result.raster_maps[var_name.lower()] = grid
                        
                        # Compute observed mask
                        arr_val = np.array(grid, dtype=float)
                        obs_mask = (~np.isnan(arr_val)).tolist()
                        result.observed_masks[var_name] = obs_mask
                        result.observed_masks[var_name.upper()] = obs_mask
                        result.observed_masks[var_name.lower()] = obs_mask
                        
                        meta_dict = {
                            "resolution_m": res_m,
                            "content_hash": c_hash,
                            "artifact_instance_hash": inst_hash,
                            "source_schema_version": asmae_schema_version,
                            "source_plot_id": asmae_plot_id,
                            "source_generated_at": asmae_generated_at,
                            "scene_stack_mode": scene_mode,
                            "state_update_allowed": False,
                            "diagnostic_only": True,
                        }
                        result.raster_metadata[var_name] = meta_dict
                        result.raster_metadata[var_name.upper()] = meta_dict
                        result.raster_metadata[var_name.lower()] = meta_dict

        # Ensure asmae_feature_pack is fully enriched with metadata
        if result.asmae_feature_pack is None:
            result.asmae_feature_pack = {}
        if "observed_masks" not in result.asmae_feature_pack:
            result.asmae_feature_pack["observed_masks"] = result.observed_masks
        if "authority" not in result.asmae_feature_pack:
            result.asmae_feature_pack["authority"] = {
                "source_reality": result.asmae_evidence_state.get("source_reality") if result.asmae_evidence_state else "raster_composite_proxy",
                "scene_stack_mode": result.asmae_evidence_state.get("scene_stack_mode") if result.asmae_evidence_state else "unavailable",
                "real_asmae_evidence": result.real_asmae_evidence,
                "composite_advisory_allowed": result.asmae_evidence_state.get("composite_advisory_allowed", False) if result.asmae_evidence_state else False,
                "current_1m_approval_allowed": result.asmae_evidence_state.get("current_1m_approval_allowed", False) if result.asmae_evidence_state else False,
                "state_update_allowed": result.asmae_evidence_state.get("state_update_allowed", False) if result.asmae_evidence_state else False,
            }
        if "grid_spec" not in result.asmae_feature_pack:
            result.asmae_feature_pack["grid_spec"] = get_attr_or_key(asmae_out, "grid_spec") or {}
        if "resolution_decision" not in result.asmae_feature_pack:
            result.asmae_feature_pack["resolution_decision"] = res_decision
        if "operator_hashes" not in result.asmae_feature_pack:
            result.asmae_feature_pack["operator_hashes"] = get_attr_or_key(asmae_out, "observation_operator_refs") or []

    return result
