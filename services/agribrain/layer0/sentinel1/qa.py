"""
Sentinel-1 SAR Quality Assessment.

Alpha-weighted QA based on signal plausibility, border noise, speckle,
incidence geometry, and orbit metadata. No cloud/shadow concepts.
"""

from __future__ import annotations

import math
from typing import List, Optional

from layer0.sentinel1.masks import Sentinel1MaskSet
from layer0.sentinel1.schemas import SARQualityClass, Sentinel1QAResult


# Reliability and sigma tables from CONTRACT.md
QA_TABLE = {
    SARQualityClass.EXCELLENT: {"reliability": 0.90, "sigma_mult": 1.0},
    SARQualityClass.GOOD:      {"reliability": 0.80, "sigma_mult": 1.2},
    SARQualityClass.DEGRADED:  {"reliability": 0.55, "sigma_mult": 1.8},
    SARQualityClass.UNUSABLE:  {"reliability": 0.0,  "sigma_mult": 999.0},
}


def _alpha_weighted_fraction(
    mask: List[List[int]],
    alpha: List[List[float]],
) -> float:
    """Compute alpha-weighted fraction: sum(alpha * mask) / sum(alpha)."""
    num = 0.0
    den = 0.0
    h = len(mask)
    for r in range(h):
        w = len(mask[r])
        for c in range(w):
            a = alpha[r][c] if r < len(alpha) and c < len(alpha[r]) else 0.0
            den += a
            if mask[r][c]:
                num += a
    if den < 1e-12:
        return 0.0
    return num / den


