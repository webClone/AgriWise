# ASMAE — Data Contracts

## System Name
**ASMAE** — Adaptive Scientific MicroZone Assimilation Engine

## Non-Negotiable Rules
1. Sentinel-2 remains 10m/20m/60m native evidence.
2. 1m is never called "direct satellite observation."
3. 1m can become "plot-certified learned micro-zone display," not "true 1m sensor truth."
4. Confidence increases only with validated, diverse, calibrated evidence.
5. Confidence must be allowed to decrease after drift, contradiction, crop rotation, or failed retrovalidation.
6. Every micro-zone state must carry uncertainty.
7. Every adaptive resolution must pass radiometric consistency.
8. No prescription may be triggered directly from diagnostic-only 1m outputs.
9. Weak labels are not ground truth.
10. Layer 8 actions consume only gated, confidence-approved evidence.

---

## Data Flow

```
Layer 0 (sources)
  → Layer 1 (coarse evidence)
  → Layers 2–8 (coarse priors)
  → ASMAE (scientific micro-zone assimilation)
  → ASMAE-Learn (plot-specific learning/certification)
  → Layer 1 (refined fusion)
  → Layers 2–8 (refined reasoning)
  → Layer 10 (truthful visual surfaces)
  → UI (adaptive resolution, confidence, uncertainty, actions)
```

---

## Contract: Layer 0 → ASMAE

### Required
| Field | Type | Description |
|-------|------|-------------|
| `scene_id` | `str` | Unique scene identifier |
| `sensor` | `enum` | S2, S1, S5P, EXTERNAL |
| `acquisition_time` | `datetime` | UTC ISO 8601 |
| `crs` | `str` | Valid EPSG code |
| `transform` | `list[float]` | 6-element affine |
| `width`, `height` | `int` | Scene dimensions |
| `band_refs` | `dict[str, str]` | Band artifact references |
| `mask_refs` | `dict[str, str]` | Mask artifact references |
| `qa_score` | `float` | [0, 1] quality assessment |

### Invariants
- `scene_id` unique within a run
- `band_refs` must resolve to accessible artifacts
- Per-scene CRS and transform preserved (no premature grid forcing)

---

## Contract: Layer 1 → ASMAE

### Required
| Field | Type | Description |
|-------|------|-------------|
| `data_health` | `dict` | Overall data quality metrics |
| `trust_scores` | `dict` | Per-source trust scores |
| `raster_composites_baseline` | `dict` | Baseline composites |
| `temporal_coverage` | `dict` | Date ranges covered |

### Invariants
- Layer 1 composites are **observations**, not state truth
- Trust scores must be per-source

---

## Contract: Layers 2–8 → ASMAE (Coarse Priors)

### Layer 2 (Vegetation)
`phenology_stage`, `growth_curve`, `crop_identity_probability`, `vegetation_trend`, `stress_anomaly_envelope`, `stage_specific_reliability`

### Layer 3 (Water)
`et0`, `soil_moisture`, `water_stress`, `irrigation_requirement`, `water_balance`

### Layer 4 (Nutrient)
`nutrient_demand`, `chlorophyll_proxy`, `salinity`, `nue`

### Layer 5 (Bio)
`biotic_threat_risk`, `disease_suitability`, `outbreak_probability`

### Layer 6 (Yield)
`yield_sensitivity`, `economic_value_of_confidence`, `scouting_roi_priority`

### Layer 7 (Risk)
`climate_shock_risk`, `scenario_outputs`, `future_stress_windows`

### Layer 8 (Constraints ONLY)

> **⚠️ Layer 8 must NEVER become ASMAE truth.**

`do_not_prescribe_zones`, `action_feasibility`, `spray_drift_constraints`, `salinity_leaching_constraints`, `phenology_dosing_windows`

### Invariants
- All priors versioned with `run_id`
- No future holdout leakage
- Low-confidence ASMAE never triggers irreversible Layer 8 action

---

## Contract: ASMAE → Layer 1 (Refined Rasters)

### Provided
| Field | Type | Description |
|-------|------|-------------|
| `raster_maps` | `dict[str, 2D]` | State variable grids |
| `uncertainty_maps` | `dict[str, 2D]` | Per-state uncertainty |
| `confidence_maps` | `dict[str, 2D]` | Per-state confidence |
| `resolution_decision` | `dict` | Selected resolution + reasons |
| `certification` | `dict` | Plot certification status |
| `provenance` | `dict` | Full run provenance |

### Invariants
- All rasters include uncertainty
- No output called "direct 1m satellite observation"
- Content hash deterministic for same inputs

---

## Contract: ASMAE → Layer 10 (Visual Surfaces)

### Invariants
- Visual surfaces respect resolution decision
- Low-confidence zones fall back to 10m baseline
- 1m display requires explicit certification
- `visual_intensity` computed from ASMAE confidence

---

## State Vector

NDVI is an **observation**, not a state variable.

| Index | State | Bounds | Unit |
|-------|-------|--------|------|
| 0 | vigor | [0, 1] | — |
| 1 | lai | [0, 8] | m²/m² |
| 2 | chlorophyll | [0, 80] | μg/cm² |
| 3 | canopy_water | [0, 1] | — |
| 4 | root_zone_water | [0, 1] | vol. fraction |
| 5 | surface_wetness_event | [0, 1] | — |
| 6 | structure | [0, 1] | — |
| 7 | bare_soil_fraction | [0, 1] | — |
| 8 | salinity_stress | [0, 1] | — |
| 9 | thermal_stress | [0, 1] | — |
| 10 | biotic_confounder_risk | [0, 1] | — |
| 11 | phenology_progress | [0, 1] | — |
| 12 | stress_memory | [0, 1] | — |

---

## Schema Design: Runtime vs Manifest

### Runtime Objects (in-memory only)
- `ASMAESceneRuntime`: `bands: dict[str, np.ndarray]`
- `ObservationOperatorRuntime`: `H_matrix: scipy.sparse.csr_matrix`

### Serializable Manifests (storage/API)
- `ASMAESceneManifest`: `band_refs: dict[str, str]`, `shape`, `dtype`, `content_hash`
- `ObservationOperatorManifest`: `h_matrix_artifact_ref`, `h_matrix_format: "csr_v1"`, `h_matrix_shape`

### H_t Storage
- Runtime: `scipy.sparse.csr_matrix`
- Storage: `.npz` artifact referenced by manifest
- Never stored as giant JSON

---

## Feature Flag

ASMAE must not run in production without `ASMAE_ENABLED=true`.
