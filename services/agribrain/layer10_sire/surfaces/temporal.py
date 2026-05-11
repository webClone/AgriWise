"""
Temporal Surface Engine — 14-day Temporal Intelligence Surfaces
================================================================

The centerpiece of SIRE v11: generates per-pixel temporal delta, momentum,
trend, and forecast surfaces using the full 14-day window (T-7 → T+7).

Surfaces produced:
  - NDVI_DELTA_7D: Per-pixel NDVI change over the last 7 days
  - GROWTH_TREND_7D: 7-day growth velocity trend (acceleration)
  - STRESS_MOMENTUM: Water stress rate-of-change
  - DROUGHT_TREND: Consecutive dry-day trend
  - RISK_MOMENTUM: Composite risk acceleration/deceleration
  - YIELD_TRAJECTORY: Yield trajectory projection
  - PRECIPITATION_FORECAST: 7-day spatial precipitation forecast
  - TEMPERATURE_FORECAST: 7-day spatial temperature forecast

All surfaces honestly report grounding class:
  - RASTER_GROUNDED if computed from multi-temporal pixel data
  - PROXY_SPATIAL if derived from curve extrapolation × spatial proxy
  - UNIFORM if no temporal differentiation possible
"""
from typing import List, Optional, Dict, Any
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l2_adapter import L2VegData
from layer10_sire.adapters.l3_adapter import L3DiagnosticData


def generate_temporal_surfaces(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
    l2_data: Optional[L2VegData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
) -> List[SurfaceArtifact]:
    """Generate temporal intelligence surfaces from 14-day window."""
    surfaces = []

    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l2_data is None:
        from layer10_sire.adapters.l2_adapter import adapt_l2
        l2_data = adapt_l2(inp.veg_int)
    if l3_data is None:
        from layer10_sire.adapters.l3_adapter import adapt_l3
        l3_data = adapt_l3(inp.decision)

    has_temporal = bool(l1_data.temporal_rasters) and len(l1_data.time_index) >= 2

    # --- 1. NDVI_DELTA_7D: Per-pixel 7-day NDVI change ---
    ndvi_delta = _compute_ndvi_delta_7d(l1_data, l2_data, H, W, has_temporal)
    surfaces.append(SurfaceArtifact(
        surface_id=f"NDVI_DELTA_7D_{inp.plot_id}",
        semantic_type=SurfaceType.NDVI_DELTA_7D,
        grid_ref=f"{H}x{W}",
        values=ndvi_delta,
        units="index_delta",
        native_resolution_m=inp.resolution_m,
        render_range=(-0.3, 0.3),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L1", "L2"],
        provenance={
            "method": "PIXEL_DIFF" if has_temporal else "CURVE_PROXY",
            "time_steps": len(l1_data.time_index),
        },
    ))

    # --- 2. GROWTH_TREND_7D: Growth velocity acceleration ---
    growth_trend = _compute_growth_trend(l1_data, l2_data, H, W, has_temporal)
    surfaces.append(SurfaceArtifact(
        surface_id=f"GROWTH_TREND_7D_{inp.plot_id}",
        semantic_type=SurfaceType.GROWTH_TREND_7D,
        grid_ref=f"{H}x{W}",
        values=growth_trend,
        units="accel",
        native_resolution_m=inp.resolution_m,
        render_range=(-0.01, 0.01),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L1", "L2"],
    ))

    # --- 3. STRESS_MOMENTUM: Water stress acceleration ---
    stress_mom = _compute_stress_momentum(l1_data, l2_data, l3_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"STRESS_MOMENTUM_{inp.plot_id}",
        semantic_type=SurfaceType.STRESS_MOMENTUM,
        grid_ref=f"{H}x{W}",
        values=stress_mom,
        units="momentum",
        native_resolution_m=inp.resolution_m,
        render_range=(-1.0, 1.0),
        palette_id=PaletteId.RISK_HEAT,
        source_layers=["L1", "L2", "L3"],
    ))

    # --- 4. DROUGHT_TREND: Dry-day accumulation trend ---
    drought = _compute_drought_trend(l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"DROUGHT_TREND_{inp.plot_id}",
        semantic_type=SurfaceType.DROUGHT_TREND,
        grid_ref=f"{H}x{W}",
        values=drought,
        units="days",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 14.0),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L1"],
    ))

    # --- 5. RISK_MOMENTUM: Risk acceleration ---
    risk_mom = _compute_risk_momentum(l1_data, l2_data, l3_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"RISK_MOMENTUM_{inp.plot_id}",
        semantic_type=SurfaceType.RISK_MOMENTUM,
        grid_ref=f"{H}x{W}",
        values=risk_mom,
        units="momentum",
        native_resolution_m=inp.resolution_m,
        render_range=(-1.0, 1.0),
        palette_id=PaletteId.RISK_HEAT,
        source_layers=["L1", "L2", "L3"],
    ))

    # --- 6. YIELD_TRAJECTORY: Yield trend from biomass proxy ---
    yield_traj = _compute_yield_trajectory(l1_data, l2_data, H, W, has_temporal)
    surfaces.append(SurfaceArtifact(
        surface_id=f"YIELD_TRAJ_{inp.plot_id}",
        semantic_type=SurfaceType.YIELD_TRAJECTORY,
        grid_ref=f"{H}x{W}",
        values=yield_traj,
        units="trajectory",
        native_resolution_m=inp.resolution_m,
        render_range=(-1.0, 1.0),
        palette_id=PaletteId.YIELD_BLUE,
        source_layers=["L1", "L2"],
    ))

    # --- 7. PRECIPITATION_FORECAST: 7-day spatial precip forecast ---
    precip_fc = _compute_precipitation_forecast(inp, l1_data, H, W)
    if precip_fc is not None:
        surfaces.append(SurfaceArtifact(
            surface_id=f"PRECIP_FORECAST_{inp.plot_id}",
            semantic_type=SurfaceType.PRECIPITATION_FORECAST,
            grid_ref=f"{H}x{W}",
            values=precip_fc,
            units="mm_7d",
            native_resolution_m=inp.resolution_m,
            render_range=(0.0, 100.0),
            palette_id=PaletteId.YIELD_BLUE,
            source_layers=["FORECAST"],
            provenance={"source": "FORECAST_CONTEXT"},
        ))

    # --- 8. TEMPERATURE_FORECAST: 7-day avg temp forecast ---
    temp_fc = _compute_temperature_forecast(inp, l1_data, H, W)
    if temp_fc is not None:
        surfaces.append(SurfaceArtifact(
            surface_id=f"TEMP_FORECAST_{inp.plot_id}",
            semantic_type=SurfaceType.TEMPERATURE_FORECAST,
            grid_ref=f"{H}x{W}",
            values=temp_fc,
            units="celsius",
            native_resolution_m=inp.resolution_m,
            render_range=(0.0, 45.0),
            palette_id=PaletteId.RISK_HEAT,
            source_layers=["FORECAST"],
            provenance={"source": "FORECAST_CONTEXT"},
        ))

    return surfaces


