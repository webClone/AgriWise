# Task A02: L4 Hydrology Rainfall Discontinuity & N-Leaching Unit Error

## 1. Finding Overview
* **Finding ID:** A02
* **Severity:** **P0 — Physical Discontinuity & Unit Calculation Error**
* **Component:** Layer 4 Nutrients (Soil Water Balance Engine)
* **Primary Target File:** [`services/agribrain/layer4_nutrients/soil_water_balance/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/soil_water_balance/engine.py) (lines 259–317)

---

## 2. Technical Analysis & Code Audit

### Issue 1: Severe Rainfall Effective Precipitation Discontinuity
In `services/agribrain/layer4_nutrients/soil_water_balance/engine.py`, lines 261–266:
```python
# Empirical USDA-SCS approximation for daily effective precipitation
if rain < 250.0:
    p_eff = rain * (125.0 - 0.2 * rain) / 125.0
else:
    p_eff = 0.1 * rain + 25.0  # Assumes heavy tropical runoff
```
#### Mathematical Breakdown:
- At $\text{rain} = 249.9\text{ mm}$:
  $$P_{\text{eff}} = 249.9 \times \frac{125.0 - 0.2 \times 249.9}{125.0} = 249.9 \times \frac{75.02}{125.0} = \mathbf{149.98\text{ mm}}$$
- At $\text{rain} = 250.0\text{ mm}$:
  $$P_{\text{eff}} = 0.1 \times 250.0 + 25.0 = 25.0 + 25.0 = \mathbf{50.00\text{ mm}}$$
- **Discontinuity:** A $0.1\text{ mm}$ increase in precipitation causes an instantaneous drop of **$100.0\text{ mm}$** of soil water input.
- **Root Cause:** The empirical formula used is adapted from the USDA-SCS *monthly* precipitation equation, but modified incorrectly. Furthermore, a daily model should not use monthly empirical coefficients.

---

### Issue 2: Factor-of-10 Dimensional Unit Error in Nitrogen Leaching
In `services/agribrain/layer4_nutrients/soil_water_balance/engine.py`, line 317:
```python
total_n_leached = total_deep_perc * no3_conc_mg_l / 1000.0  # kg N/ha
```
#### Dimensional Derivation:
- Deep percolation is given in millimeters ($1\text{ mm} = 10^{-3}\text{ m}$).
- Area basis is 1 hectare ($1\text{ ha} = 10,000\text{ m}^2$).
- Volume of drainage per hectare per mm:
  $$V = 10^{-3}\text{ m} \times 10,000\text{ m}^2 = 10\text{ m}^3 = 10,000\text{ L/ha}$$
- Mass of nitrogen per hectare:
  $$\text{Mass} = \text{Drainage (L/ha)} \times C\ (\text{mg/L}) = 10,000 \times C\ (\text{mg/ha})$$
- Convert milligrams to kilograms ($1\text{ kg} = 10^6\text{ mg}$):
  $$\text{Mass (kg/ha)} = \frac{10,000 \times C}{1,000,000} = \frac{C}{100} = \mathbf{0.01 \times \text{Drainage (mm)} \times C\ (\text{mg/L})}$$
- **Current code:** divides by `1000.0` (factor $0.001$), underestimating leached mass by **$10\times$**!
- **Chemical Convention:** The comment specifies `# kg N/ha` while the variable name is `no3_conc_mg_l`. If $C$ is $\text{NO}_3^-$ concentration, it must be multiplied by $\frac{M_N}{M_{NO_3}} = \frac{14.0067}{62.0049} \approx 0.2259$ to obtain elemental Nitrogen ($\text{N}$).

---

## 3. Agronomical & Decision Impact
- **Extreme Rainfall Shock:** During heavy tropical storms or flood events ($>250\text{ mm}$), the engine erroneously reports that the soil received only $50\text{ mm}$ of water instead of $>150\text{ mm}$. This falsely triggers drought/water-stress warnings right after catastrophic rainfall!
- **Dangerous Fertilizer Over-Application:** Nitrogen leaching is underestimated tenfold ($10\text{ kg N/ha}$ actual loss is reported as $1\text{ kg N/ha}$). Farmers are advised that their soil retained most fertilizer, leading to severe under-fertilization or conversely uncalibrated top-dressing schedules.

---

## 4. Implementation Plan

### Step 1: Replace Effective Precipitation Formula
Replace lines 261–266 in `services/agribrain/layer4_nutrients/soil_water_balance/engine.py` with a continuous daily runoff formulation (USDA-SCS Curve Number or continuous FAO-56 daily infiltration model):
```python
# Continuous daily effective precipitation calculation
if rain <= 0.0:
    p_eff = 0.0
elif rain <= 5.0:
    # Minimal canopy interception loss (< 5mm)
    p_eff = max(0.0, rain - 1.0)
elif rain <= 125.0:
    # USDA SCS Daily continuous formulation
    p_eff = rain * (1.0 - 0.2 * (rain / 125.0))
else:
    # Continuous high-rain branch ensuring C0 continuity at rain = 125.0 mm:
    # At 125 mm: 125 * (1 - 0.2) = 100.0 mm
    p_eff = 100.0 + 0.5 * (rain - 125.0)
```

### Step 2: Fix Nitrogen Leaching Arithmetic and Chemical Conversion
Replace line 317 with:
```python
# Conversion: 1 mm drainage over 1 ha = 10,000 L/ha.
# (total_deep_perc mm * 10,000 L/ha * no3_conc_mg_l mg/L) / 1,000,000 mg/kg = * 0.01
# If no3_conc is nitrate (NO3-), convert to elemental Nitrogen (NO3-N) via factor 14/62 (~0.2259)
CONVERSION_MM_MG_L_TO_KG_HA = 0.01
NITRATE_TO_NITROGEN_FACTOR = 14.0067 / 62.0049  # 0.2259

total_no3_leached_kg_ha = total_deep_perc * no3_conc_mg_l * CONVERSION_MM_MG_L_TO_KG_HA
total_n_leached = round(total_no3_leached_kg_ha * NITRATE_TO_NITROGEN_FACTOR, 3)
```

---

## 5. Verification & Test Plan

### Automated Regression Tests
Create test suite in `tests/test_a02_hydrology_math.py`:
1. **Continuity Test across Boundary:**
   ```python
   rain_below = 249.9
   rain_above = 250.1
   p_below = compute_effective_precip(rain_below)
   p_above = compute_effective_precip(rain_above)
   assert abs(p_above - p_below) < 1.0, f"Discontinuity detected: {p_below} vs {p_above}"
   ```
2. **N-Leaching Dimensional Test:**
   ```python
   # 10 mm drainage with 50 mg/L NO3
   # 10 mm * 10,000 L/ha = 100,000 L
   # 100,000 L * 50 mg/L = 5,000,000 mg = 5.0 kg NO3/ha
   # Elemental N: 5.0 * 0.2259 = 1.13 kg N/ha
   leached_n = compute_n_leaching(deep_perc_mm=10.0, no3_mg_l=50.0)
   assert math.isclose(leached_n, 1.13, rel_tol=1e-2)
   ```

---

## 6. Progress Tracking Checklist
- [ ] Effective precipitation function rewritten for continuity.
- [ ] Nitrogen leaching formula updated with $0.01$ conversion factor and $\text{NO}_3\to\text{N}$ ratio.
- [ ] Verification tests implemented and passing.
- [ ] Downstream Layer 4 nutrient balances re-verified against golden profiles.
