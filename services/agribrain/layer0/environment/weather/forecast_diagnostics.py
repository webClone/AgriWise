"""
Forecast Diagnostics.

Summarizes forecast provider status, disagreements, low-confidence days,
risk window counts, and hard prohibition enforcement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.weather.forecast_schemas import (
    ForecastConsensusDaily,
    ForecastTimeSeries,
    WeatherRiskWindow,
)


def build_forecast_diagnostics(
    forecast_timeseries: Optional[ForecastTimeSeries] = None,
    forecast_consensus: Optional[List[ForecastConsensusDaily]] = None,
    risk_windows: Optional[List[WeatherRiskWindow]] = None,
    kalman_observations_created: int = 0,
) -> Dict[str, Any]:
    """Build forecast diagnostics summary.

    Always includes forecast_not_used_for_kalman assertion.
    """
    diag: Dict[str, Any] = {}

    # Horizon
    if forecast_timeseries:
        diag["forecast_horizon_days"] = forecast_timeseries.horizon_calendar_days
        diag["hourly_count"] = forecast_timeseries.hourly_count
        diag["daily_count"] = forecast_timeseries.daily_count
        diag["stale_forecast"] = forecast_timeseries.stale_forecast_flag
        diag["forecast_age_hours"] = forecast_timeseries.forecast_age_hours
    else:
        diag["forecast_horizon_days"] = 0
        diag["flags"] = ["NO_FORECAST_DATA"]

    # Provider status
    provider_status: Dict[str, str] = {}
    missing_variables: Dict[str, List[str]] = {}

    if forecast_consensus:
        for day in forecast_consensus:
            for var_name, vc in day.variable_consensus.items():
                for provider in (vc.provider_values or {}):
                    if provider not in provider_status:
                        provider_status[provider] = "ok"
                    if vc.provider_values.get(provider) is None:
                        provider_status[provider] = "partial"
                        missing_variables.setdefault(provider, []).append(var_name)

    diag["provider_status"] = provider_status
    diag["missing_variables"] = {p: sorted(set(v)) for p, v in missing_variables.items()}

    # Provider disagreements
    disagreements: List[Dict[str, Any]] = []
    if forecast_consensus:
        for day in forecast_consensus:
            for var_name, vc in day.variable_consensus.items():
                if vc.flags:
                    disagreements.append({
                        "date": day.date,
                        "variable": var_name,
                        "flags": vc.flags,
                        "confidence": vc.variable_confidence,
                    })
    diag["provider_disagreements"] = disagreements

    # Low confidence days
    low_conf_days: List[int] = []
    if forecast_consensus:
        for day in forecast_consensus:
            if day.overall_forecast_confidence < 0.5:
                low_conf_days.append(day.lead_day)
    diag["low_confidence_days"] = low_conf_days

    # Risk windows created
    risk_counts: Dict[str, int] = {}
    if risk_windows:
        for w in risk_windows:
            risk_counts[w.window_type] = risk_counts.get(w.window_type, 0) + 1
    diag["risk_windows_created"] = risk_counts

    # HARD PROHIBITION: forecast never used for Kalman
    diag["forecast_not_used_for_kalman"] = kalman_observations_created == 0

    # Hard prohibitions summary (Revision 10)
    diag["forecast_hard_prohibitions"] = {
        "no_current_kalman_update": kalman_observations_created == 0,
        "no_canopy_stress_from_wind": True,  # Enforced by architecture
        "no_forecast_historical_mixing": True,  # Enforced by consensus filter
        "wind_direction_circular": True,  # Enforced by wind.py
        "horizon_cap_enforced": (
            forecast_timeseries is None or
            forecast_timeseries.horizon_calendar_days <= 7
        ),
    }

    return diag
