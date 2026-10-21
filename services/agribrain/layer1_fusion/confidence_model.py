"""
Layer 1 Confidence Model.

Deterministic rule-based confidence scoring.
No ML, no random.

final_confidence = min(source, qa, spatial, freshness, role_ceiling, conflict_ceiling)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .schemas import EvidenceConflict, EvidenceItem, DATA_STATUS_CEILING

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real


# Role ceilings per source family
# Harmonized with SOURCE_CONFIDENCE_CEILING in fusion_rules.py.
# These represent instrument-level measurement fidelity limits.
ROLE_CEILINGS: Dict[str, float] = {
    "sensor":           0.95,
    "sentinel2":        0.88,
    "sentinel1":        0.78,
    "sentinel5p":       0.75,
    "eo_foundation":    0.78,
    "environment":      0.82,
    "weather_forecast": 0.70,
    "geo_context":      0.85,
    "perception":       0.72,
    "user_event":       0.92,
    "history":          0.45,
    "drone_structural": 0.90,
    "l0_state":         0.80,
    "raster_composite": 0.85,
    "zone_segmentation": 0.75,
}

# Weak evidence categories (capped lower)
_WEAK_EVIDENCE = {
    "model_estimate": 0.50,
    "forecast": 0.60,
    "static_prior": 0.75,
    "diagnostic": 0.55,
}


def _is_qualified_support(counterpart: Optional[EvidenceItem]) -> bool:
    """Return True if counterpart is qualified to impose scientific penalties on an evidence item."""
    if counterpart is None:
        return True  # Fallback for synthetic/unbound conflict references in unit tests
    if getattr(counterpart, "diagnostic_only", False):
        return False
    if not getattr(counterpart, "state_update_allowed", True):
        return False
    if getattr(counterpart, "production_usable", True) is False:
        return False
    if getattr(counterpart, "data_status", "") in ("unavailable", "fallback"):
        return False

    conf = finite_real(getattr(counterpart, "confidence", None))
    if conf is None or conf <= 0.0:
        return False

    rel = finite_real(getattr(counterpart, "reliability", None))
    if rel is None or rel <= 0.0:
        return False

    return True


def compute_confidence(
    item: EvidenceItem,
    conflicts: List[EvidenceConflict],
    items_by_id: Optional[Dict[str, EvidenceItem]] = None,
) -> float:
    """Compute final confidence for an evidence item.

    Uses: min(source_confidence, qa_score, freshness, role_ceiling,
              observation_type_ceiling, conflict_penalty)
    """
    # Source confidence (from adapter)
    fin_conf = finite_real(item.confidence)
    source_conf = 0.0 if (fin_conf is None or fin_conf < 0.0) else min(1.0, fin_conf)

    # Freshness
    fin_fresh = finite_real(item.freshness_score)
    freshness = 0.0 if (fin_fresh is None or fin_fresh < 0.0) else min(1.0, fin_fresh)

    # Role ceiling
    role_ceiling = ROLE_CEILINGS.get(item.source_family, 0.50)

    # Observation type ceiling
    obs_ceiling = _WEAK_EVIDENCE.get(item.observation_type, 1.0)

    # Data status ceiling (defense-in-depth)
    status_ceiling = DATA_STATUS_CEILING.get(item.data_status, 0.5)

    # Conflict penalty
    conflict_penalty = 1.0
    for c in conflicts:
        if c.source_a == item.evidence_id or c.source_b == item.evidence_id:
            # Shield qualified sources from zero-quality / diagnostic-only / state-ineligible counterparts
            if items_by_id is not None:
                counterpart_id = c.source_b if c.source_a == item.evidence_id else c.source_a
                counterpart = items_by_id.get(counterpart_id)
                if counterpart is not None and not _is_qualified_support(counterpart):
                    continue

            if c.severity == "major":
                conflict_penalty = min(conflict_penalty, 0.5)
            elif c.severity == "moderate":
                conflict_penalty = min(conflict_penalty, 0.7)
            elif c.severity == "minor":
                conflict_penalty = min(conflict_penalty, 0.85)

    # Reliability from QA
    fin_qa = finite_real(item.reliability)
    qa_score = 0.0 if (fin_qa is None or fin_qa < 0.0) else min(1.0, fin_qa)

    # Final: min of all components
    final = min(
        source_conf,
        qa_score,
        freshness,
        role_ceiling,
        obs_ceiling,
        status_ceiling,
        conflict_penalty,
    )

    return max(0.0, min(1.0, final))


def compute_confidence_batch(
    items: List[EvidenceItem],
    conflicts: List[EvidenceConflict],
) -> List[EvidenceItem]:
    """Update confidence for all items considering conflicts."""
    items_by_id = {item.evidence_id: item for item in items if getattr(item, "evidence_id", None)}
    for item in items:
        item.confidence = compute_confidence(item, conflicts, items_by_id=items_by_id)
    return items
