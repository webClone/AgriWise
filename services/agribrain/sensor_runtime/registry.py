from __future__ import annotations

import os
import json
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


_DEVICE_REGISTRY: Dict[str, SensorDeviceRegistration] = {}


def is_production() -> bool:
    """Helper to check if environment is production."""
    env_vars = ["AGRIWISE_PRODUCTION", "AGRIWISE_ENV", "ENV", "ENVIRONMENT"]
    for var in env_vars:
        val = os.getenv(var, "").lower()
        if val in ("true", "production"):
            return True
    return False


def register_device(device: SensorDeviceRegistration) -> None:
    """Register a device in-memory (primarily for tests)."""
    import sys
    _DEVICE_REGISTRY[device.device_id] = device
    for mod_name in ("sensor_runtime.registry", "services.agribrain.sensor_runtime.registry"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_DEVICE_REGISTRY"):
            mod._DEVICE_REGISTRY[device.device_id] = device


def load_persistent_registry() -> dict:
    """Load and parse registry from a persistent JSON file source."""
    path = os.getenv("AGRIWISE_SENSOR_REGISTRY_PATH")
    if not path:
        raise ValueError("sensor_registry_unavailable")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        registry = {}
        for dev_id, entry in data.items():
            registry[dev_id] = SensorDeviceRegistration(
                device_id=entry["device_id"],
                vendor=entry["vendor"],
                model=entry["model"],
                protocol=entry["protocol"],
                farm_id=entry["farm_id"],
                plot_id=entry["plot_id"],
                latitude=float(entry["latitude"]),
                longitude=float(entry["longitude"]),
                variables=entry["variables"],
                installation_datetime=datetime.fromisoformat(entry["installation_datetime"]),
                status=entry["status"],
                firmware_version=entry.get("firmware_version"),
                zone_id=entry.get("zone_id"),
                sensor_families=entry.get("sensor_families", []),
                installed_by=entry.get("installed_by"),
                depth_cm=entry.get("depth_cm"),
                gauge_area_cm2=entry.get("gauge_area_cm2"),
                calibration_factor=entry.get("calibration_factor"),
                mounting_height_m=entry.get("mounting_height_m"),
                exposure_height_m=entry.get("exposure_height_m"),
                pipe_identifier=entry.get("pipe_identifier"),
                placement_type=entry.get("placement_type", "unknown"),
                expected_interval_seconds=entry.get("expected_interval_seconds"),
                calibration_profile_id=entry.get("calibration_profile_id"),
            )
        return registry
    except Exception:
        raise ValueError("sensor_registry_unavailable")


def get_device_registration(device_id: str) -> Optional[SensorDeviceRegistration]:
    """Retrieve device registration metadata."""
    if is_production():
        registry = load_persistent_registry()
        return registry.get(device_id)
    return _DEVICE_REGISTRY.get(device_id)


import sys
# Unified namespace cross-aliasing (F37)
if "services.agribrain.sensor_runtime.registry" in sys.modules and "sensor_runtime.registry" not in sys.modules:
    sys.modules["sensor_runtime.registry"] = sys.modules["services.agribrain.sensor_runtime.registry"]
elif "sensor_runtime.registry" in sys.modules and "services.agribrain.sensor_runtime.registry" not in sys.modules:
    sys.modules["services.agribrain.sensor_runtime.registry"] = sys.modules["sensor_runtime.registry"]

