import math
from datetime import datetime
from typing import List, Dict, Any

from layer7_planning.schema import SuitabilityState, EvidenceLogit, SuitabilityDriver
from layer7_planning.engines.ccl_crop_library import CropProfile

def compute_planting_window(date: datetime, profile: CropProfile, l1_out: Any, region: str = "north_africa") -> SuitabilityState:
    """
    Engine B: Planting Window Engine (PWE)
    Computes whether current date is inside a safe window for a crop.
    Outputs Probability + Confidence.
    """
    logits = []
    
    # 1. Base Region Seasonality Logits
    windows = profile.planting_windows.get(region, [])
    current_month = date.month
    
    in_season = False
    for w in windows:
        start = w["start_month"]
        end = w["end_month"]
        if start <= end and (start <= current_month <= end): in_season = True
        elif start > end and (current_month >= start or current_month <= end): in_season = True
            
    if in_season:
        logits.append(EvidenceLogit(
            driver=SuitabilityDriver.SEASON_LENGTH,
            condition=f"Month {current_month} is inside '{region}' window",
            logit_delta=2.0,
            weight=1.0,
            source_refs=["CCL_Calendar"]
        ))
    else:
        # Penalize heavily if out of season, but don't strictly 0 it out without checking actual temps
        logits.append(EvidenceLogit(
            driver=SuitabilityDriver.SEASON_LENGTH,
            condition=f"Month {current_month} is OUTSIDE '{region}' window",
            logit_delta=-3.0,
            weight=1.0,
            source_refs=["CCL_Calendar"]
        ))
        
    confidence = 1.0 # Base
    
    # 2. Real-Time Temperature Override from L1
    if not l1_out or not hasattr(l1_out, "plot_timeseries") or not l1_out.plot_timeseries:
        confidence -= 0.4 # Penalty for no weather forecast/history
        logits.append(EvidenceLogit(
            driver=SuitabilityDriver.TEMP,
            condition="Missing weather telemetry. Relying purely on calendar normals.",
            logit_delta=0.0,
            weight=0.0,
            source_refs=["L1_Missing"]
        ))
    else:
        # We have L1. Let's check 7-day forecast if it exists, fallback to last 7 days.
        forecasts = getattr(l1_out, "forecast_7d", [])
        source_lbl = "L1_Weather"
        
        if forecasts and len(forecasts) > 0:
            t_min_avg = sum(f.get("temp_min", 15.0) for f in forecasts) / len(forecasts)
            source_lbl = "L1_Forecast"
        else:
            ts = l1_out.plot_timeseries
            last_7d = ts[-7:] if len(ts) >= 7 else ts
            t_min_avg = sum(r.get("t_min", 15.0) or 15.0 for r in last_7d) / len(last_7d) if last_7d else 15.0
        
        # Frost check
        if t_min_avg <= profile.frost_sensitivity_c + 2.0:
            logits.append(EvidenceLogit(
                driver=SuitabilityDriver.FROST_RISK,
                condition=f"Frost risk check: HIGH. Forecasted min temp ({t_min_avg:.1f}C) is dangerously near frost sensitivity ({profile.frost_sensitivity_c}C).",
                logit_delta=-2.5,
                weight=1.0,
                source_refs=[source_lbl]
            ))
        else:
             logits.append(EvidenceLogit(
                driver=SuitabilityDriver.FROST_RISK,
                condition=f"Frost risk check: CLEAR. Forecasted min temp ({t_min_avg:.1f}C) is safe.",
                logit_delta=0.5,
                weight=1.0,
                source_refs=[source_lbl]
            ))
             
        # Germination Check
        if t_min_avg < profile.min_planting_temp_c:
             logits.append(EvidenceLogit(
                driver=SuitabilityDriver.TEMP,
                condition=f"Soil temperature forecast: TOO COLD. ({t_min_avg:.1f}C) is below min germination ({profile.min_planting_temp_c}C).",
                logit_delta=-1.5,
                weight=1.0,
                source_refs=[source_lbl]
            ))
        elif t_min_avg >= profile.optimal_temp_min_c:
             logits.append(EvidenceLogit(
                driver=SuitabilityDriver.TEMP,
                condition=f"Soil temperature forecast: OPTIMAL. ({t_min_avg:.1f}C) is ideal for rapid emergence.",
                logit_delta=1.0,
                weight=1.0,
                source_refs=[source_lbl]
            ))

    # Compute final probability P = 1 / (1 + e^-logit_sum)
    sum_logits = sum(l.logit_delta * l.weight for l in logits)
    prob_ok = 1.0 / (1.0 + math.exp(-sum_logits))
    
    # Cap confidence
    confidence = max(0.1, min(confidence, 1.0))
    
    severity = "LOW"
    if prob_ok < 0.3: severity = "CRITICAL"
    elif prob_ok < 0.6: severity = "MODERATE"
    
    return SuitabilityState(
        id="WINDOW_STATE",
        probability_ok=prob_ok,
        confidence=confidence,
        severity=severity,
        drivers_used=[SuitabilityDriver.SEASON_LENGTH, SuitabilityDriver.TEMP, SuitabilityDriver.FROST_RISK],
        evidence_trace=logits,
        notes=["Probability computed via Sigmoid function over calendar and real-time logic."]
    )
