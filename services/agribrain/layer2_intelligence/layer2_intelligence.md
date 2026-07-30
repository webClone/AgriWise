# Layer 2 Audit: Photosynthetic Vigor and Biophysical Stress Attribution (layer2_intelligence)

## 1. Executive Summary & Verification Status
This sub-module of Layer 2 is responsible for computing zone-level photosynthetic indices and attributing biophysical vegetation anomalies to specific stress categories (water, nutrients, disease).
* **Code Integrity:** High. Spatio-temporal stress attribution and interactions run without error.
* **Test Status:** Passing all core regression tests.
* **Integration Status:** Feeds direct StressEvidence items to Layer 3 Decision engines.

---

## 2. Granular Engine Inventory & Mapping
1. **Layer2IntelligenceEngine** ([engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_intelligence/engine.py)): Orchestrates zone feature filtering, stress summaries, and health metrics.
2. **PhenologyAdjuster** ([phenology_adjuster.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_intelligence/phenology_adjuster.py)): Modulates stress thresholds based on current BBCH crop stages and growing degree days.
3. **StressAttributor** ([stress_attributor.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_intelligence/stress_attributor.py)): Executes the biophysical stress attribution equations.
4. **ZoneIntelligence** ([zone_intelligence.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_intelligence/zone_intelligence.py)): Computes vegetation indices and baseline anomalies per zone.
5. **Layer3Adapter** ([outputs/layer3_adapter.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_intelligence/outputs/layer3_adapter.py)): Serializes stress vectors and diagnostics for Layer 3.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - `Layer1ContextPackage` containing spatial indexes and fused biophysical features from **Layer 1**.
* **Outputs Generated:**
  - `Layer3InputContext` containing zone stress vectors, chlorophyll indices, and evidence lists routed to **Layer 3 (Decision)**.

---

## 4. Key Mathematical Formulations

### A. Photochemical Reflectance Index (PRI)
$$\text{PRI} = \frac{R_{531} - R_{570}}{R_{531} + R_{570}}$$

### B. Bayesian Stress Posterior Probability
Using Naive Bayes Stress Confidence Fusion to aggregate features (NDVI, NDMI, soil moisture, VPD, etc.):
$$P(\text{Stress}_k \mid \text{Evidence}) = \frac{P(\text{Evidence} \mid \text{Stress}_k) \cdot P(\text{Stress}_k)}{\sum_j P(\text{Evidence} \mid \text{Stress}_j) \cdot P(\text{Stress}_j)}$$

### C. Compound Stress Synergy (Mittler 2006)
If multiple co-occurring stresses (e.g. WATER + THERMAL or WATER + NUTRIENT) are detected, a synergistic multiplier is applied to represent compound physiological impairment:
$$\text{Severity}_{compound} = \text{Severity}_{dominant} \times 1.15 \quad (\text{Capped at } 1.0)$$

### D. EO Foundation Model Anomaly Corroboration
Allows the deep learning anomaly score to corroborate existing hand-crafted stress items, or trigger an `UNKNOWN` stress if high anomaly scores are detected in the absence of standard index deviations:
$$\text{Severity}_{new} = \text{Severity}_{old} + \text{boost} \quad \text{where } \text{boost} = \min(0.15, (\text{anomaly\_score} - 0.6) \times 0.375)$$

---

## 5. Audit Recommendations
1. **Increase Prior Diversity:** Dynamically initialize prior probabilities $P(\text{Stress}_k)$ using regional soil type and historical crop rotations.
2. **Refine Stage-Specific Thresholds:** Ensure `PhenologyAdjuster` incorporates specific stress sensitivity curves during the grain-filling phase for cereals.
