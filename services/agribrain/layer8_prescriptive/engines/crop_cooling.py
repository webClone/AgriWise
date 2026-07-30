"""
Layer 8 Engine: Crop Canopy Cooling Irrigation Engine
======================================================
Prescribes evaporative canopy cooling irrigation when air temperatures exceed
critical crop-specific thresholds during sensitive phenological stages.
"""
import logging
from layer8_prescriptive.schema import ActionCard, ActionType, RateRange, PriorityBreakdown, ConfidenceLevel, TimeWindow

logger = logging.getLogger(__name__)

# Crop reproductive temperature thresholds where heat stress causes damage (pollen sterility etc)
_CROP_HEAT_THRESHOLDS = {
    "corn": 35.0,
    "wheat": 32.0,
    "soybean": 35.0,
    "rice": 34.0,
    "cotton": 38.0,
    "potato": 30.0,
}

class CropCoolingEngine:
    """Prescribes micro-irrigation for crop canopy temperature cooling."""

    def evaluate_cooling_need(self, action_cards, crop, phenology_stage, forecast):
        """
        Evaluates weather forecast for heat wave periods during critical stage.
        If found, generates a canopy cooling irrigation action or inflates urgency.
        
        Args:
            action_cards: list of ActionCards
            crop: crop name string
            phenology_stage: current crop growth stage
            forecast: list of weather forecast daily dictionaries containing temp_max
            
        Returns:
            list of ActionCards (possibly with a new cooling irrigation action card added)
        """
        # Crop-cooling is only relevant during critical reproductive stages
        if "REPRODUCTIVE" not in phenology_stage.upper():
            return action_cards
            
        heat_thresh = _CROP_HEAT_THRESHOLDS.get(crop.lower(), 35.0)
        
        # Check forecast for hot days exceeding heat threshold
        hot_days = []
        for day in forecast:
            t_max = day.get("temp_max")
            if t_max is None:
                t_max = day.get("temperature")
            if t_max is None:
                t_max = 25.0
            if t_max > heat_thresh:
                hot_days.append(day)
                
        if not hot_days:
            return action_cards
            
        # Select maximum temperature predicted
        max_temps = []
        for day in hot_days:
            t_max = day.get("temp_max")
            if t_max is None:
                t_max = day.get("temperature")
            if t_max is None:
                t_max = 25.0
            max_temps.append(t_max)
        max_temp = max(max_temps)
        cooling_mm = round(0.5 * (max_temp - heat_thresh) * 1.2, 1)
        cooling_mm = max(1.0, min(10.0, cooling_mm)) # Clamp cooling irrigation to a safe range [1mm, 10mm]
        
        # Check if we already have an irrigation card
        has_irrigation = False
        for card in action_cards:
            if card.action_type == ActionType.IRRIGATE:
                has_irrigation = True
                card.priority_breakdown.urgency_score = min(1.0, card.priority_breakdown.urgency_score + 0.20)
                card.explain += " [Heatwave cooling required: max temp {:.1f}C exceeds threshold {:.1f}C]".format(
                    max_temp, heat_thresh
                )
                
        if not has_irrigation:
            # Generate a new cooling irrigation action card
            cooling_card = ActionCard(
                action_id="irr-cooling-001",
                action_type=ActionType.IRRIGATE,
                priority_score=0.85,
                priority_breakdown=PriorityBreakdown(
                    impact_score=0.80,
                    urgency_score=0.95,
                    risk_score=0.90,
                    cost_score=0.75,
                    confidence_score=0.90
                ),
                zone_targets=["plot"],
                zone_allocation={"plot": 1.0},
                rate=RateRange(
                    recommended=cooling_mm,
                    min_safe=max(1.0, round(cooling_mm * 0.5, 1)),
                    max_safe=max(cooling_mm, 5.0),
                    unit="mm"
                ),
                time_window=TimeWindow(
                    earliest=hot_days[0].get("date", ""),
                    latest=hot_days[-1].get("date", "")
                ),
                explain="Evaporative cooling irrigation prescribed ({} mm) for reproductive heat wave mitigation".format(cooling_mm),
                confidence=ConfidenceLevel.HIGH,
                heuristic=True
            )
            action_cards.append(cooling_card)
            logger.info("CropCooling: Prescribed crop cooling irrigation (%.1f mm) due to predicted heatwave (max temp %.2f C)",
                        cooling_mm, max_temp)
                        
        return action_cards

crop_cooling_engine = CropCoolingEngine()
