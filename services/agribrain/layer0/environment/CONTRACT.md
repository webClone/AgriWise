# Environmental Context Engine V1 Contract

## Source Roles

| Source | Role | Resolution | Kalman usage |
|--------|------|-----------|-------------|
| SoilGrids (ISRIC) | Fine soil property prior | 250 m | Process model parameters — NOT daily observations |
| FAO/HWSD v2.0 | Coarse soil/ecological fallback + classification | ~1 km | Static context — risk flags, classification |
| Open-Meteo | Primary ag-weather + ET₀ provider | Point-based | Process forcing + weak modelled soil moisture obs |
| OpenWeather | Current/forecast cross-check | Point-based | Consensus input — never independent Kalman truth |

## SoilGrids V1 Properties (11 core)

| Property | SoilGrids ID | Raw unit | Conversion | Output unit |
|----------|-------------|----------|-----------|-------------|
| Bulk density | bdod | cg/cm³ | ÷ 100 | kg/dm³ |
| Clay content | clay | g/kg | ÷ 10 | % |
| Silt content | silt | g/kg | ÷ 10 | % |
| Sand content | sand | g/kg | ÷ 10 | % |
| Coarse fragments | cfvo | cm³/100cm³ | ÷ 10 | vol% |
| Soil pH (H₂O) | phh2o | pH × 10 | ÷ 10 | pH |
| Soil organic carbon | soc | dg/kg | ÷ 10 | g/kg |
| Cation exchange capacity | cec | mmol(c)/kg | ÷ 10 | cmol(c)/kg |
| Total nitrogen | nitrogen | cg/kg | ÷ 100 | g/kg |
| Water content at 33 kPa | wv003 | 0.1 vol% | ÷ 10 | vol% |
| Water content at 1500 kPa | wv1500 | 0.1 vol% | ÷ 10 | vol% |

### Canonical naming rule
The canonical property ID is `wv003`, not `wv0033`. If external data uses `wv0033`,
the normalizer MUST map it to `wv003`.

### V1 optional (not required for engine to function)
`wv0010`, `ocd`, `ocs`

### SoilGrids Depth Intervals
| Depth | Label |
|-------|-------|
| 0–5 cm | sl1 |
| 5–15 cm | sl2 |
| 15–30 cm | sl3 |
| 30–60 cm | sl4 |
| 60–100 cm | sl5 |
| 100–200 cm | sl6 |

### Label rule
SoilGrids values are `soil_prior`, NEVER `soil_measurement`.

## AWC Calculation

```
awc_volumetric_proxy = wv003 - wv1500  (vol%)
awc_mm_layer = (wv003 - wv1500) / 100 × layer_thickness_mm × fine_earth_fraction
fine_earth_fraction = 1 - (cfvo / 100)
```

Coarse-fragment correction is REQUIRED. Stony soils must not appear to hold too much water.

Root-zone AWC outputs: `root_zone_awc_mm_0_30`, `root_zone_awc_mm_0_60`, `root_zone_awc_mm_0_100`

## Texture Consistency Rule
`clay + silt + sand ≈ 1000 g/kg` (raw) or `≈ 100%` (converted).
Tolerance: ±5%.

## SoilGrids QA

| Class | Condition |
|-------|-----------|
| GOOD | All 11 properties present, depth complete, texture consistent, uncertainty moderate |
| DEGRADED | Missing water properties (wv003/wv1500) OR high uncertainty (Q95-Q05)/mean > 0.5 |
| UNUSABLE | No profile, invalid coordinates, impossible texture values |

## FAO/HWSD Rules

- FAO/HWSD v2.0 uses 7 depth layers: 0–20, 20–40, 40–60, 60–80, 80–100, 100–150, 150–200 cm
- These do NOT align to SoilGrids 6-depth intervals
- FAO provides classification, fallback, risk flags — NOT numeric overrides of good SoilGrids
- FAO resolution always marked as ~1000m

## Weather Data Kind

Every weather record MUST have a `data_kind`:
```
current              — real-time observation/estimate
forecast             — forward-looking model prediction
historical_reanalysis — past period reanalysis (e.g., ERA5-based)
historical_forecast  — archived model forecast
statistical_climatology — long-term statistical average
```

