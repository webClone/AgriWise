"""
Drone Photogrammetry — Schemas.

All input/output contracts for the orthomosaic creation subsystem.
These contracts are stable: when real SfM libraries replace the V1
heuristic placeholders, no schema changes are required.

Design rules:
  - Provenance is MANDATORY in every OrthomosaicOutput.
  - Artifact refs are the PRIMARY handoff mechanism (not embedded arrays).
  - GCP fields are present but no fake GCP refinement in V1.
  - Optional external DEM hook for non-flat terrain.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import datetime


# ============================================================================
# Enums
# ============================================================================

class MosaicStatus(str, Enum):
    """Quality status of the final orthomosaic."""
    USABLE = "usable"
    DEGRADED = "degraded"       # Partially usable — sigma inflated
    UNUSABLE = "unusable"        # Should not be consumed by downstream


class SurfaceModelType(str, Enum):
    """Which surface model was used during orthorectification."""
    FLAT_GROUND = "flat_ground"
    EXTERNAL_DEM = "external_dem"
    DENSE_RECONSTRUCTION = "dense_reconstruction"  # V2 future


# ============================================================================
# Camera & Frame Metadata
# ============================================================================

@dataclass
class CameraIntrinsics:
    """Camera internal parameters for a single sensor model.

    Normalized from EXIF or drone capability profile.
    V1 uses simple pinhole model. V2 can add Brown-Conrady distortion.
    """
    focal_length_mm: float = 4.5
    sensor_width_mm: float = 6.3
    sensor_height_mm: float = 4.7
    image_width_px: int = 4000
    image_height_px: int = 3000
    principal_point_x: float = 0.5    # Normalized (0–1), center = 0.5
    principal_point_y: float = 0.5
    distortion_coeffs: List[float] = field(default_factory=list)
    rolling_shutter: bool = False
    rolling_shutter_readout_ms: float = 0.0

    def calculate_gsd_cm(self, altitude_m: float) -> float:
        """Ground Sample Distance in cm/pixel at given altitude."""
        gsd_mm = (altitude_m * 1000.0 * self.sensor_width_mm) / (
            self.focal_length_mm * self.image_width_px
        )
        return gsd_mm / 10.0

    def calculate_footprint_m(self, altitude_m: float) -> Tuple[float, float]:
        """Ground footprint (width_m, height_m) of a single image."""
        gsd_m = self.calculate_gsd_cm(altitude_m) / 100.0
        return (self.image_width_px * gsd_m, self.image_height_px * gsd_m)


@dataclass
class FrameGPS:
    """GPS/IMU metadata for a single frame."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0       # Altitude above ground (AGL)
    altitude_msl_m: float = 0.0   # Altitude above sea level
    heading_deg: float = 0.0      # Yaw / compass heading
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    horizontal_accuracy_m: float = 2.0   # GPS horizontal error (CEP)
    vertical_accuracy_m: float = 3.0
    rtk_fix: bool = False                # True if RTK-fixed solution


@dataclass
class FrameMetadata:
    """Per-frame metadata extracted during ingestion (Stage A)."""
    frame_id: str = ""
    frame_ref: str = ""              # URI/path to the raw frame
    sequence_index: int = 0          # Order in the mission capture sequence
    capture_timestamp: Optional[datetime.datetime] = None
    gps: FrameGPS = field(default_factory=FrameGPS)
    camera: CameraIntrinsics = field(default_factory=CameraIntrinsics)
    
    # EXIF extras
    iso: int = 0
    shutter_speed_s: float = 0.0
    aperture: float = 0.0
    white_balance: str = ""
    
    # Synthetic pixel data (for benchmarking only)
    synthetic_pixels: Optional[Dict[str, List[List[int]]]] = None

    # Flags set during ingestion
    duplicate_of: Optional[str] = None    # frame_id of the original if dup
    missing_gps: bool = False
    missing_exif: bool = False


@dataclass
class FrameQAResult:
    """Per-frame quality assessment (Stage B)."""
    frame_id: str = ""
    usable: bool = True
    rejection_reason: str = ""
    
    blur_score: float = 0.0          # 0 = sharp, 1 = severely blurred
    exposure_score: float = 1.0      # 0 = unusable, 1 = perfect exposure
    saturation_score: float = 0.0    # 0 = fine, 1 = blown out
    shadow_severity: float = 0.0     # 0 = flat light, 1 = deep shadows
    horizon_contamination: float = 0.0  # 0 = nadir, 1 = mostly sky
    motion_smear: float = 0.0        # 0 = no smear, 1 = severe
    rolling_shutter_risk: float = 0.0
    vegetation_content: float = 0.0  # Proxy for useful ag content
    coverage_usefulness: float = 1.0 # How much of the frame is useful
    
    # Overall quality weight for mosaic contribution
    quality_weight: float = 1.0      # 0 = should not contribute, 1 = ideal


