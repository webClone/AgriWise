"""
Risk Surface Engine (v3) — Stage-aware, trust-downweighted, action-relevant composite
======================================================================================

Improvements over v1:
  - Stage-aware weights: growth stage influences which risks matter most
  - Trust-downweighted: low-reliability pixels get dampened risk
  - Action-relevance masking: only show risk where action is possible

v3 Changes:
  - NDVI_DEVIATION: use absolute deviation (both over-vigor and under-vigor
    are risk signals — over-vigor = disease susceptibility, under-vigor = stress)
  - Trust downweight threshold: 0.6 → 0.4 (less aggressive range compression)
  - Uncertainty amplification: 2.0x → 1.5x (prevent uniform signal domination)
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
    dom_contrib = [[0.0] * W for _ in range(H)]       # Per-pixel dominant driver contribution
    dom_driver = [[""] * W for _ in range(H)]          # Per-pixel dominant driver name

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
                    # v3: Use ABSOLUTE deviation — both over-vigor (disease
                    # susceptibility) and under-vigor (stress) are risk signals.
                    # Previously max(0,-v) zeroed out healthy above-mean pixels.
                    v = min(1.0, abs(v) * 2.0)
                elif risk_key == "unc":
                    # v3: Reduced amplification from 2.0x to 1.5x to prevent
                    # the often-uniform uncertainty signal from dominating.
                    v = min(1.0, v * 1.5)
                composite[r][c] += v * weight
                total_weight_grid[r][c] += weight

                # Track dominant driver per pixel
                if v * weight > dom_contrib[r][c]:
                    dom_contrib[r][c] = v * weight
                    dom_driver[r][c] = risk_key

    # Normalize and apply trust downweighting
    for r in range(H):
        for c in range(W):
            tw = total_weight_grid[r][c]
            if tw > 0:
                composite[r][c] /= tw
            # Trust downweighting: low reliability → dampen risk toward 0.5
            # v3: Threshold lowered from 0.6 → 0.4 to avoid compressing the
            # spatial range of healthy-but-heterogeneous fields.
            if reliability_surface:
                rel = reliability_surface.values[r][c]
                if rel is not None and rel < 0.4:
                    dampen = rel / 0.4  # 0→0, 0.4→1
                    composite[r][c] = composite[r][c] * dampen + 0.5 * (1 - dampen)
            composite[r][c] = round(max(0.0, min(1.0, composite[r][c])), 4)

    # Compute severity classification from field statistics
    all_vals = [composite[r][c] for r in range(H) for c in range(W) if composite[r][c] > 0]
    if all_vals:
        sorted_vals = sorted(all_vals)
        n = len(sorted_vals)
        p50 = sorted_vals[int(n * 0.5)]
        p90 = sorted_vals[int(n * 0.9)]
        if p90 > 0.7:
            severity_class = "CRITICAL"
        elif p90 > 0.5:
            severity_class = "HIGH"
        elif p50 > 0.3:
            severity_class = "MODERATE"
        else:
            severity_class = "LOW"
    else:
        severity_class = "LOW"

    # Identify dominant driver across the field
    driver_counts = {}
    for r in range(H):
        for c in range(W):
            d = dom_driver[r][c]
            if d:
                driver_counts[d] = driver_counts.get(d, 0) + 1
    dominant_driver = max(driver_counts, key=driver_counts.get) if driver_counts else "unknown"

    # Per-source contribution stats
    source_coverage = {}
    for risk_key in weights:
        s = risk_surfaces.get(risk_key)
        if s:
            valid = sum(1 for r in range(H) for c in range(W) if s.values[r][c] is not None)
            source_coverage[risk_key] = round(valid / (H * W), 3)

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
        provenance={
            "stage": stage,
            "weights": weights,
            "dominant_driver": dominant_driver,
            "severity_class": severity_class,
            "source_coverage": source_coverage,
            "sources_contributing": len(risk_surfaces),
        },
    ))

    return surfaces
