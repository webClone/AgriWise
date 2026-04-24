"""
Satellite RGB Engine — Input/Output Schemas.

Defines the strict data contracts for the Satellite RGB perception engine.
Provider-agnostic: accepts any georeferenced RGB plot image.
Real free-source policy: Sentinel-2 primary, Landsat fallback.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..common.contracts import (
    PerceptionEngineInput,
    PerceptionEngineOutput,
    PerceptionEngineFamily,
    PerceptionVariable,
    PerceptionArtifact,
    ZoneOutput,
)
from ..common.base_types import SatelliteProvider


# ============================================================================
# Engine Input
# ============================================================================

@dataclass
class SatelliteRGBEngineInput(PerceptionEngineInput):
    """
    Input for the Satellite RGB perception engine.
    
    Required fields for satellite RGB:
      - plot_polygon, bbox, crs_or_georef, ground_resolution_m
    If any are missing, the engine emits a QA failure output.
    
    Provider-agnostic: the engine processes any georeferenced RGB.
    Production backbone: Sentinel-2 primary, Landsat 8/9 fallback.
    """
    # Required for satellite RGB — engine will reject without these
    rgb_image_ref: str = ""               # URI or path to the RGB image
    plot_polygon: Optional[str] = None    # WKT or GeoJSON string
    crs_or_georef: str = ""               # e.g. "EPSG:4326"
    ground_resolution_m: float = 0.0      # pixel GSD in meters
    image_width: int = 0
    image_height: int = 0

    # Optional geometry hint (can also be computed from bbox)
    plot_area_ha: Optional[float] = None          # plot area in hectares

    # Source identification
    provider: SatelliteProvider = SatelliteProvider.SENTINEL2

    # Strongly recommended
    cloud_mask_ref: Optional[str] = None  # URI to cloud mask
    cloud_estimate: Optional[float] = None  # 0–1 plot-level cloud fraction
    haze_score: Optional[float] = None     # 0–1 haze estimate
    sun_angle: Optional[float] = None      # solar zenith angle degrees
    view_angle: Optional[float] = None     # view zenith angle degrees
    recentness_days: Optional[int] = None  # days since acquisition

    # Optional
    previous_rgb_ref: Optional[str] = None  # for temporal comparison (V2)
    sentinel2_ndvi_ref: Optional[str] = None  # matching S2 scene for cross-check
    plot_grid_ref: Optional[str] = None    # Layer 0 plot grid reference

    # Content hash for caching (MUST be computed from image bytes)
    image_content_hash: str = ""

    # Synthetic pixel data (for testing without actual image files)
    synthetic_pixels: Optional[Dict[str, Any]] = None

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate that mandatory fields are present.
        Returns (is_valid, list_of_errors).
        """
        errors = []
        if not self.plot_polygon:
            errors.append("plot_polygon is required for satellite RGB")
        if not self.bbox:
            errors.append("bbox is required for satellite RGB")
        if not self.crs_or_georef:
            errors.append("crs_or_georef is required for satellite RGB")
        if self.ground_resolution_m <= 0:
            errors.append("ground_resolution_m must be positive")
        if not self.rgb_image_ref and self.synthetic_pixels is None:
            errors.append("rgb_image_ref or synthetic_pixels required")
        return len(errors) == 0, errors


# ============================================================================
# Engine Output
# ============================================================================

@dataclass
class SatelliteRGBEngineOutput(PerceptionEngineOutput):
    """
    Output from the Satellite RGB perception engine.
    
    V1 outputs:
      - plot_visibility_score
      - vegetation_fraction + bare_soil_fraction
      - anomaly_fraction (rgb_anomaly_score)
      - coarse_phenology_stage
      - boundary_contamination_score
      - zone-level outputs (zone-capable from day one)
      - artifact references (vegetation mask, anomaly map, confidence map)
    """
    # Plot-level summary (always present)
    plot_visibility_score: float = 0.0
    plot_coverage_fraction: float = 0.0
    vegetation_fraction: float = 0.0
    bare_soil_fraction: float = 0.0
    anomaly_fraction: float = 0.0
    coarse_phenology_stage: float = 0.0
    boundary_contamination_score: float = 0.0
    canopy_density_class: str = "sparse"  # "bare", "sparse", "moderate", "dense"

    # Feasibility flags
    row_detection_feasible: bool = False  # Deferred to V1.5

    def __post_init__(self):
        self.engine_family = PerceptionEngineFamily.SATELLITE_RGB
