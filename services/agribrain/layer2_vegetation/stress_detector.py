"""
Layer 2.4: Crop Stress Detection Model
Identifies anomalies in vegetation indices relative to expected phenology.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any
# from sklearn.ensemble import Isolation Forest (Dependency check issues often, will just mock logic)

class StressDetector:
    
    def __init__(self):
        self.z_threshold = 2.0
    
    def detect_stress(self, 
                      ndvi_series: pd.Series, 
                      ndmi_series: pd.Series = None,
                      precip_series: pd.Series = None) -> Dict[str, Any]:
        """
        Analyze a time-series for stress signatures.
        """
        if len(ndvi_series) < 10:
             return {"stress_prob": 0.0, "reason": "insufficient_data"}
             
        # 1. Statistical Anomaly (Z-Score of recent deviation)
        # Compare last 3 days avg vs rolling 30-day mean
        recent = ndvi_series.iloc[-3:].mean()
        baseline = ndvi_series.iloc[-30:-3].mean()
        std_dev = ndvi_series.iloc[-30:-3].std() + 0.001
        
        z_score = (recent - baseline) / std_dev
        
        stress_prob = 0.0
        reasons = []
        
        # High negative Z-score = Sudden Drop
        if z_score < -self.z_threshold:
            stress_prob = min(abs(z_score) * 20, 90) # Map Z to %
            reasons.append(f"Sudden NDVI drop (Z={z_score:.1f})")
            
        # 2. Water Stress Logic (NDMI + Rainfall)
        if ndmi_series is not None and precip_series is not None:
             recent_ndmi = ndmi_series.iloc[-3:].mean()
             recent_rain = precip_series.iloc[-10:].sum()
             
             if recent_ndmi < 0.1 and recent_rain < 5.0:
                 stress_prob = max(stress_prob, 75)
                 reasons.append("Low Plant Moisture (Low NDMI + Dry Weather)")
                 
        return {
            "stress_prob": float(stress_prob),
            "is_stressed": stress_prob > 50,
            "drivers": reasons,
            "z_score_ndvi": float(z_score)
        }

# Singleton
stress_engine = StressDetector()
