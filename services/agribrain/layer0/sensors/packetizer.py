from typing import Dict, Any, List
from datetime import datetime, timezone

from layer0.sensors.schemas import SensorAggregate, SensorQAResult, SensorRepresentativeness
from layer0.sensors.irrigation_event_detector import IrrigationProcessForcing
from sensor_runtime.schemas import NormalizedSensorReading


def build_sensor_packets(
    device_id: str,
    device: Any,
    variable: str,
    aggregates: List[SensorAggregate],
    qa: SensorQAResult,
    rep: SensorRepresentativeness,
    cal_class: str,
    health_status: str,
    readings: List[NormalizedSensorReading] = None,
    irrigation_events: List[IrrigationProcessForcing] = None
) -> List[Dict[str, Any]]:
    packets = []
    
    # === Always emitted: diagnostics for ALL readings (even unusable) ===
    
    # QA result
    packets.append({
        "type": "SENSOR_QA_RESULT",
        "device_id": device_id,
        "usable": qa.usable,
        "quality_class": qa.quality_class,
        "reading_reliability": qa.reading_reliability,
        "state_update_reliability": qa.state_update_reliability,
        "update_allowed": qa.update_allowed,
        "flags": qa.flags,
    })
    
    # Health status
    packets.append({
        "type": "SENSOR_HEALTH_STATUS",
        "device_id": device_id,
        "health_status": health_status,
        "battery_score": qa.battery_score
    })
    
    # Placement context
    packets.append({
        "type": "SENSOR_PLACEMENT_CONTEXT",
        "device_id": device_id,
        "observation_scope": rep.observation_scope,
        "update_scope": rep.update_scope,
        "flags": rep.placement_flags
    })
    
    # Calibration context
    packets.append({
        "type": "SENSOR_CALIBRATION_CONTEXT",
        "device_id": device_id,
        "calibration_class": cal_class
    })
    
    # Provenance
    packets.append({
        "type": "SENSOR_PROVENANCE",
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine_version": "sensor_v1_hardened",
    })
    
    # Raw reading reference
    if readings:
        for r in readings:
            if r.raw_payload_ref:
                packets.append({
                    "type": "SENSOR_RAW_READING_REF",
                    "device_id": device_id,
                    "reading_id": r.reading_id,
                    "raw_payload_ref": r.raw_payload_ref,
                    "variable": r.variable,
                    "original_value": r.original_value,
                    "original_unit": r.original_unit,
                })
    
    # Device registration snapshot
    if device is not None:
        packets.append({
            "type": "SENSOR_DEVICE_REGISTRATION",
            "device_id": device_id,
            "vendor": getattr(device, "vendor", "unknown"),
            "model": getattr(device, "model", "unknown"),
            "protocol": getattr(device, "protocol", "unknown"),
            "placement_type": getattr(device, "placement_type", "unknown"),
            "variables": getattr(device, "variables", []),
        })
    
    # Irrigation flow events
    if irrigation_events:
        for ev in irrigation_events:
            packets.append({
                "type": "SENSOR_IRRIGATION_FLOW_EVENT",
                "device_id": device_id,
                "event_id": ev.event_id,
                "volume_l": ev.volume_l,
                "flow_mean_l_min": ev.flow_mean_l_min,
                "confidence": ev.event_confidence,
                "flags": ev.flags,
            })
    
    # === Variable-specific event packets ===
    if readings:
        # Rainfall event
        rain_readings = [r for r in readings if r.variable == "rainfall_mm" and r.value is not None and float(r.value) > 0]
        if rain_readings:
            total_mm = sum(float(r.value) for r in rain_readings)
            packets.append({
                "type": "SENSOR_RAINFALL_EVENT",
                "device_id": device_id,
                "total_mm": total_mm,
                "reading_count": len(rain_readings),
            })
        
        # Wind event
        wind_readings = [r for r in readings if r.variable in ("wind_speed_ms", "wind_gust_ms") and r.value is not None]
        if wind_readings:
            max_wind = max(float(r.value) for r in wind_readings)
            packets.append({
                "type": "SENSOR_WIND_EVENT",
                "device_id": device_id,
                "max_wind_ms": max_wind,
                "reading_count": len(wind_readings),
            })
        
        # Leaf wetness event
        lw_readings = [r for r in readings if r.variable == "leaf_wetness" and r.value is not None]
        if lw_readings:
            max_lw = max(float(r.value) for r in lw_readings)
            packets.append({
                "type": "SENSOR_LEAF_WETNESS_EVENT",
                "device_id": device_id,
                "max_wetness": max_lw,
                "reading_count": len(lw_readings),
            })
    
    # === Value packets — only if reading is usable ===
    if not qa.usable:
        return packets

    for agg in aggregates:
        packet_type = f"SENSOR_{variable.upper()}_AGGREGATE"
        packets.append({
            "type": packet_type,
            "device_id": device_id,
            "aggregate_type": agg.aggregate_type,
            "value": agg.value,
            "unit": agg.unit
        })
        
    return packets
