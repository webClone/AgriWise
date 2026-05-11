"""
ET₀ Estimation — Full FAO-56 Penman-Monteith + Hargreaves Fallback.

Priority cascade:
  1. Provider ET₀ (Open-Meteo) — if available, trusted as-is
  2. Full FAO-56 Penman-Monteith — when T, RH, wind, and radiation are available
  3. Reduced Penman-Monteith — when T and RH available but wind/radiation are estimated
  4. Hargreaves-Samani — temperature-only fallback

Reference:
  Allen et al. (1998), FAO Irrigation and Drainage Paper No. 56.
  "Crop Evapotranspiration — Guidelines for Computing Crop Water Requirements."
"""

from __future__ import annotations

import math
from typing import Optional, Tuple


# ============================================================================
# FAO-56 Penman-Monteith (Full Implementation)
# ============================================================================

def penman_monteith_et0(
    temp_min: float,
    temp_max: float,
    temp_mean: Optional[float],
    relative_humidity_mean: float,
    wind_speed_2m: float,
    shortwave_radiation_mj: Optional[float],
    latitude_deg: float,
    day_of_year: int,
    elevation_m: float = 100.0,
) -> float:
    """FAO-56 Penman-Monteith reference evapotranspiration.

    Eq. 6 from FAO-56:
        ET₀ = [0.408 Δ(Rn − G) + γ (900/(T+273)) u₂ (es − ea)]
              / [Δ + γ(1 + 0.34 u₂)]

    Args:
        temp_min:                 Daily minimum temperature (°C)
        temp_max:                 Daily maximum temperature (°C)
        temp_mean:                Daily mean temperature (°C), computed if None
        relative_humidity_mean:   Mean relative humidity (%)
        wind_speed_2m:            Wind speed at 2 m height (m/s)
        shortwave_radiation_mj:   Incoming shortwave radiation (MJ/m²/day).
                                  If None, estimated from Ra and temperature range.
        latitude_deg:             Latitude in decimal degrees
        day_of_year:              Julian day (1–366)
        elevation_m:              Elevation above sea level (m), for pressure calc

    Returns:
        ET₀ in mm/day (≥ 0)
    """
    # ── Mean temperature ─────────────────────────────────────────────────
    T = temp_mean if temp_mean is not None else (temp_min + temp_max) / 2.0

    # ── Atmospheric pressure (Eq. 7) ─────────────────────────────────────
    P = 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26  # kPa

    # ── Psychrometric constant γ (Eq. 8) ─────────────────────────────────
    gamma = 0.000665 * P  # kPa/°C

    # ── Saturation vapour pressure es (Eq. 11-12) ────────────────────────
    es_tmin = _saturation_vapour_pressure(temp_min)
    es_tmax = _saturation_vapour_pressure(temp_max)
    es = (es_tmin + es_tmax) / 2.0

    # ── Actual vapour pressure ea (Eq. 17) ───────────────────────────────
    ea = es * (relative_humidity_mean / 100.0)

    # ── Slope of saturation vapour pressure curve Δ (Eq. 13) ─────────────
    delta = (4098.0 * _saturation_vapour_pressure(T)) / ((T + 237.3) ** 2)

    # ── Extraterrestrial radiation Ra ────────────────────────────────────
    Ra = _extraterrestrial_radiation(latitude_deg, day_of_year)

    # ── Net radiation Rn ─────────────────────────────────────────────────
    if shortwave_radiation_mj is not None and shortwave_radiation_mj >= 0:
        Rs = shortwave_radiation_mj
    else:
        # Estimate Rs from Hargreaves radiation formula (Eq. 50)
        # Rs = kRs × √(Tmax − Tmin) × Ra
        kRs = 0.16  # interior locations (0.19 for coastal)
        Rs = kRs * math.sqrt(max(0.0, temp_max - temp_min)) * Ra

    # Clear-sky solar radiation Rso (Eq. 37)
    Rso = (0.75 + 2e-5 * elevation_m) * Ra
    Rso = max(Rso, 0.001)  # Avoid division by zero

    # Net shortwave radiation Rns (Eq. 38) — albedo α = 0.23 for grass
    Rns = (1.0 - 0.23) * Rs

    # Net outgoing longwave radiation Rnl (Eq. 39)
    sigma = 4.903e-9  # Stefan-Boltzmann constant (MJ/m²/day/K⁴)
    Tmin_K4 = (temp_min + 273.16) ** 4
    Tmax_K4 = (temp_max + 273.16) ** 4

    # Cloudiness factor: clip Rs/Rso to [0.25, 1.0] range
    Rs_Rso_ratio = min(1.0, max(0.25, Rs / Rso))

    Rnl = sigma * ((Tmin_K4 + Tmax_K4) / 2.0) * \
        (0.34 - 0.14 * math.sqrt(max(0.0, ea))) * \
        (1.35 * Rs_Rso_ratio - 0.35)

    # Net radiation
    Rn = Rns - Rnl

    # ── Soil heat flux G (Eq. 42) — negligible for daily steps ───────────
    G = 0.0

    # ── FAO-56 Penman-Monteith equation (Eq. 6) ─────────────────────────
    numerator = (0.408 * delta * (Rn - G) +
                 gamma * (900.0 / (T + 273.0)) * wind_speed_2m * (es - ea))
    denominator = delta + gamma * (1.0 + 0.34 * wind_speed_2m)

    et0 = numerator / denominator
    return max(0.0, round(et0, 2))


