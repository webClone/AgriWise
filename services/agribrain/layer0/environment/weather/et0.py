"""
ET₀ Estimation.

V1: Use Open-Meteo ET₀ if present, otherwise Hargreaves fallback.
Full FAO-56 Penman-Monteith deferred to V1.1.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple


def hargreaves_et0(
    temp_min: float,
    temp_max: float,
    latitude_deg: float,
    day_of_year: int,
) -> float:
    """Hargreaves ET₀ estimation (temperature-only fallback).

    ET₀ = 0.0023 × (T_mean + 17.8) × (T_max - T_min)^0.5 × Ra

    Args:
        temp_min: Daily minimum temperature (°C)
        temp_max: Daily maximum temperature (°C)
        latitude_deg: Latitude in degrees
        day_of_year: Julian day (1-366)

    Returns:
        ET₀ in mm/day
    """
    t_mean = (temp_min + temp_max) / 2.0
    t_range = max(0.0, temp_max - temp_min)

    # Extraterrestrial radiation Ra (MJ/m²/day)
    ra = _extraterrestrial_radiation(latitude_deg, day_of_year)

    # Convert Ra from MJ/m² to mm equivalent (1 MJ/m² ≈ 0.408 mm)
    ra_mm = ra * 0.408

    et0 = 0.0023 * (t_mean + 17.8) * math.sqrt(t_range) * ra_mm
    return max(0.0, round(et0, 2))


def select_et0(
    provider_et0: Optional[float],
    temp_min: Optional[float],
    temp_max: Optional[float],
    latitude_deg: float = 0.0,
    day_of_year: int = 1,
) -> Tuple[float, str]:
    """Select best ET₀ value.

    Returns (et0_mm, source).
    Prefers provider ET₀ (Open-Meteo), falls back to Hargreaves.
    """
    if provider_et0 is not None and provider_et0 >= 0:
        return provider_et0, "open_meteo"

    if temp_min is not None and temp_max is not None:
        et0 = hargreaves_et0(temp_min, temp_max, latitude_deg, day_of_year)
        return et0, "hargreaves"

    return 0.0, "unknown"


def _extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> float:
    """Estimate extraterrestrial radiation Ra (MJ/m²/day).

    Simplified FAO method.
    """
    lat = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)

    # Sunset hour angle
    cos_ws = -math.tan(lat) * math.tan(delta)
    cos_ws = max(-1.0, min(1.0, cos_ws))  # Clamp for polar regions
    ws = math.acos(cos_ws)

    # Solar constant
    gsc = 0.0820  # MJ/m²/min

    ra = (24 * 60 / math.pi) * gsc * dr * (
        ws * math.sin(lat) * math.sin(delta) +
        math.cos(lat) * math.cos(delta) * math.sin(ws)
    )
    return max(0.0, ra)
