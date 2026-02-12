"""
Water Stress & Irrigation AI
Determines irrigation needs based on soil moisture, ET, and crop stage.
Uses FAO-56 methodology as fallback, builds dataset for DL training.
"""

from typing import Dict, Any
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.orchestrator import BaseSpecializedAI


class WaterStressAI(BaseSpecializedAI):
    """
    Assesses water stress and calculates irrigation requirements.
    Based on FAO-56 Penman-Monteith methodology.
    """
    
    # Crop coefficients (Kc) by growth stage
    CROP_KC = {
        "tomato": {
            "initial": 0.6,
            "mid": 1.15,
            "late": 0.80
        },
        "wheat": {
            "initial": 0.4,
            "mid": 1.15,
            "late": 0.25
        },
        "potato": {
            "initial": 0.5,
            "mid": 1.15,
            "late": 0.75
        },
        "corn": {
            "initial": 0.3,
            "mid": 1.20,
            "late": 0.60
        },
        "default": {
            "initial": 0.5,
            "mid": 1.0,
            "late": 0.7
        }
    }
    
    # Water stress thresholds
    STRESS_THRESHOLDS = {
        "no_stress": 0.7,      # Soil moisture > 70% AWC
        "mild_stress": 0.5,    # 50-70% AWC
        "moderate_stress": 0.3, # 30-50% AWC
        "severe_stress": 0.15   # < 30% AWC
    }
    
    def __init__(self):
        super().__init__("water_stress")
    
    def _heuristic_predict(self, context: Dict) -> Dict[str, Any]:
        """
        Rule-based irrigation assessment using FAO-56 approach.
        """
        realtime = context.get("realTime", {})
        soil = context.get("soil", {})
        water = context.get("water", {})
        climate = context.get("climate", {})
        crop = context.get("crop", "tomato").lower()
        
        # Get values
        et0 = realtime.get("et0", 3.5)  # Reference ET (mm/day)
        awc = soil.get("awc", 14) / 100  # Available Water Capacity (fraction)
        field_capacity = soil.get("wv0033", 28) / 100
        wilting_point = soil.get("wv1500", 14) / 100
        
        # Estimate current soil moisture (simplified - would use sensor in reality)
        # Using rain and ET balance assumption
        rain = realtime.get("rain", 0)
        estimated_depletion = max(0, et0 - rain) / (awc * 1000)  # Rough depletion fraction
        estimated_moisture = max(0.2, 1 - estimated_depletion)  # Fraction of AWC
        
        # Get crop coefficient based on GDD
        gdd = climate.get("growingDegreeDays", 1000)
        kc = self._get_kc(crop, gdd)
        
        # Calculate crop ET (ETc)
        etc = et0 * kc
        
        # Assess stress level
        stress_level, stress_message = self._assess_stress(estimated_moisture)
        
        # Calculate irrigation need
        if stress_level in ["moderate_stress", "severe_stress"]:
            # Irrigate to field capacity
            irrigation_needed = (field_capacity - (wilting_point + awc * estimated_moisture)) * 1000  # mm
            irrigation_needed = max(0, irrigation_needed)
        else:
            irrigation_needed = 0
        
        # Root zone depth assumption (mm)
        root_depth = self._get_root_depth(crop, gdd)
        
        result = {
            "crop": crop,
            "stress_assessment": {
                "level": stress_level,
                "message": stress_message,
                "estimated_soil_moisture": round(estimated_moisture * 100, 1),
                "awc_percentage": round(awc * 100, 1)
            },
            "water_balance": {
                "et0": et0,
                "crop_coefficient": round(kc, 2),
                "etc": round(etc, 2),
                "recent_rain": rain
            },
            "irrigation_recommendation": {
                "needed": irrigation_needed > 0,
                "amount_mm": round(irrigation_needed, 1),
                "urgency": "high" if stress_level == "severe_stress" else "moderate" if stress_level == "moderate_stress" else "low",
                "root_depth_mm": root_depth
            },
            "soil_properties": {
                "field_capacity": round(field_capacity * 100, 1),
                "wilting_point": round(wilting_point * 100, 1),
                "awc": round(awc * 100, 1)
            },
            "tips": self._get_irrigation_tips(stress_level, crop, kc),
            "source": "HEURISTIC_FAO56",
            "model_version": "1.0",
            "timestamp": datetime.now().isoformat()
        }
        
        # Log for dataset building
        self.log_sample(
            inputs={
                "realtime": realtime,
                "soil": soil,
                "climate": climate,
                "crop": crop
            },
            output=result
        )
        
        return result
    
    def _get_kc(self, crop: str, gdd: float) -> float:
        """Get crop coefficient based on growth stage."""
        kc_values = self.CROP_KC.get(crop, self.CROP_KC["default"])
        
        # Simplified stage determination
        if gdd < 300:
            return kc_values["initial"]
        elif gdd < 1200:
            return kc_values["mid"]
        else:
            return kc_values["late"]
    
    def _get_root_depth(self, crop: str, gdd: float) -> int:
        """Estimate root depth based on crop and stage."""
        max_depths = {
            "tomato": 1000,
            "wheat": 1500,
            "potato": 600,
            "corn": 1500
        }
        max_depth = max_depths.get(crop, 1000)
        
        # Linear growth to max depth
        growth_factor = min(1.0, gdd / 1000)
        return int(300 + (max_depth - 300) * growth_factor)
    
    def _assess_stress(self, moisture_fraction: float) -> tuple:
        """Assess water stress level."""
        if moisture_fraction >= self.STRESS_THRESHOLDS["no_stress"]:
            return "no_stress", "Adequate soil moisture - no irrigation needed"
        elif moisture_fraction >= self.STRESS_THRESHOLDS["mild_stress"]:
            return "mild_stress", "Minor depletion - monitor closely"
        elif moisture_fraction >= self.STRESS_THRESHOLDS["moderate_stress"]:
            return "moderate_stress", "Water stress developing - consider irrigation"
        else:
            return "severe_stress", "Critical water stress - irrigate immediately"
    
    def _get_irrigation_tips(self, stress_level: str, crop: str, kc: float) -> list:
        """Generate irrigation tips."""
        tips = []
        
        if stress_level == "severe_stress":
            tips.append("Apply irrigation immediately to prevent yield loss")
            tips.append("Consider split application to avoid runoff")
        elif stress_level == "moderate_stress":
            tips.append("Schedule irrigation within 24-48 hours")
            tips.append("Check weather forecast for rain before irrigating")
        elif stress_level == "mild_stress":
            tips.append("Monitor soil moisture daily")
            tips.append("Prepare irrigation system for potential use")
        else:
            tips.append("No irrigation needed at this time")
            tips.append(f"Current crop coefficient (Kc): {kc:.2f}")
        
        return tips


# Singleton instance
water_stress_ai = WaterStressAI()