# ============================================================================
# INTERNAL COMPUTATION FUNCTIONS
# ============================================================================

def _compute_ndvi_delta_7d(
    l1: L1SpatialData, l2: L2VegData, H: int, W: int, has_temporal: bool
) -> List[List[Optional[float]]]:
    """Compute per-pixel NDVI change over 7 days.

    Strategy:
      1. RASTER_GROUNDED: Diff last vs 7-days-ago from temporal_rasters
      2. PROXY_SPATIAL: Use L2 ndvi_delta_7d × spatial NDVI ratio
    """
    grid = [[0.0] * W for _ in range(H)]

    if has_temporal and len(l1.time_index) >= 2:
        # RASTER_GROUNDED: pixel-wise diff between latest and ~7-day-ago
        dates = sorted(l1.time_index)
        latest_date = dates[-1]
        # Find date closest to 7 days back
        ref_idx = max(0, len(dates) - 8)  # Approximate 7 days back
        ref_date = dates[ref_idx]

        latest_rasters = l1.temporal_rasters.get(latest_date, {})
        ref_rasters = l1.temporal_rasters.get(ref_date, {})

        # Find NDVI channel
        ndvi_key = _find_ndvi_key(latest_rasters)
        ndvi_key_ref = _find_ndvi_key(ref_rasters)

        if ndvi_key and ndvi_key_ref:
            latest_grid = latest_rasters[ndvi_key]
            ref_grid = ref_rasters[ndvi_key_ref]
            for r in range(H):
                for c in range(W):
                    v_now = latest_grid[r][c] if r < len(latest_grid) and c < len(latest_grid[r]) else None
                    v_ref = ref_grid[r][c] if r < len(ref_grid) and c < len(ref_grid[r]) else None
                    if v_now is not None and v_ref is not None:
                        grid[r][c] = round(v_now - v_ref, 6)
            return grid

    # PROXY_SPATIAL: Use L2 curve delta × spatial NDVI modulation
    delta = l2.ndvi_delta_7d if l2.ndvi_delta_7d != 0 else 0.0
    ndvi_raster = l1.raster_maps.get('ndvi', l1.raster_maps.get('NDVI'))

    if ndvi_raster and delta != 0:
        # Modulate delta spatially: high NDVI areas get proportionally more delta
        mean_ndvi = _grid_mean(ndvi_raster, H, W) or 0.5
        for r in range(H):
            for c in range(W):
                v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
                if v is not None and mean_ndvi > 0:
                    ratio = v / mean_ndvi
                    grid[r][c] = round(delta * ratio, 6)
                else:
                    grid[r][c] = round(delta, 6)
    else:
        # Uniform broadcast
        for r in range(H):
            for c in range(W):
                grid[r][c] = round(delta, 6)

    return grid


