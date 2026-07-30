# Layer 0: Sensors, Ingestion, Assimilation, and QA Validation

This layer forms the biophysical foundation and data-ingestion gate of the AgriWise system. It is responsible for raw telemetry ingestion, geotransform gridding, multi-source quality assessment, cross-source physical consistency validation, and zone-level state estimation using an Extended Kalman Filter (EKF).

---

## 1. Granular Engine Inventory (30 Specialized Core Modules)

This layer contains exactly 30 specialized active engines, grouped by operational responsibility:

### A. Geotransform & Spatial Gridding
1. **PlotGrid Engine** ([plot_grid.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/plot_grid.py)): Projects coordinate bounds from WGS84 degrees to local UTM meters using transverse Mercator transforms, manages CRS conversions, and computes sub-pixel boundary alpha masks to prevent field edge signal contamination.
2. **WeaknessRaster Engine** ([weakness_raster.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/weakness_raster.py)): Clusters pixel-level biophysical stress weakness indices to output initial spatial zone segments using Otsu-thresholding and spatial morphological filters.
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
30. **DNACache** ([calibration/dna_cache.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/calibration/dna_cache.py)): Caches persistent crop genetics and variety metadata to scale process parameters and adjust process noise.

---

## 2. Granular 21-Step Pipeline Execution

Every daily run of the Layer 0 ingestion and assimilation engine executing on a field plot follows this deterministic sequence:

1. **Ingest Raw Telemetry**: Collects heterogeneous raw data packets from active satellites (Sentinel-2, Sentinel-1, Sentinel-5P), weather stations, in-situ IoT soil probes, and close-range smartphone camera frameworks.
2. **Convert to Universal Envelopes**: Wraps data payloads into structured `ObservationPacket` metadata envelopes carrying initial provenance fields.
3. **Execute UTM Gridding**: Projects coordinates from geographic WGS84 degrees into UTM local meters using `PlotGrid` to compute cell distances.
4. **Build Stress Raster Masks**: Analyzes pixel-level bare soil and historical vegetated signatures via `WeaknessRaster` to construct field zone partitions.
5. **Parse Multispectral Bands**: Extracts optical band reflectances ($B_2, B_3, B_4, B_8, B_{11}, B_{12}$) from Sentinel-2 and computes NDVI, EVI, and NDMI.
6. **Parse SAR Backscatter (VV/VH)**: ATTENTION: Converts raw amplitude backscatter to decibel (dB) scale to ensure signal linearity.
7. **Screen Optical Clouds (Sentinel2QA)**: Processes L2A Scene Classification (SCL) maps to locate clouds, shadows, and aerosol edges.
8. **Correct SAR Roughness (Sentinel1QA)**: Adjusts Sentinel-1 backscatter values for incidence angle fluctuations.
9. **Screen Meteorological Outliers (WeatherQA)**: Sanitizes temperature, precipitation, and VPD signals against physical limits.
10. **Screen Soil Telemetry (SoilQA)**: Validates soil moisture, pH, and clay fractions against local soil profiles.
11. **Sanitize Farmer Event Records (UserEventQA)**: Sanitizes sowing, irrigation, and pesticide records to prevent double-entry or typing errors.
12. **Close-Range Photograph QA (ImageQAEngine)**: Filters smartphone photos for exposure anomalies, blur, and georeference drift.
13. **Scouting Perception Translation (PerceptionPacketFactory)**: Translates phone photos into point-level cover and symptom observations.
14. **Run Validation Graph consistency checks**: Evaluates cross-source physical consistency (e.g. soil wetness without rain, or camera greenness vs. NDVI) to detect anomalies.
15. **Compute Dynamic Source Reliability Weights**: Decreases reliability weights ($w_t$) for conflicting sources and slowly recovers weights for consistent ones, capping reliability in $[0.05, 1.0]$.
16. **Biophysical State Prediction (ProcessModel)**: Evolves yesterday's latent state vector $\hat{x}_{t-1|t-1}$ to today's state $\hat{x}_{t|t-1}$ using Growing Degree Days (GDD) and water percolation.
17. **Propagate Process Covariance**: Updates EKF state covariance $P_{t|t-1} = P_{t-1|t-1} + Q_t$, adding process noise based on meteorological volatility.
18. **Calculate Observation Jacobians & Expected Measurements**: Dispatches observations to custom measurement functions to build the mapping matrix $H$ and predict sensor readings.
19. **Compute Kalman Gain ($K$)**: Evaluates innovation covariance $S = H P H^T + R_{effective}$ (where $R_{effective} = \sigma^2/w_t$ incorporates dynamic reliability weights) and calculates optimal weighting gain $K$.
20. **Extended Kalman Filter State Correction**: Corrects latent states: $\hat{x}_{t|t} = \hat{x}_{t|t-1} + K (y_t - h(\hat{x}_{t|t-1}))$.
21. **Numerically Stable Joseph Form Covariance Correction**: Corrects covariance matrix $P_{t|t} = (I - KH)P_{t|t-1}(I - KH)^T + KRK^T$ to guarantee positive semi-definiteness.
22. **Enforce State Invariants & Persist Daily Release**: Clamps latent crop state values to physical boundaries, audits EKF innovations for bias or drift, compiles the final `TrustReport`, and serializes state matrices for inter-temporal continuity.

