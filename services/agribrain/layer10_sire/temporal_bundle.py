"""
Temporal Bundle Generator — Build 14-day TemporalBundle from pipeline data
===========================================================================

Assembles the full T-7 → T+7 temporal window from:
  1. L1 temporal rasters (real pixel-level history)
  2. L2 curve projections (forward extrapolation)
  3. ForecastContext (weather forecasts)
  4. Existing surface snapshots (computed by surface engines)

The TemporalBundle is the primary payload for the frontend "Time Peel" mode,
enabling per-pixel time-series scrubbing.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from layer10_sire.schema import (
    TemporalSlice, TemporalBundle, SurfaceType, SurfaceArtifact,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l2_adapter import L2VegData
from layer10_sire.adapters.l3_adapter import L3DiagnosticData


def build_temporal_bundle(
    l1_data: L1SpatialData,
    l2_data: L2VegData,
    l3_data: L3DiagnosticData,
    surfaces: List[SurfaceArtifact],
    reference_date: str = "",
    forecast_context: Any = None,
    H: int = 10,
    W: int = 10,
) -> TemporalBundle:
    """
    Build the full 14-day TemporalBundle from pipeline data.

    Architecture:
      - T-7 to T-1: retrospective slices from L1 temporal rasters
      - T0: current snapshot from computed surfaces
      - T+1 to T+7: forward projections from L2 curve + ForecastContext

    Each slice contains the NDVI (or relevant variable) spatial grid,
    confidence score, and source provenance.
    """
    bundle = TemporalBundle(
        reference_date=reference_date or _today_iso(),
        lookback_days=7,
        lookahead_days=7,
        forecast_source="COMPOSITE",
    )

    slices: List[TemporalSlice] = []

    # Determine T0 date
    t0_date = reference_date or _today_iso()
    if l1_data.time_index:
        t0_date = l1_data.time_index[-1]
    bundle.reference_date = t0_date

    # =========================================================================
    # RETROSPECTIVE SLICES (T-7 to T-1)
    # =========================================================================
    retro_slices = _build_retrospective_slices(
        l1_data, l2_data, t0_date, H, W
    )
    slices.extend(retro_slices)

    # =========================================================================
    # T0 SLICE (current snapshot from computed surfaces)
    # =========================================================================
    t0_slice = _build_t0_slice(surfaces, t0_date, H, W)
    if t0_slice:
        slices.append(t0_slice)

    # =========================================================================
    # FORECAST SLICES (T+1 to T+7)
    # =========================================================================
    forecast_slices = _build_forecast_slices(
        l2_data, forecast_context, t0_date, H, W
    )
    slices.extend(forecast_slices)
    if forecast_slices:
        bundle.forecast_source = _determine_forecast_source(forecast_context, l2_data)

    # =========================================================================
    # TREND SUMMARY
    # =========================================================================
    bundle.trend_summary = _compute_trend_summary(l2_data, l3_data, slices)

    # =========================================================================
    # TEMPORAL QUALITY
    # =========================================================================
    n_real = sum(1 for s in slices if not s.is_forecast)
    n_total = len(slices)
    bundle.temporal_quality = round(n_real / max(1, n_total), 3)

    bundle.slices = slices
    return bundle


# ============================================================================
# RETROSPECTIVE SLICE BUILDER
# ============================================================================

def _build_retrospective_slices(
    l1: L1SpatialData, l2: L2VegData, t0_date: str, H: int, W: int
) -> List[TemporalSlice]:
    """Build T-7 to T-1 slices from L1 temporal rasters or L2 curve."""
    slices = []

    if l1.temporal_rasters and len(l1.time_index) >= 2:
        # RASTER_GROUNDED: Real per-pixel temporal history
        dates = sorted(l1.temporal_rasters.keys())

        # Take up to 7 dates before T0
        t0_idx = len(dates) - 1
        retro_dates = dates[max(0, t0_idx - 7):t0_idx]

        for i, date in enumerate(retro_dates):
            day_offset = -(len(retro_dates) - i)
            date_rasters = l1.temporal_rasters[date]

            # Find NDVI channel
            ndvi_key = _find_ndvi_key(date_rasters)
            if ndvi_key:
                grid = date_rasters[ndvi_key]
                # Compute confidence from temporal metadata
                meta = l1.temporal_metadata.get(date, {})
                cloud_pct = meta.get('cloud_pct', 0.0)
                conf = max(0.3, 1.0 - cloud_pct / 100.0)

                slices.append(TemporalSlice(
                    date=date,
                    day_offset=day_offset,
                    surface_type=SurfaceType.NDVI_CLEAN,
                    values=grid,
                    is_forecast=False,
                    confidence=round(conf, 3),
                    source="L1_TENSOR",
                ))
    else:
        # CURVE_PROXY: Reconstruct from L2 curve fit
        if l2.ndvi_7d_back and len(l2.ndvi_7d_back) >= 2:
            # Use L2 curve values + latest spatial distribution
            ndvi_raster = l1.raster_maps.get('ndvi', l1.raster_maps.get('NDVI'))
            mean_ndvi = _grid_mean(ndvi_raster, H, W) if ndvi_raster else None

            for i, fit_val in enumerate(l2.ndvi_7d_back):
                day_offset = -(len(l2.ndvi_7d_back) - i)
                date = _offset_date(t0_date, day_offset)

                # Spatially modulate the fitted value
                grid = _spatially_modulate(fit_val, ndvi_raster, mean_ndvi, H, W)

                slices.append(TemporalSlice(
                    date=date,
                    day_offset=day_offset,
                    surface_type=SurfaceType.NDVI_CLEAN,
                    values=grid,
                    is_forecast=False,
                    confidence=0.7,  # Curve-fit proxy is less confident
                    source="L2_CURVE",
                ))

    return slices


# ============================================================================
# T0 SLICE BUILDER
# ============================================================================

def _build_t0_slice(
    surfaces: List[SurfaceArtifact], t0_date: str, H: int, W: int
) -> Optional[TemporalSlice]:
    """Build T0 slice from the current NDVI_CLEAN surface."""
    ndvi_surface = next(
        (s for s in surfaces if s.semantic_type == SurfaceType.NDVI_CLEAN), None
    )
    if ndvi_surface:
        return TemporalSlice(
            date=t0_date,
            day_offset=0,
            surface_type=SurfaceType.NDVI_CLEAN,
            values=ndvi_surface.values,
            is_forecast=False,
            confidence=1.0,
            source="PIPELINE_COMPUTED",
        )
    return None


# ============================================================================
# FORECAST SLICE BUILDER
# ============================================================================

def _build_forecast_slices(
    l2: L2VegData, forecast_ctx: Any, t0_date: str, H: int, W: int
) -> List[TemporalSlice]:
    """Build T+1 to T+7 forecast slices from L2 extrapolation + ForecastContext."""
    slices = []

    # Use L2 forward NDVI projection
    if l2.ndvi_7d_forward:
        # Get current NDVI spatial distribution for modulation
        current_val = l2.ndvi_fit[-1] if l2.ndvi_fit else 0.5

        for i, projected_val in enumerate(l2.ndvi_7d_forward):
            day_offset = i + 1
            date = _offset_date(t0_date, day_offset)

            # Confidence degrades with forecast horizon
            conf = max(0.2, 0.85 - 0.08 * i)

            # Apply weather impact if available
            if forecast_ctx:
                weather_mod = _compute_weather_modification(forecast_ctx, i)
                projected_val = max(-0.2, min(1.0, projected_val + weather_mod))

            # Spatially distribute (uniform for forecast)
            grid = [[round(projected_val, 6)] * W for _ in range(H)]

            slices.append(TemporalSlice(
                date=date,
                day_offset=day_offset,
                surface_type=SurfaceType.NDVI_CLEAN,
                values=grid,
                is_forecast=True,
                confidence=round(conf, 3),
                source="L2_EXTRAPOLATION" if not forecast_ctx else "L2_WEATHER_ADJUSTED",
            ))

    elif forecast_ctx:
        # No L2 projection — use weather forecast alone
        for i in range(7):
            day_offset = i + 1
            date = _offset_date(t0_date, day_offset)
            conf = max(0.2, 0.7 - 0.07 * i)

            # Generate weather-only surface (precipitation forecast)
            precip = _get_forecast_precip(forecast_ctx, i)
            if precip is not None:
                grid = [[round(precip, 2)] * W for _ in range(H)]
                slices.append(TemporalSlice(
                    date=date,
                    day_offset=day_offset,
                    surface_type=SurfaceType.PRECIPITATION_FORECAST,
                    values=grid,
                    is_forecast=True,
                    confidence=round(conf, 3),
                    source="FORECAST_API",
                ))

    return slices


# ============================================================================
# TREND SUMMARY
# ============================================================================

def _compute_trend_summary(
    l2: L2VegData, l3: L3DiagnosticData, slices: List[TemporalSlice]
) -> Dict[str, str]:
    """Compute trend summary from temporal data."""
    summary = {}

    # NDVI trend from L2
    if l2.ndvi_delta_7d > 0.02:
        summary["NDVI"] = "IMPROVING"
    elif l2.ndvi_delta_7d < -0.02:
        summary["NDVI"] = "DEGRADING"
    else:
        summary["NDVI"] = "STABLE"

    # Growth velocity trend
    summary["GROWTH_VELOCITY"] = l2.velocity_trend

    # Water stress from L3
    for pid, trend in l3.diagnosis_trend.items():
        if 'WATER' in pid.upper() or 'STRESS' in pid.upper():
            summary["WATER_STRESS"] = trend
            break

    # Risk momentum from L3
    n_worsening = sum(1 for t in l3.diagnosis_trend.values() if t == "WORSENING")
    n_improving = sum(1 for t in l3.diagnosis_trend.values() if t == "IMPROVING")
    if n_worsening > n_improving:
        summary["RISK"] = "INCREASING"
    elif n_improving > n_worsening:
        summary["RISK"] = "DECREASING"
    else:
        summary["RISK"] = "STABLE"

    # Forecast confidence from slice quality
    forecast_slices = [s for s in slices if s.is_forecast]
    if forecast_slices:
        avg_conf = sum(s.confidence for s in forecast_slices) / len(forecast_slices)
        summary["FORECAST_CONFIDENCE"] = (
            "HIGH" if avg_conf > 0.7 else "MODERATE" if avg_conf > 0.4 else "LOW"
        )

    return summary


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _today_iso() -> str:
    """Return today's date as ISO string."""
    return datetime.utcnow().strftime("%Y-%m-%d")


