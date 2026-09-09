"""MESIA Burst and Pulse Association Engine — R6 §3.4.

Associates repeated bursts, pulse trains, and frequency-hopping patterns
into candidate sequence hypotheses without forcing single-label classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.wave import WaveCandidate


@dataclass(frozen=True)
class AssociatedBurstSequence:
    """A sequence of associated bursts (e.g. FHSS hop sequence or periodic pulse train)."""

    sequence_id: str
    burst_candidate_ids: List[str]
    estimated_periodicity_s: Optional[float]
    carrier_frequencies_hz: List[float]
    is_frequency_hopping: bool
    mean_snr_db: float
    alternative_hypotheses: List[str] = field(default_factory=list)


class BurstAssociator:
    """Associates multiple discrete WaveCandidates into correlated sequences."""

    @staticmethod
    def associate_bursts(
        sequence_id: str,
        candidates: List[WaveCandidate],
        max_inter_burst_gap_s: float = 2.0,
    ) -> Optional[AssociatedBurstSequence]:
        """Group a set of temporally adjacent candidates into an associated burst sequence."""
        if len(candidates) < 2:
            return None

        sorted_cands = sorted(candidates, key=lambda c: c.start_time or datetime.min)
        cand_ids = [c.candidate_id for c in sorted_cands]
        freqs = [c.centre_frequency_hz for c in sorted_cands if c.centre_frequency_hz is not None]
        snrs = [c.snr_db for c in sorted_cands if c.snr_db is not None]

        # Calculate time differences between successive bursts
        intervals = []
        for i in range(len(sorted_cands) - 1):
            if sorted_cands[i].start_time and sorted_cands[i + 1].start_time:
                dt = (sorted_cands[i + 1].start_time - sorted_cands[i].start_time).total_seconds()
                if dt <= max_inter_burst_gap_s:
                    intervals.append(dt)

        if not intervals:
            return None

        mean_period = sum(intervals) / len(intervals)

        # Check for frequency hopping (distinct carrier frequencies across bursts)
        unique_freqs = set(freqs)
        is_fhss = len(unique_freqs) > 1

        hypotheses = ["PERIODIC_PULSE_TRAIN"]
        if is_fhss:
            hypotheses.append("FREQUENCY_HOPPING_SPREAD_SPECTRUM")

        return AssociatedBurstSequence(
            sequence_id=sequence_id,
            burst_candidate_ids=cand_ids,
            estimated_periodicity_s=mean_period,
            carrier_frequencies_hz=freqs,
            is_frequency_hopping=is_fhss,
            mean_snr_db=sum(snrs) / len(snrs) if snrs else 0.0,
            alternative_hypotheses=hypotheses,
        )
