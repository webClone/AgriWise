"""
Layer 0.5: Multiverse Monte Carlo Engine

Runs probabilistic simulations based on the Plot's true DNA parameters
and historical variability to forecast 2030 climate viability.
Includes Terraforming ROI logic for modifying DNA traits.
"""

import numpy as np
import logging
from typing import Dict, List, Tuple
from services.agribrain.layer0.state_vector import ProcessModel, DEFAULT_CROP_PARAMS

logger = logging.getLogger("agribrain.monte_carlo")

class MonteCarloMultiverse:
    """Simulates 10,000 futures to calculate yield probability distributions."""
    
    def __init__(self, plot_dna: Dict):
        """
        plot_dna must contain the inverted traits:
        theta_retention, beta_resilience, alpha_vigor, t_shift
        """
        self.traits = plot_dna["traits"]
        self.base_carbon = plot_dna.get("decadal_insights", {}).get("carbon_memory_proxy", 10.0)
        
    def simulate_multiverse(self, num_universes: int = 2000) -> Dict:
        """
        Runs stochastic weather variations to build a yield probability cloud.
        (Reduced to 2000 for standard API response time, though conceptualized as 10k)
        """
        theta = self.traits["theta_retention"]
        beta = self.traits["beta_resilience"]
        alpha = self.traits["alpha_vigor"]
        
        # We model the final yield as a stochastic function influenced heavily
        # by the DNA traits and randomized "climate shift" stressors.
        # This represents the `ProcessModel` run at macro-scale without daily iteration.
        
        scatter_points = []
        all_yields = []  # Track ALL yields for unbiased statistics
        catastrophes = 0
        records = 0
        
        for i in range(num_universes):
            # 2030 Climate Shift Randomizers
            temp_anomaly = np.random.normal(loc=1.5, scale=1.0) # +1.5C average shift
            rain_anomaly = np.random.normal(loc=-0.1, scale=0.3) # 10% less rain avg, high variance
            
            # Base yield potential
            potential = 100.0 * alpha
            
            # Stress factors
            water_stress = max(0, -rain_anomaly * 50) / max(0.1, theta) # Low retention exacerbates drought
            thermal_stress = max(0, temp_anomaly * 10) * beta # High beta penalty exacerbates heat
            
            final_yield = max(0, potential - water_stress - thermal_stress)
            
            # Add some irreducible systemic noise
            final_yield += np.random.normal(0, 5)
            final_yield = max(0, final_yield)
            
            all_yields.append(final_yield)
            
            if final_yield < 20: catastrophes += 1
            if final_yield > 120: records += 1
            
            # Keep a subset of points for the frontend scatter plot (avoid crashing browser)
            if i < 400:
                scatter_points.append({
                    "id": i,
                    "temp_anomaly": round(temp_anomaly, 2),
                    "rain_anomaly": round(rain_anomaly, 2),
                    "projected_yield": round(final_yield, 1)
                })
                
        return {
            "total_simulations": num_universes,
            "catastrophe_probability": catastrophes / num_universes,
            "record_probability": records / num_universes,
            "average_yield": float(np.mean(all_yields)),  # Unbiased: uses ALL simulations
            "std_yield": float(np.std(all_yields)),
            "scatter_points": scatter_points,
            # Data integrity metadata (#7): Document climate assumptions
            "climate_scenario": {
                "source": "illustrative_global_average",
                "horizon": "2030",
                "temp_anomaly_mean_c": 1.5,
                "rain_anomaly_mean_pct": -10,
                "note": "Projections use uniform global averages, not location-specific CMIP6/SSP scenarios.",
            },
        }

class TerraformingCalculator:
    """Calculates ROI and DNA mutations for physical field interventions."""
    
    INTERVENTIONS = {
        "biochar": {
            "name": "Biochar Injection (400t/ha)",
            "cost_per_ha": 4500,
            "mutations": {"theta_retention": 0.25, "alpha_vigor": 0.10, "beta_resilience": -0.5}
        },
        "tiling": {
            "name": "Subsurface Tile Drainage",
            "cost_per_ha": 2000,
            "mutations": {"theta_retention": -0.15, "beta_resilience": -0.2} # Reduces anoxia
        },
        "cover_crop": {
            "name": "Decadal Deep-Root Cover Crop Sequence",
            "cost_per_ha": 1200,
            # carbon_memory boost modeled as alpha_vigor uplift (soil organic matter → nutrient cycling)
            # and theta_retention uplift (root channels → macropore drainage)
            "mutations": {"alpha_vigor": 0.20, "theta_retention": 0.10}
        }
    }
    
    def __init__(self, current_dna: Dict):
        self.current = current_dna["traits"]
        self.base_carbon = current_dna.get("decadal_insights", {}).get("carbon_memory_proxy", 10.0)
        
    def calculate_roi(self, intervention_id: str, crop_value_per_ton: float = 300) -> Dict:
        if intervention_id not in self.INTERVENTIONS:
            raise ValueError("Unknown intervention")
            
        inv = self.INTERVENTIONS[intervention_id]
        
        # Create mutated DNA
        mutated_dna = {
            "traits": {
                "theta_retention": self.current["theta_retention"] + inv["mutations"].get("theta_retention", 0),
                "beta_resilience": max(0, self.current["beta_resilience"] + inv["mutations"].get("beta_resilience", 0)),
                "alpha_vigor": self.current["alpha_vigor"] + inv["mutations"].get("alpha_vigor", 0),
                "t_shift": self.current["t_shift"]
            }
        }
        
        # Run Multiverse on Base vs Mutated to get expected yield difference
        mc_base = MonteCarloMultiverse({"traits": self.current})
        mc_mut = MonteCarloMultiverse(mutated_dna)
        
        base_yield = mc_base.simulate_multiverse(1000)["average_yield"]
        mut_yield = mc_mut.simulate_multiverse(1000)["average_yield"]
        
        yield_delta = mut_yield - base_yield # Tons per ha (proxy scale)
        revenue_increase_per_year = yield_delta * crop_value_per_ton
        
        # Calculate 10-year ROI
        total_10yr_rev = revenue_increase_per_year * 10
        net_profit = total_10yr_rev - inv["cost_per_ha"]
        roi_pct = (net_profit / inv["cost_per_ha"]) * 100 if inv["cost_per_ha"] > 0 else 0
        
        return {
            "intervention": inv["name"],
            "cost_per_ha": inv["cost_per_ha"],
            "mutated_traits": mutated_dna["traits"],
            "yield_increase_tons": round(yield_delta, 2),
            "roi_10yr_pct": round(roi_pct, 1),
            "disclaimer": "illustrative",  # Costs and crop prices are static estimates, not live market data
            "crop_value_per_ton_used": crop_value_per_ton
        }
