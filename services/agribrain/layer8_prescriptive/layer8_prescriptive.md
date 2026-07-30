# Layer 8 Audit: Prescriptive Advisories & Sprinkling Gates (layer8_prescriptive)

## 1. Executive Summary & Verification Status
Layer 8 (Prescriptive) is the decision-framing and advisory synthesis gate of the AgriBrain architecture. It translates diagnostic states into ranked action cards, schedules them under weather/resource constraints, manages decision fatigue (cognitive load), and frames recommendations to maximize farmer adoption.
* **Code Integrity:** High. Zero compile issues.
* **Test Status:** 151/151 unit tests passed; all 13 regression suite checks passed.
* **Specialized Engines:** Wires 12 pipeline steps and 10 specialized advisory gates.

---

## 2. Granular Engine Inventory & Mapping
1. **ActionRankingEngine** ([action_ranker.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/action_ranker.py)): Scores and sorts actions using multi-objective prioritization.
2. **PhenologyDosingEngine** ([engines/phenology_dosing.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/phenology_dosing.py)): Modulates chemical/nutrient rates to match BBCH growth stages.
3. **CropCoolingEngine** ([engines/crop_cooling.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/crop_cooling.py)): Recommends micro-sprinkling to counter extreme heat shocks.
4. **FrostSprinklingEngine** ([engines/frost_sprinkling.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/frost_sprinkling.py)): Triggers protective sprinkling when temperature drops near freezing.
5. **SalinityLeachingEngine** ([engines/salinity_leaching.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/salinity_leaching.py)): Calculates leaching irrigation fractions based on soil electrical conductivity.
6. **TillageCompactionEngine** ([engines/tillage_compaction.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/tillage_compaction.py)): Evaluates deep tillage needs using bulk density.
7. **NutrientInteractionEngine** ([engines/nutrient_interaction.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/nutrient_interaction.py)): Adjusts rates based on Liebig's minimum and antagonism matrices.
8. **VolatilizationInhibitorEngine** ([engines/volatilization_inhibitor.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/volatilization_inhibitor.py)): Suggests NBPT inhibitors for surface urea applications under high pH and temperature.
9. **IPMCascadeEngine** ([engines/ipm_cascade.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/ipm_cascade.py)): Escalates treatments (from cultural to chemical) using pathogen pressure.
10. **LodgingPGREngine** ([engines/lodging_pgr.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/lodging_pgr.py)): Recommends Plant Growth Regulators (PGR) for dense, over-fertilized cereal canopies.
11. **EnvironmentalRiskEngine** ([engines/environmental_risk.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/environmental_risk.py)): Restricts pesticide spraying near sensitive borders.
12. **SprayDriftGateEngine** ([engines/spray_drift_gate.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py)): Enforces US EPA pesticide drift buffers and weather gating.
13. **ConstraintScheduler** ([scheduler.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/scheduler.py)): Evaluates weather forecasts to build calendar schedules.
14. **ZonePrioritizer** ([zone_prioritizer.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/zone_prioritizer.py)): Directs prescriptions to high-priority zones.
15. **CognitiveLoadEngine** ([engines/cognitive_load.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/cognitive_load.py)): Suppresses low-priority actions to prevent decision fatigue.
16. **AdoptionEngine** ([engines/adoption_model.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/adoption_model.py)): Evaluates adoption probability via Technology Acceptance Model (TAM) heuristics.
17. **FramingEngine** ([engines/framing_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/framing_engine.py)): Frames messages using Prospect Theory (Gain vs. Loss framing).

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - `Layer8Input` containing diagnoses, nutrient state indexes, pathogen risks, spatial zone IDs, crop configs, and data quality grades.
  - Aligned weather forecast matrices.
* **Outputs Generated:**
  - `Layer8Output` containing ranked action cards, calendar schedules, zone plans, tradeoffs, and gross ROI outcome projections.

---

## 4. Key Mathematical Formulations

### A. Multi-Objective Action Ranking
Action priority scores are computed via a weighted linear combination of five dimensions:
$$\text{Priority} = w_{impact} \cdot S_{impact} + w_{urgency} \cdot S_{urgency} + w_{risk} \cdot S_{risk} + w_{cost} \cdot S_{cost} + w_{confidence} \cdot S_{confidence}$$
Where actual code weights are defined as:
* $w_{impact} = 0.30$
* $w_{urgency} = 0.25$
* $w_{risk} = 0.20$
* $w_{cost} = 0.10$
* $w_{confidence} = 0.15$

