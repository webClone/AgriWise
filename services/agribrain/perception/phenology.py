"""
Phenology & Growth Stage AI
Estimates crop growth stage based on GDD accumulation.
Uses agronomic lookup tables as fallback, builds dataset for DL training.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.orchestrator import BaseSpecializedAI


class PhenologyAI(BaseSpecializedAI):
    """
    Estimates current crop growth stage and predicts future stages.
    Based on Growing Degree Days (GDD) accumulation.
    """
    
    # GDD thresholds for growth stages (base 10°C)
    CROP_PHENOLOGY = {
        "tomato": {
            "base_temp": 10,
            "stages": [
                {"name": "Germination", "gdd_start": 0, "gdd_end": 100, "description": "Seed to emergence"},
                {"name": "Seedling", "gdd_start": 100, "gdd_end": 300, "description": "Cotyledons and first true leaves"},
                {"name": "Vegetative", "gdd_start": 300, "gdd_end": 700, "description": "Leaf and stem development"},
                {"name": "Flowering", "gdd_start": 700, "gdd_end": 1100, "description": "First flowers appear"},
                {"name": "Fruit Set", "gdd_start": 1100, "gdd_end": 1400, "description": "Fruits forming"},
                {"name": "Fruit Development", "gdd_start": 1400, "gdd_end": 1800, "description": "Fruits growing"},
                {"name": "Ripening", "gdd_start": 1800, "gdd_end": 2200, "description": "Color change, harvest ready"},
                {"name": "Senescence", "gdd_start": 2200, "gdd_end": 9999, "description": "Plant decline"},
            ]
        },
        "wheat": {
            "base_temp": 0,
            "stages": [
                {"name": "Germination", "gdd_start": 0, "gdd_end": 100},
                {"name": "Emergence", "gdd_start": 100, "gdd_end": 200},
                {"name": "Tillering", "gdd_start": 200, "gdd_end": 500},
                {"name": "Stem Elongation", "gdd_start": 500, "gdd_end": 800},
                {"name": "Booting", "gdd_start": 800, "gdd_end": 1000},
                {"name": "Heading", "gdd_start": 1000, "gdd_end": 1200},
                {"name": "Flowering", "gdd_start": 1200, "gdd_end": 1400},
                {"name": "Grain Fill", "gdd_start": 1400, "gdd_end": 1800},
                {"name": "Maturity", "gdd_start": 1800, "gdd_end": 9999},
            ]
        },
        "potato": {
            "base_temp": 7,
            "stages": [
                {"name": "Sprout Development", "gdd_start": 0, "gdd_end": 150},
                {"name": "Vegetative", "gdd_start": 150, "gdd_end": 450},
                {"name": "Tuber Initiation", "gdd_start": 450, "gdd_end": 650},
                {"name": "Tuber Bulking", "gdd_start": 650, "gdd_end": 1200},
                {"name": "Maturation", "gdd_start": 1200, "gdd_end": 9999},
            ]
        },
        "corn": {
            "base_temp": 10,
            "stages": [
                {"name": "Emergence (VE)", "gdd_start": 0, "gdd_end": 120},
                {"name": "V6 (6 leaves)", "gdd_start": 120, "gdd_end": 475},
                {"name": "V12 (12 leaves)", "gdd_start": 475, "gdd_end": 870},
                {"name": "VT (Tassel)", "gdd_start": 870, "gdd_end": 1135},
                {"name": "R1 (Silking)", "gdd_start": 1135, "gdd_end": 1400},
                {"name": "R3 (Milk)", "gdd_start": 1400, "gdd_end": 1660},
                {"name": "R5 (Dent)", "gdd_start": 1660, "gdd_end": 2000},
                {"name": "R6 (Maturity)", "gdd_start": 2000, "gdd_end": 9999},
            ]
        }
    }
    
    def __init__(self):
        super().__init__("phenology")
    
    def _heuristic_predict(self, context: Dict) -> Dict[str, Any]:
        """
        Rule-based phenology prediction using GDD thresholds.
        """
        crop = context.get("crop", "tomato").lower()
        climate = context.get("climate", {})
        gdd = climate.get("growingDegreeDays", 1000)  # Default mid-season
        
        # Get crop phenology data
        crop_data = self.CROP_PHENOLOGY.get(crop, self.CROP_PHENOLOGY["tomato"])
        stages = crop_data["stages"]
        base_temp = crop_data["base_temp"]
        
        # Find current stage
        current_stage = None
        next_stage = None
        stage_progress = 0
        
        for i, stage in enumerate(stages):
            if stage["gdd_start"] <= gdd < stage["gdd_end"]:
                current_stage = stage
                stage_progress = (gdd - stage["gdd_start"]) / (stage["gdd_end"] - stage["gdd_start"])
                if i + 1 < len(stages):
                    next_stage = stages[i + 1]
                break
        
        if current_stage is None:
            current_stage = stages[-1]
            stage_progress = 1.0
        
        # Calculate days to next stage (rough estimate: ~15 GDD/day average)
        gdd_per_day = 15
        gdd_to_next = (current_stage["gdd_end"] - gdd) if next_stage else 0
        days_to_next = max(0, int(gdd_to_next / gdd_per_day))
        
        result = {
            "crop": crop,
            "current_gdd": gdd,
            "base_temp": base_temp,
            "current_stage": {
                "name": current_stage["name"],
                "description": current_stage.get("description", ""),
                "progress": round(stage_progress * 100, 1),
                "gdd_range": [current_stage["gdd_start"], current_stage["gdd_end"]]
            },
            "next_stage": {
                "name": next_stage["name"] if next_stage else "Complete",
                "gdd_threshold": next_stage["gdd_start"] if next_stage else None,
                "estimated_days": days_to_next
            } if next_stage else None,
            "all_stages": [{"name": s["name"], "gdd_start": s["gdd_start"]} for s in stages],
            "source": "HEURISTIC_GDD",
            "model_version": "1.0",
            "timestamp": datetime.now().isoformat()
        }
        
        # Log for dataset building
        self.log_sample(
            inputs={"crop": crop, "gdd": gdd, "climate": climate},
            output=result
        )
        
        return result
    
    def get_stage_recommendations(self, stage_name: str, crop: str) -> List[str]:
        """Get agronomic recommendations for current stage."""
        recommendations = {
            "tomato": {
                "Seedling": ["Apply starter fertilizer", "Protect from frost", "Begin hardening off"],
                "Vegetative": ["Side-dress nitrogen", "Stake/cage plants", "Monitor for early pests"],
                "Flowering": ["Ensure consistent watering", "Apply potassium", "Scout for blossom end rot"],
                "Fruit Set": ["Maintain calcium levels", "Reduce nitrogen", "Prune suckers"],
                "Ripening": ["Reduce irrigation", "Monitor for cracking", "Begin harvest planning"],
            },
            "wheat": {
                "Tillering": ["Apply nitrogen topdressing", "Scout for weeds"],
                "Stem Elongation": ["Apply fungicide if needed", "Monitor growth regulator timing"],
                "Heading": ["Final fungicide application", "Scout for diseases"],
                "Grain Fill": ["Avoid stress", "Monitor for lodging"],
            }
        }
        return recommendations.get(crop, {}).get(stage_name, ["Continue standard practices"])


# Singleton instance
phenology_ai = PhenologyAI()
