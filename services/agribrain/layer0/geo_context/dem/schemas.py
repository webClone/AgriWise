"""
DEM / Terrain schemas.

Copernicus DEM GLO-30 primary, GLO-90 fallback.
All terrain derivatives are labeled as proxies where appropriate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

class DEMQualityClass(Enum):
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


# ---------------------------------------------------------------------------
# DEM QA (Revision 4 — coarse/pixel-count flags)
# ---------------------------------------------------------------------------

# Thresholds for terrain derivative confidence
MIN_PIXELS_GOOD = 16
MIN_PIXELS_TERRAIN_DERIVATIVES = 9


@dataclass
class DEMQAResult:
    """Quality assessment for DEM input."""
    quality_class: DEMQualityClass = DEMQualityClass.GOOD
    valid_pixel_count: int = 0
    total_pixel_count: int = 0
    valid_fraction: float = 0.0
    nan_fraction: float = 0.0
    resolution_m: float = 0.0
    terrain_derivatives_reliable: bool = True
    placement_confidence_factor: float = 1.0   # reduced when coarse
    flags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DEM Context (Revision 3 — proxy labels)
# ---------------------------------------------------------------------------

@dataclass
class DEMContext:
    """All derived terrain features from DEM.

    Fields ending in '_proxy' are estimates from local DEM patches,
    NOT results of full hydrological routing models.
    """
    # Elevation statistics
    elevation_mean: Optional[float] = None
    elevation_min: Optional[float] = None
    elevation_max: Optional[float] = None
    elevation_std: Optional[float] = None

    # Slope statistics (degrees)
    slope_mean: Optional[float] = None
    slope_p90: Optional[float] = None
    slope_max: Optional[float] = None

    # Aspect (degrees, 0=N, 90=E, 180=S, 270=W)
    aspect_dominant: Optional[float] = None
    aspect_distribution: Dict[str, float] = field(default_factory=dict)
    # e.g. {"N": 0.3, "NE": 0.1, "E": 0.05, ...}

    # Curvature and wetness proxies (Revision 3 labeling)
    curvature_proxy: Optional[float] = None
    flow_accumulation_proxy: Optional[float] = None
    topographic_wetness_proxy: Optional[float] = None

    # Fraction features
    low_spot_fraction: float = 0.0
    ridge_fraction: float = 0.0

    # Risk scores [0, 1]
    runoff_risk_score: float = 0.0
    erosion_risk_score: float = 0.0
    cold_air_pooling_risk: float = 0.0
    irrigation_uniformity_risk: float = 0.0

    # QA
    qa: DEMQAResult = field(default_factory=DEMQAResult)

    # Source metadata
    source: str = "copernicus_dem"        # glo30 | glo90
    resolution_m: float = 30.0
