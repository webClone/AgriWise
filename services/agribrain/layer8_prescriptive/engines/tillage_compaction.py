"""
Layer 8 Engine: Soil Compaction Mitigation Tillage Engine
=========================================================
Prescribes optimal tillage depth and action based on bulk density and soil
texture to alleviate root restriction and improve water infiltration.
"""
import logging
from layer8_prescriptive.schema import ActionCard, ActionType, RateRange, PriorityBreakdown, ConfidenceLevel, TimeWindow

logger = logging.getLogger(__name__)

# Compaction bulk density thresholds (g/cm3) by USDA texture class
_COMPACTION_THRESHOLDS = {
    "clay": 1.45,
    "clay_loam": 1.50,
    "silt_loam": 1.55,
    "loam": 1.60,
    "sandy_loam": 1.65,
    "sand": 1.70,
}

class TillageCompactionEngine:
    """Evaluates soil compaction risk and prescribes mitigation tillage depth."""

    def evaluate_compaction(self, action_cards, soil_bulk_density, soil_texture, phenology_stage):
        """
        Calculates soil compaction and prescribes tillage depth if required
        pre-planting (BARE_SOIL/EMERGENCE).
        
        Args:
            action_cards: list of ActionCards
            soil_bulk_density: current bulk density (g/cm3)
            soil_texture: soil texture class name string
            phenology_stage: current crop stage
            
        Returns:
            list of ActionCards
        """
        # Compaction mitigation is typically only prescribed pre-planting or early season
        if phenology_stage.upper() not in ("BARE_SOIL", "EMERGENCE"):
            return action_cards
            
        thresh = _COMPACTION_THRESHOLDS.get(soil_texture.lower(), 1.55)
        
        if soil_bulk_density <= thresh:
            logger.debug("TillageCompaction: Bulk density %.2f g/cm3 below threshold %.2f for %s. No compaction tillage needed.",
                         soil_bulk_density, thresh, soil_texture)
            return action_cards
            
        # Calculate tillage depth scaling from compaction severity
        compaction_severity = (soil_bulk_density - thresh) / 0.3
        depth_cm = max(15.0, min(40.0, 15.0 + 25.0 * compaction_severity))
        depth_cm = round(depth_cm, 1)
        
        # Build tillage action card
        tillage_card = ActionCard(
            action_id="till-compaction-001",
            action_type=ActionType.SCOUT, # map to SCOUT since we do not have a dedicated TILL ActionType
            priority_score=0.80,
            priority_breakdown=PriorityBreakdown(
                impact_score=0.75,
                urgency_score=0.85,
                risk_score=0.70,
                cost_score=0.60,
                confidence_score=0.90
            ),
            zone_targets=["plot"],
            zone_allocation={"plot": 1.0},
            rate=RateRange(
                recommended=depth_cm,
                min_safe=15.0,
                max_safe=40.0,
                unit="cm"
            ),
            explain="Prescribed deep tillage to {} cm to mitigate soil compaction (Bulk Density={:.2f} g/cm3 exceeds limit={:.2f})".format(
                depth_cm, soil_bulk_density, thresh
            ),
            confidence=ConfidenceLevel.HIGH,
            heuristic=True
        )
        action_cards.append(tillage_card)
        logger.info("TillageCompaction: Prescribed tillage to %.1f cm due to compaction risk (BD=%.2f, limit=%.2f)",
                    depth_cm, soil_bulk_density, thresh)
                    
        return action_cards

tillage_compaction_engine = TillageCompactionEngine()
