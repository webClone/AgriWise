# Layer 2: Vegetation Intelligence & Canopy Dynamics (v5.1)

## 1. Overview and Architectural Scope

**Layer 2 (Vegetation Intelligence)** converts fused Layer 1 multi-modal field tensors ($ \mathbf{T}_t $) and qualified ASMAE features into biologically sound canopy dynamics, phenological stage trajectories, crop identification candidates, spatial heterogeneity metrics, and multi-factor stress attributions.

Layer 2 sits between multi-sensor fusion (Layer 1) and process-based diagnostic/prescriptive models (Layer 3 Water Hydrology and Layer 4 Nutrient Balances). It enforces strict epistemic gating: downstream physical engines receive verified biophysical states (LAI, FVC, root zone accessibility) and physical stress deficits ($ S_k $) without conflating diagnostic hypotheses ($ P(H \mid E) $) or prescriptive recommendations.

```mermaid
graph TD
    L1[Layer 1 Multi-Modal Field Tensor] --> L2Run[Layer 2 Runner / Coordinator]
    ASMAE[Layer 0.5 ASMAE Feature Views] --> L2Run
    
    subgraph Layer 2 Core Engine
        L2Run --> GE[Growth Curve Engine<br/>Whittaker-Henderson + GCV]
        L2Run --> PE[Phenology Engine<br/>5D HMM Viterbi + Vernalization]
        L2Run --> CE[Crop Identification<br/>209-Crop Classifier + Authority Gate]
        L2Run --> SE[Spatial Analysis Engine<br/>Moran's I + CUSUM + Theil-Sen]
        L2Run --> SA[Stress Attributor<br/>Compound Synergy + Simplex]
    end

    subgraph Canonical State Contracts
        GE --> BP[Biophysical State: LAI, FVC, fPAR, NPP]
        PE --> PH[Phenological State: Stage, Progress, GDD]
        CE --> CP[Crop Posterior: Authority Receipt]
        SA --> SS[Stress State: S_k Magnitude + P(H|E) Simplex + Impact I_k]
    end

    BP --> X2[Unified Latent State Vector X_t^L2]
    PH --> X2
    CP --> X2
    SS --> X2

    X2 --> L3[Layer 3 Hydrology & Irrigation Process Engine]
    X2 --> L4[Layer 4 Photosynthesis & Nutrient Engine]
    X2 --> L8[Layer 8 Prescriptive Governance]
```

---

## 2. Directory Layout & Module Responsibilities

Layer 2 is structured into a primary coordination package and three companion contract and uncertainty packages:

```
services/agribrain/
├── layer2_veg_int/                   # Primary Vegetation Intelligence Engine
│   ├── runner.py                     # Main coordinator orchestrating growth, phenology, anomalies & CHI
│   ├── schema.py                     # Layer 2 I/O dataclasses and phenology enums
│   ├── growth_engine.py              # Whittaker-Henderson smoother, envelope fitting, biophysical products
│   ├── phenology_engine.py           # 5D HMM Viterbi phenology decoder, chill units, effective GDD
│   ├── crop_identification.py        # 209-crop classifier, 11 scoring modules, candidate ranking
│   ├── crop_observations.py          # Evidence admission contracts for S1/S2 observations
│   ├── crop_posterior.py             # Cryptographically hashed crop authority receipts
│   ├── crop_response_profile.py      # Causal biological progress, cardinal temperatures (T_base, T_opt, T_max)
│   ├── crop_science_data.py          # Reference signatures, Köppen matrices, rotation priors, MENA prevalence
│   ├── crop_ml.py                    # Bayesian classifiers, entropy confidence, feedback store
│   ├── anomaly_engine.py             # STL-lite spectral decomposition, CUSUM drift detection
│   ├── spatial_engine.py             # Moran's I spatial autocorrelation, Mann-Kendall, Theil-Sen zone ranking
│   ├── invariants.py                 # Layer 2 runtime invariants & validation gates
│   ├── features/                     # Feature extraction (SAR temporal, red-edge, phenology dynamics)
│   ├── labels/                       # Hierarchical crop classifier, label stores, dataset builder
│   └── tests/                        # Layer 2 Dedicated Test Suite (212 test cases)
├── layer2_intelligence/              # Context enrichment and multi-factor stress attribution
│   ├── composite_runner.py           # Multi-factor intelligence coordinator
│   ├── stress_attributor.py          # Stress attribution, compound synergy (Mittler 2006), P(H|E) simplex
│   ├── phenology_adjuster.py         # Environmental modulation of developmental progress
│   ├── veg_context_enricher.py       # ASMAE feature view ingestion and fallback resolution
│   ├── weather_normalizer.py         # Climate normalization across reference baselines
│   ├── zone_intelligence.py          # Intra-plot zone aggregation and anomaly zoning
│   └── outputs/layer3_adapter.py     # Transformed state projection for Layer 3 ingestion
├── layer2_contracts/                 # Formal state vectors and transition operators
│   ├── state_contracts.py            # Latent state vector X_t^L2, UncertaintyBudget, simplex definitions
│   └── state_transition.py           # Hydraulic inertia, state propagation, and authority checking
└── layer2_uncertainty/               # Biophysical uncertainty modeling
    └── retrieval_models.py           # Optical & SAR Jacobian retrieval error propagation
```

