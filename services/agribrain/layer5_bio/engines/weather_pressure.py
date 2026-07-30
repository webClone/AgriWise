"""
Layer 5 Weather Pressure Engine — Leaf Wetness Duration (LWD) Model

The Old Science: "If humidity > 85% and temp > 20°C for 3 days → fungal alert"
The New Science: Fungi colonize leaf surfaces when microscopic water persists.
                 The key variable is Leaf Wetness Duration (LWD), not ambient humidity.

LWD Estimation Method (Dew-Point Depression):
  - When T_air approaches T_dew (DPD < 2°C), condensation forms on leaves
  - LWD ≈ hours per day where DPD < threshold
  - Extended LWD (>6-8h/day) dramatically increases fungal infection probability
  - Reference: Kim et al. (2002), Sentelhas et al. (2008)

DPD Calculation (Magnus formula approximation):
  T_dew ≈ T_air - ((100 - RH) / 5)  [simplified; valid for RH > 50%]
  DPD = T_air - T_dew = (100 - RH) / 5

When RH > 90% → DPD < 2°C → leaf wetness likely
When RH > 95% → DPD < 1°C → near-certain condensation + prolonged retention
"""

from typing import Dict, Any, List
import math

from layer5_bio.knowledge.thresholds import (
    WETNESS_RAIN_DIVISOR, WETNESS_DAYS_DIVISOR, HEAT_PENALTY_DIVISOR,
    FUNGAL_TEMP_OPTIMAL, FUNGAL_TEMP_WIDTH,
    BACTERIAL_TEMP_BASE, BACTERIAL_TEMP_SCALE,
    INSECT_DEGREE_BASE, INSECT_DEGREE_SCALE, INSECT_HEAT_OPTIMAL
)


def _clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))


def _rolling(ts: List[Dict[str, Any]], key: str, n: int) -> List:
    vals = []
    for r in ts[-n:]:
        v = r.get(key)
        vals.append(float(v) if v is not None else None)
    return vals


# ── Leaf Wetness Duration (LWD) via Dew-Point Depression ─────────────────

def _estimate_dew_point_depression(t_air: float, rh: float) -> float:
    """Estimate dew-point depression (DPD) in °C.
    
    Uses simplified Magnus-formula relationship:
      T_dew ≈ T_air - ((100 - RH) / 5)   [valid for RH > 50%]
      DPD = T_air - T_dew = (100 - RH) / 5
    
    Lower DPD → more likely leaf wetness (condensation on leaf surfaces).
    """
    rh = max(10.0, min(100.0, rh))  # safety clamp
    return (100.0 - rh) / 5.0


def _estimate_lwd_hours(t_air: float, rh: float, rain_mm: float, wind_speed: float = 2.0) -> float:
    """Estimate Leaf Wetness Duration (hours per day) from weather variables.
    
    Science:
      - DPD < 2°C → condensation likely → ~4-6h base LWD
      - DPD < 1°C → near-certain condensation → ~8-12h base LWD  
      - Rain > 0.5mm → adds 2-4h of surface wetness (depending on canopy interception)
      - High wind dries leaves faster → reduces LWD
      - Night cooling extends LWD (approximated by assuming 10h darkness)
    
    Returns estimated LWD in hours (0-24 range).
    """
    dpd = _estimate_dew_point_depression(t_air, rh)
    
    # Base LWD from dew-point depression
    if dpd < 0.5:
        base_lwd = 12.0  # Near-saturation: 12h of wetness
    elif dpd < 1.0:
        base_lwd = 8.0
    elif dpd < 2.0:
        base_lwd = 5.0
    elif dpd < 3.0:
        base_lwd = 2.0
    elif dpd < 5.0:
        base_lwd = 0.5
    else:
        base_lwd = 0.0  # DPD > 5°C: too dry for condensation
    
    # Rain contribution: canopy interception adds hours of surface wetness
    rain_lwd = 0.0
    if rain_mm > 0.5:
        rain_lwd = min(6.0, 2.0 + math.log1p(rain_mm) * 1.5)
    
    # Wind drying penalty: high wind speeds reduce LWD
    # Reference: wind > 3 m/s significantly accelerates evaporation
    wind_penalty = max(0.0, (wind_speed - 1.5) * 0.8)
    
    # Total LWD (take max of dew-based and rain-based, then subtract wind)
    lwd = max(base_lwd, rain_lwd) - wind_penalty
    
    return max(0.0, min(24.0, lwd))


