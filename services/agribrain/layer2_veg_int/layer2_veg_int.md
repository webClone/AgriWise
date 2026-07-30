# Layer 2 Audit: Canopy Dynamics, Growth Modeling, and Crop Identification (layer2_veg_int)

## 1. Executive Summary & Verification Status
This sub-module of Layer 2 models the daily biophysical canopy development, phenological stages, and identifies crop types across Algerian Wilayas.
* **Code Integrity:** Whittaker-Henderson smoother and Viterbi decoding are verified.
* **Test Status:** Crop group mapping, aridity checks, and registry lookups pass the regression suite.
* **Accuracy Gate:** Enforces strict physical limits on Leaf Area Index (LAI) and fractional cover.

---

## 2. Granular Engine Inventory & Mapping
1. **VegetationIntelligenceEngine** ([runner.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/runner.py)): Coordinates execution and computes the composite `CropHealthIndex`.
2. **GrowthCurveEngine** ([growth_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/growth_engine.py)): Executes the Whittaker-Henderson smoother and upper-envelope Savitzky-Golay filtering.
3. **PhenologyEngine** ([phenology_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/phenology_engine.py)): Decodes crop developmental stages using a log-space Hidden Markov Model (HMM) and Viterbi decoding.
4. **CropIdentificationEngine** ([crop_identification.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/crop_identification.py)): Evaluates the plot against a 209-crop registry using aridity indices and Köppen climate boundaries.
5. **TemporalAnomalyEngine** ([anomaly_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/anomaly_engine.py)): Monitors stress drop anomalies using robust Z-scores and Isolation Forests.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - Unified daily plot-level fused NDVI, EVI, NDWI, and NDMI timeseries.
  - Soil texture and meteorological forcing variables from Layer 1.
* **Outputs Generated:**
  - `ModelledCurveOutput` containing Whittaker-SG ensemble smoothed NDVI fits and derivatives.
  - `CropHealthIndex` composite scores and crop classification probabilities.

---

## 4. Key Mathematical Formulations

### A. Whittaker-Henderson Banded System
Minimizes the sum of squared residuals plus a penalty on the roughness of the curve:
$$(W + \lambda D^T D) z = W y$$
Where $W$ is the diagonal weights matrix (inverse-variance normalized to $[0, 1]$), $D$ is the $d$-th difference operator matrix (typically $d=2$), $y$ represents the raw observations, and $z$ is the smoothed output.
* **Envelope Bias Correction Pass:** Iteratively adjusts weights to fit the upper envelope (cloud-free values):
  $$w_{new} = \begin{cases} 0.5 \cdot w & \text{if } y_t < z_t \quad (\text{cloud-contaminated}) \\ 1.2 \cdot w & \text{if } y_t \ge z_t \quad (\text{likely clean canopy}) \end{cases}$$
  Weights are clipped to $[0.01, 5.0]$ across 3 iterations.

### B. Double Logistic Asymmetric TIMESAT Model
Fits crop greenup and senescence Sigmoid boundaries:
$$\text{NDVI}(t) = \text{base} + \text{amplitude} \cdot \left[ \frac{1}{1 + e^{-a_1 (t - t_1)}} - \frac{1}{1 + e^{-a_2 (t - t_2)}} \right]$$
Where:
- $a_1$ and $a_2$ are greenup and senescence steepness rates.
- $t_1$ and $t_2$ are the greenup and senescence midpoint times.

### C. Fractional Vegetation Cover (FVC)
Calculated from NDVI limits (Carlson & Ripley 1997):
$$\text{FVC} = \left( \frac{\text{NDVI} - \text{NDVI}_{soil}}{\text{NDVI}_{veg} - \text{NDVI}_{soil}} \right)^2$$
Where default soil baseline $\text{NDVI}_{soil} = 0.10$ and fully vegetated $\text{NDVI}_{veg} = 0.85$.

### D. Leaf Area Index (LAI) Estimation
Inferred via Beer-Lambert / Myneni (1997) light absorption formula:
$$\text{LAI} = -\frac{\ln(1 - \text{fPAR})}{k_{ext}}$$
Where:
- $\text{fPAR} = \max\left(0, \min\left(0.95, 1.25 \cdot \text{NDVI} - 0.025\right)\right)$
- $k_{ext} = 0.5$ (extinction coefficient).

### E. Crop Water Stress Index (CWSI)
Normalized NDWI or fallback to NDVI-max envelope (Jackson et al. 1981):
$$\text{CWSI} = 1 - \frac{\text{NDWI} - \text{NDWI}_{min}}{\text{NDWI}_{max} - \text{NDWI}_{min}} \quad \text{or} \quad 1 - \frac{\text{NDVI}}{\text{NDVI}_{max}}$$

### F. CASA Net Primary Productivity (NPP) Model
$$\text{NPP} = \text{fPAR} \cdot \text{PAR} \cdot \epsilon_{max} \cdot T_{scalar} \cdot W_{scalar}$$
Where $\epsilon_{max} = 0.604\text{ gC/MJ}$ and temperature stress $T_{scalar}$ scales down productivity based on deviation from optimal maximum thermal windows ($T_{opt}=25^\circ\text{C}, T_{min}=5^\circ\text{C}, T_{max}=45^\circ\text{C}$).

