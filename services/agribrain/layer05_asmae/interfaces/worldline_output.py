"""R5.0: Worldline output — ASMAE proposes events, world model commits.

Design rules:
  1. ASMAE submits WorldlineEventProposal objects.
  2. The canonical world-model service validates, sorts parent IDs,
     creates canonical identity, performs idempotency checking, and commits.
  3. ASMAE NEVER assigns its own event ID.
  4. ASMAE NEVER directly writes to the worldline store.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class ASMAEEventType(Enum):
    """Typed ASMAE events that may be proposed to the canonical worldline."""
    ASMAE_OBSERVATION_ASSIMILATED = "ASMAE_OBSERVATION_ASSIMILATED"
    ASMAE_STATE_FORECAST_CREATED = "ASMAE_STATE_FORECAST_CREATED"
    ASMAE_FORECAST_EVALUATED = "ASMAE_FORECAST_EVALUATED"
    ASMAE_HYPOTHESIS_UPDATED = "ASMAE_HYPOTHESIS_UPDATED"
    ASMAE_STATE_DEMOTED = "ASMAE_STATE_DEMOTED"
    ASMAE_BELIEF_SNAPSHOT = "ASMAE_BELIEF_SNAPSHOT"
    ASMAE_CALIBRATION_UPDATED = "ASMAE_CALIBRATION_UPDATED"
    ASMAE_RETROVALIDATION_COMPLETED = "ASMAE_RETROVALIDATION_COMPLETED"

    # Legacy event types (for backward-compatible adapter)
    ASMAE_RUN_RESULT = "ASMAE_RUN_RESULT"
    ASMAE_CACHED_RESULT = "ASMAE_CACHED_RESULT"


def propose_asmae_event(
    *,
    event_type: ASMAEEventType,
    payload: Mapping[str, Any],
    parent_event_ids: tuple = (),
    geometry_version: str,
    evidence_set_hash: str,
    model_version: str,
    calibration_version: str = "",
    authority_contract_version: str = "authority_v1",
    authority_ref: str,
    observation_or_valid_time: str,
) -> "WorldlineEventProposal":
    """Create a WorldlineEventProposal for submission to the canonical service.

    This is the ONLY sanctioned way ASMAE creates worldline events.
    The proposal must be submitted to CanonicalWorldlineService.commit_proposal().
    """
    if not str(authority_ref or "").strip():
        raise ValueError("authority_ref is required")
    if not str(observation_or_valid_time or "").strip():
        raise ValueError("observation_or_valid_time is required")
    try:
        from services.agribrain.world_model.canonical_worldline import WorldlineEventProposal
    except ImportError:
        try:
            from world_model.canonical_worldline import WorldlineEventProposal
        except ImportError:
            from ...world_model.canonical_worldline import WorldlineEventProposal

    return WorldlineEventProposal(
        event_type=event_type.value,
        payload=dict(payload),
        parent_event_ids=parent_event_ids,
        geometry_version=geometry_version,
        evidence_set_hash=evidence_set_hash,
        model_version=model_version,
        calibration_version=calibration_version,
        authority_contract_version=authority_contract_version,
        authority_ref=authority_ref,
        observation_or_valid_time=observation_or_valid_time,
    )
