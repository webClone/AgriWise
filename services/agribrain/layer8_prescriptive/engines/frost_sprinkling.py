"""
Layer 8 Engine: Frost-Protection Microclimatic Sprinkling Engine
================================================================
Prescribes overhead sprinkler irrigation for frost protection when predicted
temperatures drop below freezing, releasing latent heat of fusion to protect crop tissues.
"""
import logging
from layer8_prescriptive.schema import ActionCard, ActionType, RateRange, PriorityBreakdown, ConfidenceLevel, TimeWindow

import math
logger = logging.getLogger(__name__)

class FrostSprinklingEngine:
    """Prescribes microclimatic overhead sprinkling irrigation for frost protection."""

    def evaluate_frost_risk(self, action_cards, forecast):
        """
        Evaluates weather forecast for frost periods (temp_min <= 2.0C).
        If found, generates a frost-protection sprinkler irrigation action card.
        
        Args:
            action_cards: list of ActionCards
            forecast: weather forecast list
            
        Returns:
            list of ActionCards
        """
        def _get_t_min(day):
            if not isinstance(day, dict):
                return None
            val = day.get("temp_min") if day.get("temp_min") is not None else day.get("t_min_c")
            if val is not None:
                try:
                    v = float(val)
                    if math.isfinite(v):
                        return v
                except Exception:
                    pass
            return None

        def _get_wind_kmh(day):
            if not isinstance(day, dict):
                return 5.0
            val = day.get("wind_speed") if day.get("wind_speed") is not None else day.get("wind_kmh")
            if val is None:
                return 5.0
            try:
                v = float(val)
                if not math.isfinite(v):
                    return 5.0
                unit = str(day.get("wind_speed_unit") or day.get("wind_unit") or day.get("unit") or "").lower().strip()
                mult = 3.6 if unit in ("m/s", "mps") else (1.852 if unit in ("knots", "knot", "kt", "kts") else (1.60934 if unit in ("mph", "mi/h") else 1.0))
                return v * mult
            except Exception:
                return 5.0

        frost_days = []
        for day in forecast:
            t_min = _get_t_min(day)
            if t_min is not None and t_min <= 2.0:
                frost_days.append(day)
                
        if not frost_days:
            return action_cards
            
        # Select minimum temperature predicted
        min_temps = [_get_t_min(day) for day in frost_days if _get_t_min(day) is not None]
        if not min_temps:
            return action_cards
        min_temp = min(min_temps)
        # Wet bulb temperature is typically slightly lower than dry bulb temperature in dry conditions
        # Assume wet bulb is dry bulb - 1.0C for estimation
        wet_bulb = min_temp - 1.0
        
        # Wind speed from forecast
        wind_speed = max(_get_wind_kmh(day) for day in frost_days)
        
        # Frost protection water rate calculation (mm/hr of continuous application)
        # Higher wind speed increases evaporation cooling, requiring higher water rates to release heat
        sprinkling_rate_mm_hr = 0.5 * (0.0 - wet_bulb) * (1.0 + 0.05 * wind_speed)
        sprinkling_rate_mm_hr = round(max(1.5, min(8.0, sprinkling_rate_mm_hr)), 1)
        
        # Generate a new frost protection irrigation action card
        frost_card = ActionCard(
            action_id="irr-frost-001",
            action_type=ActionType.IRRIGATE,
            priority_score=0.95, # Very high priority because frost causes absolute loss
            priority_breakdown=PriorityBreakdown(
                impact_score=0.90,
                urgency_score=0.98,
                risk_score=0.95,
                cost_score=0.60,
                confidence_score=0.90
            ),
            zone_targets=["plot"],
            zone_allocation={"plot": 1.0},
            rate=RateRange(
                recommended=sprinkling_rate_mm_hr,
                min_safe=1.5,
                max_safe=8.0,
                unit="mm/hr"
            ),
            time_window=TimeWindow(
                earliest=frost_days[0].get("date", ""),
                latest=frost_days[-1].get("date", "")
            ),
            explain="Frost protection overhead sprinkling prescribed at {:.1f} mm/hr (Min Temp={:.1f}C, Wind={:.1f} km/h)".format(
                sprinkling_rate_mm_hr, min_temp, wind_speed
            ),
            confidence=ConfidenceLevel.HIGH,
            heuristic=True
        )
        action_cards.append(frost_card)
        logger.info("FrostSprinkling: Prescribed frost sprinkling at %.1f mm/hr due to predicted frost (min temp %.2f C)",
                    sprinkling_rate_mm_hr, min_temp)
                    
        return action_cards

frost_sprinkling_engine = FrostSprinklingEngine()