---

## 3. Mathematical & Algorithmic Specifications

### 3.1 Growth Curve Modeling (`growth_engine.py`)

#### Whittaker-Henderson Smoothing with GCV Lambda
Converts raw, irregularly sampled NDVI into a smooth daily biological trajectory. Solves the penalized least-squares linear system:
$$ (W + \lambda D^T D) z = W y $$
where:
- $ y \in \mathbb{R}^n $ is the vector of observed NDVI values.
- $ W = \text{diag}(w_1, \dots, w_n) $ is the inverse-variance diagonal weight matrix:
  $$ w_i = \frac{1}{\sigma_i^2 + \sigma_{\min}^2}, \quad \sigma_{\min} = 0.01 $$
- $ D \in \mathbb{R}^{(n-d) \times n} $ is the $d$-th order difference matrix ($d=2$).
- $\lambda$ is chosen via Generalized Cross-Validation (GCV):
  $$ \text{GCV}(\lambda) = \frac{n \cdot \| W^{1/2} (y - z) \|^2}{(n - \text{tr}(H))^2} $$
  with hat matrix trace approximated efficiently by $\text{tr}(H) \approx \sum_{i=1}^n \frac{w_i}{w_i + 4\lambda}$.

#### Asymmetric Upper-Envelope Reweighting with Cloud QA Gating
Cloud and shadow contamination create negative biases in optical indices. Layer 2 applies iterative asymmetric reweighting (Chen et al. 2004) across $K=3$ envelope passes:
$$
w_i^{(k+1)} = \begin{cases}
w_i^{(k)} \cdot \max(0.1, 1.0 - \text{QA}_{\text{cloud}, i}), & \text{if } y_i < z_i^{(k)} \\
w_i^{(k)} \cdot (1.0 + 0.2 \cdot (1.0 - \text{QA}_{\text{cloud}, i})), & \text{if } y_i \ge z_i^{(k)}
\end{cases}
$$
*Preservation invariant*: If explicit cloud QA is missing, conservative damping ($0.7\times$) is applied to avoid flattening acute physiological collapses (e.g., flash drought, locust attack).

#### Derived Biophysical Retrievals
1. **Leaf Area Index (LAI)** via Beer-Lambert extinction:
   $$ \text{fPAR} = \text{clamp}(1.25 \cdot \text{NDVI} - 0.025, 0.01, 0.95) $$
   $$ \text{LAI} = -\frac{\ln(1 - \text{fPAR})}{k_{\text{ext}}}, \quad k_{\text{ext}} \in [0.4, 0.6] $$
2. **Fractional Vegetation Cover (FVC)** (Carlson & Ripley 1997):
   $$ \text{FVC} = \left( \frac{\text{NDVI} - \text{NDVI}_{\text{soil}}}{\text{NDVI}_{\text{veg}} - \text{NDVI}_{\text{soil}}} \right)^2 $$
   where $\text{NDVI}_{\text{soil}}$ and $\text{NDVI}_{\text{veg}}$ are dynamically derived from the empirical 5th and 95th percentiles of the cycle distribution.
3. **Net Primary Productivity (NPP)** (Monteith 1977 & FAO-56):
   $$ \text{NPP} = \text{fPAR} \cdot \text{PAR} \cdot \epsilon_{\text{LUE}} \cdot T_{\text{scalar}} \cdot W_{\text{scalar}} $$
   Solar irradiance $\text{PAR}$ uses astronomical extraterrestrial radiation $R_a$ (FAO-56 formulation) conditioned on day-of-year and latitude.

---

### 3.2 Phenology Inference Engine (`phenology_engine.py`)

