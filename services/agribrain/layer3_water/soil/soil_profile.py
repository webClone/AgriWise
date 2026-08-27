"""
Layer 3.0 Soil Hydraulic Profile Database and Properties
Provides standardized Van Genuchten retention parameters and physical limits across USDA texture classes.
"""

from typing import Dict, Any, List, Optional
from layer3_water.contracts.water_state import SoilWaterState
from layer3_water.contracts.state_factory import WaterStateFactory


class SoilProfileDatabase:
    """Standardized pedotransfer parameter database for soil hydraulic modeling."""

    # Default hydraulic properties per USDA texture class (Van Genuchten parameters)
    TEXTURE_PROPERTIES = {
        "sand": {
            "theta_r": 0.045, "theta_wp": 0.060, "theta_fc": 0.140, "theta_s": 0.430,
            "ks_cm_day": 250.0, "vg_alpha": 0.145, "vg_n": 2.68,
        },
        "sandy_loam": {
            "theta_r": 0.065, "theta_wp": 0.095, "theta_fc": 0.210, "theta_s": 0.410,
            "ks_cm_day": 106.0, "vg_alpha": 0.075, "vg_n": 1.89,
        },
        "loam": {
            "theta_r": 0.078, "theta_wp": 0.135, "theta_fc": 0.270, "theta_s": 0.430,
            "ks_cm_day": 25.0, "vg_alpha": 0.036, "vg_n": 1.56,
        },
        "silt_loam": {
            "theta_r": 0.067, "theta_wp": 0.140, "theta_fc": 0.310, "theta_s": 0.450,
            "ks_cm_day": 10.8, "vg_alpha": 0.020, "vg_n": 1.41,
        },
        "clay_loam": {
            "theta_r": 0.095, "theta_wp": 0.180, "theta_fc": 0.320, "theta_s": 0.410,
            "ks_cm_day": 6.2, "vg_alpha": 0.019, "vg_n": 1.31,
        },
        "clay": {
            "theta_r": 0.100, "theta_wp": 0.220, "theta_fc": 0.360, "theta_s": 0.400,
            "ks_cm_day": 4.8, "vg_alpha": 0.015, "vg_n": 1.20,
        },
    }

    # Canonical 5-layer vertical discretization (cm)
    DEFAULT_LAYER_DEPTHS_CM = [10.0, 30.0, 60.0, 100.0, 200.0]

    @classmethod
    def get_canonical_soil_profile(
        cls,
        soil_type: str = "loam",
        layer_depths_cm: Optional[List[float]] = None,
        initial_saturation_fraction: float = 0.70,
    ) -> SoilWaterState:
        """Construct standard multi-layer SoilWaterState for given soil texture."""
        texture_key = soil_type.lower().replace(" ", "_")
        props = cls.TEXTURE_PROPERTIES.get(texture_key, cls.TEXTURE_PROPERTIES["loam"])
        
        layers = layer_depths_cm or cls.DEFAULT_LAYER_DEPTHS_CM
        n_layers = len(layers)
        
        th_r = [props["theta_r"]] * n_layers
        th_wp = [props["theta_wp"]] * n_layers
        th_fc = [props["theta_fc"]] * n_layers
        th_s = [props["theta_s"]] * n_layers
        ks_prof = [props["ks_cm_day"]] * n_layers
        vg_a = [props["vg_alpha"]] * n_layers
        vg_n = [props["vg_n"]] * n_layers
        
        # Initial moisture content between WP and FC
        th_init = [
            round(th_wp[i] + initial_saturation_fraction * (th_fc[i] - th_wp[i]), 4)
            for i in range(n_layers)
        ]
        
        return WaterStateFactory.create_soil_water_state(
            layer_depths_cm=layers,
            theta_profile=th_init,
            field_capacity_profile=th_fc,
            wilting_point_profile=th_wp,
            saturation_profile=th_s,
            residual_profile=th_r,
            hydraulic_conductivity_profile=ks_prof,
            van_genuchten_alpha=vg_a,
            van_genuchten_n=vg_n,
        )
