"""
ASMAE Resolution Candidates.

Generates and filters the set of candidate resolutions to evaluate.

The full candidate set is [10, 9, 8, 7, 6, 5, 4, 3, 2, 1] metres.
Candidates can be pre-filtered based on:
  - Available scene count (not enough scenes → skip fine resolutions)
  - Sensor mix (SAR-only → don't attempt < 5m)
  - Prior certification history (already failed at 3m → skip 2m, 1m)
  - Feature flags (1m disabled → don't attempt)

Design:
  - Always evaluate coarsest (10m) as baseline
  - Evaluate finest-to-coarsest so we can short-circuit on failure
  - Pre-filtering is conservative: it only removes obviously impossible candidates
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..config import (
    CANDIDATE_RESOLUTIONS_M,
    DEFAULT_RESOLUTION_M,
    MIN_S2_SCENES_OPTICAL_MODE,
)
from ..schema import ASMAEInput, ObservationOperatorRuntime
from .reason_codes import (
    DEMOTE_INSUFFICIENT_SCENES,
    GATE_MIN_SCENES,
    INFO_DEFAULT_RESOLUTION,
    ReasonCodeDetail,
)

logger = logging.getLogger(__name__)


# ── Minimum scene requirements by resolution tier ───────────────────────────

# Finer resolutions need MORE scenes because the per-zone observation
# count drops as zone size shrinks (each pixel touches fewer zones).
SCENE_REQUIREMENTS = {
    10: 3,    # Baseline — need at least 3 scenes
    9: 3,
    8: 3,
    7: 4,     # Non-divisor starts needing more diversity
    6: 4,
    5: 4,
    4: 5,
    3: 5,
    2: 6,     # Sub-pixel requires strong temporal stack
    1: 8,     # 1m needs dense temporal coverage
}


@dataclass
class CandidateResolution:
    """A single candidate resolution with pre-filter metadata."""
    resolution_m: int
    eligible: bool = True
    pre_filter_reasons: List[ReasonCodeDetail] = field(default_factory=list)

    # Scores filled in by evaluator
    score: float = 0.0
    operator_quality: float = 0.0
    scene_diversity: float = 0.0
    identifiability: float = 0.0
    prior_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolution_m": self.resolution_m,
            "eligible": self.eligible,
            "score": round(self.score, 4),
            "operator_quality": round(self.operator_quality, 4),
            "scene_diversity": round(self.scene_diversity, 4),
            "identifiability": round(self.identifiability, 4),
            "prior_confidence": round(self.prior_confidence, 4),
            "pre_filter_reasons": [r.to_dict() for r in self.pre_filter_reasons],
        }


@dataclass
class CandidateSet:
    """The full set of candidate resolutions with eligibility status."""
    candidates: List[CandidateResolution] = field(default_factory=list)

    def eligible_candidates(self) -> List[CandidateResolution]:
        """Return only eligible candidates, finest first."""
        return [c for c in self.candidates if c.eligible]

    def all_resolutions(self) -> List[int]:
        """Return all candidate resolutions."""
        return [c.resolution_m for c in self.candidates]

    def eligible_resolutions(self) -> List[int]:
        """Return only eligible resolutions."""
        return [c.resolution_m for c in self.candidates if c.eligible]

    def get(self, resolution_m: int) -> Optional[CandidateResolution]:
        """Get candidate by resolution."""
        for c in self.candidates:
            if c.resolution_m == resolution_m:
                return c
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": len(self.candidates),
            "eligible": len(self.eligible_candidates()),
            "candidates": [c.to_dict() for c in self.candidates],
        }


# ── Candidate Generation ───────────────────────────────────────────────────

def generate_candidates(
    inp: ASMAEInput,
    scenes: List[Any],
    operators: List[ObservationOperatorRuntime],
    certification_history: Optional[Dict[str, Any]] = None,
) -> CandidateSet:
    """Generate and pre-filter the candidate resolution set.

    Args:
        inp: ASMAE input bundle.
        scenes: Scene stack (ASMAESceneRuntime list).
        operators: H_t operators at 10m (from V69).
        certification_history: Optional prior certification data.

    Returns:
        CandidateSet with eligibility flags and pre-filter reasons.
    """
    candidate_set = CandidateSet()

    # Count scenes by sensor
    n_s2 = sum(1 for s in scenes if getattr(s, "sensor", "") == "S2")
    n_s1 = sum(1 for s in scenes if getattr(s, "sensor", "") == "S1")
    n_total = len(scenes)

    # Average operator support at 10m
    avg_support_10m = 0.0
    if operators:
        avg_support_10m = sum(op.support_score for op in operators) / len(operators)
    elif getattr(inp, "archive_metrics", None) or getattr(inp, "retrovalidation_residuals", None):
        avg_support_10m = 0.85
    else:
        avg_support_10m = 1.0

    # Check certification history for prior failures
    failed_resolutions: Set[int] = set()
    if certification_history:
        for res_str, status in certification_history.get("resolution_history", {}).items():
            try:
                res = int(res_str)
                if status in ("failed", "demoted"):
                    failed_resolutions.add(res)
            except (ValueError, TypeError):
                pass

    # Build candidates (coarsest to finest, stored finest-first for evaluation)
    for res_m in sorted(CANDIDATE_RESOLUTIONS_M):
        candidate = CandidateResolution(resolution_m=res_m)
        reasons: List[ReasonCodeDetail] = []

        # ── Pre-filter 1: Minimum scene count ────────────────────────
        # Consider current stack scenes plus validated historical archive depth
        arch_scenes = 0
        if getattr(inp, "archive_metrics", None):
            arch_scenes = int(inp.archive_metrics.get("scene_count", 0) or 0)
        if hasattr(inp, "historical_scene_refs") and inp.historical_scene_refs:
            arch_scenes = max(arch_scenes, len(inp.historical_scene_refs))
        effective_scene_count = max(n_total, arch_scenes)

        min_scenes = SCENE_REQUIREMENTS.get(res_m, 3)
        if effective_scene_count < min_scenes:
            candidate.eligible = False
            reasons.append(ReasonCodeDetail(
                code=DEMOTE_INSUFFICIENT_SCENES,
                category="demote",
                resolution_m=res_m,
                value=float(effective_scene_count),
                threshold=float(min_scenes),
                message=f"Need {min_scenes} scenes, have {effective_scene_count}",
            ))

        # ── Pre-filter 2: Optical mode requires S2 ──────────────────
        arch_optical = 0
        if getattr(inp, "archive_metrics", None):
            arch_optical = int(inp.archive_metrics.get("optical_good_scene_count", 0) or 0)
        effective_s2 = max(n_s2, arch_optical)

        if res_m <= 5 and effective_s2 < MIN_S2_SCENES_OPTICAL_MODE:
            # Fine resolutions need optical — SAR alone is 5m+ only
            if n_s1 > 0 and effective_s2 == 0:
                candidate.eligible = False
                reasons.append(ReasonCodeDetail(
                    code=GATE_MIN_SCENES,
                    category="gate",
                    resolution_m=res_m,
                    value=float(effective_s2),
                    threshold=float(MIN_S2_SCENES_OPTICAL_MODE),
                    message=f"SAR-only stack: {res_m}m requires optical",
                ))

        # ── Pre-filter 3: Prior certification failures ──────────────
        if res_m in failed_resolutions:
            # If this resolution previously failed, require more scenes
            extra_needed = SCENE_REQUIREMENTS.get(res_m, 3) + 3
            if n_total < extra_needed:
                candidate.eligible = False
                reasons.append(ReasonCodeDetail(
                    code=DEMOTE_INSUFFICIENT_SCENES,
                    category="demote",
                    resolution_m=res_m,
                    value=float(n_total),
                    threshold=float(extra_needed),
                    message=f"Prior failure at {res_m}m: need {extra_needed} scenes",
                ))

        # ── Pre-filter 4: 1m hard gate ──────────────────────────────
        if res_m == 1:
            # 1m always starts eligible but will face hard gates in evaluator
            # unless certification mode is enabled or certified retrovalidation is present
            has_retro_cert_1m = (
                isinstance(getattr(inp, "retrovalidation_residuals", None), dict)
                and float(inp.retrovalidation_residuals.get("1") or 0.0) >= 0.75
            )
            if inp.mode not in ("certification", "state_update", "shadow") and not (
                getattr(inp, "experimental_1m", False) or has_retro_cert_1m
            ):
                candidate.eligible = False
                reasons.append(ReasonCodeDetail(
                    code="GATE_1M_MODE_REQUIRED",
                    category="gate",
                    resolution_m=1,
                    message=f"1m requires certification/state_update/shadow mode or retro cert, got {inp.mode}",
                ))

        # ── Pre-filter 5: 10m support too low → skip all fine ──────
        if res_m < 10 and avg_support_10m < 0.2:
            candidate.eligible = False
            reasons.append(ReasonCodeDetail(
                code=DEMOTE_INSUFFICIENT_SCENES,
                category="demote",
                resolution_m=res_m,
                value=avg_support_10m,
                threshold=0.2,
                message="10m support too low for finer resolutions",
            ))

        candidate.pre_filter_reasons = reasons
        candidate_set.candidates.append(candidate)

    # Sort finest-first for evaluation (1m, 2m, ... 10m)
    candidate_set.candidates.sort(key=lambda c: c.resolution_m)

    # Ensure 10m is always eligible (it's the guaranteed fallback)
    baseline = candidate_set.get(DEFAULT_RESOLUTION_M)
    if baseline and not baseline.eligible:
        baseline.eligible = True
        baseline.pre_filter_reasons.append(ReasonCodeDetail(
            code=INFO_DEFAULT_RESOLUTION,
            category="info",
            resolution_m=DEFAULT_RESOLUTION_M,
            message="10m is always eligible as baseline fallback",
        ))

    n_eligible = len(candidate_set.eligible_candidates())
    logger.info(
        "Resolution candidates: %d total, %d eligible (scenes=%d, S2=%d, S1=%d)",
        len(candidate_set.candidates), n_eligible, n_total, n_s2, n_s1,
    )

    return candidate_set
