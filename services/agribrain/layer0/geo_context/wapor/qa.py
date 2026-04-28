"""
WaPOR Quality Assessment.

Evaluates availability, resolution adequacy, and coverage.
"""

from __future__ import annotations

from typing import List, Optional

from layer0.geo_context.wapor.schemas import (
    WaPORContext,
    WaPORQAResult,
    WaPORQualityClass,
    WAPOR_LEVEL_RESOLUTIONS,
)


def evaluate_wapor_qa(
    wapor: Optional[WaPORContext] = None,
    plot_size_m: Optional[float] = None,
) -> WaPORQAResult:
    """Evaluate WaPOR data quality."""
    if wapor is None or not wapor.wapor_available:
        reason = "WAPOR_NOT_AVAILABLE"
        if wapor is not None and wapor.flags:
            reason = wapor.flags[0]
        return WaPORQAResult(
            quality_class=WaPORQualityClass.UNUSABLE,
            available=False,
            flags=[reason],
        )

    flags: List[str] = list(wapor.flags)
    quality = WaPORQualityClass.GOOD

    # Resolution adequacy (Revision 8)
    adequate = wapor.resolution_adequate_for_plot
    if not adequate:
        quality = WaPORQualityClass.DEGRADED

    # Level-specific rules
    if wapor.wapor_level == 1:
        if quality == WaPORQualityClass.GOOD:
            quality = WaPORQualityClass.DEGRADED
        flags.append("WAPOR_LEVEL1_NO_PLOT_LEVEL_CLAIMS")

    # ET completeness
    if wapor.actual_et_10d is None and wapor.reference_et_10d is None:
        quality = WaPORQualityClass.DEGRADED
        flags.append("WAPOR_NO_ET_DATA")

    return WaPORQAResult(
        quality_class=quality,
        available=True,
        level=wapor.wapor_level,
        resolution_m=wapor.wapor_resolution_m,
        coverage_fraction=1.0,  # assumed from pre-fetch
        resolution_adequate=adequate,
        flags=flags,
    )
