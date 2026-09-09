"""Tests for DecisionIntelligenceEngine in Layer 3 Decision."""

from datetime import datetime, timezone
from layer1_fusion.schemas import DataHealthScore
from layer3_decision.schema import PlotContext, DecisionOutput, DegradationMode, Layer3InputContext
from layer3_decision.runner import DecisionIntelligenceEngine
from layer3_decision.features.builder import build_decision_features


def _make_dummy_l3_context(
    plot_id: str = "plot-test-1",
    phenology_stage: str = "VEGETATIVE",
) -> Layer3InputContext:
    return Layer3InputContext(
        plot_id=plot_id,
        layer1_run_id="run-l1",
        layer2_run_id="run-l2",
        phenology_stage=phenology_stage,
        phenology_confidence=0.85,
        stage_specific_allowed=True,
        usable_for_layer3=True,
        confidence_ceiling=0.90,
        stress_summary={"WATER": 0.2},
        stress_detail={"WATER": {"severity": 0.2, "confidence": 0.8}},
        zone_status={},
        vegetation_status={},
        operational_signals={
            "rain_available": True,
            "temp_available": True,
            "sar_available": True,
            "optical_available": True,
            "optical_obs_count": 4,
            "sar_obs_count": 3,
            "real_rain_available": True,
            "real_rain_sum_7d": 15.0,
            "real_rain_sum_14d": 35.0,
            "real_days_since_rain": 2,
        },
        data_health=DataHealthScore(
            overall=0.90,
            source_completeness=0.95,
            provenance_completeness=1.0,
            freshness=0.90,
            confidence_ceiling=0.90,
            status="ok",
        ),
    )


def test_build_decision_features_extracts_signals():
    ctx = _make_dummy_l3_context()
    plot_ctx = PlotContext(
        crop_type="wheat",
        soil_ph=7.0,
    )
    features = build_decision_features(ctx, plot_ctx)
    assert features.current_stage == "VEGETATIVE"
    assert features.stage_confidence == 0.85
    assert features.rain_available is True
    assert features.rain_sum_7d == 15.0
    assert features.rain_sum_14d == 35.0


def test_decision_engine_deterministic_execution():
    engine = DecisionIntelligenceEngine()
    ctx = _make_dummy_l3_context()
    plot_ctx = PlotContext(
        crop_type="wheat",
        soil_ph=7.0,
    )
    ts = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    out1 = engine.run_decision_cycle(ctx, plot_ctx, run_id="run-det", run_timestamp=ts)
    out2 = engine.run_decision_cycle(ctx, plot_ctx, run_id="run-det", run_timestamp=ts)

    assert isinstance(out1, DecisionOutput)
    assert isinstance(out2, DecisionOutput)
    assert out1.content_hash() == out2.content_hash()
    assert out1.quality_metrics.degradation_mode in (DegradationMode.NORMAL, DegradationMode.NO_SAR, DegradationMode.LOW_SAR_CADENCE)


def test_decision_engine_missing_data_degrades_gracefully():
    engine = DecisionIntelligenceEngine()
    ctx = Layer3InputContext(
        plot_id="plot-gap",
        layer1_run_id="run-gap-1",
        layer2_run_id="run-gap-2",
        phenology_stage="EMERGENCE",
        phenology_confidence=0.50,
        stage_specific_allowed=True,
        usable_for_layer3=True,
        stress_summary={},
        stress_detail={},
        zone_status={},
        vegetation_status={},
        operational_signals={
            "rain_available": False,
            "temp_available": False,
            "sar_available": False,
            "optical_available": False,
            "optical_obs_count": 0,
            "sar_obs_count": 0,
        },
        data_health=DataHealthScore(
            overall=0.20,
            confidence_ceiling=0.20,
            status="degraded",
        ),
    )
    plot_ctx = PlotContext(crop_type="barley")
    out = engine.run_decision_cycle(ctx, plot_ctx)
    assert out.quality_metrics.degradation_mode == DegradationMode.DATA_GAP
    assert out.quality_metrics.decision_reliability <= 0.30
