"""
Layer 4.2: Nutrient Response Model.
Simulates yield gain from Nitrogen application (What-If Analysis).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List

from crop_database import get_crop

class NutrientResponseModel:
    
    def __init__(self):
        # Mitscherlich parameters are now sourced from the centralized
        # crop_database (209+ crops). No local table needed.
        pass

    def _get_params(self, crop_type: str) -> Dict[str, float]:
        """Fetch Mitscherlich params from centralized crop_database."""
        spec = get_crop(crop_type)
        return {
            "A": spec.response_a_max,
            "c": spec.response_c_rate,
            "N_soil_default": spec.response_n_soil_default,
        }
        
    def simulate_response(self, 
                          crop_type: str, 
                          current_n_prob: float, 
                          water_stress_prob: float) -> Dict[str, Any]:
        """
        Generate Yield Response Curve for N doses [0, 25, 50, 75, 100] kg/ha.
        """
        p = self._get_params(crop_type)
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
