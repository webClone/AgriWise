"""
Suitability Surface Engine (v2) — From L7 adapter
"""
from typing import List, Optional
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l4_l9_adapters import L7PlanningData


def generate_suitability_surfaces(
    inp: Layer10Input, H: int, W: int,
    l7_data: Optional[L7PlanningData] = None,
) -> List[SurfaceArtifact]:
    """Generate suitability surface from L7 adapter data."""
    surfaces = []
    if l7_data is None:
        from layer10_sire.adapters.l4_l9_adapters import adapt_l7
        l7_data = adapt_l7(inp.planning)

    if l7_data.suitability_pct == 0:
        return surfaces

    suit = l7_data.suitability_pct / 100.0

    # Spatial modulation: higher NDVI = higher suitability
    from layer10_sire.adapters.l1_adapter import adapt_l1
    from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined
    l1_data = adapt_l1(inp.field_tensor, H, W)
    ndvi_r = get_ndvi_raster(l1_data, H, W)
    suit_grid = modulate_combined(suit, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)

    surfaces.append(SurfaceArtifact(
        surface_id=f"SUITABILITY_{inp.plot_id}",
        semantic_type=SurfaceType.CROP_SUITABILITY,
        grid_ref=f"{H}x{W}",
        values=suit_grid,
        units="fraction",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L7"],
    ))

    return surfaces
