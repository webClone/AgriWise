"""
Layer 3.0 Adaptive Physical Solver Selector
Dynamically selects numerical solver fidelity based on observation density, soil certainty, and crop economic priority.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from layer3_water.contracts.authority import HydrologyMode, SolverFidelity
from layer3_water.contracts.assimilation_state import SoilObservationVector


@dataclass(frozen=True)
class SolverSelectionDecision:
    """Decision output from adaptive solver selector."""
    hydrology_mode: HydrologyMode
    solver_fidelity: SolverFidelity
    selection_rationale: str
    target_time_step_hours: float
    numerical_convergence_tolerance: float


class SolverSelector:
    """Policy engine selecting numerical hydrology solver fidelity."""

    @classmethod
    def select_solver(
        cls,
        crop_economic_priority_factor: float = 1.0,
        soil_uncertainty_sigma: float = 0.04,
        observations: Optional[SoilObservationVector] = None,
        requested_mode: Optional[HydrologyMode] = None,
    ) -> SolverSelectionDecision:
        """Select appropriate solver fidelity based on operational and physical context."""
        if requested_mode == HydrologyMode.RICHARDS_1D:
            return SolverSelectionDecision(
                hydrology_mode=HydrologyMode.FAO56_LAYERED_BUCKET,
                solver_fidelity=SolverFidelity.EMPIRICAL_BUCKET,
                selection_rationale=(
                    "Richards 1D was requested but no validated Richards runner "
                    "is installed; truthfully degraded to the FAO-56 layered bucket."
                ),
                target_time_step_hours=24.0,
                numerical_convergence_tolerance=1e-2,
            )

        # High fidelity trigger: In-situ probe data available + high crop value OR high soil certainty
        has_probes = observations and observations.soil_probe_moisture_profile is not None
        is_high_value = crop_economic_priority_factor >= 1.5
        is_well_characterized = soil_uncertainty_sigma <= 0.025

        if has_probes or (is_high_value and is_well_characterized):
            return SolverSelectionDecision(
                hydrology_mode=HydrologyMode.FAO56_LAYERED_BUCKET,
                solver_fidelity=SolverFidelity.EMPIRICAL_BUCKET,
                selection_rationale=(
                    "High-fidelity criteria were met, but no validated Richards "
                    "runner is installed; executed the FAO-56 layered bucket "
                    f"(in-situ sensors={bool(has_probes)}, crop_priority="
                    f"{crop_economic_priority_factor:.1f}, soil_sigma="
                    f"{soil_uncertainty_sigma:.3f})."
                ),
                target_time_step_hours=24.0,
                numerical_convergence_tolerance=1e-2,
            )

        return SolverSelectionDecision(
            hydrology_mode=HydrologyMode.FAO56_LAYERED_BUCKET,
            solver_fidelity=SolverFidelity.EMPIRICAL_BUCKET,
            selection_rationale=(
                f"Selected FAO-56 layered bucket solver for operational efficiency (soil_sigma={soil_uncertainty_sigma:.3f})"
            ),
            target_time_step_hours=24.0,
            numerical_convergence_tolerance=1e-2,
        )
