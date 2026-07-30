"""Scientific Contracts — Event Identity & Parent Reference Scheme.

Isolated from world_model and layer packages.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from .exceptions import ContractViolation

WORLDLINE_IDENTITY_V1 = "v1_legacy_payload_hash"
WORLDLINE_IDENTITY_V2 = "worldline_event_identity_v2"
WORLDLINE_CONTRACT_VERSION = "canonical_worldline_v2"


@dataclass(frozen=True)
class ParentRef:
    """Canonical internal parent reference."""
    event_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id}

    def validate(self) -> None:
        if not self.event_id or not self.event_id.strip():
            raise ContractViolation("ParentRef requires event_id")


@dataclass(frozen=True)
class ExternalParentRef:
    """Explicit external parent reference across namespaces or external systems."""
    external_namespace: str
    external_event_id: str
    evidence_ref: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "external_namespace": self.external_namespace,
            "external_event_id": self.external_event_id,
            "evidence_ref": self.evidence_ref,
        }

    def validate(self) -> None:
        if not self.external_namespace or not self.external_namespace.strip():
            raise ContractViolation("ExternalParentRef requires external_namespace")
        if not self.external_event_id or not self.external_event_id.strip():
            raise ContractViolation("ExternalParentRef requires external_event_id")
        if not self.evidence_ref or not self.evidence_ref.strip():
            raise ContractViolation("ExternalParentRef requires evidence_ref")

    def identity_token(self) -> str:
        self.validate()
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
        return f"external_parent_v1:{digest}"


@dataclass(frozen=True)
class EventIdentityInput:
    """Input payload for computing deterministic v2 canonical event IDs."""
    tenant_id: str
    namespace: str
    plot_id: str
    geometry_version: str
    event_type: str
    effective_time: str
    observation_or_valid_time: str
    sorted_parent_ids: Tuple[str, ...]
    evidence_set_hash: str
    payload_hash: str
    model_version: str
    calibration_version: str
    authority_contract_version: str
    authority_ref: str = ""
    state_schema_version: str = "asmae_state_v1_13"
    worldline_contract_version: str = WORLDLINE_CONTRACT_VERSION

    def validate(self) -> None:
        for name in (
            "tenant_id", "namespace", "plot_id", "geometry_version",
            "event_type", "effective_time", "observation_or_valid_time",
            "evidence_set_hash", "payload_hash", "model_version",
            "authority_contract_version", "authority_ref",
            "state_schema_version", "worldline_contract_version",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{name} must not be blank")
        if not isinstance(self.sorted_parent_ids, tuple):
            raise ContractViolation("sorted_parent_ids must be a tuple")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in self.sorted_parent_ids
        ):
            raise ContractViolation("parent IDs must be nonblank strings")


@dataclass(frozen=True)
class EventIdentityRecord:
    """Record linking legacy and canonical identities."""
    event_id: str
    identity_version: str
    canonical_successor_id: Optional[str] = None
    legacy_aliases: Tuple[str, ...] = ()

    @property
    def is_legacy(self) -> bool:
        return self.identity_version == WORLDLINE_IDENTITY_V1

    @property
    def is_v2(self) -> bool:
        return self.identity_version == WORLDLINE_IDENTITY_V2


def _canonical_data(value: Any) -> Any:
    if is_dataclass(value):
        return _canonical_data(asdict(value))
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractViolation("worldline payload contains non-finite float")
        return value
    if isinstance(value, Enum):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_data(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_data(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_canonical_data(item) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, (datetime, date)):
        return str(value)
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    if hasattr(value, "tolist") and callable(value.tolist):
        return _canonical_data(value.tolist())
    if hasattr(value, "item") and callable(value.item):
        return _canonical_data(value.item())
    raise ContractViolation(
        f"worldline payload contains unsupported type:{type(value).__name__}"
    )


def compute_payload_hash(payload: Any) -> str:
    """Compute sha256 hash over deterministic JSON serialization of payload."""
    serialized = json.dumps(
        _canonical_data(payload),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def compute_v1_identity(
    *,
    contract_version: str,
    plot_id: str,
    event_type: str,
    geometry_hash: str,
    effective_at: str,
    authority: str,
    payload: Mapping[str, Any],
) -> str:
    """Compute legacy v1 event identity."""
    identity_input = {
        "contract_version": contract_version,
        "plot_id": plot_id,
        "event_type": event_type,
        "geometry_hash": geometry_hash,
        "effective_at": effective_at,
        "authority": authority,
        "payload": dict(payload) if payload else {},
    }
    return hashlib.sha256(
        json.dumps(identity_input, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def compute_v2_identity(inp: EventIdentityInput) -> str:
    """Compute deterministic v2 canonical identity hash."""
    inp.validate()
    canonical_dict = {
        "identity_schema": WORLDLINE_IDENTITY_V2,
        "worldline_contract_version": inp.worldline_contract_version,
        "tenant_id": inp.tenant_id,
        "namespace": inp.namespace,
        "plot_id": inp.plot_id,
        "geometry_version": inp.geometry_version,
        "event_type": inp.event_type,
        "effective_time": inp.effective_time,
        "observation_or_valid_time": inp.observation_or_valid_time,
        "parent_event_ids": sorted(set(inp.sorted_parent_ids)),
        "evidence_set_hash": inp.evidence_set_hash,
        "payload_hash": inp.payload_hash,
        "model_version": inp.model_version,
        "calibration_version": inp.calibration_version,
        "authority_contract_version": inp.authority_contract_version,
        "authority_ref": inp.authority_ref,
        "state_schema_version": inp.state_schema_version,
    }
    raw = json.dumps(canonical_dict, sort_keys=True, default=str).encode("utf-8")
    return f"evt_v2_{hashlib.sha256(raw).hexdigest()[:32]}"