**Hard rule**: forecast MUST NOT be mixed with historical truth in the same
daily consensus value.

## Weather Consensus Rules

Consensus is **per-day, per-variable** (not global).

### Temperature
- Average if providers agree within 2°C → confidence HIGH
- Disagreement > 3°C → confidence LOW

### Rainfall
- Both near zero → confident dry
- One high, one zero → `LOCAL_RAIN_UNCERTAIN`, confidence LOW
- Both high → confident rain event
- Rainfall uncertainty is HIGH by default (spatial instability)

### ET₀
- Prefer Open-Meteo ET₀ if available
- Fallback: Hargreaves approximation (temperature-only)
- Full FAO-56 Penman-Monteith deferred to V1.1

## Packet Types (10)

| Packet | Emitted when |
|--------|-------------|
| SOILGRIDS_PROFILE_PRIOR | Soil provider available |
| SOILGRIDS_DERIVED_HYDRAULICS | Profile available |
| FAO_SOIL_CONTEXT | FAO provider available |
| FAO_AGROECOLOGICAL_CONTEXT | FAO data available |
| WEATHER_PROVIDER_OBSERVATION | Per provider |
| WEATHER_CONSENSUS_DAILY | After consensus |
| WEATHER_FORCING_DAILY | After derived features |
| WEATHER_FORECAST | Forecast available |
| WEATHER_DERIVED_FEATURES | GDD, water balance, flags |
| ENVIRONMENT_PROVENANCE | Always |

### Partial failure rule
- All providers fail → ENVIRONMENT_PROVENANCE + diagnostics only
- Individual provider fails → emit failure diagnostic for that provider, continue with available providers
- SoilGrids fails + weather succeeds → still emit weather packets
- OpenWeather fails + Open-Meteo succeeds → still emit consensus (lower redundancy)

## State Adapter Rules (not kalman_adapter)

### Process model parameterization (V1 produces, V1.1 wires)
SoilGrids AWC/texture → `ProcessParameters`:
- field_capacity, wilting_point, whc_mm_per_m
- drainage_coefficient, infiltration_capacity
- root_zone_storage_mm

### Process forcing
Weather consensus → `ProcessForcing` (typed dataclass):
- date, gdd, precipitation_mm, effective_precipitation_mm, et0_mm
- vpd_kpa, radiation_mj_m2, thermal_stress_flag, frost_flag
- water_balance_mm, rainfall_confidence, weather_confidence

### Weak Kalman observations (modelled soil moisture)
| Source | Obs key | State maps to | σ | Reliability ceiling |
|--------|---------|--------------|---|---------------------|
| Open-Meteo SM 0–1cm | open_meteo_sm_0_1 | sm_0_10 | 0.15 | 0.35 |
| Open-Meteo SM 1–3cm | open_meteo_sm_1_3 | sm_0_10 | 0.15 | 0.35 |
| Open-Meteo SM 3–9cm | open_meteo_sm_3_9 | sm_10_40 | 0.18 | 0.30 |
| Open-Meteo SM 9–27cm | open_meteo_sm_9_27 | sm_10_40 | 0.18 | 0.30 |

Conditions for emission:
- data_kind must be current/historical_reanalysis (NOT long-lead forecast)
- temporal completeness acceptable
- weather consensus does not flag provider-wide failure
- labeled as `modelled_soil_moisture`, never `soil_moisture_observation`

27–81 cm layer: optional deep context, NOT mapped to Kalman state in V1.

### NOT allowed
- Weather provider → direct canopy_stress Kalman update
- SoilGrids/FAO → daily Kalman observations

## Provenance (mandatory)

### Required fields
- `latitude`, `longitude`, `coordinate_crs`
- `soilgrids_version`, `soilgrids_access_method` (mocked_fixture / wcs_tile / rest_api)
- `fao_dataset_name`, `fao_dataset_version`, `fao_resolution_m`
- `weather_providers` (list), `weather_model_or_product`, `weather_run_time`
- `timezone`
- `retrieval_timestamp`

Missing coordinates → fatal `EnvironmentalProvenanceError`.
