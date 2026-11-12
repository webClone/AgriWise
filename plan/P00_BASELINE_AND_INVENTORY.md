# Pass P00: Reproducible Baseline & Ecosystem Inventory (Reconciled)
**AgriWise Plot Tool Ecosystem Redesign 2026**  
**Lead Authors:** A0 Architecture Lead, A4 Scientific Integrity Lead  
**Date:** November 12, 2026  
**Status:** RECONCILED & ACCEPTED BASELINE

---

## Executive Summary & Scope Reconciliation

Pass P00 establishes the verified, reproducible baseline of the existing AgriWise plot subsystem before implementing any code changes in Passes P01 through P15.

### Branch & Revision Reconciliation
- **Remote Integration Branch Head:** `integrate/layer0-layer1-observation-pilot` at commit [`3bedecf`](https://github.com/webClone/AgriWise/commit/3bedecf229971827a4ebb96db97163cd5e766c78) (which published the 25 implementation specification documents under `plan/agribrain-tool-ecosystem-redesign-2026-11-12/IMPLEMENTATION_V1`).
- **Local Git Repository Head:** Commit [`1ee2c20`](https://github.com/webClone/AgriWise/commit/1ee2c20119af29dd1f0a0b46c85217d91206b744) (*"fix(pilot): strengthen ASMAE admission with cryptographic content identity binding and mixed-batch regression tests"*).
- **Network Boundary Note:** Direct outbound HTTPS connections to `github.com:443` are restricted in the sandboxed runner environment. Consequently, local baselines were established on `1ee2c20` with local working tree additions (`DevelopmentSessionBootstrap`, `farm-services.ts`, `useLayer10.ts`, and `P00_BASELINE_AND_INVENTORY.md`). All local changes are committed cleanly to the local tracking branch.
- **Protected Boundaries:**
  - `main` strictly locked at `6edd3721`.
  - Draft PR #28 remains unmerged and open at `7713333`.

---

## 1. Verified Scientific Invariants & Non-Negotiable Contracts

### 1.1 Canonical ASMAE 13-Dimensional Latent State Vector
The biophysical state ordering is strictly frozen in `services/agribrain/layer05_asmae/state/descriptors.py` (`STATE_ORDER` / `STATE_SCHEMA_VERSION = "asmae_state_v1_13"`). It consists of exactly 13 latent state coordinates:

| Index | Canonical Coordinate | Semantic Description | Physical Bounds | Identifiability / Authority |
| :---: | :--- | :--- | :---: | :--- |
| `0` | `vigor` | Canopy photosynthetic activity | $[0.0, 1.0]$ | Indirectly constrained; Prescription eligible |
| `1` | `lai` | Leaf Area Index | $[0.0, 8.0]\text{ m}^2/\text{m}^2$ | Partially identified; Diagnostic only |
| `2` | `chlorophyll` | Canopy chlorophyll absorption | $[0.0, 100.0]\ \mu\text{g/cm}^2$ | Observation constrained |
| `3` | `canopy_water` | Canopy water thickness | $[0.0, 5.0]\text{ mm}$ | Indirectly constrained |
| `4` | `root_zone_water` | Root zone soil water content | $[0.0, 0.6]\text{ m}^3/\text{m}^3$ | Model constrained + point sensor bounded |
| `5` | `surface_wetness_event` | Surface wetness indicator | $[0.0, 1.0]$ | Observation constrained (SAR / rain) |
| `6` | `structure` | Canopy structural density | $[0.0, 1.0]$ | Morphological diagnostic |
| `7` | `bare_soil_fraction` | Exposed unvegetated soil | $[0.0, 1.0]$ | Optical spectral unmixing |
| `8` | `salinity_stress` | Soil/root salinity impact | $[0.0, 1.0]$ | Diagnostic only |
| `9` | `thermal_stress` | Canopy thermal deviation | $[0.0, 1.0]$ | Thermal IR constrained |
| `10` | `biotic_confounder_risk` | Pathogen/pest spectral confounder | $[0.0, 1.0]$ | Diagnostic risk mask |
| `11` | `phenology_progress` | Phenological growth progress | $[0.0, 1.0]$ | Thermal-time / GDD driven |
| `12` | `stress_memory` | Accumulated lagged physiological stress | $[0.0, 1.0]$ | Integrated state history |

> [!IMPORTANT]
> **Scientific Boundaries:**
> 1. `root_zone_water` is a **single coordinate** in the 13-state vector. Multi-depth intervals ($0\text{--}10\text{ cm}$, $10\text{--}40\text{ cm}$, $40\text{--}100\text{ cm}$) belong to multi-layer hydrological boundary models and sensor telemetry arrays, not three additional ASMAE states.
> 2. Reference evapotranspiration ($ET_0$) and crop evapotranspiration ($ET_c$) are atmospheric forcing fluxes, not coordinates of the latent state vector $\mathbf{x}$.

---

### 1.2 Publication Validation Flags: Python (11) vs Frontend (9)
The dual verification pipeline operates across backend and frontend layers:

#### Backend Python Snapshot Reader (`services/agribrain/layer05_asmae/plot_snapshot_store.py`)
Computes **11 validation flags** stored in `node["validation"]`:
1. `nodeValid`: Hash of snapshot node matches canonical digest.
2. `publicationValid`: Hash of frontend publication matches declared digest.
3. `receiptValid`: Cryptographic publication receipt matches.
4. `inventoryValid`: Surface inventory dictionary digest matches.
5. `temporalBindingValid`: Observation window and evidence cutoff coherent.
6. `numericalBindingValid`: IEEE-754 bit-for-bit vector hash matches stored posterior. Evaluates to `None` when numerical record is absent; compound contract accepts `(numerical_binding_valid is not False)`.
7. `bindingValid`: Multi-entity tenant/farm/plot identity coherent, temporal binding valid, and numerical binding not false.
8. `lineageValid`: Worldline events and crop posterior lineage coherent.
9. `schemaValid`: Schema matches `SURFACES_SCHEMA_VERSION`.
10. `contractValid`: Derived publication status valid and numerical binding not false.
11. `publicationStatusValid`: Declared status matches derived status.

#### Frontend Canonical Head Validator (`src/lib/agribrain/layer10-request-state.mjs`)
Evaluates **9 aggregate flags** in `classifyCanonicalHeadValidation()`:
- **6 Integrity Flags (`CANONICAL_INTEGRITY_FLAGS`):** `nodeValid`, `publicationValid`, `receiptValid`, `inventoryValid`, `bindingValid`, `lineageValid`. (Any false $\to$ `"corrupt"`).
- **3 Contract Flags (`CANONICAL_CONTRACT_FLAGS`):** `schemaValid`, `contractValid`, `publicationStatusValid`. (Any false $\to$ `"stale"`).
- If all 9 pass $\to$ `"valid"`.

> [!NOTE]
> For ASMAE scientific rasters, `numericalBindingValid` must be strictly `True`, asserting IEEE-754 vector hash match and certifying `numerical_authority_verified = True`.

---

### 1.3 Actuator Lockout & Irrigation Deployment Configuration
- Backend `services/agribrain/app/production_delivery_runtime.py` enforces fail-closed opt-in:
  - Configuration flag: `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION`.
  - Default: `False` (when unset or empty string).
  - Validation: Only `"1"`, `"true"`, `"yes"` enable; any unrecognized value raises `Layer0AdmissionRequiredError`.
  - Deployment requirement: Every pilot service and deployment environment explicitly pins `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`.

---

## 2. Codebase Inventory & Current Architecture

### 2.1 Route Structure Under `/farm/[id]/plot/[plotId]`
1. **Root Plot Page** [`page.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/farm/[id]/plot/[plotId]/page.tsx) & [`layout.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/farm/[id]/plot/[plotId]/layout.tsx):
   - Mounts theme and client context providers.
   - Guarded by owner authorization and `DevelopmentSessionBootstrap`.
2. **Analysis Subroute** [`analysis/page.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/farm/[id]/plot/[plotId]/analysis/page.tsx):
   - Renders `AgriBrainCommandCenterClient`.
3. **Irrigation Subroute** [`irrigation/page.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/farm/[id]/plot/[plotId]/irrigation/page.tsx):
   - Renders `IrrigationDashboard` (monitoring/scheduling only; actuation locked).
4. **Raw Data Subroute** [`raw-data/page.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/farm/[id]/plot/[plotId]/raw-data/page.tsx):
   - Displays `RawSatelliteViewer`, `RawTelemetryHub`, and `PlotPageClient`.
5. **User Inputs Subroute** [`user-inputs/page.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/farm/[id]/plot/[plotId]/user-inputs/page.tsx):
   - Renders ground truth forms, soil data, and readiness score.
6. **Live Assistance Subroute** [`live-assistance/page.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/farm/[id]/plot/[plotId]/live-assistance/page.tsx):
   - Placeholder for agronomist and AI support.

---

### 2.2 Sizing Audit of `src/components/farm`
Audit reveals **122 distinct components** totaling **41,222 lines of code**:

| Subsystem Category | Count | Key Components | Aggregate Lines |
| :--- | :---: | :--- | :---: |
| **Map & Spatial Layers** | 18 | `PlotMapShell` (1,747L), `buildLayerStack` (1,452L), `SemanticSurfaceLayer` (666L), `ContourSurfaceLayer`, `UnifiedZoneLayer` | ~7,200L |
| **Intelligence Workspaces** | 36 | `SubsystemLayerDashboard` (1,480L), `MesiaMultiWaveStudio` (1,326L), `ResolutionCoverageHUD` (1,124L), `CropIdentityBanner` (954L), `TimelineStrip` (853L) | ~16,400L |
| **Drone & Aerial Workbench** | 8 | `DroneMissionDeck`, `DroneMissionPlanner`, `DroneLiveTelemetryPanel`, `GroundTruthOverlay` | ~2,800L |
| **Sensors & Field Panels** | 16 | `SensorNetworkWorkspace`, `SensorReadingComparison`, `PlotSoilPanel`, `PlotSARPanel`, `PlotWaterStressPanel` | ~4,900L |
| **Layout & Shell** | 44 | `PlotDashboard` (846L), `MapDrawer` (1,018L), `SidebarFarmerView` (997L), `SidebarExpertView` (863L), `AgriBrainChat` (867L) | ~9,900L |
| **Total** | **122** | **Entire Plot Operating Ecosystem** | **41,222L** |

---

## 3. Complete Itemized Inventory of the 94 Tool Concepts

The 94 tool concepts are grouped into 6 architectural tool families:

### Family 1: Remote Sensing & Spatial Evidence (24 Tools)
| ID | Tool Concept Name | Current Codebase Host | Target Pass | Status |
| :---: | :--- | :--- | :---: | :--- |
| `RS-01` | True Color RGB Basemap | `PlotMapShell.tsx` | P06 | Working |
| `RS-02` | False Color Infrared (CIR) | `PlotMapShell.tsx` | P06 | Working |
| `RS-03` | Sentinel-2 NDVI Surface | `SemanticSurfaceLayer.tsx` | P06 | Working |
| `RS-04` | EVI / Enhanced Vegetation | `SemanticSurfaceLayer.tsx` | P06 | Working |
| `RS-05` | NDRE Red-Edge Chlorophyll | `SemanticSurfaceLayer.tsx` | P06 | Prototype |
| `RS-06` | NDWI / NDMI Water Index | `SemanticSurfaceLayer.tsx` | P06 | Working |
| `RS-07` | SAVI Soil-Adjusted Index | `SemanticSurfaceLayer.tsx` | P06 | Prototype |
| `RS-08` | Sentinel-1 SAR Backscatter | `PlotSARPanel.tsx` | P06 | Prototype |
| `RS-09` | SAR Dual-Pol VV/VH Ratio | `PlotSARPanel.tsx` | P06 | Prototype |
| `RS-10` | Surface Roughness Estimate | `PlotSARPanel.tsx` | P06 | Prototype |
| `RS-11` | Thermal Inversion Map (TIRS) | `PlotMapShell.tsx` | P06 | Partial |
| `RS-12` | Evaporative Stress Fraction | `PlotWaterStressPanel.tsx` | P06 | Prototype |
| `RS-13` | Cloud & Shadow Mask HUD | `ResolutionCoverageHUD.tsx` | P06 | Working |
| `RS-14` | Atmospheric Penumbra Filter | `ResolutionCoverageHUD.tsx` | P06 | Working |
| `RS-15` | S2 Pixel Quality QA60/SCL | `ResolutionCoverageHUD.tsx` | P06 | Working |
| `RS-16` | Ground Sample Resolution Gauge | `ResolutionCoverageHUD.tsx` | P06 | Working |
| `RS-17` | Multi-Temporal Composite Viewer | `SubsystemLayerDashboard.tsx` | P06 | Working |
| `RS-18` | Zonal Contour Generator | `ContourSurfaceLayer.tsx` | P06 | Working |
| `RS-19` | Topographic Elevation Mesh | `PlotMapShell.tsx` | P06 | Partial |
| `RS-20` | Slope & Aspect Gradient HUD | `PlotMapShell.tsx` | P06 | Partial |
| `RS-21` | Micro-Zone Clustered Polygons | `UnifiedZoneLayer.tsx` | P06 | Working |
| `RS-22` | Zonal Variance & Outlier Map | `UnifiedZoneLayer.tsx` | P06 | Working |
| `RS-23` | Pixel Inspection Crosshair | `PlotMapShell.tsx` | P06 | Working |
| `RS-24` | Surface Attribution & License HUD | `SurfaceLegendBar.tsx` | P06 | Working |

### Family 2: In-Situ IoT & Ground Sensors (16 Tools)
| ID | Tool Concept Name | Current Codebase Host | Target Pass | Status |
| :---: | :--- | :--- | :---: | :--- |
| `IOT-01` | Soil Moisture 0-10cm Probe | `SensorNetworkWorkspace.tsx` | P08 | Partial |
| `IOT-02` | Soil Moisture 10-40cm Probe | `SensorNetworkWorkspace.tsx` | P08 | Partial |
| `IOT-03` | Soil Moisture 40-100cm Probe | `SensorNetworkWorkspace.tsx` | P08 | Partial |
| `IOT-04` | Soil Temperature Profile | `SensorNetworkWorkspace.tsx` | P08 | Partial |
| `IOT-05` | Bulk Soil EC Probe | `PlotSoilData.tsx` | P08 | Working |
| `IOT-06` | Soil pH Sensor Station | `PlotSoilData.tsx` | P08 | Working |
| `IOT-07` | Microclimate Air Temperature | `RawTelemetryHub.tsx` | P08 | Working |
| `IOT-08` | Relative Humidity Sensor | `RawTelemetryHub.tsx` | P08 | Working |
| `IOT-09` | Canopy Infrared Radiometer | `RawTelemetryHub.tsx` | P08 | Prototype |
| `IOT-10` | Rain Gauge Accu-Drop Station | `RawTelemetryHub.tsx` | P08 | Working |
| `IOT-11` | Solar Irradiance Pyranometer | `RawTelemetryHub.tsx` | P08 | Prototype |
| `IOT-12` | Anemometer Wind Vector Hub | `RawTelemetryHub.tsx` | P08 | Working |
| `IOT-13` | IP Camera Live Stream Hub | `IPCameraViewer.tsx` | P08 | Working |
| `IOT-14` | LoRaWAN RSSI & Battery HUD | `SensorNetworkWorkspace.tsx` | P08 | Working |
| `IOT-15` | Sensor Drift & Recalibration | `SensorReadingComparison.tsx`| P08 | Prototype |
| `IOT-16` | Field Sample Lab Import (NPK) | `PlotSoilData.tsx` | P08 | Working |

### Family 3: Drone & Aerial Workbench (14 Tools)
| ID | Tool Concept Name | Current Codebase Host | Target Pass | Status |
| :---: | :--- | :--- | :---: | :--- |
| `UAV-01` | Mission Flight Path Planner | `DroneMissionPlanner.tsx` | P09 | Prototype |
| `UAV-02` | Autonomous Waypoint Dispatcher | `DroneMissionPlanner.tsx` | P09 | Prototype |
| `UAV-03` | RTL & Geofence Boundary Check | `DroneMissionDeck.tsx` | P09 | Prototype |
| `UAV-04` | Live UAV Telemetry & Altitude | `DroneLiveTelemetryPanel.tsx` | P09 | Prototype |
| `UAV-05` | Sub-5cm Orthomosaic Viewer | `PlotMapShell.tsx` | P09 | Prototype |
| `UAV-06` | 3D Canopy DSM / Elevation | `PlotMapShell.tsx` | P09 | Prototype |
| `UAV-07` | Multispectral 5-Band Inspection | `GroundTruthOverlay.tsx` | P09 | Prototype |
| `UAV-08` | Individual Tree Canopy Extractor | `DroneMissionDeck.tsx` | P09 | Prototype |
| `UAV-09` | Canopy Gap & Shadow Analyzer | `DroneMissionDeck.tsx` | P09 | Prototype |
| `UAV-10` | Thermal Stress Orthomosaic | `GroundTruthOverlay.tsx` | P09 | Prototype |
| `UAV-11` | Weed Patch Density Mask | `GroundTruthOverlay.tsx` | P09 | Prototype |
| `UAV-12` | Emergence Stand Count Metric | `GroundTruthOverlay.tsx` | P09 | Prototype |
| `UAV-13` | Drone Battery & Coverage Hub | `DroneMissionDeck.tsx` | P09 | Prototype |
| `UAV-14` | Photogrammetry QA & Stitch HUD | `PhotogrammetryInspection.tsx`| P09 | Prototype |

### Family 4: MESIA Radio Science & Electromagnetic (12 Tools)
| ID | Tool Concept Name | Current Codebase Host | Target Pass | Status |
| :---: | :--- | :--- | :---: | :--- |
| `MES-01` | Soil Complex Permittivity | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-02` | L-Band Penetration Calculator | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-03` | C-Band Scattering Dispersion | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-04` | Multipath Attenuation Model | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-05` | RF Signal Quality Spectrogram | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-06` | SDR Receiver Status & Lock | `MesiaObservatoryWorkspace.tsx`| P10 | Prototype |
| `MES-07` | Antenna Azimuth / Polarization | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-08` | Phase Shift & Interferometry | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-09` | Ground Truth Permittivity Cal | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-10` | Frequency Sweep 400MHz-6GHz | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-11` | Foliage Absorption Attenuation | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |
| `MES-12` | Subsurface Layer Profile Model | `MesiaMultiWaveStudio.tsx` | P10 | Prototype |

### Family 5: Simulation & Agronomic Decisions (16 Tools)
| ID | Tool Concept Name | Current Codebase Host | Target Pass | Status |
| :---: | :--- | :--- | :---: | :--- |
| `SIM-01` | FAO-56 Single Crop Water Need | `PlotWaterStressPanel.tsx` | P12 | Working |
| `SIM-02` | Dual Crop Coefficient (Ke + Kcb) | `PlotWaterStressPanel.tsx` | P12 | Working |
| `SIM-03` | Daily Soil Water Balance Run | `PlotWaterStressPanel.tsx` | P12 | Working |
| `SIM-04` | Deficit Irrigation Window Calc | `IrrigationDashboard.tsx` | P12 | Working |
| `SIM-05` | Irrigation Event Scheduler | `IrrigationDashboard.tsx` | P12 | Working |
| `SIM-06` | What-If Rainfall Shift Sandbox | `WhatIfSandboxUI.tsx` | P11 | Working |
| `SIM-07` | What-If Heatwave Stress Sandbox | `WhatIfSandboxUI.tsx` | P11 | Working |
| `SIM-08` | Yield Potential Estimator | `CropIdentityBanner.tsx` | P12 | Working |
| `SIM-09` | Degree-Day Thermal Progress | `PlotPhenologyCard.tsx` | P12 | Working |
| `SIM-10` | Crop Growth Stage Projection | `PlotPhenologyCard.tsx` | P12 | Working |
| `SIM-11` | Salinity Leaching Requirement | `DecisionConfiguration.tsx` | P12 | Working |
| `SIM-12` | Nitrogen Uptake Curve Tracker | `PlotSoilData.tsx` | P12 | Working |
| `SIM-13` | Pest Risk Degree-Day Model | `EnginePipelinePanel.tsx` | P12 | Working |
| `SIM-14` | Disease Infection Hours HUD | `EnginePipelinePanel.tsx` | P12 | Working |
| `SIM-15` | Harvest Window Readiness Index | `CropIdentityBanner.tsx` | P12 | Working |
| `SIM-16` | Economic Margin Sensitivity | `WhatIfSandboxUI.tsx` | P11 | Working |

### Family 6: 4D Spatiotemporal Timeline (12 Tools)
| ID | Tool Concept Name | Current Codebase Host | Target Pass | Status |
| :---: | :--- | :--- | :---: | :--- |
| `4D-01` | 14-Day Acquisition Time Scrub | `TimelineStrip.tsx` | P13 | Working |
| `4D-02` | Dual-Epoch Split Compare | `TimelineStrip.tsx` | P13 | Prototype |
| `4D-03` | Temporal Delta Heatmap | `SemanticSurfaceLayer.tsx` | P13 | Working |
| `4D-04` | Ingest vs Acquisition Stamp QA | `TimelineStrip.tsx` | P13 | Working |
| `4D-05` | Multi-Year Phenology Overlay | `CropIdentityBanner.tsx` | P13 | Working |
| `4D-06` | Event Marker Annotation Tool | `TimelineStrip.tsx` | P13 | Working |
| `4D-07` | Satellite Pass Forecast Orbit | `ResolutionCoverageHUD.tsx` | P13 | Working |
| `4D-08` | Time-Series Trend Line Chart | `QuicklookStrip.tsx` | P13 | Working |
| `4D-09` | Dynamic Raster Playback Loop | `TimelineStrip.tsx` | P13 | Prototype |
| `4D-10` | Anomaly Spike Detector | `TimelineStrip.tsx` | P13 | Working |
| `4D-11` | Historical Replay Mode | `TimelineStrip.tsx` | P13 | Working |
| `4D-12` | Immutable Audit Ledger Export | `ParcelAssessmentProvider.tsx`| P13 | Working |

---

## 4. Real Browser Execution Baselines

### 4.1 Missing-Data / Unmaterialized Baseline
- **URL Tested:** `http://localhost:3000/farm/697ddd3bd4195b809226a680/plot/69fb754f2ab4b04e9f00394c`
- **Session:** Verified via `DevelopmentSessionBootstrap`.
- **Render Output:**
  - Header: `"cmara"`, `"orange · 1.3 ha"`, `"Stage unknown"`, `"23° Weather snapshot"`.
  - Navigation tabs: Overview, Raw Data, User Inputs, AgriBrain, Live Help.
  - Interactive map: Base polygon rendered with satellite underlay.
  - Fail-Closed Map Evidence HUD:
    - `01 / SCIENTIFIC SOURCE AND DATE: Not reported · Not reported`
    - `02 / UNITS AND SOURCE RESOLUTION: Not reported · Not reported`
    - `04 / INTERPRETATION STATUS: No scientific surface`
    - `Visual basemap: Not reported · Not reported. Not scientific evidence.`
  - Zero unhandled exceptions; Error Boundary (`src/app/farm/error.tsx`) is **not** triggered.

### 4.2 Valid Scientific Publication Baseline
- **URL Tested:** `http://localhost:3000/farm/69ad7b6f7e6843e8234afcf6/plot/6a09d9e91dd0c7ed6fce7d50` (Plot A / Afroun)
- **Publication Fixture:** Canonical snapshot `L10-SNAP-MITIDJA-202609081200` on disk.
- **Render Output:**
  - Header: `"afroun"`, `"حمضيات · 20.3 ha"`, `"Stage unknown"`.
  - Providers mount with valid receipt hashes: `publication_receipt_hash = "7cec1464..."`.
  - ASMAE durable worker integration latching correctly.

---

## 5. Verification Floor & Test Execution Manifest

### 5.1 Frontend Verification
- **Command:** `node --experimental-vm-modules --test (Get-ChildItem tests/frontend/*.test.mjs).FullName`
- **Result:** **111 passed / 0 failed** in 2.24s.
- **TypeScript:** `npx tsc --noEmit` $\to$ **0 errors**.

### 5.2 Python Backend Targeted Suite Manifest
- **Total Python Test Files in Repo:** 208 test files under `services/agribrain/`.
- **Targeted Scientific Fusion Suite:**
  - `services/agribrain/layer1_fusion/tests/`: 156 tests
  - `services/agribrain/tests/test_pilot_phase1_empirical_run.py`: 2 tests
  - `services/agribrain/tests/test_pilot_context_scope.py` + empirical fixtures: 13 tests
  - **Total Targeted Tests:** **171 passed / 0 failed** in 8.84s.

---

## 6. Revised Pass P01 Scope Boundary

To ensure P01 remains strictly focused and bounded without premature structural creep:

### IN SCOPE for P01: Critical Remediation
1. **Owner Authorization Uniformity:**
   - Enforce server-side owner verification across root page and all 5 subroutes (`/analysis`, `/raw-data`, `/user-inputs`, `/irrigation`, `/live-assistance`).
   - Eliminate race conditions in `DevelopmentSessionBootstrap`.
2. **Geospatial Geometry Canonicalization:**
   - Standardize GeoJSON normalization, winding order, and WGS84 validation.
   - **Constraint:** Must preserve MultiPolygon geometries with holes.
   - **Constraint:** Must NOT mutate existing publication geometry hashes; versioned migration required if identity changes.
3. **Scientific Publication Status:**
   - Enforce fail-closed diagnostics when evidence is unavailable.
   - Guard against `telemetry_scope_incomplete` crashes.
4. **Eliminate Misleading Simulation/Prescription Fallbacks:**
   - Deprecate silent fallback tile calls in `PlotDashboard.tsx`.
   - Strictly separate observed sensor ground truth from model prior estimates.

### DEFERRED to P03–P04:
- Decoupling modal boolean flags (`showDronePanel`, `showSensorsPanel`, `showMesiaPanel`, `showIrrigationPanel`) into the Tool Registry is **deferred to P03–P04**, after the shared workspace state contract is established.
