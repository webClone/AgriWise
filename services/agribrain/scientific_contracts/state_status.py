"""Scientific Contracts — Frozen State Support Status Enum & Telemetry.

Isolated from world_model and layer packages.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, List, Optional

from .exceptions import ContractViolation

logger = logging.getLogger(__name__)


class StateSupportStatus(str, Enum):
    """Canonical state support status enum."""
    UNSUPPORTED = "unsupported"
    PRIOR_CONSTRAINED = "prior_constrained"
    TEMPORALLY_CONDITIONED = "temporally_conditioned"
    SPATIALLY_CONDITIONED = "spatially_conditioned"
    MODEL_PROPAGATED = "model_propagated"
    ASSIMILATED = "assimilated"


# Legacy status aliases mapping strictly to canonical enum values
_ALIASES: Dict[str, StateSupportStatus] = {
    "timeseries_conditioned": StateSupportStatus.TEMPORALLY_CONDITIONED,
    "archive_timeseries_conditioned": StateSupportStatus.TEMPORALLY_CONDITIONED,
    "spatial_assimilated": StateSupportStatus.ASSIMILATED,
    "process_model_only": StateSupportStatus.MODEL_PROPAGATED,
}

# Telemetry log for alias tracking
TELEMETRY_LOG: List[Dict[str, str]] = []


def normalize_status(raw: str, producer: str = "") -> StateSupportStatus:
    """Strict status normalization with telemetry logging.

    Raises ContractViolation on unknown or misspelled statuses.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ContractViolation("empty_or_non_string_state_status")

    raw_str = raw.strip()

    if raw_str in _ALIASES:
        canonical = _ALIASES[raw_str]
        entry = {
            "producer": producer or "unknown",
            "raw_status": raw_str,
            "normalized_status": canonical.value,
        }
        TELEMETRY_LOG.append(entry)
        logger.warning(
            "Legacy StateSupportStatus alias '%s' normalized to '%s' (producer: %s)",
            raw_str, canonical.value, producer
        )
        return canonical

    try:
        return StateSupportStatus(raw_str)
    except ValueError as exc:
        raise ContractViolation(
            f"unknown_state_support_status:{raw_str}"
        ) from exc
