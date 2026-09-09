"""MESIA GNSS-Reflectometry (GNSS-IR) Solver — R6 §5.4 / P5.4.

Implements GNSS Interferometric Reflectometry (GNSS-IR) for ground-level
soil moisture and vegetation water sensing using multipath SNR oscillations.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .contracts import GnssInterferometryObservation
from ..assimilation.fdtd_solver import BiologicalPermittivityMap


class GnssReflectometrySolver:
    """Mathematical solver for GNSS-IR multipath interferometry."""

    SPEED_OF_LIGHT = 299792458.0  # m/s
    GPS_L1_FREQ = 1575.42e6        # Hz
    GPS_L2_FREQ = 1227.60e6        # Hz
    GALILEO_E1_FREQ = 1575.42e6    # Hz

    @staticmethod
    def get_wavelength(freq_hz: float) -> float:
        """Calculate carrier wavelength in metres."""
        return GnssReflectometrySolver.SPEED_OF_LIGHT / freq_hz

    @staticmethod
    def detrend_snr(
        elevations_deg: List[float], snrs_db: List[float]
    ) -> Tuple[List[float], List[float]]:
        """
        Detrends raw SNR series over elevation angle to isolate multipath oscillations.
        Direct line-of-sight signal is modeled as a 2nd-order polynomial in sin(elevation).
        Returns: (sin_elevations, detrended_snrs_linear)
        """
        if len(elevations_deg) < 5 or len(elevations_deg) != len(snrs_db):
            raise ValueError("Insufficient data points for GNSS-IR detrending (need >= 5).")

        sin_e = [math.sin(math.radians(e)) for e in elevations_deg]

        # Adaptive degree polynomial detrending based on elevation variance
        import numpy as np
        import warnings
        sin_e_arr = np.array(sin_e, dtype=np.float64)
        std_x = float(np.std(sin_e_arr))
        deg = 2 if (std_x > 0.05 and len(sin_e_arr) >= 6) else (1 if std_x > 0.01 else 0)
        try:
            import numpy.exceptions as _np_exc
            _RankWarning = getattr(_np_exc, "RankWarning", UserWarning)
        except (ImportError, AttributeError):
            _RankWarning = getattr(np, "RankWarning", UserWarning)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", _RankWarning)
            coeffs = np.polyfit(sin_e_arr, snrs_db, deg)
            baseline = np.polyval(coeffs, sin_e_arr)
        detrended = [float(y - b) for y, b in zip(snrs_db, baseline)]
        return sin_e, detrended

    @staticmethod
    def lomb_scargle_peak_height(
        sin_e: List[float],
        detrended_snr: List[float],
        carrier_freq_hz: float,
        h_min_m: float = 0.5,
        h_max_m: float = 5.0,
        h_step_m: float = 0.02,
    ) -> Tuple[float, float, float]:
        """
        Computes the dominant multipath spatial frequency and solves for:
        (effective_height_m, phase_shift_rad, peak_power).
        Frequency relation: f = 2 * h_eff / lambda
        """
        wavelength = GnssReflectometrySolver.get_wavelength(carrier_freq_hz)
        best_power = -1.0
        best_h = h_min_m
        best_phase = 0.0

        n = len(sin_e)
        mean_y = sum(detrended_snr) / n
        centered_y = [y - mean_y for y in detrended_snr]
        var_y = sum(y ** 2 for y in centered_y) or 1.0

        curr_h = h_min_m
        while curr_h <= h_max_m:
            omega = (4.0 * math.pi * curr_h) / wavelength

            # Lomb-Scargle tau parameter: tan(2*omega*tau) = sum(sin(2*omega*t)) / sum(cos(2*omega*t))
            s2 = sum(math.sin(2.0 * omega * t) for t in sin_e)
            c2 = sum(math.cos(2.0 * omega * t) for t in sin_e)
            tau = 0.5 * math.atan2(s2, c2) / omega

            # Cosine and sine projections
            c_terms = [math.cos(omega * (t - tau)) for t in sin_e]
            s_terms = [math.sin(omega * (t - tau)) for t in sin_e]

            c_sum2 = sum(c ** 2 for c in c_terms) or 1e-12
            s_sum2 = sum(s ** 2 for s in s_terms) or 1e-12

            yc_sum = sum(y * c for y, c in zip(centered_y, c_terms))
            ys_sum = sum(y * s for y, s in zip(centered_y, s_terms))

            # Normalized Lomb-Scargle spectral power
            power = 0.5 * ((yc_sum ** 2) / c_sum2 + (ys_sum ** 2) / s_sum2) / var_y

            if power > best_power:
                best_power = power
                best_h = curr_h
                best_phase = math.atan2(ys_sum, yc_sum)

            curr_h += h_step_m

        return best_h, best_phase, best_power

    @staticmethod
    def phase_to_soil_vwc(
        phase_shift_rad: float,
        oscillation_amplitude_linear: float = 3.0,
        carrier_freq_hz: float = GPS_L1_FREQ,
        nominal_elev_deg: float = 15.0,
    ) -> float:
        """
        Inverts GNSS-IR multipath reflection metrics to soil volumetric water content (VWC).
        Uses exact complex circular Fresnel reflection coefficient Gamma_RL(theta, eps*(vwc, f))
        derived from Peplinski & Dobson soil dielectric dispersion.
        """
        import cmath
        # Normalized reflection coefficient from multipath oscillation amplitude
        gamma_meas = max(0.20, min(0.60, oscillation_amplitude_linear / 8.0))

        best_vwc = 0.15
        min_err = 1e9
        th = math.radians(nominal_elev_deg)
        sin_th = math.sin(th)
        cos_th = math.cos(th)
        eps0 = 8.8541878128e-12

        for step in range(2, 51):
            cand_vwc = step / 100.0
            eps_r, sigma = BiologicalPermittivityMap.get_soil_properties(cand_vwc, carrier_freq_hz)
            eps_complex = complex(eps_r, -sigma / (2.0 * math.pi * carrier_freq_hz * eps0))
            u = cmath.sqrt(eps_complex - (cos_th ** 2))
            gh = (sin_th - u) / (sin_th + u)
            gv = (eps_complex * sin_th - u) / (eps_complex * sin_th + u)
            gamma_rl = abs((gh - gv) / 2.0)
            err = abs(gamma_rl - gamma_meas)
            if err < min_err:
                min_err = err
                best_vwc = cand_vwc

        return float(best_vwc)

    @staticmethod
    def parse_nmea_gsv_sentences(nmea_lines: List[str]) -> Dict[int, List[Tuple[float, float, float]]]:
        """
        Parses NMEA GSV sentences ($GPGSV, $GAGSV, $GBGSV, $GLGSV).
        Returns: {prn: [(elevation_deg, azimuth_deg, snr_db)]}
        """
        prn_data: Dict[int, List[Tuple[float, float, float]]] = {}
        # Pattern for GSV line: $..GSV,total_msgs,msg_num,tot_sats, prn,elev,az,snr, ... *CS
        gsv_pattern = re.compile(r"^\$G[A-Z]GSV,(\d+),(\d+),(\d+),(.*)\*([0-9A-Fa-f]{2})$")

        for line in nmea_lines:
            line = line.strip()
            match = gsv_pattern.match(line)
            if not match:
                continue

            fields = match.group(4).split(",")
            # Up to 4 satellites per sentence: (prn, elev, az, snr)
            for i in range(0, len(fields) - 3, 4):
                try:
                    prn = int(fields[i])
                    elev = float(fields[i + 1])
                    az = float(fields[i + 2])
                    snr = float(fields[i + 3]) if fields[i + 3] else 0.0

                    if elev > 0.0 and snr > 0.0:
                        prn_data.setdefault(prn, []).append((elev, az, snr))
                except (ValueError, IndexError):
                    continue

        return prn_data

    @classmethod
    def solve_from_arc(
        cls,
        prn: int,
        constellation: str,
        arc_points: List[Tuple[float, float, float]],
        carrier_freq_hz: float = GPS_L1_FREQ,
        timestamp: Optional[datetime] = None,
    ) -> GnssInterferometryObservation:
        """Processes an ascending/descending satellite arc into an observation."""
        now = timestamp or datetime.now(timezone.utc)
        # Filter elevation angles between 5 and 30 degrees (optimal GNSS-IR window)
        filtered = [pt for pt in arc_points if 5.0 <= pt[0] <= 30.0]
        if len(filtered) < 5:
            # If narrow, take whatever ascending/descending we have
            filtered = arc_points

        elevations = [pt[0] for pt in filtered]
        azimuths = [pt[1] for pt in filtered]
        snrs = [pt[2] for pt in filtered]

        sin_e, detrended = cls.detrend_snr(elevations, snrs)
        h_eff, phase, power = cls.lomb_scargle_peak_height(sin_e, detrended, carrier_freq_hz)
        
        # Calculate RMS amplitude of detrended oscillation for physical dielectric inversion
        amp_rms = math.sqrt(sum(d ** 2 for d in detrended) / len(detrended)) if detrended else 3.0
        vwc = cls.phase_to_soil_vwc(
            phase,
            oscillation_amplitude_linear=amp_rms,
            carrier_freq_hz=carrier_freq_hz,
            nominal_elev_deg=sum(elevations) / len(elevations) if elevations else 15.0,
        )

        # Raw data hash for Principle P-04
        raw_repr = f"{prn}_{constellation}_{len(arc_points)}_{elevations[0]:.1f}_{elevations[-1]:.1f}"
        raw_hash = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()

        # Variance is inversely related to spectral peak sharpness
        variance = max(0.005, min(0.10, 0.05 / max(0.1, power)))

        return GnssInterferometryObservation(
            observation_id=f"gnssir-{constellation.lower()}-prn{prn}-{int(now.timestamp())}",
            timestamp=now,
            prn=prn,
            constellation=constellation,
            carrier_freq_hz=carrier_freq_hz,
            elevation_start_deg=elevations[0],
            elevation_end_deg=elevations[-1],
            azimuth_mean_deg=sum(azimuths) / len(azimuths) if azimuths else 0.0,
            effective_reflector_height_m=round(h_eff, 3),
            dielectric_phase_shift_rad=round(phase, 4),
            estimated_vwc=round(vwc, 4),
            observation_variance=round(variance, 6),
            snr_detrended_peaks=[round(d, 2) for d in detrended[:8]],
            raw_nmea_hash=raw_hash,
        )
