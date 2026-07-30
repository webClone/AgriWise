# Layer 0 Audit: Sensors, Ingestion, Assimilation, and QA Validation

## 1. Executive Summary & Verification Status
Layer 0 is the sensory, ingestion, and physical assimilation gate of the AgriBrain architecture. It is responsible for raw telemetry ingestion, UTM gridding, quality assurance filters, cross-source consistency validation, and latent state estimation using an Extended Kalman Filter (EKF).
* **Code Integrity:** High. All modules compile successfully.
* **Test Status:** 151/151 unit tests passed; all 13 regression suite checks passed.
* **Database State:** Synchronized with the `Sensor`, `SensorReading`, and `SoilAnalysis` Prisma schemas.

---

## 2. Granular Engine Inventory & Mapping (30 Engines)
The layer contains 30 active, specialized engines:

### A. Geotransform & Spatial Gridding
1. **PlotGrid Engine** ([plot_grid.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/plot_grid.py)): Projects coordinates from WGS84 degrees to local UTM meters using transverse Mercator transforms, managing boundary alpha masks to prevent field edge contamination.
2. **WeaknessRaster Engine** ([weakness_raster.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/weakness_raster.py)): Clusters pixel-level biophysical stress weaknesses using Otsu-thresholding and spatial morphological filters to segment initial management zones.
3. **GeoContextEngine** ([geo_context/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/geo_context/engine.py)): Top-level geoprocessing orchestrator. Fuses Digital Elevation Models (DEM), ESA WorldCover cropland fractions, and Dynamic World probabilities to output physiological priors.
4. **SensorPlacementEngine** ([geo_context/sensor_placement.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/geo_context/sensor_placement.py)): Recommends optimal physical locations for IoT weather stations and soil moisture probes based on terrain slope, aspect, and water accumulation routes.

### B. Raw Ingestion & Source Adapters
5. **UserInputAdapter Engine** ([user_input_adapter.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/user_input_adapter.py)): Normalizes user-reported management events (sowing dates, irrigation volumes, crop types) into structured observation packets.
6. **SensorIngestionEngine** ([sensors/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/sensors/engine.py)): Consolidates and parses point-measurements from agricultural IoT telemetry stations.
7. **IrrigationEventDetector** ([sensors/irrigation_event_detector.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/sensors/irrigation_event_detector.py)): Identifies unrecorded watering events by parsing sudden vertical spikes in soil moisture probe time-series.
8. **PerceptionPacketFactory** ([perception_packet_factory.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/perception_packet_factory.py)): Directs close-range camera frameworks, translating image files into structured observation packets.
9. **EnvironmentalEngine** ([environment/engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/environment/engine.py)): Fuses meteorological inputs (ERA5 reanalysis, Open-Meteo, local station grids) into unified climatic models.
10. **StateAdapter** ([environment/state_adapter.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/environment/state_adapter.py)): Normalizes weather records into EKF forcing structures and filters out inappropriate forecast variables.

### C. Multi-Source Quality Assessment (QA)
11. **Sentinel2QA** ([source_qa.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/source_qa.py)): Identifies optical cloud shadows, cloud edges, and aerosol contamination, dynamically inflating band uncertainty.
12. **Sentinel1QA** ([source_qa.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/source_qa.py)): Normalizes SAR radar backscatter for incidence angle variations and speckle noise.
13. **WeatherQA** ([source_qa.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/source_qa.py)): Validates laboratory temperature, pressure, and VPD variables against extreme physical envelopes.
14. **SoilQA** ([source_qa.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/source_qa.py)): Filters and sanitizes physical soil metrics (pH, organic carbon, clay fractions).
15. **UserEventQA** ([source_qa.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/source_qa.py)): Filters and sanitizes manual farmer inputs (dates, chemical volumes).
16. **ImageQAEngine** ([image_qa.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/image_qa.py)): Analyzes smartphone scouting photographs for exposure anomalies, blur, framing, and georeference flags.
17. **SensorQA** ([sensors/qa.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/sensors/qa.py)): Screens IoT sensor readings for stuck-at flatlines, out-of-bounds measurements, and high-frequency spike faults.

### D. Cross-Source Validation
18. **ValidationGraph** ([validation_graph.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/validation_graph.py)): Evaluates cross-source physical consistency (e.g. soil wetness without rain, or camera greenness vs. NDVI) to dynamically adjust source reliability.
19. **SensorSatelliteValidation** ([sensors/sensor_satellite_validation.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/sensors/sensor_satellite_validation.py)): Compares point-level soil probe readings against spatial satellite SAR wetness curves.
20. **SensorWeatherValidation** ([sensors/sensor_weather_validation.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/sensors/sensor_weather_validation.py)): Validates soil moisture infiltration rates against weather reanalysis precipitation events.

