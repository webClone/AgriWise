import math
from typing import Any

from layer7_planning.schema import SuitabilityState, EvidenceLogit, SuitabilityDriver
from layer7_planning.engines.ccl_crop_library import CropProfile

def compute_biotic_risk(profile: CropProfile, l1_out: Any, l5_out: Any, chat_memory: Any) -> SuitabilityState:
    """
    Engine E: Biotic Risk Forecast Engine (BRF)
    Forecasts early-season risk for fungal/insect using L5, L1, or rotation history.
    """
    logits = []
    confidence = 1.0
    
    # 1. Check L5 (If L5 has explicit threat matrices, we use them)
    if l5_out and hasattr(l5_out, "threat_matrix"):
         # For planting, we care about early stage vulnerabilities
         fungal = next((t for t in l5_out.threat_matrix if "fungal" in t.threat_type.lower()), None)
         if fungal and fungal.risk_score > 0.6:
              logits.append(EvidenceLogit(
                  driver=SuitabilityDriver.DISEASE_PRESSURE,
                  condition=f"Layer 5 reports high fungal pressure (Score {fungal.risk_score:.2f})",
                  logit_delta=-2.5,
                  weight=1.0,
                  source_refs=["L5_BioRisk"]
              ))
         else:
              logits.append(EvidenceLogit(
                  driver=SuitabilityDriver.DISEASE_PRESSURE,
                  condition="Layer 5 reports low/manageable biotic pressure currently.",
                  logit_delta=1.0,
                  weight=0.5,
                  source_refs=["L5_BioRisk"]
              ))
    else:
         # Fallback to L1
         confidence -= 0.3
         
         wet_days = 0
         if l1_out and hasattr(l1_out, "plot_timeseries") and l1_out.plot_timeseries:
             ts = l1_out.plot_timeseries
             wet_days = sum(1 for r in ts[-7:] if (r.get("rain", 0.0) or 0.0) > 2.0)
             
         fc_rain_sum = 0.0
         fc_temp_mean = 15.0
         if l1_out and getattr(l1_out, "forecast_7d", []):
             fc_rain_sum = sum(day.get("precipitation_sum", 0.0) for day in l1_out.forecast_7d)
             temps = [day.get("temperature_2m_mean", 15.0) for day in l1_out.forecast_7d]
             if temps:
                 fc_temp_mean = sum(temps) / len(temps)
                 
         print(f"DEBUG BRF: rain_sum={fc_rain_sum}, temp_mean={fc_temp_mean}")
         
         if fc_rain_sum > 25.0 and fc_temp_mean > 12.0:
             pathogen = "Rhizoctonia / Late Blight" if "potato" in profile.display_name.lower() else "Fusarium / Septoria"
             logits.append(EvidenceLogit(
                 driver=SuitabilityDriver.DISEASE_PRESSURE,
                 condition=f"7-day cumulative rain forecast ({fc_rain_sum:.0f}mm) and stabilizing temperatures (>12°C) significantly elevate {pathogen} risk during emergence.",
                 logit_delta=-2.5,
                 weight=1.2,
                 source_refs=["L1_Forecast7D"]
             ))
         elif wet_days >= 4:
             logits.append(EvidenceLogit(
                 driver=SuitabilityDriver.DISEASE_PRESSURE,
                 condition=f"Recent wet history ({wet_days} days > 2mm) maintains basal damping-off risk for {profile.display_name}, but forecast is drier.",
                 logit_delta=-1.0,
                 weight=1.0,
                 source_refs=["L1_Rain"]
             ))
         else:
             logits.append(EvidenceLogit(
                 driver=SuitabilityDriver.DISEASE_PRESSURE,
                 condition=f"Foliar fungal pressure remains low due to sparse rain history and drier forecast. Monitor post-emergence.",
                 logit_delta=0.8,
                 weight=0.5,
                 source_refs=["L1_Rain", "L1_Forecast7D"]
             ))
                 
    # 2. History Check (Agronomic Memory Synthesizer legacy check)
    if chat_memory and chat_memory.known_context:
         kc = chat_memory.known_context
         prev_crop = (kc.get("previous_crop") or "unknown").lower()
         disease_hist = (kc.get("disease_history") or "none").lower()
         
         if prev_crop != "unknown" and prev_crop in profile.display_name.lower():
             logits.append(EvidenceLogit(
                 driver=SuitabilityDriver.DISEASE_PRESSURE,
                 condition=f"Consecutive planting of {profile.display_name} highly increases soil-borne disease accumulation.",
                 logit_delta=-3.0,
                 weight=1.5,
                 source_refs=["Memory_Rotation"]
             ))
         elif disease_hist != "none" and disease_hist != "unknown":
             logits.append(EvidenceLogit(
                 driver=SuitabilityDriver.DISEASE_PRESSURE,
                 condition=f"Documented disease history: {disease_hist}. Risk remains in soil.",
                 logit_delta=-2.0,
                 weight=1.0,
                 source_refs=["Memory_Disease"]
             ))
             
    if not logits:
        # Default neutral prior
        logits.append(EvidenceLogit(SuitabilityDriver.DISEASE_PRESSURE, "No significant biotic threats detected.", 0.5, 0.5, []))

    # Compute P
    sum_logits = sum(l.logit_delta * l.weight for l in logits)
    prob_ok = 1.0 / (1.0 + math.exp(-sum_logits))
    confidence = max(0.1, min(confidence, 1.0))
    
    severity = "LOW"
    if prob_ok < 0.3: severity = "CRITICAL"
    elif prob_ok < 0.6: severity = "MODERATE"
    
    return SuitabilityState(
        id="BIOTIC_STATE",
        probability_ok=prob_ok,
        confidence=confidence,
        severity=severity,
        drivers_used=[SuitabilityDriver.DISEASE_PRESSURE],
        evidence_trace=logits,
        notes=["Biotic risk synthesized from L5, L1 wetness proxies, and crop rotation history."]
    )
