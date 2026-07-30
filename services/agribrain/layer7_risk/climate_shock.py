"""
Layer 7.2: Climate Shock Engine.
Detects extreme weather events (Heatwave, Frost, Heavy Rain).
"""

import pandas as pd
from typing import Dict, Any, List

class ClimateShockEngine:
    
    def detect_shocks(self, forecast_days: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze forecast for extreme events.
        """
        shock_prob = 0.0
        events = []
        
        for i, day in enumerate(forecast_days):
            t_max = day.get("temp_max", 25)
            t_min = day.get("temp_min", 15)
            rain = day.get("precip_mm", 0)
            wind = day.get("wind_speed", 0)
            
            # Heatwave
            if t_max > 35:
                shock_prob = max(shock_prob, 80)
                events.append(f"Heatwave (>35C) on Day {i+1}")
                
            # Frost
            if t_min < 2:
                shock_prob = max(shock_prob, 90) # Critical
                events.append(f"Frost Risk (<2C) on Day {i+1}")
                
            # Heavy Rain (Flood Risk)
            if rain > 50:
                shock_prob = max(shock_prob, 70)
                events.append(f"Heavy Rain (>50mm) on Day {i+1}")
                
            # Wind Gusts
            if wind > 40:
                shock_prob = max(shock_prob, 60)
                events.append(f"High Wind (>40km/h) on Day {i+1}")
                
        return {
            "shock_prob": float(shock_prob),
            "events": events,
            "is_severe": shock_prob > 60
        }

# Singleton
climate_engine = ClimateShockEngine()
