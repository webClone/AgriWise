"""Durable external-worker queue for standard ASMAE computations."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Tuple

from .job_manifest import (
    EVIDENCE_CAPABILITY_CONTRACT_VERSION,
    JOB_MANIFEST_CONTRACT_VERSION,
    JOB_RUNNER_CONTRACT_VERSION,
    ManifestError,
    build_job_identity,
    load_job_manifest,
    manifest_compatibility,
    scientific_job_id,
    write_job_manifest,
)

logger = logging.getLogger(__name__)

AGRIBRAIN_ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = AGRIBRAIN_ROOT / "artifacts" / "asmae_jobs"
JOBS_DIR = Path(os.environ.get('ASMAE_JOBS_DIR', str(JOBS_DIR))).resolve()
LEASE_SECONDS = 180
LAUNCH_COOLDOWN_SECONDS = 15
RESERVATION_STALE_SECONDS = 30
MAX_EXECUTION_ATTEMPTS = 3
_UNSET = object()

QUEUED_STATUSES: FrozenSet[str] = frozenset(
    {'queued', 'stalled', 'completed_reintegration_pending'}
)
TERMINAL_STATUSES: FrozenSet[str] = frozenset(
    {'failed', 'completed', 'superseded'}
)
_JOB_ID = re.compile(r"^[0-9a-f]{24}$")


class LeaseLostError(RuntimeError):
    '''Raised when a worker no longer owns the durable commit fence.'''

    worker_lease_lost = True


@dataclass(frozen=True)
class WorkerLease:
    token: str
    generation: int
    owner: str


@dataclass(frozen=True)
class WorkerClaim:
    path: Path
    token: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _reservation_is_stale(payload: Dict[str, Any]) -> bool:
    if payload.get("status") != "reserving":
        return False
    raw = payload.get("updated_at") or payload.get("created_at")
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return (_now() - stamp).total_seconds() >= RESERVATION_STALE_SECONDS
    except (TypeError, ValueError):
        return True


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _atomic_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        path.name + f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    last_error: Optional[OSError] = None
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.01 * (2 ** attempt))
    temporary.unlink(missing_ok=True)
    raise last_error or OSError(f"could not publish {path}")


@contextmanager
def _record_lock(path: Path, timeout_seconds: float = 15.0):
    """Cross-process write lock with stale-owner recovery."""
    lock_path = path.with_name(path.name + ".write.lock")
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()}:{threading.get_ident()}:{time.time()}")
            break
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > LEASE_SECONDS:
                    lock_path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out acquiring job record lock: {path}")
            time.sleep(0.025)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _update_job(
    path: Path,
    expected_revision: Optional[int] = None,
    expected_manifest_hash: Optional[str] = None,
    expected_lease_token: Any = _UNSET,
    expected_lease_generation: Optional[int] = None,
    expected_launch_token: Any = _UNSET,
    expected_statuses: Optional[FrozenSet[str]] = None,
    **changes: Any,
) -> Dict[str, Any]:
    with _record_lock(path):
        payload = _read_json(path)
        if not payload or not payload.get("job_id") or not payload.get("plot_id"):
            quarantine_dir = JOBS_DIR / "quarantine"
            quarantine_dir.mkdir(parents=True, exist_ok=True)
            if path.exists():
                try:
                    shutil.move(str(path), str(quarantine_dir / path.name))
                except Exception:
                    pass
            raise ValueError(f"Job record at {path} is malformed or patch-only; moved to quarantine")

        current_rev = int(payload.get("revision", 0) or 0)
        if expected_revision is not None and current_rev != expected_revision:
            raise ValueError(f"TransactionConflict: revision mismatch {current_rev} != {expected_revision}")
        if expected_manifest_hash and str(payload.get("manifest_hash", "")) != expected_manifest_hash:
            raise ValueError(f"TransactionConflict: manifest hash mismatch")
        if (
            expected_lease_token is not _UNSET
            and payload.get('lease_token') != expected_lease_token
        ):
            raise LeaseLostError('worker lease token is no longer current')
        if (
            expected_lease_generation is not None
            and int(payload.get('lease_generation', 0) or 0)
            != expected_lease_generation
        ):
            raise LeaseLostError('worker lease generation is no longer current')
        if (
            expected_launch_token is not _UNSET
            and payload.get('launch_token') != expected_launch_token
        ):
            raise LeaseLostError('worker launch token is no longer current')
        if expected_statuses and str(payload.get('status')) not in expected_statuses:
            raise LeaseLostError(
                f"worker cannot update terminal status {payload.get('status')}"
            )

        payload.update(changes)
        payload["revision"] = current_rev + 1
        payload["updated_at"] = _now().isoformat()
        _atomic_json(path, payload)
        return payload


def _paths(job_id: str) -> Tuple[Path, Path]:
    return (
        JOBS_DIR / f"{job_id}.job.json",
        JOBS_DIR / f"{job_id}.manifest.json",
    )


def _manifest_for_job(job_path: Path, payload: Dict[str, Any]) -> Path:
    job_id = str(payload.get("job_id", ""))
    expected_job, expected_manifest = _paths(job_id)
    if job_path.resolve() != expected_job.resolve():
        raise ManifestError("job record path does not match its identity")
    supplied = Path(str(payload.get("manifest_ref", "")))
    if supplied.resolve() != expected_manifest.resolve():
        raise ManifestError("job manifest path does not match its identity")
    return expected_manifest


def _requires_reintegration(context: Dict[str, Any]) -> bool:
    value = context.get("orchestrator_reintegration")
    return bool(
        isinstance(value, dict)
        and value.get("contract_version")
        == "asmae_orchestrator_reintegration_v1"
    )


def _completed_compatible(
    existing: Dict[str, Any],
    manifest_path: Path,
    identity: Dict[str, Any],
) -> Tuple[bool, str]:
    job_id = str(existing.get("job_id", ""))
    compatible, reason = manifest_compatibility(
        manifest_path, job_id=job_id, identity=identity
    )
    if not compatible:
        return False, reason
    if existing.get("status") != "completed":
        return False, "job_is_not_complete"
    snapshot_id = existing.get("final_snapshot_id")
    from .snapshot_store import snapshot_is_compatible

    if not snapshot_is_compatible(
        str(existing.get("plot_id", "")),
        geometry_hash=str(identity.get("geometry_hash", "")),
        snapshot_id=str(snapshot_id or ""),
        crop_posterior_lineage=str(
            identity.get("crop_posterior_lineage", "")
        ),
    ):
        return False, "completed_job_snapshot_is_obsolete"
    if existing.get("reintegration_required"):
        from .plot_snapshot_store import load_latest_plot_snapshot

        plot_snapshot = load_latest_plot_snapshot(
            str(existing.get("plot_id", "")),
            str(identity.get("geometry_hash", "")),
        )
        if not plot_snapshot or plot_snapshot.get("snapshot_id") != snapshot_id:
            return False, "completed_job_downstream_snapshot_is_obsolete"
    return True, "compatible"

# ── Retry decision ────────────────────────────────────────────────────────────

_TERMINAL_NON_RETRYABLE = {"manual_review", "permanent_contract", "permanent_failure"}


def resolve_retry_decision(
    existing: Dict[str, Any],
    new_contract_version: str,
) -> str:
    """Return one of: return_existing_manual_review | enqueue_successor_contract_changed
                     | retry_transient | return_existing_permanent."""
    retry_class = str(existing.get("retry_classification") or "")
    old_capability_version = str(
        existing.get("scientific_identity", {}).get(
            "evidence_capability_contract_version", ""
        )
    )
    if retry_class == "manual_review":
        # Contract changed since the failure → create a successor job
        if old_capability_version != new_contract_version:
            return "enqueue_successor_contract_changed"
        return "return_existing_manual_review"
    if retry_class in ("permanent_contract", "permanent_failure"):
        return "return_existing_permanent"
    if retry_class in {"retryable", "retryable_execution", "retryable_launch"}:
        attempts = int(existing.get("attempts", 0) or 0)
        if attempts < MAX_EXECUTION_ATTEMPTS:
            return "retry_transient"
        return "return_existing_permanent"
    return "enqueue_successor_contract_changed"


# ── Successor-job enqueue ────────────────────────────────────────────────────

def _enqueue_successor(
    predecessor: Dict[str, Any],
    plot_id: str,
    run_id: str,
    context: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Write and spawn a new job that supersedes a failed predecessor."""
    # Stamp the predecessor as superseded (immutable audit trail)
    predecessor_job_id = str(predecessor.get("job_id", ""))
    if predecessor_job_id:
        predecessor_path = JOBS_DIR / f"{predecessor_job_id}.job.json"
        if predecessor_path.exists():
            _update_job(
                predecessor_path,
                status='superseded',
                stage='superseded',
                superseded=True,
                superseded_at=_now().isoformat(),
                recoverable=False,
            )

    # Tag the context so the new job gets a different identity
    context = dict(context)
    context["evidence_capability_contract_version"] = (
        EVIDENCE_CAPABILITY_CONTRACT_VERSION
    )
    context["supersedes_job_id"] = predecessor_job_id

    identity = build_job_identity(plot_id, context, config)
    # Embed the capability version into the identity for hash differentiation
    identity["evidence_capability_contract_version"] = (
        EVIDENCE_CAPABILITY_CONTRACT_VERSION
    )
    job_id = scientific_job_id(identity)
    job_path, manifest_path = _paths(job_id)

    manifest = write_job_manifest(
        manifest_path,
        job_id=job_id,
        plot_id=plot_id,
        run_id=run_id,
        context=context,
        config=config,
        identity=identity,
    )
    _atomic_json(
        job_path,
        {
            "job_id": job_id,
            "plot_id": plot_id,
            "run_id": run_id,
            "mode": "standard",
            "status": "queued",
            "stage": "manifest_persisted",
            "progress_pct": 5,
            "attempts": 0,
            "manifest_ref": str(manifest_path),
            "manifest_hash": manifest.get("manifest_hash"),
            "manifest_contract_version": JOB_MANIFEST_CONTRACT_VERSION,
            "worker_contract_version": JOB_RUNNER_CONTRACT_VERSION,
            "evidence_capability_contract_version": EVIDENCE_CAPABILITY_CONTRACT_VERSION,
            "scientific_identity": identity,
            "context_hash": identity.get("context_hash"),
            "geometry_hash": identity.get("geometry_hash"),
            "crop_posterior_lineage": identity.get("crop_posterior_lineage"),
            "crop_lineage_id": identity.get("crop_lineage_id"),
            "supersedes_job_id": predecessor_job_id,
            "retry_reason": "superseding_obsolete_capability_contract",
            "reintegration_required": _requires_reintegration(context),
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "restart_recoverable": True,
            "compatibility": "current",
        },
    )
    spawn_worker(job_path)
    return {
        "job_id": job_id,
        "status": "queued",
        "job_ref": str(job_path),
        "manifest_ref": str(manifest_path),
        "deduplicated": False,
        "compatibility": "current",
        "progress_pct": 5,
        "supersedes_job_id": predecessor_job_id,
        "final_snapshot_id": None,
    }


