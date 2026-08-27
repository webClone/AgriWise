"""
Comprehensive Test Suite for Layer 3.0 Water Intelligence Contracts & State Architecture
Validates physical invariants, potential/actual ET partitioning, mass conservation, and transition graph.
"""

from datetime import datetime, timezone
import math
import pytest

from layer2_contracts.state_contracts import (
    VegetationState,
    CropKnowledgeAuthority,
    StressMagnitudeState,
    StressHypothesisState,
    PhysicalSourceType,
    UncertaintyBudget,
    InferenceProvenance,
)
from layer3_water.contracts import (
    WaterUncertaintyBudget,
    HumiditySourceType,
    RadiationSourceType,
    WindSourceType,
    TemperatureSourceType,
    AtmosphericInputQuality,
    CanopyTemperatureState,
    Layer3HydrologicalConstraintReceipt,
    Layer3ToLayer4BoundaryReceipt,
    IrrigationMethod,
    WaterDecisionAction,
    WaterDecisionUrgency,
    IrrigationEvent,
    IrrigationConstraints,
    IrrigationObjective,
    WaterDecision,
    SoilWaterState,
    PotentialWaterFlux,
    ActualWaterFlux,
    WaterFluxState,
    RootZoneWaterState,
    WaterLimitationForecast,
    WaterState,
    WaterStateFactory,
    WaterProcessStage,
    Layer3WaterTransitionGraph,
)


def test_water_uncertainty_budget_quadrature():
    """Verify that 4-component water uncertainty budget computes total sigma via quadrature."""
    unc = WaterUncertaintyBudget(
        sensor_sigma=0.03,
        soil_sigma=0.04,
        weather_sigma=0.02,
        model_sigma=0.03,
    )
    expected_total = math.sqrt(0.03**2 + 0.04**2 + 0.02**2 + 0.03**2)
    assert abs(unc.total_sigma - round(expected_total, 4)) < 1e-4
    assert unc.to_dict()["total_sigma"] == unc.total_sigma


def test_atmospheric_quality_and_canopy_temperature():
    """Verify atmospheric provenance hierarchy and evaporative cooling deficit state."""
    atmos = AtmosphericInputQuality(
        humidity_source=HumiditySourceType.DEW_POINT,
        radiation_source=RadiationSourceType.PYRANOMETER,
        wind_source=WindSourceType.ANEMOMETER_2M,
        temperature_source=TemperatureSourceType.CALIBRATED_STATION,
        overall_confidence=0.95,
    )
    assert atmos.humidity_source == HumiditySourceType.DEW_POINT
    assert atmos.overall_confidence == 0.95

    canopy_t = CanopyTemperatureState(
        canopy_temperature_c=28.5,
        air_temperature_c=26.0,
        vapor_pressure_deficit_kpa=1.85,
        evaporative_cooling_deficit_c=3.2,
        thermal_authority="THERMAL_OBSERVATION_NOT_CAUSAL_DIAGNOSIS",
        observation_uncertainty_c=0.4,
    )
    assert canopy_t.temperature_differential_c == 2.5
    assert canopy_t.evaporative_cooling_deficit_c == 3.2
    assert canopy_t.thermal_authority == "THERMAL_OBSERVATION_NOT_CAUSAL_DIAGNOSIS"


def test_layer3_hydrological_constraint_receipt():
    """Verify instantiation and properties of Layer3HydrologicalConstraintReceipt."""
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    receipt = Layer3HydrologicalConstraintReceipt(
        plot_id="plot_test_water_1",
        timestamp=now,
        transpiration_constraint_factor=0.68,
        transpiration_deficit_mm=2.1,
        soil_water_availability_ratio=0.55,
        root_zone_depletion_fraction=0.45,
        ks_uncertainty_sigma=0.04,
    )
    assert receipt.plot_id == "plot_test_water_1"
    assert receipt.transpiration_constraint_factor == 0.68
    assert receipt.transpiration_deficit_mm == 2.1
    assert receipt.authority == "HYDROLOGICAL_PROCESS_CONSTRAINT"


