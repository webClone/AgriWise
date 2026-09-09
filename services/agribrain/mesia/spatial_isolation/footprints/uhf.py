"""MESIA Terrestrial Broadcast UHF / VHF Footprint Operator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class BroadcastUhfFootprint:
    """Computes wide-area low-frequency terrain scattering and deep sub-surface footprint."""

    SPEED_OF_LIGHT: float = 299792458.0

    @classmethod
    def compute_scattering_footprint(
        cls,
        tx_azimuth_deg: float,
        rx_enu_m: Tuple[float, float, float],
        grazing_angle_deg: float = 15.0,
        carrier_freq_hz: float = 600e6,
        field_aperture_m: float = 80.0,
    ) -> Dict[str, Any]:
        """Calculates low-frequency ground reflection zone."""
        wavelength = cls.SPEED_OF_LIGHT / carrier_freq_hz
        theta_g_rad = math.radians(max(2.0, min(60.0, grazing_angle_deg)))

        # Specular reflection zone is elongated towards the transmitter azimuth
        rx_x, rx_y, rx_h = rx_enu_m
        h_eff = max(1.5, rx_h)
        dist_to_ground_reflection = h_eff / math.sin(theta_g_rad)

        tx_rad = math.radians(tx_azimuth_deg % 360.0)
        # Specular region lies in direction of arrival
        center_x = rx_x + dist_to_ground_reflection * math.sin(tx_rad)
        center_y = rx_y + dist_to_ground_reflection * math.cos(tx_rad)

        semi_minor_m = math.sqrt(wavelength * dist_to_ground_reflection)
        semi_major_m = semi_minor_m / math.sin(theta_g_rad)

        return {
            "center_enu_m": (center_x, center_y),
            "semi_major_m": semi_major_m,
            "semi_minor_m": semi_minor_m,
            "grazing_angle_deg": grazing_angle_deg,
            "carrier_freq_hz": carrier_freq_hz,
            "wavelength_m": wavelength,
        }

    @classmethod
    def evaluate_sensitivity_at_point(
        cls,
        x: float,
        y: float,
        center_enu_m: Tuple[float, float],
        semi_major_m: float,
        semi_minor_m: float,
        tx_azimuth_deg: float,
        state_variable: str = "theta_v_soil",
    ) -> float:
        """Evaluates sensitivity W_{uhf,q}(x, y). Deep soil content dominates."""
        cx, cy = center_enu_m
        dx = x - cx
        dy = y - cy
        th = math.radians(tx_azimuth_deg)

        u = dx * math.sin(th) + dy * math.cos(th)
        v = dx * math.cos(th) - dy * math.sin(th)

        r_sq = (u / max(2.0, semi_major_m)) ** 2 + (v / max(2.0, semi_minor_m)) ** 2

        if state_variable == "theta_v_soil":
            # Deep root-zone soil dominates UHF absorption & reflection
            val = math.exp(-1.5 * r_sq)
        elif state_variable == "vwc_vegetation":
            # Very low attenuation through dry/thin crop canopy at UHF
            val = 0.15 * math.exp(-2.0 * r_sq)
        else:
            val = 0.25 * math.exp(-1.0 * r_sq)

        return val if r_sq <= 4.0 else 0.0
