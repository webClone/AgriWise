# Sensor Runtime V1 — Contract

This package is responsible for the messy real-world reality of IoT devices. Its sole purpose is to securely ingest, authenticate, decode, normalize, and store raw sensor data.

## Boundaries
1. **No Layer 0 Logic:** This package does NOT make scientific judgments. It does not know about crop models, Geo Context, or Kalman filters.
2. **Immutable Raw Data:** Raw payloads are never modified. They are stored with a unique `raw_payload_ref`.
3. **Canonical Normalization:** All vendor payloads must be mapped into canonical variables and canonical units before leaving this package.
4. **Deterministic Gate:** Testing of decoders and protocols relies exclusively on pure functions and isolated fixture payloads. No live network brokers or HTTP servers will be used in the test suite.

## Supported Canonical Variables & Units

Vendor payloads must be mapped to exactly one of these canonical variables and units:

### Soil
- `soil_moisture_vwc` (fraction 0.0–1.0)
- `soil_water_tension_kpa` (kPa)
- `soil_temperature_c` (°C)
- `soil_ec_ds_m` (dS/m)
- `soil_ph` (pH)

### Air / Microclimate
- `air_temperature_c` (°C)
- `relative_humidity_pct` (%)
- `dew_point_c` (°C)
- `vpd_kpa` (kPa)

### Rain
- `rainfall_mm` (mm)
- `rain_rate_mm_h` (mm/h)
- *Note:* Rain gauge accumulation semantics must be marked as `incremental`, `cumulative`, or `event_total`.

### Wind
- `wind_speed_ms` (m/s)
- `wind_gust_ms` (m/s)
- `wind_direction_deg` (degrees 0–360, must be circularized)

### Radiation
- `solar_radiation_w_m2` (W/m²)
- `par_umol_m2_s` (µmol/m²/s)

### Plant
- `leaf_wetness` (bool/fraction)
- `leaf_wetness_duration_min` (minutes)

### Irrigation / Operational
- `irrigation_flow_l_min` (L/min)
- `irrigation_volume_l` (L)
- `irrigation_pressure_bar` (bar)
- `pump_state` (bool/int)
- `tank_level_pct` (%)
- `water_ec_ds_m` (dS/m)
- `water_ph` (pH)
- `water_temperature_c` (°C)

### System
- `battery_voltage_v` (V)
- `battery_pct` (%)
- `signal_rssi_dbm` (dBm)
- `signal_snr_db` (dB)

## Physical Range Overrides (Applied in layer0)

While `sensor_runtime` decodes what the device sent, downstream `layer0` enforces these physical ranges unless a sensor-specific override exists:
| Variable | Valid Range |
|----------|-------------|
| `soil_moisture_vwc` | 0.0–0.75 |
| `soil_water_tension_kpa` | 0–2000 |
| `soil_temperature_c` | -20–70 |
| `soil_ec_ds_m` | 0–30 |
| `soil_ph` | 3–11 |
| `air_temperature_c` | -50–60 |
| `relative_humidity_pct` | 0–100 |
| `rainfall_mm` | ≥ 0 |
| `rain_rate_mm_h` | 0–500 |
| `wind_speed_ms` | 0–75 |
| `wind_gust_ms` | 0–100 |
| `wind_direction_deg` | 0–360 |
| `battery_pct` | 0–100 |

## Device Status & Interval Contract
Devices must declare an `expected_interval_seconds`.
- Health computes `OFFLINE` if `now - last_seen > expected_interval * 3`.
- Quarantine status applies for replayed payloads or unauthorized device IDs.
