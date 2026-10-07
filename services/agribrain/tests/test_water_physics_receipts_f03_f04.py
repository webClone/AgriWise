"""
Unit and integration test suite for F03 and F04:
- F04: Strict validation of soil geometry (strictly increasing positive finite depths)
  and hydraulic parameter vectors (retention ordering, conductivity, van Genuchten alpha/n).
- F03: Transition receipt containing bounded actual fluxes, publication of actually integrated fluxes
  (preventing assimilation from retroactively rewriting interval water use), explicit analysis increment
  receipts for data assimilation, and mass closure calculated from serialized state and receipts.
"""

import math
from datetime import datetime, timezone
import pytest

from layer3_water.contracts import (
    WaterStateFactory,
    SoilWaterState,
    PotentialWaterFlux,
    ActualWaterFlux,
    WaterFluxState,
    RootZoneWaterState,
    IntervalFluxReceipt,
    AnalysisIncrementReceipt,
    SoilObservationVector,
    WaterPhysicsAuthority,
)
from layer3_water.soil import (
    SoilProfileDatabase,
    LayeredWaterBalanceEngine,
)
from layer3_water.soil.layered_water_balance import StepWaterBalanceResult
from layer3_water.assimilation import WaterStateAssimilator
from layer3_water.runner import WaterIntelligenceEngine


# =========================================================================
# F04: Soil Geometry and Hydraulic Parameter Vector Validation Tests
# =========================================================================

def test_f04_nonmonotonic_or_invalid_depths_rejected():
    """Ensure nonmonotonic, repeated, zero, negative, or nonfinite layer depths fail closed."""
    invalid_depth_cases = [
        [30.0, 10.0],          # Nonmonotonic decreasing
        [10.0, 10.0],          # Repeated
        [0.0, 10.0],           # Zero depth
        [-5.0, 10.0],          # Negative depth
        [float("nan"), 10.0],  # NaN
        [float("inf"), 10.0],  # Inf
        [],                    # Empty
    ]

    for depths in invalid_depth_cases:
        with pytest.raises(ValueError):
            WaterStateFactory.create_soil_water_state(
                layer_depths_cm=depths,
                theta_profile=[0.2] * len(depths),
                field_capacity_profile=[0.3] * len(depths),
                wilting_point_profile=[0.1] * len(depths),
                saturation_profile=[0.45] * len(depths),
                residual_profile=[0.05] * len(depths),
            )


def test_f04_vector_length_mismatch_rejected():
    """Ensure vector lengths must strictly match layer count."""
    depths = [10.0, 30.0, 60.0]  # 3 layers
    with pytest.raises(ValueError, match="length must match layer count"):
        WaterStateFactory.create_soil_water_state(
            layer_depths_cm=depths,
            theta_profile=[0.2, 0.2],  # only 2 layers
            field_capacity_profile=[0.3, 0.3, 0.3],
            wilting_point_profile=[0.1, 0.1, 0.1],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.05, 0.05, 0.05],
        )

    with pytest.raises(ValueError, match="hydraulic_conductivity_profile length"):
        WaterStateFactory.create_soil_water_state(
            layer_depths_cm=depths,
            theta_profile=[0.2, 0.2, 0.2],
            field_capacity_profile=[0.3, 0.3, 0.3],
            wilting_point_profile=[0.1, 0.1, 0.1],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.05, 0.05, 0.05],
            hydraulic_conductivity_profile=[25.0, 25.0],  # only 2 layers
        )


def test_f04_negative_or_zero_conductivity_rejected():
    """Reject non-positive or non-finite hydraulic conductivity."""
    depths = [10.0, 30.0]
    for ks_val in [-1.0, 0.0, float("nan"), float("inf"), -float("inf")]:
        with pytest.raises(ValueError, match="hydraulic conductivity"):
            WaterStateFactory.create_soil_water_state(
                layer_depths_cm=depths,
                theta_profile=[0.2, 0.2],
                field_capacity_profile=[0.3, 0.3],
                wilting_point_profile=[0.1, 0.1],
                saturation_profile=[0.45, 0.45],
                residual_profile=[0.05, 0.05],
                hydraulic_conductivity_profile=[ks_val, 25.0],
            )