# ============================================================================
# Hargreaves-Samani (Temperature-Only Fallback)
# ============================================================================

def hargreaves_et0(
    temp_min: float,
    temp_max: float,
    latitude_deg: float,
    day_of_year: int,
) -> float:
    """Hargreaves-Samani ET₀ estimation (temperature-only fallback).

    ET₀ = 0.0023 × (T_mean + 17.8) × (T_max − T_min)^0.5 × Ra

    Args:
        temp_min:      Daily minimum temperature (°C)
        temp_max:      Daily maximum temperature (°C)
        latitude_deg:  Latitude in degrees
        day_of_year:   Julian day (1–366)

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


# ============================================================================
# Smart Selection Cascade
# ============================================================================

def select_et0(
    provider_et0: Optional[float] = None,
    temp_min: Optional[float] = None,
    temp_max: Optional[float] = None,
    latitude_deg: float = 0.0,
    day_of_year: int = 1,
    # PM-specific inputs (new)
    temp_mean: Optional[float] = None,
    relative_humidity_mean: Optional[float] = None,
    wind_speed_2m: Optional[float] = None,
    shortwave_radiation_mj: Optional[float] = None,
    elevation_m: float = 100.0,
) -> Tuple[float, str]:
    """Select best ET₀ value using a priority cascade.

    Returns (et0_mm, source).

    Priority:
      1. Provider ET₀ (Open-Meteo)  — already computed by the provider
      2. Penman-Monteith (full)     — T + RH + wind + radiation available
      3. Penman-Monteith (reduced)  — T + RH available, wind/radiation estimated
      4. Hargreaves-Samani           — temperature-only fallback
    """
    # ── 1. Provider ET₀ ──────────────────────────────────────────────────
    if provider_et0 is not None and provider_et0 >= 0:
        return provider_et0, "open_meteo"

    # Need at least temperatures for any calculation
    if temp_min is None or temp_max is None:
        return 0.0, "unknown"

    # ── 2. Full Penman-Monteith ──────────────────────────────────────────
    if relative_humidity_mean is not None and wind_speed_2m is not None:
        et0 = penman_monteith_et0(
            temp_min=temp_min,
            temp_max=temp_max,
            temp_mean=temp_mean,
            relative_humidity_mean=relative_humidity_mean,
            wind_speed_2m=wind_speed_2m,
            shortwave_radiation_mj=shortwave_radiation_mj,
            latitude_deg=latitude_deg,
            day_of_year=day_of_year,
            elevation_m=elevation_m,
        )
        source = "penman_monteith" if shortwave_radiation_mj is not None else "penman_monteith_reduced"
        return et0, source

    # ── 3. Reduced PM (RH available, estimate wind at 2 m/s default) ─────
    if relative_humidity_mean is not None:
        et0 = penman_monteith_et0(
            temp_min=temp_min,
            temp_max=temp_max,
            temp_mean=temp_mean,
            relative_humidity_mean=relative_humidity_mean,
            wind_speed_2m=2.0,  # FAO-56 default for missing wind
            shortwave_radiation_mj=shortwave_radiation_mj,
            latitude_deg=latitude_deg,
            day_of_year=day_of_year,
            elevation_m=elevation_m,
        )
        return et0, "penman_monteith_reduced"

    # ── 4. Hargreaves-Samani (temperature only) ──────────────────────────
    et0 = hargreaves_et0(temp_min, temp_max, latitude_deg, day_of_year)
    return et0, "hargreaves"


# ============================================================================
# Shared Helper Functions
# ============================================================================

def _saturation_vapour_pressure(temp_c: float) -> float:
    """Saturation vapour pressure at temperature T (Eq. 11).

    e°(T) = 0.6108 × exp(17.27 × T / (T + 237.3))

    Returns:
        Saturation vapour pressure in kPa
    """
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def _extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> float:
    """Extraterrestrial radiation Ra (MJ/m²/day).

    FAO-56 Eq. 21 — based on latitude and day of year.
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


def wind_speed_at_2m(wind_speed: float, measurement_height: float = 10.0) -> float:
    """Convert wind speed from measurement height to 2 m (Eq. 47).

    u₂ = uz × 4.87 / ln(67.8z − 5.42)

    Most weather stations measure at 10 m.
    """
    if measurement_height <= 0:
        return wind_speed
    return wind_speed * 4.87 / math.log(67.8 * measurement_height - 5.42)
