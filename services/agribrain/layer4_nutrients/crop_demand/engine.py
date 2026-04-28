
import math
from typing import Dict, Any, List
from layer2_veg_int.schema import PhenologyOutput
from layer3_decision.schema import PlotContext

class CropDemandUptakeEngine:
    """
    Layer 4.2: Crop Demand & Uptake Engine (CDU)
    Objective: Compute N/P/K demand curves based on phenology and yield goals.
    Pure Python implementation (No Numpy).
    """
    
    def __init__(self):
        # Default Cereal Curves (Fraction of Total Uptake by Stage End)
        self.cereal_curve = {
            "EMERGENCE": {"N": 0.05, "P": 0.10, "K": 0.05},
            "VEGETATIVE": {"N": 0.60, "P": 0.50, "K": 0.70}, # Steep N/K uptake
            "REPRODUCTIVE": {"N": 0.90, "P": 0.85, "K": 1.00},
            "MATURITY": {"N": 1.00, "P": 1.00, "K": 1.00},
            "HARVESTED": {"N": 1.00, "P": 1.00, "K": 1.00},
            "DORMANCY": {"N": 0.00, "P": 0.00, "K": 0.00}
        }

    def _convolve_sma(self, data: List[float], window_size: int = 5) -> List[float]:
        """Simple Moving Average Convolve 'same' mode equivalent"""
        if not data: return []
        out = []
        half = window_size // 2
        N = len(data)
        for i in range(N):
            start = max(0, i - half)
            end = min(N, i + half + 1)
            segment = data[start:end]
            out.append(sum(segment) / len(segment))
        return out

    def compute_demand(self, phenology: PhenologyOutput, context: PlotContext) -> Dict[str, Any]:
        """
        Returns cumulative demand and critical windows for N/P/K.
        """
        # 1. Determine Yield Goal
        yield_goal_ton_ha = 10.0 # e.g. Corn
        
        # Removal Rates (kg nutrient per ton yield)
        removal_rates = {
            "N": 20.0, # 200 kg N for 10t corn
            "P": 8.0,
            "K": 20.0
        }
        
        total_needs = {k: v * yield_goal_ton_ha for k,v in removal_rates.items()}
        
        # 2. Map Phenology to Demand
        stages = phenology.stage_by_day
        n_days = len(stages)
        
        cumulative = {"N": [], "P": [], "K": []}
        daily_need = {"N": [], "P": [], "K": []}
        
        targets = {"N": [], "P": [], "K": []}
        for s in stages:
            curve = self.cereal_curve.get(s, self.cereal_curve["VEGETATIVE"])
            for nut in ["N", "P", "K"]:
                targets[nut].append(curve[nut] * total_needs[nut])
                
        for k in ["N", "P", "K"]:
            # Potenital curve
            raw = targets[k]
            # Enforce Monotonicity (accumulate max)
            curr_max = -1.0
            accumulated = []
            for val in raw:
                if val > curr_max:
                    curr_max = val
                accumulated.append(curr_max)
            
            # Smooth
            smoothed = self._convolve_sma(accumulated, window_size=5)
            cumulative[k] = smoothed
            
            # Daily Diff
            # np.diff(smoothed, prepend=0) -> out[i] = in[i] - in[i-1] (for i>0), in[0]-0
            d_uptake = []
            prev = 0.0
            for val in smoothed:
                d = max(0.0, val - prev)
                d_uptake.append(d)
                prev = val
            daily_need[k] = d_uptake
            
        # 3. Identify Critical Windows (Max deriv)
        critical_windows = []
        # Find 5-day window with max N uptake
        n_uptake = daily_need["N"]
        if len(n_uptake) > 5:
            # Moving sum of 5 days valid
            max_sum = -1.0
            peak_idx = -1
            for i in range(len(n_uptake) - 5 + 1):
                param_sum = sum(n_uptake[i:i+5])
                if param_sum > max_sum:
                    max_sum = param_sum
                    peak_idx = i
            
            if peak_idx != -1:
                # Center date
                center_day = peak_idx + 2
                critical_windows.append(f"Peak N Uptake around Day {center_day}")
            
        return {
            "N_demand_cumulative": cumulative["N"],
            "P_demand_cumulative": cumulative["P"],
            "K_demand_cumulative": cumulative["K"],
            "critical_windows": critical_windows,
            "total_needs_kg_ha": total_needs
        }
