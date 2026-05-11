"""
Nutrient Surface Engine (v4) — Spatially-aware from L4 + L1 soil + NDVI + SAR
==============================================================================

Multi-evidence spatial nutrient surfaces:
  - L4 NutrientState per nutrient (N, P, K)
  - L1 soil priors (soil_clay, soil_ph, soil_org_carbon)
  - L4 confounders (water stress, disease, salinity)
  - L4 zone_metrics (per-zone if available)
  - NDVI spatial modulation — ALWAYS applied as VRA proxy
  - SAR backscatter spatial texture (soil moisture → nutrient availability)

v4 Change: NDVI modulation is no longer "last resort". It is always blended
into the surface to ensure spatial heterogeneity even when soil rasters are
spatially uniform (e.g. SoilGrids single-point lookups broadcast to grid).
"""
from typing import List, Optional, Dict, Any
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l4_l9_adapters import L4NutrientData


def generate_nutrient_surfaces(
    inp: Layer10Input, H: int, W: int,
    l4_data: Optional[L4NutrientData] = None,
    l1_data: Optional[L1SpatialData] = None,
) -> List[SurfaceArtifact]:
    """Generate nutrient surfaces using multi-evidence spatial synthesis."""
    surfaces = []
    if l4_data is None:
        from layer10_sire.adapters.l4_l9_adapters import adapt_l4
        l4_data = adapt_l4(inp.nutrients)
    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_spatially_uniform(raster, H: int, W: int) -> bool:
    """Check if a raster has the same value everywhere (e.g. SoilGrids broadcast).

    Returns True if all non-None pixels share exactly the same value,
    meaning the raster provides no spatial differentiation.
    """
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


def _raster_stats(raster, H: int, W: int):
    """Pre-compute mean, min, max for a raster. Returns (mean, mn, mx, count)."""
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


