"""
Layer 4.3: Fertilization Optimizer.
Recommends N Dose & Timing based on ROI and Risk.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List

from crop_database import get_crop

class FertilizerOptimizer:
    
    def __init__(self):
        # Prices are now sourced from the centralized crop_database (209+ crops).
        self.cost_n = 1.0 # $/kg N (Urea ~ $500/T -> $1/kg roughly)
        self.app_cost = 15.0 # $/ha flat application cost
        
    def optimization_plan(self, 
                          response_curve: List[Dict], 
                          crop_type: str, 
                          rain_forecast_mm: float) -> Dict[str, Any]:
        """
        Select best dose for ROI.
        Constraint: Heavy rain (>20mm) prevents application.
        """
        price = get_crop(crop_type).price_usd_per_ton
        
        best_plan = None
        best_roi = -1.0
        
        # Risk Check
        if rain_forecast_mm > 20.0:
            return {
                "action": "hold",
                "reason": f"Heavy rain forecast ({rain_forecast_mm}mm). Leaching risk.",
                "dose_kg_ha": 0,
                "roi": 0
            }
            
        for step in response_curve:
            dose = step["dose_kg_ha"]
            gain_t = step["gain_t_ha"]
            
            if dose == 0: continue
            
            # Revenue = Gain * Price
            revenue = gain_t * price
            
            # Cost = (Dose * Cost_N) + App_Cost
            cost = (dose * self.cost_n) + self.app_cost
            
            # ROI
            profit = revenue - cost
            roi = profit / cost if cost > 0 else 0
            
            if roi > best_roi:
                best_roi = roi
                best_plan = {
                    "action": "apply",
                    "dose_kg_ha": dose,
                    "expected_gain_t_ha": gain_t,
                    "profit_usd_ha": round(profit, 2),
                    "roi": round(roi, 2),
                    "reason": "ROI Maximized"
                }
                
        if best_plan and best_plan["roi"] < 0.2: # Minimum ROI threshold
             return {
                "action": "hold",
                "reason": "ROI too low (< 20%)",
                "dose_kg_ha": 0
            }
            
        return best_plan if best_plan else {"action": "hold", "dose_kg_ha": 0}

# Singleton
fertilizer_engine = FertilizerOptimizer()
