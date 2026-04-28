from typing import Any, List, Optional
from datetime import datetime, timedelta

from sensor_runtime.schemas import NormalizedSensorReading
from layer0.sensors.schemas import SensorQAResult

PHYSICAL_RANGES = {
    "soil_moisture_vwc": (0.0, 0.75),
    "soil_water_tension_kpa": (0, 2000),
    "soil_temperature_c": (-20, 70),
    "soil_ec_ds_m": (0, 30),
    "soil_ph": (3, 11),
    "air_temperature_c": (-50, 60),
    "relative_humidity_pct": (0, 100),
    "rainfall_mm": (0, float("inf")),
    "rain_rate_mm_h": (0, 500),
    "wind_speed_ms": (0, 75),
    "wind_gust_ms": (0, 100),
    "wind_direction_deg": (0, 360),
    "battery_pct": (0, 100)
}

SPIKE_THRESHOLDS = {
    "soil_moisture_vwc": 0.15,
    "soil_temperature_c": 5.0,
    "air_temperature_c": 8.0,
}

# Event support: rain/irrigation within this window can explain a soil moisture spike
EVENT_SUPPORT_WINDOW_HOURS = 6
EVENT_SUPPORT_RAIN_THRESHOLD_MM = 5.0


def _check_spike_status(
    variable: str,
    calibrated_value: float,
    recent_readings: List[NormalizedSensorReading],
    reading_timestamp: datetime,
    all_recent_readings: List[NormalizedSensorReading],
) -> str:
    """Returns spike status: NO_SPIKE, UNSUPPORTED_SPIKE, EVENT_SUPPORTED_JUMP, PHYSICALLY_IMPOSSIBLE_JUMP."""
    if not recent_readings:
        return "NO_SPIKE"

    last_val = float(recent_readings[-1].value) if recent_readings[-1].value is not None else None
    if last_val is None:
        return "NO_SPIKE"

    spike_limit = SPIKE_THRESHOLDS.get(variable)
    if spike_limit is None:
        return "NO_SPIKE"

    delta = abs(calibrated_value - last_val)
    if delta <= spike_limit:
        return "NO_SPIKE"

    # Physically impossible jumps (VWC going from 0.1 to 0.7 in one reading)
    phys_min, phys_max = PHYSICAL_RANGES.get(variable, (-float("inf"), float("inf")))
    if calibrated_value < phys_min or calibrated_value > phys_max:
        return "PHYSICALLY_IMPOSSIBLE_JUMP"

    # For soil moisture, check for rain/irrigation event within time window
    if variable == "soil_moisture_vwc" and calibrated_value > last_val:
        event_window_start = reading_timestamp - timedelta(hours=EVENT_SUPPORT_WINDOW_HOURS)
        # Check for significant rain in time window
        rain_support = any(
            r.variable == "rainfall_mm"
            and r.value is not None
            and float(r.value) >= EVENT_SUPPORT_RAIN_THRESHOLD_MM
            and hasattr(r, 'timestamp')
            and r.timestamp is not None
            and r.timestamp >= event_window_start
            for r in all_recent_readings
        )
        # Check for irrigation flow in time window
        irrigation_support = any(
            r.variable == "irrigation_flow_l_min"
            and r.value is not None
            and float(r.value) > 0
            and hasattr(r, 'timestamp')
            and r.timestamp is not None
            and r.timestamp >= event_window_start
            for r in all_recent_readings
        )
        if rain_support or irrigation_support:
            return "EVENT_SUPPORTED_JUMP"

    # Rainfall and wind gust spikes are allowed by nature
    if variable in ("rainfall_mm", "wind_gust_ms"):
        return "NO_SPIKE"

    return "UNSUPPORTED_SPIKE"


