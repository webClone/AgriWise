# AgriBrain: Master System Architecture & Geostatistical Specification
## Version 10.4.0 — Unified Biophysical, Geostatistical, & GenAI Orchestration

---

## 1. Executive Summary & Architectural Philosophy

**AgriBrain** is the core biophysical simulation, geostatistical modeling, and GenAI-orchestrated decision platform of the AgriWise precision farming workspace. Designed to address the gap between raw environmental sensors and practical, on-farm action, AgriBrain compiles multi-spectral satellite imagery, weather reanalysis, in-situ soil probes, digital elevation models, and genomic profiles into a unified decision engine.

The platform is structured as an **11-layer computational stack (Layer 0 through Layer 10)**. Inside this stack, exactly **148 specialized core engines** process data to evaluate soil health, diagnose crop stress, optimize split-applications, schedule weather-compliant field operations, manage cognitive fatigue, and evaluate spatial within-field management zones.

```
                  ┌─────────────────────────────────────────────────────────┐
  Interaction     │      Layer 9: GenAI Interface & Conversational Advisor  │
                  └────────────────────────────┬────────────────────────────┘
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
  Optimization    │      Layer 8: Prescriptive Action Ranker & Safety Gates │
                  └────────────────────────────┬────────────────────────────┘
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
  Planning        │      Layer 7: Agro-Climatic Planning & Risk Composite   │
                  └────────────────────────────┬────────────────────────────┘
                                               ▼
                  ┌────────────────────────────┴────────────────────────────┐
  Economics       │      Layer 6: Yield Forecasting & Strategic Economics   │
                  └────────────────────────────┬────────────────────────────┘
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
  Biophysical     │      Layer 5: Biological Stress & Pathogen Risk Planner │
  Simulation      ├─────────────────────────────────────────────────────────┤
                  │      Layer 4: Nutrient Dynamics & VRA Optimization      ├───────┐
                  ├─────────────────────────────────────────────────────────┤       │
                  │      Layer 3: Decision & Water (Dual-Kc crop ET balance)│       │
                  └────────────────────────────┬────────────────────────────┘       │
                                               ▼                                    ▼
                  ┌─────────────────────────────────────────────────────────┐ ┌───────────┐
  State Estimation│      Layer 2: Vegetation Index Smoother & Growth Tracker│ │  Layer 10 │
                  └────────────────────────────┬────────────────────────────┘ │    │  SIRE   │
                                               ▼                              │  Spatial  │
                  ┌─────────────────────────────────────────────────────────┐ │ Geostats  │
  Sensor Fusion   │      Layer 1: Environmental Sensor Fusion & DEM Terrain │ │  & Kriging│
                  └────────────────────────────┬────────────────────────────┘ └─────┬─────┘
                                               ▼                                    │
                  ┌─────────────────────────────────────────────────────────┐       │
  Assimilation    │      Layer 0: In-Situ & Satellite Data Assimilation     │◄──────┘
                  └─────────────────────────────────────────────────────────┘
```

---

## 2. Comprehensive Layer-by-Layer Architectural In-Depth Specification

---

### Layer 0: Data Ingestion & Calibration (Data Assimilation)

#### Operational Role & Computational Philosophy
Layer 0 acts as the ingestion, QA/QC, and temporal calibration layer for all incoming raw telemetry streams, including in-situ FDR soil moisture probes, regional weather grids, dual-polarization Sentinel-1 SAR radar, and Sentinel-2 multi-spectral bands. It performs anomaly detection, sensor consensus modeling, and temporal normalization to correct for sensor drift.

#### Core Engines (Exact Count: 7)
1. **IngestionEngine** (`layer0/ingestion.py`): Ingests heterogeneous data streams from hardware portals, parsing formats into standard payloads.
2. **QualityControlEngine** (`layer0/qc.py`): Detects sensor dropouts, out-of-bounds readings, and spikes using rolling-window z-score filters.
3. **CalibrationEngine** (`layer0/calibration.py`): Corrects sensor drift using temporal calibration curves.
4. **SentinelCoreEngine** (`layer0/sentinel.py`): Manages direct APIs to ESA Copernicus Hub, retrieving Sentinel-1 and Sentinel-2 imagery.
5. **ProbeIntegrationEngine** (`layer0/probe.py`): Manages raw frequency domain reflectometry (FDR) in-situ soil probe integrations.
6. **WeatherConsensusEngine** (`layer0/consensus.py`): Resolves conflicts between in-situ weather sensors and regional weather grids using weighted consensus models.
7. **TemporalNormalizationEngine** (`layer0/temporal.py`): Normalizes raw satellite band observations to correct for atmospheric distortion and illumination angles.

#### Input & Output Interfaces
* **Upstream Inputs**: Raw physical streams, satellite imagery bands (Sentinel-2 L2A, Sentinel-1 GRD), in-situ soil FDR frequencies, and localized weather station telemetry.
* **Downstream Outputs**: Programmatic `Layer0Payload` containing verified, consensus-calibrated weather, soil, and satellite observations.

#### Biophysical Mathematical Formulations
* **QA/QC Sensor Consensus Solver**:
  $$x_{\text{consensus}} = \frac{\sum_{s=1}^S w_s \cdot x_s}{\sum_{s=1}^S w_s}$$
  Where $w_s$ is the dynamic trust weight of sensor $s$, which decays based on sensor age and observed telemetry gaps:
  $$w_s = \text{Trust}_0 \cdot \exp\left( - \lambda_{drift} \cdot t_{age} \right)$$
* **Temporal Invariant Calibration**:
  $$I_{\text{calibrated}} = \alpha_{\text{cal}} \cdot I_{\text{raw}} + \beta_{\text{cal}}$$

---

### Layer 1: Environmental Sensor Fusion (Sensor Fusion)

#### Operational Role & Computational Philosophy
Layer 1 fuses calibrated environmental, topographic, and satellite datasets into a continuous physical grid. It processes Digital Elevation Models (DEM) to calculate terrain slope and aspect, estimates soil physical limits using clay and organic matter pedotransfers, and identifies mechanical tillage events from Sentinel-1 radar backscatter spikes.

#### Core Engines (Exact Count: 7)
1. **TopographicTerrainEngine** (`layer1_fusion/engines/terrain.py`): Calculates slope, aspect, and wetness indices from DEM layers.
2. **PedotransfersEngine** (`layer1_fusion/engines/pedotransfer.py`): Calculates soil bulk density, field capacity, and wilting point from clay and organic matter fractions.
3. **S1TillageEngine** (`layer1_fusion/engines/tillage.py`): Monitors Sentinel-1 dual-polarization ($\text{VV}$ and $\text{VH}$) backscatter time-series, identifying tillage events by tracking backscatter spikes.
4. **S2OpticalNDVIEngine** (`layer1_fusion/engines/ndvi.py`): Computes raw NDVI indices from Sentinel-2 red and near-infrared bands.
5. **SpatialInterpolatorEngine** (`layer1_fusion/engines/interpolate.py`): Interpolates sparse weather and soil data across within-field management zones.
6. **InvariantVerificationEngine** (`layer1_fusion/engines/invariants.py`): Programmatically enforces physical law boundary limits (e.g., soil moisture cannot exceed porosity).
7. **CalibrationBridge** (`layer1_fusion/engines/bridge.py`): Calibrates Sentinel-2 NDVI time-series using in-situ probe readings.

