"""MESIA GNSS-R Footprint Geometry & Spatial Sensitivity Operator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class GnssReflectometryFootprint:
    """Calculates First Fresnel Ellipse and spatial sensitivity field for GNSS-R."""

    SPEED_OF_LIGHT: float = 299792458.0
    GPS_L1_FREQ: float = 1575.42e6  # 1.57542 GHz -> lambda = 0.1903 m

    @staticmethod
    def get_wavelength(carrier_freq_hz: float = GPS_L1_FREQ) -> float:
        return GnssReflectometryFootprint.SPEED_OF_LIGHT / carrier_freq_hz

    @classmethod
    def compute_ground_footprint(
        cls,
        rx_enu_m: Tuple[float, float, float],
        elev_deg: float,
        az_deg: float,
        carrier_freq_hz: float = GPS_L1_FREQ,
        is_spaceborne: bool = False,
        leo_altitude_km: float = 525.0,
        integration_time_s: float = 1.0,
    ) -> Dict[str, Any]:
        """Calculates specular point location, Fresnel semi-axes, smearing, and sensitivity function."""
        wavelength = cls.get_wavelength(carrier_freq_hz)
        elev_rad = math.radians(max(3.0, min(88.0, elev_deg)))
        az_rad = math.radians(az_deg % 360.0)
        sin_elev = math.sin(elev_rad)
        cos_elev = math.cos(elev_rad)

        rx_x, rx_y, rx_h = rx_enu_m

        if is_spaceborne:
            # Spaceborne geometry (CYGNSS / Spire)
            r_eff_m = leo_altitude_km * 1000.0
            b = math.sqrt((wavelength * r_eff_m) / sin_elev)
            a = b / sin_elev
            # Specular velocity ~ 6.2 km/s for typical 525 km LEO orbit
            v_specular = 6200.0
            l_smear = v_specular * integration_time_s
            # Specular point directly on ground
            sp_x = rx_x
            sp_y = rx_y
        else:
            # Ground-based in-situ receiver
            h_ant = max(0.5, rx_h)
            d_sp = h_ant / math.tan(elev_rad)
            # Specular reflection comes from opposite azimuth
            sp_az_rad = az_rad + math.pi
            sp_x = rx_x + d_sp * math.sin(sp_az_rad)
            sp_y = rx_y + d_sp * math.cos(sp_az_rad)

            # Ground Fresnel zone semi-axes
            b = math.sqrt((wavelength * h_ant) / sin_elev + ((wavelength / (2.0 * sin_elev)) ** 2))
            a = b / sin_elev
            l_smear = 0.0

        major_axis = a * 2.0 + l_smear
        minor_axis = b * 2.0

        # Orientation angle of the ellipse major axis on the ground (measured from East)
        # The specular track lies along azimuth az_deg
        ellipse_azimuth_deg = az_deg % 180.0

        return {
            "specular_point_enu_m": (sp_x, sp_y),
            "semi_major_m": a + (l_smear * 0.5),
            "semi_minor_m": b,
            "major_axis_m": major_axis,
            "minor_axis_m": minor_axis,
            "smearing_length_m": l_smear,
            "ellipse_azimuth_deg": ellipse_azimuth_deg,
            "is_spaceborne": is_spaceborne,
        }

    @classmethod
    def evaluate_sensitivity_at_point(
        cls,
        x: float,
        y: float,
        sp_x: float,
        sp_y: float,
        semi_major_m: float,
        semi_minor_m: float,
        ellipse_azimuth_deg: float,
        state_variable: str = "theta_v_soil",
    ) -> float:
        """Evaluates state-specific normalized sensitivity W_{m,q}(x, y)."""
        # Coordinate transformation into ellipse-aligned frame
        dx = x - sp_x
        dy = y - sp_y
        theta = math.radians(ellipse_azimuth_deg)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        # u along major axis, v along minor axis
        u = dx * sin_t + dy * cos_t
        v = dx * cos_t - dy * sin_t

        a = max(0.5, semi_major_m)
        b = max(0.5, semi_minor_m)

        # Normalized elliptical radius
        r_ell_sq = (u / a) ** 2 + (v / b) ** 2

        if state_variable == "theta_v_soil":
            # Soil sensitivity is tightly concentrated in 1st Fresnel zone
            decay_rate = 2.0
        elif state_variable == "vwc_vegetation":
            # Foliar water sensitivity includes diffuse scatter halo
            decay_rate = 1.2
            b *= 1.3
            a *= 1.3
            r_ell_sq = (u / a) ** 2 + (v / b) ** 2
        else:  # surface_roughness_s
            # Roughness affects outer Fresnel fringe transitions
            decay_rate = 1.0
            r_ell_sq = (u / a) ** 2 + (v / b) ** 2

        val = math.exp(-decay_rate * r_ell_sq)
        # Cut off at 3-sigma equivalent
        return val if r_ell_sq <= 4.0 else 0.0
