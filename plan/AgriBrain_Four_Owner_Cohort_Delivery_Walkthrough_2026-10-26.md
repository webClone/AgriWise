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

## 4. Test Verification & Receipts

1. **Focused Blocker Suite:** `services/agribrain/tests/test_audit_four_owner_cohort_verified_blockers.py`
   - **Result:** **32 / 32 passed (100%)**
   - Covers all 4 lanes: F25/F26 (Acquisition), F39 (Storage Durability), F17/F18 (Physical Stop Verification), F01/F37 (Namespace & Calibration), F04/F08 (Hydraulic Precision), and F02/F06 (Prospective Weather Cutoffs).
2. **Full Repository Python Suite:** `services/agribrain/tests/`
   - **Result:** **658 / 658 passed (100%), 129 subtests passed** (0 failures, 3 non-blocking deprecation warnings).
3. **Frontend Test Suite:** `npm run test:frontend`
   - **Result:** **32 / 32 passed (100%)**
4. **TypeScript Typecheck:** `npx tsc --noEmit`
   - **Result:** **0 errors (clean compilation)**
