"""
Module 5: Microclimate Divergence Index
Compares ERA5 grid weather predictions against actual NDVI response
to detect microclimate effects (valley pooling, urban heat, irrigation buffering).

Module 6: Soil-Plant-Atmosphere Continuum (SPAC) Efficiency
Combines ET0, soil moisture proxy, and NDVI to compute transpiration efficiency,
critical moisture threshold, and atmospheric decoupling.

Data Integrity Notes:
  - Both modules accept null_fill_days mask to exclude ERA5 gap-filled data.
  - SPAC module explicitly flags SM as "water_balance_proxy" (not real sensor data).
"""
import math
import logging
from typing import Dict, List, FrozenSet

logger = logging.getLogger("agribrain.microclimate_spac")


# ============================================================================
# Module 5: Microclimate Divergence
# ============================================================================

def analyze_microclimate_divergence(weather: List[Dict], ndvi_obs: List[Dict],
                                     sim_lai: List[float],
                                     null_fill_days: FrozenSet[str] = frozenset()) -> Dict:
    """
    Quantify how much the field's actual behavior diverges from
    what weather alone would predict (ProcessModel residual analysis).
    
    Null-filled weather days are excluded from residual comparisons
    since the model prediction for those days is based on synthetic inputs.
    """
    if len(sim_lai) < 90 or len(ndvi_obs) < 10:
        return {"status": "insufficient_data"}

    # Build day->simulated LAI map
    day_to_sim = {}
    for i, w in enumerate(weather):
        if i < len(sim_lai):
            day_to_sim[w.get("day", "")] = sim_lai[i]

    # Compare observations vs simulation
    residuals = []
    seasonal_residuals = {"winter": [], "spring": [], "summer": [], "autumn": []}
    excluded_comparisons = 0

    for o in ndvi_obs:
        day = o.get("day", "")
        obs_ndvi = o.get("lai", 0) / 3.0
        
        # P1 FIX: Skip comparisons on null-filled days (model prediction is unreliable)
        if day in null_fill_days:
            excluded_comparisons += 1
            continue
        
        if day in day_to_sim and obs_ndvi > 0.05:
            sim_ndvi = day_to_sim[day] / 3.0  # Convert LAI back to NDVI
            residual = obs_ndvi - sim_ndvi  # Positive = field outperforms model
            residuals.append(residual)

            month = _month(day)
            if month in [12, 1, 2]:
                seasonal_residuals["winter"].append(residual)
            elif month in [3, 4, 5]:
                seasonal_residuals["spring"].append(residual)
            elif month in [6, 7, 8]:
                seasonal_residuals["summer"].append(residual)
            else:
                seasonal_residuals["autumn"].append(residual)

    if not residuals:
        return {"status": "no_matching_observations"}

    mean_residual = sum(residuals) / len(residuals)
    abs_residuals = [abs(r) for r in residuals]
    mae = sum(abs_residuals) / len(abs_residuals)

    # Systematic bias: does the field consistently over/under-perform?
    positive_count = sum(1 for r in residuals if r > 0.02)
    negative_count = sum(1 for r in residuals if r < -0.02)
    bias_ratio = positive_count / max(1, positive_count + negative_count)

    if mean_residual > 0.03:
        advantage = "Microclimate Advantage"
        detail = "Field consistently outperforms regional weather prediction"
    elif mean_residual < -0.03:
        advantage = "Microclimate Disadvantage"
        detail = "Field underperforms relative to regional weather"
    else:
        advantage = "Neutral"
        detail = "Field response matches regional weather expectation"

    # Seasonal bias pattern
    seasonal_bias = {}
    for season, vals in seasonal_residuals.items():
        if vals:
            seasonal_bias[season] = {
                "mean_residual": round(sum(vals) / len(vals), 4),
                "n_observations": len(vals),
            }
        else:
            seasonal_bias[season] = {"mean_residual": 0, "n_observations": 0}

    # Model confidence: low MAE = model fits well = less microclimate effect
    if mae < 0.05:
        model_confidence = "High"
    elif mae < 0.10:
        model_confidence = "Moderate"
    else:
        model_confidence = "Low"

    result = {
        "status": "ok",
        "mean_residual_ndvi": round(mean_residual, 4),
        "mae": round(mae, 4),
        "advantage_label": advantage,
        "advantage_detail": detail,
        "bias_ratio": round(bias_ratio, 2),
        "model_confidence": model_confidence,
        "seasonal_bias": seasonal_bias,
        "n_comparisons": len(residuals),
    }
    if excluded_comparisons > 0:
        result["null_filled_comparisons_excluded"] = excluded_comparisons
    return result


