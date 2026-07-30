# Layer 1: Multi-Source Data Fusion and Spatio-Temporal Alignment

This layer forms the central context synthesis and spatio-temporal alignment hub of the AgriWise system. It integrates irregular, multi-scale, and multi-source inputs across our 9-Layer Stack into a unified, aligned, and conflict-resolved state package.

---

## 1. Detailed Engine & Adapter Inventory

This layer contains exactly 14 specialized active engines and adapters, organized by functional responsibility:

### A. Central Processing & Ingestion
1. **Layer1FusionEngine** ([engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/engine.py)): Coordinates the 21-step deterministic sequence. Translates input packages into a unified `Layer1ContextPackage`.
2. **EvidenceLedger** ([evidence_ledger.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/evidence_ledger.py)): Acts as a transactional ledger that validates, registers, and quarantines raw inputs, preventing duplication and enforcing provenance.
3. **SourceRegistry** ([source_registry.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/source_registry.py)): Maintains a lookup table of active source adapters and registers their structural constraints.

### B. Signal Diagnostics & Core Math
4. **ConflictResolver** ([conflict_resolver.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/conflict_resolver.py)): Preserves and monitors evidence discrepancies without suppression. Computes Bayesian credibility-weighted conflict severity across 10 canonical conflict types (including scope mismatch).
5. **Freshness Calculator** ([freshness.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/freshness.py)): Decays source weights dynamically based on piecewise-linear time lag from measurement.
6. **Confidence Model** ([confidence_model.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/confidence_model.py)): Computes final fused feature confidence using min-reduction across source uncertainty, QA reliability, age decay, and active conflict ceilings.
7. **ContextInvariants** ([context_invariants.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/context_invariants.py)): Enforces downstream physical safety limits (e.g., capping NDVI in $[-1.0, 1.0]$) and performs automated context self-healing.
8. **Gap Analyzer** ([gap_analyzer.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/gap_analyzer.py)): Evaluates missing evidence against 13 structural gap rules, determining blocking severity levels.

### C. Geospatial & Neural Engines
9. **RasterBackend** ([raster_backend.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/raster_backend.py)): Ingests geotiff composites, manages CRS projections, and resamples cell grids.
10. **ZonalSegmentationEngine** ([zone_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/zone_engine.py)): Clusters field-level grids (NDVI, SAR) into stable management zones based on temporal medians and percentile quantiles. Includes a pure Python quantile engine for robust fallback.
11. **EOFoundationModel** ([eo_foundation_model.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)): Executes neural embeddings in ONNX mode or projects raw bands onto a physically-grounded spectral basis (F21) utilizing USGS Spectral Library endmembers.
12. **RGBApproximator** ([rgb_approximator.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/rgb_approximator.py)): Generates red-green-blue index proxies (VARI, GLI) when multispectral band details are missing.

### D. Alignment & Downstream Adapters
13. **TemporalReconstruction** ([outputs/temporal_reconstruction.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/outputs/temporal_reconstruction.py)): Rebuilds historical timeseries using linear interpolation and Whittaker-Henderson smoothing curves.
14. **Downstream Payload Adapters**:
    * **Layer2Adapter** ([outputs/layer2_adapter.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/outputs/layer2_adapter.py)): Standardizes and packs vegetation and water features for Layer 2.
    * **Layer10Adapter** ([outputs/layer10_adapter.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/outputs/layer10_adapter.py)): Packs zone segmentations and overlays into GeoJSON features for Layer 10 (SIRE).

---

## 2. Granular 21-Step Pipeline Execution

The pipeline executes a highly structured sequence to guarantee deterministic outcomes:

