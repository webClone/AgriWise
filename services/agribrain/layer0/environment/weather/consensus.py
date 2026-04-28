"""
Weather Consensus Engine.

Per-day, per-variable consensus between weather providers.
Temperature and rainfall have different reliability rules.
Forecast must NOT be mixed with historical truth.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from layer0.environment.weather.schemas import (
    VariableConsensus,
    WeatherConsensusDaily,
    WeatherDailyRecord,
)

# Consensus thresholds
TEMP_AGREE_THRESHOLD = 2.0      # °C
TEMP_DISAGREE_THRESHOLD = 3.0   # °C
RAIN_NEAR_ZERO = 0.5            # mm


def build_daily_consensus(
    records_by_provider: Dict[str, WeatherDailyRecord],
    date: str,
) -> WeatherConsensusDaily:
    """Build per-day per-variable consensus from multiple provider records.

    Forecast and historical records should NOT be in the same consensus.
    The caller must separate them before calling this.
    """
    consensus = WeatherConsensusDaily(date=date)
    flags: List[str] = []

    if not records_by_provider:
        consensus.overall_confidence = 0.0
        consensus.flags = ["NO_PROVIDERS"]
        return consensus

    # Determine data_kind (should be homogeneous per the mixing rule)
    kinds = set(r.data_kind for r in records_by_provider.values())
    if "forecast" in kinds and any(k != "forecast" for k in kinds):
        flags.append("FORECAST_MIXED_WITH_HISTORICAL")
    consensus.data_kind = next(iter(kinds)) if len(kinds) == 1 else "mixed"

    # Temperature consensus
    consensus.variable_consensus["temp_mean"] = _consensus_temperature(
        records_by_provider, "temp_mean"
    )
    consensus.variable_consensus["temp_min"] = _consensus_temperature(
        records_by_provider, "temp_min"
    )
    consensus.variable_consensus["temp_max"] = _consensus_temperature(
        records_by_provider, "temp_max"
    )

    # Rainfall consensus
    consensus.variable_consensus["precipitation_sum"] = _consensus_rainfall(
        records_by_provider
    )

    # ET₀: prefer open_meteo
    consensus.variable_consensus["et0_mm"] = _consensus_et0(records_by_provider)

    # VPD: prefer open_meteo
    consensus.variable_consensus["vpd_mean"] = _consensus_prefer_provider(
        records_by_provider, "vpd_mean", preferred="open_meteo"
    )

    # Wind
    consensus.variable_consensus["wind_speed_max"] = _consensus_average(
        records_by_provider, "wind_speed_max"
    )

    # Radiation
    consensus.variable_consensus["shortwave_radiation_sum"] = _consensus_prefer_provider(
        records_by_provider, "shortwave_radiation_sum", preferred="open_meteo"
    )

    # Overall confidence (min across key variables)
    key_vars = ["temp_mean", "precipitation_sum", "et0_mm"]
    confidences = [
        consensus.variable_consensus[v].confidence
        for v in key_vars
        if v in consensus.variable_consensus
    ]
    consensus.overall_confidence = min(confidences) if confidences else 0.0
    consensus.flags = flags + _collect_flags(consensus.variable_consensus)

    return consensus


def _consensus_temperature(
    records: Dict[str, WeatherDailyRecord],
    attr: str,
) -> VariableConsensus:
    """Temperature: average if agree within 2°C, lower confidence if >3°C."""
    values = {}
    for provider, rec in records.items():
        val = getattr(rec, attr, None)
        if val is not None:
            values[provider] = val

    if not values:
        return VariableConsensus(variable=attr, confidence=0.0, reason="no_data")

    if len(values) == 1:
        provider, val = next(iter(values.items()))
        return VariableConsensus(
            variable=attr,
            provider_values=values,
            selected_value=val,
            confidence=0.7,
            agreement_score=1.0,
            source=provider,
            reason="single_provider",
        )

    vals = list(values.values())
    spread = max(vals) - min(vals)
    avg = sum(vals) / len(vals)

    if spread <= TEMP_AGREE_THRESHOLD:
        confidence = 0.9
        flags = []
    elif spread <= TEMP_DISAGREE_THRESHOLD:
        confidence = 0.7
        flags = []
    else:
        confidence = 0.4
        flags = ["TEMPERATURE_DISAGREEMENT"]

    return VariableConsensus(
        variable=attr,
        provider_values=values,
        selected_value=round(avg, 2),
        confidence=confidence,
        agreement_score=round(1.0 - min(1.0, spread / 10.0), 2),
        source="consensus_average",
        flags=flags,
        reason=f"spread={spread:.1f}°C",
    )


def _consensus_rainfall(
    records: Dict[str, WeatherDailyRecord],
) -> VariableConsensus:
    """Rainfall: spatial instability → high uncertainty by default."""
    values = {}
    for provider, rec in records.items():
        val = rec.precipitation_sum
        if val is not None:
            values[provider] = val

    if not values:
        return VariableConsensus(
            variable="precipitation_sum", confidence=0.0, reason="no_data"
        )

    if len(values) == 1:
        provider, val = next(iter(values.items()))
        return VariableConsensus(
            variable="precipitation_sum",
            provider_values=values,
            selected_value=val,
            confidence=0.5,  # Single provider rainfall always uncertain
            agreement_score=1.0,
            source=provider,
            reason="single_provider_rainfall",
        )

    vals = list(values.values())
    all_near_zero = all(v < RAIN_NEAR_ZERO for v in vals)
    all_high = all(v >= RAIN_NEAR_ZERO for v in vals)
    some_high_some_zero = (
        any(v >= 5.0 for v in vals) and any(v < RAIN_NEAR_ZERO for v in vals)
    )

    if all_near_zero:
        return VariableConsensus(
            variable="precipitation_sum",
            provider_values=values,
            selected_value=round(sum(vals) / len(vals), 2),
            confidence=0.8,
            agreement_score=0.95,
            source="consensus_average",
            reason="both_dry",
        )

    if all_high:
        avg = sum(vals) / len(vals)
        spread = max(vals) - min(vals)
        confidence = 0.7 if spread < max(vals) * 0.5 else 0.5
        return VariableConsensus(
            variable="precipitation_sum",
            provider_values=values,
            selected_value=round(avg, 2),
            confidence=confidence,
            agreement_score=round(1.0 - min(1.0, spread / max(max(vals), 1)), 2),
            source="consensus_average",
            reason="both_rain",
        )

    if some_high_some_zero:
        avg = sum(vals) / len(vals)
        return VariableConsensus(
            variable="precipitation_sum",
            provider_values=values,
            selected_value=round(avg, 2),
            confidence=0.25,
            agreement_score=0.1,
            source="consensus_average",
            flags=["LOCAL_RAIN_UNCERTAIN"],
            reason="providers_disagree_on_rain",
        )

    # General case
    avg = sum(vals) / len(vals)
    return VariableConsensus(
        variable="precipitation_sum",
        provider_values=values,
        selected_value=round(avg, 2),
        confidence=0.5,
        agreement_score=0.5,
        source="consensus_average",
        reason="moderate_agreement",
    )


def _consensus_et0(
    records: Dict[str, WeatherDailyRecord],
) -> VariableConsensus:
    """ET₀: prefer Open-Meteo if available."""
    values = {}
    for provider, rec in records.items():
        if rec.et0_mm is not None:
            values[provider] = rec.et0_mm

    if not values:
        return VariableConsensus(variable="et0_mm", confidence=0.0, reason="no_data")

    # Prefer open_meteo
    if "open_meteo" in values:
        return VariableConsensus(
            variable="et0_mm",
            provider_values=values,
            selected_value=values["open_meteo"],
            confidence=0.85,
            agreement_score=1.0,
            source="open_meteo",
            reason="open_meteo_preferred",
        )

    # Fallback to first available
    provider, val = next(iter(values.items()))
    return VariableConsensus(
        variable="et0_mm",
        provider_values=values,
        selected_value=val,
        confidence=0.6,
        agreement_score=1.0,
        source=provider,
        reason="fallback_provider",
    )


def _consensus_prefer_provider(
    records: Dict[str, WeatherDailyRecord],
    attr: str,
    preferred: str = "open_meteo",
) -> VariableConsensus:
    """Generic prefer-provider consensus."""
    values = {}
    for provider, rec in records.items():
        val = getattr(rec, attr, None)
        if val is not None:
            values[provider] = val

    if not values:
        return VariableConsensus(variable=attr, confidence=0.0, reason="no_data")

    if preferred in values:
        return VariableConsensus(
            variable=attr,
            provider_values=values,
            selected_value=values[preferred],
            confidence=0.8,
            source=preferred,
            reason=f"{preferred}_preferred",
        )

    provider, val = next(iter(values.items()))
    return VariableConsensus(
        variable=attr,
        provider_values=values,
        selected_value=val,
        confidence=0.6,
        source=provider,
        reason="fallback_provider",
    )


def _consensus_average(
    records: Dict[str, WeatherDailyRecord],
    attr: str,
) -> VariableConsensus:
    """Simple average consensus."""
    values = {}
    for provider, rec in records.items():
        val = getattr(rec, attr, None)
        if val is not None:
            values[provider] = val

    if not values:
        return VariableConsensus(variable=attr, confidence=0.0, reason="no_data")

    avg = sum(values.values()) / len(values)
    return VariableConsensus(
        variable=attr,
        provider_values=values,
        selected_value=round(avg, 2),
        confidence=0.7 if len(values) > 1 else 0.5,
        agreement_score=1.0,
        source="consensus_average",
    )


def _collect_flags(
    consensus: Dict[str, VariableConsensus],
) -> List[str]:
    """Collect all flags from per-variable consensus."""
    flags: List[str] = []
    for vc in consensus.values():
        flags.extend(vc.flags)
    return sorted(set(flags))
