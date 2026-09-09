# Layer 0: Sensory Ingestion, Multi-Source QA & Extended Kalman Assimilation

## 1. Executive Summary & Architectural Role
**Layer 0** is the sensory foundation, telemetry ingestion gateway, and physical state assimilation engine of AgriBrain. It acts as the immutable physical boundary between raw, noisy, heterogeneous real-world observations and the downstream diagnostic, hydrological, and agronomic intelligence layers (L1–L10).

### Core Responsibilities:
1. **Heterogeneous Telemetry Ingestion:** Ingests satellite constellations (Sentinel-2 multispectral, Sentinel-1 SAR radar, Sentinel-5P atmospheric), in-situ agricultural IoT stations (multi-depth soil moisture probes, weather stations), proximal imaging (drone orthomosaics, smartphone scouting photos, fixed IP cameras), and manual farmer records.
2. **Spatial Georeferencing & UTM Gridding:** Projects geographic coordinates (WGS84 ellipsoids) into local UTM metric grids with sub-meter numerical precision, calculating boundary alpha masks to prevent field edge spectral contamination.
3. **Multi-Source Quality Assessment (QA):** Automatically screens observations for cloud shadows, aerosol optical depth, SAR speckle, sensor flatlining/drift, camera blur, and farmer typo anomalies, dynamically inflating observation uncertainty matrices ($R$).
4. **Cross-Source Physical Validation:** Employs a bipartite validation graph to evaluate physical consistency across independent measurement streams (e.g. soil wetness spikes vs. rainfall reanalysis, camera canopy greenness vs. satellite NDVI).
5. **Latent State Assimilation (9-State EKF):** Inverts and assimilates multi-sensor observations into a continuous, 9-dimensional latent biophysical state vector using an Extended Kalman Filter with Joseph-form covariance updates.

---

## 2. Directory & Component Inventory (260 Python Modules)

