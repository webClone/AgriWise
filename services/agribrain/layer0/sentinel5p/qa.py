"""
Sentinel-5P QA Engine — SIF-specific quality assessment.

Key differences from Sentinel-2 QA:
  - Spatial resolution penalty ALWAYS applies (~7km vs ~10m)
  - Reliability ceiling capped at 0.45 (never trusted as strongly as S2)
  - Solar zenith angle matters more (SIF requires direct illumination)
  - Cloud contamination tolerance is lower (mixed pixel problem)
"""

from __future__ import annotations

from typing import List

from layer0.sentinel5p.schemas import (
    SIFQualityClass,
    Sentinel5PQAResult,
    SIFData,
)


def compute_qa(
    sif_data: SIFData,
    cloud_fraction: float = 0.0,
    solar_zenith: float = 0.0,
    spatial_resolution_km: float = 7.0,
    age_days: int = 0,
) -> Sentinel5PQAResult:
    """
    Compute QA verdict for a Sentinel-5P SIF observation.

    Hard rules:
        cloud_fraction > 0.30 → UNUSABLE (mixed pixel contamination)
        valid_fraction < 0.50 → UNUSABLE
        solar_zenith > 75° → UNUSABLE (no photosynthesis at low sun)
        sif_daily_mean is None → UNUSABLE
        age_days > 30 → STALE
    """
    flags: List[str] = []
    reason = ""

    # Basic data check
    if sif_data.sif_daily_mean is None:
        return Sentinel5PQAResult(
            usable=False,
            quality_class=SIFQualityClass.UNUSABLE,
            overall_score=0.0,
            reliability_weight=0.0,
            valid_fraction=0.0,
            reason="No SIF measurement available",
            flags=["NO_DATA"],
        )

    valid_frac = sif_data.valid_fraction

    # Hard rules
    if cloud_fraction > 0.30:
        flags.append("CLOUD_CONTAMINATION")
        reason = f"Cloud fraction {cloud_fraction:.2f} > 0.30"
    if valid_frac < 0.50:
        flags.append("LOW_VALID_FRACTION")
        if not reason:
            reason = f"Valid fraction {valid_frac:.2f} < 0.50"
    if solar_zenith > 75.0:
        flags.append("HIGH_SOLAR_ZENITH")
        if not reason:
            reason = f"Solar zenith {solar_zenith:.1f}° > 75° (insufficient illumination)"

    # Negative SIF is physically meaningless for cropland
    if sif_data.sif_daily_mean < -0.1:
        flags.append("NEGATIVE_SIF")
        if not reason:
            reason = f"SIF={sif_data.sif_daily_mean:.3f} < -0.1 (non-physical)"

    if age_days > 30:
        flags.append("STALE")

    # Determine quality class
    unusable = any(f in flags for f in [
        "CLOUD_CONTAMINATION", "LOW_VALID_FRACTION",
        "HIGH_SOLAR_ZENITH", "NEGATIVE_SIF",
    ])

    if unusable:
        quality_class = SIFQualityClass.UNUSABLE
        reliability = 0.0
        sigma_mult = 1.0
        overall = 0.0
        usable = False
        if not reason:
            reason = "Scene failed hard QA rules"
    elif cloud_fraction <= 0.10 and valid_frac >= 0.80 and age_days <= 5:
        quality_class = SIFQualityClass.EXCELLENT
        reliability = 0.45  # CEILING — never higher for S5P
        sigma_mult = 1.2
        overall = 0.80
        usable = True
        reason = "Excellent SIF scene (within resolution limits)"
    elif cloud_fraction <= 0.20 and valid_frac >= 0.60 and age_days <= 14:
        quality_class = SIFQualityClass.GOOD
        reliability = 0.38
        sigma_mult = 1.5
        overall = 0.60
        usable = True
        reason = "Good SIF scene"
    else:
        quality_class = SIFQualityClass.DEGRADED
        reliability = 0.25
        sigma_mult = 2.0
        overall = 0.35
        usable = True
        reason = "Degraded SIF quality — use with caution"

    # Spatial resolution penalty (always applied)
    resolution_penalty = min(0.3, spatial_resolution_km / 25.0)
    reliability = max(0.0, reliability - resolution_penalty * 0.1)

    # Age penalty
    if age_days > 30 and usable:
        reliability = min(reliability, 0.15)
        sigma_mult = max(sigma_mult, 3.0)
        flags.append("AGE_PENALTY")
    elif age_days > 14 and usable:
        reliability *= 0.8
        sigma_mult *= 1.3

    return Sentinel5PQAResult(
        usable=usable,
        quality_class=quality_class,
        overall_score=round(overall, 3),
        reliability_weight=round(max(0.0, min(0.45, reliability)), 4),
        sigma_multiplier=round(sigma_mult, 3),
        cloud_fraction=round(cloud_fraction, 4),
        valid_fraction=round(valid_frac, 4),
        spatial_resolution_penalty=round(resolution_penalty, 4),
        age_days=age_days,
        flags=flags,
        reason=reason,
    )
