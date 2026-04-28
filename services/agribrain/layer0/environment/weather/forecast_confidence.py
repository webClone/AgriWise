"""
Forecast Confidence Model.

Lead-time confidence decay with variable-specific and provider-agreement modifiers.
Separates variable_confidence from decision_confidence (Revision 8).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.weather.forecast_schemas import (
    BASE_LEAD_CONFIDENCE,
    VARIABLE_DECAY_MODIFIERS,
)


# Provider agreement modifiers
AGREEMENT_BONUSES = {
    "temperature_agree_2c": 0.05,
    "wind_speed_agree_3ms": 0.05,
    "rain_agree": 0.05,
}

DISAGREEMENT_PENALTIES = {
    "temperature_disagree_3c": -0.20,
    "wind_speed_disagree_5ms": -0.20,
    "rain_disagree": -0.35,
    "gust_disagree_8ms": -0.25,
}


def compute_variable_confidence(
    lead_day: int,
    variable_category: str,
    provider_agreement_modifier: float = 0.0,
    data_completeness: float = 1.0,
) -> float:
    """Compute confidence for a single forecast variable.

    confidence = base_lead × variable_decay × (1 + agreement_modifier) × completeness

    Args:
        lead_day: 0..6
        variable_category: key in VARIABLE_DECAY_MODIFIERS
        provider_agreement_modifier: positive = agreement bonus, negative = penalty
        data_completeness: fraction of expected data present (0-1)

    Returns:
        Confidence value 0.0 - 0.95
    """
    base = BASE_LEAD_CONFIDENCE.get(lead_day, 0.30)
    decay = VARIABLE_DECAY_MODIFIERS.get(variable_category, 0.70)

    confidence = base * decay * (1.0 + provider_agreement_modifier) * data_completeness
    return max(0.0, min(0.95, round(confidence, 4)))


def compute_provider_agreement_modifier(
    provider_values: Dict[str, float],
    variable_category: str,
) -> float:
    """Compute provider agreement modifier from provider values.

    Returns a modifier in range [-0.35, +0.05].
    """
    if len(provider_values) < 2:
        return 0.0

    vals = list(provider_values.values())
    spread = max(vals) - min(vals)

    if variable_category in ("temperature", "temp_min", "temp_max", "temp_mean"):
        if spread <= 2.0:
            return AGREEMENT_BONUSES["temperature_agree_2c"]
        elif spread > 3.0:
            return DISAGREEMENT_PENALTIES["temperature_disagree_3c"]

    elif variable_category in ("wind_speed", "wind_gusts"):
        if variable_category == "wind_gusts" and spread > 8.0:
            return DISAGREEMENT_PENALTIES["gust_disagree_8ms"]
        if spread <= 3.0:
            return AGREEMENT_BONUSES["wind_speed_agree_3ms"]
        elif spread > 5.0:
            return DISAGREEMENT_PENALTIES["wind_speed_disagree_5ms"]

    elif variable_category in ("precipitation", "precip_probability"):
        # Both dry or both wet
        all_dry = all(v < 1.0 for v in vals)
        all_wet = all(v >= 1.0 for v in vals)
        one_wet_one_dry = (
            any(v > 5.0 for v in vals) and any(v < 1.0 for v in vals)
        )
        if all_dry or all_wet:
            return AGREEMENT_BONUSES["rain_agree"]
        if one_wet_one_dry:
            return DISAGREEMENT_PENALTIES["rain_disagree"]

    return 0.0


def compute_daily_forecast_confidence(
    variable_confidences: Dict[str, float],
) -> float:
    """Compute overall daily forecast confidence as min of key variables."""
    key_vars = ["temperature", "precipitation", "et0", "wind_speed"]
    relevant = [
        v for k, v in variable_confidences.items()
        if any(kv in k for kv in key_vars)
    ]
    if not relevant:
        return 0.0
    return round(min(relevant), 4)


def compute_decision_confidence(
    variable_confidence: float,
    window_drivers: Dict[str, float],
) -> float:
    """Compute decision-level confidence for a risk/opportunity window.

    A dry/windy day may have uncertain rain but clear no-spray decision.
    Decision confidence can be higher than variable confidence when
    the decision is dominated by a high-confidence driver.

    Args:
        variable_confidence: average variable confidence for the window
        window_drivers: {driver_name: driver_confidence} for relevant drivers

    Returns:
        Decision confidence 0.0 - 0.95
    """
    if not window_drivers:
        return variable_confidence

    # Decision confidence is the weighted max of driver confidences
    max_driver_conf = max(window_drivers.values())
    # Blend: 60% strongest driver, 40% variable average
    decision = 0.6 * max_driver_conf + 0.4 * variable_confidence
    return max(0.0, min(0.95, round(decision, 4)))


def compute_staleness_penalty(
    forecast_age_hours: Optional[float],
) -> float:
    """Compute confidence penalty due to forecast staleness (Revision 5).

    Returns a multiplier 0.0 - 1.0.
    """
    if forecast_age_hours is None:
        return 1.0

    if forecast_age_hours <= 12.0:
        return 1.0
    elif forecast_age_hours <= 24.0:
        return 0.7
    elif forecast_age_hours <= 48.0:
        return 0.3
    else:
        return 0.0  # unusable
