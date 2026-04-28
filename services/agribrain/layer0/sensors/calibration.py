from datetime import datetime
from typing import Literal

from sensor_runtime.schemas import NormalizedSensorReading
from sensor_runtime.calibration import SensorCalibrationProfile

CALIBRATION_CEILINGS = {
    "soil_specific": 0.95,
    "field_two_point": 0.90,
    "factory": 0.80,
    "vendor_default": 0.65,
    "expired": 0.55,
    "soil_mismatch": 0.50,
    "uncalibrated": 0.45,
    "offset_scale": 0.80, # Assuming similar to factory if user-defined but not field-verified rigorously
    "field_single_point": 0.80
}


def apply_calibration(
    reading: NormalizedSensorReading,
    profile: SensorCalibrationProfile | None,
    evaluation_time: datetime,
    plot_soil_texture: dict | None = None
) -> tuple[float, float, Literal["excellent", "good", "degraded", "unusable"]]:
    """
    Applies the calibration profile to the normalized reading value.
    Returns: (calibrated_value, reliability_ceiling, calibration_class)
    """
    if reading.value is None or isinstance(reading.value, (str, bool)):
        # Can't mathematically calibrate strings/bools
        return reading.value, 1.0, "good"

    if profile is None:
        return float(reading.value), CALIBRATION_CEILINGS["uncalibrated"], "degraded"

    val = float(reading.value)
    
    # Apply polynomial if present
    if profile.polynomial:
        calibrated_val = sum(c * (val ** i) for i, c in enumerate(profile.polynomial))
    else:
        # Standard scale + offset
        calibrated_val = (val * profile.scale) + profile.offset

    # Determine reliability ceiling
    ceiling = CALIBRATION_CEILINGS.get(profile.calibration_type, 0.45)
    calib_class = "good"

    if profile.is_expired(evaluation_time):
        ceiling = min(ceiling, CALIBRATION_CEILINGS["expired"])
        calib_class = "degraded"

    if profile.calibration_type == "soil_specific" and profile.soil_texture_context and plot_soil_texture:
        # Simplified mock check for soil mismatch
        if profile.soil_texture_context.get("class") != plot_soil_texture.get("class"):
            ceiling = min(ceiling, CALIBRATION_CEILINGS["soil_mismatch"])
            calib_class = "degraded"

    if ceiling <= 0.45:
        calib_class = "unusable"

    return calibrated_val, ceiling, calib_class
