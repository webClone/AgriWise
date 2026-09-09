from types import SimpleNamespace
import pytest

from layer7_planning.engines.ccl_crop_library import get_crop_profile
from layer7_planning.engines.crb_crop_rotation import compute_crop_rotation
from layer7_planning.engines.eoe_economics import compute_economics
from layer7_planning.engines.ccr_resilience import compute_climate_resilience
from layer7_planning.engines.acm_microclimate import compute_microclimate
from layer7_planning.schema import YieldDistribution, EconomicOutcome, SuitabilityState


def test_crop_rotation_diversity_shannon_entropy():
    """Verify Shannon entropy reward for diverse rotation and penalty for monoculture."""
    wheat = get_crop_profile("wheat")
    assert wheat is not None

    l1_out = SimpleNamespace(
        plot_timeseries=[{"t_min": 2.0, "rain": 10.0}] * 10
    )

    # 1. High-diversity rotation
    chat_memory_diverse = SimpleNamespace(
        known_context={
            "previous_crop": "fava_bean",
            "rotation_history": ["fava_bean", "wheat", "barley", "canola", "chickpea"],
        }
    )
    state_diverse = compute_crop_rotation(wheat, l1_out, None, chat_memory_diverse)
    assert isinstance(state_diverse, SuitabilityState)
    assert state_diverse.probability_ok > 0.5
    assert any("Shannon Entropy" in l.condition for l in state_diverse.evidence_trace)

    # 2. Monoculture / low diversity
    chat_memory_mono = SimpleNamespace(
        known_context={
            "previous_crop": "wheat",
            "rotation_history": ["wheat", "wheat", "wheat"],
        }
    )
    state_mono = compute_crop_rotation(wheat, l1_out, None, chat_memory_mono)
    assert state_mono.probability_ok < state_diverse.probability_ok
    assert any("Continuous or low-diversity" in l.condition for l in state_mono.evidence_trace)


def test_crop_rotation_legume_nitrogen_credit():
    """Verify nitrogen credit recognized when previous crop is a legume."""
    wheat = get_crop_profile("wheat")
    l1_out = SimpleNamespace(plot_timeseries=[{"t_min": 5.0}] * 10)

    # Previous crop fava_bean gives nitrogen credit
    chat_memory_legume = SimpleNamespace(
        known_context={"previous_crop": "fava_bean", "rotation_history": ["fava_bean", "barley"]}
    )
    state_legume = compute_crop_rotation(wheat, l1_out, None, chat_memory_legume)
    assert any("nitrogen credit" in l.condition.lower() for l in state_legume.evidence_trace)


def test_economics_calculation_and_sensitivities():
    """Verify profit distributions, break-even yield, and sensitivity calculations."""
    wheat = get_crop_profile("wheat")
    assert wheat is not None
    # default wheat: price=300, cost=800

    yield_dist = YieldDistribution(mean=5.0, p10=3.5, p50=5.0, p90=6.5, contributors=["base"])
    outcome = compute_economics(wheat, yield_dist)

    assert isinstance(outcome, EconomicOutcome)
    # Expected profit = (p50 * price) - cost = (5.0 * 300) - 800 = 700
    assert outcome.expected_profit == 700.0
    # p10 profit = (3.5 * 300) - 800 = 250
    assert outcome.profit_p10 == 250.0
    # p90 profit = (6.5 * 300) - 800 = 1150
    assert outcome.profit_p90 == 1150.0
    # Ordering: p10 <= p50 <= p90
    assert outcome.profit_p10 <= outcome.profit_p50 <= outcome.profit_p90

    # Break-even yield = cost / price = 800 / 300 = 2.67 t/ha
    assert outcome.break_even_yield == round(800.0 / 300.0, 2)

    # Sensitivities dict
    assert "price_-10%" in outcome.sensitivities
    assert "yield_-10%" in outcome.sensitivities


def test_economics_user_context_overrides():
    """User context can override commodity price and production cost."""
    potato = get_crop_profile("potato")
    assert potato is not None

    yield_dist = YieldDistribution(mean=30.0, p10=20.0, p50=30.0, p90=40.0, contributors=["base"])

    # Override price to 500 (from 400) and cost to 2500 (from 3000)
    user_context = {
        "potato_price_per_ton": 500.0,
        "potato_cost_per_ha": 2500.0,
    }
    outcome = compute_economics(potato, yield_dist, user_context=user_context)
    # profit_p50 = (30 * 500) - 2500 = 12500
    assert outcome.expected_profit == 12500.0
    assert outcome.break_even_yield == round(2500.0 / 500.0, 2)


def test_climate_resilience_and_microclimate():
    """Verify stochastic climate resilience and canopy microclimate solvers."""
    olive = get_crop_profile("olive")
    assert olive is not None

    ts = [
        {"rain": 0.0, "precipitation": 0.0, "t_mean": 22.0, "tmean": 22.0, "solar_radiation": 550.0, "rh": 45.0, "wind_speed": 3.0}
        for _ in range(15)
    ]
    l1_out = SimpleNamespace(plot_timeseries=ts)

    # 1. Resilience
    resilience = compute_climate_resilience(olive, l1_out, None)
    assert isinstance(resilience, SuitabilityState)
    assert 0.0 <= resilience.probability_ok <= 1.0
    assert 0.0 <= resilience.confidence <= 1.0

    # 2. Microclimate
    microclimate = compute_microclimate(olive, l1_out, None, None)
    assert isinstance(microclimate, SuitabilityState)
    assert 0.0 <= microclimate.probability_ok <= 1.0
    assert 0.0 <= microclimate.confidence <= 1.0