### E. Latent State Assimilation (Extended Kalman Filter)
21. **DailyAssimilationEngine** ([kalman_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/kalman_engine.py)): Manages the multi-zone predict-and-correct loop sequence across days.
22. **ZoneKalmanFilter** ([kalman_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/kalman_engine.py)): Executes the $9 \times 9$ prediction and correction matrix math utilizing an online ML growth rate tuner.
23. **ObservationModel** ([observation_model.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/observation_model.py)): Computes the observation Jacobian matrix ($H$) translating latent variables into telemetry signals.
24. **StatePersistence** ([state_persistence.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/state_persistence.py)): Serializes and restores Kalman state vectors and covariance matrices to ensure historical continuity.
25. **Invariants Enforcer** ([invariants.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/invariants.py)): Enforces non-negotiable physical limits at runtime (e.g. capping NDVI in $[-1.0, 1.0]$ and SM in $[0.0, 1.0]$).

### F. Calibration & Parameter Optimization
26. **GenerativeInversionEngine** ([calibration/generative_inversion.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/calibration/generative_inversion.py)): Inverts biophysical parameters over 10-year historical Sentinel-2 data cubes using Differential Evolution or multi-grid searches to extract intrinsic Plot DNA traits.
27. **MonteCarloMultiverse** ([calibration/monte_carlo_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/calibration/monte_carlo_engine.py)): Simulates parameter sensitivity curves across a multiverse of process model permutations.
28. **MicroclimateSPAC** ([calibration/microclimate_spac.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/calibration/microclimate_spac.py)): Compares gridded ERA5 weather predictions against local NDVI response to isolate microclimatic decoupling.
29. **HydrologicalResilience** ([calibration/hydrological_resilience.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/calibration/hydrological_resilience.py)): Cross-correlates precipitation events with NDVI recovery times to measure water stress memory and precipitation use efficiency.
30. **DNACache** ([calibration/dna_cache.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/dna_cache.py)): Caches persistent crop genetics and variety metadata to scale process parameters and adjust process noise.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - Raw multi-spectral bands from Sentinel-2 ($B_2, B_3, B_4, B_8, B_{11}, B_{12}$).
  - Sentinel-1 dual-polarization amplitude backscatters ($VV, VH$).
  - Point-level IoT soil moisture probe logs and weather station telemetry.
  - Manual user management records (sowing dates, irrigation amounts).
* **Outputs Generated:**
  - Structured `ObservationPacket` ([observation_packet.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/observation_packet.py)) envelopes containing normalized variables, uncertainties ($\sigma$), and QA scores.
  - Fused latent `StateVector` ([state_vector.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/state_vector.py)) containing:
    1. `lai_proxy` (index 0): Leaf Area Index $[0.0, 10.0]$
    2. `biomass_proxy` (index 1): Structural plant biomass $[0.0, 20.0]$
    3. `sm_0_10` (index 2): Soil VWC (0–10cm surface layer) $[0.0, 1.0]$
    4. `sm_10_40` (index 3): Soil VWC (10–40cm root zone layer) $[0.0, 1.0]$
    5. `canopy_stress` (index 4): Volumetric soil water deficit canopy stress index $[0.0, 1.0]$
    6. `phenology_gdd` (index 5): Accumulated Growing Degree Days
    7. `phenology_stage` (index 6): Smooth stage float $[0.0, 4.0]$
    8. `stress_thermal` (index 7): Heat/frost stress index $[0.0, 1.0]$
    9. `photosynthetic_efficiency` (index 8): Xanthophyll/SIF-based photosynthetic efficiency $[0.0, 1.0]$

---

## 4. Key Mathematical Formulations

### A. Geotransform Projection
Coordinates are projected from geographic ellipsoids to local UTM meters:
$$\Delta y = (lat - lat_{origin}) \times 111,132 \text{ meters}$$
$$\Delta x = (lng - lng_{origin}) \times 111,320 \times \cos\left(\frac{lat \times \pi}{180}\right) \text{ meters}$$

### B. Extended Kalman Filter (EKF) Matrix Loop
* **Prediction Equations:**
  $$\hat{x}_{t|t-1} = f(\hat{x}_{t-1|t-1}, u_t)$$
  $$P_{t|t-1} = F_t P_{t-1|t-1} F_t^T + Q_t$$
  Where $Q_t = \text{diag}[0.04, 0.02, 0.03, 0.02, 0.03, 1.0, 0.02, 0.02, 0.03]$
