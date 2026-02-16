"""
Layer 5.2: Visual Detection Engine.
CNN-based diagnosis with Causal Gating from Stress/Nutrient layers.
"""

import numpy as np
from typing import Dict, Any, List

class VisualDetectionEngine:
    
    def __init__(self):
        # Mock class labels
        self.classes = ["healthy", "early_blight", "late_blight", "septoria", "nitrogen_def", "drought_stress"]
        
    def analyze_image(self, 
                      image_tensor: Any, 
                      context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Diagnose image.
        Context includes: water_stress_prob, n_def_prob from L3/L4.
        """
        # 1. Quality Gate (Mock)
        # Assume valid image for now
        quality_score = 0.95
        if quality_score < 0.5:
            return {"status": "rejected", "reason": "Blurry/Dark"}
            
        # 2. CNN Prediction (Mock)
        # Simulating a raw result that might be confused between N-def (Yellowing) and Blight (Yellowing/Spots)
        raw_probs = {
            "healthy": 0.1,
            "early_blight": 0.4, # Suspicion
            "nitrogen_def": 0.3, # Suspicion
            "drought_stress": 0.2
        }
        
        # 3. Causal Fusion / Gating
        # Use Context to refine
        # If Water Stress is High -> Boost Drought, Suppress Disease/N-Def
        # If N-Def is High -> Boost N-Def
        
        water_prob = context.get("water_stress_prob", 0)
        n_def_prob = context.get("n_deficiency_prob", 0)
        
        refined_probs = raw_probs.copy()
        
        if water_prob > 60:
            refined_probs["drought_stress"] += 0.4
            refined_probs["early_blight"] *= 0.5 # Fungal less likely in drought? (Actually depends, but for symptoms...)
            
        if n_def_prob > 60:
            refined_probs["nitrogen_def"] += 0.3
            
        # Normalize
        total = sum(refined_probs.values())
        for k in refined_probs:
            refined_probs[k] /= total
            
        # Top Class
        top_class = max(refined_probs, key=refined_probs.get)
        
        return {
            "status": "analyzed",
            "top_diagnosis": top_class,
            "confidence": refined_probs[top_class],
            "raw_probs": raw_probs,
            "refined_probs": refined_probs,
            "gating_applied": True
        }

# Singleton
visual_engine = VisualDetectionEngine()