def _build_nutrient_stress_surface(l4: L4NutrientData, l1: L1SpatialData, H: int, W: int):
    """
    Build nutrient stress surface from:
      1. L4 per-nutrient deficiency probabilities (field-level base)
      2. Zone rasterization if per-zone metrics available
      3. Soil texture priors (clay, pH, organic carbon)
      4. NDVI-based spatial modulation (always applied as VRA proxy)
      5. SAR backscatter modulation (soil moisture → nutrient availability)
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
        return _apply_spatial_modulation(grid, l1, H, W)

    # --- Priority 2: Uniform base → spatially modulated ---
    grid = [[round(max_def, 4)] * W for _ in range(H)]
    return _apply_spatial_modulation(grid, l1, H, W)


def _apply_spatial_modulation(grid, l1: L1SpatialData, H: int, W: int):
    """Modulate nutrient stress spatially using all available evidence.

    Combines:
      - Soil property rasters (clay, pH, SOC) — only if spatially heterogeneous
      - NDVI raster — always applied (VRA principle: low NDVI → higher stress)
      - SAR VH/VV backscatter — soil moisture proxy (wet → better nutrient transport)

    NDVI modulation was previously gated behind `not has_soil`, which made the
    surface spatially uniform whenever SoilGrids provided data (uniform values).
    Now NDVI is always blended, with its weight increased when soil data is
    spatially homogeneous.
    """
    soil_clay = l1.raster_maps.get('soil_clay')
    soil_ph = l1.raster_maps.get('soil_ph')
    soil_oc = l1.raster_maps.get('soil_org_carbon')
    ndvi = l1.raster_maps.get('ndvi')
    sar_vh = l1.raster_maps.get('vh') or l1.raster_maps.get('VH')

    # Detect spatially-uniform soil rasters (SoilGrids single-point broadcast)
    soil_has_spatial_info = False
    if soil_clay and not _is_spatially_uniform(soil_clay, H, W):
        soil_has_spatial_info = True
    if soil_ph and not _is_spatially_uniform(soil_ph, H, W):
        soil_has_spatial_info = True
    if soil_oc and not _is_spatially_uniform(soil_oc, H, W):
        soil_has_spatial_info = True

    # Pre-compute NDVI statistics (avoids O(H²W²) recomputation per pixel)
    ndvi_mean, ndvi_min, ndvi_max, ndvi_count = 0.5, 0.0, 1.0, 0
    ndvi_range = 0.0
    if ndvi:
        ndvi_mean, ndvi_min, ndvi_max, ndvi_count = _raster_stats(ndvi, H, W)
        ndvi_range = ndvi_max - ndvi_min

    # Pre-compute SAR VH statistics (soil moisture spatial proxy)
    sar_mean, sar_min, sar_max, sar_count = 0.0, 0.0, 0.0, 0
    sar_range = 0.0
    if sar_vh:
        sar_mean, sar_min, sar_max, sar_count = _raster_stats(sar_vh, H, W)
        sar_range = sar_max - sar_min

    # NDVI modulation weight — stronger when soil is spatially uniform
    ndvi_mod_weight = 0.5 if soil_has_spatial_info else 0.7

    for r in range(H):
        for c in range(W):
            if grid[r][c] is None:
                continue
            base = grid[r][c]
            modifier = 1.0

            # --- Soil property modulation (unchanged, always applied) ---

            # Sandy soil → higher nutrient stress (clay < 15%)
            if soil_clay and r < len(soil_clay) and c < len(soil_clay[r]) and soil_clay[r][c] is not None:
                clay = soil_clay[r][c]
                if clay < 15:
                    modifier *= 1.3  # More leaching
                elif clay > 40:
                    modifier *= 0.8  # Better retention

            # Low organic carbon → higher stress
            if soil_oc and r < len(soil_oc) and c < len(soil_oc[r]) and soil_oc[r][c] is not None:
                oc = soil_oc[r][c]
                if oc < 1.0:
                    modifier *= 1.2
                elif oc > 3.0:
                    modifier *= 0.7

            # Extreme pH → nutrient lockout
            if soil_ph and r < len(soil_ph) and c < len(soil_ph[r]) and soil_ph[r][c] is not None:
                ph = soil_ph[r][c]
                if ph < 5.5 or ph > 8.0:
                    modifier *= 1.3  # Nutrient availability drops

            # --- NDVI spatial modulation (ALWAYS applied) ---
            # VRA principle: low NDVI relative to field mean indicates
            # reduced canopy vigor, which correlates with nutrient stress.
            # Higher NDVI → healthier canopy → lower nutrient stress.
            if ndvi and ndvi_count > 0 and ndvi_range > 0.02 and ndvi_mean > 0:
                pixel_ndvi = ndvi[r][c] if r < len(ndvi) and c < len(ndvi[r]) else None
                if pixel_ndvi is not None:
                    # Normalize pixel NDVI relative to field: [-1, +1]
                    ndvi_deviation = (pixel_ndvi - ndvi_mean) / ndvi_range
                    # Invert: low NDVI → positive stress modifier
                    # Scale: ±ndvi_mod_weight of the base value
                    ndvi_factor = 1.0 - (ndvi_deviation * ndvi_mod_weight)
                    modifier *= max(0.4, min(1.8, ndvi_factor))

            # --- SAR VH spatial modulation (soil moisture proxy) ---
            # Higher VH backscatter → wetter soil → better nutrient transport
            # Lower VH → drier soil → reduced nutrient mobility → more stress
            if sar_vh and sar_count > 0 and sar_range > 0.5:
                pixel_vh = sar_vh[r][c] if r < len(sar_vh) and c < len(sar_vh[r]) else None
                if pixel_vh is not None:
                    sar_deviation = (pixel_vh - sar_mean) / sar_range
                    # Invert: low VH (dry) → higher stress
                    sar_factor = 1.0 - (sar_deviation * 0.25)
                    modifier *= max(0.7, min(1.3, sar_factor))

            grid[r][c] = round(max(0.0, min(1.0, base * modifier)), 4)

    return grid


def _build_fertility_limitation(l4: L4NutrientData, l1: L1SpatialData, H: int, W: int):
    """Build fertility limitation surface: soil quality + L4 confidence + confounders.

    Always uses NDVI spatial modulation for spatial differentiation, regardless
    of whether soil rasters exist.
    """
    from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi

    # Base limitation from L4 confidence (lower confidence → higher limitation)
    min_conf = 1.0
    has_water_confounder = False
    for state in l4.nutrient_states.values():
        min_conf = min(min_conf, state.get('confidence', 1.0))
        sev = state.get('severity', 'LOW')
        if sev in ('MODERATE', 'HIGH'):
            has_water_confounder = True

    base_limitation = round(1.0 - min_conf, 4)

    # Start with NDVI-modulated base (always, not gated behind missing soil)
    ndvi_r = get_ndvi_raster(l1, H, W)
    grid = modulate_by_ndvi(
        base_limitation, ndvi_r, H, W,
        invert=True, clamp_min=0.0, clamp_max=1.0,
    )

    # Overlay soil texture penalties on top of NDVI-modulated surface
    soil_clay = l1.raster_maps.get('soil_clay')
    soil_oc = l1.raster_maps.get('soil_org_carbon')

    for r in range(H):
        for c in range(W):
            soil_penalty = 0.0
            if soil_clay and r < len(soil_clay) and c < len(soil_clay[r]) and soil_clay[r][c] is not None:
                if soil_clay[r][c] < 10:
                    soil_penalty += 0.15
            if soil_oc and r < len(soil_oc) and c < len(soil_oc[r]) and soil_oc[r][c] is not None:
                if soil_oc[r][c] < 1.0:
                    soil_penalty += 0.10
            grid[r][c] = round(min(1.0, grid[r][c] + soil_penalty), 4)

    return grid
