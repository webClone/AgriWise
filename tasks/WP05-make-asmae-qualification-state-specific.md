# Work Package 05: Make ASMAE Qualification State-Specific

## 1. Executive Summary & Objective
ASMAE (Layer 0.5) contains sophisticated ensemble Kalman filtering and retrospective validation machinery. However, the evaluation and qualification criteria for its latent states exhibit key scientific discrepancies:
1. **Frozen-State Retrovalidation (Finding #10)**: In `retrovalidation/future_projection.py`, `predict_held_out_scene()` evaluates holdout performance by applying the observation operator $H$ directly to the final training state raster without advancing the physical state forward in time. This measures persistence rather than dynamic forecast closure.
2. **Artificial BMA Disagreement Gate (Finding #11)**: In `bma/posterior.py`, an expert is marked active only if its normalized difference from the base state is $\ge 0.02$. An independently calibrated physical model that agrees with an accurate base estimate is excluded, leading to spurious `insufficient_experts` failures.
3. **Global Authority Overstatement (Finding #12)**: Accurate reconstruction of surface satellite radiometry (e.g. Sentinel-1 SAR backscatter) is permitted to qualify latent unobserved root-zone variables without state-specific identifiability constraints.

Work Package 05 resolves these discrepancies by implementing true dynamic prospective forecasting, decoupling expert independence from numerical disagreement, and scoping model authority strictly per state variable.

---

## 2. Affected Subsystems & Source References
- **ASMAE Retrovalidation Engine**: [`services/agribrain/layer05_asmae/retrovalidation/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/retrovalidation/engine.py#L160-L295).
- **ASMAE Future Projection**: [`services/agribrain/layer05_asmae/retrovalidation/future_projection.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/retrovalidation/future_projection.py#L17-L60).
- **ASMAE Bayesian Model Averaging (BMA)**: [`services/agribrain/layer05_asmae/bma/posterior.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/bma/posterior.py#L225-L235).
- **Observation Forward Models**: [`services/agribrain/layer05_asmae/observation/s1_sar_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/observation/s1_sar_model.py).

---

## 3. Root Cause & Architectural Breakdown

### 3.1 Persistence Baseline vs Prospective Forecasting (Finding #10)
In `retrovalidation/future_projection.py`:
```python
def predict_held_out_scene(
    training_state: Dict[str, List[float]],
    holdout_scene: Any,
    operator: Optional[Any] = None,
) -> Dict[str, Any]:
...
    observations = extract_pixel_observations(holdout_scene)
    # Evaluates H * training_state without integrating dX/dt between t_train and t_holdout
```
The state vector is frozen at the acquisition time of the last training scene ($t_{\text{last}}$). The holdout scene occurs at $t_{\text{holdout}} > t_{\text{last}}$ (often 6 to 18 days later). Applying $H_{\text{holdout}}$ to $X(t_{\text{last}})$ only evaluates whether the field remained unchanged (persistence). It does not test whether the transition model accurately simulated phenology, soil drying, or canopy growth over that horizon.

### 3.2 Conflation of Disagreement with Independence in BMA (Finding #11)
In `bma/posterior.py` line 231:
```python
active = bool(target_indices and independence_key) and delta >= 0.02 and has_holdout
```
The code requires `delta >= 0.02` (normalized difference from the ensemble base estimate) as a precondition for an expert to be eligible. The intent was to prevent duplicate or cloned models from receiving double weight. However, requiring numerical difference penalizes accurate consensus: two independent models that both correctly predict true soil moisture are disqualified from active averaging.

### 3.3 State-Specific Identifiability vs Radiometric Fit (Finding #12)
Sentinel-1 SAR VV backscatter primarily reflects surface soil roughness and surface moisture (top $0-5\text{ cm}$). When a simplified SAR model reproduces VV backscatter accurately, it confirms surface agreement. It does not prove that root-zone moisture ($5-40\text{ cm}$) or deep drainage are physically identified. Granting broad operational authority across all 13 states on the basis of radiometric surface fit is a scientific category error.

---

## 4. Implementation Specification

### 4.1 Step 1: Implement Dynamic Forecast Propagation in Retrovalidation
1. Preserve the existing function as `persistence_baseline_held_out_scene(...)`.
2. Author `forecast_held_out_scene(...)` in `future_projection.py`:
   - Inputs: `training_state`, `t_last`, `holdout_scene`, `t_holdout`, `weather_forcing_at_issue_time`.
   - Propagate the ensemble state from $t_{\text{last}}$ to $t_{\text{holdout}}$ using ASMAE's transition equations (from WP04) forced strictly by weather and management data available at $t_{\text{last}}$ (issue-time forecast).
   - Apply the holdout forward operator $H_{\text{holdout}}$ to the forecasted state $X(t_{\text{holdout}})$.
3. Compute and report both metrics in retrospective evaluation receipts:
   - `persistence_rmse`: Error from frozen baseline.
   - `prospective_forecast_rmse`: Error from forward physical integration.
   - `forecast_skill_score`: $1 - (\text{forecast\_rmse} / \text{persistence\_rmse})$.

### 4.2 Step 2: Decouple BMA Eligibility from Disagreement
1. Refactor `services/agribrain/layer05_asmae/bma/posterior.py`:
   - Evaluate model eligibility based strictly on:
     1. Valid calibration artifact ID and validity domain.
     2. Declared model family and training dataset independence (`independence_key`).
     3. Passed holdout validation requirements (`has_holdout`).
   - Remove the `delta >= 0.02` gate from eligibility determination.
   - Address collinearity or duplicate models through covariance regularization or shrinkage in the posterior weighting equation, rather than hard exclusion.

### 4.3 Step 3: Enforce Per-Variable Authority Ceilings
1. In `services/agribrain/layer05_asmae/state/descriptors.py`, enforce fine-grained authority ceilings:
   - `vigor`, `bare_soil_fraction`: `AuthorityCeiling.PRESCRIPTION_ELIGIBLE` (when verified by high-resolution optical evidence).
   - `root_zone_water`: `AuthorityCeiling.DIAGNOSTIC` (unless constrained by verified in-situ soil moisture probes).
   - `salinity_stress`, `biotic_confounder_risk`: `AuthorityCeiling.MONITORING_ONLY`.
2. Ensure downstream orchestrator filters reject prescriptions that attempt to command irrigation volumes based on uncalibrated root-zone latent estimates.

---

## 5. Verification & Completion Criteria
- **Forecast Closure Verification**: The system successfully distinguishes persistence skill from dynamic physical forecasting across all holdout scenes.
- **BMA Consensus Invariant**: When two verified independent physics experts predict values within $0.01$ of the base state, both remain active and contribute to the posterior distribution without triggering `insufficient_experts`.
- **State-Scoped Authority Enforcement**: Downstream adapters verify authority per state variable; good surface SAR fit never unlocks root-zone machine execution.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #10 (Held-out scene state advancement), Finding #11 (BMA expert eligibility and disagreement), Finding #12 (Radiometric consistency vs latent state maturity), Finding #13 (Preserve existing ASMAE safeguards).
- **Defect Tasks**: [A06-asmae-external-scene-loader-resolution.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A06-asmae-external-scene-loader-resolution.md).
- **Phase Tasks**: [P01.2-repair-asmae-scene-and-sire-failures.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P01.2-repair-asmae-scene-and-sire-failures.md).
