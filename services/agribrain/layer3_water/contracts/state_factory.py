"""
Layer 3.0 Canonical Water State Factory
Guarantees physical bounds, mass conservation, Van Genuchten hydraulic potential, and valid vertical profiles.
"""

import math
from datetime import datetime
from typing import List, Optional, Dict, Any

from layer2_contracts.state_contracts import VegetationState, InferenceProvenance
from layer3_water.contracts.authority import WaterPhysicsAuthority, HydrologyMode, SolverFidelity
from layer3_water.contracts.water_uncertainty import WaterUncertaintyBudget, WaterPhysicsConfidence
from layer3_water.contracts.atmospheric_state import AtmosphericInputQuality, CanopyTemperatureState
from layer3_water.contracts.irrigation_state import WaterDecision
from layer3_water.contracts.water_state import (
    InfiltrationState,
    SoilEvaporationState,
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
)


class WaterStateFactory:
    """Canonical builder ensuring strict invariant enforcement for Layer 3 contracts."""

    @staticmethod
    def create_soil_water_state(
        layer_depths_cm: List[float],
        theta_profile: List[float],
        field_capacity_profile: List[float],
        wilting_point_profile: List[float],
        saturation_profile: List[float],
        residual_profile: List[float],
        hydraulic_conductivity_profile: Optional[List[float]] = None,
        van_genuchten_alpha: Optional[List[float]] = None,
        van_genuchten_n: Optional[List[float]] = None,
        infiltration: Optional[InfiltrationState] = None,
        evaporation_state: Optional[SoilEvaporationState] = None,
        parameter_provenance: str = "TEXTURE_PRIOR",
    ) -> SoilWaterState:
        """Create and validate vertical soil moisture profile and compute Van Genuchten suction potentials."""
        if not layer_depths_cm or not isinstance(layer_depths_cm, (list, tuple)):
            raise ValueError("layer_depths_cm must be a non-empty list of depths")
        for i, d in enumerate(layer_depths_cm):
            if not (isinstance(d, (int, float)) and math.isfinite(d) and d > 0.0):
                raise ValueError(f"Layer {i} depth {d} must be a finite positive number (> 0.0)")
            if i > 0 and d <= layer_depths_cm[i - 1]:
                raise ValueError(
                    f"Layer depths must be strictly monotonically increasing: layer {i} ({d}) <= layer {i-1} ({layer_depths_cm[i-1]})"
                )

        n_layers = len(layer_depths_cm)
        for name, prof in [
            ("theta_profile", theta_profile),
            ("field_capacity_profile", field_capacity_profile),
            ("wilting_point_profile", wilting_point_profile),
            ("saturation_profile", saturation_profile),
            ("residual_profile", residual_profile),
        ]:
            if not isinstance(prof, (list, tuple)) or len(prof) != n_layers:
                raise ValueError(f"{name} length must match layer count {n_layers}")

        if hydraulic_conductivity_profile is not None:
            if not isinstance(hydraulic_conductivity_profile, (list, tuple)) or len(hydraulic_conductivity_profile) != n_layers:
                raise ValueError(f"hydraulic_conductivity_profile length must match layer count {n_layers}")
        if van_genuchten_alpha is not None:
            if not isinstance(van_genuchten_alpha, (list, tuple)) or len(van_genuchten_alpha) != n_layers:
                raise ValueError(f"van_genuchten_alpha length must match layer count {n_layers}")
        if van_genuchten_n is not None:
            if not isinstance(van_genuchten_n, (list, tuple)) or len(van_genuchten_n) != n_layers:
                raise ValueError(f"van_genuchten_n length must match layer count {n_layers}")

        # Validate physical boundaries per layer
        for i in range(n_layers):
            th_r = residual_profile[i]
            th_wp = wilting_point_profile[i]
            th_fc = field_capacity_profile[i]
            th_s = saturation_profile[i]
            th = theta_profile[i]

            for val_name, val in [
                ("residual", th_r),
                ("wilting_point", th_wp),
                ("field_capacity", th_fc),
                ("saturation", th_s),
                ("theta", th),
            ]:
                if not (isinstance(val, (int, float)) and math.isfinite(val)):
                    raise ValueError(f"Layer {i} {val_name} must be a finite number")

            if not (0.0 <= th_r <= th_wp <= th_fc <= th_s <= 1.0):
                raise ValueError(
                    f"Layer {i} physical retention ordering violated: theta_r({th_r}) <= theta_wp({th_wp}) <= theta_fc({th_fc}) <= theta_s({th_s})"
                )
            if th_s <= th_r + 1e-4:
                raise ValueError(
                    f"Layer {i} has degenerate saturation/residual interval: theta_s({th_s}) <= theta_r({th_r}) + 1e-4"
                )
            if not (th_r <= th <= th_s + 1e-4):
                raise ValueError(
                    f"Layer {i} moisture content {th} out of physical bounds [{th_r}, {th_s}]"
                )

        ks_prof = hydraulic_conductivity_profile or [25.0] * n_layers
        for i, ks in enumerate(ks_prof):
            if not (isinstance(ks, (int, float)) and math.isfinite(ks) and ks > 0.0):
                raise ValueError(f"Layer {i} hydraulic conductivity {ks} must be a finite strictly positive number (> 0.0)")

        vg_alpha = van_genuchten_alpha or [0.03] * n_layers
        for i, a in enumerate(vg_alpha):
            if not (isinstance(a, (int, float)) and math.isfinite(a) and a > 0.0):
                raise ValueError(f"Layer {i} van Genuchten alpha {a} must be a finite strictly positive number (> 0.0)")

        vg_n = van_genuchten_n or [1.5] * n_layers
        for i, n_val in enumerate(vg_n):
            if not (isinstance(n_val, (int, float)) and math.isfinite(n_val) and n_val > 1.0):
                raise ValueError(f"Layer {i} van Genuchten n {n_val} must be a finite number strictly greater than 1.0 (> 1.0)")

        vg_m = [round(1.0 - 1.0 / n_val, 4) for n_val in vg_n]

        valid_provenance = {"TEXTURE_PRIOR", "IN_SITU_CALIBRATED", "LAB_MEASURED", "PEDOTRANSFER"}
        prov = parameter_provenance.upper() if isinstance(parameter_provenance, str) else "TEXTURE_PRIOR"
        if prov not in valid_provenance:
            prov = "TEXTURE_PRIOR"

        # Compute matric suction h(cm) and matric potential psi_m(MPa) via Van Genuchten retention inversion
        matric_pot = []
        k_unsat = []
        for i in range(n_layers):
            th = theta_profile[i]
            th_r = residual_profile[i]
            th_s = saturation_profile[i]
            alpha = max(1e-4, vg_alpha[i])
            n_val = max(1.05, vg_n[i])
            m_val = max(0.05, vg_m[i])
            ks = ks_prof[i]
            
            # Effective saturation Se ∈ [0.001, 0.999]
            se = max(0.001, min(0.999, (th - th_r) / max(1e-4, th_s - th_r)))
            
            # Matric suction h = (1 / alpha) * (Se^(-1/m) - 1)^(1/n) in cm
            h_cm = (1.0 / alpha) * ((se ** (-1.0 / m_val) - 1.0) ** (1.0 / n_val))
            # 1 cm H2O = 9.80665e-5 MPa ≈ 1 / 10197 MPa
            psi_mpa = -round(h_cm / 10197.0, 4)
            matric_pot.append(psi_mpa)
            
            # Mualem-Van Genuchten unsaturated hydraulic conductivity K(Se)
            k_u = ks * math.sqrt(se) * ((1.0 - (1.0 - se ** (1.0 / m_val)) ** m_val) ** 2)
            k_unsat.append(round(max(0.0, k_u), 4))

        return SoilWaterState(
            layer_depths_cm=layer_depths_cm,
            theta_profile=[round(v, 4) for v in theta_profile],
            field_capacity_profile=[round(v, 4) for v in field_capacity_profile],
            wilting_point_profile=[round(v, 4) for v in wilting_point_profile],
            saturation_profile=[round(v, 4) for v in saturation_profile],
            residual_profile=[round(v, 4) for v in residual_profile],
            hydraulic_conductivity_profile=[round(v, 2) for v in ks_prof],
            van_genuchten_alpha=[round(v, 4) for v in vg_alpha],
            van_genuchten_n=[round(v, 4) for v in vg_n],
            van_genuchten_m=vg_m,
            matric_potential_profile_mpa=matric_pot,
            unsaturated_conductivity_profile_cm_day=k_unsat,
            infiltration=infiltration,
            evaporation_state=evaporation_state,
            parameter_provenance=prov,
        )

    @staticmethod
    def create_root_zone_water_state(
        root_depth_m: float,
        layer_depths_cm: List[float],
        theta_profile: List[float],
        field_capacity_profile: List[float],
        wilting_point_profile: List[float],
        base_depletion_fraction_p: float = 0.50,
        etp_mm_day: float = 5.0,
        root_fraction_profile: Optional[List[float]] = None,
        soil_uncertainty_sigma: float = 0.04,
    ) -> RootZoneWaterState:
        """Calculate root-zone TAW, RAW, depletion Dr, root uptake weighting U(z), and stress factor Ks."""
        if not (isinstance(root_depth_m, (int, float)) and math.isfinite(root_depth_m) and root_depth_m > 0.0):
            raise ValueError(f"root_depth_m ({root_depth_m}) must be a finite strictly positive number (> 0.0)")
        if not layer_depths_cm or not isinstance(layer_depths_cm, (list, tuple)):
            raise ValueError("layer_depths_cm must be a non-empty list of depths")
        for i, d in enumerate(layer_depths_cm):
            if not (isinstance(d, (int, float)) and math.isfinite(d) and d > 0.0):
                raise ValueError(f"Layer {i} depth {d} must be a finite positive number (> 0.0)")
            if i > 0 and d <= layer_depths_cm[i - 1]:
                raise ValueError(
                    f"Layer depths must be strictly monotonically increasing: layer {i} ({d}) <= layer {i-1} ({layer_depths_cm[i-1]})"
                )

        n_layers = len(layer_depths_cm)
        for name, prof in [
            ("theta_profile", theta_profile),
            ("field_capacity_profile", field_capacity_profile),
            ("wilting_point_profile", wilting_point_profile),
        ]:
            if not isinstance(prof, (list, tuple)) or len(prof) != n_layers:
                raise ValueError(f"{name} length must match layer count {n_layers}")

        for i in range(n_layers):
            th = theta_profile[i]
            fc = field_capacity_profile[i]
            wp = wilting_point_profile[i]
            for pname, pval in [("theta", th), ("field_capacity", fc), ("wilting_point", wp)]:
                if not (isinstance(pval, (int, float)) and math.isfinite(pval)):
                    raise ValueError(f"Layer {i} {pname} must be a finite number")
            if not (0.0 <= wp <= fc <= 1.0):
                raise ValueError(f"Layer {i} wilting point ({wp}) cannot exceed field capacity ({fc}) in [0, 1]")

        root_depth_cm = root_depth_m * 100.0
        
        # Calculate layer root density fractions R_i if not explicitly supplied
        if root_fraction_profile is None:
            raw_r = []
            prev_d = 0.0
            for d in layer_depths_cm:
                if prev_d >= root_depth_cm:
                    raw_r.append(0.0)
                else:
                    active_top = prev_d
                    active_bot = min(d, root_depth_cm)
                    frac = math.exp(-2.5 * active_top / root_depth_cm) - math.exp(-2.5 * active_bot / root_depth_cm)
                    raw_r.append(max(0.0, frac))
                prev_d = d
            tot_r = sum(raw_r)
            root_fracs = [round(r / tot_r, 4) if tot_r > 0 else (1.0 / n_layers) for r in raw_r]
        else:
            if len(root_fraction_profile) != n_layers or abs(sum(root_fraction_profile) - 1.0) > 1e-3:
                raise ValueError(f"Root fraction profile must sum to 1.0 across {n_layers} layers")
            root_fracs = [round(v, 4) for v in root_fraction_profile]

        # Adjust depletion fraction p for evaporative demand: p = p_base + 0.04 * (5.0 - ETp)
        adj_p = round(min(0.85, max(0.10, base_depletion_fraction_p + 0.04 * (5.0 - etp_mm_day))), 3)

        # Calculate layer-by-layer Feddes stress modifiers alpha(theta_i) and uptake distribution U_i = R_i * alpha(theta_i)
        feddes_alpha = []
        raw_uptake = []
        taw_mm = 0.0
        current_water_mm = 0.0
        fc_water_mm = 0.0
        
        prev_d = 0.0
        for i, d in enumerate(layer_depths_cm):
            th = theta_profile[i]
            fc = field_capacity_profile[i]
            wp = wilting_point_profile[i]
            
            # Feddes threshold: optimal above theta_lim = wp + (1 - p) * (fc - wp)
            th_lim = wp + (1.0 - adj_p) * (fc - wp) if fc > wp else wp
            
            if th >= th_lim:
                alpha_i = 1.0
            elif th <= wp or fc <= wp:
                alpha_i = 0.0
            else:
                alpha_i = max(0.0, min(1.0, (th - wp) / max(1e-4, th_lim - wp)))
                
            feddes_alpha.append(round(alpha_i, 4))
            
            if prev_d < root_depth_cm:
                active_thickness_mm = (min(d, root_depth_cm) - prev_d) * 10.0
                layer_taw = (fc - wp) * active_thickness_mm
                taw_mm += layer_taw
                fc_water_mm += fc * active_thickness_mm
                current_water_mm += th * active_thickness_mm
                
                # Active uptake potential in layer: U_i_raw = R_i * alpha_i
                raw_uptake.append(root_fracs[i] * max(0.01, alpha_i))
            else:
                raw_uptake.append(0.0)
            prev_d = d
            
        tot_uptake = sum(raw_uptake)
        uptake_dist = [round(u / tot_uptake, 4) if tot_uptake > 0 else (1.0 / n_layers) for u in raw_uptake]
        taw_mm = max(1.0, round(taw_mm, 2))
        raw_mm = round(adj_p * taw_mm, 2)
        
        # Root zone depletion Dr (mm) = FC_storage - Current_storage (strictly derived from soil moisture state)
        dr_mm = max(0.0, min(taw_mm, round(fc_water_mm - current_water_mm, 2)))
        
        # Piecewise linear stress reduction Ks
        if dr_mm <= raw_mm:
            ks = 1.0
        elif dr_mm >= taw_mm:
            ks = 0.0
        else:
            ks = round((taw_mm - dr_mm) / (taw_mm - raw_mm), 3)

        return RootZoneWaterState(
            root_depth_m=round(root_depth_m, 2),
            root_fraction_profile=root_fracs,
            root_accessibility_profile=root_fracs,
            root_uptake_distribution_profile=uptake_dist,
            root_extraction_modifier_profile=feddes_alpha,
            total_available_water_mm=taw_mm,
            depletion_fraction_p=adj_p,
            readily_available_water_mm=raw_mm,
            root_zone_depletion_mm=dr_mm,
            stress_factor_ks=ks,
            ks_uncertainty_sigma=round(soil_uncertainty_sigma * 1.2, 4),
        )

    @staticmethod
    def create_flux_state(
        et0_mm: float,
        kcb: float,
        ke: float,
        ks: float,
        precipitation_mm: float = 0.0,
        irrigation_mm: float = 0.0,
        deep_drainage_mm: float = 0.0,
        runoff_mm: float = 0.0,
        capillary_rise_mm: float = 0.0,
    ) -> WaterFluxState:
        """Construct coupled potential and actual water flux state."""
        pot = PotentialWaterFlux(
            et0_mm=round(max(0.0, et0_mm), 2),
            kcb=round(max(0.0, kcb), 3),
            ke=round(max(0.0, ke), 3),
        )
        
        tpot = pot.tpot_mm
        tact = round(ks * tpot, 2)
        esact = pot.espot_mm
        eta = round(tact + esact, 2)
        tdef = round(max(0.0, tpot - tact), 2)
        
        act = ActualWaterFlux(
            ks=round(min(1.0, max(0.0, ks)), 3),
            precipitation_mm=round(max(0.0, precipitation_mm), 2),
            irrigation_mm=round(max(0.0, irrigation_mm), 2),
            deep_drainage_mm=round(max(0.0, deep_drainage_mm), 2),
            runoff_mm=round(max(0.0, runoff_mm), 2),
            capillary_rise_mm=round(max(0.0, capillary_rise_mm), 2),
            actual_transpiration_mm=tact,
            actual_soil_evaporation_mm=esact,
            actual_eta_mm=eta,
            transpiration_deficit_mm=tdef,
        )
        
        return WaterFluxState(potential=pot, actual=act)

    @classmethod
    def create_water_state(
        cls,
        plot_id: str,
        timestamp: datetime,
        soil_water: SoilWaterState,
        fluxes: WaterFluxState,
        root_zone: RootZoneWaterState,
        hydraulic_memory: Optional[HydraulicStressMemoryState] = None,
        limitation_forecast: Optional[WaterLimitationForecast] = None,
        assimilation_diagnostic: Optional[AssimilationDiagnostic] = None,
        vegetation_boundary: Optional[VegetationState] = None,
        thermal_observation: Optional[CanopyTemperatureState] = None,
        atmospheric_quality: Optional[AtmosphericInputQuality] = None,
        active_decision: Optional[WaterDecision] = None,
        physics_authority: WaterPhysicsAuthority = WaterPhysicsAuthority.MODELLED,
        hydrology_mode: HydrologyMode = HydrologyMode.FAO56_LAYERED_BUCKET,
        solver_fidelity: SolverFidelity = SolverFidelity.EMPIRICAL_BUCKET,
        mass_balance_error_mm: float = 0.0,
        uncertainty: Optional[WaterUncertaintyBudget] = None,
        data_health_score: float = 1.0,
        transition_receipt: Optional[IntervalFluxReceipt] = None,
        analysis_receipt: Optional[AnalysisIncrementReceipt] = None,
        posterior_demand: Optional[PotentialWaterFlux] = None,
    ) -> WaterState:
        """Construct canonical unified WaterState (X_t^L3)."""
        forecast = limitation_forecast or WaterLimitationForecast(
            forecast_days=7,
            projected_depletion_mm=[root_zone.root_zone_depletion_mm] * 7,
            days_until_critical_depletion=None if root_zone.stress_factor_ks == 1.0 else 0,
            water_limitation_probability_trajectory=[round(1.0 - root_zone.stress_factor_ks, 3)] * 7,
            transpiration_deficit_trajectory=[fluxes.actual.transpiration_deficit_mm] * 7,
            ensemble_spread_mm=[round(root_zone.total_available_water_mm * 0.08, 2)] * 7,
        )
        
        unc = uncertainty or WaterUncertaintyBudget()
        atmos = atmospheric_quality or AtmosphericInputQuality()
        confidence = WaterPhysicsConfidence.compute(
            mass_balance_error_mm=mass_balance_error_mm,
            solver_fidelity=solver_fidelity,
            weather_quality=atmos.overall_confidence,
        )
        
        memory = hydraulic_memory or HydraulicStressMemoryState.step_memory(
            prev_memory=None,
            current_ks=root_zone.stress_factor_ks,
            current_tdeficit_mm=fluxes.actual.transpiration_deficit_mm,
            current_vpd_kpa=1.5,
        )

        return WaterState(
            plot_id=plot_id,
            timestamp=timestamp,
            soil_water=soil_water,
            fluxes=fluxes,
            root_zone=root_zone,
            hydraulic_memory=memory,
            limitation_forecast=forecast,
            assimilation_diagnostic=assimilation_diagnostic,
            vegetation_boundary=vegetation_boundary,
            thermal_observation=thermal_observation,
            atmospheric_quality=atmos,
            active_decision=active_decision,
            physics_authority=physics_authority,
            hydrology_mode=hydrology_mode,
            solver_fidelity=solver_fidelity,
            mass_balance_error_mm=round(mass_balance_error_mm, 4),
            water_confidence=confidence,
            data_health_score=data_health_score,
            uncertainty=unc,
            provenance=InferenceProvenance(
                model_version="3.2.0",
                crop_profile_version="4.0.0",
                data_sources=["FAO56_DUAL_KC", "SOIL_PROFILE_HYDRAULICS", "L2_VEGETATION_STATE"],
                observation_count=1,
                authority_level=vegetation_boundary.crop_authority if vegetation_boundary else "TRANSFER",
                execution_timestamp=timestamp,
            ),
            transition_receipt=transition_receipt,
            analysis_receipt=analysis_receipt,
            posterior_demand=posterior_demand,
        )