# ============================================================================
# GCP (Ground Control Point) — schema support, no fake refinement in V1
# ============================================================================

@dataclass
class GroundControlPoint:
    """A surveyed ground control point.
    
    V1: accepted, validated, stored, surfaced in provenance.
    V1 does NOT use GCPs for alignment refinement.
    V2: real GCP-refined georegistration.
    """
    gcp_id: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0
    accuracy_m: float = 0.02      # Survey accuracy
    description: str = ""
    # Pixel coordinates in specific frames (for V2 alignment)
    frame_observations: Dict[str, Tuple[float, float]] = field(default_factory=dict)


# ============================================================================
# Reconstruction Intermediates
# ============================================================================

@dataclass
class TiePoint:
    """A matched feature point across frames."""
    point_id: str = ""
    # 3D estimated position (world coordinates)
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    # Which frames observe this point
    observations: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    # {frame_id: (pixel_x, pixel_y)}
    confidence: float = 1.0


@dataclass
class TiePointPair:
    """A correspondence between two frames."""
    frame_a_id: str = ""
    frame_b_id: str = ""
    match_count: int = 0
    inlier_count: int = 0
    confidence: float = 0.0


@dataclass
class CameraPose:
    """Refined camera position + orientation after bundle adjustment."""
    frame_id: str = ""
    # Position (world coordinates)
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0
    # Orientation (Euler angles)
    heading_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    # Uncertainty
    position_sigma_m: float = 2.0    # Position uncertainty
    orientation_sigma_deg: float = 1.0
    # Source
    source: str = "gps_only"  # "gps_only", "gps_tiepoint", "bundle_adjusted"


@dataclass
class OrthoTile:
    """A single orthorectified tile from one frame."""
    frame_id: str = ""
    # Tile bounds in map coordinates
    min_lat: float = 0.0
    max_lat: float = 0.0
    min_lon: float = 0.0
    max_lon: float = 0.0
    # Quality
    qa_weight: float = 1.0
    blur_score: float = 0.0
    # Pixel data ref (for real pipeline) or inline (for benchmark)
    tile_ref: str = ""
    synthetic_pixels: Optional[Dict[str, List[List[int]]]] = None
    # Usable mask (True = pixel is valid)
    usable_fraction: float = 1.0


# ============================================================================
# Input Contract
# ============================================================================

@dataclass
class DroneFrameSetInput:
    """Input contract for the photogrammetry subsystem.
    
    This is what the mission layer passes to photogrammetry after a
    Mapping Mode flight completes.
    """
    mission_id: str = ""
    plot_id: str = ""
    flight_mode: str = "mapping_mode"
    
    # Raw frames
    frame_refs: List[str] = field(default_factory=list)   # URIs to raw frames
    frame_count: int = 0
    
    # Camera
    camera: CameraIntrinsics = field(default_factory=CameraIntrinsics)
    
    # GPS/IMU per frame (parallel to frame_refs)
    frame_gps: List[FrameGPS] = field(default_factory=list)
    
    # Mission geometry
    plot_polygon: List[Tuple[float, float]] = field(default_factory=list)
    # [(lat, lon), ...] — vertices of the target polygon
    
    # Mission plan metadata
    target_gsd_cm: float = 2.0
    target_overlap_pct: float = 75.0
    flight_altitude_m: float = 50.0
    coverage_pattern: str = "boustrophedon"
    
    # Synthetic frames (for benchmarking only)
    synthetic_frames: Optional[List[Dict[str, List[List[int]]]]] = None
    
    # Optional: Ground Control Points (schema only, V1 stores but does not refine)
    gcps: List[GroundControlPoint] = field(default_factory=list)
    
    # Optional: External DEM
    dem_ref: Optional[str] = None            # URI to DEM raster
    dem_resolution_m: Optional[float] = None
    
    # Optional: RTK/PPK corrections
    rtk_base_station: Optional[Dict[str, Any]] = None
    ppk_corrections_ref: Optional[str] = None
    
    # Execution provenance (from drone_control when dispatch occurred)
    source_execution_id: Optional[str] = None    # Links to ExecutionReport
    vehicle_profile_id: Optional[str] = None     # Which drone flew
    capture_mode: str = "interval"                # "interval", "distance", "waypoint"
    planned_overlap: Optional[float] = None       # Planned overlap from dispatch
    flown_overlap_estimate: Optional[float] = None # Estimated from telemetry
    
    capture_timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


