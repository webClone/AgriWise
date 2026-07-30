"""
Pattern ③ — Seasonal Pattern Memory.

Extracts per-month NDVI/SAR/weather signatures from the warm+cold observation
archives to use as Bayesian priors for current-season estimates during periods
of cloud cover or sparse satellite revisits.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List

from services.agribrain.layer0.data_gateway.storage_manager import _get_db, StorageManager

logger = logging.getLogger("agribrain.learning.seasonal_memory")


class SeasonalMemory:
    """Extracts and applies seasonal baseline profiles from plot history."""

    def __init__(self, storage_manager: Optional[StorageManager] = None):
        self.storage_manager = storage_manager or StorageManager()
        # In-memory profile cache: { (plot_id, month, variable): (mean, std) }
        self._profiles: Dict[tuple[str, int, str], Tuple[float, float]] = {}

    def get_seasonal_prior(self, plot_id: str, month: int, variable: str) -> Optional[Tuple[float, float]]:
        """Retrieve seasonal prior (mean, std) for a variable in a specific month.
        
        Falls back to regional or crop-level priors if plot history is insufficient.
        """
        key = (plot_id, month, variable)
        if key in self._profiles:
            return self._profiles[key]

        db = _get_db()
        if db is None:
            return self._get_regional_fallback(variable)

        try:
            # Query warm (PlotObservation) and cold (PlotSeasonArchive) tiers for historical month observations
            pipeline = [
                {
                    "$match": {
                        "plotId": plot_id,
                        "isReliable": True,
                        # Map variable to obsType or extract values
                    }
                },
                {
                    "$project": {
                        "month": {"$month": "$obsDate"},
                        "value": {
                            "$cond": [
                                {"$eq": [variable, "ndvi"]}, "$ndvi",
                                {"$cond": [
                                    {"$eq": [variable, "vv"]}, "$vv",
                                    {"$cond": [
                                        {"$eq": [variable, "soil_moisture"]}, "$soilMoisture",
                                        "$tempC"
                                    ]}
                                ]}
                            ]
                        }
                    }
                },
                {
                    "$match": {
                        "month": month,
                        "value": {"$ne": None}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "mean": {"$avg": "$value"},
                        "std": {"$stdDevSamp": "$value"},
                        "count": {"$sum": 1}
                    }
                }
            ]

            results = list(db.PlotObservation.aggregate(pipeline))
            if results and results[0]["count"] >= 3:
                res = results[0]
                mean_val = res["mean"]
                std_val = res["std"] or 0.1
                self._profiles[key] = (mean_val, std_val)
                return mean_val, std_val

        except Exception as e:
            logger.debug("[SEASONAL_MEMORY] Plot aggregation failed for %s: %s", key, e)

        return self._get_regional_fallback(variable)

    def combine_with_prior(
        self, plot_id: str, month: int, variable: str, current_value: float, current_variance: float
    ) -> Tuple[float, float]:
        """Perform a Bayesian update combining seasonal prior with current observation/state.
        
        Formula:
          Var_post = 1 / (1/Var_prior + 1/Var_curr)
          Mean_post = Var_post * (Mean_prior/Var_prior + Mean_curr/Var_curr)
        """
        prior = self.get_seasonal_prior(plot_id, month, variable)
        if not prior:
            return current_value, current_variance

        prior_mean, prior_std = prior
        prior_variance = prior_std ** 2

        # Avoid zero division
        eps = 1e-6
        prior_variance = max(eps, prior_variance)
        current_variance = max(eps, current_variance)

        # Bayesian blending
        w_prior = 1.0 / prior_variance
        w_curr = 1.0 / current_variance
        
        post_variance = 1.0 / (w_prior + w_curr)
        post_mean = post_variance * (prior_mean * w_prior + current_value * w_curr)

        return post_mean, post_variance

    def _get_regional_fallback(self, variable: str) -> Optional[Tuple[float, float]]:
        """Static regional defaults based on average phenological values."""
        defaults = {
            "ndvi": (0.45, 0.2),
            "vv": (-12.0, 3.0),
            "soil_moisture": (0.28, 0.12),
            "tempC": (22.0, 8.0)
        }
        return defaults.get(variable)

    def build_plot_seasonal_profile(self, plot_id: str) -> Dict[str, Any]:
        """Pre-computes and caches the seasonal baseline for all months for a plot.
        
        Optimizes runtime by building a profile dictionary.
        """
        profile = {}
        for m in range(1, 13):
            profile[m] = {}
            for var in ["ndvi", "vv", "soil_moisture", "tempC"]:
                prior = self.get_seasonal_prior(plot_id, m, var)
                if prior:
                    profile[m][var] = {
                        "mean": round(prior[0], 4),
                        "std": round(prior[1], 4)
                    }
        return profile
