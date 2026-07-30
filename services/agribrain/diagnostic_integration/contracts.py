"""Immutable contracts for cross-layer diagnostic integration.

The objects in this module are intentionally independent from the concrete
Layer 2--8 schemas. A diagnostic contribution is an assertion about a belief;
it is never a state update or prescription merely because a layer produced it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Tuple
from uuid import UUID

from services.agribrain.scientific_contracts.authority import AuthorityVector
from services.agribrain.scientific_contracts.exceptions import ContractViolation


SCHEMA_VERSION = "diagnostic_contribution_v2"


class ContributionRole(str, Enum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    UNCERTAINTY_REDUCER = "UNCERTAINTY_REDUCER"


class IdentifiabilityClass(str, Enum):
    """How strongly evidence separates the stated cause from alternatives."""

    IDENTIFIED = "IDENTIFIED"
    PARTIALLY_IDENTIFIED = "PARTIALLY_IDENTIFIED"
    CONFOUNDED = "CONFOUNDED"
    HEURISTIC = "HEURISTIC"


class InfluenceUse(str, Enum):
    DIAGNOSIS = "DIAGNOSIS"
    STATE_UPDATE = "STATE_UPDATE"
    TRAINING = "TRAINING"
    PRESCRIPTION_DRIVER = "PRESCRIPTION_DRIVER"
    MACHINE_EXECUTION = "MACHINE_EXECUTION"


def _nonblank(value: Any, name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ContractViolation(f"DiagnosticContribution requires {name}")
    return result


def _string_tuple(values: Iterable[Any], name: str) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContractViolation(f"{name} must be an iterable of identifiers, not a string")
    normalized = tuple(str(value).strip() for value in values)
    if any(not value for value in normalized):
        raise ContractViolation(f"{name} contains a blank identifier")
    if len(set(normalized)) != len(normalized):
        raise ContractViolation(f"{name} contains duplicate identifiers")
    return normalized


def canonical_data(value: Any) -> Any:
    """Return a deterministic, JSON-safe value without lossy array coercion."""

    if dataclasses.is_dataclass(value):
        return canonical_data(
            {item.name: getattr(value, item.name) for item in dataclasses.fields(value)}
        )
    if isinstance(value, Enum):
        return canonical_data(value.value)
    if isinstance(value, Mapping):
        return {
            str(key): canonical_data(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_data(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [canonical_data(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if hasattr(value, "tolist") and callable(value.tolist):
        return canonical_data(value.tolist())
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractViolation("Diagnostic payload contains a non-finite float")
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID, Path)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {
            "type": "bytes",
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if hasattr(value, "__dict__"):
        return canonical_data(vars(value))
    raise ContractViolation(
        "Diagnostic payload contains unsupported identity type "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def immutable_data(value: Any) -> Any:
    """Canonicalize and recursively freeze mappings/sequences."""

    value = canonical_data(value)
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): immutable_data(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(immutable_data(item) for item in value)
    return value


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        canonical_data(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def authority_allows(authority: AuthorityVector, use: InfluenceUse) -> bool:
    return {
        InfluenceUse.DIAGNOSIS: authority.diagnosis_allowed,
        InfluenceUse.STATE_UPDATE: authority.state_update_allowed,
        InfluenceUse.TRAINING: authority.training_allowed,
        InfluenceUse.PRESCRIPTION_DRIVER: authority.prescription_driver_allowed,
        InfluenceUse.MACHINE_EXECUTION: authority.machine_execution_allowed,
    }[use]


def authority_is_subset(candidate: AuthorityVector, ceiling: AuthorityVector) -> bool:
    fields = dataclasses.fields(AuthorityVector)
    return all(not getattr(candidate, item.name) or getattr(ceiling, item.name) for item in fields)


@dataclass(frozen=True)
class DiagnosticContribution:
    """A lineage-complete, immutable assertion emitted by a diagnostic layer."""

    layer_id: str
    contribution_id: str
    input_belief_id: str
    input_evidence_ids: Tuple[str, ...]
    input_contribution_ids: Tuple[str, ...]
    target_state: str
    contribution_role: ContributionRole
    dependency_families: Tuple[str, ...]
    identifiability_class: IdentifiabilityClass
    authority: AuthorityVector
    supporting_evidence: Tuple[str, ...] = ()
    contradicting_evidence: Tuple[str, ...] = ()
    confounders: Tuple[str, ...] = ()
    block_reasons: Tuple[str, ...] = ()
    confidence: float = 1.0
    payload: Mapping[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = SCHEMA_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "layer_id", _nonblank(self.layer_id, "layer_id").upper())
        object.__setattr__(self, "contribution_id", _nonblank(self.contribution_id, "contribution_id"))
        object.__setattr__(self, "input_belief_id", _nonblank(self.input_belief_id, "input_belief_id"))
        object.__setattr__(self, "target_state", _nonblank(self.target_state, "target_state"))
        object.__setattr__(self, "generated_at", _nonblank(self.generated_at, "generated_at"))
        object.__setattr__(self, "schema_version", _nonblank(self.schema_version, "schema_version"))

        for field_name in (
            "input_evidence_ids",
            "input_contribution_ids",
            "supporting_evidence",
            "contradicting_evidence",
            "dependency_families",
            "confounders",
            "block_reasons",
        ):
            object.__setattr__(self, field_name, _string_tuple(getattr(self, field_name), field_name))

        if not isinstance(self.contribution_role, ContributionRole):
            raise ContractViolation("DiagnosticContribution requires typed contribution_role")
        if not isinstance(self.identifiability_class, IdentifiabilityClass):
            raise ContractViolation("DiagnosticContribution requires typed identifiability_class")
        if not isinstance(self.authority, AuthorityVector):
            raise ContractViolation("DiagnosticContribution requires AuthorityVector")
        if not math.isfinite(float(self.confidence)) or not (0.0 <= float(self.confidence) <= 1.0):
            raise ContractViolation(
                f"DiagnosticContribution confidence out of bounds: {self.confidence}"
            )
        if not self.input_evidence_ids and not self.input_contribution_ids:
            raise ContractViolation(
                "DiagnosticContribution requires input evidence or input contribution ancestry"
            )
        declared_evidence = set(self.input_evidence_ids)
        undeclared = (
            set(self.supporting_evidence) | set(self.contradicting_evidence)
        ) - declared_evidence
        if undeclared:
            raise ContractViolation(
                "supporting/contradicting evidence must be declared in input_evidence_ids: "
                + ", ".join(sorted(undeclared))
            )
        if set(self.supporting_evidence) & set(self.contradicting_evidence):
            raise ContractViolation("the same evidence cannot both support and contradict a contribution")
        if not self.dependency_families:
            raise ContractViolation("DiagnosticContribution requires dependency_families")

        payload = canonical_data(dict(self.payload))
        if not isinstance(payload, dict):
            raise ContractViolation("DiagnosticContribution payload must be a mapping")
        object.__setattr__(self, "payload", immutable_data(payload))

        expected_hash = canonical_hash(self.identity_payload())
        if self.content_hash and self.content_hash != expected_hash:
            raise ContractViolation("DiagnosticContribution content_hash does not match content")
        object.__setattr__(self, "content_hash", expected_hash)

    def identity_payload(self) -> Dict[str, Any]:
        """Content-addressed fields; deliberately excludes generated_at."""

        return {
            "schema_version": self.schema_version,
            "layer_id": self.layer_id,
            "contribution_id": self.contribution_id,
            "input_belief_id": self.input_belief_id,
            "input_evidence_ids": self.input_evidence_ids,
            "input_contribution_ids": self.input_contribution_ids,
            "target_state": self.target_state,
            "contribution_role": self.contribution_role,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "dependency_families": self.dependency_families,
            "confounders": self.confounders,
            "identifiability_class": self.identifiability_class,
            "authority": self.authority,
            "block_reasons": self.block_reasons,
            "confidence": float(self.confidence),
            "payload": self.payload,
        }

    def validate(self) -> None:
        """Compatibility method; construction already enforces every invariant."""

        if canonical_hash(self.identity_payload()) != self.content_hash:
            raise ContractViolation("DiagnosticContribution was mutated after construction")

    def to_dict(self) -> Dict[str, Any]:
        data = canonical_data(self.identity_payload())
        data.update({"generated_at": self.generated_at, "content_hash": self.content_hash})
        return data
