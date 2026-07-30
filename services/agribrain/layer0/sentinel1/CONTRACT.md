# Sentinel-1 SAR V1 Contract

## Input Raster Requirements

### Bands
| Band | Unit | Required | Notes |
|------|------|----------|-------|
| VV | linear_power | Required | Co-polarized backscatter |
| VH | linear_power | Required | Cross-polarized backscatter |
| dataMask | integer (0/1) | Required | Valid pixel mask |
| incidence_angle | degrees | Optional | Radar geometry |

### Input Unit Rules
- VV and VH input rasters MUST be linear backscatter power, not dB.
- If input is already dB, caller must convert to linear before passing to the engine.
- The engine will reject `unit != "linear_power"` for VV/VH inputs.
- Feature rasters (VV_DB, VH_DB) are computed internally with `unit="db"`.

### Alignment Rules
- VV shape == VH shape == dataMask shape == alpha_mask shape
- All rasters MUST have identical CRS
- All rasters MUST have `aligned_to_plot_grid = True`
- VV must have `polarization = "VV"`
- VH must have `polarization = "VH"`
- instrument_mode must be `IW`
- polarization must be `DV`
- Violations → `SARAlignmentError` (hard reject)

### Required Metadata (fatal if missing)
scene_id, product_id, acquisition_datetime, provider, processing_level (GRD),
platform, instrument_mode (IW), polarization (DV), orbit_direction,
relative_orbit, resolution_m, crs, plot_geometry_hash

## dB Plausibility Ranges

| Feature | Hard range (None if outside) | Soft range (flag if outside) |
|---------|------------------------------|-------------------------------|
| VV_dB | [-35, 5] | [-30, 0] |
| VH_dB | [-45, 0] | [-35, -5] |
| VV_minus_VH_dB | [-5, 25] | [0, 20] |
| RVI | [0, 4] mathematical | [0, 1.5] crop-normal |

Outside hard range → None (invalid).
Outside soft range → diagnostic flag + sigma inflation.

## SAR is NOT Cloud-Aware
SAR QA must NEVER use cloud/shadow concepts from Sentinel-2.
SAR validity is based on: dataMask, signal plausibility, border-noise heuristic,
incidence geometry, and speckle/scene quality.

## Feature Formulas
| Feature | Formula | Unit |
|---------|---------|------|
| VV_DB | 10 * log10(VV) | db |
| VH_DB | 10 * log10(VH) | db |
| VV_VH_ratio | VV / VH | ratio |
| VV_minus_VH_DB | VV_DB - VH_DB | db |
| span | VV + VH | linear_power |
| RVI | 4 * VH / (VV + VH) | ratio |
| cross_pol_fraction | VH / (VV + VH) | ratio |
| surface_wetness_proxy | f(VV_DB, ratio, incidence) | score [0,1] |
| structure_proxy | f(VH_DB, RVI) | score [0,1] |
| flood_score | f(VV_DB, VH_DB, span) | score [0,1] |
| roughness_proxy | f(VV_DB, VH_DB, context) | score |

## Moisture Proxy
`surface_wetness_proxy` is NOT calibrated volumetric soil moisture.
It is a weak SAR-derived wetness indicator until calibrated with sensors.

## QA Rules
- All fractions are alpha-weighted: `sum(alpha * condition) / sum(alpha)`
- Valid < 0.45 → UNUSABLE
- Border noise > 0.30 → UNUSABLE
- Low signal > 0.50 → UNUSABLE
- Missing incidence angle → flag, sigma × 1.25
- Mean incidence < 25° or > 50° → DEGRADED or angle penalty
- Scene age > 30 days → STALE flag

## Border Noise
V1 border_noise_like is HEURISTIC unless provider supplies explicit mask.
Flag: BORDER_NOISE_HEURISTIC always set when using heuristic detection.

## Quality Classes
| Class | valid_fraction | low_signal | border_noise | reliability | sigma |
|-------|---------------|------------|--------------|-------------|-------|
| EXCELLENT | ≥ 0.90 | ≤ 0.05 | ≤ 0.05 | 0.90 | ×1.0 |
| GOOD | ≥ 0.75 | ≤ 0.15 | ≤ 0.15 | 0.80 | ×1.2 |
| DEGRADED | ≥ 0.45 | any | any | 0.55 | ×1.8 |
| UNUSABLE | < 0.45 | — | — | 0.0 | — |

## Packet Rules
- UNUSABLE → emits SCENE_QA + PROVENANCE only
- UNUSABLE → zero KalmanObservations
- All packets carry provenance and uncertainty

## Kalman Rules
| Feature | Obs key | Strength | Sigma | Reliability ceiling |
|---------|---------|----------|-------|---------------------|
| VV dB | vv | strong/moderate | 1.5 dB | 0.85 |
| VH dB | vh | moderate | 2.0 dB | 0.75 |
| RVI | sar_rvi | weak | 0.10 | 0.55 |
| wetness proxy | sar_moisture_proxy | weak | 0.12 | 0.50 |
| flood_score | — | packet-only | — | — |
| emergence | — | packet-only | — | — |
| roughness | — | packet-only | — | — |

DEGRADED: all reliability ≤ 0.5, all sigma ≥ base × 2.0

## Orbit Compatibility
Temporal comparisons must only compare scenes with compatible
orbit_direction + relative_orbit unless explicitly marked low confidence.

## Provenance (mandatory)
Every ScenePackage MUST have all required metadata fields.
Validation fails fatally (SARProvenanceError) if missing.
