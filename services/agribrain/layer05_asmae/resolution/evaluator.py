"""
ASMAE Resolution Evaluator.

Scores each candidate resolution on four axes:

  1. Operator Quality   — H_t support, condition, row normalization
  2. Scene Diversity    — temporal spread, sub-pixel shift diversity
  3. Identifiability    — can the state vector be recovered at this resolution?
  4. Prior Confidence   — do layer priors provide enough regularization?

The composite score is a weighted combination:
    S = 0.35 * operator_quality
      + 0.25 * scene_diversity
      + 0.25 * identifiability
      + 0.15 * prior_confidence

Design:
  - Evaluator builds H_t at each candidate resolution using V69's operator_builder
  - Shift diversity is measured from coregistration results
  - Identifiability uses a Gramian rank proxy (H^T H diagonal dominance)
  - All scores are [0, 1] — higher is better
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import (
    CANDIDATE_RESOLUTIONS_M,
    DEFAULT_RESOLUTION_M,
    N_STATES,
    RETRO_SCORE_1M_THRESHOLD,
    RETRO_SCORE_5M_THRESHOLD,
)
from ..schema import ASMAESceneRuntime, ObservationOperatorRuntime
from .candidates import CandidateResolution, CandidateSet
from .reason_codes import (
    DEMOTE_CLOUD_COVERAGE,
    DEMOTE_ILL_CONDITIONED,
    DEMOTE_IDENTIFIABILITY_FAIL,
    DEMOTE_LOW_SNR,
    DEMOTE_LOW_SUPPORT,
    DEMOTE_NO_SHIFT_DIVERSITY,
    DEMOTE_REGISTRATION_UNCERTAINTY,
    DEMOTE_TEMPORAL_GAP,
    PROMOTE_HIGH_SUPPORT,
    PROMOTE_IDENTIFIABILITY,
    PROMOTE_SAR_DIVERSITY,
    PROMOTE_SCENE_COUNT,
    PROMOTE_SHIFT_DIVERSITY,
    PROMOTE_TEMPORAL_SPREAD,
    PROMOTE_WELL_CONDITIONED,
    ReasonCodeDetail,
)

logger = logging.getLogger(__name__)

# ── Weight vector for composite score ───────────────────────────────────────

W_OPERATOR = 0.35
W_DIVERSITY = 0.25
W_IDENTIFIABILITY = 0.25
W_PRIOR = 0.15

# ── Thresholds ──────────────────────────────────────────────────────────────

SUPPORT_HIGH = 0.8       # High-support promotion
SUPPORT_LOW = 0.3        # Low-support demotion
SUPPORT_REJECT = 0.1     # Reject outright

CONDITION_GOOD = 10.0    # Well-conditioned
CONDITION_BAD = 100.0    # Ill-conditioned demotion

SHIFT_DIVERSITY_MIN = 0.3   # Minimum shift diversity for promotion

TEMPORAL_SPAN_GOOD = 10     # Days for good temporal spread
TEMPORAL_GAP_MAX = 30       # Max gap between acquisitions (days)

REGISTRATION_RATIO = 3.0    # reg_uncertainty must be < resolution / 3


@dataclass
class EvaluationResult:
    """Full evaluation result for a single candidate resolution."""
    resolution_m: int
    operator_quality: float = 0.0
    scene_diversity: float = 0.0
    identifiability: float = 0.0
    prior_confidence: float = 0.0
    composite_score: float = 0.0

    reasons: List[ReasonCodeDetail] = field(default_factory=list)
    rejected: bool = False
    rejection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolution_m": self.resolution_m,
            "composite_score": round(self.composite_score, 4),
            "operator_quality": round(self.operator_quality, 4),
            "scene_diversity": round(self.scene_diversity, 4),
            "identifiability": round(self.identifiability, 4),
            "prior_confidence": round(self.prior_confidence, 4),
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
            "reasons": [r.to_dict() for r in self.reasons],
        }


def evaluate_candidate(
    candidate: CandidateResolution,
    operators_at_res: List[ObservationOperatorRuntime],
    scenes: List[ASMAESceneRuntime],
    coregistration_results: Optional[List[Any]] = None,
    prior_data: Optional[Dict[str, Any]] = None,
) -> EvaluationResult:
    """Evaluate a single candidate resolution.

    Args:
        candidate: The candidate to evaluate.
        operators_at_res: H_t operators built at this resolution.
        scenes: Full scene stack.
        coregistration_results: Coregistration results from V69.
        prior_data: Layer prior confidence data.

    Returns:
        EvaluationResult with per-axis scores and reason codes.
    """
    res_m = candidate.resolution_m
    result = EvaluationResult(resolution_m=res_m)

    if not operators_at_res:
        result.rejected = True
        result.rejection_reason = "No operators built at this resolution"
        return result

    # ── Axis 1: Operator Quality ────────────────────────────────────
    result.operator_quality = _score_operator_quality(
        res_m, operators_at_res, result.reasons
    )

    # Hard gate: reject if support too low
    avg_support = sum(op.support_score for op in operators_at_res) / len(operators_at_res)
    if avg_support < SUPPORT_REJECT:
        result.rejected = True
        result.rejection_reason = f"Support {avg_support:.3f} < {SUPPORT_REJECT}"
        return result

    # ── Axis 2: Scene Diversity ─────────────────────────────────────
    result.scene_diversity = _score_scene_diversity(
        res_m, scenes, operators_at_res, coregistration_results, result.reasons
    )

    # ── Axis 3: Identifiability ─────────────────────────────────────
    result.identifiability = _score_identifiability(
        res_m, operators_at_res, scenes, result.reasons
    )

    # ── Axis 4: Prior Confidence ────────────────────────────────────
    result.prior_confidence = _score_prior_confidence(
        res_m, prior_data, result.reasons
    )

    # ── Composite Score ─────────────────────────────────────────────
    result.composite_score = (
        W_OPERATOR * result.operator_quality
        + W_DIVERSITY * result.scene_diversity
        + W_IDENTIFIABILITY * result.identifiability
        + W_PRIOR * result.prior_confidence
    )

    return result


# ── Axis 1: Operator Quality ───────────────────────────────────────────────

def _score_operator_quality(
    res_m: int,
    operators: List[ObservationOperatorRuntime],
    reasons: List[ReasonCodeDetail],
) -> float:
    """Score based on H_t quality metrics across all operators."""
    if not operators:
        return 0.0

    n = len(operators)

    # Support score: fraction of valid (non-masked) pixels
    supports = [op.support_score for op in operators]
    avg_support = sum(supports) / n
    min_support = min(supports)

    # Condition number proxy
    conditions = [op.condition_number_proxy for op in operators]
    avg_condition = sum(conditions) / n

    # Registration uncertainty
    reg_uncerts = [op.registration_uncertainty_m for op in operators]
    max_reg_uncert = max(reg_uncerts)

    # ── Score components ────────────────────────────────────────────

    # Support: sigmoid-shaped score
    if avg_support >= SUPPORT_HIGH:
        support_score = 1.0
        reasons.append(ReasonCodeDetail(
            code=PROMOTE_HIGH_SUPPORT,
            category="promote",
            resolution_m=res_m,
            value=avg_support,
            threshold=SUPPORT_HIGH,
        ))
    elif avg_support >= SUPPORT_LOW:
        support_score = (avg_support - SUPPORT_LOW) / (SUPPORT_HIGH - SUPPORT_LOW)
    else:
        support_score = avg_support / SUPPORT_LOW * 0.3
        reasons.append(ReasonCodeDetail(
            code=DEMOTE_LOW_SUPPORT,
            category="demote",
            resolution_m=res_m,
            value=avg_support,
            threshold=SUPPORT_LOW,
        ))

    # Condition: low is better
    if avg_condition <= CONDITION_GOOD:
        condition_score = 1.0
        reasons.append(ReasonCodeDetail(
            code=PROMOTE_WELL_CONDITIONED,
            category="promote",
            resolution_m=res_m,
            value=avg_condition,
            threshold=CONDITION_GOOD,
        ))
    elif avg_condition <= CONDITION_BAD:
        condition_score = 1.0 - (avg_condition - CONDITION_GOOD) / (CONDITION_BAD - CONDITION_GOOD)
    else:
        condition_score = 0.1
        reasons.append(ReasonCodeDetail(
            code=DEMOTE_ILL_CONDITIONED,
            category="demote",
            resolution_m=res_m,
            value=avg_condition,
            threshold=CONDITION_BAD,
        ))

    # Registration: uncertainty must be < resolution / 3
    reg_threshold = res_m / REGISTRATION_RATIO
    if max_reg_uncert > reg_threshold:
        reg_score = max(0.0, 1.0 - (max_reg_uncert - reg_threshold) / res_m)
        reasons.append(ReasonCodeDetail(
            code=DEMOTE_REGISTRATION_UNCERTAINTY,
            category="demote",
            resolution_m=res_m,
            value=max_reg_uncert,
            threshold=reg_threshold,
        ))
    else:
        reg_score = 1.0

    # Weighted combination
    return 0.5 * support_score + 0.3 * condition_score + 0.2 * reg_score


# ── Axis 2: Scene Diversity ────────────────────────────────────────────────

def _score_scene_diversity(
    res_m: int,
    scenes: List[ASMAESceneRuntime],
    operators: List[ObservationOperatorRuntime],
    coreg_results: Optional[List[Any]],
    reasons: List[ReasonCodeDetail],
) -> float:
    """Score based on temporal spread, shift diversity, and sensor mix."""
    if not scenes:
        return 0.0

    n_scenes = len(scenes)
    n_s2 = sum(1 for s in scenes if s.sensor == "S2")
    n_s1 = sum(1 for s in scenes if s.sensor == "S1")

    # ── Temporal spread ─────────────────────────────────────────────
    times = sorted(s.acquisition_time for s in scenes)
    if len(times) >= 2:
        span_days = (times[-1] - times[0]).total_seconds() / 86400
    else:
        span_days = 0.0

    if span_days >= TEMPORAL_SPAN_GOOD:
        temporal_score = 1.0
        reasons.append(ReasonCodeDetail(
            code=PROMOTE_TEMPORAL_SPREAD,
            category="promote",
            resolution_m=res_m,
            value=span_days,
            threshold=float(TEMPORAL_SPAN_GOOD),
        ))
    elif span_days > 0:
        temporal_score = span_days / TEMPORAL_SPAN_GOOD
    else:
        temporal_score = 0.0

    # Check for temporal gaps
    max_gap = 0.0
    for i in range(1, len(times)):
        gap = (times[i] - times[i - 1]).total_seconds() / 86400
        max_gap = max(max_gap, gap)

    if max_gap > TEMPORAL_GAP_MAX:
        temporal_score *= 0.5
        reasons.append(ReasonCodeDetail(
            code=DEMOTE_TEMPORAL_GAP,
            category="demote",
            resolution_m=res_m,
            value=max_gap,
            threshold=float(TEMPORAL_GAP_MAX),
        ))

    # ── Sub-pixel shift diversity ───────────────────────────────────
    shift_diversity = _compute_shift_diversity(coreg_results, res_m)

    if shift_diversity >= SHIFT_DIVERSITY_MIN:
        shift_score = min(1.0, shift_diversity / 0.8)
        reasons.append(ReasonCodeDetail(
            code=PROMOTE_SHIFT_DIVERSITY,
            category="promote",
            resolution_m=res_m,
            value=shift_diversity,
            threshold=SHIFT_DIVERSITY_MIN,
        ))
    else:
        shift_score = shift_diversity / SHIFT_DIVERSITY_MIN * 0.5
        if res_m <= 5:
            reasons.append(ReasonCodeDetail(
                code=DEMOTE_NO_SHIFT_DIVERSITY,
                category="demote",
                resolution_m=res_m,
                value=shift_diversity,
                threshold=SHIFT_DIVERSITY_MIN,
            ))

    # ── Scene count ─────────────────────────────────────────────────
    # More scenes = better, with diminishing returns
    count_score = min(1.0, n_scenes / 8.0)
    if n_scenes >= 5:
        reasons.append(ReasonCodeDetail(
            code=PROMOTE_SCENE_COUNT,
            category="promote",
            resolution_m=res_m,
            value=float(n_scenes),
            threshold=5.0,
        ))

    # ── SAR diversity bonus ─────────────────────────────────────────
    sar_bonus = 0.0
    if n_s1 >= 2 and n_s2 >= 3:
        sar_bonus = 0.15
        reasons.append(ReasonCodeDetail(
            code=PROMOTE_SAR_DIVERSITY,
            category="promote",
            resolution_m=res_m,
            value=float(n_s1),
            message=f"SAR={n_s1}, Optical={n_s2}",
        ))

    # Composite
    diversity = (
        0.35 * temporal_score
        + 0.30 * shift_score
        + 0.20 * count_score
        + 0.15 * min(1.0, sar_bonus / 0.15)
    )

    return min(1.0, diversity + sar_bonus)


def _compute_shift_diversity(
    coreg_results: Optional[List[Any]],
    res_m: int,
) -> float:
    """Compute sub-pixel shift diversity as fraction of pixel size.

    Returns a [0, 1] diversity score. Higher means more diverse
    sub-pixel alignment across scenes (good for super-resolution).
    """
    if not coreg_results:
        return 0.0

    shifts = []
    for cr in coreg_results:
        method = str(getattr(cr, "method", "") or "")
        if (
            bool(getattr(cr, "accepted", False))
            and method.startswith("phase_gradient:")
            and float(getattr(cr, "confidence", 0.0) or 0.0) > 0.0
            and hasattr(cr, "shift_x_m")
            and hasattr(cr, "shift_y_m")
        ):
            # Normalize shift to [0, pixel) range
            sx = cr.shift_x_m % res_m if res_m > 0 else 0.0
            sy = cr.shift_y_m % res_m if res_m > 0 else 0.0
            shifts.append((sx, sy))

    if len(shifts) < 2:
        return 0.0

    # Compute pairwise distance variance
    distances = []
    for i in range(len(shifts)):
        for j in range(i + 1, len(shifts)):
            dx = shifts[i][0] - shifts[j][0]
            dy = shifts[i][1] - shifts[j][1]
            distances.append(math.sqrt(dx * dx + dy * dy))

    if not distances:
        return 0.0

    # Normalize by resolution
    max_possible = math.sqrt(2.0) * res_m  # diagonal of a pixel
    mean_dist = sum(distances) / len(distances)
    diversity = mean_dist / max_possible if max_possible > 0 else 0.0

    return min(1.0, diversity)


# ── Axis 3: Identifiability ────────────────────────────────────────────────

def _score_identifiability(
    res_m: int,
    operators: List[ObservationOperatorRuntime],
    scenes: List[ASMAESceneRuntime],
    reasons: List[ReasonCodeDetail],
) -> float:
    """Score whether the state vector is identifiable at this resolution.

    Uses a Gramian rank proxy: if H_t^T H_t has dominant diagonals
    for each state variable, the state is identifiable.

    For purely geometric operators (no full H_t matrix), we use
    a heuristic based on:
      - number of observations per microzone
      - sensor diversity (optical + SAR covers different state dims)
      - resolution-to-pixel ratio
    """
    if not operators:
        return 0.0

    n_scenes = len(scenes)
    n_sensors = len(set(s.sensor for s in scenes))

    # ── Heuristic identifiability ───────────────────────────────────
    # Observations per zone: each scene provides ~1 observation.
    # At finer resolutions, each pixel covers more zones, so
    # effective observations per zone drops.
    pixel_size = 10.0  # Assume S2 10m
    if operators:
        pixel_size = operators[0].source_resolution_m or 10.0

    zones_per_pixel = (pixel_size / res_m) ** 2 if res_m > 0 else 1.0
    observations_per_zone = n_scenes / max(zones_per_pixel, 1.0)

    # Identifiability threshold: need ~2 observations per zone
    # per state variable being estimated
    n_active_states = min(N_STATES, 5)  # Typically only 5 states are
                                         # directly observable from S2
    min_obs_ratio = n_active_states / max(observations_per_zone, 0.01)

    if observations_per_zone >= 2.0 * n_active_states:
        obs_score = 1.0
    elif observations_per_zone >= n_active_states:
        obs_score = 0.7
    elif observations_per_zone >= 2.0:
        obs_score = 0.4
    else:
        obs_score = 0.1

    # Sensor diversity: more sensors = more observable state dimensions
    sensor_score = min(1.0, n_sensors / 2.0)

    # Support-based: well-supported operators have better identifiability
    avg_support = sum(op.support_score for op in operators) / len(operators)
    support_factor = min(1.0, avg_support / 0.7)

    # ── Gramian proxy (if scipy available) ──────────────────────────
    gramian_score = _gramian_proxy(operators)
    if gramian_score is not None:
        # Use actual Gramian when available
        ident = 0.3 * obs_score + 0.2 * sensor_score + 0.2 * support_factor + 0.3 * gramian_score
    else:
        ident = 0.4 * obs_score + 0.3 * sensor_score + 0.3 * support_factor

    if ident >= 0.7:
        reasons.append(ReasonCodeDetail(
            code=PROMOTE_IDENTIFIABILITY,
            category="promote",
            resolution_m=res_m,
            value=ident,
            threshold=0.7,
            message=f"obs/zone={observations_per_zone:.1f}, sensors={n_sensors}",
        ))
    elif ident < 0.3:
        reasons.append(ReasonCodeDetail(
            code=DEMOTE_IDENTIFIABILITY_FAIL,
            category="demote",
            resolution_m=res_m,
            value=ident,
            threshold=0.3,
            message=f"obs/zone={observations_per_zone:.1f}, sensors={n_sensors}",
        ))

    return ident


def _gramian_proxy(operators: List[ObservationOperatorRuntime]) -> Optional[float]:
    """Compute Gramian diagonal dominance from H_t matrices.

    Evaluate every microzone without materialising H_t^T H_t. For a
    non-negative spatial operator, the calculation is exact; absolute H is
    used as a conservative row-sum bound for unexpected signed weights.

    Returns:
        Score in [0, 1] or None if matrices unavailable.
    """
    try:
        import numpy as np
        from scipy import sparse as sp_lib
    except ImportError:
        return None

    matrices = [op.H_matrix for op in operators if op.H_matrix is not None]
    if not matrices:
        return None

    # Check all matrices have same column count
    n_cols = matrices[0].shape[1]
    if not all(m.shape[1] == n_cols for m in matrices):
        return None

    try:
        gram_diag = np.zeros(n_cols, dtype=float)
        gram_row_abs_sum = np.zeros(n_cols, dtype=float)
        for H in matrices:
            if not sp_lib.issparse(H):
                return None
            H_abs = abs(H)
            gram_diag += np.asarray(H.multiply(H).sum(axis=0)).reshape(-1)
            pixel_abs_sums = np.asarray(H_abs.sum(axis=1)).reshape(-1)
            gram_row_abs_sum += np.asarray(H_abs.T @ pixel_abs_sums).reshape(-1)

        supported = (
            np.isfinite(gram_diag)
            & np.isfinite(gram_row_abs_sum)
            & (gram_row_abs_sum > 1e-10)
        )
        if not np.any(supported):
            return 0.0

        dominance_ratios = np.clip(
            gram_diag[supported] / gram_row_abs_sum[supported], 0.0, 1.0,
        )
        avg_dominance = float(np.mean(dominance_ratios))
        # Perfect diagonal dominance = 1.0, typical values are 0.3-0.8
        return min(1.0, avg_dominance * 1.5)

    except Exception:
        return None


# ── Axis 4: Prior Confidence ───────────────────────────────────────────────

def _score_prior_confidence(
    res_m: int,
    prior_data: Optional[Dict[str, Any]],
    reasons: List[ReasonCodeDetail],
) -> float:
    """Score based on how confident layer priors are at this resolution.

    Finer resolutions need stronger priors for regularization because
    there are more unknowns per observation.
    """
    if prior_data is None:
        base_confidence = 0.0
    else:
        value = prior_data.get("mean_confidence")
        try:
            base_confidence = float(value)
        except (TypeError, ValueError):
            base_confidence = 0.0
        if not math.isfinite(base_confidence):
            base_confidence = 0.0

    # Resolution penalty: finer resolutions need stronger priors
    resolution_factor = res_m / 10.0  # 10m=1.0, 1m=0.1
    adjusted = base_confidence * (0.4 + 0.6 * resolution_factor)

    return min(1.0, max(0.0, adjusted))


# ── Full Evaluation ────────────────────────────────────────────────────────

def evaluate_all_candidates(
    candidate_set: CandidateSet,
    scenes: List[ASMAESceneRuntime],
    operator_builder_fn,
    coregistration_results: Optional[List[Any]] = None,
    prior_data: Optional[Dict[str, Any]] = None,
) -> Dict[int, EvaluationResult]:
    """Evaluate all eligible candidate resolutions.

    Args:
        candidate_set: Pre-filtered candidates.
        scenes: Full scene stack.
        operator_builder_fn: Function(scenes, resolution_m) -> List[operator]
        coregistration_results: From V69 coregistration.
        prior_data: Layer prior confidence data.

    Returns:
        Dict mapping resolution_m -> EvaluationResult.
    """
    results: Dict[int, EvaluationResult] = {}

    for candidate in candidate_set.candidates:
        if not candidate.eligible:
            # Mark ineligible candidates with zero score
            results[candidate.resolution_m] = EvaluationResult(
                resolution_m=candidate.resolution_m,
                rejected=True,
                rejection_reason="Pre-filtered as ineligible",
                reasons=candidate.pre_filter_reasons,
            )
            continue

        # Build operators at this resolution
        try:
            ops_at_res = operator_builder_fn(scenes, candidate.resolution_m)
        except Exception as e:
            logger.warning(
                "Failed to build operators at %dm: %s",
                candidate.resolution_m, e,
            )
            results[candidate.resolution_m] = EvaluationResult(
                resolution_m=candidate.resolution_m,
                rejected=True,
                rejection_reason=f"Operator build failed: {e}",
            )
            continue

        # Evaluate
        ev = evaluate_candidate(
            candidate=candidate,
            operators_at_res=ops_at_res,
            scenes=scenes,
            coregistration_results=coregistration_results,
            prior_data=prior_data,
        )

        # Copy scores back to candidate
        candidate.score = ev.composite_score
        candidate.operator_quality = ev.operator_quality
        candidate.scene_diversity = ev.scene_diversity
        candidate.identifiability = ev.identifiability
        candidate.prior_confidence = ev.prior_confidence

        results[candidate.resolution_m] = ev

    return results
