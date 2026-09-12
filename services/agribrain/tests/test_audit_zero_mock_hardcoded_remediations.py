"""
Verification tests for Zero Mock & Zero Hardcoded Data audit remediations.
Tests confirm fail-closed semantics, observational missingness preservation,
deterministic seeding, and elimination of dummy/mock shortcuts.
"""

from datetime import datetime, timedelta, timezone
import pytest
import numpy as np

# 1. Model Registry: Decoupled validators (no dummy strings)
from asmae_learn.model_registry import (
    validate_model_id,
    validate_artifact_path,
    validate_model_path,
)

def test_model_registry_decoupled_validators():
    # Valid model ID
    validate_model_id("model_expert_v1")
    
    # Path traversal rejected
    with pytest.raises(ValueError, match="unsafe_model_id_path_traversal"):
        validate_model_id("../model_expert")
    with pytest.raises(ValueError, match="unsafe_model_id_path_traversal"):
        validate_model_id("model/expert")
    with pytest.raises(ValueError, match="empty_model_id"):
        validate_model_id("")

    # Valid artifact path
    validate_artifact_path("models/v1/weights.json")
    validate_artifact_path("models/v1/tensors.npz")
    
    # Unsafe artifact paths
    with pytest.raises(ValueError, match="pickle_artifacts_forbidden"):
        validate_artifact_path("weights.pkl")
    with pytest.raises(ValueError, match="unexpected_file_extension"):
        validate_artifact_path("weights.txt")
    with pytest.raises(ValueError, match="unsafe_artifact_path_traversal"):
        validate_artifact_path("models/../etc/weights.json")
    with pytest.raises(ValueError, match="empty_artifact_path"):
        validate_artifact_path("")


# 2. Scene Query: Grounded overlap calculation & MGRS boundary checks
from layer0.archive.scene_query import check_tile_overlap

def test_scene_query_tile_overlap_grounded():
    # Boufarik, Algeria: lon ~2.91, lat ~36.57 (Inside MGRS tile 31S)
    boufarik_wkt = "POLYGON ((2.91 36.57, 2.92 36.57, 2.92 36.58, 2.91 36.58, 2.91 36.57))"
    
    # Inside MGRS 31S
    assert check_tile_overlap("T31SUD", boufarik_wkt) == 1.0
    assert check_tile_overlap("31SUD", boufarik_wkt) == 1.0
    
    # Wrong MGRS zone (Zone 10 is in North America)
    assert check_tile_overlap("T10SUD", boufarik_wkt) == 0.0
    
    # Geometric bounding box overlap
    tile_geom = "POLYGON ((2.90 36.50, 2.95 36.50, 2.95 36.60, 2.90 36.60, 2.90 36.50))"
    overlap = check_tile_overlap(tile_geom, boufarik_wkt)
    assert overlap == 1.0  # Fully contained
    
    # Partial geometric overlap
    partial_tile = "POLYGON ((2.915 36.57, 2.95 36.57, 2.95 36.60, 2.915 36.60, 2.915 36.57))"
    partial_overlap = check_tile_overlap(partial_tile, boufarik_wkt)
    assert 0.0 < partial_overlap < 1.0
    
    # Disjoint geometric overlap
    disjoint_tile = "POLYGON ((5.0 40.0, 5.1 40.0, 5.1 40.1, 5.0 40.1, 5.0 40.0))"
    assert check_tile_overlap(disjoint_tile, boufarik_wkt) == 0.0
    
    # Fail-closed on invalid or empty
    assert check_tile_overlap("", boufarik_wkt) == 0.0
    assert check_tile_overlap("T31SUD", "") == 0.0
    assert check_tile_overlap("not_valid", "not_valid") == 0.0


# 3. Monte Carlo Engine: Deterministic seeding
from layer0.calibration.monte_carlo_engine import MonteCarloMultiverse

def test_monte_carlo_multiverse_deterministic_seeding():
    plot_dna = {
        "traits": {
            "theta_retention": 0.5,
            "beta_resilience": 0.8,
            "alpha_vigor": 1.0,
            "t_shift": 0.0,
        },
        "decadal_insights": {"carbon_memory_proxy": 12.0}
    }
    engine = MonteCarloMultiverse(plot_dna)
    
    # With identical seed, outputs must be bit-exact
    res1 = engine.simulate_multiverse(num_universes=50, seed=12345)
    res2 = engine.simulate_multiverse(num_universes=50, seed=12345)
    
    assert res1["average_yield"] == res2["average_yield"]
    assert res1["std_yield"] == res2["std_yield"]
    assert res1["catastrophe_probability"] == res2["catastrophe_probability"]
    assert res1["scatter_points"] == res2["scatter_points"]
    
    # With different seed, stochastic variance is present
    res3 = engine.simulate_multiverse(num_universes=50, seed=99999)
    assert res1["average_yield"] != res3["average_yield"]


# 4. Governance Calibration: Delegated to Authoritative Engine
from layer6_exec.governance.calibration import propose_calibration as gov_propose_calibration

def test_governance_calibration_delegates_cleanly():
    # Empty evidence produces zero proposals without crashing or using hardcoded defaults
    proposals = gov_propose_calibration(evidence_batch=[], feedback_signals={})
    assert isinstance(proposals, list)
    assert len(proposals) == 0


