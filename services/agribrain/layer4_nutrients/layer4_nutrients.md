# Layer 4 Audit: Nutrients & Soil Chemistry (layer4_nutrients)

## 1. Executive Summary & Verification Status
Layer 4 is the core nutrient management and soil chemistry engine of the AgriBrain system. It integrates biophysical proxies, tissue tests, CEC estimates, soil water balance, and nutrient interactions to compile optimal fertilizer prescriptions and soil amendment calendars.
* **Code Integrity:** High. Wires 22 active specialized engines.
* **Test Status:** 151/151 unit tests passed; all 13 regression suite checks passed.
* **Database State:** Linked to the centralized 209-crop genetics database.

---

## 2. Granular Engine Inventory & Mapping (22 Engines)
The layer integrates 22 active sub-engines:

### A. Soil Water & Crop Demand (v2.0)
1. **SoilWaterBalanceEngine** ([soil_water_balance/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/soil_water_balance/engine.py)): Computes daily water percolation, transpiration, and stress indexes.
2. **CropDemandUptakeEngine** ([crop_demand/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/crop_demand/engine.py)): Evaluates crop uptake curves across growth stages.
3. **NutrientObservationProxyEngine** ([proxies/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/proxies/engine.py)): Infers nutrient states from spectral red-edge indexes and soil tests.
4. **TillageDetector** ([proxies/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/proxies/engine.py)): Detects soil disturbance events using Sentinel-1 backscatter coherence drops.
5. **SOCDynamics** ([proxies/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/proxies/engine.py)): Simulates soil organic carbon mineralization based on tillage and temperature.
6. **NutrientInferenceEngine** ([inference/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/inference/engine.py)): Executes Bayesian log-odds mapping of nitrogen, phosphorus, and potassium deficiencies.
7. **OptimizationEngine** ([optimization/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/optimization/engine.py)): Calculates Mitscherlich yield response portfolios.
8. **PlanningEngine** ([planner/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/planner/engine.py)): Schedules application dates in a phenology-aware DAG.

### B. Soil Chemistry & VRA (v3.0)
9. **CECEngine** ([soil_chemistry/cec_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/soil_chemistry/cec_engine.py)): Estimates Cation Exchange Capacity from soil clay, sand, and organic matter.
10. **LimingEngine** ([soil_chemistry/liming_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/soil_chemistry/liming_engine.py)): Prescribes pH correction rates via the SMP buffer method.
11. **VRAEngine** ([vra/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/vra/engine.py)): Maps variable rate fertilizer applications onto Layer 2 zones.
12. **ResidualCreditEngine** ([residual_credit/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/residual_credit/engine.py)): Computes nitrogen credits from legumes or cover crop residue.
13. **NUEEngine** ([nue/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/nue/engine.py)): Tracks nutrient use efficiency.
14. **TissueAnalysisEngine** ([tissue_analysis/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/tissue_analysis/engine.py)): Interprets tissue tests via DRIS (Diagnosis and Recommendation Integrated System).
15. **NutrientInteractionEngine** ([nutrient_interactions/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/nutrient_interactions/engine.py)): Models Liebig's Law of the Minimum and nutrient antagonisms.

### C. Advanced Biophysical Models (v4.0)
16. **PhosphorusSorptionEngine** ([phosphorus_sorption/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/phosphorus_sorption/engine.py)): Models P-fixation kinetics using Langmuir isotherm equations.
17. **SalinityEngine** ([salinity/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/salinity/engine.py)): Assesses salinity impacts using Maas-Hoffman tolerance coefficients.
18. **BiologicalFixationEngine** ([biological_fixation/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/biological_fixation/engine.py)): Models symbiotic N-fixation in legumes.
19. **MicronutrientChemistryEngine** ([micronutrient_chemistry/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/micronutrient_chemistry/engine.py)): Evaluates micronutrient availability (Fe, Mn, Zn, Cu, B) as a function of soil pH, clay, and organic matter.
20. **SoilRespirationEngine** ([soil_respiration/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/soil_respiration/engine.py)): Computes dynamic microbial N-mineralization over the season.
21. **PhotosynthesisNUEEngine** ([photosynthesis_nue/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py)): Couples canopy LAI and fPAR with nitrogen supply rates.
22. **EnvironmentalLossEngine** ([environmental_losses/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/environmental_losses/engine.py)): Models nitrogen losses from volatilization, denitrification, leaching, and runoff.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - Upstream Decision plan diagnostics, daily weather, growth stages.
  - User soil tests (N, P, K, pH, OM, Clay, Sand, EC).
  - Crop varieties, previous crops, cover crops, tissue tests, and spatial zones.
* **Outputs Generated:**
  - `NutrientIntelligenceOutput` containing optimized fertilizer prescriptions, tissue test interpretations, CEC details, and nutrient budgets.
  - Downstream verification calendars.

---

## 4. Key Mathematical Formulations

### A. Mitscherlich-Baule Yield Response Model
Used to predict yield gains ($Y$) from added nutrient doses ($D$):
$$Y(D) = A_{actual} \cdot \left(1 - e^{-c \cdot (N_{soil} + D)}\right)$$
Where $A_{actual}$ is the water-limited maximum potential yield, $c$ is the crop-specific responsiveness rate, and $N_{soil}$ is the baseline soil nutrient level.

### B. Maas-Hoffman Salinity Model
Predicts relative crop yield decline ($Y_{rel}$) based on soil electrical conductivity ($EC_e$):
$$Y_{rel} = \begin{cases}
100 & \text{if } EC_e \le a \\
100 - b \cdot (EC_e - a) & \text{if } EC_e > a
\end{cases}$$
Where $a$ is the salinity threshold (dS/m) and $b$ is the percent yield loss per dS/m increase (e.g. $a = 1.7, b = 12.0$ for wheat).

### C. Nitrogen Deficiency Causal Gating
Base nitrogen deficiency probability derived from spectral red-edge indexes is dynamically down-weighted in the presence of severe water stress:
$$P(N_{deficiency})_{final} = P(N_{deficiency})_{raw} \times \text{GatingFactor} \quad \text{where } \text{GatingFactor} = 0.4 \text{ if } \text{WaterStress} > 50\%$$

### D. Langmuir Phosphorus Sorption
Models phosphorus immobilization in clay/acidic soils:
$$P_{sorbed} = \frac{Q_{max} \cdot K_{L} \cdot C_{eq}}{1 + K_{L} \cdot C_{eq}}$$
Where $Q_{max}$ is the maximum P sorption capacity, $K_L$ is the sorption energy constant, and $C_{eq}$ is equilibrium solution P.

### E. Cation Exchange Capacity (CEC) Soil Chemistry Model
$$\text{CEC}_{estimated} = (0.5 \cdot \text{Clay}\%) + (2.0 \cdot \text{OM}\%) \quad (\text{meq/100g})$$

---

## 5. Audit Recommendations
1. **Calibrate Soil Buffering:** Synchronize the liming SMP buffer curves with local Algerian calcareous soils.
2. **Optimize VRA Zones:** Increase VRA spatial resolution to match sub-meter drone imagery grids.
