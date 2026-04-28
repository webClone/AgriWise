"""
Wind Intelligence Module.

Circular statistics, wind feature computation, and threshold evaluation.
Wind direction NEVER uses arithmetic mean.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from layer0.environment.weather.forecast_schemas import (
    ForecastHourlyRecord,
    ForecastRiskConfig,
    deg_to_compass_sector,
    ms_to_kmh,
)


# ---------------------------------------------------------------------------
# Circular Statistics
# ---------------------------------------------------------------------------

def circular_mean_direction(degrees: List[float]) -> float:
    """Compute circular mean of wind directions.

    CRITICAL: 350° and 10° average to 0°, NOT 180°.
    Uses vector-average approach.
    """
    if not degrees:
        return 0.0

    sin_sum = sum(math.sin(math.radians(d)) for d in degrees)
    cos_sum = sum(math.cos(math.radians(d)) for d in degrees)
    mean = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
    return round(mean, 1)


def circular_std_direction(degrees: List[float]) -> float:
    """Compute circular standard deviation of wind directions."""
    if len(degrees) < 2:
        return 0.0

    n = len(degrees)
    sin_sum = sum(math.sin(math.radians(d)) for d in degrees)
    cos_sum = sum(math.cos(math.radians(d)) for d in degrees)
    r_bar = math.sqrt(sin_sum**2 + cos_sum**2) / n

    # Circular std deviation
    if r_bar >= 1.0:
        return 0.0
    std = math.degrees(math.sqrt(-2.0 * math.log(r_bar)))
    return round(std, 1)


def dominant_sector(degrees: List[float], bins: int = 8) -> str:
    """Determine dominant wind sector from a list of directions."""
    if not degrees:
        return "CALM"

    sectors = [deg_to_compass_sector(d, bins) for d in degrees]
    counts: Dict[str, int] = {}
    for s in sectors:
        counts[s] = counts.get(s, 0) + 1
    return max(counts, key=counts.get)


# ---------------------------------------------------------------------------
# Wind Feature Computation
# ---------------------------------------------------------------------------

def compute_daily_wind_features(
    hourly_records: List[ForecastHourlyRecord],
    config: Optional[ForecastRiskConfig] = None,
) -> Dict[str, Any]:
    """Compute daily wind features from hourly forecast records.

    All records should be for the same date.
    """
    if config is None:
        config = ForecastRiskConfig()

    if not hourly_records:
        return {}

    speeds = [r.wind_speed_10m_ms for r in hourly_records if r.wind_speed_10m_ms is not None]
    gusts = [r.wind_gusts_10m_ms for r in hourly_records if r.wind_gusts_10m_ms is not None]
    directions = [r.wind_direction_10m_deg for r in hourly_records if r.wind_direction_10m_deg is not None]

    if not speeds:
        return {}

    wind_mean = round(sum(speeds) / len(speeds), 2)
    wind_max = max(speeds)
    gust_max = max(gusts) if gusts else 0.0

    # Wind run (km/day)
    wind_run_km = round(sum(s * 3.6 for s in speeds), 2)  # m/s × 3600s = m/h, sum over hours = m, /1000 = km... but per hour so × 1
    wind_run_km = round(sum(ms_to_kmh(s) for s in speeds), 2)  # each hour contributes km/h × 1h = km

    # Direction features
    dominant_dir = circular_mean_direction(directions) if directions else 0.0
    dir_variability = circular_std_direction(directions) if directions else 0.0

    # Threshold hours
    gust_hours_above = sum(1 for g in gusts if g > config.spray_gust_max_ms)
    high_wind_hours = sum(1 for s in speeds if s > config.high_wind_ms)

    # Calm night hours (hours 20-06 local with wind < 1.5 m/s)
    calm_night_hours = 0
    for rec in hourly_records:
        hour_of_day = rec.lead_hour % 24
        if (hour_of_day >= 20 or hour_of_day <= 6):
            if rec.wind_speed_10m_ms is not None and rec.wind_speed_10m_ms < config.frost_calm_wind_ms:
                calm_night_hours += 1

    # Hot dry wind hours
    hot_dry_wind_hours = _count_hot_dry_wind_hours(hourly_records, config)

    return {
        "wind_mean_10m_ms": wind_mean,
        "wind_max_10m_ms": wind_max,
        "gust_max_10m_ms": gust_max,
        "wind_mean_kmh": ms_to_kmh(wind_mean),
        "wind_max_kmh": ms_to_kmh(wind_max),
        "gust_max_kmh": ms_to_kmh(gust_max),
        "wind_run_km_per_day": wind_run_km,
        "dominant_wind_direction_deg": dominant_dir,
        "dominant_wind_sector": dominant_sector(directions) if directions else "CALM",
        "wind_direction_variability_deg": dir_variability,
        "gust_hours_above_threshold": gust_hours_above,
        "high_wind_hours": high_wind_hours,
        "calm_night_hours": calm_night_hours,
        "hot_dry_wind_hours": hot_dry_wind_hours,
    }


def _count_hot_dry_wind_hours(
    hourly_records: List[ForecastHourlyRecord],
    config: ForecastRiskConfig,
) -> int:
    """Count hours meeting hot dry wind criteria.

    Hot dry wind: temp > threshold AND RH < threshold AND wind > threshold.
    """
    count = 0
    for rec in hourly_records:
        temp = rec.temperature_2m_c
        rh = rec.relative_humidity_2m_pct
        wind = rec.wind_speed_10m_ms

        if temp is None or rh is None or wind is None:
            continue

        if (temp > config.hot_dry_wind_temp_c and
                rh < config.hot_dry_wind_rh_pct and
                wind > config.hot_dry_wind_speed_ms):
            count += 1

    return count


# ---------------------------------------------------------------------------
# Wind Threshold Checks
# ---------------------------------------------------------------------------

def check_spray_drift_risk(
    wind_speed_ms: float,
    gust_ms: Optional[float] = None,
    config: Optional[ForecastRiskConfig] = None,
) -> bool:
    """Check if wind conditions are risky for spraying."""
    if config is None:
        config = ForecastRiskConfig()
    if wind_speed_ms > config.spray_wind_max_ms:
        return True
    if gust_ms is not None and gust_ms > config.spray_gust_max_ms:
        return True
    return False


def check_frost_calm_risk(
    tmin: float,
    wind_speed_ms: float,
    cloud_cover_pct: Optional[float] = None,
    config: Optional[ForecastRiskConfig] = None,
) -> bool:
    """Check frost-calm-night risk.

    tmin near 0-2°C AND calm night wind AND clear sky.
    """
    if config is None:
        config = ForecastRiskConfig()
    if tmin > config.frost_threshold_c:
        return False
    if wind_speed_ms > config.frost_calm_wind_ms:
        return False
    if cloud_cover_pct is not None and cloud_cover_pct > 50:
        return False
    return True