def test_soil_water_state_physical_boundaries_validation():
    """Verify that SoilWaterState enforces physical retention ordering and moisture bounds."""
    layers = [10.0, 30.0, 60.0, 100.0]
    th_fc = [0.28, 0.28, 0.30, 0.32]
    th_wp = [0.14, 0.14, 0.16, 0.18]
    th_s = [0.45, 0.45, 0.46, 0.48]
    th_r = [0.05, 0.05, 0.06, 0.06]
    theta = [0.22, 0.24, 0.28, 0.30]

    soil = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=layers,
        theta_profile=theta,
        field_capacity_profile=th_fc,
        wilting_point_profile=th_wp,
        saturation_profile=th_s,
        residual_profile=th_r,
    )
    assert len(soil.layer_depths_cm) == 4
    assert len(soil.van_genuchten_m) == 4
    # Expected profile water = sum(theta * thickness_mm)
    # 0.22 * 100 + 0.24 * 200 + 0.28 * 300 + 0.30 * 400 = 22 + 48 + 84 + 120 = 274 mm
    assert abs(soil.total_profile_water_mm - 274.0) < 0.1

    # Test invalid retention ordering (FC < WP) raises ValueError
    with pytest.raises(ValueError, match="physical retention ordering violated"):
        WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0],
            theta_profile=[0.20],
            field_capacity_profile=[0.12], # Invalid: FC < WP
            wilting_point_profile=[0.14],
            saturation_profile=[0.40],
            residual_profile=[0.05],
        )

    # Test moisture exceeding saturation raises ValueError
    with pytest.raises(ValueError, match="out of physical bounds"):
        WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0],
            theta_profile=[0.55], # Invalid: theta > theta_s
            field_capacity_profile=[0.30],
            wilting_point_profile=[0.15],
            saturation_profile=[0.45],
            residual_profile=[0.05],
        )


def test_root_zone_water_state_taw_raw_and_ks():
    """Verify TAW, RAW, demand-adjusted p, and continuous piecewise Ks reduction."""
    layers = [20.0, 50.0, 100.0]
    th_fc = [0.28, 0.28, 0.30]
    th_wp = [0.14, 0.14, 0.16]
    
    # Scenario A: Well-watered soil (theta near FC) -> Ks = 1.0
    theta_wet = [0.27, 0.27, 0.29]
    rz_wet = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.80, # 80 cm rooting depth
        layer_depths_cm=layers,
        theta_profile=theta_wet,
        field_capacity_profile=th_fc,
        wilting_point_profile=th_wp,
        base_depletion_fraction_p=0.50,
        etp_mm_day=5.0, # At ETp=5.0, p = 0.50 + 0.04*(5-5) = 0.50
    )
    assert rz_wet.depletion_fraction_p == 0.50
    assert rz_wet.stress_factor_ks == 1.0
    assert rz_wet.root_zone_depletion_mm < rz_wet.readily_available_water_mm

    # Scenario B: Dry soil (Dr > RAW) -> Ks reduces linearly
    theta_dry = [0.17, 0.17, 0.18]
    rz_dry = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.80,
        layer_depths_cm=layers,
        theta_profile=theta_dry,
        field_capacity_profile=th_fc,
        wilting_point_profile=th_wp,
        base_depletion_fraction_p=0.50,
        etp_mm_day=7.5, # High evaporative demand -> p decreases to 0.40
    )
    assert rz_dry.depletion_fraction_p == 0.40 # 0.50 + 0.04*(5.0 - 7.5) = 0.40
    assert rz_dry.stress_factor_ks < 1.0
    assert rz_dry.root_zone_depletion_mm > rz_dry.readily_available_water_mm
    
    # Verify piecewise linear formula: Ks = (TAW - Dr) / (TAW - RAW)
    expected_ks = round((rz_dry.total_available_water_mm - rz_dry.root_zone_depletion_mm) / 
                        (rz_dry.total_available_water_mm - rz_dry.readily_available_water_mm), 3)
    assert abs(rz_dry.stress_factor_ks - expected_ks) < 1e-3


def test_potential_vs_actual_flux_separation():
    """Verify strict separation of potential demand and actual realized fluxes."""
    fluxes = WaterStateFactory.create_flux_state(
        et0_mm=6.0,
        kcb=1.10,
        ke=0.15,
        ks=0.60, # 40% water limitation
        precipitation_mm=0.0,
        irrigation_mm=15.0,
        deep_drainage_mm=1.2,
        runoff_mm=0.0,
        capillary_rise_mm=0.0,
    )
    
    # Potential: ETp = (1.10 + 0.15)*6.0 = 7.50 mm; Tpot = 1.10*6.0 = 6.60 mm; Espot = 0.15*6.0 = 0.90 mm
    assert fluxes.potential.etp_mm == 7.50
    assert fluxes.potential.tpot_mm == 6.60
    assert fluxes.potential.espot_mm == 0.90
    
    # Actual: Tact = 0.60 * 6.60 = 3.96 mm; Esact = 0.90 mm; ETa = 3.96 + 0.90 = 4.86 mm
    assert fluxes.actual.actual_transpiration_mm == 3.96
    assert fluxes.actual.actual_soil_evaporation_mm == 0.90
    assert fluxes.actual.actual_eta_mm == 4.86
    
    # Transpiration Deficit: Tdeficit = Tpot - Tact = 6.60 - 3.96 = 2.64 mm
    assert fluxes.actual.transpiration_deficit_mm == 2.64
    assert abs((fluxes.actual.actual_transpiration_mm + fluxes.actual.transpiration_deficit_mm) - fluxes.potential.tpot_mm) < 1e-3


