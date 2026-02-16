"""
Layer 8.1: Action Ranking Engine.
Ranks potential interventions based on Multi-Objective Scoring (ROI, Risk, Cost, Trust).
"""

from typing import Dict, Any, List

class ActionRankingEngine:
    
    def rank_actions(self, 
                     scenarios: List[Dict[str, Any]], 
                     trust_score: float) -> List[Dict[str, Any]]:
        """
        Rank actions by: Score = w_profit * Profit + w_risk * RiskRed - Cost - Uncertainty
        """
        ranked_list = []
        
        # Weights (Configurable per user profile)
        w_profit = 1.0 # Priority on cash
        w_risk = 0.5   # Value of stability
        w_cost = 0.1   # Penalty score for expensive actions (beyond ROI calc)
        w_uncertainty = 20.0 # Heavy penalty for low trust
        
        uncertainty_penalty = (100.0 - trust_score) / 100.0 * w_uncertainty
        
        for scen in scenarios:
            # Extract metrics
            profit = scen.get("profit_delta_usd", 0)
            roi = scen.get("roi_pct", 0)
            cost = scen.get("cost", 0) # Implicit in profit, but maybe penalty helps small farmers?
            risk_red = 0 # Placeholder for risk reduction value (e.g. avoided loss)
            
            # Score Calculation
            # We use Log(Profit) or raw Profit? Raw for now.
            # Normalize profit to 0-100 scale implicitly? 
            # Or just raw score.
            
            score = (profit * w_profit) + (risk_red * w_risk) - (cost * w_cost) - uncertainty_penalty
            
            # Confidence
            confidence = "High" if trust_score > 80 else "Moderate"
            if trust_score < 50: confidence = "Low"
            
            ranked_list.append({
                "action": scen.get("scenario", "unknown"),
                "rank_score": round(score, 1),
                "expected_profit": profit,
                "roi": roi,
                "confidence": confidence,
                "reason": f"Profit ${profit:.0f} (ROI {roi:.0f}%)"
            })
            
        # Sort desc
        ranked_list.sort(key=lambda x: x["rank_score"], reverse=True)
        return ranked_list

# Singleton
action_ranker = ActionRankingEngine()
