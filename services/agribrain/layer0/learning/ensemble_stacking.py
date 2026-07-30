"""
Pattern ⑫ — Ensemble Model Stacking.

Implements a meta-learner ensemble stacking model that calculates the optimal
weighted consensus across five individual estimators: Kalman, EO Foundation,
Monte Carlo, Seasonal Memory, and Cross-Plot models.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("agribrain.learning.ensemble")


class EnsembleStacking:
    """Meta-learner consensus combining 5 diverse agronomic models."""

    def __init__(self):
        # Default static baseline weights
        self.base_weights = {
            "kalman": 0.40,
            "eo_foundation": 0.30,
            "monte_carlo": 0.15,
            "seasonal_memory": 0.10,
            "cross_plot": 0.05,
        }

    def compute_consensus(
        self,
        predictions: Dict[str, float],
        uncertainties: Dict[str, float],
        source_freshness: Dict[str, float]
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate consensus stacked prediction with dynamically adjusted weights.
        
        Adjusts weights based on:
        1. Model-reported uncertainties (higher uncertainty = lower weight).
        2. Freshness of the data (stale satellite data downweights EO).
        """
        adjusted_weights = {}
        total_w = 0.0

        for model, val in predictions.items():
            base_w = self.base_weights.get(model, 0.05)
            unc = uncertainties.get(model, 0.1) # default low uncertainty
            
            # Penalty for high uncertainty: w = base_w * exp(-2 * unc)
            adj_w = base_w * math.exp(-2.0 * max(0.01, unc))

            # Specific rules for data aging
            if model == "eo_foundation":
                # Staler satellite data diminishes EO trust
                age_days = source_freshness.get("satellite_age_days", 0.0)
                if age_days > 5.0:
                    adj_w *= max(0.1, 1.0 - 0.15 * (age_days - 5.0))

            adjusted_weights[model] = adj_w
            total_w += adj_w

        # Normalize weights so they sum to 1.0
        if total_w <= 0.0:
            normalized_weights = {k: 1.0 / len(predictions) for k in predictions.keys()}
        else:
            normalized_weights = {k: v / total_w for k, v in adjusted_weights.items()}

        # Stacked prediction
        stacked_pred = sum(predictions[model] * normalized_weights[model] for model in predictions.keys())

        return stacked_pred, normalized_weights


# Import math at module load
import math
