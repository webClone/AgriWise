# Sentinel-2 V1 Contract

## Input Raster Requirements

### Bands
| Band | Resolution | Required | Notes |
|------|-----------|----------|-------|
| B02 (Blue) | 10m | Required for EVI, BSI | |
| B03 (Green) | 10m | Optional V1 | |
| B04 (Red) | 10m | Required for NDVI, EVI, BSI | |
| B05 (Red Edge 1) | 20m→10m | Required for NDRE | Must be resampled to 10m |
| B08 (NIR) | 10m | Required for NDVI, EVI, NDMI, BSI | |
| B8A (Narrow NIR) | 20m→10m | Required for NDRE | Must be resampled to 10m |
| B11 (SWIR 1) | 20m→10m | Required for NDMI, BSI | Must be resampled to 10m |
| SCL | 20m→10m | Required | Scene Classification Layer |
| dataMask | 10m | Optional | Data validity mask |

### Alignment Rules
- All bands MUST have identical grid_shape (height × width)
- All bands MUST have identical CRS
- All bands MUST have `aligned_to_plot_grid = True`
- Alpha mask MUST have identical shape to bands
- Violations → `AlignmentError` (hard reject)

### Reflectance Scale
- `reflectance_0_1`: Native float reflectance (preferred)
- `scaled_0_10000`: ESA convention (divide by 10000)
- `byte_0_255`: Only if represents scaled reflectance, NOT rendered RGB
- Scientific indices CANNOT be computed from visual RGB-rendered bytes

## Index Formulas
| Index | Formula | Valid Range | Guard |
|-------|---------|-------------|-------|
| NDVI | (B08−B04)/(B08+B04) | [-1, 1] | denom < ε → None |
| EVI | 2.5*(B08−B04)/(B08+6*B04−7.5*B02+1) | [-1, 1.5] | out of range → None |
| NDMI | (B08−B11)/(B08+B11) | [-1, 1] | denom < ε → None |
| NDRE | (B8A−B05)/(B8A+B05) | [-1, 1] | denom < ε → None |
| BSI | ((B11+B04)−(B08+B02))/((B11+B04)+(B08+B02)) | [-1, 1] | denom < ε → None |

## QA Rules
- All fractions are alpha-weighted: `sum(alpha * condition) / sum(alpha)`
- Cloud > 50% → UNUSABLE
- Valid < 40% → UNUSABLE
- Shadow > 45% → UNUSABLE
- Snow > 30% → UNUSABLE
- Age > 45 days → STALE, reliability ≤ 0.35
- Missing cloud QA → reliability ≤ 0.65, sigma × 1.5

## Packet Rules
- UNUSABLE → emits SCENE_QA + PROVENANCE only
- UNUSABLE → zero KalmanObservations
- All packets carry provenance and uncertainty

## Kalman Rules
- NDVI/EVI: strong observations (low sigma, high reliability ceiling)
- NDMI: moderate
- NDRE/BSI: weak (high sigma, low reliability ceiling, cannot dominate state)
- DEGRADED: all reliability ≤ 0.5, all sigma ≥ base × 2.0

## Provenance (mandatory)
Every ScenePackage MUST have: scene_id, acquisition_datetime, provider,
crs, band_list, plot_geometry_hash. Validation fails if missing.
