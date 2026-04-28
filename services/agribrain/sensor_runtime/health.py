from datetime import datetime, timezone
from typing import Dict, Literal, Optional

def evaluate_battery_health(battery_pct: float) -> Literal["ok", "low", "critical"]:
    if battery_pct < 15.0:
        return "critical"
    if battery_pct < 30.0:
        return "low"
    return "ok"

def evaluate_signal_health(rssi: float, snr: Optional[float] = None) -> Literal["ok", "weak", "lost"]:
    # Mock vendor generic thresholds
    if rssi < -120.0:
        return "weak"
    return "ok"

def evaluate_offline_status(
    last_seen: datetime, 
    expected_interval_seconds: Optional[int], 
    current_time: datetime
) -> bool:
    """Returns True if the sensor is considered OFFLINE."""
    if expected_interval_seconds is None:
        return False
    
    delta_seconds = (current_time - last_seen).total_seconds()
    return delta_seconds > (expected_interval_seconds * 3)

def check_dropout(missing_count: int, threshold: int) -> bool:
    """Returns True if dropout missing count exceeds threshold in a given window."""
    return missing_count > threshold

def evaluate_health_ceiling(
    battery_status: Literal["ok", "low", "critical"],
    signal_status: Literal["ok", "weak", "lost"],
    is_offline: bool,
    maintenance_required: bool
) -> float:
    if is_offline:
        return 0.0
    if maintenance_required:
        return 0.0 # for Kalman
    
    ceil = 1.0
    if battery_status == "critical":
        ceil = min(ceil, 0.30)
    elif battery_status == "low":
        ceil = min(ceil, 0.75)
        
    if signal_status == "weak":
        ceil = min(ceil, 0.70)
    elif signal_status == "lost":
        ceil = min(ceil, 0.0)
        
    return ceil
