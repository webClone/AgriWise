"""MESIA Wi-Fi CSI Multipath Footprint & Microzone Sensitivity Operator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class WifiMultipathFootprint:
    """Computes spatial sensitivity fields for in-situ Wi-Fi CSI links across microzones."""

    SPEED_OF_LIGHT: float = 299792458.0

    @classmethod
    def compute_link_geometry(
        cls,
        tx_node_enu_m: Tuple[float, float, float],
        rx_node_enu_m: Tuple[float, float, float],
        carrier_freq_hz: float = 2400e6,
    ) -> Dict[str, Any]:
        """Calculates 3D baseline distance, azimuth, and Fresnel radius."""
        wavelength = cls.SPEED_OF_LIGHT / carrier_freq_hz
        tx_x, tx_y, tx_z = tx_node_enu_m
        rx_x, rx_y, rx_z = rx_node_enu_m

        dx = rx_x - tx_x
        dy = rx_y - tx_y
        dz = rx_z - tx_z
        baseline_m = math.sqrt(dx * dx + dy * dy + dz * dz)
        mid_x = (tx_x + rx_x) * 0.5
        mid_y = (tx_y + rx_y) * 0.5

        # Maximum Fresnel radius at midpoint
        r_fresnel_mid_m = math.sqrt((wavelength * baseline_m) / 4.0)

        return {
            "tx_node_enu_m": tx_node_enu_m,
            "rx_node_enu_m": rx_node_enu_m,
            "midpoint_enu_m": (mid_x, mid_y),
            "baseline_distance_m": baseline_m,
            "max_fresnel_radius_m": r_fresnel_mid_m,
            "carrier_freq_hz": carrier_freq_hz,
            "wavelength_m": wavelength,
        }

    @classmethod
    def evaluate_sensitivity_at_point(
        cls,
        x: float,
        y: float,
        tx_node_enu_m: Tuple[float, float, float],
        rx_node_enu_m: Tuple[float, float, float],
        max_fresnel_radius_m: float,
        state_variable: str = "vwc_vegetation",
    ) -> float:
        """Evaluates localized sensitivity W_{wifi,q}(x, y)."""
        tx_x, tx_y, _ = tx_node_enu_m
        rx_x, rx_y, _ = rx_node_enu_m

        dx = rx_x - tx_x
        dy = rx_y - tx_y
        l2 = dx * dx + dy * dy
        if l2 < 1e-4:
            return 0.0

        t = ((x - tx_x) * dx + (y - tx_y) * dy) / l2
        if t < -0.15 or t > 1.15:
            return 0.0

        proj_x = tx_x + max(0.0, min(1.0, t)) * dx
        proj_y = tx_y + max(0.0, min(1.0, t)) * dy
        d_to_link = math.hypot(x - proj_x, y - proj_y)

        t_b = max(0.05, min(0.95, t))
        local_r_f = max(0.8, max_fresnel_radius_m * 2.0 * math.sqrt(t_b * (1.0 - t_b)))

        if state_variable == "vwc_vegetation":
            # Foliar canopy interaction
            val = math.exp(-0.5 * (d_to_link / (local_r_f * 0.8)) ** 2)
        elif state_variable == "theta_v_soil":
            # Direct ground reflection
            val = 0.5 * math.exp(-0.5 * (d_to_link / (local_r_f * 1.2)) ** 2)
        else:
            val = 0.3 * math.exp(-0.5 * (d_to_link / local_r_f) ** 2)

        return val if d_to_link <= 2.5 * local_r_f else 0.0
