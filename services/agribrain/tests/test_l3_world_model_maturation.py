"""
Layer 3.0 Water Intelligence World Model Maturation Tests
Validates Van Genuchten hydraulic potential, data assimilation, stress memory, adaptive solver selection, and L3->L4 boundary.
"""

from datetime import datetime, timezone
import pytest
import math

from layer3_water.contracts import (
    WaterPhysicsAuthority,
    HydrologyMode,
    SolverFidelity,
    SoilObservationVector,
    HydraulicStressMemoryState,
    AssimilationDiagnostic,
    WaterState,
    Layer3ToLayer4BoundaryReceipt,
    WaterStateFactory,
)
from layer3_water.soil import SoilProfileDatabase
from layer3_water.assimilation import WaterStateAssimilator
from layer3_water.solver import SolverSelector
from layer3_water.runner import WaterIntelligenceEngine


def test_van_genuchten_hydraulic_potential_and_conductivity():
    """Test that Van Genuchten matric potential and unsaturated conductivity are calculated and monotonic."""
    soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam", initial_saturation_fraction=0.60)
    
    assert len(soil.matric_potential_profile_mpa) == len(soil.layer_depths_cm)
    assert len(soil.unsaturated_conductivity_profile_cm_day) == len(soil.layer_depths_cm)
    
    # Matric potential must be negative (suction)
    for psi in soil.matric_potential_profile_mpa:
        assert psi < 0.0, f"Matric potential {psi} must be negative"
        assert psi >= -10.0, f"Matric potential {psi} within reasonable soil suction range"
        
    # Unsaturated hydraulic conductivity must be positive and less than or equal to Ksat
    for k_u, k_sat in zip(soil.unsaturated_conductivity_profile_cm_day, soil.hydraulic_conductivity_profile):
        assert 0.0 <= k_u <= k_sat + 1e-4


def test_water_state_assimilation_in_situ_probe():
    """Test 1D Optimal Interpolation Kalman update with in-situ TDR probe observations."""
    prior_soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam", initial_saturation_fraction=0.40)
    prior_theta = list(prior_soil.theta_profile)
    
    # In-situ probe indicates wetter top two layers
    obs_probe = [prior_theta[0] + 0.06, prior_theta[1] + 0.04, None, None, None]
    obs_vector = SoilObservationVector(
        timestamp=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        soil_probe_moisture_profile=obs_probe,
        observation_uncertainties={"soil_probe": 0.012},
    )
    
    posterior_soil, diag = WaterStateAssimilator.assimilate_observations(
        prior_soil=prior_soil,
        observations=obs_vector,
        background_uncertainty_sigma=0.035,
    )
    
    assert diag.assimilation_method == "OPTIMAL_INTERPOLATION_1D"
    assert diag.observations_assimilated_count == 2
    assert diag.innovation_vector_norm > 0.0
    assert diag.kalman_gain_norm > 0.0
    # Variance must decrease
    assert diag.posterior_profile_variance < diag.prior_profile_variance
    assert diag.variance_reduction_fraction > 0.0
    
    # Posterior state must shift toward observation
    assert posterior_soil.theta_profile[0] > prior_theta[0]
    assert posterior_soil.theta_profile[1] > prior_theta[1]


def test_water_state_assimilation_satellite_and_thermal():
    """Test assimilation of satellite surface moisture and thermal cooling differential."""
    prior_soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam", initial_saturation_fraction=0.70)
    prior_top = prior_soil.theta_profile[0]
    
    # Satellite says top layer is drier
    obs_vector = SoilObservationVector(
        timestamp=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        satellite_surface_moisture_m3_m3=prior_top - 0.05,
        observation_uncertainties={"satellite_smap": 0.030},
    )
    
    posterior_soil, diag = WaterStateAssimilator.assimilate_observations(
        prior_soil=prior_soil,
        observations=obs_vector,
    )
    
    assert diag.observations_assimilated_count == 1
    assert "SATELLITE_SMAP_SENTINEL1" in diag.assimilated_sensor_sources
    assert posterior_soil.theta_profile[0] < prior_top