#### Input & Output Interfaces
* **Upstream Inputs**: Calibrated `Layer0Payload` data streams, including DEM rasters, clay/organic matter percentages, and Sentinel-1/2 rasters.
* **Downstream Outputs**: Strongly-typed `FusedLandscapeState` detailing soil limits, slope/aspect corrections, and tillage timelines.

#### Biophysical Mathematical Formulations
* **Soil Physics Pedotransfer van Genuchten curves**:
  $$\theta(h) = \theta_r + \frac{\theta_s - \theta_r}{\left[ 1 + (\alpha |h|)^n \right]^{1 - 1/n}}$$
  Where $\theta(h)$ is the volumetric water content at suction head $h$, $\theta_s, \theta_r$ are the saturated and residual soil moisture capacities, and $\alpha, n$ are shape parameters calculated from clay and organic matter fractions.
* **SAR Tillage Detection Backscatter Ratio**:
  $$\Delta \sigma^0_{\text{VV/VH}} = \sigma^0_{\text{VV}} - \sigma^0_{\text{VH}}$$

---

### Layer 2: Vegetation & Crop Science (State Estimation)

#### Operational Role & Computational Philosophy
Layer 2 tracks crop canopy development. It applies Whittaker-Henderson smoothers and Savitzky-Golay filters to optical NDVI time-series, calculates canopy temperature energy balances, translates vegetative indexes into Leaf Area Index (LAI) values, and identifies crop growth stages.

#### Core Engines (Exact Count: 7)
1. **PhenologyTrackerEngine** (`layer2_veg_int/engines/phenology.py`): Resolves crop phenological growth stages on the BBCH scale based on GDD thresholds.
2. **GDDCalculatorEngine** (`layer2_veg_int/engines/gdd.py`): Calculates Growing Degree Days (GDD) using daily temperature bounds.
3. **WhittakerHendersonEngine** (`layer2_veg_int/engines/whittaker.py`): Applies Whittaker-Henderson smoothers and Savitzky-Golay filters to NDVI time-series to remove cloud noise.
4. **BeerLambertLAIEngine** (`layer2_veg_int/engines/lai.py`): Translates smoothed NDVI into Leaf Area Index (LAI) values using the Beer-Lambert law.
5. **StressYieldScaler** (`layer2_veg_int/engines/stress.py`): Models the impact of vegetative water and temperature stress on potential crop yield.
6. **CropIdentificationEngine** (`layer2_veg_int/crop_identification.py`): Classifies crop species by matching NDVI time-series profiles against a reference library.
7. **CropScienceDatabase** (`layer2_veg_int/crop_science_data.py`): Stores crop-specific parameters (e.g., base temperatures, crop coefficients).

#### Input & Output Interfaces
* **Upstream Inputs**: Strongly-typed `FusedLandscapeState` detailing NDVI time-series and air temperatures.
* **Downstream Outputs**: `VegetationState` containing smoothed NDVI, current BBCH stage, GDD values, and Leaf Area Index (LAI) parameters.

#### Biophysical Mathematical Formulations
* **Whittaker-Henderson Vegetation Filter**:
  $$\min_{\mathbf{y}} \left[ \sum_{t=1}^T (y_t - x_t)^2 + \lambda \sum_{t=3}^T (\Delta^2 y_t)^2 \right]$$
  Where $x_t$ is the raw NDVI observation at day $t$, $y_t$ is the smoothed target NDVI, $\lambda$ is the smoothing penalty, and $\Delta^2 y_t$ represents the second-order difference ($y_t - 2y_{t-1} + y_{t-2}$).
* **GGD Accumulation**:
  $$\text{GDD} = \max\left( 0, \frac{T_{\text{max}} + T_{\text{min}}}{2} - T_{\text{base}} \right)$$

---

### Layer 3: Decision & Water (Biophysical Simulation)

#### Operational Role & Computational Philosophy
Layer 3 models crop water consumption and soil moisture dynamics. It calculates the FAO-56 dual crop coefficient Penman-Monteith Evapotranspiration ($ET_c$), estimates water depletion rates across root zones, and outputs dynamic irrigation prescriptions.

#### Core Engines (Exact Count: 22)
1. **FAO56EvapotranspirationEngine** (`layer3_decision/evapotranspiration.py`): Solves the Penman-Monteith equation to estimate reference crop evapotranspiration ($ET_0$).
2. **CropCoefficientScheduler** (`layer3_decision/crop_coefficient.py`): Dynamically schedules basal crop coefficients ($K_{cb}$) based on crop growth stages.
3. **SoilEvaporationEngine** (`layer3_decision/soil_evaporation.py`): Calculates soil evaporation ($K_e$) based on surface wetness and canopy cover.
4. **WaterStressScaler** (`layer3_decision/stress_scaler.py`): Scales transpiration rates based on root zone soil moisture depletion.
5. **RootZoneExpansionEngine** (`layer3_decision/root_growth.py`): Models root depth expansion based on GDD accumulation.
6. **PrecipitationEfficiencyEngine** (`layer3_decision/precipitation.py`): Calculates effective rainfall infiltration based on soil type and slope.
7. **DeepPercolationEngine** (`layer3_decision/percolation.py`): Models drainage losses below the active root zone.
8. **CapillaryRiseEngine** (`layer3_decision/capillary.py`): Simulates upward water movement from shallow water tables.
9. **WaterBalanceIntegrator** (`layer3_decision/water_balance.py`): Integrates daily water inputs and outputs to calculate soil moisture deficits.
10. **IrrigationPrescriber** (`layer3_decision/irrigation_prescriber.py`): Generates irrigation prescriptions based on root zone soil moisture deficits.
11. **SoilMoistureTrajectoryEngine** (`layer3_water/trajectory.py`): Forecasts soil moisture trends across a 7-day planning horizon.
12. **WeatherAdaptiveScheduler** (`layer3_water/scheduler.py`): Schedules irrigation events in weather-compliant calendar slots.
13. **VADIrrigationEngine** (`layer3_water/vad.py`): Optimizes irrigation scheduling based on Vapor Pressure Deficit (VPD).
14. **IrrigationFeasibilityEngine** (`layer3_water/feasibility.py`): Gates irrigation prescriptions based on operational water availability constraints.
15. **IrrigationComplianceEngine** (`layer3_water/compliance.py`): Ensures irrigation prescriptions comply with local water allocation rules.
16. **WaterQualityEngine** (`layer3_water/water_quality.py`): Models irrigation water quality impacts (e.g., salinity) on crop stress.
17. **IrrigationBridge** (`layer3_water/bridge.py`): Connects irrigation schedules with smart valves and pumping controllers.
18. **DepletionScoutingEngine** (`layer3_water/scout.py`): Calibrates soil moisture models using in-situ probe scouting readings.
19. **RunoffRiskEngine** (`layer3_water/runoff.py`): Models runoff risks based on soil type, slope, and rainfall intensity.
20. **CanopyInterceptionEngine** (`layer3_water/canopy_interception.py`): Calculates rainfall interception losses by the crop canopy.
21. **LateralWaterFlowEngine** (`layer3_water/lateral_flow.py`): Simulates lateral water movement across undulating terrain.
22. **WaterLossAuditEngine** (`layer3_water/audit.py`): Audits the daily water balance to ensure compliance with biophysical constraints.

