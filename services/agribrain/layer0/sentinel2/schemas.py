"""
Sentinel-2 V1 Schemas — Canonical data objects for the optical engine.

All downstream modules import from here. Pure Python dataclasses,
no heavy dependencies (numpy/rasterio) at the schema level.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple


# ============================================================================
# Raster primitive
# ============================================================================

@dataclass
class Raster2D:
    """
    Lightweight 2D raster with valid mask and alignment metadata.

    values[row][col] = float or None (no-data).
    valid_mask[row][col] = 1 (valid) or 0 (invalid/no-data).
    """

    values: List[List[Optional[float]]] = field(default_factory=list)
    valid_mask: List[List[int]] = field(default_factory=list)

    # Resolution and alignment
    resolution_m: float = 10.0
    resampled_from_resolution_m: Optional[float] = None
    resampling_method: Optional[str] = None  # "nearest", "bilinear", etc.
    aligned_to_plot_grid: bool = False
    grid_shape: Tuple[int, int] = (0, 0)  # (height, width)
    crs: str = ""
    value_scale: Literal["reflectance_0_1", "scaled_0_10000", "byte_0_255"] = "reflectance_0_1"
    is_reflectance_scaled: bool = True  # Must be True for byte_0_255 to allow scientific indices

    # Reference / caching support
    raster_ref: Optional[str] = None
    content_hash: Optional[str] = None

    def __post_init__(self):
        if self.values and not self.grid_shape[0]:
            self.grid_shape = (len(self.values), len(self.values[0]) if self.values else 0)
        if self.values and not self.valid_mask:
            self.valid_mask = [
                [1 if v is not None else 0 for v in row]
                for row in self.values
            ]

    @property
    def height(self) -> int:
        return self.grid_shape[0]

    @property
    def width(self) -> int:
        return self.grid_shape[1]

    def compute_content_hash(self) -> str:
        """Deterministic hash of raster content for caching."""
        raw = json.dumps(self.values, default=str).encode()
        self.content_hash = hashlib.sha256(raw).hexdigest()[:16]
        return self.content_hash


# ============================================================================
# Enums
# ============================================================================

class SceneQualityClass(str, Enum):
    """Scene quality classification from QA engine."""
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


# ============================================================================
# QA Result
# ============================================================================

@dataclass
class Sentinel2QAResult:
    """
    QA verdict for a Sentinel-2 scene over a specific plot.

    Determines whether the scene is usable and with what reliability.
    """
    usable: bool = True
    quality_class: SceneQualityClass = SceneQualityClass.GOOD
    overall_score: float = 0.8
    reliability_weight: float = 0.8
    sigma_multiplier: float = 1.0

    # Alpha-weighted fractions (computed over plot polygon, not bbox)
    valid_fraction: float = 1.0
    cloud_fraction: float = 0.0
    shadow_fraction: float = 0.0
    snow_fraction: float = 0.0
    water_fraction: float = 0.0
    haze_score: float = 0.0
    boundary_contamination_score: float = 0.0

    flags: List[str] = field(default_factory=list)
    reason: str = ""


# ============================================================================
# Plot Summary
# ============================================================================

@dataclass
class Sentinel2PlotSummary:
    """
    Alpha-weighted plot-level statistics for all V1 indices.
    Every mean/std/percentile is computed using PlotGrid alpha weights.
    """
    # Coverage
    valid_fraction: float = 0.0
    cloud_fraction: float = 0.0
    shadow_fraction: float = 0.0
    snow_fraction: float = 0.0
    water_fraction: float = 0.0
    vegetation_fraction_scl: float = 0.0
    bare_soil_fraction_scl: float = 0.0

    # Index statistics
    ndvi_mean: Optional[float] = None
    ndvi_std: Optional[float] = None
    ndvi_p10: Optional[float] = None
    ndvi_p90: Optional[float] = None

    evi_mean: Optional[float] = None
    evi_std: Optional[float] = None

    ndmi_mean: Optional[float] = None
    ndmi_std: Optional[float] = None

    ndre_mean: Optional[float] = None
    ndre_std: Optional[float] = None

    bsi_mean: Optional[float] = None
    bsi_std: Optional[float] = None

    # Spatial quality
    heterogeneity_score: float = 0.0
    anomaly_fraction: float = 0.0
    boundary_contamination_score: float = 0.0
    edge_valid_fraction: float = 0.0
    interior_valid_fraction: float = 0.0
    neighbor_green_pressure: float = 0.0


# ============================================================================
# Zone Summary
# ============================================================================

@dataclass
class Sentinel2ZoneSummary:
    """Per-zone statistics with separate reliability and confidence."""
    zone_id: str = ""
    area_fraction: float = 0.0
    valid_fraction: float = 0.0
    cloud_fraction: float = 0.0
    shadow_fraction: float = 0.0

    ndvi_mean: Optional[float] = None
    ndvi_std: Optional[float] = None
    ndmi_mean: Optional[float] = None
    ndre_mean: Optional[float] = None
    bsi_mean: Optional[float] = None
    vegetation_fraction: Optional[float] = None
    bare_soil_fraction: Optional[float] = None

    anomaly_score: float = 0.0
    reliability: float = 0.0
    sigma_multiplier: float = 1.0

    # Zone provenance
    zone_source: str = "auto_quadrant_v1"
    zone_method: str = "grid_subdivision_2x2"
    zone_confidence: float = 0.4


# ============================================================================
# Scene Metadata (mandatory provenance)
# ============================================================================

@dataclass
class Sentinel2SceneMetadata:
    """
    Scene-level provenance. ALL fields are mandatory —
    validation fails if any critical field is missing.
    """
    scene_id: str = ""
    product_id: str = ""
    acquisition_datetime: Optional[datetime] = None
    provider: str = ""
    processing_level: str = "L2A"
    processing_baseline: str = ""
    orbit_direction: str = ""
    relative_orbit: int = 0
    cloud_cover_scene: float = 0.0
    sun_zenith: float = 0.0
    sun_azimuth: float = 0.0
    view_zenith: float = 0.0
    view_azimuth: float = 0.0
    crs: str = ""
    resolution_m: float = 10.0
    bbox: List[float] = field(default_factory=list)
    band_list: List[str] = field(default_factory=list)
    scale: str = "reflectance_0_1"
    grid_alignment_hash: str = ""
    qa_version: str = "s2qa_v1"
    index_version: str = "s2idx_v1"
    plot_geometry_hash: str = ""

    def validate(self) -> List[str]:
        """Return list of missing mandatory fields."""
        errors = []
        if not self.scene_id:
            errors.append("scene_id")
        if self.acquisition_datetime is None:
            errors.append("acquisition_datetime")
        if not self.provider:
            errors.append("provider")
        if not self.crs:
            errors.append("crs")
        if not self.band_list:
            errors.append("band_list")
        if not self.plot_geometry_hash:
            errors.append("plot_geometry_hash")
        return errors


# ============================================================================
# Scene Package (master output)
# ============================================================================

@dataclass
class Sentinel2ScenePackage:
    """
    The canonical output of the Sentinel-2 engine for one scene × one plot.
    Every downstream consumer receives this object.
    """
    plot_id: str = ""
    metadata: Sentinel2SceneMetadata = field(default_factory=Sentinel2SceneMetadata)

    # Raster data (references or inline for small plots)
    bands: Dict[str, Raster2D] = field(default_factory=dict)
    indices: Dict[str, Raster2D] = field(default_factory=dict)
    masks: Dict[str, Raster2D] = field(default_factory=dict)

    # QA and summaries
    qa: Sentinel2QAResult = field(default_factory=Sentinel2QAResult)
    plot_summary: Sentinel2PlotSummary = field(default_factory=Sentinel2PlotSummary)
    zone_summaries: List[Sentinel2ZoneSummary] = field(default_factory=list)

    # Diagnostics
    diagnostics: Dict[str, Any] = field(default_factory=dict)