```
services/agribrain/layer0/
├── __init__.py                     # Package export and initialization
├── runner.py                       # Layer0Runner, Layer0RunnerInput, Layer0RunnerOutput
├── observation_packet.py           # Canonical ObservationPacket, ObservationHeader, Variable
├── observation_model.py            # Observation Jacobian matrix H and forward h(x) operators
├── kalman_engine.py                # DailyAssimilationEngine, ZoneKalmanFilter (9x9 EKF)
├── state_vector.py                 # StateVector (9 latent state variables)
├── state_engine.py                 # Multi-zone state transition and historical tracking
├── state_persistence.py            # SQLite / JSON serialization and state restoration
├── invariants.py                   # Runtime physical invariants (NDVI in [-1, 1], VWC in [0, 1])
├── plot_grid.py                    # UTM transverse Mercator projection & pixel grid manager
├── weakness_raster.py              # Spatial weakness clustering & initial zone segmentation
├── source_qa.py                    # Sensor, satellite, weather, and soil QA scoring
├── image_qa.py                     # Smartphone/drone image quality filtering (blur, exposure)
├── validation_graph.py             # Cross-source physical consistency validation engine
├── wrappers.py                     # Handoff converters for Orchestrator V2 and L1 Fusion
├── temporal_evidence.py            # Immutable chronological ordering of evidence streams
├── user_input_adapter.py           # Farmer management event ingestion & normalization
├── user_input_schema.py            # Typed schemas for sowing, spraying, irrigation, tillage
│
├── asmae_scene_products/           # Product binding & orbit metadata validation (S1/S2)
│   ├── product_binding.py          # Cryptographic scene product verification
│   └── s1_real_scene_product_fetcher.py # Orbit state vectors and slice timing
│
├── calibration/                    # Offline parameter inversion & plot DNA traits
│   ├── generative_inversion.py     # 10-year S2 cube inversion via Differential Evolution
│   ├── monte_carlo_engine.py       # Parameter sensitivity simulation across multiverse
│   ├── microclimate_spac.py        # Microclimatic decoupling isolation (ERA5 vs NDVI)
│   ├── hydrological_resilience.py  # Precipitation-NDVI recovery time correlation
│   └── dna_cache.py                # Crop variety traits & baseline process noise scaling
│
├── data_gateway/                   # Internal caching, fetch registry & request broker
│   ├── request_broker.py           # Centralized raster & telemetry broker
│   ├── fetch_registry.py           # Provider fetch functions (SentinelHub, Open-Meteo, etc.)
│   └── authority_check.py          # Data authority & integrity verification
│
├── environment/                    # Meteorological & static pedological context
│   ├── engine.py                   # EnvironmentalEngine: weather reanalysis fusion
│   ├── state_adapter.py            # Weather-to-EKF forcing adapter
│   ├── fao/                        # FAO global soil database extraction
│   ├── soilgrids/                  # ISRIC SoilGrids 250m profile extraction (clay, sand, SOC)
│   └── weather/                    # Multi-provider consensus (ERA5, Open-Meteo, MeteoBlue)
│
├── geo_context/                    # Topographic & land-cover priors
│   ├── engine.py                   # Fuses DEM, WorldCover fractions, and slope/aspect
│   ├── sensor_placement.py         # Optimal IoT probe placement recommendation
│   ├── dem/                        # NASA SRTM / Copernicus 30m elevation models
│   ├── landcover/                  # ESA WorldCover 10m cropland classification
│   └── wapor/                      # FAO WaPOR actual evapotranspiration context
│
├── learning/                       # Online ML growth rate tuning & parameter adaptation
│   ├── growth_rate_tuner.py        # Online gradient descent on EKF growth transitions
│   └── parameter_bank.py           # Dynamic storage of calibrated process parameters
│
├── perception/                     # Computer vision & proximal imaging pipelines
│   ├── common/                     # Shared feature extractors, color constancy, plant masks
│   ├── drone_rgb/                  # Orthomosaic tiling, canopy height modeling (SfM)
│   ├── farmer_photo/               # Foliar disease crop lesion detector & phenology classifier
│   ├── ip_camera/                  # Fixed camera diurnal timelapse & leaf angle tracking
│   └── satellite_rgb/              # True-color and false-color composite raster generation
│
├── sensors/                        # In-situ telemetry & IoT gateway
│   ├── engine.py                   # In-situ point telemetry ingestion
│   ├── qa.py                       # Flatline, out-of-bounds, and high-frequency spike screening
│   ├── irrigation_event_detector.py# Automatic detection of unrecorded watering spikes
│   ├── sensor_satellite_validation.py # Point capacitance probe vs. SAR wetness validation
│   └── sensor_weather_validation.py# Soil infiltration vs. precipitation cross-check
│
├── sentinel1/                      # Sentinel-1 C-Band Synthetic Aperture Radar (SAR)
│   ├── grdh_processor.py           # Radiometric calibration ($\sigma^0$), thermal noise removal
│   ├── speckle_filter.py           # Refined Lee & Gamma-MAP spatial despeckling filters
│   └── dual_pol_indices.py         # $VV, VH$, Radar Vegetation Index (RVI), cross-ratio ($VH/VV$)
│
├── sentinel2/                      # Sentinel-2 MSI Optical Multi-Spectral Radiometry
│   ├── l2a_processor.py            # Surface reflectance processing ($B_2 \dots B_{12}$)
│   ├── cloud_mask.py               # Scene Classification Layer (SCL) & Cirrus cloud masking
│   └── spectral_indices.py         # NDVI, NDRE, EVI, NDWI, NDMI, SAVI, Chlorophyll Index
│
└── sentinel5p/                     # Sentinel-5P TROPOMI Atmospheric Chemistry
    ├── no2_processor.py            # Tropospheric Nitrogen Dioxide column density
    └── ch4_co_processor.py         # Methane and Carbon Monoxide atmospheric background
```

---

## 3. Mathematical Formulations

### A. Extended Kalman Filter (EKF) Assimilation Loop
Layer 0 maintains a continuous 9-state biophysical vector per field zone:
$$\mathbf{x}_t = \begin{bmatrix} \text{LAI} & \text{Biomass} & \text{SM}_{0-10} & \text{SM}_{10-40} & \text{CanopyStress} & \text{GDD} & \text{PhenoStage} & \text{ThermalStress} & \text{PhotoEff} \end{bmatrix}^T$$

#### 1. Prediction Step (Nonlinear Process Transition):
$$\hat{\mathbf{x}}_{t|t-1} = f(\hat{\mathbf{x}}_{t-1|t-1}, \mathbf{u}_t)$$
$$\mathbf{P}_{t|t-1} = \mathbf{F}_t \mathbf{P}_{t-1|t-1} \mathbf{F}_t^T + \mathbf{Q}_t$$
Where:
- $\mathbf{u}_t$ is the daily meteorological forcing vector (temperature, solar radiation, precipitation, $ET_0$).
- $\mathbf{F}_t = \left. \frac{\partial f}{\partial \mathbf{x}} \right|_{\hat{\mathbf{x}}_{t-1|t-1}}$ is the linearized process Jacobian.
- $\mathbf{Q}_t = \text{diag}\left[ \sigma_{\text{LAI}}^2, \sigma_{\text{Bio}}^2, \sigma_{\text{SM1}}^2, \sigma_{\text{SM2}}^2, \sigma_{\text{Stress}}^2, \sigma_{\text{GDD}}^2, \sigma_{\text{Stage}}^2, \sigma_{\text{Therm}}^2, \sigma_{\text{Photo}}^2 \right]$ is the process noise covariance matrix.

