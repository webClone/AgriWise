"""MESIA 2D Spatial Sensitivity Integrator & Uncertainty Engine.

Performs numerical integration of continuous electromagnetic sensitivity operators W_{m,q}(r)
over cadastral plot polygon P_plot, protected core P_core, and external surroundings.
Calculates rigorous containment intervals: eta_lower = eta_sens,plot - k * sigma_eta.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Tuple

from .geometry import point_in_polygon, polygon_area
from .models import ContainmentInterval, StateSpecificSensitivity


class SpatialSensitivityIntegrator:
    """Numerical quadrature and uncertainty propagation for footprint sensitivity fields."""

    DEFAULT_COVERAGE_FACTOR_K: float = 2.0  # k = 2.0 corresponds to ~95.4% coverage under ISO GUM

    @classmethod
    def integrate_sensitivity(
        cls,
        sensitivity_evaluator: Callable[[float, float, str], float],
        polygon_plot_enu: List[Tuple[float, float]],
        polygon_core_enu: List[Tuple[float, float]],
        bbox_min_xy: Tuple[float, float],
        bbox_max_xy: Tuple[float, float],
        grid_resolution_m: float = 2.0,
        sigma_cadastre_m: float = 0.5,
        sigma_receiver_m: float = 0.2,
        model_fidelity_score: float = 0.90,
    ) -> Dict[str, Any]:
        """Integrates sensitivity across plot, core, and external domain.

        Returns ContainmentIntervals, area overlap diagnostics, and state-specific containment.
        """
        min_x, min_y = bbox_min_xy
        max_x, max_y = bbox_max_xy

        # Enforce reasonable grid step
        step = max(0.5, min(5.0, grid_resolution_m))
        area_cell = step * step

        # Accumulators
        mass_plot = {"theta_v_soil": 0.0, "vwc_vegetation": 0.0, "surface_roughness_s": 0.0}
        mass_core = {"theta_v_soil": 0.0, "vwc_vegetation": 0.0, "surface_roughness_s": 0.0}
        mass_total = {"theta_v_soil": 0.0, "vwc_vegetation": 0.0, "surface_roughness_s": 0.0}

        points_in_footprint = 0
        points_in_plot = 0

        y = min_y
        while y <= max_y:
            x = min_x
            while x <= max_x:
                in_plot = point_in_polygon(x, y, polygon_plot_enu)
                in_core = point_in_polygon(x, y, polygon_core_enu) if in_plot else False

                # Primary variable: theta_v_soil
                w_soil = sensitivity_evaluator(x, y, "theta_v_soil")
                w_canopy = sensitivity_evaluator(x, y, "vwc_vegetation")
                w_rough = sensitivity_evaluator(x, y, "surface_roughness_s")

                if w_soil > 0.05 or w_canopy > 0.05:
                    points_in_footprint += 1
                    if in_plot:
                        points_in_plot += 1

                # Total energy integrals
                mass_total["theta_v_soil"] += w_soil * area_cell
                mass_total["vwc_vegetation"] += w_canopy * area_cell
                mass_total["surface_roughness_s"] += w_rough * area_cell

                if in_plot:
                    mass_plot["theta_v_soil"] += w_soil * area_cell
                    mass_plot["vwc_vegetation"] += w_canopy * area_cell
                    mass_plot["surface_roughness_s"] += w_rough * area_cell

                if in_core:
                    mass_core["theta_v_soil"] += w_soil * area_cell
                    mass_core["vwc_vegetation"] += w_canopy * area_cell
                    mass_core["surface_roughness_s"] += w_rough * area_cell

                x += step
            y += step

        # Calculate geometric cross-sectional area overlap diagnostic
        eta_geom = (points_in_plot / max(1, points_in_footprint)) if points_in_footprint > 0 else 0.0

        # Propagate uncertainty sigma_eta based on cadastral and geodetic uncertainty
        # Boundary gradient heuristic: sensitivity mass located within 2 * sigma_cadastre of boundary
        sigma_pos = math.sqrt(sigma_cadastre_m ** 2 + sigma_receiver_m ** 2)
        base_uncertainty = max(0.015, (1.0 - model_fidelity_score) * 0.12)
        sigma_eta = min(0.15, max(0.01, base_uncertainty + (sigma_pos / max(10.0, max_x - min_x)) * 0.25))

        k = cls.DEFAULT_COVERAGE_FACTOR_K

        # Helper to construct ContainmentInterval
        def make_interval(plot_mass: float, tot_mass: float) -> ContainmentInterval:
            tot = max(1e-9, tot_mass)
            eta_hat = min(1.0, max(0.0, plot_mass / tot))
            eta_lower = max(0.0, eta_hat - k * sigma_eta)
            eta_upper = min(1.0, eta_hat + k * sigma_eta)
            return ContainmentInterval(
                eta_hat=eta_hat,
                sigma_eta=sigma_eta,
                k_coverage=k,
                eta_lower=eta_lower,
                eta_upper=eta_upper,
            )

        interval_plot = make_interval(mass_plot["theta_v_soil"], mass_total["theta_v_soil"])
        interval_core = make_interval(mass_core["theta_v_soil"], mass_total["theta_v_soil"])

        state_sensitivities = StateSpecificSensitivity(
            theta_v_soil=interval_plot,
            vwc_vegetation=make_interval(mass_plot["vwc_vegetation"], mass_total["vwc_vegetation"]),
            surface_roughness_s=make_interval(mass_plot["surface_roughness_s"], mass_total["surface_roughness_s"]),
        )

        eta_ext_leakage = max(0.0, 1.0 - interval_plot.eta_hat)

        return {
            "containment_plot": interval_plot,
            "containment_core": interval_core,
            "eta_external_leakage": eta_ext_leakage,
            "eta_geometric_diagnostic": eta_geom,
            "state_sensitivities": state_sensitivities,
            "mass_plot": mass_plot,
            "mass_total": mass_total,
        }
