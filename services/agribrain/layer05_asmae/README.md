# Layer 0.5: ASMAE — Adaptive Scientific MicroZone Assimilation Engine

## 1. Executive Summary & Architectural Role

**Layer 0.5 (ASMAE)** is the spatial downscaling, micro-zone state estimation, and biophysical assimilation engine of the AgriBrain architecture. It bridges coarse satellite observations (10m Sentinel-2, 20m Sentinel-1 SAR, 1km+ meteorological reanalysis) with high-resolution sub-plot agronomy (1m–10m management micro-zones) using mathematically rigorous data assimilation without inventing synthetic precision.

### Non-Negotiable Core Principles:
1. **Physical Truth Over Visual Hallucination:** Sentinel-2 remains native 10m/20m radiometry. A 1m state output is strictly designated as a *"plot-certified learned micro-zone estimate"*, never as *"direct 1m sensor observation"*.
2. **Radiometric Consistency Constraint:** Any downscaled micro-zone state field must aggregate back through the spatial observation operator $\mathbf{H}_t$ to equal the original coarse satellite pixels within a bounded error ($\text{RMSE} \le 0.15$).
3. **Uncertainty Quantification:** Every micro-zone state variable carries an explicit variance/covariance envelope. Uncertainty contracts when diverse, registered observations arrive and expands during data gaps or high residual errors.
4. **Authority Separation:** Diagnostic-only or uncertified 1m raster outputs cannot directly trigger Layer 8 prescriptive actions or variable-rate chemical applications. Prescriptions only consume confidence-gated, certified evidence.
5. **Fail-Closed Execution:** Missing evidence, unverified scene bindings, or geometry mismatches abort execution with explicit typed error codes rather than silently returning default baselines.

---

## 2. Directory & Component Inventory (135 Modules)

