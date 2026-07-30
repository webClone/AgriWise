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
