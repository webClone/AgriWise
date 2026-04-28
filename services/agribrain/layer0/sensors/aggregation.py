from datetime import datetime
from typing import List

from sensor_runtime.schemas import NormalizedSensorReading
from layer0.sensors.schemas import SensorAggregate

def compute_daily_soil_moisture_aggregates(
    device_id: str,
    readings: List[NormalizedSensorReading],
    window_start: datetime,
    window_end: datetime
) -> List[SensorAggregate]:
    """Calculate daily min, max, mean, and delta for soil moisture."""
    if not readings:
        return []
        
    valid_vals = [float(r.value) for r in readings if r.value is not None]
    if not valid_vals:
        return []
        
    v_min, v_max = min(valid_vals), max(valid_vals)
    v_mean = sum(valid_vals) / len(valid_vals)
    v_delta = valid_vals[-1] - valid_vals[0]
    
    aggs = []
    for agg_type, val in [("daily_min", v_min), ("daily_max", v_max), ("daily_mean", v_mean), ("daily_delta", v_delta)]:
        aggs.append(SensorAggregate(
            device_id=device_id,
            variable="soil_moisture_vwc",
            window_start=window_start,
            window_end=window_end,
            aggregate_type=agg_type,
            value=val,
            unit="fraction",
            sample_count=len(valid_vals),
            confidence=1.0
        ))
    return aggs

def compute_rain_event_total(
    device_id: str,
    readings: List[NormalizedSensorReading],
    window_start: datetime,
    window_end: datetime
) -> tuple[SensorAggregate | None, list[str]]:
    if not readings:
        return None, []
        
    total = 0.0
    flags = []
    for i, r in enumerate(readings):
        if r.value is None:
            continue
        mode = getattr(r, "rainfall_mode", "incremental")
        val = float(r.value)
        if mode == "incremental":
            total += val
        elif mode == "cumulative":
            if i > 0 and readings[i-1].value is not None:
                diff = val - float(readings[i-1].value)
                if diff >= 0:
                    total += diff
                else:
                    flags.append("RAIN_GAUGE_RESET_DETECTED")
                    total += val
        elif mode == "event_total":
            total = max(total, val)
            
    return SensorAggregate(
        device_id=device_id,
        variable="rainfall_mm",
        window_start=window_start,
        window_end=window_end,
        aggregate_type="rain_event_total",
        value=total,
        unit="mm",
        sample_count=len(readings),
        confidence=1.0 if "RAIN_GAUGE_RESET_DETECTED" not in flags else 0.5
    ), flags