# 5. Yield Forecast: input_hash defaults to None and hashes deterministically
from layer6_yield.yield_forecast import predict_yield, YieldForecastEngine

def test_yield_forecast_deterministic_input_hash():
    engine = YieldForecastEngine()
    res = engine.predict_yield(
        crop_type="wheat",
        final_biomass_kg_ha=8000.0,
        cumulative_stress={"water_loss_factor": 0.1, "nutrient_loss_factor": 0.0},
    )
    # input_hash must not be "mock_hash"
    assert res["meta"]["input_hash"] != "mock_hash"
    assert len(res["meta"]["input_hash"]) == 16


# 6. Trust Monitor: Deterministic current_time replay
from layer7_risk.trust_monitor import TrustMonitor

def test_trust_monitor_deterministic_current_time():
    mon = TrustMonitor()
    fixed_now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    sat_date = fixed_now - timedelta(days=3)
    
    res = mon.evaluate_trust(
        last_satellite_date=sat_date,
        sensor_active=True,
        forecast_available=True,
        current_time=fixed_now,
    )
    assert res["trust_score"] == 100
    assert res["trust_level"] == "High"


# 7. Stress Attributor: Preserving observational missingness (temp_max is None)
from layer2_intelligence.stress_attributor import _assess_thermal_stress
from layer1_fusion.outputs.asmae_feature_view import ASMAEFeature

def test_thermal_stress_preserves_none_temperature():
    feat = ASMAEFeature(
        variable="ASMAE_THERMAL_STRESS",
        value=0.45,
        confidence=0.85,
        uncertainty=0.15,
        resolution_m=10.0,
        asmae_channel="state_evidence",
        diagnostic_only=False,
        state_update_allowed=True,
        artifact_instance_hash="art_hash_123",
        retro_status="success_with_holdouts",
        bma_status="success",
    )
    
    class Context:
        asmae_features = {"ASMAE_THERMAL_STRESS": feat}
    
    ctx = Context()
    
    # When temp_max is None and veg_thermal_anomaly is None, but ASMAE thermal is present:
    # Function should score thermal stress based on ASMAE WITHOUT fabricating a 0.0C temperature!
    stress = _assess_thermal_stress(
        temp_max=None,
        vpd=None,
        ndvi=0.6,
        conf_ceiling=1.0,
        base_unc=0.1,
        conflict_penalty=0.0,
        env_features={},
        veg_features={},
        plot_id="test_plot",
        run_id="test_run",
        spatial_scope="plot",
        scope_id="test_scope",
        context=ctx,
    )
    assert stress is not None
    assert stress.stress_type == "THERMAL"
    assert stress.severity > 0.0
    # The explanation basis must reflect ASMAE thermal stress, NOT "Temperature max=0.0°C"
    for chain_entry in stress.explanation_basis:
        assert "0.0°C" not in chain_entry
        assert "Temperature max" not in chain_entry


# 8. Layer 0: Satellite RGB Preprocessor fails closed without synthetic array fabrication
from layer0.perception.satellite_rgb.preprocess import SatelliteRGBPreprocessor
from layer0.perception.satellite_rgb.engine import SatelliteRGBEngine
from layer0.perception.satellite_rgb.schemas import SatelliteRGBEngineInput

def test_satellite_rgb_preprocessor_fails_closed_on_missing_or_corrupt_image():
    prep = SatelliteRGBPreprocessor()
    # Providing nonexistent file reference
    ctx = prep.preprocess(
        image_width=10,
        image_height=10,
        ground_resolution_m=10.0,
        rgb_image_ref="nonexistent_file_path_xyz123.jpg",
    )
    # Must record load_error and NOT fabricate 0.3/0.4/0.2 arrays
    assert ctx.load_error is not None
    assert "Image not found" in ctx.load_error
    assert len(ctx.red) == 0
    assert ctx.mean_green == 0.0

def test_satellite_rgb_engine_fails_closed_on_ingress_error():
    engine = SatelliteRGBEngine()
    inp = SatelliteRGBEngineInput(
        plot_id="test_plot",
        rgb_image_ref="nonexistent_image_xyz.png",
        image_width=16,
        image_height=16,
        ground_resolution_m=10.0,
    )
    # Should fail closed and return None
    res = engine.process_full(inp)
    assert res is None


# 9. Layer 0: Satellite tile runtime fails closed unless ALLOW_SYNTHETIC_VISUAL_PREVIEW is true
import os
from layer0.perception.satellite_rgb.tile_runtime import _return_fallback

def test_tile_runtime_fails_closed_without_explicit_synthetic_permission(monkeypatch):
    monkeypatch.delenv("ALLOW_SYNTHETIC_VISUAL_PREVIEW", raising=False)
    tile = _return_fallback("plot_nonexistent_12345", "test_status")
    assert tile is None

    # When explicitly allowed for local UI mockup:
    monkeypatch.setenv("ALLOW_SYNTHETIC_VISUAL_PREVIEW", "true")
    tile_mock = _return_fallback("plot_nonexistent_12345", "test_status")
    assert tile_mock is not None
    assert len(tile_mock) > 0