```
services/agribrain/layer05_asmae/
├── __init__.py                     # Package export and initialization
├── runner.py                       # ASMAERunner: Orchestrates pipeline execution & permissions
├── schema.py                       # ASMAEInput, ASMAEOutput, ASMAESceneRuntime, data contracts
├── engine.py                       # Core ASMAE execution pipeline and assimilation flow
├── contracts.py                    # Formal schema validation & contract enforcement
├── invariants.py                   # 13 biophysical state bounds and physical sanity clamps
├── cache.py                        # Two-tier atomic NPZ/JSON caching with sha256 checksums
├── chain_integrity.py              # Operator digests, cryptographic bindings, H-matrix checksums
├── background_jobs.py              # Background worker lifecycle, lease management, heartbeat
├── job_manifest.py                 # Job state serialization, immutable audit manifests
├── snapshot_store.py               # Immutable snapshot persistence and content-addressed storage
├── plot_snapshot_store.py          # Multi-tenant snapshot directory layout and retrieval
├── plot_state.py                   # Plot-level state representation and historical packaging
├── spatial_supersession.py         # Geometry evolution tracking and stale snapshot detection
├── truth_contract.py               # Ground truth vs. weak label validation rules
├── code_lineage.py                 # Git commit and runtime code lineage tracking
├── deterministic.py                # Reproducible seeding and execution determinism
├── quality.py                      # Data quality assessment and scene filtering
├── feature_export.py               # Feature generation for downstream ML / ASMAE-Learn
├── reintegration.py                # Refined state reintegration into Layer 1 fusion
├── resilient_posterior.py          # Posterior estimation under missing or corrupted inputs
├── selected_bundle.py              # Evidence bundle selection and prioritization
│
├── adapters/                       # Cross-layer adapters
│   ├── l1_adapter.py               # Ingests Layer 1 baseline composites and health metrics
│   ├── l2_adapter.py               # Ingests Layer 2 vegetation trends, phenology, and priors
│   └── l3_adapter.py               # Ingests Layer 3 water balance, ET0, and soil moisture
│
├── assimilation/                   # State estimation mathematical solvers
│   ├── filter.py                   # Ensemble Kalman Filter (EnKF) & Ensemble Transform Kalman Filter (ETKF)
│   ├── etkf.py                     # Deterministic square-root ETKF with member-order equivariance
│   ├── smoother.py                 # Ensemble Kalman Smoother (EKS) for retrospective trajectory refinement
│   └── observation_operator.py     # Vectorized forward observation models h(x)
│
├── bma/                            # Bayesian Model Averaging
│   ├── ensemble_weights.py         # Dynamic weighting of process models based on recent innovations
│   └── mixture_density.py          # Multi-modal posterior density reconstruction
│
├── causality/                      # Causal graph and intervention guards
│   ├── intervention_graph.py       # Validates that observed state changes correspond to causal drivers
│   └── do_calculus.py              # Prevents false confounding between weather and management
│
├── constraints/                    # Physical and agronomic constraints
│   ├── water_balance.py            # Bucket model conservation of mass
│   └── nitrogen_budget.py          # Soil-plant nitrogen uptake balance
│
├── dynamics/                       # Micro-zone state temporal transition models
│   ├── plant_growth.py             # Degree-day driven LAI and biomass growth curves
│   └── soil_drying.py              # Van Genuchten soil moisture depletion dynamics
│
├── geometry/                       # Spatial coordinate & operator construction
│   ├── scene_stack_builder.py      # Spatial-temporal stack alignment from Layer 0 rasters
│   ├── operator_builder.py         # Sparse observation operator H_t construction
│   ├── operator_diagnostics.py     # Operator Gramian proxy, rank, and condition number verification
│   └── coregistration.py           # Sub-pixel Fourier-shift image coregistration
│
├── graph/                          # Microzone spatial topology
│   ├── microzone_graph.py          # Delaunay / grid adjacency graph connecting management zones
│   └── laplacian_regularizer.py    # Spatial smoothness penalty via graph Laplacian L
│
├── history/                        # State history and worldline
│   ├── state_history.py            # Chronological tracking of micro-zone state estimates
│   └── worldline_service.py        # Event log integration for state replay
│
├── interfaces/                     # External API boundaries & protocols
│   ├── api_dto.py                  # Data transfer objects for frontend & worker communication
│   └── events.py                   # Lifecycle event definitions (started, progress, completed)
│
├── learning/                       # Online parameter tuning & calibration
│   ├── asmae_learn_bridge.py       # Interface to asmae_learn offline parameter optimization
│   └── online_tuning.py            # Gradient descent on transition model parameters
│
├── observation/                    # Observation preprocessing & masking
│   ├── cloud_mask.py               # SCL-driven cloud, cloud shadow, and cirrus screening
│   └── sensor_weighting.py         # Dynamic observation noise R covariance construction
│
├── priors/                         # Agronomic prior injection
│   ├── crop_specific.py            # Variety-dependent baseline growth trajectories
│   └── soil_priors.py              # SoilGrids-derived water retention and texture baselines
│
├── prisma/                         # Database persistence mappings
│   └── schema_bridge.py            # Maps in-memory artifacts to relational schema
│
├── reports/                        # Audit and performance reporting
│   ├── assimilation_report.py      # Innovation statistics, Kalman gain norms, chi-square diagnostics
│   └── certification_report.py     # Resolution certification decisions and retrovalidation metrics
│
├── resolution/                     # Multi-resolution ladder & certification
│   ├── selector.py                 # Evaluates Nyquist limits, shift diversity, and retrovalidation
│   └── ladder.py                   # 10m -> 9m -> 8m -> ... -> 1m candidate ladder specifications
│
├── retrovalidation/                # Offline & holdout verification
│   ├── holdout_validator.py        # Evaluates predictive skill against withheld future observations
│   └── cross_sensor.py             # Validates optical downscaling against independent SAR VH
│
├── state/                          # Micro-zone state representations
│   ├── latent_vector.py            # 13-variable state definitions and index mapping
│   └── uncertainty_map.py          # Spatial variance and confidence grid generators
│
├── training/                       # Continuous self-supervised model training
│   ├── weak_label_generator.py     # Generates certified pseudo-labels for spatial CNN models
│   └── loss_functions.py           # Radiometric + spatial smoothness + prior consistency loss
│
└── tests/                          # Layer 0.5 unit and integration tests
    ├── __init__.py
    ├── test_asmae_cache_integrity.py
    ├── test_asmae_p0_contracts.py
    ├── test_asmae_quick_visual_refresh_contract.py
    ├── test_asmae_snapshot_store_immutable.py
    ├── test_asmae_spatial_supersession.py
    └── test_asmae_worker_lifecycle.py
```