---

## 3. Data Schemas & Contracts

### A. ObservationPacket ([observation_packet.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/observation_packet.py))

All incoming telemetry is converted to structured observation packets:

* `packet_id` (`str`): Auto-generated deterministic SHA-256 hash derived from the source family, acquisition timestamp, and spatial coordinate bounds.
* `source` (`ObservationSource`): Restricts to: `sentinel2`, `sentinel1`, `sentinel5p`, `weather_station`, `weather_reanalysis`, `weather_forecast`, `soilgrids`, `sensor_iot`, `user_event`, `user_observation`, `drone`, `ip_camera`, `satellite_rgb`, `farmer_photo`.
* `obs_type` (`ObservationType`): Restricts to: `raster`, `point_ts`, `vector`, `image`, `tabular`.
* `timestamp` (`datetime`): Acquisition UTC timestamp.
* `timestamp_end` (`Optional[datetime]`): Boundary timestamp for aggregated temporal windows.
* `geometry_type` (`str`): Resolution geometry: `bbox`, `point`, `polygon`.
* `bbox` (`Optional[Tuple[float, float, float, float]]`): Bounding box coordinates `(min_lng, min_lat, max_lng, max_lat)`.
* `point` (`Optional[Tuple[float, float]]`): In-situ station placement coordinates `(lat, lng)`.
* `payload` (`Dict[str, Any]`): Numeric observation metrics (e.g. `{"ndvi": 0.62}`, `{"soil_moisture": 0.32}`).
* `qa` (`QAMetadata`): Cloud probability, shadow flags, view zenith angle, incidence angle, and station distance metrics.
* `uncertainty` (`UncertaintyModel`): Per-variable instrument measurement standard errors ($\sigma$).
* `provenance` (`Provenance`): List of software processing steps, versions, licenses, and download details.
* `reliability_weight` (`float`): Updated by `ValidationGraph` ranging from $0.05$ to $1.0$.

### B. StateVector ([state_vector.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/state_vector.py))

The 9 latent state variables estimated daily per zone:

* `lai_proxy` (Index $0$): Leaf Area Index $[0.0, 10.0]$ representing canopy density.
* `biomass_proxy` (Index $1$): Structural plant biomass $[0.0, 20.0]$ derived from SAR VH.
* `sm_0_10` (Index $2$): Soil volumetric water content (0–10cm surface layer) $[0.0, 1.0]$.
* `sm_10_40` (Index $3$): Soil volumetric water content (10–40cm root zone layer) $[0.0, 1.0]$.
* `canopy_stress` (Index $4$): Volumetric soil water deficit canopy stress index $[0.0, 1.0]$.
* `phenology_gdd` (Index $5$): Accumulated Growing Degree Days (°C-days).
* `phenology_stage` (Index $6$): Smooth stage float: $0.0$=Dormant, $1.0$=Vegetative, $2.0$=Flowering, $3.0$=Ripening, $4.0$=Senescence.
* `stress_thermal` (Index $7$): Heat/frost stress index $[0.0, 1.0]$.
* `photosynthetic_efficiency` (Index $8$): Xanthophyll and SIF-based photosynthetic efficiency $[0.0, 1.0]$.

---

## 4. Mathematical & Biophysical Formulations

