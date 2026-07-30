# Layer 5 Audit: Biophysical & Chemical Engine (layer5_bio)

## 1. Executive Summary & Verification Status
Layer 5 is the core plant pathology, biotic threat, and chemical kinetics engine of the AgriBrain system. It integrates weather disease pressure, spore dispersal vectors, remote anomaly signatures, R-gene crop varieties, chemical wash-off kinetics, and visual CNN photographs to estimate biotic risk profiles.
* **Code Integrity:** High. Wires WDP, SSS, RAS, PIE, and RAP engines.
* **Test Status:** Fully verified. CNN leaf analysis and compound chemical translocations verified.
* **Accuracy Gate:** Enforces strict biophysical boundaries on pathogen probabilities ($[0.0, 1.0]$).

---

## 2. Granular Engine Inventory & Mapping
1. **Weather-Disease Pressure (WDP)** ([engines/weather_pressure.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/engines/weather_pressure.py)): Computes Leaf Wetness Duration (LWD) hours and thermal comfort ranges for pathogens.
2. **Spread Signature Solver (SSS)** ([engines/spread_signature.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/engines/spread_signature.py)): Simulates spatial spore dispersal wind vectors and spread gradients.
3. **Remote/Anomaly Signature (RAS)** ([engines/remote_signature.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/engines/remote_signature.py)): Consolidates index deviations, gated by Layer 3 structural confounder decisions.
4. **Genetical Engine** ([engines/genetical_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/engines/genetical_engine.py)): Evaluates crop variety R-gene susceptibility matching.
5. **Biophysical Engine** ([engines/biophysical_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/engines/biophysical_engine.py)): Models transpiration rates driving systemic chemical translocation.
6. **Chemical Engine** ([engines/chemical_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/engines/chemical_engine.py)): Computes chemical wash-off, half-life degradation, and spray drift risks.
7. **BioThreatInferenceEngine (PIE)** ([engines/inference.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/engines/inference.py)): Runs Bayesian log-odds combination of active symptoms and environmental risk factors.
8. **Response Action Planner (RAP)** ([engines/response_planner.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/engines/response_planner.py)): Formulates localized chemical and cultural recommendations.
9. **Visual Detection Engine** ([visual_detection.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/visual_detection.py)): Evaluates leaf camera photographs via a localized NumPy CNN classifier.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - Upstream Layer 1 tensors, Layer 2 vegetation anomalies, Layer 3 decision logs, and Layer 4 nutrient balances.
  - Plot context variety, coordinate, and applied chemical registries.
  - Optional base64 smartphone photograph strings.
* **Outputs Generated:**
  - `BioThreatIntelligenceOutput` containing threat state classifications (probability, confidence, severity), chemical protection factors, and target-zoned treatment DAGs.

---

## 4. Key Mathematical Formulations

### A. Leaf Wetness Duration (LWD) disease index
Calculates consecutive hours where Relative Humidity ($RH$) exceeds $90\%$ and temperature sits within comfortable pathogen growth ranges ($15^\circ\text{C}$ to $28^\circ\text{C}$):
$$\text{LWD}_{Hours} = \sum_{hour=1}^{24} \mathcal{I}\left(RH_{hour} > 90\% \text{ and } 15 \le T_{hour} \le 28\right)$$

### B. Spore Dispersal & Wind Vector (SSS)
Dispersal of spores from primary infection sources follows a 2D Gaussian wind plume model:
$$C(x, y) = \frac{Q}{2 \pi u \sigma_y \sigma_z} \cdot \exp\left(-\frac{y^2}{2 \sigma_y^2}\right) \cdot \exp\left(-\frac{(z_{spray}-h)^2}{2 \sigma_z^2}\right)$$
Where $Q$ is source strength, $u$ is mean wind speed, and $\sigma_y, \sigma_z$ are downwind dispersion coefficients.

### C. Chemical Protection Half-Life Decay
Fungicide/insecticide active ingredient concentration ($C(t)$) degrades exponentially over time, accelerated by high rainfall wash-off:
$$C(t) = C_0 \cdot e^{-k_{decay} \cdot t} \cdot e^{-\beta_{wash} \cdot \text{Rain}_{mm}}$$
Where $k_{decay} = \frac{\ln(2)}{DT_{50}}$, and $DT_{50}$ is chemical half-life (days). cons. Consumed by the Biophysical Engine to model translocation.

### D. R-Gene Susceptibility Matching Logits
Variety genetic resistance decreases the susceptibility logit if an active match is found:
$$\text{Logit}_{genetic} = \begin{cases}
-1.5 & \text{if } \text{R-gene match exists} \\
+0.5 & \text{if } \text{variety is susceptible} \\
0.0 & \text{otherwise}
\end{cases}$$

### E. Visual Photograph CNN Fusing
If a leaf photograph is uploaded, visual CNN features overwrite spatial indexes when confidence matches:
$$P(\text{Threat}) = \text{Confidence}_{CNN} \quad \text{if } \text{CNN Analysis status} == \text{"analyzed"}$$

---

## 5. Audit Recommendations
1. **Dynamic Half-life Calibrations:** Expand the applied chemical database to include temperature-dependent decay coefficients ($k_{decay}(T)$) for North African climates.
2. **Visual Classifier Expansion:** Incorporate deep VLM APIs to complement the localized NumPy CNN classifier for multi-symptom leaves.
