"""
Module 3: Hydrological Resilience Index
Cross-correlates precipitation with NDVI recovery to measure water use efficiency
and drought memory effects.

Data Integrity Notes:
  - Accepts null_fill_days mask to exclude ERA5 gap-filled days from drought detection
    and PUE calculations, preventing phantom-drought artifacts.
"""
import math
import logging
from typing import Dict, List, Optional, Set, FrozenSet

logger = logging.getLogger("agribrain.hydro_resilience")


def analyze_hydrological_resilience(weather: List[Dict], ndvi_obs: List[Dict],
                                     null_fill_days: FrozenSet[str] = frozenset()) -> Dict:
    """
    Compute precipitation use efficiency, drought recovery tau, and water stress memory.
    
    Args:
        weather: sorted daily weather records with "day", "precipitation", "et0"
        ndvi_obs: NDVI observations with "day", "lai" (LAI = NDVI*3)
        null_fill_days: set of day strings where weather was null-filled (exclude from analysis)
    """
    if len(weather) < 90 or len(ndvi_obs) < 10:
        return {"status": "insufficient_data"}

    # Build lookup tables (exclude null-filled days from precip/ET lookups)
    precip_by_day = {}
    et0_by_day = {}
    for w in weather:
        d = w["day"]
        if d in null_fill_days:
            continue  # Skip null-filled days entirely
        precip_by_day[d] = w.get("precipitation", 0) or 0
        et0_by_day[d] = w.get("et0", 3.0) or 3.0
    
    ndvi_by_day = {}
    for o in ndvi_obs:
        ndvi_by_day[o["day"]] = o.get("lai", 0) / 3.0

    # Use all days for ordering, but track which are real
    all_days = sorted(w["day"] for w in weather)
    real_days = [d for d in all_days if d not in null_fill_days]

    # ---- Precipitation Use Efficiency (PUE) ----
    # Monthly PUE = delta_NDVI / total_precip for each 30-day window
    pue_values = []
    for i in range(0, len(real_days) - 30, 30):
        window_days = real_days[i:i+30]
        total_rain = sum(precip_by_day.get(d, 0) for d in window_days)
        
        # Find NDVI at start and end of window
        ndvi_start = _nearest_ndvi(ndvi_by_day, window_days[0], all_days)
        ndvi_end = _nearest_ndvi(ndvi_by_day, window_days[-1], all_days)
        
        if ndvi_start is not None and ndvi_end is not None and total_rain > 5:
            pue = (ndvi_end - ndvi_start) / total_rain
            pue_values.append(pue)

    avg_pue = sum(pue_values) / len(pue_values) if pue_values else 0

    # ---- Drought Detection & Recovery Tau ----
    # Only use real (non-null-filled) days for drought detection
    droughts = _detect_droughts(real_days, precip_by_day, min_days=14, max_rain=2.0)
    recovery_taus = []
    pre_drought_peaks = []
    post_drought_peaks = []

    for drought_start, drought_end in droughts:
        # NDVI at drought start
        ndvi_pre = _nearest_ndvi(ndvi_by_day, drought_start, all_days)
        if ndvi_pre is None:
            continue
        pre_drought_peaks.append(ndvi_pre)

        # Find recovery: when NDVI returns to 90% of pre-drought level
        recovery_day = None
        for d in all_days:
            if d <= drought_end:
                continue
            ndvi_post = _nearest_ndvi(ndvi_by_day, d, all_days)
            if ndvi_post is not None and ndvi_post >= ndvi_pre * 0.9:
                recovery_day = d
                post_drought_peaks.append(ndvi_post)
                break

        if recovery_day:
            tau = _day_diff(drought_end, recovery_day)
            if 0 < tau < 365:
                recovery_taus.append(tau)

    avg_tau = sum(recovery_taus) / len(recovery_taus) if recovery_taus else None

    # ---- Water Stress Memory ----
    # Does post-drought peak decline over successive droughts?
    degradation = 0
    if len(pre_drought_peaks) >= 2 and len(post_drought_peaks) >= 2:
        first_recovery_ratio = post_drought_peaks[0] / max(0.01, pre_drought_peaks[0])
        last_recovery_ratio = post_drought_peaks[-1] / max(0.01, pre_drought_peaks[-1])
        degradation = (last_recovery_ratio - first_recovery_ratio) * 100

    # Classify
    if avg_tau is None:
        resilience_label = "No Droughts Detected"
    elif avg_tau < 30:
        resilience_label = "Highly Resilient"
    elif avg_tau < 60:
        resilience_label = "Moderately Resilient"
    elif avg_tau < 120:
        resilience_label = "Slow Recovery"
    else:
        resilience_label = "Fragile"

    # Data quality annotation
    null_fill_ratio = len(null_fill_days) / max(1, len(weather))
    quality_note = None
    if null_fill_ratio > 0.2:
        quality_note = f"{len(null_fill_days)} null-filled weather days excluded from drought detection ({null_fill_ratio*100:.0f}%)."

    result = {
        "status": "ok",
        "pue_ndvi_per_mm": round(avg_pue * 1000, 2),
        "drought_events_detected": len(droughts),
        "recovery_tau_days": round(avg_tau, 1) if avg_tau else None,
        "resilience_label": resilience_label,
        "cumulative_degradation_pct": round(degradation, 1),
        "has_permanent_damage": degradation < -5,
        "null_filled_days_excluded": len(null_fill_days),
    }
    if quality_note:
        result["quality_note"] = quality_note
    return result


def _detect_droughts(days, precip, min_days=14, max_rain=2.0):
    """Detect dry spells: >min_days consecutive with <max_rain mm total."""
    droughts = []
    streak_start = None
    streak_rain = 0
    streak_len = 0

    for i, d in enumerate(days):
        rain = precip.get(d, 0)
        if rain < max_rain / min_days:
            if streak_start is None:
                streak_start = d
                streak_rain = 0
                streak_len = 0
            streak_rain += rain
            streak_len += 1
        else:
            if streak_start and streak_len >= min_days:
                droughts.append((streak_start, days[i-1]))
            streak_start = None
            streak_len = 0

    if streak_start and streak_len >= min_days:
        droughts.append((streak_start, days[-1]))

    return droughts


def _nearest_ndvi(ndvi_map, target_day, all_days):
    """Find nearest NDVI observation within ±15 days."""
    if target_day in ndvi_map:
        return ndvi_map[target_day]
    idx = _bisect(all_days, target_day)
    for offset in range(1, 16):
        for di in [idx - offset, idx + offset]:
            if 0 <= di < len(all_days) and all_days[di] in ndvi_map:
                return ndvi_map[all_days[di]]
    return None


def _bisect(sorted_list, val):
    lo, hi = 0, len(sorted_list)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_list[mid] < val:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _day_diff(d1: str, d2: str) -> int:
    try:
        from datetime import date
        p1 = d1.split("-")
        p2 = d2.split("-")
        a = date(int(p1[0]), int(p1[1]), int(p1[2]))
        b = date(int(p2[0]), int(p2[1]), int(p2[2]))
        return abs((b - a).days)
    except:
        return 30
