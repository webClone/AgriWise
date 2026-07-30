"""
Layer 6.2: Harvest Optimization Engine.
Determines optimal window based on Readiness, Weather, and Risk.
"""

import pandas as pd
from typing import Dict, Any, List
from datetime import timedelta

class HarvestOptimizer:
    
    def optimize_window(self, 
                        current_date: pd.Timestamp,
                        phenology_stage: str,
                        forecast_weather: List[Dict],
                        disease_risk_prob: float) -> Dict[str, Any]:
        """
        Score next 7 days for harvest suitability.
        Score = w1*Readiness + w2*Weather + w3*DiseasePenalty
        """
        if "maturity" not in phenology_stage.lower() and "fruiter" not in phenology_stage.lower():
             return {
                "action": "wait",
                "reason": f"Crop not mature ({phenology_stage})",
                "window": None
            }
            
        # Evaluate next 5 days
        scores = []
        best_day = None
        max_score = -1
        
        for i, day_weather in enumerate(forecast_weather[:7]):
            day_date = current_date + timedelta(days=i)
            
            # 1. Weather Suitability (Dry & Moderate Temp)
            rain = day_weather.get("precip_mm", 0)
            temp = day_weather.get("temp_max", 25)
            
            weather_score = 100
            if rain > 2: weather_score -= 50 # Rain penalty
            if rain > 10: weather_score = 0 # Cannot harvest
            if temp > 35: weather_score -= 20 # Heat stress risk for workers/produce
            
            # 2. Disease Risk Penalty (If waiting exposes to disease)
            # If disease risk is high, 'earlier is better' -> Penalty increases over time?
            # Or simplified: if current day has low risk, good.
            risk_penalty = disease_risk_prob * 0.5
            
            # 3. Final Score
            # Assuming readiness is constant 100% in this window
            final_score = weather_score - risk_penalty
            
            scores.append({
                "date": day_date.strftime("%Y-%m-%d"),
                "score": final_score,
                "weather": "Rain" if rain > 2 else "Clear"
            })
            
            if final_score > max_score and final_score > 50:
                max_score = final_score
                best_day = day_date
                
        if best_day:
            return {
                "action": "harvest",
                "window_start": best_day.strftime("%Y-%m-%d"),
                "window_end": (best_day + timedelta(days=2)).strftime("%Y-%m-%d"),
                "quality_prediction": "High" if max_score > 80 else "Medium",
                "risk_notes": ["Rain forecast matches harvest" if max_score < 60 else "Good conditions"],
                "daily_scores": scores
            }
        else:
            return {
                "action": "hold",
                "reason": "No suitable weather window in next 7 days",
                "window": None
            }

# Singleton
harvest_engine = HarvestOptimizer()