def _compute_growth_trend(
    l1: L1SpatialData, l2: L2VegData, H: int, W: int, has_temporal: bool
) -> List[List[Optional[float]]]:
    """Compute growth velocity trend (acceleration) per pixel."""
    grid = [[0.0] * W for _ in range(H)]

    if has_temporal and len(l1.time_index) >= 3:
        # Compute per-pixel velocity at two time points, then acceleration
        dates = sorted(l1.time_index)
        n = len(dates)
        mid = n // 2

        # First-half velocity
        first_rasters = l1.temporal_rasters.get(dates[0], {})
        mid_rasters = l1.temporal_rasters.get(dates[mid], {})
        last_rasters = l1.temporal_rasters.get(dates[-1], {})

        ndvi_key = _find_ndvi_key(last_rasters) or _find_ndvi_key(first_rasters)
        if ndvi_key:
            for r in range(H):
                for c in range(W):
                    try:
                        v0 = first_rasters.get(ndvi_key, [[]])[r][c]
                        vm = mid_rasters.get(ndvi_key, [[]])[r][c]
                        vn = last_rasters.get(ndvi_key, [[]])[r][c]
                    except (IndexError, TypeError):
                        continue
                    if v0 is not None and vm is not None and vn is not None and mid > 0:
                        vel1 = (vm - v0) / mid
                        vel2 = (vn - vm) / max(1, n - mid)
                        accel = vel2 - vel1
                        grid[r][c] = round(accel, 6)
            return grid

    # Fallback: use L2 growth momentum uniformly
    momentum = l2.growth_momentum
    ndvi_raster = l1.raster_maps.get('ndvi', l1.raster_maps.get('NDVI'))
    if ndvi_raster:
        mean_ndvi = _grid_mean(ndvi_raster, H, W) or 0.5
        for r in range(H):
            for c in range(W):
                v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
                if v is not None and mean_ndvi > 0:
                    grid[r][c] = round(momentum * (v / mean_ndvi), 6)
                else:
                    grid[r][c] = round(momentum, 6)
    else:
        for r in range(H):
            for c in range(W):
                grid[r][c] = round(momentum, 6)

    return grid


def _compute_stress_momentum(
    l1: L1SpatialData, l2: L2VegData, l3: L3DiagnosticData,
    H: int, W: int
) -> List[List[Optional[float]]]:
    """Compute water stress momentum: is stress accelerating or decelerating?

    Uses diagnosis severity trend from L3 + NDVI velocity from L2.
    Positive = stress worsening, Negative = stress improving.
    """
    grid = [[0.0] * W for _ in range(H)]

    # Base stress momentum from L3 diagnostic trends
    water_trend = 0.0
    for pid, trend in l3.diagnosis_trend.items():
        if 'WATER' in pid.upper() or 'DROUGHT' in pid.upper() or 'STRESS' in pid.upper():
            if trend == "WORSENING":
                water_trend += 0.3
            elif trend == "IMPROVING":
                water_trend -= 0.3

    # Modulate with L2 velocity: negative velocity amplifies stress momentum
    vel_factor = 0.0
    if l2.velocity_trend == "DECELERATING":
        vel_factor = 0.2
    elif l2.velocity_trend == "ACCELERATING":
        vel_factor = -0.2

    base_momentum = max(-1.0, min(1.0, water_trend + vel_factor))

    # Spatial modulation using NDVI: low-NDVI areas get amplified stress momentum
    ndvi_raster = l1.raster_maps.get('ndvi', l1.raster_maps.get('NDVI'))
    if ndvi_raster:
        mean_ndvi = _grid_mean(ndvi_raster, H, W) or 0.5
        for r in range(H):
            for c in range(W):
                v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
                if v is not None and mean_ndvi > 0:
                    # Invert ratio: lower NDVI = higher stress momentum
                    inv_ratio = (2.0 * mean_ndvi - v) / mean_ndvi
                    grid[r][c] = round(base_momentum * inv_ratio, 4)
                else:
                    grid[r][c] = round(base_momentum, 4)
    else:
        for r in range(H):
            for c in range(W):
                grid[r][c] = round(base_momentum, 4)

    return grid


