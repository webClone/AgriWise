"""Durable external-worker queue for standard ASMAE computations."""

from __future__ import annotations

import hashlib
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
from typing import Any, Dict, FrozenSet, Optional, Tuple, Union

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
from .evidence_capability import CapabilityPlanIdentityError
from .code_lineage import operational_build_receipt, scientific_source_digest
from services.agribrain.common.plot_namespace import (
    PlotNamespace,
    _coerce_namespace,
    namespace_payload,
)

logger = logging.getLogger(__name__)

AGRIBRAIN_ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = AGRIBRAIN_ROOT / "artifacts" / "asmae_jobs"
JOBS_DIR = Path(os.environ.get('ASMAE_JOBS_DIR', str(JOBS_DIR))).resolve()
LEASE_SECONDS = int(os.environ.get("ASMAE_LEASE_SECONDS", "600"))
LAUNCH_COOLDOWN_SECONDS = 15
RESERVATION_STALE_SECONDS = 30
MAX_EXECUTION_ATTEMPTS = 3
PROCESS_HARD_TIMEOUT_SECONDS = float(
    os.environ.get("ASMAE_PROCESS_HARD_TIMEOUT_SECONDS", "1800")
)
MAX_WORKER_MEMORY_MB = float(
    os.environ.get("AGRIBRAIN_MAX_WORKER_MEMORY_MB", "8192")
)


