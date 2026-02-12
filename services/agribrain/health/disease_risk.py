"""
Disease Risk AI
Predicts disease probability based on weather conditions and phenology.
Uses epidemiological models as fallback, builds dataset for DL training.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json

# Import base class
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.orchestrator import BaseSpecializedAI


class DiseaseRiskAI(BaseSpecializedAI):
    """
    Predicts disease risk for crops based on environmental conditions.
    
    Diseases modeled:
    - Late Blight (Phytophthora infestans) - Tomato, Potato
    - Powdery Mildew - Various crops
    - Downy Mildew - Cucurbits, Grapes
    - Botrytis (Gray Mold) - Various crops
    """
    
    # Disease thresholds (epidemiological models)
    DISEASE_MODELS = {
        "late_blight": {
            "name": "Late Blight",
            "crops": ["tomato", "potato"],
            "conditions": {
                "temp_range": (10, 25),  # Optimal temp for pathogen
                "humidity_min": 90,       # RH > 90%
                "leaf_wetness_hours": 10, # Wet leaves > 10 hours
            },
            "severity": "high"
        },
        "powdery_mildew": {
            "name": "Powdery Mildew",
            "crops": ["tomato", "wheat", "grape", "cucumber"],
            "conditions": {
                "temp_range": (15, 28),
                "humidity_range": (40, 80),  # Moderate humidity
                "leaf_wetness_max": 20,      # Low leaf wetness
            },
            "severity": "medium"
        },
        "botrytis": {
            "name": "Botrytis (Gray Mold)",
            "crops": ["tomato", "strawberry", "grape"],
            "conditions": {
                "temp_range": (15, 23),
                "humidity_min": 85,
                "leaf_wetness_hours": 8,
            },
            "severity": "high"
        },
        "downy_mildew": {
            "name": "Downy Mildew",
            "crops": ["grape", "cucumber", "melon"],
            "conditions": {
                "temp_range": (10, 25),
                "humidity_min": 85,
                "leaf_wetness_hours": 4,
            },
            "severity": "medium"
        }
    }
    
    def __init__(self):
        super().__init__("disease_risk")
    
    def _heuristic_predict(self, context: Dict) -> Dict[str, Any]:
        """
        Rule-based disease risk prediction using epidemiological models.
        """
        realtime = context.get("realTime", {})
        crop = context.get("crop", "tomato").lower()
        
        temp = realtime.get("temp", 20)
        humidity = realtime.get("humidity", 50)
        leaf_wetness = realtime.get("leafWetness", 0)
        dew_point = realtime.get("dewPoint", 10)
        
        # Calculate disease risks
        risks = []
        overall_risk = "low"
        
        for disease_id, disease in self.DISEASE_MODELS.items():
            # Check if crop is susceptible
            if crop not in disease["crops"]:
                continue
            
            risk_score = 0
            conditions_met = []
            
            # Check temperature
            temp_min, temp_max = disease["conditions"].get("temp_range", (0, 100))
            if temp_min <= temp <= temp_max:
                risk_score += 30
                conditions_met.append(f"Temperature {temp}°C in optimal range")
            
            # Check humidity
            if "humidity_min" in disease["conditions"]:
                if humidity >= disease["conditions"]["humidity_min"]:
                    risk_score += 40
                    conditions_met.append(f"High humidity {humidity}%")
            
            if "humidity_range" in disease["conditions"]:
                h_min, h_max = disease["conditions"]["humidity_range"]
                if h_min <= humidity <= h_max:
                    risk_score += 30
                    conditions_met.append(f"Humidity {humidity}% in risk range")
            
            # Check leaf wetness
            if "leaf_wetness_hours" in disease["conditions"]:
                if leaf_wetness > 0:
                    risk_score += 30
                    conditions_met.append(f"Leaf wetness detected {leaf_wetness}%")
            
            if "leaf_wetness_max" in disease["conditions"]:
                if leaf_wetness < disease["conditions"]["leaf_wetness_max"]:
                    risk_score += 20
                    conditions_met.append("Low leaf wetness (powdery mildew risk)")
            
            # Calculate risk level
            if risk_score >= 70:
                risk_level = "high"
                overall_risk = "high"
            elif risk_score >= 40:
                risk_level = "moderate"
                if overall_risk != "high":
                    overall_risk = "moderate"
            else:
                risk_level = "low"
            
            if risk_score > 0:
                risks.append({
                    "disease": disease["name"],
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "conditions_met": conditions_met,
                    "recommendation": self._get_recommendation(disease_id, risk_level)
                })
        
        result = {
            "crop": crop,
            "overall_risk": overall_risk,
            "diseases": risks,
            "weather_factors": {
                "temperature": temp,
                "humidity": humidity,
                "leaf_wetness": leaf_wetness,
                "dew_point": dew_point
            },
            "source": "HEURISTIC_EPIDEMIOLOGICAL",
            "model_version": "1.0",
            "timestamp": datetime.now().isoformat()
        }
        
        # Log for dataset building
        self.log_sample(
            inputs={"realtime": realtime, "crop": crop},
            output=result
        )
        
        return result
    
    def _get_recommendation(self, disease_id: str, risk_level: str) -> str:
        """Get disease-specific recommendation."""
        recommendations = {
            "late_blight": {
                "high": "Apply preventive fungicide (copper-based or mancozeb). Monitor daily.",
                "moderate": "Scout for symptoms. Prepare fungicide application.",
                "low": "Continue regular monitoring."
            },
            "powdery_mildew": {
                "high": "Apply sulfur-based fungicide. Improve air circulation.",
                "moderate": "Remove affected leaves. Consider preventive treatment.",
                "low": "Maintain good canopy management."
            },
            "botrytis": {
                "high": "Apply fungicide immediately. Remove infected tissue.",
                "moderate": "Improve ventilation. Reduce humidity if possible.",
                "low": "Monitor for gray fuzzy growth on leaves/fruit."
            },
            "downy_mildew": {
                "high": "Apply systemic fungicide. Avoid overhead irrigation.",
                "moderate": "Scout lower leaves. Prepare treatment.",
                "low": "Maintain plant spacing for air circulation."
            }
        }
        return recommendations.get(disease_id, {}).get(risk_level, "Monitor conditions.")


# Singleton instance
disease_risk_ai = DiseaseRiskAI()
