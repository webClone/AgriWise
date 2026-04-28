"""
Sentinel-2 QA Engine — SCL-based quality assessment.

All fractions are alpha-weighted (computed over plot polygon, not bbox).
Determines scene usability, reliability weight, and sigma multiplier.
"""

from __future__ import annotations

from typing import List, Optional

from layer0.sentinel2.schemas import SceneQualityClass, Sentinel2QAResult
from layer0.sentinel2.masks import Sentinel2MaskSet


def compute_qa(
    mask_set: Sentinel2MaskSet,
    alpha_mask: List[List[float]],
    age_days: int = 0,
) -> Sentinel2QAResult:
    """
    Compute QA verdict from mask set and alpha-weighted plot coverage.

    All fractions are alpha-weighted:
        fraction = sum(alpha * condition) / sum(alpha)

    Hard rules:
        cloud_fraction > 0.50 → UNUSABLE
        valid_fraction < 0.40 → UNUSABLE
        shadow_fraction > 0.45 → UNUSABLE
        snow_fraction > 0.30 → UNUSABLE
        age_days > 45 → STALE, low reliability
        missing cloud data → reliability = 0.65, sigma *= 1.5
    """
    if not alpha_mask or not mask_set.valid_for_index:
        return Sentinel2QAResult(
            usable=False,
            quality_class=SceneQualityClass.UNUSABLE,
            overall_score=0.0,
            reliability_weight=0.0,
            sigma_multiplier=1.0,
            valid_fraction=0.0,
            reason="No alpha mask or mask set provided",
            flags=["NO_DATA"],
        )

    h = len(alpha_mask)
    w = len(alpha_mask[0]) if alpha_mask else 0

    # Alpha-weighted fraction computation
    total_alpha = 0.0
    valid_sum = 0.0
    cloud_sum = 0.0
    shadow_sum = 0.0
    snow_sum = 0.0
    water_sum = 0.0
    marginal_sum = 0.0
    vegetation_sum = 0.0
    bare_soil_sum = 0.0

    for r in range(h):
        for c in range(w):
            a = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
            if a <= 0:
                continue
            total_alpha += a

            if r < len(mask_set.valid_for_index) and c < len(mask_set.valid_for_index[r]):
                valid_sum += a * mask_set.valid_for_index[r][c]
            if r < len(mask_set.cloud_like) and c < len(mask_set.cloud_like[r]):
                cloud_sum += a * mask_set.cloud_like[r][c]
            if r < len(mask_set.shadow_like) and c < len(mask_set.shadow_like[r]):
                shadow_sum += a * mask_set.shadow_like[r][c]
            if r < len(mask_set.snow) and c < len(mask_set.snow[r]):
                snow_sum += a * mask_set.snow[r][c]
            if r < len(mask_set.water) and c < len(mask_set.water[r]):
                water_sum += a * mask_set.water[r][c]
            if r < len(mask_set.marginal) and c < len(mask_set.marginal[r]):
                marginal_sum += a * mask_set.marginal[r][c]
            if r < len(mask_set.valid_for_crop_inference) and c < len(mask_set.valid_for_crop_inference[r]):
                # Vegetation = valid_for_crop minus bare soil (SCL 4 vs 5)
                # For simplicity, use valid_for_crop as vegetation+bare combined
                vegetation_sum += a * mask_set.valid_for_crop_inference[r][c]

    if total_alpha < 1e-10:
        return Sentinel2QAResult(
            usable=False,
            quality_class=SceneQualityClass.UNUSABLE,
            overall_score=0.0,
            reliability_weight=0.0,
            valid_fraction=0.0,
            reason="Plot alpha mask has zero total weight",
            flags=["ZERO_ALPHA"],
        )

    valid_frac = valid_sum / total_alpha
    cloud_frac = cloud_sum / total_alpha
    shadow_frac = shadow_sum / total_alpha
    snow_frac = snow_sum / total_alpha
    water_frac = water_sum / total_alpha
    marginal_frac = marginal_sum / total_alpha

    # Compute haze score (marginal pixels contribute to atmospheric uncertainty)
    haze_score = min(1.0, marginal_frac * 2.0)

    # ---- Apply hard rules ----
    flags: list[str] = []
    reason = ""

    if cloud_frac > 0.50:
        flags.append("CLOUD_DOMINATED")
        reason = f"Cloud fraction {cloud_frac:.2f} > 0.50"
    if valid_frac < 0.40:
        flags.append("LOW_VALID_FRACTION")
        if not reason:
            reason = f"Valid fraction {valid_frac:.2f} < 0.40"
    if shadow_frac > 0.45:
        flags.append("SHADOW_DOMINATED")
        if not reason:
            reason = f"Shadow fraction {shadow_frac:.2f} > 0.45"
    if snow_frac > 0.30:
        flags.append("SNOW_DOMINATED")
        if not reason:
            reason = f"Snow fraction {snow_frac:.2f} > 0.30"

    # Check for missing cloud QA (all cloud values zero but low valid)
    cloud_qa_missing = (cloud_frac == 0.0 and shadow_frac == 0.0
                        and valid_frac < 0.90 and marginal_frac == 0.0)
    if cloud_qa_missing:
        flags.append("CLOUD_QA_MISSING")

    # Stale check
    if age_days > 45:
        flags.append("STALE")

    # ---- Determine quality class ----
    unusable = any(f in flags for f in [
        "CLOUD_DOMINATED", "LOW_VALID_FRACTION",
        "SHADOW_DOMINATED", "SNOW_DOMINATED",
    ])

    if unusable:
        quality_class = SceneQualityClass.UNUSABLE
        reliability = 0.0
        sigma_mult = 1.0
        overall = 0.0
        usable = False
        if not reason:
            reason = "Scene failed hard QA rules"
    elif valid_frac >= 0.85 and cloud_frac <= 0.10 and age_days <= 7:
        quality_class = SceneQualityClass.EXCELLENT
        reliability = 0.92
        sigma_mult = 1.0
        overall = 0.95
        usable = True
        reason = "Excellent quality scene"
    elif valid_frac >= 0.70 and cloud_frac <= 0.20 and age_days <= 14:
        quality_class = SceneQualityClass.GOOD
        reliability = 0.80
        sigma_mult = 1.15
        overall = 0.75
        usable = True
        reason = "Good quality scene"
    else:
        quality_class = SceneQualityClass.DEGRADED
        reliability = 0.55
        sigma_mult = 1.8
        overall = 0.45
        usable = True
        reason = "Degraded quality — use with caution"

    # Apply age penalty
    if age_days > 45 and usable:
        reliability = min(reliability, 0.35)
        sigma_mult = max(sigma_mult, 2.5)
        flags.append("AGE_PENALTY")
    elif age_days > 30 and usable:
        reliability *= 0.8
        sigma_mult *= 1.3

    # Apply cloud QA missing penalty
    if cloud_qa_missing and usable:
        reliability = min(reliability, 0.65)
        sigma_mult = max(sigma_mult, 1.5)

    # Apply marginal pixel penalty
    if marginal_frac > 0.15 and usable:
        reliability *= 0.9
        sigma_mult *= 1.1
        flags.append("MARGINAL_PIXELS")

    return Sentinel2QAResult(
        usable=usable,
        quality_class=quality_class,
        overall_score=round(overall, 3),
        reliability_weight=round(max(0.0, min(1.0, reliability)), 3),
        sigma_multiplier=round(sigma_mult, 3),
        valid_fraction=round(valid_frac, 4),
        cloud_fraction=round(cloud_frac, 4),
        shadow_fraction=round(shadow_frac, 4),
        snow_fraction=round(snow_frac, 4),
        water_fraction=round(water_frac, 4),
        haze_score=round(haze_score, 4),
        boundary_contamination_score=0.0,  # Computed separately in plot_extract
        flags=flags,
        reason=reason,
    )
