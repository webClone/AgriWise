
"""
Layer 2.2: Phenology Inference Engine
Infers the biological stage of the crop based on the Growth Curve and GDD.
Algorithm: Rule-Based Bayesian Filter (Simplified HMM).
"""

from typing import List, Dict, Optional, Tuple
from layer2_veg_int.schema import PhenologyStage

class PhenologyEngine:
    
    
    def __init__(self, crop_config: Optional[Dict] = None):
        # Default Wheat/Barley Priors (Generic Cereal)
        self.crop_priors = crop_config or {
            "name": "Generic Cereal",
            "gdd_base_temp": 0.0,
            "transitions": {
                "emergence_min_gdd": 100,
                "vegetative_min_gdd": 300,
                "reproductive_min_gdd": 800,
                "senescence_min_gdd": 1400,
                "harvest_min_gdd": 1800
            }
        }
        
        # State Transition Graph (Allowed Transitions)
        self.transitions = {
            PhenologyStage.BARE_SOIL: [PhenologyStage.EMERGENCE, PhenologyStage.BARE_SOIL],
            PhenologyStage.EMERGENCE: [PhenologyStage.VEGETATIVE, PhenologyStage.EMERGENCE],
            PhenologyStage.VEGETATIVE: [PhenologyStage.REPRODUCTIVE, PhenologyStage.VEGETATIVE],
            PhenologyStage.REPRODUCTIVE: [PhenologyStage.SENESCENCE, PhenologyStage.REPRODUCTIVE],
            PhenologyStage.SENESCENCE: [PhenologyStage.HARVESTED, PhenologyStage.SENESCENCE],
            PhenologyStage.HARVESTED: [PhenologyStage.BARE_SOIL, PhenologyStage.HARVESTED]
        }
    
    
    def infer_daily_stages(
        self, 
        modeled_ndvi: List[float], 
        velocity: List[float], 
        dates: List[str],
        cumulative_gdd: List[float],
        uncertainty: List[float] = None,
        high_res_visual_check: List[bool] = None
    ) -> Tuple[List[PhenologyStage], List[float]]:
        """
        Infers stage and calculates confidence based on signal-to-noise.
        Returns:
            - stages: Most likely stage per day
            - confidences: Probability/Confidence (0.0 - 1.0)
        """
        stages = []
        confidences = []
        current_stage = PhenologyStage.BARE_SOIL
        
        priors = self.crop_priors["transitions"]
        
        import math
        def get_prob(val, thresh, sigma):
            """CDF of Normal Distribution: P(x > thresh)"""
            if sigma < 1e-6: return 1.0 if val > thresh else 0.0
            z = (val - thresh) / sigma
            return 0.5 * (1.0 + math.erf(z / 1.4142))

        for i, (ndvi, v, gdd_acc) in enumerate(zip(modeled_ndvi, velocity, cumulative_gdd)):
            sigma = uncertainty[i] if uncertainty else 0.05
            
            # Logic: What is the MOST LIKELY next stage?
            candidates = self.transitions.get(current_stage, [current_stage])
            next_stage = current_stage
            confidence = 1.0
            
            # Track duration
            days_in_stage = 0
            if i > 0 and stages[-1] == current_stage:
                # Count backwards how long we've been here
                # Simple heuristic: increment counter
                # In streaming, we'd need state. Here we have full history access but simpler to just track counter locally
                pass 
                
            # Better: maintain a counter output?
            # Or just enforce rule: 
            # if (i - last_transition_idx) < MIN_DURATION: forbid transition
            
            last_transition_idx = 0
            for k in range(len(stages)-1, -1, -1):
                if stages[k] != current_stage:
                    last_transition_idx = k + 1
                    break
            
            current_duration = i - last_transition_idx
            min_duration = 7 # User Constraint
            
            # --- Rule-Based Transition Logic with GDD Gates ---
            # We calculate confidence as the distance from the decision boundary divided by uncertainty
            
            potential_next = current_stage
            calc_conf = 1.0
            
            if current_stage == PhenologyStage.BARE_SOIL:
                # Rule: NDVI > 0.20 AND V > 0.005 (Lowered threshold from 0.25)
                # Confidence is min(P(NDVI>0.20), P(V>0.005))
                p_ndvi = get_prob(ndvi, 0.20, sigma)
                # For velocity, uncertainty is sqrt(2)*sigma_ndvi technically (diff of two points)
                p_v = get_prob(v, 0.005, sigma * 1.414)
                
                cond_met = p_ndvi > 0.5 and p_v > 0.5 and gdd_acc > priors["emergence_min_gdd"]
                
                # Secondary visual check from higher-resolution sources (e.g. Drone RGB / Planet)
                has_visual_emergence = high_res_visual_check and i < len(high_res_visual_check) and high_res_visual_check[i]
                if has_visual_emergence:
                    cond_met = True
                    p_ndvi = max(p_ndvi, 0.8)
                
                if cond_met: 
                    potential_next = PhenologyStage.EMERGENCE
                    calc_conf = min(p_ndvi, p_v) if not has_visual_emergence else p_ndvi
                else:
                    # Confidence in staying Bare Soil = 1 - transition_probability
                    calc_conf = 1.0 - min(p_ndvi, p_v)
            
            elif current_stage == PhenologyStage.EMERGENCE:
                p_ndvi = get_prob(ndvi, 0.4, sigma)
                cond_met = p_ndvi > 0.5 and v > 0.01 and gdd_acc > priors["vegetative_min_gdd"]
                
                if cond_met:
                    potential_next = PhenologyStage.VEGETATIVE
                    calc_conf = p_ndvi
                else:
                    calc_conf = 1.0 - p_ndvi
            
            elif current_stage == PhenologyStage.VEGETATIVE:
                # Transition to Repro: V < 0.002 (Growth Slowing)
                # Threshold is upper bound for V. So P(V < 0.002) = 1 - P(V > 0.002)
                p_v_slow = 1.0 - get_prob(v, 0.002, sigma * 1.414)
                cond_met = p_v_slow > 0.5 and ndvi > 0.6 and gdd_acc > priors["reproductive_min_gdd"]
                
                if cond_met: 
                    potential_next = PhenologyStage.REPRODUCTIVE
                    calc_conf = p_v_slow
                else:
                    calc_conf = 1.0 - p_v_slow
            
            elif current_stage == PhenologyStage.REPRODUCTIVE:
                # Senescence: V < -0.005
                p_v_neg = 1.0 - get_prob(v, -0.005, sigma * 1.414)
                
                if gdd_acc > priors["senescence_min_gdd"] and p_v_neg > 0.5:
                    potential_next = PhenologyStage.SENESCENCE
                    calc_conf = p_v_neg
                else:
                    calc_conf = 1.0 - p_v_neg

            elif current_stage == PhenologyStage.SENESCENCE:
                p_ndvi_low = 1.0 - get_prob(ndvi, 0.25, sigma)
                
                if gdd_acc > priors["harvest_min_gdd"] and p_ndvi_low > 0.5:
                    potential_next = PhenologyStage.HARVESTED
                    calc_conf = p_ndvi_low
                else:
                    calc_conf = 1.0 - p_ndvi_low
            
            # Check Constraints
            if potential_next != current_stage:
                if current_duration < min_duration:
                    potential_next = current_stage # Force stay
                    # Penalty to confidence? Maybe.
                    calc_conf *= 0.8 
            
            # Enforce allowed transitions
            if potential_next in candidates:
                current_stage = potential_next
                confidence = calc_conf
            
            # Clamp confidence
            confidence = max(0.5, min(1.0, confidence))
            stages.append(current_stage)
            confidences.append(float(confidence))
            
        return stages, confidences

    def extract_transitions(self, dates: List[str], stages: List[PhenologyStage]) -> Dict[str, str]:
        """
        Returns {Stage -> Date} for the first occurrence of each stage.
        """
        transitions = {}
        for date, stage in zip(dates, stages):
            if stage.value not in transitions:
                transitions[stage.value] = date
        return transitions
