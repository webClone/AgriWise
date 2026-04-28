# Layer 1 Fusion Context Engine — Contract

## Purpose

Layer 1 receives observation packages from Layer 0 and produces a
single deterministic **Layer1ContextPackage** for downstream layers.
It does **NOT** diagnose, recommend, or prescribe.

---

## Evidence Schema

Every raw observation enters the engine as an `EvidenceItem`:

| Field | Type | Description |
|-------|------|-------------|
| evidence_id | str | Unique identifier |
| plot_id | str | Plot this evidence belongs to |
| variable | str | What is being measured (e.g. `ndvi`, `soil_moisture_vwc`) |
| value | Any | The observed/measured value |
| unit | str | Must be in CANONICAL_UNITS or None |
| source_family | str | One of: sentinel2, sentinel1, environment, weather_forecast, geo_context, sensor, perception, user_event, history |
| source_id | str | Specific source identifier |
| observation_type | str | measurement, derived_feature, forecast, event, static_prior, diagnostic |
| spatial_scope | str | One of: plot, zone, point, edge, raster, regional |
| scope_id | str? | Zone ID, device ID, or raster ID |
| temporal_scope | str | Assigned by engine: instant, hourly, daily, 7d_trailing, etc. |
| observed_at | datetime | When the observation was taken |
| confidence | float | 0.0-1.0 |
| reliability | float | 0.0-1.0, source QA weight |
| freshness_score | float | 0.0-1.0, computed by freshness module |
| provenance_ref | str | Non-empty trace reference |
| diagnostic_only | bool | If True, not fused into state |
| state_update_allowed | bool | If False, cannot update fused state |
| flags | List[str] | Any flags (STALE, FORECAST_DAY_N, etc.) |

---

## Fusion Invariants

### Grouping Key

Evidence is fused into features using the 4-part key:

```
(variable, spatial_scope, scope_id, temporal_scope)
```

Two evidence items with different keys produce **separate** fused features.

### Weighted Average

When N items share a key:
- `value = sum(weight_i * value_i) / sum(weight_i)` where weight = confidence * reliability
- `confidence = max(confidence_i)` capped at 0.95
- `freshness = mean(freshness_i)`
- `source_evidence_ids = union of all evidence IDs`
- `source_weights = {family: sum(weights)}`

When 1 item has a key: passthrough with no averaging.

### 7 Canonical Feature Groups

| Group | Variables |
|-------|-----------|
| water_context | moisture, wetness, precip, rain, irrigation, water, whc, field_capacity, wilting |
| vegetation_context | ndvi, ndmi, ndre, evi, lai, vegetation, canopy, chlorophyll, bsi, bare_soil |
| phenology_context | gdd, stage, planting, emergence, harvest, senescence |
| stress_evidence_context | stress, frost, thermal, drought, flood, disease_weather, vpd |
| soil_site_context | soil_, elevation, slope, aspect, landcover, cropland, wapor |
| operational_context | user_, sensor_event, forecast_risk |
| data_quality_context | source_completeness, average_freshness |

---

## 13 Hard Prohibitions

Every prohibition is **computed** from package contents. Failure = gate rejection.

| # | Prohibition | Detection Logic |
|---|-------------|----------------|
| 1 | no_fake_fallback_evidence | Every evidence item has non-empty `provenance_ref` |
| 2 | no_diagnosis_or_recommendation | No FORBIDDEN_DIAGNOSIS_TERMS in any fused feature name or value |
| 3 | no_forecast_as_observation | Weather_forecast evidence has `observation_type` in {forecast, model_estimate, static_prior} |
| 4 | no_point_sensor_to_plot_truth_without_scope | No point-scope sensor evidence appears in plot-scope state feature source_evidence_ids |
| 5 | no_geo_context_as_crop_state | All geo_context evidence is `diagnostic_only=True` or `observation_type=static_prior` |
| 6 | no_weather_as_crop_diagnosis | No {disease, deficiency, prescription, diagnosis, blight} in weather/forecast variable names or values |
| 7 | no_wapor_as_plot_truth | All WaPOR evidence is `diagnostic_only=True` or `observation_type=static_prior` |
| 8 | no_unprovenanced_fused_feature | Every fused feature has `len(source_evidence_ids) > 0` |
| 9 | no_conflict_suppression | `resolver_diag.suppressed_conflicts == 0` AND `candidate == emitted` |
| 10 | no_unit_mismatch_allowed | Every evidence item has `unit` in CANONICAL_UNITS or None |
| 11 | no_spatial_scope_collapse | Every state feature's source evidence has matching `spatial_scope` |
| 12 | no_temporal_leakage_future_to_present | Non-forecast fused features contain no forecast evidence in source_evidence_ids |
| 13 | no_simulated_data_in_user_facing_context | No SIMULATED or SYNTHETIC flags in any feature or evidence |

