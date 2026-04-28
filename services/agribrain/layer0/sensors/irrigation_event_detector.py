from datetime import datetime
from typing import List, Optional
from sensor_runtime.schemas import NormalizedSensorReading


from dataclasses import dataclass, field
import uuid

# Maximum gap between consecutive flow readings before we split into separate events
MAX_READING_GAP_MINUTES = 30.0


@dataclass
class IrrigationProcessForcing:
    event_id: str
    plot_id: str
    line_id: str | None
    start_time: datetime
    end_time: datetime
    volume_l: float | None
    flow_mean_l_min: float | None
    pressure_mean_bar: float | None
    pressure_stability_score: float
    event_confidence: float
    source_device_ids: list[str]
    flags: list[str] = field(default_factory=list)


def _integrate_volume(flow_readings: List[NormalizedSensorReading]) -> float:
    """Compute volume by timestamp integration: Σ(flow_l_min × delta_minutes)."""
    if len(flow_readings) < 2:
        if flow_readings:
            # Single reading: assume 1 minute duration as minimum
            return float(flow_readings[0].value) * 1.0 if flow_readings[0].value else 0.0
        return 0.0

    # Sort by timestamp
    sorted_readings = sorted(flow_readings, key=lambda r: r.timestamp)
    volume = 0.0
    for i in range(1, len(sorted_readings)):
        prev = sorted_readings[i - 1]
        curr = sorted_readings[i]

        delta_seconds = (curr.timestamp - prev.timestamp).total_seconds()
        delta_minutes = delta_seconds / 60.0

        # Skip duplicate timestamps
        if delta_minutes <= 0:
            continue

        # Cap unreasonable gaps — don't integrate across long gaps
        if delta_minutes > MAX_READING_GAP_MINUTES:
            continue

        # Use average of prev and curr flow for trapezoidal integration
        flow_prev = float(prev.value) if prev.value is not None else 0.0
        flow_curr = float(curr.value) if curr.value is not None else 0.0
        avg_flow = (flow_prev + flow_curr) / 2.0

        volume += avg_flow * delta_minutes

    return volume


def detect_irrigation_events(
    plot_id: str,
    flow_readings: List[NormalizedSensorReading],
    pressure_readings: List[NormalizedSensorReading],
    pipe_identifier: str,
    source_devices: List[str]
) -> List[IrrigationProcessForcing]:
    """
    Detect irrigation events from flow and pressure readings.
    Uses timestamp-based volume integration instead of simple summation.
    """
    events = []
    
    if not flow_readings:
        return events
        
    # Sort and filter
    sorted_flow = sorted(
        [r for r in flow_readings if r.value is not None and float(r.value) > 0],
        key=lambda r: r.timestamp
    )
    if not sorted_flow:
        return events
    
    # Compute volume via timestamp integration
    volume_l = _integrate_volume(sorted_flow)
    flow_vals = [float(r.value) for r in sorted_flow]
    flow_mean = sum(flow_vals) / len(flow_vals)
    
    # Pressure analysis
    pressure_vals = [float(r.value) for r in pressure_readings if r.value is not None]
    p_mean = sum(pressure_vals) / len(pressure_vals) if pressure_vals else None
    
    # Pressure stability: low variance = stable
    p_stability = 0.9
    if len(pressure_vals) > 1:
        p_var = sum((p - p_mean) ** 2 for p in pressure_vals) / len(pressure_vals)
        p_stability = max(0.0, min(1.0, 1.0 - (p_var / max(p_mean, 0.01))))
    
    flags = []
    if p_mean is not None and p_mean < 0.5:
        flags.append("LOW_PRESSURE_ANOMALY")
    
    # Event confidence based on data quality
    confidence = 0.85
    if volume_l == 0:
        confidence = 0.3
        flags.append("ZERO_INTEGRATED_VOLUME")
    if len(sorted_flow) < 3:
        confidence = min(confidence, 0.6)
        flags.append("FEW_FLOW_READINGS")
        
    events.append(IrrigationProcessForcing(
        event_id=str(uuid.uuid4()),
        plot_id=plot_id,
        line_id=pipe_identifier,
        start_time=sorted_flow[0].timestamp,
        end_time=sorted_flow[-1].timestamp,
        volume_l=volume_l,
        flow_mean_l_min=flow_mean,
        pressure_mean_bar=p_mean,
        pressure_stability_score=p_stability,
        event_confidence=confidence,
        source_device_ids=source_devices,
        flags=flags
    ))
    
    return events
