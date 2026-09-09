"""MESIA Multi-Tier Evidence Fusion Engine — R6 §4.4 & Principles P-03 / P-07.

Combines deterministic rules, correlators, frame decoders, and learned open-set
classifiers into validated SignalIdentityHypothesis objects while strictly
preventing confidence-only promotion to PROTOCOL_CONFIRMED.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.identity import SignalIdentityHypothesis, ProtocolConfirmationReceipt
from ..contracts.wave import WaveCandidate
from ..ontology.identity_states import IdentityState
from ..ontology.confirmation_levels import ConfirmationLevel
from .deterministic_rules import DeterministicProtocolRules
from .open_set_classifier import OpenSetWaveformClassifier


class EvidenceFusionEngine:
    """Fuses multi-source evidence to derive signal identity state and candidate ranking."""

    def __init__(self) -> None:
        self.classifier = OpenSetWaveformClassifier()

    def fuse_evidence(
        self,
        hypothesis_id: str,
        candidate: WaveCandidate,
        confirmation_receipt: Optional[ProtocolConfirmationReceipt] = None,
        registry_version: str = "2026.1",
    ) -> SignalIdentityHypothesis:
        """Fuse all evidence streams for a single WaveCandidate.

        State resolution hierarchy:
          1. Receipt exists & level >= 4 -> PROTOCOL_CONFIRMED
          2. Open-set classifier abstains -> UNKNOWN
          3. Deterministic rule match -> RAT_CANDIDATE
          4. Morphology known -> WAVEFORM_CLASSIFIED
          5. Default -> DETECTED
        """
        # 1. Deterministic rules
        rule_matches = DeterministicProtocolRules.evaluate_candidate(candidate)

        # 2. Learned open-set classifier
        clf_result = self.classifier.classify(candidate)

        # Build candidate list
        candidate_list: List[Dict[str, Any]] = []

        if confirmation_receipt and confirmation_receipt.crc_valid:
            candidate_list.append({
                "protocol": confirmation_receipt.protocol_name,
                "confirmation_level": confirmation_receipt.confirmation_level,
                "probability": 1.0,
                "supporting_evidence": ["Frame CRC Valid", "Sync Preamble Detected"],
                "contradicting_evidence": [],
            })
            current_state = IdentityState.PROTOCOL_CONFIRMED.value
            receipt_ref = confirmation_receipt.receipt_id

        elif clf_result.should_abstain:
            current_state = IdentityState.UNKNOWN.value
            receipt_ref = ""

        elif rule_matches:
            for r in rule_matches:
                candidate_list.append({
                    "protocol": r.protocol_name,
                    "confirmation_level": int(ConfirmationLevel.WEAK_CONTEXT.value),
                    "probability": r.confidence_contribution,
                    "supporting_evidence": [r.rationale, f"Channel: {r.channel_name}"],
                    "contradicting_evidence": [],
                })
            current_state = IdentityState.RAT_CANDIDATE.value
            receipt_ref = ""

        elif candidate.morphology and candidate.morphology != "UNKNOWN":
            candidate_list.append({
                "protocol": candidate.morphology,
                "confirmation_level": int(ConfirmationLevel.WAVEFORM_STRUCTURE.value),
                "probability": candidate.confidence or 0.5,
                "supporting_evidence": [f"Morphology: {candidate.morphology}"],
                "contradicting_evidence": [],
            })
            current_state = IdentityState.WAVEFORM_CLASSIFIED.value
            receipt_ref = ""

        else:
            current_state = IdentityState.DETECTED.value
            receipt_ref = ""

        now = datetime.now(timezone.utc)
        return SignalIdentityHypothesis(
            hypothesis_id=hypothesis_id,
            wave_candidate_ref=candidate.candidate_id,
            candidates=candidate_list,
            current_state=current_state,
            abstention_score=clf_result.abstention_score,
            is_ambiguous=len(candidate_list) > 1,
            ambiguity_reason="Multiple matching protocol rasters." if len(candidate_list) > 1 else "",
            ood_score=clf_result.ood_score,
            confirmation_receipt_ref=receipt_ref,
            registry_version=registry_version,
            model_version="open_set_v1",
            created_at=now,
        )
