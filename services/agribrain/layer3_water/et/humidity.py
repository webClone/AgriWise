"""
Layer 3.0 Psychrometric Vapor Pressure and Humidity Hierarchy
Calculates saturation vapor pressure e_s(T) and actual vapor pressure e_a per FAO-56 standard.
"""

import math
from typing import Optional, Tuple
from layer3_water.contracts.atmospheric_state import HumiditySourceType


def saturation_vapor_pressure(t_celsius: float) -> float:
    """Compute saturation vapor pressure e^0(T) in kPa per FAO-56 Eq. 11.
    
    e^0(T) = 0.6108 * exp((17.27 * T) / (T + 237.3))
    """
    return round(0.6108 * math.exp((17.27 * t_celsius) / (t_celsius + 237.3)), 4)


def mean_saturation_vapor_pressure(t_max_c: float, t_min_c: float) -> float:
    """Compute mean saturation vapor pressure e_s in kPa per FAO-56 Eq. 12.
    
    e_s = (e^0(T_max) + e^0(T_min)) / 2
    """
    es_tmax = saturation_vapor_pressure(t_max_c)
    es_tmin = saturation_vapor_pressure(t_min_c)
    return round((es_tmax + es_tmin) / 2.0, 4)


def slope_vapor_pressure_curve(t_mean_c: float) -> float:
    """Compute slope of vapor pressure curve Delta (kPa/°C) per FAO-56 Eq. 13.
    
    Delta = (4098 * e^0(T_mean)) / (T_mean + 237.3)^2
    """
    es_tmean = saturation_vapor_pressure(t_mean_c)
    return round((4098.0 * es_tmean) / ((t_mean_c + 237.3) ** 2), 4)


def compute_actual_vapor_pressure(
    t_max_c: float,
    t_min_c: float,
    dew_point_c: Optional[float] = None,
    rh_max_pct: Optional[float] = None,
    rh_min_pct: Optional[float] = None,
    rh_mean_pct: Optional[float] = None,
) -> Tuple[float, HumiditySourceType, float]:
    """Compute actual vapor pressure e_a (kPa) with strict priority hierarchy.
    
    Returns:
        (e_a_kpa, source_used, confidence_score)
    """
    # Priority 1: Dew Point Temperature (Highest Precision)
    if dew_point_c is not None:
        ea = saturation_vapor_pressure(dew_point_c)
        return ea, HumiditySourceType.DEW_POINT, 0.98

    # Priority 2: RH min & RH max (FAO-56 Eq. 17)
    if rh_max_pct is not None and rh_min_pct is not None:
        es_tmin = saturation_vapor_pressure(t_min_c)
        es_tmax = saturation_vapor_pressure(t_max_c)
        ea = (es_tmin * (rh_max_pct / 100.0) + es_tmax * (rh_min_pct / 100.0)) / 2.0
        return round(ea, 4), HumiditySourceType.RH_MIN_MAX, 0.92

    # Priority 3: RH mean (FAO-56 Eq. 19)
    if rh_mean_pct is not None:
        es_mean = mean_saturation_vapor_pressure(t_max_c, t_min_c)
        ea = es_mean * (rh_mean_pct / 100.0)
        return round(ea, 4), HumiditySourceType.RH_MEAN, 0.78

    # Priority 4: Default assumption T_dew ≈ T_min in sub-humid conditions (FAO-56 Eq. 48)
    ea = saturation_vapor_pressure(t_min_c)
    return round(ea, 4), HumiditySourceType.DEFAULT_ESTIMATE, 0.60
