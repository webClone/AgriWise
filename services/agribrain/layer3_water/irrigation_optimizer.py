"""
Layer 3.4: Irrigation Optimization Engine
Recommends irrigation events based on depletion thresholds.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from datetime import timedelta

class IrrigationOptimizer:
    
    def __init__(self):
        # Application Efficiencies
        self.efficiencies = {
            "drip": 0.95,
            "sprinkler": 0.80,
            "flood": 0.60
        }
        
    def recommend_irrigation(self, 
                           soil_df: pd.DataFrame, 
                           soil_type: str = "loam",
                           irrigation_type: str = "drip",
                           mgmt_threshold: float = 0.5) -> Dict[str, Any]:
        """
        Generate irrigation advice.
        Rule: Irrigate if Depletion > Threshold * TAW.
        Amount: Refill to Field Capacity / Efficiency.
        """
        last_state = soil_df.iloc[-1]
        depletion_pct = last_state["depletion_pct"]
        depletion_mm = last_state["depletion_mm"]
        
        eff = self.efficiencies.get(irrigation_type, 0.80)
        
        advice = {
            "action": "hold",
            "amount_mm": 0.0,
            "reason": "Soil moisture adequate",
            "urgency": "low"
        }
        
        # Logic
        if depletion_pct > mgmt_threshold:
            # Trigger Irrigation
            # Amount to refill
            gross_req = depletion_mm / eff
            
            urgency = "medium"
            if depletion_pct > 0.7:
                urgency = "critical"
                
            advice = {
                "action": "irrigate",
                "amount_mm": round(gross_req, 1),
                "reason": f"Depletion ({depletion_pct:.0%}) exceeds threshold ({mgmt_threshold:.0%})",
                "urgency": urgency,
                "efficiency_used": eff
            }
        
        return advice

# Singleton
irrigation_engine = IrrigationOptimizer()