1. **Validate Input Bundle**: Verifies that the required `plot_id` and `run_id` fields are populated in the incoming `Layer1InputBundle`.
2. **Build Source Envelopes**: Scans active sources in the bundle and creates structural metadata envelopes.
3. **Run Adapters**: Dispatches envelopes to custom source adapters (Sentinel-2, Sentinel-1, sensors, user events, geo-context) to extract normalized `EvidenceItem` structures.
4. **Validate Units/Scopes/Provenance**: Evaluates each evidence item against strict unit, spatial scope, and temporal scope rules.
5. **Quarantine Invalid Evidence**: Automatically relocates faulty or broken evidence into a quarantined partition.
6. **Build EvidenceLedger**: Ingests validated evidence into the ledger, rejecting duplicate IDs and ensuring transactional integrity.
7. **Run Temporal Alignment**: Maps each evidence item to its temporal window relative to the active run timestamp.
8. **Run Spatial Alignment**: Computes spatial indexes and maps point-scope, zone-scope, and plot-scope bounds, integrating upstream Layer 0 Extended Kalman Filter states.
9. **Ingest Raster Composites (Step 8.5)**: Decodes multi-spectral pixel arrays and resamples grids into the temporal-spatial model.
10. **EO Foundation Model Embedding (Step 8.6)**: Runs ONNX ViT inference or F21 spectral projection to generate a 128-dimensional embedding.
11. **Zone Segmentation (Step 8.7)**: Fires if NDVI composites have $\ge 16$ valid pixels; clusters grids into High, Average, and Lagging vigor zones.
12. **Compute Freshness**: Computes decay scores using piecewise-linear age tables.
13. **Run Conflict Resolver**: Evaluates 10 canonical conflict types (such as sensor vs. SAR moisture mismatch or scope mismatch) with zero-suppression proof.
14. **Run Gap Analyzer**: Traces missing telemetry families to flag gaps.
15. **Apply Confidence Model**: Applies a min-reduction formula across instrument ceilings, freshness, QA flags, and active conflict penalties.
16. **Run Fusion Rules**: Maps variables to their explicit agronomic groups.
17. **Build Fused Feature Groups**: Merges values and aggregates sources using weighted average and inverse-variance math.
18. **Build Layer 2 Input Payload**: Adapts fused states into the Downstream Crop Intelligence payload.
19. **Build Layer 10 Spatial Payload**: Translates management zones into GeoJSON MultiPolygon structures.
20. **Enforce Context Invariants (Step 17.5)**: Applies runtime constraints to prevent physical anomalies.
21. **Record Audit Log & Return**: Logs the steps executed (quarantines, conflicts, gaps) and outputs the final `Layer1ContextPackage`.

---

## 3. Data Schemas & Contracts ([schemas.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/schemas.py))

Layer 1 is governed by strict Pydantic/dataclass schemas representing the formal interface contract.

### A. Core Constants
* **Source Families**: `sentinel2`, `sentinel1`, `sentinel5p`, `eo_foundation`, `environment`, `weather_forecast`, `geo_context`, `sensor`, `perception`, `user_event`, `history`, `drone_structural`, `l0_state`, `raster_composite`, `zone_segmentation`.
* **Spatial Scopes**: `plot`, `zone`, `edge`, `point`, `irrigation_block`, `raster`, `farm`.
* **Observation Types**: `measurement`, `model_estimate`, `forecast`, `static_prior`, `derived_feature`, `diagnostic`, `event`, `state_estimate`, `derived`.
* **Canonical Units**: `degC`, `fraction`, `percent`, `mm`, `mm_day`, `m_s`, `kPa`, `dS_m`, `pH`, `kg_ha`, `W_m2`, `umol_m2_s`, `dBm`, `dB`, `m2`, `cm`, `L`, `L_min`, `deg`, `min`, `bar`, `V`, `mm_h`, `ratio`, `score`, `index`, `count`, `bool`, `class`, `linear_power`, `db`.

### B. Core Dataclass Schemas

#### 1. EvidenceItem
*Every measurement, estimate, or event is converted to this atomic unit of Layer 1.*
* `evidence_id` (`str`): Unique identifier (hash of source, timestamp, and variable).
* `plot_id` (`str`): Reference to the physical plot.
* `variable` (`str`): Normalized agronomic variable name.
* `value` (`Any`): Numerical, categorical, or coordinate value.
* `unit` (`str`): Unit restricted to `CANONICAL_UNITS` or `None`.
* `source_family` (`str`): Restricts to `SOURCE_FAMILIES`.
* `source_id` (`str`): Reference to the specific instrument or API.
* `observation_type` (`str`): Restricts to `OBSERVATION_TYPES`.
* `spatial_scope` (`str`): Restricts to `SPATIAL_SCOPES`.
* `scope_id` (`str`): Specific zone key or device ID if non-plot scoped.
* `observed_at` (`datetime`): Measurement acquisition time.
* `confidence` (`float`): Instataneous quality rating $[0.0, 1.0]$.
* `reliability` (`float`): QA-weighted reliability score.
* `freshness_score` (`float`): Age-decayed weight $[0.0, 1.0]$.
* `sigma` (`float`): Raw standard error for inverse-variance weighting.