* **Correction Equations (Joseph Form Covariance Update):**
  $$S_t = H_t P_{t|t-1} H_t^T + R_{effective}$$
  $$K_t = P_{t|t-1} H_t^T S_t^{-1}$$
  $$\hat{x}_{t|t} = \hat{x}_{t|t-1} + K_t \left(y_t - h(\hat{x}_{t|t-1})\right)$$
  $$P_{t|t} = (I - K_t H_t) P_{t|t-1} (I - K_t H_t)^T + K_t R_{effective} K_t^T$$
  Guarantees positive semi-definiteness of the error covariance matrix at runtime.

### C. Saxton-Rawls Soil Pedotransfer Equations
Translates Clay %, Sand %, and Organic Matter (OM) % into Plant-Available Water Capacity (PAWC):
$$OM\% = SOC_{g/kg} \times 0.1$$
$$\theta_{33}^* = -0.251 \cdot s + 0.195 \cdot c + 0.011 \cdot OM + 0.006 \cdot (s \cdot OM) - 0.027 \cdot (c \cdot OM) + 0.452 \cdot (s \cdot c) + 0.299$$
$$\theta_{33} = \theta_{33}^* + \left(1.283 \cdot (\theta_{33}^*)^2 - 0.374 \cdot \theta_{33}^* - 0.015\right)$$
$$\theta_{1500}^* = -0.024 \cdot s + 0.487 \cdot c + 0.006 \cdot OM + 0.005 \cdot (s \cdot OM) - 0.013 \cdot (c \cdot OM) + 0.068 \cdot (s \cdot c) + 0.031$$
$$\theta_{1500} = \theta_{1500}^* + \left(0.14 \cdot \theta_{1500}^* - 0.02\right)$$
$$PAWC = \max(0, \theta_{33} - \theta_{1500}) \times 1000 \quad \text{(mm/m)}$$

### D. Terrain Gradient Features
Calculated via DEM second-order central difference equations:
$$\theta_{slope} = \arctan\left(\sqrt{\left(\frac{\partial elev}{\partial x}\right)^2 + \left(\frac{\partial elev}{\partial y}\right)^2}\right)$$
$$\text{TWI Proxy} = \ln\left(\frac{\text{Pixel Area}}{\tan\left(\max(\theta_{slope}, 0.1 \times \frac{\pi}{180})\right)}\right)$$

### E. Biophysical Observation Models ($y_{obs} = h(x)$)
Each telemetry source and visual observation has a mathematically mapped relationship to the EKF's latent state variables:

* **Sentinel-2 NDVI:**
  $$\text{NDVI} = \text{NDVI}_{soil} + (\text{NDVI}_{max} - \text{NDVI}_{soil}) \times \left(1 - e^{-k \cdot \text{LAI}}\right)$$
  Where $\text{NDVI}_{soil} = 0.15, \text{NDVI}_{max} = 0.90, k = 0.5$. Noise: $R = 0.02^2$ ($\sigma = 0.02$).
  Jacobian row: $H[\text{IDX\_LAI}] = (\text{NDVI}_{max} - \text{NDVI}_{soil}) \cdot k \cdot e^{-k \cdot \text{LAI}}$.

* **Sentinel-2 EVI:**
  $$\text{EVI} = \text{EVI}_{soil} + (\text{EVI}_{max} - \text{EVI}_{soil}) \times \left(1 - e^{-k \cdot \text{LAI}}\right)$$
  Where $\text{EVI}_{soil} = 0.10, \text{EVI}_{max} = 0.85, k = 0.4$. Noise: $R = 0.03^2$ ($\sigma = 0.03$).
  Jacobian row: $H[\text{IDX\_LAI}] = (\text{EVI}_{max} - \text{EVI}_{soil}) \cdot k \cdot e^{-k \cdot \text{LAI}}$.

* **Sentinel-2 NDMI:**
  $$\text{NDMI} = \text{NDMI}_{base} \times (1 - \text{stress} \times 0.6) \times \min\left(1.0, \frac{\text{LAI}}{3.0}\right)$$
  Where $\text{NDMI}_{base} = 0.4$. Noise: $R = 0.04^2$ ($\sigma = 0.04$).
  Jacobian row:
  - If $\text{LAI} < 3$: $H[\text{IDX\_LAI}] = \text{NDMI}_{base} \cdot (1 - \text{stress} \cdot 0.6) / 3.0$
  - If $\text{LAI} \ge 3$: $H[\text{IDX\_LAI}] = 0.0$
  - $H[\text{IDX\_CANOPY\_STRESS}] = -\text{NDMI}_{base} \cdot 0.6 \cdot \min(1.0, \text{LAI}/3.0)$.

