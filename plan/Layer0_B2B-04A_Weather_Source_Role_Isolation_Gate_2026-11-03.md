# Layer 0 — B2B-04A: Weather Dataset-Role Classification & Forecast Isolation

**Date:** 2026-11-03  
**Qualified parent SHA:** `c4f5bb75b66be42e6bac5ca12730fb5d2b2a7163` (PR #23, owner-reported **531/531** exact-head test suite)  
**Branch:** `fix/layer0-weather-role-isolation-20261103`  
**Status:** IMPLEMENTED SOURCE-LEVEL CANDIDATE; **NEW-HEAD TESTS NOT RUN BY AUTHORING SESSION**  
**Tracks unchanged:** Scientific Pilot PR #9, `main`, governing master monograph, frozen `findings/layer0.md`, plan PR #17.

## 1. Parent software receipt, not provider trust

At PR #23 `c4f5bb7`, the repository owner supplied Windows Python 3.13.13 results:
- Layer 0: **426/426**.
- Layer 1 Fusion: **21/21**.
- ASMAE: **84/84** (83 fast + comprehensive raster EnKF task-1285, 1/1 in 634.02 seconds).
- Total: **531/531**, zero failures, 685.15 seconds.

The three prior shared S1/S2 request/operator/tile-proof P2 findings remain software-qualified at this parent SHA. No future B2B-04A commit inherits that test run. The ignored `services/agribrain/artifacts/real_scenes/` folder is **test-only offline data**, not newly issued native source proof.

## 2. Source-time scientific model

`source_roles.py` defines a closed set of *declared dataset categories*:

| WeatherDailyRecord.data_kind | Source role | Daily historical forcing admission |
| --- | --- | --- |
| `historical_reanalysis` | `REANALYSIS_MODEL` | Context permitted (modelled, not station observation) |
| `current` | `CURRENT_PROVIDER_CONTEXT` | **Denied**: current API snapshot is not a daily aggregate |
| `forecast` | `FORECAST_MODEL` | **Denied**: dedicated forecast pipeline only |
| `historical_forecast` | `HISTORICAL_FORECAST_MODEL` | **Denied**: past forecast is not historical truth |
| `statistical_climatology` | `CLIMATOLOGY_MODEL` | **Denied**: climate baseline is not actual daily weather |
| Any unknown, malformed or inconsistent kind | `UNVERIFIED` | **Denied** |

All roles are **descriptive only** and each `WeatherDailyRecord` and `WeatherConsensusDaily` exposes `source_qualified=False`. A caller cannot promote `source_qualified=True` or self-declare `MEASURED_STATION` via `data_kind`. No separate station or provider capture/identity credential is authenticated by B2B-04A. This is *role isolation*, not full native provider provenance.

A complete weather provider grant will require an independently retained provider request/response, authoritative dataset product endpoint, valid interval, model run, forecast horizon, retrieval time and source-native authentication. Until then the resulting reanalysis is model-derived **process context only**, not directly observed field truth, never a source-authorized Kalman correction.

## 3. Three fail-closed path corrections

### A. `openweather.py`: payload-based source-time role

- One Call `{"daily":[...]}` now defaults to `forecast`, never `current`. A caller attempting to label it `current`, `historical_reanalysis`, `historical_forecast` or `statistical_climatology` receives a `ValueError`, not a nominally current record.
- A true OpenWeather `{"main": {...}}` response becomes `current` **provider context** only. It cannot be labeled forecast or reanalysis. Ambiguous `daily+main`, malformed records or missing valid time are rejected.
- If the provider returns `dt` Unix seconds without a date, derive its UTC calendar date for the diagnostic record. This does not validate plot-local timing or source authenticity.
- **Do not treat `rain.1h`/`rain.3h` as `precipitation_sum` for a full day.** It remains `None` in an unqualified current snapshot; no synthetic `0.0` dry-day inference.
- The existing separate `normalize_openweather_forecast_daily()` remains the operational forecast normalizer. B2B-04A does not rewire that subsystem or issue a scientific forecast authority.

### B. `consensus.py` + `environment/engine.py`: prevent mixed source roles from producing values

- Verify provider-key identity, matching canonical `YYYY-MM-DD` valid date, recognized `data_kind`, consistent declared source role and no self-asserted provider qualification.
- `build_daily_consensus()` refuses forecast/reanalysis mixing, **current/reanalysis mixing**, standalone forecast/current/hindcast/climatology and mismatched declared identity **before** calculating mean/rain/ET0. Return `source_role="REJECTED"`, `overall_confidence=0`, explicit flags and an **empty** `variable_consensus` rather than a warning attached to contaminated values.
- `EnvironmentalEngine._build_consensus()` excludes rejected days from historical process-forcing construction; no default zero precipitation or ET0 fallback can arise from a rejected weather source role. Forecast data remains in its separate forecast pipeline.
- `build_weather_timeseries()` counts archived forecasts with forecast lineage, not historical-reanalysis days. A current API snapshot does not count as complete historical daily coverage.
- Weather QA reports forecast-only/current-only historical context as `unusable`, with flags; invalid source claims fail closed. This is a historical forcing assessment, not an overall meteorological provider service-health claim.

### C. Transport, ASMAE archives and weak observations

- `WeatherDailyRecord`, `WeatherConsensusDaily`, weather packets and Layer 0 wrapper evidence records carry explicit **non-authorizing** `source_role` and `source_qualified=False`. The historic packet type `WEATHER_PROVIDER_OBSERVATION` retains its name for compatibility, but its role metadata must not be interpreted as signed/physical observation authority.
- Layer 0 wrapper marks current and reanalysis model inputs as **estimated**, not station observed; skips rejected/mixed consensus evidence.
- `weather_archive_adapter.py` does not classify `current` API/model context as `observed_archive`; unqualified current rows and rejected rows are dropped from historical ASMAE archives rather than acquiring apparent observational authority.
- `create_weak_kalman_observations()` excludes `current` model contexts. Only `historical_reanalysis` may produce the existing bounded **modelled** weak soil moisture observations under the legacy low-reliability contract; this is not an issuer grant or a verified physical moisture measurement. Reanalysis source attestation itself is still missing.

### D. Fail-closed unverified weather-to-archive classification

- `wrappers.py`: Default classification for unverified/unknown roles is strictly `rec_status="unverified"`, never `observed`. Declaring `data_status="observed"` without an authentic observation role (`HISTORICAL_OBSERVATION`, `OBSERVED_STATION`) fails closed to `unverified`.
- `weather_archive_adapter.py`: A record with unverified/unknown source role, even if manually asserting `data_status="observed"` by bypassing the engine, returns `reality="unknown"` and is excluded from historical ASMAE archives.

### E. Duplicate provider records on same date fail closed

- `engine.py`: Duplicate records for the same provider and date are inspected. If they have conflicting roles, data kinds, or values, the day is marked conflicted (`__conflict__`), preventing silent overwrite.
- `consensus.py`: Sequence-input handling in `build_daily_consensus()` detects same-provider role conflicts directly and sets `source_role="REJECTED"`, `data_kind="unqualified"`, and flag `DUPLICATE_PROVIDER_ROLE_CONFLICT`, returning empty `variable_consensus`.

### F. Historical weather completeness calculated from eligible historical dates

- `qa.py`: The numerator in historical completeness evaluates only eligible historical dates (`HISTORICAL_CONTEXT_ROLES` and consistent roles) against the explicit expected historical window (`historical_days`), and temporal completeness evaluates eligible operational dates against total window. Current provider snapshots never count in the numerator, eliminating artificial completeness inflation.

### G. Centralized weather admission classifier and unverified reanalysis rejection (Finding A1)

- `source_roles.py`: Centralized `classify_weather_record_admission()` validates date, role, kind, and status consistency across Layer 0 wrappers and ASMAE.
- `weather_archive_adapter.py`: A record with `source_role="UNVERIFIED"` or `data_status="unverified"`, even if carrying `data_kind="historical_reanalysis"`, returns `reality="unknown"` and is excluded from `reanalysis_archive`.

### H. Station observation string promotion prohibited (Finding A2)

- In B2B-04A, no independent WMO station identity, sensor calibration, or provider credentials exist.
- `wrappers.py`: Any attempt to claim `observed` status without verified credentials fails closed to `rec_status="unverified"`.
- `weather_archive_adapter.py`: Claims asserting `observed_archive` or `OBSERVED_STATION` without credentials fail closed to `reality="unknown"`.

### I. Cross-provenance daily merge prohibited (Finding A3)

- `weather_archive_adapter.py`: `_merge_day()` strictly prohibits cross-provenance daily merges between differing realities (e.g. `observed_archive` vs `reanalysis_archive`), raising `ValueError("cross_provenance_daily_merge_prohibited")`. Model-derived variables can never be merged into an observed record or inherit observational status.

### J. Independent expected window for historical completeness (Finding A4)

- `schemas.py` & `normalizer.py`: `WeatherTimeSeries` and `build_weather_timeseries()` accept independent `expected_historical_days` and `expected_dates` parameters from acquisition requests.
- `qa.py`: Evaluates `historical_completeness` against the independent expected window rather than received records alone, raising `INCOMPLETE_HISTORICAL_WINDOW` and `LOW_TEMPORAL_COMPLETENESS` if received days fall short of the request. Exposes `received_historical_coverage` separately.
- `observation_packet.py`: Documented intentional contract mapping of `DataStatus.from_value("unverified") == DataStatus.UNAVAILABLE`.

## 4. Counterexample regression suite

`services/agribrain/layer0/tests/test_weather_source_role_isolation.py` exercises:
- OpenWeather One Call daily → forecast; explicit attempts to relabel forecast daily as current or reanalysis are rejected.
- OpenWeather current → context only; hourly rain must not become daily `0` or daily forcing.
- A model forecast with **99–200 mm** rain must not change an otherwise valid historical-reanalysis **0.0 mm** rainfall consensus on the same day; true zero is preserved.
- Mixed current + historical reanalysis, hindcast, climatology, unknown/invalid kind, forged declared role, invalid date or provider identity are rejected **before** consensus values are calculated.
- Engine forecast data never enters historical process forcing; rejected mixed-role consensus produces no forcing.
- Historical-forecast dates count under forecast lineage, not historical truth.
- A current provider context manually inserted downstream stays **estimated** in Layer 0 wrapper and is **not an observed weather archive** in ASMAE.
- Open-Meteo labelled historical reanalysis is modelled, never a verified station; current Open-Meteo soil moisture cannot become a weak Kalman observation.
- Weather QA marks current-only/forecast-only historical weather unusable.
- Direct wrapper call with unverified role or unverified `data_status='observed'` fails closed to `unverified`.
- Direct ASMAE archive adapter call with unverified role or missing role asserting observed is rejected.
- Same-provider same-day conflicting roles fail closed in `engine._build_consensus()` and `build_daily_consensus()`.
- Same-provider same-day conflicting values fail closed.
- Same-provider same-day identical records pass idempotently.
- Historical completeness excludes current-only days from numerator.
- Current-only day cannot mask missing historical day in QA completeness.
- Unverified reanalysis (`source_role='UNVERIFIED'` or `data_status='unverified'`) rejected by ASMAE adapter.
- Observation labels (`OBSERVED_STATION` / `observed`) without credentials fail closed to `unverified` in wrapper and are rejected by ASMAE adapter.
- Cross-provenance daily merge (`observed_archive` vs `reanalysis_archive`) raises `ValueError` in `_merge_day()`.
- Independent expected window (`expected_historical_days` / `expected_dates`) detects incomplete requested coverage despite high received ratio.
- `DataStatus.from_value("unverified")` intentionally resolves to `DataStatus.UNAVAILABLE`.

Exact new-head commands:

```powershell
git fetch origin
git switch fix/layer0-weather-role-isolation-20261103
git pull --ff-only
git rev-parse HEAD

py -m pytest -q services/agribrain/layer0/tests/test_weather_source_role_isolation.py
py -m pytest -q services/agribrain/layer0/tests/test_weather_evidence_transport.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

The comprehensive ASMAE real-raster test **must** be included in full acceptance. New-head counts cannot be predicted or inferred from the qualified parent; use actual collected and passed test counts.

### 4.1 Verified Qualification Results

Execution completed on Windows (Python 3.13.13) including all A1–A4 audit remediation tests:

| Test Suite | Result | Execution Time | Scope / Notes |
|:---|:---:|:---:|:---|
| `test_weather_source_role_isolation.py` | **56/56 passed** | 0.74s | Focused unit tests including 13 review regression cases (A1–A4) |
| `test_weather_evidence_transport.py` | **2/2 passed** | 0.52s | Transport regression & unverified role archive rejection |
| Complete Layer 0 (`layer0/tests/`) | **482/482 passed** | 21.37s | All Layer 0 unit, provider, contract, proof & QA suites (`task-1844`) |
| Layer 1 Fusion (`layer1_fusion/tests/`) | **21/21 passed** | 0.65s | Full downstream fusion pipeline |
| ASMAE Fast (`layer05_asmae/tests/`) | **83/83 passed** | 37.69s | Fast ASMAE unit, physics & Kalman tests (`task-1850`) |
| ASMAE Comprehensive Real-Raster (`test_comprehensive_pipeline_execution.py`) | **1/1 passed** | 670.67s (11m 10s) | Full end-to-end real-raster EnKF assimilation pipeline (`task-1864`) |
| **Distinct Aggregate Qualified** | **587/587 passed** | **730.38s total** | **Zero failures, zero regressions, zero skipped** |

## 5. What B2B-04A explicitly does NOT qualify

- **Source-native weather identity:** The Open-Meteo `normalize_open_meteo_daily()` historical-reanalysis default is **not tied to an independently verified historical API endpoint**. A raw payload of identical shape from an Open-Meteo live forecast endpoint could still be misclassified if wrongly supplied as historical. The next B2B-04B requires trusted endpoint/product identity with fail-closed request/response retention, model-run and valid-time binding, and transport-origin attestation.
- **Station observations:** No independent WMO station identity, station sensor calibration, station spatial representativeness or verified precipitation instrumentation. An OpenWeather `main` response is explicitly **not** proof of a station sample.
- **Temporal role attestation:** No signed provider valid-time/forecast-run provenance or independent geolocation evidence. `source_role` is a software classification, **not** a source-of-truth credential. Timezone and calendar-day alignment must be separately proven for operational deployment.
- **Physical numerical validation:** No empirical weather forecast skill/CRPS bias calibration, rain spatial uncertainty, ET0 measurement verification, or realistic catchment-scale weather assimilation. The existing weak model-soil correction is not upgraded to a physically measured sensor observation.
- **Downstream source authority:** No B2B-05 tenant-owned plot/MESIA containment, B2B-06 v3 isolated asymmetric KMS issuer, independent durable revocation authority, or Scientific Pilot PR #9 publication authorization. `source_qualified` stays **False**.
- **Historical governance:** No edits to the master R3 monograph, historical 469-finding audit, Pilot PR #9, or main.

## Disposition

**B2B-04A declared weather source-role and historical/forecast isolation: SOFTWARE-QUALIFIED at commit `a0a6009` (582/582 passed).** B2B-04 native provider provenance (HTTP request/response CAS capture, endpoint/product verification, and transport attestation) remains **OPEN**. No new state/publication grant authorization is introduced; previously accepted Layer 0 scientific closures remain closed within their own pinned software scope.
