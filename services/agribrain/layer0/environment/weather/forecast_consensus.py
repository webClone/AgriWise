"""
Forecast Consensus Engine.

Per-day, per-variable, per-lead-day consensus for 7-day forecast.
Forecast records NEVER enter V1 historical consensus.
Historical/current records NEVER enter forecast consensus.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from layer0.environment.weather.forecast_schemas import (
    ForecastConsensusDaily,
    ForecastDailyRecord,
    ForecastVariableConsensus,
)
from layer0.environment.weather.forecast_confidence import (
    compute_variable_confidence,
    compute_provider_agreement_modifier,
)

# Thresholds
TEMP_AGREE_C = 2.0
TEMP_MODERATE_C = 3.0
RAIN_DRY_THRESHOLD_MM = 1.0
RAIN_WET_THRESHOLD_MM = 5.0
WIND_AGREE_MS = 3.0
WIND_DISAGREE_MS = 5.0
GUST_AGREE_MS = 5.0
GUST_DISAGREE_MS = 8.0
DIRECTION_AGREE_DEG = 45.0
DIRECTION_DISAGREE_DEG = 90.0


def build_forecast_consensus(
    daily_records: List[ForecastDailyRecord],
) -> List[ForecastConsensusDaily]:
    """Build per-day forecast consensus from multiple provider daily records.

    Groups by date, builds per-variable consensus for each day.
    HARD RULE: Only forecast records accepted.
    """
    # Group by date
    by_date: Dict[str, Dict[str, ForecastDailyRecord]] = defaultdict(dict)
    for rec in daily_records:
        if rec.data_kind != "forecast":
            continue  # Hard prohibition: no historical/current in forecast consensus
        if rec.date:
            by_date[rec.date][rec.provider] = rec

    consensus_list = []
    for date in sorted(by_date.keys()):
        providers = by_date[date]
        lead_day = next(iter(providers.values())).lead_day
        daily = _build_daily_consensus(providers, date, lead_day)
        consensus_list.append(daily)

    return consensus_list


def _build_daily_consensus(
    records: Dict[str, ForecastDailyRecord],
    date: str,
    lead_day: int,
) -> ForecastConsensusDaily:
    """Build consensus for a single forecast day."""
    consensus = ForecastConsensusDaily(date=date, lead_day=lead_day)
    flags: List[str] = []

    if not records:
        consensus.overall_forecast_confidence = 0.0
        consensus.flags = ["NO_PROVIDERS"]
        return consensus

    consensus.provider_count = len(records)

    # Temperature consensus
    for temp_var in ("tmin_c", "tmax_c", "tmean_c"):
        var_name = temp_var.replace("_c", "")
        consensus.variable_consensus[var_name] = _consensus_temperature(
            records, temp_var, var_name, lead_day
        )

    # Rainfall consensus (Open-Meteo preferred on disagreement — Q3 answer)
    consensus.variable_consensus["precipitation"] = _consensus_forecast_rainfall(
        records, lead_day
    )

    # ET₀ — prefer Open-Meteo
    consensus.variable_consensus["et0"] = _consensus_prefer_provider(
        records, "et0_sum_mm", "et0", lead_day, preferred="open_meteo"
    )

    # VPD — prefer Open-Meteo
    consensus.variable_consensus["vpd_max"] = _consensus_prefer_provider(
        records, "vpd_max_kpa", "vpd", lead_day, preferred="open_meteo"
    )

    # Wind speed — average with disagreement flagging
    consensus.variable_consensus["wind_speed"] = _consensus_wind_speed(
        records, lead_day
    )

    # Wind gust — max for safety with disagreement flagging
    consensus.variable_consensus["wind_gusts"] = _consensus_wind_gusts(
        records, lead_day
    )

    # Wind direction — circular mean
    consensus.variable_consensus["wind_direction"] = _consensus_wind_direction(
        records, lead_day
    )

    # Sub-confidences
    temp_conf = consensus.variable_consensus.get("tmean", ForecastVariableConsensus())
    rain_conf = consensus.variable_consensus.get("precipitation", ForecastVariableConsensus())
    wind_conf = consensus.variable_consensus.get("wind_speed", ForecastVariableConsensus())

    consensus.temperature_confidence = temp_conf.variable_confidence
    consensus.rainfall_confidence = rain_conf.variable_confidence
    consensus.wind_confidence = wind_conf.variable_confidence

    # Overall = min of key variable confidences
    key_confs = [temp_conf.variable_confidence, rain_conf.variable_confidence]
    if wind_conf.variable_confidence > 0:
        key_confs.append(wind_conf.variable_confidence)
    consensus.overall_forecast_confidence = min(key_confs) if key_confs else 0.0

    # Collect flags
    for vc in consensus.variable_consensus.values():
        flags.extend(vc.flags)
    consensus.flags = sorted(set(flags))

    return consensus


def _consensus_temperature(
    records: Dict[str, ForecastDailyRecord],
    attr: str,
    var_name: str,
    lead_day: int,
) -> ForecastVariableConsensus:
    """Temperature consensus: average if agree, prefer OM if disagree >3°C."""
    values = {}
    for provider, rec in records.items():
        val = getattr(rec, attr, None)
        if val is not None:
            values[provider] = val

    if not values:
        return ForecastVariableConsensus(variable=var_name, lead_day=lead_day)

    if len(values) == 1:
        provider, val = next(iter(values.items()))
        conf = compute_variable_confidence(lead_day, "temperature")
        return ForecastVariableConsensus(
            variable=var_name, date="", lead_day=lead_day,
            provider_values=values, selected_value=val,
            selected_provider=provider,
            provider_agreement_score=1.0,
            variable_confidence=conf,
            reason="single_provider",
        )

    vals = list(values.values())
    spread = max(vals) - min(vals)

    agreement_mod = compute_provider_agreement_modifier(values, "temperature")
    conf = compute_variable_confidence(lead_day, "temperature", agreement_mod)
    flags = []

    if spread <= TEMP_AGREE_C:
        selected = round(sum(vals) / len(vals), 2)
        reason = f"agree_within_{TEMP_AGREE_C}C"
    elif spread <= TEMP_MODERATE_C:
        selected = round(sum(vals) / len(vals), 2)
        reason = f"moderate_spread_{spread:.1f}C"
    else:
        # Prefer Open-Meteo if available
        if "open_meteo" in values:
            selected = values["open_meteo"]
            reason = "prefer_open_meteo_on_disagreement"
        else:
            selected = round(sum(vals) / len(vals), 2)
            reason = f"average_fallback_{spread:.1f}C"
        flags.append("TEMP_PROVIDER_DISAGREEMENT")

    return ForecastVariableConsensus(
        variable=var_name, lead_day=lead_day,
        provider_values=values, selected_value=selected,
        provider_agreement_score=round(1.0 - min(1.0, spread / 10.0), 2),
        variable_confidence=conf,
        flags=flags, reason=reason,
    )


def _consensus_forecast_rainfall(
    records: Dict[str, ForecastDailyRecord],
    lead_day: int,
) -> ForecastVariableConsensus:
    """Forecast rainfall consensus.

    On disagreement (one >5mm, other <1mm): prefer Open-Meteo, flag LOCAL_RAIN_UNCERTAIN.
    """
    values = {}
    for provider, rec in records.items():
        val = rec.precipitation_sum_mm
        if val is not None:
            values[provider] = val

    if not values:
        return ForecastVariableConsensus(variable="precipitation", lead_day=lead_day)

    if len(values) == 1:
        provider, val = next(iter(values.items()))
        conf = compute_variable_confidence(lead_day, "precipitation")
        return ForecastVariableConsensus(
            variable="precipitation", lead_day=lead_day,
            provider_values=values, selected_value=val,
            selected_provider=provider,
            variable_confidence=conf * 0.8,  # Single provider rainfall lower
            reason="single_provider_rainfall",
        )

    vals = list(values.values())
    all_dry = all(v < RAIN_DRY_THRESHOLD_MM for v in vals)
    all_wet = all(v >= RAIN_DRY_THRESHOLD_MM for v in vals)
    one_wet_one_dry = (
        any(v >= RAIN_WET_THRESHOLD_MM for v in vals) and
        any(v < RAIN_DRY_THRESHOLD_MM for v in vals)
    )

    agreement_mod = compute_provider_agreement_modifier(values, "precipitation")
    conf = compute_variable_confidence(lead_day, "precipitation", agreement_mod)
    flags = []

    if all_dry:
        selected = 0.0
        reason = "both_dry"
    elif all_wet:
        selected = round(sum(vals) / len(vals), 2)
        reason = "both_wet"
    elif one_wet_one_dry:
        # Prefer Open-Meteo (Q3 answer)
        if "open_meteo" in values:
            selected = values["open_meteo"]
        else:
            selected = round(sum(vals) / len(vals), 2)
        flags.append("LOCAL_RAIN_UNCERTAIN")
        reason = "providers_disagree_on_rain"
    else:
        selected = round(sum(vals) / len(vals), 2)
        reason = "moderate_agreement"

    # Check high probability but low amount
    probs = {}
    for provider, rec in records.items():
        prob = rec.precipitation_probability_max_pct
        if prob is not None:
            probs[provider] = prob

    if probs and max(probs.values()) > 50 and selected < RAIN_DRY_THRESHOLD_MM:
        flags.append("RAIN_POSSIBLE_LOW_AMOUNT")

    return ForecastVariableConsensus(
        variable="precipitation", lead_day=lead_day,
        provider_values=values, selected_value=selected,
        provider_agreement_score=round(1.0 if all_dry or all_wet else 0.3, 2),
        variable_confidence=conf,
        flags=flags, reason=reason,
    )


def _consensus_wind_speed(
    records: Dict[str, ForecastDailyRecord],
    lead_day: int,
) -> ForecastVariableConsensus:
    """Wind speed consensus: average if agree within 3 m/s."""
    values = {}
    for provider, rec in records.items():
        val = rec.wind_speed_max_10m_ms
        if val is not None:
            values[provider] = val

    if not values:
        return ForecastVariableConsensus(variable="wind_speed", lead_day=lead_day)

    agreement_mod = compute_provider_agreement_modifier(values, "wind_speed")
    conf = compute_variable_confidence(lead_day, "wind_speed", agreement_mod)
    vals = list(values.values())
    spread = max(vals) - min(vals) if len(vals) > 1 else 0.0
    flags = []

    if spread > WIND_DISAGREE_MS:
        flags.append("WIND_SPEED_UNCERTAIN")

    selected = round(sum(vals) / len(vals), 2)

    return ForecastVariableConsensus(
        variable="wind_speed", lead_day=lead_day,
        provider_values=values, selected_value=selected,
        provider_agreement_score=round(1.0 - min(1.0, spread / 10.0), 2),
        variable_confidence=conf,
        flags=flags,
        reason=f"spread={spread:.1f}ms",
    )


def _consensus_wind_gusts(
    records: Dict[str, ForecastDailyRecord],
    lead_day: int,
) -> ForecastVariableConsensus:
    """Wind gust consensus: choose max for safety on disagreement >8 m/s."""
    values = {}
    for provider, rec in records.items():
        val = rec.wind_gusts_max_10m_ms
        if val is not None:
            values[provider] = val

    if not values:
        return ForecastVariableConsensus(variable="wind_gusts", lead_day=lead_day)

    agreement_mod = compute_provider_agreement_modifier(values, "wind_gusts")
    conf = compute_variable_confidence(lead_day, "wind_gusts", agreement_mod)
    vals = list(values.values())
    spread = max(vals) - min(vals) if len(vals) > 1 else 0.0
    flags = []

    if spread > GUST_DISAGREE_MS:
        selected = max(vals)  # Safety: use max gust
        flags.append("WIND_GUST_UNCERTAIN")
        reason = "max_gust_for_safety"
    elif len(vals) > 1:
        selected = round(sum(vals) / len(vals), 2)
        reason = "gust_average"
    else:
        selected = vals[0]
        reason = "single_provider"

    return ForecastVariableConsensus(
        variable="wind_gusts", lead_day=lead_day,
        provider_values=values, selected_value=selected,
        variable_confidence=conf,
        flags=flags, reason=reason,
    )


def _consensus_wind_direction(
    records: Dict[str, ForecastDailyRecord],
    lead_day: int,
) -> ForecastVariableConsensus:
    """Wind direction consensus using CIRCULAR mean (never arithmetic)."""
    import math

    values = {}
    for provider, rec in records.items():
        val = rec.dominant_wind_direction_deg
        if val is not None:
            values[provider] = val

    if not values:
        return ForecastVariableConsensus(variable="wind_direction", lead_day=lead_day)

    if len(values) == 1:
        provider, val = next(iter(values.items()))
        return ForecastVariableConsensus(
            variable="wind_direction", lead_day=lead_day,
            provider_values=values, selected_value=val,
            selected_provider=provider,
            variable_confidence=0.7,
            reason="single_provider",
        )

    # Circular mean
    vals = list(values.values())
    sin_sum = sum(math.sin(math.radians(v)) for v in vals)
    cos_sum = sum(math.cos(math.radians(v)) for v in vals)
    circular_mean = math.degrees(math.atan2(sin_sum, cos_sum)) % 360

    # Circular spread for agreement check
    angular_diffs = []
    for v in vals:
        diff = abs(v - circular_mean)
        angular_diffs.append(min(diff, 360 - diff))
    max_spread = max(angular_diffs)

    flags = []
    if max_spread > DIRECTION_DISAGREE_DEG:
        flags.append("WIND_DIRECTION_UNCERTAIN")
        conf = 0.3
    elif max_spread > DIRECTION_AGREE_DEG:
        conf = 0.5
    else:
        conf = 0.8

    return ForecastVariableConsensus(
        variable="wind_direction", lead_day=lead_day,
        provider_values=values,
        selected_value=round(circular_mean, 1),
        provider_agreement_score=round(1.0 - min(1.0, max_spread / 180.0), 2),
        variable_confidence=conf,
        flags=flags,
        reason=f"circular_mean_spread={max_spread:.0f}deg",
    )


def _consensus_prefer_provider(
    records: Dict[str, ForecastDailyRecord],
    attr: str,
    var_name: str,
    lead_day: int,
    preferred: str = "open_meteo",
) -> ForecastVariableConsensus:
    """Generic prefer-provider consensus for forecast variables."""
    values = {}
    for provider, rec in records.items():
        val = getattr(rec, attr, None)
        if val is not None:
            values[provider] = val

    if not values:
        return ForecastVariableConsensus(variable=var_name, lead_day=lead_day)

    category = var_name if var_name in ("et0", "vpd") else "temperature"
    conf = compute_variable_confidence(lead_day, category)

    if preferred in values:
        return ForecastVariableConsensus(
            variable=var_name, lead_day=lead_day,
            provider_values=values, selected_value=values[preferred],
            selected_provider=preferred,
            variable_confidence=conf,
            reason=f"{preferred}_preferred",
        )

    provider, val = next(iter(values.items()))
    return ForecastVariableConsensus(
        variable=var_name, lead_day=lead_day,
        provider_values=values, selected_value=val,
        selected_provider=provider,
        variable_confidence=conf * 0.8,
        reason="fallback_provider",
    )
