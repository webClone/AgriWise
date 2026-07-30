"""
Layer 5.3: Outbreak Probability Engine.
Aggregates risks across multiple plots/zones to detect regional outbreaks.
"""

from typing import Dict, Any, List

class OutbreakPredictionEngine:
    
    def predict_outbreak(self, 
                         regional_plot_risks: List[Dict[str, Any]], 
                         disease_name: str,
                         asmae_biotic_risk: float = 0.0) -> Dict[str, Any]:
        """
        Estimate regional outbreak probability.
        Input: List of risk results from neighbor plots.
        """
        if not regional_plot_risks:
            return {
                "outbreak_prob": 0.0,
                "regional_status": "low",
                "plots_affected": "0/0",
                "disease": disease_name,
                "scout_priority": "standard",
                "asmae_sensitized": False,
            }
            
        # Count high-risk plots
        total_plots = len(regional_plot_risks)
        high_risk_count = 0
        
        for risk in regional_plot_risks:
             # Extract disease prob
             d_probs = risk.get("risks", {}).get(disease_name, {})
             if d_probs.get("prob", 0) > 60:
                  high_risk_count += 1
        
        prevalence = high_risk_count / total_plots
        
        # ASMAE biotic risk acts as a sensitizer / scout amplifier
        # If there are no high-risk plots, ASMAE alone cannot trigger outbreak
        sensitizer_multiplier = 1.0
        if asmae_biotic_risk > 0.4:
            sensitizer_multiplier = 1.0 + (asmae_biotic_risk - 0.4) * 0.67
            
        outbreak_prob = prevalence * 1.5 * 100
        if prevalence > 0.0:
            outbreak_prob *= sensitizer_multiplier
        outbreak_prob = min(outbreak_prob, 99.0)
        
        status = "low"
        if outbreak_prob > 30: status = "moderate"
        if outbreak_prob > 60: status = "high_alert"
        
        # Scout priority amplification
        scout_priority = "standard"
        if asmae_biotic_risk > 0.5 or outbreak_prob > 40:
            scout_priority = "high"
        if asmae_biotic_risk > 0.7 or outbreak_prob > 70:
            scout_priority = "urgent"
        
        return {
            "outbreak_prob": float(outbreak_prob),
            "regional_status": status,
            "plots_affected": f"{high_risk_count}/{total_plots}",
            "disease": disease_name,
            "scout_priority": scout_priority,
            "asmae_sensitized": asmae_biotic_risk > 0.4,
        }

# Singleton
outbreak_engine = OutbreakPredictionEngine()


def predict_outbreak(
    regional_plot_risks: List[Dict[str, Any]],
    disease_name: str,
    asmae_biotic_risk: float = 0.0,
) -> Dict[str, Any]:
    return outbreak_engine.predict_outbreak(
        regional_plot_risks, disease_name, asmae_biotic_risk
    )

