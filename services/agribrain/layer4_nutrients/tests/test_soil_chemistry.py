"""Tests for CECEngine and LimingEngine in Layer 4 Nutrients."""

from layer4_nutrients.soil_chemistry.cec_engine import CECEngine, CECResult
from layer4_nutrients.soil_chemistry.liming_engine import LimingEngine, LimeProduct


def test_cec_estimation_from_soil_properties():
    engine = CECEngine()
    # Sandy soil with low OM
    res_sand = engine.estimate_cec(
        clay_pct=5.0,
        sand_pct=85.0,
        organic_matter_pct=1.0,
        ph=6.5,
    )
    assert isinstance(res_sand, CECResult)
    assert res_sand.cec_estimated < 15.0
    assert res_sand.k_leaching_risk in ("high", "moderate")

    # Clay soil with higher OM
    res_clay = engine.estimate_cec(
        clay_pct=45.0,
        sand_pct=15.0,
        organic_matter_pct=3.5,
        ph=7.0,
    )
    assert res_clay.cec_estimated > res_sand.cec_estimated
    assert res_clay.nutrient_holding_capacity in ("good", "moderate")


def test_liming_requirement_for_acidic_soil():
    engine = LimingEngine()
    res = engine.compute_lime_requirement(
        current_ph=5.0,
        crop_type="corn",
        clay_pct=22.0,
        organic_matter_pct=2.5,
    )
    assert res.caco3_equivalent_kg_ha > 0.0
    assert res.product_rate_kg_ha > 0.0
    assert res.target_ph > res.current_ph
    assert res.product in (LimeProduct.AG_LIME, LimeProduct.DOLOMITIC)


def test_liming_not_needed_for_neutral_or_alkaline_soil():
    engine = LimingEngine()
    res = engine.compute_lime_requirement(
        current_ph=7.2,
        crop_type="corn",
    )
    assert res.caco3_equivalent_kg_ha == 0.0
    assert res.product_rate_kg_ha == 0.0
    assert "no lime needed" in res.notes.lower() or res.caco3_equivalent_kg_ha == 0.0
