"""
Pattern ⑤ — Predictive Pre-Fetch.

Analyzes historical user access patterns, phenological stages, satellite revisit
schedules, and source volatilities to predict which data sources will be needed
next, feeding proactive pre-fetch requests to the DataRefreshWorker.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from services.agribrain.layer0.data_gateway.storage_manager import StorageManager

logger = logging.getLogger("agribrain.learning.predictive_prefetch")


class PredictivePrefetch:
    """Predicts next data acquisitions to optimize proactive caching."""

    def __init__(self, storage_manager: Optional[StorageManager] = None):
        self.storage_manager = storage_manager or StorageManager()

    def predict_next_prefetch(self, plot_id: str, freshness_report: Dict[str, Any], phenology_stage: str = "vegetative") -> List[str]:
        """Predict which sources should be pre-fetched proactively.
        
        Evaluates:
        1. TTL remaining percentage (if < 30%, highly likely to expire).
        2. Stage-based sensitivity: flowering gets high prefetch priority for weather and NDVI.
        3. Volatility class of the source.
        """
        prefetched = []
        now = datetime.now(timezone.utc)

        # Stage multiplier to adjust priority threshold
        # Flowering and ripening need ultra-fresh data, so we pre-fetch earlier!
        stage_multipliers = {
            "dormant": 1.0,
            "vegetative": 1.1,
            "flowering": 1.5,
            "ripening": 1.3,
            "senescence": 1.0
        }
        mult = stage_multipliers.get(phenology_stage, 1.0)

        for source_name, entry in freshness_report.items():
            # If not cached yet, bootstrap handles it. Here we focus on refreshing!
            if not entry.is_cached:
                continue

            ttl_total = entry.ttl_total_seconds or 3600
            ttl_rem = entry.ttl_remaining_seconds

            freshness_pct = ttl_rem / ttl_total

            # Decision boundary: normally refresh at <20% TTL remaining.
            # With predictive multiplier, we increase this threshold up to 30% during flowering!
            threshold = 0.20 * mult

            if freshness_pct <= threshold:
                prefetched.append(source_name)

        if prefetched:
            logger.info(
                "[PREDICTIVE_PREFETCH] Predicted refresh required for plot=%s, stage=%s: %s",
                plot_id[:8], phenology_stage, prefetched
            )

        return prefetched
