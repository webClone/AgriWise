"""
Layer 8 Engine: Soil Salinity Leaching Requirement Engine
=========================================================
Calculates the leaching fraction and requirement based on crop-specific
salinity tolerance thresholds (ECe) to wash salts below the root zone.
Based on FAO Irrigation and Drainage Paper 29 / 56.
"""
import logging
import math
from layer8_prescriptive.schema import ActionCard, ActionType, RateRange

logger = logging.getLogger(__name__)

# Crop salinity tolerance thresholds ECe (dS/m) where yield starts to decrease
# FAO-29 / FAO-56 agricultural guidelines
_CROP_SALINITY_THRESHOLD = {
    "corn": 1.7,
    "wheat": 6.0,
    "soybean": 5.0,
    "rice": 3.0,
    "cotton": 7.7,
    "potato": 1.7,
}

class SalinityLeachingEngine:
    """Calculates Leaching Requirement (LR) to flush excessive soil salts."""

    def adjust_irrigation_for_salinity(self, action_cards, crop, soil_salinity_ece, water_salinity_ecw=1.0):
        """
        Adjusts irrigation recommended rates for leaching requirement.
        
        Args:
            action_cards: list of ActionCards
            crop: crop name string
            soil_salinity_ece: current soil salinity (dS/m)
            water_salinity_ecw: irrigation water salinity (dS/m, default 1.0)
            
        Returns:
            list of ActionCards with adjusted rates
        """
        if not action_cards:
            return action_cards

        try:
            soil_salinity_ece = float(soil_salinity_ece)
            if not math.isfinite(soil_salinity_ece) or soil_salinity_ece < 0.0:
                return action_cards
        except (TypeError, ValueError):
            return action_cards

        try:
            water_salinity_ecw = float(water_salinity_ecw)
            if not math.isfinite(water_salinity_ecw) or water_salinity_ecw <= 0.0:
                water_salinity_ecw = 1.0
        except (TypeError, ValueError):
            water_salinity_ecw = 1.0

        crop_threshold = _CROP_SALINITY_THRESHOLD.get(str(crop).lower(), 2.0)
        
        # If soil salinity is below threshold, no leaching requirement is needed
        if soil_salinity_ece <= crop_threshold:
            logger.debug("SalinityLeaching: soil ece (%.2f dS/m) below threshold (%.2f dS/m) for %s. No leaching needed.",
                         soil_salinity_ece, crop_threshold, crop)
            return action_cards
            
        # FAO Leaching Fraction (LF) formula: LF = ECw / (5 * ECe - ECw)
        # where ECe is crop tolerance threshold
        denom = 5.0 * crop_threshold - water_salinity_ecw
        if denom <= 0:
            denom = 1.0
        lf = water_salinity_ecw / denom
        lf = max(0.0, min(0.35, lf)) # Clamp leaching fraction to a maximum of 35% for safety
        
        # Leaching Requirement (LR) = LF / (1.0 - LF)
        lr = lf / (1.0 - lf)
        
        for card in action_cards:
            if card.action_type == ActionType.IRRIGATE and card.rate is not None:
                orig = card.rate.recommended
                hard_cap = card.rate.max_safe
                min_safe = card.rate.min_safe

                # Sanitize orig
                if isinstance(orig, bool) or orig is None:
                    safe_orig = 0.0
                else:
                    try:
                        safe_orig = float(orig)
                        if not math.isfinite(safe_orig):
                            safe_orig = 0.0
                    except (TypeError, ValueError):
                        safe_orig = 0.0
                safe_orig = max(0.0, safe_orig)

                # Sanitize hard_cap
                safe_cap = None
                if hard_cap is not None:
                    if isinstance(hard_cap, bool):
                        safe_cap = 0.0
                    else:
                        try:
                            f_cap = float(hard_cap)
                            if not math.isfinite(f_cap) or f_cap < 0.0:
                                safe_cap = 0.0
                            else:
                                safe_cap = f_cap
                        except (TypeError, ValueError):
                            safe_cap = 0.0

                # Sanitize min_safe
                safe_min = None
                if min_safe is not None:
                    if isinstance(min_safe, bool):
                        safe_min = 0.0
                    else:
                        try:
                            f_min = float(min_safe)
                            if not math.isfinite(f_min) or f_min < 0.0:
                                safe_min = 0.0
                            else:
                                safe_min = f_min
                        except (TypeError, ValueError):
                            safe_min = 0.0

                # Inconsistent bounds: if min_safe > max_safe, clamp min_safe = safe_cap
                if safe_min is not None and safe_cap is not None and safe_min > safe_cap:
                    safe_min = safe_cap

                raw_adj = round(safe_orig * (1.0 + lr), 1)

                if safe_cap is not None and safe_cap >= 0.0:
                    adj = max(0.0, min(raw_adj, safe_cap))
                else:
                    adj = max(0.0, raw_adj)

                if safe_min is not None:
                    adj = max(safe_min, adj)

                if safe_cap is not None:
                    adj = min(adj, safe_cap)
                
                card.rate = RateRange(
                    recommended=adj,
                    min_safe=safe_min if card.rate.min_safe is not None else None,
                    max_safe=safe_cap if card.rate.max_safe is not None else None,
                    unit=card.rate.unit
                )
                
                card.explain += " [Salinity leaching LR={:.1%} adjusted rate from {} to {} {}]".format(
                    lr, orig, adj, card.rate.unit
                )
                logger.info("SalinityLeaching: Adjusted irrigation rate by +%.1f%% due to salinity stress (ECe=%.2f, limit=%.2f)",
                            lr * 100, soil_salinity_ece, crop_threshold)
                            
        return action_cards

salinity_leaching_engine = SalinityLeachingEngine()
