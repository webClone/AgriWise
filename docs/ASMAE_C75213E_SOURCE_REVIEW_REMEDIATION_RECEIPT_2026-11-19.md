# ASMAE C752-P1-01 through C752-P2-04 Remediation Verification Receipt

**Date:** 2026-11-19  
**Branch:** `feat/akaloris-asmae-ir04-r03-r04-review-20261119`  
**Base Commit:** `c75213e3e3889c380c623452798a4519d25b472d`  
**Target Draft PR #32 Head (Unchanged / On Hold):** `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`  
**Protected Main (Untouched):** `6edd3721c0defa7eed94b44cf96601ba59a49696`  
**Draft PR #30 Head (Untouched):** `599c4f6`  

---

## 1. Executive Summary

All four open source review blockers identified in `plan/ASMAE_C75213E_INDEPENDENT_SOURCE_REVIEW.md` have been fully remediated and verified with dedicated adversarial acceptance tests, full Layer 05 suite execution, and full frontend and type-check passes.

| Finding ID | Severity | Description | Status | Verification Reference |
|---|---|---|---|---|
| **C752-P1-01** | P1 | Query knowledge cutoff $K$ overwrote actual scene commitment | **CLOSED** | `test_c752_p1_01_bitemporal_replay_and_engine_separation` |
| **C752-P1-02** | P1 | Admission authority: unsigned booleans & optional scene namespace conferred support | **CLOSED** | `test_c752_p1_02_mandatory_namespace_and_positive_admission_authority` |
| **C752-P1-03** | P1 | Multiband S2 physics defaulted to 10 m $\sigma=5.0$ m when assimilation operator contained 20 m bands | **CLOSED** | `test_c752_p1_03_multiband_s2_physics_conservative_psf` |
| **C752-P2-04** | P2 | In-process TestClient with mock payload; no real worker reintegration or OS subprocess cold read | **CLOSED** | `test_c752_p2_04_worker_reintegration_and_subprocess_cold_read` |

---

## 2. Technical Remediation Details

### C752-P1-01: Bitemporal Leakage in Engine Replay
- **Defect:** `engine.py:2779` passed `committed_at=knowledge_cutoff` into `adapt_scenes_to_footprints()`. The adapter allowed this argument to rewrite `scene.committed_at` to query $K$, enabling a Day 5 observation committed on Day 20 to leak into a Day 10 replay query.
- **Fix:** In `engine.py:2779`, changed `committed_at=knowledge_cutoff` to `committed_at=None`. In `observation_footprint_adapter.py`, commitment derives strictly from `scene_comm` (immutable journal record). Dual-clock filtering in `evaluate_state_cell_support` enforces independent checks:
  $$\text{valid\_time} \le T \quad \land \quad \text{committed\_at} \le K$$
- **Proof:** `test_c752_p1_01_bitemporal_replay_and_engine_separation` exercises $(T=10, K=10)$ where Day 20 commitment is excluded (`spatial_support != "local_operator"`), and $(T=10, K=21)$ where it is admitted (`spatial_support == "local_operator"`).

### C752-P1-02: Admission Authority & Mandatory Namespace Identity
- **Defect:** `observation_footprint_adapter.py` permitted missing scene `tenant_id`, `farm_id`, `plot_id`, and `geometry_sha256` to pass through when absent. Any syntactically valid 64-hex SHA string with booleans `production_usable=True` was treated as admitted without authentic provider admission proof.
- **Fix:** In `observation_footprint_adapter.py`, when `require_operator_binding=True`:
  - `tenant_id`, `farm_id`, `plot_id`, and lowercase SHA-256 `geometry_sha256` are strictly mandatory and must match the target grid namespace.
  - Positive signed admission proof is required: `product_binding in ("exact_catalog_item", "verified_provider_asset", "signed_provider_asset")`, valid `admission_receipt`, verified signer in `binding_proof`, or genuine provider product.
  - Forged admission booleans with `product_binding="unknown"` and unverified asset hashes strictly fail closed.
