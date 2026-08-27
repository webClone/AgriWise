"""Fail-closed authorization contract for farmer-facing prescriptions.

Layer 2--5 outputs are scientific evidence, not prescriptions.  This envelope
is the only contract allowed to carry exact actions across the public
serialization boundary.  Its identity binds the selected L8 payload to the
belief, tribunal, influence manifest, policy snapshot, and final plan that
authorized it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Tuple

from .exceptions import ContractViolation


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_data(value: Any) -> Any:
    """Return a deterministic JSON-compatible representation."""

    if isinstance(value, Mapping):
        return {
            str(key): canonical_data(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_data(item) for item in value]
    if hasattr(value, "value"):
        return canonical_data(value.value)
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        canonical_data(value), sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContractViolation(f"Prescription authorization requires {field_name}")
    return text


def _required_hash(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name).lower()
    if not _SHA256_RE.fullmatch(text):
        raise ContractViolation(
            f"Prescription authorization {field_name} must be a SHA-256 hash"
        )
    return text


def _immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(canonical_data(dict(value)))


@dataclass(frozen=True)
class AuthorizedActionV1:
    """Exact L8-selected action payload approved for public serialization."""

    action_id: str
    action_type: str
    priority_score: float
    urgency_score: float
    confidence: str
    rationale: str
    rate: Mapping[str, Any] = field(default_factory=dict)
    timing: Mapping[str, Any] = field(default_factory=dict)
    zone_targets: Tuple[str, ...] = ()
    requires_confirmation: bool = True
    machine_execution_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", _required_text(self.action_id, "action_id"))
        object.__setattr__(self, "action_type", _required_text(self.action_type, "action_type"))
        for name in ("priority_score", "urgency_score"):
            try:
                score = float(getattr(self, name))
            except (TypeError, ValueError) as exc:
                raise ContractViolation(f"Prescription authorization requires numeric {name}") from exc
            if not 0.0 <= score <= 1.0:
                raise ContractViolation(f"Prescription authorization {name} must be within [0, 1]")
            object.__setattr__(self, name, score)
        object.__setattr__(self, "confidence", _required_text(self.confidence, "confidence"))
        object.__setattr__(self, "rationale", str(self.rationale or ""))
        object.__setattr__(self, "rate", _immutable_mapping(self.rate or {}))
        object.__setattr__(self, "timing", _immutable_mapping(self.timing or {}))
        object.__setattr__(
            self, "zone_targets", tuple(str(value) for value in self.zone_targets)
        )
        if self.machine_execution_allowed and self.requires_confirmation:
            raise ContractViolation(
                "Machine-executable actions cannot still require confirmation"
            )

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "priority_score": self.priority_score,
            "urgency_score": self.urgency_score,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "rate": dict(self.rate),
            "timing": dict(self.timing),
            "zone_targets": list(self.zone_targets),
            "requires_confirmation": self.requires_confirmation,
            "machine_execution_allowed": self.machine_execution_allowed,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuthorizedActionV1":
        return cls(
            action_id=value.get("action_id", ""),
            action_type=value.get("action_type", ""),
            priority_score=value.get("priority_score", -1.0),
            urgency_score=value.get("urgency_score", -1.0),
            confidence=value.get("confidence", ""),
            rationale=value.get("rationale", ""),
            rate=value.get("rate") or {},
            timing=value.get("timing") or {},
            zone_targets=tuple(value.get("zone_targets") or ()),
            requires_confirmation=bool(value.get("requires_confirmation", True)),
            machine_execution_allowed=bool(
                value.get("machine_execution_allowed", False)
            ),
        )

    @classmethod
    def from_l8_action(cls, value: Any) -> "AuthorizedActionV1":
        """Capture the exact action fields covered by L8's content hash."""

        action_type = getattr(value, "action_type", "")
        confidence = getattr(value, "confidence", "")
        rate = getattr(value, "rate", None)
        timing = getattr(value, "time_window", None)
        breakdown = getattr(value, "priority_breakdown", None)
        return cls(
            action_id=getattr(value, "action_id", ""),
            action_type=getattr(action_type, "value", action_type),
            priority_score=getattr(value, "priority_score", -1.0),
            urgency_score=getattr(breakdown, "urgency_score", -1.0),
            confidence=getattr(confidence, "value", confidence),
            rationale=getattr(value, "explain", ""),
            rate=({
                "recommended": getattr(rate, "recommended", None),
                "min_safe": getattr(rate, "min_safe", None),
                "max_safe": getattr(rate, "max_safe", None),
                "unit": getattr(rate, "unit", ""),
            } if rate is not None else {}),
            timing=({
                "earliest": getattr(timing, "earliest", ""),
                "latest": getattr(timing, "latest", ""),
                "optimal": getattr(timing, "optimal", None),
            } if timing is not None else {}),
            zone_targets=tuple(getattr(value, "zone_targets", ()) or ()),
            requires_confirmation=bool(
                getattr(value, "requires_confirmation", True)
            ),
            machine_execution_allowed=False,
        )