### G. HMM Viterbi Stage Inference
* **Emission Log-Likelihood:** Evaluates a 5-dimension vector $x_t = [\text{NDVI}, \text{velocity}, \text{GDD\_frac}, \text{NDWI}, \text{photoperiod}]$:
  $$\ln P(x_t \mid s_k) = \sum_{j=1}^5 \ln \mathcal{N}\left(x_{t,j}; \mu_{k,j}, \sigma_{k,j}^2\right) + \text{Penalty}_{GDD}(s_k, GDD_t) + \text{Penalty}_{vern}(s_k, CU_t)$$
  Where the diagonal Gaussian stage signatures $\mathcal{N}(\mu, \sigma^2)$ are:
  - `BARE_SOIL`: $\text{NDVI}\sim(0.12, 0.06)$, $\text{vel}\sim(0.0, 0.005)$, $\text{gdd\_frac}\sim(0.0, 0.05)$, $\text{ndwi}\sim(-0.3, 0.1)$, $\text{photo}\sim(10, 3)$
  - `EMERGENCE`: $\text{NDVI}\sim(0.25, 0.08)$, $\text{vel}\sim(0.01, 0.008)$, $\text{gdd\_frac}\sim(0.08, 0.06)$, $\text{ndwi}\sim(-0.2, 0.1)$, $\text{photo}\sim(11, 2)$
  - `VEGETATIVE`: $\text{NDVI}\sim(0.55, 0.12)$, $\text{vel}\sim(0.008, 0.006)$, $\text{gdd\_frac}\sim(0.3, 0.15)$, $\text{ndwi}\sim(-0.05, 0.12)$, $\text{photo}\sim(13, 2)$
  - `REPRODUCTIVE`: $\text{NDVI}\sim(0.72, 0.10)$, $\text{vel}\sim(0.0, 0.005)$, $\text{gdd\_frac}\sim(0.55, 0.15)$, $\text{ndwi}\sim(0.05, 0.10)$, $\text{photo}\sim(14, 2)$
  - `SENESCENCE`: $\text{NDVI}\sim(0.40, 0.12)$, $\text{vel}\sim(-0.008, 0.006)$, $\text{gdd\_frac}\sim(0.8, 0.15)$, $\text{ndwi}\sim(-0.15, 0.10)$, $\text{photo}\sim(12, 2)$
  - `HARVESTED`: $\text{NDVI}\sim(0.15, 0.06)$, $\text{vel}\sim(-0.002, 0.005)$, $\text{gdd\_frac}\sim(0.95, 0.10)$, $\text{ndwi}\sim(-0.3, 0.1)$, $\text{photo}\sim(11, 3)$

* **Transition Constraints:** Enforces monotonic progression. Log transition probabilities $\ln P(s_{next} \mid s_{curr})$:
  - Self-loop: $\ln(0.92)$
  - Forward transition: $\ln(0.08)$
  - Stage cycle resets: annual harvested to bare soil $\ln(0.05)$; perennial senescence to dormancy $\ln(0.06)$.
  - **Min-Duration Penalty:** Transition probability is penalized by $-5.0$ if the crop spends fewer than the minimum timesteps in the current stage: `BARE_SOIL` (5), `EMERGENCE` (7), `VEGETATIVE` (14), `REPRODUCTIVE` (10), `SENESCENCE` (7), `HARVESTED` (5), `DORMANCY` (14).

### H. Richardson Chill Unit Model (Vernalization)
Chill units ($CU$) accumulate based on daily minimum temperature ($T_{min}$):
$$CU_{accum} = \sum_{t} \mathbb{I}\left(T_{chill\_min} < T_{min,t} < T_{chill\_max}\right)$$
For cereals/perennials: $T_{chill\_min}=0.0^\circ\text{C}, T_{chill\_max}=7.2^\circ\text{C}$. Transition to reproductive stage is gated if progress falls below 80% (vernalization complete):
$$\text{Penalty}_{vern} = \begin{cases} -15.0 & \text{if } \text{progress} < 50\% \\ -8.0 \cdot (1 - \text{progress}) & \text{if } 50\% \le \text{progress} < 80\% \\ 0.0 & \text{if } \text{progress} \ge 80\% \end{cases}$$

### I. Effective GDD Sánchez Model
$$\text{Effective GDD} = \max(0, T_{mean} - T_{base}) \times \text{photo\_factor} \times \text{heat\_penalty}$$
Where:
- Short-day crops: $\text{photo\_factor} = \min(1.0, \text{day\_length} / 14.0)$ (otherwise 1.0).
- Heat stress penalty (Sánchez et al. 2014):
  $$\text{heat\_penalty} = \begin{cases} \max\left(0.0, 1.0 - \frac{T_{max} - T_{opt\_max}}{10.0}\right) & \text{if } T_{max} > T_{opt\_max} \\ 1.0 & \text{if } T_{max} \le T_{opt\_max} \end{cases}$$

---

## 5. Audit Recommendations
1. **Calibrate Extinction Coefficients ($k_{ext}$):** Dynamically calibrate extinction coefficients inside `Beer-Lambert` based on resolved crop types to improve Leaf Area Index accuracy.
2. **Optimize Viterbi Transition Matrix:** Scale HMM transition penalties dynamically during years with extreme early thermal volatility.
