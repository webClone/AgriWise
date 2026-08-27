"""
Layer 7.1: Risk Composite Index Engine.
Aggregates Water, Nutrient, Disease, and Climate risks into a single score.
"""

from typing import Dict, Any, List, Mapping

class RiskCompositeEngine:
    
    def calculate_composite_risk(self, 
                                 water_stress_prob: float, 
                                 nutrient_stress_prob: float, 
                                 disease_risk_prob: float,
                                 climate_shock_prob: float,
                                 stage_label: str = "UNKNOWN",
                                 semantic_context: Any = None) -> Dict[str, Any]:
        """
        Weighted aggregation of domain-specific risks.
        Weights adapt to crop stage (e.g., Disease > Nutrient in late stage).
        """
        # Default Weights
        weights = {
            "water": 0.3,
            "nutrient": 0.2,
            "disease": 0.3,
            "climate": 0.2
        }
        
        stage_allowed = bool(
            semantic_context is not None
            and getattr(semantic_context, "stage_specific_allowed", False)
            and getattr(semantic_context, "phenology_posterior_hash", "")
        )
        stage_mix = (
            dict(getattr(semantic_context, "stage_posterior", {}) or {})
            if stage_allowed else {}
        )
        if stage_allowed and not stage_mix:
            stage_mix = {str(getattr(semantic_context, "phenology_stage", "UNKNOWN")): 1.0}

        # Marginalize adaptive weights over the canonical posterior.  The raw
        # stage_label argument is retained only for API compatibility and is
        # never treated as evidence.
        if stage_mix:
            aggregate = {key: 0.0 for key in weights}
            total = sum(max(0.0, float(value)) for value in stage_mix.values()) or 1.0
            for stage, probability in stage_mix.items():
                branch = dict(weights)
                stage_token = str(stage).lower()
                if "flowering" in stage_token or "fruiting" in stage_token or "reproductive" in stage_token:
                    branch["disease"] = 0.4
                    branch["nutrient"] = 0.1
                elif "vegetative" in stage_token:
                    branch["nutrient"] = 0.3
                    branch["disease"] = 0.1
                    branch["water"] = 0.4
                p = max(0.0, float(probability)) / total
                for key, value in branch.items():
                    aggregate[key] += p * value
            weights = aggregate
            
        # Calculate Weighted Score
        score = (
            water_stress_prob * weights["water"] +
            nutrient_stress_prob * weights["nutrient"] +
            disease_risk_prob * weights["disease"] +
            climate_shock_prob * weights["climate"]
        )
        
        # Normalize/Clamp
        score = min(max(score, 0), 100)
        
        level = "Low"
        if score > 40: level = "Moderate"
        if score > 70: level = "High"
        
        # Identify Top Drivers
        components = {
            "water": water_stress_prob,
            "nutrient": nutrient_stress_prob,
            "disease": disease_risk_prob,
            "climate": climate_shock_prob
        }
        top_drivers = sorted(components.items(), key=lambda x: x[1], reverse=True)[:2]
        formatted_drivers = [f"{k.capitalize()} ({v:.0f}%)" for k, v in top_drivers if v > 20]

        return {
            "risk_score": round(score, 1),
            "risk_level": level,
            "components": components,
            "top_drivers": formatted_drivers,
            "weights": weights,
            "phenology_evidence_class": (
                "canonical_stage_posterior" if stage_allowed else "generic_stage_weights"
            ),
            "phenology_posterior_hash": (
                str(getattr(semantic_context, "phenology_posterior_hash", ""))
                if stage_allowed else ""
            ),
        }

# Singleton
risk_engine = RiskCompositeEngine()
