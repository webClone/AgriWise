"""
Layer 3.0 Multi-Layer Soil Water Balance Engine
Simulates infiltration, vertical percolation cascade, Feddes root water extraction U(z), and drainage.
"""

from typing import List, Tuple, Optional
import math

from layer3_water.contracts.water_state import (
    InfiltrationState,
    SoilEvaporationState,
    SoilWaterState,
    RootZoneWaterState,
    IntervalFluxReceipt,
)
from layer3_water.contracts.state_factory import WaterStateFactory


class StepWaterBalanceResult(tuple):
    """5-element tuple backward-compatible result providing access to transition receipt."""

    def __new__(
        cls,
        updated_soil: SoilWaterState,
        actual_infil: float,
        runoff: float,
        deep_drainage: float,
        mass_balance_error: float,
        receipt: Optional[IntervalFluxReceipt] = None,
    ):
        instance = super().__new__(
            cls, (updated_soil, actual_infil, runoff, deep_drainage, mass_balance_error)
        )
        instance._receipt = receipt
        return instance

    @property
    def updated_soil(self) -> SoilWaterState:
        return self[0]

    @property
    def actual_infil(self) -> float:
        return self[1]

    @property
    def runoff(self) -> float:
        return self[2]

    @property
    def deep_drainage(self) -> float:
        return self[3]

    @property
    def mass_balance_error(self) -> float:
        return self[4]

    @property
    def receipt(self) -> Optional[IntervalFluxReceipt]:
        return getattr(self, "_receipt", None)