# ============================================================================
# Module 6: SPAC Efficiency
# ============================================================================

def analyze_spac_efficiency(weather: List[Dict], ndvi_obs: List[Dict],
                            null_fill_days: FrozenSet[str] = frozenset()) -> Dict:
    """
    Soil-Plant-Atmosphere Continuum analysis:
    - Transpiration Efficiency (biomass per unit ET)
    - Critical Soil Moisture Threshold
    - Atmospheric Decoupling Index
    
    Note: Soil moisture is estimated via a simple water-balance bucket model,
    NOT from real sensor data. This is flagged in the output.
    """
    if len(weather) < 90 or len(ndvi_obs) < 10:
        return {"status": "insufficient_data"}

    # Build daily lookup (exclude null-filled days from TE calculation)
    et0_by_day = {}
    precip_by_day = {}
    sm_proxy = {}  # Cumulative water balance as SM proxy
    
    cumulative_balance = 50.0  # Start at 50% capacity
    null_excluded = 0
    for w in weather:
        day = w.get("day", "")
        et0 = w.get("et0", 3.0) or 3.0
        precip = w.get("precipitation", 0) or 0
        
        is_null = day in null_fill_days
        if is_null:
            null_excluded += 1
        
        # Still build SM proxy for continuity (needs daily balance),
        # but mark null-filled days in ET/precip lookups
        et0_by_day[day] = et0
        precip_by_day[day] = precip
        
        # Simple bucket model for SM proxy (0-100 scale)
        cumulative_balance += precip - et0 * 0.6
        cumulative_balance = max(0, min(100, cumulative_balance))
        sm_proxy[day] = cumulative_balance

    ndvi_by_day = {}
    for o in ndvi_obs:
        ndvi_by_day[o.get("day", "")] = o.get("lai", 0) / 3.0

    # ---- Transpiration Efficiency ----
    # Monthly: NDVI_gain / cumulative_ET0
    # P1 FIX: Exclude windows where >50% of days are null-filled
    all_days = sorted(et0_by_day.keys())
    te_values = []
    for i in range(0, len(all_days) - 30, 30):
        window = all_days[i:i+30]
        
        # Check null-fill contamination in this window
        nf_in_window = sum(1 for d in window if d in null_fill_days)
        if nf_in_window > len(window) * 0.5:
            continue  # Skip heavily contaminated windows
        
        real_days_in_window = [d for d in window if d not in null_fill_days]
        total_et = sum(et0_by_day.get(d, 3) for d in real_days_in_window)
        
        ndvi_start = _nearest(ndvi_by_day, window[0], all_days)
        ndvi_end = _nearest(ndvi_by_day, window[-1], all_days)
        
        if ndvi_start is not None and ndvi_end is not None and total_et > 10:
            # Only count growth periods (positive delta)
            delta = ndvi_end - ndvi_start
            if delta > 0:
                te = delta / total_et
                te_values.append(te)

    avg_te = sum(te_values) / len(te_values) if te_values else 0

    # ---- Critical Soil Moisture Threshold ----
    # Find the SM level below which NDVI starts declining
    sm_ndvi_pairs = []
    for day in sorted(ndvi_by_day.keys()):
        if day in sm_proxy and ndvi_by_day[day] > 0.1:
            sm_ndvi_pairs.append((sm_proxy[day], ndvi_by_day[day]))

    critical_sm = _find_critical_threshold(sm_ndvi_pairs)

    # ---- Decoupling Index ----
    # When ET0 is high but NDVI stays stable → plant has deep water access
    # P1 FIX: Only count real (non-null-filled) high-ET days
    decoupling_events = 0
    total_high_et_days = 0
    
    for day in sorted(ndvi_by_day.keys()):
        if day in null_fill_days:
            continue  # Don't assess decoupling on synthetic weather
        et0 = et0_by_day.get(day, 3)
        if et0 > 5.0:  # High atmospheric demand
            total_high_et_days += 1
            ndvi_now = ndvi_by_day[day]
            # Check if NDVI is stable despite high ET
            ndvi_prev = _nearest(ndvi_by_day, _day_offset(day, -14), all_days)
            if ndvi_prev is not None and ndvi_now >= ndvi_prev * 0.95:
                decoupling_events += 1

    decoupling_ratio = decoupling_events / max(1, total_high_et_days)

    if decoupling_ratio > 0.7:
        decoupling_label = "Strong Decoupling"
        decoupling_detail = "Deep root access or irrigation buffering detected"
    elif decoupling_ratio > 0.4:
        decoupling_label = "Partial Decoupling"
        decoupling_detail = "Moderate buffering capacity"
    else:
        decoupling_label = "Coupled"
        decoupling_detail = "Plant response tracks atmospheric demand closely"

    # TE classification
    if avg_te > 0.003:
        te_label = "Excellent"
    elif avg_te > 0.001:
        te_label = "Good"
    elif avg_te > 0.0005:
        te_label = "Moderate"
    else:
        te_label = "Low"

    return {
        "status": "ok",
        "transpiration_efficiency": round(avg_te * 10000, 2),
        "te_label": te_label,
        "critical_sm_pct": round(critical_sm, 1) if critical_sm else None,
        # P2 FIX: Explicitly flag SM source as proxy, not real sensor data
        "sm_source": "water_balance_proxy",
        "sm_source_note": "Soil moisture is estimated from a precipitation-ET water balance model, not from real soil sensors.",
        "decoupling_index": round(decoupling_ratio, 2),
        "decoupling_label": decoupling_label,
        "decoupling_detail": decoupling_detail,
        "null_filled_days_excluded": null_excluded,
    }