#### Reliability-Aware Gating Adjustments (L0 Audit Grade)
* **Grade A / B (Normal):** Full ranking, all actions eligible.
* **Grade C (Low Trust / Conflict Flag):** Prefer `SCOUT` / `MONITOR` actions. Mark irreversible actions (e.g. `SPRAY`, `FERTILIZE`, `REPLANT`) as `requires_confirmation = True`.
* **Grade D / F (Very Low Trust):** Restrict allowed actions to safe fallback actions (`SCOUT`, `WAIT`, `MONITOR`). Block irreversible actions (`is_allowed = False`, `blocked_reason = ["audit_grade_too_low"]`).
* **Rate Spread Adjustment:** Recommendation rate spreads are widened based on confidence level:
  $$\text{Spread} = \begin{cases} \pm 30\% & \text{for } \text{MODERATE} \text{ confidence} \\ \pm 50\% & \text{for } \text{LOW} \text{ confidence} \end{cases}$$

### B. EPA Spray Drift Buffer Zone Gating
If maximum wind speed in the forecast exceeds $25\text{ km/h}$, pesticide spray actions are prohibited (`is_allowed = False` with warning). Otherwise, the compliance engine calculates the required buffer zone footprint in meters:
$$\text{Buffer Zone (meters)} = \max\left(10.0, \frac{\text{Wind Speed (km/h)}}{5.0} \times 15.0 \times C_{nozzle}\right)$$
Where nozzle diameter coefficients ($C_{nozzle}$) are:
- `FINE`: 1.2
- `MEDIUM`: 1.0
- `COARSE`: 0.7
- `ULTRA_COARSE`: 0.4

### C. TAM compliance Neural Network Model (2-Layer MLP)
Predicts compliance compliance probability ($P_{adopt}$) based on perceived usefulness, ease of use, familiarity, cost, trust, and urgency:
* **Neural Network Topology:**
  - Input vector $X = [x_1, x_2, x_3, x_4, x_5, x_6] \in \mathbb{R}^6$
  - Hidden Layer: 4 neurons with ReLU activation: $a_1 = \max(0, X \cdot W_1 + b_1)$
  - Output Layer: 1 neuron with Sigmoid activation: $P_{adopt} = \text{Sigmoid}(a_1 \cdot W_2 + b_2)$
* **Feature Vector Mapping:**
  1. $x_1$ (perceived usefulness): $\min(1.0, \text{Priority} \cdot 2.0 \cdot C_{confidence})$ (where $C_{high}=0.90, C_{med}=0.65, C_{low}=0.35$).
  2. $x_2$ (perceived ease): type baseline (e.g., `MONITOR`=0.95, `IRRIGATE`=0.70, `SPRAY`=0.40, `REPLANT`=0.25).
  3. $x_3$ (familiarity): type baseline (e.g., `MONITOR`=0.95, `FERTILIZE`=0.85, `SPRAY`=0.65, `REPLANT`=0.20).
  4. $x_4$ (cost sensitivity): $\min(1.0, \text{cost}_{ratio} / 0.05)$, where $\text{cost}_{ratio} = \text{cost}_{action} / \text{revenue}_{expected}$.
  5. $x_5$ (trust grade score): L0 grade mapping ($A=1.0, B=0.8, C=0.6, D=0.4, F=0.2$).
  6. $x_6$ (urgency): $S_{urgency}$ score.
* **Online Training (Backpropagation):** Computes cross-entropy loss gradients and executes Stochastic Gradient Descent weight updates to adapt dynamically to farmer compliance logs.

### D. Prospect Theory Framing (Kahneman & Tversky 1979)
Frames message recommendations dynamically to maximize adoption based on loss-aversion:
* **Frame Type Selection:**
  - **LOSS Frame:** if urgency $> 0.7$ and impact $> 0.5$ (e.g., "*Without action, expect up to X% yield reduction...*").
  - **GAIN Frame:** if urgency $< 0.4$ or impact $< 0.3$ (e.g., "*This action could improve yield by Y%*").
  - **NEUTRAL Frame:** otherwise, or if confidence level is `LOW` (avoids unverified claims).
* **Yield Impact Scaling:**
  - Estimated yield loss (LOSS Frame): $15\% \times S_{impact}$
  - Estimated yield gain (GAIN Frame): $12\% \times S_{impact}$
* **Financial Anchoring:** cost is anchored to potential loss:
  $$\text{Anchoring String} = \text{"\$Cost/ha to protect \$ProtectedValue/ha crop value"}$$

### E. Volatilization Urea Gating
NBPT urease inhibitors are automatically appended to nitrogen applications if:
$$\text{Soil pH} > 7.5 \quad \land \quad \text{Air Temperature} > 25^\circ\text{C} \quad (\text{Volatilization danger zone})$$

---

## 5. Audit Recommendations
1. **Integrate Equipment Constraints:** Connect fertilizer spreader bandwidth constraints directly to the scheduler.
2. **Expand Framing Translations:** Provide framed messaging outputs in localized Arabic and Tamazight dialects.
