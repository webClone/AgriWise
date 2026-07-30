"""
Pattern ⑪ — Active Learning Triggers.

Evaluates Kalman filter state uncertainties and telemetry gaps to identify
plots with the highest model entropy. Recommends targeted farmer observations,
drone missions, or IoT sensor deployments to reduce prediction variance.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("agribrain.learning.active_learning")


class ActiveLearningTriggers:
    """Detects model uncertainty thresholds and triggers physical action recommendations."""

    def __init__(self, uncertainty_threshold: float = 0.35):
        self.uncertainty_threshold = uncertainty_threshold

    def evaluate_uncertainty(
        self,
        plot_id: str,
        uncertainty_dict: Dict[str, float],
        days_since_obs: int,
        sensor_inventory: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check Kalman state variances and return recommended information-acquisition actions."""
        recommendations = []

        # 1. Check average state uncertainty
        # Typically the sum of state variances in state_covariance
        lai_var = uncertainty_dict.get("lai", 0.0)
        sm_var = uncertainty_dict.get("soil_moisture", 0.0)
        
        avg_uncertainty = (lai_var + sm_var) / 2.0

        # Gaps analysis
        if avg_uncertainty > self.uncertainty_threshold or days_since_obs > 15:
            logger.info(
                "[ACTIVE_LEARNING] High uncertainty (%.3f) or long gap (%dd) on plot %s",
                avg_uncertainty, days_since_obs, plot_id[:8]
            )

            # Recommend Drone/Optical Survey if S2 has gaps (cloud cover)
            if days_since_obs > 10:
                recommendations.append({
                    "action_id": "active_learning:drone_survey",
                    "action_type": "DRONE_SURVEY",
                    "priority": "MEDIUM" if days_since_obs < 15 else "HIGH",
                    "reason": f"No cloud-free optical observation for {days_since_obs} days has inflated model variance.",
                    "benefit": "Acquire high-resolution RGB/NDVI composite to reset state vector bounds."
                })

            # Recommend Soil Moisture Probe if variance of SM is extremely high
            if sm_var > 0.20 and not sensor_inventory.get("soil_probes_active", False):
                recommendations.append({
                    "action_id": "active_learning:iot_soil_probe",
                    "action_type": "IOT_DEPLOYMENT",
                    "priority": "HIGH" if sm_var > 0.30 else "MEDIUM",
                    "reason": f"High daily soil moisture variance (variance={sm_var:.3f}) makes irrigation forecast unreliable.",
                    "benefit": "Deploying 3-depth telemetry soil moisture probe resolves local percolation rates."
                })

            # Recommend Field Photo (Visual Inspection)
            if lai_var > 0.25:
                recommendations.append({
                    "action_id": "active_learning:farmer_photo",
                    "action_type": "FIELD_VISIT",
                    "priority": "MEDIUM",
                    "reason": f"High LAI biophysical variance (variance={lai_var:.3f}).",
                    "benefit": "Upload a farmer crop photo to visually verify vegetative coverage stage."
                })

        return recommendations
