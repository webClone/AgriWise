"""
Land Cover Quality Assessment.

Evaluates WorldCover and Dynamic World quality:
coverage, consistency, unknown fractions, probability QA.
"""

from __future__ import annotations

from typing import List, Optional

from layer0.geo_context.landcover.schemas import (
    DynamicWorldContext,
    LandCoverQAResult,
    LandCoverQualityClass,
    WorldCoverContext,
)


def evaluate_landcover_qa(
    worldcover: Optional[WorldCoverContext] = None,
    dynamic_world: Optional[DynamicWorldContext] = None,
) -> LandCoverQAResult:
    """Evaluate land cover quality from available sources."""
    flags: List[str] = []
    quality = LandCoverQualityClass.GOOD
    valid_frac = 0.0
    unknown_frac = 0.0

    wc_available = worldcover is not None
    dw_available = dynamic_world is not None

    if not wc_available and not dw_available:
        return LandCoverQAResult(
            quality_class=LandCoverQualityClass.UNUSABLE,
            worldcover_available=False,
            dynamic_world_available=False,
            valid_fraction=0.0,
            unknown_fraction=1.0,
            flags=["NO_LANDCOVER_DATA"],
        )

    # WorldCover QA
    if wc_available:
        valid_frac = worldcover.landcover_valid_fraction
        unknown_frac = worldcover.unknown_fraction

        if worldcover.unknown_fraction > 0.1:
            flags.append("LANDCOVER_HIGH_UNKNOWN_FRACTION")
            quality = LandCoverQualityClass.DEGRADED

        if worldcover.landcover_valid_fraction < 0.5:
            quality = LandCoverQualityClass.UNUSABLE
            flags.append("LANDCOVER_LOW_VALID_FRACTION")

    # Dynamic World QA (Revision 6)
    if dw_available:
        if not dynamic_world.probability_sum_valid:
            flags.append("DYNAMIC_WORLD_PROBABILITY_SUM_INVALID")
            if quality == LandCoverQualityClass.GOOD:
                quality = LandCoverQualityClass.DEGRADED

        if dynamic_world.class_entropy > 0.8:
            flags.append("DYNAMIC_WORLD_HIGH_ENTROPY")

        if dynamic_world.recent_non_crop_alert:
            flags.append("DYNAMIC_WORLD_NON_CROP_ALERT")

    # Cross-source consistency
    if wc_available and dw_available:
        wc_crop = worldcover.cropland_fraction
        dw_crop = dynamic_world.crop_probability_mean
        if abs(wc_crop - dw_crop) > 0.3:
            flags.append("DYNAMIC_WORLD_DISAGREES_WITH_WORLD_COVER")

    return LandCoverQAResult(
        quality_class=quality,
        worldcover_available=wc_available,
        dynamic_world_available=dw_available,
        valid_fraction=round(valid_frac, 4),
        unknown_fraction=round(unknown_frac, 4),
        flags=flags,
    )
