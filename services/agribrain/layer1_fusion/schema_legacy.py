
"""
Layer 1 Schema Definition.
Defines the core data structures for Input (Evidence) and Output (FieldTensor).
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from .raster_backend import GridSpec # Import shared contract

class EvidenceSourceType(str, Enum):
    SATELLITE_OPTICAL = "satellite_optical"
    SATELLITE_SAR = "satellite_sar"
    WEATHER = "weather"
    SOIL = "soil"
    SENSOR = "sensor"
    USER_EVENT = "user_event"
    USER_OBSERVATION = "user_observation"
    WEATHER_FORECAST = "weather_forecast"

class ValidationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    FLAGGED = "flagged"
    REJECTED = "rejected"

@dataclass
class EvidenceItem:
    """
    Core Input Unit. Everything entering Layer 1 is 'Evidence'.
    """
    id: str
    source_type: EvidenceSourceType
    timestamp: datetime
    location_scope: str # "plot", "point", "raster"
    payload: Dict[str, Any] # Raw data content
    
    # Metadata
    sensor_id: Optional[str] = None
    confidence_score: float = 1.0 # 0.0 - 1.0 (Initial trust)
    
    # Validation State
    status: ValidationStatus = ValidationStatus.PENDING
    flags: List[str] = field(default_factory=list) # e.g. ["cloudy", "outlier"]
    reason_codes: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.id,
            "source_type": self.source_type,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "flags": self.flags,
            "confidence": self.confidence_score,
            "payload_summary": list(self.payload.keys()) # Don't dump full payload in logs
        }

class FieldTensorChannels(str, Enum):
    # --- 1. Optical (Sentinel-2) ---
    NDVI = "ndvi"
    NDVI_UNC = "ndvi_uncertainty"
    EVI = "evi"
    NDMI = "ndmi"
    NDWI = "ndwi"
    
    # --- 2. SAR (Sentinel-1) ---
    VV = "vv"
    VH = "vh"
    SAR_RATIO = "vv_vh_ratio"
    
    # --- 3. Weather (Open-Meteo) ---
    PRECIPITATION = "precipitation"
    TEMP_MAX = "temp_max"
    TEMP_MIN = "temp_min"
    ET0 = "et0"
    GDD = "gdd" # Growing Degree Days
    
    # --- 4. Soil (SoilGrids - Static) ---
    SOIL_CLAY = "soil_clay"
    SOIL_SAND = "soil_sand"
    SOIL_PH = "soil_ph"
    SOIL_OC = "soil_org_carbon"
    
    # --- 5. Quality & Masks ---
    CLOUD_MASK = "cloud_mask" # 0=Clear, 1=Cloud
    VALIDITY_MASK = "validity_mask" # 0=Valid, 1=Invalid

@dataclass
class FieldTensor:
    """
    The Single Source of Truth for a Plot.
    Production Spec v2: Spatio-Temporal 4D Tensor.
    """
    plot_id: str
    run_id: str
    version: str = "2.0.0"
    
    # Unified Grid Definition
    grid_spec: GridSpec = field(default_factory=lambda: GridSpec(
        crs="EPSG:4326", 
        transform=(0,0,0,0,0,0), 
        width=10, 
        height=10, 
        bounds=(0,0,0,0), 
        resolution=10.0
    ))
    
    # Unified Time Axis
    time_index: List[str] = field(default_factory=list) # ISO Dates [T]
    
    # Channel Definition
    channels: List[FieldTensorChannels] = field(default_factory=lambda: [
        FieldTensorChannels.NDVI,
        FieldTensorChannels.NDVI_UNC,
        FieldTensorChannels.VV,
        FieldTensorChannels.VH,
        FieldTensorChannels.PRECIPITATION
    ])
    
    # --- THE TENSOR ---
    # Shape: [Time, Height, Width, Channels]
    # Type: List[List[List[List[float]]]] (Pure Python Fallback)
    #       or np.ndarray (if available)
    data: Any = field(default_factory=list)
    
    # --- SPATIAL EXTENSIONS ---
    grid: Dict[str, Any] = field(default_factory=dict) # cells: id, centroid, area, mask
    maps: Dict[str, Any] = field(default_factory=dict) # variable -> raster_ref/array
    zones: Dict[str, Any] = field(default_factory=dict) # zone_id -> polygon/mask + area_pct + label
    
    # Metadata & Provenance
    provenance: Dict[str, Any] = field(default_factory=dict) # Lineage graph
    static: Dict[str, Any] = field(default_factory=dict) # Unchanging field props

    # Compatibility View (Layer 1 Legacy)
    plot_timeseries: List[Dict] = field(default_factory=list)
    zone_stats: Dict[str, Any] = field(default_factory=dict) # variable -> {zone_id -> timeseries}
    
    # Forward-Looking Models
    forecast_7d: List[Dict] = field(default_factory=list)
    
    # ==========================================================================
    # LAYER 0 OUTPUTS — Daily State Estimation
    # ==========================================================================
    
    # Per-zone daily estimated state vector
    # Structure: { "zone_a": [ {day: "2024-01-01", lai: 1.2, sm_0_10: 0.3, ...}, ... ] }
    daily_state: Dict[str, List[Dict]] = field(default_factory=dict)
    
    # Per-zone daily uncertainty (sigma per variable per day)
    # Structure: { "zone_a": [ {day: "2024-01-01", lai: 0.15, sm_0_10: 0.05, ...}, ... ] }
    state_uncertainty: Dict[str, List[Dict]] = field(default_factory=dict)
    
    # Source contribution log (who contributed what per day)
    # Structure: [ {day: "2024-01-01", sources: {s2: 0.6, s1: 0.3, weather: 0.1}, conflicts: [...]} ]
    provenance_log: List[Dict] = field(default_factory=list)
    
    # Per-pixel spatial reliability map (latest snapshot)
    # Structure: { "reliability": [[...]], "last_valid_obs": [[...]] }
    spatial_reliability: Dict[str, Any] = field(default_factory=dict)
    
    # Plot boundary metadata
    # Structure: { "confidence": 0.85, "source": "user_drawn", "alpha_summary": {...} }
    boundary_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self):
        result = {
            "plot_id": self.plot_id,
            "run_id": self.run_id,
            "version": self.version,
            "shape": self.get_shape(),
            "channels": [c.value for c in self.channels],
            "time_index": self.time_index,
            "grid_spec": self.grid_spec.to_dict(),
            "static": self.static,
            "grid": self.grid,
            "zones": self.zones,
            "zone_stats": self.zone_stats,
            # "data": self.data, # WARNING: Too large to dump in full JSON usually
            # "maps": self.maps, # WARNING: Too large to dump in full JSON
            "plot_timeseries": self.plot_timeseries, # Return the summary view by default
            "forecast_7d": self.forecast_7d,
            "provenance": self.provenance,
        }
        # Layer 0 outputs (if populated by Kalman engine)
        if self.daily_state:
            result["daily_state"] = self.daily_state
        if self.state_uncertainty:
            result["state_uncertainty"] = self.state_uncertainty
        if self.provenance_log:
            result["provenance_log"] = self.provenance_log
        if self.boundary_info:
            result["boundary_info"] = self.boundary_info
        if self.spatial_reliability:
            result["spatial_reliability"] = self.spatial_reliability
        return result

    def get_shape(self) -> List[int]:
        """Returns [T, H, W, C]"""
        try:
            if not self.data: return [0, 0, 0, 0]
            T = len(self.data)
            H = len(self.data[0])
            W = len(self.data[0][0])
            C = len(self.data[0][0][0])
            return [T, H, W, C]
        except:
            return [0, 0, 0, 0]

@dataclass
class FusionOutput:
    """
    The full contract passed to Layer 2+.
    Contains the Tensor + Audit Trail.
    """
    tensor: FieldTensor
    evidence_summary: List[Dict] # Summary of used inputs
    validation_report: Dict[str, Any] # Issues, warnings, health score
    logs: List[Dict] = field(default_factory=list) # Lineage Events
    observation_products: Optional[Dict[str, Any]] = None  # Perception bundle output
    raster_composites: Optional[Dict[str, Any]] = None     # Raster grids from Process API
    
    def to_json(self):
        result = {
            "tensor": self.tensor.to_json(),
            "evidence_summary": self.evidence_summary,
            "validation_report": self.validation_report,
            "logs": self.logs
        }
        if self.observation_products:
            result["observation_products"] = self.observation_products
        return result

