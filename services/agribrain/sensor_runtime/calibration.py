from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, List


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
