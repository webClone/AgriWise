from typing import Any
from services.agribrain.layer7_planning.schema import YieldDistribution, SuitabilityState
from services.agribrain.layer7_planning.engines.ccl_crop_library import CropProfile

def compute_yield_distribution(profile: CropProfile, window_state: SuitabilityState, water_state: SuitabilityState, soil_state: SuitabilityState, biotic_state: SuitabilityState) -> YieldDistribution:
    """
    Engine F: Yield Potential & Variability Engine (YVE)
    Produces yield distributions considering downside risk from weather, biotic limits, and soil constraints.
    """
    base_mean = profile.target_gdd / 100.0 # Just a proxy heuristic. Profile could hold explicit base yields.
    
    # Let's derive a better target yield if it's explicitly available, or use a sane default.
    # The CropProfile currently assumes standard target_yield logic based on constraints.
    if hasattr(profile, "target_yield_t_ha"):
        base_mean = profile.target_yield_t_ha
    else:
        # Fallback dictionary
        yields = {"potato": 40.0, "wheat": 5.0}
        base_mean = yields.get(profile.id, 20.0)
        
    p50 = base_mean
    p90 = base_mean * 1.15 # Up to 15% better purely through optimal management
    p10 = base_mean * 0.70 # Baseline standard deviation implies 30% downside
    
    contributors = []
    
    # 1. Season Window Penalty
    if window_state.probability_ok < 0.4:
         penalty = 0.3 # 30% hit on yield if planted way out of cycle
         p50 *= (1.0 - penalty)
         p90 *= (1.0 - penalty)
         p10 *= (1.0 - penalty * 1.5) # Downside crashes
         contributors.append(f"Severely affected expected yield due to {window_state.severity} season window deviation.")
    elif window_state.probability_ok < 0.7:
         penalty = 0.1
         p50 *= (1.0 - penalty)
         contributors.append("Late/Early planting clipped maximum yield bounds.")
         
    # 2. Water Availability (Hard limiter)
    if water_state.probability_ok < 0.3:
         # Fatal bottleneck for yield
         p90 = p50 * 0.8 # No upside if no water
         p50 *= 0.5
         p10 *= 0.3
         contributors.append(f"Water constraints critically slashed expected yields (Probability OK: {water_state.probability_ok:.2f}).")
    elif water_state.probability_ok < 0.6:
         p50 *= 0.85
         p90 *= 0.90
         contributors.append("Moderate water limitations restricted maximum potential yield.")
         
    # 3. Biotic Risk Variability Width
    # Disease doesn't just hit the mean, it violently expands the downside risk.
    if biotic_state.severity == "CRITICAL" or biotic_state.probability_ok < 0.4:
         p10 *= 0.4 # Catastrophic failure risk
         contributors.append("High disease pressure radically expands downside variance (p10).")
         
    # 4. Data Gap Uncertainty Expansion
    avg_conf = (window_state.confidence + water_state.confidence + biotic_state.confidence + soil_state.confidence) / 4.0
    if avg_conf < 0.8:
         uncertainty_spread = (1.0 - avg_conf) * 1.5
         p10 *= (1.0 - min(uncertainty_spread, 0.7))
         contributors.append(f"Data gaps expand uncertainty bands significantly! (Overall Confidence: {avg_conf:.2f}).")
         
    # Ensure sane bounds
    p10 = max(0.0, p10)
    p50 = max(p10, p50)
    p90 = max(p50, p90)
    
    return YieldDistribution(
        mean=p50, # In skewed, p50 isn't mean, but we simplify for MVP reporting
        p10=round(p10, 2),
        p50=round(p50, 2),
        p90=round(p90, 2),
        contributors=contributors or ["Nominal stable yield distribution assumed."]
    )