#### Input & Output Interfaces
* **Upstream Inputs**: `VegetationState` parameters, soil pedotransfer limits, and weather forecasts.
* **Downstream Outputs**: `WaterIntelligenceOutput` detailing crop water consumption ($ET_c$), root zone depletion, and irrigation schedules.

#### Biophysical Mathematical Formulations
* **FAO-56 Dual-Kc Crop Evapotranspiration**:
  $$ET_c = \left( K_{cb} \cdot K_s + K_e \right) \cdot ET_0$$
  Where $ET_0$ is the reference grass evapotranspiration ($\text{mm/day}$), $K_{cb}$ is the basal crop transpiration coefficient, $K_s$ is the soil water stress reduction factor, and $K_e$ is the soil evaporation coefficient.
* **FAO-56 Daily Root Zone Water Balance**:
  $$D_r = D_{r,\text{prev}} - I - P - CR + ET_c + DP$$

---

### Layer 4: Nutrient Dynamics & VRA Optimization (Biophysical Simulation)

#### Operational Role & Computational Philosophy
Layer 4 tracks soil chemical dynamics, coordinating nitrogen, phosphorus, and potassium pools. It models crop nutrient uptake using Mitscherlich-Baule curves, simulates phosphorus buffering with Langmuir sorption isotherms, estimates cation exchange capacity, and calculates liming requirements.

#### Core Engines (Exact Count: 22)
1. **SoilWaterBalanceEngine** (`layer4_nutrients/engines/swb.py`): Models soil water balance.
2. **TillageDetectionEngine** (`layer4_nutrients/engines/tillage.py`): Identifies tillage events from radar backscatter data.
3. **SOCDynamicsEngine** (`layer4_nutrients/engines/soc.py`): Simulates soil organic carbon transformations and decomposition.
4. **CropDemandUptakeEngine** (`layer4_nutrients/engines/cdu.py`): Models crop nutrient demand and uptake across growth stages.
5. **NutrientObservationProxy** (`layer4_nutrients/engines/nop.py`): Translates satellite imagery into spatial nutrient proxy layers.
6. **InferenceEngine** (`layer4_nutrients/engines/inference.py`): Infers soil nutrient levels by fusing soil tests and proxy layers.
7. **OptimizationEngine** (`layer4_nutrients/engines/optimization.py`): Optimizes fertilizer split-application rates to maximize yield.
8. **PlannerEngine** (`layer4_nutrients/engines/planner.py`): Generates variable rate fertilizer plans.
9. **NutrientInteractionEngine** (`layer4_nutrients/engines/liebig.py`): Audits fertilizer plans using Liebig's Law of the Minimum.
10. **CECSolverEngine** (`layer4_nutrients/engines/cec.py`): Calculates soil Cation Exchange Capacity (CEC) and base cation exchange saturation vectors.
11. **LimingEngine** (`layer4_nutrients/engines/liming.py`): Calculates agricultural lime requirements using SMP buffer equations.
12. **VRAZoneInterpolator** (`layer4_nutrients/engines/vra_zones.py`): Interpolates fertilizer rates across spatial management zones.
13. **ResidualLegumeCredits** (`layer4_nutrients/engines/legumes.py`): Calculates residual nitrogen credits from preceding legume crops.
14. **NUETrackingEngine** (`layer4_nutrients/engines/nue.py`): Tracks Nitrogen Use Efficiency (NUE) across growth stages.
15. **TissueAnalysisEngine** (`layer4_nutrients/engines/dris.py`): Audits plant tissue nutrient levels using DRIS indices.
16. **PhosphorusSorptionEngine** (`layer4_nutrients/engines/p_sorption.py`): Models phosphorus adsorption and desorption using Langmuir isotherms.
17. **SalinityEngine** (`layer4_nutrients/engines/salinity.py`): Models soil salinity effects on crop nutrient uptake.
18. **BNFEngine** (`layer4_nutrients/engines/bnf.py`): Models biological nitrogen fixation (BNF) in legume crops.
19. **SoilRespirationEngine** (`layer4_nutrients/engines/respiration.py`): Simulates daily microbial soil respiration and carbon mineralization.
20. **PhotosynthesisNUEEngine** (`layer4_nutrients/engines/photo_nue.py`): Simulates canopy photosynthesis and Nitrogen Use Efficiency.
21. **EnvironmentalLossEngine** (`layer4_nutrients/engines/env_loss.py`): Models nitrogen losses through denitrification, leaching, volatilization, and immobilization.
22. **LimitingNutrientEnforcer** (`layer4_nutrients/engines/limiting.py`): Programmatically enforces Liebig's Law of the Minimum across N/P/K fertilizer prescriptions.

#### Input & Output Interfaces
* **Upstream Inputs**: Strongly-typed `VegetationState` parameters, soil pedotransfer limits, and weather forecasts.
* **Downstream Outputs**: `NutrientIntelligenceOutput` detailing soil N/P/K levels, cation exchange capacity, liming requirements, and VRA fertilizer prescriptions.

#### Biophysical Mathematical Formulations
* **Mitscherlich-Baule Crop Yield Response Curve**:
  $$Y = Y_{\text{max}} \cdot \left( 1 - \exp\left( -\beta_N \cdot (N + x_N) \right) \right) \cdot \left( 1 - \exp\left( -\beta_P \cdot (P + x_P) \right) \right) \cdot \left( 1 - \exp\left( -\beta_K \cdot (K + x_K) \right) \right)$$
  Where $Y_{\text{max}}$ is the theoretical maximum potential yield ($\text{t/ha}$), $N, P, K$ are the applied fertilizer nutrient rates ($\text{kg/ha}$), $x_N, x_P, x_K$ are the baseline soil nutrient pools, and $\beta_N, \beta_P, \beta_K$ are the nutrient response coefficients.
* **Langmuir Phosphorus Sorption Isotherm**:
  $$S = \frac{S_{\text{max}} \cdot K_L \cdot C_p}{1.0 + K_L \cdot C_p}$$

---

### Layer 5: Biological Stress & Pathogen Risk (Biophysical Simulation)

#### Operational Role & Computational Philosophy
Layer 5 evaluates disease and pest pressures. It models fungal spore release wind detachers, leaf wetness duration, Cauchy spatial downwind dispersal kernels, NBS-LRR gene-for-gene cultivar immunities, pesticide chemical weathering, and Bayesian diagnostic updates.

