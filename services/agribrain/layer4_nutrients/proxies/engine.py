

from typing import Dict, Any, List
from layer1_fusion.schema import FieldTensor
from layer2_veg_int.schema import VegIntOutput

class NutrientObservationProxyEngine:
    """
    Layer 4.3: Nutrient Observation & Proxy Engine (NOP)
    Objective: Convert remote signals into nutrient evidence, with confounder control.
    """
    
    def __init__(self):
        # Baseline NDVI stats per stage (Mean, StdDev) for typical healthy crop
        self.baselines = {
            "EMERGENCE": (0.35, 0.05),
            "VEGETATIVE": (0.75, 0.10), # V-stage rapid growth
            "REPRODUCTIVE": (0.85, 0.05), # Peak canopy
            "MATURITY": (0.60, 0.15), # Senescence
            "HARVESTED": (0.20, 0.10)
        }
    
    def extract_features(self, tensor: FieldTensor, veg_int: VegIntOutput) -> Dict[str, Any]:
        """
        Compute:
        - ndvi_stage_z (deviation from expected)
        - growth_adequacy (slope check)
        - heterogeneity_flag (spatial stability)
        """
        # 1. Get Current Status
        # Use last valid NDVI from curve fit (smoother than raw)
        current_ndvi = veg_int.curve.ndvi_fit[-1] 
        current_d1 = veg_int.curve.ndvi_fit_d1[-1]
        
        # Current Stage
        current_stage = veg_int.phenology.stage_by_day[-1]
        
        # 2. Compute NDVI Z-Score
        baseline_mean, baseline_std = self.baselines.get(current_stage, (0.5, 0.2))
        ndvi_z = (current_ndvi - baseline_mean) / baseline_std
        
        # 3. Growth Adequacy (Slope Check)
        # In Vegetative, we expect d1 > 0.01 (approx)
        expected_d1 = 0.0
        if current_stage == "VEGETATIVE":
            expected_d1 = 0.015
        elif current_stage == "EMERGENCE":
            expected_d1 = 0.005
            
        growth_adequacy = 1.0 # 100% adequate
        if expected_d1 > 0:
            growth_adequacy = max(0, min(1.5, current_d1 / expected_d1))
            
        # 4. Heterogeneity Flag
        # From L2 Spatial Stability
        is_heterogeneous = False
        if veg_int.stability:
             if veg_int.stability.stability_class in ["UNSTABLE", "HETEROGENEOUS"]:
                 is_heterogeneous = True
             if veg_int.stability.mean_spatial_var > 0.15: # High spatial variance
                 is_heterogeneous = True
                 
        return {
            "ndvi_stage_z": float(ndvi_z),
            "growth_adequacy": float(growth_adequacy), # < 0.5 means stalling
            "heterogeneity_flag": is_heterogeneous,
            "current_ndvi": float(current_ndvi),
            "current_stage": current_stage
        }
