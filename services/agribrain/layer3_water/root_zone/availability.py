"""
Layer 3.0 Root Zone Water Availability and Stress Factor Engine
Computes root-zone TAW, RAW, depletion Dr, root uptake weighting U(z), and stress reduction factor Ks.
"""

from typing import List, Optional
from layer3_water.contracts.water_state import SoilWaterState, RootZoneWaterState
from layer3_water.contracts.state_factory import WaterStateFactory


class RootZoneAvailabilityEngine:
    """Evaluates root zone water availability and physiological extraction reduction factor Ks."""

    @classmethod
    def evaluate_root_zone(
        cls,
        soil_state: SoilWaterState,
        root_depth_m: float = 1.0,
        base_depletion_fraction_p: float = 0.50,
        etp_mm_day: float = 5.0,
        root_fraction_profile: Optional[List[float]] = None,
        soil_uncertainty_sigma: float = 0.04,
    ) -> RootZoneWaterState:
        """Evaluate root zone hydrological parameters and stress reduction coefficient Ks."""
        return WaterStateFactory.create_root_zone_water_state(
            root_depth_m=root_depth_m,
            layer_depths_cm=soil_state.layer_depths_cm,
            theta_profile=soil_state.theta_profile,
            field_capacity_profile=soil_state.field_capacity_profile,
            wilting_point_profile=soil_state.wilting_point_profile,
            base_depletion_fraction_p=base_depletion_fraction_p,
            etp_mm_day=etp_mm_day,
            root_fraction_profile=root_fraction_profile,
            soil_uncertainty_sigma=soil_uncertainty_sigma,
        )
