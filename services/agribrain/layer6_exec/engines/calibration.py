"""
Engine 5: Calibration — Prediction-vs-Outcome Learning Loop

Compares upstream layer predictions against ground-truth evidence and
outcome metrics to propose parameter adjustments for future runs.

Calibration Channels:
  1. Scout vs. Remote Sensing — Ground-truth correction
  2. Outcome vs. Prediction — Forecast bias detection
  3. Confidence Calibration — Over/under-confidence correction
  4. Threshold Calibration — Decision boundary tuning

Each proposal requires human approval (ApprovalStatus.PROPOSED).
No auto-apply — farmer trust requires transparency.
"""

from typing import Any, Dict, List
from layer6_exec.schema import (
    CalibrationProposal, NormalizedEvidence, EvidenceType,
    ApprovalStatus, OutcomeMetric, OutcomeMetricId,
    UpstreamDigest,
)


def _mean(vals: List[float]) -> float:
    return sum(vals) / max(len(vals), 1) if vals else 0.0


def propose_calibration(
    evidence: List[NormalizedEvidence],
    outcomes: List[OutcomeMetric],
    digest: UpstreamDigest,
) -> List[CalibrationProposal]:
    """Generate calibration proposals from evidence contradictions and outcomes."""
    proposals: List[CalibrationProposal] = []

    # ── Channel 1: Scout vs. Remote Sensing ──────────────────────────────
    _check_scout_vs_remote(evidence, digest, proposals)

    # ── Channel 2: Outcome vs. Prediction ────────────────────────────────
    _check_outcome_bias(outcomes, proposals)

    # ── Channel 3: Confidence Calibration ────────────────────────────────
    _check_confidence_calibration(digest, outcomes, proposals)

    return proposals


def _check_scout_vs_remote(
    evidence: List[NormalizedEvidence],
    digest: UpstreamDigest,
    proposals: List[CalibrationProposal],
) -> None:
    """Channel 1: Ground-truth scout reports vs. remote sensing predictions."""
    scout_clean = 0
    scout_disease = 0
    scout_severities: List[float] = []

    for ev in evidence:
        if ev.type != EvidenceType.SCOUT_FORM:
            continue
        sev = ev.payload.get("severity", 0.0)
        observed = ev.payload.get("observed", "")

        if isinstance(sev, (int, float)):
            scout_severities.append(float(sev))
            if sev < 0.1:
                scout_clean += 1
            elif sev > 0.5:
                scout_disease += 1

        if isinstance(observed, str) and "clean" in observed.lower():
            scout_clean += 1

    # Case A: Many clean scouts but L5 says high fungal risk
    if scout_clean >= 3 and digest.fungal_pressure > 0.6:
        proposals.append(CalibrationProposal(
            target_layer="L5",
            parameter_key="wdp_fungal_weight",
            current_value=1.6,
            proposed_value=1.3,
            reason=(
                f"Repeated CLEAN scout reports ({scout_clean}) contradict "
                f"high WDP fungal signal ({digest.fungal_pressure:.0%}). "
                f"Reduce fungal pressure weight."
            ),
            evidence_support=[f"{scout_clean} clean scouts"],
            confidence=0.65,
            magnitude=0.3,
            status=ApprovalStatus.PROPOSED,
        ))

    # Case B: Scout confirms disease but remote says low risk
    if scout_disease >= 2 and digest.fungal_pressure < 0.3:
        proposals.append(CalibrationProposal(
            target_layer="L5",
            parameter_key="wdp_fungal_weight",
            current_value=1.6,
            proposed_value=2.0,
            reason=(
                f"Scout reports confirm disease ({scout_disease} high-severity) "
                f"but L5 fungal pressure is only {digest.fungal_pressure:.0%}. "
                f"Increase fungal pressure sensitivity."
            ),
            evidence_support=[f"{scout_disease} disease scouts"],
            confidence=0.7,
            magnitude=0.4,
            status=ApprovalStatus.PROPOSED,
        ))

    # Case C: Scout says NDVI looks good but L2 shows declining
    if scout_clean >= 3 and digest.ndvi_trend == "DECLINING":
        proposals.append(CalibrationProposal(
            target_layer="L2",
            parameter_key="ndvi_trend_sensitivity",
            current_value=0.003,
            proposed_value=0.005,
            reason=(
                f"Scout reports show healthy crop but L2 detects DECLINING trend. "
                f"NDVI trend sensitivity may be too aggressive."
            ),
            evidence_support=[f"{scout_clean} clean scouts, NDVI trend=DECLINING"],
            confidence=0.5,
            magnitude=0.002,
            status=ApprovalStatus.PROPOSED,
        ))


def _check_outcome_bias(
    outcomes: List[OutcomeMetric],
    proposals: List[CalibrationProposal],
) -> None:
    """Channel 2: Systematic bias in outcome predictions."""
    if not outcomes:
        return

    ndvi_deltas = [o.delta_value for o in outcomes
                   if o.metric_id == OutcomeMetricId.NDVI_RECOVERY]
    velocity_deltas = [o.delta_value for o in outcomes
                       if o.metric_id == OutcomeMetricId.GROWTH_VELOCITY_RECOVERY]

    # Check for systematic over-prediction (interventions not working)
    if len(ndvi_deltas) >= 3:
        avg_delta = _mean(ndvi_deltas)
        negative_count = sum(1 for d in ndvi_deltas if d < 0)

        if negative_count > len(ndvi_deltas) * 0.7:
            proposals.append(CalibrationProposal(
                target_layer="L6",
                parameter_key="expected_impact_multiplier",
                current_value=1.0,
                proposed_value=0.7,
                reason=(
                    f"Systematic negative outcomes: {negative_count}/{len(ndvi_deltas)} "
                    f"interventions showed negative NDVI delta (avg={avg_delta:.4f}). "
                    f"Reduce expected impact estimates."
                ),
                evidence_support=[f"avg_ndvi_delta={avg_delta:.4f}"],
                confidence=0.6,
                magnitude=0.3,
                status=ApprovalStatus.PROPOSED,
            ))


def _check_confidence_calibration(
    digest: UpstreamDigest,
    outcomes: List[OutcomeMetric],
    proposals: List[CalibrationProposal],
) -> None:
    """Channel 3: Detect over/under-confidence in upstream layers."""
    # Check if high-confidence diagnoses lead to low-confidence outcomes
    high_conf_diag = [d for d in digest.active_diagnoses
                      if d.get("confidence", 0) > 0.8]
    low_conf_outcomes = [o for o in outcomes if o.confidence < 0.3]

    if len(high_conf_diag) >= 2 and len(low_conf_outcomes) >= 2:
        proposals.append(CalibrationProposal(
            target_layer="L3",
            parameter_key="confidence_ceiling",
            current_value=1.0,
            proposed_value=0.85,
            reason=(
                f"High-confidence diagnoses ({len(high_conf_diag)}) yielded "
                f"low-confidence outcomes ({len(low_conf_outcomes)}). "
                f"L3 may be over-confident. Apply confidence ceiling."
            ),
            evidence_support=["over-confidence pattern"],
            confidence=0.55,
            magnitude=0.15,
            status=ApprovalStatus.PROPOSED,
        ))