* **Sentinel-1 SAR VV:**
  $$\text{VV(dB)} = \text{VV}_{dry} + \text{sens} \times \text{SM}_{0\_10} + \text{atten} \times \text{LAI}$$
  Where $\text{VV}_{dry} = -18.0\text{ dB}, \text{sens} = 10.0\text{ dB}, \text{atten} = -0.3\text{ dB}$. Noise: $R = 1.5^2$ ($\sigma = 1.5\text{ dB}$).
  Jacobian row: $H[\text{IDX\_SM\_0\_10}] = 10.0, H[\text{IDX\_LAI}] = -0.3$.

* **Sentinel-1 SAR VH:**
  $$\text{VH(dB)} = \text{VH}_{base} + \text{sens}_{bio} \times \text{Biomass} + \text{sens}_{moist} \times \text{SM}_{0\_10}$$
  Where $\text{VH}_{base} = -22.0\text{ dB}, \text{sens}_{bio} = 3.0\text{ dB}, \text{sens}_{moist} = 2.0\text{ dB}$. Noise: $R = 2.0^2$ ($\sigma = 2.0\text{ dB}$).
  Jacobian row: $H[\text{IDX\_BIOMASS}] = 3.0, H[\text{IDX\_SM\_0\_10}] = 2.0$.

* **In-Situ Soil Probe:**
  - **Shallow ($\le 10$cm):** $\text{SM}_{probe} = \text{SM}_{0\_10}$. Noise: $R = 0.03^2$ ($\sigma = 0.03$).
  - **Deep ($> 10$cm):** $\text{SM}_{probe} = w_{top} \cdot \text{SM}_{0\_10} + (1 - w_{top}) \cdot \text{SM}_{10\_40}$ where $w_{top} = \max\left(0, 1.0 - \frac{\text{Depth}_{cm} - 10}{30}\right)$. Noise: $R = 0.04^2$ ($\sigma = 0.04$).
  Jacobian row: $H[\text{IDX\_SM\_0\_10}] = w_{top}, H[\text{IDX\_SM\_10\_40}] = 1 - w_{top}$.

* **Camera / Satellite RGB Canopy Cover:**
  $$\text{Cover} = 1.0 - e^{-k \cdot \text{LAI}}$$
  Where $k = 0.6$ (camera) or $k = 0.5$ (satellite). Noise: $R = 0.08^2$ (camera) or $R = 0.10^2$ (satellite).
  Jacobian row: $H[\text{IDX\_LAI}] = k \cdot e^{-k \cdot \text{LAI}}$.

* **Phenology Stage Camera Heuristic:**
  $$\text{Stage}_{obs} = \text{phenology\_stage}$$
  Direct observation of stage. Noise: $R = 0.80^2$ ($\sigma = 0.80$, reflecting high heuristic uncertainty).
  Jacobian row: $H[\text{IDX\_PHENO\_STAGE}] = 1.0$.

* **Camera / RGB Anomaly Stress Proxy:**
  $$\text{Stress}_{obs} = \text{canopy\_stress}$$
  Direct observation of stress. Noise: $R = 0.30^2$ (camera) or $R = 0.40^2$ (satellite anomaly score).
  Jacobian row: $H[\text{IDX\_CANOPY\_STRESS}] = 1.0$.

* **Sentinel-2 NDRE (Red-Edge):**
  $$\text{NDRE} = \text{NDRE}_{min} + (\text{NDRE}_{max} - \text{NDRE}_{min}) \times \left(1 - e^{-k \cdot \text{LAI}}\right) \times (1 - \text{stress} \times 0.4)$$
  Where $\text{NDRE}_{min} = 0.05, \text{NDRE}_{max} = 0.6, k = 0.35$. Noise: $R = 0.06^2$ ($\sigma = 0.06$).
  Jacobian row:
  - $H[\text{IDX\_LAI}] = 0.5 \cdot (\text{NDRE}_{max} - \text{NDRE}_{min}) \cdot k \cdot e^{-k \cdot \text{LAI}} \cdot (1 - \text{stress} \cdot 0.4)$
  - $H[\text{IDX\_CANOPY\_STRESS}] = -0.5 \cdot (\text{NDRE}_{max} - \text{NDRE}_{min}) \cdot (1 - e^{-k \cdot \text{LAI}}) \cdot 0.4$.

