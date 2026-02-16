"""
Layer 6.1: Yield Forecasting Engine (Hybrid).
Predicts yield using Biomass Baseline and Stress Penalties (Water, Nutrient, Disease).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List

class YieldForecastEngine:
    
    def __init__(self):
        # Harvest Indices (HI) - biomass to yield conversion
        self.harvest_indices = {
            "wheat": 0.45,
            "tomato": 0.60, # Fresh weight ratio roughly
            "corn": 0.50
        }
        
    def predict_yield(self, 
                      crop_type: str,
                      final_biomass_kg_ha: float,
                      cumulative_stress: Dict[str, float],
                      confidence_scores: Dict[str, float] = None,
                      input_hash: str = "mock_hash") -> Dict[str, Any]:
        """
        Hybrid Prediction with Uncertainty Propagation & Versioning.
        Y_final = (Biomass * HI) * (1 - Loss_Water) * (1 - Loss_Nutri) * (1 - Loss_Dis)
        """
        if confidence_scores is None:
            confidence_scores = {"biomass": 0.8, "stress": 0.7}
            
        hi = self.harvest_indices.get(crop_type.lower(), 0.5)
        
        # 1. Potential/Baseline Yield
        y_potential = final_biomass_kg_ha * hi / 1000.0
        
        # 2. Stress Penalties (Multiplicative with Capping)
        l_water = cumulative_stress.get("water_loss_factor", 0.0)
        l_nutri = cumulative_stress.get("nutrient_loss_factor", 0.0)
        l_disease = cumulative_stress.get("disease_loss_factor", 0.0)
        
        # Double-Counting / Leakage Prevention
        # Correlated risks: Water Stress often causes "Nutrient-like" symptoms.
        # If both are high, we don't multiply full overlap.
        # Simple heuristic: Max(L_water, L_nutri) + 0.2 * Min(...) instead of independent?
        # For now, we will just cap the TOTAL loss to prevent absurd drops (e.g. 0.1 yield).
        
        # Calculate naive reduction first
        naive_factor = (1 - l_water) * (1 - l_nutri) * (1 - l_disease)
        total_loss = 1.0 - naive_factor
        
        # Cap Loss at 70% unless catastrophic failure confirm
        if total_loss > 0.7:
            total_loss = 0.7 
            
        reduction_factor = 1.0 - total_loss
        y_final = y_potential * reduction_factor
        
        # 3. Attribution
        attribution = {
            "water": 0.0, "nutrient": 0.0, "disease": 0.0, "unknown": 0.1
        }
        sum_raw_loss = l_water + l_nutri + l_disease
        if sum_raw_loss > 0:
            attribution["water"] = round(l_water / sum_raw_loss * (total_loss - 0.1), 2)
            attribution["nutrient"] = round(l_nutri / sum_raw_loss * (total_loss - 0.1), 2)
            attribution["disease"] = round(l_disease / sum_raw_loss * (total_loss - 0.1), 2)
            attribution["unknown"] = 0.1 # Residual uncertainty
            
        # 4. Uncertainty Propagation
        # Base uncertainty from Biomass (Sensor/Model error)
        biomass_conf = confidence_scores.get("biomass", 0.8)
        stress_conf = confidence_scores.get("stress", 0.7)
        
        # Lower confidence = Wider interval
        # Base CV (Coefficient of Variation)
        base_cv = 0.1 + (1 - biomass_conf) * 0.2 # 10-30%
        # Add stress uncertainty
        stress_cv = (1 - stress_conf) * 0.15 # additional 0-15%
        
        total_cv = base_cv + stress_cv
        std_dev = y_final * total_cv
        
        # Trust Tier
        avg_conf = (biomass_conf + stress_conf) / 2
        trust = "Low"
        if avg_conf > 0.6: trust = "Moderate"
        if avg_conf > 0.8: trust = "High"

        return {
            "yield_mean_t_ha": round(y_final, 2),
            "yield_p10": round(max(0, y_final - 1.645 * std_dev), 2),
            "yield_p90": round(y_final + 1.645 * std_dev, 2),
            "confidence_score": round(avg_conf, 2),
            "trust_tier": trust,
            "potential_yield_t_ha": round(y_potential, 2),
            "reduction_factor": round(reduction_factor, 2),
            "attribution": attribution,
            "meta": {
                "model_version": "L6_HYBRID_V1.1",
                "input_hash": input_hash,
                "coverage": "partial" # Mock
            }
        }

# Singleton
yield_engine = YieldForecastEngine()
