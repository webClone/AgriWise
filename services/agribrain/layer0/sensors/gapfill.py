from typing import List
from sensor_runtime.schemas import NormalizedSensorReading

def apply_gapfill(readings: List[NormalizedSensorReading], max_gap_minutes: int = 60) -> List[NormalizedSensorReading]:
    """
    Mock gapfill: If the gap between two valid readings is < max_gap_minutes,
    we could interpolate. V1 does not fabricate data unless explicitly requested
    for strict models, so we just return readings as-is.
    """
    return readings