* **Sentinel-2 BSI (Bare Soil Index):**
  $$\text{BSI} = \text{BSI}_{veg} + (\text{BSI}_{bare} - \text{BSI}_{veg}) \times e^{-k \cdot \text{LAI}}$$
  Where $\text{BSI}_{bare} = 0.3, \text{BSI}_{veg} = -0.15, k = 0.4$. Noise: $R = 0.08^2$ ($\sigma = 0.08$).
  Jacobian row: $H[\text{IDX\_LAI}] = -0.5 \cdot (\text{BSI}_{bare} - \text{BSI}_{veg}) \cdot k \cdot e^{-k \cdot \text{LAI}}$.

* **SAR RVI (Radar Vegetation Index):**
  $$\text{RVI} = \text{RVI}_{base} + \text{sens}_{bio} \times \text{Biomass} + \text{sens}_{lai} \times \text{LAI}$$
  Where $\text{RVI}_{base} = 0.2, \text{sens}_{bio} = 0.15, \text{sens}_{lai} = 0.05$. Noise: $R = 0.10^2$ ($\sigma = 0.10$).
  Jacobian row: $H[\text{IDX\_BIOMASS}] = 0.15, H[\text{IDX\_LAI}] = 0.05$.

* **SAR Moisture Proxy:**
  $$\text{SM}_{proxy} = \max\left(0.0, \min(1.0, 2.0 \cdot \text{SM}_{0\_10})\right)$$
  Noise: $R = 0.12^2$ ($\sigma = 0.12$, uncalibrated baseline).
  Jacobian row: $H[\text{IDX\_SM\_0\_10}] = 2.0$ if $\text{SM}_{0\_10} < 0.5$ else $0.0$.

* **Sentinel-5P SIF (Solar-Induced Fluorescence):**
  $$\text{SIF} = \text{SIF}_{max} \times \text{photo\_eff} \times \left(1 - e^{-k \cdot \text{LAI}}\right)$$
  Where $\text{SIF}_{max} = 2.0, k = 0.5$. Noise: $R = 0.15^2$ ($\sigma = 0.15$, regional $7\text{km}$ resolution).
  Jacobian row:
  - $H[\text{IDX\_PHOTO\_EFF}] = \text{SIF}_{max} \cdot (1 - e^{-k \cdot \text{LAI}})$
  - $H[\text{IDX\_LAI}] = \text{SIF}_{max} \cdot \text{photo\_eff} \cdot k \cdot e^{-k \cdot \text{LAI}}$.

* **Sentinel-2 PRI (Photochemical Reflectance Index):**
  $$\text{PRI} = \left(\text{PRI}_{stressed} + (\text{PRI}_{healthy} - \text{PRI}_{stressed}) \times \text{photo\_eff}\right) \times \min\left(1.0, \frac{\text{LAI}}{3.0}\right)$$
  Where $\text{PRI}_{stressed} = -0.05, \text{PRI}_{healthy} = 0.02$. Noise: $R = 0.08^2$ ($\sigma = 0.08$).
  Jacobian row:
  - $H[\text{IDX\_PHOTO\_EFF}] = (\text{PRI}_{healthy} - \text{PRI}_{stressed}) \cdot \min(1.0, \text{LAI}/3.0)$
  - If $\text{LAI} < 3$: $H[\text{IDX\_LAI}] = (\text{PRI}_{stressed} + (\text{PRI}_{healthy} - \text{PRI}_{stressed}) \cdot \text{photo\_eff}) / 3.0$
  - If $\text{LAI} \ge 3$: $H[\text{IDX\_LAI}] = 0.0$.

* **Drone Weed Fraction:**
  $$\text{Weed} = 0.3 \times \text{stress} + 0.2 \times (1.0 - \text{photo\_eff})$$
  Noise: $R = 0.25^2$ ($\sigma = 0.25$, indirect proxy).
  Jacobian row: $H[\text{IDX\_CANOPY\_STRESS}] = 0.3, H[\text{IDX\_PHOTO\_EFF}] = -0.2$.

---

## 5. Audit Recommendations
1. **Sensor Calibration Drift Monitoring:** Implement cumulative CUSUM drift detection in `SensorQA` to flag sensors experiencing progressive calibration degradation.
2. **Dynamic Process Noise ($Q_t$) Tuning:** Modify process covariance to scale process noise dynamically based on extreme meteorological volatility (e.g., thermal shock events).

