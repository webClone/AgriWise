import math
from typing import Any

from services.agribrain.layer7_planning.schema import SuitabilityState, EvidenceLogit, SuitabilityDriver
from services.agribrain.layer7_planning.engines.ccl_crop_library import CropProfile

def compute_soil_workability(profile: CropProfile, l1_out: Any, soil_texture: str = "unknown") -> SuitabilityState:
    """
    Engine C: Soil Trafficability & Seedbed Engine (STE)
    Determines if field can be worked now (compaction vs emergence risk).
    """
    logits = []
    confidence = 1.0
    
    if not l1_out or not hasattr(l1_out, "plot_timeseries") or not l1_out.plot_timeseries:
        return SuitabilityState(
            id="WORKABILITY_STATE",
            probability_ok=0.5, # Unknown implies middle ground prior
            confidence=0.1, # Extremely low confidence
            severity="MODERATE",
            drivers_used=[SuitabilityDriver.RAIN_7D],
            evidence_trace=[EvidenceLogit(SuitabilityDriver.RAIN_7D, "Missing environmental data", 0, 0, [])],
            notes=["No L1 data to compute workability."]
        )
        
    if soil_texture == "unknown":
         confidence -= 0.3 # We tolerate lack of soil texture but confidence drops
         soil_texture = "loam" # Fallback heuristic
         
    ts = l1_out.plot_timeseries
    last_7d = ts[-7:] if len(ts) >= 7 else ts
    last_3d = ts[-3:] if len(ts) >= 3 else ts
    
    rain_7d = sum(r.get("rain", 0.0) or 0.0 for r in last_7d)
    rain_3d = sum(r.get("rain", 0.0) or 0.0 for r in last_3d)
    
    # 1. Base Soil Compatibility Logit
    if (soil_texture or "").lower() in [s.lower() for s in profile.preferred_soil_type]:
         logits.append(EvidenceLogit(
             driver=SuitabilityDriver.SOIL_TEXTURE,
             condition=f"Soil {soil_texture} is perfect for {profile.display_name}",
             logit_delta=1.5,
             weight=1.0,
             source_refs=["CCL_Soil"]
         ))
    else:
         logits.append(EvidenceLogit(
             driver=SuitabilityDriver.SOIL_TEXTURE,
             condition=f"Soil {soil_texture} is completely unsupported for typical {profile.display_name}",
             logit_delta=-2.0,
             weight=1.0,
             source_refs=["CCL_Soil"]
         ))
         
    # 2. Workability Trafficability Logit (Compaction Risk)
    if "clay" in (soil_texture or "").lower() and rain_3d > 10.0:
         logits.append(EvidenceLogit(
             driver=SuitabilityDriver.RAIN_7D,
             condition=f"High risk of compaction machinery on wet clay (rain_3d: {rain_3d:.1f}mm)",
             logit_delta=-3.0,
             weight=1.5, # High weight
             source_refs=["L1_Rain"]
         ))
         
    # 3. Moisture Profile Logit
    if rain_7d > profile.max_planting_rain_7d_mm:
         logits.append(EvidenceLogit(
             driver=SuitabilityDriver.RAIN_7D,
             condition=f"Recent rain {rain_7d:.1f}mm exceeds {profile.max_planting_rain_7d_mm}mm safe limit (waterlogging)",
             logit_delta=-4.0,
             weight=2.0, # Fatal limitation
             source_refs=["L1_Rain"]
         ))
    elif rain_7d < 2.0:
         # Some crops need pre-irrigation if very dry
         logits.append(EvidenceLogit(
             driver=SuitabilityDriver.RAIN_7D,
             condition=f"Very dry {rain_7d:.1f}mm. Seedbed might be too powdery/dry for emergence without irrigation.",
             logit_delta=-1.0,
             weight=1.0,
             source_refs=["L1_Rain"]
         ))
    else:
         logits.append(EvidenceLogit(
             driver=SuitabilityDriver.RAIN_7D,
             condition=f"Moisture is optimal for seedbed prep ({rain_7d:.1f}mm)",
             logit_delta=2.0,
             weight=1.0,
             source_refs=["L1_Rain"]
         ))
         
    # Compute P
    sum_logits = sum(l.logit_delta * l.weight for l in logits)
    prob_ok = 1.0 / (1.0 + math.exp(-sum_logits))
    confidence = max(0.1, min(confidence, 1.0))
    
    severity = "LOW"
    if prob_ok < 0.2: severity = "CRITICAL"
    elif prob_ok < 0.5: severity = "MODERATE"
    
    return SuitabilityState(
        id="WORKABILITY_STATE",
        probability_ok=prob_ok,
        confidence=confidence,
        severity=severity,
        drivers_used=[SuitabilityDriver.SOIL_TEXTURE, SuitabilityDriver.RAIN_7D],
        evidence_trace=logits,
        notes=["Calculated via logistic sigmoid on soil compatibility and wetness constraints."]
    )
