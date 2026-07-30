"""
Weekly DNA Recalibration Engine.

Periodically re-inverts PlotDNA traits using historical and recent observation
data to track soil development, climate shifts, and management effects over time.
Versions the DNA states and feeds calibrations back to the ML patterns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from services.agribrain.layer0.data_gateway.storage_manager import _get_db
from services.agribrain.layer0.data_gateway.event_bus import event_bus
from services.agribrain.layer0.calibration.generative_inversion import trigger_dna_sequencing
from services.agribrain.layer0.learning.adaptive_weighting import AdaptiveObservationWeighter

logger = logging.getLogger("agribrain.learning.dna_recalibration")


class DNARecalibrationScheduler:
    """Manages weekly PlotDNA sequencing and trait evolution versioning."""

    def __init__(self, adaptive_weighter: Optional[AdaptiveObservationWeighter] = None):
        self.adaptive_weighter = adaptive_weighter or AdaptiveObservationWeighter()

    def recalibrate_plot(self, plot_id: str, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """Re-run generative biophysical parameter inversion to calibrate PlotDNA.
        
        Saves versioned DNASnapshots and computes week-over-week trait drifts.
        """
        db = _get_db()
        if db is None:
            logger.warning("[DNA_RECALIB] MongoDB down. Skipping DNA recalibration for plot=%s", plot_id[:8])
            return None

        try:
            # 1. Fetch current PlotDNA traits for comparison
            current_dna = db.PlotDNA.find_one({"plotId": plot_id})
            old_traits = current_dna.get("traits", {}) if current_dna else {}

            # 2. Re-run biophysical parameter inversion
            logger.info("[DNA_RECALIB] Inverting biophysical parameters for plot=%s...", plot_id[:8])
            new_dna_data = trigger_dna_sequencing(plot_id, lat, lng)
            new_traits = new_dna_data.get("traits", {})

            # 3. Compute trait drift metrics (week-over-week Δ per trait)
            drift = {}
            for trait in ["theta_retention", "beta_resilience", "alpha_vigor", "t_shift"]:
                old_val = old_traits.get(trait, 1.0 if trait != "t_shift" else 0.0)
                new_val = new_traits.get(trait, 1.0 if trait != "t_shift" else 0.0)
                drift[trait] = round(new_val - old_val, 4)

            # 4. Save versioned PlotDNASnapshot
            now = datetime.now(timezone.utc)
            snapshot = {
                "plotId": plot_id,
                "timestamp": now,
                "traits": new_traits,
                "decadal_insights": new_dna_data.get("decadal_insights", {}),
                "drift": drift,
                "data_quality": new_dna_data.get("data_quality", {}),
            }
            db.PlotDNASnapshot.insert_one(snapshot)

            # 5. Update main PlotDNA document
            db.PlotDNA.update_one(
                {"plotId": plot_id},
                {
                    "$set": {
                        "traits": new_traits,
                        "decadal_insights": new_dna_data.get("decadal_insights", {}),
                        "advanced_phenometrics": new_dna_data.get("advanced_phenometrics", {}),
                        "lastRecalibrated": now,
                    }
                },
                upsert=True
            )

            logger.info(
                "[DNA_RECALIB] DNA Recalibrated for plot=%s. Traits: %s. Drift: %s",
                plot_id[:8], new_traits, drift
            )

            # 6. Recalibrate Adaptive Weighting R-values for this plot
            self.adaptive_weighter.weekly_batch_recalibrate(plot_id)

            # 7. Emit EventBus notification
            event_bus.publish("dna_recalibrated", {
                "plot_id": plot_id,
                "traits": new_traits,
                "drift": drift,
                "timestamp": now.isoformat()
            })

            return new_dna_data

        except Exception as e:
            logger.error("[DNA_RECALIB] DNA Recalibration failed for plot=%s: %s", plot_id[:8], e)
            return None

    def recalibrate_all_active(self) -> int:
        """Weekly batch: re-invert DNA for all active plots."""
        db = _get_db()
        if db is None:
            return 0

        try:
            # Gather all active plots from PlotDNA
            plots = list(db.PlotDNA.find({}, {"plotId": 1, "lat": 1, "lng": 1}))
            if not plots:
                logger.info("[DNA_RECALIB] No plots found for weekly recalibration.")
                return 0

            logger.info("[DNA_RECALIB] Running weekly DNA recalibration on %d plots...", len(plots))
            success_count = 0
            for p in plots:
                plot_id = p.get("plotId")
                lat = p.get("lat") or 0.0
                lng = p.get("lng") or 0.0
                if plot_id:
                    res = self.recalibrate_plot(plot_id, lat, lng)
                    if res:
                        success_count += 1

            logger.info("[DNA_RECALIB] Completed batch: %d/%d plots recalibrated successfully", success_count, len(plots))
            return success_count

        except Exception as e:
            logger.error("[DNA_RECALIB] Weekly batch recalibration failed: %s", e)
            return 0

    def get_dna_evolution(self, plot_id: str) -> List[Dict[str, Any]]:
        """Return versioned DNA snapshot history for a plot."""
        db = _get_db()
        if db is None:
            return []

        try:
            cursor = db.PlotDNASnapshot.find({"plotId": plot_id}).sort("timestamp", 1)
            evolution = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                if isinstance(doc.get("timestamp"), datetime):
                    doc["timestamp"] = doc["timestamp"].isoformat()
                evolution.append(doc)
            return evolution
        except Exception as e:
            logger.warning("[DNA_RECALIB] Failed to fetch DNA evolution for %s: %s", plot_id, e)
            return []