#### Core Engines (Exact Count: 11)
1. **VerticalSporeEngine** (`layer5_bio/engines/vertical_spore.py`): Models vertical spore release and canopy escape fractions.
2. **WindShearSporeEngine** (`layer5_bio/engines/wind_spore.py`): Models wind-driven spore detachment from crop residues, accounting for leaf wetness and fluttering.
3. **CauchyDispersalEngine** (`layer5_bio/engines/cauchy.py`): Models spatial downwind spore deposition using a Cauchy dispersal kernel.
4. **EnergyBalanceEngine** (`layer5_bio/engines/energy.py`): Calculates canopy energy balances and transpiration rates.
5. **CultivarETIEngine** (`layer5_bio/engines/eti.py`): Models gene-for-gene NBS-LRR cultivar resistance and immune activation.
6. **HIGSRNAiEngine** (`layer5_bio/engines/rnai.py`): Simulates RNAi target gene silencing efficiency for biological crop protection.
7. **GeneticsClassifier** (`layer5_bio/engines/genetics_classifier.py`): Classifies crop genetic susceptibility using cross-attention mechanisms.
8. **ChemicalWeatheringEngine** (`layer5_bio/engines/weathering.py`): Models pesticide degradation from solar UV photolysis and rain wash-off.
9. **SprayDriftEngine** (`layer5_bio/engines/spray_drift.py`): Projects pesticide spray drift using Random Forest regressors.
10. **VisualSymptomEngine** (`layer5_bio/engines/visual_symptoms.py`): Detects crop disease symptoms from photographs using convolutional neural networks.
11. **BioThreatInference** (`layer5_bio/engines/biothreat_inference.py`): Computes posterior disease probabilities using Bayesian diagnostic updates.

#### Input & Output Interfaces
* **Upstream Inputs**: Strongly-typed `VegetationState` parameters, soil pedotransfer limits, and weather forecasts.
* **Downstream Outputs**: `BioThreatIntelligenceOutput` detailing pathogen risk, disease symptoms, and chemical weathering rates.

#### Biophysical Mathematical Formulations
* **Aerodynamic Spore Detachment & Wind Shear**:
  $$\text{Logit}(P_{release}) = 2.0 \cdot \left[ F_{drag} + F_{inertial} - F_{adhesion} \right]$$
  $$a_{flutter} = \left( 2\pi \cdot f \right)^2 \cdot \left[ \frac{\beta_{flutter} \cdot u^{1.5}}{\sqrt{\text{LAI}}} \right]$$
* **Spatial Spore Dispersal Cauchy Kernel**:
  $$I(d) = \frac{I_0}{\pi \cdot L \cdot \left[ 1 + \left( \frac{d}{L} \right)^2 \right]}$$

---

### Layer 6: Yield Forecasting & Strategic Economics (Economics)

#### Operational Role & Computational Philosophy
Layer 6 evaluates long-term environmental and financial outcomes. It models daily soil organic carbon dynamics using the RothC model, simulates solute nitrate leaching, projects yield distributions using Monte Carlo simulations, calculates harvest windows, and runs causal Difference-in-Differences evaluators to isolate intervention returns.

#### Core Engines (Exact Count: 12)
1. **InterventionSynthesisEngine** (`layer6_exec/engines/interventions.py`): Synthesizes tactical recommendations from Layer 3, 4, and 5 into a unified execution plan.
2. **ResourceFeasibilityEngine** (`layer6_exec/engines/feasibility.py`): Gates recommendations through multi-dimensional capacity constraints (e.g., labor and equipment availability).
3. **VPDSprayWindowEngine** (`layer6_exec/engines/vpd_spray.py`): Calculates optimal pesticide spray windows based on wind speed and VPD constraints.
4. **RothCSOCEngine** (`layer6_exec/engines/rothc.py`): Models daily organic carbon transformations across DPM, RPM, BIO, and HUM soil carbon pools.
5. **SoluteLeachingEngine** (`layer6_exec/engines/leaching.py`): Models vertical solute nitrate leaching through soil horizons.
6. **CausalOutcomeEvaluator** (`layer6_exec/engines/causal.py`): Isolates real treatment effects against synthetic spatial control baselines using Difference-in-Differences.
7. **DAGTaskRunner** (`layer6_exec/engines/dag_runner.py`): Executes dependency-aware prescriptive action DAGs.
8. **FeedbackCalibrationEngine** (`layer6_exec/engines/calibration.py`): Calibrates soil carbon models using ground-truth soil test feedback.
9. **IrrigationBridgeEngine** (`layer6_exec/engines/irrigation_bridge.py`): Links irrigation schedules with physical pumping station runtime targets.
10. **YieldMonteCarloEngine** (`layer6_yield/engines/yield_forecast.py`): Projects yield distributions ($P_{10}$, $P_{50}$, $P_{90}$) by running Monte Carlo simulations.
11. **HarvestOptimizerEngine** (`layer6_yield/engines/harvest_optimizer.py`): Calculates the optimal harvest window by balancing crop maturity, moisture dry-down, and weather risks.
12. **ProfitabilityCalculator** (`layer6_yield/engines/profitability.py`): Calculates net profit margins and Return on Investment (ROI) for alternative intervention paths.

#### Input & Output Interfaces
* **Upstream Inputs**: Strongly-typed `VegetationState` parameters, soil pedotransfer limits, and weather forecasts.
* **Downstream Outputs**: `StrategicEconomicsOutput` detailing projected yields, net profits, carbon sequestration rates, and resource feasibility constraints.

#### Biophysical Mathematical Formulations
* **RothC Carbon Sequestration dynamics**:
  $$\frac{dC_i}{dt} = \text{Input}_i - k_i \cdot C_i \cdot f(T_s) \cdot f(\theta) \cdot (1.0 - \Omega_{\text{tillage}})$$
* **Optimal Harvest Day Objective Function**:
  $$t^* = \arg\max_{t} \left[ \text{Yield}(t) \cdot \text{Price}(t) - \text{DryingCost}(t) - \text{QualityLoss}(t) \right]$$

---

### Layer 7: Agro-Climatic Planning & Risk Composite (Planning)

#### Operational Role & Computational Philosophy
Layer 7 manages seasonal planning and environmental risks. It models sigmoidal planting windows, calculates the Drought Recovery Index (DRI) from vegetative indexes, aggregates multi-attribute risks using stage-adaptive weights, and monitors telemetry trust using latency decay curves.

