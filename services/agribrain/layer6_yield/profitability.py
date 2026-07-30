"""
Layer 6.3: Profitability Calculator.
Computes Profit, Margins, and ROI for interventions.
"""

from typing import Dict, Any, List

class ProfitabilityCalculator:
    
    def calculate_profit(self, 
                         yield_mean_t_ha: float, 
                         price_per_ton: float,
                         input_costs_per_ha: float) -> Dict[str, Any]:
        """
        Gross Margin Analysis.
        """
        revenue = yield_mean_t_ha * price_per_ton
        profit = revenue - input_costs_per_ha
        roi_pct = (profit / input_costs_per_ha) * 100 if input_costs_per_ha > 0 else 0
        
        return {
            "revenue_usd_ha": round(revenue, 2),
            "costs_usd_ha": round(input_costs_per_ha, 2),
            "profit_usd_ha": round(profit, 2),
            "roi_pct": round(roi_pct, 1),
            "break_even_yield": round(input_costs_per_ha / price_per_ton, 2)
        }

    def evaluate_intervention(self, 
                              cost_of_action: float, 
                              expected_yield_gain_t: float, 
                              price_per_ton: float) -> Dict[str, Any]:
        """
        ROI for specific action (e.g., Spraying, Fert).
        """
        gain_value = expected_yield_gain_t * price_per_ton
        net_benefit = gain_value - cost_of_action
        roi = (net_benefit / cost_of_action) * 100 if cost_of_action > 0 else 0
        
        return {
            "action_cost": cost_of_action,
            "expected_revenue_gain": round(gain_value, 2),
            "net_benefit": round(net_benefit, 2),
            "roi_pct": round(roi, 1),
            "is_viable": roi > 20 # Minimum hurdle
        }

# Singleton
profit_engine = ProfitabilityCalculator()
