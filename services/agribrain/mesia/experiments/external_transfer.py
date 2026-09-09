"""MESIA E7 External Transfer & Generalization Harness — R6 §10.8 / P8.8.

Evaluates out-of-distribution transfer performance across unseen agricultural sites,
crops (citrus, olive, date palm, wheat), soil textures, and seasons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ExternalTransferEvaluationResult:
    """Outcome of evaluating behaviour models on an unseen external site."""

    transfer_id: str
    target_crop: str
    target_soil_type: str
    unseen_site_id: str
    sample_count: int
    mean_absolute_error_vwc: float
    is_generalization_threshold_met: bool


class ExternalTransferHarness:
    """Runs cross-site external holdout validation."""

    @staticmethod
    def evaluate_unseen_domain_transfer(
        transfer_id: str,
        crop: str,
        soil_type: str,
        site_id: str,
        predicted_vwc: List[float],
        ground_truth_vwc: List[float],
        max_acceptable_mae_vwc: float = 0.04,
    ) -> ExternalTransferEvaluationResult:
        """Compute generalization MAE against independent field truth."""
        raise NotImplementedError("External multi-site validation database required.")
