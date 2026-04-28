"""
Forecast Derived Features.

Computes 7-day summary and per-day agronomic summaries from forecast consensus.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.weather.forecast_schemas import (
    Forecast7DaySummary,
    ForecastConsensusDaily,
    ForecastDailyAgSummary,
    ForecastRiskConfig,
    ForecastVariableConsensus,
)
from layer0.environment.weather.derived import compute_gdd, compute_water_balance


def compute_forecast_7day_summary(
    consensus_days: List[ForecastConsensusDaily],
    wind_features_by_day: Optional[Dict[str, Dict[str, Any]]] = None,
    config: Optional[ForecastRiskConfig] = None,
) -> Forecast7DaySummary:
    """Compute 7-day aggregated forecast summary.

    Args:
        consensus_days: list of ForecastConsensusDaily (one per day)
        wind_features_by_day: {date: wind_features_dict} from wind.py
        config: risk configuration
    """
    if config is None:
        config = ForecastRiskConfig()

    if not consensus_days:
        return Forecast7DaySummary()

    total_precip = 0.0
    total_et0 = 0.0
    total_gdd = 0.0
    max_vpd = 0.0
    vpd_values: List[float] = []
    confidences: List[float] = []
    rain_events = 0

    heat_hours = 0
    frost_hours = 0
    high_wind_hours = 0
    hot_dry_wind_hours = 0
    sprayable_hours = 0

    for day in consensus_days:
        # Extract consensus values
        precip = _get_selected(day, "precipitation") or 0.0
        et0 = _get_selected(day, "et0") or 0.0
        tmin = _get_selected(day, "tmin")
        tmax = _get_selected(day, "tmax")
        vpd = _get_selected(day, "vpd_max")

        total_precip += precip
        total_et0 += et0

        if tmin is not None and tmax is not None:
            total_gdd += compute_gdd(tmin, tmax, t_base=5.0)

        if vpd is not None:
            vpd_values.append(vpd)
            if vpd > max_vpd:
                max_vpd = vpd

        if precip >= 1.0:
            rain_events += 1

        confidences.append(day.overall_forecast_confidence)

        # Wind-based hours from wind features
        date = day.date
        if wind_features_by_day and date in wind_features_by_day:
            wf = wind_features_by_day[date]
            high_wind_hours += wf.get("high_wind_hours", 0)
            hot_dry_wind_hours += wf.get("hot_dry_wind_hours", 0)

            # Estimate sprayable hours (24 minus wind-bad hours)
            bad_hours = wf.get("gust_hours_above_threshold", 0)
            sprayable_hours += max(0, 24 - bad_hours)
        else:
            # Estimate from daily data: assume 12 sprayable if no wind data
            sprayable_hours += 12

        # Heat/frost from daily temps
        if tmax is not None and tmax > config.heat_stress_temp_c:
            heat_hours += 8  # Approximate daytime hours
        if tmin is not None and tmin <= config.frost_threshold_c:
            frost_hours += 6  # Approximate nighttime hours

    water_balance = round(total_precip - total_et0, 2)

    # Irrigation need score: higher when water balance is more negative
    irrigation_need = 0.0
    if water_balance < -20:
        irrigation_need = min(1.0, abs(water_balance) / 50.0)

    # Drydown score: how quickly the field might dry
    drydown_score = 0.0
    if total_precip < 5.0 and total_et0 > 20.0:
        drydown_score = min(1.0, total_et0 / 40.0)

    return Forecast7DaySummary(
        forecast_7d_precip_sum_mm=round(total_precip, 2),
        forecast_7d_et0_sum_mm=round(total_et0, 2),
        forecast_7d_water_balance_mm=water_balance,
        forecast_7d_gdd=round(total_gdd, 2),
        forecast_max_vpd_kpa=round(max_vpd, 2),
        forecast_mean_vpd_kpa=round(sum(vpd_values) / len(vpd_values), 2) if vpd_values else 0.0,
        forecast_heat_stress_hours=heat_hours,
        forecast_frost_hours=frost_hours,
        forecast_high_wind_hours=high_wind_hours,
        forecast_hot_dry_wind_hours=hot_dry_wind_hours,
        forecast_sprayable_hours=sprayable_hours,
        forecast_irrigation_need_score=round(irrigation_need, 2),
        forecast_rain_event_count=rain_events,
        forecast_drydown_score=round(drydown_score, 2),
        forecast_confidence_mean=round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        forecast_confidence_min=round(min(confidences), 4) if confidences else 0.0,
    )


def compute_forecast_daily_ag_summaries(
    consensus_days: List[ForecastConsensusDaily],
    wind_features_by_day: Optional[Dict[str, Dict[str, Any]]] = None,
    config: Optional[ForecastRiskConfig] = None,
) -> List[ForecastDailyAgSummary]:
    """Compute per-day agronomic summaries from forecast."""
    if config is None:
        config = ForecastRiskConfig()

    summaries = []
    for day in consensus_days:
        precip = _get_selected(day, "precipitation") or 0.0
        et0 = _get_selected(day, "et0") or 0.0
        tmin = _get_selected(day, "tmin")
        tmax = _get_selected(day, "tmax")
        vpd = _get_selected(day, "vpd_max") or 0.0
        wind_max = _get_selected(day, "wind_speed")
        gust_max = _get_selected(day, "wind_gusts")

        gdd = compute_gdd(tmin, tmax, t_base=5.0) if tmin is not None and tmax is not None else 0.0
        water_balance = compute_water_balance(precip, et0)

        # Risk flags
        risk_flags: List[str] = []
        if tmax is not None and tmax > config.heat_stress_temp_c:
            risk_flags.append("HEAT_STRESS")
        if tmin is not None and tmin <= config.frost_threshold_c:
            risk_flags.append("FROST_RISK")
        if wind_max is not None and wind_max > config.high_wind_ms:
            risk_flags.append("HIGH_WIND")
        if gust_max is not None and gust_max > config.gust_damage_ms:
            risk_flags.append("GUST_DAMAGE")

        # Spray window best hours (estimate)
        spray_hours = 12
        if wind_max is not None and wind_max > config.spray_wind_max_ms:
            spray_hours = max(0, spray_hours - 6)
        if precip > config.spray_rain_amount_threshold_mm:
            spray_hours = max(0, spray_hours - 6)

        # Wind features
        wf = {}
        if wind_features_by_day and day.date in wind_features_by_day:
            wf = wind_features_by_day[day.date]

        # Irrigation window score
        irrigation_score = 0.5
        if water_balance < -5.0:
            irrigation_score = min(1.0, abs(water_balance) / 10.0)

        # Field access (rough estimate)
        field_access = 0.8
        if precip > 10.0:
            field_access = 0.2
        elif precip > 5.0:
            field_access = 0.5

        summaries.append(ForecastDailyAgSummary(
            date=day.date,
            lead_day=day.lead_day,
            precip_sum_mm=precip,
            et0_sum_mm=et0,
            water_balance_mm=water_balance,
            gdd=gdd,
            vpd_max=vpd,
            tmax=tmax,
            tmin=tmin,
            wind_max=wind_max,
            gust_max=gust_max,
            spray_window_best_hours=spray_hours,
            irrigation_window_score=round(irrigation_score, 2),
            field_access_score=round(field_access, 2),
            risk_flags=risk_flags,
            variable_confidence=day.overall_forecast_confidence,
            decision_confidence=day.overall_forecast_confidence,
        ))

    return summaries


def _get_selected(day: ForecastConsensusDaily, var: str) -> Optional[float]:
    """Extract selected value from consensus variable."""
    vc = day.variable_consensus.get(var)
    if vc is None:
        return None
    return vc.selected_value