#### Core Engines (Exact Count: 17)
1. **ZoneSuitabilityEngine** (`layer7_planning/engines/zone_suitability.py`): Calculates long-term agro-climatic suitability grades for candidate crops across management zones.
2. **AspectMicroclimateEngine** (`layer7_planning/engines/aspect_solar.py`): Corrects incoming solar radiation budgets based on topographic terrain slope and aspect.
3. **BioticPathogenRisk** (`layer7_planning/engines/biotic_pathogens.py`): Models residue-borne pathogen carryover risk based on preceding crop rotations.
4. **CultivarLibraryEngine** (`layer7_planning/engines/cultivar_library.py`): Resolves crop-specific parameters (e.g., GDD thresholds, cold tolerances) from a cultivar database.
5. **ClimateResilienceEngine** (`layer7_planning/engines/resilience.py`): Calculates post-stress crop recovery rates using historical NDVI datasets.
6. **CropRotationPlanner** (`layer7_planning/engines/rotation_planner.py`): Optimizes multi-year crop rotations to improve soil health and break pest cycles.
7. **PlanningEconomicsEngine** (`layer7_planning/engines/economics.py`): Projects seasonal input costs and gross revenue margins for alternative planting plans.
8. **PedSeedbedEngine** (`layer7_planning/engines/seedbed_prep.py`): Evaluates soil physical limits to determine seedbed preparation requirements.
9. **PlantingWindowEngine** (`layer7_planning/engines/planting_window.py`): Evaluates rolling mean soil temperatures and soil moisture levels to identify optimal planting windows.
10. **SoilWorkabilityEngine** (`layer7_planning/engines/soil_workability.py`): Evaluates soil trafficability plastic limits based on clay and organic matter content.
11. **WaterFeasibilityEngine** (`layer7_planning/engines/water_feasibility.py`): Models seasonal irrigation water balances against storage capacities.
12. **YieldMonteCarloPlanner** (`layer7_planning/engines/yield_dist.py`): Projects long-term crop yield probability distributions using historical weather reanalysis.
13. **S1SoilHealthTrajectory** (`layer7_planning/engines/soil_health.py`): Monitors multi-year soil carbon and tillage intensity trends using Sentinel-1 SAR backscatter data.
14. **ClimateShockInsurance** (`layer7_risk/engines/insurance_triggers.py`): Triggers index-based crop insurance payouts when weather metrics exceed shock thresholds.
15. **RiskCompositeEngine** (`layer7_risk/engines/risk_composite.py`): Aggregates water, nutrient, biological, and microclimatic risk indices into a single value.
16. **ScenarioSimulator** (`layer7_risk/engines/scenario_sim.py`): Stress-tests agricultural strategies by simulating climate shock events.
17. **TrustMonitorEngine** (`layer7_risk/engines/trust_monitor.py`): Calculates real-time trust metrics for environmental sensors, applying penalties for missing or out-of-date telemetry.

#### Input & Output Interfaces
* **Upstream Inputs**: Strongly-typed `VegetationState` parameters, soil pedotransfer limits, and weather forecasts.
* **Downstream Outputs**: `AgroClimaticPlanningOutput` detailing crop suitability grades, optimal planting windows, composite risk levels, and sensor trust metrics.

#### Biophysical Mathematical Formulations
* **Sigmoidal Planting Window Readiness Probability**:
  $$S_{planting} = \frac{1}{1 + \exp\left( -\kappa_{temp} \cdot (T_{soil} - T_{base}) \right)} \cdot g(\theta)$$
* **Drought Recovery Index (DRI)**:
  $$\text{DRI} = \frac{\sum_{t=t_{\text{rec\_start}}}^{t_{\text{rec\_end}}} \left( VI(t) - VI_{stress}(t_{\text{stress\_peak}}) \right)}{(t_{rec\_end} - t_{rec\_start}) \cdot \sigma_{VI\_historical}}$$

---

### Layer 8: Prescriptive Action Ranker & Safety Gates (Optimization)

#### Operational Role & Computational Philosophy
Layer 8 compiles prescriptive action schedules. It ranks intervention candidates using multi-objective optimization, scales rates by phenology, and enforces exactly 7 safety gates (salinity leaching requirements, canopy cooling micro-irrigation, EPA spray drift buffer zones, subsoil compaction tillage, lodging PGR regulators, ammonia volatilization urease inhibitors, and frost sprinklers).

#### Core Engines (Exact Count: 16)
1. **ActionRankingEngine** (`layer8_prescriptive/action_ranker.py`): Ranks intervention candidates using multi-objective optimization, calculating priority scores based on expected crop impact, emergency urgency, risk reduction value, inverse cost penalty, and trust-grade confidence.
2. **ZonePrioritizer** (`layer8_prescriptive/zone_prioritizer.py`): Allocates resources across within-field management zones, adjusting priorities based on spatial telemetry trust.
3. **AdoptionModelTAM** (`layer8_prescriptive/engines/adoption_model.py`): Scores farmer adoption probability using a 2-layer Feedforward Neural Network (TAM MLP). It maps farmer ease, usefulness, cost, and trust into adoption scores.
4. **CognitiveLoad** (`layer8_prescriptive/engines/cognitive_load.py`): Prunes redundant or excessive recommendations to prevent decision fatigue using Sweller's cognitive complexity limits.
5. **EnvironmentalRisk** (`layer8_prescriptive/engines/environmental_risk.py`): Evaluates chemical runoff risks based on soil textures, slopes, and precipitation forecasts.
6. **Framing** (`layer8_prescriptive/engines/framing_engine.py`): Generates message framing anchored in economic outcomes, using prospect-theory gain/loss principles.
7. **IPMCascade** (`layer8_prescriptive/engines/ipm_cascade.py`): Enforces Integrated Pest Management (IPM) targeted cascades. It gates chemical actions, escalating from monitoring and biological controls to chemical targeted inputs only when threat pressures exceed Economic Injury Levels (EIL) and Pre-Harvest Interval (PHI) limits.
8. **SalinityLeaching** (`layer8_prescriptive/engines/salinity_leaching.py`): Evaluates soil salinity stress. It calculates the FAO-29 Leaching Requirement (LR) based on crop-specific electrical conductivity thresholds ($EC_e$), scaling irrigation volumes to flush soluble salts below the root zone.
9. **CropCooling** (`layer8_prescriptive/engines/crop_cooling.py`): Prescribes crop canopy micro-irrigation cooling on days when maximum temperatures exceed reproductive heat thresholds, mitigating flower sterility and heat shocks.
10. **SprayDriftGate** (`layer8_prescriptive/engines/spray_drift_gate.py`): Enforces US EPA pesticide spray drift safety limits. It calculates physical off-target buffer zones based on droplet size, boom height, and travel speed, blocking spray actions when wind speed exceeds $25 \text{ km/h}$.
11. **TillageCompaction** (`layer8_prescriptive/engines/tillage_compaction.py`): Gates mechanical tillage operations. It evaluates bulk density compaction risk against USDA soil texture thresholds, prescribing deep subsoil tillage depths.
12. **LodgingPGR** (`layer8_prescriptive/engines/lodging_pgr.py`): Evaluates plant lodging risks. It models plant height, growth speed, nitrogen surplus, and wind gust mechanics, prescribing Plant Growth Regulators (PGRs) to restrict stem elongation.
13. **VolatilizationInhibitor** (`layer8_prescriptive/engines/volatilization_inhibitor.py`): Models fertilizer ammonia volatilization risks on dry, alkaline soils, prescribing NBPT urease inhibitor coatings to slow urea hydrolysis.
14. **FrostSprinkling** (`layer8_prescriptive/engines/frost_sprinkling.py`): Models overhead frost protection sprinkling, calculating rates to release latent heat of fusion during freezing events.
15. **ConstraintScheduler** (`layer8_prescriptive/scheduler.py`): Schedules actions into weather-compliant calendar slots within the planning horizon, accounting for rain, temperature, and wind.
16. **VolatilizationSafetyEngine** (`layer8_prescriptive/engines/volatilization_safety.py`): Verifies NBPT coating rates to ensure fertilizer applications remain within environmental safety limits.

