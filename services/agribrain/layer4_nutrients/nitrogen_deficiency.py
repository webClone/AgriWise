"""
Layer 4.1: Nitrogen Deficiency Detection Engine.
Detects N limitation using spectral features gated by water stress.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List

class NitrogenDeficiencyEngine:
    
    def __init__(self):
        # Baselines (Mocked)
        self.regional_baseline_ndvi = 0.75 
        
    def detect_deficiency(self, 
                          ndvi_series: pd.Series, 
                          stage_label: str,
                          water_stress_prob: float) -> Dict[str, Any]:
        """
        Diagnose N deficiency.
        """
        # 1. Spectral Symptoms (Chlorosis/Stunted growth)
        # Check Peak and Slope
        current_ndvi = ndvi_series.iloc[-1]
        mean_ndvi = ndvi_series.mean()
        
        # Deviation from baseline (if in vegetative/peak support)
        # Assuming we are in a stage where high NDVI is expected
        expected = self.regional_baseline_ndvi
        if "vegetative" in stage_label or "flowering" in stage_label:
             expected = 0.7
        elif "emergence" in stage_label:
             expected = 0.3
             
        spectral_deficit = max(0, expected - current_ndvi)
        
        # 2. Probability Calculation
        # Base prob from spectral deficit
        prob = min(spectral_deficit * 200, 90) # 0.1 gap -> 20% prob
        
        # 3. Causal Gating (Water vs N)
        # If Water Stress is high, yellowing/stunting is likely Drought, not Nitrogen.
        # Down-weight N-deficiency probability.
        
        gating_factor = 1.0
        if water_stress_prob > 50:
            gating_factor = 0.4 # Significant reduction
            
        final_prob = prob * gating_factor
        
        # Severity
        severity = "none"
        if final_prob > 30: severity = "mild"
        if final_prob > 60: severity = "moderate"
        if final_prob > 80: severity = "severe"
            
        drivers = []
        if spectral_deficit > 0.1:
            drivers.append(f"Low NDVI ({current_ndvi:.2f} vs {expected})")
            
        if water_stress_prob > 50:
             drivers.append(f"Water Stress detected ({water_stress_prob:.0f}%) - interfering signal")
             
        return {
            "n_deficiency_prob": float(final_prob),
            "severity": severity,
            "drivers": drivers,
            "water_gating_applied": water_stress_prob > 50
        }

# Singleton
n_def_engine = NitrogenDeficiencyEngine()
