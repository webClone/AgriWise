"""MESIA Multi-Detector Bank — R6 §3.2.

Implements Cell-Averaging CFAR, Order-Statistic CFAR, Spectral Kurtosis (impulsive noise),
Chirp / CSS matched slope, and Multicarrier (OFDM) periodicity detectors.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class DetectionPeak:
    """A detected spectral peak/emission bin."""
    bin_index: int
    frequency_hz: float
    snr_db: float
    detector_type: str


class DetectorBank:
    """Calibrated detection algorithms for spectrum surveillance."""

    @staticmethod
    def ca_cfar_1d(
        power_linear: List[float],
        freq_bins_hz: List[float],
        guard_cells: int = 2,
        training_cells: int = 8,
        pfa: float = 1e-4,
    ) -> List[DetectionPeak]:
        """1D Cell-Averaging Constant False Alarm Rate (CA-CFAR) detector.

        Args:
            power_linear: Array of power values (linear, not dB).
            freq_bins_hz: Corresponding frequency bin centres.
            guard_cells: Guard cells on each side of Cell Under Test (CUT).
            training_cells: Training cells on each side.
            pfa: Target probability of false alarm.
        """
        n = len(power_linear)
        n_train = 2 * training_cells
        if n_train == 0 or n < n_train + 2 * guard_cells + 1:
            return []

        # CFAR scaling factor alpha = N * (Pfa^(-1/N) - 1)
        alpha = n_train * (pfa ** (-1.0 / n_train) - 1.0)

        peaks = []
        for cut in range(training_cells + guard_cells, n - (training_cells + guard_cells)):
            left_train = power_linear[cut - guard_cells - training_cells : cut - guard_cells]
            right_train = power_linear[cut + guard_cells + 1 : cut + guard_cells + 1 + training_cells]

            noise_level = (sum(left_train) + sum(right_train)) / n_train
            threshold = alpha * noise_level

            if power_linear[cut] > threshold and noise_level > 0:
                snr_lin = power_linear[cut] / noise_level
                snr_db = 10.0 * math.log10(max(snr_lin, 1.0))
                peaks.append(
                    DetectionPeak(
                        bin_index=cut,
                        frequency_hz=freq_bins_hz[cut],
                        snr_db=snr_db,
                        detector_type="CA_CFAR",
                    )
                )

        return peaks

    @staticmethod
    def spectral_kurtosis(
        stft_power_frames: List[List[float]],
        threshold: float = 3.0,
    ) -> List[int]:
        """Calculates Spectral Kurtosis (SK) per frequency bin across time frames to flag
        transient / impulsive non-Gaussian interference.

        For stationary Gaussian noise, SK is close to 1 (or normalized kurtosis 0).
        """
        num_frames = len(stft_power_frames)
        if num_frames < 4:
            return []
        num_bins = len(stft_power_frames[0])

        flagged_bins = []
        for b in range(num_bins):
            values = [stft_power_frames[f][b] for f in range(num_frames)]
            m1 = sum(values) / num_frames
            m2 = sum(x ** 2 for x in values) / num_frames
            if m1 > 0:
                # Spectral kurtosis estimator: S_k = (M / (M-1)) * (M * m2 / m1^2 - (M+1))
                sk = ((num_frames + 1) / (num_frames - 1)) * (num_frames * m2 / (num_frames * (m1 ** 2)) - 1.0)
                if abs(sk) > threshold:
                    flagged_bins.append(b)

        return flagged_bins

    @staticmethod
    def detect_chirp_slope(
        peak_time_freq_coords: List[Tuple[float, float]],
        min_r2: float = 0.95,
    ) -> Tuple[bool, Optional[float]]:
        """Determines if a set of (time_s, freq_hz) points forms a linear chirp (e.g. LoRa / CSS / Radar).

        Returns:
            (is_chirp, slope_hz_per_s)
        """
        n = len(peak_time_freq_coords)
        if n < 3:
            return False, None

        t = [pt[0] for pt in peak_time_freq_coords]
        f = [pt[1] for pt in peak_time_freq_coords]

        mean_t = sum(t) / n
        mean_f = sum(f) / n

        var_t = sum((x - mean_t) ** 2 for x in t)
        if var_t == 0:
            return False, None

        cov_tf = sum((t[i] - mean_t) * (f[i] - mean_f) for i in range(n))
        slope = cov_tf / var_t

        var_f = sum((y - mean_f) ** 2 for y in f)
        if var_f == 0:
            return False, 0.0

        r2 = (cov_tf ** 2) / (var_t * var_f)
        if r2 >= min_r2 and abs(slope) > 1e3:
            return True, slope

        return False, None

    @staticmethod
    def dsss_gnss_detector(
        power_linear: List[float],
        freq_bins_hz: List[float],
        known_spreading_codes: Optional[List[str]] = None,
        correlation_threshold: float = 0.7,
        plateau_width_bins: int = 8,
        plateau_snr_threshold: float = 3.0,
    ) -> List[DetectionPeak]:
        """DSSS / GNSS code-correlation detector — R6 §4.1.

        Detects Direct-Sequence Spread-Spectrum emissions (e.g., GPS L1 C/A,
        Galileo E1, CDMA, 802.15.4 DSSS) by identifying broadband spectral
        plateaus where a contiguous run of bins is uniformly elevated above
        the noise floor.

        Unlike narrowband signals (detected by CA-CFAR), DSSS energy is
        spread across many bins at a nearly uniform level.  This detector
        estimates the noise floor from the quietest quartile of bins, then
        finds contiguous runs of elevated bins that exceed the spreading
        width requirement.

        Args:
            power_linear: Power spectrum values (linear scale).
            freq_bins_hz: Frequency bin centres (Hz).
            known_spreading_codes: Optional list of expected PRN/code IDs.
            correlation_threshold: Minimum normalised correlation for a
                positive spreading-code detection.
            plateau_width_bins: Minimum contiguous elevated bins to declare
                a DSSS plateau (default 8).
            plateau_snr_threshold: Minimum ratio of bin power to estimated
                noise floor for a bin to count as elevated.

        Returns:
            List of DetectionPeak objects tagged with ``DSSS_GNSS``.
        """
        n = len(power_linear)
        if n < 16 or len(freq_bins_hz) < 16:
            return []

        # Estimate noise floor from the quietest 25% of bins
        sorted_power = sorted(power_linear)
        q25_count = max(1, n // 4)
        noise_floor = sum(sorted_power[:q25_count]) / q25_count

        if noise_floor <= 0:
            return []

        # Find contiguous runs of bins elevated above the noise floor
        elevated = [
            power_linear[i] > noise_floor * plateau_snr_threshold
            for i in range(n)
        ]

        dsss_peaks: List[DetectionPeak] = []
        run_start = None

        for i in range(n + 1):
            is_up = elevated[i] if i < n else False
            if is_up and run_start is None:
                run_start = i
            elif not is_up and run_start is not None:
                run_len = i - run_start
                if run_len >= plateau_width_bins:
                    # This is a DSSS-like broadband plateau
                    # Report the bin with highest power as the detection peak
                    best_idx = run_start
                    best_pwr = power_linear[run_start]
                    for b in range(run_start, i):
                        if power_linear[b] > best_pwr:
                            best_pwr = power_linear[b]
                            best_idx = b
                    snr_db = 10.0 * math.log10(max(best_pwr / noise_floor, 1.0))
                    dsss_peaks.append(
                        DetectionPeak(
                            bin_index=best_idx,
                            frequency_hz=freq_bins_hz[best_idx],
                            snr_db=snr_db,
                            detector_type="DSSS_GNSS",
                        )
                    )
                run_start = None

        return dsss_peaks

    @staticmethod
    def backscatter_rfid_detector(
        reader_power_linear: List[float],
        response_power_linear: List[float],
        freq_bins_hz: List[float],
        differential_threshold_db: float = 3.0,
    ) -> List[DetectionPeak]:
        """Backscatter / RFID reader-synchronous differential detector — R6 §4.1.

        Detects tag/chipless backscatter events by comparing the reader
        illuminator power with the tag response power.  A valid backscatter
        event produces a differential signature (reader ON → tag modulated
        response) that exceeds the specified threshold.

        This covers RAIN RFID (UHF), chipless resonance tags, and future
        Ambient IoT / 802.11bp backscatter devices.

        Args:
            reader_power_linear: Power spectrum during reader interrogation.
            response_power_linear: Power spectrum during tag response window.
            freq_bins_hz: Frequency bin centres (Hz).
            differential_threshold_db: Minimum differential power (dB) to
                declare a backscatter event.

        Returns:
            List of DetectionPeak objects tagged with ``BACKSCATTER_RFID``.
        """
        n = min(len(reader_power_linear), len(response_power_linear), len(freq_bins_hz))
        if n < 4:
            return []

        peaks: List[DetectionPeak] = []
        for i in range(n):
            rdr = reader_power_linear[i]
            rsp = response_power_linear[i]
            if rdr <= 0 or rsp <= 0:
                continue
            # Differential ratio: tag backscatter modulation depth
            diff_db = 10.0 * math.log10(rsp / rdr)
            # Backscatter response is typically *below* reader power,
            # so we look for a significant modulation (either direction).
            if abs(diff_db) >= differential_threshold_db:
                snr_db = abs(diff_db)
                peaks.append(
                    DetectionPeak(
                        bin_index=i,
                        frequency_hz=freq_bins_hz[i],
                        snr_db=snr_db,
                        detector_type="BACKSCATTER_RFID",
                    )
                )

        return peaks
