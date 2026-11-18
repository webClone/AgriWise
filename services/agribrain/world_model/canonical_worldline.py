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


class ConcurrencyConflictError(ContractViolation):
    """Raised when a compare-and-swap on predecessor head detects concurrent update."""
    pass


CAS_UNSET = object()


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
    "evidence_hash",
    "interval_hash",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc_iso(val: Any) -> datetime:
    """Parse timestamp into UTC timezone-aware datetime."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if hasattr(val, "isoformat") and not isinstance(val, str):
        val = val.isoformat()
    s = str(val or "").strip()
    if not s:
        raise ValueError("Timestamp cannot be blank")
    s = s.replace("Z", "+00:00")
    if len(s) == 10 and s.count("-") == 2:
        dt = datetime.fromisoformat(s).replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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

    def __init__(
        self,
        root: Optional[Union[Path, str]] = None,
        durable_anchor_root: Optional[Union[Path, str]] = None,
    ) -> None:
        if root is not None:
            clean_str = str(root).strip()
            if not clean_str:
                raise ValueError("worldline root cannot be empty string")
            if ".." in clean_str.split("/") or ".." in clean_str.split("\\"):
                raise SecurityViolation(f"Path traversal in worldline root: {clean_str}")
            self.root = Path(clean_str).resolve()
        else:
            self.root = Path(CANONICAL_WORLDLINE_ROOT).resolve()

        anchor_env = durable_anchor_root or os.environ.get("CANONICAL_DURABLE_CHECKPOINT_ROOT")
        if anchor_env:
            clean_anchor = str(anchor_env).strip()
            if ".." in clean_anchor.split("/") or ".." in clean_anchor.split("\\"):
                raise SecurityViolation(f"Path traversal in durable checkpoint root: {clean_anchor}")
            self.durable_anchor_root: Optional[Path] = Path(clean_anchor).resolve()
        else:
            self.durable_anchor_root = None

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
        clean_eid = str(event_id).strip()
        if not clean_eid or ".." in clean_eid or "/" in clean_eid or "\\" in clean_eid:
            raise SecurityViolation(f"Invalid event_id {event_id}: path traversal characters not permitted")
        plot_events = (self._plot_dir(plot_id, tenant_id, namespace) / "events").resolve()
        target = (plot_events / f"{clean_eid}.json").resolve()
        if not target.is_relative_to(plot_events):
            raise SecurityViolation(f"Event ID {event_id} escapes plot events directory")
        return target

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

    def _hydraulic_head_path(self, plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default") -> Path:
        return self._plot_dir(plot_id, tenant_id, namespace) / "hydraulic_head.json"

    def _hydraulic_checkpoint_path(self, plot_id: str, checkpoint_id: str, tenant_id: str = "default_tenant", namespace: str = "default") -> Path:
        clean_id = str(checkpoint_id).strip()
        if not clean_id or ".." in clean_id or "/" in clean_id or "\\" in clean_id:
            raise ValueError(f"Invalid checkpoint_id {checkpoint_id}: path traversal characters not permitted")
        checkpoints_dir = (self._plot_dir(plot_id, tenant_id, namespace) / "checkpoints").resolve()
        target_path = (checkpoints_dir / f"{clean_id}.json").resolve()
        try:
            target_path.relative_to(checkpoints_dir)
        except ValueError:
            raise ValueError(f"Checkpoint ID {checkpoint_id} escapes checkpoints directory")
        return target_path

    def load_latest_hydraulic_checkpoint(
        self,
        plot_id: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        cycle_id: Optional[str] = None,
        geometry_version: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load latest committed hydraulic checkpoint for a tenant plot, optionally scoped by cycle/geometry."""
        head_data = self._read(self._hydraulic_head_path(plot_id, tenant_id, namespace))
        if not head_data or not head_data.get("latest_checkpoint_id"):
            return None

        # Check if caller requested specific cycle/geometry scope
        if cycle_id is not None or geometry_version is not None:
            c_target = cycle_id or "default_cycle"
            g_target = geometry_version or "default_geom"
            scope_key = f"{c_target}::{g_target}"
            scoped_heads = head_data.get("scoped_heads", {}) or {}
            if scope_key in scoped_heads:
                cp_id = scoped_heads[scope_key]
                cp_path = self._hydraulic_checkpoint_path(plot_id, cp_id, tenant_id, namespace)
                res = self._read(cp_path)
                if res:
                    res_out = dict(res)
                    cp_seqs = head_data.get("checkpoint_sequences", {}) or {}
                    pub_seq = cp_seqs.get(cp_id)
                    if pub_seq is not None:
                        res_out["sequence"] = pub_seq
                        res_out["publication_generation"] = pub_seq
                    elif head_data.get("scoped_sequences", {}).get(scope_key) is not None:
                        pub_seq = head_data["scoped_sequences"][scope_key]
                        res_out["sequence"] = pub_seq
                        res_out["publication_generation"] = pub_seq
                    elif head_data.get("latest_checkpoint_id") == cp_id and head_data.get("sequence"):
                        pub_seq = int(head_data["sequence"])
                        res_out["sequence"] = pub_seq
                        res_out["publication_generation"] = pub_seq
                    return res_out

            # Fallback: traverse predecessor chain starting from latest_checkpoint_id
            curr_id = head_data.get("latest_checkpoint_id")
            visited = set()
            while curr_id and curr_id not in visited:
                visited.add(curr_id)
                cp_path = self._hydraulic_checkpoint_path(plot_id, curr_id, tenant_id, namespace)
                cp_data = self._read(cp_path)
                if not cp_data:
                    break
                cp_cycle = cp_data.get("cycle_id", "default_cycle")
                cp_geom = cp_data.get("geometry_version", "default_geom")
                if cp_cycle == c_target and cp_geom == g_target:
                    res_out = dict(cp_data)
                    cp_seqs = head_data.get("checkpoint_sequences", {}) or {}
                    pub_seq = cp_seqs.get(curr_id)
                    if pub_seq is not None:
                        res_out["sequence"] = pub_seq
                        res_out["publication_generation"] = pub_seq
                    elif head_data.get("latest_checkpoint_id") == curr_id and head_data.get("sequence"):
                        pub_seq = int(head_data["sequence"])
                        res_out["sequence"] = pub_seq
                        res_out["publication_generation"] = pub_seq
                    return res_out
                curr_id = cp_data.get("predecessor_head")

            return None

        cp_id = head_data.get("latest_checkpoint_id")
        cp_path = self._hydraulic_checkpoint_path(plot_id, cp_id, tenant_id, namespace)
        res = self._read(cp_path)
        if res:
            res_out = dict(res)
            cp_seqs = head_data.get("checkpoint_sequences", {}) or {}
            pub_seq = cp_seqs.get(cp_id)
            if pub_seq is not None:
                res_out["sequence"] = pub_seq
                res_out["publication_generation"] = pub_seq
            elif head_data.get("sequence"):
                res_out["sequence"] = int(head_data["sequence"])
                res_out["publication_generation"] = int(head_data["sequence"])
            return res_out
        return None

    def save_hydraulic_checkpoint(
        self,
        *,
        plot_id: str,
        checkpoint_id: str,
        checkpoint_payload: Dict[str, Any],
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        cycle_id: str = "default_cycle",
        geometry_version: str = "default_geom",
        expected_predecessor_head: Any = CAS_UNSET,
    ) -> Dict[str, Any]:
        """Commit a scoped hydraulic checkpoint with compare-and-swap on predecessor head."""
        # R08 + R17: Checkpoint path containment validation
        cp_path = self._hydraulic_checkpoint_path(plot_id, checkpoint_id, tenant_id, namespace)

        with self._head_lock(plot_id, tenant_id, namespace):
            head_path = self._hydraulic_head_path(plot_id, tenant_id, namespace)
            current_head = self._read(head_path)
            current_head_id = current_head.get("head_hash") or current_head.get("latest_checkpoint_id")

            scope_key = f"{cycle_id}::{geometry_version}"
            scoped_heads = dict(current_head.get("scoped_heads", {}) or {})
            if not scoped_heads and current_head_id:
                # Migrate legacy un-scoped head: traverse chain and seed latest head for each scope
                curr_mig = current_head_id
                visited_mig = set()
                while curr_mig and curr_mig not in visited_mig:
                    visited_mig.add(curr_mig)
                    c_path = self._hydraulic_checkpoint_path(plot_id, curr_mig, tenant_id, namespace)
                    c_data = self._read(c_path)
                    if not c_data:
                        break
                    c_cyc = c_data.get("cycle_id", "default_cycle")
                    c_geom = c_data.get("geometry_version", "default_geom")
                    c_key = f"{c_cyc}::{c_geom}"
                    if c_key not in scoped_heads:
                        scoped_heads[c_key] = curr_mig
                    curr_mig = c_data.get("predecessor_head")

            scoped_head = scoped_heads.get(scope_key)
            if scoped_head is None and not scoped_heads:
                if (current_head.get("cycle_id", "default_cycle") == cycle_id and
                    current_head.get("geometry_version", "default_geom") == geometry_version):
                    scoped_head = current_head_id
            target_predecessor = scoped_head

            # R08 + V11: Immutability, full record identity, and interrupted publication recovery
            if cp_path.exists():
                existing = self._read(cp_path)
                existing_payload = _public(existing.get("payload")) if existing else None
                new_payload = _public(checkpoint_payload)
                matches_payload = (existing_payload is not None) and (existing_payload == new_payload)
                matches_cycle = existing and (existing.get("cycle_id", "default_cycle") == cycle_id)
                matches_geom = existing and (existing.get("geometry_version", "default_geom") == geometry_version)
                if matches_payload and matches_cycle and matches_geom:
                    # Check if head publication is committed
                    if current_head_id == checkpoint_id or scoped_heads.get(scope_key) == checkpoint_id:
                        # Already published head: return existing record idempotently
                        rec_out = dict(existing)
                        cp_seqs = current_head.get("checkpoint_sequences", {}) or {}
                        pub_seq = cp_seqs.get(checkpoint_id)
                        if pub_seq is not None:
                            rec_out["sequence"] = pub_seq
                            rec_out["publication_generation"] = pub_seq
                        elif current_head.get("scoped_sequences", {}).get(scope_key) is not None:
                            pub_seq = current_head["scoped_sequences"][scope_key]
                            rec_out["sequence"] = pub_seq
                            rec_out["publication_generation"] = pub_seq
                        elif current_head_id == checkpoint_id and current_head.get("sequence"):
                            pub_seq = int(current_head["sequence"])
                            rec_out["sequence"] = pub_seq
                            rec_out["publication_generation"] = pub_seq
                        return rec_out

                    # V11: Interrupted publication recovery: checkpoint exists, head was not updated
                    # Recover head ONLY if predecessor_head matches the expected predecessor head!
                    if existing.get("predecessor_head") in (target_predecessor, current_head_id):
                        head_seq = int(current_head.get("sequence", 0) or 0)
                        orphan_seq = int(existing.get("sequence", 0) or 0)
                        seq = max(head_seq + 1, orphan_seq)
                        scoped_heads[scope_key] = checkpoint_id
                        scoped_seqs = dict(current_head.get("scoped_sequences", {}) or {})
                        cp_seqs = dict(current_head.get("checkpoint_sequences", {}) or {})
                        latest_cp = current_head.get("latest_checkpoint_id") or current_head_id
                        if (latest_cp or current_head_id) and current_head.get("sequence"):
                            prev_seq = int(current_head["sequence"])
                            if latest_cp and latest_cp not in cp_seqs:
                                cp_seqs[latest_cp] = prev_seq
                            if current_head_id and current_head_id not in cp_seqs:
                                cp_seqs[current_head_id] = prev_seq
                            for s_key, s_head in scoped_heads.items():
                                if s_head in (latest_cp, current_head_id) and s_key not in scoped_seqs:
                                    scoped_seqs[s_key] = prev_seq
                            cur_sc = f"{current_head.get('cycle_id', 'default_cycle')}::{current_head.get('geometry_version', 'default_geom')}"
                            if cur_sc not in scoped_seqs and (not scoped_heads or scoped_heads.get(cur_sc) in (latest_cp, current_head_id)):
                                scoped_seqs[cur_sc] = prev_seq
                        scoped_seqs[scope_key] = seq
                        cp_seqs[checkpoint_id] = seq
                        new_head = {
                            "tenant_id": tenant_id,
                            "namespace": namespace,
                            "plot_id": plot_id,
                            "sequence": seq,
                            "latest_checkpoint_id": checkpoint_id,
                            "head_hash": checkpoint_id,
                            "cycle_id": cycle_id,
                            "geometry_version": geometry_version,
                            "scoped_heads": scoped_heads,
                            "scoped_sequences": scoped_seqs,
                            "checkpoint_sequences": cp_seqs,
                            "updated_at": _now(),
                        }
                        self._atomic(head_path, new_head)
                        rec_out = dict(existing)
                        rec_out["sequence"] = seq
                        rec_out["publication_generation"] = seq
                        return rec_out
                    else:
                        raise ConcurrencyConflictError(
                            f"Checkpoint {checkpoint_id} exists but is an uncommitted orphan whose predecessor does not match current head {current_head_id}"
                        )
                raise ConcurrencyConflictError(
                    f"Checkpoint {checkpoint_id} already exists with differing payload/metadata; checkpoints are immutable"
                )

            # R08: Self-parent loop prevention
            if checkpoint_id == target_predecessor or checkpoint_id == current_head_id:
                raise ValueError(f"Self-parent loop rejected: checkpoint {checkpoint_id} cannot have itself as predecessor head")
            if expected_predecessor_head is not CAS_UNSET and checkpoint_id == expected_predecessor_head:
                raise ValueError(f"Self-parent loop rejected: checkpoint {checkpoint_id} cannot have itself as predecessor head")

            if expected_predecessor_head is not CAS_UNSET and target_predecessor != expected_predecessor_head:
                raise ConcurrencyConflictError(
                    f"Predecessor head conflict for plot {plot_id}: expected {expected_predecessor_head}, found {target_predecessor}"
                )

            seq = int(current_head.get("sequence", 0) or 0) + 1
            record = {
                "checkpoint_id": checkpoint_id,
                "tenant_id": tenant_id,
                "namespace": namespace,
                "plot_id": plot_id,
                "cycle_id": cycle_id,
                "geometry_version": geometry_version,
                "sequence": seq,
                "predecessor_head": target_predecessor,
                "committed_at": _now(),
                "payload": _public(checkpoint_payload),
            }

            self._atomic(cp_path, record)

            if self.durable_anchor_root:
                anchor_cp_dir = self.durable_anchor_root / str(tenant_id).strip() / str(namespace).strip() / self._plot_key(plot_id) / "checkpoints"
                anchor_cp_dir.mkdir(parents=True, exist_ok=True)
                self._atomic(anchor_cp_dir / f"{clean_id}.json", record)

            scoped_heads[f"{cycle_id}::{geometry_version}"] = checkpoint_id
            scoped_seqs = dict(current_head.get("scoped_sequences", {}) or {})
            cp_seqs = dict(current_head.get("checkpoint_sequences", {}) or {})
            latest_cp = current_head.get("latest_checkpoint_id") or current_head_id
            if (latest_cp or current_head_id) and current_head.get("sequence"):
                prev_seq = int(current_head["sequence"])
                if latest_cp and latest_cp not in cp_seqs:
                    cp_seqs[latest_cp] = prev_seq
                if current_head_id and current_head_id not in cp_seqs:
                    cp_seqs[current_head_id] = prev_seq
                for s_key, s_head in scoped_heads.items():
                    if s_head in (latest_cp, current_head_id) and s_key not in scoped_seqs:
                        scoped_seqs[s_key] = prev_seq
                cur_sc = f"{current_head.get('cycle_id', 'default_cycle')}::{current_head.get('geometry_version', 'default_geom')}"
                if cur_sc not in scoped_seqs and (not scoped_heads or scoped_heads.get(cur_sc) in (latest_cp, current_head_id)):
                    scoped_seqs[cur_sc] = prev_seq
            scoped_seqs[f"{cycle_id}::{geometry_version}"] = seq
            cp_seqs[checkpoint_id] = seq
            new_head = {
                "tenant_id": tenant_id,
                "namespace": namespace,
                "plot_id": plot_id,
                "sequence": seq,
                "latest_checkpoint_id": checkpoint_id,
                "head_hash": checkpoint_id,
                "cycle_id": cycle_id,
                "geometry_version": geometry_version,
                "scoped_heads": scoped_heads,
                "scoped_sequences": scoped_seqs,
                "checkpoint_sequences": cp_seqs,
                "updated_at": _now(),
            }
            self._atomic(head_path, new_head)
            record["publication_generation"] = seq
            return record

    def load_event(self, plot_id: str, event_id: str, tenant_id: str = "default_tenant", namespace: str = "default") -> Dict[str, Any]:
        """Load specific event by ID for a tenant plot."""
        return self._read(self._event_path(plot_id, event_id, tenant_id, namespace))

    def load_all_events(
        self,
        plot_id: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        fail_on_corrupt: bool = False,
    ) -> List[Dict[str, Any]]:
        """Load all persisted events for a tenant plot, ordered by sequence."""
        events_dir = self._plot_dir(plot_id, tenant_id, namespace) / "events"
        if not events_dir.exists() or not events_dir.is_dir():
            if fail_on_corrupt:
                head = self.load_head(plot_id, tenant_id, namespace)
                head_seq = int(head.get("sequence") or 0) if head else 0
                if head_seq > 0:
                    raise CorruptedWorldlineError(
                        f"Worldline journal tail truncation detected for plot {plot_id}: head watermark sequence {head_seq} but events directory missing or empty"
                    )
            return []
        events = []
        for file in events_dir.glob("*.json"):
            try:
                rec = self._read(file)
                if not rec or not isinstance(rec, dict) or "event_id" not in rec:
                    if fail_on_corrupt:
                        raise CorruptedWorldlineError(f"Worldline file {file} is not a valid event record")
                    continue
                events.append(rec)
            except Exception as exc:
                if fail_on_corrupt:
                    if isinstance(exc, CorruptedWorldlineError):
                        raise
                    raise CorruptedWorldlineError(f"Worldline event file corruption at {file}: {exc}") from exc
                logger.warning("Could not read worldline event file %s: %s", file, exc)
        events.sort(
            key=lambda e: (
                int(e.get("sequence") or 0),
                str(e.get("committed_at") or ""),
                str(e.get("effective_at") or ""),
            )
        )
        if fail_on_corrupt:
            if events:
                # 1. Check for sequence continuity and valid committed_at timestamps (IR03-V02, IR03-V03)
                for idx, event in enumerate(events):
                    seq = event.get("sequence")
                    if seq is None:
                        raise CorruptedWorldlineError(f"Event {event.get('event_id')} missing sequence number")
                    expected_seq = idx + 1
                    if int(seq) != expected_seq:
                        raise CorruptedWorldlineError(
                            f"Worldline sequence gap detected for plot {plot_id}: expected sequence {expected_seq}, found {seq}"
                        )
                    comm_str = event.get("committed_at")
                    if not comm_str:
                        raise CorruptedWorldlineError(f"Event {event.get('event_id')} missing committed_at timestamp")
                    try:
                        _parse_utc_iso(comm_str)
                    except Exception as exc:
                        raise CorruptedWorldlineError(
                            f"Event {event.get('event_id')} has invalid committed_at timestamp '{comm_str}': {exc}"
                        ) from exc

            # 2. Check head watermark against event count (detects tail truncation)
            head = self.load_head(plot_id, tenant_id, namespace)
            head_seq = int(head.get("sequence") or 0) if head else 0
            if head_seq > 0:
                if len(events) != head_seq:
                    raise CorruptedWorldlineError(
                        f"Worldline journal tail truncation detected for plot {plot_id}: head watermark sequence {head_seq} but found {len(events)} events"
                    )
                if events and int(events[-1].get("sequence") or 0) != head_seq:
                    raise CorruptedWorldlineError(
                        f"Worldline journal sequence mismatch for plot {plot_id}: head watermark sequence {head_seq} but last event sequence is {events[-1].get('sequence')}"
                    )
            elif events:
                raise CorruptedWorldlineError(
                    f"Worldline journal missing head watermark for plot {plot_id} while {len(events)} events exist"
                )

            # 3. Check against durable checkpoints to detect joint head+journal rollback
            candidate_checkpoint_dirs = [self._plot_dir(plot_id, tenant_id, namespace) / "checkpoints"]
            if self.durable_anchor_root:
                anchor_cp_dir = self.durable_anchor_root / str(tenant_id).strip() / str(namespace).strip() / self._plot_key(plot_id) / "checkpoints"
                candidate_checkpoint_dirs.append(anchor_cp_dir)

            for checkpoints_dir in candidate_checkpoint_dirs:
                if checkpoints_dir.exists() and checkpoints_dir.is_dir():
                    for cp_file in checkpoints_dir.glob("*.json"):
                        try:
                            cp_data = self._read(cp_file)
                            cp_seq = int(cp_data.get("sequence") or cp_data.get("head_sequence") or 0)
                            if cp_seq > head_seq:
                                raise CorruptedWorldlineError(
                                    f"Worldline journal rollback detected for plot {plot_id}: checkpoint watermark sequence {cp_seq} exceeds current head sequence {head_seq}"
                                )
                        except Exception as exc:
                            if isinstance(exc, CorruptedWorldlineError):
                                raise
                            logger.warning("Could not read checkpoint %s: %s", cp_file, exc)
        return events

    def select_eligible_events(
        self,
        plot_id: str,
        event_type: str,
        valid_time_T: Any,
        knowledge_cutoff_K: Any,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        fail_on_corrupt: bool = True,
    ) -> List[Dict[str, Any]]:
        """Walk immutable event journal and select events strictly satisfying:
          1. event.tenant_id == tenant_id
          2. event.plot_id == plot_id
          3. event.event_type == event_type
          4. event.committed_at <= knowledge_cutoff_K
          5. (event.observation_or_valid_time or event.effective_at) <= valid_time_T
          6. All ancestor parent events committed_at <= knowledge_cutoff_K (provenance integrity)
        Ordered deterministically by (valid_time ASC, sequence ASC, committed_at ASC).
        """
        all_events = self.load_all_events(
            plot_id=plot_id,
            tenant_id=tenant_id,
            namespace=namespace,
            fail_on_corrupt=fail_on_corrupt,
        )

        t_dt = _parse_utc_iso(valid_time_T)
        k_dt = _parse_utc_iso(knowledge_cutoff_K)

        eligible: List[tuple[datetime, int, datetime, Dict[str, Any]]] = []
        for rec in all_events:
            if rec.get("event_type") != event_type:
                continue
            if rec.get("plot_id") != plot_id or rec.get("tenant_id") != tenant_id:
                continue

            committed_str = rec.get("committed_at")
            valid_str = rec.get("observation_or_valid_time") or rec.get("effective_at")
            if not committed_str or not valid_str:
                if fail_on_corrupt:
                    raise CorruptedWorldlineError(
                        f"Event {rec.get('event_id')} missing committed_at or valid_time"
                    )
                continue

            try:
                committed_dt = _parse_utc_iso(committed_str)
                valid_dt = _parse_utc_iso(valid_str)
            except Exception as exc:
                if fail_on_corrupt:
                    raise CorruptedWorldlineError(
                        f"Event {rec.get('event_id')} has unparseable timestamp: {exc}"
                    ) from exc
                continue

            # Dual-clock filter: committed_at <= K and valid_time <= T
            if committed_dt > k_dt or valid_dt > t_dt:
                continue

            # Evidence Classification Guard (IR03-V08):
            # Forecasts, scenario projections, and synthetic data must never masquerade as historical observations
            payload = rec.get("payload") or {}
            if isinstance(payload, dict):
                if payload.get("is_forecast") or payload.get("scenario") or payload.get("synthetic"):
                    logger.warning("Event %s contains forecast/scenario/synthetic data; rejected from historical observation set", rec.get("event_id"))
                    continue
            if rec.get("event_kind") in {"forecast", "scenario", "synthetic"}:
                logger.warning("Event %s is classified as %s; rejected from historical observation set", rec.get("event_id"), rec.get("event_kind"))
                continue

            # Recursive Dependency Provenance Check (IR03-V04):
            # Traverse complete DAG of parent/ancestor references; ensure NO ancestor committed at t > K
            dependency_violation = False
            visited_ancestors: set[str] = set()
            ancestor_queue: list[str] = [str(pid).strip() for pid in (rec.get("parent_event_ids") or []) if str(pid).strip()]
            while ancestor_queue:
                ancestor_id = ancestor_queue.pop(0)
                if ancestor_id in visited_ancestors:
                    continue
                visited_ancestors.add(ancestor_id)

                if ancestor_id == rec.get("event_id"):
                    if fail_on_corrupt:
                        raise CorruptedWorldlineError(f"Causal cycle detected: event {rec.get('event_id')} references itself as parent")
                    dependency_violation = True
                    break

                p_path = self._event_path(plot_id, ancestor_id, tenant_id, namespace)
                if not p_path.exists():
                    logger.warning(
                        "Derived event %s references missing ancestor %s; fail closed",
                        rec.get("event_id"), ancestor_id
                    )
                    if fail_on_corrupt:
                        raise CorruptedWorldlineError(
                            f"Derived event {rec.get('event_id')} references missing ancestor event {ancestor_id}"
                        )
                    dependency_violation = True
                    break

                try:
                    p_rec = self._read(p_path)
                    if not p_rec:
                        if fail_on_corrupt:
                            raise CorruptedWorldlineError(
                                f"Derived event {rec.get('event_id')} references empty/unreadable ancestor {ancestor_id}"
                            )
                        dependency_violation = True
                        break

                    p_comm_str = p_rec.get("committed_at")
                    p_val_str = p_rec.get("observation_or_valid_time") or p_rec.get("effective_at")
                    if p_comm_str:
                        p_comm_dt = _parse_utc_iso(p_comm_str)
                        if p_comm_dt > k_dt:
                            logger.warning(
                                "Derived event %s references ancestor %s committed after cutoff (%s > %s)",
                                rec.get("event_id"), ancestor_id, p_comm_str, k_dt.isoformat()
                            )
                            dependency_violation = True
                            break

                    if p_val_str:
                        p_val_dt = _parse_utc_iso(p_val_str)
                        if p_val_dt > t_dt:
                            logger.warning(
                                "Derived event %s references ancestor %s observed after valid time T (%s > %s)",
                                rec.get("event_id"), ancestor_id, p_val_str, t_dt.isoformat()
                            )
                            dependency_violation = True
                            break

                    # Check nested provider/BMA calibration/cutoff inside ancestor payload
                    anc_payload = p_rec.get("payload") or {}
                    if isinstance(anc_payload, dict):
                        bma_meta = anc_payload.get("bma_weights") or anc_payload.get("calibration") or {}
                        if isinstance(bma_meta, dict):
                            cal_at = bma_meta.get("calibrated_at") or bma_meta.get("derived_at") or bma_meta.get("cutoff_at")
                            if cal_at:
                                cal_dt = _parse_utc_iso(cal_at)
                                if cal_dt > k_dt:
                                    logger.warning(
                                        "Derived event %s ancestor %s has nested BMA/calibration derived after cutoff (%s > %s)",
                                        rec.get("event_id"), ancestor_id, cal_at, k_dt.isoformat()
                                    )
                                    dependency_violation = True
                                    break

                    # Queue transitive ancestors
                    for gp_id in p_rec.get("parent_event_ids") or []:
                        clean_gpid = str(gp_id).strip()
                        if clean_gpid and clean_gpid not in visited_ancestors:
                            ancestor_queue.append(clean_gpid)
                except Exception as p_exc:
                    if fail_on_corrupt:
                        if isinstance(p_exc, CorruptedWorldlineError):
                            raise
                        raise CorruptedWorldlineError(
                            f"Failed to verify ancestor {ancestor_id} for event {rec.get('event_id')}: {p_exc}"
                        ) from p_exc
                    dependency_violation = True
                    break
            if dependency_violation:
                continue

            seq = int(rec.get("sequence") or 0)
            eligible.append((valid_dt, seq, committed_dt, rec))

        # Deterministic sort: valid_time ASC, sequence ASC, committed_at ASC
        eligible.sort(key=lambda item: (item[0], item[1], item[2]))
        return [item[3] for item in eligible]

    def latest_eligible_payload(
        self,
        plot_id: str,
        event_type: str,
        valid_time_T: Any,
        knowledge_cutoff_K: Any,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        fail_on_corrupt: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Select latest payload satisfying (T, K) without inspecting mutable head."""
        events = self.select_eligible_events(
            plot_id=plot_id,
            event_type=event_type,
            valid_time_T=valid_time_T,
            knowledge_cutoff_K=knowledge_cutoff_K,
            tenant_id=tenant_id,
            namespace=namespace,
            fail_on_corrupt=fail_on_corrupt,
        )
        if not events:
            return None
        latest_event = events[-1]
        payload = dict(latest_event.get("payload") or {})
        payload["_worldline_event_id"] = latest_event.get("event_id")
        payload["_worldline_committed_at"] = latest_event.get("committed_at")
        payload["_worldline_valid_time"] = (
            latest_event.get("observation_or_valid_time")
            or latest_event.get("effective_at")
        )
        payload["_worldline_sequence"] = latest_event.get("sequence")
        payload["_worldline_payload_hash"] = latest_event.get("payload_hash")
        return payload

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

    def latest_payload(
        self,
        plot_id: str,
        event_type: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Retrieve latest payload for a specific event_type."""
        head = self.load_head(plot_id, tenant_id, namespace)
        event_id = (head.get("latest_by_type") or {}).get(event_type)
        event = (
            self.load_event(plot_id, str(event_id), tenant_id, namespace)
            if event_id else {}
        )
        payload = event.get("payload")
        if not isinstance(payload, dict):
            return {}
        result = dict(payload)
        result["_worldline_event_id"] = event.get("event_id")
        return result

    def commit_event(
        self,
        *,
        plot_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        geometry_hash: str = "",
        effective_at: Optional[Any] = None,
        observation_or_valid_time: Optional[Any] = None,
        parent_event_ids: Optional[Iterable[Any]] = None,
        authority: str = "",
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Convenience method to propose and commit an event in one canonical step."""
        if not str(authority or "").strip():
            raise ValueError("authority is required for worldline writes")
        if not str(geometry_hash or "").strip():
            raise ValueError("geometry_hash is required for worldline writes")

        payload_dict = dict(payload or {})
        if effective_at is None or not str(effective_at).strip():
            raise ValueError("effective_at is required for worldline writes")
        if observation_or_valid_time is None or not str(observation_or_valid_time).strip():
            raise ValueError("observation_or_valid_time is required for worldline writes")
        valid_time = observation_or_valid_time
        if hasattr(valid_time, "isoformat"):
            valid_time = valid_time.isoformat()

        parents = tuple(parent_event_ids or ())

        proposal = WorldlineEventProposal(
            event_type=str(event_type),
            payload=payload_dict,
            parent_event_ids=parents,
            geometry_version=str(geometry_hash),
            evidence_set_hash=_stable(payload or {}),
            model_version="asmae_v0.5.0",
            calibration_version="",
            authority_contract_version="authority_v1",
            authority_ref=str(authority),
            state_schema_version=STATE_SCHEMA_VERSION,
            observation_or_valid_time=str(valid_time),
        )

        return self.commit_proposal(
            plot_id=plot_id,
            proposal=proposal,
            effective_at=effective_at,
            tenant_id=tenant_id,
            namespace=namespace,
        )

    def hydrate_context(
        self,
        plot_id: str,
        context: Dict[str, Any],
        valid_time_T: Optional[Any] = None,
        knowledge_cutoff_K: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Hydrate missing live inputs or execute bitemporal historical hydration."""
        geometry_hash = str(context.get("geometry_hash", "") or "")
        tenant_id = str(context.get("tenant_id") or "default_tenant")
        namespace = str(context.get("worldline_namespace") or "default")

        t_param = valid_time_T or context.get("observation_valid_time") or context.get("as_of")
        k_param = (
            knowledge_cutoff_K
            or context.get("knowledge_cutoff_time")
            or context.get("knowledge_cutoff_K")
            or context.get("knowledge_cutoff")
        )

        if t_param is not None and k_param is not None:
            # Dual-clock bitemporal replay mode
            t_dt = _parse_utc_iso(t_param)
            k_dt = _parse_utc_iso(k_param)

            selected_evidence_set: List[Dict[str, Any]] = []

            archive_payload = self.latest_eligible_payload(
                plot_id,
                "ARCHIVE_POSTERIOR_VALIDATED",
                t_dt,
                k_dt,
                tenant_id,
                namespace,
                fail_on_corrupt=True,
            )
            if archive_payload:
                archive = archive_payload.get("archive_posterior")
                if isinstance(archive, dict) and archive.get("geometry_hash") == geometry_hash:
                    context["archive_posterior"] = archive
                    context["archive_metrics"] = archive_payload.get(
                        "historical_metrics", {}
                    )
                    context["archive_baselines"] = archive_payload.get("baseline", {})
                    context["archive_bma"] = archive_payload.get("archive_bma", {})
                    context["retrovalidation_residuals"] = archive_payload.get(
                        "retrovalidation", {}
                    )
                    context["archive_metrics_hash"] = (
                        archive_payload.get("archive_metrics_hash")
                        or _stable(archive_payload)
                    )
                    context["archive_metrics_status"] = "available"
                    context["worldline_archive_event_id"] = archive_payload.get(
                        "_worldline_event_id"
                    )
                    selected_evidence_set.append({
                        "event_id": archive_payload.get("_worldline_event_id"),
                        "event_type": "ARCHIVE_POSTERIOR_VALIDATED",
                        "committed_at": archive_payload.get("_worldline_committed_at"),
                        "observation_or_valid_time": archive_payload.get("_worldline_valid_time"),
                        "payload_hash": archive_payload.get("_worldline_payload_hash") or _stable(archive_payload),
                    })

            crop_payload = self.latest_eligible_payload(
                plot_id,
                "CROP_POSTERIOR",
                t_dt,
                k_dt,
                tenant_id,
                namespace,
                fail_on_corrupt=True,
            )
            if crop_payload:
                crop_posterior = crop_payload.get("crop_posterior", {})
                context["crop_posterior"] = crop_posterior
                context["crop_posterior_lineage"] = (
                    crop_payload.get("content_hash")
                    or crop_posterior.get("content_hash")
                    or _stable(crop_payload)
                )
                context["crop_lineage_id"] = crop_posterior.get("lineage_id")
                context["worldline_crop_event_id"] = crop_payload.get(
                    "_worldline_event_id"
                )
                selected_evidence_set.append({
                    "event_id": crop_payload.get("_worldline_event_id"),
                    "event_type": "CROP_POSTERIOR",
                    "committed_at": crop_payload.get("_worldline_committed_at"),
                    "observation_or_valid_time": crop_payload.get("_worldline_valid_time"),
                    "payload_hash": crop_payload.get("_worldline_payload_hash") or _stable(crop_payload),
                })

            selected_evidence_set.sort(
                key=lambda item: (str(item.get("event_type")), str(item.get("event_id")))
            )
            evidence_digest = hashlib.sha256(
                json.dumps(selected_evidence_set, sort_keys=True).encode("utf-8")
            ).hexdigest()

            replay_receipt = {
                "contract_version": "canonical_bitemporal_replay_receipt_v1",
                "replay_mode": "bitemporal_deterministic_v1",
                "tenant_id": tenant_id,
                "plot_id": plot_id,
                "geometry_hash": geometry_hash,
                "query_parameters": {
                    "observation_valid_time": t_dt.isoformat(),
                    "knowledge_cutoff_time": k_dt.isoformat(),
                },
                "selected_evidence_set": selected_evidence_set,
                "evidence_set_digest": f"sha256:{evidence_digest}",
                "status": "replayed",
            }
            context["bitemporal_replay_receipt"] = replay_receipt
            # Immutable historical replay never binds mutable live head
            context["plot_worldline_head"] = None
            return context

        # Live forward assimilation mode
        geometry_hash = str(context.get("geometry_hash", "") or "")
        tenant_id = str(context.get("tenant_id") or "default_tenant")
        namespace = str(context.get("worldline_namespace") or "default")
        archive_event = self.latest_payload(
            plot_id, "ARCHIVE_POSTERIOR_VALIDATED", tenant_id, namespace
        )
        archive = archive_event.get("archive_posterior")
        if (
            not context.get("archive_posterior")
            and isinstance(archive, dict)
            and archive.get("geometry_hash") == geometry_hash
        ):
            context["archive_posterior"] = archive
            context["archive_metrics"] = archive_event.get(
                "historical_metrics", {}
            )
            context["archive_baselines"] = archive_event.get("baseline", {})
            context["archive_bma"] = archive_event.get("archive_bma", {})
            context["retrovalidation_residuals"] = archive_event.get(
                "retrovalidation", {}
            )
            context["archive_metrics_hash"] = archive_event.get(
                "archive_metrics_hash"
            ) or _stable(archive_event)
            context["archive_metrics_status"] = "available"
            context["worldline_archive_event_id"] = archive_event.get(
                "_worldline_event_id"
            )

        crop_payload = self.latest_payload(
            plot_id, "CROP_POSTERIOR", tenant_id, namespace
        )
        if crop_payload and not context.get("crop_posterior"):
            crop_posterior = crop_payload.get("crop_posterior", {})
            context["crop_posterior"] = crop_posterior
            context["crop_posterior_lineage"] = crop_payload.get(
                "content_hash"
            ) or crop_posterior.get(
                "content_hash"
            ) or _stable(crop_payload)
            context["crop_lineage_id"] = crop_posterior.get(
                "lineage_id"
            )
        context["plot_worldline_head"] = self.load_head(
            plot_id, tenant_id, namespace
        )
        return context

    def commit_asmae_result(
        self,
        result: Mapping[str, Any],
        *,
        geometry_hash: str,
        snapshot_ref: str = "",
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Commit an ASMAE execution result to canonical worldline history."""
        artifact = dict(result.get("plot_state_artifact") or {})
        if not artifact:
            return {}
        event_type = (
            "CURRENT_POSTERIOR_VALIDATED"
            if bool(
                (result.get("diagnostics") or {}).get(
                    "scientific_production_usable", False
                )
            )
            else "CURRENT_POSTERIOR_DIAGNOSTIC"
        )
        artifact_time = str(artifact.get("as_of") or "").strip()
        artifact_authority = str(
            artifact.get("authority_level") or ""
        ).strip()
        if not artifact_time:
            raise ValueError("plot-state artifact as_of is required")
        if not artifact_authority:
            raise ValueError("plot-state artifact authority_level is required")
        event = self.commit_event(
            plot_id=str(result.get("plot_id", "")),
            event_type=event_type,
            geometry_hash=geometry_hash,
            effective_at=artifact_time,
            observation_or_valid_time=artifact_time,
            authority=artifact_authority,
            tenant_id=tenant_id,
            namespace=namespace,
            payload={
                "plot_state_artifact": artifact,
                "output_content_hash": result.get("content_hash"),
                "snapshot_ref": snapshot_ref,
                "archive_update_candidate": event_type
                == "CURRENT_POSTERIOR_VALIDATED",
            },
        )
        return event

    def commit_acquisition_plan(
        self,
        *,
        plot_id: str,
        geometry_hash: str,
        reason: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Commit an archive observation acquisition requirement."""
        event_time = datetime.now(timezone.utc)
        return self.commit_event(
            plot_id=plot_id,
            event_type="ARCHIVE_ACQUISITION_PLAN",
            geometry_hash=geometry_hash,
            authority="DIAGNOSTIC",
            effective_at=event_time,
            observation_or_valid_time=event_time,
            tenant_id=tenant_id,
            namespace=namespace,
            payload={
                "status": "needs_observations",
                "reason": reason,
                "requested_sources": ["sentinel2", "sentinel1", "weather"],
                "synthetic_observations_allowed": False,
            },
        )


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
