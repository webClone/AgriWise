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
import hashlib
import json
from typing import List
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.scientific_contracts.crop_phenology import (
    consume_canonical_phenology_output,
)


# Stage-aware weight profiles
# v4: Removed uncertainty (unc) — data quality should NOT inflate risk scores.
# Uncertainty now modulates CONFIDENCE of the risk assessment via trust
# downweighting (see reliability_surface block below), not the score itself.
STAGE_WEIGHTS = {
    "BARE_SOIL":     {"water": 0.15, "nutrient": 0.25, "disease": 0.10, "ndvi_dev": 0.50},
    "EMERGENCE":     {"water": 0.30, "nutrient": 0.20, "disease": 0.15, "ndvi_dev": 0.35},
    "VEGETATIVE":    {"water": 0.35, "nutrient": 0.25, "disease": 0.25, "ndvi_dev": 0.15},
    "REPRODUCTIVE":  {"water": 0.35, "nutrient": 0.25, "disease": 0.25, "ndvi_dev": 0.15},
    "SENESCENCE":    {"water": 0.20, "nutrient": 0.15, "disease": 0.25, "ndvi_dev": 0.40},
    "HARVESTED":     {"water": 0.15, "nutrient": 0.15, "disease": 0.10, "ndvi_dev": 0.60},
    "UNKNOWN":       {"water": 0.30, "nutrient": 0.25, "disease": 0.20, "ndvi_dev": 0.25},
}

RISK_SOURCE_MAP = {
    SurfaceType.WATER_STRESS_PROB: "water",
    SurfaceType.NUTRIENT_STRESS_PROB: "nutrient",
    SurfaceType.BIOTIC_PRESSURE: "disease",
    SurfaceType.NDVI_DEVIATION: "ndvi_dev",
}


def generate_risk_surfaces(
    inp: Layer10Input, H: int, W: int,
    existing_surfaces: List[SurfaceArtifact],
) -> List[SurfaceArtifact]:
    """Generate stage-aware, trust-weighted composite risk surface."""
    surfaces = []

    # Determine phenology stage
    stage = consume_canonical_phenology_output(inp.veg_int)["resolved_crop_stage"]
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

    parent_ids = [s.surface_id for _, s in sorted(risk_surfaces.items())]
    parent_hashes = [
        hashlib.sha256(json.dumps(
            s.values, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")).hexdigest()
        for _, s in sorted(risk_surfaces.items())
    ]

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
            "derived_from_surface_ids": parent_ids,
            "derived_from_content_hashes": parent_hashes,
            "operator_model_version": "composite_risk_v4",
            "derivation_class": "model_assisted",
            "derivation_authority": "diagnostic",
            "source_reality": "provider_derived",
            "observed_support_ratio": min(source_coverage.values()) if source_coverage else 0.0,
            "uncertainty_propagation": "parent_support_and_reliability_surface",
            "production_usable": False,
            "real_provider_product": False,
            "diagnostic_only": True,
            "state_update_allowed": False,
            "prescription_driver_allowed": False,
            "state_update_authority": "none",
            "prescription_authority": "blocked_diagnostic_only",
        },
    ))

    return surfaces
