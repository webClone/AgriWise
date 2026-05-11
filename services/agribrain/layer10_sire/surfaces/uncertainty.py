"""
Uncertainty Surface Engine (v4) — Multi-evidence spatial uncertainty
====================================================================

Multi-evidence trust surfaces:
  - L1 NDVI_UNC raster (per-pixel uncertainty)
  - L1 spatial_reliability raster (per-pixel)
  - L1 provenance_log per-zone source contributions
  - NDVI spatial modulation (low NDVI = noisier signal = higher uncertainty)
  - SAR backscatter modulation (low SAR = weaker signal = higher uncertainty)
  - Conflict density from source disagreement

v4 Changes:
  - clamp_max raised from 0.5 to 0.8 — high uncertainty pixels were being
    crushed when base unc_val was already ~0.5
  - Added SAR VH as additional spatial evidence source
  - Increased modulation strength for better spatial differentiation
  - Reliability surface always NDVI-modulated (not gated behind missing zones)
"""
from typing import List, Optional, Dict
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l2_adapter import L2VegData

SOURCE_CATEGORIES = ['s2', 's1', 'weather', 'soil', 'sensor', 'user']


def _raster_stats(raster, H: int, W: int):
    """Pre-compute mean, min, max, count for a raster."""
    vals = []
    for r in range(min(H, len(raster))):
        row = raster[r]
        for c in range(min(W, len(row))):
            v = row[c]
            if v is not None:
                vals.append(v)
    if not vals:
        return 0.0, 0.0, 0.0, 0
    return sum(vals) / len(vals), min(vals), max(vals), len(vals)


def _is_spatially_uniform(raster, H: int, W: int) -> bool:
    """Check if all non-None pixels share the same value."""
    first_val = None
    for r in range(min(H, len(raster))):
        row = raster[r]
        for c in range(min(W, len(row))):
            v = row[c]
            if v is not None:
                if first_val is None:
                    first_val = v
                elif abs(v - first_val) > 1e-6:
                    return False
    return True


def generate_uncertainty_surfaces(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
    l2_data: Optional[L2VegData] = None,
) -> List[SurfaceArtifact]:
    """Generate trust/uncertainty surfaces from multi-evidence synthesis."""
    surfaces = []
    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l2_data is None:
        from layer10_sire.adapters.l2_adapter import adapt_l2
        l2_data = adapt_l2(inp.veg_int)

    # --- 1. UNCERTAINTY_SIGMA — multi-evidence spatial ---
    unc_raster = _build_uncertainty_sigma(l1_data, l2_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"UNC_SIGMA_{inp.plot_id}",
        semantic_type=SurfaceType.UNCERTAINTY_SIGMA,
        grid_ref=f"{H}x{W}",
        values=unc_raster,
        units="sigma",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 0.8),
        palette_id=PaletteId.UNCERTAINTY_GRAY,
        source_layers=["L1"],
    ))

    # --- 2. DATA_RELIABILITY — from real raster + obs_coverage + zone stability ---
    rel_grid = _build_reliability(l1_data, l2_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"RELIABILITY_{inp.plot_id}",
        semantic_type=SurfaceType.DATA_RELIABILITY,
        grid_ref=f"{H}x{W}",
        values=rel_grid,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.UNCERTAINTY_GRAY,
        source_layers=["L1", "L2"],
    ))

    # --- 3. SOURCE_DOMINANCE — per-zone from provenance ---
    dom_grid, dom_weights = _build_per_zone_dominance(l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"SRC_DOM_{inp.plot_id}",
        semantic_type=SurfaceType.SOURCE_DOMINANCE,
        grid_ref=f"{H}x{W}",
        values=dom_grid,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.SOURCE_SPECTRAL,
        source_layers=["L1"],
        source_weights=dom_weights,
    ))

    return surfaces