def test_f04_invalid_van_genuchten_parameters_rejected():
    """Reject alpha <= 0 and n <= 1.0 (which would yield m <= 0 or division by zero)."""
    depths = [10.0, 30.0]
    # alpha <= 0
    with pytest.raises(ValueError, match="van Genuchten alpha"):
        WaterStateFactory.create_soil_water_state(
            layer_depths_cm=depths,
            theta_profile=[0.2, 0.2],
            field_capacity_profile=[0.3, 0.3],
            wilting_point_profile=[0.1, 0.1],
            saturation_profile=[0.45, 0.45],
            residual_profile=[0.05, 0.05],
            van_genuchten_alpha=[0.0, 0.03],
        )

    # n <= 1.0
    for invalid_n in [1.0, 0.8, -1.5, float("nan")]:
        with pytest.raises(ValueError, match="van Genuchten n"):
            WaterStateFactory.create_soil_water_state(
                layer_depths_cm=depths,
                theta_profile=[0.2, 0.2],
                field_capacity_profile=[0.3, 0.3],
                wilting_point_profile=[0.1, 0.1],
                saturation_profile=[0.45, 0.45],
                residual_profile=[0.05, 0.05],
                van_genuchten_n=[invalid_n, 1.5],
            )


def test_f04_degenerate_retention_intervals_rejected():
    """Reject degenerate saturation/residual intervals where theta_s <= theta_r + 1e-4."""
    depths = [10.0, 30.0]
    with pytest.raises(ValueError, match="degenerate saturation/residual interval"):
        WaterStateFactory.create_soil_water_state(
            layer_depths_cm=depths,
            theta_profile=[0.10, 0.20],
            field_capacity_profile=[0.10, 0.30],
            wilting_point_profile=[0.10, 0.10],
            saturation_profile=[0.10, 0.45],  # theta_s == theta_r
            residual_profile=[0.10, 0.05],
        )


def test_f04_parameter_provenance_recorded_and_propagated():
    """Verify parameter provenance is recorded and propagated through water balance and assimilation."""
    depths = [10.0, 30.0]
    soil = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=depths,
        theta_profile=[0.2, 0.2],
        field_capacity_profile=[0.3, 0.3],
        wilting_point_profile=[0.1, 0.1],
        saturation_profile=[0.45, 0.45],
        residual_profile=[0.05, 0.05],
        parameter_provenance="IN_SITU_CALIBRATED",
    )
    assert soil.parameter_provenance == "IN_SITU_CALIBRATED"

    rz = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.3,
        layer_depths_cm=depths,
        theta_profile=[0.2, 0.2],
        field_capacity_profile=[0.3, 0.3],
        wilting_point_profile=[0.1, 0.1],
    )

    # Propagates through LayeredWaterBalanceEngine
    result = LayeredWaterBalanceEngine.step_water_balance(
        prev_soil=soil,
        root_zone=rz,
        precipitation_mm=5.0,
        irrigation_mm=0.0,
        actual_transpiration_mm=1.0,
        actual_soil_evaporation_mm=0.5,
    )
    assert result.updated_soil.parameter_provenance == "IN_SITU_CALIBRATED"

    # Propagates through WaterStateAssimilator
    obs = SoilObservationVector(
        timestamp=datetime.now(timezone.utc),
        soil_probe_moisture_profile=[0.25, 0.25],
    )
    post_soil, diag = WaterStateAssimilator.assimilate_observations(prior_soil=soil, observations=obs)
    assert post_soil.parameter_provenance == "IN_SITU_CALIBRATED"


def test_f04_root_zone_validation_enforces_monotonicity_and_domain():
    """Verify RootZoneWaterState builder rejects invalid root depths and nonmonotonic layer depths."""
    with pytest.raises(ValueError, match="root_depth_m"):
        WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.0,
            layer_depths_cm=[10.0, 30.0],
            theta_profile=[0.2, 0.2],
            field_capacity_profile=[0.3, 0.3],
            wilting_point_profile=[0.1, 0.1],
        )

    with pytest.raises(ValueError, match="strictly monotonically increasing"):
        WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.5,
            layer_depths_cm=[30.0, 10.0],
            theta_profile=[0.2, 0.2],
            field_capacity_profile=[0.3, 0.3],
            wilting_point_profile=[0.1, 0.1],
        )


# =========================================================================
# F03: Transition Receipt & Realized vs Posterior Flux Separation Tests
# =========================================================================

