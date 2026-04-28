"""
Sentinel-1 SAR V1 Schemas.

All dataclasses for SAR rasters, QA, summaries, metadata, and scene packages.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple


@dataclass
class SARRaster2D:
    """A 2D SAR raster aligned to PlotGrid."""

    values: List[List[Optional[float]]] = field(default_factory=list)
    valid_mask: List[List[int]] = field(default_factory=list)

    unit: Literal["linear_power", "db", "ratio", "score"] = "linear_power"
    polarization: Optional[Literal["VV", "VH"]] = None

    resolution_m: float = 10.0
    resampled_from_resolution_m: Optional[float] = None
    resampling_method: Optional[str] = None
    aligned_to_plot_grid: bool = False
    grid_shape: Tuple[int, int] = (0, 0)  # (height, width)
    crs: str = ""

    incidence_angle_ref: Optional[str] = None
    raster_ref: Optional[str] = None
    content_hash: Optional[str] = None

    def compute_content_hash(self) -> str:
        """Compute deterministic hash of values for raster refs."""
        raw = json.dumps(self.values, sort_keys=True, default=str)
        self.content_hash = hashlib.md5(raw.encode()).hexdigest()[:16]
        return self.content_hash


class SARQualityClass(Enum):
    """SAR scene quality classification."""
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


@dataclass
class Sentinel1QAResult:
    """SAR quality assessment result."""
    usable: bool = True
    quality_class: SARQualityClass = SARQualityClass.GOOD

    overall_score: float = 0.0
    reliability_weight: float = 0.80
    sigma_multiplier: float = 1.0

    valid_fraction: float = 0.0
    border_noise_fraction: float = 0.0
    low_signal_fraction: float = 0.0
    incidence_angle_mean: Optional[float] = None
    incidence_angle_std: Optional[float] = None
    incidence_angle_penalty: float = 0.0
    speckle_score: float = 1.0  # 1.0 = no speckle, 0.0 = extreme speckle
    orbit_consistency_score: float = 1.0

    flags: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class Sentinel1PlotSummary:
    """Plot-level SAR summary with alpha-weighted stats."""
    valid_fraction: float = 0.0

    vv_db_mean: Optional[float] = None
    vv_db_std: Optional[float] = None
    vv_db_p10: Optional[float] = None
    vv_db_p90: Optional[float] = None

    vh_db_mean: Optional[float] = None
    vh_db_std: Optional[float] = None
    vh_db_p10: Optional[float] = None
    vh_db_p90: Optional[float] = None

    vv_vh_ratio_mean: Optional[float] = None
    vv_minus_vh_db_mean: Optional[float] = None
    rvi_mean: Optional[float] = None
    cross_pol_fraction_mean: Optional[float] = None
    span_mean: Optional[float] = None

    surface_wetness_proxy_mean: Optional[float] = None
    structure_proxy_mean: Optional[float] = None
    flood_score: Optional[float] = None
    roughness_proxy: Optional[float] = None

    heterogeneity_score: float = 0.0
    anomaly_fraction: float = 0.0

    # QA fractions
    border_noise_fraction: float = 0.0
    low_signal_fraction: float = 0.0


@dataclass
class Sentinel1ZoneSummary:
    """Zone-level SAR summary with zone-specific QA."""
    zone_id: str = ""
    zone_source: str = "auto_quadrant_v1"
    zone_method: str = "grid_subdivision_2x2"
    zone_confidence: float = 0.4
    area_fraction: float = 0.0

    valid_fraction: float = 0.0
    border_noise_fraction: float = 0.0
    low_signal_fraction: float = 0.0
    reliability: float = 0.0
    sigma_multiplier: float = 1.0

    vv_db_mean: Optional[float] = None
    vh_db_mean: Optional[float] = None
    vv_vh_ratio_mean: Optional[float] = None
    rvi_mean: Optional[float] = None
    surface_wetness_proxy_mean: Optional[float] = None
    structure_proxy_mean: Optional[float] = None
    flood_score: Optional[float] = None

    anomaly_score: float = 0.0


@dataclass
class Sentinel1SceneMetadata:
    """Mandatory SAR scene provenance metadata."""
    scene_id: str = ""
    product_id: str = ""
    acquisition_datetime: Optional[datetime] = None
    provider: str = ""
    processing_level: Literal["GRD"] = "GRD"
    platform: str = ""  # S1A, S1C, etc.
    instrument_mode: Literal["IW", "EW", "SM"] = "IW"
    polarization: Literal["DV", "DH", "SV", "SH"] = "DV"
    orbit_direction: Literal["ASCENDING", "DESCENDING"] = "ASCENDING"
    relative_orbit: int = 0
    resolution_m: float = 10.0
    crs: str = ""
    grid_alignment_hash: str = ""
    plot_geometry_hash: str = ""
    sar_version: str = "s1sar_v1"
    qa_version: str = "s1qa_v1"
    feature_version: str = "s1feat_v1"

    def validate(self) -> List[str]:
        """Return list of missing mandatory fields."""
        errors = []
        if not self.scene_id:
            errors.append("scene_id")
        if not self.product_id:
            errors.append("product_id")
        if self.acquisition_datetime is None:
            errors.append("acquisition_datetime")
        if not self.provider:
            errors.append("provider")
        if not self.crs:
            errors.append("crs")
        if not self.plot_geometry_hash:
            errors.append("plot_geometry_hash")
        if not self.platform:
            errors.append("platform")
        if self.relative_orbit <= 0:
            errors.append("relative_orbit")
        return errors


@dataclass
class Sentinel1ScenePackage:
    """Complete SAR scene observation package."""
    plot_id: str = ""
    metadata: Sentinel1SceneMetadata = field(default_factory=Sentinel1SceneMetadata)
    rasters: Dict[str, SARRaster2D] = field(default_factory=dict)
    features: Dict[str, SARRaster2D] = field(default_factory=dict)
    qa: Sentinel1QAResult = field(default_factory=Sentinel1QAResult)
    plot_summary: Sentinel1PlotSummary = field(default_factory=Sentinel1PlotSummary)
    zone_summaries: List[Sentinel1ZoneSummary] = field(default_factory=list)
    packets: List[Dict[str, Any]] = field(default_factory=list)
    kalman_observations: List[Any] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