def _build_uncertainty_sigma(l1: L1SpatialData, l2: L2VegData, H: int, W: int):
    """Build UNCERTAINTY_SIGMA surface from multiple evidence sources.

    v5: Multi-factor base uncertainty + wide spatial modulation.

    Base uncertainty anchored to actual data quality:
      - Observation freshness (data age → higher uncertainty)
      - Source diversity (more sources → lower uncertainty)
      - Spectral coverage (NDVI + SAR available → lower base)
      - Temporal coverage (curve fit quality from L2)

    Spatial modulation for per-pixel differentiation:
      - NDVI signal strength (low NDVI → noisier spectral → +uncertainty)
      - SAR backscatter (low VH → weaker signal → +uncertainty)
      - Edge penalty (boundary pixels less reliable)
      - Deterministic micro-noise fallback when no rasters available
    """
    # Try real NDVI uncertainty raster first
    unc_raster = l1.raster_maps.get('ndvi_uncertainty')
    has_real_unc = unc_raster is not None and not _is_spatially_uniform(unc_raster, H, W)

    if has_real_unc:
        return unc_raster

    # ── Step 1: Compute data-quality-anchored base uncertainty ──
    quality_factors = []

    # Factor A: Temporal coverage — L2 curve fit quality
    if l2.ndvi_fit_unc:
        curve_unc = l2.ndvi_fit_unc[-1]
        # Normalize: good fit (0.01) → 0.05, poor fit (0.5) → 0.40
        quality_factors.append(min(0.40, max(0.05, curve_unc * 0.8)))
    else:
        quality_factors.append(0.30)  # No curve → moderate penalty

    # Factor B: Source diversity — how many raster types are available
    available_sources = set()
    for key in l1.raster_maps:
        k = key.lower()
        if 'ndvi' in k:
            available_sources.add('optical')
        elif k in ('vh', 'vv', 'cr'):
            available_sources.add('sar')
        elif 'soil' in k or 'clay' in k or 'ph' in k or 'oc' in k:
            available_sources.add('soil')
        elif 'moisture' in k:
            available_sources.add('moisture')
    diversity_score = len(available_sources) / 4.0  # 4 possible categories
    # More sources → less uncertainty: 0 sources → 0.40, 4 sources → 0.05
    quality_factors.append(max(0.05, 0.40 - diversity_score * 0.35))

    # Factor C: Spatial coverage — what fraction of pixels have real data
    ndvi_r = None
    from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster
    ndvi_r = get_ndvi_raster(l1, H, W)
    ndvi_valid = 0
    total_px = H * W
    for r in range(min(H, len(ndvi_r))):
        for c in range(min(W, len(ndvi_r[r]))):
            if ndvi_r[r][c] is not None:
                ndvi_valid += 1
    coverage = ndvi_valid / max(1, total_px)
    # Full coverage → 0.05, no coverage → 0.35
    quality_factors.append(max(0.05, 0.35 * (1.0 - coverage)))

    # Factor D: Uniform raster fallback value (if available)
    if unc_raster is not None:
        mean_v, _, _, count = _raster_stats(unc_raster, H, W)
        if count > 0 and mean_v > 0:
            quality_factors.append(min(0.40, max(0.05, mean_v)))

    # Aggregate: weighted average of factors
    base_unc = sum(quality_factors) / len(quality_factors) if quality_factors else 0.25

    # ── Step 2: Pre-compute raster stats for spatial modulation ──
    ndvi_mean, ndvi_min, ndvi_max, ndvi_count = _raster_stats(ndvi_r, H, W)
    ndvi_range = ndvi_max - ndvi_min

    sar_vh = l1.raster_maps.get('vh') or l1.raster_maps.get('VH')
    sar_mean, sar_min, sar_max, sar_count = 0.0, 0.0, 0.0, 0
    sar_range = 0.0
    if sar_vh:
        sar_mean, sar_min, sar_max, sar_count = _raster_stats(sar_vh, H, W)
        sar_range = sar_max - sar_min

    # ── Step 3: Build per-pixel uncertainty grid ──
    grid = [[base_unc] * W for _ in range(H)]

    for r in range(H):
        for c in range(W):
            modifier = 1.0

            # NDVI modulation: low NDVI → noisier spectral signal → more uncertainty
            # v5: increased to ±35% spread (was ±15% in v4)
            if ndvi_count > 0 and ndvi_range > 0.02 and ndvi_mean > 0:
                pixel_ndvi = ndvi_r[r][c] if r < len(ndvi_r) and c < len(ndvi_r[r]) else None
                if pixel_ndvi is not None:
                    ndvi_dev = (pixel_ndvi - ndvi_mean) / ndvi_range
                    # Low NDVI → higher uncertainty (inverted relationship)
                    ndvi_factor = 1.0 - ndvi_dev * 0.7
                    modifier *= max(0.3, min(2.2, ndvi_factor))
                else:
                    # No pixel data → increase uncertainty by 50%
                    modifier *= 1.5

            # SAR modulation: low backscatter → weaker signal → more uncertainty
            # v5: strengthened from ±10% to ±25%
            if sar_vh and sar_count > 0 and sar_range > 0.5:
                pixel_vh = sar_vh[r][c] if r < len(sar_vh) and c < len(sar_vh[r]) else None
                if pixel_vh is not None:
                    sar_dev = (pixel_vh - sar_mean) / sar_range
                    sar_factor = 1.0 - sar_dev * 0.5
                    modifier *= max(0.5, min(1.8, sar_factor))

            # Edge penalty: boundary pixels are inherently less reliable
            is_edge = (r == 0 or r == H - 1 or c == 0 or c == W - 1)
            if is_edge:
                modifier *= 1.15  # 15% edge penalty

            # Deterministic micro-noise fallback when neither NDVI nor SAR modulated
            if ndvi_count == 0 and sar_count == 0:
                seed = ((r * 7919 + c * 6271 + 2017) * 2654435761) & 0xFFFFFFFF
                noise = ((seed & 0xFFFF) / 0xFFFF) * 2.0 - 1.0
                modifier *= (1.0 + noise * 0.25)

            grid[r][c] = round(max(0.01, min(0.8, base_unc * modifier)), 4)

    return grid