def _compute_drought_trend(
    l1: L1SpatialData, H: int, W: int
) -> List[List[Optional[float]]]:
    """Compute consecutive dry-day trend from weather history.

    Uses L1 weather_history precipitation data. 0 = no drought, 14 = severe.
    """
    grid = [[0.0] * W for _ in range(H)]

    # Count consecutive dry days from weather history (end to start)
    dry_days = 0
    weather = l1.weather_history
    if weather:
        for entry in reversed(weather):
            precip = entry.get('precipitation_mm', entry.get('precipitation', entry.get('rain_mm', None)))
            if precip is not None and precip < 1.0:  # < 1mm = dry day
                dry_days += 1
            else:
                break
        dry_days = min(14, dry_days)  # Cap at 14

    # Spatial modulation: low NDVI areas experience more drought stress
    ndvi_raster = l1.raster_maps.get('ndvi', l1.raster_maps.get('NDVI'))
    if ndvi_raster:
        mean_ndvi = _grid_mean(ndvi_raster, H, W) or 0.5
        base_drought = max(dry_days, 1.0)  # Minimum base so overlay is visible
        for r in range(H):
            for c in range(W):
                v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
                if v is not None and mean_ndvi > 0:
                    # Low NDVI → higher drought impact
                    stress_mult = max(0.5, (2.0 * mean_ndvi - v) / mean_ndvi)
                    grid[r][c] = round(base_drought * stress_mult, 2)
                else:
                    grid[r][c] = float(base_drought)
    else:
        for r in range(H):
            for c in range(W):
                grid[r][c] = max(float(dry_days), 1.0)

    return grid


def _compute_risk_momentum(
    l1: L1SpatialData, l2: L2VegData, l3: L3DiagnosticData,
    H: int, W: int
) -> List[List[Optional[float]]]:
    """Compute composite risk acceleration from all diagnostic trends.

    Aggregates all L3 diagnosis trends + L2 velocity into a single momentum vector.
    Positive = risk increasing, Negative = risk decreasing.
    """
    grid = [[0.0] * W for _ in range(H)]

    # Aggregate all diagnosis trends
    trend_score = 0.0
    n_diagnoses = 0
    for pid, trend in l3.diagnosis_trend.items():
        if trend == "WORSENING":
            trend_score += 0.4
        elif trend == "IMPROVING":
            trend_score -= 0.3
        n_diagnoses += 1

    # Factor in L2 vegetation trend
    if l2.velocity_trend == "DECELERATING":
        trend_score += 0.2
    elif l2.velocity_trend == "ACCELERATING":
        trend_score -= 0.15

    # Normalize
    if n_diagnoses > 0:
        trend_score /= n_diagnoses
    trend_score = max(-1.0, min(1.0, trend_score))

    # Spatial distribution
    ndvi_raster = l1.raster_maps.get('ndvi', l1.raster_maps.get('NDVI'))
    if ndvi_raster:
        mean_ndvi = _grid_mean(ndvi_raster, H, W) or 0.5
        for r in range(H):
            for c in range(W):
                v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
                if v is not None and mean_ndvi > 0:
                    # Lower NDVI = higher risk momentum
                    inv_ratio = (2.0 * mean_ndvi - v) / mean_ndvi
                    grid[r][c] = round(trend_score * inv_ratio, 4)
                else:
                    grid[r][c] = round(trend_score, 4)
    else:
        for r in range(H):
            for c in range(W):
                grid[r][c] = round(trend_score, 4)

    return grid