def test_f03_step_water_balance_returns_receipt_and_conserves_mass():
    """Verify StepWaterBalanceResult provides IntervalFluxReceipt and enforces physical closure."""
    soil = SoilProfileDatabase.get_canonical_soil_profile("loam")
    rz = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.8,
        layer_depths_cm=soil.layer_depths_cm,
        theta_profile=soil.theta_profile,
        field_capacity_profile=soil.field_capacity_profile,
        wilting_point_profile=soil.wilting_point_profile,
    )

    result = LayeredWaterBalanceEngine.step_water_balance(
        prev_soil=soil,
        root_zone=rz,
        precipitation_mm=12.0,
        irrigation_mm=5.0,
        actual_transpiration_mm=3.5,
        actual_soil_evaporation_mm=1.2,
        capillary_rise_mm=0.0,
        days_since_wetting=0,
    )

    # Backward compatibility: unpacks as 5-tuple
    soil_next, actual_infil, runoff, deep_drainage, mass_err = result
    assert isinstance(result, tuple)
    assert len(result) == 5

    # Rich receipt access
    receipt = result.receipt
    assert isinstance(receipt, IntervalFluxReceipt)
    assert receipt.initial_storage_mm == soil.total_profile_water_mm
    assert receipt.final_storage_mm == soil_next.total_profile_water_mm
    assert receipt.actual_infiltration_mm == actual_infil
    assert receipt.surface_runoff_mm == runoff
    assert receipt.deep_drainage_mm == deep_drainage
    assert receipt.mass_conserved is True
    assert receipt.water_closure_error_mm <= 0.05

    # Check physical mass conservation equation:
    # delta_S = (Infiltration + Capillary) - (Transpiration + Evaporation + Drainage)
    expected_delta_s = round(
        (receipt.actual_infiltration_mm + receipt.capillary_rise_mm)
        - (receipt.actual_transpiration_mm + receipt.actual_soil_evaporation_mm + receipt.deep_drainage_mm),
        4,
    )
    assert abs(receipt.storage_change_mm - expected_delta_s) <= 0.05


def test_f03_pipeline_publishes_integrated_fluxes_and_separates_posterior_demand():
    """Verify that assimilation does not retroactively rewrite the fluxes used in the interval.
    
    In the defect scenario:
    - Interval ran with water stress (Ks < 1.0), so prior integrated transpiration was small (e.g. 1.32 mm).
    - An in-situ probe measurement arrived at the end of the day indicating high moisture (posterior Ks = 1.0).
    - Bug previously: published fluxes were recomputed with posterior Ks = 1.0, reporting 8.52 mm actual transpiration!
    - Repair: published fluxes must strictly match the transition receipt (1.32 mm), while 8.52 mm is exposed
      only as next-interval posterior demand.
    """
    # Start with dry soil (near wilting point)
    dry_soil = SoilProfileDatabase.get_canonical_soil_profile("loam", initial_saturation_fraction=0.05)
    
    # In-situ probe reports wet soil (0.35 across all 5 layers)
    wet_probe = SoilObservationVector(
        timestamp=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        soil_probe_moisture_profile=[0.35, 0.35, 0.35, 0.35, 0.35],
        observation_uncertainties={"soil_probe": 0.010},
    )

    weather = {
        "t_max_c": 32.0,
        "t_min_c": 18.0,
        "precipitation_mm": 0.0,
        "wind_speed_2m_m_s": 2.0,
        "rh_min_pct": 30.0,
        "rh_max_pct": 75.0,
        "net_radiation_mj_m2": 20.0,
    }

    water_state, feedback = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot_f03_test",
        timestamp=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        soil_profile_state=dry_soil,
        soil_observations=wet_probe,
        weather_observations=weather,
    )

    # 1. Transition receipt must exist and record what was integrated
    assert water_state.transition_receipt is not None
    integrated_tact = water_state.transition_receipt.actual_transpiration_mm
    
    # 2. Published fluxes MUST match the transition receipt exactly
    assert water_state.fluxes.actual.actual_transpiration_mm == round(integrated_tact, 2)
    assert water_state.fluxes.actual.actual_soil_evaporation_mm == round(water_state.transition_receipt.actual_soil_evaporation_mm, 2)

    # 3. Posterior root zone now reflects the wet probe (Ks is high)
    assert water_state.root_zone.stress_factor_ks > 0.80

    # 4. Posterior demand is exposed separately
    assert water_state.posterior_demand is not None
    assert water_state.posterior_demand.tpot_mm > 0.0

    # 5. Analysis increment receipt explicitly accounts for the water gained through assimilation
    assert water_state.analysis_receipt is not None
    analysis = water_state.analysis_receipt
    assert analysis.pre_assimilation_storage_mm == water_state.transition_receipt.final_storage_mm
    assert analysis.post_assimilation_storage_mm == water_state.soil_water.total_profile_water_mm
    assert analysis.storage_increment_mm > 0.0  # Probe injected water
    assert analysis.variance_reduction_fraction > 0.0
    assert "IN_SITU_PROBE_TDR" in analysis.assimilated_sensor_sources

    # 6. Mass balance closure reported on water_state comes from the serialized state and receipt
    assert water_state.mass_balance_error_mm == water_state.transition_receipt.water_closure_error_mm
    assert water_state.mass_balance_error_mm <= 0.05
