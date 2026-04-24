"""
Shared base types for all perception engines.

Enums, feasibility gates, and reliability bundles used across
satellite_rgb, farmer_photo, drone, and ip_camera engines.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class GeometryScope(str, Enum):
    """Spatial scope of a perception output."""
    PLOT = "plot"        # whole-plot aggregate
    ZONE = "zone"        # management zone
    PIXEL = "pixel"      # per-pixel raster


class SatelliteProvider(str, Enum):
    """Supported satellite RGB providers (provider-agnostic engine)."""
    SENTINEL2 = "sentinel2"       # Primary free source
    LANDSAT8 = "landsat8"         # Fallback free source
    LANDSAT9 = "landsat9"         # Fallback free source
    SYNTHETIC = "synthetic"       # Test fixtures
    OTHER = "other"               # Any georeferenced RGB


@dataclass
class FeasibilityGate:
    """
    Gate that determines whether a specific feature can be extracted.
    
    Used to prevent emitting outputs when conditions are insufficient.
    Example: row detection requires ground_resolution_m < 2.0.
    """
    feature_name: str
    is_feasible: bool
    reason: str = ""
    min_resolution_m: Optional[float] = None
    min_coverage_fraction: Optional[float] = None
    min_pixel_count: Optional[int] = None

    @staticmethod
    def block(feature_name: str, reason: str) -> "FeasibilityGate":
        """Create a blocking gate."""
        return FeasibilityGate(
            feature_name=feature_name,
            is_feasible=False,
            reason=reason,
        )

    @staticmethod
    def allow(feature_name: str) -> "FeasibilityGate":
        """Create a passing gate."""
        return FeasibilityGate(
            feature_name=feature_name,
            is_feasible=True,
        )


@dataclass
class ReliabilityBundle:
    """
    Standardized reliability outputs from QA.
    
    Every perception engine must produce this bundle.
    It determines how strongly the Kalman filter trusts the observation.
    """
    qa_score: float = 1.0           # 0–1 overall quality
    reliability_weight: float = 1.0  # 0–1 Kalman trust weight
    sigma_inflation: float = 1.0     # Multiply base sigma by this
    flags: List[str] = field(default_factory=list)

    def is_usable(self, min_score: float = 0.1) -> bool:
        """Whether this observation is usable at all."""
        return self.qa_score >= min_score
