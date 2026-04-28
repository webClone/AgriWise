"""
Weather Risk Windows.

Operational agronomic risk/opportunity window detection from forecast data.
Score polarity: opportunity_score for work windows, risk_score for hazards (Revision 6).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.weather.forecast_schemas import (
    ForecastConsensusDaily,
    ForecastDailyAgSummary,
    ForecastRiskConfig,
    WeatherRiskWindow,
)


def detect_risk_windows(
    daily_summaries: List[ForecastDailyAgSummary],
    consensus_days: List[ForecastConsensusDaily],
    wind_features_by_day: Optional[Dict[str, Dict[str, Any]]] = None,
    config: Optional[ForecastRiskConfig] = None,
) -> List[WeatherRiskWindow]:
    """Scan 7-day forecast and emit typed risk/opportunity windows.

    All windows carry confidence.
    """
    if config is None:
        config = ForecastRiskConfig()

    windows: List[WeatherRiskWindow] = []

    for i, summary in enumerate(daily_summaries):
        date = summary.date
        lead_day = summary.lead_day
        conf = summary.variable_confidence

        # Look-ahead data for rain-in-next-6h etc.
        next_day_precip = 0.0
        if i + 1 < len(daily_summaries):
            next_day_precip = daily_summaries[i + 1].precip_sum_mm

        wf = {}
        if wind_features_by_day and date in wind_features_by_day:
            wf = wind_features_by_day[date]

        # --- Spray Window ---
        spray = score_spray_window(summary, next_day_precip, wf, conf, config)
        windows.append(spray)

        # --- Irrigation Window ---
        # Compute cumulative water balance
        cumulative_wb = sum(s.water_balance_mm for s in daily_summaries[:i+1])
        irrigation = score_irrigation_window(summary, cumulative_wb, next_day_precip, wf, conf, config)
        windows.append(irrigation)

        # --- Heat Stress ---
        if summary.tmax is not None and summary.tmax > config.heat_stress_temp_c:
            windows.append(WeatherRiskWindow(
                window_type="HEAT_STRESS_WINDOW",
                date=date,
                risk_score=min(1.0, (summary.tmax - config.heat_stress_temp_c) / 10.0),
                confidence=conf,
                window_confidence=conf,
                severity=_severity_from_score(min(1.0, (summary.tmax - config.heat_stress_temp_c) / 10.0)),
                window_basis="daily_approximation",
                drivers={"tmax": summary.tmax, "vpd_max": summary.vpd_max},
                flags=summary.risk_flags,
                recommendation_hint="Monitor crop stress; consider irrigation to reduce canopy temperature.",
            ))

        # --- Frost Window ---
        if summary.tmin is not None and summary.tmin <= config.frost_threshold_c:
            calm_night = wf.get("calm_night_hours", 0)
            frost_risk = 0.6
            if calm_night > 3:
                frost_risk = 0.8
            windows.append(WeatherRiskWindow(
                window_type="FROST_WINDOW",
                date=date,
                risk_score=frost_risk,
                confidence=conf,
                window_confidence=conf,
                severity=_severity_from_score(frost_risk),
                window_basis="hourly" if wind_features_by_day else "daily_approximation",
                drivers={"tmin": summary.tmin, "calm_night_hours": calm_night},
                flags=["FROST_RISK"],
                recommendation_hint="Risk of frost damage. Consider protection measures.",
            ))

        # --- High Wind Window ---
        if summary.wind_max is not None and summary.wind_max > config.high_wind_ms:
            risk = min(1.0, summary.wind_max / config.severe_gust_ms)
            windows.append(WeatherRiskWindow(
                window_type="HIGH_WIND_WINDOW",
                date=date,
                risk_score=risk,
                confidence=conf,
                window_confidence=conf,
                severity=_severity_from_score(risk),
                window_basis="daily_approximation",
                drivers={"wind_max": summary.wind_max, "gust_max": summary.gust_max},
                flags=["HIGH_WIND"],
                recommendation_hint="Avoid field operations. Secure structures.",
            ))

        # --- Hot Dry Wind Window ---
        hdw_hours = wf.get("hot_dry_wind_hours", 0)
        if hdw_hours > 0:
            risk = min(1.0, hdw_hours / 8.0)
            windows.append(WeatherRiskWindow(
                window_type="HOT_DRY_WIND_WINDOW",
                date=date,
                risk_score=risk,
                confidence=conf,
                window_confidence=conf,
                severity=_severity_from_score(risk),
                window_basis="hourly",
                drivers={"hot_dry_wind_hours": hdw_hours},
                flags=["HOT_DRY_WIND"],
                recommendation_hint="Hot dry wind accelerates crop stress. Monitor water status.",
            ))

        # --- Rain Event Window ---
        if summary.precip_sum_mm >= 5.0:
            windows.append(WeatherRiskWindow(
                window_type="RAIN_EVENT_WINDOW",
                date=date,
                risk_score=min(1.0, summary.precip_sum_mm / 30.0),
                confidence=conf,
                window_confidence=conf,
                severity=_severity_from_score(min(1.0, summary.precip_sum_mm / 30.0)),
                window_basis="daily_approximation",
                drivers={"precip_sum_mm": summary.precip_sum_mm},
                recommendation_hint="Significant rain expected. Plan field access accordingly.",
            ))

        # --- Field Access Window ---
        windows.append(WeatherRiskWindow(
            window_type="FIELD_ACCESS_WINDOW",
            date=date,
            opportunity_score=summary.field_access_score,
            confidence=conf,
            window_confidence=conf,
            severity="low" if summary.field_access_score > 0.6 else "moderate",
            window_basis="daily_approximation",
            drivers={"precip": summary.precip_sum_mm, "field_access_score": summary.field_access_score},
            recommendation_hint="Good" if summary.field_access_score > 0.6 else "Limited field access.",
        ))

    return windows


def score_spray_window(
    summary: ForecastDailyAgSummary,
    next_day_precip: float,
    wind_features: Dict[str, Any],
    forecast_confidence: float,
    config: ForecastRiskConfig,
) -> WeatherRiskWindow:
    """Score spray window opportunity.

    Good spray window: low wind, no rain soon, not too hot, reasonable VPD.
    """
    score = 1.0
    flags: List[str] = []
    drivers: Dict[str, Any] = {}

    # Wind penalty
    wind_max = summary.wind_max or 0.0
    gust_max = summary.gust_max or 0.0

    if wind_max > config.spray_wind_max_ms:
        score -= 0.35
        flags.append("HIGH_WIND_FOR_SPRAY")
        drivers["wind_ms"] = wind_max

    if gust_max > config.spray_gust_max_ms:
        score -= 0.25
        flags.append("HIGH_GUST_FOR_SPRAY")
        drivers["gust_ms"] = gust_max

    # Rain penalty (next day as proxy for "next 6h" at daily resolution)
    if next_day_precip > config.spray_rain_amount_threshold_mm:
        score -= 0.40
        flags.append("RAIN_SOON")
        drivers["next_day_precip_mm"] = next_day_precip

    # Temperature penalty
    tmax = summary.tmax or 0.0
    if tmax > config.spray_temp_max_c:
        score -= 0.15
        flags.append("TOO_HOT_FOR_SPRAY")

    # VPD penalty
    vpd = summary.vpd_max or 0.0
    if vpd > config.spray_vpd_max_kpa:
        score -= 0.15
        flags.append("HIGH_VPD_FOR_SPRAY")

    # Confidence cap
    if forecast_confidence < 0.5:
        score = min(score, 0.6)
        flags.append("LOW_FORECAST_CONFIDENCE")

    score = max(0.0, min(1.0, score))

    return WeatherRiskWindow(
        window_type="SPRAY_WINDOW",
        date=summary.date,
        opportunity_score=round(score, 2),
        confidence=forecast_confidence,
        window_confidence=round(score * forecast_confidence, 2),
        severity="low" if score > 0.6 else "moderate" if score > 0.3 else "high",
        window_basis="daily_approximation",
        drivers=drivers,
        flags=flags,
        recommendation_hint="Good spray window" if score > 0.6 else "Poor spray conditions",
    )


def score_irrigation_window(
    summary: ForecastDailyAgSummary,
    cumulative_water_balance: float,
    next_day_precip: float,
    wind_features: Dict[str, Any],
    forecast_confidence: float,
    config: ForecastRiskConfig,
) -> WeatherRiskWindow:
    """Score irrigation opportunity/need.

    Need rises with negative water balance. Delay if rain likely.
    """
    need_score = 0.0
    flags: List[str] = []
    drivers: Dict[str, Any] = {"cumulative_water_balance_mm": cumulative_water_balance}

    # Water deficit drives need
    if cumulative_water_balance < -20:
        need_score = min(1.0, abs(cumulative_water_balance) / 50.0)
        flags.append("WATER_DEFICIT")

    # Rain forecast delay
    if next_day_precip > 10.0 and forecast_confidence > 0.6:
        need_score *= 0.5
        flags.append("RAIN_DELAY_POSSIBLE")
        drivers["next_day_precip_mm"] = next_day_precip

    # Hot dry wind urgency
    hdw = wind_features.get("hot_dry_wind_hours", 0)
    if hdw > 2:
        need_score = min(1.0, need_score + 0.2)
        flags.append("HOT_DRY_WIND_URGENCY")

    # Sprinkler wind penalty
    if config.irrigation_method == "sprinkler":
        wind_max = summary.wind_max or 0.0
        if wind_max > config.spray_wind_max_ms:
            need_score *= 0.7
            flags.append("WIND_SPRINKLER_PENALTY")

    need_score = max(0.0, min(1.0, need_score))

    return WeatherRiskWindow(
        window_type="IRRIGATION_WINDOW",
        date=summary.date,
        opportunity_score=round(need_score, 2),
        confidence=forecast_confidence,
        window_confidence=round(need_score * forecast_confidence, 2),
        severity="low" if need_score < 0.3 else "moderate" if need_score < 0.7 else "high",
        window_basis="daily_approximation",
        drivers=drivers,
        flags=flags,
        recommendation_hint="Irrigate" if need_score > 0.6 else "Monitor water status",
    )


def _severity_from_score(score: float) -> str:
    """Convert a 0-1 risk score to severity label."""
    if score >= 0.8:
        return "severe"
    elif score >= 0.6:
        return "high"
    elif score >= 0.3:
        return "moderate"
    return "low"
