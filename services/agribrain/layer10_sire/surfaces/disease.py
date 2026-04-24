"""
Disease Surface Engine (v3) — Hotspot projection + weather gradient + vegetation density
========================================================================================

Multi-evidence spatial disease surfaces:
  - L5 BioThreatState per threat (probability, spread_pattern, confounders)
  - L3 diagnoses hotspot_zone_ids for hotspot projection
  - L1 NDVI as vegetation density (denser canopy → more disease pressure)
  - L5 zone_metrics (per-zone if available)
  - Weather pressure as spatially uniform signal (genuinely field-wide)
"""
from typing import List, Optional, Dict
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l3_adapter import L3DiagnosticData
from services.agribrain.layer10_sire.adapters.l4_l9_adapters import L5BioData


def generate_disease_surfaces(
    inp: Layer10Input, H: int, W: int,
    l5_data: Optional[L5BioData] = None,
    l1_data: Optional[L1SpatialData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
) -> List[SurfaceArtifact]:
    """Generate disease surfaces from multi-evidence spatial synthesis."""
    surfaces = []
    if l5_data is None:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l5
        l5_data = adapt_l5(inp.bio)
    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l3_data is None:
        from services.agribrain.layer10_sire.adapters.l3_adapter import adapt_l3
        l3_data = adapt_l3(inp.decision)

    if not l5_data.threat_probs:
        return surfaces

    # --- 1. BIOTIC_PRESSURE — multi-evidence spatial ---
    max_threat = max(l5_data.threat_probs, key=l5_data.threat_probs.get)
    max_prob = l5_data.threat_probs[max_threat]
    spread = l5_data.threat_spreads.get(max_threat, 'UNIFORM')

    pressure_grid = _build_biotic_pressure(
        max_prob, spread, l1_data, l3_data, H, W
    )

    surfaces.append(SurfaceArtifact(
        surface_id=f"BIOTIC_PRESS_{inp.plot_id}",
        semantic_type=SurfaceType.BIOTIC_PRESSURE,
        grid_ref=f"{H}x{W}",
        values=pressure_grid,
        units="probability",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.DISEASE_ORANGE,
        source_layers=["L3", "L5"],
    ))

    # --- 2. WEATHER_PRESSURE — genuinely field-wide (honest uniform) ---
    wp = l5_data.weather_pressure_score
    wp_grid = [[round(wp, 4)] * W for _ in range(H)]

    surfaces.append(SurfaceArtifact(
        surface_id=f"WEATHER_PRESS_{inp.plot_id}",
        semantic_type=SurfaceType.WEATHER_PRESSURE,
        grid_ref=f"{H}x{W}",
        values=wp_grid,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.DISEASE_ORANGE,
        source_layers=["L5"],
    ))

    return surfaces


def _build_biotic_pressure(
    base_prob: float, spread_pattern: str,
    l1: L1SpatialData, l3: L3DiagnosticData,
    H: int, W: int,
):
    """
    Multi-evidence biotic pressure surface:
      1. L3 hotspot zones → high pressure in diagnosed zones
      2. L5 spread pattern → spatial texture
      3. NDVI vegetation density → denser canopy = more disease pressure
      4. Combine as weighted blend
    """
    grid = [[0.0] * W for _ in range(H)]

    # --- Evidence A: L3 hotspot zone projection ---
    hotspot_grid = None
    bio_dx = None
    for dx in l3.diagnoses:
        pid = getattr(dx, 'problem_id', '').upper()
        if "LATE_BLIGHT" in pid or "FUNGAL" in pid or "DISEASE" in pid:
            bio_dx = dx
            prob = getattr(dx, 'probability', 0.0)
            sev = getattr(dx, 'severity', 1.0)
            conf = getattr(dx, 'confidence', 0.5)
            hotspots = getattr(dx, 'hotspot_zone_ids', [])
            break # Found a relevant diagnosis, use it

    if bio_dx:
        # Note: 'affected_area_pct' is not a standard attribute of L3Diagnosis,
        # assuming it might be present in some custom dx objects or needs to be retrieved differently.
        # For now, keeping the original logic's intent but adapting to getattr if it were an object.
        # If bio_dx is an object, it won't have .get()
        # If it's a dict, getattr won't work.
        # Assuming dx is an object, and affected_area_pct might be an attribute.
        affected_pct = getattr(bio_dx, 'affected_area_pct', 100.0) / 100.0
        if hotspots and l1.zone_masks:
            hotspot_grid = [[0.0] * W for _ in range(H)]
            hotspot_cells = set()
            for z_id in hotspots:
                for r, c in l1.zone_masks.get(z_id, []):
                    if r < H and c < W:
                        hotspot_grid[r][c] = base_prob
                        hotspot_cells.add((r, c))
            # Non-hotspot zones get reduced probability
            for r in range(H):
                for c in range(W):
                    if (r, c) not in hotspot_cells:
                        hotspot_grid[r][c] = base_prob * 0.15

    # --- Evidence B: Spread pattern texture ---
    spread_grid = _apply_spread_pattern(base_prob, spread_pattern, H, W)

    # --- Evidence C: NDVI vegetation density (denser = more pressure) ---
    veg_grid = [[base_prob] * W for _ in range(H)]
    ndvi = l1.raster_maps.get('ndvi')
    if ndvi:
        vals = [ndvi[r][c] for r in range(H) for c in range(W) if ndvi[r][c] is not None]
        if vals:
            ndvi_mean = sum(vals) / len(vals)
            if ndvi_mean > 0:
                for r in range(H):
                    for c in range(W):
                        v = ndvi[r][c]
                        if v is not None:
                            # Denser canopy → more disease pressure
                            density_factor = v / ndvi_mean
                            veg_grid[r][c] = round(base_prob * density_factor, 4)

    # --- Weighted blend ---
    weights = []
    grids = []
    if hotspot_grid:
        grids.append(hotspot_grid)
        weights.append(0.5)  # Highest: L3 diagnosis evidence
    grids.append(spread_grid)
    weights.append(0.3 if hotspot_grid else 0.5)  # Spread pattern
    grids.append(veg_grid)
    weights.append(0.2 if hotspot_grid else 0.5)  # Vegetation density

    total_w = sum(weights)
    for r in range(H):
        for c in range(W):
            val = sum(g[r][c] * w for g, w in zip(grids, weights)) / total_w
            grid[r][c] = round(max(0.0, min(1.0, val)), 4)

    return grid


def _apply_spread_pattern(prob: float, pattern: str, H: int, W: int):
    """Generate spatial texture from spread pattern."""
    grid = [[0.0] * W for _ in range(H)]

    if pattern in ('PATCHY', 'RANDOM'):
        # Concentrated hotspots — gradient from focal point
        focal_r, focal_c = H // 3, W // 3
        max_dist = ((H ** 2 + W ** 2) ** 0.5) / 2
        for r in range(H):
            for c in range(W):
                dist = ((r - focal_r) ** 2 + (c - focal_c) ** 2) ** 0.5
                falloff = max(0.0, 1.0 - dist / max(1, max_dist))
                grid[r][c] = round(prob * (0.2 + 0.8 * falloff), 4)

    elif pattern == 'EDGE_DRIVEN':
        # Higher at field edges (wind-borne, neighboring field infection)
        for r in range(H):
            for c in range(W):
                edge_dist = min(r, c, H - 1 - r, W - 1 - c)
                max_edge = min(H, W) // 2
                edge_factor = max(0.0, 1.0 - edge_dist / max(1, max_edge))
                grid[r][c] = round(prob * (0.1 + 0.9 * edge_factor), 4)

    else:  # UNIFORM / UNKNOWN
        for r in range(H):
            for c in range(W):
                grid[r][c] = round(prob, 4)

    return grid
