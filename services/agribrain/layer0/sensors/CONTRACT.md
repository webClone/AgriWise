# Layer 0 Sensor Engine V1 — Contract

This package bridges the gap between normalized IoT data (`sensor_runtime`) and high-trust scientific intelligence. 
**Core Rule:** Sensors are strong evidence only after calibration, placement validation, QA, and representativeness checks. A bad sensor must never dominate the plot state.

## Hard Prohibitions (Production Gate Enforced)

The production gate will fail if the engine cannot strictly guarantee the following hard prohibitions:

```json
{
  "sensor_hard_prohibitions": {
    "uncalibrated_sensor_no_high_trust": true,
    "unknown_placement_no_plot_wide_update": true,
    "edge_sensor_no_plot_wide_update": true,
    "wet_lowspot_sensor_not_plot_mean": true,
    "flatline_sensor_no_kalman": true,
    "spike_sensor_degraded_or_rejected": true,
    "bad_battery_degrades_reliability": true,
    "bad_signal_degrades_reliability": true,
    "wind_no_direct_canopy_stress": true,
    "leaf_wetness_no_direct_disease_diagnosis": true,
    "forecast_not_sensor_truth": true,
    "irrigation_flow_not_soil_moisture_without_response": true,
    "point_sensor_scope_respected": true
  }
}
```

## Calibration Reliability Ceilings

Maximum reliability assigned to an observation is capped by its calibration quality:

| Calibration Status | Max Plot-Wide Reliability |
|--------------------|---------------------------|
| Soil-specific field calibration | 0.95 |
| Two-point field calibration | 0.90 |
| Factory calibration | 0.80 |
| Vendor default | 0.65 |
| Expired calibration | 0.55 |
| Calibration mismatch with soil texture | 0.50 |
| Uncalibrated | 0.45 |

## Representativeness Ceilings

A sensor's geographic influence is bound by its placement, using Geo Context validation. We distinguish between `observation_scope` (where the sensor physically measures) and `update_scope` (the scale of state it is allowed to update).

| Placement Type | Default Scope (Update Scope) | Max Plot-wide Reliability |
|----------------|---------------|---------------------------|
| Representative zone | zone/plot (if validated) | 0.85 |
| Weather station (good exposure) | plot/farm microclimate | 0.85 |
| Irrigation line | irrigation block | 0.60 |
| Unknown | point | 0.45 |
| Known wet spot | wet-zone diagnostic | 0.40 for plot |
| Known dry spot | dry-zone diagnostic | 0.40 for plot |
| Edge | point/edge | 0.35 |

*Depth overlap mapping*: Depth bounds (e.g., a sensor covering 15-45 cm) must map dynamically to layer boundaries rather than assuming midpoint perfection.

## Kalman & Process Forcing Mapping Rules

### Strong Kalman Candidates
- Calibrated representative VWC 0–10 cm → `sm_0_10`
- Calibrated representative VWC 10–40 cm → `root-zone soil moisture`
- Soil temperature at root depth → `root-zone temperature`

### Process Forcing (Event Triggers, Not State Updates)
- Rain gauge → precipitation forcing/event
- Irrigation flow → irrigation forcing/event (requires valid `event_confidence`)
- Air temp/RH/wind/radiation → local weather forcing

### Context / Diagnostic Only (Packet Output)
- Leaf wetness → disease-weather context
- Soil EC/pH → salinity/fertility context
- Water EC/pH → water-quality/fertigation context
- Pump state / tank level → operational event/context

## QA Default Rules (Physical Ranges & Anomalies)

- **Spikes:** 
  - `soil_moisture_vwc` jump > 0.15 in 15 mins → spike (unless supported by rain/irrigation).
  - `soil_temperature` jump > 5°C in 15 mins → spike.
  - `air_temperature` jump > 8°C in 15 mins → spike.
- **Flatline:** `N = 12` consecutive expected readings, or 6 hours for hourly sensors.
- **Ranges:** See physical ranges defined in `sensor_runtime/CONTRACT.md`. Values outside these boundaries are marked unusable unless explicitly overridden.
- **Quarantine:** Replayed payloads, impossible values, or severe flatlines must trigger quarantine behavior (no state updates, packets only).
