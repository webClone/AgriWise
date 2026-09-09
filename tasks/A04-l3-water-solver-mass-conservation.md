# Task A04: L3 Layered Water Solver Mass Balance Violation

## 1. Finding Overview
* **Finding ID:** A04
* **Severity:** **P0 — Law of Conservation of Mass Violation**
* **Component:** Layer 3 Water (Soil Layered Water Balance Solver)
* **Primary Target File:** [`services/agribrain/layer3_water/soil/layered_water_balance.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/soil/layered_water_balance.py) (lines 115–148)

---

## 2. Technical Analysis & Code Audit

### Defect 1: Water Spontaneously Created at Wilting Point
In `services/agribrain/layer3_water/soil/layered_water_balance.py`, lines 121–123:
```python
# 4. Layer-by-Layer Root Water Extraction U(z) via Feddes weighting
for i in range(n_layers):
    if i < len(uptake_fractions):
        layer_uptake = round(uptake_fractions[i] * actual_transpiration_mm, 2)
        allowable_plant_extract = max(0.0, new_storage[i] - wp_storage_mm[i])
        actual_layer_uptake = min(layer_uptake, allowable_plant_extract)
        new_storage[i] = max(wp_storage_mm[i], new_storage[i] - actual_layer_uptake) # <-- DEFECT!
```
#### Reproducing Probe:
- Consider dry topsoil starting at residual water content $\theta_r = 0.078$ ($\approx 39\text{ mm}$ for a 500mm layer).
- Wilting point is $\theta_{wp} = 0.135$ ($67.5\text{ mm}$).
- Zero rain, zero irrigation, zero transpiration:
  - `allowable_plant_extract = max(0.0, 39.0 - 67.5) = 0.0`
  - `actual_layer_uptake = 0.0`
  - `new_storage[i] = max(67.5, 39.0 - 0.0) = 67.5\text{ mm}`!
- **Result:** $28.5\text{ mm}$ of water was created per layer out of nothing! Over a 5-layer profile, **$114\text{ mm}$ of non-existent water was manufactured**, and the solver reported a $114\text{ mm}$ mass error!

---

### Defect 2: Inconsistent Storage State in Mass Closure Equation
In `services/agribrain/layer3_water/soil/layered_water_balance.py`, lines 137–147:
```python
delta_s = s_next - s_prev
inflows = actual_infil + capillary_rise_mm
total_plant_extracted = sum(
    min(round(uptake_fractions[i] * actual_transpiration_mm, 2),
        max(0.0, layer_storage_mm[i] - wp_storage_mm[i])) # <-- USES PRE-INFILTRATION STORAGE!
    for i in range(min(n_layers, len(uptake_fractions)))
)
outflows = total_plant_extracted + actual_top_evap + deep_drainage
mass_balance_error = round(abs(delta_s - (inflows - outflows)), 4)
```
- In Step 4 (line 121), the plant extraction used `new_storage[i]` (which had *already received infiltration*).
- In the mass balance calculation (line 143), `total_plant_extracted` is recalculated using `layer_storage_mm[i]` (the *pre-infiltration* storage).
- Whenever it rains, the two extraction amounts differ, causing the solver to falsely declare a mass balance error on valid physical steps!

---

### Defect 3: Capillary Rise Saturation Clipping
In line 127:
```python
if capillary_rise_mm > 0.0:
    new_storage[-1] = min(sat_storage_mm[-1], new_storage[-1] + capillary_rise_mm)
```
If `new_storage[-1] + capillary_rise_mm > sat_storage_mm[-1]`, water is clipped at saturation, but `inflows` (line 141) still counts the full `capillary_rise_mm`. The rejected flux is lost from the ledger.

---

## 3. Agronomical & Physical Impact
- **Hydrological Instability:** Dry soils instantly "jump" to wilting point. Crop models never see extreme moisture stress because the code prevents soil from ever staying below the wilting point.
- **Invalid Irrigation Schedules:** The MPC optimizer relies on accurate depletion states; with phantom water creation, required irrigation depths are underestimated by tens of millimeters, risking crop failure.

---

## 4. Implementation Plan

### Step 1: Repair Plant Water Uptake Storage Update
In `services/agribrain/layer3_water/soil/layered_water_balance.py`:
- Track actual extracted plant uptake explicitly per layer.
- Never floor storage at `wp_storage_mm[i]` if the soil was already below wilting point.
- Soil storage can be drawn down to residual moisture $\theta_r$ by evaporation, but roots only extract down to wilting point:
```python
actual_layer_uptakes = []
for i in range(n_layers):
    if i < len(uptake_fractions):
        layer_uptake_target = round(uptake_fractions[i] * actual_transpiration_mm, 2)
        # Root uptake is limited by available water above wilting point
        water_above_wp = max(0.0, new_storage[i] - wp_storage_mm[i])
        actual_extract = min(layer_uptake_target, water_above_wp)
        new_storage[i] -= actual_extract
        actual_layer_uptakes.append(actual_extract)
    else:
        actual_layer_uptakes.append(0.0)
```

### Step 2: Account for Capillary Rise Inflow Accurately
```python
actual_capillary_inflow = 0.0
if capillary_rise_mm > 0.0:
    avail_space = max(0.0, sat_storage_mm[-1] - new_storage[-1])
    actual_capillary_inflow = min(capillary_rise_mm, avail_space)
    new_storage[-1] += actual_capillary_inflow
```

### Step 3: Exact Mass Balance Closure Accounting
Compute outflows using the exact values extracted during the step:
```python
total_plant_extracted = sum(actual_layer_uptakes)
outflows = total_plant_extracted + actual_top_evap + deep_drainage
inflows = actual_infil + actual_capillary_inflow

s_prev = sum(layer_storage_mm)
s_next = sum(new_storage)
delta_s = s_next - s_prev

mass_balance_error = round(abs(delta_s - (inflows - outflows)), 4)
if mass_balance_error > 0.01:
    logger.error(f"[Hydrology] Mass conservation violated: delta_s={delta_s}, inflows={inflows}, outflows={outflows}, err={mass_balance_error} mm")
```

---

## 5. Verification & Test Plan

### Automated Numerical Probes
Create `tests/test_a04_water_conservation.py`:
1. **Residual Moisture Zero Flux Probe:**
   - Profile at $\theta = \theta_r$ ($< \theta_{wp}$).
   - Run daily step with $P=0, I=0, ET=0$.
   - Assert `mass_balance_error == 0.0000`.
   - Assert `new_storage == initial_storage` (zero water added).
2. **Rainfall & Extraction Mass Balance Probe:**
   - Profile at $\theta = \theta_{wp}$.
   - Apply $P=20\text{ mm}$, Transpiration $= 5\text{ mm}$, Evaporation $= 2\text{ mm}$.
   - Assert `abs(delta_s - (inflows - outflows)) < 1e-4`.

---

## 6. Progress Tracking Checklist
- [ ] Uptake extraction flooring at wilting point removed.
- [ ] Actual layer-by-layer extraction recorded and used in mass balance.
- [ ] Capillary rise saturation clipping properly accounted for in net inflows.
- [ ] Mass balance closure error $< 0.001\text{ mm}$ verified on dry and wet profiles.
- [ ] Unit tests added to test suite.