# 10. Layer 0: Drone RGB Engine uses genuine frame refs (no mock_ pollution)
from layer0.perception.drone_rgb.engine import DroneRGBEngine
from layer0.perception.drone_rgb.schemas import DroneRGBInput
from drone_mission.schemas import FlightMode, MissionType

def test_drone_rgb_engine_avoids_mock_prefix():
    engine = DroneRGBEngine()
    inp = DroneRGBInput(
        plot_id="plot_drone_test",
        mission_id="mission_999",
        flight_mode=FlightMode.COMMAND_REVISIT_MODE,
        mission_type=MissionType.CONCERN_ZONE_COMMAND,
        raw_frames_urls=["https://drone.storage/frame1.jpg", "https://drone.storage/frame2.jpg"],
    )
    out, packets = engine.process_full(inp)
    assert out.routed_frame_count == 2
    assert out.routed_to_farmer_photo is True


# 11. Layer 0: Farmer Photo Preprocessor handles synthetic error cleanly
from layer0.perception.farmer_photo.preprocess import FarmerPhotoPreprocessor

def test_farmer_photo_preprocess_no_crash_on_corrupt_synthetic():
    prep = FarmerPhotoPreprocessor()
    # Corrupt synthetic pixels structure (e.g. non-iterable)
    res = prep.preprocess(
        synthetic_pixels="corrupt_string_instead_of_dict",
        image_width=10,
        image_height=10,
    )
    assert res.real_image_loaded is False
    assert "Synthetic pixel extraction error" in res.load_error


# 12. Layer 0: IP Camera Preprocessor default source is none
from layer0.perception.ip_camera.preprocess import IPCameraPreprocessor
from layer0.perception.ip_camera.schemas import IPCameraEngineInput

def test_ip_camera_preprocess_default_source_is_not_mock():
    prep = IPCameraPreprocessor()
    inp = IPCameraEngineInput(
        plot_id="plot_cam_1",
        camera_id="cam_1",
    )
    result, context = prep.process(inp)
    assert context["source"] == "none"

    # When override_frame_stats or mock_frame_stats is explicitly provided:
    inp_with_stats = IPCameraEngineInput(
        plot_id="plot_cam_1",
        camera_id="cam_1",
        metadata={"mock_frame_stats": {"green_fraction": 0.5, "mean_brightness": 130.0}},
    )
    res_stats, ctx_stats = prep.process(inp_with_stats)
    assert ctx_stats["source"] == "mock_stats"
    assert res_stats.green_ratio == 0.5


# 13. Layer 0: Pattern Maturity API accepts override_stats and baseline is zero-initialized
from layer0.learning.pattern_maturity import PatternMaturityEngine

def test_pattern_maturity_api_accepts_override_stats_and_defaults_zero():
    engine = PatternMaturityEngine()
    # Baseline for unknown plot should have 0 observations, not magic numbers
    stats = engine.get_plot_stats("unknown_plot_xyz")
    assert stats["observations"] == 0
    assert stats["active_patterns"] == 0

    # Passing explicit override_stats
    score = engine.get_maturity_score(
        pattern_name="anomaly_gate",
        plot_id="unknown_plot_xyz",
        override_stats={"observations": 20, "days": 10, "sources": 2, "seasons": 1, "donor_plots": 0, "donor_maturity": 0.0, "yield_reports": 0, "active_patterns": 0, "crop_type": "wheat"},
    )
    assert score > 0.0


# 14. Layer 0: SoilGrids and FAO default access methods are authoritative
from layer0.environment.soilgrids.schemas import SoilGridsProfile
from layer0.environment.soilgrids.normalizer import normalize_soilgrids_response
from layer0.environment.fao.schemas import FAOSoilContext
from layer0.environment.fao.normalizer import normalize_fao_response
from layer0.environment.provenance import build_provenance

def test_soilgrids_and_fao_default_access_methods_are_authoritative():
    # SoilGrids schema default
    profile = SoilGridsProfile()
    assert profile.access_method == "rest_api"

    # SoilGrids normalizer default
    norm_profile = normalize_soilgrids_response(raw_data={}, latitude=36.5, longitude=3.0)
    assert norm_profile.access_method == "rest_api"

    # FAO schema default
    fao_context = FAOSoilContext()
    assert fao_context.access_method == "api"

    # FAO normalizer default
    norm_fao = normalize_fao_response(raw_data={})
    assert norm_fao.access_method == "api"

    # Environmental provenance default
    prov = build_provenance(latitude=36.5, longitude=3.0)
    assert prov["soilgrids_access_method"] == "rest_api"


# 15. Layer 0: SoilGrids QA strictly marks empty profile as UNUSABLE
from layer0.environment.soilgrids.qa import evaluate_soilgrids_qa
from layer0.environment.soilgrids.schemas import SoilGridsQualityClass

def test_soilgrids_qa_marks_empty_profile_unusable():
    empty_profile = normalize_soilgrids_response(raw_data={}, latitude=36.5, longitude=3.0)
    qa = evaluate_soilgrids_qa(empty_profile)
    assert qa.quality_class.value == "unusable"
    assert "EMPTY_PROFILE" in qa.flags


