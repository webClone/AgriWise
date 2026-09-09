"""MESIA Spaceborne GNSS-R (CYGNSS / Spire) Ingestion Engine — R6 §5.4 / P5.4.

Ingests orbital bistatic GNSS reflections recorded by LEO satellites (NASA CYGNSS, Spire)
for 100% pure remote soil moisture sensing with zero field hardware.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .contracts import PureRemoteObservation


class SpaceborneGnssrEngine:
    """Ingests and inverts spaceborne GNSS-R reflection telemetry."""

    @staticmethod
    def is_point_in_polygon(lat: float, lon: float, polygon_coords: List[Tuple[float, float]]) -> bool:
        """
        Standard ray-casting algorithm to test if (lat, lon) is inside polygon_coords [(lat, lon), ...].
        """
        n = len(polygon_coords)
        if n < 3:
            return False

        inside = False
        p1_lat, p1_lon = polygon_coords[0]
        for i in range(n + 1):
            p2_lat, p2_lon = polygon_coords[i % n]
            if lon > min(p1_lon, p2_lon):
                if lon <= max(p1_lon, p2_lon):
                    if lat <= max(p1_lat, p2_lat):
                        if p1_lon != p2_lon:
                            xinters = (lon - p1_lon) * (p2_lat - p1_lat) / (p2_lon - p1_lon) + p1_lat
                        if p1_lat == p2_lat or lat <= xinters:
                            inside = not inside
            p1_lat, p1_lon = p2_lat, p2_lon

        return inside

    @staticmethod
    def reflectivity_to_soil_vwc(
        reflectivity_db: float,
        incidence_angle_deg: float = 30.0,
        surface_roughness_cm: float = 1.0,
    ) -> Tuple[float, float]:
        """
        Inverts orbital bistatic reflectivity Gamma (dB) to soil volumetric water content (VWC).
        Corrects for surface roughness using the Choudhury roughness model:
        Gamma_rough = Gamma_smooth * exp(-h_rough * cos^2(theta))
        where h_rough = 4 * k^2 * s^2, k = 2 * pi / lambda (L-band lambda ~ 0.19 m).
        """
        wavelength_m = 0.1903  # GPS L1
        k = 2.0 * math.pi / wavelength_m
        s_m = surface_roughness_cm / 100.0
        theta_rad = math.radians(incidence_angle_deg)
        cos_th = math.cos(theta_rad)

        # Roughness correction factor
        h_rough = (2.0 * k * s_m * cos_th) ** 2
        roughness_attenuation_linear = math.exp(-h_rough)

        # Measured linear reflectivity
        gamma_meas = 10.0 ** (reflectivity_db / 10.0)
        gamma_smooth = min(0.95, max(0.01, gamma_meas / (roughness_attenuation_linear + 1e-6)))

        # Invert smooth Fresnel reflection at circular polarization (Gamma_RL approx |(eps - 1)/(sqrt(eps) + 1)|^2)
        # Approximate inversion: sqrt(eps) approx (1 + sqrt(gamma)) / (1 - sqrt(gamma))
        r_sq = math.sqrt(gamma_smooth)
        inferred_eps = ((1.0 + r_sq) / max(0.05, 1.0 - r_sq)) ** 2
        inferred_eps = max(2.5, min(40.0, inferred_eps))

        # Invert soil dielectric permittivity using exact Newton-Raphson polynomial inversion
        from ..assimilation.fdtd_solver import BiologicalPermittivityMap
        vwc = BiologicalPermittivityMap.invert_soil_permittivity_topp(inferred_eps)
        variance = 0.02 + 0.01 * (reflectivity_db < -25.0)  # Lower SNR increases variance

        return float(vwc), float(variance)

    @classmethod
    def filter_and_ingest_tracks(
        cls,
        granule_id: str,
        mission: str,
        specular_tracks: List[Dict[str, Any]],
        farm_polygon: List[Tuple[float, float]],
    ) -> List[PureRemoteObservation]:
        """
        Filters orbital specular points that intersect the farm polygon and generates PureRemoteObservations.
        specular_tracks element: {"lat": float, "lon": float, "reflectivity_db": float, "time": datetime, "incidence_angle_deg": float}
        """
        observations: List[PureRemoteObservation] = []

        for track in specular_tracks:
            lat = float(track.get("lat", 0.0))
            lon = float(track.get("lon", 0.0))

            if not cls.is_point_in_polygon(lat, lon, farm_polygon):
                continue

            refl_db = float(track.get("reflectivity_db", -18.0))
            inc_ang = float(track.get("incidence_angle_deg", 30.0))
            ts = track.get("time") or datetime.now(timezone.utc)

            vwc, var = cls.reflectivity_to_soil_vwc(refl_db, inc_ang)

            obs_id = f"remote-{mission.lower()}-{int(ts.timestamp())}-{abs(hash(f'{lat}_{lon}')) % 10000}"
            obs = PureRemoteObservation(
                observation_id=obs_id,
                mission=mission,
                timestamp=ts,
                specular_point_wgs84=(round(lat, 5), round(lon, 5)),
                reflectivity_db=round(refl_db, 2),
                estimated_root_zone_vwc=round(vwc, 4),
                confidence=round(max(0.1, 1.0 - var * 10.0), 3),
                coverage_fraction=1.0,
                external_granule_id=granule_id,
            )
            observations.append(obs)

        return observations
