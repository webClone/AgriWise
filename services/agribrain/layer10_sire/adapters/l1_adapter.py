"""
L1 Adapter — Extract spatial data from FieldTensor
====================================================

Normalizes L1 FieldTensor into Layer 10 internal structures.
Handles: 4D tensor data, maps, zones, zone_stats, daily_state,
         provenance_log, spatial_reliability, grid_spec.
"""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class L1SpatialData:
    """Normalized L1 spatial extraction for Layer 10."""
    # Grid dimensions (from grid_spec or tensor shape)
    height: int = 10
    width: int = 10
    resolution_m: float = 10.0

    # Raster maps — variable→2D array [H][W]
    raster_maps: Dict[str, List[List[Optional[float]]]] = field(default_factory=dict)

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

    # Run ID
    run_id: str = ""


def adapt_l1(field_tensor: Any, target_h: int = 10, target_w: int = 10) -> L1SpatialData:
    """
    Extract all spatial intelligence from FieldTensor.

    Priority:
      1. Real 4D tensor data (spatial truth)
      2. maps dict (raster refs)
      3. zone_stats (per-zone timeseries)
      4. daily_state (per-zone daily state)
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
    if gs is not None:
        h = getattr(gs, 'height', target_h)
        w = getattr(gs, 'width', target_w)
        res = getattr(gs, 'resolution', 10.0)
        if h > 0 and w > 0:
            result.height = h
            result.width = w
            result.resolution_m = res

    H, W = result.height, result.width

    # --- Strategy 1: Extract from 4D tensor data [T, H, W, C] ---
    tensor_data = getattr(field_tensor, 'data', [])
    channels = getattr(field_tensor, 'channels', [])
    if tensor_data and isinstance(tensor_data, list) and len(tensor_data) > 0:
        try:
            last_t = tensor_data[-1]  # Latest time step
            if isinstance(last_t, list) and len(last_t) > 0:
                actual_h = len(last_t)
                actual_w = len(last_t[0]) if last_t[0] else 0
                for ci, ch in enumerate(channels):
                    ch_name = ch.value if hasattr(ch, 'value') else str(ch)
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

    # --- Strategy 2: Extract from maps dict ---
    maps = getattr(field_tensor, 'maps', {}) or {}
    for var_name, raster_data in maps.items():
        if var_name in result.raster_maps:
            continue  # Tensor data takes priority
        if isinstance(raster_data, list) and len(raster_data) > 0:
            raster = [[None]*W for _ in range(H)]
            for r in range(min(H, len(raster_data))):
                row = raster_data[r]
                if isinstance(row, list):
                    for c in range(min(W, len(row))):
                        raster[r][c] = float(row[c]) if row[c] is not None else None
            result.raster_maps[var_name] = raster

    # --- Strategy 2b: Extract raw raster composites directly (Fix C) ---
    rcs = getattr(field_tensor, 'raster_composites', {}) or {}
    for rc_key, rc_data in rcs.items():
        target_keys = []
        if rc_key == 'NDVI': target_keys = ['ndvi', 'NDVI']
        elif rc_key == 'NDMI': target_keys = ['ndmi', 'NDMI']
        elif rc_key == 'QUALITY': target_keys = ['quality_mask']
        elif rc_key == 'SAR': target_keys = ['vv', 'vh', 'VV', 'VH']
        
        for ch_key in target_keys:
            if ch_key not in result.raster_maps and "values" in rc_data:
                # If it's SAR, we ideally want both VV and VH, but if only 'values' exists, it's VV.
                # If there are sub-grids like 'vv' and 'vh' from the TAR parser, use those instead.
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
                    result.zone_timeseries[var_name][z_id] = [
                        float(v) for v in ts if isinstance(v, (int, float))
                    ]

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

    # --- Broadcast field-level values to raster if no spatial data exists ---
    # Fix C: Stop L1 contradiction, we no longer broadcast fake spatial rasters.
    # _broadcast_missing(result, H, W)

    return result
