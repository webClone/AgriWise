"""
Layer 3 -> Layer 4 Boundary Contract & Information Barrier Test
Verifies the clean causal boundary, schema versioning, and encapsulation between Water Intelligence and Bio Intelligence.
"""

from datetime import datetime, timezone
import pytest

from layer2_contracts.state_contracts import (
    VegetationState,
    CropKnowledgeAuthority,
    StressMagnitudeState,
    PhysicalSourceType,
    UncertaintyBudget,
)
from layer3_water.contracts import (
    WaterState,
    WaterPhysicsAuthority,
    HydrologyMode,
    SolverFidelity,
    Layer3ToLayer4BoundaryReceipt,
    Layer3HydrologicalConstraintReceipt,
)
from layer3_water.runner import WaterIntelligenceEngine


def test_l3_schema_versioning_and_boundary_receipt_generation():
    """Verify WaterState schema versioning (3.0) and to_layer4_boundary_receipt extraction."""
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    
    # Mock Layer 2 VegetationState
    s_water = StressMagnitudeState(
        stress_type="WATER",
        value=0.30,
        uncertainty=UncertaintyBudget(0.02, 0.02, 0.0, 0.02),
        source=PhysicalSourceType.DERIVED,
    )
    veg_state = VegetationState(
        plot_id="plot_almond_orchard_7",
        timestamp=now,
        development_time=450.0,
        phenology_stage="NUT_DEVELOPMENT",
        stage_progress_fraction=0.60,
        crop_authority=CropKnowledgeAuthority.FIELD_VALIDATED,
        lai=3.2,
        fvc=0.75,
        fpar=0.80,
        canopy_water_index=-0.04,
        root_depth_proxy_m=1.1,
        root_zone_accessibility="DEEP",
        physical_stress_states={"WATER": s_water},
    )

    weather_obs = {
        "t_max_c": 33.0,
        "t_min_c": 19.0,
        "precipitation_mm": 0.0,
        "wind_speed_2m_m_s": 2.4,
        "rh_min_pct": 32.0,
        "rh_max_pct": 78.0,
        "net_radiation_mj_m2": 21.0,
    }

    water_state, feedback_to_l2 = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot_almond_orchard_7",
        timestamp=now,
        vegetation_state=veg_state,
        weather_observations=weather_obs,
        soil_type="silt_loam",
        hydrology_mode=HydrologyMode.FAO56_LAYERED_BUCKET,
    )

    # 1. Verify schema versioning
    assert water_state.schema_version == "3.0"
    assert isinstance(feedback_to_l2, Layer3HydrologicalConstraintReceipt)

    # 2. Extract Layer 3 -> Layer 4 Boundary Receipt
    receipt_l4 = water_state.to_layer4_boundary_receipt()
    assert isinstance(receipt_l4, Layer3ToLayer4BoundaryReceipt)
    
    # 3. Verify physical boundary properties
    assert receipt_l4.plot_id == "plot_almond_orchard_7"
    assert receipt_l4.timestamp == now
    assert 0.0 <= receipt_l4.stress_factor_ks <= 1.0
    assert receipt_l4.transpiration_deficit_mm >= 0.0
    assert receipt_l4.transpiration_deficit_sigma_mm >= 0.0
    assert receipt_l4.total_available_water_mm > 0.0
    assert receipt_l4.readily_available_water_mm > 0.0
    assert receipt_l4.root_zone_depletion_mm >= 0.0
    assert 0.0 <= receipt_l4.water_availability_ratio <= 1.0
    assert receipt_l4.physics_authority in ("ASSIMILATED", "MODELLED")
    assert receipt_l4.solver_fidelity == "EMPIRICAL_BUCKET"
    assert 0.80 <= receipt_l4.water_confidence_score <= 1.0


def test_l3_l4_information_barrier_encapsulation():
    """Verify that Layer 4 boundary receipt has NO access to raw remote sensing or hydraulic mechanics."""
    receipt_fields = set(Layer3ToLayer4BoundaryReceipt.__dataclass_fields__.keys())

    # Strictly permitted biophysical boundary fields
    permitted_fields = {
        "plot_id",
        "timestamp",
        "stress_factor_ks",
        "transpiration_deficit_mm",
        "transpiration_deficit_sigma_mm",
        "total_available_water_mm",
        "readily_available_water_mm",
        "root_zone_depletion_mm",
        "water_availability_ratio",
        "cumulative_transpiration_deficit_mm",
        "consecutive_days_under_limitation",
        "severe_limitation_days_count",
        "integrated_hydraulic_stress_index",
        "water_stress_recovery_rate",
        "drought_exposure_class",
        "physics_authority",
        "solver_fidelity",
        "water_confidence_score",
        "assimilation_status",
    }

    assert receipt_fields == permitted_fields

    # Forbidden leakages that must NEVER exist on the L3 -> L4 boundary
    forbidden_spectral_fields = {"ndmi", "evi", "ndvi", "swir", "nir", "thermal_radiance"}
    forbidden_soil_mechanics = {"van_genuchten_n", "van_genuchten_alpha", "ksat", "theta_r"}
    forbidden_actuator_fields = {"valve_status", "flow_rate_m3_hr", "pump_pressure"}

    for field_name in forbidden_spectral_fields:
        assert field_name not in receipt_fields, f"Forbidden spectral leakage: {field_name}"

    for field_name in forbidden_soil_mechanics:
        assert field_name not in receipt_fields, f"Forbidden soil mechanics leakage: {field_name}"

    for field_name in forbidden_actuator_fields:
        assert field_name not in receipt_fields, f"Forbidden actuator leakage: {field_name}"
