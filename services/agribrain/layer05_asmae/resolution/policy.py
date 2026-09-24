"""
ASMAE Resolution Policy.

Hard gates and soft rules that constrain the resolution selector.

Policies encode scientific invariants:
  1. 1m requires explicit certification (retro > 0.75)
  2. Resolution cannot exceed the sensor's Nyquist limit
  3. If operator quality drops below threshold, demote
  4. Visual and state-update resolutions may differ
  5. Research resolution is always produced at 1m (for audit)

Policies are evaluated AFTER the evaluator scores candidates
and BEFORE the selector makes the final pick.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..config import (
    DEFAULT_RESOLUTION_M,
    RETRO_SCORE_1M_THRESHOLD,
    RETRO_SCORE_5M_THRESHOLD,
)
from ..schema import ASMAECertification
from .evaluator import EvaluationResult
from .reason_codes import (
    DEMOTE_LOW_SUPPORT,
    DEMOTE_RETROVALIDATION_FAIL,
    GATE_1M_CERTIFICATION_REQUIRED,
    GATE_1M_RETRO_FAIL,
    GATE_1M_RETRO_PASS,
    GATE_MIN_SUPPORT,
    INFO_RESEARCH_ONLY,
    INFO_VISUAL_OVERRIDE,
    ReasonCodeDetail,
)

logger = logging.getLogger(__name__)


# ── Policy Thresholds ──────────────────────────────────────────────────────

COMPOSITE_MINIMUM = 0.25          # Below this, resolution is rejected
COMPOSITE_CONFIDENCE = 0.50       # Above this, resolution is trusted
SUPPORT_HARD_MINIMUM = 0.15       # Below this, hard reject

# Visual resolution can be finer than effective if operator quality allows
VISUAL_BONUS_MAX = 2              # Visual can be up to 2 steps finer

# Sensor Nyquist limits (finest supportable resolution)
SENSOR_NYQUIST = {
    "S2": 2,       # Sentinel-2: 10m bands → 2m Nyquist (with sub-pixel)
    "S1": 5,       # Sentinel-1 SAR: 10m GRD → 5m Nyquist
    "S5P": 500,    # S5P: 3.5km → not relevant for plot-scale
    "EXTERNAL": 1, # Drones/photos: can be sub-meter
}


@dataclass
class PolicyResult:
    """Result of applying resolution policies."""
    # The effective resolution after policy application
    effective_resolution_m: int = DEFAULT_RESOLUTION_M
    visual_resolution_m: int = DEFAULT_RESOLUTION_M
    state_update_resolution_m: int = DEFAULT_RESOLUTION_M
    training_resolution_m: int = DEFAULT_RESOLUTION_M
    research_resolution_m: int = 1  # Always 1m for research

    safe_for_1m_claim: bool = False

    # Policy actions taken
    demoted_candidates: List[Dict[str, Any]] = field(default_factory=list)
    policy_reasons: Dict[int, List[ReasonCodeDetail]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "effective_resolution_m": self.effective_resolution_m,
            "visual_resolution_m": self.visual_resolution_m,
            "state_update_resolution_m": self.state_update_resolution_m,
            "training_resolution_m": self.training_resolution_m,
            "research_resolution_m": self.research_resolution_m,
            "safe_for_1m_claim": self.safe_for_1m_claim,
            "demoted_candidates": self.demoted_candidates,
            "policy_reasons": {
                str(k): [r.to_dict() for r in v]
                for k, v in self.policy_reasons.items()
            },
        }


def apply_policies(
    evaluation_results: Dict[int, EvaluationResult],
    scenes: List[Any],
    certification: Optional[ASMAECertification] = None,
    retro_scores: Optional[Dict[int, float]] = None,
    mode: str = "shadow",
) -> PolicyResult:
    """Apply resolution policies to evaluation results.

    Args:
        evaluation_results: Scores from evaluator.
        scenes: Scene stack for sensor analysis.
        certification: Prior certification status.
        retro_scores: Historical retrovalidation scores per resolution.
        mode: ASMAE mode.

    Returns:
        PolicyResult with final resolution assignments.
    """
    result = PolicyResult()
    retro_scores = retro_scores or {}

    # Determine sensor types present
    sensors = set()
    for s in scenes:
        if hasattr(s, "sensor"):
            sensors.add(s.sensor)

    # ── Pass 1: Hard Gates ──────────────────────────────────────────
    for res_m, ev in sorted(evaluation_results.items()):
        reasons: List[ReasonCodeDetail] = []

        # Gate 1: Composite minimum
        if not ev.rejected and ev.composite_score < COMPOSITE_MINIMUM:
            ev.rejected = True
            ev.rejection_reason = f"Composite {ev.composite_score:.3f} < {COMPOSITE_MINIMUM}"
            reasons.append(ReasonCodeDetail(
                code=GATE_MIN_SUPPORT,
                category="gate",
                resolution_m=res_m,
                value=ev.composite_score,
                threshold=COMPOSITE_MINIMUM,
            ))
            result.demoted_candidates.append({
                "resolution_m": res_m,
                "reason": "composite_below_minimum",
                "score": round(ev.composite_score, 4),
            })

        # Gate 2: Support hard minimum
        if not ev.rejected and ev.operator_quality < SUPPORT_HARD_MINIMUM:
            ev.rejected = True
            ev.rejection_reason = f"Operator quality {ev.operator_quality:.3f} < {SUPPORT_HARD_MINIMUM}"
            reasons.append(ReasonCodeDetail(
                code=DEMOTE_LOW_SUPPORT,
                category="demote",
                resolution_m=res_m,
                value=ev.operator_quality,
                threshold=SUPPORT_HARD_MINIMUM,
            ))

        # Gate 3: Sensor Nyquist limit
        from ..evidence_classifier import _is_valid_proof
        has_certified_trust_root = any(_is_valid_proof(s) for s in scenes)
        has_retro_cert = retro_scores.get(res_m, 0.0) >= RETRO_SCORE_1M_THRESHOLD
        finest_nyquist = min(
            SENSOR_NYQUIST.get(s, 10) for s in sensors
        ) if sensors else 10
        if res_m < finest_nyquist:
            # Only reject if no external data, certified trust root, or certified retrovalidation can fill the gap
            if "EXTERNAL" not in sensors and not has_certified_trust_root and not has_retro_cert:
                ev.rejected = True
                ev.rejection_reason = f"{res_m}m exceeds Nyquist limit {finest_nyquist}m"
                result.demoted_candidates.append({
                    "resolution_m": res_m,
                    "reason": "exceeds_nyquist",
                    "sensor_limit": finest_nyquist,
                })

        # Gate 4: 1m certification
        if res_m == 1 and not ev.rejected:
            retro_1m = retro_scores.get(1, 0.0)
            reasons.append(ReasonCodeDetail(
                code=GATE_1M_CERTIFICATION_REQUIRED,
                category="gate",
                resolution_m=1,
                value=retro_1m,
                threshold=RETRO_SCORE_1M_THRESHOLD,
            ))

            if retro_1m >= RETRO_SCORE_1M_THRESHOLD:
                result.safe_for_1m_claim = True
                reasons.append(ReasonCodeDetail(
                    code=GATE_1M_RETRO_PASS,
                    category="gate",
                    resolution_m=1,
                    value=retro_1m,
                    threshold=RETRO_SCORE_1M_THRESHOLD,
                ))
            else:
                ev.rejected = True
                ev.rejection_reason = f"1m retro {retro_1m:.3f} < {RETRO_SCORE_1M_THRESHOLD}"
                reasons.append(ReasonCodeDetail(
                    code=GATE_1M_RETRO_FAIL,
                    category="gate",
                    resolution_m=1,
                    value=retro_1m,
                    threshold=RETRO_SCORE_1M_THRESHOLD,
                ))

        # Gate 5: Sub-5m retrovalidation
        if 1 < res_m <= 5 and not ev.rejected:
            retro = retro_scores.get(res_m, 0.0)
            if retro > 0 and retro < RETRO_SCORE_5M_THRESHOLD:
                reasons.append(ReasonCodeDetail(
                    code=DEMOTE_RETROVALIDATION_FAIL,
                    category="demote",
                    resolution_m=res_m,
                    value=retro,
                    threshold=RETRO_SCORE_5M_THRESHOLD,
                ))
                # Soft demotion: reduce score but don't reject
                ev.composite_score *= 0.5

        if reasons:
            result.policy_reasons[res_m] = reasons

    # ── Pass 2: Select Effective Resolution ─────────────────────────
    # Pick the finest certified resolution meeting confidence threshold,
    # or the finest non-rejected resolution with highest composite score.
    eligible = [
        (res_m, ev)
        for res_m, ev in sorted(evaluation_results.items())
        if not ev.rejected
    ]

    if eligible:
        fine_eligible = [
            (res_m, ev) for res_m, ev in eligible
            if res_m < DEFAULT_RESOLUTION_M
            and ev.composite_score >= COMPOSITE_CONFIDENCE
            and (retro_scores.get(res_m, 0.0) >= RETRO_SCORE_1M_THRESHOLD or res_m >= finest_nyquist)
        ]
        if fine_eligible:
            fine_eligible.sort(key=lambda x: (x[0], -x[1].composite_score))
            best_res, best_ev = fine_eligible[0]
            result.effective_resolution_m = best_res
            if best_res == 1:
                result.safe_for_1m_claim = True
        else:
            eligible.sort(key=lambda x: (-x[1].composite_score, x[0]))
            best_res, best_ev = eligible[0]
            if best_res < DEFAULT_RESOLUTION_M and best_ev.composite_score < COMPOSITE_CONFIDENCE:
                result.effective_resolution_m = DEFAULT_RESOLUTION_M
            else:
                result.effective_resolution_m = best_res
    else:
        result.effective_resolution_m = DEFAULT_RESOLUTION_M

    # ── Pass 3: Visual Resolution ───────────────────────────────────
    # Visual can be slightly finer than effective if operator quality allows
    effective = result.effective_resolution_m
    visual_candidates = [
        (res_m, ev) for res_m, ev in evaluation_results.items()
        if not ev.rejected and res_m <= effective and res_m >= max(1, effective - VISUAL_BONUS_MAX)
    ]

    if visual_candidates:
        # Pick finest visual candidate with adequate operator quality
        visual_candidates.sort(key=lambda x: x[0])
        for vis_res, vis_ev in visual_candidates:
            if vis_ev.operator_quality >= 0.5:
                result.visual_resolution_m = vis_res
                if vis_res < effective:
                    reasons_v = result.policy_reasons.setdefault(vis_res, [])
                    reasons_v.append(ReasonCodeDetail(
                        code=INFO_VISUAL_OVERRIDE,
                        category="info",
                        resolution_m=vis_res,
                        message=f"Visual {vis_res}m finer than effective {effective}m",
                    ))
                break
        else:
            result.visual_resolution_m = effective
    else:
        result.visual_resolution_m = effective

    # ── Pass 4: State Update and Training Resolutions ───────────────
    # State update: same as effective (conservative)
    result.state_update_resolution_m = result.effective_resolution_m

    # Training: can be one step finer for forward-looking data export
    training_candidates = [
        (res_m, ev) for res_m, ev in evaluation_results.items()
        if not ev.rejected and res_m <= effective
    ]
    if training_candidates:
        training_candidates.sort(key=lambda x: x[0])
        result.training_resolution_m = training_candidates[0][0]
    else:
        result.training_resolution_m = effective

    # ── Research: always 1m ─────────────────────────────────────────
    result.research_resolution_m = 1
    r1_reasons = result.policy_reasons.setdefault(1, [])
    r1_reasons.append(ReasonCodeDetail(
        code=INFO_RESEARCH_ONLY,
        category="info",
        resolution_m=1,
        message="Research resolution always 1m",
    ))

    logger.info(
        "Policy result: effective=%dm, visual=%dm, training=%dm, 1m_safe=%s",
        result.effective_resolution_m,
        result.visual_resolution_m,
        result.training_resolution_m,
        result.safe_for_1m_claim,
    )

    return result
