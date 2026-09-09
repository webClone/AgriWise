import pytest
import pandas as pd
from types import SimpleNamespace
from layer6_yield.harvest_optimizer import HarvestOptimizer
from layer6_yield.profitability import ProfitabilityCalculator


def test_harvest_optimizer_maturity_window():
    """Verify harvest window optimization when crop has reached confirmed maturity."""
    optimizer = HarvestOptimizer()
    current_date = pd.Timestamp("2026-06-01")
    
    # Semantic context confirming mature stage
    sem_mature = SimpleNamespace(
        stage_specific_allowed=True,
        phenology_posterior_hash="hash_mature_001",
        phenology_stage="MATURITY",
    )
    
    # 7-day forecast with dry warm weather
    forecast = [
        {"precip_mm": 0.0, "temp_max": 26.0}
        for _ in range(7)
    ]
    
    res = optimizer.optimize_window(
        current_date=current_date,
        phenology_stage="MATURITY",
        forecast_weather=forecast,
        disease_risk_prob=0.10,
        semantic_context=sem_mature,
    )
    
    assert res["action"] == "harvest"
    assert "window_start" in res
    assert "window_end" in res
    assert res["production_eligible"] is True


def test_harvest_optimizer_unconfirmed_stage():
    """Verify that unconfirmed or vegetative stage causes optimizer to wait or verify."""
    optimizer = HarvestOptimizer()
    current_date = pd.Timestamp("2026-06-01")
    
    # Semantic context in vegetative stage
    sem_veg = SimpleNamespace(
        stage_specific_allowed=True,
        phenology_posterior_hash="hash_veg_001",
        phenology_stage="VEGETATIVE",
    )
    forecast = [{"precip_mm": 0.0, "temp_max": 25.0} for _ in range(7)]
    
    res = optimizer.optimize_window(
        current_date=current_date,
        phenology_stage="VEGETATIVE",
        forecast_weather=forecast,
        disease_risk_prob=0.0,
        semantic_context=sem_veg,
    )
    
    assert res["action"] == "wait"
    assert res["production_eligible"] is False


def test_profitability_calculator_margin_and_roi():
    """Verify gross margin, ROI %, and intervention feasibility hurdle."""
    calc = ProfitabilityCalculator()
    
    # Gross Margin: 5 t/ha at $250/t with $600/ha input cost
    # Revenue = $1250, Profit = $650, ROI = 108.3%
    profit_profile = calc.calculate_profit(
        yield_mean_t_ha=5.0,
        price_per_ton=250.0,
        input_costs_per_ha=600.0,
    )
    assert profit_profile["revenue_usd_ha"] == 1250.0
    assert profit_profile["profit_usd_ha"] == 650.0
    assert profit_profile["roi_pct"] > 100.0
    assert profit_profile["break_even_yield"] == 2.4

    # Intervention evaluation: $100 cost for 0.8t yield gain at $250/t
    # Gain = $200, Net Benefit = $100, ROI = 100% > 20% hurdle
    inv_eval = calc.evaluate_intervention(
        cost_of_action=100.0,
        expected_yield_gain_t=0.8,
        price_per_ton=250.0,
    )
    assert inv_eval["net_benefit"] == 100.0
    assert inv_eval["roi_pct"] == 100.0
    assert inv_eval["is_viable"] is True
