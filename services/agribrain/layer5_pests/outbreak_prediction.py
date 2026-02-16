"""
Layer 5.3: Outbreak Probability Engine.
Aggregates risks across multiple plots/zones to detect regional outbreaks.
"""

from typing import Dict, Any, List

class OutbreakPredictionEngine:
    
    def predict_outbreak(self, 
                         regional_plot_risks: List[Dict[str, Any]], 
                         disease_name: str) -> Dict[str, Any]:
        """
        Estimate regional outbreak probability.
        Input: List of risk results from neighbor plots.
        """
        if not regional_plot_risks:
            return {"prob": 0.0, "status": "no_data"}
            
        # Count high-risk plots
        total_plots = len(regional_plot_risks)
        high_risk_count = 0
        
        for risk in regional_plot_risks:
             # Extract disease prob
             d_probs = risk.get("risks", {}).get(disease_name, {})
             if d_probs.get("prob", 0) > 60:
                 high_risk_count += 1
        
        prevalence = high_risk_count / total_plots
        
        outbreak_prob = min(prevalence * 1.5 * 100, 99) # Amplify signal
        
        status = "low"
        if outbreak_prob > 30: status = "moderate"
        if outbreak_prob > 60: status = "high_alert"
        
        return {
            "outbreak_prob": float(outbreak_prob),
            "regional_status": status,
            "plots_affected": f"{high_risk_count}/{total_plots}",
            "disease": disease_name
        }

# Singleton
outbreak_engine = OutbreakPredictionEngine()
