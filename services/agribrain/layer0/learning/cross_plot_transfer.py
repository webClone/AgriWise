"""
Pattern ④ — Cross-Plot Transfer Learning.

Allows cold-start plots (newly created plots with zero or few observations) to
borrow learned agricultural process parameters (like growth rates, soil traits,
and noise distributions) from geographically and phenologically similar
"donor" plots of the same crop type.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple

from services.agribrain.layer0.data_gateway.storage_manager import _get_db

logger = logging.getLogger("agribrain.learning.cross_plot")


class CrossPlotTransfer:
    """Borrows and blends ML parameters from mature donor plots for new plots."""

    def __init__(self, initial_confidence: float = 0.8, decay_per_obs: float = 0.005, floor: float = 0.1):
        self.initial_confidence = initial_confidence
        self.decay_per_obs = decay_per_obs
        self.floor = floor

    def get_transfer_weight(self, own_observations: int) -> float:
        """Compute the trust weight [floor - initial_confidence] for neighbor donor data.
        
        Decreases linearly as the plot acquires its own observations.
        """
        weight = self.initial_confidence - (self.decay_per_obs * own_observations)
        return max(self.floor, min(self.initial_confidence, weight))

    def find_similar_donor_plots(self, plot_id: str, crop_type: str, lat: float, lng: float, limit: int = 5) -> List[Dict[str, Any]]:
        """Query MongoDB to find mature, geographically close plots of the same crop type."""
        db = _get_db()
        if db is None:
            return []

        try:
            # Query mature neighbors
            query = {
                "plotId": {"$ne": plot_id},
                "cropType": crop_type,
                "observationCounts.total": {"$gte": 50}  # Mature donor threshold
            }
            
            donors = list(db.PlotDNA.find(query).limit(50))
            if not donors:
                return []

            # Score similarity based on geographical distance and optional DNA trait similarity
            scored_donors = []
            for d in donors:
                d_lat = d.get("lat") or lat
                d_lng = d.get("lng") or lng
                
                # Haversine distance proxy (simple L2 squared Euclidean distance is sufficient for scaling)
                dist_sq = (d_lat - lat) ** 2 + (d_lng - lng) ** 2
                
                # DNA trait similarity index (if exists)
                trait_sim = 1.0
                d_traits = d.get("traits", {})
                
                scored_donors.append({
                    "plotId": d["plotId"],
                    "distance_score": dist_sq,
                    "traits": d_traits,
                    "lat": d_lat,
                    "lng": d_lng
                })

            # Sort by distance (smaller = closer)
            scored_donors.sort(key=lambda x: x["distance_score"])
            return scored_donors[:limit]

        except Exception as e:
            logger.warning("[CROSS_PLOT] Donor search failed for %s: %s", plot_id, e)
            return []

    def borrow_lai_growth_rate(
        self, plot_id: str, crop_type: str, lat: float, lng: float, 
        own_observations: int, own_rate: float
    ) -> float:
        """Blend plot's own learned growth rate with neighbor donor rates.
        
        New plots borrow optimal process rates to avoid cold-start calibration lag.
        """
        donors = self.find_similar_donor_plots(plot_id, crop_type, lat, lng)
        if not donors:
            return own_rate

        # Get donor rates from MongoDB
        db = _get_db()
        if db is None:
            return own_rate

        donor_rates = []
        for d in donors:
            try:
                # Retrieve learned adaptive rates or traits
                doc = db.PlotDNA.find_one({"plotId": d["plotId"]})
                if doc and "traits" in doc:
                    rate = doc["traits"].get("lai_growth_rate") or doc["traits"].get("alpha_vigor")
                    if rate:
                        donor_rates.append(float(rate))
            except Exception:
                continue

        if not donor_rates:
            return own_rate

        # Average donor rates
        avg_donor_rate = sum(donor_rates) / len(donor_rates)
        
        # Calculate blending weights
        transfer_w = self.get_transfer_weight(own_observations)
        own_w = 1.0 - transfer_w

        blended_rate = (transfer_w * avg_donor_rate) + (own_w * own_rate)
        logger.info(
            "[CROSS_PLOT] Blended growth rate for cold-start plot %s (obs=%d): donor_avg=%.5f vs own=%.5f -> blended=%.5f (donor_w=%.2f)",
            plot_id[:8], own_observations, avg_donor_rate, own_rate, blended_rate, transfer_w
        )
        return blended_rate
