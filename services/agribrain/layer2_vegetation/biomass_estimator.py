"""
Layer 2.3: Biomass Estimation Model
Estimates dry matter biomass based on integrated vegetation indices (AUC).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

class BiomassEstimator:
    
    def __init__(self):
        # Empirical coefficients (Mock for generic crop)
        # Biomass (kg/ha) ~ slope * Cumulative_NDVI 
        self.coefs = {
            "tomato": 45.0, # kg/ha per NDVI-day
            "wheat": 60.0,
            "generic": 50.0
        }
    
    def estimate_biomass(self, 
                         ndvi_series: pd.Series, 
                         gdd_series: pd.Series,
                         crop_type: str = "generic") -> Dict[str, Any]:
        """
        Estimate current biomass accumulation.
        """
        # 1. Calculate AUC (Area Under Curve) for NDVI (Time-integrated NDVI)
        # Approximation: Sum of daily NDVI values (assuming daily step)
        # Only count positive NDVI (active vegetation)
        active_ndvi = ndvi_series[ndvi_series > 0.1]
        ndvi_integral = active_ndvi.sum()
        
        # 2. Apply coefficient
        slope = self.coefs.get(crop_type.lower(), self.coefs["generic"])
        biomass_est = ndvi_integral * slope
        
        # 3. Uncertainty (Increases with time/magnitude)
        uncertainty = biomass_est * 0.15 # 15% error margin
        
        return {
            "biomass_kg_ha": float(biomass_est),
            "uncertainty_kg_ha": float(uncertainty),
            "ndvi_integral": float(ndvi_integral),
            "unit": "kg/ha (Dry Matter)"
        }

# Singleton
biomass_engine = BiomassEstimator()
