"""MESIA Capture Escalation Controller — R6 §3.6.

Controls dynamic escalation from low-rate coarse sweeps to high-rate IQ capture,
protocol decode, or active probing within storage and policy budgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.wave import WaveCandidate


class EscalationDecision(str):
    NO_ESCALATION = "NO_ESCALATION"
    ESCALATE_TO_IQ_DWELL = "ESCALATE_TO_IQ_DWELL"
    ESCALATE_TO_PROTOCOL_DECODE = "ESCALATE_TO_PROTOCOL_DECODE"
    ESCALATE_TO_ACTIVE_PROBE = "ESCALATE_TO_ACTIVE_PROBE"


@dataclass(frozen=True)
class EscalationPlan:
    """Action plan resulting from an escalation decision."""

    decision: EscalationDecision
    target_candidate_id: str
    target_frequency_hz: float
    target_bandwidth_hz: float
    capture_duration_s: float
    estimated_storage_mb: float
    is_budget_approved: bool
    escalation_reason: str


class CaptureEscalationController:
    """Decides when an observable candidate warrants escalation."""

    def __init__(
        self,
        min_snr_for_iq_dwell_db: float = 6.0,
        min_snr_for_protocol_decode_db: float = 12.0,
        available_storage_mb: float = 10000.0,
    ) -> None:
        self.min_snr_iq = min_snr_for_iq_dwell_db
        self.min_snr_decode = min_snr_for_protocol_decode_db
        self.available_storage_mb = available_storage_mb

    def evaluate_escalation(
        self,
        candidate: WaveCandidate,
        max_dwell_duration_s: float = 1.0,
    ) -> EscalationPlan:
        """Evaluate whether to escalate capture for a given WaveCandidate."""
        snr = candidate.snr_db or 0.0
        bw = candidate.bandwidth_hz or 20e6
        freq = candidate.centre_frequency_hz or 2400e6

        # Estimated raw IQ storage: 2 * sample_rate * 2 bytes (16-bit complex) * duration
        # sample_rate ~= 1.25 * bandwidth
        sample_rate = bw * 1.25
        bytes_per_sec = sample_rate * 4.0
        estimated_storage_mb = (bytes_per_sec * max_dwell_duration_s) / (1024.0 * 1024.0)

        is_approved = estimated_storage_mb <= self.available_storage_mb

        if snr >= self.min_snr_decode and is_approved:
            decision = EscalationDecision.ESCALATE_TO_PROTOCOL_DECODE
            reason = f"High SNR ({snr:.1f} dB >= {self.min_snr_decode} dB) supports protocol correlation/decode."
        elif snr >= self.min_snr_iq and is_approved:
            decision = EscalationDecision.ESCALATE_TO_IQ_DWELL
            reason = f"Moderate SNR ({snr:.1f} dB >= {self.min_snr_iq} dB) warrants high-rate IQ capture."
        else:
            decision = EscalationDecision.NO_ESCALATION
            reason = "Insufficient SNR or storage budget exhausted."

        return EscalationPlan(
            decision=decision,
            target_candidate_id=candidate.candidate_id,
            target_frequency_hz=freq,
            target_bandwidth_hz=bw,
            capture_duration_s=max_dwell_duration_s if decision != EscalationDecision.NO_ESCALATION else 0.0,
            estimated_storage_mb=estimated_storage_mb if decision != EscalationDecision.NO_ESCALATION else 0.0,
            is_budget_approved=is_approved,
            escalation_reason=reason,
        )
