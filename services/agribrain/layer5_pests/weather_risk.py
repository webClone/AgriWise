"""
Layer 5.1: Weather-Based Risk Engine.
Estimates Disease and Pest risk based on meteorological conditions and phenology.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List

class WeatherRiskEngine:
    
    def __init__(self):
        # Disease Rules (Simplified Epidemiology)
        # Late Blight (Tomato/Potato): High Humidity + Moderate Temp
        self.disease_models = {
            "late_blight": {"temp_min": 10, "temp_max": 25, "rh_threshold": 90, "wet_hours": 10},
            "powdery_mildew": {"temp_min": 15, "temp_max": 28, "rh_threshold": 60, "wet_hours": 0} # Loves dry leaves, high humidity air
        }
        
    def assess_risk(self, 
                    weather_history: pd.DataFrame, 
                    gdd_cum: float,
                    crop_type: str) -> Dict[str, Any]:
        """
        Evaluate risk events over recent weather window (last 3-5 days).
        """
        # 1. Disease Risk (Rule-Based)
        # MVP: Check if yesterday met conditions
        last_day = weather_history.iloc[-1]
        t_mean = last_day.get("temp_mean", 20)
        rh_max = last_day.get("humidity_max", 80)
        precip = last_day.get("precip", 0)
        
        risk_profile = {}
        
        # Late Blight Check
        lb_score = 0
        rules = self.disease_models["late_blight"]
        if rules["temp_min"] <= t_mean <= rules["temp_max"]:
            lb_score += 1
        if rh_max >= rules["rh_threshold"] or precip > 2.0: # Wetness proxy
            lb_score += 2
            
        risk_profile["late_blight"] = {
            "prob": min(lb_score * 33, 95),
            "drivers": ["High Humidity" if rh_max > 90 else None, "favorable temp"]
        }
        
        # 2. Pest Risk (GDD Based)
        # e.g., Tomato Fruit Worm / Pinworm thresholds
        # MVP: Just a placeholder logic
        pest_score = 0
        if 400 < gdd_cum < 800: # Active larval stage
            pest_score = 60
            
        risk_profile["gdd_pest_risk"] = {
            "prob": pest_score,
            "stage_gdd": gdd_cum
        }
        
        # 3. Spray Window
        # Don't spray if windy or raining soon
        wind_speed = last_day.get("wind_speed", 0)
        forecast_rain = 0 # Mock
        
        can_spray = True
        reason = "Good conditions"
        if wind_speed > 15: 
            can_spray = False
            reason = "Too windy (>15km/h)"
        elif forecast_rain > 5:
            can_spray = False
            reason = "Rain forecast"
            
        return {
            "risks": risk_profile,
            "spray_window": {
                "recommended": can_spray,
                "reason": reason
            },
            "confidence": 0.9 # High if data present
        }

# Singleton
weather_risk_engine = WeatherRiskEngine()
