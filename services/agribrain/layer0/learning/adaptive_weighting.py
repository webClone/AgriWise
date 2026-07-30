"""
Pattern ① — Adaptive Observation Weighting.

Learns per-source, per-plot Kalman observation noise (R) values from
historical prediction residuals.
Updated dynamically during Kalman updates and optionally batch-recalibrated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from services.agribrain.layer0.data_gateway.storage_manager import _get_db

logger = logging.getLogger("agribrain.learning.adaptive_weighting")


class AdaptiveObservationWeighter:
    """Learns optimal Kalman R values (observation noise covariance) per plot/source.
    
    Standard Kalman filters use static R (noise variances). In agriculture, source
    noise varies wildly by season, cloud coverage, coordinate, and sensor quality.
    
    This pattern adapts R based on innovation covariance matching:
      Innovation: v_k = y_k - H * x_k|k-1
      Expected variance: E[v_k * v_k^T] = H * P_k|k-1 * H^T + R_k
      Adaptive estimate: R_k = alpha * R_k-1 + (1 - alpha) * (v_k^2 - H * P * H^T)
    """

    def __init__(self, ema_alpha: float = 0.15):
        self.ema_alpha = ema_alpha
        # In-memory cache to avoid excessive DB reads: { (plot_id, source, obs_type): current_R }
        self._r_cache: Dict[tuple[str, str, str], float] = {}

    def get_adaptive_R(
        self, plot_id: str, source: str, obs_type: str, base_sigma: float, default_R: float
    ) -> float:
        """Retrieve learned R-value, falling back to default if immature or DB down."""
        cache_key = (plot_id, source, obs_type)
        if cache_key in self._r_cache:
            return self._r_cache[cache_key]

        db = _get_db()
        if db is None:
            return default_R

        try:
            doc = db.PlotAdaptiveR.find_one({
                "plotId": plot_id,
                "source": source,
                "obsType": obs_type
            })
            if doc and "R_value" in doc:
                r_val = doc["R_value"]
                self._r_cache[cache_key] = r_val
                return r_val
        except Exception as e:
            logger.warning("[ADAPTIVE_R] DB read failed for %s: %s", cache_key, e)

        # Fallback to default
        return default_R

    def update_residual(
        self,
        plot_id: str,
        source: str,
        obs_type: str,
        residual: float,
        HPHt: float,
        base_sigma: float,
        default_R: float
    ) -> float:
        """Update R-value using a prediction innovation residual.
        
        Calculates:
          Instantaneous R: v_k^2 - HPH^T
          Clamped to prevent negative or extreme values: min = 0.1 * default_R, max = 10 * default_R
          Updates EMA: R_new = alpha * R_old + (1 - alpha) * R_inst
        """
        current_R = self.get_adaptive_R(plot_id, source, obs_type, base_sigma, default_R)
        
        # Calculate residual-based variance
        v_sq = residual ** 2
        inst_R = v_sq - HPHt
        
        # Clamp inst_R to physical/sensible bounds to avoid stability issues
        min_R = 0.05 * (base_sigma ** 2)
        max_R = 20.0 * (base_sigma ** 2)
        inst_R = max(min_R, min(max_R, inst_R))
        
        # Smooth with EMA
        new_R = self.ema_alpha * current_R + (1.0 - self.ema_alpha) * inst_R
        new_R = max(min_R, min(max_R, new_R))
        
        cache_key = (plot_id, source, obs_type)
        self._r_cache[cache_key] = new_R
        
        # Persist to database async/lazy-style
        db = _get_db()
        if db is not None:
            try:
                db.PlotAdaptiveR.update_one(
                    {"plotId": plot_id, "source": source, "obsType": obs_type},
                    {
                        "$set": {
                            "R_value": new_R,
                            "lastUpdated": datetime.now(timezone.utc),
                            "residual_ema": float(v_sq),  # Track raw residuals
                        }
                    },
                    upsert=True
                )
            except Exception as e:
                logger.warning("[ADAPTIVE_R] DB write failed for %s: %s", cache_key, e)
                
        return new_R

    def weekly_batch_recalibrate(self, plot_id: str):
        """Batch update R values from a week of stored innovations.
        
        Called by Weekly DNA Recalibration Engine.
        """
        db = _get_db()
        if db is None:
            return
            
        try:
            # Aggregate recent observations
            observations = list(db.PlotObservation.find({
                "plotId": plot_id,
                "isReliable": True
            }).sort("obsDate", -1).limit(100))
            
            if not observations:
                return

            # Group residuals by source and obsType
            groups: Dict[tuple[str, str], List[float]] = {}
            for obs in observations:
                src = obs.get("source")
                o_type = obs.get("obsType")
                # Estimate residuals from features
                val = obs.get("ndvi") or obs.get("vv") or obs.get("soilMoisture")
                if val is not None and src and o_type:
                    # Look up last predicted state if available
                    key = (src, o_type)
                    if key not in groups:
                        groups[key] = []
                    # Standard deviation of values as a proxy of noise
                    groups[key].append(float(val))

            for (src, o_type), vals in groups.items():
                if len(vals) < 5:
                    continue
                # Variance of recent observations over a window serves as an empirical upper bound
                mean_val = sum(vals) / len(vals)
                variance = sum((x - mean_val)**2 for x in vals) / len(vals)
                
                # Base sigma guess based on source
                base_sigma = 0.1
                default_R = base_sigma ** 2
                
                # Soft recalibrate toward empirical variance
                current_R = self.get_adaptive_R(plot_id, src, o_type, base_sigma, default_R)
                new_R = 0.7 * current_R + 0.3 * max(0.01 * default_R, min(10.0 * default_R, variance))
                
                db.PlotAdaptiveR.update_one(
                    {"plotId": plot_id, "source": src, "obsType": o_type},
                    {
                        "$set": {
                            "R_value": new_R,
                            "lastUpdated": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True
                )
                self._r_cache[(plot_id, src, o_type)] = new_R
                logger.info("[ADAPTIVE_R] Weekly recalibrated R for plot=%s, source=%s/%s: -> %.5f", plot_id[:8], src, o_type, new_R)

        except Exception as e:
            logger.warning("[ADAPTIVE_R] Weekly batch recalibration failed for plot %s: %s", plot_id, e)
