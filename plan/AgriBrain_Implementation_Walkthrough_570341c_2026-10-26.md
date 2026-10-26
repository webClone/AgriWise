# AgriBrain Implementation Walkthrough and Cohort Delivery Plan

**Candidate Commit:** `570341c0fd769c8aceb0babab65bdf5e443faf74` (with post-review refinements)  
**Branch:** `feat/f36-t09-asmae-13-state-publication`  
**Date:** 26 October 2026  
**Audience:** Four-Owner Cohort Delivery Team (Foundation, Trajectory, Execution, Acquisition) & Independent Verification Gate  

---

## 1. Executive Status & Progress Tracking

| Metric | Current Value | Notes |
|---|---|---|
| **Overall Implementation Estimate** | **32%** | Baseline estimate; 285 tracking register ticket checkboxes open in task register |
| **Change from Previous Audit** | **0% (rounded)** | Measured by accepted software outcomes, not raw commit count |
| **Current Cohort Estimate** | **53%** | 16-package maturity across the 4 delivery lanes |
| **Formal Acceptance Milestones** | **0 / 52** | Formal package sign-offs remain strictly open until full integration acceptance |
| **Current Head Commit** | `570341c` (+ follow-on) | 13+ commits ahead of `main`; builds upon verified `563c6fa` closure |

---

## 2. Technical Findings Disposition & Verification Walkthrough

The independent verification of commit `570341c` confirmed that prior R706 integration issues (typed SIRE uncertainty array evaluation, canonical `bare_soil_fraction` support lookup, and cache receipt parity) are verified closed within their software scopes. The deeper source review identified four targeted numerical and behavioral findings, which have now been comprehensively resolved and verified:

### Finding 1: Scale-Aware Covariance Symmetry & Numerical Tolerances (P1/P2)
* **Problem:**  
  1. The matrix `[[1e-8, 5e-5], [0, 1e-8]]` was accepted as symmetric because the absolute symmetry tolerance was `1e-4` while `np.linalg.eigvalsh()` consumed only one triangle of the matrix.
  2. The matrix `[[1e-15, 1e-13], [1e-13, 1e-15]]` has a negative eigenvalue of order `-9.9e-14`, but was accepted because the minimum PSD floor was fixed at `1e-12`.
* **Resolution in `services/agribrain/layer10_sire/surfaces/asmae.py`:**
  - Implemented scale-aware relative symmetry verification:
    ```python
    scale = max(max_diag, max_elem)
    sym_tol = max(1e-14, 1e-4 * scale)
    for i in range(n_rows):
        for j in range(i + 1, n_rows):
            diff = abs(float(cov[i][j]) - float(cov[j][i]))
            pair_scale = max(abs(float(cov[i][j])), abs(float(cov[j][i])))
            if diff > sym_tol or diff > max(1e-14, 1e-4 * pair_scale):
                return False, True
    ```
  - Replaced the fixed `1e-12` minimum PSD floor with a scale-relative tolerance:
    ```python
    tol = max(1e-15, 1e-6 * mat_scale)
    if np.any(eigenvals < -tol):
        return False, True
    ```
  - Explicit non-finite checks (`np.all(np.isfinite(mat))` and `np.all(np.isfinite(eigenvals))`) reject NaN / Inf values immediately.
* **Verification:**  
  Both counterexamples `[[1e-8, 5e-5], [0, 1e-8]]` and `[[1e-15, 1e-13], [1e-13, 1e-15]]` reject fail-closed as `(False, True)`.

---

### Finding 2: Unified Assimilation Rollback in $H_t$ and Proxy Paths (P2)
* **Problem:**  
  1. While the $H_t$ branch restored `step_prior_cube` on negligible influence, the proxy update path called `_proxy_update_single_obs(ensemble, ...)` on the live dictionary before testing influence, leaving `ensemble` mutated when `update_applied=False`.
  2. In mixed-target observations (e.g. `ndvi` targeting `['vigor', 'lai']`), if `vigor` had significant innovation but `lai` had negligible innovation, the uninfluenced state (`lai`) was not rolled back to its prior ensemble values.
