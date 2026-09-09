"""MESIA Identity Contracts — R6 §5.

SignalIdentityHypothesis — Ranked waveform/RAT/protocol candidates with
  supporting AND contradicting evidence.
ProtocolConfirmationReceipt — Direct correlator/decoder/CRC/reference/
  native-device evidence supporting CONFIRMED status.

Key rule (§5.3): A learned classifier may propose candidates, but it
cannot create PROTOCOL_CONFIRMED by itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


from .receipts import ProtocolConfirmationReceipt



@dataclass(frozen=True)
class SignalIdentityHypothesis:
    """Ranked waveform/RAT/protocol candidates — R6 Appendix A.

    The decision engine retains supporting AND contradicting evidence,
    not only a class score.
    """

    hypothesis_id: str
    wave_candidate_ref: str
    """Reference to the WaveCandidate this hypothesis is about."""

    # Candidates ranked by supporting evidence strength
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    """Each entry: {
        'protocol': str,
        'confirmation_level': int,
        'probability': float,
        'supporting_evidence': List[str],
        'contradicting_evidence': List[str],
    }"""

    # Current identity state
    current_state: str = ""
    """IdentityState value."""

    # Abstention / ambiguity
    abstention_score: Optional[float] = None
    """Calibrated abstention score — higher means more likely to abstain."""

    is_ambiguous: bool = False
    ambiguity_reason: str = ""

    # OOD scoring
    ood_score: Optional[float] = None
    """Out-of-distribution score for open-set detection."""

    # Receipt (if confirmed)
    confirmation_receipt_ref: str = ""

    # Versioning
    registry_version: str = ""
    """SignalIdentityProfile registry version used."""

    model_version: str = ""
    """Learned classifier version (if any classifier contributed)."""

    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif isinstance(val, (list, tuple)):
                val = list(val)
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def top_candidate(self) -> Optional[Dict[str, Any]]:
        """Return the highest-probability candidate, if any."""
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda c: c.get("probability", 0.0))