# ============================================================================
# Provenance — MANDATORY in every output
# ============================================================================

@dataclass
class PipelineProvenance:
    """Mandatory provenance record for every orthomosaic.
    
    This is non-negotiable: every OrthomosaicOutput must include complete
    provenance so downstream consumers can assess trustworthiness.
    """
    # Source frames
    source_frame_ids: List[str] = field(default_factory=list)
    total_frames_ingested: int = 0
    frames_rejected_qa: int = 0
    frames_used_in_mosaic: int = 0
    
    # QA summary
    mean_frame_blur: float = 0.0
    mean_frame_exposure: float = 1.0
    worst_frame_blur: float = 0.0
    
    # Alignment
    alignment_method: str = "gps_only"  # "gps_only", "gps_tiepoint", "bundle_adjusted"
    alignment_confidence: float = 0.0
    mean_reprojection_error_px: float = 0.0
    tiepoint_density: float = 0.0       # avg tie points per frame pair
    
    # Surface model
    surface_model_type: str = "flat_ground"
    dem_source: str = ""                # Empty if flat-ground
    
    # Mosaic
    seam_score: float = 0.0             # 0 = no seam artifacts, 1 = severe
    contribution_uniformity: float = 1.0  # How evenly frames contribute
    
    # Georeferencing
    georef_confidence: float = 0.0
    crs: str = "EPSG:4326"
    gcps_provided: int = 0
    gcps_used: int = 0                  # V1: always 0 (no fake refinement)
    
    # Processing
    pipeline_version: str = "heuristic_v1"
    processing_steps: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


# ============================================================================
# Output Contract
# ============================================================================

@dataclass
class OrthomosaicOutput:
    """Output contract for the photogrammetry subsystem.
    
    This is what drone_rgb Mapping Mode consumes. Artifact refs are the
    PRIMARY handoff mechanism — not embedded pixel arrays.
    
    Provenance is MANDATORY.
    """
    mission_id: str = ""
    plot_id: str = ""
    
    # --- Primary artifact refs (the main handoff) ---
    orthomosaic_ref: str = ""           # URI to the stitched orthomosaic
    orthomosaic_preview_ref: str = ""   # URI to a preview image
    metadata_ref: str = ""              # URI to metadata JSON
    quality_report_ref: str = ""        # URI to quality report JSON
    
    # --- Spatial metadata ---
    crs: str = "EPSG:4326"
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # (min_lon, min_lat, max_lon, max_lat)
    ground_resolution_cm: float = 0.0
    
    # --- Quality metrics ---
    coverage_completeness: float = 0.0    # Fraction of plot polygon covered
    outside_polygon_waste: float = 0.0    # Fraction of mosaic outside polygon
    georegistration_confidence: float = 0.0
    seam_artifact_score: float = 0.0      # 0 = clean, 1 = severe
    blur_score: float = 0.0              # 0 = sharp, 1 = blurred
    achieved_overlap: float = 0.0         # Mean pairwise overlap fraction
    holes_fraction: float = 0.0           # Fraction of plot with no data
    
    # --- Usability gate ---
    status: MosaicStatus = MosaicStatus.USABLE
    usable: bool = True
    qa_score: float = 1.0                 # 0–1 overall quality
    sigma_inflation: float = 1.0          # Multiplier for downstream uncertainty
    rejection_reason: str = ""
    
    # --- Optional high-value outputs ---
    dsm_ref: str = ""                     # Digital Surface Model
    footprint_union_ref: str = ""         # Union of all frame footprints
    contribution_map_ref: str = ""        # Which frame contributed where
    uncertainty_map_ref: str = ""         # Per-pixel uncertainty
    
    # --- MANDATORY provenance ---
    provenance: PipelineProvenance = field(default_factory=PipelineProvenance)
    
    # --- Inline pixel data (for benchmark/testing only) ---
    # In production, consumers use orthomosaic_ref. In benchmarks,
    # this allows passing pixel arrays directly to drone_rgb.
    _benchmark_pixels: Optional[Dict[str, List[List[int]]]] = None
