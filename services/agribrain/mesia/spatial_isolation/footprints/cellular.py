"""MESIA Cellular Forward-Scatter Footprint & Ray Tube Sensitivity Operator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CellularForwardScatterFootprint:
    """Computes bistatic chord cylinder and sensitivity field for cellular downlink signals."""

    SPEED_OF_LIGHT: float = 299792458.0

    @classmethod
    def compute_bistatic_chord(
        cls,
        tower_enu_m: Tuple[float, float, float],
        receiver_enu_m: Tuple[float, float, float],
        carrier_freq_hz: float = 1800e6,
    ) -> Dict[str, Any]:
        """Calculates 3D chord line, Fresnel radius, and path profile."""
        wavelength = cls.SPEED_OF_LIGHT / max(1e6, carrier_freq_hz)
        tx_x, tx_y, tx_z = tower_enu_m
        rx_x, rx_y, rx_z = receiver_enu_m

        dx = rx_x - tx_x
        dy = rx_y - tx_y
        dz = rx_z - tx_z
        total_distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        # First Fresnel ellipsoid maximum radius at midpoint d1 = d2 = D/2
        r_fresnel_max = math.sqrt((wavelength * total_distance) / 4.0)

        # Azimuth angle of the chord from tower to receiver (degrees from North)
        bearing_deg = math.degrees(math.atan2(dx, dy)) % 360.0

        return {
            "tower_enu_m": tower_enu_m,
            "receiver_enu_m": receiver_enu_m,
            "total_distance_m": total_distance,
            "max_fresnel_radius_m": r_fresnel_max,
            "bearing_deg": bearing_deg,
            "carrier_freq_hz": carrier_freq_hz,
            "wavelength_m": wavelength,
        }

    @classmethod
    def evaluate_sensitivity_at_point(
        cls,
        x: float,
        y: float,
        tower_enu_m: Tuple[float, float, float],
        receiver_enu_m: Tuple[float, float, float],
        max_fresnel_radius_m: float,
        state_variable: str = "vwc_vegetation",
    ) -> float:
        """Evaluates sensitivity W_{cell,q}(x, y) along the bistatic chord."""
        tx_x, tx_y, _ = tower_enu_m
        rx_x, rx_y, _ = receiver_enu_m

        # Distance from (x, y) to line segment between tower and receiver
        line_dx = rx_x - tx_x
        line_dy = rx_y - tx_y
        line_len_sq = line_dx * line_dx + line_dy * line_dy
        if line_len_sq < 1e-6:
            return 0.0

        # Projection parameter t
        t = ((x - tx_x) * line_dx + (y - tx_y) * line_dy) / line_len_sq

        # If point is outside the segment along the path, decay sharply
        if t < -0.1 or t > 1.1:
            return 0.0

        # Closest point on segment
        proj_x = tx_x + max(0.0, min(1.0, t)) * line_dx
        proj_y = tx_y + max(0.0, min(1.0, t)) * line_dy
        dist_to_ray = math.hypot(x - proj_x, y - proj_y)

        # Local Fresnel radius at fractional distance t: r_F(t) = sqrt(lambda * D * t * (1-t))
        t_bounded = max(0.01, min(0.99, t))
        local_r_f = max(1.5, max_fresnel_radius_m * 2.0 * math.sqrt(t_bounded * (1.0 - t_bounded)))

        if state_variable == "vwc_vegetation":
            # Direct canopy attenuation along the ray
            sigma_w = local_r_f * 0.75
            val = math.exp(-0.5 * (dist_to_ray / sigma_w) ** 2)
        elif state_variable == "theta_v_soil":
            # Specular bounce forward reflection
            sigma_w = local_r_f * 1.5
            val = 0.35 * math.exp(-0.5 * (dist_to_ray / sigma_w) ** 2)
        else:
            sigma_w = local_r_f
            val = 0.20 * math.exp(-0.5 * (dist_to_ray / sigma_w) ** 2)

        return val if dist_to_ray <= 3.0 * local_r_f else 0.0