---

## Conflict Types (9 canonical + SCOPE_MISMATCH)

| Type | Trigger |
|------|---------|
| SENSOR_VS_SAR_MOISTURE_CONFLICT | Sensor moisture vs SAR wetness proxy disagree |
| SENSOR_VS_WEATHER_RAIN_CONFLICT | Sensor rain vs weather station precipitation disagree |
| S2_VS_SENSOR_VEGETATION_CONFLICT | S2 NDVI vs sensor canopy greenness disagree |
| FORECAST_VS_OBSERVED_WEATHER_CONFLICT | Forecast precipitation vs observed precipitation disagree |
| WAPOR_ET_VS_LOCAL_WATER_BALANCE | WaPOR ET vs local sensor moisture disagree |
| GEO_BOUNDARY_CONTAMINATION_CONFLICT | Edge-scope evidence disagrees with plot-scope |
| USER_EVENT_VS_SENSOR_EVENT_CONFLICT | User-reported event contradicts sensor readings |
| S1_WETNESS_WITHOUT_RAIN_OR_IRRIGATION | SAR wetness detected without rain or irrigation evidence |
| S2_STRESS_WITH_ADEQUATE_WATER | S2 stress indicators with adequate sensor moisture |
| SCOPE_MISMATCH | Point and plot evidence for related variables disagree |

---

## Output Package

`Layer1ContextPackage` contains:

| Field | Type | Description |
|-------|------|-------------|
| plot_id | str | Plot identifier |
| run_id | str | Deterministic run identifier |
| generated_at | datetime | Timestamp of generation |
| time_window | TimeWindow | Analysis window (start, end, label) |
| spatial_index | SpatialIndex | Zones, points, edge regions, raster refs |
| fused_features | FusedFeatureSet | 7 groups of canonical fused features |
| evidence_items | List[EvidenceItem] | All accepted evidence items |
| conflicts | List[EvidenceConflict] | All detected conflicts |
| gaps | List[EvidenceGap] | All detected gaps |
| state_summary | StateSummary | Usability assessment |
| provenance | Layer1Provenance | Run metadata, input_package_ids: Dict[str, List[str]] |
| diagnostics | Layer1Diagnostics | Data health, prohibition results |
| content_hash() | str | SHA-256 of full deterministic serialization |

---

## Determinism Contract

Same `Layer1InputBundle` produces same `Layer1ContextPackage` produces same `content_hash()`.

- `content_hash()` delegates to `compute_package_hash()` which SHA-256s the full API serializer output
- All timestamps use explicit `run_timestamp`, no `datetime.now()` in the pipeline
- `_parse_date()` falls back to `run_timestamp`, not to wall clock
- Sets are sorted before serialization, floats rounded to 4 decimal places

---

## Gate Integration

The production gate runner (`run_production_gate.py`) proves prohibitions by:

1. Creating a representative 6-source fixture bundle (S2, S1, forecast, geo, sensor, user event)
2. Running it through `Layer1FusionEngine().fuse(bundle)`
3. Extracting `pkg.diagnostics.hard_prohibition_results`
4. Including computed results in the gate report
5. Running `evaluate_gate_rules()` against the report for final verdict

The gate report includes `production_gate_evaluation: { gate_passed, violations }`.

---

## Canonical Units

```
fraction, score, index, ratio, mm, mm/hr, degC, db,
cm, m, m/s, deg, hPa, W/m2, kg/m3, bool, count
```

## Canonical Spatial Scopes

```
plot, zone, point, edge, raster, regional
```
