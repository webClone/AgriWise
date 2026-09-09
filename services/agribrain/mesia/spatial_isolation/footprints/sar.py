"""MESIA Synthetic Aperture Radar (SAR) Footprint & Visibility Operator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SarRadarFootprint:
    """Computes spaceborne SAR pixel response, point spread function, and topographic visibility."""

    @classmethod
    def evaluate_pixel_point_spread(
        cls,
        x: float,
        y: float,
        pixel_center_enu_m: Tuple[float, float],
        resolution_range_m: float = 10.0,
        resolution_azimuth_m: float = 10.0,
        flight_heading_deg: float = 192.0,  # Sentinel-1 descending heading
        state_variable: str = "theta_v_soil",
    ) -> float:
        """Evaluates SAR PSF footprint W_{sar,q}(x, y)."""
        px, py = pixel_center_enu_m
        dx = x - px
        dy = y - py

        head_rad = math.radians(flight_heading_deg)
        # Along-track (azimuth) and cross-track (slant range)
        u_az = dx * math.sin(head_rad) + dy * math.cos(head_rad)
        v_rg = dx * math.cos(head_rad) - dy * math.sin(head_rad)

        sig_az = resolution_azimuth_m * 0.6
        sig_rg = resolution_range_m * 0.6

        r_sq = (u_az / sig_az) ** 2 + (v_rg / sig_rg) ** 2

        if state_variable == "theta_v_soil":
            # Co-pol VV surface soil backscatter
            val = math.exp(-0.5 * r_sq)
        elif state_variable == "vwc_vegetation":
            # Cross-pol VH volume scattering
            val = 0.85 * math.exp(-0.5 * r_sq)
        else:
            val = 0.70 * math.exp(-0.5 * r_sq)

        return val if r_sq <= 4.0 else 0.0

    @classmethod
    def classify_terrain_visibility(
        cls,
        local_incidence_angle_deg: float,
        terrain_slope_deg: float = 0.0,
        aspect_diff_deg: float = 0.0,
    ) -> str:
        """Classifies pixel radar visibility: VISIBLE, FORESHORTENED, LAYOVER, SHADOW, AMBIGUOUS."""
        eff_incidence = local_incidence_angle_deg - terrain_slope_deg * math.cos(math.radians(aspect_diff_deg))
        if eff_incidence <= 5.0:
            return "LAYOVER"
        elif eff_incidence <= 15.0:
            return "FORESHORTENED"
        elif eff_incidence >= 85.0:
            return "SHADOW"
        elif 20.0 <= eff_incidence <= 75.0:
            return "VISIBLE"
        else:
            return "AMBIGUOUS"