### A. Geotransform Projection
Coordinates are projected from geographic ellipsoids to local UTM meters:
$$\Delta y = (lat - lat_{origin}) \times 111,132 \text{ meters}$$
$$\Delta x = (lng - lng_{origin}) \times 111,320 \times \cos\left(\frac{lat \times \pi}{180}\right) \text{ meters}$$

### B. Growing Degree Day (GDD) Accumulation
Daily thermal energy accumulation drives physiological crop progression:
$$\Delta GDD = \max(0, T_{mean} - T_{base})$$
where $T_{mean} = \frac{T_{max} + T_{min}}{2}$ and $T_{base}$ is the crop-specific base temperature (e.g. $5.0^\circ\text{C}$ for wheat).

### C. Terrain Gradient Features
Terrain attributes are computed from DEM coordinates using second-order central difference gradient equations:
$$\text{Slope Radian} = \theta_{slope} = \arctan\left(\sqrt{\left(\frac{\partial elev}{\partial x}\right)^2 + \left(\frac{\partial elev}{\partial y}\right)^2}\right)$$
$$\text{Slope Degree} = \theta_{slope} \times \frac{180}{\pi}$$
$$\text{Aspect Degree} = \left(90^\circ - \text{atan2}\left(-\frac{\partial elev}{\partial y}, \frac{\partial elev}{\partial x}\right) \times \frac{180}{\pi}\right) \bmod 360^\circ$$
$$\text{Curvature} = \nabla^2 elev = \frac{\partial^2 elev}{\partial x^2} + \frac{\partial^2 elev}{\partial y^2}$$
$$\text{Topographic Wetness Index (TWI) Proxy} = \ln\left(\frac{\text{Pixel Area}}{\tan\left(\max(\theta_{slope}, 0.1 \times \frac{\pi}{180})\right)}\right)$$

### D. Soil Grids Pedogenic Memory & PAWC
Using the Saxton & Rawls (2006) pedotransfer equations, the Plant-Available Water Capacity (PAWC) in mm/m is extracted from Clay, Sand, and Soil Organic Carbon (SOC):
$$OM\% = SOC_{g/kg} \times 0.1$$
$$\theta_{33}^* = -0.251 \cdot s + 0.195 \cdot c + 0.011 \cdot OM + 0.006 \cdot (s \cdot OM) - 0.027 \cdot (c \cdot OM) + 0.452 \cdot (s \cdot c) + 0.299$$
$$\theta_{33} = \theta_{33}^* + \left(1.283 \cdot (\theta_{33}^*)^2 - 0.374 \cdot \theta_{33}^* - 0.015\right)$$
$$\theta_{1500}^* = -0.024 \cdot s + 0.487 \cdot c + 0.006 \cdot OM + 0.005 \cdot (s \cdot OM) - 0.013 \cdot (c \cdot OM) + 0.068 \cdot (s \cdot c) + 0.031$$
$$\theta_{1500} = \theta_{1500}^* + \left(0.14 \cdot \theta_{1500}^* - 0.02\right)$$
$$PAWC = \max(0, \theta_{33} - \theta_{1500}) \times 1000$$
where $c = \frac{Clay\%}{100}$ and $s = \frac{Sand\%}{100}$.

USDA Soil Texture is classified using hierarchical thresholds:
$$\text{Texture} = \begin{cases}
\text{Clay} & \text{if } clay \ge 40\% \\
\text{Silty Clay} & \text{if } clay \ge 40\% \text{ and } silt \ge 40\% \\
\text{Sandy Clay} & \text{if } clay \ge 35\% \text{ and } sand \ge 45\% \\
\text{Loam} & \text{if } 7\% \le clay < 27\%, 28\% \le silt < 50\%, sand \le 52\% \\
\text{Sand} & \text{if } clay < 10\%, silt < 15\%, sand \ge 85\%
\end{cases}$$

### E. Hydrological Resilience & Drought Memory
Precipitation Use Efficiency (PUE) is quantified over 30-day windows:
$$PUE = \frac{NDVI_{end} - NDVI_{start}}{\sum Rain_{mm}}$$
Water Stress Memory Degradation ($\Delta_{degrade}$) represents the loss of plant recovery capability across successive drought drydown events:
$$\Delta_{degrade} = \left(\frac{NDVI_{post, last}}{NDVI_{pre, last}} - \frac{NDVI_{post, first}}{NDVI_{pre, first}}\right) \times 100$$
Drought Recovery Time ($\tau_{recovery}$) measures the number of days required for the canopy to return to $90\%$ of its pre-drought peak.

