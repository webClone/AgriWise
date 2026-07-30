"""
Hotspot Summarizer.

Aggregates multi-frame Farmer Photo results from command-mode revisits
into a zone-level diagnosis summary.

Uses majority-vote for consensus with a mixed-evidence safeguard:
if the best frame shows a severe symptom with high QA but the majority
disagrees, the summary surfaces "mixed_evidence" instead of forcing
a confident consensus.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from layer0.observation_packet import ObservationPacket


@dataclass
class HotspotSummary:
    """Aggregated zone diagnosis from multiple command-mode close-ups."""
    zone_id: str
    mission_id: str
    frame_count: int

    # Best-frame selection
    best_frame_idx: int = 0
    best_frame_qa_score: float = 0.0

    # Aggregated symptom verdict
    top_symptom: str = "unknown"            # e.g., "chlorosis", "necrosis", "healthy"
    symptom_confidence: float = 0.0
    severity: str = "unknown"               # "mild", "moderate", "severe"

    # Evidence quality
    consensus_type: str = "unanimous"       # "unanimous", "majority", "mixed_evidence"

    # Supporting evidence
    symptom_votes: Dict[str, int] = field(default_factory=dict)
    crop_consensus: Optional[str] = None
    organ_consensus: Optional[str] = None


# QA threshold: if best frame has QA >= this and shows a severe symptom,
# it cannot be overruled by a weak majority.
_STRONG_FRAME_QA_THRESHOLD = 0.7
# Vote fraction below which we trigger mixed_evidence if best frame disagrees
_MIXED_EVIDENCE_VOTE_THRESHOLD = 0.6


class HotspotSummarizer:
    """Aggregates multi-frame Farmer Photo results into zone diagnosis."""

    def summarize(
        self,
        packets: List[ObservationPacket],
        zone_id: str,
        mission_id: str,
    ) -> HotspotSummary:
        """Aggregate symptoms across frames with majority-vote + best-frame selection.
        
        Mixed-evidence rule: If the best frame (highest QA) shows a different
        symptom than the majority vote, AND the vote fraction is below 60%,
        the consensus_type is set to "mixed_evidence" to prevent hiding a
        strong minority signal.
        """
        summary = HotspotSummary(
            zone_id=zone_id,
            mission_id=mission_id,
            frame_count=len(packets),
        )

        if not packets:
            return summary

        # Extract per-frame data
        symptoms = []
        crops = []
        organs = []
        qa_scores = []

        for pkt in packets:
            payload = pkt.payload if isinstance(pkt.payload, dict) else {}
            symptom = payload.get("top_symptom", payload.get("symptom", "unknown"))
            crop = payload.get("crop", None)
            organ = payload.get("organ", None)
            qa = getattr(pkt.qa, "scene_score", 0.5) if pkt.qa else 0.5

            symptoms.append(str(symptom))
            crops.append(str(crop) if crop else None)
            organs.append(str(organ) if organ else None)
            qa_scores.append(float(qa))

        # Best frame = highest QA
        best_idx = max(range(len(qa_scores)), key=lambda i: qa_scores[i])
        summary.best_frame_idx = best_idx
        summary.best_frame_qa_score = qa_scores[best_idx]

        # Symptom voting
        symptom_votes: Dict[str, int] = {}
        for s in symptoms:
            symptom_votes[s] = symptom_votes.get(s, 0) + 1
        summary.symptom_votes = symptom_votes

        # Majority symptom
        majority_symptom = max(symptom_votes, key=symptom_votes.get)
        majority_count = symptom_votes[majority_symptom]
        vote_fraction = majority_count / len(symptoms)

        # Best-frame symptom
        best_frame_symptom = symptoms[best_idx]

        # Apply mixed-evidence rule
        if (
            best_frame_symptom != majority_symptom
            and qa_scores[best_idx] >= _STRONG_FRAME_QA_THRESHOLD
            and vote_fraction < _MIXED_EVIDENCE_VOTE_THRESHOLD
        ):
            # Best frame disagrees with weak majority → surface as mixed
            summary.top_symptom = best_frame_symptom
            summary.consensus_type = "mixed_evidence"
            summary.symptom_confidence = qa_scores[best_idx] * 0.6  # Penalised
        elif vote_fraction >= 1.0:
            summary.top_symptom = majority_symptom
            summary.consensus_type = "unanimous"
            summary.symptom_confidence = vote_fraction * _mean(qa_scores)
        else:
            summary.top_symptom = majority_symptom
            summary.consensus_type = "majority"
            summary.symptom_confidence = vote_fraction * _mean(qa_scores)

        # Severity heuristic
        if summary.symptom_confidence >= 0.7:
            summary.severity = "severe"
        elif summary.symptom_confidence >= 0.4:
            summary.severity = "moderate"
        else:
            summary.severity = "mild"

        # Crop / organ consensus (simple majority)
        summary.crop_consensus = _majority([c for c in crops if c])
        summary.organ_consensus = _majority([o for o in organs if o])

        return summary


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _majority(items: List[str]) -> Optional[str]:
    if not items:
        return None
    counts: Dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return max(counts, key=counts.get)
