from typing import List
from sensor_runtime.schemas import NormalizedSensorReading

def apply_gapfill(readings: List[NormalizedSensorReading], max_gap_minutes: int = 60) -> List[NormalizedSensorReading]:
    """
    Interpolate missing telemetry data points if the temporal gap between consecutive 
    readings is within max_gap_minutes. Currently returns the readings as-is to preserve 
    original telemetry fidelity.
    """
    return readings
