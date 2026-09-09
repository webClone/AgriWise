"""MESIA Time-Frequency Segmentation & WaveCandidate Formation — R6 §3.3.

Segments time-frequency detection grids into bounded candidate emissions
and produces validated WaveCandidate objects without premature protocol naming.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.wave import WaveCandidate
from .detector_bank import DetectionPeak, DetectorBank


class TimeFrequencySegmenter:
    """Groups detection peaks into WaveCandidate emission contracts."""

    @staticmethod
    def segment_emission(
        candidate_id: str,
        detection_peaks: List[Tuple[float, DetectionPeak]],
        receiver_id: str,
        native_artefact_uri: str,
        native_artefact_hash: str,
        antenna_path_ref: str = "",
        calibration_state_ref: str = "",
        epoch_start_time: Optional[datetime] = None,
    ) -> Optional[WaveCandidate]:
        """Convert a cluster of (time_offset_s, DetectionPeak) points into a WaveCandidate.

        Args:
            candidate_id: Unique candidate UUID.
            detection_peaks: List of (time_offset_s, DetectionPeak).
            receiver_id: Identifier of the capturing receiver.
            native_artefact_uri: S3/local URI to raw capture.
            native_artefact_hash: SHA-256 hash of the native raw data.
        """
        if not detection_peaks:
            return None

        base_time = epoch_start_time or datetime.now(timezone.utc)

        times = [pt[0] for pt in detection_peaks]
        freqs = [pt[1].frequency_hz for pt in detection_peaks]
        snrs = [pt[1].snr_db for pt in detection_peaks]

        min_t, max_t = min(times), max(times)
        min_f, max_f = min(freqs), max(freqs)

        duration_s = max_t - min_t
        bandwidth_hz = max_f - min_f if max_f > min_f else 200e3  # minimum bin resolution
        centre_freq_hz = (min_f + max_f) / 2.0
        mean_snr = sum(snrs) / len(snrs)

        # Morphology determination
        coords = [(pt[0], pt[1].frequency_hz) for pt in detection_peaks]
        is_chirp, slope = DetectorBank.detect_chirp_slope(coords)

        if is_chirp:
            morphology = "CSS_CHIRP"
        elif bandwidth_hz > 5e6:
            morphology = "OFDM"
        elif bandwidth_hz < 50e3:
            morphology = "NARROWBAND_CW"
        else:
            morphology = "UNKNOWN"

        start_dt = base_time + timedelta(seconds=min_t)
        end_dt = base_time + timedelta(seconds=max_t)

        return WaveCandidate(
            candidate_id=candidate_id,
            start_time=start_dt,
            end_time=end_dt,
            centre_frequency_hz=centre_freq_hz,
            bandwidth_hz=bandwidth_hz,
            morphology=morphology,
            duty_cycle_pct=100.0 if duration_s > 0 else 10.0,
            periodicity_s=None,
            slope_hz_per_s=slope,
            detection_method="MULTI_DETECTOR_CFAR",
            snr_db=mean_snr,
            confidence=min(1.0, mean_snr / 25.0) if mean_snr > 0 else 0.1,
            masks=[],
            uncertainty_description=f"BW_uncertainty={bandwidth_hz*0.05:.1f}Hz, time_unc=10us",
            native_artefact_uri=native_artefact_uri,
            native_artefact_hash=native_artefact_hash,
            receiver_id=receiver_id,
            antenna_path_ref=antenna_path_ref,
            calibration_state_ref=calibration_state_ref,
        )