#### 2. FusedFeature
*The output feature generated from fusing one or more aligned evidence items.*
* `name` (`str`): Agronomic variable name (e.g. `ndvi`).
* `value` (`Any`): Multi-source weighted value.
* `unit` (`str`): Canonical unit.
* `spatial_scope` (`str`): Resolution boundary (`plot`, `zone`, `point`).
* `scope_id` (`str`): Zone key or device ID if applicable.
* `temporal_scope` (`str`): Alignment window (`daily`, `7d`, `static`).
* `confidence` (`float`): Fused source ceiling and QA-constrained confidence.
* `uncertainty` (`float`): Inverse-variance propagated standard error.
* `freshness` (`float`): Average freshness of contributing sources.
* `source_evidence_ids` (`List[str]`): Full audit references to all contributing ledger evidence (no orphan features).
* `source_weights` (`Dict[str, float]`): Normalized fractional weights assigned to contributing source families.

#### 3. DataHealthScore
*Aggregated quality scoring routing downstream.*
* `overall` (`float`): Combined health grade $[0.0, 1.0]$.
* `source_completeness` (`float`): Completeness score across required families.
* `provenance_completeness` (`float`): Provenance chain coverage score.
* `freshness` (`float`): Average timeliness of inputs.
* `spatial_fidelity` (`float`): Spatial polygon intersection coverage.
* `conflict_penalty` (`float`): Reductions applied due to unresolved conflicts.
* `gap_penalty` (`float`): Reductions applied due to blocking data gaps.
* `confidence_ceiling` (`float`): Hard limit applied to downstream confidence based on sensor health.
* `status` (`Literal["ok", "degraded", "unusable"]`): Overall data health flag.

#### 4. SpatialIndex
*Canonical geometry reference that prevents downstream layers from inventing their own coordinates.*
* `plot_id` (`str`): Physical plot ID.
* `zones` (`List[ZoneRef]`): Registered management vigor zones.
* `points` (`List[PointRef]`): IoT and station coordinates with lat/lng placements.
* `edge_regions` (`List[EdgeRegionRef]`): Boundary geometry limits to trace contamination.
* `raster_refs` (`List[RasterRef]`): Ingested spectral and SAR geotiff references.

---

## 4. Agronomic Vocabulary Boundary (Strict Isolation)

To maintain structural isolation between layers, Layer 1 describes **context** (measurements and signals) and is strictly forbidden from performing **diagnosis** or **prescription**. 

Any variable or text violating this boundary is blocked at runtime by the `ContextInvariants` compiler.

```
┌──────────────────────────────────────────────┐
│        LAYER 1: BIOPHYSICAL CONTEXT          │
│  - "NDVI = 0.28"                             │
│  - "Soil Moisture = 12.5%"                   │
│  - "Canopy Temperature = 34.5°C"             │
└──────────────────────┬───────────────────────┘
                       │
             [BOUNDARY GATING LIMIT]
                       │
┌──────────────────────▼───────────────────────┐
│       LAYER 2+: CROP INTEGRATION & DIAG      │
│  - "Nitrogen deficiency detected (92%)"     │
│  - "Severe Water Stress anomaly"             │
│  - "Prescription: Irrigate + Apply Urea"     │
└──────────────────────────────────────────────┘
```

### Forbidden Agronomic Domains & Terms

1. **Nutrient Diagnoses** (*Nutritional crop status is gated to Layer 4*):
   * *Forbidden terms*: `nitrogen deficiency`, `phosphorus deficiency`, `potassium deficiency`, `micronutrient deficit`, `sulfur deficiency`, `zinc deficiency`, `boron toxicity`, `nutrient prescription`.
2. **Pathology Diagnoses** (*Plant disease identification is gated to Layer 5*):
   * *Forbidden terms*: `fungal disease`, `bacterial disease`, `viral disease`, `disease diagnosis`, `blight`, `rust`, `wilt`, `fusarium`, `septoria`, `anthracnose`, `downy mildew`.