* **Resolution in `services/agribrain/layer05_asmae/assimilation/filter.py`:**
  - **Proxy Full Rollback:** When `not has_actual_influence`, `ensemble` is restored completely from `step_prior_ensemble`:
    ```python
    if not has_actual_influence:
        for k in ensemble:
            ensemble[k] = [row[:] for row in step_prior_ensemble[k]]
        reports.append({...})
        continue
    ```
  - **Mixed-Target Rollback:** For both $H_t$ and proxy paths, uninfluenced target states are rolled back while keeping influenced states updated:
    - In `update_step_ht`:
      ```python
      for state_index in target_indices:
          state_name = STATE_NAMES[state_index]
          if not per_state_influence[state_name]['state_influenced']:
              state_cube[:, :, state_index] = step_prior_cube[:, :, state_index]
      ```
    - In `update_step_proxy`:
      ```python
      for state_index in target_indices:
          state_name = STATE_NAMES[state_index]
          if not per_state_influence[state_name]['state_influenced']:
              for nid in node_ids:
                  for i_member in range(len(ensemble[nid])):
                      ensemble[nid][i_member][state_index] = step_prior_ensemble[nid][i_member][state_index]
      ```
* **Verification:**  
  Verified that negligible-influence proxy observations return `ensemble == prior_ensemble`. Verified that mixed-target updates record `accepted_target_states: ['vigor']`, `excluded_target_states: ['lai']`, and leave `lai` identically equal to prior.

---

### Finding 3: V90 Variable Identity Safeguard (P2)
* **Problem:**  
  The standard variable name resolver prioritized metadata `variable` before checking surface type. A surface of type `SurfaceType.ASMAE_ROOT_ZONE_WATER` with conflicting metadata `variable="canopy_water"` could resolve to `"canopy_water"`.
* **Resolution in `services/agribrain/layer10_sire/surfaces/asmae.py`:**
  - Added an explicit conflict detection guard:
    ```python
    canon_v = canonical_state_key(v) if v else None
    canon_s = canonical_state_key(s)

    # Reject conflicting canonical declarations
    if canon_v and canon_v in STATE_ORDER and canon_s and canon_s in STATE_ORDER and canon_v != canon_s:
        return "conflict_rejected"
    ```
  - If a surface artifact declares `ASMAE_ROOT_ZONE_WATER` with metadata `variable="canopy_water"`, it returns `"conflict_rejected"`, which fails closed in `verify_v90_certification_record`.
* **Verification:**  
  `get_standard_variable_name(SurfaceType.ASMAE_ROOT_ZONE_WATER, "canopy_water") == "conflict_rejected"`.

---

### Finding 4: Layer 5 v3 and Layer 10 Cache Coexistence Execution
* **Problem:**  
  The initial coexistence test verified `get_asmae_cache_key`, but did not execute live Layer 10 caching operations (`save_layer10_to_cache` and `load_layer10_from_cache`).
* **Resolution in `services/agribrain/tests/test_563c6fa_closure_and_numerical_invariants.py`:**
  - Updated `test_layer5_v3_and_layer10_coexistence` to execute the full Layer 10 pipeline:
    1. Instantiates a valid `Layer10Output` with `SurfaceArtifact`.
    2. Writes to cache via `save_layer10_to_cache`.
    3. Reads back via `load_layer10_from_cache` and asserts parity.
    4. Confirms Layer 5 v3 cache key remains completely stable and unaffected.
    5. Cleans up candidate JSON/NPZ artifacts on teardown.
* **Verification:**  
  `test_layer5_v3_and_layer10_coexistence` passes cleanly.

---

## 3. Four-Owner Cohort Delivery Model

