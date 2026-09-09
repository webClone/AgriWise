# Layer 1: Multi-Source Data Fusion & Spatio-Temporal Alignment

## 1. Executive Summary & Architectural Mission

**Layer 1 (Fusion)** is the central context synthesis, spatio-temporal alignment, and physical evidence aggregation hub of the AgriBrain architecture. It ingests normalized telemetry and raster packages from Layer 0 (and micro-zone outputs from Layer 0.5 ASMAE), resolving observational conflicts, validating physical units, aligning irregular time series, and fusing multi-scale measurements into a deterministic, un-hallucinated **`Layer1ContextPackage`**.

### Fundamental Separation of Concerns:
- **Layer 1 describes CONTEXT:** *"What the sensors observe, when, with what confidence, and where."*
  - Example: `NDVI=0.28, chlorophyll_index=0.15, soil_moisture_vwc=0.12, confidence=0.78`
- **Layer 2+ performs DIAGNOSIS:** *"What those physical observations mean agronomically."*
  - Example: `Nitrogen deficiency likely (72% probability), root-zone water stress`
- **Layer 1 Never Prescribes or Diagnoses:** It is strictly prohibited from emitting diagnostic terms (e.g. *"disease"*, *"deficiency"*) or prescriptions (e.g. *"irrigate now"*).
- **Layer 1 Never Performs Live Data Fetching:** It receives pre-assembled input bundles from the orchestrator and data gateway.

---

## 2. Directory & Component Inventory (60 Modules)

```
services/agribrain/layer1_fusion/
├── __init__.py                     # Package export and initialization
├── engine.py                       # Layer1FusionEngine: 21-step deterministic fusion pipeline
├── schemas.py                      # Layer1InputBundle, Layer1ContextPackage, EvidenceItem, FusedFeatureSet
├── schema.py                       # Legacy FieldTensor contract export
├── runner.py                       # Standard entry point run_layer1_fusion() and orchestrator interface
├── conflict_resolver.py            # Detects 10 canonical conflict types with Bayesian credibility weighting
├── freshness.py                    # Piecewise linear decay curves for observation aging
├── zone_engine.py                  # Management zone clustering (quantiles on temporal S2/SAR medians)
├── spatial_alignment.py            # Preserves spatial scopes (plot, zone, point, edge, raster)
├── temporal_alignment.py           # Window assignment and chronological ordering
├── fusion_rules.py                 # 4-part key grouping and weighted average aggregation
├── context_invariants.py           # Runtime invariant validation (bounds, non-finite checks, provenance)
├── eo_foundation_model.py          # Learned spectral embeddings & USGS spectral library basis projection
├── evidence_ledger.py              # Deduplication, quarantine, and audit trail for evidence items
├── evidence_validation.py          # Strict checking of units, values, and coordinate scopes
├── gap_analyzer.py                 # Detects missing sensor/satellite streams across analysis window
├── raster_backend.py               # TileStore and Rasterio backends for spatial composite handling
├── raster_ingest.py                # Adopts raster references without premature pixel degradation
├── truth_bridge.py                 # Bridges spatial truth classifications with pixel arrays
├── unit_registry.py                # Canonical ASCII units registry
├── confidence_model.py             # Min-reduction confidence calculation with conflict penalties
├── corrections.py                  # Sensor bias and drift correction utilities
├── diagnostics.py                  # Diagnostics aggregator and data health scoring
├── source_family.py                # Source family enumerations and hierarchy
├── source_registry.py              # Registry of source adapters and evidence extractors
│
├── adapters/                       # Source-specific evidence extractors
│   ├── sentinel2.py                # S2 bands, NDVI, NDMI, NDRE, EVI, SCL cloud masks
│   ├── sentinel1.py                # SAR VV, VH, VV/VH ratio, radar wetness proxies
│   ├── sentinel5p.py               # TROPOMI SIF and atmospheric column density
│   ├── environment.py              # Weather reanalysis (ERA5/Open-Meteo) and soil priors
│   ├── weather_forecast.py         # 7-day forecast extraction (marked as forecast/model_estimate)
│   ├── geo_context.py              # DEM, slope, aspect, ESA WorldCover, WaPOR context
│   ├── sensors.py                  # In-situ soil capacitance, weather station, IoT telemetry
│   ├── user_events.py              # Sowing, spraying, irrigation, tillage event logs
│   ├── drone.py                    # Drone orthomosaic structural features & SfM elevation
│   ├── perception.py               # Proximal RGB camera & smartphone scouting evidence
│   ├── asmae_adapter.py            # ASMAE downscaled micro-zone state raster ingestion
│   ├── l0_state.py                 # Layer 0 Kalman state vector handoff
│   ├── layer0_source_package.py    # Raw Layer 0 SourcePackage adapter
│   └── microzone.py                # Microzone spatial feature adapter
│
├── outputs/                        # Downstream contract adapters
│   ├── layer2_adapter.py           # Builds Layer2InputContext payload
│   ├── layer10_adapter.py          # Builds Layer10 spatial publication payload
│   └── legacy_compat.py            # Builds legacy FieldTensor for backward compatibility
│
├── validation/                     # Static contract validation utilities
│   └── contract_validator.py       # Validates output package against CONTRACT.md
│
└── tests/                          # Layer 1 unit and integration tests
    ├── __init__.py
    ├── test_fusion_pipeline.py     # End-to-end 21-step pipeline & determinism test
    ├── test_conflict_resolver.py   # 10 canonical conflict types & Bayesian credibility
    ├── test_freshness_scoring.py   # Piecewise linear decay curves per source family
    ├── test_zone_engine.py         # Management zone quantile clustering & fallback
    ├── test_spatial_alignment.py   # Scope preservation & spatial index generation
    ├── test_context_invariants.py  # Runtime safety & physical invariant enforcement
    └── test_legacy_fieldtensor_compat.py # FieldTensor generation & Layer 2 compatibility
```