def _compute_lwd_metrics(ts: List[Dict[str, Any]], n_days: int = 7) -> Dict[str, float]:
    """Compute LWD metrics over a rolling window.
    
    Returns dict with:
      - lwd_mean_hours: average daily LWD over the window
      - lwd_max_hours: maximum single-day LWD
      - lwd_consecutive_wet_days: consecutive days with LWD > 4h
      - dpd_mean: mean dew-point depression
      - lwd_cumulative_hours: total LWD hours in the window
    """
    lwd_hours = []
    dpd_values = []
    
    for record in ts[-n_days:]:
        t_air = record.get("tmean")
        rh = record.get("humidity") or record.get("rh")
        rain = record.get("rain", 0.0)
        wind = record.get("wind_speed") or record.get("wind", 2.0)
        
        if t_air is not None:
            t_air = float(t_air)
            rh_val = float(rh) if rh is not None else 70.0  # conservative default
            rain_val = float(rain) if rain is not None else 0.0
            wind_val = float(wind) if wind is not None else 2.0
            
            lwd = _estimate_lwd_hours(t_air, rh_val, rain_val, wind_val)
            dpd = _estimate_dew_point_depression(t_air, rh_val)
            lwd_hours.append(lwd)
            dpd_values.append(dpd)
    
    if not lwd_hours:
        return {
            "lwd_mean_hours": 0.0,
            "lwd_max_hours": 0.0,
            "lwd_consecutive_wet_days": 0,
            "dpd_mean": 10.0,
            "lwd_cumulative_hours": 0.0,
            "lwd_available": False,
        }
    
    # Consecutive wet days (LWD > 4h)
    consecutive = 0
    max_consecutive = 0
    for lwd in lwd_hours:
        if lwd > 4.0:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
    
    return {
        "lwd_mean_hours": sum(lwd_hours) / len(lwd_hours),
        "lwd_max_hours": max(lwd_hours),
        "lwd_consecutive_wet_days": max_consecutive,
        "dpd_mean": sum(dpd_values) / len(dpd_values) if dpd_values else 10.0,
        "lwd_cumulative_hours": sum(lwd_hours),
        "lwd_available": True,
    }


# ── Main Entry Point ─────────────────────────────────────────────────────