#### 2. Correction Step with Joseph-Form Covariance Stabilization:
When an observation packet arrives with measurement vector $\mathbf{y}_t$ and covariance $\mathbf{R}_t$:
$$\mathbf{y}_{\text{innov}} = \mathbf{y}_t - h(\hat{\mathbf{x}}_{t|t-1})$$
$$\mathbf{S}_t = \mathbf{H}_t \mathbf{P}_{t|t-1} \mathbf{H}_t^T + \mathbf{R}_{\text{effective}}$$
$$\mathbf{K}_t = \mathbf{P}_{t|t-1} \mathbf{H}_t^T \mathbf{S}_t^{-1}$$
$$\hat{\mathbf{x}}_{t|t} = \hat{\mathbf{x}}_{t|t-1} + \mathbf{K}_t \mathbf{y}_{\text{innov}}$$
$$\mathbf{P}_{t|t} = (\mathbf{I} - \mathbf{K}_t \mathbf{H}_t) \mathbf{P}_{t|t-1} (\mathbf{I} - \mathbf{K}_t \mathbf{H}_t)^T + \mathbf{K}_t \mathbf{R}_{\text{effective}} \mathbf{K}_t^T$$
> **Mathematical Note:** The symmetric Joseph-form update guarantees that the state error covariance matrix $\mathbf{P}_{t|t}$ remains strictly positive semi-definite and symmetric even under severe machine precision round-off.

### B. Dynamic Observation Uncertainty Inflation ($\mathbf{R}_{\text{effective}}$)
Observation noise is not static; it is dynamically modulated by the QA screening engines:
$$\mathbf{R}_{\text{effective}} = \mathbf{R}_{\text{nominal}} \times \left(1.0 + \sum_k w_k \cdot \text{Penalty}_k\right)$$
Where penalties include:
- Optical cloud/aerosol contamination ($0 \to 500\%$).
- Sensor battery decay or temperature drift.
- SAR incidence angle deviation from $38^\circ$ nominal.
- Cross-source physical inconsistency detected by the Validation Graph.

### C. Geotransform Projection (WGS84 to Local UTM)
Local Cartesian offsets $(\Delta x, \Delta y)$ in meters from the plot origin $(lat_0, lng_0)$:
$$\Delta y = (lat - lat_0) \times 111,132.0 \text{ meters}$$
$$\Delta x = (lng - lng_0) \times 111,320.0 \times \cos\left(\frac{lat_0 \cdot \pi}{180}\right) \text{ meters}$$

---

## 4. Input & Output Contracts

### Input Contract (`Layer0RunnerInput`):
```python
@dataclass
class Layer0RunnerInput:
    plot_id: str
    polygon: Dict[str, Any]             # GeoJSON Polygon in EPSG:4326
    start_date: str                     # "YYYY-MM-DD"
    end_date: str                       # "YYYY-MM-DD"
    crop_type: str                      # e.g. "POTATO", "WHEAT"
    target_resolution_m: float = 10.0
    enable_cache: bool = True
    manual_events: List[Dict[str, Any]] = field(default_factory=list)
```

### Output Contract (`Layer0RunnerOutput`):
```python
@dataclass
class Layer0RunnerOutput:
    plot_id: str
    grid: PlotGrid                      # UTM coordinates, affine transform, dimensions
    packets: List[ObservationPacket]    # All normalized, QA-scored observation packets
    state_vector: StateVector           # Fused 9-dimensional latent state
    state_covariance: List[List[float]] # 9x9 uncertainty covariance
    validation_report: Dict[str, Any]   # Cross-source physical consistency report
    execution_time_s: float
```

---

## 5. Failure Semantics & Invariant Enforcement
1. **Fail-Closed QA Gates:** Corrupted or invalid rasters (e.g. unprojected coordinates, out-of-bounds sensor spikes) are assigned zero quality scores or rejected via typed receipts, never admitted into the Kalman loop.
2. **Physical State Clamping:** Invariants are strictly enforced at the exit of every prediction and correction step:
   - $0.0 \le \text{LAI} \le 10.0$
   - $0.0 \le \text{Biomass} \le 25.0\text{ t/ha}$
   - $\theta_r \le \text{SM} \le \theta_{\text{sat}}$
   - $0.0 \le \text{CanopyStress} \le 1.0$
3. **No Phantom Water:** Missing weather never triggers zero stress; if observations are absent, the Kalman filter smoothly expands the state covariance $\mathbf{P}$ via $\mathbf{Q}_t$ to reflect growing uncertainty.