- **Proof:** `test_c752_p1_02_mandatory_namespace_and_positive_admission_authority` validates failure on missing tenant/farm/plot/geometry, forged booleans, and unverified hashes.

### C752-P1-03: Multiband S2 Physics & Conservative PSF
- **Defect:** When Sentinel-2 `candidate.band` was `None`, `geometry/psf.py` and operator building defaulted to 10 m band parameters ($\sigma=5.0$ m, $\text{FWHM} \approx 11.77$ m), even if the scene raster included 20 m bands (e.g. B05, B11 SWIR).
- **Fix:** 
  - In `operator_builder.py` and `observation_footprint_adapter.py`, when Sentinel-2 `band` is unspecified or `None`, `scene.bands` is inspected. If any 20 m band (`{"B05", "B06", "B07", "B8A", "B11", "B12"}`) is present, the operator conservatively selects `band="B05"`, $\sigma=10.0$ m ($\text{FWHM} \approx 23.548$ m, native resolution = 20.0 m).
  - Added `band` field to `ObservationOperatorRuntime` and `ObservationOperatorManifest`.
  - Rejects claiming 10 m resolution for multiband observations containing 20 m channels.
- **Proof:** `test_c752_p1_03_multiband_s2_physics_conservative_psf` validates that an S2 scene with B04 and B11 builds an operator with $\sigma=10.0$ m, $\text{FWHM} > 20$ m, native resolution = 20.0 m, and effective resolution $\ge 20$ m.

### C752-P2-04: True Worker Reintegration & Subprocess Cold Read Proof
- **Defect:** Prior HNEW-06 test constructed payloads in-process, did not call `rebuild_canonical_plot_snapshot`, and used in-process `TestClient(app)` sharing memory state.
- **Fix:**
  - Implemented `rebuild_canonical_plot_snapshot` invocation from `services/agribrain/layer05_asmae/reintegration.py`, verifying worldline event commitment, publication receipt hash, and durable snapshot artifacts.
  - Configured `plot_snapshot_store.py` to respect `AGRIWISE_SNAPSHOT_STORE_ROOT` for complete test isolation.
  - Executed an out-of-process OS subprocess (`subprocess.run([sys.executable, ...])`) with zero memory sharing. The child process loads the snapshot from disk via `load_and_validate_plot_snapshot_by_id`, validates `numericalBindingValid` and `VALID_NORMAL` status, reads the latest head, exercises the FastAPI HTTP API (`/v2/snapshots/{id}` and `/v2/plots/{id}/snapshot`), and verifies that a subsequent diagnostic snapshot with missing sigma does not overwrite or suppress the valid older head.
- **Proof:** `test_c752_p2_04_worker_reintegration_and_subprocess_cold_read` passed with exit code 0 and stdout confirmation.

---

## 3. Independent Verification Results

- **New Acceptance Suite:**
  `pytest services/agribrain/layer05_asmae/tests/test_asmae_c752_p1_p2_source_review_remediation.py -v`
  **Result:** 4/4 passed (0 failures).

- **Full Layer 05 ASMAE Suite:**
  `pytest services/agribrain/layer05_asmae/ -q`
  **Result:** 226 passed, 1 deselected, 1 warning, 3 subtests passed in 83.32s.

- **Frontend Test Suite:**
  `node scripts/run-frontend-tests.mjs`
  **Result:** 341 passed (47 test files).

- **TypeScript Compilation:**
  `npx tsc --noEmit`
  **Result:** 0 errors.

---

## 4. Governance & Hold Invariants

1. **Draft PR #32 Status:** Untouched and open on GitHub at `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`. No fast-forward or rebase has been performed.
2. **Draft PR #30 Status:** Untouched at `599c4f6`.
3. **Protected Main Status:** Untouched at `6edd3721c0defa7eed94b44cf96601ba59a49696`.
4. **Master Findings Register:** 238 findings across 3 cohorts (40 / 48 / 150) preserved with 0 findings closed.
5. **Certification Holds:**
   - 1 m spatial resolution certification: **ON HOLD**.
   - Numerical publication authority: **ON HOLD**.
   - Verified actuator interlocks (`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`): **FAIL-CLOSED**.
