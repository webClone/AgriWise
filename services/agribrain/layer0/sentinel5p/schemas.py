"""
Sentinel-5P SIF Schemas — Canonical data objects.

Pure Python dataclasses. No heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================================
# Enums
# ============================================================================

class SIFQualityClass(str, Enum):
    """SIF scene quality classification."""
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


# ============================================================================
# Scene Metadata
# ============================================================================

@dataclass
class Sentinel5PSceneMetadata:
    """
    Scene-level provenance for a TROPOMI SIF acquisition.

    Mandatory fields are validated at ingestion time.
    """
    scene_id: str = ""
    acquisition_datetime: Optional[datetime] = None
    provider: str = "TROPOMI"
    processing_level: str = "L2A"
    orbit_number: int = 0
    footprint_km2: float = 0.0      # Spatial footprint area
    spatial_resolution_km: float = 7.0  # Effective resolution
    cloud_fraction: float = 0.0
    solar_zenith_angle: float = 0.0
    sif_retrieval_method: str = "TROPOSIF"  # e.g., "TROPOSIF", "NIESIF"
    plot_geometry_hash: str = ""
    qa_version: str = "s5p_sif_qa_v1"

    def validate(self) -> List[str]:
        """Return list of missing mandatory fields."""
        errors = []
        if not self.scene_id:
            errors.append("scene_id")
        if self.acquisition_datetime is None:
            errors.append("acquisition_datetime")
        if not self.plot_geometry_hash:
            errors.append("plot_geometry_hash")
        return errors


# ============================================================================
# SIF Data
# ============================================================================

@dataclass
class SIFData:
    """
    SIF measurement for a plot footprint.

    Values are in mW/m²/sr/nm (standard TROPOMI SIF unit).
    Realistic range: 0–2.5 for healthy cropland.
    """
    sif_daily_mean: Optional[float] = None       # mW/m²/sr/nm
    sif_daily_std: Optional[float] = None
    sif_instantaneous: Optional[float] = None     # Single-pass value
    sif_relative: Optional[float] = None          # Normalized SIF (SIF / PAR)
    par_mean: Optional[float] = None              # Photosynthetically Active Radiation
    valid_pixel_count: int = 0
    total_pixel_count: int = 0

    @property
    def valid_fraction(self) -> float:
        if self.total_pixel_count == 0:
            return 0.0
        return self.valid_pixel_count / self.total_pixel_count


# ============================================================================
# QA Result
# ============================================================================

@dataclass
class Sentinel5PQAResult:
    """
    QA verdict for a Sentinel-5P SIF scene over a plot.

    The spatial resolution penalty is always active: TROPOMI's ~7km pixel
    means the plot signal is diluted by surrounding landscape.
    """
    usable: bool = True
    quality_class: SIFQualityClass = SIFQualityClass.GOOD
    overall_score: float = 0.6
    reliability_weight: float = 0.40   # Ceiling: 0.45 (coarse resolution)
    sigma_multiplier: float = 1.5

    cloud_fraction: float = 0.0
    valid_fraction: float = 1.0
    spatial_resolution_penalty: float = 0.3  # Always applied
    age_days: int = 0

    flags: List[str] = field(default_factory=list)
    reason: str = ""


# ============================================================================
# Scene Package (master output)
# ============================================================================

@dataclass
class Sentinel5PScenePackage:
    """
    The canonical output of the Sentinel-5P engine for one SIF scene × one plot.
    """
    plot_id: str = ""
    metadata: Sentinel5PSceneMetadata = field(default_factory=Sentinel5PSceneMetadata)
    sif_data: SIFData = field(default_factory=SIFData)
    qa: Sentinel5PQAResult = field(default_factory=Sentinel5PQAResult)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
