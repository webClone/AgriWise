"""
V77: Causal hypothesis tracking.

Tracks likely causes of state changes without pretending they are proven.

Vocabulary states (user-approved, strictly enforced):
  - suspected: initial assignment based on state change pattern
  - supported: multiple evidence sources agree
  - contradicted: evidence contradicts the hypothesis
  - unknown: no evidence to assign a cause
  - externally_confirmed: validated by external source (farmer, sensor)

"confirmed" is NOT a valid status unless external validation exists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import CAUSE_HYPOTHESES, CAUSAL_STATUS_VOCABULARY

logger = logging.getLogger(__name__)


@dataclass
class CausalState:
    """Cause probabilities for a single microzone."""
    microzone_id: str
    cause_probabilities: Dict[str, float] = field(default_factory=dict)
    most_likely_cause: str = "unknown"
    cause_status: str = "unknown"  # From CAUSAL_STATUS_VOCABULARY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "microzone_id": self.microzone_id,
            "cause_probabilities": {
                k: round(v, 4) for k, v in self.cause_probabilities.items()
            },
            "most_likely_cause": self.most_likely_cause,
            "cause_status": self.cause_status,
        }


def track_causes(
    state_result: dict,
    priors: dict,
    crop_context: dict,
) -> Dict[str, Any]:
    """Track causal hypotheses for state changes.

    Uses Bayesian cause probability update from state transitions + priors.
    "unknown" always remains an allowed category.

    Returns per-microzone causal states.
    """
    means = state_result.get("raster_maps", {})
    timeline = state_result.get("state_timeline", [])

    causal_states: Dict[str, CausalState] = {}

    for nid, state in means.items():
        # Initialize uniform cause priors
        probs = {cause: 1.0 / len(CAUSE_HYPOTHESES) for cause in CAUSE_HYPOTHESES}

        # Update based on state values
        probs = _update_from_state(probs, state)

        # Update from layer priors
        probs = _update_from_priors(probs, priors)

        # Normalize
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}

        # Determine most likely cause and status
        best_cause = max(probs, key=probs.get)  # type: ignore
        best_prob = probs[best_cause]

        if best_cause == "unknown":
            status = "unknown"
        elif best_prob > 0.6:
            status = "supported"
        elif best_prob > 0.3:
            status = "suspected"
        else:
            status = "unknown"

        # Enforce vocabulary
        if status not in CAUSAL_STATUS_VOCABULARY:
            status = "unknown"

        causal_states[nid] = CausalState(
            microzone_id=nid,
            cause_probabilities=probs,
            most_likely_cause=best_cause,
            cause_status=status,
        )

    result = {
        "causal_states": {nid: cs.to_dict() for nid, cs in causal_states.items()},
        "vocabulary_used": list(CAUSAL_STATUS_VOCABULARY),
        "n_microzones": len(causal_states),
    }

    logger.info("V77 causal tracking: %d microzones tracked", len(causal_states))
    return result


def _update_from_state(
    probs: Dict[str, float], state: List[float],
) -> Dict[str, float]:
    """Update cause probabilities based on current state values."""
    from ..config import (
        IDX_CANOPY_WATER, IDX_ROOT_ZONE_WATER, IDX_SALINITY,
        IDX_THERMAL, IDX_BIOTIC, IDX_BARE_SOIL, IDX_SURFACE_WETNESS,
    )

    # Water stress indicators
    if len(state) > IDX_ROOT_ZONE_WATER and state[IDX_ROOT_ZONE_WATER] < 0.3:
        probs["water_stress"] *= 2.0

    # Salinity
    if len(state) > IDX_SALINITY and state[IDX_SALINITY] > 0.4:
        probs["salinity_constraint"] *= 2.5

    # Thermal stress
    if len(state) > IDX_THERMAL and state[IDX_THERMAL] > 0.5:
        probs["thermal_stress"] *= 2.0

    # Biotic confounder
    if len(state) > IDX_BIOTIC and state[IDX_BIOTIC] > 0.3:
        probs["biotic_confounder_possible"] *= 2.0

    # Surface wetness event
    if len(state) > IDX_SURFACE_WETNESS and state[IDX_SURFACE_WETNESS] > 0.7:
        probs["surface_wetness_event"] *= 2.5

    # Bare soil → harvest or tillage
    if len(state) > IDX_BARE_SOIL and state[IDX_BARE_SOIL] > 0.7:
        probs["harvest_reset"] *= 1.5
        probs["tillage_reset"] *= 1.5

    return probs


def _update_from_priors(
    probs: Dict[str, float], priors: dict,
) -> Dict[str, float]:
    """Update cause probabilities from layer priors."""
    l5 = priors.get("layer5", {})
    if isinstance(l5, dict) and l5.get("usable_as_prior"):
        biotic_risk = l5.get("biotic_threat_risk", 0.0)
        if biotic_risk > 0.3:
            probs["biotic_confounder_possible"] *= (1.0 + biotic_risk)

    l3 = priors.get("layer3", {})
    if isinstance(l3, dict) and l3.get("usable_as_prior"):
        water_balance = l3.get("water_balance")
        if water_balance is not None and water_balance < -0.3:
            probs["water_stress"] *= 1.5

    return probs
