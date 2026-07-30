"""
Layer 8 Engine: Nitrogen Volatilization & Urease Inhibitor Engine
==================================================================
Evaluates ammonia volatilization risks for urea fertilizers applied on warm,
high-pH soils, and prescribes urease inhibitors (NBPT) to conserve nitrogen.
"""
import logging
import math
from layer8_prescriptive.schema import ActionCard, ActionType

logger = logging.getLogger(__name__)

class VolatilizationInhibitorEngine:
    """Evaluates nitrogen volatilization risk and prescribes urease inhibitors (NBPT)."""

    def evaluate_volatilization(self, action_cards, soil_ph, air_temperature, soil_moisture_pct):
        """
        Calculates volatilization risk and appends NBPT coating instructions to fertilize cards.
        
        Args:
            action_cards: list of ActionCards
            soil_ph: soil pH (standard range 4.0 - 9.0)
            air_temperature: current air temperature (C)
            soil_moisture_pct: soil moisture percentage (0 - 100%)
            
        Returns:
            list of ActionCards
        """
        # Volatilization risk is high on high-pH (alkaline) soils, high temperature, and dry surface soils
        # Logit-like sigmoidal pH multiplier
        ph_factor = 1.0 / (1.0 + math.exp(-(soil_ph - 7.0)))
        
        # Temperature scaling (zero risk below 10C)
        temp_factor = max(0.0, min(1.0, (air_temperature - 10.0) / 20.0))
        
        # Soil dryness factor (volatilization is highest on damp-to-dry soil surfaces drying out)
        dryness_factor = max(0.0, min(1.0, (80.0 - soil_moisture_pct) / 60.0))
        
        volatilization_risk = ph_factor * temp_factor * dryness_factor
        volatilization_risk = round(volatilization_risk, 2)
        
        for card in action_cards:
            if card.action_type == ActionType.FERTILIZE:
                # Check if card is applying urea or general nitrogen
                is_urea = True # assume urea by default for nitrogen fertilizing
                if is_urea and volatilization_risk > 0.60:
                    card.explain += " [Volatilization risk {:.2f}: NBPT coating required (soil pH={:.1f}, temp={:.1f}C)]".format(
                        volatilization_risk, soil_ph, air_temperature
                    )
                    logger.info("VolatilizationInhibitor: Prescribed NBPT inhibitor coating for N fertilizer due to risk %.2f",
                                volatilization_risk)
                                
        return action_cards

volatilization_inhibitor_engine = VolatilizationInhibitorEngine()
