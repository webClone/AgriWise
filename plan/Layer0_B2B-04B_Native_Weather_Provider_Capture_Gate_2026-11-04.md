# Layer 0 — B2B-04B: Native Weather Provider HTTP Capture and CAS Binding

**Date:** 2026-11-04  
**Qualified Parent SHA:** `2323ad710062740aad7c3e7779bcf2a23e032e55` (PR #24, verified **589/589** exact-head test suite)  
**Branch:** `feat/layer0-weather-native-capture-20261104`  
**Status:** IMPLEMENTATION PHASE; new-head tests pending  
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
     - Historical Forecast Archive: `https://api.open-meteo.com/v1/forecast` with historical dates or model runs $\to$ `HISTORICAL_FORECAST_MODEL` (stitched runs cannot claim a single initialization time)
   - **OpenWeather Differentiation:**
     - One Call 3.0: `https://api.openweathermap.org/data/3.0/onecall` $\to$ `FORECAST_MODEL` (for daily forecasts). One Call 2.5 is permanently deprecated as of June 2024.
     - Current Weather 2.5: `https://api.openweathermap.org/data/2.5/weather` $\to$ `CURRENT_PROVIDER_CONTEXT` (context snapshot only, never daily total)
     - Timemachine 3.0: `https://api.openweathermap.org/data/3.0/onecall/timemachine` $\to$ historical reanalysis/context
2. **Native HTTP Weather Acquisition Boundary (`weather_acquisition_boundary.py`):**
   - GET-specific capture adapter integrated with `DataRequestBroker` / `fetch_registry.py`.
   - Strips sensitive query parameters (`appid`, `api_key`, `key`, `token`, `secret`) before hashing or persisting request metadata.
   - Strict TLS validation, refusal of HTTP redirects (`allow_redirects=False`), and fail-closed timeout/error handling.
3. **Content-Addressed Evidence Store (`weather_evidence_store.py`):**
   - Retains exact raw HTTP response payload bytes and computes SHA-256 digest over raw bytes.
   - Domain-separated evidence identity: `EVIDENCE_DOMAIN = "akaloris/layer0/native-weather-acquisition-evidence/v1"`.
   - Immutable evidence manifest binding requested coordinates, valid interval, timezone, retrieval timestamp, credential-safe canonical query string, response byte count, and payload SHA-256.
4. **Weather Product Qualification (`weather_qualifier.py`):**
   - Verifies raw CAS response hash against stored evidence receipt.
   - Validates that returned coordinates match requested coordinates within provider grid tolerance ($\le 0.05^\circ$).
   - Reconciles returned date array with requested start and end dates.
   - Derives dataset roles strictly from the verified product registry receipt, never from caller assertions or unverified JSON payloads.
   - Preserves true measured zero precipitation (distinguishing `0.0` from missing/unreported).
5. **Downstream Lineage Binding:**
   - Propagates verified acquisition evidence IDs into `WeatherDailyRecord`, `ObservationPacket`, Layer 0 wrappers, and ASMAE archives.
   - Maintains `source_qualified=False` (diagnostic provenance only; physical station observation authority and Kalman state-grant issuance remain separated for B2B-05/B2B-06).

---

## 3. What B2B-04B explicitly does NOT qualify

- **Physical station measurement:** An HTTP capture receipt proves authentic transport from a provider API, **not** an independently calibrated WMO weather station on the ground.
- **State-update grants:** Does not issue authorization for unsupervised Kalman state updates or Scientific Pilot PR #9 publication.
- **Plot IAM / MESIA containment:** Spatial ownership and containment authority remain the scope of milestone B2B-05.
- **Asymmetric KMS Issuer:** Cryptographic issuer keys remain isolated in milestone B2B-06.

---

## 4. Implementation Plan & Milestones

- [ ] **B2B-04B-01:** Implement `weather_product_registry.py` with immutable contracts for Open-Meteo and OpenWeather.
- [ ] **B2B-04B-02:** Implement `weather_acquisition_boundary.py` with GET capture, credential redaction, and redirect prohibition.
- [ ] **B2B-04B-03:** Implement `weather_evidence_store.py` with CAS retention, SHA-256 byte digests, and proof manifests.
- [ ] **B2B-04B-04:** Implement `weather_qualifier.py` for spatial/temporal/product validation and cold-cache replay.
- [ ] **B2B-04B-05:** Bind native acquisition evidence into `open_meteo.py`, `openweather.py`, and `engine.py`.
- [ ] **B2B-04B-06:** Construct comprehensive adversarial regression test suite (`test_weather_native_acquisition.py`).
