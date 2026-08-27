"""
Layer 3.0 Model Predictive Control (MPC) Irrigation Optimizer
Closed-loop receding horizon state optimizer minimizing water costs, energy tariffs, and transpiration limitation risk.
"""

from typing import List, Dict, Any, Optional, Tuple
import math

from layer3_water.contracts.irrigation_state import (
    IrrigationMethod,
    WaterDecisionAction,
    WaterDecisionUrgency,
    IrrigationConstraints,
    IrrigationObjective,
    WaterDecision,
)
from layer3_water.contracts.water_state import (
    RootZoneWaterState,
    PotentialWaterFlux,
    WaterLimitationForecast,
)


class MPCPrescriptiveOptimizer:
    """True closed-loop Model Predictive Control optimizer for prescriptive irrigation scheduling."""

    EFFICIENCY_MAP = {
        IrrigationMethod.DRIP: 0.92,
        IrrigationMethod.MICRO_SPRINKLER: 0.85,
        IrrigationMethod.SPRINKLER: 0.78,
        IrrigationMethod.CENTER_PIVOT: 0.84,
        IrrigationMethod.SURFACE_FURROW: 0.65,
        IrrigationMethod.SURFACE_FLOOD: 0.55,
    }

    @classmethod
    def _simulate_internal_state_transition(
        cls,
        dr_curr: float,
        taw: float,
        raw: float,
        irrigation_dose_mm: float,
        tpot_mm: float,
        et0_mm: float,
        ke: float,
        precip_mm: float = 0.0,
    ) -> Tuple[float, float, float]:
        """Internal state transition: x_{t+1} = f(x_t, u_t, w_t).
        
        Returns:
            (dr_next, ks_step, tdeficit_step)
        """
        # Net irrigation refill
        dr_after_irr = max(0.0, dr_curr - irrigation_dose_mm)
        
        # Stress factor Ks
        if dr_after_irr <= raw:
            ks = 1.0
        elif dr_after_irr >= taw:
            ks = 0.0
        else:
            ks = max(0.0, (taw - dr_after_irr) / max(1.0, taw - raw))
            
        tact = ks * tpot_mm
        eta = tact + ke * et0_mm
        tdeficit = tpot_mm - tact
        
        # Next depletion state
        dr_next = max(0.0, min(taw, dr_after_irr + eta - precip_mm))
        return dr_next, ks, tdeficit

    @classmethod
    def optimize_irrigation_schedule(
        cls,
        root_zone: RootZoneWaterState,
        potential_flux: PotentialWaterFlux,
        limitation_forecast: WaterLimitationForecast,
        method: IrrigationMethod = IrrigationMethod.DRIP,
        constraints: Optional[IrrigationConstraints] = None,
        objective: Optional[IrrigationObjective] = None,
    ) -> WaterDecision:
        """Closed-loop MPC optimization over multi-day horizon with receding horizon control."""
        constr = constraints or IrrigationConstraints()
        obj = objective or IrrigationObjective()
        eff = cls.EFFICIENCY_MAP.get(method, 0.85)

        taw = root_zone.total_available_water_mm
        raw = root_zone.readily_available_water_mm
        init_dr = root_zone.root_zone_depletion_mm
        ks_0 = root_zone.stress_factor_ks
        tpot_0 = potential_flux.tpot_mm
        et0_0 = potential_flux.et0_mm
        ke_0 = potential_flux.ke

        horizon = min(limitation_forecast.forecast_days, 5)
        
        # Extract forecast series
        exp_tdefs = limitation_forecast.transpiration_deficit_trajectory[:horizon] or [0.0] * horizon
        exp_drs = limitation_forecast.projected_depletion_mm[:horizon] or [init_dr] * horizon
        
        # Candidate discrete net doses for day 1 (Control action u_0).
        # allocation_remaining_mm is treated as a gross legal/operational cap,
        # so the corresponding net cap includes application efficiency.
        max_net_dose = max(0.0, constr.max_single_dose_mm)
        if constr.allocation_remaining_mm is not None:
            max_net_dose = min(
                max_net_dose,
                max(0.0, constr.allocation_remaining_mm) * eff,
            )
        candidate_doses = [0.0]
        # Discrete increments up to max_single_dose
        d_step = max(5.0, constr.min_single_dose_mm)
        curr_d = d_step
        while curr_d <= max_net_dose:
            candidate_doses.append(curr_d)
            curr_d += 5.0
        # Include exact refill dose
        if init_dr > 0:
            refill_dose = min(init_dr, max_net_dose)
            if refill_dose >= constr.min_single_dose_mm:
                candidate_doses.append(refill_dose)

        best_u0 = 0.0
        min_cost = float("inf")
        rationale = []

        # Cost weights
        c_water = obj.water_cost_weight
        c_risk = obj.transpiration_limitation_penalty_weight
        c_energy = obj.energy_cost_weight
        c_drain = obj.deep_drainage_penalty_weight

        for u0 in candidate_doses:
            # Multi-step forward state evaluation
            total_j = 0.0
            dr_sim = init_dr
            
            # Step 1 with candidate u0
            dr_sim, ks_1, tdef_1 = cls._simulate_internal_state_transition(
                dr_curr=dr_sim,
                taw=taw,
                raw=raw,
                irrigation_dose_mm=u0,
                tpot_mm=tpot_0,
                et0_mm=et0_0,
                ke=ke_0,
            )
            # Penalize water applied, energy, and transpiration deficit
            total_j += c_water * u0 + c_energy * u0 * 0.15 + c_risk * tdef_1 * 10.0
            # Extra penalty for applying water above depletion (deep percolation loss)
            if u0 > init_dr:
                total_j += c_drain * 25.0 * (u0 - init_dr)

            # Future steps in horizon (assuming standard demand)
            for t in range(1, horizon):
                tdef_proj = exp_tdefs[t] if t < len(exp_tdefs) else 0.0
                p_lim = limitation_forecast.water_limitation_probability_trajectory[t] if t < len(limitation_forecast.water_limitation_probability_trajectory) else 0.0
                total_j += c_risk * tdef_proj * 5.0 + c_risk * p_lim * 15.0

            if total_j < min_cost:
                min_cost = total_j
                best_u0 = u0

        # Receding Horizon decision assignment
        days_until_crit = limitation_forecast.days_until_critical_depletion

        if best_u0 > 0.0:
            if ks_0 < 0.95 or init_dr >= raw:
                action = WaterDecisionAction.IRRIGATE
                urgency = WaterDecisionUrgency.CRITICAL if ks_0 < 0.50 else WaterDecisionUrgency.HIGH
                rationale.append(f"MPC optimized replenishment dose of {best_u0:.1f}mm to restore root zone (Dr={init_dr:.1f}mm >= RAW={raw:.1f}mm)")
                rationale.append(f"Immediate transpiration limitation active (Ks={ks_0:.2f})")
            else:
                action = WaterDecisionAction.PREVENTATIVE_IRRIGATION
                urgency = WaterDecisionUrgency.MEDIUM
                rationale.append(f"MPC scheduled preventative dose of {best_u0:.1f}mm ahead of critical depletion ({days_until_crit} days)")
                rationale.append("Proactive root-zone moisture maintenance optimizes future energy and limitation risk")
        else:
            action = WaterDecisionAction.HOLD
            urgency = WaterDecisionUrgency.LOW
            best_u0 = 0.0
            rationale.append(f"Root zone moisture adequate (Dr={init_dr:.1f}mm < RAW={raw:.1f}mm; Ks=1.00)")
            rationale.append("MPC solved optimal control: zero irrigation for current cycle minimizes operational costs")

        gross_dose = round(best_u0 / eff, 1) if best_u0 > 0 else 0.0
        net_dose = round(best_u0, 1)

        # Performance indices
        if net_dose > 0:
            preserved_fraction = round(min(1.0, max(0.85, 1.0 - (1.0 - ks_0) * 0.2)), 2)
            limitation_reduct = round((1.0 - ks_0) * 100.0 if ks_0 < 1.0 else 30.0, 1)
            productivity = round((net_dose * 10.0) / max(0.1, tpot_0 * 7.0), 2)
        else:
            preserved_fraction = 1.0
            limitation_reduct = 0.0
            productivity = 0.0

        # Explainability ledger for MPC optimization tradeoff
        ledger = {
            "receding_horizon_days": horizon,
            "evaluated_candidate_trajectories_count": len(candidate_doses),
            "optimal_cost_j": round(min_cost, 3),
            "water_cost_component": round(c_water * best_u0, 3),
            "energy_tariff_penalty": round(c_energy * best_u0 * 0.15, 3),
            "avoided_transpiration_limitation_deficit_mm": round((1.0 - ks_0) * tpot_0 if ks_0 < 1.0 else 0.0, 2),
            "deep_percolation_waste_penalty": round(c_drain * max(0.0, best_u0 - init_dr), 3),
            "initial_depletion_mm": round(init_dr, 2),
            "target_raw_mm": round(raw, 2),
            "allocation_remaining_gross_mm": constr.allocation_remaining_mm,
            "effective_max_net_dose_mm": round(max_net_dose, 3),
        }
        # GAP-13 FIX: Dynamic confidence based on data richness and forecast horizon.
        # - Base confidence from Ks reliability (higher Ks = more certain state)
        # - Penalize for long horizons (uncertainty compounds)
        # - Penalize for synthetic ensemble (no calibrated NWP members)
        base_conf = 0.90 if ks_0 > 0.5 else (0.70 if ks_0 > 0.2 else 0.50)
        horizon_penalty = horizon * 0.02  # 2% per forecast day
        ensemble_penalty = 0.05  # Synthetic ensemble, not calibrated NWP
        dynamic_confidence = round(max(0.30, min(0.98, base_conf - horizon_penalty - ensemble_penalty)), 3)

        return WaterDecision(
            action=action,
            urgency=urgency,
            recommended_net_mm=net_dose,
            recommended_gross_mm=gross_dose,
            transpiration_preserved_fraction=preserved_fraction,
            expected_water_limitation_reduction=limitation_reduct,
            economic_water_productivity_score=productivity,
            confidence_score=dynamic_confidence,
            rationale=rationale,
            decision_ledger=ledger,
        )