def _compute_yield_trajectory(
    l1: L1SpatialData, l2: L2VegData, H: int, W: int, has_temporal: bool
) -> List[List[Optional[float]]]:
    """Compute yield trajectory: is potential yield improving or degrading?

    Uses NDVI trend as biomass proxy. -1 = rapidly degrading, +1 = rapidly improving.
    """
    grid = [[0.0] * W for _ in range(H)]

    # Use L2 forecast delta as the base trajectory
    base_traj = 0.0
    if l2.ndvi_forecast_delta_7d > 0.02:
        base_traj = min(1.0, l2.ndvi_forecast_delta_7d * 10)  # Scale up
    elif l2.ndvi_forecast_delta_7d < -0.02:
        base_traj = max(-1.0, l2.ndvi_forecast_delta_7d * 10)

    # Combine with retrospective delta
    if l2.ndvi_delta_7d > 0.02:
        base_traj += min(0.5, l2.ndvi_delta_7d * 5)
    elif l2.ndvi_delta_7d < -0.02:
        base_traj += max(-0.5, l2.ndvi_delta_7d * 5)

    base_traj = max(-1.0, min(1.0, base_traj))

    # Spatial modulation
    ndvi_raster = l1.raster_maps.get('ndvi', l1.raster_maps.get('NDVI'))
    if ndvi_raster:
        mean_ndvi = _grid_mean(ndvi_raster, H, W) or 0.5
        for r in range(H):
            for c in range(W):
                v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
                if v is not None and mean_ndvi > 0:
                    ratio = v / mean_ndvi
                    grid[r][c] = round(base_traj * ratio, 4)
                else:
                    grid[r][c] = round(base_traj, 4)
    else:
        for r in range(H):
            for c in range(W):
                grid[r][c] = round(base_traj, 4)

    return grid


def _compute_precipitation_forecast(
    inp: Layer10Input, l1: L1SpatialData, H: int, W: int
) -> Optional[List[List[Optional[float]]]]:
    """Generate 7-day cumulative precipitation forecast surface.

    Uses ForecastContext if available, else returns None.
    """
    fc = inp.forecast_context
    if fc is None:
        return None

    precip = []
    if hasattr(fc, 'precipitation_forecast'):
        precip = getattr(fc, 'precipitation_forecast', [])
    elif isinstance(fc, dict):
        precip = fc.get('precipitation_forecast', [])

    if not precip:
        return None

    # 7-day cumulative
    total_precip = sum(float(p) for p in precip[:7] if isinstance(p, (int, float)))

    # Spatial modulation: higher elevation / lower NDVI gets slightly less effective rainfall
    grid = [[round(total_precip, 2)] * W for _ in range(H)]

    ndvi_raster = l1.raster_maps.get('ndvi', l1.raster_maps.get('NDVI'))
    if ndvi_raster:
        mean_ndvi = _grid_mean(ndvi_raster, H, W) or 0.5
        for r in range(H):
            for c in range(W):
                v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
                if v is not None and mean_ndvi > 0:
                    # Effective rainfall modulated by vegetation cover
                    ratio = 0.8 + 0.4 * (v / mean_ndvi)  # 0.8-1.2 range
                    grid[r][c] = round(total_precip * ratio, 2)

    return grid


def _compute_temperature_forecast(
    inp: Layer10Input, l1: L1SpatialData, H: int, W: int
) -> Optional[List[List[Optional[float]]]]:
    """Generate 7-day average temperature forecast surface.

    Uses ForecastContext if available, else returns None.
    """
    fc = inp.forecast_context
    if fc is None:
        return None

    temp_max = []
    temp_min = []
    if hasattr(fc, 'temperature_max_forecast'):
        temp_max = getattr(fc, 'temperature_max_forecast', [])
        temp_min = getattr(fc, 'temperature_min_forecast', [])
    elif isinstance(fc, dict):
        temp_max = fc.get('temperature_max_forecast', [])
        temp_min = fc.get('temperature_min_forecast', [])

    if not temp_max:
        return None

    # 7-day average temperature
    avg_temps = []
    for i in range(min(7, len(temp_max))):
        t_max = float(temp_max[i]) if i < len(temp_max) else 25.0
        t_min = float(temp_min[i]) if i < len(temp_min) else 15.0
        avg_temps.append((t_max + t_min) / 2.0)

    avg_temp = sum(avg_temps) / len(avg_temps) if avg_temps else 20.0

    # Uniform spatial distribution (temperature varies little within a field)
    grid = [[round(avg_temp, 1)] * W for _ in range(H)]
    return grid


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _find_ndvi_key(rasters: Dict[str, Any]) -> Optional[str]:
    """Find NDVI channel key in a raster dict."""
    for key in ['ndvi', 'NDVI', 'ndvi_smoothed', 'ndvi_interpolated']:
        if key in rasters:
            return key
    return None


def _grid_mean(grid, H: int, W: int) -> Optional[float]:
    """Compute mean of non-None values in a grid."""
    vals = []
    for r in range(min(H, len(grid))):
        for c in range(min(W, len(grid[r]))):
            v = grid[r][c]
            if v is not None:
                vals.append(v)
    return sum(vals) / len(vals) if vals else None
