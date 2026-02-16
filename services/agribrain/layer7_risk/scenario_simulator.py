"""
Layer 7.3: Scenario Simulator.
Simulates outcomes of interventions ("What-If" Analysis).
"""

from typing import Dict, Any, List

class ScenarioSimulator:
    
    def simulate_intervention(self, 
                              baseline_state: Dict[str, Any], 
                              intervention: str,
                              yield_potential_t_ha: float,
                              price_per_ton: float) -> Dict[str, Any]:
        """
        Re-compute outcome based on intervention effect.
        Intervention modifies stress factors.
        """
        # Baseline Penalties
        l_water = baseline_state.get("water_loss_factor", 0.0)
        l_nutri = baseline_state.get("nutrient_loss_factor", 0.0)
        l_disease = baseline_state.get("disease_loss_factor", 0.0)
        
        # Apply Intervention Effect
        cost_added = 0.0
        
        if intervention == "irrigate":
            # Reduces water stress
            l_water *= 0.2 # Significant reduction
            cost_added = 20.0 # $/ha
            
        elif intervention == "fertilize":
            # Reduces nutrient stress
            l_nutri *= 0.3
            cost_added = 50.0 # $/ha
            
        elif intervention == "fungicide":
            # Reduces disease risk
            l_disease *= 0.1
            cost_added = 30.0 # $/ha
            
        # Re-calculate Loss
        new_factor = (1 - l_water) * (1 - l_nutri) * (1 - l_disease)
        new_yield = yield_potential_t_ha * new_factor
        
        # Financial Delta
        # Assuming baseline yield calc was similar
        old_factor = (1 - baseline_state.get("water_loss_factor", 0)) * \
                     (1 - baseline_state.get("nutrient_loss_factor", 0)) * \
                     (1 - baseline_state.get("disease_loss_factor", 0))
                     
        old_yield = yield_potential_t_ha * old_factor
        
        yield_gain = new_yield - old_yield
        revenue_gain = yield_gain * price_per_ton
        profit_delta = revenue_gain - cost_added
        
        return {
            "scenario": intervention,
            "new_yield_t_ha": round(new_yield, 2),
            "yield_delta": round(yield_gain, 2),
            "profit_delta_usd": round(profit_delta, 2),
            "roi_pct": round(profit_delta / cost_added * 100, 0) if cost_added > 0 else 0
        }

# Singleton
scenario_engine = ScenarioSimulator()
