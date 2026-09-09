"""MESIA Terrestrial Broadcast (DVB-T2 / FM) Deep Sub-Surface Sensing Engine — R6 §6.5.

Leverages high-power megawatt terrestrial TV and FM radio transmitters as long-wavelength
illuminators of opportunity for deep root-zone soil moisture sensing.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Optional, Tuple

from ..assimilation.fdtd_solver import BiologicalPermittivityMap


class BroadcastUhfEngine:
    """Deep soil root-zone moisture solver using terrestrial UHF/VHF broadcasts."""

    SPEED_OF_LIGHT = 299792458.0
    MU_0 = 4.0 * math.pi * 1e-7

    @staticmethod
    def compute_skin_depth_m(freq_hz: float, conductivity_s_m: float) -> float:
        """
        Computes electromagnetic skin depth delta in metres:
        delta = 1 / sqrt(pi * f * mu_0 * sigma)
        """
        sigma = max(1e-4, float(conductivity_s_m))
        denom = math.sqrt(math.pi * freq_hz * BroadcastUhfEngine.MU_0 * sigma)
        return float(1.0 / denom)

    @staticmethod
    def fresnel_reflection_coefficient(
        eps_r: float, grazing_angle_deg: float, polarization: str = "HORIZONTAL"
    ) -> float:
        """
        Computes Fresnel power reflection coefficient |Gamma|^2 for soil surface.
        grazing_angle_deg: Angle relative to the ground plane (0 = horizontal, 90 = vertical).
        """
        theta_rad = math.radians(max(0.5, min(89.5, grazing_angle_deg)))
        sin_th = math.sin(theta_rad)
        cos_th = math.cos(theta_rad)

        radicand = max(1e-5, eps_r - (cos_th ** 2))
        sqrt_term = math.sqrt(radicand)

        if polarization.upper() == "VERTICAL":
            num = eps_r * sin_th - sqrt_term
            den = eps_r * sin_th + sqrt_term
        else:  # HORIZONTAL
            num = sin_th - sqrt_term
            den = sin_th + sqrt_term

        gamma = num / (den + 1e-12)
        return float(min(1.0, max(0.0, gamma ** 2)))

    @classmethod
    def solve_deep_vwc(
        cls,
        measured_reflectivity: float,
        grazing_angle_deg: float,
        freq_hz: float = 600e6,  # 600 MHz UHF DVB-T2
        polarization: str = "HORIZONTAL",
    ) -> Tuple[float, float, float]:
        """
        Inverts Fresnel reflection to find soil permittivity eps_r, deep VWC, and sensing skin depth.
        Returns: (deep_vwc, skin_depth_m, observation_variance)
        """
        r = max(0.01, min(0.95, float(measured_reflectivity)))
        gamma = math.sqrt(r)

        theta_rad = math.radians(max(0.5, min(89.5, grazing_angle_deg)))
        sin_th = math.sin(theta_rad)
        cos_th = math.cos(theta_rad)

        # Invert horizontal Fresnel equation: gamma = (sqrt(eps - cos^2) - sin_th) / (sqrt(eps - cos^2) + sin_th)
        # sqrt(eps - cos^2) = sin_th * (1 + gamma) / (1 - gamma)
        term = sin_th * (1.0 + gamma) / max(0.01, 1.0 - gamma)
        inferred_eps = (term ** 2) + (cos_th ** 2)

        # Permittivity bounds check
        inferred_eps = max(2.5, min(40.0, inferred_eps))

        # Invert Topp polynomial for volumetric water content using unified solver
        vwc = BiologicalPermittivityMap.invert_soil_permittivity_topp(inferred_eps)

        # Calculate skin depth at this inferred moisture
        _, sigma = BiologicalPermittivityMap.get_soil_properties(vwc, freq_hz)
        skin_depth = cls.compute_skin_depth_m(freq_hz, sigma)
        variance = 0.015 + 0.02 * (1.0 - sin_th)

        return float(vwc), float(skin_depth), float(variance)