def test_hydraulic_stress_memory_accumulation_and_recovery():
    """Test multi-day historical hydraulic stress memory tracking and recovery dynamics."""
    # Day 1: Moderate stress (Ks = 0.70, Tdef = 1.5mm, VPD = 2.0kPa)
    mem_d1 = HydraulicStressMemoryState.step_memory(
        prev_memory=None,
        current_ks=0.70,
        current_tdeficit_mm=1.5,
        current_vpd_kpa=2.0,
    )
    assert mem_d1.cumulative_transpiration_deficit_mm == 1.5
    assert mem_d1.consecutive_days_under_limitation == 1
    assert mem_d1.severe_limitation_days_count == 0
    assert mem_d1.integrated_hydraulic_stress_index == round(0.30 * 2.0, 3)
    assert mem_d1.drought_exposure_class == "ACUTE_MILD"
    
    # Day 2 to Day 5: Progressive severe drought (Ks = 0.40)
    curr_mem = mem_d1
    for day in range(2, 6):
        curr_mem = HydraulicStressMemoryState.step_memory(
            prev_memory=curr_mem,
            current_ks=0.40,
            current_tdeficit_mm=3.0,
            current_vpd_kpa=2.5,
        )
    assert curr_mem.consecutive_days_under_limitation == 5
    assert curr_mem.severe_limitation_days_count == 4
    assert curr_mem.cumulative_transpiration_deficit_mm == round(1.5 + 4 * 3.0, 2)
    assert curr_mem.drought_exposure_class == "CHRONIC_MODERATE"
    
    # Day 6: Full re-watering / irrigation (Ks = 1.0, Tdef = 0.0)
    mem_recovery = HydraulicStressMemoryState.step_memory(
        prev_memory=curr_mem,
        current_ks=1.00,
        current_tdeficit_mm=0.0,
        current_vpd_kpa=1.2,
    )
    assert mem_recovery.consecutive_days_under_limitation == 0
    assert mem_recovery.water_stress_recovery_rate == round(1.0 - 0.40, 3)
    assert mem_recovery.cumulative_transpiration_deficit_mm == curr_mem.cumulative_transpiration_deficit_mm


def test_adaptive_solver_selector_reports_only_the_executed_solver():
    """High-fidelity eligibility cannot create false Richards provenance."""
    # Case 1: Standard field, no sensors -> Empirical bucket
    d1 = SolverSelector.select_solver(
        crop_economic_priority_factor=1.0,
        soil_uncertainty_sigma=0.04,
    )
    assert d1.hydrology_mode == HydrologyMode.FAO56_LAYERED_BUCKET
    assert d1.solver_fidelity == SolverFidelity.EMPIRICAL_BUCKET
    
    # Case 2: probes make Richards desirable, but the uninstalled solver must
    # degrade truthfully to the implemented bucket runner.
    obs_probe = SoilObservationVector(
        timestamp=datetime.now(timezone.utc),
        soil_probe_moisture_profile=[0.25, 0.26, 0.27, 0.28, 0.28],
    )
    d2 = SolverSelector.select_solver(
        crop_economic_priority_factor=1.0,
        observations=obs_probe,
    )
    assert d2.hydrology_mode == HydrologyMode.FAO56_LAYERED_BUCKET
    assert d2.solver_fidelity == SolverFidelity.EMPIRICAL_BUCKET
    assert "no validated Richards runner" in d2.selection_rationale
    
    # Case 3: policy eligibility still cannot overstate implementation fidelity.
    d3 = SolverSelector.select_solver(
        crop_economic_priority_factor=2.0,
        soil_uncertainty_sigma=0.020,
    )
    assert d3.hydrology_mode == HydrologyMode.FAO56_LAYERED_BUCKET
    assert d3.solver_fidelity == SolverFidelity.EMPIRICAL_BUCKET


def test_full_pipeline_with_assimilation_and_memory_to_layer4():
    """Execute complete Layer 3 World Model pipeline and verify rich L3->L4 receipt."""
    obs_vector = SoilObservationVector(
        timestamp=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        soil_probe_moisture_profile=[0.24, 0.25, 0.26, 0.27, 0.27],
        observation_uncertainties={"soil_probe": 0.010},
    )
    prev_mem = HydraulicStressMemoryState(
        cumulative_transpiration_deficit_mm=8.5,
        consecutive_days_under_limitation=2,
        severe_limitation_days_count=0,
        integrated_hydraulic_stress_index=3.2,
        historical_min_ks=0.75,
    )
    
    water_state, receipt_l2 = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot_orchard_alpha",
        timestamp=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        soil_observations=obs_vector,
        previous_hydraulic_memory=prev_mem,
        soil_type="clay_loam",
        weather_observations={
            "t_max_c": 33.0,
            "t_min_c": 19.0,
            "precipitation_mm": 0.0,
            "wind_speed_2m_m_s": 2.4,
            "rh_min_pct": 32.0,
            "rh_max_pct": 78.0,
            "net_radiation_mj_m2": 21.0,
        },
    )
    
    assert water_state.physics_authority == WaterPhysicsAuthority.OBSERVED
    assert water_state.hydrology_mode == HydrologyMode.FAO56_LAYERED_BUCKET
    assert water_state.solver_fidelity == SolverFidelity.EMPIRICAL_BUCKET
    assert water_state.assimilation_diagnostic is not None
    assert water_state.assimilation_diagnostic.observations_assimilated_count > 0
    assert len(water_state.soil_water.matric_potential_profile_mpa) == 5
    
    # Verify L3 -> L4 Boundary Receipt
    l4_receipt = water_state.to_layer4_boundary_receipt()
    assert isinstance(l4_receipt, Layer3ToLayer4BoundaryReceipt)
    assert l4_receipt.cumulative_transpiration_deficit_mm >= 8.5
    assert l4_receipt.assimilation_status == "OPTIMAL_INTERPOLATION_1D"
    assert l4_receipt.physics_authority == "OBSERVED"
    assert l4_receipt.solver_fidelity == "EMPIRICAL_BUCKET"
    assert l4_receipt.water_confidence_score > 0.85
