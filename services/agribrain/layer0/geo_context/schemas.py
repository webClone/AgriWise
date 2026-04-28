"""
Geo Context Engine V1 — Top-level schemas.

Defines GeoContextPackage, PlotValidityAssessment, SensorPlacementGuidance,
SatelliteTrustModifiers, RasterInput, and supporting types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Raster alignment contract (Revision 1)
# ---------------------------------------------------------------------------

MAX_RASTER_DIM_V1 = 512  # Max 512x512 pixels in V1


@dataclass
class RasterInput:
    """Validated raster input with alignment contract.

    Every raster input must carry shape, CRS, resolution, alignment flag,
    and valid mask. Alpha mask is optional for boundary weighting.
    """
    data: np.ndarray                          # 2D array of values
    valid_mask: np.ndarray                    # bool 2D, same shape as data
    resolution_m: float                       # > 0
    crs: str = "EPSG:4326"                    # coordinate reference system
    aligned_to_plot_grid: bool = True         # must be True
    alpha_mask: Optional[np.ndarray] = None   # float [0,1] 2D, same shape
    raster_ref: Optional[str] = None          # provenance reference
    content_hash: Optional[str] = None        # integrity hash
    transform_hash: Optional[str] = None      # spatial transform hash
    plot_grid_hash: Optional[str] = None      # grid definition hash

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise ValueError(f"Raster data must be 2D, got {self.data.ndim}D")
        if self.valid_mask.shape != self.data.shape:
            raise ValueError(
                f"valid_mask shape {self.valid_mask.shape} != data shape {self.data.shape}"
            )
        if self.alpha_mask is not None and self.alpha_mask.shape != self.data.shape:
            raise ValueError(
                f"alpha_mask shape {self.alpha_mask.shape} != data shape {self.data.shape}"
            )
        if self.resolution_m <= 0:
            raise ValueError(f"resolution_m must be > 0, got {self.resolution_m}")
        if not self.aligned_to_plot_grid:
            raise ValueError("Raster must be aligned to plot grid")
        if self.data.shape[0] > MAX_RASTER_DIM_V1 or self.data.shape[1] > MAX_RASTER_DIM_V1:
            raise ValueError(
                f"Raster {self.data.shape} exceeds V1 max {MAX_RASTER_DIM_V1}x{MAX_RASTER_DIM_V1}"
            )


# ---------------------------------------------------------------------------
# Alpha-weighted summary helper (Revision 2)
# ---------------------------------------------------------------------------

def alpha_weighted_mean(
    values: np.ndarray,
    valid_mask: np.ndarray,
    alpha_mask: Optional[np.ndarray] = None,
) -> Optional[float]:
    """Compute alpha-weighted mean: sum(alpha * valid * value) / sum(alpha * valid).

    Returns None if no valid pixels.
    """
    mask = valid_mask.astype(bool)
    if alpha_mask is not None:
        weights = alpha_mask * mask.astype(float)
    else:
        weights = mask.astype(float)

    total_weight = weights.sum()
    if total_weight == 0:
        return None

    return float(np.sum(weights * values) / total_weight)


def alpha_weighted_std(
    values: np.ndarray,
    valid_mask: np.ndarray,
    alpha_mask: Optional[np.ndarray] = None,
) -> Optional[float]:
    """Compute alpha-weighted standard deviation.

    Returns None if no valid pixels.
    """
    mean = alpha_weighted_mean(values, valid_mask, alpha_mask)
    if mean is None:
        return None

    mask = valid_mask.astype(bool)
    if alpha_mask is not None:
        weights = alpha_mask * mask.astype(float)
    else:
        weights = mask.astype(float)

    total_weight = weights.sum()
    if total_weight == 0:
        return None

    variance = float(np.sum(weights * (values - mean) ** 2) / total_weight)
    return float(np.sqrt(variance))


# ---------------------------------------------------------------------------
# Quality classes
# ---------------------------------------------------------------------------

class GeoContextQualityClass(Enum):
    """Overall geo context quality."""
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


# ---------------------------------------------------------------------------
# Plot Validity Assessment
# ---------------------------------------------------------------------------

@dataclass
class PlotValidityAssessment:
    """Assessment of whether a plot is valid agricultural land."""
    cropland_confidence: float = 0.0
    non_ag_contamination_score: float = 0.0
    boundary_mismatch_score: float = 0.0
    water_contamination_score: float = 0.0
    builtup_contamination_score: float = 0.0
    tree_edge_contamination_score: float = 0.0
    flags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sensor Placement Guidance (Revision 10 — confidence + scope)
# ---------------------------------------------------------------------------

@dataclass
class SensorZoneRecommendation:
    """A single sensor placement recommendation."""
    zone_id: str = ""
    sensor_type: str = "soil_moisture"
    placement_confidence: float = 0.0          # [0, 1]
    representativeness_scope: str = "zone"     # plot | zone | point
    recommended_depths_cm: List[int] = field(default_factory=lambda: [15, 45])
    reason_codes: List[str] = field(default_factory=list)
    source_drivers: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class SensorPlacementGuidance:
    """Full sensor placement guidance for a plot."""
    recommended_zones: List[SensorZoneRecommendation] = field(default_factory=list)
    avoid_zones: List[SensorZoneRecommendation] = field(default_factory=list)
    wet_zone_candidates: List[SensorZoneRecommendation] = field(default_factory=list)
    dry_zone_candidates: List[SensorZoneRecommendation] = field(default_factory=list)
    representative_zone_candidates: List[SensorZoneRecommendation] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Satellite Trust Modifiers (Revision 9 — scope)
# ---------------------------------------------------------------------------

@dataclass
class SatelliteTrustModifiers:
    """Modifiers for satellite source reliability based on geo context."""
    sentinel2_boundary_risk: float = 0.0       # edge scope
    sentinel1_terrain_risk: float = 0.0        # zone scope
    sat_rgb_landcover_risk: float = 0.0        # plot scope
    dynamic_world_disagreement: float = 0.0    # plot scope

    sentinel2_boundary_risk_scope: str = "edge"
    sentinel1_terrain_risk_scope: str = "zone"
    sat_rgb_landcover_risk_scope: str = "plot"
    dynamic_world_disagreement_scope: str = "plot"

    flags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main output: GeoContextPackage
# ---------------------------------------------------------------------------

@dataclass
class GeoContextPackage:
    """Top-level output of the Geo Context Engine V1."""
    plot_id: str = ""
    timestamp: Optional[str] = None

    # Sub-contexts (any can be None on provider failure)
    dem_context: Optional[Any] = None           # DEMContext from dem/schemas
    landcover_context: Optional[Any] = None     # LandCoverContext from landcover/schemas
    wapor_context: Optional[Any] = None         # WaPORContext from wapor/schemas

    # Derived outputs
    sensor_placement: SensorPlacementGuidance = field(default_factory=SensorPlacementGuidance)
    plot_validity: PlotValidityAssessment = field(default_factory=PlotValidityAssessment)
    satellite_trust_modifiers: SatelliteTrustModifiers = field(default_factory=SatelliteTrustModifiers)

    # Packets and diagnostics
    packets: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
