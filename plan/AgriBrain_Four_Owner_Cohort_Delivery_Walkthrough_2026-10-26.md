# AgriBrain Four-Owner Cohort Delivery & Track A Blocker Remediation Walkthrough

**Pinned Baseline Revision:** `f041a8f` / `730b9fe` · 26 October 2026  
**Branch:** `feat/f36-t09-asmae-13-state-publication`  
**Governing Decision:** Advance Four-Owner Cohort simultaneously across Track A (Demonstrated Blockers) and Track B (Dependency-Ready Package Criteria); ASMAE A+B corrective cycle remains closed within verified software scope.

---

## 1. Executive Metric Summary

| Metric | Status / Value | Audit Reconciliation |
|---|---|---|
| **Overall Estimated Achievement** | **32%** | Unchanged (285 register checkboxes open across 52 packages) |
| **Immediate Cohort Maturity** | **53%** | 16 selected cohort packages across 4 delivery lanes |
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

### Lane 4: Acquisition — F25 & F26 Model Identity and Tile Hash Provenance
* **File:** `services/agribrain/layer1_fusion/eo_foundation_model.py`
* **Defect:** 
  1. An ONNX execution failure silently invoked the spectral fallback, but `infer()` continued to report `onnx_foundation` with `0.85` confidence ceiling because it checked the configured mode rather than the actual executing backend.
  2. `_compute_tile_hash` concatenated raw float values without encoding band names, spatial dimensions ($H \times W$), or cloud masks, permitting scientific hash collisions across different physical inputs.
* **Remediation:**
  - `_infer_onnx` returns `None` on runtime errors, enabling `infer()` to catch the fallback condition, set `actual_backend = "spectral_basis_v2"`, assign `model_id = actual_backend`, and apply the fallback confidence ceiling `0.75`.
  - `_compute_tile_hash` now binds spatial grid dimensions `f"dim:{h}x{w}"`, band identities `f"band:{band}"`, and SHA-256 cloud-mask digests `f"cloud:{cm_h}x{cm_w}:{cm_hash}"`.

### Lane 2: Trajectory & Persistence — F39 Durable Sensor Storage
* **File:** `services/agribrain/sensor_runtime/storage.py`
* **Defect:** Process-local dictionaries (`_RAW_STORAGE`, `_NORMALIZED_STORAGE`) held mutable object references without disk persistence, failing cold-restart recovery and distributed multi-worker durability.
* **Remediation:**
  - Implemented durable file-backed persistence (`artifacts/sensor_store` or `AGRIWISE_SENSOR_STORAGE_DIR`).
  - Added deep-copy immutability on write and read.
  - Implemented atomic persistence for raw messages (`raw_{message_id}.json`) and append-only line format for normalized readings (`normalized_readings.jsonl`).
  - Implemented `rehydrate_storage()` for crash/restart recovery and `clear_storage()` for test isolation.

### Lane 3: Execution — F17 & F18 Physical Stop Contract & Operation Ownership
* **Files:** 
  - `services/agribrain/irrigation_runtime/schemas.py`
  - `services/agribrain/irrigation_runtime/drivers/lorawan_driver.py`
  - `services/agribrain/irrigation_runtime/drivers/modbus_driver.py`
  - `services/agribrain/irrigation_runtime/actuator.py`
* **Defect:** Stop paths cleared `_active_command` on transport success (queued LoRaWAN downlink or Modbus coil write) without positively confirming physical cessation, permitting double starts or lost ownership.
* **Remediation:**
  - Added `ActuatorStatus.STOP_PENDING_CONFIRMATION` and `transport_acknowledged_only`, `confirmed_physical_stop` flags to `CommandResult`.
  - LoRaWAN driver marks queued downlinks as `transport_acknowledged_only=True, confirmed_physical_stop=False`.
  - Modbus driver reads back flow rate and status register; stop is only confirmed when `actual_flow == 0.0` and status running bit is cleared.
  - Actuator enters `STOP_PENDING_CONFIRMATION` upon unconfirmed stop, **retaining `_active_command` and operation ownership**, and rejecting new `START_ZONE` commands until `confirm_stop()` is invoked.

### Lane 1: Foundation — F01 & F37 Calibration Admission & Namespace Parity
* **Files:**
  - `services/agribrain/sensor_runtime/ingestion.py`
  - `services/agribrain/sensor_runtime/registry.py`
  - `services/agribrain/sensor_runtime/calibration.py`
  - `services/agribrain/sensor_runtime/__init__.py`
* **Defect:**
  1. Calibration quality check did not verify finiteness (`math.isnan(q)` bypassed quality checks).
  2. Conditional import of `os` inside production check caused `UnboundLocalError` in nonproduction mode when checking `AGRIWISE_STRICT_SECURITY`.
  3. Module aliasing split `sensor_runtime` and `services.agribrain.sensor_runtime` dictionaries.
* **Remediation:**
  - Added `not math.isfinite(q)` to reject nonfinite calibration scores.
  - Moved `import os` and `import math` unconditionally to top level.
  - Unified `_DEVICE_REGISTRY` and `_CALIBRATION_PROFILES` across both import paths in `sys.modules`.

### Lane 2: Trajectory — F04 & F08 Hydraulic Precision & Trajectory Digest
* **Files:**
  - `services/agribrain/layer3_water/contracts/state_factory.py`
  - `services/agribrain/layer3_decision/runner.py`
* **Defect:**
  1. Rounding conductivity and van Genuchten parameters truncated small valid positive values (e.g. $K_{sat} = 0.0008 \to 0.0$).
  2. Cache state digest in Layer 3 omitted `few_exposed_wetted_fraction`, causing cache collisions between differing surface wetting regimes.
  3. Fallback checkpoint selection relied on filesystem modification time (`st_mtime`).
* **Remediation:**
  - Preserved full floating-point precision in `state_factory.py`.
  - Included `few_exposed_wetted_fraction`, `surface_storage_mm`, and `kr_reduction_factor` in the canonical soil-state digest.
  - Replaced filesystem sorting with canonical worldline checkpoint queries subject to `issued_at <= step_ts`.

---

## 4. Test Verification & Receipts

1. **Focused Blocker Suite:** `services/agribrain/tests/test_audit_four_owner_cohort_verified_blockers.py`
   - **Result:** 14 / 14 passed (100%)
2. **Full Repository Python Suite:** `services/agribrain/tests/`
   - **Result:** 640 / 640 passed (100%), 129 subtests passed
   - Verified legacy ASMAE import isolation hermeticity.
3. **Frontend Test Suite:** `npm run test:frontend`
   - **Result:** 32 / 32 passed (100%)
4. **TypeScript Typecheck:** `npx tsc --noEmit`
   - **Result:** 0 errors