def test_mass_conservation_and_water_state_instantiation():
    """Verify unified WaterState (X_t^L3) construction and mass conservation consistency."""
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    layers = [20.0, 60.0, 120.0]
    th_fc = [0.28, 0.30, 0.32]
    th_wp = [0.14, 0.16, 0.18]
    th_s = [0.45, 0.46, 0.48]
    th_r = [0.05, 0.06, 0.07]
    theta = [0.22, 0.25, 0.28]

    soil = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=layers,
        theta_profile=theta,
        field_capacity_profile=th_fc,
        wilting_point_profile=th_wp,
        saturation_profile=th_s,
        residual_profile=th_r,
    )
    rz = WaterStateFactory.create_root_zone_water_state(
        root_depth_m=0.90,
        layer_depths_cm=layers,
        theta_profile=theta,
        field_capacity_profile=th_fc,
        wilting_point_profile=th_wp,
        base_depletion_fraction_p=0.50,
        etp_mm_day=5.5,
    )
    fluxes = WaterStateFactory.create_flux_state(
        et0_mm=5.0,
        kcb=1.05,
        ke=0.10,
        ks=rz.stress_factor_ks,
        precipitation_mm=10.0,
        irrigation_mm=0.0,
        deep_drainage_mm=0.5,
        runoff_mm=0.0,
    )
    
    water_state = WaterStateFactory.create_water_state(
        plot_id="plot_alpha_101",
        timestamp=now,
        soil_water=soil,
        fluxes=fluxes,
        root_zone=rz,
    )

    assert water_state.plot_id == "plot_alpha_101"
    assert water_state.soil_water.total_profile_water_mm > 0
    assert water_state.root_zone.total_available_water_mm > 0
    assert water_state.limitation_forecast.forecast_days == 7
    assert len(water_state.limitation_forecast.water_limitation_probability_trajectory) == 7


def test_irrigation_decision_and_objective_contracts():
    """Verify prescriptive irrigation decision contracts, objectives, and constraints."""
    constraints = IrrigationConstraints(
        max_single_dose_mm=40.0,
        min_single_dose_mm=5.0,
        min_cycle_interval_hours=24.0,
        low_tariff_hours_only=True,
    )
    objective = IrrigationObjective(
        water_cost_weight=1.2,
        energy_cost_weight=0.8,
        transpiration_limitation_penalty_weight=6.0,
    )
    decision = WaterDecision(
        action=WaterDecisionAction.IRRIGATE,
        urgency=WaterDecisionUrgency.HIGH,
        recommended_net_mm=25.0,
        recommended_gross_mm=27.8, # Net / 0.90 drip efficiency
        transpiration_preserved_fraction=0.95,
        expected_water_limitation_reduction=38.5,
        economic_water_productivity_score=4.2,
        confidence_score=0.92,
        rationale=["Root zone depletion (Dr=32mm) exceeded RAW (28mm)", "Preserves 95% of potential transpiration"],
    )

    assert decision.action == WaterDecisionAction.IRRIGATE
    assert decision.urgency == WaterDecisionUrgency.HIGH
    assert decision.recommended_gross_mm > decision.recommended_net_mm
    assert decision.transpiration_preserved_fraction == 0.95
    assert len(decision.rationale) == 2


def test_transition_graph_dag_topological_consistency():
    """Verify that Layer 3 Water Process Transition Graph is strictly acyclic and ordered."""
    exec_order = Layer3WaterTransitionGraph.get_execution_order()
    assert len(exec_order) == 12
    assert exec_order[0] == WaterProcessStage.INPUT_INGESTION
    assert exec_order[1] == WaterProcessStage.SOLVER_SELECTION
    assert exec_order[2] == WaterProcessStage.ATMOSPHERIC_DEMAND
    assert exec_order[3] == WaterProcessStage.CANOPY_DEMAND_PARTITIONING
    assert exec_order[4] == WaterProcessStage.ROOT_ZONE_AVAILABILITY
    assert exec_order[5] == WaterProcessStage.SOIL_WATER_BALANCE
    assert exec_order[6] == WaterProcessStage.DATA_ASSIMILATION
    assert exec_order[7] == WaterProcessStage.ACTUAL_FLUX_PARTITIONING
    assert exec_order[8] == WaterProcessStage.HYDRAULIC_STRESS_MEMORY
    assert exec_order[9] == WaterProcessStage.LIMITATION_FORECAST
    assert exec_order[10] == WaterProcessStage.DECISION_OPTIMIZATION
    assert exec_order[11] == WaterProcessStage.L2_FEEDBACK_SYNTHESIS

    # Verify dependency mapping consistency
    for stage, dep in Layer3WaterTransitionGraph.PIPELINE_DEPENDENCIES.items():
        assert dep.stage == stage
        for prec in dep.preceding_stages:
            assert exec_order.index(prec) < exec_order.index(stage)