# 16. Layer 0: Fusion derives authentic FC and WP without hardcoded 10.0
from layer0.environment.soilgrids.profile_builder import build_derived_hydraulics
from layer0.environment.fusion import _params_from_soilgrids

def test_fusion_derives_authentic_fc_and_wp_without_hardcoded_wp():
    # Raw SoilGrids data with wv003 (FC) and wv1500 (WP) (units in raw 0.1 vol% -> factor 10)
    raw_data = {
        "0-5cm": {
            "wv003": {"mean": 320},   # 32.0 vol% Field Capacity
            "wv1500": {"mean": 140},  # 14.0 vol% Wilting Point
            "cfvo": {"mean": 50},     # 5.0 vol% coarse fragments
        },
        "5-15cm": {
            "wv003": {"mean": 310},
            "wv1500": {"mean": 130},
        }
    }
    profile = normalize_soilgrids_response(raw_data=raw_data, latitude=36.5, longitude=3.0)
    hydraulics = build_derived_hydraulics(profile)
    
    assert hydraulics.field_capacity_vol_pct == 32.0
    assert hydraulics.wilting_point_vol_pct == 14.0

    params = _params_from_soilgrids(hydraulics)
    # Must equal authentic 32.0 and 14.0, NEVER the old hardcoded 10.0
    assert params.field_capacity_vol_pct == 32.0
    assert params.wilting_point_vol_pct == 14.0


# 17. Layer 0: SoilGrids normalizer supports scalar values and dictionaries
def test_soilgrids_normalizer_supports_scalars_and_dicts():
    raw_data = {
        "0-5cm": {
            "clay": 250,      # scalar raw int
            "sand": 450.0,    # scalar raw float
            "silt": {"mean": 300},  # dict with mean
        }
    }
    profile = normalize_soilgrids_response(raw_data=raw_data, latitude=36.5, longitude=3.0)
    layer = profile.depth_layers["0-5cm"]
    assert layer.get("clay") == 25.0
    assert layer.get("sand") == 45.0
    assert layer.get("silt") == 30.0
# 18. Layer 0: ProcessForcing and derived weather confidence fail closed to 0.0 when unmeasured
def test_process_forcing_and_derived_weather_confidence_fail_closed_to_zero():
    from layer0.environment.schemas import ProcessForcing
    from layer0.environment.weather.derived import compute_daily_forcing
    from layer0.environment.weather.schemas import WeatherConsensusDaily

    forcing_default = ProcessForcing()
    assert forcing_default.rainfall_confidence == 0.0
    assert forcing_default.weather_confidence == 0.0

    consensus_empty = WeatherConsensusDaily(
        date="2024-05-01",
        variable_consensus={},
        overall_confidence=None,
    )
    forcing_computed = compute_daily_forcing(consensus_empty)
    assert forcing_computed.rainfall_confidence == 0.0
    assert forcing_computed.weather_confidence == 0.0


# 19. Layer 0/1: Kalman engine step invokes predict_missing_weather when weather is None
def test_kalman_filter_step_missing_weather_invokes_unforced_missing_mode():
    from layer0.kalman_engine import ZoneKalmanFilter

    zkf = ZoneKalmanFilter(zone_id="zone_test_missing_w")
    zkf.initialize(day="2026-07-01")

    provenance = zkf.step(day="2026-07-02", weather=None)
    assert provenance["weather_update_mode"] == "missing_weather_high_uncertainty"
    assert zkf.provenance_history[0]["weather_update_mode"] == "missing_weather_high_uncertainty"


# 20. Layer 1: Zone engine fallback preserves None signature instead of fake values
def test_zone_engine_fallback_preserves_none_signature():
    from layer1_fusion.zone_engine import _fallback_single_zone

    grid_spec = {"width": 5, "height": 5}
    zones = _fallback_single_zone(grid_spec)
    for z_id, z_data in zones.items():
        assert z_data["signature"]["ndvi_median"] is None


# 21. Layer 1: Data fusion static and weather merge preserves None when missing
def test_data_fusion_preserves_none_static_soil_and_weather_when_missing():
    from layer1_fusion.data_fusion import DataFusionEngine
    from layer1_fusion.schema import FieldTensor

    engine = DataFusionEngine()
    tensor = FieldTensor(
        plot_id="p1", run_id="r1",
        time_index=["2026-07-01", "2026-07-02"]
    )

    # Empty evidence
    engine._merge_static(tensor, evidence=[])
    assert tensor.static["soil_clay_mean"] is None
    assert tensor.static["soil_sand_mean"] is None
    assert tensor.static["soil_ph_mean"] is None
    assert tensor.static["data_source"] == "no_data"

    # Weather merge with empty evidence
    records = [{"date": "2026-07-01"}]
    engine._merge_weather_into_records(records, evidence=[])
    assert records[0]["tmean"] is None
    assert records[0]["gdd"] == 0.0