3. **Management Prescriptions** (*Irrigation scheduling and planning is gated to Layers 7 and 8*):
   * *Forbidden terms*: `irrigate now`, `apply fertilizer`, `spray fungicide`, `irrigation recommendation`, `harvest now`, `recommended action`, `apply herbicide`, `prune now`, `schedule irrigation`, `adjust fertilizer rate`.
4. **Yield & Impact Predictions** (*Yield calculations and loss assessments are gated to Layer 6*):
   * *Forbidden terms*: `yield loss`, `severe stress`, `yield forecast`, `expected yield`, `production estimate`, `economic loss`, `crop failure`.

---

## 5. Mathematical & Logic Formulations

### A. Bayesian Conflict Credibility & Severity
When two evidence sources ($a$ and $b$) conflict, their joint credibility ($C$) is computed from freshness ($F$) and reliability ($R$):
$$C(e) = F(e) \times R(e)$$
$$W_{conflict} = \frac{C(a) + C(b)}{2}$$

The difference $\Delta v = |v_a - v_b|$ is compared against the variable's threshold adjusted by the phenology factor $\phi_{growth}$:
$$\text{Threshold}_{eff} = \text{Threshold}_{base} \times \phi_{growth}$$
$$\text{Severity} = \begin{cases} 
\text{major} & \text{if } \Delta v > 2 \times \text{Threshold}_{eff} \text{ and } W_{conflict} > 0.6 \\ 
\text{moderate} & \text{if } \Delta v > 1.5 \times \text{Threshold}_{eff} \text{ and } W_{conflict} > 0.4 \\ 
\text{minor} & \text{otherwise} 
\end{cases}$$

### B. Bayesian-Inspired Confidence Impact
Disagreements between two highly confident sources penalize overall confidence severely, whereas conflicts with already uncertain sources are heavily discounted:
$$\text{Impact}_{conflict} = 1 - \frac{\text{Conf}_a \times \text{Conf}_b}{\max(\text{Conf}_a, \text{Conf}_b)}$$

### C. Contextual Confidence Min-Reduction
Deterministic confidence fusion is computed by taking the minimum of all diagnostic constraints:
$$\text{Conf}_{fused} = \min\left(\text{Conf}_{source}, \text{Score}_{qa}, \text{Freshness}, \text{Ceiling}_{role}, \text{Ceiling}_{type}, \text{Penalty}_{conflict}\right)$$

### D. Source-Family Confidence Ceilings
Ceilings represent physical limits of instrument measurement accuracy:
* `sensor`: $0.95$ (Calibrated direct ground-truth contact)
* `sentinel2`: $0.88$ (Residual aerosol scattering and shadow)
* `sentinel1`: $0.78$ (C-band speckle noise and incidence angle roughness)
* `environment`: $0.82$ (ERA5 gridded reanalysis interpolation grid error)
* `weather_forecast`: $0.70$ (NWP forecast skill decay)
* `geo_context`: $0.85$ (DEM elevation accuracy and SoilGrids spatial resolution)

### E. Piecewise Freshness Weight Decay
Telemetry age $t_{hours} = \frac{t_{run} - t_{obs}}{3600}$. Freshness decays along source-specific curves:
* **IoT Sensor**: $[(6\text{h}, 0.95), (24\text{h}, 0.80), (72\text{h}, 0.60), (168\text{h}, 0.30)]$
* **Sentinel-2**: $[(120\text{h}, 0.85), (240\text{h}, 0.65), (480\text{h}, 0.40)]$
* **Sentinel-1**: $[(144\text{h}, 0.80), (288\text{h}, 0.60), (576\text{h}, 0.35)]$

### F. USGS Endmember Spectral Basis Unmixing (F21 Fallback)
In fallback mode (F21), the 128-d embedding is constructed by first calculating 7 agronomic spectral indices and projecting statistics (Mean, Std, Min, Max, P25, P75, Skewness, Kurtosis) of 6 Sentinel-2 bands ($B_2, B_3, B_4, B_8, B_{11}, B_{12}$) onto physically-grounded endmember vectors from the USGS Spectral Library:
$$\vec{e}_{proj} = \tanh\left(\mathbf{W}_{USGS} \cdot \vec{f}_{stats}\right)$$
where $\mathbf{W}_{USGS}$ is built from USGS Spectral Library reflectance vectors representing green vegetation, dry soil, water, shadow, and senescent vegetation.

