# Layer 0 — B2B-04B: Native Weather Provider HTTP Capture and CAS Binding

**Date:** 2026-11-04  
**Qualified Parent SHA:** `2323ad710062740aad7c3e7779bcf2a23e032e55` (PR #24, verified **589/589** exact-head test suite)  
**Published Milestone Head:** `60ebe35b23b706b167885f1069cd3da8f6df6c82` (609/609 passed baseline)  
**Branch:** `feat/layer0-weather-native-capture-20261104`  
**Status:** AUDIT REMEDIATION VERIFIED (616/616 passed)  
**Governing monograph & frozen records:** Scientific Pilot PR #9 (`71ee1f7`), `main` (`6edd372`), master monograph, and frozen `findings/layer0.md` remain completely untouched.

---

## 1. Parent Software Qualification Receipt

At parent commit `2323ad710062740aad7c3e7779bcf2a23e032e55`, full exact-head Windows Python 3.13.13 qualification was confirmed:
- Complete Layer 0: **484 / 484 passed** (18.80s via task-1912)
- Layer 1 Fusion: **21 / 21 passed** (0.66s)
- ASMAE Fast: **83 / 83 passed** (36.56s via task-1918)
- ASMAE Comprehensive Real-Raster: **1 / 1 passed** (659.39s / 10m 59s via task-1922)
- **Aggregate Total:** **589 / 589 distinct passed tests**, zero failures, zero skipped (715.41s total runtime).

This parent software qualification established robust descriptive role typing and archive-boundary admission. B2B-04B moves from descriptive labels to **verifiable source-native acquisition provenance**.

---

## 2. Architectural Scope and Boundaries

B2B-04B establishes:
1. **Immutable Weather Product Registry (`weather_product_registry.py`):**
   - Strictly defines allowed HTTPS endpoints, HTTP methods, required query parameters, schema validators, and authoritative dataset-role bindings.
   - **Open-Meteo Differentiation:**
     - Historical Reanalysis API: `https://archive-api.open-meteo.com/v1/archive` $\to$ `REANALYSIS_MODEL`
     - Live Forecast API: `https://api.open-meteo.com/v1/forecast` $\to$ `FORECAST_MODEL`
     - Historical Forecast Archive: `https://historical-forecast-api.open-meteo.com/v1/forecast` with historical dates or model runs $\to$ `HISTORICAL_FORECAST_MODEL` (stitched runs cannot claim a single initialization time)
   - **OpenWeather Differentiation:**
     - One Call 3.0: `https://api.openweathermap.org/data/3.0/onecall` $\to$ `FORECAST_MODEL` (for daily forecasts). One Call 2.5 is permanently deprecated as of June 2024.
     - Current Weather 2.5: `https://api.openweathermap.org/data/2.5/weather` $\to$ `CURRENT_PROVIDER_CONTEXT` (context snapshot only, never daily total)
     - Timemachine 3.0: `https://api.openweathermap.org/data/3.0/onecall/timemachine` $\to$ historical reanalysis/context
2. **Native HTTP Weather Acquisition Boundary (`weather_acquisition_boundary.py`):**
   - GET-specific capture adapter integrated with `DataRequestBroker` / `fetch_registry.py`.
   - Strips sensitive query parameters (`appid`, `api_key`, `key`, `token`, `secret`) before hashing or persisting request metadata.
   - Strict TLS validation, refusal of HTTP redirects (`allow_redirects=False`), and fail-closed timeout/error handling.
   - Rejects endpoints containing query strings (`?appid=...`), userinfo (`user:pass@`), or fragments (`#...`).
3. **Content-Addressed Evidence Store (`weather_evidence_store.py`):**
   - Retains exact raw HTTP response payload bytes and computes SHA-256 digest over raw bytes.
   - Domain-separated evidence identity: `EVIDENCE_DOMAIN = "akaloris/layer0/native-weather-acquisition-evidence/v1"`.
   - Immutable evidence manifest binding requested coordinates, valid interval, timezone, retrieval timestamp, credential-safe canonical query string, response byte count, and payload SHA-256.
4. **Weather Product Qualification (`weather_qualifier.py`):**
   - Verifies raw CAS response hash against stored evidence receipt and enforces exact field reconciliation against stored manifests.
   - Validates that returned coordinates match requested coordinates within provider grid tolerance ($\le 0.05^\circ$).
   - Reconciles returned date array with requested start and end dates.
   - Validates provider payload structures (enforces non-empty daily series for Open-Meteo, temporal range reconciliation within 3600s for OpenWeather Timemachine).
   - Derives dataset roles strictly from the verified product registry receipt, never from caller assertions or unverified JSON payloads.
   - Preserves true measured zero precipitation (distinguishing `0.0` from missing/unreported).
5. **Downstream Lineage Binding:**
   - Propagates verified acquisition evidence IDs into `WeatherDailyRecord`, `ObservationPacket`, Layer 0 wrappers, and ASMAE archives.
   - Maintains `source_qualified=False` (diagnostic provenance only; physical station observation authority and Kalman state-grant issuance remain separated for B2B-05/B2B-06).

---

## 3. Akaloris Code Audit Remediation (Findings 1–5)

1. **Finding 1 — Receipt Substitution Vulnerability Closed:**
   - Enforced `store.verified_cache_receipt(receipt.acquisition_id)` verification in `weather_qualifier.py`.
   - Validates all 11 acquisition-bound fields (`endpoint`, `sha256`, `byte_count`, `valid_start`, `valid_end`, `canonical_query_sha256`, etc.) directly against the immutable on-disk CAS manifest before accepting any receipt.
   - Fails closed with `"acquisition_receipt_manifest_mismatch"` on substituted response digests or object IDs.
2. **Finding 2 — Wire-Request Parameter Binding:**
   - Parses `response.request.url`, extracts and sanitizes transmitted query parameters in `weather_acquisition_evidence.py`.
   - Compares wire query against declared parameters (`_canonical_params_equal`).
   - Fails closed with `"prepared provider request query differs from acquisition claim"` on any parameter tampering or discrepancy.
   - Persists `wire_query_sha256` in the replay record.
3. **Finding 3 — Endpoint-Level Credential Leakage Prevention:**
   - Implemented `normalize_and_validate_endpoint()` in `weather_product_registry.py`.
   - Applied at product registration, boundary acquisition, and receipt verification.
   - Fails closed with `"endpoint_contains_embedded_query_string"` if query parameters (`?appid=...`), userinfo (`user:pass@`), or fragments (`#...`) are embedded in the endpoint URL.
4. **Finding 4 — Product Semantics & Structural Checks:**
   - Open-Meteo Historical Forecast host corrected to `https://historical-forecast-api.open-meteo.com/v1/forecast` (`HISTORICAL_FORECAST_MODEL`), separated from live forecast host `https://api.open-meteo.com/v1/forecast`. Live forecast endpoint strictly rejects historical dates.
   - Open-Meteo payload structural validation enforces presence of `daily.time` and non-empty time series, failing closed with `"missing_daily_time_series"`.
   - OpenWeather Timemachine reconciles `dt` within 3600s tolerance of requested start date, failing closed with `"weather_temporal_range_mismatch"`.
   - OpenWeather Current 2.5 and One Call 3.0 require coordinate blocks and valid data payload structures.
5. **Finding 5 — Downstream Lineage Binding & Wiring:**
   - `packetizer.py` emits `WEATHER_CONSENSUS_DAILY` with `daily_consensus.evidence_ids` in payload and provenance.
   - `observation_packet.py` adds `acquisition_ids: List[str]` to `Provenance`.
   - `wrappers.py` (`ensure_observation_packet` and `_canonical_weather_records`) preserves `native_acquisition_ids` and `acquisition_ids`.
   - `weather_archive_adapter.py` prioritizes verified `native_acquisition_ids` / `evidence_ids` over synthetic hashes.
   - `fetch_registry.py` wires native capture passthrough for live data requests.

---

## 4. What B2B-04B explicitly does NOT qualify

- **Physical station measurement:** An HTTP capture receipt proves authentic transport from a provider API, **not** an independently calibrated WMO weather station on the ground.
- **State-update grants:** Does not issue authorization for unsupervised Kalman state updates or Scientific Pilot PR #9 publication.
- **Plot IAM / MESIA containment:** Spatial ownership and containment authority remain the scope of milestone B2B-05.
- **Asymmetric KMS Issuer:** Cryptographic issuer keys remain isolated in milestone B2B-06.

---

## 5. Implementation Plan & Milestones

- [x] **B2B-04B-01:** Implement `weather_product_registry.py` with immutable contracts for Open-Meteo and OpenWeather.
- [x] **B2B-04B-02:** Implement `weather_acquisition_boundary.py` with GET capture, credential redaction, endpoint credential sanitization, and redirect prohibition.
- [x] **B2B-04B-03:** Implement `weather_evidence_store.py` with CAS retention, SHA-256 byte digests, and proof manifests.
- [x] **B2B-04B-04:** Implement `weather_qualifier.py` for spatial/temporal/product structural validation, cold-cache replay, and CAS manifest verification.
- [x] **B2B-04B-05:** Bind native acquisition evidence into `open_meteo.py`, `openweather.py`, `engine.py`, `packetizer.py`, and `weather_archive_adapter.py`.
- [x] **B2B-04B-06:** Construct comprehensive adversarial regression test suite (27 focused tests in `test_weather_native_acquisition.py`).

---

## 6. Exact-Head Software Qualification Receipt

Executed on local Windows environment (Python 3.13.13, pytest 9.0.3, pluggy 1.6.0):
- **Layer 0 Full Suite:** **511 / 511 passed** in 18.52s (task-2373)
  - Focused weather native capture tests: **27 / 27 passed**
- **Layer 1 Fusion:** **21 / 21 passed** in 0.73s
- **ASMAE Fast Suite:** **83 / 83 passed** (3 subtests) in 56.94s (task-2385)
- **ASMAE Comprehensive Real-Raster (EnKF):** **1 / 1 passed** in 413.12s (6m 53s via task-2389)
- **Aggregate Total:** **616 / 616 distinct passed tests**, 0 failures, 0 skipped (489.31s total runtime).



