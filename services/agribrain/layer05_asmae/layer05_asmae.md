# Layer 0.5 Audit: Adaptive Scientific MicroZone Assimilation Engine (ASMAE)

## 1. Executive Summary & Verification Status
Layer 0.5 (ASMAE) is the core micro-zone spatial and temporal state-estimation engine of the AgriBrain architecture. It refines coarse satellite observations (10m–60m) into plot-certified learned micro-zone states using Ensemble Kalman Filtering/Smoothing (EnKF/EKS) and spatial microzone graphs.
* **Code Integrity:** High. Pipeline orchestration and diagnostics are fully verified.
* **Feature Gating:** Enforced by the `ASMAE_ENABLED` feature flag to prevent unauthorized production runs.
* **Integration Status:** Generates weak labels for learning and certifies sub-pixel map overlays.

---

## 2. Granular Engine Inventory & Mapping
The engine leverages specialized sub-modules to perform spat-temporal reconstruction:
1. **SceneStackBuilder** (`layer05_asmae/geometry/scene_stack_builder.py`): Gathers and aligns temporal observation records from Layer 0 data gateways.
2. **OperatorBuilder** (`layer05_asmae/geometry/operator_builder.py`): Constructs the observation mapping operator ($H_t$) at candidate resolutions.
3. **Coregistration Solver** (`layer05_asmae/geometry/coregistration.py`): Performs sub-pixel image coregistration to align temporal stacks.
4. **Resolution Selector** (`layer05_asmae/resolution/selector.py`): Evaluates the resolution ladder using Nyquist constraints, scene diversity, and operator quality, selecting the effective resolution.
5. **Operator Diagnostics** (`layer05_asmae/geometry/operator_diagnostics.py`): Programmatically validates $H_t$ operators, hard-gating execution if errors are detected outside shadow mode.
6. **Invariants Gate** (`layer05_asmae/invariants.py`): Enforces non-negotiable biophysical bounds on output state variables.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - `ASMAEInput` bundle containing scene configurations, sensor IDs, CRS details, affine transforms, and quality scores.
  - Coarse agronomic priors from Layer 2 to Layer 8.
* **Outputs Generated:**
  - `ASMAEOutput` containing refined state raster grids (`raster_maps`), uncertainty maps, confidence maps, and a resolution decision audit trail.
  - Exported weak labels for continuous convolutional model training.

---

## 4. Key Mathematical Formulations

### A. $H_t$ Observation Operator Mapping
Maps high-resolution latent states ($x_t$) to coarse raw satellite observations ($y_t$):
$$y_t = H_t x_t + v_t \quad \text{where } v_t \sim \mathcal{N}(0, R)$$
If operator diagnostic errors exceed limits in non-shadow mode, a hard-block RuntimeError is raised.

### B. Radiometric Consistency Constraint
Enforces that downscaled states aggregate back to match the original coarse pixel observations:
$$\| H_t \hat{x}_t - y_t \|_2^2 \le \epsilon_{threshold} \quad (\text{Threshold } \epsilon_{threshold} = 0.15 \text{ RMSE; hard reject at } 0.30)$$

### C. The 13 Latent Micro-Zone States & Physical Bounds
Kalman updates are clamped to the following physical boundaries daily:
1. `vigor` (index 0): Canopy photosynthetic activity $[0.0, 1.0]$
2. `lai` (index 1): Leaf Area Index $[0.0, 8.0]$
3. `chlorophyll` (index 2): Foliar chlorophyll content $[0.0, 80.0] \text{ }\mu\text{g/cm}^2$
4. `canopy_water` (index 3): Canopy water content (NDMI-driven) $[0.0, 1.0]$
5. `root_zone_water` (index 4): Root-zone soil moisture VWC $[0.0, 1.0]$
6. `surface_wetness_event` (index 5): Event-based surface water $[0.0, 1.0]$
7. `structure` (index 6): Canopy/biomass structure (SAR VH) $[0.0, 1.0]$
8. `bare_soil_fraction` (index 7): Exposed soil fraction $[0.0, 1.0]$
9. `salinity_stress` (index 8): Salinity-induced stress $[0.0, 1.0]$
10. `thermal_stress` (index 9): Thermal stress $[0.0, 1.0]$
11. `biotic_confounder_risk` (index 10): Biotic pressure risk $[0.0, 1.0]$
12. `phenology_progress` (index 11): Phenological stage progress $[0.0, 1.0]$ (0=bare soil, 1=harvest)
13. `stress_memory` (index 12): EWMA stress accumulator $[0.0, 1.0]$

### D. Resolution Selection Ladder Nyquist Gates
Candidate resolutions evaluated: $10\text{m}, 9\text{m}, 8\text{m}, 7\text{m}, 6\text{m}, 5\text{m}, 4\text{m}, 3\text{m}, 2\text{m}, 1\text{m}$.
Certification at $1\text{m}$ resolution requires a retrovalidation score $\ge 0.75$; intermediate resolutions require $\ge 0.50$.

---

## 5. Audit Recommendations
1. **Accelerate V71–V79 Implementations:** Integrate the complete mathematical solver for V71 (microzone graph building) and V74 (EnKF/EKS state estimation solver) to replace the current skeleton overrides.
2. **Optimize H_t Memory Layout:** Ensure $H_t$ matrices are strictly stored as SciPy sparse `csr_matrix` formats and written as `.npz` binary files instead of large JSON logs, preserving API performance.
