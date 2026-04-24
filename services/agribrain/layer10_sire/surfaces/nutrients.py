"""
Nutrient Surface Engine (v3) — Source-grounded from L4 + L1 soil + confounders
==============================================================================

Multi-evidence spatial nutrient surfaces:
  - L4 NutrientState per nutrient (N, P, K)
  - L1 soil priors (soil_clay, soil_ph, soil_org_carbon)
  - L4 confounders (water stress, disease, salinity)
  - L4 zone_metrics (per-zone if available)
  - NDVI as final modulation if no other spatial source
"""
from typing import List, Optional, Dict, Any
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l4_l9_adapters import L4NutrientData


def generate_nutrient_surfaces(
    inp: Layer10Input, H: int, W: int,
    l4_data: Optional[L4NutrientData] = None,
    l1_data: Optional[L1SpatialData] = None,
) -> List[SurfaceArtifact]:
    """Generate nutrient surfaces using multi-evidence spatial synthesis."""
    surfaces = []
    if l4_data is None:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l4
        l4_data = adapt_l4(inp.nutrients)
    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)

    if not l4_data.nutrient_states:
        return surfaces

    # --- 1. NUTRIENT_STRESS_PROB — multi-evidence spatial synthesis ---
    stress_grid = _build_nutrient_stress_surface(l4_data, l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"NUT_STRESS_{inp.plot_id}",
        semantic_type=SurfaceType.NUTRIENT_STRESS_PROB,
        grid_ref=f"{H}x{W}",
        values=stress_grid,
        units="probability",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.NUTRIENT_YELLOW,
        source_layers=["L1", "L4"],
    ))

    # --- 2. FERTILITY_LIMITATION — soil-grounded limitation ---
    lim_grid = _build_fertility_limitation(l4_data, l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"FERTILITY_LIM_{inp.plot_id}",
        semantic_type=SurfaceType.FERTILITY_LIMITATION,
        grid_ref=f"{H}x{W}",
        values=lim_grid,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.NUTRIENT_YELLOW,
        source_layers=["L1", "L4"],
    ))

    return surfaces


def _build_nutrient_stress_surface(l4: L4NutrientData, l1: L1SpatialData, H: int, W: int):
    """
    Build nutrient stress surface from:
      1. L4 per-nutrient deficiency probabilities
      2. Soil texture priors (clay, pH, organic carbon)
      3. Zone rasterization if per-zone metrics available
      4. NDVI modulation as final spatial proxy
    """
    # Aggregate deficiency: max across N, P, K
    max_def = 0.0
    nutrient_probs = {}
    for nut_key, state in l4.nutrient_states.items():
        p = state.get('probability_deficient', 0.0)
        nutrient_probs[nut_key] = p
        max_def = max(max_def, p)

    # --- Priority 1: Zone rasterization from L4 zone_metrics ---
    if l4.zone_metrics and l1.zone_masks:
        grid = [[None] * W for _ in range(H)]
        assigned = set()
        for z_id, cells in l1.zone_masks.items():
            zm = l4.zone_metrics.get(z_id, {})
            zone_stress = zm.get('nutrient_stress', max_def) if isinstance(zm, dict) else max_def
            for r, c in cells:
                if r < H and c < W:
                    grid[r][c] = round(zone_stress, 4)
                    assigned.add((r, c))
        # Fill unassigned
        for r in range(H):
            for c in range(W):
                if (r, c) not in assigned:
                    grid[r][c] = round(max_def, 4)
        return _apply_soil_modulation(grid, l1, H, W)

    # --- Priority 2: Soil-texture modulated stress ---
    grid = [[round(max_def, 4)] * W for _ in range(H)]
    return _apply_soil_modulation(grid, l1, H, W)


def _apply_soil_modulation(grid, l1: L1SpatialData, H: int, W: int):
    """Modulate nutrient stress by soil properties — sandy/low-OC → more stress."""
    soil_clay = l1.raster_maps.get('soil_clay')
    soil_ph = l1.raster_maps.get('soil_ph')
    soil_oc = l1.raster_maps.get('soil_org_carbon')
    ndvi = l1.raster_maps.get('ndvi')

    has_soil = soil_clay or soil_ph or soil_oc

    for r in range(H):
        for c in range(W):
            if grid[r][c] is None:
                continue
            base = grid[r][c]
            modifier = 1.0

            # Sandy soil → higher nutrient stress (clay < 15%)
            if soil_clay and soil_clay[r][c] is not None:
                clay = soil_clay[r][c]
                if clay < 15:
                    modifier *= 1.3  # More leaching
                elif clay > 40:
                    modifier *= 0.8  # Better retention

            # Low organic carbon → higher stress
            if soil_oc and soil_oc[r][c] is not None:
                oc = soil_oc[r][c]
                if oc < 1.0:
                    modifier *= 1.2
                elif oc > 3.0:
                    modifier *= 0.7

            # Extreme pH → nutrient lockout
            if soil_ph and soil_ph[r][c] is not None:
                ph = soil_ph[r][c]
                if ph < 5.5 or ph > 8.0:
                    modifier *= 1.3  # Nutrient availability drops

            # NDVI proxy (last resort spatial differentiation)
            if not has_soil and ndvi and ndvi[r][c] is not None:
                ndvi_vals = [ndvi[rr][cc] for rr in range(H) for cc in range(W) if ndvi[rr][cc] is not None]
                if ndvi_vals:
                    ndvi_mean = sum(ndvi_vals) / len(ndvi_vals)
                    if ndvi_mean > 0:
                        modifier *= max(0.5, 2.0 - ndvi[r][c] / ndvi_mean)

            grid[r][c] = round(max(0.0, min(1.0, base * modifier)), 4)

    return grid


def _build_fertility_limitation(l4: L4NutrientData, l1: L1SpatialData, H: int, W: int):
    """Build fertility limitation surface: soil quality + L4 confidence + confounders."""
    # Base limitation from L4 confidence (lower confidence → higher limitation)
    min_conf = 1.0
    has_water_confounder = False
    for state in l4.nutrient_states.values():
        min_conf = min(min_conf, state.get('confidence', 1.0))
        sev = state.get('severity', 'LOW')
        if sev in ('MODERATE', 'HIGH'):
            has_water_confounder = True

    base_limitation = round(1.0 - min_conf, 4)

    grid = [[base_limitation] * W for _ in range(H)]

    # Soil texture adds limitation: sandy + low OC → more limited
    soil_clay = l1.raster_maps.get('soil_clay')
    soil_oc = l1.raster_maps.get('soil_org_carbon')

    for r in range(H):
        for c in range(W):
            soil_penalty = 0.0
            if soil_clay and soil_clay[r][c] is not None:
                if soil_clay[r][c] < 10:
                    soil_penalty += 0.15
            if soil_oc and soil_oc[r][c] is not None:
                if soil_oc[r][c] < 1.0:
                    soil_penalty += 0.10
            grid[r][c] = round(min(1.0, grid[r][c] + soil_penalty), 4)

    return grid
