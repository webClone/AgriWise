from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional, Tuple


@dataclass
class SensorDeviceRegistration:
    """Registry entry for a physical sensor device deployed in the field."""
    # Mandatory core identity
    device_id: str
    vendor: str
    model: str
    protocol: str
    
    # Mandatory geographical/plot identity
    farm_id: str
    plot_id: str
    latitude: float
    longitude: float
    
    # Mandatory capability & status
    variables: List[str]
    installation_datetime: datetime
    status: Literal["active", "inactive", "maintenance", "retired", "lost"]

    # Optional fields
    firmware_version: Optional[str] = None
    zone_id: Optional[str] = None
    sensor_families: List[str] = field(default_factory=list)
    installed_by: Optional[str] = None

    # Conditionally Mandatory (checked at runtime or instantiation)
    depth_cm: Optional[float] = None
    depth_interval_cm: Optional[Tuple[float, float]] = None
    exposure_height_m: Optional[float] = None
    gauge_area_cm2: Optional[float] = None
    calibration_factor: Optional[float] = None
    mounting_height_m: Optional[float] = None
    pipe_identifier: Optional[str] = None

    # Placement and Geo Context
    placement_type: Literal[
        "representative_zone",
        "known_wet_spot",
        "known_dry_spot",
        "edge",
        "irrigation_line",
        "weather_station",
        "control_point",
        "unknown"
    ] = "unknown"

    # Engine configurations
    expected_interval_seconds: Optional[int] = None
    calibration_profile_id: Optional[str] = None
    geo_context_ref: Optional[str] = None
    soil_context_ref: Optional[str] = None

    def validate(self) -> None:
        """Enforces conditionally mandatory fields."""
        if not self.variables:
            raise ValueError(f"Device {self.device_id} must declare variables to become active.")
            
        if any("soil" in v for v in self.variables):
            if self.depth_cm is None and self.depth_interval_cm is None:
                raise ValueError(f"Soil sensor {self.device_id} must define depth_cm or depth_interval_cm.")
                
        if "rainfall_mm" in self.variables and self.gauge_area_cm2 is None and self.calibration_factor is None:
            raise ValueError(f"Rain gauge {self.device_id} must define gauge_area_cm2 or calibration_factor.")
            
        if "wind_speed_ms" in self.variables and self.mounting_height_m is None:
            raise ValueError(f"Wind sensor {self.device_id} must define mounting_height_m.")
            
        if "weather_station" == self.placement_type and self.exposure_height_m is None:
            raise ValueError(f"Weather station {self.device_id} must define exposure_height_m.")
            
        if "irrigation_flow_l_min" in self.variables and not self.pipe_identifier:
            raise ValueError(f"Irrigation flow sensor {self.device_id} must have a pipe_identifier.")