Crop development is modeled as a discrete Hidden Markov Model with continuous 5-dimensional multivariate observations:
$$ \mathbf{o}_t = [\text{NDVI}_t, \Delta \text{NDVI}_t, \text{GDD}_{\text{frac}, t}, \text{NDWI}_t, \text{DayLength}_t] $$

#### States and Transition Constraints
1. Annual states: $\mathcal{S} = \{ \text{BARE\_SOIL}, \text{EMERGENCE}, \text{VEGETATIVE}, \text{REPRODUCTIVE}, \text{SENESCENCE}, \text{HARVESTED} \}$.
2. Perennial states cycle through $\text{DORMANCY}$ rather than $\text{BARE\_SOIL} / \text{HARVESTED}$.
3. Strict monotonicity: Backwards transitions are forbidden ($\log T_{i,j} = -\infty$ for $j < i$ except cycle loops).

#### Effective Development Rate Decomposition
Biological time accumulates via explicit physical decomposition:
$$ \Delta D_t = \text{GDD}_{\text{raw}, t} \cdot f_{\text{photoperiod}}(\text{DayLength}_t) \cdot f_{\text{thermal}}(T_{\max, t}) $$
- **Thermal Time**: $\text{GDD}_{\text{raw}, t} = \max(0, T_{\text{mean}, t} - T_{\text{base}})$.
- **Photoperiod Factor**: For short-day crops, $f_{\text{photo}} = \frac{1}{1 + \exp(1.5 \cdot (\text{DayLength} - P_{\text{crit}}))}$.
- **Heat Penalty** (Sánchez et al. 2014): $f_{\text{thermal}} = \max(0.0, 1.0 - \frac{T_{\max} - T_{\text{opt}}}{10.0})$ when $T_{\max} > T_{\text{opt}}$.

#### Vernalization Chilling Units (Richardson 1974 / Utah Model)
For obligate winter cereals (winter wheat, barley), the $\text{VEGETATIVE} \to \text{REPRODUCTIVE}$ transition is physically blocked until sufficient chill units accumulate:
$$ \text{CU}_{\text{progress}} = \frac{\sum \text{CU}_t}{\text{CU}_{\text{required}}} $$
$$ \text{Penalty}_{\text{vern}} = \begin{cases} 0.0 & \text{if } \text{CU}_{\text{progress}} \ge 0.8 \text{ or not obligate} \\ -20.0 \cdot (1 - \text{CU}_{\text{progress}}) & \text{if } 0.5 \le \text{CU}_{\text{progress}} < 0.8 \\ -50.0 & \text{if } \text{CU}_{\text{progress}} < 0.5 \text{ (forbidden)} \end{cases} $$

#### Semi-Markov Duration Penalties
Dynamic programming (Viterbi decoding) applies duration penalties to prevent stage chattering or biologically implausible residence times:
$$ \text{Pen}_{\text{dur}}(s, \Delta t) = \begin{cases} -5.0 & \text{if } \Delta t < t_{\min}(s) \text{ and transitioning} \\ -2.0 \cdot \frac{\Delta t - 2.5 t_{\exp}(s)}{t_{\exp}(s)} & \text{if } \Delta t > 2.5 t_{\exp}(s) \text{ and self-looping} \end{cases} $$

---

### 3.3 Biophysical Crop Intelligence (`crop_identification.py`)

Identifies crop species across a 209-crop registry using 11 scientific scoring dimensions:
1. Reference NDVI Gaussian matching and peak amplitude scaling.
2. Regional crop calendar windows (MENA/Algeria agro-ecological zones).
3. Multi-spectral index consistency ($\text{EVI}, \text{NDMI}, \text{NDWI}$).
4. Köppen-Geiger climate affinity matrix (Beck et al. 2018).
5. Aridity index and irrigation feasibility.
6. Agronomic crop rotation priors (Bayesian transition matrix).
7. NDVI curve shape descriptors (asymmetry, skewness, greenup slope).
8. Botanical family clustering and tiebreakers.
9. Phenological phase compatibility.
10. Parcel area priors.
11. SAR backscatter temporal stability ($\sigma^0_{VV}, \sigma^0_{VH}$).

#### Epistemic Authority Hierarchy
The identified crop is assigned an explicit authority tier:
- **`CALIBRATED`**: Validated ground truth / release-gated machine learning model.
- **`TRANSFERRED`**: Species-level literature prior matching regional agro-climate.
- **`PRIOR_ONLY`**: Regional statistical likelihood (unresolved satellite sequence).
- **`UNKNOWN`**: Strict fail-closed fallback preventing erroneous prescriptive guidance.

