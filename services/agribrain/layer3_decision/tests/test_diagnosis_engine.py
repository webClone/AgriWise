"""Tests for DiagnosisEngine in Layer 3 Decision."""

from layer3_decision.diagnosis.inference import DiagnosisEngine, _get_ky
from layer3_decision.features.builder import DecisionFeatures
from layer3_decision.schema import PlotContext, Diagnosis


def test_ky_yield_response_factors():
    # Maize has high flowering sensitivity Ky > 1.0
    assert _get_ky("maize", "REPRODUCTIVE") == 1.50
    # Wheat has moderate reproductive Ky
    assert _get_ky("wheat", "REPRODUCTIVE") == 0.55
    # Bare soil has 0 sensitivity
    assert _get_ky("wheat", "BARE_SOIL") == 0.0


def test_diagnosis_engine_runs_hypotheses():
    engine = DiagnosisEngine()
    features = DecisionFeatures(
        current_stage="REPRODUCTIVE",
        days_in_stage=15,
        stage_confidence=0.90,
        rain_sum_7d=0.0,
        rain_sum_14d=2.0,
        days_since_rain=12,
        soil_moisture_proxy=0.20,  # Dry soil
        heat_stress_days=4,
        has_anomaly=True,
        anomaly_severity=0.45,
        anomaly_type="VEGETATION_DROP",
        rain_available=True,
        temp_available=True,
        optical_available=True,
        sar_available=True,
        optical_obs_count=5,
        sar_obs_count=4,
    )
    context = PlotContext(
        crop_type="wheat",
        soil_ph=6.8,
    )
    diagnoses = engine.diagnose(features, context)
    assert isinstance(diagnoses, list)
    assert len(diagnoses) > 0

    top = diagnoses[0]
    assert isinstance(top, Diagnosis)
    assert top.probability >= 0.0
    assert top.confidence >= 0.0
    assert len(top.evidence_trace) > 0


def test_diagnosis_engine_healthy_state_produces_low_stress_probabilities():
    engine = DiagnosisEngine()
    features = DecisionFeatures(
        current_stage="VEGETATIVE",
        days_in_stage=20,
        stage_confidence=0.95,
        growth_adequacy=0.90,
        growth_velocity_7d=0.015,
        rain_sum_7d=25.0,
        rain_sum_14d=50.0,
        days_since_rain=2,
        soil_moisture_proxy=0.75,
        has_anomaly=False,
        rain_available=True,
        temp_available=True,
        optical_available=True,
        sar_available=True,
        optical_obs_count=6,
        sar_obs_count=5,
    )
    context = PlotContext(
        crop_type="wheat",
        soil_ph=7.0,
    )
    diagnoses = engine.diagnose(features, context)
    water_diag = next((d for d in diagnoses if "water" in d.problem_id.lower()), None)
    if water_diag:
        assert water_diag.probability < 0.40
