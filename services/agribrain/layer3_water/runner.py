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
    WaterFluxState,
    RootZoneWaterState,
    WaterLimitationForecast,
    HydraulicStressMemoryState,
    AssimilationDiagnostic,
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
        et0_res = PenmanMonteithET0.calculate_et0(
            t_max_c=t_max,
            t_min_c=t_min,
            net_radiation_mj_m2=rn,
            wind_speed_2m_m_s=wind,
            dew_point_c=dew_point,
            rh_max_pct=rh_max,
            rh_min_pct=rh_min,
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
        top_storage = current_soil.theta_profile[0] * 100.0
        
        ke, evap_state = DualKcEngine.calculate_soil_evaporation_ke(
            kcb=kcb,
            kc_max=kc_max,
            fvc=fvc,
            surface_storage_mm=top_storage,
            days_since_wetting=days_since_wetting,
        )

        pot_etp = (kcb + ke) * et0_res.et0_mm_day

        # 5. Root Zone Availability & Stress Reduction Ks
        root_zone = RootZoneAvailabilityEngine.evaluate_root_zone(
            soil_state=current_soil,
            root_depth_m=root_depth_m,
            etp_mm_day=pot_etp,
        )

        # 6. Dual Flux Partitioning
        flux_state = DualKcEngine.partition_evapotranspiration(
            et0_mm=et0_res.et0_mm_day,
            kcb=kcb,
            ke=ke,
            ks=root_zone.stress_factor_ks,
            precipitation_mm=precip,
            irrigation_mm=irrigation_applied_mm,
        )

        # 7. Multi-Layer Soil Water Balance Propagation (Prognostic Prior X^-)
        prognostic_soil, actual_infil, runoff, deep_drainage, mass_balance_err = LayeredWaterBalanceEngine.step_water_balance(
            prev_soil=current_soil,
            root_zone=root_zone,
            precipitation_mm=precip,
            irrigation_mm=irrigation_applied_mm,
            actual_transpiration_mm=flux_state.actual.actual_transpiration_mm,
            actual_soil_evaporation_mm=flux_state.actual.actual_soil_evaporation_mm,
            days_since_wetting=days_since_wetting,
        )

        # 8. Data Assimilation Update (Posterior X^+ = X^- + K(y - H X^-))
        posterior_soil, assim_diag = WaterStateAssimilator.assimilate_observations(
            prior_soil=prognostic_soil,
            observations=soil_observations,
            background_uncertainty_sigma=et0_res.uncertainty.soil_sigma,
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

        # Assimilation changes the root-zone stress factor.  Publish fluxes
        # computed from that posterior state rather than stale prior Ks.
        flux_state = DualKcEngine.partition_evapotranspiration(
            et0_mm=et0_res.et0_mm_day,
            kcb=kcb,
            ke=ke,
            ks=final_root_zone.stress_factor_ks,
            precipitation_mm=precip,
            irrigation_mm=irrigation_applied_mm,
            deep_drainage_mm=deep_drainage,
            runoff_mm=runoff,
        )

        # 9. Physical Water Limitation Evaluation with uncertainty propagation
        limitation_state = WaterLimitationEngine.evaluate_limitation(
            root_zone=final_root_zone,
            potential_flux=flux_state.potential,
            et0_uncertainty_sigma=et0_res.uncertainty.total_sigma,
        )

        # 10. Historical Hydraulic Stress Memory Accumulation
        vpd_val = et0_res.vapor_pressure_deficit_kpa
        hydraulic_memory = HydraulicStressMemoryState.step_memory(
            prev_memory=previous_hydraulic_memory,
            current_ks=final_root_zone.stress_factor_ks,
            current_tdeficit_mm=flux_state.actual.transpiration_deficit_mm,
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
            potential_flux=flux_state.potential,
            limitation_forecast=lim_forecast,
            method=irrigation_method,
            constraints=irrigation_constraints,
            objective=irrigation_objective,
        )

        # Determine physical authority level
        if soil_observations and soil_observations.soil_probe_moisture_profile:
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

        water_state = WaterStateFactory.create_water_state(
            plot_id=plot_id,
            timestamp=timestamp,
            soil_water=posterior_soil,
            fluxes=flux_state,
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
            mass_balance_error_mm=mass_balance_err,
            uncertainty=posterior_uncertainty,
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
            transpiration_deficit_mm=flux_state.actual.transpiration_deficit_mm,
            soil_water_availability_ratio=round(avail_ratio, 3),
            root_zone_depletion_fraction=round(final_root_zone.root_zone_depletion_mm / max(1.0, final_root_zone.total_available_water_mm), 3),
            ks_uncertainty_sigma=final_root_zone.ks_uncertainty_sigma,
        )

        return water_state, feedback_to_l2