@dataclass(frozen=True)
class PrescriptionAuthorizationEnvelopeV1:
    """Content-addressed proof that exact L8 actions may leave the pipeline."""

    input_belief_id: str
    tribunal_content_hash: str
    prescription_manifest_hash: str
    prescription_manifest_entry_ids: Tuple[str, ...]
    policy_snapshot_hash: str
    l8_run_id: str
    l8_content_hash: str
    final_execution_plan_hash: str
    actions: Tuple[AuthorizedActionV1, ...]
    schema_version: str = "prescription_authorization_envelope_v1"
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "input_belief_id", _required_text(self.input_belief_id, "input_belief_id")
        )
        for name in (
            "tribunal_content_hash",
            "prescription_manifest_hash",
            "policy_snapshot_hash",
            "l8_content_hash",
            "final_execution_plan_hash",
        ):
            object.__setattr__(self, name, _required_hash(getattr(self, name), name))
        object.__setattr__(self, "l8_run_id", _required_text(self.l8_run_id, "l8_run_id"))
        entry_ids = tuple(sorted({_required_text(v, "manifest entry id") for v in self.prescription_manifest_entry_ids}))
        if not entry_ids:
            raise ContractViolation(
                "Prescription authorization requires selected manifest entries"
            )
        object.__setattr__(self, "prescription_manifest_entry_ids", entry_ids)
        actions = tuple(
            value if isinstance(value, AuthorizedActionV1) else AuthorizedActionV1.from_mapping(value)
            for value in self.actions
        )
        if not actions:
            raise ContractViolation("Prescription authorization requires at least one action")
        if len({action.action_id for action in actions}) != len(actions):
            raise ContractViolation("Prescription authorization contains duplicate action IDs")
        object.__setattr__(self, "actions", actions)
        expected = canonical_hash(self.identity_payload())
        supplied = str(self.content_hash or "").lower()
        if supplied and supplied != expected:
            raise ContractViolation(
                "Prescription authorization content_hash does not match content"
            )
        object.__setattr__(self, "content_hash", expected)

    def identity_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "input_belief_id": self.input_belief_id,
            "tribunal_content_hash": self.tribunal_content_hash,
            "prescription_manifest_hash": self.prescription_manifest_hash,
            "prescription_manifest_entry_ids": self.prescription_manifest_entry_ids,
            "policy_snapshot_hash": self.policy_snapshot_hash,
            "l8_run_id": self.l8_run_id,
            "l8_content_hash": self.l8_content_hash,
            "final_execution_plan_hash": self.final_execution_plan_hash,
            "actions": [action.to_dict() for action in self.actions],
        }

    def to_dict(self) -> dict:
        return {**canonical_data(self.identity_payload()), "content_hash": self.content_hash}

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> "PrescriptionAuthorizationEnvelopeV1":
        if not isinstance(value, Mapping):
            raise ContractViolation("Prescription authorization envelope must be a mapping")
        if value.get("schema_version") != "prescription_authorization_envelope_v1":
            raise ContractViolation("Unsupported prescription authorization schema")
        return cls(
            input_belief_id=value.get("input_belief_id", ""),
            tribunal_content_hash=value.get("tribunal_content_hash", ""),
            prescription_manifest_hash=value.get("prescription_manifest_hash", ""),
            prescription_manifest_entry_ids=tuple(
                value.get("prescription_manifest_entry_ids") or ()
            ),
            policy_snapshot_hash=value.get("policy_snapshot_hash", ""),
            l8_run_id=value.get("l8_run_id", ""),
            l8_content_hash=value.get("l8_content_hash", ""),
            final_execution_plan_hash=value.get("final_execution_plan_hash", ""),
            actions=tuple(value.get("actions") or ()),
            schema_version=value.get("schema_version", ""),
            content_hash=value.get("content_hash", ""),
        )


def selected_entries_exist(
    envelope: PrescriptionAuthorizationEnvelopeV1,
    manifest_entries: Iterable[Mapping[str, Any]],
) -> bool:
    available = {
        str(entry.get("contribution_id") or "")
        for entry in manifest_entries
        if isinstance(entry, Mapping)
    }
    return set(envelope.prescription_manifest_entry_ids).issubset(available)