def _offset_date(base_date: str, days: int) -> str:
    """Offset an ISO date string by N days."""
    try:
        dt = datetime.strptime(base_date, "%Y-%m-%d")
        return (dt + timedelta(days=days)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return base_date


def _find_ndvi_key(rasters: Dict[str, Any]) -> Optional[str]:
    """Find NDVI channel key in a raster dict."""
    for key in ['ndvi', 'NDVI', 'ndvi_smoothed', 'ndvi_interpolated']:
        if key in rasters:
            return key
    return None


def _grid_mean(grid, H: int, W: int) -> Optional[float]:
    """Compute mean of non-None values."""
    if grid is None:
        return None
    vals = []
    for r in range(min(H, len(grid))):
        for c in range(min(W, len(grid[r]))):
            v = grid[r][c]
            if v is not None:
                vals.append(v)
    return sum(vals) / len(vals) if vals else None


def _spatially_modulate(
    field_val: float, ndvi_raster, mean_ndvi: Optional[float], H: int, W: int
) -> List[List[Optional[float]]]:
    """Modulate a field-level value spatially using NDVI distribution."""
    grid = [[round(field_val, 6)] * W for _ in range(H)]
    if ndvi_raster and mean_ndvi and mean_ndvi > 0:
        for r in range(min(H, len(ndvi_raster))):
            for c in range(min(W, len(ndvi_raster[r]))):
                v = ndvi_raster[r][c]
                if v is not None:
                    ratio = v / mean_ndvi
                    grid[r][c] = round(field_val * ratio, 6)
    return grid


def _compute_weather_modification(forecast_ctx: Any, day_idx: int) -> float:
    """Compute NDVI modification from weather forecast for a given day.

    Heavy rainfall → slightly positive (hydration), no rain + heat → negative.
    """
    precip = _get_forecast_precip(forecast_ctx, day_idx) or 0.0
    temp_max = _get_forecast_temp_max(forecast_ctx, day_idx) or 30.0

    mod = 0.0
    if precip > 10:
        mod += 0.005  # Rain helps
    elif precip < 1 and temp_max > 35:
        mod -= 0.01  # Drought + heat hurts
    return mod


def _get_forecast_precip(forecast_ctx: Any, day_idx: int) -> Optional[float]:
    """Get precipitation forecast for a given day."""
    if forecast_ctx is None:
        return None
    precip = getattr(forecast_ctx, 'precipitation_forecast', None)
    if precip is None and isinstance(forecast_ctx, dict):
        precip = forecast_ctx.get('precipitation_forecast', [])
    if precip and day_idx < len(precip):
        return float(precip[day_idx])
    return None


def _get_forecast_temp_max(forecast_ctx: Any, day_idx: int) -> Optional[float]:
    """Get max temperature forecast for a given day."""
    if forecast_ctx is None:
        return None
    temps = getattr(forecast_ctx, 'temperature_max_forecast', None)
    if temps is None and isinstance(forecast_ctx, dict):
        temps = forecast_ctx.get('temperature_max_forecast', [])
    if temps and day_idx < len(temps):
        return float(temps[day_idx])
    return None


def _determine_forecast_source(forecast_ctx: Any, l2: L2VegData) -> str:
    """Determine the forecast source for provenance."""
    if forecast_ctx:
        src = getattr(forecast_ctx, 'forecast_source', '')
        if src:
            return f"L2_CURVE + {src}"
        return "L2_CURVE + WEATHER_API"
    if l2.ndvi_7d_forward:
        return "L2_EXTRAPOLATION"
    return "NONE"
