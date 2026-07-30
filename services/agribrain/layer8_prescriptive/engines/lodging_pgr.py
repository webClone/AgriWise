"""
Layer 8 Engine: Crop Lodging Risk & Plant Growth Regulator (PGR) Engine
========================================================================
Calculates lodging risk based on plant canopy height, growth rate, nitrogen supply,
and wind speed, and prescribes Plant Growth Regulator (PGR) dosage as mitigation.
"""
import logging
from layer8_prescriptive.schema import ActionCard, ActionType, RateRange, PriorityBreakdown, ConfidenceLevel

logger = logging.getLogger(__name__)

class LodgingPGREngine:
    """Calculates crop lodging risk and prescribes Plant Growth Regulators (PGR)."""

    def evaluate_lodging_risk(self, action_cards, crop, canopy_height_m, growth_velocity_daily, nitrogen_surplus_kg_ha, forecast):
        """
        Evaluates lodging risk and prescribes PGR spray if required.
        
        Args:
            action_cards: list of ActionCards
            crop: crop name string
            canopy_height_m: plant height (m)
            growth_velocity_daily: growth rate (NDVI units or biomass units/day)
            nitrogen_surplus_kg_ha: estimated nitrogen surplus
            forecast: weather forecast list
            
        Returns:
            list of ActionCards
        """
        # Lodging is mainly critical for tall crops like wheat, corn, rice
        if crop.lower() not in ("corn", "wheat", "rice"):
            return action_cards
            
        # Get maximum wind gust in forecast
        max_wind_gust = 0.0
        for day in forecast:
            gust = day.get("wind_gust")
            if gust is None:
                gust = day.get("wind_speed")
            if gust is None:
                gust = 0.0
            if gust > max_wind_gust:
                max_wind_gust = gust
                
        if max_wind_gust == 0.0:
            max_wind_gust = 10.0
            
        # Standard lodging risk index formulation
        # High height, fast vegetative growth, excess N, and high wind gusts combine to increase risk
        lodging_risk = canopy_height_m * (1.0 + 5.0 * growth_velocity_daily) * (1.0 + 0.005 * max_wind_surplus(nitrogen_surplus_kg_ha)) * (max_wind_gust / 30.0)
        lodging_risk = round(max(0.0, min(1.0, lodging_risk)), 2)
        
        if lodging_risk <= 0.70:
            logger.debug("LodgingPGR: Calculated lodging risk %.2f is safe.", lodging_risk)
            return action_cards
            
        # Prescribe Plant Growth Regulator (PGR) like chlormequat chloride
        pgr_rate_l_ha = 1.5 if crop.lower() == "wheat" else 2.5
        
        pgr_card = ActionCard(
            action_id="pgr-lodging-001",
            action_type=ActionType.SPRAY,
            priority_score=round(0.40 + 0.50 * lodging_risk, 4),
            priority_breakdown=PriorityBreakdown(
                impact_score=0.80,
                urgency_score=0.85,
                risk_score=0.85,
                cost_score=0.70,
                confidence_score=0.90
            ),
            zone_targets=["plot"],
            zone_allocation={"plot": 1.0},
            rate=RateRange(
                recommended=pgr_rate_l_ha,
                min_safe=round(pgr_rate_l_ha * 0.8, 1),
                max_safe=round(pgr_rate_l_ha * 1.2, 1),
                unit="L/ha"
            ),
            explain="Prescribed Plant Growth Regulator (PGR) spray due to High Lodging Risk ({:.2f} index, wind gust {:.1f} km/h)".format(
                lodging_risk, max_wind_gust
            ),
            confidence=ConfidenceLevel.HIGH,
            heuristic=True
        )
        action_cards.append(pgr_card)
        logger.info("LodgingPGR: Prescribed PGR spray at %.1f L/ha due to lodging risk %.2f", pgr_rate_l_ha, lodging_risk)
        
        return action_cards

def max_wind_surplus(n_surplus):
    return max(0.0, n_surplus)

lodging_pgr_engine = LodgingPGREngine()