### F. Microclimate & Decoupling Indices
Microclimate Divergence ($Residual$) measures localized crop behavior relative to weather-driven expectations:
$$Residual_{NDVI} = NDVI_{observed} - NDVI_{simulated}$$
The Atmospheric Decoupling Index ($Index_{decouple}$) evaluates the plant's buffering capacity during high evaporative demands ($ET_0 > 5.0\text{ mm/day}$):
$$Index_{decouple} = \frac{\sum \text{High } ET_0 \text{ days with stable } NDVI}{\text{Total High } ET_0 \text{ days}}$$

### G. Plot DNA Parameter Overrides & Noise Inflation
Using persisting sequenced DNA traits, crop parameters and Kalman process noise are dynamically adjusted. The noise inflation factor ($Factor_{inflation}$) accounts for telemetry gaps and missing historical records:
$$Factor_{inflation} = \min\left(3.0, \max\left(1.0, \left(1.0 + \frac{Null\%_{weather}}{50.0}\right) \times \left(1.0 + \frac{\max(0, 30 - Obs_{ndvi})}{30.0}\right)\right)\right)$$

Persistent DNA overrides are mapped onto ProcessModel crop variables:
$$WHC_{effective} = WHC_{default} \times \max(0.3, \theta_{retention})$$
$$T_{max, effective} = T_{max, default} - \beta_{resilience}$$
$$GrowthRate_{effective} = GrowthRate_{default} \times \max(0.5, \alpha_{vigor})$$
$$GDD_{veg} = GDD_{veg, default} + T_{shift}$$

### H. Adaptive Logistic Canopy Growth
Leaf Area Index (LAI) growth is driven by thermal time, restricted by moisture deficits, developmental stages, and a ceiling scaling factor:
$$Growth_{LAI} = r_{LAI} \times \Delta GDD \times (1 - \text{Stress}_{water} \times 0.5) \times \text{Mod}_{stage} \times \left(1 - \left(\frac{\text{LAI}}{\text{LAI}_{max}}\right)^2\right)$$
where $r_{LAI}$ is the growth rate, and $\text{Mod}_{stage}$ represents establishment limits.

### I. Dual-Layer Soil Infiltration & Evapotranspiration
Soil moisture is modeled across two distinct hydrological layers:

$$\text{TopLayer}_{VWC}(t) = \text{TopLayer}_{VWC}(t-1) + \frac{\text{Rain} + \text{Irrigation} - 0.6 \cdot ET_{crop} - \text{Percolation}}{\text{WHC}_{top}}$$

$$\text{RootLayer}_{VWC}(t) = \text{RootLayer}_{VWC}(t-1) + \frac{\text{Percolation} - 0.4 \cdot ET_{crop} - \text{Drainage}}{\text{WHC}_{root}}$$

Percolation represents gravitational drainage that occurs once the surface layer capacity is exceeded:
$$\text{Percolation} = \max\left(0, \text{TopLayer}_{VWC} \cdot \text{WHC}_{top} - \text{WHC}_{top}\right)$$
$$\text{Drainage} = \max\left(0, \text{RootLayer}_{VWC} \cdot \text{WHC}_{root} - \text{WHC}_{root}\right)$$
where $\text{WHC}_{top} = \text{WHC}_{base} \times 0.1\text{m}$ and $\text{WHC}_{root} = \text{WHC}_{base} \times 0.3\text{m}$.

### J. Photosynthetic Efficiency Dynamics
The active photosynthetic efficiency ($\epsilon_{photo}$) decays when thermal or moisture stress bounds are exceeded and recovers slowly when stress conditions resolve:
$$\epsilon_{photo}(t) = \begin{cases}
0.6 \cdot \epsilon_{photo}(t-1) + 0.4 \cdot (1 - \text{Pressure}_{shutdown}) & \text{if } \text{Pressure}_{shutdown} > 0.1 \\
0.9 \cdot \epsilon_{photo}(t-1) + 0.1 \cdot \left(0.9 + 0.1 \cdot (1 - \text{Stress}_{water})\right) & \text{otherwise}
\end{cases}$$
where:
$$\text{Pressure}_{shutdown} = \min\left(1.0, \frac{\max(0, \text{Stress}_{thermal} - 0.3)}{0.7} + \frac{\max(0, \text{Stress}_{water} - 0.4)}{0.6}\right)$$

