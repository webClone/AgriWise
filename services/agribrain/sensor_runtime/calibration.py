from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, List
import os
import json


@dataclass
class SensorCalibrationProfile:
    """Stores the calibration configuration for a specific device and variable."""
    calibration_profile_id: str
    device_id: str
    variable: str

    calibration_type: Literal[
        "factory",
        "field_single_point",
        "field_two_point",
        "soil_specific",
        "offset_scale",
        "vendor_default",
        "uncalibrated"
    ]

    valid_from: datetime

    offset: float = 0.0
    scale: float = 1.0
    polynomial: Optional[List[float]] = None

    valid_until: Optional[datetime] = None

    calibration_quality: float = 1.0
    calibration_source: str = "unknown"
    soil_texture_context: Optional[dict] = None
    notes: Optional[str] = None

    def is_expired(self, current_time: datetime) -> bool:
        if self.valid_until and current_time > self.valid_until:
            return True
        return False


_CALIBRATION_PROFILES = {}


def is_production() -> bool:
    """Helper to check if environment is production."""
    env_vars = ["AGRIWISE_PRODUCTION", "AGRIWISE_ENV", "ENV", "ENVIRONMENT"]
    for var in env_vars:
        val = os.getenv(var, "").lower()
        if val in ("true", "production"):
            return True
    return False


def register_calibration_profile(profile: SensorCalibrationProfile) -> None:
    """Register a calibration profile dynamically (primarily for tests)."""
    _CALIBRATION_PROFILES[profile.device_id] = profile


def load_persistent_calibration(device_id: str, variable: Optional[str] = None) -> Optional[SensorCalibrationProfile]:
    """Load calibration profiles dynamically from JSON path in production."""
    path = os.getenv("AGRIWISE_SENSOR_CALIBRATION_PATH")
    if not path:
        raise ValueError("sensor_calibration_unavailable")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entry = None
        if variable:
            entry = data.get(f"{device_id}_{variable}")
            if not entry:
                # Try to look up using compatible aliases in the same family
                from sensor_runtime.ingestion import VARIABLE_FAMILIES
                aliases = {variable}
                for family, family_aliases in VARIABLE_FAMILIES.items():
                    if variable in family_aliases:
                        aliases = family_aliases
                        break
                for alias in aliases:
                    if alias != variable:
                        entry = data.get(f"{device_id}_{alias}")
                        if entry:
                            break
            if not entry:
                # If still not found, check if there are other profiles for this device
                # to trigger a calibration_variable_mismatch instead of unavailable,
                # but ONLY if that other profile is NOT for a registered variable of the device.
                from sensor_runtime.registry import get_device_registration
                reg = get_device_registration(device_id)
                reg_vars = reg.variables if reg else []
                for k, v in data.items():
                    if k.startswith(f"{device_id}_"):
                        profile_var = v.get("variable")
                        if profile_var not in reg_vars:
                            entry = v
                            break
        if not entry:
            entry = data.get(device_id)
        if not entry:
            return None
            
        valid_until_str = entry.get("valid_until")
        valid_until_dt = None
        if valid_until_str:
            valid_until_dt = datetime.fromisoformat(valid_until_str)

        return SensorCalibrationProfile(
            calibration_profile_id=entry["calibration_profile_id"],
            device_id=entry["device_id"],
            variable=entry["variable"],
            calibration_type=entry["calibration_type"],
            valid_from=datetime.fromisoformat(entry["valid_from"]),
            offset=entry.get("offset", 0.0),
            scale=entry.get("scale", 1.0),
            polynomial=entry.get("polynomial"),
            valid_until=valid_until_dt,
            calibration_quality=entry.get("calibration_quality") if "calibration_quality" in entry else None,
            calibration_source=entry.get("calibration_source", "unknown"),
        )
    except Exception as e:
        if isinstance(e, ValueError) and str(e) in ("sensor_calibration_unavailable", "sensor_uncalibrated"):
            raise
        raise ValueError("sensor_calibration_unavailable")


def get_calibration_profile(device_id: str, variable: Optional[str] = None) -> Optional[SensorCalibrationProfile]:
    """Retrieve calibration profile for a device."""
    if is_production():
        return load_persistent_calibration(device_id, variable)
    if variable:
        key = f"{device_id}_{variable}"
        if key in _CALIBRATION_PROFILES:
            return _CALIBRATION_PROFILES[key]
    return _CALIBRATION_PROFILES.get(device_id)