# ── Compatible-job lookup ────────────────────────────────────────────────────

def latest_compatible_job(
    plot_id: str,
    geometry_hash: Optional[str] = None,
    capability_plan_hash: Optional[str] = None,
    worker_contract_version: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the most recent job whose identity matches the current capability
    contract, geometry, and worker version. Returns None when no match exists."""
    if not JOBS_DIR.exists():
        return None
    matches = []
    for job_path in JOBS_DIR.glob("*.job.json"):
        payload = _read_json(job_path)
        if str(payload.get("plot_id", "")) != str(plot_id):
            continue
        if geometry_hash and str(payload.get("geometry_hash", "")) != geometry_hash:
            continue
        if worker_contract_version and str(
            payload.get("worker_contract_version", "")
        ) != worker_contract_version:
            continue
        if capability_plan_hash:
            sid = payload.get("scientific_identity") or {}
            job_cap_hash = str(sid.get("capability_plan_hash", ""))
            if job_cap_hash != capability_plan_hash:
                continue
        if payload.get("superseded"):
            continue
        matches.append(payload)
    if not matches:
        return None
    return max(matches, key=lambda v: str(v.get("updated_at", "")))



def enqueue_standard_job(
    plot_id: str,
    run_id: str,
    context: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist a validated manifest before making a job visible to workers."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    identity = build_job_identity(plot_id, context, config)
    job_id = scientific_job_id(identity)
    job_path, manifest_path = _paths(job_id)
    existing = _read_json(job_path)
    owns_reservation = False

    # Reserve a previously unseen scientific identity with O_EXCL. Other API
    # processes wait for the owner to publish the manifest/job record instead
    # of concurrently overwriting it.
    if not existing and not job_path.exists():
        reservation = {
            "job_id": job_id,
            "plot_id": plot_id,
            "run_id": run_id,
            "status": "reserving",
            "stage": "identity_reserved",
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "scientific_identity": identity,
            "revision": 0,
        }
        try:
            with job_path.open("x", encoding="utf-8") as handle:
                json.dump(reservation, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            existing = reservation
            owns_reservation = True
        except FileExistsError:
            for _ in range(200):
                time.sleep(0.025)
                existing = _read_json(job_path)
                if existing and existing.get("status") != "reserving":
                    return enqueue_standard_job(plot_id, run_id, context, config)
            return {
                "job_id": job_id,
                "status": "queued",
                "stage": "identity_reserved",
                "job_ref": str(job_path),
                "manifest_ref": str(manifest_path),
                "deduplicated": True,
                "compatibility": "reservation_pending",
                "progress_pct": 0,
                "final_snapshot_id": None,
            }
    # On Windows another process can observe the O_EXCL reservation path in
    # the tiny interval before its JSON payload is fully flushed.  Treat an
    # existing-but-not-yet-readable record as a reservation in progress;
    # otherwise that observer can publish the same manifest and spawn a
    # duplicate worker.
    if job_path.exists() and not existing and not owns_reservation:
        for _ in range(200):
            time.sleep(0.025)
            existing = _read_json(job_path)
            if existing:
                break
        if not existing:
            return {
                "job_id": job_id,
                "status": "queued",
                "stage": "identity_reserved",
                "job_ref": str(job_path),
                "manifest_ref": str(manifest_path),
                "deduplicated": True,
                "compatibility": "reservation_pending",
                "progress_pct": 0,
                "final_snapshot_id": None,
            }
    if existing.get("status") == "reserving" and not owns_reservation:
        if _reservation_is_stale(existing):
            with _record_lock(job_path):
                current = _read_json(job_path)
                if _reservation_is_stale(current):
                    existing = current
                    owns_reservation = True
        for _ in range(200):
            if owns_reservation:
                break
            time.sleep(0.025)
            published = _read_json(job_path)
            if published and published.get("status") != "reserving":
                return enqueue_standard_job(plot_id, run_id, context, config)
        return {
            "job_id": job_id,
            "status": "queued",
            "stage": "identity_reserved",
            "job_ref": str(job_path),
            "manifest_ref": str(manifest_path),
            "deduplicated": True,
            "compatibility": "reservation_pending",
            "progress_pct": 0,
            "final_snapshot_id": None,
        }

    if existing.get("status") in {
        "queued",
        "running",
        'stalled',
        "completed_reintegration_pending",
    }:
        compatible, reason = manifest_compatibility(
            manifest_path, job_id=job_id, identity=identity
        )
        if compatible:
            return {
                "job_id": job_id,
                "status": _canonical_status(existing.get('status')),
                "job_ref": str(job_path),
                "manifest_ref": str(manifest_path),
                "deduplicated": True,
                "compatibility": "compatible",
                "progress_pct": existing.get("progress_pct", 0),
                "final_snapshot_id": existing.get("final_snapshot_id"),
                'recoverable': True,
            }
        superseded = _update_job(
            job_path,
            status='superseded',
            stage='superseded_contract',
            superseded=True,
            compatibility='obsolete',
            compatibility_reason=reason,
            retry_classification="permanent_contract",
            recoverable=False,
        )
        return {
            **_public_job_payload(superseded),
            'job_ref': str(job_path),
            'manifest_ref': str(manifest_path),
            'deduplicated': True,
        }

    if existing.get("status") == "completed":
        compatible, reason = _completed_compatible(
            existing, manifest_path, identity
        )
        if compatible:
            return {
                "job_id": job_id,
                "status": "completed",
                "job_ref": str(job_path),
                "manifest_ref": str(manifest_path),
                "deduplicated": True,
                "compatibility": "compatible",
                "progress_pct": 100,
                "final_snapshot_id": existing.get("final_snapshot_id"),
                "final_snapshot_ref": existing.get("final_snapshot_ref"),
            }
        superseded = _update_job(
            job_path,
            status='superseded',
            stage='superseded_snapshot',
            superseded=True,
            compatibility='obsolete',
            compatibility_reason=reason,
            retry_classification="permanent_contract",
            recoverable=False,
        )
        return {
            **_public_job_payload(superseded),
            'job_ref': str(job_path),
            'manifest_ref': str(manifest_path),
            'deduplicated': True,
        }

    # ── Explicit failed / degraded branch ────────────────────────────────
    # The original code had no branch for failed/manual_review and would
    # silently overwrite the failed record as queued.  We now resolve a
    # retry decision before writing anything.
    if _canonical_status(existing.get('status')) == 'failed':
        decision = resolve_retry_decision(
            existing, EVIDENCE_CAPABILITY_CONTRACT_VERSION
        )
        if decision == "return_existing_manual_review":
            # No auto-retry; return the immutable failed state so the UI shows it
            return {
                "job_id": str(existing.get("job_id", "")),
                "status": "failed",
                "stage": existing.get("stage", ""),
                "failure_code": existing.get("reason", ""),
                "retry_classification": "manual_review",
                "job_ref": str(job_path),
                "manifest_ref": str(manifest_path),
                "deduplicated": True,
                "superseded": False,
                "progress_pct": int(existing.get("progress_pct", 100)),
                "updated_at": existing.get("updated_at", ""),
            }
        if decision == "return_existing_permanent":
            return {
                "job_id": str(existing.get("job_id", "")),
                "status": "failed",
                "stage": existing.get("stage", ""),
                "failure_code": existing.get("reason", ""),
                "retry_classification": existing.get("retry_classification", "permanent"),
                "job_ref": str(job_path),
                "manifest_ref": str(manifest_path),
                "deduplicated": True,
                "superseded": False,
                "progress_pct": int(existing.get("progress_pct", 100)),
                "updated_at": existing.get("updated_at", ""),
            }
        if decision == "enqueue_successor_contract_changed":
            return _enqueue_successor(
                existing, plot_id, run_id, context, config
            )
        # retry_transient — fall through to normal write below

    if _canonical_status(existing.get('status')) == 'superseded':
        return {
            **_public_job_payload(existing),
            'job_ref': str(job_path),
            'manifest_ref': str(manifest_path),
            'deduplicated': True,
        }

    try:
        manifest = write_job_manifest(
            manifest_path,
            job_id=job_id,
            plot_id=plot_id,
            run_id=run_id,
            context=context,
            config=config,
            identity=identity,
        )
        attempts = int(existing.get("attempts", 0) or 0)
        _atomic_json(
            job_path,
            {
            "job_id": job_id,
            "plot_id": plot_id,
            "run_id": run_id,
            "mode": "standard",
            "status": "queued",
            "stage": "manifest_persisted",
            "progress_pct": 5,
            "attempts": attempts,
            "manifest_ref": str(manifest_path),
            "manifest_hash": manifest.get("manifest_hash"),
            "manifest_contract_version": JOB_MANIFEST_CONTRACT_VERSION,
            "worker_contract_version": JOB_RUNNER_CONTRACT_VERSION,
            "scientific_identity": identity,
            "context_hash": identity.get("context_hash"),
            "geometry_hash": identity.get("geometry_hash"),
            "crop_posterior_lineage": identity.get(
                "crop_posterior_lineage"
            ),
            "crop_lineage_id": identity.get("crop_lineage_id"),
            "reintegration_required": _requires_reintegration(context),
            "created_at": existing.get("created_at") or _now().isoformat(),
            "updated_at": _now().isoformat(),
            "restart_recoverable": True,
            "compatibility": "current",
            "evidence_capability_contract_version": EVIDENCE_CAPABILITY_CONTRACT_VERSION,
            "capability_plan_hash": identity.get("capability_plan_hash"),
            "revision": int(existing.get("revision", 0) or 0) + 1,
            },
        )
    except Exception as exc:
        _update_job(
            job_path,
            status='failed',
            stage="manifest_publication_failed",
            reason=str(exc),
            retry_classification="retryable_launch",
            recoverable=True,
        )
        raise
    spawn_worker(job_path)
    return {
        "job_id": job_id,
        "status": "queued",
        "job_ref": str(job_path),
        "manifest_ref": str(manifest_path),
        "deduplicated": False,
        "compatibility": "current",
        "progress_pct": 5,
        "final_snapshot_id": None,
    }


REPO_ROOT = AGRIBRAIN_ROOT.parents[1]


def _parse_timestamp(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
    except (TypeError, ValueError):
        return None


def _canonical_status(status: Any) -> str:
    raw = str(status or 'queued')
    return {
        'reserving': 'queued',
        'completed_reintegration_pending': 'queued',
        'failed_to_launch': 'failed',
        'degraded': 'failed',
        'error': 'failed',
        'obsolete': 'superseded',
    }.get(raw, raw)


def _public_job_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    public = dict(payload)
    public['status'] = _canonical_status(public.get('status'))
    public['recoverable'] = bool(
        public.get('recoverable')
        or public['status'] in {'queued', 'stalled'}
    ) and public['status'] not in TERMINAL_STATUSES
    public.pop('lease_token', None)
    public.pop('launch_token', None)
    return public


def _job_log_paths(job_path: Path) -> Tuple[Path, Path]:
    stem = job_path.name.removesuffix('.job.json')
    return (
        job_path.with_name(f'{stem}.worker.log'),
        job_path.with_name(f'{stem}.events.jsonl'),
    )


def _append_job_event(job_path: Path, event: str, **details: Any) -> None:
    _, event_path = _job_log_paths(job_path)
    record = {
        'timestamp': _now().isoformat(),
        'event': event,
        'job_id': job_path.name.removesuffix('.job.json'),
        **details,
    }
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with _record_lock(event_path):
        with event_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + '\n')
            handle.flush()
            os.fsync(handle.fileno())


def _reserve_launch(job_path: Path) -> Optional[str]:
    with _record_lock(job_path):
        payload = _read_json(job_path)
        if not payload:
            return None
        status = _canonical_status(payload.get('status'))
        if status in TERMINAL_STATUSES:
            return None
        if status == 'running':
            if not _lease_expired(payload):
                return None
            exhausted = _recovery_attempt_count(payload) >= MAX_EXECUTION_ATTEMPTS
            payload.update(
                status='failed' if exhausted else 'stalled',
                stage=(
                    'worker_recovery_exhausted'
                    if exhausted
                    else 'worker_lease_expired'
                ),
                stalled_at=_now().isoformat(),
                recovery_reason=(
                    'maximum_recovery_attempts_exhausted'
                    if exhausted
                    else 'expired_worker_lease'
                ),
                retry_classification=(
                    'manual_review' if exhausted else 'retryable_execution'
                ),
                recoverable=not exhausted,
                stale_lease_owner=payload.get('lease_owner'),
                lease_owner=None,
                lease_token=None,
                lease_generation=(
                    int(payload.get('lease_generation', 0) or 0) + 1
                ),
                lease_expires_at=None,
            )
            if exhausted:
                payload['revision'] = int(payload.get('revision', 0) or 0) + 1
                payload['updated_at'] = _now().isoformat()
                _atomic_json(job_path, payload)
                return None
            status = 'stalled'
        reserved_at = _parse_timestamp(payload.get('launch_reserved_at'))
        if (
            reserved_at is not None
            and (_now() - reserved_at).total_seconds() < LAUNCH_COOLDOWN_SECONDS
        ):
            return None
        launch_token = uuid.uuid4().hex
        stdout_path, event_path = _job_log_paths(job_path)
        payload.update(
            launch_token=launch_token,
            launch_reserved_at=_now().isoformat(),
            launch_state='reserved',
            launch_attempts=int(payload.get('launch_attempts', 0) or 0) + 1,
            worker_log_ref=str(stdout_path),
            worker_event_log_ref=str(event_path),
            recoverable=True,
        )
        payload['revision'] = int(payload.get('revision', 0) or 0) + 1
        payload['updated_at'] = _now().isoformat()
        _atomic_json(job_path, payload)
        return launch_token


def spawn_worker(job_path: Path) -> bool:
    """Launch a detached worker once for the current durable launch token."""
    launch_token = _reserve_launch(job_path)
    if launch_token is None:
        return False
    environment = dict(os.environ)
    current_pythonpath = environment.get("PYTHONPATH", "")
    new_paths = [str(REPO_ROOT), str(AGRIBRAIN_ROOT)]
    if current_pythonpath:
        new_paths.append(current_pythonpath)
    environment["PYTHONPATH"] = os.pathsep.join(new_paths)
    environment['ASMAE_JOBS_DIR'] = str(JOBS_DIR)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    stdout_path, _ = _job_log_paths(job_path)
    _append_job_event(job_path, 'worker_launch_reserved')
    try:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        with stdout_path.open('ab', buffering=0) as worker_log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    '-m',
                    'services.agribrain.layer05_asmae.background_jobs',
                    str(job_path),
                    launch_token,
                ],
                cwd=str(REPO_ROOT),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=worker_log,
                stderr=subprocess.STDOUT,
                close_fds=True,
                creationflags=creationflags,
                start_new_session=(os.name != 'nt'),
            )
        _update_job(
            job_path,
            expected_launch_token=launch_token,
            worker_pid=process.pid,
            launch_state='started',
            launched_at=_now().isoformat(),
        )
        _append_job_event(job_path, 'worker_process_started', pid=process.pid)
        return True
    except OSError as exc:
        _update_job(
            job_path,
            expected_launch_token=launch_token,
            status='failed',
            stage='launch_failed',
            error=str(exc),
            retry_classification='retryable_launch',
            recoverable=True,
            launch_state='failed',
        )
        _append_job_event(
            job_path,
            'worker_launch_failed',
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return False


def _lease_expired(payload: Dict[str, Any]) -> bool:
    expires_at = _parse_timestamp(payload.get('lease_expires_at'))
    return expires_at is None or expires_at <= _now()


def _recovery_attempt_count(payload: Dict[str, Any]) -> int:
    if payload.get('resume_phase') == 'reintegration':
        return int(payload.get('reintegration_attempts', 0) or 0)
    return int(payload.get('attempts', 0) or 0)


def _job_created_at(payload: Dict[str, Any]) -> datetime:
    """Return immutable request recency; status updates must not reorder jobs."""
    return (
        _parse_timestamp(payload.get('created_at'))
        or _parse_timestamp(payload.get('updated_at'))
        or datetime.min.replace(tzinfo=timezone.utc)
    )


def _commit_job_lifecycle_event(
    job_path: Path,
    payload: Dict[str, Any],
    event_type: str,
    **details: Any,
) -> Optional[str]:
    """Best-effort canonical audit event; never authorizes a state update."""
    try:
        saved = load_job_manifest(_manifest_for_job(job_path, payload))
        context = dict(saved.get('context') or {})
        geometry_hash = str(
            payload.get('geometry_hash')
            or (saved.get('identity') or {}).get('geometry_hash')
            or ''
        )
        if not geometry_hash:
            return None
        from .history.worldline_service import PlotWorldlineService

        event_time = _now().isoformat()
        event = PlotWorldlineService().commit_event(
            plot_id=str(payload.get('plot_id') or ''),
            event_type=event_type,
            geometry_hash=geometry_hash,
            authority='DIAGNOSTIC_NO_STATE_UPDATE',
            effective_at=event_time,
            observation_or_valid_time=event_time,
            tenant_id=str(context.get('tenant_id') or 'default_tenant'),
            namespace=str(context.get('worldline_namespace') or 'default'),
            payload={
                'job_id': payload.get('job_id'),
                'run_id': payload.get('run_id'),
                'manifest_hash': payload.get('manifest_hash'),
                'status': payload.get('status'),
                'stage': payload.get('stage'),
                **details,
            },
        )
        return str(event.get('event_id') or '') or None
    except Exception as exc:
        logger.debug('Could not commit %s lifecycle event: %s', event_type, exc)
        return None


def _mark_stalled_if_expired(
    job_path: Path, payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    candidate = payload or _read_json(job_path)
    if candidate.get('status') != 'running' or not _lease_expired(candidate):
        return candidate
    changed = False
    with _record_lock(job_path):
        current = _read_json(job_path)
        if current.get('status') == 'running' and _lease_expired(current):
            generation = int(current.get('lease_generation', 0) or 0) + 1
            exhausted = _recovery_attempt_count(current) >= MAX_EXECUTION_ATTEMPTS
            current.update(
                status='failed' if exhausted else 'stalled',
                stage=(
                    'worker_recovery_exhausted'
                    if exhausted
                    else 'worker_lease_expired'
                ),
                stalled_at=_now().isoformat(),
                recovery_reason=(
                    'maximum_recovery_attempts_exhausted'
                    if exhausted
                    else 'expired_worker_lease'
                ),
                retry_classification=(
                    'manual_review'
                    if exhausted
                    else current.get('retry_classification', 'retryable_execution')
                ),
                recoverable=not exhausted,
                stale_lease_owner=current.get('lease_owner'),
                lease_owner=None,
                lease_token=None,
                lease_generation=generation,
                lease_expires_at=None,
            )
            current['revision'] = int(current.get('revision', 0) or 0) + 1
            current['updated_at'] = _now().isoformat()
            _atomic_json(job_path, current)
            changed = True
        candidate = current
    if changed:
        lifecycle_type = (
            'ASMAE_JOB_RECOVERY_EXHAUSTED'
            if candidate.get('status') == 'failed'
            else 'ASMAE_JOB_STALLED'
        )
        lifecycle_event_id = _commit_job_lifecycle_event(
            job_path,
            candidate,
            lifecycle_type,
            recovery_reason=candidate.get('recovery_reason'),
            stale_lease_owner=candidate.get('stale_lease_owner'),
        )
        _append_job_event(
            job_path,
            (
                'worker_recovery_exhausted'
                if candidate.get('status') == 'failed'
                else 'worker_lease_expired'
            ),
            lease_generation=candidate.get('lease_generation'),
            previous_owner=candidate.get('stale_lease_owner'),
            worldline_event_id=lifecycle_event_id,
        )
    return candidate


def _supersede_recovery_candidate(
    job_path: Path,
    payload: Dict[str, Any],
    winner: Dict[str, Any],
) -> Dict[str, Any]:
    """Revoke an older active request so its worker cannot publish later."""
    active_statuses = frozenset({
        'queued', 'stalled', 'running', 'completed_reintegration_pending',
    })
    current = dict(payload)
    superseded: Optional[Dict[str, Any]] = None
    for _ in range(4):
        if str(current.get('status')) not in active_statuses:
            return current
        try:
            superseded = _update_job(
                job_path,
                expected_revision=int(current.get('revision', 0) or 0),
                expected_statuses=active_statuses,
                status='superseded',
                stage='superseded_by_newer_plot_request',
                superseded=True,
                superseded_at=_now().isoformat(),
                superseded_by_job_id=winner.get('job_id'),
                superseded_by_run_id=winner.get('run_id'),
                recovery_reason='newer_unsuperseded_plot_job_exists',
                recoverable=False,
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                lease_generation=int(
                    current.get('lease_generation', 0) or 0
                ) + 1,
                launch_token=None,
            )
            break
        except (LeaseLostError, ValueError):
            current = _read_json(job_path)
    if superseded is None:
        return current

    lifecycle_event_id = _commit_job_lifecycle_event(
        job_path,
        superseded,
        'ASMAE_JOB_SUPERSEDED',
        superseded_by_job_id=winner.get('job_id'),
        superseded_by_run_id=winner.get('run_id'),
    )
    _append_job_event(
        job_path,
        'worker_job_superseded',
        superseded_by_job_id=winner.get('job_id'),
        superseded_by_run_id=winner.get('run_id'),
        worldline_event_id=lifecycle_event_id,
    )
    return superseded


def recover_pending_jobs(
    *, plot_id: Optional[str] = None, job_id: Optional[str] = None
) -> int:
    """Recover at most the newest unsuperseded request for each plot."""
    if not JOBS_DIR.exists():
        return 0
    records = []
    for job_path in JOBS_DIR.glob("*.job.json"):
        payload = _read_json(job_path)
        if not payload:
            continue
        if plot_id is not None and str(payload.get('plot_id')) != str(plot_id):
            continue
        payload = _mark_stalled_if_expired(job_path, payload)
        records.append((job_path, payload))

    if job_id is not None:
        requested = next((
            payload for _, payload in records
            if str(payload.get('job_id')) == str(job_id)
        ), None)
        if requested is None:
            return 0
        requested_plot_id = str(requested.get('plot_id'))
        records = [
            pair for pair in records
            if str(pair[1].get('plot_id')) == requested_plot_id
        ]

    active_statuses = {
        'queued', 'stalled', 'running', 'completed_reintegration_pending',
    }
    active_by_plot: Dict[str, list[Tuple[Path, Dict[str, Any]]]] = {}
    for job_path, payload in records:
        if payload.get('superseded') or str(payload.get('status')) not in active_statuses:
            continue
        active_by_plot.setdefault(str(payload.get('plot_id')), []).append(
            (job_path, payload)
        )

    resumed = 0
    for candidates in active_by_plot.values():
        winner_path, winner = max(
            candidates,
            key=lambda pair: (
                _job_created_at(pair[1]),
                str(pair[1].get('job_id') or ''),
            ),
        )
        for candidate_path, candidate in candidates:
            if candidate_path != winner_path:
                _supersede_recovery_candidate(candidate_path, candidate, winner)

        if job_id is not None and str(winner.get('job_id')) != str(job_id):
            continue
        status = str(winner.get('status'))
        if status == 'completed_reintegration_pending':
            winner = _update_job(
                winner_path,
                status='stalled',
                stage='downstream_reintegration_retry',
                resume_phase='reintegration',
                recovery_reason='reintegration_pending',
                recoverable=True,
            )
            status = 'stalled'
        if status in {'queued', 'stalled'} and spawn_worker(winner_path):
            resumed += 1
            lifecycle_event_id = _commit_job_lifecycle_event(
                winner_path,
                _read_json(winner_path) or winner,
                'ASMAE_JOB_RECOVERED',
                recovery_reason=winner.get('recovery_reason'),
            )
            _append_job_event(
                winner_path,
                'worker_recovery_launched',
                worldline_event_id=lifecycle_event_id,
            )
    return resumed


def _claim(job_path: Path) -> Optional[WorkerClaim]:
    lock_path = job_path.with_suffix(".lock")
    claim_token = uuid.uuid4().hex
    try:
        descriptor = os.open(
            str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
        )
    except FileExistsError:
        payload = _read_json(job_path)
        try:
            lock_age_seconds = time.time() - lock_path.stat().st_mtime
        except OSError:
            lock_age_seconds = LEASE_SECONDS + 1
        if lock_age_seconds < LEASE_SECONDS or not _lease_expired(payload):
            return None
        try:
            lock_path.unlink()
        except OSError:
            return None
        return _claim(job_path)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    'pid': os.getpid(),
                    'claim_token': claim_token,
                    'created_at': _now().isoformat(),
                },
                sort_keys=True,
            )
        )
        handle.flush()
        os.fsync(handle.fileno())
    return WorkerClaim(path=lock_path, token=claim_token)


def _release_claim(claim: WorkerClaim) -> None:
    try:
        value = _read_json(claim.path)
        if value.get('claim_token') == claim.token:
            claim.path.unlink(missing_ok=True)
    except OSError:
        pass


def _begin_lease(
    job_path: Path, launch_token: Optional[str]
) -> Optional[Tuple[Dict[str, Any], WorkerLease]]:
    with _record_lock(job_path):
        payload = _read_json(job_path)
        status = _canonical_status(payload.get('status'))
        if status not in {'queued', 'stalled'}:
            return None
        current_launch_token = payload.get('launch_token')
        if current_launch_token and current_launch_token != launch_token:
            return None
        if launch_token and not current_launch_token:
            return None
        if launch_token is None:
            launch_token = uuid.uuid4().hex
            payload['launch_token'] = launch_token
        resume_reintegration = bool(
            payload.get('resume_phase') == 'reintegration'
            or payload.get('status') == 'completed_reintegration_pending'
        )
        generation = int(payload.get('lease_generation', 0) or 0) + 1
        lease = WorkerLease(
            token=uuid.uuid4().hex,
            generation=generation,
            owner=f'pid:{os.getpid()}',
        )
        payload.update(
            status='running',
            stage=(
                'downstream_reintegration'
                if resume_reintegration
                else 'scientific_execution'
            ),
            progress_pct=85 if resume_reintegration else 15,
            attempts=(
                int(payload.get('attempts', 0) or 0)
                + (0 if resume_reintegration else 1)
            ),
            lease_owner=lease.owner,
            lease_token=lease.token,
            lease_generation=lease.generation,
            lease_expires_at=(
                _now() + timedelta(seconds=LEASE_SECONDS)
            ).isoformat(),
            last_heartbeat_at=_now().isoformat(),
            worker_started_at=_now().isoformat(),
            recoverable=True,
            launch_state='claimed',
            resume_phase='reintegration' if resume_reintegration else 'scientific',
        )
        payload['revision'] = int(payload.get('revision', 0) or 0) + 1
        payload['updated_at'] = _now().isoformat()
        _atomic_json(job_path, payload)
        return payload, lease


def _fenced_update_job(
    job_path: Path, lease: WorkerLease, **changes: Any
) -> Dict[str, Any]:
    return _update_job(
        job_path,
        expected_lease_token=lease.token,
        expected_lease_generation=lease.generation,
        expected_statuses=frozenset({'running'}),
        **changes,
    )


def _renew_lease(job_path: Path, lease: WorkerLease) -> Dict[str, Any]:
    return _fenced_update_job(
        job_path,
        lease,
        lease_owner=lease.owner,
        lease_expires_at=(
            _now() + timedelta(seconds=LEASE_SECONDS)
        ).isoformat(),
        last_heartbeat_at=_now().isoformat(),
    )


def assert_worker_commit_fence(job_path: Path, lease: WorkerLease) -> None:
    """Renew the lease immediately before a worker publishes durable science."""
    _renew_lease(job_path, lease)


def _validate_result(
    result: Any, payload: Dict[str, Any], identity: Dict[str, Any]
) -> None:
    if not isinstance(result, dict):
        raise ManifestError("worker result is not an object")
    if str(result.get("plot_id", "")) != str(payload.get("plot_id", "")):
        raise ManifestError("worker result plot identity mismatch")
    status = str(result.get("status", ""))
    if status not in {"success", "partial", "unavailable", "error"}:
        raise ManifestError(f"worker result has invalid status: {status}")
    if status in {"success", "partial"}:
        if not isinstance(result.get("plot_state_artifact"), dict):
            raise ManifestError("completed worker result has no plot-state artifact")
        snapshot_id = result.get("snapshot_id")
        from .snapshot_store import snapshot_is_compatible

        if not snapshot_is_compatible(
            str(payload.get("plot_id", "")),
            geometry_hash=str(identity.get("geometry_hash", "")),
            snapshot_id=str(snapshot_id or ""),
            crop_posterior_lineage=str(
                identity.get("crop_posterior_lineage", "")
            ),
        ):
            raise ManifestError(
                "completed worker result has no compatible canonical snapshot"
            )


def _required_scientific_valid_time(
    result: Dict[str, Any], context: Dict[str, Any], job: Dict[str, Any]
) -> str:
    evidence_state = result.get("asmae_evidence_state")
    if not isinstance(evidence_state, dict):
        evidence_state = {}
    for candidate in (
        result.get("as_of"),
        result.get("observation_or_valid_time"),
        evidence_state.get("as_of"),
        context.get("end_date"),
        context.get("reference_date"),
        context.get("as_of"),
        job.get("created_at"),
    ):
        parsed = _parse_timestamp(candidate)
        if parsed is not None:
            return parsed.isoformat()
    raise ManifestError("worker result has no explicit scientific valid time")


def _commit_job_evidence(
    result: Dict[str, Any], payload: Dict[str, Any], saved: Dict[str, Any]
) -> Optional[str]:
    if not result.get("snapshot_id"):
        return None
    from .history.worldline_service import PlotWorldlineService

    context = dict(saved.get("context") or {})
    valid_time = _required_scientific_valid_time(result, context, payload)
    authority = result.get("authority_level")
    if not str(authority or "").strip():
        authority = (
            "PRODUCTION_ASSIMILATED"
            if result.get("production_usable") is True
            else "DIAGNOSTIC_NO_STATE_UPDATE"
        )
    event = PlotWorldlineService().commit_event(
        plot_id=str(payload.get("plot_id", "")),
        event_type="ASMAE_JOB_COMPLETED",
        geometry_hash=str(payload.get("geometry_hash", "") or ""),
        authority=str(authority),
        effective_at=valid_time,
        observation_or_valid_time=valid_time,
        tenant_id=str(context.get("tenant_id") or "default_tenant"),
        namespace=str(context.get("worldline_namespace") or "default"),
        parent_event_ids=[
            str(value) for value in [result.get("worldline_event_id")]
            if value
        ],
        payload={
            "job_id": payload.get("job_id"),
            "manifest_hash": payload.get("manifest_hash"),
            "snapshot_id": result.get("snapshot_id"),
            "snapshot_ref": result.get("snapshot_ref"),
            "asmae_content_hash": result.get("content_hash"),
            "crop_posterior_lineage": result.get(
                "crop_posterior_lineage"
            ),
            "result_status": result.get("status"),
        },
    )
    return event.get("event_id")


def _run_reintegration(
    *,
    result: Dict[str, Any],
    saved: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    from .reintegration import rebuild_canonical_plot_snapshot

    return rebuild_canonical_plot_snapshot(
        asmae_result=result,
        context=saved["context"],
        job_id=str(payload.get("job_id", "")),
        manifest_hash=str(saved.get("manifest_hash", "")),
    )


def run_job(job_path: Path, launch_token: Optional[str] = None) -> None:
    claim = _claim(job_path)
    if claim is None:
        return
    stop_heartbeat = threading.Event()
    lease_lost = threading.Event()
    heartbeat_thread: Optional[threading.Thread] = None
    lease: Optional[WorkerLease] = None
    saved: Dict[str, Any] = {}
    try:
        begun = _begin_lease(job_path, launch_token)
        if begun is None:
            _append_job_event(
                job_path,
                'stale_worker_launch_rejected',
                supplied_launch_token=bool(launch_token),
            )
            return
        payload, lease = begun
        _append_job_event(
            job_path,
            'worker_lease_acquired',
            lease_generation=lease.generation,
            owner=lease.owner,
        )
        manifest_path = _manifest_for_job(job_path, payload)
        saved = load_job_manifest(manifest_path)
        if str(saved.get('manifest_hash', '')) != str(
            payload.get('manifest_hash', '')
        ):
            raise ManifestError('job record and manifest hash do not match')
        identity = dict(saved.get("identity") or {})
        resume_reintegration = payload.get('resume_phase') == 'reintegration'

        def heartbeat() -> None:
            while not stop_heartbeat.wait(LEASE_SECONDS / 3):
                try:
                    _renew_lease(job_path, lease)
                except LeaseLostError:
                    lease_lost.set()
                    stop_heartbeat.set()
                    _append_job_event(
                        job_path,
                        'worker_lease_lost',
                        lease_generation=lease.generation,
                    )
                    return

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

        if resume_reintegration:
            assert_worker_commit_fence(job_path, lease)
            from .snapshot_store import load_latest_snapshot

            result = load_latest_snapshot(
                str(payload.get("plot_id", "")),
                str(identity.get("geometry_hash", "")),
            )
            if not result or result.get("snapshot_id") != payload.get(
                "final_snapshot_id"
            ):
                raise ManifestError(
                    "pending reintegration snapshot is no longer compatible"
                )
        else:
            from .runner import ASMAERunner

            config = dict(saved.get("config") or {})
            config["disable_job_recovery"] = True
            context = dict(saved.get("context") or {})
            context["is_background_run"] = True
            context['_worker_commit_fence'] = lambda: assert_worker_commit_fence(
                job_path, lease
            )
            runner = ASMAERunner(config=config)
            result = runner.execute(
                plot_id=str(payload.get("plot_id", "")),
                run_id=str(payload.get("run_id", "")),
                context=context,
                mode="standard",
            )
            if lease_lost.is_set():
                raise LeaseLostError('worker lease was lost during execution')
            assert_worker_commit_fence(job_path, lease)
            _validate_result(result, payload, identity)

        result_status = str(result.get("status", "error"))
        if result_status in {"success", "partial"}:
            assert_worker_commit_fence(job_path, lease)
            reintegration_required = bool(payload.get('reintegration_required'))
            reintegration_attempt = int(
                payload.get('reintegration_attempts', 0) or 0
            ) + (1 if reintegration_required else 0)
            _fenced_update_job(
                job_path,
                lease,
                stage="downstream_reintegration",
                progress_pct=85,
                result_status=result_status,
                final_snapshot_id=result.get("snapshot_id"),
                asmae_snapshot_ref=result.get("snapshot_ref"),
                resume_phase=(
                    'reintegration' if reintegration_required else 'scientific'
                ),
                reintegration_attempts=reintegration_attempt,
            )
            assert_worker_commit_fence(job_path, lease)
            evidence_event_id = _commit_job_evidence(result, payload, saved)
            _fenced_update_job(
                job_path,
                lease,
                evidence_event_id=evidence_event_id,
            )
            if reintegration_required:
                try:
                    assert_worker_commit_fence(job_path, lease)
                    reintegration = _run_reintegration(
                        result=result, saved=saved, payload=payload
                    )
                except Exception as reintegration_exc:
                    stop_heartbeat.set()
                    if heartbeat_thread:
                        heartbeat_thread.join(timeout=2.0)
                    reintegration_exhausted = (
                        reintegration_attempt >= MAX_EXECUTION_ATTEMPTS
                    )
                    _fenced_update_job(
                        job_path,
                        lease,
                        status='failed' if reintegration_exhausted else 'stalled',
                        stage=(
                            'downstream_reintegration_failed'
                            if reintegration_exhausted
                            else 'downstream_reintegration_retry'
                        ),
                        progress_pct=90,
                        result_status=result_status,
                        final_snapshot_id=result.get("snapshot_id"),
                        asmae_snapshot_ref=result.get("snapshot_ref"),
                        reintegration_error=str(reintegration_exc),
                        retry_classification=(
                            'manual_review'
                            if reintegration_exhausted
                            else 'retryable_reintegration'
                        ),
                        recoverable=not reintegration_exhausted,
                        resume_phase='reintegration',
                        recovery_reason='reintegration_failed',
                        lease_expires_at=None,
                        lease_token=None,
                        lease_owner=None,
                    )
                    _append_job_event(
                        job_path,
                        (
                            'downstream_reintegration_failed'
                            if reintegration_exhausted
                            else 'downstream_reintegration_stalled'
                        ),
                        error=str(reintegration_exc),
                        attempt=reintegration_attempt,
                    )
                    logger.exception(
                        "ASMAE downstream reintegration is pending"
                    )
                    return
            else:
                reintegration = {
                    "status": "not_requested",
                    "snapshot_id": result.get("snapshot_id"),
                    "snapshot_ref": result.get("snapshot_ref"),
                }
            terminal = "completed"
        elif result_status == "unavailable":
            reintegration = {"status": "not_applicable"}
            terminal = 'failed'
        else:
            reintegration = {"status": "not_applicable"}
            terminal = "failed"

        stop_heartbeat.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2.0)
        _fenced_update_job(
            job_path,
            lease,
            status=terminal,
            stage="complete",
            progress_pct=100,
            result_status=result_status,
            cache_key=result.get("cache_key"),
            reason=result.get("reason"),
            failure_diagnostics=result.get("failure_diagnostics"),
            final_snapshot_id=reintegration.get("snapshot_id")
            or result.get("snapshot_id"),
            final_snapshot_ref=reintegration.get("snapshot_ref")
            or result.get("snapshot_ref"),
            reintegration_status=reintegration.get("status"),
            reintegration_error=None,
            reintegration_worldline_event_id=reintegration.get(
                "worldline_event_id"
            ),
            downstream_layer_run_ids=reintegration.get("layer_run_ids", {}),
            compatibility="current",
            retry_classification=(
                "none" if terminal == "completed" else "manual_review"
            ),
            lease_expires_at=None,
            lease_token=None,
            lease_owner=None,
            recoverable=False,
        )
        _append_job_event(
            job_path,
            'worker_finished',
            status=terminal,
            result_status=result_status,
        )
        logger.info(
            "Standard ASMAE job %s finished with %s",
            payload.get("job_id"),
            terminal,
        )
    except LeaseLostError as exc:
        stop_heartbeat.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2.0)
        _append_job_event(
            job_path,
            'stale_worker_commit_rejected',
            error=str(exc),
            lease_generation=lease.generation if lease else None,
        )
        logger.warning('Stale ASMAE worker commit rejected: %s', exc)
    except ManifestError as exc:
        stop_heartbeat.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2.0)
        if lease is not None:
            _fenced_update_job(
                job_path,
                lease,
                status='failed',
                stage='contract_validation_failed',
                error=str(exc),
                retry_classification='permanent_contract',
                lease_expires_at=None,
                lease_token=None,
                lease_owner=None,
                recoverable=False,
            )
        _append_job_event(
            job_path,
            'worker_contract_rejected',
            error=str(exc),
            error_type=type(exc).__name__,
        )
        logger.error("ASMAE job contract rejected: %s", exc)
    except Exception as exc:
        stop_heartbeat.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2.0)
        current = _read_json(job_path)
        attempts = int(current.get("attempts", 0) or 0)
        classification = (
            "retryable_execution"
            if attempts < MAX_EXECUTION_ATTEMPTS
            else "manual_review"
        )
        try:
            if lease is None:
                raise LeaseLostError('worker failed before acquiring a lease')
            _fenced_update_job(
                job_path,
                lease,
                status='failed',
                stage='execution_failed',
                error=str(exc),
                error_type=type(exc).__name__,
                retry_classification=classification,
                lease_expires_at=None,
                lease_token=None,
                lease_owner=None,
                recoverable=classification == 'retryable_execution',
            )
        except LeaseLostError:
            _append_job_event(
                job_path,
                'stale_worker_failure_commit_rejected',
                original_error=str(exc),
            )
            return
        _append_job_event(
            job_path,
            'worker_execution_failed',
            error=str(exc),
            error_type=type(exc).__name__,
            traceback=traceback.format_exc(),
            retry_classification=classification,
        )
        try:
            from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService, WorldlineEventProposal
            svc = CanonicalWorldlineService()
            failure_effective_at = _now().isoformat()
            failure_context = dict(saved.get("context") or {})
            failure_valid_time = _required_scientific_valid_time(
                {}, failure_context, current
            )
            proposal = WorldlineEventProposal(
                event_type="ASMAE_SPATIAL_REFRESH_FAILED",
                payload={
                    "job_id": current.get("job_id"),
                    "manifest_hash": current.get("manifest_hash"),
                    "failure_class": "WORKER_EXECUTION_FAILURE",
                    "error": str(exc),
                    "retryable": classification == "retryable_execution",
                },
                geometry_version=str(current.get("geometry_hash") or "g1"),
                evidence_set_hash=str(current.get("context_hash") or "e1"),
                model_version="asmae_v0.5.0",
                authority_ref="DIAGNOSTIC_NO_STATE_UPDATE",
                observation_or_valid_time=failure_valid_time,
            )
            svc.commit_proposal(
                plot_id=current.get("plot_id", "default_plot"),
                proposal=proposal,
                effective_at=failure_effective_at,
                tenant_id=str(failure_context.get("tenant_id") or "default_tenant"),
                namespace=str(failure_context.get("worldline_namespace") or "default"),
            )
        except Exception as event_exc:
            logger.warning("Could not record ASMAE_SPATIAL_REFRESH_FAILED event: %s", event_exc)
        logger.exception("Standard ASMAE job failed: %s", job_path)
    finally:
        stop_heartbeat.set()
        _release_claim(claim)


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    if not _JOB_ID.fullmatch(str(job_id)):
        return None
    job_path, _ = _paths(str(job_id))
    payload = _read_json(job_path)
    if not payload:
        return None
    payload = _mark_stalled_if_expired(job_path, payload)
    return _public_job_payload(payload)


def latest_job_for_plot(
    plot_id: str, run_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if not JOBS_DIR.exists():
        return None
    matches = []
    for job_path in JOBS_DIR.glob("*.job.json"):
        payload = _read_json(job_path)
        if (
            str(payload.get("plot_id", "")) == str(plot_id)
            and (
                run_id is None
                or str(payload.get("run_id", "")) == str(run_id)
            )
        ):
            payload = _mark_stalled_if_expired(job_path, payload)
            matches.append(_public_job_payload(payload))
    if not matches:
        return None
    if run_id is None:
        unsuperseded = [
            value for value in matches if not value.get("superseded")
        ]
        if unsuperseded:
            matches = unsuperseded
    return max(
        matches,
        key=lambda value: (
            _job_created_at(value),
            str(value.get("job_id", "")),
        ),
    )


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(
            "usage: python -m layer05_asmae.background_jobs "
            "<job.json> [launch-token]"
        )
    run_job(
        Path(sys.argv[1]).resolve(),
        launch_token=sys.argv[2] if len(sys.argv) == 3 else None,
    )
