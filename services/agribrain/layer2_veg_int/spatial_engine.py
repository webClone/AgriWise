
"""
Layer 2.4: Spatial Proxy Stability Engine
Analyzes the spatial variance (uncertainty) of a plot over time as a PROXY for true spatial heterogeneity.
Determines if it is STABLE, HETEROGENEOUS (persistently variable), or TRANSIENTLY_VARIABLE.
"""

import math
import statistics
from typing import List, Dict, Tuple
from layer2_veg_int.schema import SpatialMetrics

class SpatialProxyStabilityEngine:
    
    def __init__(self, 
                 heterogeneity_threshold: float = 0.15, 
                 transient_threshold: float = 0.05):
        """
        Args:
            heterogeneity_threshold: Mean spatial std dev above this => Soil/Terrain issues.
            transient_threshold: Std dev of spatial std dev above this => Spreading stress.
        """
        self.heterogeneity_threshold = heterogeneity_threshold
        self.transient_threshold = transient_threshold

    def analyze_stability(self, dates: List[str], spatial_std_series: List[float]) -> SpatialMetrics:
        """
        Computes stability metrics from the time-series of spatial standard deviation (ndvi_unc).
        """
        if not spatial_std_series or len(spatial_std_series) < 2:
             return SpatialMetrics(0.0, 0.0, "UNKNOWN", 0.0)
            
        # 1. Compute Statistics
        spatial_variability_proxy = statistics.mean(spatial_std_series)
        std_var = statistics.stdev(spatial_std_series)
        
        # 2. Classification & Confidence
        stability_class = "STABLE"
        conf = 1.0
        
        # Transient issues (Volatile Variance) takes precedence
        if std_var > self.transient_threshold:
            stability_class = "TRANSIENT_VAR"
            # Confidence based on distance from threshold
            dist = std_var - self.transient_threshold
            conf = 0.5 + min(0.5, dist * 20.0) # Reach 1.0 if dist >= 0.025
            
        elif spatial_variability_proxy > self.heterogeneity_threshold:
            stability_class = "HETEROGENEOUS"
            dist = spatial_variability_proxy - self.heterogeneity_threshold
            conf = 0.5 + min(0.5, dist * 10.0) # Reach 1.0 if dist >= 0.05
            
        else:
            stability_class = "STABLE"
            dist = self.heterogeneity_threshold - spatial_variability_proxy
            conf = 0.5 + min(0.5, dist * 10.0)
            
        return SpatialMetrics(
            mean_spatial_var=spatial_variability_proxy,
            std_spatial_var=std_var,
            stability_class=stability_class,
            confidence=float(conf)
        )