---

### 3.4 Multi-Factor Stress Attribution (`stress_attributor.py`)

Layer 2 decouples **Physical Deficit Magnitude** ($S_k \in [0, 1]$) from **Biological Impact** ($I_k \in [0, 1]$):
- **Physical Deficit ($S_k$)**: A crop-independent index reflecting environmental severity (e.g. soil moisture depletion, canopy temperature excess).
- **Biological Impact ($I_k$)**: The damage inflicted on the specific crop at its current developmental stage:
  $$ I_{k, \text{raw}} = S_k \cdot s_k(c, z) \cdot \beta_{ij} $$
  $$ I_{k, \text{norm}} = \min(1.0, I_{k, \text{raw}}) $$
  where $s_k(c, z)$ is the stage sensitivity multiplier and $\beta_{ij}$ is the compound stress synergy factor.

#### Compound Stress Interaction Matrix (Mittler 2006)
Co-occurring stresses trigger supra-additive biological damage:
| Stress Pair | Synergy Factor $\beta_{ij}$ | Physiological Mechanism |
| :--- | :---: | :--- |
| **WATER + THERMAL** | **1.35** | Stomatal closure prevents transpirational cooling, causing thermal runaway |
| **WATER + SALINITY** | **1.25** | Combined matric and osmotic potential collapse leaf turgor |
| **THERMAL + BIOTIC** | **1.20** | Heat-induced membrane leakage accelerates pathogen colonization |
| **SALINITY + THERMAL** | **1.15** | Ion toxicity exacerbated by high transpiration demand |

*Physical Preservation Invariant*: $\beta_{ij}$ mutates the biological impact ($I_k$) and explanation basis, but **never** alters the physical stress magnitude ($S_k$).

#### Continuous Competing Diagnostic Simplex
Stresses are evaluated as competing hypotheses under a continuous Dirichlet/Bayesian probability simplex:
$$ \sum_{H \in \mathcal{H}} P(H \mid E) = 1.0, \quad \mathcal{H} = \{ \text{WATER}, \text{THERMAL}, \text{NUTRIENT}, \text{SALINITY}, \text{BIOTIC}, \text{UNRESOLVED} \} $$
- $H_{\text{UNRESOLVED}}$ is continuously active from timestep zero to absorb unexplained vegetation decline residuals.
- Epistemic uncertainty is tracked via Shannon entropy: $H(P) = -\sum_{H} P(H \mid E) \ln P(H \mid E)$.

---

### 3.5 Spatial Analysis Engine (`spatial_engine.py`)

#### Moran's I Spatial Autocorrelation
Differentiates between widespread abiotic stress (high spatial clustering) and localized biotic attacks (low spatial autocorrelation):
$$ I = \frac{N}{W} \frac{\sum_{i=1}^N \sum_{j=1}^N w_{ij} (x_i - \bar{x})(x_j - \bar{x})}{\sum_{i=1}^N (x_i - \bar{x})^2} $$
- **Spatial Invariant**: Moran's $I$ is calculated **only** when an explicit spatial adjacency matrix or zone centroids $(x_i, y_i)$ are supplied. If geometry is unavailable, the engine emits `status="UNAVAILABLE"` and does not guess coordinates.

#### CUSUM Control Charts & Theil-Sen Trend
- Cumulative Sum (Page 1954) detects persistent structural shifts in spatial variance:
  $$ S_t = \max(0, S_{t-1} + (z_t - k)) $$
- Zone-level trends are fitted using the non-parametric Theil-Sen estimator (median of pairwise slopes):
  $$ \beta = \text{median}\left( \frac{y_j - y_i}{x_j - x_i} \right), \quad i < j $$

---

### 3.6 Canonical Latent State Contract (`layer2_contracts`)

The consolidated output of Layer 2 is the **Unified Latent Vegetation State Vector** ($X_t^{L2}$):

```python
@dataclass
class VegetationState:
    plot_id: str
    timestamp: datetime
    
    # Biological development coordinate
    development_time: float             # Accumulated biological time D_t
    phenology_stage: str                # Current Viterbi stage
    stage_progress_fraction: float      # [0.0, 1.0] relative to cycle
    crop_authority: CropKnowledgeAuthority
    
    # Physical canopy & root state
    lai: float                          # Leaf Area Index (m2/m2)
    fvc: float                          # Fractional Vegetation Cover [0, 1]
    fpar: float                         # Fraction of Absorbed PAR [0, 1]
    biomass_proxy: float                # Accumulated dry matter (g/m2)
    canopy_water_index: Optional[float]
    root_depth_proxy_m: Optional[float] # Active rooting depth (m)
    root_zone_accessibility: str        # SHALLOW | MODERATE | DEEP
    
    # Multi-tier stress states
    physical_stress_states: Dict[str, StressMagnitudeState]
    diagnostic_hypothesis_state: StressHypothesisState
    biological_impact_states: Dict[str, StressImpactEstimate]
    
    # Quality & Provenance
    data_health_score: float
    provenance: InferenceProvenance
```