def evaluate_qa(
    reading: NormalizedSensorReading,
    calibrated_value: float,
    recent_readings: List[NormalizedSensorReading],
    flatline_count: int,
    health_ceiling: float,
    calibration_ceiling: float,
    representativeness_confidence: float,
    maintenance_ceiling: float,
    update_allowed: bool,
    all_recent_readings: List[NormalizedSensorReading] | None = None,
) -> SensorQAResult:
    usable = True
    flags = []
    reason = "QA passed."

    # Range check
    min_val, max_val = PHYSICAL_RANGES.get(reading.variable, (-float("inf"), float("inf")))
    if not (min_val <= calibrated_value <= max_val):
        usable = False
        flags.append("OUT_OF_PHYSICAL_RANGE")
        reason = f"Value {calibrated_value} outside allowed range ({min_val}-{max_val})."

    # Spike check — time-window based
    qa_score = 1.0
    spike_status = _check_spike_status(
        reading.variable,
        calibrated_value,
        recent_readings,
        reading.timestamp,
        all_recent_readings or [],
    )
    if spike_status == "UNSUPPORTED_SPIKE":
        flags.append("UNSUPPORTED_SPIKE")
        usable = False
        qa_score = 0.0
        reason = "Unsupported spike detected."
    elif spike_status == "PHYSICALLY_IMPOSSIBLE_JUMP":
        flags.append("PHYSICALLY_IMPOSSIBLE_JUMP")
        usable = False
        qa_score = 0.0
        reason = "Physically impossible value jump."
    elif spike_status == "EVENT_SUPPORTED_JUMP":
        flags.append("EVENT_SUPPORTED_JUMP")
        # Usable but degraded
        qa_score = 0.75

    # Flatline check: 12 consecutive identical readings
    if flatline_count >= 12:
        flags.append("FLATLINE_DETECTED")
        usable = False
        qa_score = 0.0
        reason = "Sensor flatlining."

    if not usable:
        qa_score = 0.0

    # reading_reliability: true quality of the data point, independent of state-update scope
    # Does NOT include scope/update restrictions
    reading_reliability = min(
        calibration_ceiling,
        representativeness_confidence,
        health_ceiling,
        maintenance_ceiling,
        qa_score
    )

    # state_update_reliability: factors in whether this sensor is allowed to update state
    state_update_reliability = reading_reliability if update_allowed else 0.0

    # Quality class based on reading_reliability (NOT state_update_reliability)
    if reading_reliability < 0.20:
        quality_class = "unusable"
    elif reading_reliability < 0.60:
        quality_class = "degraded"
    elif reading_reliability < 0.80:
        quality_class = "good"
    else:
        quality_class = "excellent"

    # Determine limiting factor
    if reading_reliability < qa_score and reading_reliability < 1.0:
        if reading_reliability == calibration_ceiling:
            reason = "UNCALIBRATED_OR_LOW_CALIBRATION"
        elif reading_reliability == representativeness_confidence:
            reason = "LOW_REPRESENTATIVENESS"
        elif reading_reliability == health_ceiling:
            reason = "BATTERY_OR_SIGNAL_LOW"
        elif reading_reliability == maintenance_ceiling:
            reason = "MAINTENANCE_REQUIRED"

    if not update_allowed:
        flags.append("DIAGNOSTIC_ONLY_NO_STATE_UPDATE")

    return SensorQAResult(
        usable=usable,
        quality_class=quality_class,
        qa_score=qa_score,
        reading_reliability=reading_reliability,
        state_update_reliability=state_update_reliability,
        update_allowed=update_allowed,
        reliability_weight=state_update_reliability,  # backward compat: Kalman uses this
        sigma_multiplier=1.0 if usable else 10.0,
        range_score=1.0 if "OUT_OF_PHYSICAL_RANGE" not in flags else 0.0,
        spike_score=1.0 if "UNSUPPORTED_SPIKE" not in flags else 0.0,
        flatline_score=1.0 if "FLATLINE_DETECTED" not in flags else 0.0,
        dropout_score=1.0,
        battery_score=health_ceiling,
        signal_score=1.0,
        calibration_score=calibration_ceiling,
        placement_score=representativeness_confidence,
        representativeness_score=representativeness_confidence,
        flags=flags,
        reason=reason
    )
