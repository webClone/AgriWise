# Task A05: Water Posterior Fluxes & Sigma Propagation Disconnect

## 1. Finding Overview
* **Finding ID:** A05
* **Severity:** **P1 — Pipeline Coherence & Uncertainty Accounting Defect**
* **Component:** Layer 3 Water (WaterIntelligenceEngine Pipeline Runner)
* **Primary Target File:** [`services/agribrain/layer3_water/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/runner.py) (lines 187–287)

---

## 2. Technical Analysis & Code Audit

### Defect 1: Decoupling of Transitioned State and Reported Fluxes
In `services/agribrain/layer3_water/runner.py`:
1. At lines 180–186, soil storage is propagated across the daily time step using prior transpiration:
   ```python
   prognostic_soil = WaterStateAssimilator.execute_daily_water_balance(
       ...
       actual_transpiration_mm=flux_state.actual.actual_transpiration_mm, # Prior Ks
       ...
   )
   ```
2. At line 189, `assimilate_observations` assimilates sensor data to produce `posterior_soil`.
3. At lines 215–224, `DualKcEngine.partition_evapotranspiration` is called again with `ks = final_root_zone.stress_factor_ks` (posterior stress) to generate a new `flux_state`.
4. This new `flux_state` is packaged into the final `WaterState` (line 274).
*The Inconsistency:* The fluxes recorded in `WaterState.fluxes` were **never extracted from the soil**. Downstream consumers (e.g. Layer 4 leaching models, water accounting ledgers) receive flux numbers that disagree with the actual soil storage difference $\Delta S$.

---

### Defect 2: Posterior Uncertainty Sigma Dropped & Mathematically Incorrect
In `services/agribrain/layer3_water/runner.py`, lines 201–204:
```python
_posterior_soil_sigma = max(0.01, round(
    et0_res.uncertainty.soil_sigma * (1.0 - assim_diag.variance_reduction_fraction),
    4,
))
```
1. **Mathematical Inconsistency:**
   If the variance reduction fraction is $f = \frac{\sigma^2_{\text{prior}} - \sigma^2_{\text{post}}}{\sigma^2_{\text{prior}}}$, then:
   $$\sigma^2_{\text{post}} = \sigma^2_{\text{prior}} (1 - f) \implies \sigma_{\text{post}} = \sigma_{\text{prior}} \sqrt{1 - f}$$
   Multiplying standard deviation $\sigma$ directly by $(1 - f)$ over-reduces the standard deviation.
2. **Variable Discarded:**
   At line 248 (ensemble forecast):
   ```python
   lim_forecast = EnsembleForecastEngine.simulate_depletion_forecast(
       ...
       soil_uncertainty_sigma=et0_res.uncertainty.soil_sigma, # <-- Stale prior sigma!
   )
   ```
   At line 287 (canonical construction):
   ```python
   water_state = WaterStateFactory.create_water_state(
       ...
       uncertainty=et0_res.uncertainty, # <-- Stale prior uncertainty container!
   )
   ```
   `_posterior_soil_sigma` is calculated but **never passed to any consumer**.

---

## 3. Agronomical & Systemic Impact
- **Misaligned Water Accounting:** Crop water consumption ($ET_a$) reported to irrigators does not match soil moisture depletion measured by capacitance probes or simulated in water balance.
- **Under-Reported Risk in Forecasting:** The ensemble depletion forecast does not reflect reduced uncertainty after sensor assimilation, running broader or narrower Monte Carlo bands than mathematically warranted.

---

## 4. Implementation Plan

### Step 1: Clean Separation of Prior Forecast and Posterior Analysis
In `services/agribrain/layer3_water/runner.py`:
- Clearly demarcate:
  - `prior_fluxes`: Used for state transition $\mathbf{x}^- = f(\mathbf{x}_{t-1}, \mathbf{u}, \text{prior\_flux})$.
  - `analysis_increment`: $\Delta \mathbf{x} = \mathbf{K} (\mathbf{y} - \mathbf{H}\mathbf{x}^-)$.
  - `posterior_fluxes`: Published as diagnostic rate of the updated root zone, explicitly documented as diagnostic rather than transition flux.
- Retain both in `WaterState`:
  ```python
  water_state.fluxes = prior_fluxes # Reflects exact mass balance conservation
  water_state.diagnostic_fluxes = posterior_fluxes # Reflects instantaneous state capacity
  ```

### Step 2: Correct Sigma Derivation and Pass to Downstream Consumers
1. Correct the formula:
   ```python
   if assim_diag and assim_diag.observations_assimilated_count > 0:
       var_reduction = max(0.0, min(0.99, assim_diag.variance_reduction_fraction))
       _posterior_soil_sigma = max(0.005, round(
           et0_res.uncertainty.soil_sigma * math.sqrt(1.0 - var_reduction),
           4,
       ))
   ```
2. Propagate to `EnsembleForecastEngine`:
   ```python
   soil_uncertainty_sigma=_posterior_soil_sigma,
   ```
3. Update `et0_res.uncertainty` or construct an explicit `posterior_uncertainty` container for `create_water_state`.

---

## 5. Verification & Test Plan

### Automated Tests
1. **Uncertainty Propagation Verification:**
   - Run pipeline with 1 assimilated probe observation that yields variance reduction $0.36$.
   - Prior $\sigma = 0.05$.
   - Assert posterior $\sigma = 0.05 \times \sqrt{1 - 0.36} = 0.05 \times 0.8 = 0.04$.
   - Verify `water_state.uncertainty.soil_sigma == 0.04`.
2. **Flux Consistency Check:**
   - Assert $\Delta S = \text{Infiltration} - \text{Drainage} - \text{Evap} - \text{Transpiration}$.

---

## 6. Progress Tracking Checklist
- [ ] $\sqrt{1 - f}$ formula applied to posterior standard deviation.
- [ ] `_posterior_soil_sigma` passed to `EnsembleForecastEngine`.
- [ ] `_posterior_soil_sigma` passed to `WaterStateFactory`.
- [ ] Documentation added clarifying transition fluxes vs diagnostic fluxes.
- [ ] Unit tests written and passing.
