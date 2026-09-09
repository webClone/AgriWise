"""Tests for CropSuitabilityEngine in Layer 3 Decision."""

from layer3_decision.suitability_engine import CropSuitabilityEngine, CropSuitabilityResult


def test_suitability_engine_initialization():
    engine = CropSuitabilityEngine()
    assert engine is not None


def test_suitability_evaluation_mediterranean_climate():
    engine = CropSuitabilityEngine()
    result = engine.evaluate(
        lat=36.75,
        lng=3.05,
        annual_rainfall_mm=600.0,
        mean_temp_c=18.0,
        soil_ph=7.2,
        soil_texture="clay_loam",
        soil_salinity_ds_m=1.2,
        slope_pct=3.0,
    )
    assert isinstance(result, CropSuitabilityResult)
    assert result.total_evaluated > 100
    assert len(result.rainfed) <= 15
    assert len(result.irrigated) <= 15
    assert len(result.rainfed) > 0

    top_irrigated = result.irrigated[0]
    top_rainfed = result.rainfed[0]
    assert top_irrigated.score >= top_rainfed.score or top_irrigated.score > 50


def test_suitability_extreme_aridity_triggers_limiting_factors():
    engine = CropSuitabilityEngine()
    result = engine.evaluate(
        lat=32.0,
        lng=3.0,
        annual_rainfall_mm=80.0,  # Hyper-arid Sahara edge
        mean_temp_c=25.0,
        soil_ph=8.2,
        soil_salinity_ds_m=5.0,  # High salinity
        slope_pct=2.0,
    )
    assert len(result.limiting_factors_summary) > 0
    assert any("rainfall" in lf.lower() for lf in result.limiting_factors_summary)
    assert any("salinity" in lf.lower() for lf in result.limiting_factors_summary)


def test_suitability_to_dict_serializable():
    engine = CropSuitabilityEngine()
    result = engine.evaluate(
        lat=36.0,
        lng=4.0,
        annual_rainfall_mm=450.0,
        mean_temp_c=16.0,
    )
    d = result.to_dict()
    assert "rainfed" in d
    assert "irrigated" in d
    assert "limiting_factors_summary" in d
    assert isinstance(d["rainfed"], list)
