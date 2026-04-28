"""
Yield Surface Engine (v3) — Multi-evidence: NDVI + stability + stress zones + suitability
==========================================================================================

Per-pixel yield prediction using:
  - L7 planning yield distribution (P10/P50/P90)
  - NDVI as biomass proxy (primary spatial)
  - Stability score (reliable NDVI → more trusted yield)
  - Stress zone penalty (water/nutrient stress zones reduce yield)
  - Suitability score modulation
"""
from typing import List, Optional
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l2_adapter import L2VegData
from layer10_sire.adapters.l4_l9_adapters import L7PlanningData


def generate_yield_surfaces(
    inp: Layer10Input, H: int, W: int,
    l7_data: Optional[L7PlanningData] = None,
    l1_data: Optional[L1SpatialData] = None,
    l2_data: Optional[L2VegData] = None,
) -> List[SurfaceArtifact]:
    """Generate yield surfaces with multi-evidence spatial modulation."""
    surfaces = []
    if l7_data is None:
        from layer10_sire.adapters.l4_l9_adapters import adapt_l7
        l7_data = adapt_l7(inp.planning)
    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l2_data is None:
        from layer10_sire.adapters.l2_adapter import adapt_l2
        l2_data = adapt_l2(inp.veg_int)

    if l7_data.yield_p50 == 0:
        return surfaces

    # Build spatial yield scalar: per-pixel fraction of field-mean yield potential
    yield_scalar = _build_yield_scalar(l1_data, l2_data, H, W)

    # --- 1. YIELD_P50 ---
    p50_grid = [[round(l7_data.yield_p50 * yield_scalar[r][c], 2)
                 for c in range(W)] for r in range(H)]
    surfaces.append(SurfaceArtifact(
        surface_id=f"YIELD_P50_{inp.plot_id}",
        semantic_type=SurfaceType.YIELD_P50,
        grid_ref=f"{H}x{W}",
        values=p50_grid,
        units="t/ha",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 15.0),
        palette_id=PaletteId.YIELD_BLUE,
        source_layers=["L2", "L7"],
    ))

    # --- 2. YIELD_GAP — inverted: lower scalar → bigger gap ---
    gap = l7_data.yield_p90 - l7_data.yield_p50
    gap_grid = [[round(gap * (2.0 - yield_scalar[r][c]), 2)
                 for c in range(W)] for r in range(H)]
    surfaces.append(SurfaceArtifact(
        surface_id=f"YIELD_GAP_{inp.plot_id}",
        semantic_type=SurfaceType.YIELD_GAP,
        grid_ref=f"{H}x{W}",
        values=gap_grid,
        units="t/ha",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 5.0),
        palette_id=PaletteId.YIELD_BLUE,
        source_layers=["L2", "L7"],
    ))

    # --- 3. PROFIT ---
    profit_grid = [[round(l7_data.profit_p50 * yield_scalar[r][c], 2)
                    for c in range(W)] for r in range(H)]
    surfaces.append(SurfaceArtifact(
        surface_id=f"PROFIT_{inp.plot_id}",
        semantic_type=SurfaceType.PROFIT_SURFACE,
        grid_ref=f"{H}x{W}",
        values=profit_grid,
        units="currency/ha",
        native_resolution_m=inp.resolution_m,
        render_range=(-500.0, 2000.0),
        palette_id=PaletteId.YIELD_BLUE,
        source_layers=["L2", "L7"],
    ))

    return surfaces


def _build_yield_scalar(l1: L1SpatialData, l2: L2VegData, H: int, W: int):
    """
    Build per-pixel yield scalar (0.5–1.5 of field mean):
      - NDVI / field mean: primary spatial proxy
      - Stability: trusted NDVI gets more weight
      - Zone-level: if zone metrics exist, use per-zone scalars
    """
    scalar = [[1.0] * W for _ in range(H)]

    # --- Evidence A: NDVI ratio ---
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
                            scalar[r][c] = v / ndvi_mean

    # --- Evidence B: Stability modulation ---
    # Stable areas → trust their scalar; heterogeneous → dampen toward mean
    stability_dampen = 1.0
    if l2.stability_class == 'HETEROGENEOUS':
        stability_dampen = 0.7
    elif l2.stability_class == 'TRANSIENT_VAR':
        stability_dampen = 0.85

    if stability_dampen < 1.0:
        for r in range(H):
            for c in range(W):
                deviation = scalar[r][c] - 1.0
                scalar[r][c] = 1.0 + deviation * stability_dampen

    # --- Evidence C: Zone-level adjustments ---
    if l2.zone_metrics and l1.zone_masks:
        for z_id, cells in l1.zone_masks.items():
            zm = l2.zone_metrics.get(z_id, {})
            if isinstance(zm, dict):
                zone_score = zm.get('stability_score', zm.get('quality', 0.5))
                # Low stability zones get dampened yield
                zone_factor = 0.8 + 0.4 * zone_score  # 0.8–1.2 range
                for r, c in cells:
                    if r < H and c < W:
                        scalar[r][c] *= zone_factor

    # Clamp to [0.3, 2.0]
    for r in range(H):
        for c in range(W):
            scalar[r][c] = max(0.3, min(2.0, scalar[r][c]))

    return scalar
