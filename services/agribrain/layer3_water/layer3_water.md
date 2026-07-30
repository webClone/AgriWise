# Layer 3 Audit: Water & Soil Diagnosis (layer3_water)

## 1. Executive Summary & Verification Status
Layer 3 (Water) computes reference and crop evapotranspiration ($ET_0, ET_c$), dynamic crop coefficients ($Kc$) derived from satellite canopy vegetation indices, and root-zone water balance profiles.
* **Code Integrity:** High. Evapotranspiration, soil moisture, and irrigation optimization modules compile and run cleanly.
* **Test Status:** 151/151 unit tests passed; all 13 regression suite checks passed.
* **Database State:** Integrates with local soil attributes and weather records.

---

## 2. Granular Engine Inventory & Mapping
1. **Evapotranspiration Engine** ([evapotranspiration.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/evapotranspiration.py)): Computes Penman-Monteith and Hargreaves-Samani reference ET and applies dynamic crop coefficient adjustments.
2. **Soil Moisture Engine** ([soil_moisture.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/soil_moisture.py)): Implements the dual-layer soil moisture balance model.
3. **Water Stress Engine** ([water_stress.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/water_stress.py)): Calculates water depletion fractions and crop stress indices.
4. **Irrigation Optimizer** ([irrigation_optimizer.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/irrigation_optimizer.py)): Prescribes optimal irrigation times and volumes based on soil moisture forecasts.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - Daily minimum/maximum temperatures, relative humidity, wind speed, solar radiation.
  - Latitude, elevation, and crop type config.
  - Soil parameters (Field Capacity, Wilting Point, Clay/Sand fractions).
* **Outputs Generated:**
  - `et0` reference evapotranspiration (mm/day) and `etc` crop evapotranspiration.
  - Daily soil moisture VWC profiles and water stress index scores ($K_s \in [0.0, 1.0]$).
  - Recommended irrigation amounts.

---

## 4. Key Mathematical Formulations

### A. FAO-56 Penman-Monteith Reference $ET_0$
$$ET_0 = \frac{0.408 \Delta (R_n - G) + \gamma \frac{900}{T + 273} u_2 (e_s - e_a)}{\Delta + \gamma (1 + 0.34 u_2)}$$
Where $R_n$ is net radiation, $G$ is soil heat flux, $T$ is mean air temperature, $u_2$ is wind speed at 2m, $e_s - e_a$ is vapor pressure deficit, $\Delta$ is slope vapor pressure curve, and $\gamma$ is psychrometric constant.

### B. Hargreaves-Samani Fallback $ET_0$
Used when wind/humidity sensors are unavailable:
$$ET_0 = 0.0023 \cdot R_a \cdot (T_{mean} + 17.8) \cdot \sqrt{T_{max} - T_{min}}$$
Where $R_a$ is extraterrestrial radiation (mm/day equivalent).

### C. FAO-56 Table 12 Crop Coefficients & Advective Adjustment (Eq. 62)
In arid zones (low humidity, high winds), mid-season Kc is adjusted upward to account for advective energy:
$$Kc_{mid} = Kc + \left[0.04 \cdot (u_2 - 2) - 0.004 \cdot (RH_{min} - 45)\right] \cdot \left(\frac{h}{3}\right)^{0.3}$$
Where $u_2$ is wind speed at 2m (m/s), $RH_{min}$ is minimum relative humidity (%), and $h$ is mean crop height (m). Clamped to $[Kc_{mid}, Kc_{mid} + 0.20]$.

### D. Dynamic Crop Coefficient $Kc$ (Johnson & Trout 2012)
Relates crop cover fraction $F_c$ to dynamic $Kc$:
$$F_c = \max\left(0, \min\left(1.0, 1.26 \cdot \text{NDVI} - 0.18\right)\right)$$
$$Kc = Kc_{min} + (Kc_{full} - Kc_{min}) \cdot F_c$$

### E. Dual-Layer Soil Moisture Model
Models water movement through two distinct layers:
* Surface layer (0–10cm):
  $$\text{TopLayer}_{VWC}(t) = \text{TopLayer}_{VWC}(t-1) + \frac{\text{Rain} + \text{Irrigation} - 0.6 \cdot ET_{crop} - \text{Percolation}}{\text{WHC}_{top}}$$
* Root layer (10–40cm):
  $$\text{RootLayer}_{VWC}(t) = \text{RootLayer}_{VWC}(t-1) + \frac{\text{Percolation} - 0.4 \cdot ET_{crop} - \text{Drainage}}{\text{WHC}_{root}}$$

---

## 5. Audit Recommendations
1. **Dynamic Soil Layering:** Allow dynamic root-depth progression ($Z_r$) rather than static 10cm/40cm layer depths.
2. **Local Canopy Calibrations:** Calibrate crop-specific albedos in net radiation ($R_n$) to improve Penman-Monteith accuracy.
