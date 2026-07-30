"""
Pattern ⑥ — Confidence Decay Curves.

Implements source-specific mathematical decay functions to calculate the
real-time confidence (or information value) of observations as time elapses.
"""

from __future__ import annotations

import math
import logging
from typing import Dict, Any

logger = logging.getLogger("agribrain.learning.confidence_decay")


class ConfidenceDecay:
    """Computes real-time confidence scores [0.0 - 1.0] for cached sources."""

    def __init__(self):
        # Time constants (tau) and nominal revisit periods in seconds
        self.configs = {
            "weather": {"type": "exponential", "tau": 1800},         # 30 minutes
            "forecast": {"type": "exponential", "tau": 7200},        # 2 hours
            "sensor": {"type": "exponential", "tau": 3600},          # 1 hour
            "sentinel2": {"type": "linear", "revisit_days": 5},      # 5 days
            "sentinel1": {"type": "linear", "revisit_days": 12},     # 12 days
            "soilgrids": {"type": "constant", "floor": 0.95},        # Years, near constant
        }

    def get_decay_confidence(self, source: str, age_seconds: float) -> float:
        """Compute the decaying confidence score of a source based on its age."""
        # Find matching config
        config = self.configs.get(source)
        if not config:
            # Map other sources dynamically
            if "sentinel2" in source:
                config = self.configs["sentinel2"]
            elif "sentinel1" in source:
                config = self.configs["sentinel1"]
            elif "weather" in source or "meteo" in source:
                config = self.configs["weather"]
            elif "soil" in source:
                config = self.configs["soilgrids"]
            else:
                # Default generic exponential decay (24h)
                config = {"type": "exponential", "tau": 86400}

        decay_type = config["type"]

        if decay_type == "constant":
            # Decays extremely slowly
            floor = config.get("floor", 0.9)
            year_seconds = 365 * 86400
            return max(floor, 1.0 - (0.05 * (age_seconds / year_seconds)))

        elif decay_type == "exponential":
            tau = config.get("tau", 3600)
            return math.exp(-age_seconds / max(1, tau))

        elif decay_type == "linear":
            revisit_days = config.get("revisit_days", 5)
            max_period = revisit_days * 86400
            # Linearly drop confidence down to a floor of 0.1 at revisit threshold
            conf = 1.0 - (0.9 * (age_seconds / max_period))
            return max(0.1, min(1.0, conf))

        return 1.0
