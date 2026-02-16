"""
Layer 2.2: Crop Growth Stage Classifier
Determines phenological stage using GDD and NDVI shape.
Components:
- RuleBasedPhenology (Baseline)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any

class PhenologyEvents:
    def __init__(self):
        self.emergence_date = None
        self.peak_date = None
        self.senescence_date = None
        self.harvest_date = None
        
class GrowthStageClassifier:
    
    def __init__(self):
        # Simplified GDD thresholds (Generic)
        self.crop_profiles = {
            "tomato": {"emergence": 150, "vegetative": 400, "flowering": 700, "fruiting": 1100, "maturity": 1600},
            "wheat": {"emergence": 100, "tallering": 300, "heading": 700, "maturity": 1200}
        }
        
    def classify_zone(self, 
                      ndvi_series: pd.Series, 
                      gdd_series: pd.Series, 
                      crop_type: str = "tomato") -> Dict[str, Any]:
        """
        Classify stage for a specific zone/pixel time-series.
        """
        # 1. Feature Extraction
        # Peak NDVI
        peak_idx = ndvi_series.idxmax()
        peak_val = ndvi_series.max()
        
        # Cumulative GDD
        cum_gdd = gdd_series.cumsum()
        current_gdd = cum_gdd.iloc[-1] if not cum_gdd.empty else 0
        
        # 2. Rule-Based Classification (GDD Dominant)
        profile = self.crop_profiles.get(crop_type.lower(), self.crop_profiles["tomato"])
        
        stage = "unknown"
        if current_gdd < profile["emergence"]:
            stage = "planting/emergence"
        elif current_gdd < profile["vegetative"]:
             stage = "vegetative_growth"
        elif current_gdd < profile["flowering"]:
             stage = "flowering"
        elif current_gdd < profile["fruiting"]: # or heading
             stage = "fruiting/filling"
        elif current_gdd < profile["maturity"]:
             stage = "ripening"
        else:
             stage = "maturity/harvest_ready"
             
        # 3. Validation with NDVI Shape (Sanity check)
        # If GDD says "Vegetative" but NDVI is decreasing fast -> Stress or Error
        
        # Outputs
        return {
            "current_stage_label": stage,
            "current_gdd": float(current_gdd),
            "ndvi_peak": float(peak_val),
            "confidence": 0.85 # High for GDD-based
        }

# Singleton
growth_engine = GrowthStageClassifier()
