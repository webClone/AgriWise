"""
Pattern ⑩ — Ground-Truth Feedback Loop.

Integrates actual yield reports to perform closed-loop calibration of PlotDNA.
If the process model over/under-predicts final yields, this pattern updates
intrinsic vigor and stress traits proportionally to correct decadal drifts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from services.agribrain.layer0.data_gateway.storage_manager import _get_db

logger = logging.getLogger("agribrain.learning.feedback")


class FarmerFeedbackLoop:
    """Closes the loop between actual harvest outcomes and model biophysics."""

    def __init__(self, learning_rate: float = 0.08):
        self.learning_rate = learning_rate

    def apply_yield_feedback(
        self, plot_id: str, crop_type: str, actual_yield: float, predicted_yield: float
    ) -> Optional[Dict[str, float]]:
        """Apply Bayesian correction to PlotDNA traits using harvest performance.
        
        Formula:
          error = (actual - predicted) / predicted
          alpha_vigor_new = alpha_vigor_old * (1.0 + learning_rate * error)
        """
        if predicted_yield <= 0.0 or actual_yield <= 0.0:
            return None

        db = _get_db()
        if db is None:
            return None

        try:
            # 1. Fetch current DNA traits
            dna = db.PlotDNA.find_one({"plotId": plot_id})
            if not dna or "traits" not in dna:
                logger.warning("[FEEDBACK] No PlotDNA found for plot %s to calibrate.", plot_id[:8])
                return None

            traits = dna["traits"]
            old_vigor = traits.get("alpha_vigor", 1.0)
            old_retention = traits.get("theta_retention", 1.0)

            # 2. Compute error
            yield_error = (actual_yield - predicted_yield) / predicted_yield
            
            # 3. Update Vigor (directly proportional to harvest error)
            new_vigor = old_vigor * (1.0 + self.learning_rate * yield_error)
            # Clamp to safe bounds [0.5, 1.5]
            new_vigor = max(0.5, min(1.5, new_vigor))

            # 4. Update Retention (water-holding adjustment, slightly influenced)
            # If yield was underperformed, water retention might have been lower than estimated
            retention_err = yield_error * 0.3
            new_retention = old_retention * (1.0 + self.learning_rate * retention_err)
            new_retention = max(0.5, min(1.5, new_retention))

            updated_traits = {
                "alpha_vigor": round(new_vigor, 4),
                "theta_retention": round(new_retention, 4),
                "beta_resilience": traits.get("beta_resilience", 1.0),
                "t_shift": traits.get("t_shift", 0.0),
            }

            # 5. Persist to MongoDB
            db.PlotDNA.update_one(
                {"plotId": plot_id},
                {
                    "$set": {
                        "traits": updated_traits,
                        "lastFeedbackYield": {
                            "actual": actual_yield,
                            "predicted": predicted_yield,
                            "error_pct": round(yield_error * 100.1, 1),
                            "date": datetime.now(timezone.utc)
                        }
                    }
                }
            )

            # Create versioned snapshot for auditing
            db.PlotDNASnapshot.insert_one({
                "plotId": plot_id,
                "timestamp": datetime.now(timezone.utc),
                "traits": updated_traits,
                "type": "feedback_yield_update",
                "notes": f"Calibrated via actual yield report: actual={actual_yield:.1f} vs pred={predicted_yield:.1f}"
            })

            logger.info(
                "[FEEDBACK] Ground-truth yield applied for plot=%s. Vigor calibrated: %.4f -> %.4f (+%.1f%% error)",
                plot_id[:8], old_vigor, new_vigor, yield_error * 100
            )

            return updated_traits

        except Exception as e:
            logger.error("[FEEDBACK] Ground-truth feedback loop failed for plot %s: %s", plot_id[:8], e)
            return None
