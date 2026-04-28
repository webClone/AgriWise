"""
Water Surface Engine (v2) — Spatial-first water stress from L1/L3 adapter data
"""
from typing import List, Optional
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l3_adapter import L3DiagnosticData


def generate_water_surfaces(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
) -> List[SurfaceArtifact]:
    """Generate water surfaces from L1/L3 adapter data (spatial-first)."""
    surfaces = []
    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l3_data is None:
        from layer10_sire.adapters.l3_adapter import adapt_l3
        l3_data = adapt_l3(inp.decision)

    # --- 1. WATER_STRESS_PROB — from L3 diagnoses + spatial modulation ---
    stress_grid = _compute_spatial_water_stress(l1_data, l3_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"WATER_STRESS_{inp.plot_id}",
        semantic_type=SurfaceType.WATER_STRESS_PROB,
        grid_ref=f"{H}x{W}",
        values=stress_grid,
        units="probability",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L1", "L3"],
    ))

    # --- 2. DROUGHT_ACCUMULATION — from L1 precipitation ---
    drought_grid = _compute_spatial_drought(l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"DROUGHT_{inp.plot_id}",
        semantic_type=SurfaceType.DROUGHT_ACCUMULATION,
        grid_ref=f"{H}x{W}",
        values=drought_grid,
        units="days",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 30.0),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L1"],
    ))

    return surfaces


def _compute_spatial_water_stress(l1: L1SpatialData, l3: L3DiagnosticData, H: int, W: int):
    """Derive water stress probability spatially from L3 diagnoses + L1 hotspots."""
    grid = [[0.0]*W for _ in range(H)]

    # Find water stress diagnosis
    stress_dx = None
    l3_diags = l3.diagnoses # Assuming l3.diagnoses is the list of diagnosis objects
    for dx in l3_diags:
        pid = getattr(dx, 'problem_id', '').upper()
        if "WATER_STRESS" in pid or "DROUGHT" in pid:
            prob = getattr(dx, 'probability', 0.0)
            # sev = getattr(dx, 'severity', 1.0) # Not used in current logic
            # conf = getattr(dx, 'confidence', 0.5) # Not used in current logic
            # hotspots = getattr(dx, 'hotspot_zone_ids', []) # Not used in current logic for selection
            if stress_dx is None or prob > getattr(stress_dx, 'probability', 0.0):
                stress_dx = dx

    if stress_dx is None:
        return grid

    base_prob = getattr(stress_dx, 'probability', 0.0)
    affected_pct = getattr(stress_dx, 'affected_area_pct', 100.0) / 100.0
    hotspot_zones = getattr(stress_dx, 'hotspot_zone_ids', [])

    # Strategy A: Hotspot zones get full probability, others get reduced
    if hotspot_zones and l1.zone_masks:
        hotspot_cells = set()
        for z_id in hotspot_zones:
            for r, c in l1.zone_masks.get(z_id, []):
                if r < H and c < W:
                    hotspot_cells.add((r, c))

        if hotspot_cells:
            for r in range(H):
                for c in range(W):
                    if (r, c) in hotspot_cells:
                        grid[r][c] = round(base_prob, 4)
                    else:
                        grid[r][c] = round(base_prob * 0.2, 4)  # Low outside hotspots
            return grid

    # Strategy B: Use NDVI deviation as spatial proxy (lower NDVI → more stress)
    ndvi_raster = l1.raster_maps.get('ndvi')
    if ndvi_raster:
        vals = [ndvi_raster[r][c] for r in range(H) for c in range(W)
                if ndvi_raster[r][c] is not None]
        if vals:
            ndvi_mean = sum(vals) / len(vals)
            ndvi_range = max(vals) - min(vals) if len(vals) > 1 else 1.0
            for r in range(H):
                for c in range(W):
                    v = ndvi_raster[r][c]
                    if v is not None and ndvi_range > 0:
                        # Lower NDVI → higher stress
                        stress = base_prob * (1.0 - (v - min(vals)) / ndvi_range)
                        grid[r][c] = round(max(0.0, min(1.0, stress * affected_pct)), 4)
            return grid

    # Strategy C: Affected area fraction broadcast
    total_cells = H * W
    affected_cells = int(total_cells * affected_pct)
    for i in range(total_cells):
        r, c = divmod(i, W)
        grid[r][c] = round(base_prob if i < affected_cells else base_prob * 0.1, 4)

    return grid


def _compute_spatial_drought(l1: L1SpatialData, H: int, W: int):
    """Compute trailing dry days — spatial if precipitation raster exists."""
    # Check for precipitation timeseries
    precip_ts = l1.last_values.get('precipitation')
    dry_days = 0

    # Try zone-level precipitation
    if 'precipitation' in l1.zone_timeseries:
        zone_droughts = {}
        for z_id, ts in l1.zone_timeseries['precipitation'].items():
            dd = 0
            for p in reversed(ts):
                if p > 2.0:
                    break
                dd += 1
            zone_droughts[z_id] = float(dd)

        if zone_droughts and l1.zone_masks:
            grid = [[0.0]*W for _ in range(H)]
            for z_id, cells in l1.zone_masks.items():
                dd = zone_droughts.get(z_id, 0.0)
                for r, c in cells:
                    if r < H and c < W:
                        grid[r][c] = dd
            return grid

    # Fallback: field-level
    grid = [[float(dry_days)]*W for _ in range(H)]
    return grid