### K. Online ML Recalibration
When remote observations correct the latent Leaf Area Index, the EKF updates the process model's growth rate using an exponential moving average (EMA):
$$\text{LAI}_{error} = \text{LAI}_{post} - \text{LAI}_{pre}$$
$$\text{EMA}_{error}(t) = \alpha \cdot \frac{\text{LAI}_{error}}{\text{LAI}_{pre}} + (1 - \alpha) \cdot \text{EMA}_{error}(t-1)$$
$$\text{Rate}_{new} = r_{LAI} \times \left(1.0 + \max\left(-0.5, \min\left(0.5, 2.0 \cdot \text{EMA}_{error}\right)\right)\right)$$
where $\alpha = 0.3$, and $\text{Rate}_{new}$ is constrained within $[0.002, 0.015]$.

### L. Extended Kalman Filter (EKF) Matrix Loop

#### 1. Prediction Equations
$$\hat{x}_{t|t-1} = f(\hat{x}_{t-1|t-1}, u_t)$$
$$P_{t|t-1} = F_t P_{t-1|t-1} F_t^T + Q_t$$
where $Q_t$ represents the diagonal process noise matrix:
$$Q_t = \text{diag}[0.04, 0.02, 0.03, 0.02, 0.03, 1.0, 0.02, 0.02, 0.03]$$

#### 2. Correction Equations (Joseph Form Covariance Update)
For each available scalar observation $y_t$:
$$S_t = H_t P_{t|t-1} H_t^T + R_{effective}$$
$$K_t = P_{t|t-1} H_t^T S_t^{-1}$$
$$\hat{x}_{t|t} = \hat{x}_{t|t-1} + K_t \left(y_t - h(\hat{x}_{t|t-1})\right)$$
$$P_{t|t} = (I - K_t H_t) P_{t|t-1} (I - K_t H_t)^T + K_t R_{effective} K_t^T$$
where:
* $H_t = \frac{\partial h}{\partial x}$ is the Jacobian vector of the measurement model.
* $R_{effective} = \frac{\sigma^2}{w_t}$ represents the observation noise variance scaled by the ValidationGraph reliability weight ($w_t$).

---

## 5. Biophysical Observation Models ($y_obs = h(x)$)

### A. Sentinel-2 NDVI
$$\text{NDVI} = \text{NDVI}_{soil} + (\text{NDVI}_{max} - \text{NDVI}_{soil}) \times \left(1 - e^{-k_{ext} \cdot \text{LAI}}\right)$$
$$\frac{\partial \text{NDVI}}{\partial \text{LAI}} = (\text{NDVI}_{max} - \text{NDVI}_{soil}) \times k_{ext} \times e^{-k_{ext} \cdot \text{LAI}}$$
where $\text{NDVI}_{soil} = 0.15$, $\text{NDVI}_{max} = 0.90$, and $k_{ext} = 0.50$. Base instrument uncertainty $\sigma = 0.02$.

### B. Sentinel-2 EVI
$$\text{EVI} = \text{EVI}_{soil} + (\text{EVI}_{max} - \text{EVI}_{soil}) \times \left(1 - e^{-k \cdot \text{LAI}}\right)$$
$$\frac{\partial \text{EVI}}{\partial \text{LAI}} = (\text{EVI}_{max} - \text{EVI}_{soil}) \times k \times e^{-k \cdot \text{LAI}}$$
where $\text{EVI}_{soil} = 0.10$, $\text{EVI}_{max} = 0.85$, and $k = 0.40$. Base instrument uncertainty $\sigma = 0.03$.

### C. Sentinel-2 NDMI
$$\text{NDMI} = \text{Base}_{ndmi} \times (1 - \text{Stress}_{canopy} \times 0.6) \times \min\left(1.0, \frac{\text{LAI}}{3.0}\right)$$
where $\text{Base}_{ndmi} = 0.40$. Base instrument uncertainty $\sigma = 0.04$.

