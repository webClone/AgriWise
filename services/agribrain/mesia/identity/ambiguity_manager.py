"""MESIA Ambiguity Manager & Hypothesis Arbiter — R6 §4.6.

Retains multiple candidate hypotheses when signatures overlap (e.g. Wi-Fi vs BLE
vs Zigbee in 2.4 GHz) and schedules targeted verification instead of forced labeling.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..contracts.identity import SignalIdentityHypothesis


class AmbiguityManager:
    """Manages overlapping identity candidates and ambiguous hypotheses."""

    @staticmethod
    def resolve_or_retain_ambiguity(
        hypothesis: SignalIdentityHypothesis,
        ambiguity_margin: float = 0.15,
    ) -> SignalIdentityHypothesis:
        """Evaluate candidate probabilities in a SignalIdentityHypothesis.

        If the top two candidates have close probabilities (|p1 - p2| <= margin),
        marks the hypothesis as AMBIGUOUS and retains both.
        """
        if len(hypothesis.candidates) < 2:
            return hypothesis

        sorted_cands = sorted(hypothesis.candidates, key=lambda c: c.get("probability", 0.0), reverse=True)
        p1 = sorted_cands[0].get("probability", 0.0)
        p2 = sorted_cands[1].get("probability", 0.0)

        if abs(p1 - p2) <= ambiguity_margin:
            # Ambiguity cannot be resolved without direct decoder/correlator receipt
            # Mutate to AMBIGUOUS state
            d = hypothesis.to_dict()
            d["is_ambiguous"] = True
            d["current_state"] = "AMBIGUOUS"
            d["ambiguity_reason"] = (
                f"Close candidate scores: {sorted_cands[0]['protocol']} ({p1:.2f}) vs "
                f"{sorted_cands[1]['protocol']} ({p2:.2f}). Direct capture receipt required."
            )
            return SignalIdentityHypothesis(**d)

        return hypothesis
