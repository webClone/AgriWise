"""
Vegetation Surface Engine (v2) — True spatial surfaces from L1/L2 adapter data
===============================================================================

Uses L1 adapter raster_maps (from 4D tensor or maps dict) for true per-pixel
values. Falls back to zone rasterization, then field broadcast as last resort.
"""
import math
from typing import List, Optional
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l2_adapter import L2VegData


def generate_vegetation_surfaces(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
    l2_data: Optional[L2VegData] = None,
) -> List[SurfaceArtifact]:
    """Generate vegetation surfaces using adapter data (spatial-first)."""
    surfaces = []
    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l2_data is None:
        from services.agribrain.layer10_sire.adapters.l2_adapter import adapt_l2
        l2_data = adapt_l2(inp.veg_int)

    # --- 1. NDVI_CLEAN — from L1 raster or broadcast ---
    ndvi_grid = _get_spatial_raster(l1_data, 'ndvi', H, W)
    field_mean = _grid_mean(ndvi_grid, H, W)

    ndvi_source_key = _find_direct_raster_key(l1_data, "ndvi")
    ndvi_metadata = _find_raster_metadata(l1_data, ndvi_source_key or "ndvi")

    # Inject spatial variation when the raster is broadcast-filled (no real per-pixel
    # satellite data). Zone-based variation is honest — it reflects actual zone structure
    # from the FieldTensor. The gradient fallback uses measured spatial variance to create
    # a plausible proxy when zones are absent. Without this, the overlay is a flat tint
    # that provides zero spatial information to the farmer.
    #
    # Skip injection if we already have real per-pixel raster data (from 4D tensor or
    # raster_composites) — in that case the spatial variation is genuine.
    # Broadcast values remain uniform. Spatial texture must come from admitted
    # raster pixels or explicit zone geometry, never a generated gradient.

    # Clamp NDVI strictly to biophysical valid range [-1.0, 1.0] before appending
    for r in range(H):
        for c in range(W):
            if ndvi_grid[r][c] is not None:
                ndvi_grid[r][c] = round(max(-1.0, min(1.0, ndvi_grid[r][c])), 4)

    ndvi_provenance = {
        "source_signal_used": "NDVI_CLEAN",
        "source_variable": ndvi_source_key,
    }
    # Only copy truth fields that actually travelled with the admitted L1
    # RasterRef.  Missing metadata remains missing/unknown; it is never
    # upgraded from the existence of finite values alone.
    for key in (
        "truth_class",
        "source_reality",
        "real_provider_product",
        "production_usable",
        "diagnostic_only",
        "state_update_allowed",
        "observed_spatial_surface",
        "prescription_driver_allowed",
        "authority_block_reason",
        "source_basis",
        "content_hash",
        "raster_id",
    ):
        if key in ndvi_metadata:
            ndvi_provenance[key] = ndvi_metadata[key]

    surfaces.append(SurfaceArtifact(
        surface_id=f"NDVI_CLEAN_{inp.plot_id}",
        semantic_type=SurfaceType.NDVI_CLEAN,
        grid_ref=f"{H}x{W}",
        values=ndvi_grid,
        units="index",
        native_resolution_m=inp.resolution_m,
        render_range=(-0.1, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L1"],
        provenance=ndvi_provenance,
        grounding_class=ndvi_metadata.get("grounding_class"),
        raster_basis=[ndvi_source_key] if ndvi_source_key else [],
        observed_ratio=float(ndvi_metadata.get("observed_ratio", 0.0) or 0.0),
    ))

    # --- 2. NDVI_DEVIATION — per-cell vs field mean ---
    dev_grid = [[None]*W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            v = ndvi_grid[r][c]
            if v is not None and field_mean is not None:
                dev_grid[r][c] = round(v - field_mean, 4)

    surfaces.append(SurfaceArtifact(
        surface_id=f"NDVI_DEV_{inp.plot_id}",
        semantic_type=SurfaceType.NDVI_DEVIATION,
        grid_ref=f"{H}x{W}",
        values=dev_grid,
        units="index_delta",
        native_resolution_m=inp.resolution_m,
        render_range=(-0.5, 0.5),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L1"],
    ))

    # --- 3. BASELINE_ANOMALY — spatially modulated by NDVI deviation ---
    baseline_lag = 0.0
    for anom in getattr(l2_data, 'anomalies', []):
        atype = anom.get('type') if isinstance(anom, dict) else getattr(anom, 'type', '')
        asev = anom.get('severity', 0.0) if isinstance(anom, dict) else getattr(anom, 'severity', 0.0)
        if atype in ["STALL", "DROP", "DELAYED_EMERGENCE", "EARLY_SENESCENCE"]:
            baseline_lag -= (asev * 0.2)

    # Spatial modulation: low NDVI areas are further behind expectation
    baseline_grid = [[round(baseline_lag, 4)] * W for _ in range(H)]
    if field_mean is not None and field_mean > 0:
        for r in range(H):
            for c in range(W):
                v = ndvi_grid[r][c]
                if v is not None:
                    ratio = (v / field_mean) - 1.0  # Negative for below-mean areas
                    baseline_grid[r][c] = round(baseline_lag + ratio * 0.15, 4)
    
    surfaces.append(SurfaceArtifact(
        surface_id=f"BASELINE_ANOM_{inp.plot_id}",
        semantic_type=SurfaceType.BASELINE_ANOMALY,
        grid_ref=f"{H}x{W}",
        values=baseline_grid,
        units="index_delta",
        native_resolution_m=inp.resolution_m,
        render_range=(-0.5, 0.5),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L2"],
    ))

    # --- 3. GROWTH_VELOCITY — from L2 curve, spatially modulated ---
    vel_val = l2_data.ndvi_fit_d1[-1] if l2_data.ndvi_fit_d1 else 0.0
    if vel_val == 0.0:
        # No L2 curve — derive velocity proxy from NDVI spatial deviation
        vel_grid = [[0.0] * W for _ in range(H)]
    else:
        vel_grid = _modulate_field_value(vel_val, ndvi_grid, field_mean, H, W)

    surfaces.append(SurfaceArtifact(
        surface_id=f"GROWTH_VEL_{inp.plot_id}",
        semantic_type=SurfaceType.GROWTH_VELOCITY,
        grid_ref=f"{H}x{W}",
        values=vel_grid,
        units="index/day",
        native_resolution_m=inp.resolution_m,
        render_range=(-0.05, 0.05),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L2"],
    ))

    # --- 4. STABILITY_CLASS — spatially from L1 zones or L2 spatial var ---
    stab_grid = _build_stability_grid(l1_data, l2_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"STABILITY_{inp.plot_id}",
        semantic_type=SurfaceType.STABILITY_CLASS,
        grid_ref=f"{H}x{W}",
        values=stab_grid,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.UNCERTAINTY_GRAY,
        source_layers=["L2"],
    ))

    return surfaces


def _has_data(grid, H, W):
    if not grid: return False
    for r in range(min(H, len(grid))):
        if grid[r]:
            for c in range(min(W, len(grid[r]))):
                if grid[r][c] is not None:
                    return True
    return False


def _find_direct_raster_key(l1: L1SpatialData, var: str) -> Optional[str]:
    """Return the actual admitted raster key used for a variable, if any."""
    candidates = [var]
    candidates.extend({
        "ndvi": ["NDVI", "ndvi_smoothed", "ndvi_interpolated", "ndvi_mean"],
        "ndmi": ["NDMI", "ndmi_interpolated", "ndmi_mean"],
    }.get(var, []))
    for key in candidates:
        raster = l1.raster_maps.get(key)
        if raster is not None and _has_data(raster, l1.height, l1.width):
            return key
    return None


def _find_raster_metadata(l1: L1SpatialData, key: str) -> dict:
    """Resolve metadata aliases without manufacturing provider authority."""
    candidates = [key, key.lower(), key.upper()]
    if key.lower().startswith("ndvi"):
        candidates.extend(["ndvi", "NDVI"])
    for candidate in candidates:
        metadata = l1.raster_metadata.get(candidate)
        if isinstance(metadata, dict):
            return metadata
    return {}

def _get_spatial_raster(l1: L1SpatialData, var: str, H: int, W: int):
    """Get raster for variable, trying real spatial → zone rasterize → broadcast."""
    # 1) Direct raster
    if var in l1.raster_maps:
        r = l1.raster_maps[var]
        if _has_data(r, H, W):
            return r

    # 2) Alias lookup
    aliases = {
        'ndvi': ['NDVI', 'ndvi_smoothed', 'ndvi_interpolated', 'ndvi_mean'],
        'ndmi': ['NDMI', 'ndmi_interpolated', 'ndmi_mean'],
    }
    for alias in aliases.get(var, []):
        if alias in l1.raster_maps:
            r = l1.raster_maps[alias]
            if _has_data(r, H, W):
                return r

    # 3) Zone rasterization — if we have per-zone values
    if l1.zone_masks:
        zone_var = None
        if var in l1.zone_timeseries:
            zone_var = var
        else:
            for alias in aliases.get(var, []):
                if alias in l1.zone_timeseries:
                    zone_var = alias
                    break
        
        if zone_var:
            grid = [[None]*W for _ in range(H)]
            for z_id, cells in l1.zone_masks.items():
                ts = l1.zone_timeseries[zone_var].get(z_id, [])
                val = ts[-1] if ts else None
                for r, c in cells:
                    if r < H and c < W:
                        grid[r][c] = val
            if any(grid[r][c] is not None for r in range(H) for c in range(W)):
                return grid

    # 4) Field-level broadcast (last resort)
    val = l1.last_values.get(var)
    if val is None:
        for alias in aliases.get(var, []):
            if alias in l1.last_values:
                val = l1.last_values[alias]
                break

    if val is not None:
        return [[val]*W for _ in range(H)]

    return [[None]*W for _ in range(H)]


def _smooth_grid(g, H, W, passes=2):
    """Gaussian-like spatial smoothing filter to dissolve blocky zone margins."""
    for _ in range(passes):
        temp = [[0.0] * W for _ in range(H)]
        for r in range(H):
            for c in range(W):
                val_sum = 0.0
                weight_sum = 0.0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < H and 0 <= nc < W:
                            weight = 4.0 if (dr == 0 and dc == 0) else (2.0 if (dr == 0 or dc == 0) else 1.0)
                            val_sum += g[nr][nc] * weight
                            weight_sum += weight
                temp[r][c] = val_sum / weight_sum
        g = temp
    return g


def _modulate_field_value(field_val, ndvi_grid, field_mean, H, W):
    """Spatially modulate a field-level value using NDVI as a spatial proxy.
    Higher NDVI → proportionally more of the value. Conserves field mean."""
    grid = [[None]*W for _ in range(H)]
    if field_mean is None or field_mean == 0 or field_val is None:
        for r in range(H):
            for c in range(W):
                grid[r][c] = field_val if field_val is not None else 0.0
        return grid

    for r in range(H):
        for c in range(W):
            v = ndvi_grid[r][c]
            if v is not None and field_mean != 0:
                ratio = v / field_mean  # cells with higher NDVI get more
                grid[r][c] = round(field_val * ratio, 6)
            else:
                grid[r][c] = field_val
    return grid


def _build_stability_grid(l1: L1SpatialData, l2: L2VegData, H: int, W: int):
    """Build spatial stability score from zone structure + L2 metrics."""
    base_score = {
        "STABLE": 0.9, "MODERATE": 0.5, "HETEROGENEOUS": 0.2,
        "TRANSIENT_VAR": 0.3, "UNKNOWN": 0.5,
    }.get(l2.stability_class, 0.5) * l2.stability_confidence

    if l1.zone_masks:
        # Zone-aware: different stability per zone using zone_metrics
        grid = [[None]*W for _ in range(H)]
        zone_scores = {}
        for z_id in l1.zone_masks:
            zm = l2.zone_metrics.get(z_id, {})
            if isinstance(zm, dict):
                zone_scores[z_id] = zm.get('stability_score', base_score)
            else:
                zone_scores[z_id] = base_score

        assigned = set()
        for z_id, cells in l1.zone_masks.items():
            score = zone_scores.get(z_id, base_score)
            for r, c in cells:
                if r < H and c < W:
                    grid[r][c] = round(score, 3)
                    assigned.add((r, c))

        # Fill unassigned cells
        for r in range(H):
            for c in range(W):
                if (r, c) not in assigned:
                    grid[r][c] = round(base_score, 3)

        # Check if zone-aware scores are actually varied
        unique_scores = set(v for row in grid for v in row if v is not None)
        if len(unique_scores) <= 1:
            # All zones got same score — add NDVI-based within-zone modulation
            from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined
            ndvi_r = get_ndvi_raster(l1, H, W)
            grid = modulate_combined(base_score, ndvi_r, H, W, invert=False, clamp_min=0.1, clamp_max=1.0)

        return grid
    else:
        # Spatial modulation: areas with higher NDVI are more stable
        from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi
        ndvi_r = get_ndvi_raster(l1, H, W)
        grid = modulate_by_ndvi(base_score, ndvi_r, H, W, invert=False, clamp_min=0.1, clamp_max=1.0)
        return grid


def _grid_mean(grid, H, W):
    """Compute mean of non-None values."""
    vals = [grid[r][c] for r in range(H) for c in range(W) if grid[r][c] is not None]
    return sum(vals) / len(vals) if vals else None
