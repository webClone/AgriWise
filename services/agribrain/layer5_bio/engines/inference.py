
from typing import Dict, List, Any
import math

from services.agribrain.layer5_bio.schema import (
    ThreatId, ThreatClass, BioThreatState, Severity, EvidenceLogit, SpreadPattern
)
from services.agribrain.layer3_decision.schema import Driver
from services.agribrain.layer5_bio.knowledge.threats import THREAT_PRIORS, THREAT_CLASS

def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1/(1+z)
    z = math.exp(x)
    return z/(1+z)

def _logit(p: float) -> float:
    p = max(1e-6, min(1-1e-6, p))
    return math.log(p/(1-p))

def _severity(prob: float, timing_criticality: float = 1.0) -> Severity:
    score = prob * timing_criticality
    if score > 0.85: return Severity.CRITICAL
    if score > 0.65: return Severity.HIGH
    if score > 0.45: return Severity.MODERATE
    return Severity.LOW

def infer_threat_states(
    evidence_by_threat: Dict[ThreatId, List[EvidenceLogit]],
    spread: Dict[str, Any],
    nutrient_output,
    plot_context: Dict[str, Any],
    confidence: float
) -> Dict[str, BioThreatState]:

    pattern = spread["pattern"]
    if isinstance(pattern, SpreadPattern):
        spread_pattern = pattern
    else:
        spread_pattern = SpreadPattern.UNKNOWN

    out: Dict[str, BioThreatState] = {}

    for tid, ev_list in evidence_by_threat.items():
        prior = THREAT_PRIORS.get(tid, 0.08)  # conservative default
        logits = _logit(prior)

        drivers = set()
        for ev in ev_list:
            logits += (ev.weight * ev.logit_delta)
            drivers.add(ev.driver)

        prob = _sigmoid(logits)

        # timing criticality: use phenology if you want (here, safe default)
        timing_crit = 1.0
        sev = _severity(prob, timing_crit)

        out[tid.value] = BioThreatState(
            threat_id=tid,
            threat_class=THREAT_CLASS.get(tid, ThreatClass.DISEASE),
            probability=float(prob),
            confidence=float(confidence),
            severity=sev,
            drivers_used=sorted(list(drivers), key=lambda d: str(d)),
            evidence_trace=ev_list,
            spread_pattern=spread_pattern,
            confounders=[],  # you can map in the runner if you want strict enums here
            notes=""
        )

    # Always add DATA_GAP state if confidence too low
    if confidence < 0.55:
        out[ThreatId.DATA_GAP.value] = BioThreatState(
            threat_id=ThreatId.DATA_GAP,
            threat_class=ThreatClass.SYSTEM,
            probability=0.7,
            confidence=confidence,
            severity=Severity.MODERATE,
            drivers_used=[],
            evidence_trace=[],
            spread_pattern=spread_pattern,
            confounders=[],
            notes="Low data reliability; verify with field scouting/photos."
        )

    return out
