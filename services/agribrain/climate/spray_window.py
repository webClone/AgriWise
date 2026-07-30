"""
Spray Window AI
Determines optimal spray windows based on meteorological conditions.
Uses agronomic rules as fallback, builds dataset for DL training.
"""

from typing import Dict, Any, List
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.orchestrator import BaseSpecializedAI


class SprayWindowAI(BaseSpecializedAI):
    """
    Determines optimal spray windows for pesticide/fungicide application.
    Uses Delta-T, wind speed, humidity, and other factors.
    """
    
    # Optimal ranges for different spray types
    SPRAY_CONDITIONS = {
        "general": {
            "delta_t": {"optimal": (2, 8), "acceptable": (1, 10), "avoid": (0, 1, 10, 15)},
            "wind_speed": {"optimal": (3, 15), "acceptable": (0, 20), "max": 20},
            "humidity": {"optimal": (40, 80), "acceptable": (30, 90)},
            "rain_hours_before": 4,  # No rain in last 4 hours
            "rain_hours_after": 2,   # No rain expected for 2 hours
        },
        "systemic": {  # Systemic products need leaf uptake
            "delta_t": {"optimal": (2, 6), "acceptable": (1, 8)},
            "humidity": {"optimal": (50, 85), "acceptable": (40, 90)},
        },
        "contact": {  # Contact products need coverage
            "delta_t": {"optimal": (3, 8), "acceptable": (2, 10)},
            "humidity": {"optimal": (40, 70), "acceptable": (30, 80)},
        }
    }
    
    def __init__(self):
        super().__init__("spray_window")
    
    def _heuristic_predict(self, context: Dict) -> Dict[str, Any]:
        """
        Rule-based spray window assessment.
        """
        realtime = context.get("realTime", {})
        
        delta_t = realtime.get("deltaT", 5)
        wind = realtime.get("windSpeed", 10)
        humidity = realtime.get("humidity", 50)
        rain = realtime.get("rain", 0)
        temp = realtime.get("temp", 20)
        uv = realtime.get("uvIndex", 5)
        solar_rad = realtime.get("solarRad", 0)
        leaf_wetness = realtime.get("leafWetness", 0)
        
        conditions = self.SPRAY_CONDITIONS["general"]
        
        # Evaluate each factor
        factors = []
        overall_score = 100
        
        # Delta-T assessment
        dt_opt = conditions["delta_t"]["optimal"]
        dt_acc = conditions["delta_t"]["acceptable"]
        if dt_opt[0] <= delta_t <= dt_opt[1]:
            factors.append({
                "factor": "Delta-T",
                "value": delta_t,
                "status": "optimal",
                "message": f"Delta-T {delta_t} is ideal for spray application"
            })
        elif dt_acc[0] <= delta_t <= dt_acc[1]:
            factors.append({
                "factor": "Delta-T",
                "value": delta_t,
                "status": "acceptable",
                "message": f"Delta-T {delta_t} is acceptable but not ideal"
            })
            overall_score -= 15
        else:
            factors.append({
                "factor": "Delta-T",
                "value": delta_t,
                "status": "poor",
                "message": f"Delta-T {delta_t} - {'Too low (inversion risk)' if delta_t < dt_acc[0] else 'Too high (droplet evaporation)'}"
            })
            overall_score -= 40
        
        # Wind assessment
        if wind <= conditions["wind_speed"]["max"]:
            if conditions["wind_speed"]["optimal"][0] <= wind <= conditions["wind_speed"]["optimal"][1]:
                factors.append({
                    "factor": "Wind",
                    "value": wind,
                    "status": "optimal",
                    "message": f"Wind {wind} km/h is suitable"
                })
            else:
                factors.append({
                    "factor": "Wind",
                    "value": wind,
                    "status": "acceptable",
                    "message": f"Wind {wind} km/h - {'Low (check for inversions)' if wind < 3 else 'Moderate'}"
                })
                overall_score -= 10
        else:
            factors.append({
                "factor": "Wind",
                "value": wind,
                "status": "poor",
                "message": f"Wind {wind} km/h is too high - spray drift risk"
            })
            overall_score -= 50
        
        # Humidity assessment
        hum_opt = conditions["humidity"]["optimal"]
        hum_acc = conditions["humidity"]["acceptable"]
        if hum_opt[0] <= humidity <= hum_opt[1]:
            factors.append({
                "factor": "Humidity",
                "value": humidity,
                "status": "optimal",
                "message": f"Humidity {humidity}% is ideal"
            })
        elif hum_acc[0] <= humidity <= hum_acc[1]:
            factors.append({
                "factor": "Humidity",
                "value": humidity,
                "status": "acceptable",
                "message": f"Humidity {humidity}% is acceptable"
            })
            overall_score -= 10
        else:
            factors.append({
                "factor": "Humidity",
                "value": humidity,
                "status": "poor",
                "message": f"Humidity {humidity}% - {'Too dry' if humidity < hum_acc[0] else 'Too humid'}"
            })
            overall_score -= 25
        
        # Rain assessment
        if rain > 0:
            factors.append({
                "factor": "Rain",
                "value": rain,
                "status": "poor",
                "message": f"Rain detected ({rain}mm) - Do not spray"
            })
            overall_score -= 100  # No spray during rain
        else:
            factors.append({
                "factor": "Rain",
                "value": 0,
                "status": "optimal",
                "message": "No rain - conditions suitable"
            })
        
        # Leaf wetness
        if leaf_wetness > 0:
            factors.append({
                "factor": "Leaf Wetness",
                "value": leaf_wetness,
                "status": "caution",
                "message": f"Leaves wet ({leaf_wetness}%) - May affect adhesion"
            })
            overall_score -= 15
        else:
            factors.append({
                "factor": "Leaf Wetness",
                "value": 0,
                "status": "optimal",
                "message": "Leaves dry - good for application"
            })
        
        # Solar radiation (time of day indicator)
        if solar_rad == 0:
            factors.append({
                "factor": "Time of Day",
                "value": "Night/Dawn",
                "status": "caution",
                "message": "Low light - consider waiting for dawn/dusk"
            })
        elif solar_rad > 800:
            factors.append({
                "factor": "Solar Radiation",
                "value": solar_rad,
                "status": "caution",
                "message": "High UV - products may degrade faster"
            })
            overall_score -= 10
        
        # Calculate overall recommendation
        overall_score = max(0, min(100, overall_score))
        
        if overall_score >= 80:
            recommendation = "SPRAY_NOW"
            recommendation_text = "Excellent conditions - proceed with spray application"
        elif overall_score >= 60:
            recommendation = "ACCEPTABLE"
            recommendation_text = "Acceptable conditions - can spray with caution"
        elif overall_score >= 40:
            recommendation = "MARGINAL"
            recommendation_text = "Marginal conditions - consider waiting for improvement"
        else:
            recommendation = "DO_NOT_SPRAY"
            recommendation_text = "Poor conditions - do not spray"
        
        result = {
            "recommendation": recommendation,
            "recommendation_text": recommendation_text,
            "score": overall_score,
            "factors": factors,
            "conditions_summary": {
                "delta_t": delta_t,
                "wind_speed": wind,
                "humidity": humidity,
                "rain": rain,
                "leaf_wetness": leaf_wetness,
                "temperature": temp
            },
            "tips": self._get_tips(factors),
            "source": "HEURISTIC_AGRONOMIC",
            "model_version": "1.0",
            "timestamp": datetime.now().isoformat()
        }
        
        # Log for dataset building
        self.log_sample(
            inputs={"realtime": realtime},
            output=result
        )
        
        return result
    
    def _get_tips(self, factors: List[Dict]) -> List[str]:
        """Generate practical tips based on conditions."""
        tips = []
        
        for f in factors:
            if f["factor"] == "Delta-T" and f["status"] == "poor":
                if f["value"] < 2:
                    tips.append("Wait for temperature to rise or humidity to drop")
                else:
                    tips.append("Consider early morning or evening application")
            
            if f["factor"] == "Wind" and f["status"] == "poor":
                tips.append("Use drift-reducing nozzles if must spray")
                tips.append("Consider early morning when wind is usually calmer")
            
            if f["factor"] == "Leaf Wetness" and f["status"] == "caution":
                tips.append("Wait for dew to dry before applying")
        
        if not tips:
            tips.append("Conditions are favorable - apply as planned")
        
        return tips


# Singleton instance
spray_window_ai = SprayWindowAI()
