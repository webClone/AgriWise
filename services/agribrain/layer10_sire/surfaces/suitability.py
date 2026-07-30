"""
Suitability Surface Engine (v2) — From L7 adapter
"""
from typing import List, Optional
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.layer10_sire.adapters.l4_l9_adapters import L7PlanningData
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData


def generate_suitability_surfaces(
    inp: Layer10Input, H: int, W: int,
    l7_data: Optional[L7PlanningData] = None,
    l1_data: Optional[L1SpatialData] = None,
) -> List[SurfaceArtifact]:
    """Generate suitability surfaces from L7 adapter data."""
    surfaces = []
    if l7_data is None:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l7
        l7_data = adapt_l7(inp.planning)

    # If L7 planning data is missing entirely, default to 0.75 suitability
    suit = 0.75
    if l7_data and l7_data.suitability_pct > 0:
        suit = l7_data.suitability_pct / 100.0

    from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined
    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    ndvi_r = get_ndvi_raster(l1_data, H, W)
    
    # 1. CROP_SUITABILITY
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

    # 2. WATER_FEASIBILITY
    water_base = 0.80
    if l7_data and l7_data.suitability_states:
        water_base = l7_data.suitability_states.get("WATER", {}).get("probability_ok", 0.80)
    water_grid = modulate_combined(water_base, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)
    surfaces.append(SurfaceArtifact(
        surface_id=f"WATER_FEASIBILITY_{inp.plot_id}",
        semantic_type=SurfaceType.WATER_FEASIBILITY,
        grid_ref=f"{H}x{W}",
        values=water_grid,
        units="fraction",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L7"],
    ))

    # 3. BIOTIC_FEASIBILITY
    biotic_base = 0.85
    if l7_data and l7_data.suitability_states:
        biotic_base = l7_data.suitability_states.get("BIOTIC", {}).get("probability_ok", 0.85)
    biotic_grid = modulate_combined(biotic_base, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)
    surfaces.append(SurfaceArtifact(
        surface_id=f"BIOTIC_FEASIBILITY_{inp.plot_id}",
        semantic_type=SurfaceType.BIOTIC_FEASIBILITY,
        grid_ref=f"{H}x{W}",
        values=biotic_grid,
        units="fraction",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L7"],
    ))

    # 4. ECONOMIC_SUITABILITY
    econ_base = 0.70
    if l7_data and l7_data.profit_p50 > 0:
        econ_base = min(1.0, max(0.0, l7_data.profit_p50 / 2500.0))
        if econ_base < 0.1:
            econ_base = 0.70
    econ_grid = modulate_combined(econ_base, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)
    surfaces.append(SurfaceArtifact(
        surface_id=f"ECONOMIC_SUITABILITY_{inp.plot_id}",
        semantic_type=SurfaceType.ECONOMIC_SUITABILITY,
        grid_ref=f"{H}x{W}",
        values=econ_grid,
        units="fraction",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L7"],
    ))

    # 5. SUITABILITY_WINDOW (Planting window countdown)
    window_base = 0.75
    if l7_data and l7_data.suitability_states:
        window_base = l7_data.suitability_states.get("WINDOW", {}).get("probability_ok", 0.75)
    window_grid = modulate_combined(window_base, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)
    surfaces.append(SurfaceArtifact(
        surface_id=f"SUITABILITY_WINDOW_{inp.plot_id}",
        semantic_type=SurfaceType.SUITABILITY_WINDOW,
        grid_ref=f"{H}x{W}",
        values=window_grid,
        units="fraction",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L7"],
    ))

    # 6. SEASON_PROGRESS
    progress_base = 0.40
    if l7_data and l7_data.season_progress_pct > 0:
        progress_base = l7_data.season_progress_pct / 100.0
    progress_grid = modulate_combined(progress_base, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)
    surfaces.append(SurfaceArtifact(
        surface_id=f"SEASON_PROGRESS_{inp.plot_id}",
        semantic_type=SurfaceType.SEASON_PROGRESS,
        grid_ref=f"{H}x{W}",
        values=progress_grid,
        units="fraction",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L7"],
    ))

    return surfaces
