# Work Package 07: Implement the MESIA-to-ASMAE Observation Boundary

## 1. Executive Summary & Objective
MESIA was conceived in the system monograph as an opportunistic in-situ RF observer providing high-frequency microzone constraints to ASMAE's ensemble Kalman filter. However, in the current codebase, the boundary connecting MESIA to ASMAE is completely broken and scientifically invalid:
1. **Discarded Assimilation Events (Finding #14)**: In `mesia/service.py` line 2514, `scan_plot_spectrum()` executes the Layer 0 admission bridge via `l0_rec, _ = bridge.process_and_admit_observation(...)`. The returned ASMAE innovation proposal is discarded into `_`. In operational runs, MESIA proposals never reach ASMAE's filter.
2. **Probability-to-Moisture Substitution (Finding #15)**: In `mesia/assimilation/asmae_operator.py` line 67, the code assigns:
   ```python
   measured_vwc = likelihood.likelihood_value
   innovation = measured_vwc - prior_state_vwc
   ```
   `likelihood.likelihood_value` is a dimensionless hypothesis score ($0.0 - 1.0$) derived from SNR deviation in `behaviour/likelihood_engine.py`. The code treats this dimensionless probability as a physical volumetric water content ($m^3/m^3$), subtracting the prior moisture to compute an innovation. A score of $0.85$ applied to a dry soil ($0.15\text{ VWC}$) produces a catastrophic $+0.70$ innovation, instantly flooding the field in the state vector.
3. **Contained Observability (Finding #20)**: `observability_analyzer.py` hardcodes `is_observable=False`, which prevents bad updates today, but leaves the physical tomographic inversion unimplemented.

Work Package 07 re-architects the MESIA-to-ASMAE boundary with mathematically rigorous observation operators, physical unit checking, and an active observation dispatcher.

---

## 2. Affected Subsystems & Source References
- **MESIA Service**: [`services/agribrain/mesia/service.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/service.py#L2510-L2535).
- **MESIA ASMAE Operator**: [`services/agribrain/mesia/assimilation/asmae_operator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/assimilation/asmae_operator.py#L55-L87).
- **Likelihood Engine**: [`services/agribrain/mesia/behaviour/likelihood_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/behaviour/likelihood_engine.py).
- **Observability Analyzer**: [`services/agribrain/mesia/observability_analyzer.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/observability_analyzer.py).
- **ASMAE Observation Dispatcher**: [`services/agribrain/layer05_asmae/observation/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/observation/).

---

## 3. Mathematical & Physical Derivation

### 3.1 Resolving the Probability vs VWC Defect (Finding #15)
In standard data assimilation (Kalman Filter), the innovation is defined in observation space:
$$d = y - h(x)$$
where:
- $y \in \mathbb{R}^m$ is the actual physical measurement vector with unit $U$.
- $x \in \mathbb{R}^n$ is the state vector.
- $h: \mathbb{R}^n \to \mathbb{R}^m$ is the forward observation operator mapping physical state to expected measurement in unit $U$.
- $R \in \mathbb{R}^{m \times m}$ is the measurement error covariance with unit $U^2$.

In MESIA, raw Wi-Fi/GNSS signals measure attenuation $\Delta \text{SNR}$ (in dB) or phase shift $\Delta \phi$ (in radians).
If MESIA operates in **Observation Space**:
- Measurement: $y = \Delta \text{SNR}_{\text{obs}}\text{ (dB)}$.
- Forward Operator: $h(\theta_v, \text{canopy}) = \alpha \cdot \text{canopy} + \beta(\text{soil}) \cdot \theta_v\text{ (dB)}$.
- Innovation: $d = \Delta \text{SNR}_{\text{obs}} - h(\hat{x})\text{ (dB)}$.
- Kalman Gain: $K = P H^T (H P H^T + R)^{-1}$, which properly maps dB innovation into state updates ($\Delta \theta_v$).

Alternatively, if MESIA operates in **Likelihood Space**:
- The likelihood engine evaluates $L(x) = p(y | x)$ over the state space.
- In an ensemble filter, the likelihood is used directly to reweight ensemble particles:
  $$w_i \propto w_i^{(0)} \cdot p(y | x_i)$$
  without ever subtracting a probability from a physical moisture value.

The current code conflates the two by subtracting a dimensionless likelihood value from volumetric moisture!

---

## 4. Implementation Specification

### 4.1 Step 1: Implement Strongly-Typed ASMAEObservationPayload
In `services/agribrain/scientific_contracts/observation.py`:
```python
@dataclass(frozen=True)
class ASMAEObservationPayload:
    observation_id: str
    target_state_variable: str           # E.g. "root_zone_water", "canopy_water"
    microzone_id: str
    depth_stratum: str                   # "SURFACE_0_5CM", "ROOT_ZONE_5_30CM"
    observation_value: float             # Physical value y
    observation_units: str               # Must match target state units ("volumetric fraction [0,1]")
    observation_variance: float          # R variance in units^2
    forward_operator_id: str             # Operator used to map state to measurement
    calibration_certificate_id: str      # Required for operational promotion
    truth_class: str                     # "DERIVED_MODEL_INFERRED"
    knowledge_cutoff: datetime
```

### 4.2 Step 2: Refactor `asmae_operator.py`
1. Remove `measured_vwc = likelihood.likelihood_value`.
2. Provide two explicit entry points:
   - `from_calibrated_inversion(...)`: Takes an inverted physical soil moisture estimate derived from a calibrated dielectric model (Topp's equation), with strict units and GUM metrology variance.
   - `from_ensemble_likelihood(...)`: Evaluates the Gaussian likelihood of the observed RF feature against each ASMAE ensemble member's state, updating ensemble weights.
3. Assert that units match: if `target_state_variable == "root_zone_water"`, verify `observation_units == "volumetric fraction [0,1]"` and `observation_value <= 0.60`.

### 4.3 Step 3: Implement ASMAE Observation Dispatcher
1. In `services/agribrain/layer05_asmae/observation/dispatcher.py`, build `ASMAEObservationDispatcher`:
   - Receives admitted observation proposals from Layer 0 / MESIA.
   - Validates qualification certificates and epoch activity. If uncalibrated, logs a durable abstention receipt (`status="abstained_uncalibrated"`).
   - Ingests validated observations into the EnKF assimilation queue.
2. In `services/agribrain/mesia/service.py`, replace `l0_rec, _ = ...` with:
   ```python
   l0_rec, asmae_proposal = bridge.process_and_admit_observation(...)
   if asmae_proposal and asmae_proposal.is_usable_for_assimilation:
       dispatcher.dispatch_proposal(asmae_proposal)
   ```

### 4.4 Step 4: True Observability & Lattice Mapping
1. Connect MESIA microzones directly to ASMAE's canonical spatial lattice cells (from WP02).
2. In `observability_analyzer.py`, compute the Fisher Information Matrix of the link geometry. Set `is_observable = True` only when the matrix conditioning is finite and non-singular under whitened measurement noise.

---

## 5. Verification & Completion Criteria
- **Zero Probability-to-Moisture Substitutions**: The string `measured_vwc = likelihood.likelihood_value` is permanently removed from the codebase.
- **End-to-End Dispatch**: An admitted, calibrated MESIA observation flows into ASMAE's EnKF queue, updates the ensemble, and produces a verifiable `AssimilationReceipt`.
- **Durable Abstention Receipts**: Uncalibrated or unobservable MESIA scans generate explicit audit receipts recording the exact reason for exclusion.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #14 (Discarded MESIA ASMAE event), Finding #15 (Likelihood treated as measured VWC), Finding #19 (Lattice consumption), Finding #20 (Observability containment).
- **Defect Tasks**: [A08-mesia-rf-snr-vwc-assimilation.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A08-mesia-rf-snr-vwc-assimilation.md), [A10-mesia-asmae-adapter-and-payload-integration.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A10-mesia-asmae-adapter-and-payload-integration.md).
- **Phase Tasks**: [P03.3-connect-complete-asmae-numerical-tensors.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P03.3-connect-complete-asmae-numerical-tensors.md), [P03.4-mesia-shadow-operation-before-authority.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P03.4-mesia-shadow-operation-before-authority.md).

---

## 7. Execution Status & Verification Report (COMPLETED)

### 7.1 Architecture & Implementation Summary
1. **Physical Units & Inversion Integrity (Finding #15)**:
   - Created `services/agribrain/scientific_contracts/observation.py` defining canonical `ASMAEObservationPayload`. Enforces strict physical units (`volumetric fraction [0,1]` for soil moisture), realistic porosity bounds $[0.0, 0.65]$, strictly positive measurement variance, and qualification certificate lineage.
   - Refactored `services/agribrain/mesia/assimilation/asmae_operator.py` to eradicate `measured_vwc = likelihood.likelihood_value`.
   - Added `from_calibrated_inversion` implementing physical forward/inverse mappings with boundary enforcement.
   - Added `from_ensemble_likelihood` implementing Gaussian particle reweighting directly in measurement space without state corruption.

2. **Observation Dispatching & Durable Abstention (Finding #14)**:
   - Implemented `services/agribrain/layer05_asmae/observation/dispatcher.py` with `ASMAEObservationDispatcher` and `ObservationAbstentionReceipt`.
   - Updated `services/agribrain/mesia/service.py` to capture `l0_rec, asmae_event` from `bridge.process_and_admit_observation(...)` and route every proposal to the dispatcher.
   - Gated admission: qualified observations enter the EnKF queue; uncalibrated or fail-closed observations generate an immutable `ObservationAbstentionReceipt` embedded in `p["dispatch_receipt"]`.

3. **Algebraic Observability Analysis (Finding #20)**:
   - Updated `services/agribrain/mesia/assimilation/observability_analyzer.py` to compute algebraic observability using the Fisher Information Matrix ($A^T A$) rank and condition number:
     $$\text{is\_observable} = (\text{effective\_rank} == N_{\text{zones}}) \land (\kappa < 10^6) \land (N_{\text{zones}} > 0)$$
   - Generates structured `abstention_reasons` when geometry is rank-deficient or ill-conditioned.

### 7.2 Test Verification
- **Dedicated Suite**: `services/agribrain/mesia/tests/test_mesia_asmae_observation_boundary.py` (12/12 PASSED in 5.36s).
- **Subsystem Regression**: `services/agribrain/mesia/tests/` (120/120 PASSED in 36.33s).
- **Full AgriBrain Regression**: `services/agribrain/` (777/777 PASSED, 22 warnings, 3 subtests passed in 99.72s).

