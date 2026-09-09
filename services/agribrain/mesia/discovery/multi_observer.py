"""MESIA Multi-Observer Event Corroboration — R6 §3.5.

Fuses detections from overlapping front ends or spatial receivers strictly
at event level to verify consistency and reject local instrument spurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.wave import WaveCandidate


@dataclass(frozen=True)
class CorroboratedEventRecord:
    """Multi-observer corroborated wave detection event."""

    event_id: str
    participating_candidate_ids: List[str]
    coincident_receiver_ids: List[str]
    time_of_arrival_spread_s: float
    frequency_agreement_hz: float
    is_corroborated: bool
    is_suspected_local_spur: bool
    confidence_score: float
    notes: str = ""


class MultiObserverCorroborator:
    """Corroborates wave events across multiple spatial or overlapping receivers."""

    @staticmethod
    def corroborate_event(
        event_id: str,
        candidates: List[WaveCandidate],
        max_time_spread_s: float = 0.05,
        max_frequency_spread_hz: float = 500e3,
    ) -> CorroboratedEventRecord:
        """Evaluate coincidence between candidates detected by different receivers."""
        if not candidates:
            raise ValueError("Corroboration requires at least one WaveCandidate.")

        if len(candidates) == 1:
            # Single observer detection — not cross-corroborated, could be local spur if SNR is low
            c = candidates[0]
            return CorroboratedEventRecord(
                event_id=event_id,
                participating_candidate_ids=[c.candidate_id],
                coincident_receiver_ids=[c.receiver_id],
                time_of_arrival_spread_s=0.0,
                frequency_agreement_hz=0.0,
                is_corroborated=False,
                is_suspected_local_spur=False,
                confidence_score=c.confidence or 0.5,
                notes="Single receiver detection.",
            )

        times = [c.start_time.timestamp() for c in candidates if c.start_time]
        freqs = [c.centre_frequency_hz for c in candidates if c.centre_frequency_hz is not None]
        rx_ids = list(set(c.receiver_id for c in candidates))

        t_spread = max(times) - min(times) if times else 0.0
        f_spread = max(freqs) - min(freqs) if freqs else 0.0

        is_consistent = (t_spread <= max_time_spread_s) and (f_spread <= max_frequency_spread_hz)

        # High confidence if multi-receiver agrees
        confidence = 0.95 if (is_consistent and len(rx_ids) > 1) else 0.4

        return CorroboratedEventRecord(
            event_id=event_id,
            participating_candidate_ids=[c.candidate_id for c in candidates],
            coincident_receiver_ids=rx_ids,
            time_of_arrival_spread_s=t_spread,
            frequency_agreement_hz=f_spread,
            is_corroborated=is_consistent and len(rx_ids) > 1,
            is_suspected_local_spur=not is_consistent,
            confidence_score=confidence,
            notes="Multi-observer coincidence verified." if is_consistent else "Timing/frequency mismatch across receivers.",
        )
