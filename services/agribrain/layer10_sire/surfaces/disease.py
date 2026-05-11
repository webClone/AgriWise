"""
Disease Surface Engine (v4) — Hotspot projection + weather gradient + vegetation density
========================================================================================

Multi-evidence spatial disease surfaces:
  - L5 BioThreatState per threat (probability, spread_pattern, confounders)
  - L3 diagnoses hotspot_zone_ids for hotspot projection
  - L1 NDVI as vegetation density (denser canopy → more disease pressure)
  - L1 SAR VH as soil moisture proxy (wetter → more fungal pressure)
  - L5 zone_metrics (per-zone if available)
  - Weather pressure as spatially uniform signal (genuinely field-wide)

v4 Change: UNIFORM spread pattern now uses edge-distance gradient + NDVI
modulation instead of flat stamping, ensuring spatial heterogeneity even
when no disease hotspots are diagnosed.
"""
from typing import List, Optional, Dict
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l3_adapter import L3DiagnosticData
from layer10_sire.adapters.l4_l9_adapters import L5BioData


def generate_disease_surfaces(
    inp: Layer10Input, H: int, W: int,
    l5_data: Optional[L5BioData] = None,
    l1_data: Optional[L1SpatialData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
) -> List[SurfaceArtifact]:
    """Generate disease surfaces from multi-evidence spatial synthesis."""
    surfaces = []
    if l5_data is None:
        from layer10_sire.adapters.l4_l9_adapters import adapt_l5
        l5_data = adapt_l5(inp.bio)
    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l3_data is None:
        from layer10_sire.adapters.l3_adapter import adapt_l3
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

    # --- 2. WEATHER_PRESSURE — modulated by canopy density (denser = more humid microclimate) ---
    wp = max(l5_data.weather_pressure_score, 0.05)  # Minimum base for spatial variation
    from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi
    ndvi_r = get_ndvi_raster(l1_data, H, W)
    # Denser canopy traps humidity → amplifies weather-driven disease pressure
    wp_grid = modulate_by_ndvi(wp, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)

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


def _raster_stats(raster, H: int, W: int):
    """Pre-compute mean, min, max, range for a raster."""
    vals = []
    for r in range(min(H, len(raster))):
        row = raster[r]
        for c in range(min(W, len(row))):
            v = row[c]
            if v is not None:
                vals.append(v)
    if not vals:
        return 0.0, 0.0, 0.0, 0.0
    mn, mx = min(vals), max(vals)
    return sum(vals) / len(vals), mn, mx, mx - mn


def _build_biotic_pressure(
    base_prob: float, spread_pattern: str,
    l1: L1SpatialData, l3: L3DiagnosticData,
    H: int, W: int,
):
    """
    Multi-evidence biotic pressure surface:
      1. L3 hotspot zones → high pressure in diagnosed zones
      2. L5 spread pattern → spatial texture (now NDVI-modulated even for UNIFORM)
      3. NDVI vegetation density → denser canopy = more disease pressure
      4. SAR VH soil moisture → wetter soil = higher fungal/bacterial pressure
      5. Combine as weighted blend
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
            break  # Found a relevant diagnosis, use it

    if bio_dx:
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
    spread_grid = _apply_spread_pattern(base_prob, spread_pattern, l1, H, W)

    # --- Evidence C: NDVI vegetation density (denser = more pressure) ---
    ndvi = l1.raster_maps.get('ndvi')
    veg_grid = [[base_prob] * W for _ in range(H)]
    if ndvi:
        ndvi_mean, _, _, ndvi_range = _raster_stats(ndvi, H, W)
        if ndvi_mean > 0 and ndvi_range > 0.02:
            for r in range(H):
                for c in range(W):
                    v = ndvi[r][c] if r < len(ndvi) and c < len(ndvi[r]) else None
                    if v is not None:
                        # Denser canopy → more disease pressure
                        # Normalize around field mean: ±0.6 modulation
                        deviation = (v - ndvi_mean) / ndvi_range
                        density_factor = 1.0 + deviation * 0.6
                        veg_grid[r][c] = round(base_prob * max(0.3, min(1.8, density_factor)), 4)

    # --- Evidence D: SAR VH soil moisture (wetter = more fungal pressure) ---
    sar_vh = l1.raster_maps.get('vh') or l1.raster_maps.get('VH')
    moisture_grid = None
    if sar_vh:
        sar_mean, _, _, sar_range = _raster_stats(sar_vh, H, W)
        if sar_range > 0.5:
            moisture_grid = [[base_prob] * W for _ in range(H)]
            for r in range(H):
                for c in range(W):
                    v = sar_vh[r][c] if r < len(sar_vh) and c < len(sar_vh[r]) else None
                    if v is not None:
                        # Higher VH backscatter → wetter soil → higher fungal pressure
                        sar_dev = (v - sar_mean) / sar_range
                        moisture_factor = 1.0 + sar_dev * 0.4
                        moisture_grid[r][c] = round(base_prob * max(0.5, min(1.5, moisture_factor)), 4)

    # --- Weighted blend ---
    weights = []
    grids = []
    if hotspot_grid:
        grids.append(hotspot_grid)
        weights.append(0.45)  # Highest: L3 diagnosis evidence
    grids.append(spread_grid)
    weights.append(0.25 if hotspot_grid else 0.35)  # Spread pattern
    grids.append(veg_grid)
    weights.append(0.20 if hotspot_grid else 0.35)  # Vegetation density
    if moisture_grid:
        grids.append(moisture_grid)
        weights.append(0.10 if hotspot_grid else 0.30)  # SAR moisture

    total_w = sum(weights)
    for r in range(H):
        for c in range(W):
            val = sum(g[r][c] * w for g, w in zip(grids, weights)) / total_w
            grid[r][c] = round(max(0.0, min(1.0, val)), 4)

    return grid


def _apply_spread_pattern(prob: float, pattern: str, l1: L1SpatialData, H: int, W: int):
    """Generate spatial texture from spread pattern.

    v4: UNIFORM mode now uses mild edge-distance gradient + NDVI modulation
    instead of stamping the same value everywhere.
    """
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
        # v4: Instead of flat stamping, apply mild edge-distance gradient
        # combined with NDVI vegetation density. Disease pressure is never
        # truly uniform — edges have different microclimate, and denser
        # canopy areas trap more humidity.
        ndvi = l1.raster_maps.get('ndvi')
        ndvi_mean, _, _, ndvi_range = (0.0, 0.0, 0.0, 0.0)
        if ndvi:
            ndvi_mean, _, _, ndvi_range = _raster_stats(ndvi, H, W)

        max_edge = max(1, min(H, W) // 2)
        for r in range(H):
            for c in range(W):
                # Mild edge bias (0.85 center → 1.0 edge): field borders
                # are more exposed to external disease inoculum
                edge_dist = min(r, c, H - 1 - r, W - 1 - c)
                edge_factor = 0.85 + 0.15 * max(0.0, 1.0 - edge_dist / max_edge)

                # NDVI density modulation: denser canopy = higher humidity
                ndvi_factor = 1.0
                if ndvi and ndvi_mean > 0 and ndvi_range > 0.02:
                    pixel_ndvi = ndvi[r][c] if r < len(ndvi) and c < len(ndvi[r]) else None
                    if pixel_ndvi is not None:
                        ndvi_dev = (pixel_ndvi - ndvi_mean) / ndvi_range
                        ndvi_factor = 1.0 + ndvi_dev * 0.3  # ±30% modulation
                        ndvi_factor = max(0.6, min(1.4, ndvi_factor))

                grid[r][c] = round(prob * edge_factor * ndvi_factor, 4)

    return grid
