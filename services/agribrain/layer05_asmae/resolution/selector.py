"""
ASMAE Resolution Selector.

The top-level orchestrator that:
  1. Generates candidate resolutions (candidates.py)
  2. Evaluates each candidate (evaluator.py)
  3. Applies hard gates and policies (policy.py)
  4. Assembles the final ResolutionDecision

This is the single entry point called by the ASMAE engine.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from ..config import CANDIDATE_RESOLUTIONS_M, DEFAULT_RESOLUTION_M
from ..schema import (
    ASMAECertification,
    ASMAEInput,
    ASMAESceneRuntime,
    ObservationOperatorRuntime,
    ResolutionDecision,
)
from .candidates import CandidateSet, generate_candidates
from .evaluator import EvaluationResult, evaluate_all_candidates
from .policy import PolicyResult, apply_policies
from .reason_codes import INFO_BEST_CANDIDATE, INFO_DEFAULT_RESOLUTION, ReasonCodeDetail
from .resource_planner import plan_resolution

logger = logging.getLogger(__name__)


def select_resolution(
    inp: ASMAEInput,
    scenes: List[ASMAESceneRuntime],
    operators_10m: List[ObservationOperatorRuntime],
    operator_builder_fn: Callable[
        [List[ASMAESceneRuntime], int], List[ObservationOperatorRuntime]
    ],
    coregistration_results: Optional[List[Any]] = None,
    certification: Optional[ASMAECertification] = None,
    retro_scores: Optional[Dict[int, float]] = None,
    prior_data: Optional[Dict[str, Any]] = None,
    certification_history: Optional[Dict[str, Any]] = None,
) -> ResolutionDecision:
    """Select the optimal resolution for an ASMAE run.

    This is the top-level entry point for the resolution ladder.

    Pipeline:
        1. Generate candidate set with pre-filtering
        2. Evaluate each eligible candidate using operator_builder_fn
        3. Apply hard gates and policies
        4. Assemble ResolutionDecision

    Args:
        inp: ASMAE input bundle.
        scenes: Scene stack from V68.
        operators_10m: H_t operators at 10m from V69.
        operator_builder_fn: Builds operators at any resolution.
            Signature: (scenes, resolution_m) -> [operator]
        coregistration_results: From V69 coregistration.
        certification: Prior certification status for this plot.
        retro_scores: Historical retrovalidation scores per resolution.
        prior_data: Layer prior confidence data.
        certification_history: Historical resolution pass/fail data.

    Returns:
        ResolutionDecision with full audit trail.
    """
    # ── Step 1: Generate candidates ─────────────────────────────────
    candidate_set = generate_candidates(
        inp=inp,
        scenes=scenes,
        operators=operators_10m,
        certification_history=certification_history,
    )
    resource_plans: Dict[int, Dict[str, Any]] = {}
    if scenes:
        for candidate in candidate_set.candidates:
            plan = plan_resolution(
                scenes[0], candidate.resolution_m, inp.mode, inp,
            )
            resource_plans[candidate.resolution_m] = plan
            if not plan['feasible']:
                candidate.eligible = False
                candidate.pre_filter_reasons.append(ReasonCodeDetail(
                    code='GATE_RESOURCE_MEMORY_LIMIT',
                    category='gate',
                    resolution_m=candidate.resolution_m,
                    value=float(plan['estimated_peak_bytes']),
                    threshold=float(plan['memory_limit_bytes']),
                    message='candidate rejected before H_t/ensemble allocation',
                ))

    # ── Step 2: Evaluate ────────────────────────────────────────────
    # Build a wrapper that uses 10m operators for 10m, and builds new ones
    # for other resolutions
    def _build_at_resolution(
        scenes: List[ASMAESceneRuntime], res_m: int
    ) -> List[ObservationOperatorRuntime]:
        if res_m == DEFAULT_RESOLUTION_M:
            return operators_10m
        return operator_builder_fn(scenes, res_m)

    evaluation_results = evaluate_all_candidates(
        candidate_set=candidate_set,
        scenes=scenes,
        operator_builder_fn=_build_at_resolution,
        coregistration_results=coregistration_results,
        prior_data=prior_data,
    )

    # ── Step 3: Apply policies ──────────────────────────────────────
    policy_result = apply_policies(
        evaluation_results=evaluation_results,
        scenes=scenes,
        certification=certification,
        retro_scores=retro_scores,
        mode=inp.mode,
    )

    # ── Step 4: Assemble ResolutionDecision ─────────────────────────
    # Collect all tested resolutions
    tested = sorted(evaluation_results.keys())

    # Collect candidate scores
    candidate_scores: Dict[int, float] = {}
    for res_m, ev in evaluation_results.items():
        candidate_scores[res_m] = ev.composite_score

    # Collect reason codes
    all_reasons: Dict[int, List[str]] = {}
    for res_m, ev in evaluation_results.items():
        codes = [r.code for r in ev.reasons]
        # Add policy reasons
        for pr in policy_result.policy_reasons.get(res_m, []):
            codes.append(pr.code)
        all_reasons[res_m] = codes
    for candidate in candidate_set.candidates:
        codes = all_reasons.setdefault(candidate.resolution_m, [])
        codes.extend(
            reason.code for reason in candidate.pre_filter_reasons
            if reason.code not in codes
        )

    # Mark best candidate
    eff = policy_result.effective_resolution_m
    if eff in all_reasons:
        all_reasons[eff].append(INFO_BEST_CANDIDATE)

    decision = ResolutionDecision(
        candidate_resolutions_tested_m=tested,
        selected_effective_resolution_m=policy_result.effective_resolution_m,
        selected_visual_resolution_m=policy_result.visual_resolution_m,
        selected_state_update_resolution_m=policy_result.state_update_resolution_m,
        selected_training_resolution_m=policy_result.training_resolution_m,
        research_resolution_m=1,
        safe_for_1m_claim=policy_result.safe_for_1m_claim,
        demoted_candidates=policy_result.demoted_candidates,
        candidate_scores=candidate_scores,
        reason_codes=all_reasons,
        resource_plans=resource_plans,
    )

    logger.info(
        "Resolution selected: effective=%dm (score=%.3f), "
        "tested=%d candidates, demoted=%d",
        decision.selected_effective_resolution_m,
        candidate_scores.get(eff, 0.0),
        len(tested),
        len(decision.demoted_candidates),
    )

    return decision
