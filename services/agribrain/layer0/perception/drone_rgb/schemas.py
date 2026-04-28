"""
Drone RGB Engine Schemas.

Defines the input and output contracts for the dual-mode Drone perception engine.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import datetime

from layer0.perception.common.contracts import PerceptionEngineOutput


@dataclass
class RowBreak:
    """A detected gap/break within a single crop row."""
    row_index: int
    start_block: int       # Start position along the row (block units)
    end_block: int         # End position along the row (block units)
    gap_length_blocks: int # Length of the break in blocks

from drone_mission.schemas import FlightMode, MissionType

@dataclass
class DroneRGBInput:
    """Input payload for the Drone RGB Engine."""
    plot_id: str
    mission_id: str
    flight_mode: FlightMode
    mission_type: MissionType
    
    # MAPPING_MODE inputs
    orthomosaic_url: Optional[str] = None
    orthomosaic_metadata: Optional[Dict[str, Any]] = None # e.g., resolution, crs, bounds
    synthetic_ortho_pixels: Optional[Dict[str, List[List[int]]]] = None # For benchmarking
    
    # Photogrammetry subsystem output (primary handoff for mapping mode)
    # When provided, pixel data and metadata are extracted from this instead
    # of raw synthetic_ortho_pixels.
    orthomosaic_output: Optional[Any] = None  # OrthomosaicOutput (imported at runtime)
    
    # COMMAND_REVISIT_MODE inputs
    raw_frames_urls: Optional[List[str]] = None
    target_zone_id: Optional[str] = None
    commanded_altitude_m: Optional[float] = None
    synthetic_frame_pixels: Optional[List[Dict[str, List[List[int]]]]] = None # For benchmarking
    
    # Orchard override (optional — auto-estimated if not set)
    expected_tree_spacing_m: Optional[float] = None

    # Execution provenance (from drone_control when dispatch occurred)
    source_execution_id: Optional[str] = None    # Links to ExecutionReport
    driver_type: Optional[str] = None            # "mock", "dji_wayline", "mavsdk"
    mission_runtime_quality: Optional[float] = None  # 0-1, from execution report

    capture_timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class DroneStructuralMap:
    """A spatial output from the Mapping mode."""
    map_type: str # "canopy_cover", "row_continuity", "weed_pressure", "stand_gaps"
    resolution_cm: float
    data_grid: List[List[float]] # The actual 2D raster data
    # Coordinates for georegistration
    top_left_lat: float = 0.0
    top_left_lon: float = 0.0
    bottom_right_lat: float = 0.0
    bottom_right_lon: float = 0.0


@dataclass
class DroneRGBOutput(PerceptionEngineOutput):
    """Output payload from the Drone RGB Engine."""
    plot_id: str = ""
    mission_id: str = ""
    is_valid: bool = True
    qa_score: float = 1.0
    rejection_reason: Optional[str] = None
    
    # Structural outputs (Mapping Mode)
    row_azimuth_deg: Optional[float] = None
    row_spacing_cm: Optional[float] = None
    canopy_cover_fraction: Optional[float] = None
    bare_soil_fraction: Optional[float] = None
    weed_pressure_index: Optional[float] = None
    
    # V1.5 Row continuity outputs
    row_count: int = 0
    row_continuity_scores: List[float] = field(default_factory=list)
    row_breaks: List[RowBreak] = field(default_factory=list)
    stand_density_per_row: List[float] = field(default_factory=list)
    
    # V1.5 In-row vs inter-row weed separation
    in_row_weed_fraction: float = 0.0
    inter_row_weed_fraction: float = 0.0
    
    # V1.5 Orchard mode outputs
    tree_count: int = 0
    missing_tree_count: int = 0
    canopy_diameters_cm: List[float] = field(default_factory=list)
    canopy_uniformity_cv: float = 0.0
    
    # Spatial outputs
    spatial_maps: List[DroneStructuralMap] = field(default_factory=list)
    
    # Command Mode pass-through
    # The actual symptom extraction happens in FarmerPhotoEngine, 
    # but we track the routing status here.
    routed_to_farmer_photo: bool = False
    routed_frame_count: int = 0
    
    # V1.5B: Aggregated hotspot summary from command-mode multi-frame revisits
    hotspot_summary: Optional[Any] = None  # HotspotSummary (imported at runtime to avoid circular)
    
    # Photogrammetry provenance (when mosaic came from drone_photogrammetry)
    orthomosaic_provenance: Optional[Dict[str, Any]] = None