class LayeredWaterBalanceEngine:
    """Multi-layer vertical soil water balance propagator."""

    @classmethod
    def step_water_balance(
        cls,
        prev_soil: SoilWaterState,
        root_zone: RootZoneWaterState,
        precipitation_mm: float,
        irrigation_mm: float,
        actual_transpiration_mm: float,
        actual_soil_evaporation_mm: float,
        capillary_rise_mm: float = 0.0,
        days_since_wetting: int = 0,
        fraction_wetted: Optional[float] = None,
    ) -> StepWaterBalanceResult:
        """Propagate multi-layer soil water state through daily hydrological flux cycle.
        
        Returns:
            StepWaterBalanceResult: 5-element tuple (updated_soil, actual_infil, runoff, deep_drainage, mass_balance_error)
            with .receipt providing IntervalFluxReceipt.
        """
        if not prev_soil.layer_depths_cm:
            raise ValueError("layer_depths_cm must be a non-empty list")
        for i, d in enumerate(prev_soil.layer_depths_cm):
            if not (isinstance(d, (int, float)) and math.isfinite(d) and d > 0.0):
                raise ValueError(f"Layer {i} depth {d} must be a finite positive number (> 0.0)")
            if i > 0 and d <= prev_soil.layer_depths_cm[i - 1]:
                raise ValueError(
                    f"Layer depths must be strictly monotonically increasing: layer {i} ({d}) <= layer {i-1} ({prev_soil.layer_depths_cm[i-1]})"
                )

        # CEB05: Validate all hydrological fluxes as finite, non-boolean real scalars >= 0.0
        for name, val in [
            ("precipitation_mm", precipitation_mm),
            ("irrigation_mm", irrigation_mm),
            ("actual_transpiration_mm", actual_transpiration_mm),
            ("actual_soil_evaporation_mm", actual_soil_evaporation_mm),
            ("capillary_rise_mm", capillary_rise_mm),
        ]:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be a finite real number, got {val!r}")
            if val < 0.0:
                raise ValueError(f"{name} cannot be negative, got {val}")

        n_layers = len(prev_soil.layer_depths_cm)
        layer_thickness_mm = []
        prev_d = 0.0
        for d in prev_soil.layer_depths_cm:
            thickness = (d - prev_d) * 10.0
            if thickness <= 0.0:
                raise ValueError(f"Layer thickness must be positive: {thickness}")
            layer_thickness_mm.append(thickness)
            prev_d = d

        # Current water storage per layer (mm)
        layer_storage_mm = [
            round(th * thickness, 2)
            for th, thickness in zip(prev_soil.theta_profile, layer_thickness_mm)
        ]
        sat_storage_mm = [
            round(th_s * thickness, 2)
            for th_s, thickness in zip(prev_soil.saturation_profile, layer_thickness_mm)
        ]
        fc_storage_mm = [
            round(th_fc * thickness, 2)
            for th_fc, thickness in zip(prev_soil.field_capacity_profile, layer_thickness_mm)
        ]
        wp_storage_mm = [
            round(th_wp * thickness, 2)
            for th_wp, thickness in zip(prev_soil.wilting_point_profile, layer_thickness_mm)
        ]
        res_storage_mm = [
            round(th_r * thickness, 2)
            for th_r, thickness in zip(prev_soil.residual_profile, layer_thickness_mm)
        ]

        # CEB05: Explicit initial surface / depression storage validation
        prev_infil = getattr(prev_soil, "infiltration", None)
        raw_init_surface = getattr(prev_infil, "surface_storage_mm", 0.0) if prev_infil else 0.0
        raw_max_surface = getattr(prev_infil, "max_surface_storage_mm", 0.0) if prev_infil else 0.0
        for name, val in [("surface_storage_mm", raw_init_surface), ("max_surface_storage_mm", raw_max_surface)]:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be a finite real number, got {val!r}")
            if val < 0.0:
                raise ValueError(f"{name} cannot be negative, got {val}")
        init_surface_storage_mm = float(raw_init_surface)
        max_surface_storage_mm = float(raw_max_surface)
        if init_surface_storage_mm > max_surface_storage_mm:
            raise ValueError(f"Initial surface storage ({init_surface_storage_mm}) cannot exceed max capacity ({max_surface_storage_mm})")

        # 1. Surface Infiltration & Runoff Partitioning
        # Total water available at the surface (precipitation + irrigation + initial surface storage)
        total_surface_water = precipitation_mm + irrigation_mm + init_surface_storage_mm
        # Topsoil infiltration capacity: K_sat scaled by available pore space
        top_avail_pore = max(0.0, sat_storage_mm[0] - layer_storage_mm[0])
        # Daily infiltration capacity based on hydraulic conductivity (mm/day)
        top_ks_mm_day = prev_soil.hydraulic_conductivity_profile[0] * 10.0
        infil_capacity = min(top_avail_pore + top_ks_mm_day, top_ks_mm_day * 1.5)

        if total_surface_water <= infil_capacity:
            gross_infil = total_surface_water
            initial_surface_runoff = 0.0
        else:
            gross_infil = infil_capacity
            initial_surface_runoff = round(total_surface_water - infil_capacity, 6)

        # Surface ponding storage absorbs initial surface excess up to max_surface_storage_mm
        if max_surface_storage_mm > 0.0:
            surf_stored_initial = min(initial_surface_runoff, max_surface_storage_mm)
            surface_excess_runoff = initial_surface_runoff - surf_stored_initial
            current_surface_storage = surf_stored_initial
        else:
            surface_excess_runoff = initial_surface_runoff
            current_surface_storage = 0.0

        # 2. Add Infiltrated Water to Top Layer and Inflow Percolation Cascade
        percolating_flux = gross_infil
        new_storage = list(layer_storage_mm)

        for i in range(n_layers):
            new_storage[i] += percolating_flux
            percolating_flux = 0.0

            # Excess above Field Capacity drains downward (percolation)
            if new_storage[i] > fc_storage_mm[i]:
                excess = new_storage[i] - fc_storage_mm[i]
                # Drainage rate governed by hydraulic conductivity
                layer_ks_mm = prev_soil.hydraulic_conductivity_profile[i] * 10.0
                drainage_step = min(excess, layer_ks_mm)
                new_storage[i] -= drainage_step
                percolating_flux = drainage_step

        deep_drainage = round(percolating_flux, 6)

        # 3. Upward Perched Saturation Routing (Backflow from impeding layers)
        # When lower layers exceed saturation due to low conductivity, excess water perches upward
        for i in range(n_layers - 1, 0, -1):
            if new_storage[i] > sat_storage_mm[i]:
                perched_excess = new_storage[i] - sat_storage_mm[i]
                new_storage[i] = sat_storage_mm[i]
                new_storage[i - 1] += perched_excess

        # Exfiltration / return flow emerging at the soil surface from perched saturation
        if new_storage[0] > sat_storage_mm[0]:
            return_flow_mm = new_storage[0] - sat_storage_mm[0]
            new_storage[0] = sat_storage_mm[0]
        else:
            return_flow_mm = 0.0

        # Partition return flow between surface depression storage and return flow runoff
        if max_surface_storage_mm > 0.0:
            avail_surface_space = max(0.0, max_surface_storage_mm - current_surface_storage)
            stored_return = min(return_flow_mm, avail_surface_space)
            final_surface_storage_mm = current_surface_storage + stored_return
            return_flow_runoff_mm = return_flow_mm - stored_return
        else:
            final_surface_storage_mm = current_surface_storage
            return_flow_runoff_mm = return_flow_mm

        # Net infiltration entering and retained in soil column
        net_infil = gross_infil - return_flow_mm
        total_runoff = surface_excess_runoff + return_flow_runoff_mm

        # 4. Topsoil Evaporation Extraction (Es_act)
        # Surface ponding evaporates first, then topsoil layer bounded by residual water
        evap_from_surface = min(actual_soil_evaporation_mm, final_surface_storage_mm)
        final_surface_storage_mm = round(final_surface_storage_mm - evap_from_surface, 6)
        remaining_soil_evap = actual_soil_evaporation_mm - evap_from_surface

        allowable_soil_evap = max(0.0, new_storage[0] - res_storage_mm[0])
        actual_top_evap = min(remaining_soil_evap, allowable_soil_evap)
        new_storage[0] = round(new_storage[0] - actual_top_evap, 6)
        total_evap = round(evap_from_surface + actual_top_evap, 6)

        # 5. Layer-by-Layer Root Water Extraction U(z) via Feddes weighting
        # Plant roots cannot extract below permanent wilting point (WP)
        uptake_fractions = root_zone.root_uptake_distribution_profile
        total_plant_extracted = 0.0
        for i in range(n_layers):
            if i < len(uptake_fractions):
                layer_uptake = round(uptake_fractions[i] * actual_transpiration_mm, 2)
                allowable_plant_extract = max(0.0, new_storage[i] - wp_storage_mm[i])
                actual_layer_uptake = min(layer_uptake, allowable_plant_extract)
                new_storage[i] = round(new_storage[i] - actual_layer_uptake, 6)
                total_plant_extracted += actual_layer_uptake

        # 6. Capillary Rise Addition to Bottom Layer (bounded by available pore space)
        actual_capillary_rise = 0.0
        if capillary_rise_mm > 0.0:
            allowable_rise = max(0.0, sat_storage_mm[-1] - new_storage[-1])
            actual_capillary_rise = min(capillary_rise_mm, allowable_rise)
            new_storage[-1] = round(new_storage[-1] + actual_capillary_rise, 6)

        # 7. Recompute Volumetric Water Content Profile theta_i = S_i / thickness
        new_theta = [
            round(min(sat, max(th_r, s / thickness)), 6)
            for s, thickness, sat, th_r in zip(
                new_storage, layer_thickness_mm, prev_soil.saturation_profile, prev_soil.residual_profile
            )
        ]

        # Topsoil evaporation memory state derived from actual layer thickness
        rew_mm = max(2.0, (prev_soil.field_capacity_profile[0] - prev_soil.wilting_point_profile[0]) * layer_thickness_mm[0] * 0.5)
        top_storage_avail = max(0.0, new_storage[0] - wp_storage_mm[0])
        days_wet = 0 if total_surface_water > 5.0 else (days_since_wetting + 1)

        # Method-specific or propagated exposed wetted fraction
        if fraction_wetted is not None:
            few_val = round(max(0.01, min(1.0, float(fraction_wetted))), 3)
        elif prev_soil.evaporation_state is not None:
            few_val = prev_soil.evaporation_state.few_exposed_wetted_fraction
        else:
            few_val = 0.65

        evap_state = SoilEvaporationState(
            surface_storage_mm=round(min(rew_mm, top_storage_avail), 2),
            max_surface_storage_mm=round(rew_mm, 2),
            days_since_wetting=days_wet,
            kr_reduction_factor=round(min(1.0, top_storage_avail / rew_mm) if rew_mm > 0 else 1.0, 3),
            few_exposed_wetted_fraction=few_val,
        )

        infil_state = InfiltrationState(
            precipitation_mm=round(precipitation_mm, 2),
            irrigation_mm=round(irrigation_mm, 2),
            total_surface_water_mm=round(total_surface_water, 2),
            infiltration_capacity_mm=round(infil_capacity, 2),
            actual_infiltration_mm=round(net_infil, 2),
            surface_excess_runoff_mm=round(surface_excess_runoff, 2),
            gross_infiltration_mm=round(gross_infil, 2),
            return_flow_runoff_mm=round(return_flow_runoff_mm, 2),
            surface_storage_mm=round(final_surface_storage_mm, 2),
            max_surface_storage_mm=round(max_surface_storage_mm, 2),
            surface_water_evaporation_mm=round(evap_from_surface, 2),
        )

        updated_soil = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=prev_soil.layer_depths_cm,
            theta_profile=new_theta,
            field_capacity_profile=prev_soil.field_capacity_profile,
            wilting_point_profile=prev_soil.wilting_point_profile,
            saturation_profile=prev_soil.saturation_profile,
            residual_profile=prev_soil.residual_profile,
            hydraulic_conductivity_profile=prev_soil.hydraulic_conductivity_profile,
            van_genuchten_alpha=prev_soil.van_genuchten_alpha,
            van_genuchten_n=prev_soil.van_genuchten_n,
            infiltration=infil_state,
            evaporation_state=evap_state,
            parameter_provenance=getattr(prev_soil, "parameter_provenance", "TEXTURE_PRIOR"),
        )

        # 8. Whole-System Storage Closure Accounting
        # delta(S_soil + S_surface) = P + I + C - ET_a - D - Q_runoff
        initial_soil_storage = prev_soil.total_profile_water_mm
        final_soil_storage = updated_soil.total_profile_water_mm
        delta_s_soil = round(final_soil_storage - initial_soil_storage, 4)
        delta_s_surface = round(final_surface_storage_mm - init_surface_storage_mm, 4)
        delta_s_system = round(delta_s_soil + delta_s_surface, 4)

        system_inflows = round(precipitation_mm + irrigation_mm + actual_capillary_rise, 4)
        system_outflows = round(total_plant_extracted + total_evap + deep_drainage + total_runoff, 4)
        serialized_closure_error = round(abs(delta_s_system - (system_inflows - system_outflows)), 4)

        receipt = IntervalFluxReceipt(
            initial_storage_mm=initial_soil_storage,
            final_storage_mm=final_soil_storage,
            storage_change_mm=delta_s_soil,
            actual_infiltration_mm=round(net_infil, 4),
            surface_runoff_mm=round(total_runoff, 4),
            actual_transpiration_mm=round(total_plant_extracted, 4),
            actual_soil_evaporation_mm=round(actual_top_evap, 4),
            actual_eta_mm=round(total_plant_extracted + total_evap, 4),
            deep_drainage_mm=round(deep_drainage, 4),
            capillary_rise_mm=round(actual_capillary_rise, 4),
            precipitation_mm=round(precipitation_mm, 4),
            irrigation_mm=round(irrigation_mm, 4),
            water_closure_error_mm=serialized_closure_error,
            mass_conserved=(serialized_closure_error <= 0.05),
            initial_surface_storage_mm=round(init_surface_storage_mm, 4),
            final_surface_storage_mm=round(final_surface_storage_mm, 4),
            gross_infiltration_mm=round(gross_infil, 4),
            return_flow_runoff_mm=round(return_flow_runoff_mm, 4),
            surface_water_evaporation_mm=round(evap_from_surface, 4),
        )

        return StepWaterBalanceResult(
            updated_soil,
            round(net_infil, 2),
            round(total_runoff, 2),
            round(deep_drainage, 2),
            serialized_closure_error,
            receipt=receipt,
        )
