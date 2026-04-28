from typing import Dict, Any
from layer7_planning.schema import YieldDistribution, EconomicOutcome
from layer7_planning.engines.ccl_crop_library import CropProfile

def compute_economics(profile: CropProfile, yield_dist: YieldDistribution, user_context: Dict[str, Any] = None) -> EconomicOutcome:
    """
    Engine G: Economics & Optimization Engine (EOE)
    Computes profit/risk for each crop option based on yield distributions.
    """
    # 1. Base prices and costs (fallback to profile defaults if user context missing)
    price_per_ton = profile.default_price_per_ton
    base_cost_ha = profile.base_production_cost_per_ha
    
    if user_context:
        # User could override defaults in settings/memory
        price_per_ton = user_context.get(f"{profile.id}_price_per_ton", price_per_ton)
        base_cost_ha = user_context.get(f"{profile.id}_cost_per_ha", base_cost_ha)
        
    # 2. Compute Profits based on Yield Distribution
    # Revenue = Yield * Price
    # Profit = Revenue - Fixed Costs (Simplification: Assuming all costs are fixed per hectare for MVP)
    
    profit_p50 = (yield_dist.p50 * price_per_ton) - base_cost_ha
    profit_p10 = (yield_dist.p10 * price_per_ton) - base_cost_ha
    profit_p90 = (yield_dist.p90 * price_per_ton) - base_cost_ha
    
    # Expected profit is often weighted in skewed agricultural distributions, but we'll use p50 here for simplicity
    expected_profit = profit_p50
    
    # 3. Break-even Yield
    # How many tons needed to just cover base_cost_ha?
    if price_per_ton > 0:
        break_even_yield = base_cost_ha / price_per_ton
    else:
        break_even_yield = float('inf')
        
    # 4. Sensitivity Analysis (Simple variance calculation)
    # What happens if price drops 10%? What if yield drops 10%?
    price_down_10 = (yield_dist.p50 * (price_per_ton * 0.9)) - base_cost_ha
    yield_down_10 = ((yield_dist.p50 * 0.9) * price_per_ton) - base_cost_ha
    
    sensitivities = {
        "price_-10%": f"${price_down_10 - profit_p50:,.0f}/ha",
        "yield_-10%": f"${yield_down_10 - profit_p50:,.0f}/ha"
    }
    
    return EconomicOutcome(
        expected_profit=round(expected_profit, 2),
        profit_p10=round(profit_p10, 2),
        profit_p50=round(profit_p50, 2),
        profit_p90=round(profit_p90, 2),
        break_even_yield=round(break_even_yield, 2),
        sensitivities=sensitivities
    )
