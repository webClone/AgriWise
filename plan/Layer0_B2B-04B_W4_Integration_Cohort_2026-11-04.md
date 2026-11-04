# Layer 0 — B2B-04B W4 Weather Integration Cohort

**Starting revision:** `e4dfe2ffe3efefcfefa69e5462b656852da2445a`  
**Branch:** `fix/layer0-weather-integration-cohort-20261104`  
**Status:** VERIFIED & QUALIFIED (644/644 passed)

This cohort addresses the independent W4-01 through W4-09 weather findings.
It does not modify the master architecture monograph, frozen historical
`findings/layer0.md`, the scientific-pilot PR #9, or `main`.
Previously accepted S1/S2 producer/operator/tile contracts are not reopened.

## Vertical slice

`DataRequestBroker.get("open_meteo_archive")` → registered fetch →
approved HTTPS GET → CAS receipt and raw bytes → weather native QA →
broker CAS cache verification → environmental normalization of that **same
stored payload** → weather consensus and process forcing → packet provenance →
Layer 0 wrapper → ASMAE historical archive.

The historical reanalysis provider is the first native-integrated product;
OpenWeather and the forecast routes remain compatibility paths with no native
provenance guarantee. The application must not interpret a user-supplied
`native_acquisition_id` as a verified capture. If the native evidence root is
missing, historical legacy fetches are explicitly marked
`native_capture_status="unattested_legacy"`, with no native evidence ID.
If `AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE` is enabled, absence of the
evidence root fails closed across both fetch and cache boundaries. When configured,
stale legacy broker caches must refresh or return no attested native output.

## W4 gate implementation

- **W4-01:** First ordinary registered historical-weather path creates native
  capture in CAS. Engine verifies the immutable manifest and re-screens the
  stored original payload; forged IDs and altered broker caches are rejected.
- **W4-02:** Source/time classifier consumes every supported top-level/nested
  role, status, and denial carrier. Real ISO calendar validity is required;
  ASMAE must evaluate restrictions before flattening nested packets.
- **W4-03:** Native screen accepts only canonical internal daily units for
  requested variables and aligned finite nonboolean numeric values. Unsupported
  inches/Fahrenheit reject rather than mislabel. Missing required series
  reject instead of fabricating zero; unavailable rain cannot generate zero
  forcing. Existing unverified legacy routes remain outside this native screen.
- **W4-04:** Finite response coordinates, real sorted unique continuous daily
  calendar dates, aligned arrays and requested interval coverage are required.
- **W4-05:** Actual request *and response* schemes must be HTTPS, with matching
  sanitized wire queries. Provider exception bodies are not emitted into
  normal error messages or chained tracebacks.
- **W4-06:** Consolidation keys incorporate the complete nonsecret request
  identity (`start_date`, `end_date`, `param_hash`). Nearby plots requesting
  different temporal windows produce distinct batch keys, preventing cross-window
  batch consolidation and result substitution.
- **W4-07:** Strict native mode (`AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE=1`)
  is enforced at broker entry, cache-read, and return boundaries. An existing
  legacy cache hit cannot bypass native verification when the evidence root is absent.
- **W4-08:** Strict native mode is enforced at direct environmental ingestion.
  When enabled, `EnvironmentalEngine.process()` rejects and quarantines unattested
  weather inputs that lack verifiable native CAS acquisition records.
- **W4-09:** ASMAE archive adapter independently verifies claimed native acquisition
  IDs against CAS manifests before export. Directly submitted arbitrary IDs are
  discarded from native evidence exports and fall back to synthetic content hashes.

## Exact-Head Software Qualification Receipt

Executed locally on Windows environment (Python 3.13.13, pytest 9.0.3, pluggy 1.6.0):

| Test Suite | Scope | Result | Duration | Task Receipt |
| :--- | :--- | :--- | :--- | :--- |
| **Layer 0 Complete** | Full Layer 0 unit and integration suite | **539 / 539 passed** | 16.90s | `task-2651` |
| *W4 Integration Cohort* | Broker-to-archive, schema, unit, transport, W4-06..09 counterexamples | *28 / 28 passed* | 1.75s | `test_weather_integration_cohort.py` |
| *Native Acquisition* | Boundary, CAS, replay, manifest reconciliation | *27 / 27 passed* | 1.06s | `test_weather_native_acquisition.py` |
| *Role Isolation* | Descriptive classification & archive admission | *58 / 58 passed* | 0.54s | `test_weather_source_role_isolation.py` |
| **Layer 1 Fusion** | Layer 1 feature fusion & temporal alignment | **21 / 21 passed** | 0.67s | Synchronous |
| **ASMAE Fast** | Archive adapter, evidence ingestion, EnKF fast | **83 / 83 passed** (3 subtests) | 27.69s | `task-2657` |
| **ASMAE Comprehensive** | Full 365-day real-raster Sentinel-1/2, ERA5, EnKF | **1 / 1 passed** | 432.21s (7m 12s) | `task-2661` |
| **Aggregate Distinct Total** | **Zero failures, zero skipped** | **644 / 644 passed** | **477.47s** (7m 57s) | Complete Exact-Head Suite |