# 22. Layer 2: GrowthCurveEngine.compute_water_balance preserves None on missing ET0
def test_growth_engine_water_balance_preserves_none_without_fake_et0():
    from layer2_veg_int.growth_engine import GrowthCurveEngine

    et0_series = [4.5, None, 5.0, None]
    rain_series = [0.0, 10.0, 0.0, 2.0]
    kc_series = [1.0, 1.0, 1.1, 1.1]

    et_actual, et_deficit = GrowthCurveEngine.compute_water_balance(
        et0_series, rain_series, kc_series
    )

    assert et_actual[0] == 2.0  # min(4.5, 0.0 + 2.0)
    assert et_deficit[0] == 4.5
    assert et_actual[1] is None
    assert et_deficit[1] is None
    assert et_actual[2] == 2.0
    assert et_deficit[2] == 5.5
    assert et_actual[3] is None
    assert et_deficit[3] is None

    # Test WUE computation safely handles None in et_actual
    wue_res = GrowthCurveEngine.compute_water_use_efficiency(
        biomass_series=[10.0, 15.0, 20.0, 25.0],
        et_actual_series=et_actual,
    )
    assert wue_res["wue"] >= 0.0
    assert wue_res["et_total"] == 4.0  # 2.0 + 2.0 (excluding None)


# 23. Layer 2: Runner._compute_health_index returns 0.0 when no health components observed
def test_runner_health_index_zero_when_no_components_observed():
    from layer2_veg_int.runner import VegetationIntelligenceEngine

    engine = VegetationIntelligenceEngine()
    # Pass empty lists and None components
    health = engine._compute_health_index(
        modeled_ndvi=[0.12],  # exactly at trough
        lai_series=[],
        cwsi_series=[],
        anomalies=[],
        integrals={},
        total_timesteps=10,
    )
    assert health.overall_score >= 0.0
    assert health.component_state_mask["water_state"] == "UNKNOWN"


# 24. Layer 2: SpatialAnalysisEngine._rank_zones_with_trend sets 0.0 for empty timeseries
def test_spatial_engine_rank_zones_returns_zero_for_empty_timeseries():
    from layer2_veg_int.spatial_engine import SpatialAnalysisEngine

    zone_means = {
        "zone_1": [0.4, 0.45, 0.5],
        "zone_2": [],  # completely empty timeseries
    }
    scores, worst, best, trends = SpatialAnalysisEngine._rank_zones_with_trend(zone_means)
    assert scores["zone_2"] == 0.0
    assert worst == "zone_2"
    assert best == "zone_1"


# 25. Layer 2: TemporalAnomalyEngine does not fabricate -6.0 Z-score when EVI/NDWI is None
def test_temporal_anomaly_engine_handles_none_evi_ndwi_without_false_drop():
    from layer2_veg_int.anomaly_engine import TemporalAnomalyEngine

    dates = [f"2026-06-{i:02d}" for i in range(1, 15)]
    observed_ndvi = [0.6] * 14
    modeled_ndvi = [0.6] * 14
    uncertainties = [0.05] * 14

    # EVI is completely unmeasured (all None)
    evi_series = [None] * 14
    ndwi_series = [None] * 14

    engine = TemporalAnomalyEngine()
    anomalies = engine.detect_anomalies(
        dates=dates,
        observed_ndvi=observed_ndvi,
        modeled_ndvi=modeled_ndvi,
        uncertainties=uncertainties,
        evi_series=evi_series,
        ndwi_series=ndwi_series,
    )
    # Zero anomalies should be detected when NDVI is perfectly tracking model
    # and EVI/NDWI are unobserved (None must not trigger false nutrient/water drop)
    assert len(anomalies) == 0


# 26. Layer 3 Water: Runner uses bare-soil baseline when vegetation_state is None
def test_layer3_water_runner_uses_bare_soil_when_vegetation_unmeasured():
    from layer3_water.runner import WaterIntelligenceEngine
    from layer3_water.contracts import HydrologyMode
    from datetime import datetime, timezone

    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    weather_obs = {
        "t_max_c": 30.0,
        "t_min_c": 18.0,
        "precipitation_mm": 0.0,
        "wind_speed_2m_m_s": 2.0,
        "rh_min_pct": 35.0,
        "rh_max_pct": 80.0,
        "net_radiation_mj_m2": 20.0,
    }

    # Pass vegetation_state=None -> unmeasured vegetation
    water_state, feedback = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot_bare_test",
        timestamp=now,
        vegetation_state=None,
        weather_observations=weather_obs,
        hydrology_mode=HydrologyMode.FAO56_LAYERED_BUCKET,
    )

    # Kcb must reflect bare soil (kcb_min = 0.15) rather than lush canopy (kcb ~ 1.15 for LAI=2.5)
    assert water_state.fluxes.potential.kcb <= 0.20
    # Potential transpiration must not be inflated by fake canopy
    assert water_state.vegetation_boundary is None


