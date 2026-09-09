import pytest
from layer5_bio.visual_detection import VisualDetectionEngine, visual_engine
from layer5_bio.outbreak_prediction import OutbreakPredictionEngine, predict_outbreak


def test_visual_detection_engine_fail_closed_contract():
    """Verify that the unvalidated vision engine abstains from diagnostic authority."""
    engine = VisualDetectionEngine()
    assert engine.validation_status == "DISABLED_UNVALIDATED_MODEL"
    
    # Passing dummy image tensor and context
    res = engine.analyze_image(image_tensor=None, context={"crop": "tomato"})
    
    assert res["status"] == "unavailable"
    assert res["authority"] == "VISUALIZATION_ONLY_NO_DIAGNOSIS"
    assert "No validated" in res["reason"]


def test_outbreak_prediction_zero_prevalence():
    """Verify that zero regional plot risks return low status and standard scout priority."""
    res = predict_outbreak(
        regional_plot_risks=[],
        disease_name="late_blight",
        asmae_biotic_risk=0.2,
    )
    
    assert res["outbreak_prob"] == 0.0
    assert res["regional_status"] == "low"
    assert res["scout_priority"] == "standard"
    assert res["asmae_sensitized"] is False


def test_outbreak_prediction_regional_spread_and_asmae_amplification():
    """Verify outbreak scaling across multiple plots with ASMAE biotic risk sensitizer."""
    # 4 plots total: 3 have high risk (>60)
    plot_risks = [
        {"risks": {"late_blight": {"prob": 80}}},
        {"risks": {"late_blight": {"prob": 75}}},
        {"risks": {"late_blight": {"prob": 65}}},
        {"risks": {"late_blight": {"prob": 20}}},
    ]
    
    # Baseline regional prediction without ASMAE sensitizer
    base_res = predict_outbreak(
        regional_plot_risks=plot_risks,
        disease_name="late_blight",
        asmae_biotic_risk=0.1,
    )
    assert base_res["plots_affected"] == "3/4"
    assert base_res["outbreak_prob"] > 60.0
    assert base_res["regional_status"] == "high_alert"
    
    # With strong ASMAE biotic risk (0.8), priority becomes urgent and probability is amplified
    sensitized_res = predict_outbreak(
        regional_plot_risks=plot_risks,
        disease_name="late_blight",
        asmae_biotic_risk=0.8,
    )
    assert sensitized_res["asmae_sensitized"] is True
    assert sensitized_res["scout_priority"] == "urgent"
    assert sensitized_res["outbreak_prob"] >= base_res["outbreak_prob"]
