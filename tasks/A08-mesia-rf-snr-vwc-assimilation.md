# Task A08: MESIA Likelihood Assigned Directly as Volumetric Water Content

## 1. Finding Overview
* **Finding ID:** A08
* **Severity:** **P0 — Physical Incommensurability & Scientific Corruption**
* **Component:** MESIA Behaviour & ASMAE Assimilation Operator
* **Primary Target Files:**
  - [`services/agribrain/mesia/behaviour/likelihood_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/behaviour/likelihood_engine.py) (lines 46–51)
  - [`services/agribrain/mesia/assimilation/asmae_operator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/assimilation/asmae_operator.py) (lines 58–80)

---

## 2. Technical Analysis & Code Audit

### The Code Flaw
In `services/agribrain/mesia/behaviour/likelihood_engine.py`:
```python
snr = feat.features.get("snr_db", 20.0)
innovation = float(snr - 20.0)
# Likelihood value based on nuisance safety (Dimensionless Gaussian PDF score [0.01, 1.0])
likelihood_val = math.exp(-0.5 * (innovation / 3.0) ** 2) if nuisance.is_safe_for_soil_assimilation else 0.01
```
In `services/agribrain/mesia/assimilation/asmae_operator.py`, lines 67–68:
```python
# DEFECT: assigns dimensionless probability score as volumetric water content!
measured_vwc = likelihood.likelihood_value if likelihood.likelihood_value is not None else prior_state_vwc
innovation = measured_vwc - prior_state_vwc
```

### Reproducing Probe:
1. Radio packet received with nominal SNR of $20.0\text{ dB}$ (no RF disturbance).
2. `innovation = 20.0 - 20.0 = 0.0`.
3. `likelihood_val = \exp(0) = 1.000` (meaning "high statistical confidence").
4. `ASMAEObservationOperator.create_innovation` sets `measured_vwc = 1.000`.
5. Natural soil saturation $\theta_{\text{sat}}$ is typically $0.40 - 0.50\text{ m}^3/\text{m}^3$. A VWC of $1.00$ corresponds to $100\%$ pure standing water (an open lake)!
6. With prior soil VWC of $0.20$, the operator computes:
   $$\text{innovation} = 1.00 - 0.20 = \mathbf{+0.80\text{ m}^3/\text{m}^3}$$
   This injects an immense, physically impossible moisture surge into the Kalman state!

---

## 3. Agronomical & Scientific Impact
- **Severe State Corruption:** If MESIA is ever permitted to update biological states, every nominal Wi-Fi or LoRa radio packet creates a phantom flood in the soil model.
- **Dimensional Nonsense:** A dimensionless statistical likelihood score ($p \in [0, 1]$) is conflated with a physical volumetric fraction ($m^3/m^3$).

---

## 4. Implementation Plan

### Step 1: Clarify Measurement Vector vs Statistical Weight
A radio signal is NOT a direct measurement of soil moisture. The native measurement is signal power/phase ($\text{dB}, \text{rad}$).
To derive an actual moisture estimate $\hat{\theta}_v$, an explicit physical/empirical observation operator must be defined:
$$\hat{\theta}_v = h(\text{RSSI}, \text{SNR}, \text{soil\_texture})$$
In `services/agribrain/mesia/behaviour/likelihood_engine.py`:
- `likelihood_val` must represent the **confidence weight** $w \in [0, 1]$, NOT the physical value.
- Introduce `estimated_physical_value` computed via an explicit calibrated transfer function, or keep native signal units.

### Step 2: Refactor `ASMAEObservationOperator`
In `services/agribrain/mesia/assimilation/asmae_operator.py`:
```python
# Check that target variable has a calibrated observation model
if likelihood.target_variable == "volumetric_water_content":
    # Must come from a calibrated physical model, NOT a probability score
    if not hasattr(likelihood, "calibrated_physical_value") or likelihood.calibrated_physical_value is None:
        raise ValueError(
            f"Cannot assimilate MESIA proposal {likelihood.likelihood_id}: "
            f"missing calibrated_physical_value for variable '{likelihood.target_variable}'. "
            f"Likelihood score ({likelihood.likelihood_value}) is a dimensionless confidence, not a VWC measurement."
        )
    measured_vwc = likelihood.calibrated_physical_value
    # Physical plausibility bounding: soil VWC cannot exceed saturation (e.g. 0.55) or fall below 0.01
    measured_vwc = max(0.01, min(0.55, measured_vwc))
    innovation = measured_vwc - prior_state_vwc
```

### Step 3: Enforce Scientific Containment
If no calibrated observation operator exists for the active radio link:
- Set `target_state_variable = "rf_signal_departure_db"`.
- Prohibit direct biological state updates until field calibration against physical TDR/capacitance probes is verified.

---

## 5. Verification & Test Plan

### Automated Tests
1. **Dimension Mismatch Rejection Test:**
   - Attempt to pass a `BehaviourLikelihood` with `target_variable="volumetric_water_content"` and `likelihood_value=1.0` without calibrated physical value.
   - Assert `ValueError` is raised (Principle P-08 enforcement).
2. **Nominal Calibration Test:**
   - Provide a valid calibrated dielectric response yielding $\theta_v = 0.22$.
   - Assert `measured_vwc == 0.22` and `innovation == 0.02` against prior $0.20$.
   - Assert `innovation` never exceeds physical bounds $[0.01, 0.55]$.

---

## 6. Progress Tracking Checklist
- [ ] Confusing `likelihood_value` $\to$ `measured_vwc` assignment removed.
- [ ] Physical plausibility bounds $[0.01, 0.55]$ enforced on soil moisture innovations.
- [ ] Explicit distinction made between statistical confidence and physical measurement.
- [ ] Uncalibrated RF proposals prevented from targeting biological state variables.
- [ ] Automated rejection tests written and passing.