#### Quad-Component Uncertainty Budget
All retrieved state variables propagate uncertainty via quadratic quadrature:
$$ \sigma_{\text{total}} = \sqrt{\sigma_{\text{sensor}}^2 + \sigma_{\text{retrieval}}^2 + \sigma_{\text{conflict}}^2 + \sigma_{\text{model}}^2} $$

---

## 4. Test Suite and Verification

The Layer 2 test suite has been centralized into [`services/agribrain/layer2_veg_int/tests/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/tests/) containing **24 test modules** and **212 tests**:

| Test Module | Tests | Scope |
| :--- | :---: | :--- |
| `test_crop_cycle_context_v2.py` | 12 | Cycle context building, multi-season boundaries, rotation validation |
| `test_crop_evidence_contracts_v2.py` | 5 | Immutable typed crop evidence ledgers and state schemas |
| `test_crop_farmer_authority_conditioning.py` | 1 | Farmer crop declaration vs. model conflict arbitration |
| `test_crop_governance_contracts.py` | 8 | Crop governance receipts, model version seals, tamper detection |
| `test_crop_identify_dto.py` | 5 | Crop candidate DTO serialization, candidate ranking validation |
| `test_crop_identify_endpoint_behavior.py` | 2 | REST endpoint behavior, fail-closed handling on missing tensors |
| `test_crop_label_authority.py` | 6 | Multi-tier label authority, human audit overrides |
| `test_crop_label_training_authority.py` | 9 | Supervised training data admission and quality tier gating |
| `test_crop_model_input_governance.py` | 13 | Model input governance, anti-leakage checks, tensor dimensionality |
| `test_crop_model_release_gate.py` | 6 | Production model release gates, accuracy and F1 acceptance thresholds |
| `test_crop_observation_admission.py` | 21 | S2 optical observation admission, cloud masking, outlier clipping |
| `test_crop_prior_feedback_safety.py` | 12 | Feedback loops safety, anti-overfitting priors |
| `test_crop_runtime_declaration_closure.py` | 9 | Runtime closure when farmer declarations conflict with phenology |
| `test_crop_s1_observation_admission.py` | 17 | S1 SAR observation admission, incident angle correction, speckle filtering |
| `test_crop_science_provenance.py` | 3 | SHA-256 cryptographic provenance of crop science parameters |
| `test_crop_season_evidence_and_acquisition.py` | 8 | Acquisition scheduling and temporal coverage verification |
| `test_l2_crop_conditioned_pipeline.py` | 26 | Full Layer 2 pipeline integration, compound stress amplification |
| `test_l2_p0_fixes.py` | 11 | P0/P1 regression tests (vernalization, photoperiod, FAO-56 Ra, Moran's I) |
| `test_l2_phase2_whittaker.py` | 4 | Inverse-variance weighting, cloud QA envelope gating, integrals |
| `test_l2_phase3_phenology.py` | 2 | Development rate decomposition, semi-Markov duration penalties |
| `test_l2_phase4_biophysical.py` | 3 | Dynamic FVC endpoints, optical CWSI proxy, RTM stub interfaces |
| `test_l2_state_estimation_closure.py` | 9 | Uncertainty budget quadrature, continuous hypothesis simplex, state transitions |
| `test_phenology_publication_authority.py` | 6 | Phenology publication receipt verification, downstream authority |
| `test_phenology_single_owner.py` | 15 | Single-owner phenology enforcement, immutability, no floor clipping |
| **Total** | **212** | **100% Green across all 212 tests** |

### Multi-Layer Combined Test Verification
When executed concurrently across the foundational layers:
- **Layer 0 (`layer0`)**: 27 tests passing.
- **Layer 0.5 (`layer05_asmae`)**: 60 tests passing.
- **Layer 1 (`layer1_fusion`)**: 21 tests passing.
- **Layer 2 (`layer2_veg_int`)**: 212 tests passing.
- **Total Combined**: **320 tests passing (0 failures, 100% green)**.
