"""
Yield Surface Engine (v4) — Stress-integrated yield intelligence
==================================================================

Per-pixel yield prediction using:
  - L7 planning yield distribution (P10/P50/P90)
  - NDVI as biomass proxy (primary spatial)
  - Stability score (reliable NDVI → more trusted yield)
  - Stress zone penalty (water/nutrient/disease surfaces → yield loss)
  - Suitability score modulation

v4: Added YIELD_PENALTY and YIELD_VALUE_AT_RISK surfaces that translate
    observed stress into economic impact. A farmer can now see:
    "Water stress in zone A is projected to reduce yield by 0.8 t/ha"
"""
from typing import List, Optional
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l2_adapter import L2VegData
from services.agribrain.layer10_sire.adapters.l4_l9_adapters import L7PlanningData


# Stress → yield penalty response curves (fraction of yield lost)
# Source: empirical yield response models (Doorenbos & Kassam 1979)
_STRESS_YIELD_FACTOR = {
    "water":    0.45,   # Ky ≈ 0.45 for grain crops (FAO-33)
    "nutrient": 0.35,   # Moderate N-response
    "disease":  0.30,   # Biotic pressure → quality + quantity loss
}


def generate_yield_surfaces(
    inp: Layer10Input, H: int, W: int,
    l7_data: Optional[L7PlanningData] = None,
    l1_data: Optional[L1SpatialData] = None,
    l2_data: Optional[L2VegData] = None,
    existing_surfaces: Optional[List[SurfaceArtifact]] = None,
) -> List[SurfaceArtifact]:
    """Generate yield surfaces with multi-evidence spatial modulation."""
    surfaces = []
    if l7_data is None:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l7
        l7_data = adapt_l7(inp.planning)
    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l2_data is None:
        from services.agribrain.layer10_sire.adapters.l2_adapter import adapt_l2
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

    # --- 4. YIELD_PENALTY — stress-integrated yield loss per pixel ---
    # Uses observed stress surfaces to estimate actual yield reduction
    if existing_surfaces:
        penalty_grid, penalty_prov = _compute_yield_penalty(
            p50_grid, existing_surfaces, H, W
        )
        surfaces.append(SurfaceArtifact(
            surface_id=f"YIELD_PENALTY_{inp.plot_id}",
            semantic_type=SurfaceType.YIELD_PENALTY,
            grid_ref=f"{H}x{W}",
            values=penalty_grid,
            units="t/ha",
            native_resolution_m=inp.resolution_m,
            render_range=(0.0, 5.0),
            palette_id=PaletteId.STRESS_RED,
            source_layers=["L2", "L3", "L4", "L5", "L7"],
            provenance=penalty_prov,
        ))

        # --- 5. YIELD_VALUE_AT_RISK — monetary loss surface ---
        price_per_ton = getattr(l7_data, 'price_per_ton', 0)
        if price_per_ton <= 0:
            price_per_ton = 250.0  # Default: $250/t for grain crops
        var_grid = [[round(penalty_grid[r][c] * price_per_ton, 2)
                     for c in range(W)] for r in range(H)]
        surfaces.append(SurfaceArtifact(
            surface_id=f"YIELD_VAR_{inp.plot_id}",
            semantic_type=SurfaceType.YIELD_VALUE_AT_RISK,
            grid_ref=f"{H}x{W}",
            values=var_grid,
            units="currency/ha",
            native_resolution_m=inp.resolution_m,
            render_range=(0.0, 1500.0),
            palette_id=PaletteId.RISK_HEAT,
            source_layers=["L2", "L3", "L4", "L5", "L7"],
            provenance={
                "price_per_ton": price_per_ton,
                "reference": "Doorenbos & Kassam 1979, FAO-33",
            },
        ))

    return surfaces


def _compute_yield_penalty(
    p50_grid, existing_surfaces: List[SurfaceArtifact], H: int, W: int
):
    """Compute per-pixel yield penalty from observed stress surfaces.

    Uses the Stewart model (FAO-33): Ya/Ym = 1 - Ky × (1 - ETa/ETm)
    Generalized: yield_loss = potential × Σ(stress_i × Ky_i)

    Penalty is multiplicative: if water stress = 0.6 and Ky = 0.45,
    that pixel loses 27% of its potential yield (0.6 × 0.45).
    """
    # Find stress surfaces
    stress_map = {
        SurfaceType.WATER_STRESS_PROB: "water",
        SurfaceType.NUTRIENT_STRESS_PROB: "nutrient",
        SurfaceType.BIOTIC_PRESSURE: "disease",
    }

    stress_surfaces = {}
    for s in existing_surfaces:
        if s.semantic_type in stress_map:
            stress_surfaces[stress_map[s.semantic_type]] = s

    penalty = [[0.0] * W for _ in range(H)]
    max_loss = 0.0

    for r in range(H):
        for c in range(W):
            potential = p50_grid[r][c] if p50_grid[r][c] is not None else 0
            total_penalty_frac = 0.0

            for stress_key, ky in _STRESS_YIELD_FACTOR.items():
                surf = stress_surfaces.get(stress_key)
                if surf is None:
                    continue
                stress_val = surf.values[r][c] if r < len(surf.values) and c < len(surf.values[r]) else None
                if stress_val is not None:
                    total_penalty_frac += stress_val * ky

            # Cap total penalty at 85% (total crop failure rare in irrigated ag)
            total_penalty_frac = min(0.85, total_penalty_frac)
            pixel_loss = round(potential * total_penalty_frac, 3)
            penalty[r][c] = pixel_loss
            max_loss = max(max_loss, pixel_loss)

    # Compute field-average stats for provenance
    all_vals = [penalty[r][c] for r in range(H) for c in range(W)]
    avg_loss = sum(all_vals) / len(all_vals) if all_vals else 0

    prov = {
        "stress_sources": list(stress_surfaces.keys()),
        "yield_factors": {k: v for k, v in _STRESS_YIELD_FACTOR.items() if k in stress_surfaces},
        "max_pixel_loss_tha": round(max_loss, 2),
        "mean_field_loss_tha": round(avg_loss, 2),
        "reference": "Stewart model (FAO-33, Doorenbos & Kassam 1979)",
    }

    return penalty, prov


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
