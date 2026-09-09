"""R5.0: Canonical worldline service — system-wide owner.

This is the SINGLE canonical implementation for plot worldline events.
It validates, assigns identity, and persists events. ASMAE and other
layers propose events through WorldlineEventProposal but do NOT
directly write or assign canonical identity.

Migration path from layer05_asmae/history/worldline_service.py:
  R5.0: This module created; old module becomes delegating adapter.
  R5.1: Internal callers migrated.
  R5.2: External import warnings become test errors.
  R5.3: Adapter removed after artifact compatibility review.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from services.agribrain.scientific_contracts.exceptions import ContractViolation


class SecurityViolation(ContractViolation):
    """Raised when an operation violates filesystem containment or namespace boundaries."""
    pass


class CorruptedWorldlineError(ContractViolation):
    """Raised when a worldline file exists but contains corrupted or invalid JSON."""
    pass


from .event_identity import (
    WORLDLINE_CONTRACT_VERSION,
    WORLDLINE_IDENTITY_V2,
    EventIdentityInput,
    EventIdentityRecord,
    ExternalParentRef,
    ParentRef,
    compute_payload_hash,
    compute_v2_identity,
)

logger = logging.getLogger(__name__)


CANONICAL_WORLDLINE_ROOT = (
    Path(__file__).resolve().parents[1] / "artifacts" / "plot_worldlines"
)

VOLATILE_IDENTITY_KEYS = {
    "generated_at",
    "published_at",
    "run_started_at",
    "run_completed_at",
    "artifact_published_at",
    "render_published_at",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable(value: Any) -> str:
    return compute_payload_hash(_public(value))


def _public(value: Any) -> Any:
    """Strip volatile keys from payload for identity computation."""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public(item)
            for key, item in value.items()
            if str(key) not in VOLATILE_IDENTITY_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            key: _public(item)
            for key, item in vars(value).items()
            if not key.startswith("_") and key not in VOLATILE_IDENTITY_KEYS
        }
    return value


def _canonical_parent(parent: Any) -> tuple[str, Optional[Dict[str, Any]]]:
    if isinstance(parent, ExternalParentRef):
        return parent.identity_token(), parent.to_dict()
    if isinstance(parent, ParentRef):
        parent.validate()
        return parent.event_id, None
    if isinstance(parent, str) and parent.strip():
        return parent.strip(), None
    raise ValueError("parent references must be ParentRef, ExternalParentRef, or nonblank internal event ID")


class CanonicalWorldlineService:
    """System-wide canonical worldline service.

    Owns the single backing store for all plot worldline events.
    ASMAE and other layers interact through proposals, not direct writes.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or CANONICAL_WORLDLINE_ROOT)

    @staticmethod
    def _plot_key(plot_id: str) -> str:
        return hashlib.sha256(str(plot_id).encode("utf-8")).hexdigest()[:32]

    def _plot_dir(self, plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default") -> Path:
        if not str(plot_id).strip():
            raise ValueError("plot_id is required")
        t_clean = str(tenant_id).strip()
        ns_clean = str(namespace).strip()
        if not t_clean:
            raise ValueError("tenant_id is required")
        if not ns_clean:
            raise ValueError("namespace is required")

        for seg in (t_clean, ns_clean):
            if ".." in seg or "/" in seg or "\\" in seg:
                raise SecurityViolation(f"Path traversal detected in tenant or namespace: {seg}")

        resolved_root = self.root.resolve()
        target = (self.root / t_clean / ns_clean / self._plot_key(plot_id)).resolve()
        if not target.is_relative_to(resolved_root):
            raise SecurityViolation(f"Path traversal detected in worldline access: {target}")
        return target

    def _head_path(self, plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default") -> Path:
        return self._plot_dir(plot_id, tenant_id, namespace) / "head.json"

    def _event_path(self, plot_id: str, event_id: str, tenant_id: str = "default_tenant", namespace: str = "default") -> Path:
        return self._plot_dir(plot_id, tenant_id, namespace) / "events" / f"{event_id}.json"

    @staticmethod
    def _read(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            content = path.read_text(encoding="utf-8")
            if not content.strip():
                raise CorruptedWorldlineError(f"Empty worldline file at {path}")
            value = json.loads(content)
            if not isinstance(value, dict):
                raise CorruptedWorldlineError(f"Worldline file at {path} did not contain a JSON object")
            return value
        except json.JSONDecodeError as exc:
            raise CorruptedWorldlineError(f"Worldline storage corruption at {path}: {exc}") from exc
        except OSError as exc:
            raise CorruptedWorldlineError(f"Failed to read worldline file at {path}: {exc}") from exc

    @staticmethod
    def _atomic(path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(
            path.suffix
            + f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
        )
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        last_error = None
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                return
            except OSError as exc:
                last_error = exc
                time.sleep(0.01 * (2 ** attempt))
        temporary.unlink(missing_ok=True)
        raise last_error or OSError(f"could not publish worldline file {path}")

    @contextmanager
    def _head_lock(self, plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default"):
        plot_dir = self._plot_dir(plot_id, tenant_id, namespace)
        plot_dir.mkdir(parents=True, exist_ok=True)
        lock_path = plot_dir / "head.lock"
        descriptor = None
        for _ in range(100):
            try:
                descriptor = os.open(
                    str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                break
            except FileExistsError:
                try:
                    if time.time() - lock_path.stat().st_mtime > 180.0:
                        lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                time.sleep(0.01)
        if descriptor is None:
            raise TimeoutError("plot worldline head is locked")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
            yield
        finally:
            try:
                lock_path.unlink()
            except OSError:
                pass

    def load_head(self, plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default") -> Dict[str, Any]:
        """Load current head state for a tenant plot."""
        return self._read(self._head_path(plot_id, tenant_id, namespace))

    def load_event(self, plot_id: str, event_id: str, tenant_id: str = "default_tenant", namespace: str = "default") -> Dict[str, Any]:
        """Load specific event by ID for a tenant plot."""
        return self._read(self._event_path(plot_id, event_id, tenant_id, namespace))

    def validate_proposal(
        self, proposal: "WorldlineEventProposal", plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default"
    ) -> List[str]:
        """Validate a proposal before committing."""
        violations = []
        if not plot_id or not str(plot_id).strip():
            violations.append("plot_id is required")
        if not tenant_id or not str(tenant_id).strip():
            violations.append("tenant_id is required")
        if not namespace or not str(namespace).strip():
            violations.append("namespace is required")
        if not proposal.event_type:
            violations.append("event_type is required")
        if not proposal.geometry_version:
            violations.append("geometry_version is required")
        if not proposal.model_version:
            violations.append("model_version is required")
        if not proposal.evidence_set_hash:
            violations.append("evidence_set_hash is required")
        if not proposal.authority_contract_version:
            violations.append("authority_contract_version is required")
        if not proposal.authority_ref or not str(proposal.authority_ref).strip():
            violations.append("authority_ref is required")
        if not proposal.observation_or_valid_time or not str(proposal.observation_or_valid_time).strip():
            violations.append("observation_or_valid_time is required")

        # External lineage must be a typed, evidence-bearing ExternalParentRef.
        for parent in proposal.parent_event_ids:
            try:
                parent_id, external = _canonical_parent(parent)
            except (ValueError, TypeError) as exc:
                violations.append(f"invalid_parent_ref:{exc}")
                continue
            if external is not None:
                continue
            event_path = self._event_path(plot_id, str(parent_id), tenant_id, namespace)
            if not event_path.exists():
                violations.append(f"parent_event_not_found:{parent_id}")

        return violations

    def commit_proposal(
        self,
        *,
        plot_id: str,
        proposal: "WorldlineEventProposal",
        namespace: str = "default",
        tenant_id: str = "default_tenant",
        effective_at: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Validate and commit a worldline event proposal.

        ASMAE proposes. This service validates, assigns canonical identity,
        and commits. ASMAE never assigns its own event ID.
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must not be blank")

        effective_time = (
            effective_at.isoformat()
            if hasattr(effective_at, "isoformat")
            else str(effective_at or "")
        )
        if not effective_time.strip():
            raise ValueError("effective_at is required")

        violations = self.validate_proposal(proposal, plot_id, tenant_id, namespace)
        if violations:
            raise ValueError(
                f"Event proposal validation failed: {'; '.join(violations)}"
            )

        scientific_payload = _public(dict(proposal.payload or {}))
        payload_hash = compute_payload_hash(scientific_payload)

        normalized_parents = [
            _canonical_parent(parent) for parent in (proposal.parent_event_ids or [])
        ]
        parent_ids = [parent_id for parent_id, _ in normalized_parents]
        external_parent_refs = [
            external for _, external in normalized_parents if external is not None
        ]

        # Canonicalize parent ordering
        sorted_parents = tuple(sorted(set(parent_ids)))

        # Build v2 identity input
        identity_input = EventIdentityInput(
            tenant_id=tenant_id,
            namespace=namespace,
            plot_id=plot_id,
            geometry_version=proposal.geometry_version,
            event_type=proposal.event_type,
            effective_time=effective_time,
            observation_or_valid_time=str(proposal.observation_or_valid_time or ""),
            sorted_parent_ids=sorted_parents,
            evidence_set_hash=proposal.evidence_set_hash,
            payload_hash=payload_hash,
            model_version=proposal.model_version,
            calibration_version=proposal.calibration_version,
            authority_contract_version=proposal.authority_contract_version,
            authority_ref=proposal.authority_ref,
            state_schema_version=proposal.state_schema_version,
            worldline_contract_version=WORLDLINE_CONTRACT_VERSION,
        )

        event_id = compute_v2_identity(identity_input)
        authority_ref = proposal.authority_ref

        event_record = {
            "event_id": event_id,
            "identity_version": WORLDLINE_IDENTITY_V2,
            "contract_version": WORLDLINE_CONTRACT_VERSION,
            "tenant_id": tenant_id,
            "namespace": namespace,
            "plot_id": plot_id,
            "event_type": proposal.event_type,
            "geometry_version": proposal.geometry_version,
            "effective_at": effective_time,
            "observation_or_valid_time": str(
                proposal.observation_or_valid_time or ""
            ),
            "parent_event_ids": list(sorted_parents),
            "external_parent_refs": external_parent_refs,
            "evidence_set_hash": proposal.evidence_set_hash,
            "payload_hash": payload_hash,
            "model_version": proposal.model_version,
            "calibration_version": proposal.calibration_version,
            "authority_contract_version": proposal.authority_contract_version,
            "state_schema_version": proposal.state_schema_version,
            "authority": authority_ref,
            "authority_ref": authority_ref,
            "payload": scientific_payload,
            "committed_at": _now(),
        }

        event_path = self._event_path(plot_id, event_id, tenant_id, namespace)
        with self._head_lock(plot_id, tenant_id, namespace):
            if event_path.exists():
                # Idempotent — same proposal produces same ID
                existing = self._read(event_path)
                head = self.load_head(plot_id, tenant_id, namespace)
                existing_seq = int(existing.get("sequence") or 1)
                head_seq = int(head.get("sequence") or 0)
                # ONLY update head if recommitted event is >= current head sequence (prevent rollback)
                if not head or existing_seq >= head_seq:
                    latest_by_type = dict(head.get("latest_by_type") or {})
                    latest_by_type[proposal.event_type] = event_id
                    sequence = max(existing_seq, head_seq)
                    self._atomic(self._head_path(plot_id, tenant_id, namespace), {
                        "contract_version": WORLDLINE_CONTRACT_VERSION,
                        "tenant_id": tenant_id,
                        "namespace": namespace,
                        "plot_id": plot_id,
                        "sequence": sequence,
                        "latest_event_id": event_id,
                        "latest_event_type": proposal.event_type,
                        "latest_by_type": latest_by_type,
                        "updated_at": _now(),
                    })
                logger.info(
                    "Idempotent event commit: %s already exists (seq %d vs head seq %d)",
                    event_id[:16], existing_seq, head_seq
                )
                return existing

            # Assign sequence
            head = self.load_head(plot_id, tenant_id, namespace)
            sequence = int(head.get("sequence", 0) or 0) + 1
            event_record["sequence"] = sequence

            # Persist event
            self._atomic(event_path, event_record)

            # Update head
            latest_by_type = dict(head.get("latest_by_type") or {})
            latest_by_type[proposal.event_type] = event_id
            self._atomic(self._head_path(plot_id, tenant_id, namespace), {
                "contract_version": WORLDLINE_CONTRACT_VERSION,
                "tenant_id": tenant_id,
                "namespace": namespace,
                "plot_id": plot_id,
                "sequence": sequence,
                "latest_event_id": event_id,
                "latest_event_type": proposal.event_type,
                "latest_by_type": latest_by_type,
                "updated_at": _now(),
            })

        logger.info(
            "Committed worldline event %s (type=%s, seq=%d)",
            event_id[:16], proposal.event_type, sequence,
        )
        return event_record


# ── WorldlineEventProposal ───────────────────────────────────────────────────

from dataclasses import dataclass, field as dc_field
from services.agribrain.scientific_contracts.state_schema_ref import STATE_SCHEMA_VERSION


@dataclass(frozen=True)
class WorldlineEventProposal:
    """Immutable proposal for a worldline event.

    ASMAE (or any layer) submits this. The canonical service validates,
    assigns identity, performs idempotency checking, and commits.

    The proposer NEVER assigns an event ID.
    """
    event_type: str
    payload: Mapping[str, Any]
    parent_event_ids: tuple = ()
    geometry_version: str = ""
    evidence_set_hash: str = ""
    model_version: str = ""
    calibration_version: str = ""
    authority_contract_version: str = "authority_v1"
    authority_ref: str = ""
    state_schema_version: str = STATE_SCHEMA_VERSION
    observation_or_valid_time: Optional[str] = None
