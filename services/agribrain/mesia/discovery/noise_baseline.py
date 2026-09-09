"""MESIA Noise and Interference Baseline Tracker — R6 §3.1.

Tracks time-varying noise floors, receiver spurs, image responses, and
occupancy baselines across frequency bins without assuming Gaussian stationarity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class NoiseFloorEstimate:
    """Estimated background noise floor across a frequency grid."""

    receiver_id: str
    evaluated_at: datetime
    freq_bins_hz: List[float]
    noise_floor_dbm: List[float]
    noise_variance_db: float
    known_spur_indices: List[int] = field(default_factory=list)

    @property
    def mean_noise_floor_dbm(self) -> float:
        if not self.noise_floor_dbm:
            return -100.0
        return sum(self.noise_floor_dbm) / len(self.noise_floor_dbm)

    def is_spur(self, bin_index: int) -> bool:
        return bin_index in self.known_spur_indices


class NoiseBaselineTracker:
    """Estimates time-varying noise floor using percentile / minimum-statistics."""

    def __init__(self, percentile: float = 20.0, spur_threshold_db: float = 12.0) -> None:
        self.percentile = percentile
        self.spur_threshold_db = spur_threshold_db

    def estimate_baseline(
        self,
        receiver_id: str,
        freq_bins_hz: List[float],
        psd_matrix_dbm: List[List[float]],
    ) -> NoiseFloorEstimate:
        """Estimate per-bin noise floor from a matrix of PSD frames over time.

        Args:
            psd_matrix_dbm: List of time frames, where each frame is a list of PSD values (dBm) per frequency bin.
        """
        if not psd_matrix_dbm or not freq_bins_hz:
            now = datetime.now(timezone.utc)
            return NoiseFloorEstimate(receiver_id, now, [], [], 0.0, [])

        num_frames = len(psd_matrix_dbm)
        num_bins = len(freq_bins_hz)

        noise_floor = []
        for bin_idx in range(num_bins):
            bin_values = sorted(psd_matrix_dbm[f][bin_idx] for f in range(num_frames))
            # Take percentile index
            p_idx = max(0, min(int((self.percentile / 100.0) * num_frames), num_frames - 1))
            noise_floor.append(bin_values[p_idx])

        # Compute median of noise floor across spectrum
        sorted_nf = sorted(noise_floor)
        median_nf = sorted_nf[len(sorted_nf) // 2]

        # Identify stationary spurs (bins consistently exceeding median by spur_threshold_db)
        spur_indices = [
            i for i, val in enumerate(noise_floor)
            if (val - median_nf) >= self.spur_threshold_db
        ]

        # Calculate noise variance across non-spur bins
        clean_bins = [val for i, val in enumerate(noise_floor) if i not in spur_indices]
        if len(clean_bins) > 1:
            mean_c = sum(clean_bins) / len(clean_bins)
            var_c = sum((x - mean_c) ** 2 for x in clean_bins) / (len(clean_bins) - 1)
        else:
            var_c = 1.0

        now = datetime.now(timezone.utc)
        return NoiseFloorEstimate(
            receiver_id=receiver_id,
            evaluated_at=now,
            freq_bins_hz=list(freq_bins_hz),
            noise_floor_dbm=noise_floor,
            noise_variance_db=var_c,
            known_spur_indices=spur_indices,
        )
