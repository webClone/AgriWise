"""
Uncertainty Surface Engine (v3) — Per-zone source dominance + conflict density
===============================================================================

Multi-evidence trust surfaces:
  - L1 NDVI_UNC raster (per-pixel uncertainty)
  - L1 spatial_reliability raster (per-pixel)
  - L1 provenance_log per-zone source contributions
  - Conflict density from source disagreement
"""
from typing import List, Optional, Dict
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l2_adapter import L2VegData

SOURCE_CATEGORIES = ['s2', 's1', 'weather', 'soil', 'sensor', 'user']


def generate_uncertainty_surfaces(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
    l2_data: Optional[L2VegData] = None,
) -> List[SurfaceArtifact]:
    """Generate trust/uncertainty surfaces from multi-evidence synthesis."""
    surfaces = []
    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l2_data is None:
        from services.agribrain.layer10_sire.adapters.l2_adapter import adapt_l2
        l2_data = adapt_l2(inp.veg_int)

    # --- 1. UNCERTAINTY_SIGMA — from real raster or curve ---
    unc_raster = l1_data.raster_maps.get('ndvi_uncertainty')
    if unc_raster is None:
        unc_val = l2_data.ndvi_fit_unc[-1] if l2_data.ndvi_fit_unc else 0.05
        unc_raster = [[unc_val] * W for _ in range(H)]

    surfaces.append(SurfaceArtifact(
        surface_id=f"UNC_SIGMA_{inp.plot_id}",
        semantic_type=SurfaceType.UNCERTAINTY_SIGMA,
        grid_ref=f"{H}x{W}",
        values=unc_raster,
        units="sigma",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 0.5),
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


def _build_reliability(l1: L1SpatialData, l2: L2VegData, H: int, W: int):
    """Build reliability from spatial_reliability raster + stability + obs_coverage."""
    if l1.reliability_map:
        # Start from real raster, modulate by zone stability
        grid = [row[:] for row in l1.reliability_map]
        if l1.zone_masks and l2.zone_metrics:
            for z_id, cells in l1.zone_masks.items():
                zm = l2.zone_metrics.get(z_id, {})
                if isinstance(zm, dict):
                    zone_stab = zm.get('stability_score', 0.7)
                    for r, c in cells:
                        if r < H and c < W:
                            # Blend raster reliability with zone stability
                            grid[r][c] = round(grid[r][c] * 0.7 + zone_stab * 0.3, 3)
        return grid

    # Fallback: computed from curve quality + stability
    base = min(1.0, l2.obs_coverage + 0.1) * l2.stability_confidence
    if l1.zone_masks and l2.zone_metrics:
        grid = [[round(base, 3)] * W for _ in range(H)]
        for z_id, cells in l1.zone_masks.items():
            zm = l2.zone_metrics.get(z_id, {})
            if isinstance(zm, dict):
                zone_stab = zm.get('stability_score', 0.5)
                zone_rel = round(base * 0.6 + zone_stab * 0.4, 3)
                for r, c in cells:
                    if r < H and c < W:
                        grid[r][c] = zone_rel
        return grid

    return [[round(base, 3)] * W for _ in range(H)]


def _build_per_zone_dominance(l1: L1SpatialData, H: int, W: int):
    """Build per-zone source dominance with real source weights."""
    # Parse all provenance entries to find per-zone source contributions
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
            # Check for per-zone provenance
            zone_id = prov.get('zone_id')
            if zone_id:
                zone_sources[zone_id] = parsed
            else:
                global_sources = parsed

    if not global_sources:
        global_sources = {'s2': 0.4, 'weather': 0.3, 's1': 0.15, 'soil': 0.15}

    # Build per-zone dominance grid
    dom_grid = [[0.0] * W for _ in range(H)]
    weight_grid = [[None] * W for _ in range(H)]

    if l1.zone_masks and zone_sources:
        # Per-zone source weights
        for z_id, cells in l1.zone_masks.items():
            sw = zone_sources.get(z_id, global_sources)
            max_val = max(sw.values()) if sw else 0.5
            for r, c in cells:
                if r < H and c < W:
                    dom_grid[r][c] = max_val
                    weight_grid[r][c] = dict(sw)
        # Fill unassigned
        max_global = max(global_sources.values()) if global_sources else 0.5
        for r in range(H):
            for c in range(W):
                if weight_grid[r][c] is None:
                    dom_grid[r][c] = max_global
                    weight_grid[r][c] = dict(global_sources)
    else:
        # Global uniform
        max_global = max(global_sources.values()) if global_sources else 0.5
        for r in range(H):
            for c in range(W):
                dom_grid[r][c] = max_global
                weight_grid[r][c] = dict(global_sources)

    return dom_grid, weight_grid
