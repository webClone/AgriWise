"""
Forecast Packet Emission.

V1.1 packet types for forecast intelligence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.weather.forecast_schemas import (
    Forecast7DaySummary,
    ForecastConsensusDaily,
    ForecastProcessForcing,
    ForecastTimeSeries,
    WeatherRiskWindow,
)


# Packet type constants
WEATHER_FORECAST_7D = "WEATHER_FORECAST_7D"
WIND_FORECAST_7D = "WIND_FORECAST_7D"
WEATHER_FORECAST_CONFIDENCE = "WEATHER_FORECAST_CONFIDENCE"
WEATHER_RISK_WINDOWS = "WEATHER_RISK_WINDOWS"
WEATHER_FORECAST_DERIVED_FEATURES = "WEATHER_FORECAST_DERIVED_FEATURES"
FORECAST_PROCESS_FORCING = "FORECAST_PROCESS_FORCING"
CHIRPS_RAINFALL_BASELINE = "CHIRPS_RAINFALL_BASELINE"
ERA5LAND_CLIMATE_BASELINE = "ERA5LAND_CLIMATE_BASELINE"
NASA_POWER_AGROCLIMATE_FALLBACK = "NASA_POWER_AGROCLIMATE_FALLBACK"


def emit_forecast_packets(
    forecast_timeseries: Optional[ForecastTimeSeries] = None,
    forecast_consensus: Optional[List[ForecastConsensusDaily]] = None,
    forecast_derived: Optional[Forecast7DaySummary] = None,
    risk_windows: Optional[List[WeatherRiskWindow]] = None,
    forecast_forcing: Optional[List[ForecastProcessForcing]] = None,
    wind_features_by_day: Optional[Dict[str, Dict[str, Any]]] = None,
    forecast_diagnostics: Optional[Dict[str, Any]] = None,
    chirps_data: Optional[Dict[str, Any]] = None,
    era5_data: Optional[Dict[str, Any]] = None,
    nasa_power_data: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Emit V1.1 forecast packets."""
    packets: List[Dict[str, Any]] = []

    # WEATHER_FORECAST_7D
    if forecast_timeseries and (forecast_timeseries.hourly_count > 0 or forecast_timeseries.daily_count > 0):
        packets.append({
            "packet_type": WEATHER_FORECAST_7D,
            "payload": {
                "horizon_calendar_days": forecast_timeseries.horizon_calendar_days,
                "lead_day_range": forecast_timeseries.lead_day_range,
                "hourly_count": forecast_timeseries.hourly_count,
                "daily_count": forecast_timeseries.daily_count,
                "providers": forecast_timeseries.providers,
                "date_range": [forecast_timeseries.date_range_start, forecast_timeseries.date_range_end],
                "stale_forecast": forecast_timeseries.stale_forecast_flag,
            },
        })

    # WIND_FORECAST_7D
    if wind_features_by_day:
        wind_summary: Dict[str, Any] = {
            "wind_mean_10m_ms_by_day": {},
            "gust_max_10m_ms_by_day": {},
            "dominant_direction_by_day": {},
            "high_wind_hours": 0,
            "hot_dry_wind_hours": 0,
        }
        for date, wf in wind_features_by_day.items():
            wind_summary["wind_mean_10m_ms_by_day"][date] = wf.get("wind_mean_10m_ms", 0)
            wind_summary["gust_max_10m_ms_by_day"][date] = wf.get("gust_max_10m_ms", 0)
            wind_summary["dominant_direction_by_day"][date] = wf.get("dominant_wind_direction_deg", 0)
            wind_summary["high_wind_hours"] += wf.get("high_wind_hours", 0)
            wind_summary["hot_dry_wind_hours"] += wf.get("hot_dry_wind_hours", 0)

        packets.append({
            "packet_type": WIND_FORECAST_7D,
            "payload": wind_summary,
        })

    # WEATHER_FORECAST_CONFIDENCE
    if forecast_consensus:
        confidence_by_day = []
        for day in forecast_consensus:
            confidence_by_day.append({
                "date": day.date,
                "lead_day": day.lead_day,
                "overall": day.overall_forecast_confidence,
                "temperature": day.temperature_confidence,
                "rainfall": day.rainfall_confidence,
                "wind": day.wind_confidence,
            })
        packets.append({
            "packet_type": WEATHER_FORECAST_CONFIDENCE,
            "payload": {
                "confidence_by_day": confidence_by_day,
                "status": "available",
            },
        })
    else:
        # Revision 9: emit confidence packet even when unavailable
        packets.append({
            "packet_type": WEATHER_FORECAST_CONFIDENCE,
            "payload": {"status": "unavailable"},
        })

    # WEATHER_RISK_WINDOWS
    if risk_windows:
        by_type: Dict[str, List] = {}
        for w in risk_windows:
            by_type.setdefault(w.window_type, []).append({
                "date": w.date,
                "opportunity_score": w.opportunity_score,
                "risk_score": w.risk_score,
                "confidence": w.confidence,
                "window_confidence": w.window_confidence,
                "severity": w.severity,
                "window_basis": w.window_basis,
                "drivers": w.drivers,
                "flags": w.flags,
                "recommendation_hint": w.recommendation_hint,
            })
        packets.append({
            "packet_type": WEATHER_RISK_WINDOWS,
            "payload": by_type,
        })

    # WEATHER_FORECAST_DERIVED_FEATURES
    if forecast_derived:
        from dataclasses import asdict
        packets.append({
            "packet_type": WEATHER_FORECAST_DERIVED_FEATURES,
            "payload": asdict(forecast_derived),
        })

    # FORECAST_PROCESS_FORCING
    if forecast_forcing:
        from dataclasses import asdict
        packets.append({
            "packet_type": FORECAST_PROCESS_FORCING,
            "payload": {
                "forcing_by_day": [asdict(f) for f in forecast_forcing],
            },
        })

    # CHIRPS_RAINFALL_BASELINE
    if chirps_data:
        packets.append({
            "packet_type": CHIRPS_RAINFALL_BASELINE,
            "payload": chirps_data,
        })

    # ERA5LAND_CLIMATE_BASELINE
    if era5_data:
        packets.append({
            "packet_type": ERA5LAND_CLIMATE_BASELINE,
            "payload": era5_data,
        })

    # NASA_POWER_AGROCLIMATE_FALLBACK
    if nasa_power_data:
        packets.append({
            "packet_type": NASA_POWER_AGROCLIMATE_FALLBACK,
            "payload": nasa_power_data,
        })

    return packets
