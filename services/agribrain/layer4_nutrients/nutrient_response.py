"""
Layer 4.2: Nutrient Response Model.
Simulates yield gain from Nitrogen application (What-If Analysis).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List

class NutrientResponseModel:
    
    def __init__(self):
        # Default Mitscherlich parameters (Mock per crop)
        # Y = A * (1 - exp(-c * (N_soil + N_fert)))
        self.params = {
            "wheat": {"A": 8.0, "c": 0.02, "N_soil_default": 40}, # A in T/ha
            "tomato": {"A": 100.0, "c": 0.015, "N_soil_default": 60}
        }
        
    def simulate_response(self, 
                          crop_type: str, 
                          current_n_prob: float, 
                          water_stress_prob: float) -> Dict[str, Any]:
        """
        Generate Yield Response Curve for N doses [0, 25, 50, 75, 100] kg/ha.
        """
        p = self.params.get(crop_type.lower(), self.params["wheat"])
        A_max = p["A"]
        c_rate = p["c"]
        n_soil = p["N_soil_default"]
        
        # Adjust N_soil based on deficiency prob (inverse proxy)
        # If prob high -> soil N is low
        if current_n_prob > 50:
            n_soil *= 0.6  # Depleted
            
        # Adjust Potential (A_max) based on Water Stress
        # Drought limits max yield regardless of N
        water_limit_factor = max(0.2, 1.0 - (water_stress_prob / 100.0))
        A_actual = A_max * water_limit_factor
        
        # Calculate curve
        doses = [0, 25, 50, 75, 100]
        curve = []
        
        base_yield = A_actual * (1 - np.exp(-c_rate * n_soil))
        
        for dose in doses:
            total_n = n_soil + dose
            pred_yield = A_actual * (1 - np.exp(-c_rate * total_n))
            gain = max(0, pred_yield - base_yield)
            
            curve.append({
                "dose_kg_ha": dose,
                "yield_t_ha": round(pred_yield, 2),
                "gain_t_ha": round(gain, 2),
                "pct_increase": round((gain / base_yield) * 100, 1) if base_yield > 0 else 0
            })
            
        return {
            "baseline_yield_t_ha": float(base_yield),
            "water_limited_potential": float(A_actual),
            "response_curve": curve
        }

# Singleton
response_engine = NutrientResponseModel()