def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is currently alive."""
    if pid <= 0:
        return False
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            try:
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    STILL_ACTIVE = 259
                    return exit_code.value == STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def _get_process_rss_mb(pid: int) -> float:
    """Get resident memory in MB for the given process PID."""
    if pid <= 0:
        return 0.0
    try:
        import psutil
        proc = psutil.Process(pid)
        return float(proc.memory_info().rss) / (1024.0 * 1024.0)
    except Exception:
        pass
    if os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD),
                    ('PageFaultCount', wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if handle:
                try:
                    counters = PROCESS_MEMORY_COUNTERS()
                    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                    if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                        return float(counters.WorkingSetSize) / (1024.0 * 1024.0)
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
    return 0.0


class BoundedJobExecutor:
    """Enforces global concurrency bounding, FIFO queuing, and single-leader recovery."""

    def __init__(self, max_workers: Optional[int] = None):
        self._configured_max = max_workers

    @property
    def max_workers(self) -> int:
        if self._configured_max is not None:
            return self._configured_max
        try:
            return max(1, int(os.environ.get("AGRIBRAIN_MAX_WORKERS", "4")))
        except (ValueError, TypeError):
            return 4

    def get_active_worker_pids(self) -> List[int]:
        """Scan active job records and return PIDs of running live supervisors/workers."""
        if not JOBS_DIR.exists():
            return []
        active_pids = []
        for job_path in JOBS_DIR.glob("*.job.json"):
            try:
                payload = _read_json(job_path)
                if not payload:
                    continue
                status = payload.get("status")
                if status in ("running", "reserving") and not _lease_expired(payload):
                    pid = payload.get("supervisor_pid") or payload.get("worker_pid")
                    if pid and is_pid_alive(int(pid)):
                        active_pids.append(int(pid))
            except Exception:
                pass
        return list(set(active_pids))

    def get_active_worker_count(self) -> int:
        return len(self.get_active_worker_pids())

    def can_spawn(self) -> bool:
        return self.get_active_worker_count() < self.max_workers

    def get_queued_jobs(self) -> List[Path]:
        """Return all queued jobs sorted in FIFO order by creation timestamp."""
        if not JOBS_DIR.exists():
            return []
        queued = []
        for job_path in JOBS_DIR.glob("*.job.json"):
            try:
                payload = _read_json(job_path)
                if not payload:
                    continue
                if payload.get("status") == "queued" and not payload.get("superseded") and payload.get("manifest_hash"):
                    queued.append((_job_created_at(payload), job_path))
            except Exception:
                pass
        queued.sort(key=lambda item: item[0])
        return [item[1] for item in queued]

    def process_next_queued_job(self) -> Optional[Path]:
        """If worker slot available, dequeue and spawn oldest queued job."""
        if not self.can_spawn():
            return None
        queued = self.get_queued_jobs()
        for job_path in queued:
            if spawn_worker(job_path):
                return job_path
        return None

    def on_worker_completed(self, job_path: Optional[Path] = None) -> None:
        """Called when a worker process terminates to drain the queue."""
        self.process_next_queued_job()

    def drain_queue(self) -> int:
        """Spawn queued jobs up to available capacity."""
        spawned = 0
        while self.can_spawn():
            job = self.process_next_queued_job()
            if not job:
                break
            spawned += 1
        return spawned


bounded_executor = BoundedJobExecutor()

PROCESS_TERMINATE_GRACE_SECONDS = float(
    os.environ.get("ASMAE_PROCESS_TERMINATE_GRACE_SECONDS", "5")
)
_UNSET = object()
_ENQUEUE_THREAD_LOCK = threading.RLock()

QUEUED_STATUSES: FrozenSet[str] = frozenset(
    {'queued', 'stalled', 'completed_reintegration_pending'}
)
TERMINAL_STATUSES: FrozenSet[str] = frozenset(
    {'failed', 'completed', 'superseded', 'cancelled'}
)
_JOB_ID = re.compile(r"^(?:[0-9a-f]{24}|job_[a-zA-Z0-9_-]{8,32})$")


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
    raw_manifest_ref = payload.get("manifest_ref")
    if not raw_manifest_ref or str(raw_manifest_ref).strip() in ("", "None"):
        return expected_manifest
    supplied = Path(str(raw_manifest_ref))
    if not supplied.is_absolute():
        supplied = JOBS_DIR / supplied
    if supplied.resolve() != expected_manifest.resolve():
        raise ManifestError("job manifest path does not match its identity")
    return expected_manifest


def _requires_reintegration(context: Dict[str, Any]) -> bool:
    from .reintegration import REINTEGRATION_CONTRACT_VERSION

    value = context.get("orchestrator_reintegration")
    return bool(
        isinstance(value, dict)
        and value.get("contract_version")
        == REINTEGRATION_CONTRACT_VERSION
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


def classify_execution_failure(exc: BaseException, attempts: int) -> Tuple[str, str]:
    """Return retry class and stage without retrying deterministic contracts."""
    deterministic_contract_failure = isinstance(exc, CapabilityPlanIdentityError) or (
        "CAPABILITY_PLAN_IDENTITY_MISMATCH" in str(exc)
    )
    if deterministic_contract_failure:
        return "permanent_contract", "contract_validation_failed"
    if attempts < MAX_EXECUTION_ATTEMPTS:
        return "retryable_execution", "execution_failed"
    return "manual_review", "execution_failed"


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
    if retry_class == "permanent_contract" and old_capability_version != new_contract_version:
        return "enqueue_successor_contract_changed"
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
    namespace: PlotNamespace,
    run_id: str,
    context: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Write and spawn a new job that supersedes a failed predecessor."""
    namespace = _coerce_namespace(namespace)
    plot_id = namespace.plot_id
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

    context.update(namespace_payload(namespace))
    context["plot_namespace"] = namespace_payload(namespace)
    identity = build_job_identity(namespace, context, config)
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
        namespace=namespace,
        run_id=run_id,
        context=context,
        config=config,
        identity=identity,
    )
    _atomic_json(
        job_path,
        {
            "job_id": job_id,
            "plot_namespace": namespace_payload(namespace),
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": plot_id,
            "run_id": run_id,
            "mode": "standard",
            "status": "queued",
            "stage": "manifest_persisted",
            "progress_pct": 5,
            "attempts": 0,
            "manifest_ref": manifest_path.name,
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
        "manifest_ref": manifest_path.name,
        "deduplicated": False,
        "compatibility": "current",
        "progress_pct": 5,
        "supersedes_job_id": predecessor_job_id,
        "final_snapshot_id": None,
    }


# ── Compatible-job lookup ────────────────────────────────────────────────────

def latest_compatible_job(
    namespace: PlotNamespace,
    geometry_hash: Optional[str] = None,
    capability_plan_hash: Optional[str] = None,
    worker_contract_version: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the most recent job whose identity matches the current capability
    contract, geometry, and worker version. Returns None when no match exists."""
    namespace = _coerce_namespace(namespace)
    if not JOBS_DIR.exists():
        return None
    matches = []
    for job_path in JOBS_DIR.glob("*.job.json"):
        payload = _read_json(job_path)
        try:
            payload_namespace = _coerce_namespace(payload.get("plot_namespace"))
        except ValueError:
            continue
        if payload_namespace != namespace:
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
    namespace: PlotNamespace,
    run_id: str,
    context: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Serialize same-process publication before the cross-process fence.

    Windows can transiently return EACCES rather than EEXIST when two request
    threads race an O_EXCL create.  A process-local reentrant lock removes that
    ambiguity; the durable reservation below remains the authority fence
    between separate API processes.
    """
    with _ENQUEUE_THREAD_LOCK:
        return _enqueue_standard_job_locked(namespace, run_id, context, config)


def _enqueue_standard_job_locked(
    namespace: PlotNamespace,
    run_id: str,
    context: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist a namespaced, validated manifest before exposing a job."""
    namespace = _coerce_namespace(namespace)
    plot_id = namespace.plot_id
    context = dict(context or {})
    for key, expected in (
        ("tenant_id", namespace.tenant_id),
        ("farm_id", namespace.farm_id),
        ("plot_id", namespace.plot_id),
    ):
        current = str(context.get(key) or "").strip()
        if current and current != expected:
            raise ValueError(f"durable job namespace mismatch for {key}")
    if context.get("plot_namespace"):
        if _coerce_namespace(context["plot_namespace"]) != namespace:
            raise ValueError("durable job context PlotNamespace mismatch")
    context.update(namespace_payload(namespace))
    context["plot_namespace"] = namespace_payload(namespace)
    spatial_summary = dict(
        (context.get("capability_plan_summary") or {}).get(
            "spatial_scene_capability"
        ) or {}
    )
    if spatial_summary and int(spatial_summary.get("accepted_count", 0) or 0) <= 0:
        return {
            "job_id": None,
            "plot_id": str(plot_id),
            "run_id": str(run_id),
            "status": "not_eligible",
            "stage": "spatial_eligibility_preflight",
            "terminal": True,
            "reason": "NOT_ELIGIBLE_NO_EXECUTABLE_SPATIAL_SCENE",
            "failure_code": "NOT_ELIGIBLE_NO_EXECUTABLE_SPATIAL_SCENE",
            "retry_classification": "acquisition_required",
            "retry_eligible": False,
            "acquisition_required": True,
            "temporal_diagnostic_available": bool(
                ((context.get("capability_plan_summary") or {}).get(
                    "temporal_capability", {}
                ) or {}).get("accepted_count", 0)
                or ((context.get("capability_plan_summary") or {}).get(
                    "composite_raster_capability", {}
                ) or {}).get("accepted_count", 0)
            ),
            "capability_plan_hash": context.get("capability_plan_hash"),
            "execution_plan_hash": context.get("execution_plan_hash"),
            "quarantine_ledger_hash": context.get("quarantine_ledger_hash"),
            "accepted_spatial_scene_count": 0,
            "deduplicated": False,
        }
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    identity = build_job_identity(namespace, context, config)
    job_id = scientific_job_id(identity)
    request_lineage_id = str(run_id)
    execution_run_id = f"ASMAE-RUN-{job_id}"
    job_path, manifest_path = _paths(job_id)
    existing = _read_json(job_path)
    owns_reservation = False

    # Reserve a previously unseen scientific identity with O_EXCL. Other API
    # processes wait for the owner to publish the manifest/job record instead
    # of concurrently overwriting it.
    if not existing and not job_path.exists():
        reservation = {
            "job_id": job_id,
            "plot_namespace": namespace_payload(namespace),
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": plot_id,
            "run_id": execution_run_id,
            "request_lineage_id": request_lineage_id,
            "status": "reserving",
            "stage": "identity_reserved",
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "scientific_identity": identity,
            "manifest_ref": manifest_path.name,
            "revision": 0,
        }
        try:
            with job_path.open("x", encoding="utf-8") as handle:
                json.dump(reservation, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            existing = reservation
            owns_reservation = True
        except OSError:
            # Windows may report EACCES/WinError 5 instead of EEXIST when
            # another thread/process has just created and is still flushing
            # the O_EXCL reservation.  It is contention only when the target
            # now exists; genuine filesystem failures must still surface.
            if not job_path.exists():
                raise
            for _ in range(200):
                time.sleep(0.025)
                existing = _read_json(job_path)
                if existing and existing.get("status") != "reserving":
                    return enqueue_standard_job(namespace, run_id, context, config)
            return {
                "job_id": job_id,
                "run_id": execution_run_id,
                "request_lineage_id": request_lineage_id,
                "status": "queued",
                "stage": "identity_reserved",
                "job_ref": str(job_path),
                "manifest_ref": manifest_path.name,
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
                "run_id": execution_run_id,
                "request_lineage_id": request_lineage_id,
                "status": "queued",
                "stage": "identity_reserved",
                "job_ref": str(job_path),
                "manifest_ref": manifest_path.name,
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
                return enqueue_standard_job(namespace, run_id, context, config)
        return {
            "job_id": job_id,
            "run_id": execution_run_id,
            "request_lineage_id": request_lineage_id,
            "status": "queued",
            "stage": "identity_reserved",
            "job_ref": str(job_path),
            "manifest_ref": manifest_path.name,
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
                "run_id": existing.get("run_id") or execution_run_id,
                "request_lineage_id": existing.get("request_lineage_id") or request_lineage_id,
                "status": _canonical_status(existing.get('status')),
                "job_ref": str(job_path),
                "manifest_ref": manifest_path.name,
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
            'manifest_ref': manifest_path.name,
            'deduplicated': True,
        }

    if existing.get("status") == "completed":
        compatible, reason = _completed_compatible(
            existing, manifest_path, identity
        )
        if compatible:
            return {
                "job_id": job_id,
                "run_id": existing.get("run_id") or execution_run_id,
                "request_lineage_id": existing.get("request_lineage_id") or request_lineage_id,
                "status": "completed",
                "job_ref": str(job_path),
                "manifest_ref": manifest_path.name,
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
            'manifest_ref': manifest_path.name,
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
                "manifest_ref": manifest_path.name,
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
                "manifest_ref": manifest_path.name,
                "deduplicated": True,
                "superseded": False,
                "progress_pct": int(existing.get("progress_pct", 100)),
                "updated_at": existing.get("updated_at", ""),
            }
        if decision == "enqueue_successor_contract_changed":
            return _enqueue_successor(
                existing, namespace, run_id, context, config
            )
        # retry_transient — fall through to normal write below

    if _canonical_status(existing.get('status')) == 'superseded':
        return {
            **_public_job_payload(existing),
            'job_ref': str(job_path),
            'manifest_ref': manifest_path.name,
            'deduplicated': True,
        }

    try:
        manifest = write_job_manifest(
            manifest_path,
            job_id=job_id,
            plot_id=plot_id,
            namespace=namespace,
            run_id=execution_run_id,
            context=context,
            config=config,
            identity=identity,
        )
        attempts = int(existing.get("attempts", 0) or 0)
        _update_job(
            job_path,
            mode="standard",
            status="queued",
            stage="manifest_persisted",
            progress_pct=5,
            attempts=attempts,
            manifest_ref=manifest_path.name,
            manifest_hash=manifest.get("manifest_hash"),
            manifest_contract_version=JOB_MANIFEST_CONTRACT_VERSION,
            worker_contract_version=JOB_RUNNER_CONTRACT_VERSION,
            scientific_identity=identity,
            context_hash=identity.get("context_hash"),
            geometry_hash=identity.get("geometry_hash"),
            crop_posterior_lineage=identity.get(
                "crop_posterior_lineage"
            ),
            crop_lineage_id=identity.get("crop_lineage_id"),
            reintegration_required=_requires_reintegration(context),
            restart_recoverable=True,
            compatibility="current",
            evidence_capability_contract_version=EVIDENCE_CAPABILITY_CONTRACT_VERSION,
            capability_plan_hash=identity.get("capability_plan_hash"),
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
        "run_id": execution_run_id,
        "request_lineage_id": request_lineage_id,
        "status": "queued",
        "job_ref": str(job_path),
        "manifest_ref": manifest_path.name,
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
        'completed_reintegration_pending': 'queued',
        'failed_to_launch': 'failed',
        'degraded': 'failed',
        'error': 'failed',
        'obsolete': 'superseded',
        'canceled': 'cancelled',
    }.get(raw, raw)


def _public_job_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    public = dict(payload)
    raw_st = str(public.get('status') or 'queued')
    public['status'] = 'queued' if raw_st == 'reserving' else _canonical_status(raw_st)
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
        raw_status = str(payload.get('status') or '')
        if raw_status == 'reserving' or not payload.get('manifest_hash'):
            return None
        status = _canonical_status(raw_status)
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
        launch_generation = int(payload.get('launch_attempts', 0) or 0) + 1
        identity = dict(payload.get('scientific_identity') or {})
        phase = 'reintegration' if payload.get('resume_phase') == 'reintegration' else 'scientific'
        identity_source_digest = str(identity.get('scientific_source_digest', ''))
        current_source_digest = scientific_source_digest()
        receipt = operational_build_receipt(
            source_bundle_digest=current_source_digest,
            config_hash=str(identity.get('config_hash', '')),
            manifest_hash=str(payload.get('manifest_hash', '')),
            phase=phase,
            launch_generation=launch_generation,
            input_snapshot_id=str(payload.get('final_snapshot_id', '') or ''),
        )
        receipt['scientific_identity_source_digest'] = identity_source_digest
        receipt['source_matches_scientific_identity'] = (
            not identity_source_digest or current_source_digest == identity_source_digest
        )
        operational_attempts = list(payload.get('operational_attempts') or [])
        operational_attempts.append(receipt)
        if phase == 'scientific' and identity_source_digest and current_source_digest != identity_source_digest:
            receipt['launch_permitted'] = False
            receipt['block_reason'] = 'scientific_source_changed_before_launch'
            payload.update(
                status='superseded',
                stage='source_bundle_changed_before_launch',
                compatibility='obsolete',
                compatibility_reason='scientific_source_digest_mismatch',
                retry_classification='new_scientific_identity_required',
                recoverable=False,
                operational_attempts=operational_attempts,
                active_operational_attempt_id=receipt['operational_attempt_id'],
                source_build_digest=current_source_digest,
            )
            payload['revision'] = int(payload.get('revision', 0) or 0) + 1
            payload['updated_at'] = _now().isoformat()
            _atomic_json(job_path, payload)
            return None
        receipt['launch_permitted'] = True
        stdout_path, event_path = _job_log_paths(job_path)
        payload.update(
            launch_token=launch_token,
            launch_reserved_at=_now().isoformat(),
            launch_state='reserved',
            launch_attempts=launch_generation,
            operational_attempts=operational_attempts,
            active_operational_attempt_id=receipt['operational_attempt_id'],
            source_build_digest=receipt['source_bundle_digest'],
            worker_executable_sha256=receipt['worker_executable_sha256'],
            worker_log_ref=stdout_path.name,
            worker_event_log_ref=event_path.name,
            recoverable=True,
        )
        payload['revision'] = int(payload.get('revision', 0) or 0) + 1
        payload['updated_at'] = _now().isoformat()
        _atomic_json(job_path, payload)
        return launch_token


def spawn_worker(job_path: Path) -> bool:
    """Launch a detached worker once for the current durable launch token."""
    if not bounded_executor.can_spawn():
        logger.info(
            "Worker pool concurrency cap reached (%d active); job queued: %s",
            bounded_executor.get_active_worker_count(), job_path.name
        )
        return False
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
    if os.name == "nt":
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
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
                    '--supervise',
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
            supervisor_pid=process.pid,
            launch_state='started',
            launched_at=_now().isoformat(),
        )
        _append_job_event(job_path, 'worker_process_started', pid=process.pid)
        return True
    except Exception as exc:
        try:
            _update_job(
                job_path,
                expected_launch_token=launch_token,
                status='failed',
                stage='launch_failed',
                error=str(exc),
                retry_classification='retryable_launch',
                recoverable=True,
                launch_state='failed',
                lease_expires_at=None,
                lease_token=None,
                lease_owner=None,
            )
        except Exception:
            pass
        _append_job_event(
            job_path,
            'worker_launch_failed',
            error=str(exc),
            error_type=type(exc).__name__,
        )
        lock_path = job_path.with_suffix(".lock")
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass
        bounded_executor.on_worker_completed(job_path)
        return False


def _lease_expired(payload: Dict[str, Any]) -> bool:
    expires_at = _parse_timestamp(payload.get('lease_expires_at'))
    if expires_at is None:
        return True
    if expires_at <= _now():
        worker_pid = payload.get('worker_pid')
        if worker_pid and is_pid_alive(int(worker_pid)):
            return False
        return True
    return False


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
        from services.agribrain.world_model.canonical_worldline import (
            CanonicalWorldlineService,
        )

        event_time = _now().isoformat()
        event = CanonicalWorldlineService().commit_event(
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
    if candidate.get('status') not in ('running', 'completed_reintegration_pending') or not _lease_expired(candidate):
        return candidate
    changed = False
    with _record_lock(job_path):
        current = _read_json(job_path)
        if current.get('status') in ('running', 'completed_reintegration_pending') and _lease_expired(current):
            was_reintegration = (current.get('status') == 'completed_reintegration_pending')
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
                resume_phase='reintegration' if was_reintegration else current.get('resume_phase', 'scientific'),
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
            pass
    return superseded or current


# Task A07/P01.3 compatibility alias
_supersede_and_requeue_job = _supersede_recovery_candidate


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
            worker_pid=os.getpid(),
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
    if status not in {"success", "partial", "unavailable", "error", "failed_spatial_timeout"}:
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
    # P0-D: Capability-plan-hash identity validation
    import os
    allow_drift = os.environ.get("ASMAE_ALLOW_PLAN_HASH_DRIFT") == "true"
    result_plan_hash = str(result.get("capability_plan_hash", "") or "")
    job_plan_hash = str(identity.get("capability_plan_hash", "") or "")
    if result_plan_hash and job_plan_hash and result_plan_hash != job_plan_hash:
        msg = (
            f"CAPABILITY_PLAN_IDENTITY_MISMATCH: "
            f"frozen={job_plan_hash}, executed={result_plan_hash}"
        )
        if allow_drift:
            logger.warning("Plan hash drift (migration mode): %s", msg)
        else:
            raise ManifestError(msg)


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
    from services.agribrain.world_model.canonical_worldline import (
        CanonicalWorldlineService,
    )

    context = dict(saved.get("context") or {})
    valid_time = _required_scientific_valid_time(result, context, payload)
    authority = (
        str(result.get("authority_level") or "PRODUCTION_ASSIMILATED")
        if result.get("production_usable") is True
        else "DIAGNOSTIC_NO_STATE_UPDATE"
    )
    event_type = _completed_result_event_type(result)
    event = CanonicalWorldlineService().commit_event(
        plot_id=str(payload.get("plot_id", "")),
        event_type=event_type,
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
            "execution_status": "completed",
            "spatial_available": event_type != "ASMAE_TEMPORAL_DIAGNOSTIC_COMPLETED",
            "production_usable": result.get("production_usable") is True,
        },
    )
    return event.get("event_id")


def _completed_result_event_type(result: Dict[str, Any]) -> str:
    """Classify a successful execution without conflating authority with failure."""
    evidence = result.get("asmae_evidence_state")
    if not isinstance(evidence, dict):
        evidence = {}
    plot_state = result.get("plot_state_artifact")
    if not isinstance(plot_state, dict):
        plot_state = {}
    spatial = bool(
        result.get("current_spatial_assimilation")
        or result.get("spatial_raster_available")
        or evidence.get("current_spatial_assimilation")
        or evidence.get("spatial_raster_available")
        or plot_state.get("spatial_raster_available")
    )
    if not spatial:
        try:
            spatial = int(result.get("scene_count") or evidence.get("scene_count") or 0) > 0
        except (TypeError, ValueError):
            spatial = False
    if spatial and result.get("production_usable") is True:
        return "ASMAE_SPATIAL_PRODUCTION_COMPLETED"
    if spatial:
        return "ASMAE_SPATIAL_DIAGNOSTIC_COMPLETED"
    return "ASMAE_TEMPORAL_DIAGNOSTIC_COMPLETED"


def _commit_job_failure_event(
    result: Dict[str, Any], payload: Dict[str, Any], saved: Dict[str, Any]
) -> Tuple[str, Optional[str]]:
    try:
        from services.agribrain.world_model.canonical_worldline import (
            CanonicalWorldlineService,
        )
        context = dict(saved.get("context") or {})
        valid_time = datetime.now(timezone.utc).isoformat()
        job_id = str(payload.get("job_id", ""))
        run_id = str(payload.get("run_id") or context.get("run_id") or "")
        reason = str(result.get("reason") or "execution_failed")
        idempotency_key = (
            f"{job_id}:{run_id}:"
            f"{hashlib.sha256(reason.encode('utf-8')).hexdigest()[:16]}"
        )
        event = CanonicalWorldlineService().commit_event(
            plot_id=str(payload.get("plot_id", "")),
            event_type="ASMAE_SPATIAL_REFRESH_FAILED",
            geometry_hash=str(payload.get("geometry_hash", "") or context.get("geometry_hash") or "f750290c"),
            authority="FAIL_CLOSED",
            effective_at=valid_time,
            observation_or_valid_time=valid_time,
            tenant_id=str(context.get("tenant_id") or "default_tenant"),
            namespace=str(context.get("worldline_namespace") or "default"),
            payload={
                "job_id": job_id,
                "run_id": run_id,
                "manifest_hash": payload.get("manifest_hash"),
                "result_status": result.get("status") or "error",
                "execution_status": "failed",
                "reason": reason,
                "failure_diagnostics": result.get("failure_diagnostics") or {},
                "idempotency_key": idempotency_key,
            },
        )
        return "committed", event.get("event_id")
    except Exception as exc:
        logger.warning("Could not commit ASMAE_SPATIAL_REFRESH_FAILED to worldline: %s", exc)
        return "lineage_commit_failed", None


def _finalize_supervised_timeout(
    job_path: Path, launch_token: str, elapsed_seconds: float
) -> None:
    """Publish typed timeout truth after the supervised child is confirmed dead."""
    primary_reason = "PROCESS_HARD_TIMEOUT"
    current = _read_json(job_path)
    if not current or str(current.get("status")) in TERMINAL_STATUSES:
        return
    diagnostics = {
        "failure_code": primary_reason,
        "elapsed_ms": round(elapsed_seconds * 1000.0, 3),
        "deadline_ms": round(PROCESS_HARD_TIMEOUT_SECONDS * 1000.0, 3),
        "supervision_contract": "asmae_process_watchdog_v1",
        "cooperative_cancellation": True,
        "terminate_attempted": True,
    }
    try:
        terminal = _update_job(
            job_path,
            expected_launch_token=launch_token,
            expected_statuses=frozenset({"queued", "stalled", "running"}),
            status="failed",
            stage="process_hard_timeout",
            progress_pct=100,
            result_status="failed_spatial_timeout",
            reason=primary_reason,
            error=(
                "ASMAE worker exceeded process hard timeout "
                f"({PROCESS_HARD_TIMEOUT_SECONDS:.1f}s)"
            ),
            error_type="ProcessHardTimeout",
            failure_diagnostics=diagnostics,
            retry_classification="manual_review",
            recoverable=False,
            lease_expires_at=None,
            lease_token=None,
            lease_owner=None,
        )
    except LeaseLostError:
        return
    _append_job_event(
        job_path, "worker_process_hard_timeout", status="failed", **diagnostics
    )
    result = {
        "status": "failed_spatial_timeout",
        "reason": primary_reason,
        "failure_diagnostics": diagnostics,
    }
    try:
        saved = load_job_manifest(_manifest_for_job(job_path, terminal))
    except Exception as exc:
        logger.warning("Could not load manifest for timeout lineage: %s", exc)
        saved = {}
    _commit_job_failure_event(result, terminal, saved)


def _finalize_supervised_process_exit(
    job_path: Path,
    launch_token: str,
    *,
    exit_code: int,
    elapsed_seconds: float,
) -> None:
    """Publish typed failure truth when the supervised worker exits unexpectedly."""
    primary_reason = "UNEXPECTED_PROCESS_EXIT"
    current = _read_json(job_path)
    if not current or str(current.get("status")) in TERMINAL_STATUSES:
        return
    diagnostics = {
        "failure_code": primary_reason,
        "exit_code": exit_code,
        "elapsed_ms": round(elapsed_seconds * 1000.0, 3),
        "supervision_contract": "asmae_process_watchdog_v1",
        "cooperative_cancellation": False,
        "terminate_attempted": False,
    }
    try:
        terminal = _update_job(
            job_path,
            expected_launch_token=launch_token,
            expected_statuses=frozenset({"queued", "stalled", "running"}),
            status="failed",
            stage="worker_process_crashed",
            progress_pct=100,
            result_status="failed_process_exit",
            reason=primary_reason,
            error=f"Worker process exited unexpectedly with code {exit_code}",
            error_type="UnexpectedProcessExit",
            failure_diagnostics=diagnostics,
            retry_classification="manual_review",
            recoverable=False,
            lease_expires_at=None,
            lease_token=None,
            lease_owner=None,
        )
    except LeaseLostError:
        return
    _append_job_event(
        job_path, "worker_process_crashed", status="failed", **diagnostics
    )
    result = {
        "status": "failed_process_exit",
        "reason": primary_reason,
        "failure_diagnostics": diagnostics,
    }
    try:
        saved = load_job_manifest(_manifest_for_job(job_path, terminal))
    except Exception as exc:
        logger.warning("Could not load manifest for process crash lineage: %s", exc)
        saved = {}
    _commit_job_failure_event(result, terminal, saved)


def supervise_job(job_path: Path, launch_token: str) -> None:
    """Own a monotonic deadline and kill a non-cooperative scientific child."""
    environment = dict(os.environ)
    environment["ASMAE_SUPERVISED_CHILD"] = "1"
    current_pythonpath = environment.get("PYTHONPATH", "")
    new_paths = [str(REPO_ROOT), str(AGRIBRAIN_ROOT)]
    if current_pythonpath:
        new_paths.append(current_pythonpath)
    environment["PYTHONPATH"] = os.pathsep.join(new_paths)
    environment["ASMAE_JOBS_DIR"] = str(JOBS_DIR)
    started = time.monotonic()
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "services.agribrain.layer05_asmae.background_jobs",
            "--execute",
            str(job_path),
            str(launch_token),
        ],
        cwd=str(REPO_ROOT),
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=None,
        stderr=None,
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        start_new_session=(os.name != "nt"),
    )
    try:
        _update_job(
            job_path,
            expected_launch_token=launch_token,
            supervisor_pid=os.getpid(),
            worker_pid=child.pid,
            watchdog_timeout_seconds=PROCESS_HARD_TIMEOUT_SECONDS,
            watchdog_contract="asmae_process_watchdog_v1",
        )
    except Exception:
        child.terminate()
        try:
            child.wait(timeout=max(1.0, PROCESS_TERMINATE_GRACE_SECONDS))
        except Exception:
            child.kill()
        lock_path = job_path.with_suffix(".lock")
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass
        bounded_executor.on_worker_completed(job_path)
        raise
    memory_exceeded = False
    peak_rss_mb = 0.0

    def _monitor_memory():
        nonlocal memory_exceeded, peak_rss_mb
        poll_int = 0.5
        deadline = started + PROCESS_HARD_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if hasattr(child, "poll"):
                try:
                    if child.poll() is not None:
                        break
                except Exception:
                    break
            rss = _get_process_rss_mb(getattr(child, "pid", 0))
            if rss > peak_rss_mb:
                peak_rss_mb = rss
            if rss > MAX_WORKER_MEMORY_MB:
                memory_exceeded = True
                try:
                    child.terminate()
                except Exception:
                    pass
                break
            time.sleep(poll_int)

    monitor_thread = threading.Thread(target=_monitor_memory, daemon=True)
    monitor_thread.start()

    timed_out = False
    try:
        try:
            child.wait(timeout=PROCESS_HARD_TIMEOUT_SECONDS)
            if not memory_exceeded and getattr(child, "returncode", 0) == 0:
                return
        except subprocess.TimeoutExpired:
            timed_out = True
            child.terminate()
        try:
            child.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=max(1.0, PROCESS_TERMINATE_GRACE_SECONDS))

        lock_path = job_path.with_suffix(".lock")
        try:
            lock_value = _read_json(lock_path)
            if int(lock_value.get("pid") or -1) == child.pid:
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass

        exit_code = getattr(child, "returncode", None)
        if exit_code is None:
            try:
                exit_code = child.poll()
            except Exception:
                exit_code = -1

        elapsed = time.monotonic() - started

        if memory_exceeded:
            diagnostics = {
                "failure_code": "MEMORY_QUOTA_EXCEEDED",
                "peak_rss_mb": peak_rss_mb,
                "quota_mb": MAX_WORKER_MEMORY_MB,
                "exit_code": exit_code,
                "elapsed_ms": round(elapsed * 1000.0, 3),
            }
            _update_job(
                job_path,
                expected_launch_token=launch_token,
                status="failed",
                stage="memory_quota_exceeded",
                error=f"Worker process exceeded memory quota ({peak_rss_mb:.1f} MB > {MAX_WORKER_MEMORY_MB:.1f} MB)",
                retry_classification="manual_review",
                recoverable=False,
                failure_diagnostics=diagnostics,
            )
            _append_job_event(
                job_path,
                "worker_memory_quota_exceeded",
                status="failed",
                peak_rss_mb=peak_rss_mb,
                quota_mb=MAX_WORKER_MEMORY_MB,
                exit_code=exit_code,
            )
        elif timed_out:
            _finalize_supervised_timeout(job_path, launch_token, elapsed)
        else:
            _finalize_supervised_process_exit(
                job_path,
                launch_token,
                exit_code=exit_code if exit_code is not None else -1,
                elapsed_seconds=elapsed,
            )
    finally:
        bounded_executor.on_worker_completed(job_path)


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
        parent_event_id=str(payload.get("evidence_event_id") or ""),
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
        manifest_hash = str(saved.get('manifest_hash', ''))
        job_manifest_hash = str(payload.get('manifest_hash') or '')
        if not job_manifest_hash and manifest_hash:
            logger.info('Reconciling missing manifest_hash from verified manifest: %s', manifest_hash)
            payload['manifest_hash'] = manifest_hash
            job_manifest_hash = manifest_hash
            try:
                _update_job(job_path, manifest_hash=manifest_hash)
            except Exception:
                pass
        if manifest_hash != job_manifest_hash:
            raise ManifestError('job record and manifest hash do not match')
        try:
            job_namespace = _coerce_namespace(payload.get("plot_namespace"))
            manifest_namespace = _coerce_namespace(saved.get("plot_namespace"))
        except ValueError as exc:
            raise ManifestError("durable job has no valid PlotNamespace") from exc
        if job_namespace != manifest_namespace:
            raise ManifestError("job record and manifest PlotNamespace do not match")
        for key, expected in namespace_payload(job_namespace).items():
            if str(payload.get(key) or "") != expected:
                raise ManifestError(f"job record {key} does not match PlotNamespace")
        identity = dict(saved.get("identity") or {})
        resume_reintegration = payload.get('resume_phase') == 'reintegration'

        def heartbeat() -> None:
            while not stop_heartbeat.wait(min(60.0, LEASE_SECONDS / 3)):
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
                except Exception as exc:
                    logger.warning("Heartbeat renewal encountered transient error: %s", exc)

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

        if resume_reintegration:
            assert_worker_commit_fence(job_path, lease)
            from .snapshot_store import (
                SnapshotIntegrityError,
                load_snapshot_exact,
            )

            try:
                result = load_snapshot_exact(
                    plot_id=str(payload.get("plot_id", "")),
                    geometry_hash=str(identity.get("geometry_hash", "")),
                    snapshot_ref=str(
                        payload.get("asmae_snapshot_ref")
                        or payload.get("final_snapshot_ref")
                        or ""
                    ),
                    snapshot_id=str(payload.get("final_snapshot_id") or ""),
                )
            except SnapshotIntegrityError as exc:
                raise ManifestError(
                    "pending reintegration has no valid immutable snapshot binding"
                ) from exc
            if not result:
                raise ManifestError(
                    "pending reintegration snapshot is no longer compatible"
                )
        else:
            from .runner import ASMAERunner

            config = dict(saved.get("config") or {})
            config["disable_job_recovery"] = True
            progress_by_step = {
                "scene_stack": 24,
                "observation_operators": 34,
                "resolution_ladder": 41,
                "selected_operator_bundle": 48,
                "microzone_graph": 52,
                "layer_priors": 55,
                "state_estimation": 71,
                "radiometric_consistency": 75,
                "retrovalidation": 80,
                "causal_tracking": 82,
                "bma_ensemble": 83,
                "weak_labels": 84,
                "invariants": 84,
                "pipeline": 85,
            }

            def publish_scientific_progress(
                step: str, status: str, details: Dict[str, Any],
            ) -> None:
                target = progress_by_step.get(step)
                if target is None:
                    return
                progress = (
                    max(15, target - 3) if status == "starting" else target
                )
                _fenced_update_job(
                    job_path,
                    lease,
                    stage=f"scientific_{step}",
                    progress_pct=progress,
                    scientific_phase=step,
                    scientific_phase_status=status,
                    scientific_phase_details=dict(details or {}),
                )

            config["_worker_progress_callback"] = publish_scientific_progress
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
        # P0-C: Detect spatial execution failure inside partial results
        _result_diag = result.get("diagnostics") or {}
        is_spatial_failure = (
            _result_diag.get("chain_integrity_error") is True
            or _result_diag.get("failure_code") == "STATE_ESTIMATION_TIMEOUT"
            or result_status in ("failed_spatial_timeout", "failed_spatial_fallback")
        )
        if result_status == "success" or (result_status == "partial" and not is_spatial_failure):
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
            # Keep the in-memory record aligned with the durable update so the
            # first reintegration attempt and every retry use the same parent.
            payload["evidence_event_id"] = evidence_event_id
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
        elif result_status == "partial" and is_spatial_failure:
            # Spatial execution failed (timeout/chain integrity) — durable job is FAILED
            reintegration = {"status": "not_applicable"}
            terminal = "failed"
            _commit_job_failure_event(result, payload, saved)
            _append_job_event(
                job_path, "worker_spatial_execution_failed",
                status="failed", result_status=result_status,
                failure_code=_result_diag.get("failure_code", "SPATIAL_EXECUTION_FAILURE"),
                reason=result.get("reason") or _result_diag.get("reason"),
            )
        elif result_status == "unavailable":
            reintegration = {"status": "not_applicable"}
            terminal = 'failed'
            _commit_job_failure_event(result, payload, saved)
            _append_job_event(job_path, "worker_execution_failed", status="failed", result_status=result_status, reason=result.get("reason"))
        else:
            reintegration = {"status": "not_applicable"}
            terminal = "failed"
            _commit_job_failure_event(result, payload, saved)
            _append_job_event(job_path, "worker_execution_failed", status="failed", result_status=result_status, reason=result.get("reason"))

        stop_heartbeat.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2.0)
        terminal_record = _read_json(job_path)
        operational_attempts = list(terminal_record.get('operational_attempts') or [])
        attempt_summary = {
            "scientific_execution_attempts": int(terminal_record.get('attempts', 0) or 0),
            "reintegration_attempts": int(terminal_record.get('reintegration_attempts', 0) or 0),
            "total_worker_launches": int(terminal_record.get('launch_attempts', 0) or 0),
            "operational_receipt_count": len(operational_attempts),
        }
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
            publication_receipt_ref=reintegration.get(
                "publication_receipt_ref"
            ),
            publication_receipt_hash=reintegration.get(
                "publication_receipt_hash"
            ),
            downstream_layer_run_ids=reintegration.get("layer_run_ids", {}),
            crop_worldline_event_id=reintegration.get(
                "crop_worldline_event_id"
            ) or result.get("crop_worldline_event_id"),
            phenology_worldline_event_id=reintegration.get(
                "phenology_worldline_event_id"
            ) or result.get("phenology_worldline_event_id"),
            compatibility="current",
            retry_classification=(
                "none" if terminal == "completed" else "manual_review"
            ),
            lease_expires_at=None,
            lease_token=None,
            lease_owner=None,
            recoverable=False,
            attempt_summary=attempt_summary,
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
        classification, failure_stage = classify_execution_failure(exc, attempts)
        deterministic_contract_failure = classification == "permanent_contract"
        try:
            if lease is None:
                raise LeaseLostError('worker failed before acquiring a lease')
            _fenced_update_job(
                job_path,
                lease,
                status='failed',
                stage=failure_stage,
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
                    "failure_class": (
                        "CAPABILITY_PLAN_IDENTITY_MISMATCH"
                        if deterministic_contract_failure
                        else "WORKER_EXECUTION_FAILURE"
                    ),
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
    plot_id: Union[PlotNamespace, str],
    run_id: Optional[str] = None,
    tenant_id: str = "",
    farm_id: str = "",
) -> Optional[Dict[str, Any]]:
    if isinstance(plot_id, PlotNamespace):
        target_plot_id = plot_id.plot_id
        target_tenant_id = plot_id.tenant_id
        target_farm_id = plot_id.farm_id
    else:
        target_plot_id = str(plot_id)
        target_tenant_id = tenant_id.strip()
        target_farm_id = farm_id.strip()

    if not JOBS_DIR.exists():
        return None
    matches = []
    for job_path in JOBS_DIR.glob("*.job.json"):
        payload = _read_json(job_path)
        if str(payload.get("plot_id", "")) != target_plot_id:
            continue
        if target_tenant_id and str(payload.get("tenant_id", "")) != target_tenant_id:
            continue
        if target_farm_id and str(payload.get("farm_id", "")) != target_farm_id:
            continue
        if run_id is not None and str(payload.get("run_id", "")) != str(run_id):
            continue

        payload = _mark_stalled_if_expired(job_path, payload)
        matches.append(_public_job_payload(payload))

    if not matches:
        return None
    if run_id is None:
        running_jobs = [
            v for v in matches
            if v.get("status") in {"queued", "running", "stalled", "claimed"}
        ]
        if running_jobs:
            return max(running_jobs, key=lambda v: (_job_created_at(v), str(v.get("job_id", ""))))

        unsuperseded = [
            value for value in matches if not value.get("superseded") and value.get("status") != "superseded"
        ]
        valid_unsuperseded = []
        for v in unsuperseded:
            if v.get("status") == "completed":
                ref = v.get("final_snapshot_ref")
                if ref and not Path(ref).exists():
                    continue
            valid_unsuperseded.append(v)
        candidate_matches = valid_unsuperseded if valid_unsuperseded else unsuperseded
        latest_match = max(
            candidate_matches,
            key=lambda value: (
                _job_created_at(value),
                str(value.get("job_id", "")),
            ),
        ) if candidate_matches else None

        try:
            from services.agribrain.layer05_asmae.plot_snapshot_store import load_latest_plot_snapshot
            head = load_latest_plot_snapshot(plot_id)
            if head and head.get("publication_job_id"):
                pub_job_id = str(head["publication_job_id"])
                pub_match = next((v for v in matches if str(v.get("job_id", "")) == pub_job_id), None)
                if pub_match:
                    # Do not latch onto a stale historical snapshot job if a newer valid candidate exists
                    if latest_match and _job_created_at(latest_match) > _job_created_at(pub_match):
                        return latest_match
                    return pub_match
        except Exception:
            pass

        if latest_match:
            return latest_match
    return max(
        matches,
        key=lambda value: (
            _job_created_at(value),
            str(value.get("job_id", "")),
        ),
    )



def acquire_recovery_leader_lock(lease_seconds: int = 60) -> bool:
    """
    Acquire single-leader advisory lease across API replicas before running recovery scans.
    Tries MongoDB collection 'job_recovery_leader_lock', with fallback to filesystem lock.
    """
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=lease_seconds)
    my_id = f"pid_{os.getpid()}_{uuid.uuid4().hex[:8]}"

    lock_file = JOBS_DIR / ".recovery_leader.lock"
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    if lock_file.exists():
        data = _read_json(lock_file)
        if data:
            exp = _parse_timestamp(data.get("lease_expires_at"))
            if exp and exp > now and data.get("leader_id") != my_id:
                return False

    try:
        from services.agribrain.app.mongo_client import get_db
        from pymongo import ReturnDocument
        db = get_db()
        coll = db["job_recovery_leader_lock"]
        doc = coll.find_one_and_update(
            {
                "_id": "recovery_leader",
                "$or": [
                    {"lease_expires_at": {"$lt": now}},
                    {"lease_expires_at": None},
                ]
            },
            {
                "$set": {
                    "leader_id": my_id,
                    "lease_expires_at": expires,
                    "acquired_at": now,
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if doc and doc.get("leader_id") == my_id:
            try:
                _atomic_json(lock_file, {
                    "leader_id": my_id,
                    "lease_expires_at": expires.isoformat(),
                    "acquired_at": now.isoformat(),
                })
            except Exception:
                pass
            return True
        return False
    except Exception:
        # Filesystem fallback
        try:
            _atomic_json(lock_file, {
                "leader_id": my_id,
                "lease_expires_at": expires.isoformat(),
                "acquired_at": now.isoformat(),
            })
            return True
        except Exception:
            # Fail closed: never allow concurrent leader recovery on lock acquisition errors
            return False


def recover_pending_jobs(
    namespace: Optional[PlotNamespace] = None,
    plot_id: Optional[str] = None,
    tenant_id: str = "",
    farm_id: str = "",
) -> int:
    """Recover stalled/pending ASMAE background jobs for a plot or namespace."""
    if not JOBS_DIR.exists():
        return 0

    target_plot_id = namespace.plot_id if isinstance(namespace, PlotNamespace) else (plot_id or "")
    target_tenant_id = namespace.tenant_id if isinstance(namespace, PlotNamespace) else tenant_id
    target_farm_id = namespace.farm_id if isinstance(namespace, PlotNamespace) else farm_id

    recovered = 0

    matching_jobs = []
    for job_path in JOBS_DIR.glob("*.job.json"):
        payload = _read_json(job_path)
        if not payload:
            continue
        if target_plot_id and str(payload.get("plot_id", "")) != target_plot_id:
            continue
        if target_tenant_id and str(payload.get("tenant_id", "")) != target_tenant_id:
            continue
        if target_farm_id and str(payload.get("farm_id", "")) != target_farm_id:
            continue

        payload = _mark_stalled_if_expired(job_path, payload)
        raw_status = str(payload.get("status", ""))
        if raw_status == "reserving" or not payload.get("manifest_hash"):
            continue
        status = _canonical_status(raw_status)
        if status in ("queued", "stalled", "running") or raw_status == "completed_reintegration_pending":
            # Active lease protection: if running or completed_reintegration_pending and lease is unexpired, do not preempt
            if raw_status in ("running", "completed_reintegration_pending") and not _lease_expired(payload):
                continue
            matching_jobs.append((job_path, payload))

    if not matching_jobs:
        return 0

    matching_jobs.sort(
        key=lambda item: _job_created_at(item[1]),
        reverse=True,
    )

    newest_job_path, newest_payload = matching_jobs[0]

    for old_path, old_payload in matching_jobs[1:]:
        old_raw = str(old_payload.get("status", ""))
        old_status = _canonical_status(old_raw)
        if old_status in ("queued", "stalled", "running") or old_raw == "completed_reintegration_pending":
            _update_job(
                old_path,
                status="superseded",
                stage="superseded_by_newer_run",
                superseded_by_job_id=newest_payload.get("job_id"),
                recoverable=False,
            )


    attempts = _recovery_attempt_count(newest_payload)
    if attempts >= MAX_EXECUTION_ATTEMPTS:
        _update_job(
            newest_job_path,
            status="failed",
            stage="max_attempts_exceeded",
            error=f"Recovery attempt ceiling reached ({MAX_EXECUTION_ATTEMPTS})",
            recoverable=False,
        )
        return 0

    if spawn_worker(newest_job_path):
        recovered += 1

    return recovered



def recover_all_pending_jobs(namespace: Optional[Union[PlotNamespace, str]] = None) -> int:
    """Recover all pending jobs across all plots/namespaces on application startup, or for a specific namespace."""
    if namespace:
        return recover_pending_jobs(namespace=namespace)
    if not JOBS_DIR.exists():
        return 0
    if not acquire_recovery_leader_lock():
        logger.info("Another replica holds recovery leader lock; skipping startup recovery scan.")
        return 0
    total = 0
    namespaces = set()
    for job_path in JOBS_DIR.glob("*.job.json"):
        payload = _read_json(job_path)
        if payload and payload.get("plot_id"):
            t_id = str(payload.get("tenant_id") or "").strip()
            f_id = str(payload.get("farm_id") or "").strip()
            p_id = str(payload.get("plot_id") or "").strip()
            if p_id:
                namespaces.add((t_id, f_id, p_id))

    from services.agribrain.common.plot_namespace import PlotNamespace
    for t_id, f_id, p_id in namespaces:
        if t_id and f_id:
            ns = PlotNamespace(tenant_id=t_id, farm_id=f_id, plot_id=p_id)
            total += recover_pending_jobs(namespace=ns)
        else:
            total += recover_pending_jobs(plot_id=p_id, tenant_id=t_id, farm_id=f_id)
    return total



if __name__ == "__main__":

    if len(sys.argv) == 4 and sys.argv[1] == "--supervise":
        supervise_job(Path(sys.argv[2]).resolve(), sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == "--execute":
        run_job(Path(sys.argv[2]).resolve(), launch_token=sys.argv[3])
    elif len(sys.argv) in {2, 3}:
        run_job(
            Path(sys.argv[1]).resolve(),
            launch_token=sys.argv[2] if len(sys.argv) == 3 else None,
        )
    else:
        raise SystemExit(
            "usage: python -m layer05_asmae.background_jobs "
            "[--supervise|--execute] <job.json> [launch-token]"
        )
