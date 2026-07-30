# Geo Context Engine V1 Contract

## Purpose

Before trusting field sensors, know where they sit: slope, drainage,
land-cover contamination, crop-mask validity, and regional water-productivity context.

This engine sits **after** Environment / Weather Forecast V1.1 and **before** Sensors.

## Source Roles

| Source | Role | Resolution | Kalman usage |
|--------|------|-----------|-------------|
| Copernicus DEM GLO-30 | Primary terrain context | 30 m | **NONE** — static context only |
| Copernicus DEM GLO-90 | Fallback terrain context | 90 m | **NONE** — static context only |
| ESA WorldCover | Baseline land-cover classification | 10 m | **NONE** — QA flags, trust modifiers |
| Dynamic World | Dynamic land-cover probabilities | 10 m | **NONE** — confidence context only |
| FAO WaPOR | Regional ET / biomass / water productivity | 30–250 m | **NONE** — validation context only |

## Hard Prohibition: No Kalman Observations

Geo Context **MUST NOT** create Kalman observations. It may affect:

- Sensor placement guidance
- Sensor representativeness assessment
- Satellite source reliability (trust modifiers)
- Plot validity assessment
- Zone generation inputs
- Diagnostic context

### Forbidden

| Action | Why |
|--------|-----|
| DEM slope → direct soil moisture update | Terrain is static context, not measurement |
| Land cover class → direct LAI update | Land cover is classification, not biophysical |
| WaPOR ET → direct current water stress update | WaPOR is regional validation, not plot truth |
| Dynamic World crop probability → direct crop health update | DW is noisy classification, not state |
| Sensor placement → state update | Placement is guidance, not observation |

## Raster Alignment Contract

Every raster input **MUST** carry:

| Field | Required | Rule |
|-------|----------|------|
| `shape` | Yes | Must match alpha mask shape |
| `crs` | Yes | Must be consistent across inputs |
| `resolution_m` | Yes | Must be > 0 |
| `aligned_to_plot_grid` | Yes | Must be True |
| `valid_mask` | Yes | Boolean array, same shape as data |
| `alpha_mask` | Optional | Float [0,1] array for boundary weighting |
| `raster_ref` | Optional | Reference ID for provenance |
| `content_hash` | Optional | Integrity hash |

### Rejection rules

- Raster shape ≠ alpha mask shape → **reject**
- CRS mismatch across inputs → **reject**
- `aligned_to_plot_grid` is False → **reject**
- Missing `valid_mask` → **reject**
- Resolution missing → **reject**

## Raster Size Contract (V1)

- Maximum raster dimensions: **512 × 512 pixels**
- Larger rasters are downsampled or rejected

### Downsampling rules

| Raster type | Method |
|-------------|--------|
| DEM (continuous) | Mean/median elevation, preserve min/max diagnostics |
| ESA WorldCover (categorical) | Mode / class majority, **not average** |
| Dynamic World (probability) | Per-class probability mean |
| WaPOR (continuous) | Mean/median with valid-mask weighting |

**Never average categorical class IDs.**

## Alpha-Weighted Summary Rule

ALL plot-level summaries MUST use:

```
weighted_mean = sum(alpha × valid × value) / sum(alpha × valid)
```

This applies to:

- DEM terrain statistics
- Land-cover fractions
- Dynamic World probabilities
- WaPOR ET / biomass summaries
- Boundary contamination scores

## Packet Types

| Packet | When |
|--------|------|
| `DEM_TERRAIN_CONTEXT` | DEM available |
| `DEM_DRAINAGE_CONTEXT` | DEM available |
| `DEM_SENSOR_PLACEMENT_GUIDANCE` | DEM available |
| `LANDCOVER_BASELINE_CONTEXT` | WorldCover available |
| `LANDCOVER_DYNAMIC_CONTEXT` | Dynamic World available |
| `LANDCOVER_BOUNDARY_CONTAMINATION` | Land cover available |
| `PLOT_VALIDITY_CONTEXT` | Any source available |
| `WAPOR_WATER_PRODUCTIVITY_CONTEXT` | WaPOR available |
| `WAPOR_ET_BIOMASS_CONTEXT` | WaPOR available |
| `GEO_CONTEXT_PROVENANCE` | **Always** |
| `GEO_CONTEXT_DIAGNOSTICS` | **Always** |

### All-fail rule

If all sources fail:
- Emit `GEO_CONTEXT_PROVENANCE` + `GEO_CONTEXT_DIAGNOSTICS` only
- No other packets

If one source fails:
- Continue with available sources
- Emit source-specific failure diagnostics

## Provider Failure Behavior

| Failure | Behavior |
|---------|----------|
| DEM missing | Skip terrain, degrade sensor placement confidence |
| WorldCover missing | Skip land-cover baseline, degrade plot validity |
| Dynamic World missing | Skip dynamic context, use WorldCover only |
| WaPOR missing | Emit `WAPOR_NOT_AVAILABLE_FOR_REGION`, continue |
| WaPOR outside coverage | Emit `WAPOR_OUT_OF_COVERAGE`, `wapor_available=False` |
| All sources missing | Emit provenance + diagnostics only |

## Sensor Placement Output

Each recommendation includes:
- `zone_id` — spatial identifier
- `sensor_type` — e.g. `soil_moisture`
- `placement_confidence` — [0, 1]
- `representativeness_scope` — `plot` | `zone` | `point`
- `recommended_depths_cm` — list
- `reason_codes` — list of supporting evidence
- `source_drivers` — which data sources informed this

## Satellite Trust Modifiers

Each modifier includes:
- Risk score [0, 1]
- `modifier_scope` — `plot` | `edge` | `zone` | `source_specific`

| Modifier | Scope | Meaning |
|----------|-------|---------|
| `sentinel2_boundary_risk` | `edge` | Reduce S2 edge-zone vegetation confidence |
| `sentinel1_terrain_risk` | `zone` | Reduce SAR moisture interpretation on steep terrain |
| `sat_rgb_landcover_risk` | `plot` | Reduce RGB veg fraction if non-crop contamination |
| `dynamic_world_disagreement` | `plot` | Flag plot validity uncertainty |

## Production Gate

### Required report fields

```json
{
  "geo_context_engine_ok": true,
  "geo_context_tests": {
    "passed": 100,
    "failed": 0,
    "warnings": 0
  },
  "geo_context_hard_prohibitions": {
    "no_direct_kalman_updates": true,
    "dem_not_soil_moisture_truth": true,
    "landcover_not_crop_health": true,
    "wapor_not_plot_truth": true,
    "dynamic_world_not_crop_health": true,
    "sensor_placement_not_state_update": true
  }
}
```

### Gate fails if

- Geo Context Tests step missing
- `geo_context_tests.failed > 0`
- `geo_context_tests.passed < 90`
- Any hard prohibition is false
- All-sources-failed case emits non-audit packets
- Any Kalman observation is returned
