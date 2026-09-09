"""MESIA Commercial Microwave Link (CML) Backhaul Ingestion Engine — R6 §6.5.

Leverages existing telecom point-to-point microwave links (7–38 GHz) traversing
near or over agricultural valleys to monitor near-surface humidity and rain events remotely.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Optional, Tuple

from .contracts import PureRemoteObservation


class CommercialMicrowaveLinkEngine:
    """Computes atmospheric and canopy moisture attenuation from telecom microwave links."""

    @staticmethod
    def get_itu_p838_coefficients(freq_ghz: float) -> Tuple[float, float]:
        """
        Approximate ITU-R P.838 power-law coefficients a, b for horizontal polarization:
        Specific attenuation gamma_R = a * R^b (dB/km) as a function of rain rate R (mm/h).
        """
        f = max(5.0, min(45.0, float(freq_ghz)))
        # Empirical regression for 10-30 GHz
        if f < 15.0:
            a = 0.016 * ((f / 10.0) ** 2.2)
            b = 1.15 - 0.01 * f
        elif f < 25.0:
            a = 0.08 + 0.01 * (f - 15.0)
            b = 1.05 - 0.008 * (f - 15.0)
        else:
            a = 0.25 + 0.02 * (f - 25.0)
            b = 0.95 - 0.005 * (f - 25.0)
        return float(a), float(b)

    @classmethod
    def process_link_attenuation(
        cls,
        link_id: str,
        freq_ghz: float,
        link_length_km: float,
        baseline_rsl_dbm: float,
        measured_rsl_dbm: float,
        specular_center_wgs84: Tuple[float, float],
        timestamp: Optional[datetime] = None,
    ) -> PureRemoteObservation:
        """
        Evaluates microwave backhaul attenuation delta to detect rain or surface wetness.
        """
        now = timestamp or datetime.now(timezone.utc)
        excess_loss_db = max(0.0, baseline_rsl_dbm - measured_rsl_dbm)
        specific_attenuation_db_km = excess_loss_db / max(0.1, link_length_km)

        a, b = cls.get_itu_p838_coefficients(freq_ghz)
        # Invert rain rate / moisture flux: R = (gamma / a)^(1/b)
        inferred_rain_rate = (specific_attenuation_db_km / a) ** (1.0 / b) if specific_attenuation_db_km > 0.01 else 0.0

        # Surface wetness proxy
        surface_wetness = min(1.0, inferred_rain_rate / 15.0 + (specific_attenuation_db_km / 2.0))
        confidence = 0.85 if excess_loss_db > 1.0 else 0.50

        obs_id = f"cml-{link_id}-{int(now.timestamp())}"
        return PureRemoteObservation(
            observation_id=obs_id,
            mission="CML_TELECOM",
            timestamp=now,
            specular_point_wgs84=specular_center_wgs84,
            reflectivity_db=round(-excess_loss_db, 2),
            estimated_root_zone_vwc=round(surface_wetness, 4),
            confidence=round(confidence, 3),
            coverage_fraction=1.0,
            external_granule_id=f"LINK_{link_id}",
        )
