
"""
Layer 6 Execution Governance: Calibration Interface.
Delegates to the authoritative calibration engine in layer6_exec.engines.calibration.
"""

from typing import List, Dict, Any, Optional

from layer6_exec.schema import (
    CalibrationProposal, NormalizedEvidence, OutcomeMetric, UpstreamDigest
)
from layer6_exec.engines.calibration import propose_calibration as _propose_calibration_engine

def propose_calibration(
    evidence_batch: List[NormalizedEvidence],
    feedback_signals: Optional[Any] = None,
    digest: Optional[UpstreamDigest] = None,
) -> List[CalibrationProposal]:
    """
    Learning Loop: Generate proposals based on contradictions and ground truth.
    Delegates to the authoritative calibration engine.
    """
    outcomes: List[OutcomeMetric] = []
    if isinstance(feedback_signals, list):
        outcomes = [m for m in feedback_signals if isinstance(m, OutcomeMetric)]
    elif isinstance(feedback_signals, dict):
        raw_outcomes = feedback_signals.get("outcomes", [])
        if isinstance(raw_outcomes, list):
            outcomes = [m for m in raw_outcomes if isinstance(m, OutcomeMetric)]

    up_digest = digest or UpstreamDigest()
    return _propose_calibration_engine(
        evidence=evidence_batch,
        outcomes=outcomes,
        digest=up_digest,
    )