#### Input & Output Interfaces
* **Upstream Inputs**: Fused landscape states, crop growth parameters, water deficits, pathogen risk indices, and resource constraints.
* **Downstream Outputs**: Strongly-typed `Layer8Output` containing prescriptive action plans, weather-compliant schedules, and zone prioritisations.

#### Biophysical Mathematical Formulations
* **FAO-29 Salinity Leaching Requirement Gating**:
  $$LF = \frac{EC_w}{5 \cdot EC_e - EC_w}$$
  $$LR = \frac{LF}{1.0 - LF}$$
  $$\text{Rate}_{adjusted} = \text{Rate}_{raw} \cdot \left( 1.0 + LR \right)$$
* **TAM Neural Network Forward Pass**:
  $$\mathbf{a}_1 = \max\left( 0, \mathbf{x} \cdot \mathbf{W}_1 + \mathbf{b}_1 \right)$$
  $$a_2 = \sigma\left( \mathbf{a}_1 \cdot \mathbf{W}_2 + b_2 \right) = \frac{1}{1 + \exp\left( - z_2 \right)}$$

---

### Layer 9: GenAI Interface & Conversational Advisor (Interaction)

#### Operational Role & Computational Philosophy
Layer 9 serves as the conversational interaction hub. It translates biophysical and prescriptive states into persona-grounded natural language summaries, syncs ActionCards with trackable FieldTasks, manages data requests using Value-of-Information (VoI) metrics, and verifies response quality.

#### Core Engines (Exact Count: 17)
1. **ContextAssembly** (`layer9_interface/engines/context_assembly.py`): Integrates raw telemetry and processed outputs from Layers 1 to 8 and Layer 10 (SIRE) into a unified structured `Layer9Input`.
2. **IntentRouter** (`layer9_interface/engines/intent_router.py`): Classifies user queries into intent categories (`UserIntent`) and detects the farmer's agricultural expertise level (`ExpertiseLevel`), adjusting the system's explanation depth and vocabulary.
3. **ConversationMemory** (`layer9_interface/engines/conversation_memory.py`): Manages multi-turn conversation memory, tracking active session contexts, crop focuses, and preceding turns to support natural follow-up queries.
4. **AdvisoryEngine** (`layer9_interface/engines/advisory_engine.py`): Generates grounded templates summarizing diagnoses, actions, and schedules matching the user's expertise level.
5. **QAEngine** (`layer9_interface/engines/qa_engine.py`): Resolves free-text user queries by routing them to grounded LLM contexts, ensuring responses only contain verified facts from upstream databases.
6. **ReportEngine** (`layer9_interface/engines/report_engine.py`): Compiles comprehensive, formatted markdown reports summarizing plot statuses, economic forecasts, and risk trends.
7. **SpatialNarrator** (`layer9_interface/engines/spatial_narrator.py`): Translates spatial management zone data (Layer 10) into natural language explanations, highlighting localized soil, water, and crop anomalies.
8. **AlertEngine** (`layer9_interface/engines/alert_engine.py`): Generates push and SMS notifications for weather risks, nutrient deficits, and biological threats, resolving severity thresholds to prevent alert fatigue.
9. **CoachEngine** (`layer9_interface/engines/coach_engine.py`): Proactively prompts and guides farmers to collect specific field observations, explaining the biophysical value of the requested data.
10. **TaskManager** (`layer9_interface/engines/task_manager.py`): Synchronizes prescriptive ActionCards (Layer 8) with dynamic, trackable `FieldTask` lists and overdue metrics.
11. **DataRequest** (`layer9_interface/engines/data_request.py`): Identifies biophysical data gaps (e.g., outdated satellite data), generating structured requests for soil/pest photos to improve model confidence.
12. **ReminderEngine** (`layer9_interface/engines/reminder_engine.py`): Triggers time-sensitive push/SMS notifications based on weather windows, crop stages, or data staleness.
13. **PolicyEnforcer** (`layer9_interface/engines/policy_enforcer.py`): Audits generated summaries against allowed terminology lists, filters out unsafe chemical recommendations, and injects disclaimers when confidence is low.
14. **HallucinationGuard** (`layer9_interface/hallucination_guard.py`): programmatically validates generated text, ensuring every number, date, rate, and zone matches the verified upstream data.
15. **ResponseQuality** (`layer9_interface/engines/response_quality.py`): Evaluates response quality, scoring naturalness, template compliance, and completeness to feed the system's learning loop.
16. **TelemetryCollector** (`layer9_interface/engines/telemetry_collector.py`): Logs activity details, latency traces, and intent distributions to a JSONL log file.
17. **LocalVLM** (`layer9_interface/engines/local_vlm.py`): Processes base64 scouting photographs locally using a convolutional neural network, identifying leaf symptoms and pest pressure.
18. **WhatIfSandbox** (`layer9_interface/engines/what_if_sandbox.py`): Executes the custom what-if sandbox simulation, allowing interactive trials of alternative schedules.

#### Input & Output Interfaces
* **Upstream Inputs**: Master input payloads, query intents, base64 photographed leaves, and scheduling constraints.
* **Downstream Outputs**: Strongly-typed `InterfaceOutput` containing summaries, zone cards, alerts, explanations, and safety disclaimers.

#### Biophysical Mathematical Formulations
* **Response Groundedness Score**:
  $$S_{ground} = \max\left( 0.0, 1.0 - N_{hallucination\_flags} \cdot 0.15 \right)$$
  Where $N_{hallucination\_flags}$ represents the number of validation failures identified by the HallucinationGuard.
* **Proactive Value-of-Information (VoI)**:
  $$\text{VoI} = \Delta \text{Confidence}_{\text{estimated}} \cdot \text{Urgency}_{\text{active}}$$

---

### Layer 10: SIRE - Spatial Representation & Geostatistics (Geostatistics)

#### Operational Role & Computational Philosophy
Layer 10 (SIRE) operates as the spatial and geostatistical core. Fusing telemetry with Layer 1 features, it executes semivariogram estimation, Ordinary Kriging spatial interpolations, spatial entropy calculations, and contour vectorization to define within-field management zones.