def build_weather_pressure(
    ts: List[Dict[str, Any]],
    veg_output,
    plot_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Build weather-derived biotic pressure signals.
    
    Returns both the legacy pressure proxies AND the new LWD-based metrics.
    The inference engine will prefer LWD when available.
    """
    # Legacy rolling statistics
    rain7 = [v for v in _rolling(ts, "rain", 7) if v is not None]
    t7 = [v for v in _rolling(ts, "tmean", 7) if v is not None]

    rain_sum_7d = sum(rain7) if rain7 else 0.0
    tmean_7d = (sum(t7) / len(t7)) if t7 else 20.0
    wet_days_7d = sum(1 for v in _rolling(ts, "rain", 7) if (v is not None and v > 0.5))
    heat_days_7d = sum(1 for v in _rolling(ts, "tmean", 7) if (v is not None and v > 30.0))

    # Legacy wetness proxy (preserved for backward compatibility)
    leaf_wetness_legacy = _clamp(
        (rain_sum_7d / WETNESS_RAIN_DIVISOR)
        + (wet_days_7d / WETNESS_DAYS_DIVISOR)
        - (heat_days_7d / HEAT_PENALTY_DIVISOR)
    )

    # ── NEW SCIENCE: Leaf Wetness Duration (LWD) ────────────────────────
    lwd_metrics = _compute_lwd_metrics(ts, n_days=7)
    
    # Use LWD as primary wetness signal when available; fallback to legacy
    if lwd_metrics["lwd_available"]:
        # Normalize LWD mean to [0, 1] scale: 0h → 0.0, 12h → 1.0
        leaf_wetness = _clamp(lwd_metrics["lwd_mean_hours"] / 12.0)
    else:
        leaf_wetness = leaf_wetness_legacy

    # ── Fungal pressure (LWD-enhanced) ──────────────────────────────────
    # Science: Fungal infection requires both:
    #   1. Sufficient LWD for spore germination (>4h for most species)
    #   2. Optimal temperature band (15-25°C for most foliar fungi)
    temp_band = 1.0 - _clamp(abs(tmean_7d - FUNGAL_TEMP_OPTIMAL) / FUNGAL_TEMP_WIDTH)
    
    if lwd_metrics["lwd_available"]:
        # LWD-based fungal pressure: consecutive wet days + temperature optimality
        lwd_factor = _clamp(lwd_metrics["lwd_mean_hours"] / 10.0)
        consec_factor = _clamp(lwd_metrics["lwd_consecutive_wet_days"] / 4.0)
        fungal_pressure = _clamp(0.45 * lwd_factor + 0.30 * consec_factor + 0.25 * temp_band)
    else:
        fungal_pressure = _clamp(0.65 * leaf_wetness + 0.35 * temp_band)

    # ── Bacterial pressure ──────────────────────────────────────────────
    # Bacterial pathogens: warm + wet + wind-driven rain splashing
    bacterial_pressure = _clamp(
        0.7 * leaf_wetness
        + 0.3 * _clamp((tmean_7d - BACTERIAL_TEMP_BASE) / BACTERIAL_TEMP_SCALE)
    )

    # ── Insect pressure (degree-day proxy) ──────────────────────────────
    dd = max(0.0, tmean_7d - INSECT_DEGREE_BASE)
    insect_degree = _clamp(dd / INSECT_DEGREE_SCALE)
    insect_pressure = _clamp(
        0.6 * insect_degree
        + 0.25 * (1.0 - leaf_wetness)
        + 0.15 * _clamp((tmean_7d - INSECT_HEAT_OPTIMAL) / 10.0)
    )

    # ── Powdery Mildew specific pressure ────────────────────────────────
    # Science: Powdery mildew thrives in moderate humidity (40-70%) WITHOUT rain.
    # It actually prefers dry leaves + warm days + cool nights (diurnal oscillation).
    rh_vals = [v for v in _rolling(ts, "humidity", 7) if v is not None]
    if not rh_vals:
        rh_vals = [v for v in _rolling(ts, "rh", 7) if v is not None]
    mean_rh = (sum(rh_vals) / len(rh_vals)) if rh_vals else 60.0
    
    # Temperature oscillation: std of daily temps
    t_min_vals = [v for v in _rolling(ts, "tmin", 7) if v is not None]
    t_max_vals = [v for v in _rolling(ts, "tmax", 7) if v is not None]
    if t_min_vals and t_max_vals and len(t_min_vals) == len(t_max_vals):
        diurnal_range = sum(mx - mn for mx, mn in zip(t_max_vals, t_min_vals)) / len(t_min_vals)
    else:
        diurnal_range = 8.0  # conservative default
    
    pm_humidity_factor = 1.0 - abs(mean_rh - 55.0) / 45.0  # Peak at 55% RH
    pm_humidity_factor = _clamp(pm_humidity_factor)
    pm_diurnal_factor = _clamp(diurnal_range / 15.0)  # Wider diurnal → higher risk
    pm_dry_factor = 1.0 - _clamp(rain_sum_7d / 20.0)  # Dry conditions favor powdery mildew
    
    powdery_mildew_pressure = _clamp(
        0.35 * pm_humidity_factor + 0.35 * pm_diurnal_factor + 0.30 * pm_dry_factor
    )

    return {
        "rain_sum_7d": rain_sum_7d,
        "tmean_7d": tmean_7d,
        "wet_days_7d": wet_days_7d,
        "heat_days_7d": heat_days_7d,
        # Legacy proxy (preserved)
        "leaf_wetness_proxy": leaf_wetness_legacy,
        # New Science: LWD metrics
        "leaf_wetness_lwd": leaf_wetness,
        "lwd_mean_hours": lwd_metrics["lwd_mean_hours"],
        "lwd_max_hours": lwd_metrics["lwd_max_hours"],
        "lwd_consecutive_wet_days": lwd_metrics["lwd_consecutive_wet_days"],
        "dpd_mean": lwd_metrics["dpd_mean"],
        "lwd_cumulative_hours": lwd_metrics["lwd_cumulative_hours"],
        "lwd_available": lwd_metrics["lwd_available"],
        # Pressure indices
        "fungal_pressure": fungal_pressure,
        "bacterial_pressure": bacterial_pressure,
        "insect_degree_proxy": insect_degree,
        "insect_pressure": insect_pressure,
        "powdery_mildew_pressure": powdery_mildew_pressure,
    }
