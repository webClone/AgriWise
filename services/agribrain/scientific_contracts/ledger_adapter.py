"""Scientific Contracts — Strict State Support Ledger Normalization Adapter.

Enforces Amendment 1: Converts list to dict, validates entries, rejects duplicate states,
rejects non-dict items, and raises ContractViolation on malformed or unsupported types.
"""

from __future__ import annotations

from typing import Any, Dict

from .exceptions import ContractViolation
from .state_status import StateSupportStatus, normalize_status
from .state_support import ObservationRelationship, StateSupportRecord


_RELATIONSHIP_STATUSES = {
    "observed": ObservationRelationship.DIRECT,
    "indirectly_observed": ObservationRelationship.INDIRECT,
    "proxy_conditioned": ObservationRelationship.PROXY,
}


def canonicalize_state_support_record(state: str, value: Dict[str, Any]) -> Dict[str, Any]:
    """Convert either legacy producer vocabulary into the one ledger schema."""
    raw = dict(value)
    declared_state = raw.get("state")
    if declared_state is not None and str(declared_state).strip() != state:
        raise ContractViolation(
            f"state_support_key_mismatch:{state}:{declared_state}"
        )
    accepted_count = _accepted_update_count(
        raw.get("accepted_update_count", 0), state
    )
    raw_status = str(raw.get("support_status") or raw.get("status") or "").strip()
    relationship_raw = str(raw.get("observation_relationship") or "").strip()
    relationship = _RELATIONSHIP_STATUSES.get(raw_status)
    if relationship is None:
        try:
            relationship = ObservationRelationship(relationship_raw or "none")
        except ValueError as exc:
            raise ContractViolation(
                f"unknown_observation_relationship:{relationship_raw}"
            ) from exc

    if raw_status in _RELATIONSHIP_STATUSES:
        support_status = (
            StateSupportStatus.ASSIMILATED
            if accepted_count > 0
            else StateSupportStatus.PRIOR_CONSTRAINED
        )
    else:
        support_status = normalize_status(
            raw_status or "unsupported", producer="state_support_ledger"
        )

    source_ids = raw.get("source_feature_ids")
    if source_ids is None:
        source_ids = raw.get("observation_features", raw.get("support", []))
    if not isinstance(source_ids, (list, tuple, set)):
        raise ContractViolation(f"invalid_source_feature_ids:{state}")

    block_reasons = raw.get("block_reasons") or []
    if not isinstance(block_reasons, (list, tuple, set)):
        raise ContractViolation(f"invalid_block_reasons:{state}")
    if raw.get("exclusion_reason"):
        block_reasons = [*block_reasons, str(raw["exclusion_reason"])]

    accepted_count = _counter(raw.get("accepted_update_count", 0), "accepted_update_count", state)
    direct_count = _counter(raw.get("direct_observation_count", 0), "direct_observation_count", state)
    proxy_count = _counter(raw.get("proxy_observation_count", 0), "proxy_observation_count", state)
    indirect_count = _counter(raw.get("indirect_observation_count", 0), "indirect_observation_count", state)

    canonical = StateSupportRecord(
        state=state,
        support_status=support_status,
        observation_relationship=relationship,
        source_feature_ids=tuple(sorted({str(item) for item in source_ids if str(item).strip()})),
        accepted_update_count=accepted_count,
        direct_observation_count=direct_count,
        proxy_observation_count=proxy_count,
        indirect_observation_count=indirect_count,
        prior_variance=raw.get("prior_variance"),
        posterior_variance=raw.get("posterior_variance"),
        information_gain=raw.get("information_gain"),
        spatial_support=str(raw.get("spatial_support") or "none"),
        authority_ceiling=str(raw.get("authority_ceiling") or "DIAGNOSTIC"),
        block_reasons=tuple(dict.fromkeys(str(item) for item in block_reasons if str(item).strip())),
    ).to_dict()

    for key, item in raw.items():
        if key not in {"status", "support", "observation_features", "exclusion_reason"} and key not in canonical:
            canonical[key] = item
    return canonical


def _counter(value: Any, name: str, state: str) -> int:
    if isinstance(value, bool):
        raise ContractViolation(f"invalid_{name}:{state}")
    try:
        result = int(value or 0)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractViolation(f"invalid_{name}:{state}") from exc
    try:
        if float(value or 0) != float(result) or result < 0:
            raise ContractViolation(f"invalid_{name}:{state}")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractViolation(f"invalid_{name}:{state}") from exc
    return result


def _accepted_update_count(value: Any, state: str) -> int:
    return _counter(value, "accepted_update_count", state)


def validate_ledger_dict(value: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Validate that every dict entry is a state support record dict."""
    result: Dict[str, Dict[str, Any]] = {}
    for state_key, item in value.items():
        if not isinstance(state_key, str) or not state_key.strip():
            raise ContractViolation("invalid_state_support_key")
        if not isinstance(item, dict):
            raise ContractViolation(f"invalid_state_support_entry_type:{type(item).__name__}")
        result[state_key] = canonicalize_state_support_record(state_key, item)
    return result


def index_state_support_ledger(value: Any) -> Dict[str, Dict[str, Any]]:
    """Strictly convert list or dict into canonical Dict[str, StateSupportRecord].

    Does NOT silently return {} for malformed values.
    Raises ContractViolation on invalid schemas.
    """
    if value is None:
        raise ContractViolation("state_support_ledger_is_none")

    if isinstance(value, dict):
        return validate_ledger_dict(value)

    if isinstance(value, list):
        indexed: Dict[str, Dict[str, Any]] = {}
        for item in value:
            if not isinstance(item, dict):
                raise ContractViolation(
                    f"invalid_state_support_entry:{type(item).__name__}"
                )
            state = item.get("state")
            if not isinstance(state, str) or not state.strip():
                raise ContractViolation("invalid_state_support_entry_missing_state")

            if state in indexed:
                raise ContractViolation(f"duplicate_state_support_entry:{state}")

            indexed[state] = canonicalize_state_support_record(state, item)

        return indexed

    raise ContractViolation(
        f"invalid_state_support_ledger_type:{type(value).__name__}"
    )