def _compute_speckle_score(
    vv_linear: List[List[Optional[float]]],
    valid_mask: List[List[int]],
    alpha: List[List[float]],
    window: int = 3,
) -> float:
    """
    Estimate speckle score from local coefficient of variation (CV).

    speckle_score = clamp(1 - median(local_cv), 0, 1)
    Higher score = less speckle = better quality.
    """
    h = len(vv_linear)
    w = len(vv_linear[0]) if vv_linear else 0
    half = window // 2

    cvs = []
    for r in range(h):
        for c in range(w):
            if not valid_mask[r][c]:
                continue
            a = alpha[r][c] if r < len(alpha) and c < len(alpha[r]) else 0.0
            if a <= 0:
                continue

            # Gather local window
            vals = []
            for dr in range(-half, half + 1):
                for dc in range(-half, half + 1):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w and valid_mask[nr][nc]:
                        v = vv_linear[nr][nc]
                        if v is not None and v > 0:
                            vals.append(v)

            if len(vals) >= 4:
                mean_v = sum(vals) / len(vals)
                if mean_v > 1e-12:
                    var = sum((x - mean_v) ** 2 for x in vals) / len(vals)
                    std_v = math.sqrt(var)
                    cv = std_v / abs(mean_v)
                    cvs.append(cv)

    if not cvs:
        return 0.5  # Unknown — neutral

    # Median CV
    cvs.sort()
    median_cv = cvs[len(cvs) // 2]

    # Speckle score: 1 - median_cv, clamped [0, 1]
    return max(0.0, min(1.0, 1.0 - median_cv))


def compute_sar_qa(
    mask_set: Sentinel1MaskSet,
    alpha_mask: List[List[float]],
    vv_linear: Optional[List[List[Optional[float]]]] = None,
    incidence_angle: Optional[List[List[Optional[float]]]] = None,
    age_days: Optional[float] = None,
    orbit_direction: Optional[str] = None,
    baseline_orbit_direction: Optional[str] = None,
) -> Sentinel1QAResult:
    """
    Compute SAR quality assessment from masks and metadata.

    Returns Sentinel1QAResult with quality class, reliability, and flags.
    """
    flags = []

    # Alpha-weighted fractions
    valid_fraction = _alpha_weighted_fraction(mask_set.valid_for_backscatter, alpha_mask)
    border_noise_fraction = _alpha_weighted_fraction(mask_set.border_noise_like, alpha_mask)
    low_signal_fraction = _alpha_weighted_fraction(mask_set.low_signal, alpha_mask)

    # Border noise is heuristic in V1
    if border_noise_fraction > 0:
        flags.append("BORDER_NOISE_HEURISTIC")
    if border_noise_fraction > 0.15:
        flags.append("BORDER_NOISE_HIGH")

    # Low signal
    if low_signal_fraction > 0.30:
        flags.append("LOW_SIGNAL_DOMINATED")

    # Speckle score
    speckle_score = 0.5
    if vv_linear is not None:
        speckle_score = _compute_speckle_score(
            vv_linear, mask_set.valid_for_backscatter, alpha_mask
        )
    if speckle_score < 0.4:
        flags.append("HIGH_SPECKLE")

    # Incidence angle analysis
    inc_mean = None
    inc_std = None
    inc_penalty = 0.0

    if incidence_angle is not None:
        vals = []
        h = len(incidence_angle)
        for r in range(h):
            for c in range(len(incidence_angle[r])):
                a = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
                if a > 0:
                    v = incidence_angle[r][c]
                    if v is not None:
                        vals.append(v)

        if vals:
            inc_mean = sum(vals) / len(vals)
            if len(vals) > 1:
                inc_std = math.sqrt(sum((v - inc_mean) ** 2 for v in vals) / len(vals))
            else:
                inc_std = 0.0

            # Penalty for extreme angles
            if inc_mean < 25.0 or inc_mean > 50.0:
                inc_penalty = 0.3
                flags.append("INCIDENCE_ANGLE_EXTREME")
            elif inc_mean < 30.0 or inc_mean > 45.0:
                inc_penalty = 0.1
                flags.append("INCIDENCE_ANGLE_MARGINAL")

            # Penalty for high variation over small plot
            if inc_std is not None and inc_std > 5.0:
                inc_penalty += 0.1
                flags.append("INCIDENCE_ANGLE_VARIABLE")
    else:
        flags.append("INCIDENCE_ANGLE_MISSING")
        inc_penalty = 0.15  # Sigma × 1.25 handled via sigma_mult

    # Orbit direction check
    orbit_score = 1.0
    if baseline_orbit_direction is not None and orbit_direction is not None:
        if orbit_direction != baseline_orbit_direction:
            flags.append("ORBIT_DIRECTION_CHANGED")
            orbit_score = 0.7

    # Stale scene
    if age_days is not None and age_days > 30:
        flags.append("STALE")

    # Quality class determination
    if valid_fraction < 0.45 or border_noise_fraction > 0.30 or low_signal_fraction > 0.50:
        quality_class = SARQualityClass.UNUSABLE
    elif valid_fraction >= 0.90 and low_signal_fraction <= 0.05 and border_noise_fraction <= 0.05:
        quality_class = SARQualityClass.EXCELLENT
    elif valid_fraction >= 0.75 and low_signal_fraction <= 0.15 and border_noise_fraction <= 0.15:
        quality_class = SARQualityClass.GOOD
    else:
        quality_class = SARQualityClass.DEGRADED

    # Missing incidence can never be EXCELLENT
    if "INCIDENCE_ANGLE_MISSING" in flags and quality_class == SARQualityClass.EXCELLENT:
        quality_class = SARQualityClass.GOOD

    # Lookup reliability/sigma
    table = QA_TABLE[quality_class]
    reliability = table["reliability"]
    sigma_mult = table["sigma_mult"]

    # Apply incidence penalty
    if inc_penalty > 0 and quality_class != SARQualityClass.UNUSABLE:
        reliability = max(0.0, reliability - inc_penalty)
        sigma_mult *= (1.0 + inc_penalty)

    # Apply incidence missing sigma inflation
    if "INCIDENCE_ANGLE_MISSING" in flags and quality_class != SARQualityClass.UNUSABLE:
        sigma_mult *= 1.25

    # Overall score
    overall = valid_fraction * 0.4 + speckle_score * 0.2 + (1.0 - border_noise_fraction) * 0.2 + orbit_score * 0.2

    usable = quality_class != SARQualityClass.UNUSABLE

    # Build reason
    if not usable:
        reasons = []
        if valid_fraction < 0.45:
            reasons.append("valid_fraction_low")
        if border_noise_fraction > 0.30:
            reasons.append("border_noise_severe")
        if low_signal_fraction > 0.50:
            reasons.append("low_signal_dominated")
        reason = "UNUSABLE: " + ", ".join(reasons)
    else:
        reason = f"{quality_class.value}: valid={valid_fraction:.2f}"

    return Sentinel1QAResult(
        usable=usable,
        quality_class=quality_class,
        overall_score=round(overall, 3),
        reliability_weight=round(reliability, 3),
        sigma_multiplier=round(sigma_mult, 3),
        valid_fraction=round(valid_fraction, 4),
        border_noise_fraction=round(border_noise_fraction, 4),
        low_signal_fraction=round(low_signal_fraction, 4),
        incidence_angle_mean=round(inc_mean, 2) if inc_mean is not None else None,
        incidence_angle_std=round(inc_std, 2) if inc_std is not None else None,
        incidence_angle_penalty=round(inc_penalty, 3),
        speckle_score=round(speckle_score, 3),
        orbit_consistency_score=round(orbit_score, 3),
        flags=flags,
        reason=reason,
    )