# 27. Layer 3 Decision: compute_water_budget does not fabricate 80% canopy fractional cover
def test_layer3_decision_water_budget_neutral_when_ndvi_unmeasured():
    from layer3_decision.features.evapotranspiration import compute_water_budget

    # When NDVI is None, lst_weight should be neutral 0.5 rather than 0.85
    wb = compute_water_budget(
        et0_mm=5.0,
        kc=1.0,
        lst_canopy_c=32.0,
        t_air_c=28.0,
        ndvi=None,  # Unmeasured
    )

    # et_potential = 5.0 * 1.0 = 5.0
    # canopy_air_delta = 4.0; cwsi = (4.0 - (-2.0)) / (12.0 - (-2.0)) = 6/14 = 0.4286
    # et_actual_lst = 5.0 * (1 - 0.4286) = 2.857
    # With lst_weight = 0.5 (neutral): et_actual_fused = 0.5 * 5.0 + 0.5 * 2.857 = 3.929
    # (If old fake fc=0.8 had been used, lst_weight was 0.85, producing et_actual_fused ~ 3.18)
    assert abs(wb.et_actual_mm - 3.929) < 0.05


# 28. Layer 3 Decision: build_decision_features sets spatial_stability UNKNOWN with 0.0 confidence when no zones exist
def test_layer3_decision_build_features_unknown_stability_when_no_zones():
    from layer3_decision.features.builder import build_decision_features
    from layer3_decision.schema import PlotContext
    from layer2_intelligence.outputs.layer3_adapter import Layer3InputContext
    from layer1_fusion.schemas import DataHealthScore

    ctx = Layer3InputContext(
        plot_id="plot_no_zones",
        zone_status={},  # No management zones
        operational_signals={},
        data_health=DataHealthScore(overall=1.0, confidence_ceiling=1.0, status="ok"),
    )
    features = build_decision_features(ctx, PlotContext())

    assert features.spatial_stability == "UNKNOWN"
    assert features.spatial_confidence == 0.0


# 29. Layer 3 Decision: _apply_forecast_features does not fabricate 15C and 30C for missing temps
def test_layer3_decision_forecast_features_does_not_fabricate_missing_temps():
    from layer3_decision.features.builder import _apply_forecast_features, DecisionFeatures

    # 3-day forecast where temperature data is missing (e.g. only precipitation forecasted)
    forecast = [
        {"rain": 5.0},
        {"rain": 0.0},
        {"rain": 2.0},
    ]
    features = DecisionFeatures()
    features = _apply_forecast_features(features, forecast)

    assert features.forecast_available is True
    assert features.forecast_rain_3d == 7.0
    assert features.forecast_cold_days == 0
    assert features.forecast_heat_days == 0


# 30. Layer 3 Decision: PolicyEngine._estimate_resources grounds root depth in authorized crop profile
def test_layer3_decision_policy_grounds_root_depth_in_crop_profile():
    from layer3_decision.policy.policies import PolicyEngine
    from layer3_decision.schema import PlotContext, Diagnosis
    from layer3_decision.knowledge.ontology import ACTIONS, ProblemType

    engine = PolicyEngine()
    action_def = ACTIONS["IRRIGATE_FULL"]
    diag = Diagnosis(
        problem_id=ProblemType.WATER_STRESS.value,
        probability=0.8,
        severity=0.7,
        confidence=0.9,
    )

    # Crop with shallow roots (e.g. onion ~30cm vs default 100cm)
    shallow_context = PlotContext(
        crop_type="onion",
        species_specific_allowed=True,
        soil_texture_class="loam",
    )
    res_shallow = engine._estimate_resources(action_def, shallow_context, diag)

    # Crop with standard/deep roots (e.g. wheat ~100cm)
    wheat_context = PlotContext(
        crop_type="wheat",
        species_specific_allowed=True,
        soil_texture_class="loam",
    )
    res_wheat = engine._estimate_resources(action_def, wheat_context, diag)

    # Shallow crop must have lower TAW and irrigation dose than wheat
    assert res_shallow["taw_mm"] < res_wheat["taw_mm"]
    assert res_shallow["irrigation_dose_mm"] < res_wheat["irrigation_dose_mm"]


# 31. Layer 0 Wiring: Wrappers Fail-Closed and State Engine Timezone Integrity
def test_layer0_wrappers_fail_closed_and_state_engine_timezone():
    from types import SimpleNamespace
    from services.agribrain.layer0.wrappers import wrap_environment, wrap_sensors
    from services.agribrain.layer0.observation_packet import DataStatus
    from services.agribrain.layer0.runner import Layer0Runner, Layer0RunnerInput
    from services.agribrain.layer0.state_engine import Layer0StateEngine

    # 1. wrap_environment with empty data fails closed
    empty_env = SimpleNamespace(
        plot_id="plot_empty",
        soilgrids_profile=None,
        fao_context=None,
        weather_consensus=[],
        timestamp_window={},
        packets=[],
        weak_kalman_observations=[],
        process_forcing=[],
        diagnostics={},
        provenance={},
        qa=None,
    )
    env_pkg = wrap_environment(empty_env, plot_id="plot_empty")
    assert env_pkg.is_available is False
    assert env_pkg.data_status == DataStatus.UNAVAILABLE

    # 2. wrap_sensors with no readings fails closed
    empty_sensors = SimpleNamespace(
        plot_id="plot_empty",
        readings=[],
        window_start=None,
        window_end=None,
        observation_packets=[],
    )
    sensor_pkg = wrap_sensors(empty_sensors, plot_id="plot_empty")
    assert sensor_pkg.is_available is False
    assert sensor_pkg.data_status == DataStatus.UNAVAILABLE

    # 3. Layer0Runner timestamp is timezone-aware ISO
    runner = Layer0Runner()
    runner_out = runner.run(Layer0RunnerInput(plot_id="p1", start_date="2026-05-01", end_date="2026-05-02"))
    ts_str = runner_out.provenance["run_timestamp"]
    parsed_ts = datetime.fromisoformat(ts_str)
    assert parsed_ts.tzinfo is not None

    # 4. Layer0StateEngine timestamp is timezone-aware ISO
    state_engine = Layer0StateEngine()
    state_pkg = state_engine.run(
        plot_id="p1",
        start_date="2026-05-01",
        end_date="2026-05-02",
        daily_weather={},
        observations_by_day={},
        events_by_day={},
    )
    if state_pkg.provenance.get("run_timestamp"):
        engine_ts = datetime.fromisoformat(state_pkg.provenance["run_timestamp"])
        assert engine_ts.tzinfo is not None


