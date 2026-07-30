from typing import List, Literal

def check_maintenance_required(
    battery_status: str,
    offline_status: bool,
    calibration_expired: bool,
    flatline_detected: bool,
    rain_gauge_clogged_suspicion: bool
) -> List[Literal[
    "SENSOR_MAINTENANCE_REQUIRED",
    "SENSOR_CALIBRATION_DUE",
    "SENSOR_BATTERY_REPLACE",
    "SENSOR_OFFLINE",
    "SENSOR_CLEAN_RAIN_GAUGE",
    "SENSOR_CHECK_PROBE_PLACEMENT"
]]:
    actions = []
    
    if battery_status in ["low", "critical"]:
        actions.append("SENSOR_BATTERY_REPLACE")
    
    if offline_status:
        actions.append("SENSOR_OFFLINE")
        
    if calibration_expired:
        actions.append("SENSOR_CALIBRATION_DUE")
        
    if rain_gauge_clogged_suspicion:
        actions.append("SENSOR_CLEAN_RAIN_GAUGE")
        
    if flatline_detected:
        actions.append("SENSOR_CHECK_PROBE_PLACEMENT")
        
    if actions:
        actions.append("SENSOR_MAINTENANCE_REQUIRED")
        
    return actions
