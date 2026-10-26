# AgriBrain Four-Owner Cohort Delivery & Track A Blocker Remediation Walkthrough

**Pinned Baseline Revision:** `f041a8f` / `730b9fe` · 26 October 2026  
**Branch:** `feat/f36-t09-asmae-13-state-publication`  
**Governing Decision:** Advance Four-Owner Cohort simultaneously across Track A (Demonstrated Blockers) and Track B (Dependency-Ready Package Criteria); ASMAE A+B corrective cycle remains closed within verified software scope.

---

## 1. Executive Metric Summary

| Metric | Status / Value | Audit Reconciliation |
|---|---|---|
| **Overall Estimated Achievement** | **32%** | Unchanged (285 register checkboxes open across 52 packages) |
| **Immediate Cohort Maturity** | **54%** | 16 selected cohort packages across 4 delivery lanes |
| **Formal Package Acceptance** | **0 / 52** | Intentionally 0/52; formal sign-off requires integrated acceptance |
| **ASMAE A+B Corrective Cycle** | **Closed** | Closed within verified software scope (no reopening) |
| **Four-Owner Cohort Execution** | **Active** | Advancing parallel lanes with unified schema contracts |

---

## 2. Four-Owner Cohort Delivery Architecture

The cohort delivery model organizes 16 high-leverage packages under four parallel delivery lanes:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                FOUR-OWNER COHORT MATRIX                                │
├─────────────────────────┬─────────────────────────┬────────────────────────────────────┤
│ Lane                    │ Existing Packages       │ Responsibilities                   │
├─────────────────────────┼─────────────────────────┼────────────────────────────────────┤
│ 1. Foundation & Ingress │ F37, F01, F02           │ Ingress admission, namespaces,     │
│                         │                         │ calibration & temporal cutoffs     │
├─────────────────────────┼─────────────────────────┼────────────────────────────────────┤
│ 2. Trajectory & Storage │ F03, F04, F06, F07,     │ Mass-conserving water balance,     │
│                         │ F08, F09, F39           │ parameter precision, cache digests │
├─────────────────────────┼─────────────────────────┼────────────────────────────────────┤
│ 3. Execution & Safety   │ F16, F17, F18, F19      │ Physical stop contracts, watchdogs,│
│                         │                         │ quotas, unconfirmed stop ownership │
├─────────────────────────┼─────────────────────────┼────────────────────────────────────┤
│ 4. Acquisition & EO     │ F25, F26                │ True backend provenance, spatial   │
│                         │                         │ tile hash collision resistance     │
└─────────────────────────┴─────────────────────────┴────────────────────────────────────┘
```

---

## 3. Track A: Demonstrated Blocker Remediation Summary

### Lane 4: Acquisition — F25 & F26 Model Identity, Tile Hash Precision, and Tensor Alignment
* **File:** `services/agribrain/layer1_fusion/eo_foundation_model.py`
* **Remediation:**
  - `_infer_onnx` returns `None` on runtime errors, enabling `infer()` to catch the fallback condition, set `actual_backend = "spectral_basis_v2"`, assign `model_id = actual_backend`, and apply the fallback confidence ceiling `0.75`.
  - Replaced lossy 4-decimal float formatting with exact IEEE-754 `float(v).hex()` serialization in `_compute_tile_hash()`.
  - Tile hash now binds CRS, affine transform, and preprocessing version (`f"crs:{crs}|xform:{xform}|prep:{prep}"`) in addition to spatial dimensions and cloud masks.
  - Added strict multi-band `(H, W)` alignment check in `infer()`, raising `ValueError("band_dimension_mismatch")` if band grids or cloud masks mismatch.
  - Bound `model_version="1.0.0"` and `preprocessing_version="2.0.0"` into `EmbeddingResult`.

### Lane 2: Trajectory & Persistence — F39 Multi-Worker Storage Durability
* **Files:**
  - `services/agribrain/sensor_runtime/storage.py`
  - `services/agribrain/sensor_runtime/ingestion.py`
* **Remediation:**
  - Implemented cross-process atomic exclusive create with `os.O_CREAT | os.O_EXCL` in `store_raw_message()`, preventing race condition overwrites and ensuring true immutability.
  - Replaced lossy ID stripping with strict `_validate_and_encode_id()` that rejects path traversal sequences (`..`, `/`, `\`) and invalid characters.
  - Coordinated append-only writes to `normalized_readings.jsonl` using inter-process lock files (`_acquire_and_append()`).
  - Added in-memory list clearing in `rehydrate_storage()` and `clear_storage()` to prevent duplicate record accumulation across re-reads.
  - Connected `store_normalized_reading(r)` inside `sensor_runtime/ingestion.py`.

### Lane 3: Execution & Safety — F16, F17, F18 Physical Stop Contracts & Evidence Verification
* **Files:**
  - `services/agribrain/irrigation_runtime/schemas.py`
  - `services/agribrain/irrigation_runtime/drivers/modbus_driver.py`
  - `services/agribrain/irrigation_runtime/drivers/http_driver.py`
  - `services/agribrain/irrigation_runtime/drivers/mqtt_driver.py`
  - `services/agribrain/irrigation_runtime/actuator.py`
  - `services/agribrain/irrigation_runtime/dispatcher.py`
* **Remediation:**
  - `_read_feedback()` in Modbus driver returns `(Optional[float], Optional[float])`, yielding `None` on missing registers rather than fabricating `0.0`. Stop commands require affirmative evidence (`actual_flow == 0.0 and running_bit == 0`); missing registers leave `transport_acknowledged_only=True, confirmed_physical_stop=False`.
  - HTTP and MQTT drivers return `transport_acknowledged_only=True, confirmed_physical_stop=False` when physical proof of cessation is absent from response payloads.
  - Fixed parameter dictionary collision in `http_driver.py` `_build_url()`.
  - Implemented restricted `confirm_stop(receipt)` on `IrrigationActuator` and `confirm_stopped_event(event_id, receipt)` on `CommandDispatcher`, requiring a dictionary with valid device and zero-flow evidence to release ownership to `ONLINE`.
  - Updated `dispatcher.py` across `cancel_event`, `emergency_stop_all`, safety violations, and restart recovery so transport success (`stop_res.success`) is never treated as physical cessation when `transport_acknowledged_only=True` or `actuator.status == STOP_PENDING_CONFIRMATION`.

### Lane 1: Foundation & Temporal — F01, F02, F06, F37 Namespace Integrity & Prospective Weather Cutoffs
* **Files:**
  - `services/agribrain/sensor_runtime/__init__.py`
  - `services/agribrain/layer3_decision/runner.py`
  - `services/agribrain/sensor_runtime/calibration.py`
* **Remediation:**
  - Installed `_SensorRuntimeNamespaceBridge(MetaPathFinder)` into `sys.meta_path` guaranteeing `reg.__class__ is SensorDeviceRegistration` regardless of import ordering between `sensor_runtime` and `services.agribrain.sensor_runtime`.
  - Enforced `issued_at <= step_limit_ts` in `_is_weather_issuance_eligible()`, rejecting prospective/future weather observations while admitting unversioned date records when `date <= step_limit_ts.date()`.
  - Scoped checkpoint fallback in Layer 3 with `cycle_id` and `geometry_version`, ensuring fallback selections never cross crop cycles or field boundary versions.

---

## 4. Track B: Post-Audit Integrations S, D, E Remediation Summary (Commit `3687d65` Findings)

### Integration S: Physical Execution Authority (P1 — F16, F17, F18, F19)
* **Files:**
  - `services/agribrain/irrigation_runtime/dispatcher.py`
  - `services/agribrain/irrigation_runtime/actuator.py`
  - `services/agribrain/irrigation_runtime/drivers/modbus_driver.py`
  - `services/agribrain/irrigation_runtime/drivers/http_driver.py`
  - `services/agribrain/irrigation_runtime/drivers/mqtt_driver.py`
* **Remediation:**
  - **Restart Reconciliation & STOP Retry Authority:** Closed transport-success shortcuts across `reconcile_on_restart`, `check_execution_status`, `emergency_stop_all`, and `emergency_stop_event` via centralized `_is_stop_confirmed(actuator, stop_res)`. Stop commands require affirmative verified physical stop (`confirmed_stop`) and cannot advance to `CANCELLED` or release quota on transport ACK alone.
  - **Stop-Pending State in Actuator Core:** In `actuator.py` `_execute_stop_direct`, real transport protocols (`MODBUS`, `HTTP`, `MQTT`, `LORAWAN`) with unconfirmed physical stop enter `ActuatorStatus.STOP_PENDING_CONFIRMATION`, retaining active command and operation ownership without fabricating `confirmed_physical_stop=True`.
  - **Receipt Hardening in `confirm_stop()`:** Made `device_id` and active `operation_id` strictly mandatory; enforced 600s freshness window, rejected future-dated observations (> 30s), verified trusted provenance, and rejected contradictory telemetry (`is_stopped=False`, `is_running=True`, `flow_rate > 0.0`).
  - **Modbus Driver Feedback:** Requires affirmative instrumentation on all mapped registers (both `flow == 0.0` and running bit cleared). Partial or missing instrumentation fails closed (`confirmed_physical_stop=False`, `transport_acknowledged_only=True`).
  - **HTTP Driver Telemetry:** Rejects contradictory telemetry (e.g. `status="STOPPED"` with `is_running=True`, `flow_rate > 0.0`, or `is_stopped=False` fails closed) in `_stop_zone` and `emergency_stop`.
  - **MQTT Driver ACK:** Explicitly returns `confirmed_physical_stop=True, transport_acknowledged_only=False` upon controller-level ACK.

### Integration D: Durable Evidence and Replay (P2 — F39, F02, F06)
* **Files:**
  - `services/agribrain/sensor_runtime/storage.py`
  - `services/agribrain/sensor_runtime/ingestion.py`
  - `services/agribrain/layer3_decision/runner.py`
* **Remediation:**
  - **Injective Identity Encoding:** In `storage.py`, `_validate_and_encode_id()` uses a SHA-256 digest (`f"{clean_prefix}_{digest}"`), eliminating path-traversal and collision aliases between sanitized variants (e.g. `urn:dev:123` vs `urn_COLON_dev_COLON_123`).
  - **Write Atomicity:** Raw sensor messages are written to unique temp files with `fsync`, exclusively claimed via `os.open(..., O_CREAT | O_EXCL)`, and published via atomic `os.replace`.
  - **Normalized Evidence Integrity:** In `store_normalized_reading()`, writes and `fsync` occur to disk before in-memory cache publication. In `sensor_runtime/ingestion.py`, failures in normalized storage fail closed by raising `RuntimeError`.
  - **Distributed Multi-Worker Rehydration:** In `get_normalized_readings()`, checking file metadata (`st_mtime`/`st_size`) against cached stat rehydrates in-memory records so multiple worker processes observe concurrent appends.
  - **Replay Weather Eligibility:** In `layer3_decision/runner.py`, enforced `_is_weather_issuance_eligible(w, step_limit_ts)` on `plot_hist` and `retained_weather_map` entries, preventing prospective weather leak during historical replays.

### Integration E: EO Qualification (P2 — F25, F26)
* **Files:**
  - `services/agribrain/layer1_fusion/eo_foundation_model.py`
* **Remediation:**
  - **Rectangular Grid Enforcement:** Rejects ragged row lengths across all multi-band grids, ensuring strictly rectangular `(H, W)` tensors.
  - **Spatial Identity Qualification:** When raster CRS or affine transform is missing, marks spatial identity unqualified (`UNQUALIFIED_SPATIAL_CRS`, `UNQUALIFIED_SPATIAL_TRANSFORM`) and sets `is_spatial_qualified=False`.
  - **Model Weights Provenance Binding:** Computes SHA-256 digest of loaded ONNX weights/bytes and binds it to `EmbeddingResult.model_provenance["weights_digest"]` alongside versioned preprocessing contracts.

---

## 5. Test Verification & Receipts

1. **Focused Blocker Suite:** `services/agribrain/tests/test_audit_four_owner_cohort_verified_blockers.py`
   - **Result:** **45 / 45 passed (100%)**
   - Covers:
     - Lane 1 (Foundation & Temporal): F01, F02, F06, F37 (Namespace & Prospective Weather Cutoffs)
     - Lane 2 (Trajectory & Persistence): F04, F08, F39 (Hydraulic Precision, Durability, Injective Storage)
     - Lane 3 (Execution & Safety): F16, F17, F18, F19 (Physical Stop Verification, Receipt Hardening, Driver Affirmation)
     - Lane 4 (Acquisition & EO): F25, F26 (Spatial Qualification, Ragged Grid Rejection, Weights Binding)
     - Integrations S, D, E: `TestPostAuditIntegrationsSDE` (13/13 passed)
2. **Full Repository Python Suite:** `services/agribrain/tests/`
   - **Result:** **671 / 671 passed (100%), 129 subtests passed** (0 failures, 3 non-blocking deprecation warnings).
3. **Frontend Test Suite:** `npm run test:frontend`
   - **Result:** **32 / 32 passed (100%)**
4. **TypeScript Typecheck:** `npx tsc --noEmit`
   - **Result:** **0 errors (clean compilation)**
