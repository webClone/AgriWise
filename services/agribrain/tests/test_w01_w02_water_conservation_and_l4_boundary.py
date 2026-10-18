"""
Tests for W01 (Physical soil water mass conservation under impedance profile)
and W02 (Typed L3 -> L4 root boundary receipt and consumption).

Verifies:
1. Heterogeneous conductivity impedance profile ([100, 0.01, 0.01] cm/day) closes mass balance.
2. Dry and permeable controls close exactly.
3. Full pipeline execution with ET and impedance profile maintains physical conservation.
4. Partial-layer and extended root-depth support calculation.
5. Canonical 137.57 mm supported storage is preserved through L4 without 83.30 mm substitution.
6. Depth-weighted FC (0.295), WP (0.0966667), Sat (0.440) are transferred and consumed in L4 SWB.
7. Downstream L4 fails closed on nonconserved hydrological transitions.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
import pytest

from layer3_water.contracts import (
    Layer3ToLayer4BoundaryReceipt,
    IntervalFluxReceipt,
    WaterFluxState,
    PotentialWaterFlux,
    ActualWaterFlux,
)
from layer3_water.contracts.state_factory import WaterStateFactory
from layer3_water.soil.layered_water_balance import LayeredWaterBalanceEngine
from layer3_water.runner import WaterIntelligenceEngine
from layer4_nutrients.runner import run_layer4_standalone


# ==============================================================================
# W01: Physical Soil Water Mass Conservation Under Impedance Profile
# ==============================================================================

def test_w01_impedance_profile_conserves_mass_without_water_deletion():
    """Verify heterogeneous conductivity profile [100, 0.01, 0.01] cm/day closes mass balance."""
    # Profile: 0-10-30-60 cm, theta/FC = 0.30, Sat = 0.45, Ks = [100, 0.01, 0.01] cm/day
    s = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=[10.0, 30.0, 60.0],
        theta_profile=[0.30, 0.30, 0.30],
        field_capacity_profile=[0.30, 0.30, 0.30],
        wilting_point_profile=[0.15, 0.15, 0.15],
        saturation_profile=[0.45, 0.45, 0.45],
        residual_profile=[0.05, 0.05, 0.05],
        hydraulic_conductivity_profile=[100.0, 0.01, 0.01],
        van_genuchten_alpha=[0.03, 0.03, 0.03],
        van_genuchten_n=[1.5, 1.5, 1.5],
    )
    rz = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.6,
        layer_depths_cm=s.layer_depths_cm,
        theta_profile=s.theta_profile,
        field_capacity_profile=s.field_capacity_profile,
        wilting_point_profile=s.wilting_point_profile,
        saturation_profile=s.saturation_profile,
    )

    # 100 mm rain, 0 irrigation, 0 extraction
    result = LayeredWaterBalanceEngine.step_water_balance(
        prev_soil=s,
        root_zone=rz,
        precipitation_mm=100.0,
        irrigation_mm=0.0,
        actual_transpiration_mm=0.0,
        actual_soil_evaporation_mm=0.0,
    )

    receipt = result.receipt
    assert receipt is not None
    assert receipt.initial_storage_mm == 180.0
    # Layer 0 saturates at 45 mm, Layer 1 saturates at 90 mm, Layer 2 remains at FC 90 mm
    assert receipt.final_storage_mm == 225.0
    assert receipt.storage_change_mm == 45.0
    assert receipt.gross_infiltration_mm == 100.0
    # Return flow from perched saturation overflow: 54.9 mm
    assert receipt.return_flow_runoff_mm == 54.9
    assert receipt.surface_runoff_mm == 54.9
    assert receipt.actual_infiltration_mm == 45.1
    assert receipt.deep_drainage_mm == 0.1
    # Physical conservation: closure error <= 0.05 mm
    assert receipt.water_closure_error_mm <= 0.05
    assert receipt.mass_conserved is True


def test_w01_dry_and_permeable_controls_close_exactly():
    """Verify dry and permeable controls close with zero unreconciled water loss."""
    # Dry Control: 0 rain, 0 irrigation, 0 extraction
    s_dry = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=[10.0, 30.0, 60.0],
        theta_profile=[0.30, 0.30, 0.30],
        field_capacity_profile=[0.30, 0.30, 0.30],
        wilting_point_profile=[0.15, 0.15, 0.15],
        saturation_profile=[0.45, 0.45, 0.45],
        residual_profile=[0.05, 0.05, 0.05],
        hydraulic_conductivity_profile=[100.0, 0.01, 0.01],
        van_genuchten_alpha=[0.03, 0.03, 0.03],
        van_genuchten_n=[1.5, 1.5, 1.5],
    )
    rz_dry = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.6,
        layer_depths_cm=s_dry.layer_depths_cm,
        theta_profile=s_dry.theta_profile,
        field_capacity_profile=s_dry.field_capacity_profile,
        wilting_point_profile=s_dry.wilting_point_profile,
    )
    res_dry = LayeredWaterBalanceEngine.step_water_balance(
        prev_soil=s_dry,
        root_zone=rz_dry,
        precipitation_mm=0.0,
        irrigation_mm=0.0,
        actual_transpiration_mm=0.0,
        actual_soil_evaporation_mm=0.0,
    )
    assert res_dry.receipt.water_closure_error_mm <= 0.01
    assert res_dry.receipt.mass_conserved is True
    assert res_dry.receipt.storage_change_mm == 0.0

    # Permeable Control: 100 mm rain, highly permeable [100, 100, 100] cm/day
    s_perm = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=[10.0, 30.0, 60.0],
        theta_profile=[0.30, 0.30, 0.30],
        field_capacity_profile=[0.30, 0.30, 0.30],
        wilting_point_profile=[0.15, 0.15, 0.15],
        saturation_profile=[0.45, 0.45, 0.45],
        residual_profile=[0.05, 0.05, 0.05],
        hydraulic_conductivity_profile=[100.0, 100.0, 100.0],
        van_genuchten_alpha=[0.03, 0.03, 0.03],
        van_genuchten_n=[1.5, 1.5, 1.5],
    )
    rz_perm = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.6,
        layer_depths_cm=s_perm.layer_depths_cm,
        theta_profile=s_perm.theta_profile,
        field_capacity_profile=s_perm.field_capacity_profile,
        wilting_point_profile=s_perm.wilting_point_profile,
    )
    res_perm = LayeredWaterBalanceEngine.step_water_balance(
        prev_soil=s_perm,
        root_zone=rz_perm,
        precipitation_mm=100.0,
        irrigation_mm=0.0,
        actual_transpiration_mm=0.0,
        actual_soil_evaporation_mm=0.0,
    )
    assert res_perm.receipt.water_closure_error_mm <= 0.01
    assert res_perm.receipt.mass_conserved is True
    # In permeable control, water drains through profile to deep drainage
    assert res_perm.receipt.deep_drainage_mm == 100.0


def test_w01_full_water_intelligence_pipeline_impedance_conserves_mass():
    """Verify complete execute_pipeline with ET and impedance profile maintains closure <= 0.05 mm."""
    s = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=[10.0, 30.0, 60.0],
        theta_profile=[0.30, 0.30, 0.30],
        field_capacity_profile=[0.30, 0.30, 0.30],
        wilting_point_profile=[0.15, 0.15, 0.15],
        saturation_profile=[0.45, 0.45, 0.45],
        residual_profile=[0.05, 0.05, 0.05],
        hydraulic_conductivity_profile=[100.0, 0.01, 0.01],
        van_genuchten_alpha=[0.03, 0.03, 0.03],
        van_genuchten_n=[1.5, 1.5, 1.5],
    )
    w_obs = {
        "t_max_c": 30.0,
        "t_min_c": 18.0,
        "precipitation_mm": 100.0,
        "wind_speed_2m_m_s": 2.0,
        "rh_min_pct": 40.0,
        "rh_max_pct": 80.0,
        "net_radiation_mj_m2": 20.0,
    }
    water_state, _ = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot_impedance_test",
        timestamp=datetime.now(timezone.utc),
        soil_profile_state=s,
        weather_observations=w_obs,
    )
    assert water_state.mass_conserved is True
    assert water_state.mass_balance_error_mm <= 0.05
    assert water_state.transition_receipt is not None
    assert water_state.transition_receipt.water_closure_error_mm <= 0.05


def test_w01_partial_root_depth_support_integration():
    """Verify compute_root_zone_support handles partial-layer overlap and unknown deeper support."""
    s = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=[10.0, 30.0, 60.0],  # thicknesses: 100 mm, 200 mm, 300 mm
        theta_profile=[0.20, 0.25, 0.30],
        field_capacity_profile=[0.28, 0.30, 0.32],
        wilting_point_profile=[0.10, 0.12, 0.14],
        saturation_profile=[0.42, 0.44, 0.46],
        residual_profile=[0.05, 0.05, 0.05],
        hydraulic_conductivity_profile=[25.0, 15.0, 10.0],
        van_genuchten_alpha=[0.03, 0.03, 0.03],
        van_genuchten_n=[1.5, 1.5, 1.5],
    )

    # Partial layer overlap: root depth = 25 cm
    # Layer 0 (0-10 cm): full 10 cm (100 mm)
    # Layer 1 (10-30 cm): partial 15 cm (150 mm)
    # Total supported depth = 25 cm (250 mm)
    # Expected storage = 0.20 * 100 + 0.25 * 150 = 20.0 + 37.5 = 57.5 mm
    # Expected FC = (0.28 * 100 + 0.30 * 150) / 250 = (28 + 45) / 250 = 73 / 250 = 0.292
    # Expected WP = (0.10 * 100 + 0.12 * 150) / 250 = (10 + 18) / 250 = 28 / 250 = 0.112
    # Expected Sat = (0.42 * 100 + 0.44 * 150) / 250 = (42 + 66) / 250 = 108 / 250 = 0.432
    s_root, fc_root, wp_root, sat_root, supp_depth_cm = s.compute_root_zone_support(25.0)

    assert s_root == pytest.approx(57.5, abs=0.01)
    assert fc_root == pytest.approx(0.292, abs=0.0001)
    assert wp_root == pytest.approx(0.112, abs=0.0001)
    assert sat_root == pytest.approx(0.432, abs=0.0001)
    assert supp_depth_cm == 25.0

    # Extended root depth exceeding profile: root depth = 100 cm with 60 cm soil profile
    # Supports exactly the 60 cm profile
    s_root_deep, _, _, _, supp_depth_deep = s.compute_root_zone_support(100.0)
    assert supp_depth_deep == 60.0
    assert s_root_deep == pytest.approx(0.20 * 100 + 0.25 * 200 + 0.30 * 300, abs=0.01)


# ==============================================================================
# W02: Typed L3 -> L4 Root Boundary Receipt & Consumption
# ==============================================================================

def test_w02_l4_consumes_canonical_storage_and_hydraulic_aggregates():
    """Verify L4 receives canonical 137.57 mm storage and 0.295/0.0966667/0.440 retention parameters."""
    # Profile configured to match canonical audit test:
    # 0-10-30-60 cm with weighted FC 0.295, WP 0.0966667, Sat 0.440, storage 137.57 mm
    s = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=[10.0, 30.0, 60.0],
        theta_profile=[0.20, 0.22, 0.2452333],
        field_capacity_profile=[0.25, 0.28, 0.32],
        wilting_point_profile=[0.08, 0.09, 0.1066667],
        saturation_profile=[0.41, 0.43, 0.4566667],
        residual_profile=[0.05, 0.05, 0.05],
        hydraulic_conductivity_profile=[15.0, 10.0, 5.0],
        van_genuchten_alpha=[0.03, 0.03, 0.03],
        van_genuchten_n=[1.5, 1.5, 1.5],
    )
    rz = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.6,
        layer_depths_cm=s.layer_depths_cm,
        theta_profile=s.theta_profile,
        field_capacity_profile=s.field_capacity_profile,
        wilting_point_profile=s.wilting_point_profile,
        saturation_profile=s.saturation_profile,
    )
    fx = WaterFluxState(
        potential=PotentialWaterFlux(et0_mm=5.0, kcb=0.8, ke=0.2),
        actual=ActualWaterFlux(ks=1.0, precipitation_mm=0.0, irrigation_mm=0.0, deep_drainage_mm=0.0, runoff_mm=0.0),
    )
    ws = WaterStateFactory.create_water_state(
        plot_id="plot_w02_canonical",
        timestamp=datetime.now(timezone.utc),
        soil_water=s,
        root_zone=rz,
        fluxes=fx,
    )

    # Verify L3 boundary receipt properties before passing to L4
    receipt = ws.to_layer4_boundary_receipt()
    assert isinstance(receipt, Layer3ToLayer4BoundaryReceipt)
    assert receipt.root_zone_storage_mm == pytest.approx(137.57, abs=0.05)
    assert receipt.theta_fc_root == pytest.approx(0.295, abs=0.001)
    assert receipt.theta_wp_root == pytest.approx(0.0966667, abs=0.001)
    assert receipt.theta_sat_root == pytest.approx(0.440, abs=0.001)
    assert receipt.supported_root_depth_cm == 60.0
    assert receipt.mass_conserved is True

    # Execute complete Layer 4 standalone runner
    l3_decision = SimpleNamespace(canonical_water_state=ws)
    weather = [{"date": "2026-08-20", "temp_avg_c": 22.0, "rain_mm": 0.0, "et0": 5.0, "t_max": 28.0, "t_min": 16.0}]
    soil_props = {"clay_pct": 20.0, "organic_matter_pct": 2.0, "ph": 6.8}

    out = run_layer4_standalone(
        plot_id="plot_w02_canonical",
        crop_type="almond",
        l3_decision=l3_decision,
        soil_props=soil_props,
        daily_weather=weather,
    )

    # Verification: generic 83.30 mm substitution has vanished
    swb = out.swb_output
    assert swb.soil_moisture_mm == pytest.approx(137.57, abs=0.05)
    assert swb.soil_moisture_mm != pytest.approx(83.30, abs=0.5)

    # Verification: generic 0.30/0.15/0.45 has vanished
    assert swb.theta_fc == pytest.approx(0.295, abs=0.001)
    assert swb.theta_wp == pytest.approx(0.0966667, abs=0.001)
    assert swb.theta_sat == pytest.approx(0.440, abs=0.001)
    assert swb.taw_mm == pytest.approx(119.0, abs=0.1)
    assert swb.supported_root_depth_cm == 60.0
    assert swb.status == "OK"
    assert swb.is_degraded is False


def test_w02_l4_fails_closed_on_nonconserved_water_transition():
    """Verify that failed physical water conservation causes L4 to fail closed, block prescriptions, and flag degradation."""
    s = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=[10.0, 30.0, 60.0],
        theta_profile=[0.30, 0.30, 0.30],
        field_capacity_profile=[0.30, 0.30, 0.30],
        wilting_point_profile=[0.15, 0.15, 0.15],
        saturation_profile=[0.45, 0.45, 0.45],
        residual_profile=[0.05, 0.05, 0.05],
        hydraulic_conductivity_profile=[25.0, 15.0, 10.0],
        van_genuchten_alpha=[0.03, 0.03, 0.03],
        van_genuchten_n=[1.5, 1.5, 1.5],
    )
    rz = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.6,
        layer_depths_cm=s.layer_depths_cm,
        theta_profile=s.theta_profile,
        field_capacity_profile=s.field_capacity_profile,
        wilting_point_profile=s.wilting_point_profile,
    )
    fx = WaterFluxState(
        potential=PotentialWaterFlux(et0_mm=5.0, kcb=0.8, ke=0.2),
        actual=ActualWaterFlux(ks=1.0, precipitation_mm=0.0, irrigation_mm=0.0, deep_drainage_mm=0.0, runoff_mm=0.0),
    )
    # Simulate failed conservation transition (e.g. 25 mm unreconciled error)
    ws_failed = WaterStateFactory.create_water_state(
        plot_id="plot_w02_fail",
        timestamp=datetime.now(timezone.utc),
        soil_water=s,
        root_zone=rz,
        fluxes=fx,
        mass_balance_error_mm=25.0,
    )
    assert ws_failed.mass_conserved is False

    l3_decision = SimpleNamespace(canonical_water_state=ws_failed)
    weather = [{"date": "2026-08-20", "temp_avg_c": 22.0, "rain_mm": 0.0, "et0": 5.0, "t_max": 28.0, "t_min": 16.0}]
    soil_props = {
        "nitrogen_ppm": 5.0,
        "phosphorus_ppm": 5.0,
        "potassium_ppm": 50.0,
        "clay_pct": 20.0,
        "organic_matter_pct": 2.0,
        "ph": 6.8,
    }

    out = run_layer4_standalone(
        plot_id="plot_w02_fail",
        crop_type="almond",
        l3_decision=l3_decision,
        soil_props=soil_props,
        daily_weather=weather,
    )

    # 1. SWB output flags failure
    swb = out.swb_output
    assert swb.status == "DEGRADED_NONCONSERVED_WATER"
    assert swb.is_degraded is True
    assert swb.mass_conserved is False
    assert swb.uncertainty_multiplier == 2.0
    assert swb.water_closure_error_mm == 25.0

    # 2. Nutrient states confidence capped
    for state in out.nutrient_states.values():
        assert state.confidence <= 0.20
        assert "unclosed hydrological mass balance" in state.notes

    # 3. Prescriptions blocked from execution
    for rx in out.prescriptions:
        assert rx.is_allowed is False
        assert "nonconserved_water_transition" in rx.blocked_reason

    # 4. Data health score and quality metrics reflect unclosed boundary
    assert out.data_health.overall <= 0.20
    assert out.data_health.status == "degraded"
    assert "PHYSICALLY_CONSERVED_WATER_BOUNDARY" in out.quality_metrics.missing_drivers
    assert any(p["driver"] == "hydrology_mass_balance" for p in out.quality_metrics.penalties_applied)
