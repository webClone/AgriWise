
from typing import Dict, Any, List
import math

def _clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))

def _rolling(ts: List[Dict[str, Any]], key: str, n: int):
    vals = []
    # ts is plot_timeseries from L1
    for r in ts[-n:]:
        v = r.get(key)
        vals.append(float(v) if v is not None else None)
    return vals

from layer5_bio.knowledge.thresholds import (
    WETNESS_RAIN_DIVISOR, WETNESS_DAYS_DIVISOR, HEAT_PENALTY_DIVISOR,
    FUNGAL_TEMP_OPTIMAL, FUNGAL_TEMP_WIDTH,
    BACTERIAL_TEMP_BASE, BACTERIAL_TEMP_SCALE,
    INSECT_DEGREE_BASE, INSECT_DEGREE_SCALE, INSECT_HEAT_OPTIMAL
)

def build_weather_pressure(ts: List[Dict[str, Any]], veg_output, plot_context: Dict[str, Any]) -> Dict[str, Any]:
    # last 7 days
    rain7 = [v for v in _rolling(ts, "rain", 7) if v is not None]
    t7 = [v for v in _rolling(ts, "tmean", 7) if v is not None]

    rain_sum_7d = sum(rain7) if rain7 else 0.0
    tmean_7d = (sum(t7) / len(t7)) if t7 else 20.0
    wet_days_7d = sum(1 for v in _rolling(ts, "rain", 7) if (v is not None and v > 0.5))
    heat_days_7d = sum(1 for v in _rolling(ts, "tmean", 7) if (v is not None and v > 30.0))

    # wetness proxy: wet persistence + rain amount - extreme heat penalty
    leaf_wetness = _clamp((rain_sum_7d / WETNESS_RAIN_DIVISOR) + (wet_days_7d / WETNESS_DAYS_DIVISOR) - (heat_days_7d / HEAT_PENALTY_DIVISOR))

    # fungal: wetness + moderate temperatures
    temp_band = 1.0 - _clamp(abs(tmean_7d - FUNGAL_TEMP_OPTIMAL) / FUNGAL_TEMP_WIDTH)  # peak around 20C
    fungal_pressure = _clamp(0.65 * leaf_wetness + 0.35 * temp_band)

    # bacterial: storms/warm wet (proxy)
    bacterial_pressure = _clamp(0.7 * leaf_wetness + 0.3 * _clamp((tmean_7d - BACTERIAL_TEMP_BASE) / BACTERIAL_TEMP_SCALE))

    # insects: degree day proxy (rough)
    dd = max(0.0, tmean_7d - INSECT_DEGREE_BASE)
    insect_degree = _clamp(dd / INSECT_DEGREE_SCALE)
    insect_pressure = _clamp(0.6 * insect_degree + 0.25 * (1.0 - leaf_wetness) + 0.15 * _clamp((tmean_7d - INSECT_HEAT_OPTIMAL) / 10.0))

    return {
        "rain_sum_7d": rain_sum_7d,
        "tmean_7d": tmean_7d,
        "wet_days_7d": wet_days_7d,
        "heat_days_7d": heat_days_7d,
        "leaf_wetness_proxy": leaf_wetness,
        "fungal_pressure": fungal_pressure,
        "bacterial_pressure": bacterial_pressure,
        "insect_degree_proxy": insect_degree,
        "insect_pressure": insect_pressure,
    }