Agronomic index equations implemented:
$$\text{NDVI} = \frac{B_8 - B_4}{B_8 + B_4} \quad \text{(Chlorophyll Density)}$$
$$\text{NDMI} = \frac{B_8 - B_{11}}{B_8 + B_{11}} \quad \text{(Leaf Water Content)}$$
$$\text{BSI} = \frac{(B_{11} + B_4) - (B_8 + B_2)}{(B_{11} + B_4) + (B_8 + B_2)} \quad \text{(Bare Soil Exposure)}$$
$$\text{SAVI} = \frac{B_8 - B_4}{B_8 + B_4 + 0.5} \times 1.5 \quad \text{(Soil-Adjusted Canopy)}$$
$$\text{EVI} = 2.5 \times \frac{B_8 - B_4}{B_8 + 6.0 \cdot B_4 - 7.5 \cdot B_2 + 1.0} \quad \text{(Enhanced Vegetation)}$$
$$\text{GRVI} = \frac{B_3 - B_4}{B_3 + B_4} \quad \text{(Green-Red Senescence)}$$

### G. L2 Anomaly Distance
Neural anomalies are computed as normalized L2 distance in the embedding space against a healthy, high-vigor reference signature $\vec{e}_{ref}$:
$$\text{AnomalyScore} = \min\left(2.0, \frac{\|\vec{e}_{proj} - \vec{e}_{ref}\|_2}{3.0}\right)$$

### H. Quantile Zone Clustering & GeoJSON Polygon Conversion
Percentile thresholds $P_{33.3}$ and $P_{66.6}$ segment temporal median NDVI maps:
$$\text{Zone A (High Vigor)} \ge P_{66.6}$$
$$\text{Zone B (Average Vigor)} \in [P_{33.3}, P_{66.6})$$
$$\text{Zone C (Lagging / Stress)} < P_{33.3}$$

Spatial grid cells ($y, x$) are mapped into GeoJSON rings by dividing the coordinate bounding box:
$$\Delta_{lat} = \frac{lat_{max} - lat_{min}}{H}, \quad \Delta_{lng} = \frac{lng_{max} - lng_{min}}{W}$$
$$Ring = \left[ [x \Delta_{lng}, y \Delta_{lat}], [(x+1) \Delta_{lng}, y \Delta_{lat}], [(x+1) \Delta_{lng}, (y+1) \Delta_{lat}], [x \Delta_{lng}, (y+1) \Delta_{lat}], [x \Delta_{lng}, y \Delta_{lat}] \right]$$

### I. Inverse-Variance Uncertainty Propagation
Uncertainty values ($\sigma$) are propagated and weighted via inverse variance:
$$\sigma_{fused} = \frac{1}{\sqrt{\sum_{i} \frac{1}{\sigma_i^2}}}$$
$$w_s = \frac{\frac{1}{\sigma_s^2}}{\sum_{k} \frac{1}{\sigma_k^2}}$$

---

## 6. Scientific References

* **Rouse, J. W., et al. (1974)**. *Monitoring the Vernal Advancement and Retrogradation (Green Wave Effect) of Natural Vegetation*. NASA/GSFC Type III Final Report.
* **Gao, B. C. (1996)**. *NDWI—A Normalized Difference Water Index for Remote Sensing of Vegetation Liquid Water from Space*. Remote Sensing of Environment.
* **Huete, A. R. (1988)**. *A Soil-Adjusted Vegetation Index (SAVI)*. Remote Sensing of Environment.
* **Huete, A. R., et al. (2002)**. *Overview of the Radiometric and Biophysical Performance of the MODIS Vegetation Indices*. Remote Sensing of Environment.
* **Dempster, A. P. (1968)**. *A Generalization of Bayesian Inference*. Journal of the Royal Statistical Society.
* **Hall, D. L., & Llinas, J. (1997)**. *An Introduction to Multisensor Data Fusion*. Proceedings of the IEEE.
* **Thenkabail, P. S., et al. (2013)**. *Spectral Hyperspectral Libraries for Irrigated Crops and Soil Backgrounds*. Remote Sensing of Environment.
* **Eilers, P. H. C. (2003)**. *A Perfect Smoother with Working Weights*. Analytical Chemistry.
* **Chen, J., et al. (2004)**. *A Simple Method for Reconstructing a High-Quality NDVI Time-Series Data Set Based on the Savitzky-Golay Filter*. Remote Sensing of Environment.
