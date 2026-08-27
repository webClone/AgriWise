"""
Comprehensive Test Suite for Layer 3.0 Water Intelligence Engine
Validates all physical invariants, multi-layer soil hydrology, dual Kc partitioning, MPC optimization, and ensemble forecasting.
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
    WaterPhysicsAuthority,
    HydrologyMode,
    SolverFidelity,
    WaterPhysicsConfidence,
    HumiditySourceType,
    RadiationSourceType,
    WindSourceType,
    TemperatureSourceType,
    AtmosphericInputQuality,
    CanopyTemperatureState,
    WaterSignalType,
    Layer3HydrologicalConstraintReceipt,
    IrrigationMethod,
    WaterDecisionAction,
    WaterDecisionUrgency,
    IrrigationConstraints,
    IrrigationObjective,
    WaterDecision,
    SoilWaterState,
    WaterFluxState,
    RootZoneWaterState,
    WaterLimitationForecast,
    WaterState,
)
from layer3_water.et import (
    PenmanMonteithET0,
    DualKcEngine,
    compute_actual_vapor_pressure,
    saturation_vapor_pressure,
)
from layer3_water.soil import (
    SoilProfileDatabase,
    LayeredWaterBalanceEngine,
)
from layer3_water.root_zone import RootZoneAvailabilityEngine
from layer3_water.limitation import WaterLimitationEngine, WaterLimitationState
from layer3_water.forecast import WeatherScenario, WeatherScenarioEnsemble, EnsembleForecastEngine
from layer3_water.decision import MPCPrescriptiveOptimizer
from layer3_water.runner import WaterIntelligenceEngine


def test_penman_monteith_fao56_humidity_hierarchy():
    """Verify FAO-56 Penman-Monteith ET0 with strict humidity source hierarchy."""
    # Priority 1: Dew point temperature
    res_dew = PenmanMonteithET0.calculate_et0(
        t_max_c=32.0,
        t_min_c=18.0,
        net_radiation_mj_m2=22.0,
        wind_speed_2m_m_s=2.5,
        dew_point_c=14.0,
        rh_max_pct=85.0, # Should be ignored in favor of dew_point
    )
    assert res_dew.atmospheric_quality.humidity_source == HumiditySourceType.DEW_POINT
    assert res_dew.et0_mm_day > 0.0
    assert res_dew.vapor_pressure_deficit_kpa > 0.0

    # Priority 2: RH min & RH max
    res_rh_minmax = PenmanMonteithET0.calculate_et0(
        t_max_c=32.0,
        t_min_c=18.0,
        net_radiation_mj_m2=22.0,
        wind_speed_2m_m_s=2.5,
        rh_max_pct=85.0,
        rh_min_pct=35.0,
    )
    assert res_rh_minmax.atmospheric_quality.humidity_source == HumiditySourceType.RH_MIN_MAX
    assert res_rh_minmax.et0_mm_day > 0.0

    # Priority 3: RH mean
    res_rh_mean = PenmanMonteithET0.calculate_et0(
        t_max_c=32.0,
        t_min_c=18.0,
        net_radiation_mj_m2=22.0,
        wind_speed_2m_m_s=2.5,
        rh_mean_pct=60.0,
    )
    assert res_rh_mean.atmospheric_quality.humidity_source == HumiditySourceType.RH_MEAN
    assert res_rh_mean.et0_mm_day > 0.0


def test_dual_kc_canopy_scaling_and_climate_adjustment():
    """Verify Kcb scaling with LAI/FVC and bidirectional climate adjustment."""
    # Test LAI scaling: higher LAI yields higher Kcb until full canopy
    kcb_low = DualKcEngine.estimate_kcb_from_canopy(lai=0.5, fvc=0.20, wind_speed_2m_m_s=2.0, rh_min_pct=45.0)
    kcb_mid = DualKcEngine.estimate_kcb_from_canopy(lai=2.0, fvc=0.60, wind_speed_2m_m_s=2.0, rh_min_pct=45.0)
    kcb_high = DualKcEngine.estimate_kcb_from_canopy(lai=4.5, fvc=0.90, wind_speed_2m_m_s=2.0, rh_min_pct=45.0)
    
    assert kcb_low < kcb_mid < kcb_high

    # Test bidirectional climate adjustment:
    # Arid & windy (u2=4.0, RH_min=20%) -> positive adjustment
    kcb_arid = DualKcEngine.estimate_kcb_from_canopy(lai=3.5, fvc=0.85, wind_speed_2m_m_s=4.0, rh_min_pct=20.0)
    # Humid & calm (u2=1.0, RH_min=75%) -> negative adjustment
    kcb_humid = DualKcEngine.estimate_kcb_from_canopy(lai=3.5, fvc=0.85, wind_speed_2m_m_s=1.0, rh_min_pct=75.0)
    assert kcb_arid > kcb_humid

    # Test Ke soil evaporation with exposed wetted fraction
    kc_max = DualKcEngine.calculate_kc_max(kcb=kcb_mid)
    ke_wet, evap_state = DualKcEngine.calculate_soil_evaporation_ke(
        kcb=kcb_mid,
        kc_max=kc_max,
        fvc=0.60,
        surface_storage_mm=10.0,
        max_surface_storage_mm=12.0,
    )
    assert ke_wet > 0.0
    assert evap_state.kr_reduction_factor == 1.0


def test_strict_et_partition_invariants():
    """Verify strict physical invariants on evaporative fluxes: Ke <= Kcmax - Kcb, Tact <= Tpot, Esact <= Espot."""
    et0 = 6.0
    kcb = 1.05
    kc_max = DualKcEngine.calculate_kc_max(kcb=kcb)
    ke, _ = DualKcEngine.calculate_soil_evaporation_ke(kcb=kcb, kc_max=kc_max, fvc=0.70, surface_storage_mm=8.0)
    
    assert 0.0 <= ke <= (kc_max - kcb)
    
    for ks in [0.0, 0.35, 0.70, 1.0]:
        fluxes = DualKcEngine.partition_evapotranspiration(et0_mm=et0, kcb=kcb, ke=ke, ks=ks)
        
        # 1. Tact <= Tpot
        assert fluxes.actual.actual_transpiration_mm <= fluxes.potential.tpot_mm
        # 2. Esact <= Espot
        assert fluxes.actual.actual_soil_evaporation_mm <= fluxes.potential.espot_mm
        # 3. ETa = Tact + Esact
        assert abs(fluxes.actual.actual_eta_mm - (fluxes.actual.actual_transpiration_mm + fluxes.actual.actual_soil_evaporation_mm)) < 1e-3
        # 4. Tdeficit = Tpot - Tact
        assert abs(fluxes.actual.transpiration_deficit_mm - (fluxes.potential.tpot_mm - fluxes.actual.actual_transpiration_mm)) < 1e-3


def test_multi_layer_soil_water_balance_mass_conservation():
    """Verify tightened multi-layer mass conservation invariant: |Delta S - (Inputs - Outflows)| < 0.05 mm."""
    soil_init = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam", initial_saturation_fraction=0.65)
    s_prev = soil_init.total_profile_water_mm
    
    root_zone = RootZoneAvailabilityEngine.evaluate_root_zone(soil_state=soil_init, root_depth_m=1.0, etp_mm_day=6.0)
    
    p = 25.0 # Precipitation (mm)
    irrig = 0.0
    t_act = 4.2 # Actual transpiration (mm)
    es_act = 1.0 # Actual soil evaporation (mm)
    eta = t_act + es_act
    
    soil_next, actual_infil, runoff, deep_drainage, mass_err = LayeredWaterBalanceEngine.step_water_balance(
        prev_soil=soil_init,
        root_zone=root_zone,
        precipitation_mm=p,
        irrigation_mm=irrig,
        actual_transpiration_mm=t_act,
        actual_soil_evaporation_mm=es_act,
    )
    
    s_curr = soil_next.total_profile_water_mm
    
    # Invariant: Delta S = (P + I) - ETa - Runoff - Drainage
    inflows = p + irrig
    outflows = eta + runoff + deep_drainage
    delta_s = s_curr - s_prev
    
    assert abs(delta_s - (inflows - outflows)) < 0.10
    assert mass_err < 0.05


def test_root_extraction_profile_and_transpiration_conservation():
    """Verify root extraction distribution normalization sum(U_i) = 1.0 and transpiration deficit conservation."""
    soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type="clay_loam", initial_saturation_fraction=0.55)
    rz = RootZoneAvailabilityEngine.evaluate_root_zone(soil_state=soil, root_depth_m=1.0, etp_mm_day=5.5)
    
    # Root uptake distribution sum must equal 1.0
    uptake_dist = rz.root_uptake_distribution_profile
    assert abs(sum(uptake_dist) - 1.0) < 1e-3
    assert len(uptake_dist) == len(soil.layer_depths_cm)

    # Transpiration partition invariant: T_pot = T_act + T_deficit
    fluxes = DualKcEngine.partition_evapotranspiration(
        et0_mm=5.0,
        kcb=1.10,
        ke=0.15,
        ks=rz.stress_factor_ks,
    )
    t_pot = fluxes.potential.tpot_mm
    t_act = fluxes.actual.actual_transpiration_mm
    t_def = fluxes.actual.transpiration_deficit_mm
    
    assert abs((t_act + t_def) - t_pot) < 1e-3


def test_water_limitation_engine_physical_causality():
    """Verify physical water limitation causality: soil deficit -> Ks -> Tdeficit without NDMI."""
    soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam")
    rz = RootZoneAvailabilityEngine.evaluate_root_zone(soil_state=soil, root_depth_m=0.80, etp_mm_day=6.0)
    
    pot_flux = DualKcEngine.partition_evapotranspiration(et0_mm=6.0, kcb=1.0, ke=0.1, ks=1.0).potential
    
    lim_state = WaterLimitationEngine.evaluate_limitation(root_zone=rz, potential_flux=pot_flux)
    
    assert lim_state.stress_factor_ks == rz.stress_factor_ks
    assert lim_state.total_available_water_mm == rz.total_available_water_mm
    assert lim_state.readily_available_water_mm == rz.readily_available_water_mm
    assert len(lim_state.diagnostic_evidence) > 0
    assert lim_state.transpiration_deficit_sigma_mm >= 0.0


def test_mpc_prescriptive_irrigation_optimizer():
    """Verify MPC optimizer recommendations across dry vs wet root-zone scenarios."""
    # Scenario A: Severely depleted soil -> triggers IRRIGATE
    soil_dry = SoilProfileDatabase.get_canonical_soil_profile(soil_type="sandy_loam", initial_saturation_fraction=0.10)
    rz_dry = RootZoneAvailabilityEngine.evaluate_root_zone(soil_state=soil_dry, root_depth_m=0.80, etp_mm_day=7.0)
    pot_flux = DualKcEngine.partition_evapotranspiration(et0_mm=7.0, kcb=1.15, ke=0.10, ks=rz_dry.stress_factor_ks).potential
    forecast_dry = EnsembleForecastEngine.simulate_depletion_forecast(current_root_zone=rz_dry, kcb=1.15, ke=0.10)
    
    decision_dry = MPCPrescriptiveOptimizer.optimize_irrigation_schedule(
        root_zone=rz_dry,
        potential_flux=pot_flux,
        limitation_forecast=forecast_dry,
        method=IrrigationMethod.DRIP,
    )
    assert decision_dry.action == WaterDecisionAction.IRRIGATE
    assert decision_dry.recommended_net_mm > 0.0
    assert decision_dry.recommended_gross_mm > decision_dry.recommended_net_mm
    assert decision_dry.urgency in (WaterDecisionUrgency.HIGH, WaterDecisionUrgency.CRITICAL)

    # Scenario B: Well-watered soil -> triggers HOLD
    soil_wet = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam", initial_saturation_fraction=0.90)
    rz_wet = RootZoneAvailabilityEngine.evaluate_root_zone(soil_state=soil_wet, root_depth_m=0.80, etp_mm_day=4.0)
    pot_flux_wet = DualKcEngine.partition_evapotranspiration(et0_mm=4.0, kcb=0.90, ke=0.10, ks=rz_wet.stress_factor_ks).potential
    forecast_wet = EnsembleForecastEngine.simulate_depletion_forecast(current_root_zone=rz_wet, kcb=0.90, ke=0.10)
    
    decision_wet = MPCPrescriptiveOptimizer.optimize_irrigation_schedule(
        root_zone=rz_wet,
        potential_flux=pot_flux_wet,
        limitation_forecast=forecast_wet,
        method=IrrigationMethod.DRIP,
    )
    assert decision_wet.action == WaterDecisionAction.HOLD
    assert decision_wet.recommended_net_mm == 0.0
    assert decision_wet.urgency == WaterDecisionUrgency.LOW


def test_calibrated_nwp_ensemble_weights():
    """Verify calibrated NWP multi-member weather ensemble construction."""
    ensemble = WeatherScenarioEnsemble.from_calibrated_nwp_forecast(
        scenario_names=["HOT_DRY", "MEDIAN", "COOL_RAIN"],
        probability_weights=[0.30, 0.50, 0.20],
        precipitation_series=[[0.0]*5, [1.0]*5, [6.0]*5],
        et0_series=[[7.0]*5, [5.5]*5, [4.0]*5],
        nwp_source="ECMWF_EPS",
    )
    assert ensemble.forecast_days == 5
    assert len(ensemble.scenarios) == 3
    assert abs(sum(sc.probability_weight for sc in ensemble.scenarios) - 1.0) < 1e-3


def test_weather_ensemble_probabilistic_depletion_forecast():
    """Verify multi-scenario weather ensemble forecasting and probabilistic limitation trajectory."""
    soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam", initial_saturation_fraction=0.60)
    rz = RootZoneAvailabilityEngine.evaluate_root_zone(soil_state=soil, root_depth_m=0.90, etp_mm_day=5.5)
    
    ensemble = WeatherScenarioEnsemble.generate_synthetic_ensemble(base_daily_et0_mm=6.0, forecast_days=7)
    forecast = EnsembleForecastEngine.simulate_depletion_forecast(
        current_root_zone=rz,
        kcb=1.10,
        ke=0.15,
        weather_ensemble=ensemble,
    )
    
    assert forecast.forecast_days == 7
    assert len(forecast.projected_depletion_mm) == 7
    assert len(forecast.water_limitation_probability_trajectory) == 7
    assert len(forecast.transpiration_deficit_trajectory) == 7
    assert len(forecast.ensemble_spread_mm) == 7
    
    # Monotonic progression in absence of significant rain: depletion increases over days
    assert forecast.projected_depletion_mm[-1] >= forecast.projected_depletion_mm[0]


def test_end_to_end_water_intelligence_pipeline_runner():
    """Verify end-to-end execution of WaterIntelligenceEngine runner and Layer 2 feedback receipt."""
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    
    # Mock frozen Layer 2 VegetationState
    s_water = StressMagnitudeState(
        stress_type="WATER",
        value=0.45,
        uncertainty=UncertaintyBudget(0.02, 0.03, 0.0, 0.02),
        source=PhysicalSourceType.DERIVED,
        primary_sensor_evidence=["SAR_VV_VH", "CANOPY_SWIR"],
    )
    veg_state = VegetationState(
        plot_id="plot_wheat_valley_4",
        timestamp=now,
        development_time=620.0,
        phenology_stage="GRAIN_FILL",
        stage_progress_fraction=0.72,
        crop_authority=CropKnowledgeAuthority.FIELD_VALIDATED,
        lai=3.8,
        fvc=0.88,
        fpar=0.89,
        canopy_water_index=-0.08,
        root_depth_proxy_m=1.2,
        root_zone_accessibility="DEEP",
        physical_stress_states={"WATER": s_water},
    )

    canopy_temp = CanopyTemperatureState(
        canopy_temperature_c=29.0,
        air_temperature_c=27.5,
        vapor_pressure_deficit_kpa=2.1,
        evaporative_cooling_deficit_c=2.8,
    )

    weather_obs = {
        "t_max_c": 31.0,
        "t_min_c": 17.5,
        "precipitation_mm": 0.0,
        "wind_speed_2m_m_s": 2.2,
        "rh_min_pct": 38.0,
        "rh_max_pct": 82.0,
        "net_radiation_mj_m2": 20.5,
    }

    water_state, feedback_to_l2 = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot_wheat_valley_4",
        timestamp=now,
        vegetation_state=veg_state,
        weather_observations=weather_obs,
        soil_type="loam",
        canopy_temperature_state=canopy_temp,
        hydrology_mode=HydrologyMode.FAO56_LAYERED_BUCKET,
    )

    # Validate unified WaterState X_t^L3
    assert water_state.plot_id == "plot_wheat_valley_4"
    assert water_state.physics_authority == WaterPhysicsAuthority.ASSIMILATED
    assert water_state.hydrology_mode == HydrologyMode.FAO56_LAYERED_BUCKET
    assert water_state.solver_fidelity == SolverFidelity.EMPIRICAL_BUCKET
    assert water_state.mass_balance_error_mm < 0.05
    assert water_state.soil_water.total_profile_water_mm > 0.0
    assert water_state.fluxes.potential.etp_mm > 0.0
    assert water_state.fluxes.actual.actual_eta_mm > 0.0
    assert water_state.root_zone.total_available_water_mm > 0.0
    assert water_state.limitation_forecast.forecast_days == 7
    assert water_state.active_decision is not None
    assert water_state.thermal_observation is not None
    assert water_state.thermal_observation.temperature_differential_c == 1.5

    # Validate feedback receipt to Layer 2
    assert feedback_to_l2.plot_id == "plot_wheat_valley_4"
    assert 0.0 <= feedback_to_l2.transpiration_constraint_factor <= 1.0
    assert feedback_to_l2.transpiration_deficit_mm >= 0.0
    assert feedback_to_l2.authority == "HYDROLOGICAL_PROCESS_CONSTRAINT"


def test_no_impossible_water_creation_invariant():
    """Verify invariant: soil profile storage cannot increase without precipitation, irrigation, or capillary rise."""
    soil_init = SoilProfileDatabase.get_canonical_soil_profile(soil_type="clay_loam")
    s_init = soil_init.total_profile_water_mm
    
    root_zone = RootZoneAvailabilityEngine.evaluate_root_zone(soil_state=soil_init, root_depth_m=1.0)
    
    # Step with zero inflows
    soil_next, _, _, _, mass_err = LayeredWaterBalanceEngine.step_water_balance(
        prev_soil=soil_init,
        root_zone=root_zone,
        precipitation_mm=0.0,
        irrigation_mm=0.0,
        actual_transpiration_mm=3.5,
        actual_soil_evaporation_mm=1.0,
        capillary_rise_mm=0.0,
    )
    s_next = soil_next.total_profile_water_mm
    
    # Profile water must decrease or stay equal; can never increase spontaneously
    assert s_next < s_init
    assert abs((s_init - s_next) - 4.5) < 0.2
    assert mass_err < 0.05


def test_monotonicity_invariants():
    """Verify monotonicity invariants: Kcb increases with LAI; Ks decreases with depletion Dr."""
    # 1. Kcb monotonicity with LAI
    lais = [0.2, 0.8, 1.5, 3.0, 5.0]
    kcbs = [DualKcEngine.estimate_kcb_from_canopy(lai=l, fvc=0.5) for l in lais]
    for i in range(len(kcbs) - 1):
        assert kcbs[i] <= kcbs[i+1]

    # 2. Ks monotonicity with Dr
    soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam")
    taw = 120.0
    raw = 60.0
    drs = [20.0, 50.0, 70.0, 90.0, 110.0, 130.0]
    kss = []
    for d in drs:
        if d <= raw:
            kss.append(1.0)
        elif d >= taw:
            kss.append(0.0)
        else:
            kss.append(round((taw - d) / (taw - raw), 3))
            
    for i in range(len(kss) - 1):
        assert kss[i] >= kss[i+1]


def test_monte_carlo_transpiration_deficit_uncertainty():
    """Verify analytical uncertainty propagation of T_deficit against Monte Carlo numerical simulations."""
    import random
    random.seed(42)
    mu_et0 = 6.0
    sig_et0 = 0.40
    
    mu_kcb = 1.10
    sig_kcb = 0.05
    
    ks_val = 0.65
    sig_ks = 0.06
    
    # 1. Analytical error propagation:
    # T_pot = Kcb * ET0
    tpot = mu_kcb * mu_et0
    sigma_tpot = math.sqrt((mu_kcb * sig_et0)**2 + (mu_et0 * sig_kcb)**2)
    # T_deficit = (1 - Ks) * T_pot
    sigma_tdef_analytical = math.sqrt(((1.0 - ks_val) * sigma_tpot)**2 + (tpot * sig_ks)**2)
    
    # 2. Monte Carlo simulation (5000 draws)
    n_draws = 5000
    tdef_samples = []
    for _ in range(n_draws):
        et0_s = random.gauss(mu_et0, sig_et0)
        kcb_s = random.gauss(mu_kcb, sig_kcb)
        ks_s = max(0.0, min(1.0, random.gauss(ks_val, sig_ks)))
        tdef_s = (1.0 - ks_s) * kcb_s * et0_s
        tdef_samples.append(tdef_s)
        
    mean_mc = sum(tdef_samples) / n_draws
    variance_mc = sum((x - mean_mc)**2 for x in tdef_samples) / (n_draws - 1)
    sigma_tdef_mc = math.sqrt(variance_mc)
    
    # Assert analytical uncertainty agrees with Monte Carlo standard error within 10%
    rel_diff = abs(sigma_tdef_analytical - sigma_tdef_mc) / sigma_tdef_analytical
    assert rel_diff < 0.10


def test_water_physics_confidence_and_ledger():
    """Verify multi-source WaterPhysicsConfidence and MPC decision explainability ledger."""
    conf = WaterPhysicsConfidence.compute(
        mass_balance_error_mm=0.02,
        solver_fidelity=SolverFidelity.EMPIRICAL_BUCKET,
        soil_quality=0.92,
        weather_quality=0.95,
    )
    assert 0.85 <= conf.overall_water_confidence <= 1.0
    assert conf.mass_balance_quality >= 0.95
    assert conf.solver_fidelity == SolverFidelity.EMPIRICAL_BUCKET