To eliminate whole-repository audit cycles and deliver measurable progress against the 52 work packages, implementation proceeds under four parallel owner lanes:

| Delivery Lane | Owner Responsibility | Existing Packages | Current Estimated Maturity | Immediate Milestones |
|---|---|---|---|---|
| **Lane 1: Foundation & Integration** | Shared contracts, schema authority, admission gates | F37, F01, F02 | **52%** | Reuse/close startup identity and admission cutoffs; freeze ingress contracts |
| **Lane 2: Trajectory & Storage** | Durable state, backward compatibility, trajectory persistence | F03/F04/F06 → F07/F08 → F09 → F39 | **56%** | Close integrated receipts, durable predecessor state, and ST03 tickets |
| **Lane 3: Execution** | Watchdogs, quotas, task execution, retry reconciliation | F16 → F17 → F18/F19 | **52%** | Close watchdog/quota, physical operation ownership, reconciled retry |
| **Lane 4: Acquisition & Learning** | Backend/input contracts, support identity, observation ingestion | F25 → F26 | **42%** | Close input contracts, complete support identity, prepare F27/F28 |

### Program-Wide Cohort Sequencing (A through E)

1. **Cohort A (Immediate):** Foundation / Trajectory / Execution (16 packages: F37, F01–F04, F06–F09, F16–F19, F25–F26, F39) — 388–660 total planned hours.
2. **Cohort B:** Correction Integrations / Reliability (25 packages: F05, F10–F15, F20–F24, F27–F36, F38, F40, T11) — 756–1,300 planned hours.
3. **Cohort C:** Coupled Baseline / Product / Corpus / References (5 packages: T01, T02, T08, T09, T12) — 540–960 planned hours.
4. **Cohort D:** Representation / Instruments / Rollout / Economics (4 packages: T03, T06, T04, T05) — 520–960 planned hours.
5. **Cohort E:** Investigation / Institutions (2 packages: T07, T10) — 360–660 planned hours.

---

## 4. Test Suite Summary & Evidence Gate

The test suite in [test_563c6fa_closure_and_numerical_invariants.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/tests/test_563c6fa_closure_and_numerical_invariants.py) covers all verified repairs:

1. `test_small_indefinite_covariance_rejected`: Validates rejection of `[[1e-8, 5e-5], [0, 1e-8]]` (asymmetry) and `[[1e-15, 1e-13], [1e-13, 1e-15]]` (negative eigenvalue).
2. `test_nonfinite_covariance_rejected`: Validates rejection of NaN/Inf covariance matrices.
3. `test_root_zone_water_v90_variable_resolution`: Validates canonical resolution of `root_zone_water` and rejection of contradictory canonical declarations (`"conflict_rejected"`).
4. `test_display_policy_nan_handling`: Validates fail-closed diagnostic trust tier on NaN confidence or uncertainty.
5. `test_invariant_missing_uncertainty_fail_closed`: Validates INV-16 enforcement on missing/non-finite uncertainty.
6. `test_layer5_v3_and_layer10_coexistence`: Validates concurrent execution of Layer 5 v3 cache key generation and Layer 10 cache save/load.
7. `test_negligible_influence_ensemble_rollback`: Validates full `step_prior_cube` restoration on negligible-influence $H_t$ updates.
8. `test_proxy_negligible_influence_rollback`: Validates full `step_prior_ensemble` restoration on negligible-influence proxy updates.
9. `test_mixed_target_influence_rollback_ht`: Validates rollback of uninfluenced target slices while retaining influenced updates in $H_t$.
10. `test_mixed_target_influence_rollback_proxy`: Validates rollback of uninfluenced target columns while retaining influenced updates in proxy.

**Exit Gate Criteria:**
- 10/10 targeted closure tests passing.
- 53/53 integrated ASMAE publication and Stage 1-3 tests passing.
- 22/22 SIRE Layer 10 tests passing.
- TypeScript compilation and frontend tests clean.
