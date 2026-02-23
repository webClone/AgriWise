import math
from typing import Any

from services.agribrain.layer7_planning.schema import SuitabilityState, EvidenceLogit, SuitabilityDriver
from services.agribrain.layer7_planning.engines.ccl_crop_library import CropProfile

def compute_water_feasibility(profile: CropProfile, l1_out: Any, irrigation_type: str = "unknown") -> SuitabilityState:
    """
    Engine D: Water Availability & Irrigation Feasibility Engine (WFE)
    Checks whether water resources can support the crop given policy and climate.
    """
    logits = []
    confidence = 1.0
    
    # 1. Irrigation Type Prior
    if irrigation_type == "unknown":
         confidence -= 0.3
         logits.append(EvidenceLogit(
             driver=SuitabilityDriver.WATER_QUOTA,
             condition="Missing irrigation context. Relying on conservative rainfed assumptions.",
             logit_delta=-0.5,
             weight=0.5,
             source_refs=["Context_Missing"]
         ))
    elif irrigation_type in ["drip", "sprinkler", "center_pivot"]:
         logits.append(EvidenceLogit(
             driver=SuitabilityDriver.WATER_QUOTA,
             condition=f"High-efficiency irrigation present ({irrigation_type})",
             logit_delta=2.0,
             weight=1.0,
             source_refs=["Context_Present"]
         ))
    elif irrigation_type == "rainfed":
         if profile.varieties and "drought_tolerant" in str(profile.varieties):
              logits.append(EvidenceLogit(
                  driver=SuitabilityDriver.WATER_QUOTA,
                  condition="Rainfed field, but crop variety has drought tolerance.",
                  logit_delta=-0.5, # Slightly risky but viable
                  weight=1.0,
                  source_refs=["Context_Rainfed"]
              ))
         else:
              logits.append(EvidenceLogit(
                  driver=SuitabilityDriver.WATER_QUOTA,
                  condition=f"Rainfed field. {profile.display_name} typically requires irrigation for high yield.",
                  logit_delta=-2.5, # Very risky for water-heavy crops
                  weight=1.5,
                  source_refs=["Context_Rainfed"]
              ))
              
    # 2. Water availability logic (Simulated ET0 vs Rain if L1 is passed)
    if l1_out and hasattr(l1_out, "plot_timeseries") and l1_out.plot_timeseries:
         ts = l1_out.plot_timeseries
         last_14d = ts[-14:] if len(ts) >= 14 else ts
         rain_14d = sum(r.get("rain", 0.0) or 0.0 for r in last_14d)
         et0_14d = sum(r.get("et0", 4.0) or 4.0 for r in last_14d) # fallback 4mm/day
         
         if rain_14d < (et0_14d * 0.2) and irrigation_type == "rainfed":
             logits.append(EvidenceLogit(
                  driver=SuitabilityDriver.WATER_QUOTA,
                  condition=f"Severe moisture deficit (rain {rain_14d:.1f} vs ET0 {et0_14d:.1f}) in rainfed field.",
                  logit_delta=-3.0,
                  weight=2.0, # Fatal limitation
                  source_refs=["L1_Weather"]
             ))
         elif rain_14d > (et0_14d * 0.8):
             logits.append(EvidenceLogit(
                 driver=SuitabilityDriver.RAIN_7D,
                 condition="Strong precipitation regime, reducing irrigation dependency.",
                 logit_delta=1.5,
                 weight=1.0,
                 source_refs=["L1_Weather"]
             ))
             
    # Compute P
    sum_logits = sum(l.logit_delta * l.weight for l in logits)
    prob_ok = 1.0 / (1.0 + math.exp(-sum_logits))
    confidence = max(0.1, min(confidence, 1.0))
    
    severity = "LOW"
    if prob_ok < 0.25: severity = "CRITICAL"
    elif prob_ok < 0.6: severity = "MODERATE"
    
    return SuitabilityState(
        id="WATER_STATE",
        probability_ok=prob_ok,
        confidence=confidence,
        severity=severity,
        drivers_used=[SuitabilityDriver.WATER_QUOTA, SuitabilityDriver.RAIN_7D],
        evidence_trace=logits,
        notes=["Water feasibility determined by irrigation type and recent ET0 vs Rain deficit."]
    )
