"""Small transition contracts toward the target agricultural state architecture.

These contracts reserve the X/Z/H/M/U boundary without claiming that the
Agricultural World Model, MESIA, or Omega are implemented.  They are immutable,
content-addressed diagnostic contracts and deliberately contain no action,
dose, product, schedule, or machine-execution fields.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Tuple

from .authority import AuthorityVector
from .exceptions import ContractViolation


SCIENTIFIC_STATE_ENVELOPE_V1 = "scientific_state_envelope_v1"
MECHANISM_EXPERT_CONTRIBUTION_V3 = "mechanism_expert_contribution_v3"


def _required_text(value: Any, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ContractViolation(f"{name} is required")
    return normalized


def _identifier_tuple(values: Iterable[Any], name: str) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContractViolation(f"{name} must be an iterable of identifiers")
    normalized = tuple(_required_text(value, name) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ContractViolation(f"{name} contains duplicate identifiers")
    return normalized


def _canonical(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            item.name: _canonical(getattr(value, item.name))
            for item in dataclasses.fields(value)
            if item.name != "content_hash"
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractViolation("transition contract contains a non-finite float")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise ContractViolation(
        "transition contract contains unsupported value type "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def _freeze_mapping(value: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractViolation(f"{name} must be a mapping")

    def freeze(item: Any) -> Any:
        canonical = _canonical(item)
        if isinstance(canonical, dict):
            return MappingProxyType({key: freeze(val) for key, val in canonical.items()})
        if isinstance(canonical, list):
            return tuple(freeze(val) for val in canonical)
        return canonical

    return freeze(value)


def _content_hash(value: Any) -> str:
    encoded = json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _probability_distribution(
    value: Mapping[str, Any],
    name: str,
    *,
    unresolved_required: bool = False,
) -> Mapping[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise ContractViolation(f"{name} must be a non-empty probability mapping")
    normalized = {}
    for key, probability in value.items():
        key_text = _required_text(key, f"{name} key")
        try:
            numeric = float(probability)
        except (TypeError, ValueError) as exc:
            raise ContractViolation(f"{name}[{key_text}] must be numeric") from exc
        if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
            raise ContractViolation(f"{name}[{key_text}] must be within [0, 1]")
        normalized[key_text] = numeric
    if not math.isclose(sum(normalized.values()), 1.0, abs_tol=1e-6):
        raise ContractViolation(f"{name} probabilities must sum to 1")
    if unresolved_required and "UNRESOLVED" not in {key.upper() for key in normalized}:
        raise ContractViolation(f"{name} requires explicit UNRESOLVED mass")
    return MappingProxyType(dict(sorted(normalized.items())))


@dataclass(frozen=True)
class ScientificStateEnvelopeV1:
    """Transition representation of S[t] = (X, Z, H, M, U)."""

    belief_id: str
    worldline_head: str
    X_refs: Tuple[str, ...]
    H_distribution: Mapping[str, float]
    M_refs: Tuple[str, ...]
    U: Mapping[str, Any]
    geometry_version: str
    evidence_cutoff: str
    authority_vector: AuthorityVector
    Z_ref: Optional[str] = None
    schema_version: str = SCIENTIFIC_STATE_ENVELOPE_V1
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "belief_id", _required_text(self.belief_id, "belief_id"))
        object.__setattr__(self, "worldline_head", _required_text(self.worldline_head, "worldline_head"))
        object.__setattr__(self, "geometry_version", _required_text(self.geometry_version, "geometry_version"))
        object.__setattr__(self, "evidence_cutoff", _required_text(self.evidence_cutoff, "evidence_cutoff"))
        object.__setattr__(self, "schema_version", _required_text(self.schema_version, "schema_version"))
        object.__setattr__(self, "X_refs", _identifier_tuple(self.X_refs, "X_refs"))
        object.__setattr__(self, "M_refs", _identifier_tuple(self.M_refs, "M_refs"))
        if not self.X_refs:
            raise ContractViolation("ScientificStateEnvelopeV1 requires explicit X_refs")
        if self.Z_ref is not None:
            object.__setattr__(self, "Z_ref", _required_text(self.Z_ref, "Z_ref"))
        object.__setattr__(
            self,
            "H_distribution",
            _probability_distribution(
                self.H_distribution, "H_distribution", unresolved_required=True,
            ),
        )
        uncertainty = _freeze_mapping(self.U, "U")
        required_u = {"uncertainty", "missingness", "ood_status", "limitations"}
        missing_u = sorted(required_u - set(uncertainty))
        if missing_u:
            raise ContractViolation("U missing required fields: " + ", ".join(missing_u))
        object.__setattr__(self, "U", uncertainty)
        if not isinstance(self.authority_vector, AuthorityVector):
            raise ContractViolation("authority_vector must be AuthorityVector")
        expected = _content_hash(self)
        if self.content_hash and self.content_hash != expected:
            raise ContractViolation("ScientificStateEnvelopeV1 content_hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    def to_dict(self) -> dict[str, Any]:
        data = _canonical(self)
        data["content_hash"] = self.content_hash
        return data


@dataclass(frozen=True)
class MechanismExpertContributionV3:
    """Diagnostic-only mechanism expert contribution over a canonical state."""

    expert_id: str
    expert_version: str
    input_belief_id: str
    target_state: str
    support: float
    contradiction: float
    unknown: float
    evidence_ids: Tuple[str, ...]
    dependency_families: Tuple[str, ...]
    confounders: Tuple[str, ...]
    alternative_hypotheses: Tuple[str, ...]
    applicability_domain: Mapping[str, Any]
    ood_status: str
    predicted_observables: Mapping[str, Any]
    next_discriminating_measurements: Tuple[str, ...]
    uncertainty: Mapping[str, Any]
    authority: AuthorityVector
    schema_version: str = MECHANISM_EXPERT_CONTRIBUTION_V3
    content_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "expert_id", "expert_version", "input_belief_id", "target_state",
            "ood_status", "schema_version",
        ):
            object.__setattr__(
                self, field_name, _required_text(getattr(self, field_name), field_name),
            )
        for field_name in (
            "evidence_ids", "dependency_families", "confounders",
            "alternative_hypotheses", "next_discriminating_measurements",
        ):
            object.__setattr__(
                self,
                field_name,
                _identifier_tuple(getattr(self, field_name), field_name),
            )
        if not self.evidence_ids:
            raise ContractViolation("MechanismExpertContributionV3 requires evidence_ids")
        if not self.dependency_families:
            raise ContractViolation(
                "MechanismExpertContributionV3 requires dependency_families"
            )
        probabilities = (float(self.support), float(self.contradiction), float(self.unknown))
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in probabilities):
            raise ContractViolation("support/contradiction/unknown must be within [0, 1]")
        if not math.isclose(sum(probabilities), 1.0, abs_tol=1e-6):
            raise ContractViolation("support/contradiction/unknown must sum to 1")
        object.__setattr__(self, "support", probabilities[0])
        object.__setattr__(self, "contradiction", probabilities[1])
        object.__setattr__(self, "unknown", probabilities[2])
        for field_name in (
            "applicability_domain", "predicted_observables", "uncertainty",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_mapping(getattr(self, field_name), field_name),
            )
        if not isinstance(self.authority, AuthorityVector):
            raise ContractViolation("authority must be AuthorityVector")
        if self.authority.prescription_driver_allowed or self.authority.machine_execution_allowed:
            raise ContractViolation(
                "MechanismExpertContributionV3 is diagnostic-only and cannot carry "
                "prescription or machine-execution authority"
            )
        expected = _content_hash(self)
        if self.content_hash and self.content_hash != expected:
            raise ContractViolation("MechanismExpertContributionV3 content_hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    def to_dict(self) -> dict[str, Any]:
        data = _canonical(self)
        data["content_hash"] = self.content_hash
        return data