def _find_critical_threshold(sm_ndvi_pairs):
    """Find SM level where NDVI-SM correlation breaks down."""
    if len(sm_ndvi_pairs) < 10:
        return None
    
    # Sort by SM
    pairs = sorted(sm_ndvi_pairs, key=lambda x: x[0])
    
    # Sliding window: find where NDVI starts declining as SM drops
    best_threshold = None
    best_contrast = 0
    
    for pct in range(20, 80, 5):
        idx = int(len(pairs) * pct / 100)
        if idx < 3 or idx >= len(pairs) - 3:
            continue
        below = [p[1] for p in pairs[:idx]]
        above = [p[1] for p in pairs[idx:]]
        
        mean_below = sum(below) / len(below)
        mean_above = sum(above) / len(above)
        contrast = mean_above - mean_below
        
        if contrast > best_contrast:
            best_contrast = contrast
            best_threshold = pairs[idx][0]
    
    return best_threshold


def _nearest(lookup, target, all_days):
    if target in lookup:
        return lookup[target]
    idx = _bisect(all_days, target)
    for off in range(1, 16):
        for di in [idx - off, idx + off]:
            if 0 <= di < len(all_days) and all_days[di] in lookup:
                return lookup[all_days[di]]
    return None


def _bisect(lst, val):
    lo, hi = 0, len(lst)
    while lo < hi:
        mid = (lo + hi) // 2
        if lst[mid] < val:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _month(d):
    try:
        return int(d.split("-")[1])
    except:
        return 1


def _day_offset(day_str, offset_days):
    try:
        from datetime import date, timedelta
        p = day_str.split("-")
        d = date(int(p[0]), int(p[1]), int(p[2]))
        return (d + timedelta(days=offset_days)).isoformat()
    except:
        return day_str
