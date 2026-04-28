from datetime import datetime, timezone
from typing import List, Dict, Any

from sensor_runtime.registry import SensorDeviceRegistration
from sensor_runtime.schemas import NormalizedSensorReading
from layer0.sensors.schemas import SensorContextPackage, SensorAggregate, SensorQAResult
from layer0.sensors.calibration import apply_calibration
from layer0.sensors.representativeness import evaluate_representativeness
from layer0.sensors.qa import evaluate_qa
from layer0.sensors.aggregation import compute_daily_soil_moisture_aggregates, compute_rain_event_total
from layer0.sensors.packetizer import build_sensor_packets
from layer0.sensors.kalman_adapter import map_to_kalman_observations, map_to_process_forcing
from layer0.sensors.validation import run_cross_validation
from layer0.sensors.diagnostics import build_diagnostics

from sensor_runtime.health import evaluate_battery_health, evaluate_signal_health, evaluate_offline_status, evaluate_health_ceiling
from layer0.sensors.irrigation_event_detector import detect_irrigation_events


def _extract_health_value(all_readings: List[NormalizedSensorReading], variable: str, default: float) -> float:
    """Extract the most recent value for a canonical health variable from readings."""
    for r in reversed(all_readings):
        if r.variable == variable and r.value is not None:
            return float(r.value)
    return default


def process_sensor_window(
    plot_id: str,
    window_start: datetime,
    window_end: datetime,
    devices: List[SensorDeviceRegistration],
    readings: List[NormalizedSensorReading],
    calibration_profiles: Dict[str, Any],
    geo_context: Dict[str, Any] | None,
    satellite_context: Dict[str, Any] | None,
    weather_context: Dict[str, Any] | None,
    historical_readings_by_device: Dict[str, List[NormalizedSensorReading]] | None = None
) -> SensorContextPackage:
    
    qa_results = []
    aggregates = []
    observation_packets = []
    kalman_obs = []
    forces = []
    
    for device in devices:
        device_readings = [r for r in readings if r.device_id == device.device_id]
        if not device_readings:
            continue
            
        profile = calibration_profiles.get(device.device_id)
        flags = geo_context.get("flags", []) if geo_context else []
        rep = evaluate_representativeness(device.placement_type, flags)
        
        history = historical_readings_by_device.get(device.device_id, []) if historical_readings_by_device else []
        all_readings = history + device_readings
        
        # Health extraction: priority is normalized readings > raw_msg metadata > defaults
        # Uses canonical variable names: signal_rssi_dbm, signal_snr_db
        battery_pct = _extract_health_value(all_readings, "battery_pct", 100.0)
        rssi_val = _extract_health_value(all_readings, "signal_rssi_dbm", -50.0)
        snr_val = _extract_health_value(all_readings, "signal_snr_db", 10.0)
        
        bat_status = evaluate_battery_health(battery_pct)
        sig_status = evaluate_signal_health(rssi_val, snr_val)
        
        # Determine if this device is allowed to update Kalman state
        # Diagnostic/point sensors (edge, wetspot, unknown) may NOT update state
        device_update_allowed = rep.update_scope != "none"
        
        for i, r in enumerate(device_readings):
            cal_val, rel_ceil, cal_class = apply_calibration(r, profile, window_end, geo_context.get("soil_texture") if geo_context else None)
            
            is_offline = evaluate_offline_status(r.timestamp, device.expected_interval_seconds, window_end)
            maintenance_req = device.status in ("maintenance", "retired", "lost")
            
            health_ceil = evaluate_health_ceiling(bat_status, sig_status, is_offline, maintenance_req)
            health_status_str = "critical" if health_ceil <= 0.3 else ("low" if health_ceil < 1.0 else "ok")
            
            # Combine history up to this reading for spike/flatline analysis
            combined_hist = history + device_readings[:i]
            flatline_count = 0
            if combined_hist and cal_val is not None:
                for past_r in reversed(combined_hist):
                    if past_r.variable == r.variable and past_r.value == r.value:
                        flatline_count += 1
                    elif past_r.variable == r.variable:
                        break
            
            qa = evaluate_qa(
                reading=r,
                calibrated_value=cal_val if isinstance(cal_val, float) else 0.0,
                recent_readings=[past for past in combined_hist if past.variable == r.variable],
                flatline_count=flatline_count,
                health_ceiling=health_ceil,
                calibration_ceiling=rel_ceil,
                representativeness_confidence=rep.confidence,
                maintenance_ceiling=0.0 if maintenance_req else 1.0,
                update_allowed=device_update_allowed,
                all_recent_readings=combined_hist,
            )
            qa_results.append(qa)
            
            # Kalman observations — only if state update is allowed AND reliability is high enough
            kalman_obs.extend(map_to_kalman_observations(
                r.variable,
                cal_val if isinstance(cal_val, float) else 0.0,
                qa,
                rep,
                device.depth_interval_cm or ((device.depth_cm, device.depth_cm) if device.depth_cm else None)
            ))
            # Process forcing (weather, precipitation) — lower threshold than Kalman
            forces.extend(map_to_process_forcing(r.variable, cal_val if isinstance(cal_val, float) else 0.0, qa, rep))
            
        # Aggregation
        if "soil_moisture_vwc" in device.variables:
            sm_aggs = compute_daily_soil_moisture_aggregates(
                device.device_id,
                [r for r in device_readings if r.variable == "soil_moisture_vwc"],
                window_start, window_end
            )
            aggregates.extend(sm_aggs)
            
        if "rainfall_mm" in device.variables:
            rain_agg, rain_flags = compute_rain_event_total(
                device.device_id,
                [r for r in device_readings if r.variable == "rainfall_mm"],
                window_start, window_end
            )
            if rain_agg:
                if rain_flags:
                    rain_agg.confidence = 0.5
                aggregates.append(rain_agg)
                
        # Irrigation process forcing — via event detector ONLY (no raw flow forcing to prevent double-count)
        irr_events = []
        if "irrigation_flow_l_min" in device.variables and device.pipe_identifier:
            flow_readings = [r for r in device_readings if r.variable == "irrigation_flow_l_min"]
            press_readings = [r for r in device_readings if r.variable == "irrigation_pressure_bar"]
            irr_events = detect_irrigation_events(plot_id, flow_readings, press_readings, device.pipe_identifier, [device.device_id])
            forces.extend(irr_events)
                
        # Packetize — always emit diagnostics even for unusable readings
        if qa_results:
            device_packets = build_sensor_packets(
                device_id=device.device_id,
                device=device,
                variable=device.variables[0],
                aggregates=aggregates,
                qa=qa_results[-1],
                rep=rep,
                cal_class=cal_class,
                health_status=health_status_str,
                readings=device_readings,
                irrigation_events=irr_events
            )
            observation_packets.extend(device_packets)

    # Cross Validation
    val_events = run_cross_validation(aggregates, satellite_context, weather_context)
    
    # Diagnostics
    diags = build_diagnostics(devices, qa_results, val_events)

    return SensorContextPackage(
        plot_id=plot_id,
        window_start=window_start,
        window_end=window_end,
        devices=devices,
        readings=readings,
        qa_results=qa_results,
        aggregates=aggregates,
        placement_context={"geo_context_used": geo_context is not None},
        observation_packets=observation_packets,
        kalman_observations=kalman_obs,
        process_forcing_events=forces,
        validation_events=val_events,
        diagnostics=diags,
        provenance={"timestamp": datetime.now(timezone.utc).isoformat()}
    )
