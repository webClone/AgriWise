"""
Layer 3.3: Water Stress Detection Engine
Distinguishes water stress using Soil Model (Ks) + Satellite (NDMI).
"""

import warnings
import numpy as np
import pandas as pd
from typing import Dict, Any

class WaterStressDetector:
    
    def detect_water_stress(self, 
                            soil_df: pd.DataFrame, 
                            ndmi_series: pd.Series) -> Dict[str, Any]:
        """
        Analyze recent soil state and spectral moisture for stress alerts.
        """
        warnings.warn(
            "WaterStressDetector is deprecated as of Layer 3.0. "
            "Use layer3_water.limitation.WaterLimitationEngine for canonical physical limitation.",
            DeprecationWarning,
            stacklevel=2,
        )
        # 1. Soil Model Indicator (Ks)
        # last 3 days average Ks
        recent_ks = soil_df["stress_ks"].iloc[-3:].mean()
        
        # 2. Satellite Indicator (NDMI)
        # Check trend or absolute low
        recent_ndmi = ndmi_series.iloc[-3:].mean() if not ndmi_series.empty else 0.0
        
        prob = 0.0
        drivers = []
        
        # Model says Dry?
        if recent_ks < 0.8:
            prob += 40
            drivers.append(f"High Root Depletion (Ks={recent_ks:.2f})")
            if recent_ks < 0.5:
                prob += 20 # Severe
                
        # Satellite confirms?
        if recent_ndmi < 0.0: # Very dry veg
             prob += 30
             drivers.append(f"Vegetation Water Content Low (NDMI={recent_ndmi:.2f})")
        
        # Consistency Check
        # If Model says WET but NDMI says DRY -> Sensor/Model mismatch (Confidence penalization)
        # If Model says DRY but NDMI says WET -> Lag effect? Or Irrigation not logged?
        
        return {
            "water_stress_prob": min(prob, 99.0),
            "drivers": drivers,
            "ks_avg": float(recent_ks),
            "ndmi_avg": float(recent_ndmi)
        }

# Singleton
water_stress_engine = WaterStressDetector()
