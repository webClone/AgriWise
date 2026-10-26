# AgriBrain Implementation Walkthrough and Cohort Delivery Plan

**Candidate Commit:** `730b9fe` (verified closed)  
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
| **Current Head Commit** | `730b9fe` | 15 commits ahead of `main`; builds upon verified `563c6fa` closure |

---

## 2. Technical Findings Disposition & Verification Walkthrough

The independent verification of commit `aaf3895` confirmed the resolution of prior integration findings. The review highlighted three targeted areas for contract and numerical hardening, which have now been comprehensively resolved:

### Finding 1: Strict Covariance Validity, Cauchy-Schwarz & Tightened PSD Tolerances (P1/P2)
* **Problem:**  
  1. Asymmetry at small scales: `[[1e-8, 5e-5], [0, 1e-8]]` was previously accepted by absolute checks.
  2. Micro-scale negative eigenvalue: `[[1e-15, 1e-13], [1e-13, 1e-15]]` has eigenvalue $-9.9\times 10^{-14}$.
  3. Zero-variance / cross-covariance inconsistency: `[[1.0, 0.001], [0.001, 0.0]]` has variable 1 with zero variance but nonzero cross-covariance with variable 0, violating Cauchy-Schwarz ($\text{Cov}(X, Y)^2 \le \text{Var}(X)\text{Var}(Y)$) with an invalid negative eigenvalue $\approx -10^{-6}$. Loose `1e-6` PSD tolerance admitted this matrix.
* **Resolution in `services/agribrain/layer10_sire/surfaces/asmae.py`:**
  - **Zero-Variance Consistency:** If any $\text{Var}(i) \le 10^{-15}$, all associated cross-covariances must be zero:
    ```python
    if var_i <= 1e-15:
        for j in range(n_rows):
            if abs(float(cov[i][j])) > 1e-15 or abs(float(cov[j][i])) > 1e-15:
                return False, True
    ```
  - **Cauchy-Schwarz Consistency:** Enforces $\text{Cov}(i, j)^2 \le \text{Var}(i)\text{Var}(j)$ across all index pairs:
    ```python
    cs_bound = var_i * var_j
    margin = max(1e-15, 1e-9 * (scale ** 2))
    if (cov_ij ** 2) > (cs_bound + margin):
        return False, True
    ```
  - **Tightened PSD Eigenvalue Tolerance:** Floating-point rounding on symmetric float64 matrices is bounded by machine precision ($O(n \epsilon \|A\|)$), so PSD tolerance is tightened to `max(1e-15, 1e-11 * mat_scale)`:
    ```python
    tol = max(1e-15, 1e-11 * mat_scale)
    if np.any(eigenvals < -tol):
        return False, True
    ```
* **Verification:**  
  All counterexamples (`[[1e-8, 5e-5], [0, 1e-8]]`, `[[1e-15, 1e-13], [1e-13, 1e-15]]`, and `[[1.0, 0.001], [0.001, 0.0]]`) reject fail-closed as `(False, True)`.

---

### Finding 2: Unconditional V90 Conflict Rejection (P2)
* **Problem:**  
  Returning `"conflict_rejected"` from `get_standard_variable_name()` signaled disagreement, but if passed directly to `verify_v90_certification_record()`, the resolver would attempt storage lookups with `"conflict_rejected"` as the variable identifier.
* **Resolution in `services/agribrain/layer10_sire/surfaces/asmae.py` & `certification/v90_resolver.py`:**
  - **Caller Pre-Check in `asmae.py`:** If `v90_var == "conflict_rejected"`, bypass calling `verify_v90_certification_record()` entirely, set `is_certified_v90 = False`, and return fail-closed `V90ResolutionResult(approved=False, reason_codes=["canonical_variable_conflict", "variable_mismatch"])`.
  - **Resolver Guard in `v90_resolver.py`:** In `verify_v90_certification_record()`, explicitly reject `variable == "conflict_rejected"` immediately before attempting any storage loads.
* **Verification:**  
  `verify_v90_certification_record(certification_id="CERT_MOCK", plot_id="test_plot", variable="conflict_rejected")` returns `approved=False` with `reason_codes=['canonical_variable_conflict', 'variable_mismatch']`.

---

### Finding 3: ASMAE-Specific Cache Roundtrip & Rollout Gate Enforcement (P2)
* **Problem:**  
  Prior cache coexistence tests used generic `SurfaceType.NDVI_CLEAN` and did not exercise the ASMAE-specific rollout check (`should_render_l10_asmae`) or test rehydration of ASMAE surfaces from NPZ.
