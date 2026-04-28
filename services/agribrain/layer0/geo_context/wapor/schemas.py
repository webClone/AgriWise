"""
WaPOR schemas.

FAO WaPOR water productivity context.
Resolution/level gating (Revision 8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class WaPORQualityClass(Enum):
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


# Resolution thresholds per level (Revision 8)
WAPOR_LEVEL_RESOLUTIONS = {
    1: 250.0,   # Level 1: Africa/Near East, 250 m
    2: 100.0,   # Level 2: Selected countries/basins, 100 m
    3: 30.0,    # Level 3: Selected areas, ~30 m
}


@dataclass
class WaPORContext:
    """WaPOR water productivity context for a plot."""
    wapor_available: bool = False
    wapor_level: int = 0                     # 1, 2, or 3
    wapor_resolution_m: float = 0.0

    # ET context (10-day or dekadal)
    actual_et_10d: Optional[float] = None     # mm/10d
    reference_et_10d: Optional[float] = None  # mm/10d
    et_ratio: Optional[float] = None          # actual / reference

    # Productivity
    biomass_trend: Optional[float] = None     # trend direction
    water_productivity_score: Optional[float] = None
    land_productivity_score: Optional[float] = None
    irrigation_performance_proxy: Optional[float] = None

    # Regional context
    green_blue_water_context: Optional[str] = None

    # Confidence (Revision 8)
    wapor_confidence: float = 0.0
    resolution_adequate_for_plot: bool = False

    # Flags
    flags: List[str] = field(default_factory=list)


@dataclass
class WaPORQAResult:
    """Quality assessment for WaPOR data."""
    quality_class: WaPORQualityClass = WaPORQualityClass.GOOD
    available: bool = False
    level: int = 0
    resolution_m: float = 0.0
    coverage_fraction: float = 0.0
    resolution_adequate: bool = False
    flags: List[str] = field(default_factory=list)
