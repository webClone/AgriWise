"""
Layer 3.2: Soil Moisture Modeing Engine (Bucket Model)
Tracks root-zone water storage (S_t).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List

class SoilMoistureModel:
    
    def __init__(self):
        # Default Soil Properties (Volumetric Water Content)
        # Field Capacity (fc), Wilting Point (wp)
        self.soil_defaults = {
            "sand": {"fc": 0.15, "wp": 0.06}, # Low holding capacity
            "loam": {"fc": 0.27, "wp": 0.14},
            "clay": {"fc": 0.35, "wp": 0.20}  # High holding capacity
        }
        
    def get_taw(self, soil_type: str, root_depth_m: float = 1.0) -> float:
        """
        Total Available Water (TAW) in mm.
        TAW = 1000 * (theta_fc - theta_wp) * Zr
        """
        props = self.soil_defaults.get(soil_type.lower(), self.soil_defaults["loam"])
        theta_fc = props["fc"]
        theta_wp = props["wp"]
        
        return 1000.0 * (theta_fc - theta_wp) * root_depth_m

    def run_water_balance(self,
                          precip: pd.Series,
                          etc: pd.Series,
                          irrigation: pd.Series = None,
                          soil_type: str = "loam",
                          initial_depletion_pct: float = 0.5) -> pd.DataFrame:
        """
        Daily Water Balance Simulation.
        S_t+1 = S_t + P + I - ETc - D - R
        """
        # Setup
        taw = self.get_taw(soil_type) # mm
        
        # Initial State (Assume 50% capacity if unknown)
        storage = taw * initial_depletion_pct
        
        results = []
        
        # Iterate days
        for i, date in enumerate(precip.index):
            p_t = precip.iloc[i]
            etc_t = etc.iloc[i]
            i_t = irrigation.iloc[i] if irrigation is not None else 0.0
            
            # 1. Inflow
            inflow = p_t + i_t
            
            # 2. Outflow (ET)
            # Actual ET is reduced if soil is very dry (Ks factor)
            # Simplified here: Ks handled in Stress Engine, here we deplete bucket
            # But realistically, depletion slows down as it gets drier.
            
            # Calculate Soil Water Depletion (Dr)
            # Dr = TAW - Storage
            dr = taw - storage
            
            # Ks check (FAO 56)
            # p_threshold = 0.5 (average)
            # if dr > 0.5 * taw: Ks < 1 (Stress)
            # et_act = etc_t * Ks
            
            # Simplified ET reduction logic
            ks = 1.0
            if dr > 0.6 * taw: # Stress zone
                ks = max(0, (taw - dr) / ((1 - 0.6) * taw))
                
            et_act = etc_t * ks
            
            # 3. Update Storage
            # S_new = S_old + In - Out
            new_storage = storage + inflow - et_act
            
            # 4. Drainage / Runoff (Cap at TAW)
            drainage = 0.0
            if new_storage > taw:
                drainage = new_storage - taw
                new_storage = taw # Field Capacity
                
            # Prevent negative storage
            if new_storage < 0:
                new_storage = 0
            
            storage = new_storage
            depletion = taw - storage
            
            results.append({
                "date": date,
                "storage_mm": storage,
                "depletion_mm": depletion,
                "depletion_pct": depletion / taw,
                "et_actual": et_act,
                "drainage": drainage,
                "stress_ks": ks
            })
            
        return pd.DataFrame(results).set_index("date")

# Singleton
soil_engine = SoilMoistureModel()