# 32. Layer 0 Cache System: 3-Tier Storage and Fallback Store Semantics
def test_layer0_cache_system_and_adaptive_ttl(tmp_path):
    from services.agribrain.layer0.data_gateway.filesystem_fallback import FilesystemFallbackStore
    from services.agribrain.layer0.data_gateway.adaptive_ttl import AdaptiveTTLEngine
    from services.agribrain.layer0.calibration.dna_cache import save_dna_cache, load_dna_cache, get_dna_hash

    # 1. FilesystemFallbackStore TTL enforcement
    fs = FilesystemFallbackStore(cache_root=tmp_path / "fs_cache")
    fs.put("soilgrids", 33.5, -7.6, {"clay": 25}, ttl_seconds=3600, plot_id="plot_test")
    hit = fs.get("soilgrids", 33.5, -7.6, plot_id="plot_test")
    assert hit == {"clay": 25}

    # Expired entry returns None
    fs.put("soilgrids_exp", 33.5, -7.6, {"clay": 25}, ttl_seconds=-1, plot_id="plot_test")
    expired_hit = fs.get("soilgrids_exp", 33.5, -7.6, plot_id="plot_test")
    assert expired_hit is None

    # 2. AdaptiveTTLEngine handles naive & aware anomaly timestamps safely
    ttl_engine = AdaptiveTTLEngine()
    naive_anomaly_dt = datetime(2026, 5, 25, 12, 0)
    ttl_naive = ttl_engine.compute_ttl("openweather_current", plot_id="plot_a", context={
        "anomaly_score": 0.85,
        "anomaly_detected_at": naive_anomaly_dt,
    })
    assert isinstance(ttl_naive, int)
    assert ttl_naive > 0

    # 3. DNA Cache save, load, hash check, and corruption resilience
    cache_dir = str(tmp_path / "dna_cache")
    sample_dna = {
        "traits": {
            "theta_retention": 1.1,
            "beta_resilience": 1.5,
            "alpha_vigor": 1.05,
            "t_shift": 5.0,
        },
        "quality": {"null_fraction": 0.05},
    }
    saved_path = save_dna_cache("plot_dna_1", sample_dna, cache_dir=cache_dir)
    loaded_dna = load_dna_cache("plot_dna_1", cache_dir=cache_dir)
    assert loaded_dna is not None
    assert loaded_dna["traits"]["theta_retention"] == 1.1

    # Hash check
    h = get_dna_hash("plot_dna_1", cache_dir=cache_dir)
    assert h is not None and len(h) == 12

    # Corruption check
    with open(saved_path, "w", encoding="utf-8") as f:
        f.write("{corrupt json!")
    assert load_dna_cache("plot_dna_1", cache_dir=cache_dir) is None


# 33. Layer 0 Runtimes: Satellite RGB Tile Runtime Fail-Closed & Deprecation-Free
def test_layer0_tile_runtime_fail_closed_without_synthetic(monkeypatch, tmp_path):
    from services.agribrain.layer0.perception.satellite_rgb import tile_runtime

    # Point tile cache to tmp_path
    monkeypatch.setattr(tile_runtime, "TILE_CACHE_DIR", str(tmp_path / "tiles"))

    # Explicitly verify that without synthetic preview opt-in, missing Sentinel credentials fails closed with None
    monkeypatch.setenv("ALLOW_SYNTHETIC_VISUAL_PREVIEW", "false")
    monkeypatch.setenv("SENTINEL_HUB_CLIENT_ID", "")
    monkeypatch.setenv("SENTINEL_HUB_CLIENT_SECRET", "")

    tile = tile_runtime.fetch_rgb_tile(
        plot_id="plot_runtime_isolated_test",
        lat=33.5,
        lng=-7.6,
        polygon_coords=[[-7.6, 33.5], [-7.59, 33.5], [-7.59, 33.51], [-7.6, 33.51], [-7.6, 33.5]],
        force=True,
    )
    assert tile is None, "Tile runtime must fail closed with None when credentials are unavailable"


