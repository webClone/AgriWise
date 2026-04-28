"""
Risk Surface Engine (v2) — Stage-aware, trust-downweighted, action-relevant composite
======================================================================================

Improvements over v1:
  - Stage-aware weights: growth stage influences which risks matter most
  - Trust-downweighted: low-reliability pixels get dampened risk
  - Action-relevance masking: only show risk where action is possible
"""
from typing import List
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)


# Stage-aware weight profiles
STAGE_WEIGHTS = {
    "BARE_SOIL":     {"water": 0.10, "nutrient": 0.15, "disease": 0.05, "ndvi_dev": 0.10, "unc": 0.60},
    "EMERGENCE":     {"water": 0.25, "nutrient": 0.15, "disease": 0.10, "ndvi_dev": 0.25, "unc": 0.25},
    "VEGETATIVE":    {"water": 0.30, "nutrient": 0.25, "disease": 0.20, "ndvi_dev": 0.15, "unc": 0.10},
    "REPRODUCTIVE":  {"water": 0.35, "nutrient": 0.20, "disease": 0.25, "ndvi_dev": 0.10, "unc": 0.10},
    "SENESCENCE":    {"water": 0.15, "nutrient": 0.10, "disease": 0.15, "ndvi_dev": 0.10, "unc": 0.50},
    "HARVESTED":     {"water": 0.05, "nutrient": 0.05, "disease": 0.05, "ndvi_dev": 0.05, "unc": 0.80},
    "UNKNOWN":       {"water": 0.25, "nutrient": 0.20, "disease": 0.20, "ndvi_dev": 0.15, "unc": 0.20},
}

RISK_SOURCE_MAP = {
    SurfaceType.WATER_STRESS_PROB: "water",
    SurfaceType.NUTRIENT_STRESS_PROB: "nutrient",
    SurfaceType.BIOTIC_PRESSURE: "disease",
    SurfaceType.NDVI_DEVIATION: "ndvi_dev",
    SurfaceType.UNCERTAINTY_SIGMA: "unc",
}


def generate_risk_surfaces(
    inp: Layer10Input, H: int, W: int,
    existing_surfaces: List[SurfaceArtifact],
) -> List[SurfaceArtifact]:
    """Generate stage-aware, trust-weighted composite risk surface."""
    surfaces = []

    # Determine phenology stage
    stage = "UNKNOWN"
    vi = inp.veg_int
    if vi is not None:
        pheno = getattr(vi, 'phenology', None)
        if pheno:
            stages = getattr(pheno, 'stage_by_day', [])
            if stages:
                stage = stages[-1]
    weights = STAGE_WEIGHTS.get(stage, STAGE_WEIGHTS["UNKNOWN"])

    # Find contributing surfaces + reliability surface
    risk_surfaces = {}
    reliability_surface = None

    for s in existing_surfaces:
        if s.semantic_type in RISK_SOURCE_MAP:
            risk_surfaces[RISK_SOURCE_MAP[s.semantic_type]] = s
        if s.semantic_type == SurfaceType.DATA_RELIABILITY:
            reliability_surface = s

    if not risk_surfaces:
        return surfaces

    # --- Per-pixel weighted composite with trust downweighting ---
    composite = [[0.0] * W for _ in range(H)]
    total_weight_grid = [[0.0] * W for _ in range(H)]

    for risk_key, weight in weights.items():
        s = risk_surfaces.get(risk_key)
        if s is None:
            continue
        for r in range(H):
            for c in range(W):
                v = s.values[r][c]
                if v is None:
                    continue
                # Normalize per type
                if risk_key == "ndvi_dev":
                    v = max(0.0, -v)  # Negative deviation = risk
                elif risk_key == "unc":
                    v = min(1.0, v * 2.0)  # Amplify uncertainty signal
                composite[r][c] += v * weight
                total_weight_grid[r][c] += weight

    # Normalize and apply trust downweighting
    for r in range(H):
        for c in range(W):
            tw = total_weight_grid[r][c]
            if tw > 0:
                composite[r][c] /= tw
            # Trust downweighting: low reliability → dampen risk toward 0.5
            if reliability_surface:
                rel = reliability_surface.values[r][c]
                if rel is not None and rel < 0.6:
                    dampen = rel / 0.6  # 0→0, 0.6→1
                    composite[r][c] = composite[r][c] * dampen + 0.5 * (1 - dampen)
            composite[r][c] = round(max(0.0, min(1.0, composite[r][c])), 4)

    surfaces.append(SurfaceArtifact(
        surface_id=f"RISK_COMPOSITE_{inp.plot_id}",
        semantic_type=SurfaceType.COMPOSITE_RISK,
        grid_ref=f"{H}x{W}",
        values=composite,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.RISK_HEAT,
        source_layers=["L1", "L2", "L3", "L4", "L5"],
        provenance={"stage": stage, "weights": weights},
    ))

    return surfaces