---

## 3. The 21-Step Deterministic Fusion Pipeline

When `Layer1FusionEngine.fuse(bundle)` is invoked:

```
[1. Validate Input Bundle] ──► [2. Build Source Envelopes] ──► [3. Run Adapters (EvidenceItems)]
            │
            ▼
[4. Validate Units/Scopes/Provenance] ──► [5. Quarantine Invalid Evidence] ──► [6. Build EvidenceLedger]
            │
            ▼
[7. Temporal Alignment] ──► [8. Spatial Alignment & Scopes] ──► [8.5 Raster Ingestion]
            │
            ▼
[8.6 EO Foundation Embedding] ──► [8.7 Zone Segmentation] ──► [9. Compute Freshness Scores]
            │
            ▼
[10. Run Conflict Resolver] ──► [11. Run Gap Analyzer] ──► [12. Apply Confidence Model]
            │
            ▼
[13. Run Fusion Rules] ──► [14. Build Fused Feature Groups] ──► [15. Build Layer 2 Context]
            │
            ▼
[16. Build Layer 10 Payload] ──► [17. Computed Prohibitions] ──► [17.5 Enforce Context Invariants]
            │
            ▼
[18. Record Audit Log] ──► [19. Return Layer1ContextPackage]
```

---

## 4. Key Mathematical Formulations

### A. 4-Part Grouping Key for Feature Aggregation
Evidence items are grouped into fused features strictly by their 4-part tuple:
$$\text{Key} = (\text{variable}, \ \text{spatial\_scope}, \ \text{scope\_id}, \ \text{temporal\_scope})$$
Items with different spatial scopes (e.g. `point` vs. `plot`) or different temporal scopes are **never collapsed or blended together**.