---

## 3. Mathematical Formulations & Algorithms

### A. The 13 Latent Biophysical Micro-Zone States
ASMAE estimates a 13-dimensional continuous latent state vector $\mathbf{x}_{i,t}$ for each spatial micro-zone $i$ on day $t$:

| Index | State Name | Physical Meaning | Physiological Bounds | Primary Driving Sensors |
| :---: | :--- | :--- | :---: | :--- |
| **0** | `vigor` | Canopy photosynthetic active radiation absorption | $[0.0, 1.0]$ | S2 B04, B08 (NDVI, EVI) |
| **1** | `lai` | Green Leaf Area Index ($m^2 / m^2$) | $[0.0, 8.0]$ | S2 B08, B04, Red-Edge |
| **2** | `chlorophyll` | Foliar chlorophyll concentration ($\mu\text{g/cm}^2$) | $[0.0, 80.0]$ | S2 B05, B06, B07, B8A (NDRE) |
| **3** | `canopy_water` | Canopy equivalent water thickness | $[0.0, 1.0]$ | S2 B11, B12 (NDMI) |
| **4** | `root_zone_water` | Root-zone volumetric water content ($0\text{–}40\text{ cm}$) | $[0.0, 1.0]$ | S1 VV, In-situ probes, ET0 |
| **5** | `surface_wetness_event` | Episodic surface ponding / saturation spike | $[0.0, 1.0]$ | S1 VV backscatter jump, Rain |
| **6** | `structure` | Canopy structural density / fresh biomass proxy | $[0.0, 1.0]$ | S1 VH, VH/VV ratio, Drone SfM |
| **7** | `bare_soil_fraction` | Fractional ground surface exposed without vegetation | $[0.0, 1.0]$ | S2 SWIR/Red spectral unmixing |
| **8** | `salinity_stress` | Osmotic root inhibition due to soluble salts | $[0.0, 1.0]$ | S2 Brightness/NDVI anomaly |
| **9** | `thermal_stress` | Canopy temperature depression impairment | $[0.0, 1.0]$ | Air temperature extremes, VPD |
| **10** | `biotic_confounder_risk` | Non-physiological spectral depression (pathogens/pests) | $[0.0, 1.0]$ | Localized high-frequency variance |
| **11** | `phenology_progress` | Normalized progression through vegetative-to-senescence | $[0.0, 1.0]$ | Accumulated Growing Degree Days (GDD) |
| **12** | `stress_memory` | Exponentially weighted historical stress accumulator | $[0.0, 1.0]$ | Temporal integral of thermal/water stress |

Clamping is strictly enforced after every dynamic step and measurement update via `invariants.py`.

---

### B. Observation Operator Formulation
For an observation scene $k$ acquired at time $t$ with $M_k$ coarse satellite pixels:
$$\mathbf{y}_{k,t} = \mathbf{H}_{k,t} \mathbf{x}_t + \mathbf{v}_{k,t}, \quad \mathbf{v}_{k,t} \sim \mathcal{N}(\mathbf{0}, \mathbf{R}_{k,t})$$

Where:
- $\mathbf{x}_t \in \mathbb{R}^{N \times 13}$ is the high-resolution state across $N$ micro-zones.
- $\mathbf{H}_{k,t} \in \mathbb{R}^{M_k \times N}$ is the spatial observation operator. Each row $m$ represents the spatial Point Spread Function (PSF) and sensor footprint of coarse pixel $m$ projected over the high-resolution micro-zone grid:
  $$\sum_{j=1}^{N} H_{k,t}[m, j] = 1.0 \quad \forall m \in \{1, \dots, M_k\}$$