def _build_reliability(l1: L1SpatialData, l2: L2VegData, H: int, W: int):
    """Build reliability surface: spatial_reliability raster + stability + NDVI.

    v4: Always applies NDVI modulation on top of base reliability, even when
    zone scores exist but are uniform.
    """
    from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster

    # Check if reliability_map is actually spatial or uniform broadcast
    rel_map_is_spatial = False
    if l1.reliability_map:
        rel_map_is_spatial = not _is_spatially_uniform(l1.reliability_map, H, W)

    if l1.reliability_map and rel_map_is_spatial:
        # Start from real raster, modulate by zone stability
        grid = [row[:] for row in l1.reliability_map]
        if l1.zone_masks and l2.zone_metrics:
            for z_id, cells in l1.zone_masks.items():
                zm = l2.zone_metrics.get(z_id, {})
                if isinstance(zm, dict):
                    zone_stab = zm.get('stability_score', 0.7)
                    for r, c in cells:
                        if r < H and c < W:
                            grid[r][c] = round(grid[r][c] * 0.7 + zone_stab * 0.3, 3)
        return grid

    # Fallback: computed from curve quality + stability
    base = min(1.0, l2.obs_coverage + 0.1) * l2.stability_confidence

    # Always apply NDVI spatial modulation for differentiation
    ndvi_r = get_ndvi_raster(l1, H, W)
    ndvi_mean, _, _, ndvi_count = _raster_stats(ndvi_r, H, W)
    ndvi_range = 0.0
    if ndvi_count > 0:
        _, ndvi_min, ndvi_max, _ = _raster_stats(ndvi_r, H, W)
        ndvi_range = ndvi_max - ndvi_min

    # Start with zone scores if available
    grid = [[round(base, 3)] * W for _ in range(H)]
    if l1.zone_masks and l2.zone_metrics:
        for z_id, cells in l1.zone_masks.items():
            zm = l2.zone_metrics.get(z_id, {})
            if isinstance(zm, dict):
                zone_stab = zm.get('stability_score', 0.5)
                zone_rel = round(base * 0.6 + zone_stab * 0.4, 3)
                for r, c in cells:
                    if r < H and c < W:
                        grid[r][c] = zone_rel

    # Always overlay NDVI modulation: higher NDVI → more reliable
    if ndvi_count > 0 and ndvi_range > 0.02 and ndvi_mean > 0:
        for r in range(H):
            for c in range(W):
                pixel_ndvi = ndvi_r[r][c] if r < len(ndvi_r) and c < len(ndvi_r[r]) else None
                if pixel_ndvi is not None:
                    ndvi_dev = (pixel_ndvi - ndvi_mean) / ndvi_range
                    # Higher NDVI → better satellite signal → more reliable
                    ndvi_factor = 1.0 + ndvi_dev * 0.5
                    grid[r][c] = round(max(0.1, min(1.0, grid[r][c] * ndvi_factor)), 4)

    return grid


def _build_per_zone_dominance(l1: L1SpatialData, H: int, W: int):
    """Build per-zone source dominance with real source weights."""
    zone_sources = {}
    global_sources = {}

    for prov in l1.source_contributions:
        if not isinstance(prov, dict):
            continue
        sources = prov.get('sources', {})
        if sources:
            total = sum(float(v) for v in sources.values()) or 1.0
            parsed = {cat: round(float(sources.get(cat, sources.get(f'satellite_{cat}', 0.0))) / total, 3)
                      for cat in SOURCE_CATEGORIES}
            zone_id = prov.get('zone_id')
            if zone_id:
                zone_sources[zone_id] = parsed
            else:
                global_sources = parsed

    if not global_sources:
        global_sources = {'s2': 0.4, 'weather': 0.3, 's1': 0.15, 'soil': 0.15}

    dom_grid = [[0.0] * W for _ in range(H)]
    weight_grid = [[None] * W for _ in range(H)]

    if l1.zone_masks and zone_sources:
        for z_id, cells in l1.zone_masks.items():
            sw = zone_sources.get(z_id, global_sources)
            max_val = max(sw.values()) if sw else 0.5
            for r, c in cells:
                if r < H and c < W:
                    dom_grid[r][c] = max_val
                    weight_grid[r][c] = dict(sw)
        max_global = max(global_sources.values()) if global_sources else 0.5
        for r in range(H):
            for c in range(W):
                if weight_grid[r][c] is None:
                    dom_grid[r][c] = max_global
                    weight_grid[r][c] = dict(global_sources)
    else:
        from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, ndvi_stats
        ndvi_r = get_ndvi_raster(l1, H, W)
        mean_ndvi, mn, mx, _valid = ndvi_stats(ndvi_r, H, W)
        rng = mx - mn if mx > mn else 1.0
        max_global = max(global_sources.values()) if global_sources else 0.5
        for r in range(H):
            for c in range(W):
                v = ndvi_r[r][c] if r < len(ndvi_r) and c < len(ndvi_r[r]) else None
                if v is not None and rng > 0.01:
                    norm = (v - mean_ndvi) / rng
                    mod = max_global * (1.0 + norm * 0.3)
                    dom_grid[r][c] = round(max(0.0, min(1.0, mod)), 4)
                else:
                    dom_grid[r][c] = max_global
                weight_grid[r][c] = dict(global_sources)

    return dom_grid, weight_grid