* **Resolution & New Test in `test_563c6fa_closure_and_numerical_invariants.py`:**
  - Added `test_layer10_asmae_surface_cache_roundtrip_with_rollout_gate`:
    1. Instantiates a `Layer10Output` containing an ASMAE surface (`SurfaceType.ASMAE_VIGOR`) and versioned receipt.
    2. Writes to cache via `save_layer10_to_cache()`.
    3. Exercises `load_layer10_from_cache()` under active rollout (`L10_ASMAE_SURFACES_ENABLED="true"` for registered `test_plot`) and validates full NPZ array rehydration and `asmae_proof` parity.
    4. Exercises the rollout gate under disabled rollout (`L10_ASMAE_SURFACES_ENABLED="false"`), asserting that `load_layer10_from_cache()` fails closed to `None` (safe cache miss).
* **Verification:**  
  Test passes cleanly.

---

### Finding 4: Assimilation Receipt-State Consistency in $H_t$ and Proxy Paths
* **Problem:**  
  In mixed-target updates where target state $A$ was influenced and target state $B$ was excluded as negligible, $B$'s state values were rolled back, but the reported `posterior_variance`, `posterior_mean`, and `information_gain` reflected the state prior to rollback.
* **Resolution in `services/agribrain/layer05_asmae/assimilation/filter.py`:**
  - In both `update_step_ht` and `update_step_proxy`, recompute `posterior_mean` and `posterior_variance` immediately after reverting uninfluenced target slices/columns:
    ```python
    posterior_variance = _state_variance_summary(state_cube, target_indices)
    posterior_mean = _state_mean_summary(state_cube, target_indices)
    information_gain = {
        state: max(0.0, prior - posterior_variance.get(state, prior))
        for state, prior in prior_variance.items()
    }
    ```
  - For any excluded state, reported `posterior_variance` strictly equals `prior_variance`, `information_gain` is `0.0`, and `posterior_mean` strictly matches the returned ensemble.
* **Verification:**  
  Unit tests confirm that for excluded `lai`, `reports[0]["posterior_variance"]["lai"] == reports[0]["prior_variance"]["lai"]` and `reports[0]["information_gain"]["lai"] == 0.0`.

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

1. `test_small_indefinite_covariance_rejected`: Validates rejection of `[[1e-8, 5e-5], [0, 1e-8]]` (asymmetry), `[[1e-15, 1e-13], [1e-13, 1e-15]]` (negative eigenvalue), and `[[1.0, 0.001], [0.001, 0.0]]` (zero-variance / cross-covariance Cauchy-Schwarz violation).
2. `test_nonfinite_covariance_rejected`: Validates rejection of NaN/Inf covariance matrices.
3. `test_root_zone_water_v90_variable_resolution`: Validates canonical resolution of `root_zone_water`, rejection of contradictory canonical declarations (`"conflict_rejected"`), and unconditional resolver denial.
4. `test_display_policy_nan_handling`: Validates fail-closed diagnostic trust tier on NaN confidence or uncertainty.
5. `test_invariant_missing_uncertainty_fail_closed`: Validates INV-16 enforcement on missing/non-finite uncertainty.
6. `test_layer5_v3_and_layer10_coexistence`: Validates concurrent execution of Layer 5 v3 cache key generation and Layer 10 cache save/load.
7. `test_layer10_asmae_surface_cache_roundtrip_with_rollout_gate`: Validates ASMAE-specific Layer 10 cache save/load, NPZ rehydration, and rollout gate enforcement.
8. `test_negligible_influence_ensemble_rollback`: Validates full `step_prior_cube` restoration on negligible-influence $H_t$ updates.
9. `test_proxy_negligible_influence_rollback`: Validates full `step_prior_ensemble` restoration on negligible-influence proxy updates.
10. `test_mixed_target_influence_rollback_ht`: Validates rollback of uninfluenced target slices while retaining influenced updates in $H_t$ and asserts posterior summary consistency.
11. `test_mixed_target_influence_rollback_proxy`: Validates rollback of uninfluenced target columns while retaining influenced updates in proxy and asserts posterior summary consistency.

**Exit Gate Criteria:**
- 11/11 targeted closure tests passing.
- 53/53 integrated ASMAE publication and Stage 1-3 tests passing.
- 22/22 SIRE Layer 10 tests passing.
- TypeScript compilation and frontend tests clean.