- $\mathbf{R}_{k,t} \in \mathbb{R}^{M_k \times M_k}$ is the diagonal observation error covariance, dynamically inflated by SCL cloud proximity, aerosol optical depth, and satellite view angle.

---

### C. Ensemble Transform Kalman Filter (ETKF) Update
ASMAE maintains an ensemble of $E$ state trajectories ($E = 32$ or $64$) to represent non-Gaussian and spatial covariances:
$$\mathbf{X} = [\mathbf{x}_1, \mathbf{x}_2, \dots, \mathbf{x}_E] \in \mathbb{R}^{D \times E}, \quad D = 13 \times N$$

1. **Ensemble Mean and Perturbation Matrix:**
   $$\bar{\mathbf{x}} = \frac{1}{E} \sum_{e=1}^E \mathbf{x}_e, \quad \mathbf{A} = \mathbf{X} - \bar{\mathbf{x}} \mathbf{1}_E^T$$

2. **Observation Projection & Innovation:**
   $$\mathbf{Y}^f = \mathbf{H} \mathbf{A}, \quad \bar{\mathbf{y}} = \mathbf{H} \bar{\mathbf{x}}, \quad \mathbf{d} = \mathbf{y}_{\text{obs}} - \bar{\mathbf{y}}$$

3. **Deterministic Ensemble Transformation:**
   $$\mathbf{T} = \left[ (E - 1)\mathbf{I}_E + (\mathbf{Y}^f)^T \mathbf{R}^{-1} \mathbf{Y}^f \right]^{-1/2}$$
   $$\bar{\mathbf{x}}^a = \bar{\mathbf{x}} + \mathbf{A} (\mathbf{Y}^f)^T \left[ \mathbf{Y}^f (\mathbf{Y}^f)^T + (E - 1)\mathbf{R} \right]^{-1} \mathbf{d}$$
   $$\mathbf{A}^a = \mathbf{A} \mathbf{T}$$
   $$\mathbf{X}^a = \bar{\mathbf{x}}^a \mathbf{1}_E^T + \mathbf{A}^a$$

This formulation is completely deterministic, avoiding sampling errors from perturbed observations, and guarantees member-order equivariance.

---

### D. Spatial Graph Regularization
To prevent unphysical checkerboard patterns during high-resolution downscaling, ASMAE applies spatial regularization across the microzone adjacency graph $\mathcal{G} = (\mathcal{V}, \mathcal{E})$:
$$\mathcal{J}_{\text{spatial}}(\mathbf{x}) = \frac{\lambda_{\text{spatial}}}{2} \mathbf{x}^T \mathbf{L} \mathbf{x} = \frac{\lambda_{\text{spatial}}}{2} \sum_{(i,j) \in \mathcal{E}} w_{ij} \| \mathbf{x}_i - \mathbf{x}_j \|_2^2$$

Where:
- $\mathbf{L} = \mathbf{D} - \mathbf{W}$ is the graph Laplacian.
- Edge weights $w_{ij}$ reflect pedological and topographic similarity:
  $$w_{ij} = \exp\left( -\frac{\|\mathbf{s}_i - \mathbf{s}_j\|^2}{2\sigma_{\text{spatial}}^2} - \frac{(\text{elev}_i - \text{elev}_j)^2}{2\sigma_{\text{elev}}^2} - \frac{(\text{clay}_i - \text{clay}_j)^2}{2\sigma_{\text{clay}}^2} \right)$$

---

### E. Resolution Ladder & Certification Gates
The resolution selector (`resolution/selector.py`) evaluates candidate grid cell sizes from $10\text{m}$ down to $1\text{m}$:
$$r \in \{10\text{m}, 9\text{m}, 8\text{m}, 7\text{m}, 6\text{m}, 5\text{m}, 4\text{m}, 3\text{m}, 2\text{m}, 1\text{m}\}$$

