"""
Historical Comparison Engine.
Compares ASMAE output states against historical crop and site profiles
to identify contradictions and evaluate broad rollout readiness.
"""

from __future__ import annotations
from typing import Any, Dict, List

def compare_asmae_with_history(
    plot_id: str,
    asmae_output: Dict[str, Any],
    history: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare ASMAE estimates with known historical records of a plot."""
    contradictions = []
    scores = []
    
    # 1. ASMAE Vigor vs known crop stage
    # If planting date exists and crop stage is dormant, vigor should be very low
    current_vigor = asmae_output.get("vigor", asmae_output.get("state_summary", {}).get("vigor_mean", 0.0))
    crop_stage = history.get("crop_stage", "")
    if crop_stage == "dormant" and current_vigor > 0.35:
        contradictions.append({
            "type": "phenology_mismatch",
            "severity": "medium",
            "asmae": current_vigor,
            "history": f"crop_stage is dormant (expected vigor <= 0.35)"
        })
        scores.append(0.4)
    else:
        scores.append(1.0)
        
    # 2. ASMAE Canopy Water vs irrigation / rain history
    # If no irrigation or rain for 20 days and canopy water is very high, flag mismatch
    canopy_water = asmae_output.get("canopy_water", asmae_output.get("state_summary", {}).get("canopy_water_mean", 0.0))
    has_recent_water = history.get("recent_irrigation_or_rain", True)
    if not has_recent_water and canopy_water > 0.75:
        contradictions.append({
            "type": "irrigation_mismatch",
            "severity": "medium",
            "asmae": canopy_water,
            "history": "no recent irrigation or rain (expected lower canopy water)"
        })
        scores.append(0.5)
    else:
        scores.append(1.0)
        
    # 3. ASMAE Salinity Stress vs known salinity / soil EC
    salinity_stress = asmae_output.get("salinity_stress", asmae_output.get("state_summary", {}).get("salinity_stress_mean", 0.0))
    has_salinity_history = history.get("has_salinity_record", False)
    if salinity_stress > 0.60 and not has_salinity_history:
        contradictions.append({
            "type": "salinity_mismatch",
            "severity": "medium",
            "asmae": salinity_stress,
            "history": "no salinity record"
        })
        scores.append(0.5)
    else:
        scores.append(1.0)
        
    # 4. ASMAE Biotic Confounder vs field notes / photos
    biotic_stress = asmae_output.get("biotic_confounder_risk", asmae_output.get("state_summary", {}).get("biotic_confounder_risk_mean", 0.0))
    has_biotic_history = history.get("has_biotic_record", False)
    if biotic_stress > 0.70 and not has_biotic_history:
        contradictions.append({
            "type": "biotic_mismatch",
            "severity": "low",
            "asmae": biotic_stress,
            "history": "no biotic pressure reported in field notes"
        })
        scores.append(0.7)
    else:
        scores.append(1.0)
        
    # 5. ASMAE Yield sensitivity vs historical yield
    yield_sensitivity = asmae_output.get("yield_sensitivity", 0.0)
    has_yield_history = history.get("has_yield_history", True)
    if yield_sensitivity > 0.8 and not has_yield_history:
        contradictions.append({
            "type": "yield_mismatch",
            "severity": "low",
            "asmae": yield_sensitivity,
            "history": "no yield history to validate sensitivity"
        })
        scores.append(0.8)
    else:
        scores.append(1.0)
        
    # Calculate agreement score
    agreement_score = sum(scores) / len(scores) if scores else 1.0
    
    # Determine rollout recommendation
    # If agreement score < 0.70 or medium/high severity contradictions are found: demote or validation hold
    critical_contradictions = any(c["severity"] in ("medium", "high") for c in contradictions)
    if agreement_score < 0.70 or critical_contradictions:
        recommendation = "continue_internal_validation"
    else:
        recommendation = "promote_rollout_phase"
        
    return {
        "plot_id": plot_id,
        "agreement_score": round(agreement_score, 2),
        "contradictions": contradictions,
        "rollout_recommendation": recommendation
    }

