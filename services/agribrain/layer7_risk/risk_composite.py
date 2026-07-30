"""
Layer 7.1: Risk Composite Index Engine.
Aggregates Water, Nutrient, Disease, and Climate risks into a single score.
"""

from typing import Dict, Any, List

class RiskCompositeEngine:
    
    def calculate_composite_risk(self, 
                                 water_stress_prob: float, 
                                 nutrient_stress_prob: float, 
                                 disease_risk_prob: float,
                                 climate_shock_prob: float,
                                 stage_label: str) -> Dict[str, Any]:
        """
        Weighted aggregation of domain-specific risks.
        Weights adapt to crop stage (e.g., Disease > Nutrient in late stage).
        """
        # Default Weights
        weights = {
            "water": 0.3,
            "nutrient": 0.2,
            "disease": 0.3,
            "climate": 0.2
        }
        
        # Adaptive Weighting
        if "flowering" in stage_label or "fruiting" in stage_label:
            # Disease is critical in reproductive stages
            weights["disease"] = 0.4
            weights["nutrient"] = 0.1
        elif "vegetative" in stage_label:
            # Nutrient/Water drive biomass
            weights["nutrient"] = 0.3
            weights["disease"] = 0.1
            weights["water"] = 0.4
            
        # Calculate Weighted Score
        score = (
            water_stress_prob * weights["water"] +
            nutrient_stress_prob * weights["nutrient"] +
            disease_risk_prob * weights["disease"] +
            climate_shock_prob * weights["climate"]
        )
        
        # Normalize/Clamp
        score = min(max(score, 0), 100)
        
        level = "Low"
        if score > 40: level = "Moderate"
        if score > 70: level = "High"
        
        # Identify Top Drivers
        components = {
            "water": water_stress_prob,
            "nutrient": nutrient_stress_prob,
            "disease": disease_risk_prob,
            "climate": climate_shock_prob
        }
        top_drivers = sorted(components.items(), key=lambda x: x[1], reverse=True)[:2]
        formatted_drivers = [f"{k.capitalize()} ({v:.0f}%)" for k, v in top_drivers if v > 20]

        return {
            "risk_score": round(score, 1),
            "risk_level": level,
            "components": components,
            "top_drivers": formatted_drivers
        }

# Singleton
risk_engine = RiskCompositeEngine()