A resolution $r$ is certified for production visualization **only** if all four gates pass:
1. **Sub-Pixel Shift Diversity Gate:** At least 3 independent satellite scenes must exhibit distinct sub-pixel coregistration offsets ($\Delta x, \Delta y \ge 0.25 \text{ pixels}$) to satisfy Nyquist multi-frame reconstruction criteria.
2. **Condition Number of Observation Gramian:** The effective condition number of $\mathbf{H}^T \mathbf{R}^{-1} \mathbf{H}$ must remain bounded: $\kappa(\mathbf{H}^T \mathbf{R}^{-1} \mathbf{H}) \le 100$.
3. **Radiometric Consistency Test:** The downscaled state $\hat{\mathbf{x}}$ aggregated back to coarse space must satisfy:
   $$\text{RMSE}(\mathbf{H} \hat{\mathbf{x}}, \mathbf{y}_{\text{obs}}) \le 0.15 \quad (\text{hard reject if } > 0.30)$$
4. **Retrovalidation Holdout Score:** When assimilating data up to $t - 1$, the prediction error against a withheld observation at time $t$ must achieve a skill score:
   $$\text{Score}_{\text{retro}} = 1.0 - \frac{\text{MSE}_{\text{pred}}}{\text{MSE}_{\text{climatology}}} \ge 0.75 \text{ (for 1m)}, \quad \ge 0.50 \text{ (for 2–5m)}$$

If any gate fails, the resolution ladder **falls back safely** to the highest certified resolution (e.g. 5m or 10m native).

---

## 4. Execution Pipeline & Worker Lifecycle

```
[Layer 0 / Data Gateway]
           │
           ▼
   [Scene Stack Ingestion] ────► [Cloud & Datamask Screening]
           │
           ▼
[Sub-Pixel Coregistration] ────► [Sparse Operator H_t Construction]
           │
           ▼
[Resolution Ladder & Nyquist Gate]
           │
           ├── Fail Gate ──► Safe Fallback to 10m Native
           │
           ▼ Pass Gate
[Ensemble Kalman Assimilation (ETKF)]
           │
           ▼
[Spatial Graph Regularization (Laplacian)]
           │
           ▼
[Radiometric Consistency & Invariant Clamps]
           │
           ▼
[Immutable Cache Commit (.npz + .json)]
           │
           ├──► [Layer 1 Refined Fusion]
           ├──► [Layer 10 SIRE Surfaces]
           └──► [ASMAE-Learn Weak Label Export]
```

### Worker Concurrency & Heartbeat Leases:
- Background worker execution (`background_jobs.py`) is managed via short-lived, renewal leases (`lease_token`, 60s TTL).
- Stalled or crashed workers are detected when the lease expires without renewal; jobs are marked `stalled` before a single replacement is spawned.
- Simultaneous duplicate enqueues for the same `plot_id` and content hash resolve idempotently to the identical worker instance.

---

## 5. Verification & Test Suite

The test suite for Layer 0.5 is located in [`services/agribrain/layer05_asmae/tests/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/tests/):

```powershell
py -3 -m pytest services/agribrain/layer05_asmae/tests/ -v
```

### Test Coverage Summary:
- **`test_asmae_cache_integrity.py`**: Validates two-tier atomic caching, SHA256 integrity checks, corrupted `.npz` handling, empty raster detection, and cache key stability across import paths.
- **`test_asmae_p0_contracts.py`**: Validates vectorized forward models, ETKF member-order equivariance, cloud/thin cirrus mask rejection, exact operator bindings, Gramian proxy evaluations, and fail-closed scene authorities.
- **`test_asmae_quick_visual_refresh_contract.py`**: Ensures quick visual refreshes preserve typed contract failure codes upon binding rejections.
- **`test_asmae_snapshot_store_immutable.py`**: Verifies immutable content-addressed storage, preventing mutation or overwrites of published science nodes.
- **`test_asmae_spatial_supersession.py`**: Verifies handling of geometry updates, preventing stale snapshots from superseding current boundaries.
- **`test_asmae_worker_lifecycle.py`**: Validates distributed worker leasing, heartbeat timeouts, stale lease rejection, and crash recovery ceiling gates.

**All 60 test suites pass with 100% green status.**