### B. Weighted Average Aggregation
When $N$ evidence items share the identical grouping key:
$$\bar{v} = \frac{\sum_{i=1}^N w_i \cdot v_i}{\sum_{i=1}^N w_i} \quad \text{where } w_i = \text{confidence}_i \times \text{reliability}_i$$

- **Fused Confidence:** $\text{Conf}_{\text{fused}} = \min\left(0.95, \ \max_{i} \text{confidence}_i\right)$
- **Fused Freshness:** $\bar{F} = \frac{1}{N} \sum_{i=1}^N \text{freshness}_i$
- **Source Contribution Attribution:**
  $$W_{\text{family}} = \sum_{i \in \text{family}} w_i$$

### C. Bayesian Credibility-Weighted Conflict Resolution
Credibility $C(e)$ of an evidence item $e$ combines observation freshness $F(e)$ and source reliability $R(e)$:
$$C(e) = F(e) \times R(e)$$

When two sources $a$ and $b$ disagree on variable $x$:
- **Severity Classification:**
  - $\mathbf{major}$: $|v_a - v_b| > 2 \cdot \theta_{\text{threshold}} \quad \text{AND} \quad \frac{C(a) + C(b)}{2} > 0.6$
  - $\mathbf{moderate}$: $|v_a - v_b| > 1.5 \cdot \theta_{\text{threshold}} \quad \text{AND} \quad \frac{C(a) + C(b)}{2} > 0.4$
  - $\mathbf{minor}$: otherwise
- **Bayesian Confidence Penalty:**
  $$\text{Penalty} = 1.0 - \frac{\text{conf}_a \times \text{conf}_b}{\max(\text{conf}_a, \text{conf}_b)}$$
- **Zero Suppression Guarantee:** Every candidate conflict detected is emitted in the package. Suppressed conflicts are strictly 0.

### D. Piecewise Linear Freshness Decay
Observation age $\Delta t = t_{\text{run}} - t_{\text{obs}}$ decays according to source-specific curves:

| Source Family | Freshness $> 0.8$ | Freshness $> 0.5$ | Stale Cutoff ($< 0.2$) | Notes |
| :--- | :---: | :---: | :---: | :--- |
| **In-Situ Sensors** | $\le 24\text{ h}$ | $\le 72\text{ h}$ | $> 720\text{ h}$ | Rapid decay for dynamic soil moisture |
| **Sentinel-2 Optical** | $\le 5\text{ days}$ | $\le 15\text{ days}$ | $> 30\text{ days}$ | Reflects phenological dynamics |
| **Sentinel-1 SAR** | $\le 6\text{ days}$ | $\le 12\text{ days}$ | $> 24\text{ days}$ | 6–12 day satellite orbit revisit |
| **Weather Forecast** | $\text{Day } 0\text{--}1$ | $\text{Day } 3$ | $\ge \text{Day } 6$ | Rapid forecast uncertainty expansion |
| **SoilGrids / DEM** | Infinite | Infinite | Never | Static pedological & topographic priors |

### E. Confidence Min-Reduction Formula
Fused feature confidence represents the conservative lower bound of evidence quality:
$$\text{Conf}_{\text{final}} = \min\left(\text{Conf}_{\text{fused}}, \ \text{Score}_{\text{QA}}, \ \bar{F}, \ \text{Ceiling}_{\text{role}}, \ (1.0 - \text{Penalty}_{\text{conflict}})\right)$$

---

## 5. The 13 Hard Invariant Prohibitions

Layer 1 computes and enforces 13 hard safety prohibitions during every execution. A violation causes gate rejection:

| # | Prohibition | Failure Condition & Detection Logic |
| :---: | :--- | :--- |
| **1** | `no_fake_fallback_evidence` | Any evidence item has empty `provenance_ref`. |
| **2** | `no_diagnosis_or_recommendation` | Fused feature names/values contain forbidden diagnostic vocabulary (e.g. "nitrogen deficiency", "blight", "irrigate now"). |
| **3** | `no_forecast_as_observation` | Weather forecast evidence is labeled as direct physical measurement instead of `forecast` or `model_estimate`. |
| **4** | `no_point_sensor_to_plot_truth_without_scope` | Point capacitance probe evidence is directly attributed as plot-wide truth without explicit spatial zone mapping. |
| **5** | `no_geo_context_as_crop_state` | Topographic/soil maps (DEM, WorldCover) are interpreted as dynamic crop states. |
| **6** | `no_weather_as_crop_diagnosis` | Weather data asserts disease pathology diagnoses directly. |
| **7** | `no_wapor_as_plot_truth` | Coarse 100m WaPOR water productivity is treated as ground plot truth without diagnostic marking. |
| **8** | `no_unprovenanced_fused_feature` | A fused feature exists with empty `source_evidence_ids`. |
| **9** | `no_conflict_suppression` | Detected observational discrepancies are silently masked or deleted. |
| **10** | `no_unit_mismatch_allowed` | Non-canonical or inconsistent units are ingested without normalization. |
| **11** | `no_spatial_scope_collapse` | Zone-level or point-level measurements are averaged into plot-level state features. |
| **12** | `no_temporal_leakage_future_to_present` | Future forecast data leaks into historical/current observation features. |
| **13** | `no_simulated_data_in_user_facing_context` | Synthetic or simulated data is passed without clear `SIMULATED` provenance tagging. |

---

## 6. The 7 Canonical Fused Feature Groups

1. **`water_context`**: Volumetric soil moisture, rain accumulation, irrigation depth, ET0, field capacity, water holding capacity.
2. **`vegetation_context`**: NDVI, NDMI, NDRE, EVI, Leaf Area Index (LAI), foliar chlorophyll, Bare Soil Index (BSI).
3. **`phenology_context`**: Growing Degree Days (GDD), phenological stage progression, sowing date, estimated harvest window.
4. **`stress_evidence_context`**: Thermal stress hours, canopy temperature depression, drought indices, Vapor Pressure Deficit (VPD).
5. **`soil_site_context`**: Soil texture fractions (clay/sand/silt), organic carbon, pH, elevation, slope, aspect.
6. **`operational_context`**: User management events (tillage, fertilizer application, spraying), sensor maintenance status.
7. **`data_quality_context`**: Overall source completeness, mean freshness score, active conflict count.

---

## 7. Verification & Test Suite

The test suite for Layer 1 is located in [`services/agribrain/layer1_fusion/tests/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/tests/):

```powershell
py -3 -m pytest services/agribrain/layer1_fusion/tests/ -v
```

### Test Coverage Summary:
- **`test_fusion_pipeline.py`**: Validates the 21-step deterministic fusion pipeline, input bundle validation, evidence ledger creation, 7 feature groups, determinism of `content_hash()`, and 13 hard prohibition tests.
- **`test_conflict_resolver.py`**: Validates detection of canonical conflict types (sensor vs SAR moisture, forecast vs observed weather, S2 vs sensor greenness), Bayesian credibility weighting, and zero conflict suppression.
- **`test_freshness_scoring.py`**: Validates source-specific piecewise linear decay curves across sensors, satellite radiometry, weather forecasts, and static pedological priors.
- **`test_zone_engine.py`**: Validates management zone quantile clustering, handling of cloudy/NaN scenes, and single-zone fallback.
- **`test_spatial_alignment.py`**: Validates spatial index generation, strict scope preservation (point, zone, edge, raster, plot), and raster geographic authority.
- **`test_context_invariants.py`**: Validates runtime physical boundaries (NDVI in [-1, 1], moisture in [0, 1]), non-finite value screening, and provenance completeness.
- **`test_legacy_fieldtensor_compat.py`**: Validates legacy `FieldTensor` generation from `Layer1ContextPackage` to guarantee seamless compatibility with downstream Layer 2 pipelines.