### D. Sentinel-1 SAR VV
$$\text{VV(dB)} = \text{VV}_{dry} + \text{Sensitivity}_{soil} \times \text{SM}_{0\_10} + \text{Atten}_{veg} \times \text{LAI}$$
where $\text{VV}_{dry} = -18.0\text{ dB}$, $\text{Sensitivity}_{soil} = 10.0\text{ dB/unit}$, and $\text{Atten}_{veg} = -0.3\text{ dB/unit}$. Base instrument uncertainty $\sigma = 1.50\text{ dB}$.

### E. Sentinel-1 SAR VH
$$\text{VH(dB)} = \text{VH}_{base} + \text{Sensitivity}_{biomass} \times \text{Biomass} + \text{Contrib}_{moisture} \times \text{SM}_{0\_10}$$
where $\text{VH}_{base} = -22.0\text{ dB}$, $\text{Sensitivity}_{biomass} = 3.0\text{ dB/unit}$, and $\text{Contrib}_{moisture} = 2.0\text{ dB/unit}$. Base instrument uncertainty $\sigma = 2.00\text{ dB}$.

### F. Sentinel-5P Solar-Induced Fluorescence (SIF)
$$\text{SIF} = \text{SIF}_{max} \times \epsilon_{photo} \times \left(1 - e^{-k_{lai} \cdot \text{LAI}}\right)$$
where $\text{SIF}_{max} = 2.00$ and $k_{lai} = 0.50$. Base instrument uncertainty $\sigma = 0.15$.

### G. Sentinel-2 Photochemical Reflectance Index (PRI)
$$\text{PRI} = \left(\text{PRI}_{stressed} + \left(\text{PRI}_{healthy} - \text{PRI}_{stressed}\right) \times \epsilon_{photo}\right) \times \min\left(1.0, \frac{\text{LAI}}{3.0}\right)$$
where $\text{PRI}_{stressed} = -0.05$ and $\text{PRI}_{healthy} = 0.02$. Base instrument uncertainty $\sigma = 0.08$.

### H. In-Situ Soil Probe Overlap
$$\text{SM}_{probe} = w_{top} \cdot \text{SM}_{0\_10} + (1 - w_{top}) \cdot \text{SM}_{10\_40}$$
where:
$$w_{top} = \max\left(0, 1.0 - \frac{\text{Depth}_{cm} - 10}{30}\right)$$
Base instrument uncertainty $\sigma = 0.03$.

---

## 6. Scientific References

* **Kalman, R. E. (1960)**. *A New Approach to Linear Filtering and Prediction Problems*. Journal of Basic Engineering, 82(1), 35-45.
* **Saxton, K. E., & Rawls, W. J. (2006)**. *Soil Water Characteristic Estimates by Texture and Organic Matter for Hydrologic Solutions*. Soil Science Society of America Journal, 70(5), 1569-1578.
* **Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998)**. *Crop Evapotranspiration: Guidelines for Computing Crop Water Requirements*. FAO Irrigation and Drainage Paper 56, Rome.
* **Gelb, A. (Ed.). (1974)**. *Applied Optimal Estimation*. MIT Press, Cambridge, MA. (Theoretical basis for the numerically stable Joseph Form Covariance Update).
* **Ritchie, J. T. (1998)**. *Development of Soil Water Models in CERES Crops*. In *Understanding Options for Agricultural Production* (pp. 115-130). Springer, Dordrecht.
* **Baret, F., & Guyot, G. (1991)**. *Potentials and Limits of Vegetation Indices for LAI and APAR Estimation*. Remote Sensing of Environment, 35(2-3), 161-173.
* **Ulaby, F. T., Dubois, P. C., & van Zyl, J. (1996)**. *Radar Mapping of Soil Moisture*. In *Proceedings of IGARSS '96*.
* **Meroni, M., Rossini, M., Guanter, L., Alonzo, R., Cogliati, S., Colombo, R., ... & Verhoef, W. (2009)**. *Remote Sensing of Solar-Induced Chlorophyll Fluorescence: Review of Methods and Applications*. Biogeosciences, 6(6), 999-1013.
* **Gamon, J. A., Peñuelas, J., & Field, C. B. (1992)**. *A Narrow-Band Spectral Index that Tracks Photosynthetic Light-Use Efficiency for Consistent Semiarid Canopies*. Remote Sensing of Environment, 41(1), 35-44.
