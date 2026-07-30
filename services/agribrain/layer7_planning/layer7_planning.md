# Layer 7 Audit: Planning Engine (layer7_planning)

## 1. Executive Summary & Verification Status
Layer 7 (Planning) evaluates regional crop suitability, planting windows, seedbed workability, and farm economics. It leverages the 209-crop CCL library to compute optimized planting dates and crop rotation schedules.
* **Code Integrity:** High. Zero compile issues.
* **Test Status:** Crop alternative evaluation and aridity indexing are fully verified.
* **Specialized Engines:** Wires 8 core engines + 3 advanced engines + 1 SAR soil health trajectory solver.

---

## 2. Granular Engine Inventory & Mapping
1. **Crop Profile Library (CCL)** ([engines/ccl_crop_library.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/ccl_crop_library.py)): Stores base parameters (Harvest Index, GDD thermal comfort bounds, Mitscherlich inputs) for 209 crops.
2. **Planting Window Engine (PWE)** ([engines/pwe_planting_window.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/pwe_planting_window.py)): Evaluates planting windows based on historical temperature and frost recurrence.
3. **Seedbed Workability (STE)** ([engines/ste_seedbed.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/ste_seedbed.py)): Assesses soil trafficability using texture and moisture.
4. **Water Feasibility (WFE)** ([engines/wfe_water_feasibility.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/wfe_water_feasibility.py)): Compares water requirements against regional allocations.
5. **Biotic Risk Feasibility (BRF)** ([engines/brf_biotic_risk.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/brf_biotic_risk.py)): Maps historical disease pressure to potential rotations.
6. **Yield Distribution (YVE)** ([engines/yve_yield_distribution.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/yve_yield_distribution.py)): Runs yield forecasts for candidate crop scenarios.
7. **Economics Engine (EOE)** ([engines/eoe_economics.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/eoe_economics.py)): Predicts revenues, variable costs, and gross profits.
8. **Execution Planner (PED)** ([engines/ped_planner.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/ped_planner.py)): Formulates sowing calendars.
9. **Crop Rotation (CRB)** ([engines/crb_crop_rotation.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/crb_crop_rotation.py)): Suggests crop options to optimize nitrogen fixation and break disease cycles.
10. **Microclimate Engine (ACM)** ([engines/acm_microclimate.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/acm_microclimate.py)): Isolates terrain-induced thermal decoupling.
11. **Climate Resilience (CCR)** ([engines/ccr_resilience.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/ccr_resilience.py)): Evaluates crop tolerance to sandstorms and droughts.
12. **Soil Health Trajectory Engine** (within [runner.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/runner.py)): Computes soil structure degradation risks from SAR S1 backscatters.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - `OrchestratorInput` detailing coordinates, date ranges, and target crops.
  - Aligned environmental tensors from Layer 1.
  - Active pathogen risk logs from Layer 5.
* **Outputs Generated:**
  - `Layer7Output` containing lists of alternative crop evaluations, rank scores, per-zone suitability indexes, and planting instructions.

---

## 4. Key Mathematical Formulations

### A. SAR Soil Health Trajectory & Tillage Detection
Tillage events are detected using sudden spikes in Sentinel-1 VV backscatter:
$$\text{VV}_{spike} = \text{VV}_{current} - \text{mean}(\text{VV}_{window}) > 3.0\text{ dB}$$
Topsoil structure health score decays based on cumulative detected tillage spikes:
$$\text{Soil Health Score} = \begin{cases}
1.0 & \text{if } \text{TillageSpikes} == 0 \\
0.85 & \text{if } \text{TillageSpikes} == 1 \\
0.60 & \text{if } 2 \le \text{TillageSpikes} \le 3 \\
0.40 - 0.05 \cdot (\text{TillageSpikes} - 4) & \text{otherwise}
\end{cases}$$

### B. Single-Crop Suitability Indexing
Weighted synthesis of biophysical limitations:
$$\text{Suitability} = w_{window} \cdot P_{window} + w_{water} \cdot P_{water} + w_{soil} \cdot P_{soil} + w_{bio} \cdot P_{bio} + w_{rotation} \cdot P_{rotation} + w_{micro} \cdot P_{micro} + w_{resil} \cdot P_{resil} + w_{econ} \cdot P_{econ} - 0.45 \cdot \text{UnknownRiskPenalty}$$
Where:
* Weights: $w_{window} = 0.20, w_{water} = 0.15, w_{soil} = 0.15, w_{bio} = 0.08, w_{rotation} = 0.12, w_{micro} = 0.08, w_{resil} = 0.12, w_{econ} = 0.10$.
* UnknownRiskPenalty is the sum of $(1 - \text{Confidence})$ across all evaluated domains.

### C. Seedbed Workability index
STE evaluates workability based on soil moisture relative to field capacity and wilting point:
$$\text{Workability} = \begin{cases}
1.0 & \text{if } \theta_{wp} \cdot 1.1 \le \text{SM} \le \theta_{fc} \cdot 0.85 \\
0.0 & \text{if } \text{SM} \ge \theta_{fc} \quad (\text{too wet / muddy}) \\
0.3 & \text{if } \text{SM} \le \theta_{wp} \quad (\text{too dry / compacted})
\end{cases}$$

---

## 5. Audit Recommendations
1. **Dynamic Economic Budgets:** Connect fertilizer prices to the EOE engine to refine net crop margin calculations.
2. **Crop Rotation Database Expansion:** Build specific rotational constraints for North African desert climates.
