# Layer 0 — B2B-04B W4 Weather Integration Cohort

**Starting revision:** `e4dfe2ffe3efefcfefa69e5462b656852da2445a`  
**Branch:** `fix/layer0-weather-integration-cohort-20261104`  
**Status:** DRAFT IMPLEMENTATION — TEST AND LIVE-PROVIDER QUALIFICATION PENDING

This cohort addresses the independent W4-01 through W4-05 weather findings.
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
evidence root fails closed. When configured, stale legacy broker caches must
refresh or return no attested native output.

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

## Qualification instructions

Run at the **final immutable head**, not at a parent SHA:

```powershell
py -m pytest -q services/agribrain/layer0/tests/test_weather_integration_cohort.py
py -m pytest -q services/agribrain/layer0/tests/test_weather_native_acquisition.py
py -m pytest -q services/agribrain/layer0/tests/test_weather_source_role_isolation.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

Also require one controlled **broker**, not just helper, path: a stale legacy
cache refreshes to CAS, raw bytes are re-screened, a true zero persists
and the exact acquisition ID reaches the archive. Test malformed daily arrays,
nonfinite/null coordinates, unit disagreement, masked forecast aliases,
invalid dates, HTTP schemes, offline outage and cold replay. Provider-network
smoke testing, deployment, pilot publication, KMS and field validation remain
separate open gates. No 616/616 inherited execution receipt qualifies these
new edits before actual reruns.
