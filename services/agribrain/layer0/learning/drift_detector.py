"""
Pattern ⑧ — Distribution Drift Detector.

Implements a Kolmogorov-Smirnov (KS) statistical drift detector to compare recent
observation distributions against baseline historical distributions.
Emits 'calibration_drift' events when sensor or telemetry calibrations shift.
"""

from __future__ import annotations

import math
import logging
from typing import List, Dict, Any, Optional

from services.agribrain.layer0.data_gateway.event_bus import event_bus

logger = logging.getLogger("agribrain.learning.drift")


class DistributionDriftDetector:
    """Detects statistical shifts (sensor drift, climate anomaly) via KS test."""

    def __init__(self, significance_level: float = 0.05):
        self.significance_level = significance_level

    def detect_drift(self, baseline: List[float], recent: List[float], source: str, variable: str) -> Dict[str, Any]:
        """Perform Kolmogorov-Smirnov two-sample test to detect distribution drift.
        
        Null hypothesis (H0): Recent sample belongs to baseline distribution.
        """
        n1 = len(baseline)
        n2 = len(recent)

        if n1 < 5 or n2 < 5:
            return {"drift_detected": False, "reason": "Insufficient sample sizes"}

        # Sort samples to construct empirical CDFs
        s_base = sorted(baseline)
        s_rec = sorted(recent)

        # Merge sorted unique values to evaluate CDF difference
        all_vals = sorted(list(set(s_base + s_rec)))

        max_d = 0.0
        i1 = 0
        i2 = 0
        
        # Calculate maximum difference between empirical CDFs
        for val in all_vals:
            while i1 < n1 and s_base[i1] <= val:
                i1 += 1
            while i2 < n2 and s_rec[i2] <= val:
                i2 += 1
            
            cdf1 = float(i1) / n1
            cdf2 = float(i2) / n2
            
            d = abs(cdf1 - cdf2)
            if d > max_d:
                max_d = d

        # Critical value calculation for alpha = 0.05
        # D_crit = 1.36 * sqrt((n1 + n2)/(n1 * n2))
        c_alpha = 1.36 if self.significance_level == 0.05 else 1.63 # 0.01 level
        critical_d = c_alpha * math.sqrt((n1 + n2) / (n1 * n2))

        drift_detected = max_d > critical_d

        result = {
            "source": source,
            "variable": variable,
            "sample_sizes": (n1, n2),
            "ks_statistic": round(max_d, 4),
            "critical_value": round(critical_d, 4),
            "drift_detected": drift_detected,
        }

        if drift_detected:
            logger.warning(
                "[DRIFT_DETECTOR] Calibration drift detected for %s/%s! KS=%.4f vs Crit=%.4f",
                source, variable, max_d, critical_d
            )
            # Emit notification to EventBus
            event_bus.publish("calibration_drift", {
                "source": source,
                "variable": variable,
                "ks_statistic": max_d,
                "critical_value": critical_d,
                "sample_sizes": [n1, n2],
            })

        return result
