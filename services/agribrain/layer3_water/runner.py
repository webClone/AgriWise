"""
Layer 3.0 Unified Water Intelligence Engine Runner
Integrates multi-layer soil hydrology, data assimilation, dual Kc evaporative partitioning, stress memory, and MPC optimization.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from layer2_contracts.state_contracts import VegetationState
from layer3_water.contracts import (
    WaterPhysicsAuthority,
    HydrologyMode,
    SolverFidelity,
    AtmosphericInputQuality,
    CanopyTemperatureState,
    SoilObservationVector,
    Layer3HydrologicalConstraintReceipt,
    IrrigationMethod,
    IrrigationConstraints,
    IrrigationObjective,
    WaterDecision,
    SoilWaterState,
    PotentialWaterFlux,
    ActualWaterFlux,
    WaterFluxState,
    RootZoneWaterState,
    WaterLimitationForecast,
    HydraulicStressMemoryState,
    AssimilationDiagnostic,
    IntervalFluxReceipt,
    AnalysisIncrementReceipt,
    WaterState,
    WaterStateFactory,
    WaterUncertaintyBudget,
)
from layer3_water.et import (
    PenmanMonteithET0,
    DualKcEngine,
)
from layer3_water.soil import (
    SoilProfileDatabase,
    LayeredWaterBalanceEngine,
)
from layer3_water.root_zone import RootZoneAvailabilityEngine
from layer3_water.limitation import WaterLimitationEngine, WaterLimitationState
from layer3_water.forecast import EnsembleForecastEngine, WeatherScenarioEnsemble
from layer3_water.decision import MPCPrescriptiveOptimizer
from layer3_water.assimilation import WaterStateAssimilator
from layer3_water.solver import SolverSelector
from services.agribrain.scientific_contracts.exceptions import ContractViolation
try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real


class WaterIntelligenceEngine:
    """Transitional Layer 3 water-state estimation pipeline."""

    @classmethod
    def execute_pipeline(
        cls,
        plot_id: str,
        timestamp: datetime,
        vegetation_state: Optional[VegetationState] = None,
        weather_observations: Optional[Dict[str, Any]] = None,
        soil_profile_state: Optional[SoilWaterState] = None,
        soil_observations: Optional[SoilObservationVector] = None,
        previous_hydraulic_memory: Optional[HydraulicStressMemoryState] = None,
        soil_type: str = "loam",
        irrigation_applied_mm: float = 0.0,
        irrigation_method: IrrigationMethod = IrrigationMethod.DRIP,
        irrigation_constraints: Optional[IrrigationConstraints] = None,
        irrigation_objective: Optional[IrrigationObjective] = None,
        weather_ensemble: Optional[WeatherScenarioEnsemble] = None,
        canopy_temperature_state: Optional[CanopyTemperatureState] = None,
        requested_hydrology_mode: Optional[HydrologyMode] = None,
        hydrology_mode: Optional[HydrologyMode] = None,
        days_since_wetting: int = 0,
    ) -> Tuple[WaterState, Layer3HydrologicalConstraintReceipt]:
        """Execute full Layer 3 water intelligence state estimation cycle.
        
        Returns:
            (canonical_water_state_X_L3, hydrological_feedback_to_layer2)
        """
        if not weather_observations:
            raise ContractViolation(
                "Layer 3 water requires explicit weather observations; "
                "empty inputs cannot produce a modelled atmospheric state"
            )
        required_weather = {
            "t_max_c", "t_min_c", "precipitation_mm",
            "wind_speed_2m_m_s", "rh_min_pct", "rh_max_pct",
            "net_radiation_mj_m2",
        }
        missing_weather = sorted(
            key for key in required_weather
            if weather_observations.get(key) is None
        )
        if missing_weather:
            raise ContractViolation(
                "Layer 3 water missing explicit weather elements: "
                + ", ".join(missing_weather)
            )

        weather_observations = dict(weather_observations)
        for key in required_weather | {"dew_point_c", "weather_sigma", "weather_sigma_override"}:
            if weather_observations.get(key) is None:
                continue
            value = finite_real(weather_observations[key])
            if value is None:
                raise ContractViolation(f"Layer 3 water requires finite numeric weather: {key}")
            weather_observations[key] = value
        if weather_observations["t_min_c"] > weather_observations["t_max_c"]:
            raise ContractViolation("Layer 3 water requires t_min_c <= t_max_c")
        for key in ("precipitation_mm", "wind_speed_2m_m_s"):
            if weather_observations[key] < 0.0:
                raise ContractViolation(f"Layer 3 water requires non-negative weather: {key}")
        for key in ("rh_min_pct", "rh_max_pct"):
            if not 0.0 <= weather_observations[key] <= 100.0:
                raise ContractViolation(f"Layer 3 water humidity outside [0, 100]: {key}")
        if weather_observations["rh_min_pct"] > weather_observations["rh_max_pct"]:
            raise ContractViolation("Layer 3 water requires rh_min_pct <= rh_max_pct")
        for key in ("weather_sigma", "weather_sigma_override"):
            if weather_observations.get(key) is not None and weather_observations[key] < 0.0:
                raise ContractViolation(f"Layer 3 water requires non-negative weather uncertainty: {key}")
        applied = finite_real(irrigation_applied_mm)
        if applied is None or applied < 0.0:
            raise ContractViolation("Layer 3 water requires finite non-negative applied irrigation")
        irrigation_applied_mm = applied

        mode = requested_hydrology_mode or hydrology_mode
        weather = weather_observations or {}
        t_max = weather["t_max_c"]
        t_min = weather["t_min_c"]
        precip = weather["precipitation_mm"]
        wind = weather["wind_speed_2m_m_s"]
        rh_min = weather["rh_min_pct"]
        rh_max = weather["rh_max_pct"]
        dew_point = weather.get("dew_point_c")
        rn = weather["net_radiation_mj_m2"]
        
        # 1. Adaptive Numerical Solver Selection Policy
        crop_priority = irrigation_objective.crop_economic_priority_factor if irrigation_objective else 1.0
        solver_decision = SolverSelector.select_solver(
            crop_economic_priority_factor=crop_priority,
            observations=soil_observations,
            requested_mode=mode,
        )

        # 2. Atmospheric Reference ET0 with input provenance
        weather_sigma_override = None
        if "weather_sigma_override" in weather and weather["weather_sigma_override"] is not None:
            weather_sigma_override = float(weather["weather_sigma_override"])
        elif "weather_sigma" in weather and weather["weather_sigma"] is not None:
            weather_sigma_override = float(weather["weather_sigma"])
        elif weather.get("imputation_uncertainty_flag") or weather.get("imputation_method"):
            weather_sigma_override = 0.08

        et0_res = PenmanMonteithET0.calculate_et0(
            t_max_c=t_max,
            t_min_c=t_min,
            net_radiation_mj_m2=rn,
            wind_speed_2m_m_s=wind,
            dew_point_c=dew_point,
            rh_max_pct=rh_max,
            rh_min_pct=rh_min,
            weather_sigma_override=weather_sigma_override,
        )

        # 3. Extract vegetation coordinates from Layer 2 latent state
        if vegetation_state:
            lai = vegetation_state.lai
            fvc = vegetation_state.fvc
            root_depth_m = vegetation_state.root_depth_proxy_m or 1.0
        else:
            # Unmeasured vegetation: bare-soil baseline without fabricated lush canopy
            lai = 0.0
            fvc = 0.0
            root_depth_m = 0.3

        # 4. Dual Kc Canopy Demand & Soil Evaporation
        kcb = DualKcEngine.estimate_kcb_from_canopy(
            lai=lai,
            fvc=fvc,
            wind_speed_2m_m_s=wind,
            rh_min_pct=rh_min,
        )
        kc_max = DualKcEngine.calculate_kc_max(kcb=kcb, wind_speed_2m_m_s=wind, rh_min_pct=rh_min)
        
        # Initialize or retrieve multi-layer soil profile
        current_soil = soil_profile_state or SoilProfileDatabase.get_canonical_soil_profile(soil_type=soil_type)
        top_thickness_mm = current_soil.layer_depths_cm[0] * 10.0 if current_soil.layer_depths_cm else 100.0
        top_storage = current_soil.theta_profile[0] * top_thickness_mm
        
        # Effective days since wetting from parameter or previous soil evaporation state
        effective_days_since_wetting = days_since_wetting
        if effective_days_since_wetting == 0 and current_soil and getattr(current_soil, "evaporation_state", None):
            effective_days_since_wetting = current_soil.evaporation_state.days_since_wetting

        # Method-specific wetted fraction mapping per FAO-56 Table 20
        method_wetted_fractions = {
            IrrigationMethod.DRIP: 0.35,
            IrrigationMethod.MICRO_SPRINKLER: 0.60,
            IrrigationMethod.SPRINKLER: 1.00,
            IrrigationMethod.CENTER_PIVOT: 1.00,
            IrrigationMethod.SURFACE_FURROW: 0.70,
            IrrigationMethod.SURFACE_FLOOD: 1.00,
        }
        if precip > 0.0:
            fw = 1.0
        elif irrigation_applied_mm > 0.0:
            fw = method_wetted_fractions.get(irrigation_method, 1.0)
        elif current_soil and getattr(current_soil, "evaporation_state", None):
            fw = current_soil.evaporation_state.few_exposed_wetted_fraction
        else:
            fw = 1.0

        ke, evap_state = DualKcEngine.calculate_soil_evaporation_ke(
            kcb=kcb,
            kc_max=kc_max,
            fvc=fvc,
            surface_storage_mm=top_storage,
            fraction_wetted_by_irrigation=fw,
            days_since_wetting=effective_days_since_wetting,
        )

        pot_etp = (kcb + ke) * et0_res.et0_mm_day

        # 5. Root Zone Availability & Stress Reduction Ks
        root_zone = RootZoneAvailabilityEngine.evaluate_root_zone(
            soil_state=current_soil,
            root_depth_m=root_depth_m,
            etp_mm_day=pot_etp,
        )

        # 6. Dual Flux Partitioning (Prognostic Prior Demand)
        prior_flux_state = DualKcEngine.partition_evapotranspiration(
            et0_mm=et0_res.et0_mm_day,
            kcb=kcb,
            ke=ke,
            ks=root_zone.stress_factor_ks,
            precipitation_mm=precip,
            irrigation_mm=irrigation_applied_mm,
        )

        # 7. Multi-Layer Soil Water Balance Propagation (Prognostic Prior X^-)
        step_result = LayeredWaterBalanceEngine.step_water_balance(
            prev_soil=current_soil,
            root_zone=root_zone,
            precipitation_mm=precip,
            irrigation_mm=irrigation_applied_mm,
            actual_transpiration_mm=prior_flux_state.actual.actual_transpiration_mm,
            actual_soil_evaporation_mm=prior_flux_state.actual.actual_soil_evaporation_mm,
            days_since_wetting=effective_days_since_wetting,
            fraction_wetted=fw,
        )
        prognostic_soil = step_result[0]
        actual_infil = step_result[1]
        runoff = step_result[2]
        deep_drainage = step_result[3]
        mass_balance_err = step_result[4]
        flux_receipt = getattr(step_result, "receipt", None)

        # 8. Data Assimilation Update (Posterior X^+ = X^- + K(y - H X^-))
        posterior_soil, assim_diag = WaterStateAssimilator.assimilate_observations(
            prior_soil=prognostic_soil,
            observations=soil_observations,
            background_uncertainty_sigma=et0_res.uncertainty.soil_sigma,
        )

        # Build explicit AnalysisIncrementReceipt
        pre_storage = prognostic_soil.total_profile_water_mm
        post_storage = posterior_soil.total_profile_water_mm
        analysis_receipt = AnalysisIncrementReceipt(
            pre_assimilation_storage_mm=pre_storage,
            post_assimilation_storage_mm=post_storage,
            storage_increment_mm=round(post_storage - pre_storage, 4),
            prior_profile_variance=assim_diag.prior_profile_variance,
            posterior_profile_variance=assim_diag.posterior_profile_variance,
            variance_reduction_fraction=assim_diag.variance_reduction_fraction,
            bound_corrections_applied=getattr(assim_diag, "bound_corrections_applied", 0),
            assimilated_sensor_sources=list(assim_diag.assimilated_sensor_sources),
        )

        # GAP-3 FIX: Extract assimilation posterior variance to propagate
        # as calibrated soil_sigma into downstream uncertainty budgets.
        # This replaces the hardcoded 0.04 with the actual posterior uncertainty.
        _posterior_soil_sigma = et0_res.uncertainty.soil_sigma  # fallback
        if assim_diag and assim_diag.observations_assimilated_count > 0:
            # Defect A05 / Finding #27 fix: sqrt(1 - f) variance reduction scaling on standard deviation
            var_reduction = max(0.0, min(0.99, float(getattr(assim_diag, "variance_reduction_fraction", 0.0) or 0.0)))
            _posterior_soil_sigma = max(0.005, round(
                et0_res.uncertainty.soil_sigma * math.sqrt(1.0 - var_reduction),
                4,
            ))

        # Re-evaluate root zone with updated posterior soil state
        final_root_zone = RootZoneAvailabilityEngine.evaluate_root_zone(
            soil_state=posterior_soil,
            root_depth_m=root_depth_m,
            etp_mm_day=pot_etp,
        )

        # Realized interval fluxes: Publish the fluxes actually integrated in the transition receipt
        realized_transp = (
            flux_receipt.actual_transpiration_mm
            if flux_receipt
            else prior_flux_state.actual.actual_transpiration_mm
        )
        realized_evap = (
            flux_receipt.actual_soil_evaporation_mm
            if flux_receipt
            else prior_flux_state.actual.actual_soil_evaporation_mm
        )
        realized_drainage = flux_receipt.deep_drainage_mm if flux_receipt else deep_drainage
        realized_runoff = flux_receipt.surface_runoff_mm if flux_receipt else runoff
        realized_capillary = flux_receipt.capillary_rise_mm if flux_receipt else 0.0
        tpot = prior_flux_state.potential.tpot_mm
        realized_ks = round(realized_transp / tpot, 3) if tpot > 0.0 else 1.0
        realized_tdef = round(max(0.0, tpot - realized_transp), 2)

        realized_surface_evap = flux_receipt.surface_water_evaporation_mm if flux_receipt else 0.0

        published_actual = ActualWaterFlux(
            ks=round(min(1.0, max(0.0, realized_ks)), 3),
            precipitation_mm=precip,
            irrigation_mm=irrigation_applied_mm,
            deep_drainage_mm=round(realized_drainage, 2),
            runoff_mm=round(realized_runoff, 2),
            capillary_rise_mm=round(realized_capillary, 2),
            actual_transpiration_mm=round(realized_transp, 2),
            actual_soil_evaporation_mm=round(realized_evap, 2),
            surface_water_evaporation_mm=round(realized_surface_evap, 2),
            actual_eta_mm=round(realized_transp + realized_evap + realized_surface_evap, 2),
            transpiration_deficit_mm=realized_tdef,
        )
        published_flux_state = WaterFluxState(
            potential=prior_flux_state.potential,
            actual=published_actual,
        )

        # Expose posterior demand as next-interval diagnostic
        posterior_demand = PotentialWaterFlux(
            et0_mm=et0_res.et0_mm_day,
            kcb=kcb,
            ke=ke,
        )

        # 9. Physical Water Limitation Evaluation with uncertainty propagation
        limitation_state = WaterLimitationEngine.evaluate_limitation(
            root_zone=final_root_zone,
            potential_flux=published_flux_state.potential,
            et0_uncertainty_sigma=et0_res.uncertainty.total_sigma,
        )

        # 10. Historical Hydraulic Stress Memory Accumulation
        vpd_val = et0_res.vapor_pressure_deficit_kpa
        hydraulic_memory = HydraulicStressMemoryState.step_memory(
            prev_memory=previous_hydraulic_memory,
            current_ks=final_root_zone.stress_factor_ks,
            current_tdeficit_mm=published_flux_state.actual.transpiration_deficit_mm,
            current_vpd_kpa=vpd_val,
        )

        # 11. Weather Ensemble Limitation Forecast with coupled calibrated posterior soil uncertainty
        lim_forecast = EnsembleForecastEngine.simulate_depletion_forecast(
            current_root_zone=final_root_zone,
            kcb=kcb,
            ke=ke,
            weather_ensemble=weather_ensemble,
            soil_uncertainty_sigma=_posterior_soil_sigma,
        )

        # 12. MPC Prescriptive Irrigation Optimization
        decision = MPCPrescriptiveOptimizer.optimize_irrigation_schedule(
            root_zone=final_root_zone,
            potential_flux=published_flux_state.potential,
            limitation_forecast=lim_forecast,
            method=irrigation_method,
            constraints=irrigation_constraints,
            objective=irrigation_objective,
        )

        # Determine physical authority level
        has_observed_probe = (
            "IN_SITU_PROBE_TDR" in assim_diag.assimilated_sensor_sources
            and not any(term in s.upper() for s in getattr(soil_observations, "provenance_sources", []) for term in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED"))
            and not any(term in s.upper() for s in assim_diag.assimilated_sensor_sources for term in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED"))
        )
        if has_observed_probe:
            authority = WaterPhysicsAuthority.OBSERVED
        elif assim_diag.observations_assimilated_count > 0 or vegetation_state:
            authority = WaterPhysicsAuthority.ASSIMILATED
        else:
            authority = WaterPhysicsAuthority.MODELLED

        # 13. Canonical WaterState Construction with calibrated posterior uncertainty
        posterior_uncertainty = WaterUncertaintyBudget(
            sensor_sigma=et0_res.uncertainty.sensor_sigma,
            soil_sigma=_posterior_soil_sigma,
            weather_sigma=et0_res.uncertainty.weather_sigma,
            model_sigma=et0_res.uncertainty.model_sigma,
        )

        serialized_closure_err = flux_receipt.water_closure_error_mm if flux_receipt else mass_balance_err

        water_state = WaterStateFactory.create_water_state(
            plot_id=plot_id,
            timestamp=timestamp,
            soil_water=posterior_soil,
            fluxes=published_flux_state,
            root_zone=final_root_zone,
            hydraulic_memory=hydraulic_memory,
            limitation_forecast=lim_forecast,
            assimilation_diagnostic=assim_diag,
            vegetation_boundary=vegetation_state,
            thermal_observation=canopy_temperature_state,
            atmospheric_quality=et0_res.atmospheric_quality,
            active_decision=decision,
            physics_authority=authority,
            hydrology_mode=solver_decision.hydrology_mode,
            solver_fidelity=solver_decision.solver_fidelity,
            mass_balance_error_mm=serialized_closure_err,
            uncertainty=posterior_uncertainty,
            transition_receipt=flux_receipt,
            analysis_receipt=analysis_receipt,
            posterior_demand=posterior_demand,
        )

        # 14. Hydrological Feedback Receipt to Layer 2
        avail_ratio = (
            (final_root_zone.total_available_water_mm - final_root_zone.root_zone_depletion_mm)
            / max(1.0, final_root_zone.total_available_water_mm)
        )
        feedback_to_l2 = Layer3HydrologicalConstraintReceipt(
            plot_id=plot_id,
            timestamp=timestamp,
            transpiration_constraint_factor=final_root_zone.stress_factor_ks,
            transpiration_deficit_mm=published_flux_state.actual.transpiration_deficit_mm,
            soil_water_availability_ratio=round(avail_ratio, 3),
            root_zone_depletion_fraction=round(final_root_zone.root_zone_depletion_mm / max(1.0, final_root_zone.total_available_water_mm), 3),
            ks_uncertainty_sigma=final_root_zone.ks_uncertainty_sigma,
        )

        return water_state, feedback_to_l2
