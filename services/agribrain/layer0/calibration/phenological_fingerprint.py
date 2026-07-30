"""
Module 2: Phenological Fingerprint
Decomposes multi-year NDVI timeseries into individual growing seasons
and extracts per-season biophysical metrics.
"""
import math
import logging
from typing import Dict, List, Any

logger = logging.getLogger("agribrain.phenological")


def analyze_phenological_fingerprint(ndvi_obs: List[Dict], weather: List[Dict]) -> Dict:
    """
    Decompose NDVI timeseries into seasons and extract fingerprint metrics.
    
    Args:
        ndvi_obs: List of {"day": "YYYY-MM-DD", "lai": float} (LAI = NDVI*3)
        weather: List of {"day": "YYYY-MM-DD", "temp_max": float, ...}
    """
    if len(ndvi_obs) < 10:
        return {"status": "insufficient_data", "seasons": []}

    # Convert LAI back to NDVI for analysis
    dated = []
    for o in ndvi_obs:
        ndvi = o.get("lai", 0) / 3.0
        day = o.get("day", "")
        if ndvi > 0.05 and day:
            dated.append({"day": day, "ndvi": ndvi, "doy": _doy(day), "year": _year(day)})

    dated.sort(key=lambda x: x["day"])
    if len(dated) < 10:
        return {"status": "insufficient_data", "seasons": []}

    # Group by year
    years = {}
    for d in dated:
        y = d["year"]
        if y not in years:
            years[y] = []
        years[y].append(d)

    seasons = []
    for yr, obs in sorted(years.items()):
        if len(obs) < 4:
            continue
        s = _extract_season(obs, yr)
        if s:
            seasons.append(s)

    if not seasons:
        return {"status": "no_seasons_detected", "seasons": []}

    # Inter-annual stability
    peak_vals = [s["peak_ndvi"] for s in seasons]
    mean_peak = sum(peak_vals) / len(peak_vals)
    if mean_peak > 0 and len(peak_vals) > 1:
        std_peak = math.sqrt(sum((v - mean_peak) ** 2 for v in peak_vals) / len(peak_vals))
        cv = std_peak / mean_peak
    else:
        cv = 0

    # Trend: is peak NDVI rising or falling over the years?
    if len(peak_vals) >= 3:
        first_half = sum(peak_vals[:len(peak_vals)//2]) / max(1, len(peak_vals)//2)
        second_half = sum(peak_vals[len(peak_vals)//2:]) / max(1, len(peak_vals) - len(peak_vals)//2)
        trend_pct = ((second_half - first_half) / max(0.01, first_half)) * 100
    else:
        trend_pct = 0

    stability_label = "Stable" if cv < 0.10 else "Moderate" if cv < 0.20 else "Volatile"

    return {
        "status": "ok",
        "total_seasons": len(seasons),
        "seasons": seasons,
        "inter_annual_cv": round(cv, 3),
        "stability_label": stability_label,
        "peak_trend_pct": round(trend_pct, 1),
        "mean_peak_ndvi": round(mean_peak, 3),
        "mean_season_length_days": round(sum(s["season_length_days"] for s in seasons) / len(seasons), 0),
    }


def _extract_season(obs: List[Dict], year: int) -> Dict:
    """Extract metrics for a single growing season."""
    ndvi_vals = [o["ndvi"] for o in obs]
    days = [o["doy"] for o in obs]

    peak_idx = ndvi_vals.index(max(ndvi_vals))
    peak_ndvi = ndvi_vals[peak_idx]
    peak_doy = days[peak_idx]

    # Find green-up: last point before peak where NDVI < 30% of peak
    greenup_idx = 0
    threshold = peak_ndvi * 0.3
    for i in range(peak_idx - 1, -1, -1):
        if ndvi_vals[i] < threshold:
            greenup_idx = i
            break

    # Find senescence: first point after peak where NDVI < 30% of peak
    senesc_idx = len(obs) - 1
    for i in range(peak_idx + 1, len(obs)):
        if ndvi_vals[i] < threshold:
            senesc_idx = i
            break

    # Green-up velocity (NDVI/day)
    greenup_days = max(1, days[peak_idx] - days[greenup_idx])
    greenup_vel = (peak_ndvi - ndvi_vals[greenup_idx]) / greenup_days

    # Senescence velocity
    senesc_days = max(1, days[senesc_idx] - days[peak_idx])
    senesc_vel = (peak_ndvi - ndvi_vals[senesc_idx]) / senesc_days

    # Season length
    season_len = days[senesc_idx] - days[greenup_idx]

    # Cumulative NDVI (trapezoidal approximation)
    cum_ndvi = 0
    for i in range(greenup_idx, min(senesc_idx, len(obs) - 1)):
        dt = days[i + 1] - days[i] if i + 1 < len(days) else 1
        cum_ndvi += 0.5 * (ndvi_vals[i] + ndvi_vals[i + 1]) * dt

    return {
        "year": year,
        "peak_ndvi": round(peak_ndvi, 3),
        "peak_doy": peak_doy,
        "greenup_doy": days[greenup_idx],
        "senescence_doy": days[senesc_idx],
        "greenup_velocity": round(greenup_vel * 1000, 2),  # ×1000 for readability
        "senescence_velocity": round(senesc_vel * 1000, 2),
        "season_length_days": max(0, season_len),
        "cumulative_ndvi": round(cum_ndvi, 1),
    }


def _doy(date_str: str) -> int:
    """Day of year from YYYY-MM-DD."""
    try:
        parts = date_str.split("-")
        from datetime import date
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        return d.timetuple().tm_yday
    except:
        return 1

def _year(date_str: str) -> int:
    try:
        return int(date_str.split("-")[0])
    except:
        return 2020
