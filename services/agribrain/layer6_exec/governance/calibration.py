
from typing import List, Dict, Any

from services.agribrain.layer6_exec.schema import (
    CalibrationProposal, NormalizedEvidence, EvidenceType, ApprovalStatus
)

def propose_calibration(
    evidence_batch: List[NormalizedEvidence],
    feedback_signals: Dict[str, Any] # e.g. outcome metrics
) -> List[CalibrationProposal]:
    """
    Learning Loop: Generate proposals based on contradictions.
    """
    proposals = []
    
    # 1. Scout vs Remote Contradiction
    # Example: Scout says "NO DISEASE" but we had High Disease Pressure
    # Need to iterate evidence and look for specifics
    
    scout_clean_count = 0
    scout_severity_sum = 0.0
    
    for ev in evidence_batch:
        if ev.type == EvidenceType.SCOUT_FORM:
            sev = ev.payload.get("severity", 0.0)
            if sev < 0.1:
                scout_clean_count += 1
            else:
                scout_severity_sum += sev
    
    # Heuristic: If we have many CLEAN scout reports, but the System (L5) said High Risk (simulated check)
    # Ideally logic would compare Outcome vs L5 Prediction
    # Stub Logic:
    if scout_clean_count > 5:
        proposals.append(CalibrationProposal(
            target_layer="L5",
            parameter_key="wdp_fungal_weight",
            current_value=1.6, # From our hardcoded knowledge
            proposed_value=1.4,
            reason="Repeated CLEAN scout reports despite high WDP signals.",
            evidence_support=[],
            status=ApprovalStatus.PROPOSED
        ))

    return proposals