#### Core Engines (Exact Count: 10)
1. **SemivariogramEngine** (`layer10_sire/zones/semivariogram.py`): Estimates spatial semivariograms to model the spatial continuity of soil and vegetation properties.
2. **KrigingEngine** (`layer10_sire/zones/kriging.py`): Executes spatial interpolations using Ordinary Kriging algorithms to generate continuous maps.
3. **EntropyEngine** (`layer10_sire/zones/entropy.py`): Calculates spatial entropy to quantify field soil and crop variability.
4. **ContourEngine** (`layer10_sire/zones/contour.py`): Generates vector boundaries to define management zones based on soil texture and crop performance.
5. **GeoregistrationEngine** (`layer10_sire/imagery/georegistration.py`): Ortho-rectifies and geoconforms raw satellite rasters onto field coordinate systems.
6. **ExplainabilityEngine** (`layer10_sire/explainability.py`): Generates natural language explanations of geostatistical zoning, explaining spatial soil and water dynamics.
7. **ConversationalExplainability** (`layer10_sire/explainability_conversational.py`): Generates dialog cards explaining spatial within-field soil and crop anomalies.
8. **L10FrontendBridge** (`layer10_sire/l10_frontend_bridge.py`): Compiles geostatistical rasters into GeoJSON vector layers for display on the frontend map.
9. **L0EnricherEngine** (`layer10_sire/layer0_enricher.py`): Projects spatial telemetry down to Layer 0 in-situ probe nodes using geostatistical Kriging.
10. **L1EnricherEngine** (`layer10_sire/layer1_enricher.py`): Computes spatial soil texture and pedotransfer limits across management zones.

#### Input & Output Interfaces
* **Upstream Inputs**: Calibrated landscape states, in-situ probe readings, and satellite imagery rasters.
* **Downstream Outputs**: Geostatistical GeoJSON maps, spatial zones, spatial entropy values, and georegistered surfaces.

#### Biophysical Mathematical Formulations
* **Geostatistical Semivariogram**:
  $$\gamma(h) = \frac{1}{2 N(h)} \sum_{i=1}^{N(h)} \left[ Z(\mathbf{x}_i) - Z(\mathbf{x}_i + \mathbf{h}) \right]^2$$
* **Spatial Ordinary Kriging System**:
  $$Z^*(\mathbf{x}_0) = \sum_{i=1}^n \lambda_i \cdot Z(\mathbf{x}_i)$$
  $$\sum_{j=1}^n \lambda_j \cdot \gamma(\mathbf{x}_i - \mathbf{x}_j) + \mu = \gamma(\mathbf{x}_i - \mathbf{x}_0) \quad \forall i, \quad \sum_{j=1}^n \lambda_j = 1$$
* **Spatial Entropy Heterogeneity**:
  $$H_{\text{spatial}} = - \sum_{k=1}^K p_k \cdot \ln(p_k)$$

---

## 3. Master Operational Data Flow Matrix

The operational data flow matrix details the programmatic inputs, outputs, and dependencies across all layers.

| Step | Processing Node | Upstream Dependency | Downstream Target | Core Variables Transferred |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1** | **Layer 0 Ingestion** | Hardware sensors, Copernicus APIs | Layer 1 Environmental Fusion | Raw S2 spectral bands, FDR frequencies, localized wind/temp |
| **Step 2** | **Layer 0 QA/QC** | Raw Ingested payloads | Layer 0 consensus filter | Spike detection z-scores, calibration metrics |
| **Step 3** | **Layer 0 Consensus** | QA/QC filtered streams | Layer 1 Landscape Fusion | Calibrated air temperature consensus grids, soil moisture inputs |
| **Step 4** | **Layer 1 Terrain** | Topographic DEM layers | Layer 1 pedotransfer engines | Aspect, slope angles, Solar microclimate corrections |
| **Step 5** | **Layer 1 Pedotransfer** | Soil maps, clay fractions | Layer 3 dual-Kc water balance | Porosity, Field Capacity ($\theta_{fc}$), Wilting Point ($\theta_{wp}$) |
| **Step 6** | **Layer 1 SAR Tillage** | Sentinel-1 SAR imagery | Layer 4 Soil Carbon model | Backscatter spikes ($\Delta \sigma^0$), tillage event timestamps |
| **Step 7** | **Layer 2 Whittaker** | Sentinel-2 raw NDVI layers | Layer 2 Beer-Lambert LAI | Smoothed vegetative profiles, cross-validation parameters ($\lambda$) |
| **Step 8** | **Layer 2 Beer-Lambert** | Smoothed NDVI profiles | Layer 3 Dual-Kc water balance | Leaf Area Index (LAI) values, canopy heat fluxes |
| **Step 9** | **Layer 3 FAO-56 Dual-Kc**| Leaf Area Index (LAI) | Layer 3 water balance track | Basal crop coefficient scheduler ($K_{cb}$), soil evaporation ($K_e$) |
| **Step 10** | **Layer 3 Water balance**| Crop water coefficients | Layer 8 prescriptive optimization | Soil moisture root zone deficits ($D_r$), irrigation schedules |
| **Step 11** | **Layer 4 Mitscherlich**| Soil testing databases | Layer 8 prescriptive scheduler | Crop nutrient uptake curves, fertilizer split-application rates |
| **Step 12** | **Layer 4 P Langmuir** | Soil testing databases | Layer 8 variable rate optimization | Active soil mineral phosphorus pools, phosphorus buffering capacities |
| **Step 13** | **Layer 5 spore wind-shear**| Daily wind speeds, leaf wetness | Layer 5 Cauchy dispersal kernel | Spore release probabilities, leaf fluttering speeds |
| **Step 14** | **Layer 5 Cauchy Dispersal**| Spore release probabilities | Layer 8 IPM cascade enforcer | Spatial spore deposition curves downwind ($I(d)$) |
| **Step 15** | **Layer 6 RothC Carbon** | Tillage timestamps, soil test data | Layer 6 Strategic Economics | Daily organic carbon transformation profiles across carbon pools |
| **Step 16** | **Layer 6 Monte Carlo Yield**| Leaf Area Index, water deficits | Layer 6 Strategic Economics | Crop yield distributions ($P_{10}$, $P_{50}$, $P_{90}$) |
| **Step 17** | **Layer 7 Planting window** | Mean soil temperatures | Layer 8 multi-objective scheduler | Germination suitability probability metrics |
| **Step 18** | **Layer 8 Multi-objective**| Deficits, nutrient requirements | Layer 8 TAM neural networks | Structured prescriptive ActionCards, prioritized plans |
| **Step 19** | **Layer 8 TAM Neural Net** | ActionCards, cost sensitivity | Layer 9 interface advisor | Farmer adoption probability metrics ($a_2$) |
| **Step 20** | **Layer 9 Interface summary**| ActionCards, disclaimers | Layer 9 UI cards, Frontend map | Persona-grounded natural language advice summaries |
| **Step 21** | **Layer 10 SIRE Spatial** | Landscape states, satellite data | Layer 9 Frontend bridge | Geostatistical Ordinary Kriging surfaces, contour vector zones |

---

## 4. Master Biophysical & Geostatistical Equations (LaTeX)

