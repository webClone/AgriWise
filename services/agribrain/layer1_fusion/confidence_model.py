"""
Layer 1 Confidence Model.

Deterministic rule-based confidence scoring.
No ML, no random.

final_confidence = min(source, qa, spatial, freshness, role_ceiling, conflict_ceiling)
"""

from __future__ import annotations

from typing import Dict, List

from .schemas import EvidenceConflict, EvidenceItem


# Role ceilings per source family
ROLE_CEILINGS: Dict[str, float] = {
    "sensor": 0.95,
    "sentinel2": 0.85,
    "sentinel1": 0.65,
    "environment": 0.70,
    "weather_forecast": 0.60,
    "geo_context": 0.75,
    "perception": 0.60,
    "user_event": 0.90,
    "history": 0.35,
}

# Weak evidence categories (capped lower)
_WEAK_EVIDENCE = {
    "model_estimate": 0.50,
    "forecast": 0.60,
    "static_prior": 0.75,
    "diagnostic": 0.55,
}


def compute_confidence(
    item: EvidenceItem,
    conflicts: List[EvidenceConflict],
) -> float:
    """Compute final confidence for an evidence item.

    Uses: min(source_confidence, qa_score, freshness, role_ceiling,
              observation_type_ceiling, conflict_penalty)
    """
    # Source confidence (from adapter)
    source_conf = item.confidence

    # Freshness
    freshness = item.freshness_score

    # Role ceiling
    role_ceiling = ROLE_CEILINGS.get(item.source_family, 0.50)

    # Observation type ceiling
    obs_ceiling = _WEAK_EVIDENCE.get(item.observation_type, 1.0)

    # Conflict penalty
    conflict_penalty = 1.0
    for c in conflicts:
        if c.source_a == item.evidence_id or c.source_b == item.evidence_id:
            if c.severity == "major":
                conflict_penalty = min(conflict_penalty, 0.5)
            elif c.severity == "moderate":
                conflict_penalty = min(conflict_penalty, 0.7)
            elif c.severity == "minor":
                conflict_penalty = min(conflict_penalty, 0.85)

    # Reliability from QA
    qa_score = item.reliability

    # Final: min of all components
    final = min(
        source_conf,
        qa_score,
        freshness,
        role_ceiling,
        obs_ceiling,
        conflict_penalty,
    )

    return max(0.0, min(1.0, final))


def compute_confidence_batch(
    items: List[EvidenceItem],
    conflicts: List[EvidenceConflict],
) -> List[EvidenceItem]:
    """Update confidence for all items considering conflicts."""
    for item in items:
        item.confidence = compute_confidence(item, conflicts)
    return items
