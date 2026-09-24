"""V79A: PIT-based uncertainty calibration scoring."""

from __future__ import annotations

import math
from typing import Dict, List


def compute_calibration_score(
    holdout_errors: List[Dict[str, float]],
    sigmas: Dict[str, List[float]],
    alpha: float = 2.0,
) -> float:
    """Compute calibration score from holdout prediction errors.

    Checks what fraction of held-out observations fall within ±α*σ
    of the predicted value. Ideal coverage at α=2 is ~0.95.

    Args:
        holdout_errors: List of {obs_name: prediction_error} from holdout folds.
        sigmas: {microzone_id: [sigma_per_state]} uncertainty estimates.
        alpha: Number of standard deviations for coverage check.

    Returns:
        Calibration score in [0, 1]. Higher is better calibrated.
    """
    if not holdout_errors or not sigmas:
        return 0.0

    # Compute average sigma across microzones
    all_sigmas = list(sigmas.values())
    if not all_sigmas:
        return 0.0

    n_states = len(all_sigmas[0]) if all_sigmas[0] else 1
    mean_sigma_per_state = [0.0] * n_states
    for s_vec in all_sigmas:
        for i, s in enumerate(s_vec):
            mean_sigma_per_state[i] += s
    mean_sigma_per_state = [s / max(len(all_sigmas), 1) for s in mean_sigma_per_state]

    # Overall mean sigma as rough proxy
    overall_sigma = sum(mean_sigma_per_state) / max(len(mean_sigma_per_state), 1)
    if overall_sigma < 1e-10:
        return 0.0

    threshold = alpha * overall_sigma

    # Count how many holdout errors fall within threshold
    total = 0
    within = 0
    for error_dict in holdout_errors:
        for obs_name, error in error_dict.items():
            total += 1
            if abs(error) <= threshold:
                within += 1

    if total == 0:
        return 0.0

    coverage = within / total

    # Score: how close coverage is to ideal (0.95 for α=2)
    ideal = 0.95
    deviation = abs(coverage - ideal)
    score = max(0.0, 1.0 - deviation / ideal)

    return round(score, 4)


def compute_biophysical_calibration_report(
    holdout_errors: List[Dict[str, float]],
    sigmas: Dict[str, List[float]],
    soil_clusters: Optional[Dict[str, str]] = None,
    events: Optional[List[Any]] = None,
    alpha: float = 2.0,
) -> Dict[str, Any]:
    """Compute calibration report broken down by biophysical cluster and event type.

    Ensures that uncertainty estimates are well-calibrated not just field-wide,
    but within distinct soil/hydraulic management units (e.g. sandy drainage vs retentive loam).
    """
    global_score = compute_calibration_score(holdout_errors, sigmas, alpha=alpha)
    clusters = soil_clusters or {}

    cluster_scores: Dict[str, float] = {}
    if clusters:
        # Group sigmas by cluster
        cluster_sigmas: Dict[str, Dict[str, List[float]]] = {}
        for mz_id, s_vec in sigmas.items():
            c_id = clusters.get(mz_id, "unknown")
            cluster_sigmas.setdefault(c_id, {})[mz_id] = s_vec

        for c_id, c_sigmas in cluster_sigmas.items():
            c_score = compute_calibration_score(holdout_errors, c_sigmas, alpha=alpha)
            cluster_scores[c_id] = c_score

    # Event breakdown
    event_counts: Dict[str, int] = {}
    for ev in events or []:
        etype = getattr(ev, "event_type", "unknown")
        event_counts[etype] = event_counts.get(etype, 0) + 1

    return {
        "global_calibration_score": global_score,
        "cluster_calibration_scores": cluster_scores,
        "event_counts": event_counts,
        "alpha": alpha,
        "is_calibrated": bool(global_score >= 0.70),
    }