### 1. Soil Moisture Depletion & Effective Precipitation Infiltration Invariant
The daily root zone water balance must remain bounded within physical soil limits, where soil moisture depletion ($D_r$) cannot exceed total available water ($TAW$) and effective precipitation is controlled by soil infiltration capacity (Layer 3 Decision):

$$D_r = \max\left( 0.0, \min\left( TAW, D_{r,\text{prev}} - P_{\text{eff}} - I_{\text{eff}} + ET_c + DP \right) \right)$$

$$TAW = 1000 \cdot \left( \theta_{fc} - \theta_{wp} \right) \cdot Z_r$$

$$P_{\text{eff}} = P \cdot \left( 1.0 - \alpha_{\text{slope}} \cdot \sin(\beta_{\text{slope}}) \right) \cdot \left( 1.0 - \exp\left( - \frac{\text{Infiltration}}{\theta_{fc} - \theta} \right) \right)$$

Where:
* $TAW$ is the Total Available Water (mm), $\theta_{fc}$ and $\theta_{wp}$ are the volumetric water content at field capacity and wilting point, and $Z_r$ is the active root depth (m).
* $P_{\text{eff}}$ is the effective precipitation infiltrating the soil, adjusted for slope runoff ($\beta_{\text{slope}}$) and soil saturation.

### 2. Double-Difference Causal Intervention Evaluator
The real economic benefit of prescriptive split-applications is isolated against spatial control zones within the same field using a Difference-in-Differences causal evaluator (Layer 6 Yield):

$$\Delta_{\text{causal}} = \left( Y_{\text{treated},\text{post}} - Y_{\text{treated},\text{pre}} \right) - \left( Y_{\text{control},\text{post}} - Y_{\text{control},\text{pre}} \right)$$

$$\text{ROI}_{\text{causal}} = \frac{\Delta_{\text{causal}} \cdot \text{Price}_{\text{crop}} - \text{Cost}_{\text{treatment}}}{\text{Cost}_{\text{treatment}}}$$

Where:
* $Y_{\text{treated}}$ is the yield in management zones where the prescription was executed.
* $Y_{\text{control}}$ is the yield in synthetic control zones where standard base rates were applied.

### 3. Soil Organic Carbon RothC first-order kinetics
Soil carbon decomposition and carbon sequestration rates are modeled using first-order decay kinetics across DPM, RPM, BIO, and HUM soil carbon pools (Layer 6 Yield):

$$\frac{dC_{\text{DPM}}}{dt} = \text{Input}_{\text{plant}} \cdot f_{\text{DPM}} - k_{\text{DPM}} \cdot C_{\text{DPM}} \cdot f(T_s) \cdot f(\theta) \cdot \left( 1.0 - \Omega_{\text{tillage}} \right)$$

$$\frac{dC_{\text{RPM}}}{dt} = \text{Input}_{\text{plant}} \cdot (1.0 - f_{\text{DPM}}) - k_{\text{RPM}} \cdot C_{\text{RPM}} \cdot f(T_s) \cdot f(\theta) \cdot \left( 1.0 - \Omega_{\text{tillage}} \right)$$

$$\frac{dC_{\text{BIO}}}{dt} = 0.46 \cdot \left( k_{\text{DPM}} \cdot C_{\text{DPM}} + k_{\text{RPM}} \cdot C_{\text{RPM}} \right) - k_{\text{BIO}} \cdot C_{\text{BIO}} \cdot f(T_s) \cdot f(\theta)$$

Where:
* $f_{\text{DPM}}$ is the plant carbon fraction allocated to the decomposable plant material pool.
* $k_i$ is the decomposition constant, and $f(T_s), f(\theta)$ are temperature and moisture scale factors.
* $\Omega_{\text{tillage}}$ is the tillage intensity penalty, representing accelerated carbon oxidation.

### 4. Spore Release Drag and Leaf resontant fluttering
spore detachment from infected plant leaves is modeled as a function of wind drag and leaf resonant fluttering (Layer 5 Bio):

$$\text{Logit}(P_{release}) = 2.0 \cdot \left[ F_{drag} + F_{inertial} - F_{adhesion} \right]$$

$$F_{drag} = \frac{1}{2} C_d \cdot \rho_{air} \cdot u^2 \cdot A_{spore}$$

$$F_{inertial} = m_{spore} \cdot a_{flutter} = m_{spore} \cdot \left( 2\pi \cdot f \right)^2 \cdot \left[ \frac{\beta_{flutter} \cdot u^{1.5}}{\sqrt{\text{LAI}}} \right]$$

$$F_{adhesion} = F_0 \cdot \left( 1.0 + 0.05 \cdot \text{RH}_{\%} \right)$$

Where $u$ is the canopy wind speed, $\text{RH}_{\%}$ is the relative humidity, and $a_{flutter}$ is the leaf fluttering acceleration.

---

## 5. Peer-Reviewed Scientific Bibliography

The biophysical, geostatistical, economic, and conversational models integrated into AgriBrain are based on the following peer-reviewed literature:

* **Geostatistical Kriging & Semivariance**: Journel, A. G., & Huijbregts, C. J. (1978). *Mining Geostatistics*. Academic Press.
* **Whittaker Smoothing Algorithms**: Eilers, P. H. (2003). *A Perfect Smoother*. Analytical Chemistry, 75(14), 3631-3637.
* **van Genuchten Soil Water Retention**: van Genuchten, M. T. (1980). *A Closed-form Equation for Predicting the Hydraulic Conductivity of Unsaturated Soils*. Soil Science Society of America Journal, 44(5), 892-898.
* **FAO-56 Dual crop ET balance**: Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop Evapotranspiration: Guidelines for Computing Crop Water Requirements*. FAO Irrigation and Drainage Paper 56.
* **Mitscherlich-Baule Crop Yield response**: Baule, B. (1918). *Zu Mitscherlichs Gesetz der physiologischen Beziehungen*. Landwirtschaftliche Jahrbücher, 51, 363-385.
* **Spore Dispersal & Cauchy Physics**: Aylor, D. E. (1990). *The Role of Wind in Aerial Dispersal of Fungal Spores*. Annual Review of Phytopathology, 28(1), 73-92.
* **RothC Organic Carbon Model**: Coleman, K., & Jenkinson, D. S. (1996). *RothC-26.3: A Model for the Turnover of Carbon in Soil*. In: *Evaluation of Soil Organic Matter Models*. Springer.
* **Technology Acceptance Model (TAM)**: Davis, F. D. (1989). *Perceived Usefulness, Perceived Ease of Use, and User Acceptance of Information Technology*. MIS Quarterly, 13(3), 319-340.
* **Prospect Theory & Nudge Framing**: Kahneman, D., & Tversky, A. (1979). *Prospect Theory: An Analysis of Decision under Risk*. Econometrica, 47(2), 263-291.
* **Proactive Nudging & Human-AI Interfaces**: Shneiderman, B. (2020). *Human-Centered Artificial Intelligence: Reliable, Safe & Trustworthy*. International Journal of Human-Computer Interaction, 36(6), 495-504.