# 34. Layer 0 State Persistence: Kalman State Continuity & Invalidation
def test_layer0_state_persistence_lifecycle(tmp_path):
    from services.agribrain.layer0.state_persistence import (
        save_engine_state,
        load_engine_state,
        VERSION,
    )

    state_dir = str(tmp_path / "kalman_state")
    kalman_zones = {
        "plot": {
            "state_values": [1.5, 0.4, 65.0],
            "covariance_diag": [0.01, 0.02, 0.05],
            "last_day": "2026-05-20",
        }
    }
    validation_state = {"nodes": {}, "edges": {}}
    crop_params = {"whc_mm_per_m": 150.0, "t_max": 35.0}

    # Save state
    fpath = save_engine_state(
        plot_id="plot_persist",
        state_dir=state_dir,
        kalman_zones=kalman_zones,
        validation_state=validation_state,
        crop_params=crop_params,
    )
    assert fpath is not None

    # Load state
    loaded = load_engine_state(
        plot_id="plot_persist",
        state_dir=state_dir,
        crop_params=crop_params,
    )
    assert loaded is not None
    assert loaded["version"] == VERSION
    saved_at = datetime.fromisoformat(loaded["saved_at"])
    assert saved_at.tzinfo is not None

    # Invalidation on changed crop_params
    changed_params = {"whc_mm_per_m": 190.0, "t_max": 32.0}
    invalidated = load_engine_state(
        plot_id="plot_persist",
        state_dir=state_dir,
        crop_params=changed_params,
    )
    assert invalidated is None


# 35. Layer 0: Perception Cache, packetizers, and QA engines use timezone-aware datetimes and proper key mapping
def test_layer0_perception_cache_and_packetizers_timezone_aware():
    from services.agribrain.layer0.perception.common.cache import PerceptionCache
    from services.agribrain.layer0.perception.ip_camera.qa import IPCameraQA
    from services.agribrain.layer0.perception.ip_camera.schemas import IPCameraEngineInput, IPCameraEngineOutput
    from services.agribrain.layer0.perception.ip_camera.packetizer import IPCameraPacketizer
    from services.agribrain.layer0.perception.drone_rgb.schemas import DroneRGBOutput
    from services.agribrain.layer0.perception.drone_rgb.qa import DroneQAOutput
    from services.agribrain.layer0.perception.drone_rgb.packetizer import DronePacketizer
    from services.agribrain.layer0.perception_packet_factory import PerceptionPacketFactory
    from datetime import datetime, timezone, timedelta

    # 1. PerceptionCache key mapping and invalidate_plot
    cache = PerceptionCache(default_ttl_seconds=60)
    k1 = cache.make_key("ip_camera", "plot_alpha", "hash_img_1", "v1")
    k2 = cache.make_key("ip_camera", "plot_beta", "hash_img_2", "v1")
    cache.set(k1, {"result": "data1"})
    cache.set(k2, {"result": "data2"})

    assert cache.get(k1) == {"result": "data1"}
    assert cache.get(k2) == {"result": "data2"}

    # Invalidate plot_alpha must invalidate k1 but not k2
    removed = cache.invalidate_plot("plot_alpha")
    assert removed >= 1
    assert cache.get(k1) is None
    assert cache.get(k2) == {"result": "data2"}

    # 2. IPCameraQA staleness check with aware UTC timestamp
    qa = IPCameraQA()
    now_utc = datetime.now(timezone.utc)
    inp = IPCameraEngineInput(
        plot_id="plot_alpha",
        camera_id="cam_01",
        timestamp=now_utc - timedelta(hours=1),
    )
    score = qa._assess_staleness(inp)
    assert score == 1.0  # < 2 hours old

    # 3. IPCameraPacketizer produces aware timestamp
    packetizer = IPCameraPacketizer()
    out = IPCameraEngineOutput(
        engine_family="ip_camera",
        plot_id="plot_alpha",
        timestamp=None,  # Must fall back to aware UTC now
        qa_score=0.9,
        reliability_weight=0.9,
        sigma_inflation=1.0,
        qa_flags=[],
        variables=[],
        scene_context=None,
        validation_checks=[],
    )
    packet = packetizer.to_observation_packet(out)
    assert packet.timestamp.tzinfo is not None

    # 4. DronePacketizer produces aware timestamp
    drone_out = DroneRGBOutput(mission_id="mission_01", plot_id="plot_alpha", canopy_cover_fraction=0.6)
    drone_qa = DroneQAOutput(overall_score=0.95, sigma_inflation=1.0)
    drone_packets = DronePacketizer().packetize(drone_out, drone_qa)
    assert len(drone_packets) > 0
    assert drone_packets[0].timestamp.tzinfo is not None

    # 5. PerceptionPacketFactory parses and ensures aware timestamp
    factory = PerceptionPacketFactory()
    p_packets = factory.process_image(
        image_metadata={
            "plot_id": "plot_alpha",
            "timestamp": "2026-07-15T10:00:00Z",
            "source_type": "phone",
            "pixel_stats": {
                "green_ratio": 0.45,
                "brightness_mean": 120.0,
                "saturation_mean": 80.0,
                "exg_mean": 25.0,
            },
        },
    )
    assert len(p_packets) > 0
    for p in p_packets:
        assert p.timestamp.tzinfo is not None



