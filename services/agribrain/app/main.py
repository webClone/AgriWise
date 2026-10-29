"""
AgriBrain API - AI Organism Backend
Specialized AIs orchestrated by LLM conductor
[CropID Engine v2.0.0 — per-crop prior scoring]
"""

# Load environment variables from project root .env file
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agribrain.app")

# Load .env file from project root (agriwise directory)
project_root = Path(__file__).parent.parent.parent.parent  # services/agribrain/app/main.py -> agriwise
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] Loaded environment from: {env_path}")

import sys
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
agribrain_root = project_root / "services" / "agribrain"
if str(agribrain_root) not in sys.path:
    sys.path.insert(0, str(agribrain_root))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, Header, Query, Path as FastAPIPath, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union, Tuple
import json
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
import threading as _threading
import time as _progress_time

from services.agribrain.common.plot_namespace import PlotNamespace, _coerce_namespace
from services.agribrain.app.internal_service_auth import require_internal_service_request, init_mongo_nonce_indexes

# Import specialized AIs
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.orchestrator import orchestrator, AIOrchestrator
from health.disease_risk import disease_risk_ai
from perception.phenology import phenology_ai
from climate.spray_window import spray_window_ai
from climate.water_stress import water_stress_ai

# Register all specialized AIs
orchestrator.register_ai("disease_risk", disease_risk_ai)
orchestrator.register_ai("phenology", phenology_ai)
orchestrator.register_ai("spray_window", spray_window_ai)
orchestrator.register_ai("water_stress", water_stress_ai)

_refresh_worker = None
_asmae_recovery_stop = None
_asmae_recovery_thread = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _refresh_worker, _asmae_recovery_stop, _asmae_recovery_thread
    logger.info("[STARTUP] Starting background data refresh worker...")
    try:
        from layer0.data_gateway.refresh_worker import DataRefreshWorker
        _refresh_worker = DataRefreshWorker()
        _refresh_worker.start()
    except Exception as _e:
        logger.error(f"[STARTUP] Refresh worker failed to start: {_e}")

    try:
        import threading as _worker_threading
        from services.agribrain.layer05_asmae.background_jobs import recover_all_pending_jobs

        recovered = recover_all_pending_jobs()
        logger.info('[STARTUP] Launched %s recoverable ASMAE job(s)', recovered)
        _asmae_recovery_stop = _worker_threading.Event()

        def _asmae_recovery_loop():
            while not _asmae_recovery_stop.wait(30.0):
                try:
                    recover_all_pending_jobs()
                except Exception as recovery_exc:
                    logger.exception(
                        '[ASMAE] Durable worker recovery scan failed: %s',
                        recovery_exc,
                    )

        _asmae_recovery_thread = _worker_threading.Thread(
            target=_asmae_recovery_loop,
            name='asmae-worker-recovery',
            daemon=True,
        )
        _asmae_recovery_thread.start()
    except Exception as _e:
        logger.exception('[STARTUP] ASMAE job recovery failed: {_e}')

    # Initialize shared Mongo nonce indexes if storage is connected
    try:
        from app.mongo_client import get_db
        _db = get_db()
        if _db is not None:
            init_mongo_nonce_indexes(_db)
            logger.info("[STARTUP] Initialized Mongo nonce collection indexes.")
    except Exception as _nonce_err:
        logger.warning(f"[STARTUP] Mongo nonce index initialization deferred: {_nonce_err}")

    # V65E Cache Temp Cleanup: Purge stale .tmp files and legacy cache files from the surfaces cache directory on startup.
    try:
        cache_dir = Path(__file__).resolve().parents[1] / "artifacts" / "surfaces_cache"
        if cache_dir.exists() and cache_dir.is_dir():
            now = _progress_time.time()
            LEGACY_CACHE_VERSION_MARKERS = [
                "_v62b.json",
                "_v63d_surface_metadata.json",
                "_v63e_surface_contract.json",
                "_v65e_categorical_integrity.json",
            ]
            for filename in os.listdir(cache_dir):
                file_path = cache_dir / filename
                if filename.endswith(".tmp"):
                    try:
                        file_mtime = file_path.stat().st_mtime
                        if (now - file_mtime) > 300:
                            file_path.unlink(missing_ok=True)
                            logger.info(f"[STARTUP] Removed stale cache temp file: {file_path}")
                    except Exception as fe:
                        logger.error(f"[STARTUP] Failed to remove stale tmp file {file_path}: {fe}")
                elif any(marker in filename for marker in LEGACY_CACHE_VERSION_MARKERS):
                    try:
                        file_path.unlink(missing_ok=True)
                        logger.info(f"[STARTUP] Removed legacy cache file: {file_path}")
                    except Exception as fe:
                        logger.error(f"[STARTUP] Failed to remove legacy cache file {file_path}: {fe}")
    except Exception as e:
        logger.error(f"[STARTUP] Surfaces cache temp and legacy cleanup failed: {e}")

    yield
    logger.info("[SHUTDOWN] Stopping background data refresh worker...")
    if _asmae_recovery_stop is not None:
        _asmae_recovery_stop.set()
    if _asmae_recovery_thread is not None:
        _asmae_recovery_thread.join(timeout=5.0)
    try:
        if _refresh_worker is not None:
            _refresh_worker.stop()
    except Exception as _e:
        logger.error(f"[SHUTDOWN] Refresh worker failed to stop: {_e}")

app = FastAPI(
    title="AgriBrain API",
    description="AI Organism for Agriculture - Specialized Deep Learning modules orchestrated by LLM",
    version="2.0.0",
    lifespan=lifespan
)

_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_frontend_url = os.environ.get("FRONTEND_URL")
if _frontend_url:
    _cors_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Pipeline Progress Store (in-memory, thread-safe, PlotNamespace-keyed)
_progress_lock = _threading.Lock()
_progress_store: Dict[str, Dict[str, Any]] = {}  # run_id -> progress state
_plot_run_map: Dict[Tuple[str, str, str], str] = {}  # (tenant_id, farm_id, plot_id) -> latest run_id
_last_recovery_scan_time: Dict[str, float] = {}
_RUN_RESULTS_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "run_results"


def _run_result_path(run_id: str) -> Path:
    import re
    safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(run_id))
    return _RUN_RESULTS_DIR / f"{safe_id}.json"


def _persist_run_result(
    run_id: str,
    namespace: PlotNamespace,
    payload: Dict[str, Any],
    geometry_hash: str = "",
) -> Path:
    """Publish the durable result and canonical head before terminal progress."""
    import uuid
    ns = _coerce_namespace(namespace)
    path = _run_result_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    envelope = {
        "run_id": run_id,
        "plot_id": ns.plot_id,
        "plot_namespace": {
            "tenant_id": ns.tenant_id,
            "farm_id": ns.farm_id,
            "plot_id": ns.plot_id,
        },
        "published_at": datetime.utcnow().isoformat() + "Z",
        "result": payload,
    }
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(envelope, handle, separators=(",", ":"), default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)

    # The browser consumes only a validated canonical head.  Terminal L10
    # provider/degraded results therefore need the same immutable publication
    # chain as completed ASMAE reintegration; otherwise a successful run is
    # permanently reported as "canonical publication pending".
    from services.agribrain.layer05_asmae.plot_snapshot_store import (
        publish_canonical_layer10_snapshot,
    )
    publish_canonical_layer10_snapshot(
        namespace=ns,
        geometry_hash=str(geometry_hash or ""),
        frontend_payload=payload,
        request_run_id=run_id,
    )
    return path

def _update_progress(
    namespace: Union[PlotNamespace, str],
    stage: str,
    status: str,
    elapsed: float = 0.0,
    run_id: Optional[str] = None
):
    """Thread-safe run-scoped progress update using PlotNamespace.to_tuple() key."""
    if isinstance(namespace, PlotNamespace):
        ns = namespace
    else:
        str_val = str(namespace).strip()
        found_ns = None
        with _progress_lock:
            for k_tuple in _plot_run_map:
                if len(k_tuple) == 3 and k_tuple[2] == str_val:
                    found_ns = PlotNamespace(tenant_id=k_tuple[0], farm_id=k_tuple[1], plot_id=k_tuple[2])
                    break
        if found_ns:
            ns = found_ns
        else:
            # Progress is authority-bearing state.  Never manufacture a second
            # namespace for a bare plot id; callers must supply the durable
            # namespace or refer to an already-registered plot.
            ns = _coerce_namespace(namespace)

    ns_key = ns.to_tuple()
    with _progress_lock:
        r_id = run_id or _plot_run_map.get(ns_key) or f"run-{ns.plot_id}"
        _plot_run_map[ns_key] = r_id
        if r_id not in _progress_store:
            _progress_store[r_id] = {
                "run_id": r_id,
                "plot_id": ns.plot_id,
                "namespace": ns,
                "stages": [],
                "started_at": _progress_time.time(),
                "status": "running",
                "active": True,
                "terminal": False,
            }
        _progress_store[r_id]["namespace"] = ns
        _progress_store[r_id]["updated_at"] = _progress_time.time()
        
        is_final_stage = stage.strip().lower() in {
            "complete", "completed", "pipeline complete", "pipeline completed"
        }
        is_term = status in ("failed", "error", "degraded", "cancelled") or (
            status == "done" and is_final_stage
        )
        if is_term:
            _progress_store[r_id]["active"] = False
            _progress_store[r_id]["terminal"] = True
            _progress_store[r_id]["status"] = status

        entry = {
            "stage": stage,
            "status": status,
            "elapsed": round(elapsed, 2),
            "timestamp": round(_progress_time.time() - _progress_store[r_id]["started_at"], 2),
        }
        stages = _progress_store[r_id]["stages"]
        existing = next((i for i, s in enumerate(stages) if s["stage"] == stage), None)
        if existing is not None:
            stages[existing] = entry
        else:
            stages.append(entry)

def _terminalize_progress(
    namespace: Union[PlotNamespace, str],
    status: str = "failed",
    run_id: Optional[str] = None,
    *,
    failure: Optional[Dict[str, Any]] = None,
):
    if isinstance(namespace, PlotNamespace):
        ns = namespace
    else:
        str_val = str(namespace).strip()
        found_ns = None
        with _progress_lock:
            for k_tuple in _plot_run_map:
                if len(k_tuple) == 3 and k_tuple[2] == str_val:
                    found_ns = PlotNamespace(tenant_id=k_tuple[0], farm_id=k_tuple[1], plot_id=k_tuple[2])
                    break
        if found_ns:
            ns = found_ns
        else:
            ns = _coerce_namespace(namespace)

    ns_key = ns.to_tuple()
    with _progress_lock:
        r_id = run_id or _plot_run_map.get(ns_key)
        if r_id and r_id in _progress_store:
            _progress_store[r_id]["active"] = False
            _progress_store[r_id]["terminal"] = True
            _progress_store[r_id]["status"] = status
            if failure:
                _progress_store[r_id]["failure"] = dict(failure)


def _request_failure_from_exception(
    exc: Exception,
    *,
    stage: str = "layer10_surface_publication",
) -> Dict[str, str]:
    """Retain typed request failure detail without inventing an ASMAE job."""
    detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
    if isinstance(detail, dict):
        message = str(detail.get("error") or detail.get("detail") or detail)
        explicit_code = str(detail.get("code") or "")
    else:
        message = str(detail)
        explicit_code = ""
    prefix = message.split(":", 1)[0].strip()
    prefix_is_code = bool(prefix) and all(
        char.isupper() or char.isdigit() or char == "_" for char in prefix
    )
    exception_name = type(exc).__name__
    derived_code = "".join(
        ("_" + char if char.isupper() and index else char.upper())
        for index, char in enumerate(exception_name)
    )
    return {
        "code": explicit_code or (prefix if prefix_is_code else derived_code),
        "stage": stage,
        "type": exception_name,
        "message": message,
    }

def _clear_progress(namespace: Union[PlotNamespace, str], run_id: Optional[str] = None):
    ns = namespace if isinstance(namespace, PlotNamespace) else _coerce_namespace(namespace)
    ns_key = ns.to_tuple()
    with _progress_lock:
        r_id = run_id or _plot_run_map.get(ns_key)
        if r_id:
            _progress_store.pop(r_id, None)
        if _plot_run_map.get(ns_key) == r_id:
            _plot_run_map.pop(ns_key, None)

@app.get("/v2/snapshots/{snapshot_id}")
def api_v2_exact_snapshot(
    snapshot_id: str,
    namespace: PlotNamespace = Depends(require_internal_service_request)
):
    """Read an exact validated publication. A superseded ID is never replaced.

    Until historical snapshot receipts have an independent integrity validator,
    only the verified current head can be served through this public API.
    """
    from services.agribrain.layer05_asmae.plot_snapshot_store import (
        load_plot_snapshot_by_id, load_latest_plot_snapshot,
    )

    existing = load_plot_snapshot_by_id(snapshot_id, namespace=namespace)
    if existing is None:
        raise HTTPException(status_code=404, detail="Exact snapshot not found for namespace")

    validated = load_latest_plot_snapshot(namespace)
    if not validated or str(validated.get("snapshot_id") or "") != snapshot_id:
        raise HTTPException(status_code=409, detail="Exact snapshot was superseded; no substitution is allowed")

    validation = validated.get("validation") or {}
    required_flags = (
        "nodeValid", "publicationValid", "receiptValid",
        "inventoryValid", "bindingValid", "lineageValid",
        "schemaValid", "contractValid", "publicationStatusValid",
    )
    if not all(validation.get(flag) is True for flag in required_flags):
        raise HTTPException(status_code=409, detail="Exact snapshot integrity or schema validation failed")
    if not isinstance(validated.get("frontend_payload"), dict):
        raise HTTPException(status_code=409, detail="Exact snapshot has no validated frontend publication")

    response = dict(validated)
    response.pop("asmae", None)
    response.pop("scientific_result", None)
    response["available"] = True
    return Response(
        content=json.dumps(response).encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": "no-cache"}
    )


_SNAPSHOT_RESPONSE_CACHE: Dict[Tuple[str, str, str], bytes] = {}
_SNAPSHOT_RESPONSE_CACHE_LOCK = _threading.Lock()


@app.get("/v2/plots/{plot_id}/snapshot")
def api_v2_canonical_plot_snapshot(
    plot_id: str,
    namespace: PlotNamespace = Depends(require_internal_service_request)
):
    """Retrieve canonical plot snapshot head for the authenticated namespace."""
    if namespace.plot_id != plot_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Header X-Plot-Id does not match URL path parameter plot_id"
        )
    from services.agribrain.layer05_asmae.plot_snapshot_store import load_latest_plot_snapshot
    snapshot = load_latest_plot_snapshot(namespace)
    if snapshot is None:
        return {
            "available": False,
            "reason": "canonical_head_not_published",
            "plot_id": namespace.plot_id,
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
        }
    validation = snapshot.get("validation") or {}
    integrity_keys = (
        "nodeValid",
        "publicationValid",
        "receiptValid",
        "inventoryValid",
        "bindingValid",
        "lineageValid",
    )
    contract_keys = (
        "schemaValid",
        "contractValid",
        "publicationStatusValid",
    )
    invalid_integrity_flags = [
        key for key in integrity_keys if validation.get(key) is not True
    ]
    if invalid_integrity_flags:
        # A corrupt or incompletely bound head remains on disk as immutable
        # audit evidence, but it is quarantined from browser/scientific
        # authority.  Returning HTTP 200 with ``available: false`` preserves
        # the client's last-known-good raster while a repair/refresh is
        # requested; importantly, no payload from the invalid head is exposed
        # as a candidate publication.
        return {
            "available": False,
            "reason": "canonical_head_integrity_invalid",
            "status": "quarantined",
            "quarantined": True,
            "refreshRequired": True,
            "retainLastKnownGood": True,
            "invalidIntegrityFlags": invalid_integrity_flags,
            "plot_id": namespace.plot_id,
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "snapshot_id": snapshot.get("snapshot_id"),
            "validation": validation,
            "contract_validation": snapshot.get("contract_validation") or {},
        }
    if not all(validation.get(key) is True for key in contract_keys):
        return {
            "available": False,
            "reason": "canonical_head_schema_stale",
            "status": "stale",
            "quarantined": False,
            "refreshRequired": True,
            "retainLastKnownGood": True,
            "plot_id": namespace.plot_id,
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "snapshot_id": snapshot.get("snapshot_id"),
            "validation": validation,
            "contract_validation": snapshot.get("contract_validation") or {},
        }

    cache_key = (
        namespace.stable_key(),
        str(snapshot.get("snapshot_id")),
        str(snapshot.get("frontend_publication_hash") or ""),
    )
    with _SNAPSHOT_RESPONSE_CACHE_LOCK:
        cached_bytes = _SNAPSHOT_RESPONSE_CACHE.get(cache_key)
    if cached_bytes is not None:
        return Response(
            content=cached_bytes,
            media_type="application/json",
            headers={"Cache-Control": "no-cache"}
        )

    response = dict(snapshot)
    response.pop("asmae", None)
    response.pop("scientific_result", None)
    response["available"] = True

    raw_bytes = json.dumps(response).encode("utf-8")
    with _SNAPSHOT_RESPONSE_CACHE_LOCK:
        if len(_SNAPSHOT_RESPONSE_CACHE) > 20:
            _SNAPSHOT_RESPONSE_CACHE.clear()
        _SNAPSHOT_RESPONSE_CACHE[cache_key] = raw_bytes

    return Response(
        content=raw_bytes,
        media_type="application/json",
        headers={"Cache-Control": "no-cache"}
    )


@app.get("/v2/progress/{plot_id}")
def api_v2_progress(
    plot_id: str,
    run_id: Optional[str] = None,
    namespace: PlotNamespace = Depends(require_internal_service_request)
):
    """Polling endpoint for request-local and durable ASMAE progress."""
    if namespace.plot_id != plot_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Header X-Plot-Id does not match URL path parameter plot_id"
        )

    recovery_triggered = 0
    now_ts = _progress_time.time()
    ns_key = namespace.stable_key()
    if now_ts - _last_recovery_scan_time.get(ns_key, 0.0) >= 15.0:
        _last_recovery_scan_time[ns_key] = now_ts
        try:
            from services.agribrain.layer05_asmae.background_jobs import recover_all_pending_jobs
            recovery_triggered = recover_all_pending_jobs(namespace=namespace)
        except Exception as recovery_exc:
            logger.warning('Durable ASMAE recovery failed during progress poll: %s', recovery_exc)

    with _progress_lock:
        target_run_id = run_id or _plot_run_map.get(namespace.to_tuple())
        data = _progress_store.get(target_run_id) if target_run_id else None
        if data and data.get("namespace") and data["namespace"] != namespace:
            data = None

    durable_job = None
    try:
        from services.agribrain.layer05_asmae.background_jobs import latest_job_for_plot
        durable_job = latest_job_for_plot(namespace, run_id=run_id)
    except Exception as progress_exc:
        logger.debug("Durable ASMAE progress unavailable: %s", progress_exc)

    durable_error = ""
    if durable_job:
        durable_job = dict(durable_job)
        durable_error = str(durable_job.get("error") or durable_job.get("reason") or "")
        scientific_identity = durable_job.get("scientific_identity")
        if not isinstance(scientific_identity, dict):
            scientific_identity = {}
        if "CAPABILITY_PLAN_IDENTITY_MISMATCH" in durable_error:
            from services.agribrain.layer05_asmae.evidence_capability import EVIDENCE_CAPABILITY_CONTRACT_VERSION

            old_contract = str(
                scientific_identity.get("evidence_capability_contract_version", "")
                or durable_job.get("evidence_capability_contract_version", "")
            )
            durable_job.update({
                "failure_code": "CAPABILITY_PLAN_IDENTITY_MISMATCH",
                "stage": "contract_validation_failed",
                "retry_classification": "permanent_contract",
                "recoverable": False,
                "retry_eligible": old_contract != EVIDENCE_CAPABILITY_CONTRACT_VERSION,
                "current_evidence_capability_contract_version": EVIDENCE_CAPABILITY_CONTRACT_VERSION,
            })

        durable_status = str(durable_job.get("status") or "").lower()
        old_source_digest = str(
            scientific_identity.get("scientific_source_digest") or ""
        )
        if durable_status == "failed" and old_source_digest:
            from services.agribrain.layer05_asmae.code_lineage import scientific_source_digest

            try:
                current_source_digest = scientific_source_digest()
            except Exception as digest_exc:
                # Retry eligibility is advisory metadata; polling the durable
                # terminal state must remain available if lineage inspection
                # is temporarily unavailable.
                logger.debug(
                    "Scientific source digest unavailable during progress poll: %s",
                    digest_exc,
                )
                current_source_digest = ""
            if current_source_digest and old_source_digest != current_source_digest:
                # This is a response annotation only. ``durable_job`` is a
                # copy, so the immutable terminal job record remains intact.
                durable_job.update({
                    "retry_eligible": True,
                    "current_scientific_source_digest": current_source_digest,
                })

    from services.agribrain.layer05_asmae.plot_snapshot_store import load_latest_plot_snapshot
    canonical_head = load_latest_plot_snapshot(namespace)

    final_snapshot_id = None
    if durable_job and durable_job.get("final_snapshot_id"):
        final_snapshot_id = durable_job["final_snapshot_id"]
    elif canonical_head and canonical_head.get("snapshot_id"):
        final_snapshot_id = canonical_head["snapshot_id"]

    stages = data.get("stages", []) if data else (durable_job.get("stages", []) if durable_job else [])
    durable_status = str((durable_job or {}).get("status") or "").lower()
    if durable_job is not None:
        status_val = durable_status or "idle"
    elif data:
        status_val = data.get("status", "running")
    else:
        status_val = "idle"

    head_snapshot_id = canonical_head.get("snapshot_id") if canonical_head else None
    if status_val == "completed" and final_snapshot_id and head_snapshot_id == final_snapshot_id:
        publication_relation = "published"
    elif status_val == "completed":
        completed_at_str = (durable_job or {}).get("completed_at") or (durable_job or {}).get("updated_at")
        try:
            completed_dt = _parse_timestamp(completed_at_str)
            age_s = (_progress_time.time() - completed_dt.timestamp()) if completed_dt else 999999
        except Exception:
            age_s = 999999
        if age_s > 60:
            publication_relation = "published" if head_snapshot_id else "stale_completed"
        else:
            publication_relation = "completed_unpublished"
    elif durable_error or status_val in ("failed", "error"):
        publication_relation = "failed"
    else:
        publication_relation = "in_progress"
    terminal_status = status_val in ("completed", "failed", "superseded")
    if durable_job is not None:
        active = status_val in ("queued", "running", "stalled")
        terminal = terminal_status
    else:
        active = False if terminal_status else (
            data.get("active", True) if data else False
        )
        terminal = True if terminal_status else (
            data.get("terminal", False) if data else False
        )

    return {
        "plot_id": namespace.plot_id,
        "tenant_id": namespace.tenant_id,
        "farm_id": namespace.farm_id,
        "run_id": target_run_id or (durable_job.get("run_id") if durable_job else None),
        "active": active,
        "terminal": terminal,
        "status": status_val,
        "publicationRelation": publication_relation,
        "stages": stages,
        "final_snapshot_id": final_snapshot_id,
        "canonical_head_snapshot_id": head_snapshot_id,
        "recovery_triggered": recovery_triggered,
        "request_failure": data.get("failure") if data else None,
        "durable_job": durable_job,
        # Compatibility name used by the browser job-state adapter. Both names
        # reference the same durable, namespace-validated record.
        "asmae_job": durable_job,
    }

# ============================================================================
# Request/Response Models
# ============================================================================

class OrchestrationRequest(BaseModel):
    """Request to the AI Organism orchestrator"""
    query: str
    context: Dict[str, Any]  # Full plot context (realTime, soil, climate, etc.)
    crop: Optional[str] = "tomato"

class OrchestrationResponse(BaseModel):
    """Response from AI Organism orchestrator"""
    detected_intents: List[str]
    routed_to: List[str]
    ai_results: Dict[str, Any]
    needs_llm_synthesis: bool
    timestamp: str

class SpecializedAIRequest(BaseModel):
    """Direct request to a specific AI"""
    context: Dict[str, Any]
    crop: Optional[str] = "tomato"

class V2RunRequest(BaseModel):
    """Unified Next.js API route payload"""
    context: str  # Base64 encoded context
    query: Optional[str] = ""
    mode: Optional[str] = "chat"
    history: Optional[str] = ""
    exp: Optional[str] = "INTERMEDIATE"
    userMode: Optional[str] = "FARMER"
    force_refresh: Optional[bool] = False  # V63A: bypass surfaces cache for smoke tests
    experimental_1m: Optional[bool] = False
    visual_intensity: Optional[float] = 0.40
    source_policy: Optional[str] = None
    run_id: Optional[str] = None

class V2IntentRequest(BaseModel):
    query: str
    history: Optional[str] = ""

class V2SandboxRequest(BaseModel):
    """Payload for interactive biophysical what-if sandbox simulation"""
    context: str  # Base64 encoded context
    temp_offset: Optional[float] = 0.0
    rain_volume: Optional[float] = 0.0
    irrigation_mode: Optional[str] = "default"
    nitrogen_applied: Optional[float] = 0.0

# ============================================================================
# Legacy Endpoints (for backward compatibility)
# ============================================================================

class EORequest(BaseModel):
    field_id: str
    start_date: str
    end_date: str

class YieldRequest(BaseModel):
    field_id: str
    crop: str

@app.get("/")
def root():
    return {
        "status": "healthy",
        "service": "agribrain",
        "version": "2.0.0",
        "capabilities": ["disease-risk", "phenology", "spray-window", "water-stress"],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/debug/sentinel")
def debug_sentinel():
    """
    Diagnostic endpoint to test Sentinel Hub authentication.
    Returns detailed error information to help debug connection issues.
    """
    import requests
    
    # Check environment variables
    client_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
    client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
    
    result = {
        "env_loaded": True,
        "client_id_present": bool(client_id),
        "client_id_prefix": client_id[:15] + "..." if client_id else None,
        "client_secret_present": bool(client_secret),
        "client_secret_length": len(client_secret) if client_secret else 0,
        "auth_url": "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        "auth_test": None,
        "error": None
    }
    
    if not client_id or not client_secret:
        result["error"] = "Missing SENTINEL_HUB_CLIENT_ID or SENTINEL_HUB_CLIENT_SECRET"
        return result
    
    # Try authentication
    try:
        auth_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        response = requests.post(auth_url, data=payload, timeout=15)
        result["auth_status_code"] = response.status_code
        
        if response.status_code == 200:
            token_data = response.json()
            result["auth_test"] = "SUCCESS"
            result["token_type"] = token_data.get("token_type")
            result["expires_in"] = token_data.get("expires_in")
        else:
            result["auth_test"] = "FAILED"
            result["error"] = response.text[:500]  # Limit error message length
            
    except Exception as e:
        result["auth_test"] = "ERROR"
        result["error"] = str(e)
    
    return result

@app.get("/debug/sar-test")
def debug_sar_test(lat: float = 36.5, lng: float = 2.9):
    """
    Test actual SAR data request to diagnose data fetching issues.
    """
    import requests
    from datetime import datetime, timedelta
    
    result = {
        "lat": lat,
        "lng": lng,
        "steps": []
    }
    
    # Step 1: Get token
    try:
        from eo.sentinel import get_access_token, SENTINEL_STATS_URL
        token = get_access_token()
        result["steps"].append({"step": "get_token", "status": "SUCCESS", "token_prefix": "REDACTED"})
    except Exception as e:
        result["steps"].append({"step": "get_token", "status": "ERROR", "error": str(e)})
        return result
    
    # Step 2: Build request
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    start_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59Z")
    
    delta = 0.002
    bbox = [lng - delta, lat - delta, lng + delta, lat + delta]
    
    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: ["VV", "VH", "dataMask"],
            output: [
                { id: "vv", bands: 1, sampleType: "FLOAT32" },
                { id: "vh", bands: 1, sampleType: "FLOAT32" },
                { id: "dataMask", bands: 1, sampleType: "UINT8" }
            ]
        };
    }
    function evaluatePixel(s) {
        return {
            vv: [10 * Math.log10(s.VV)],
            vh: [10 * Math.log10(s.VH)],
            dataMask: [s.dataMask]
        };
    }
    """
    
    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": { "crs": "http://www.opengis.net/def/crs/EPSG/0/4326" }
            },
            "data": [{
                "type": "sentinel-1-grd",
                "timeRange": { "from": start_str, "to": end_str },
                "dataFilter": { "acquisitionMode": "IW" }
            }]
        },
        "aggregation": {
            "timeRange": { "from": start_str, "to": end_str },
            "aggregationInterval": { "of": "P90D" },
            "evalscript": evalscript,
            "width": 1,
            "height": 1
        }
    }
    
    result["request"] = {
        "url": SENTINEL_STATS_URL,
        "bbox": bbox,
        "time_range": f"{start_str} to {end_str}"
    }
    
    # Step 3: Make request
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(SENTINEL_STATS_URL, json=payload, headers=headers, timeout=30)
        result["steps"].append({
            "step": "api_request", 
            "status_code": response.status_code
        })
        
        if response.status_code == 200:
            data = response.json()
            result["response"] = data
            result["steps"].append({"step": "parse_response", "status": "SUCCESS", "data_count": len(data.get("data", []))})
        else:
            result["steps"].append({"step": "api_request", "status": "FAILED", "error": response.text[:500]})
            
    except Exception as e:
        result["steps"].append({"step": "api_request", "status": "ERROR", "error": str(e)})
    
    return result

@app.get("/eo/rainfall-climatology")
def get_rainfall_climatology(lat: float, lng: float):
    """
    Get 30-year monthly rainfall normals (1991-2020) from ERA5 via Open-Meteo.
    """
    from eo.sentinel import fetch_rainfall_climatology
    result = fetch_rainfall_climatology(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch rainfall climatology", "lat": lat, "lng": lng}

@app.get("/eo/rainfall-history")
def get_rainfall_history(lat: float, lng: float, years: int = 30):
    """
    Get annual rainfall history for the past N years.
    """
    from eo.sentinel import fetch_rainfall_history
    result = fetch_rainfall_history(lat, lng, years)
    if result:
        return result
    return {"error": "Could not fetch rainfall history", "lat": lat, "lng": lng}

@app.get("/eo/drought-analysis")
def get_drought_analysis(lat: float, lng: float):
    """
    Analyze drought frequency and risk based on historical rainfall.
    """
    from eo.sentinel import calculate_drought_frequency
    result = calculate_drought_frequency(lat, lng)
    if result:
        return result
    return {"error": "Could not perform drought analysis", "lat": lat, "lng": lng}

@app.get("/eo/rainfall-anomaly")
def get_rainfall_anomaly(lat: float, lng: float):
    """
    Compare current year's rainfall to 30-year baseline.
    """
    from eo.sentinel import get_current_rainfall_anomaly
    result = get_current_rainfall_anomaly(lat, lng)
    if result:
        return result
    return {"error": "Could not calculate rainfall anomaly", "lat": lat, "lng": lng}



@app.get("/tools/eo/get_field_indicators")
def get_field_indicators(field_id: str, start_date: str, end_date: str):
    """Legacy EO endpoint - now routes to Crop Observation AI"""
    return {
        "field_id": field_id,
        "date_range": {"start": start_date, "end": end_date},
        "ndvi": 0.65,
        "ndmi": 0.42,
        "source": "LEGACY_FALLBACK",
        "message": "Use /orchestrate for AI Organism routing"
    }

# ============================================================================
# Multi-Source Earth Observation Endpoints
# ============================================================================

@app.get("/eo/indices")
def get_vegetation_indices(lat: float, lng: float):
    """
    Get multiple vegetation indices from Sentinel-2:
    - NDVI: Vegetation health
    - EVI: Enhanced vegetation (better for dense canopy)
    - NDWI: Water content in vegetation
    - NDMI: Moisture stress
    """
    from eo.sentinel import fetch_vegetation_indices
    result = fetch_vegetation_indices(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch vegetation indices", "lat": lat, "lng": lng}

@app.get("/eo/soil-moisture")
def get_soil_moisture(lat: float, lng: float):
    """
    Get Sentinel-1 SAR backscatter as soil moisture proxy.
    VV/VH polarization ratio correlates with soil moisture.
    """
    from eo.sentinel import fetch_soil_moisture_proxy
    result = fetch_soil_moisture_proxy(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch SAR data", "lat": lat, "lng": lng}

@app.post("/v2/mesia/simulate-wifi-csi")
def simulate_mesia_wifi_csi(
    payload: Dict[str, Any],
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    Simulates or processes farmstead AP or edge IoT Wi-Fi CSI sensing.
    Authority is derived strictly from server-authenticated PlotNamespace.
    """
    from services.agribrain.mesia.service import MesiaProductionService
    spoofed_keys = {"tenant_id", "tenantId", "farm_id", "farmId"}
    if any(k in payload for k in spoofed_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client payload must not specify tenant_id, tenantId, farm_id, or farmId. Authority is derived exclusively from authenticated tokens.",
        )
    dist = float(payload.get("ap_distance_m", 35.0))
    ssid = str(payload.get("ssid", "Farmstead_HQ_IoT"))
    freq = float(payload.get("frequency_mhz", 2437.0))
    return MesiaProductionService.simulate_or_ingest_wifi_csi(
        plot_namespace=namespace,
        ap_distance_m=dist,
        ssid=ssid,
        frequency_mhz=freq,
    )

@app.post("/v2/mesia/ingest-nmea")
def ingest_mesia_nmea(
    payload: Dict[str, Any],
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    Ingests native NMEA survey log containing actual ground-level radio wave observations.
    Authority is derived strictly from server-authenticated PlotNamespace.
    """
    from services.agribrain.mesia.service import MesiaProductionService
    spoofed_keys = {"tenant_id", "tenantId", "farm_id", "farmId"}
    if any(k in payload for k in spoofed_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client payload must not specify tenant_id, tenantId, farm_id, or farmId. Authority is derived exclusively from authenticated tokens.",
        )
    nmea_text = payload.get("nmea_text", "")
    if not nmea_text:
        return {"error": "nmea_text is required"}
    return MesiaProductionService.ingest_nmea_log(plot_namespace=namespace, nmea_text=nmea_text)

@app.post("/v2/mesia/ingest-sigmf-csi")
def ingest_mesia_sigmf_csi(
    payload: Dict[str, Any],
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    Ingests native SigMF Wi-Fi CSI captures containing ground-level OFDM channel matrices.
    Authority is derived strictly from server-authenticated PlotNamespace.
    """
    from services.agribrain.mesia.service import MesiaProductionService
    import base64
    spoofed_keys = {"tenant_id", "tenantId", "farm_id", "farmId"}
    if any(k in payload for k in spoofed_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client payload must not specify tenant_id, tenantId, farm_id, or farmId. Authority is derived exclusively from authenticated tokens.",
        )
    data_b64 = payload.get("data_b64", "")
    if not data_b64:
        return {"error": "data_b64 is required"}
    try:
        data_bytes = base64.b64decode(data_b64)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid base64: {e}")
    meta_json = payload.get("meta_json")
    return MesiaProductionService.ingest_sigmf_csi(
        plot_namespace=namespace,
        data_bytes=data_bytes,
        meta_json=meta_json,
    )

@app.post("/v2/mesia/ingest-oran-kpm")
def ingest_mesia_oran_kpm(
    payload: Dict[str, Any],
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    Ingests live O-RAN E2 KPM telemetry with cryptographic consent validation.
    Authority is derived strictly from server-authenticated PlotNamespace.
    """
    from services.agribrain.mesia.service import MesiaProductionService
    spoofed_keys = {"tenant_id", "tenantId", "farm_id", "farmId"}
    if any(k in payload for k in spoofed_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client payload must not specify tenant_id, tenantId, farm_id, or farmId. Authority is derived exclusively from authenticated tokens.",
        )
    raw_kpm = payload.get("raw_kpm_data", {})
    if not raw_kpm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="raw_kpm_data is required")
    operator_name = payload.get("operator_name", "Mobilis DZ")
    cell_id = int(payload.get("cell_id", 60401))
    return MesiaProductionService.ingest_oran_e2_kpm_telemetry(
        plot_namespace=namespace,
        raw_kpm_data=raw_kpm,
        operator_name=operator_name,
        cell_id=cell_id,
    )

@app.get("/v2/mesia/{plot_id}/fleet-health")
def get_mesia_fleet_health(
    plot_id: str,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    Evaluates fleet health, temperature-accelerated calibration wear, and continuous drift sentinels.
    """
    from services.agribrain.mesia.service import MesiaProductionService
    return MesiaProductionService.evaluate_fleet_and_drift_status(plot_namespace=namespace)

@app.get("/v2/mesia/{plot_id}")
def get_mesia_spectrum_observatory(
    plot_id: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    soil_type: Optional[str] = None,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    MESIA Multi-Environment Spectrum Intelligence Architecture (TRL 1-2 Research Demonstrator).
    Discovers ambient RF signals of opportunity (GNSS-R, Cellular Downlink, 
    Broadcast UHF, Spaceborne CYGNSS) to remotely sense sub-surface VWC and foliar water
    with zero in-situ hardware. Emits Principle P-08 ASMAE advisory evidence proposals.
    """
    from services.agribrain.mesia.service import MesiaProductionService
    polygon = None
    if lat is not None and lng is not None:
        # Small box around lat, lng
        d = 0.0015
        polygon = [(lat + d, lng - d), (lat + d, lng + d), (lat - d, lng + d), (lat - d, lng - d)]
    return MesiaProductionService.scan_plot_spectrum(
        plot_namespace=namespace,
        polygon_wgs84=polygon,
        soil_type=soil_type,
    )

@app.post("/v2/mesia/{plot_id}")
def post_mesia_spectrum_observatory(
    plot_id: str,
    payload: Dict[str, Any],
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    Runs MESIA spectrum scan using explicitly provided parcel geoJson and soilType.
    Authority is derived strictly from server-authenticated PlotNamespace.
    """
    from services.agribrain.mesia.service import MesiaProductionService
    spoofed_keys = {"tenant_id", "tenantId", "farm_id", "farmId"}
    if any(k in payload for k in spoofed_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client payload must not specify tenant_id, tenantId, farm_id, or farmId. Authority is derived exclusively from authenticated tokens.",
        )
    polygon = None
    soil_type = payload.get("soil_type") or payload.get("soilType")
    geo_json = payload.get("geo_json") or payload.get("geoJson")
    if geo_json and isinstance(geo_json, dict):
        geom = geo_json.get("geometry", geo_json)
        raw_coords = geom.get("coordinates", [])
        if raw_coords and isinstance(raw_coords[0], list):
            # GeoJSON is [lon, lat] -> convert to [(lat, lon), ...]
            polygon = [(float(pt[1]), float(pt[0])) for pt in raw_coords[0] if len(pt) >= 2]

    return MesiaProductionService.scan_plot_spectrum(
        plot_namespace=namespace,
        polygon_wgs84=polygon,
        soil_type=soil_type,
    )

@app.get("/eo/sar-timeseries")
def get_sar_timeseries(lat: float, lng: float, days: int = 30):
    """
    Get 30-day Sentinel-1 SAR time-series (VV/VH).
    Cloud-independent data for trend analysis.
    """
    from eo.sentinel import fetch_sar_timeseries
    result = fetch_sar_timeseries(lat, lng, days)
    if result:
        return result
    return {"error": "Could not fetch SAR timeseries", "lat": lat, "lng": lng}

@app.get("/eo/sar-biomass")
def get_sar_biomass(lat: float, lng: float):
    """
    Get crop biomass estimate from Sentinel-1 VH backscatter.
    Higher VH = denser/taller vegetation.
    """
    from eo.sentinel import fetch_biomass_estimate
    result = fetch_biomass_estimate(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch biomass data", "lat": lat, "lng": lng}

@app.get("/eo/sar-flood")
def get_sar_flood(lat: float, lng: float):
    """
    Detect flooded vs dry soil using Sentinel-1 SAR.
    Low VV indicates water (specular reflection).
    """
    from eo.sentinel import detect_flood_status
    result = detect_flood_status(lat, lng)
    if result:
        return result
    return {"error": "Could not detect flood status", "lat": lat, "lng": lng}

@app.get("/eo/sar-emergence")
def get_sar_emergence(lat: float, lng: float):
    """
    Detect early crop emergence from VH temporal rise.
    SAR sees crop structure BEFORE NDVI reacts.
    """
    from eo.sentinel import detect_crop_emergence
    result = detect_crop_emergence(lat, lng)
    if result:
        return result
    return {"error": "Could not detect crop emergence", "lat": lat, "lng": lng}

@app.get("/eo/historical-weather")
def get_historical_weather(lat: float, lng: float, start_date: str, end_date: str):
    """
    Get ERA5 historical climate data via Open-Meteo.
    Useful for training data and climate pattern analysis.
    """
    from eo.sentinel import fetch_historical_weather
    result = fetch_historical_weather(lat, lng, start_date, end_date)
    if result:
        return result
    return {"error": "Could not fetch historical weather", "lat": lat, "lng": lng}

@app.get("/eo/fire-risk")
def get_fire_risk(lat: float, lng: float, radius_km: int = 50):
    """
    Get active fire data from NASA FIRMS (MODIS/VIIRS).
    Returns fire detections within radius in the last 7 days.
    """
    from eo.sentinel import fetch_fire_risk
    result = fetch_fire_risk(lat, lng, radius_km)
    if result:
        return result
    return {"error": "Could not fetch fire data", "lat": lat, "lng": lng}

@app.get("/eo/all")
def get_all_eo_data(lat: float, lng: float):
    """
    Fetch ALL available EO data for a location in one call.
    Combines: Sentinel-2 indices, Sentinel-1 SAR, soil, solar, air quality, elevation, fire risk
    """
    from eo.sentinel import fetch_all_eo_data
    return fetch_all_eo_data(lat, lng)

@app.get("/eo/soil-layers")
def get_soil_moisture_layers(lat: float, lng: float):
    """
    Get multi-layer soil moisture from Open-Meteo (ERA5-Land).
    Returns moisture at 0-7cm, 7-28cm, 28-100cm, and 100-255cm depths.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_soil_moisture_layers
    result = fetch_soil_moisture_layers(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch soil moisture layers", "lat": lat, "lng": lng}

@app.get("/eo/water-balance")
def get_water_balance(lat: float, lng: float, days_past: int = 30, days_future: int = 7):
    """
    Get Water Balance (Precipitation - ET0) for past and future.
    Used for Water Stress Analysis.
    """
    from eo.sentinel import fetch_water_balance
    result = fetch_water_balance(lat, lng, days_past, days_future)
    if result:
        return result
    return {"error": "Could not calculate water balance", "lat": lat, "lng": lng}

@app.get("/eo/land-cover")
def get_land_cover(lat: float, lng: float):
    """
    Get Land Cover classification (Sentinel-2 SCL).
    """
    from eo.sentinel import fetch_land_cover
    result = fetch_land_cover(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch land cover", "lat": lat, "lng": lng}

@app.get("/eo/sar-analysis")
def get_sar_analysis(lat: float, lng: float):
    """
    Get comprehensive SAR analysis (Moisture, Biomass, Flood, Emergence).
    Aggregates multiple SAR-based metrics into one response.
    """
    from eo.sentinel import (
        fetch_soil_moisture_proxy, 
        fetch_biomass_estimate, 
        detect_flood_status, 
        detect_crop_emergence
    )
    
    # We could run these in parallel threads for speed, but for now sequential is fine or
    # reliance on Sentinel Hub cache will make subsequent calls fast.
    
    moisture = fetch_soil_moisture_proxy(lat, lng)
    biomass = fetch_biomass_estimate(lat, lng)
    flood = detect_flood_status(lat, lng)
    emergence = detect_crop_emergence(lat, lng)
    
    return {
        "moisture": moisture if moisture else {"error": "Unavailable"},
        "biomass": biomass if biomass else {"error": "Unavailable"},
        "flood": flood if flood else {"error": "Unavailable"},
        "emergence": emergence if emergence else {"error": "Unavailable"}
    }

@app.get("/eo/environment-analysis")
def get_environment_analysis(lat: float, lng: float):
    """
    Get environmental context (Air Quality, Fire Risk, Elevation).
    """
    from eo.sentinel import (
        fetch_air_quality,
        fetch_fire_risk,
        fetch_elevation
    )
    
    air = fetch_air_quality(lat, lng)
    fire = fetch_fire_risk(lat, lng)
    elevation = fetch_elevation(lat, lng)
    
    return {
        "air_quality": air if air else {"error": "Unavailable"},
        "fire_risk": fire if fire else {"error": "Unavailable"},
        "elevation": elevation if elevation else {"error": "Unavailable"}
    }

@app.get("/eo/soil-properties")
def get_soil_properties(lat: float, lng: float):
    """
    Get soil properties from SoilGrids (ISRIC).
    Returns: pH, organic carbon, nitrogen, clay/sand/silt content, CEC.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_soil_properties
    result = fetch_soil_properties(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch soil properties", "lat": lat, "lng": lng}

@app.get("/eo/solar")
def get_solar_radiation(lat: float, lng: float, days: int = 7):
    """
    Get solar radiation and GDD (Growing Degree Days) from NASA POWER.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_solar_radiation
    result = fetch_solar_radiation(lat, lng, days)
    if result:
        return result
    return {"error": "Could not fetch solar data", "lat": lat, "lng": lng}

@app.get("/eo/elevation")
def get_elevation(lat: float, lng: float):
    """
    Get elevation data from Open-Elevation API.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_elevation
    result = fetch_elevation(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch elevation", "lat": lat, "lng": lng}

@app.get("/eo/air-quality")
def get_air_quality(lat: float, lng: float):
    """
    Get air quality data from Open-Meteo.
    Returns: PM2.5, PM10, Ozone, NO2, SO2, AQI.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_air_quality
    result = fetch_air_quality(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch air quality", "lat": lat, "lng": lng}

@app.get("/eo/weather")
def get_openweather(lat: float, lng: float):
    """
    Get current weather from OpenWeatherMap.
    Uses your OPENWEATHER_API_KEY from .env file.
    """
    from eo.sentinel import fetch_openweather_data
    result = fetch_openweather_data(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch weather", "lat": lat, "lng": lng}

@app.get("/eo/forecast")
def get_openweather_forecast(lat: float, lng: float):
    """
    Get 5-day weather forecast from OpenWeatherMap.
    Uses your OPENWEATHER_API_KEY from .env file.
    """
    from eo.sentinel import fetch_openweather_forecast
    result = fetch_openweather_forecast(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch forecast", "lat": lat, "lng": lng}


# ============================================================================
# EO CACHE MONITORING
# ============================================================================

@app.get("/eo/cache/stats")
def get_cache_stats():
    """Get EO cache statistics — cache layer health and hit rates."""
    try:
        from eo.cache import cache_stats
        return cache_stats()
    except ImportError:
        return {"status": "disabled", "reason": "Cache module not available"}

@app.post("/eo/cache/invalidate")
def invalidate_cache(source: Optional[str] = None, lat: Optional[float] = None,
                     lng: Optional[float] = None):
    """Manually invalidate EO cache entries. Use with caution."""
    try:
        from eo.cache import cache_invalidate
        deleted = cache_invalidate(source, lat, lng)
        return {"status": "ok", "deleted": deleted}
    except ImportError:
        return {"status": "disabled", "reason": "Cache module not available"}



# ============================================================================
# PHENOLOGY & GROWTH STAGE ENDPOINTS
# ============================================================================

@app.get("/phenology/calendar")
def get_crop_calendar_endpoint(crop: str):
    """
    Get crop calendar with planting/harvest windows and GDD requirements.
    Available crops: tomato, wheat, corn, potato, olive, grape, citrus, date_palm
    """
    from eo.sentinel import get_crop_calendar
    result = get_crop_calendar(crop)
    if result:
        return result
    return {"error": f"No calendar found for crop: {crop}", "available_crops": ["tomato", "wheat", "corn", "potato", "olive", "grape", "citrus", "date_palm"]}

@app.get("/phenology/kc")
def get_crop_kc_endpoint(crop: str, growth_stage: str = None):
    """
    Get FAO crop coefficients (Kc) for water requirement estimation.
    Available crops: tomato, wheat, corn, potato, olive, grape, citrus, date_palm, cotton, rice, soybean, sunflower, barley
    """
    from eo.sentinel import get_crop_kc
    result = get_crop_kc(crop, growth_stage)
    if result:
        return result
    return {"error": f"No Kc found for crop: {crop}"}

@app.get("/phenology/gdd")
def get_gdd_accumulation(lat: float, lng: float, crop: str = "tomato", days: int = 90):
    """
    Calculate cumulative Growing Degree Days (GDD) for a location.
    Returns current growth stage based on GDD accumulation.
    """
    from eo.sentinel import fetch_gdd_accumulation
    result = fetch_gdd_accumulation(lat, lng, crop, days)
    if result:
        return result
    return {"error": "Could not calculate GDD", "lat": lat, "lng": lng}

@app.get("/phenology/all")
def get_comprehensive_phenology(lat: float, lng: float, crop: str = "tomato"):
    """
    Get comprehensive phenology data: crop calendar, Kc values, GDD, and current growth stage.
    """
    from eo.sentinel import fetch_comprehensive_phenology
    return fetch_comprehensive_phenology(lat, lng, crop)

@app.get("/phenology/crops")
def get_available_crops():
    """
    Get list of all supported crops with their data.
    """
    from eo.sentinel import CROP_CALENDARS, CROP_KC_COEFFICIENTS
    return {
        "crops_with_calendar": list(CROP_CALENDARS.keys()),
        "crops_with_kc": list(CROP_KC_COEFFICIENTS.keys()),
        "source": "fao-crop-data"
    }

@app.post("/tools/ml/predict_yield")
def predict_yield(req: YieldRequest):
    """Legacy ML endpoint - now routes to Yield Prediction AI"""
    return {
        "field_id": req.field_id,
        "crop": req.crop,
        "predicted_yield_t_ha": 45.0,
        "confidence": 0.82,
        "source": "LEGACY_FALLBACK",
        "message": "Use /orchestrate for AI Organism routing"
    }

# ============================================================================
# AI Organism Endpoints
# ============================================================================

@app.post("/orchestrate", response_model=OrchestrationResponse)
def orchestrate(req: OrchestrationRequest):
    """
    Main AI Organism endpoint.
    Routes query to specialized AIs based on intent classification.
    Returns structured results for LLM synthesis.
    """
    # Add crop to context
    context = req.context.copy()
    context["crop"] = req.crop
    
    # Route through orchestrator
    result = orchestrator.route_query(req.query, context)
    
    return OrchestrationResponse(
        detected_intents=result["detected_intents"],
        routed_to=result["routed_to"],
        ai_results=result["results"],
        needs_llm_synthesis=True,  # LLM should always synthesize
        timestamp=datetime.now().isoformat()
    )


# ============================================================================
# /v2/satellite-tile  RGB Tile Runtime (Weekly Cache)
# ============================================================================

class SatelliteTileRequest(BaseModel):
    """Request for satellite RGB tile."""
    plot_id: str
    lat: float
    lng: float
    polygon: Optional[Any] = None
    force: bool = False

@app.post("/v2/satellite-tile")
def api_satellite_tile(req: SatelliteTileRequest):
    """
    Fetch a Sentinel-2 True Color RGB tile for a plot polygon.
    Cached for 7 days. Frontend calls once on plot page load.
    """
    try:
        from layer0.perception.satellite_rgb.tile_runtime import (
            fetch_rgb_tile, get_tile_metadata, _is_cache_valid
        )
        
        if not req.force and _is_cache_valid(req.plot_id):
            meta = get_tile_metadata(req.plot_id)
            return {"status": "cached", "plot_id": req.plot_id, "metadata": meta}
        
        image_bytes = fetch_rgb_tile(
            plot_id=req.plot_id, lat=req.lat, lng=req.lng,
            polygon_coords=req.polygon, force=req.force,
        )
        
        if image_bytes:
            meta = get_tile_metadata(req.plot_id)
            return {"status": "fetched", "plot_id": req.plot_id, "tile_size_bytes": len(image_bytes), "metadata": meta}
        else:
            return {"status": "unavailable", "plot_id": req.plot_id, "message": "Could not fetch satellite tile."}
    except Exception as e:
        return {"status": "error", "plot_id": req.plot_id, "error": str(e)}

@app.post("/v2/satellite-vision")
def api_satellite_vision(req: SatelliteTileRequest):
    """Run LLM vision analysis on a cached satellite tile."""
    try:
        from layer0.perception.satellite_rgb.tile_runtime import get_cached_tile, get_cached_vision, cache_vision_result, TILE_CACHE_DIR, _plot_id_hash
        from layer0.perception.satellite_rgb.llm_vision import analyze_tile, _CIRCUIT_TRIPPED_AT
        import layer0.perception.satellite_rgb.llm_vision as llm_mod
        import json
        import os
        import time

        # Force reset circuit breaker on each call (it was tripped from stale session)
        llm_mod._CIRCUIT_TRIPPED_AT = None

        # 1. In-memory cache check
        cached_vision = get_cached_vision(req.plot_id)
        if cached_vision:
            print(f"[VISION_API] In-memory cache hit for plot {req.plot_id}")
            return {"status": "analyzed", "plot_id": req.plot_id, "vision": cached_vision}

        # 2. Filesystem cache check
        vision_cache_path = os.path.join(TILE_CACHE_DIR, f"vision_{_plot_id_hash(req.plot_id)}.json")
        if not req.force and os.path.exists(vision_cache_path):
            try:
                with open(vision_cache_path, "r") as f:
                    cached_data = json.load(f)
                if (time.time() - cached_data.get("_cached_at", 0)) < 3 * 24 * 3600: # 3 days TTL
                    print(f"[VISION_API] Filesystem cache hit for plot {req.plot_id}")
                    cache_vision_result(req.plot_id, cached_data["vision"])
                    return {"status": "analyzed", "plot_id": req.plot_id, "vision": cached_data["vision"]}
            except Exception as ce:
                print(f"[VISION_API] File cache read error: {ce}")

        image_bytes = get_cached_tile(req.plot_id)
        if not image_bytes:
            return {"status": "no_tile", "plot_id": req.plot_id, "message": "No cached tile. Call /v2/satellite-tile first."}

        print(f"[VISION_API] Running vision on {len(image_bytes)} bytes for plot {req.plot_id}")
        result = analyze_tile(image_bytes=image_bytes, plot_context={"region": "Algeria"})

        if result:
            vision_dict = {
                "crop_rows_detected": result.crop_rows_detected,
                "estimated_crop_type": result.estimated_crop_type,
                "vegetation_pct": result.vegetation_pct,
                "bare_soil_pct": result.bare_soil_pct,
                "emergence_stage": result.emergence_stage,
                "weed_pressure": result.weed_pressure,
                "confidence": result.confidence,
                "field_uniformity": result.field_uniformity,
                "irrigation_visible": result.irrigation_visible,
                "explanation": result.raw_explanation,
            }

            # Cache in-memory and to file
            cache_vision_result(req.plot_id, vision_dict)
            try:
                os.makedirs(TILE_CACHE_DIR, exist_ok=True)
                with open(vision_cache_path, "w") as f:
                    json.dump({"vision": vision_dict, "_cached_at": time.time()}, f)
            except Exception as ce:
                print(f"[VISION_API] File cache write error: {ce}")

            return {
                "status": "analyzed", "plot_id": req.plot_id,
                "vision": vision_dict,
            }
        else:
            return {"status": "vision_unavailable", "plot_id": req.plot_id, "message": "LLM vision analysis failed or rate-limited."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "plot_id": req.plot_id, "error": str(e)}

class PlotDNARequest(BaseModel):
    plot_id: str
    lat: float
    lng: float
    polygon: Optional[Any] = None

@app.post("/v2/plot-dna")
def api_plot_dna(
    req: PlotDNARequest,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    Returns the Plot DNA Decadal Inversion data using REAL EO DATA.
    Includes the biophysical traits, fluid topologies, and exhaustion index.
    """
    if req.plot_id and req.plot_id.strip() != namespace.plot_id.strip():
        raise HTTPException(
            status_code=403,
            detail="Payload plot_id does not match authenticated token namespace",
        )
    try:
        from layer0.calibration.generative_inversion import trigger_dna_sequencing
        from layer10_sire.surfaces.fluid_topology import generate_fluid_payload
        
        # Pull actual EO data using the plot geometry
        dna_sequence = trigger_dna_sequencing(req.plot_id, req.lat, req.lng, req.polygon)
        fluid_data = generate_fluid_payload(req.plot_id, req.lat, req.lng, req.polygon)
        
        # DNA 4.0: Persist to cache for downstream Kalman injection
        try:
            from layer0.calibration.dna_cache import save_dna_cache
            save_dna_cache(req.plot_id, dna_sequence)
            print(f"[DNA] Cached DNA sequence for plot {req.plot_id}")
        except Exception as cache_err:
            print(f"[DNA] Cache write failed (non-critical): {cache_err}")
        
        # Plot DNA 3.0: Multiverse & Terraforming ROI
        from layer0.calibration.monte_carlo_engine import MonteCarloMultiverse, TerraformingCalculator
        mc_engine = MonteCarloMultiverse(dna_sequence)
        multiverse_data = mc_engine.simulate_multiverse()
        
        tf_calc = TerraformingCalculator(dna_sequence)
        terraforming_roi = {
            "biochar": tf_calc.calculate_roi("biochar"),
            "tiling": tf_calc.calculate_roi("tiling"),
            "cover_crop": tf_calc.calculate_roi("cover_crop")
        }
        
        return {
            "status": "success",
            "plot_id": req.plot_id,
            "dna": dna_sequence,
            "dna_cached": True,
            "fluid_topology": fluid_data,
            "multiverse": multiverse_data,
            "terraforming": terraforming_roi
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "type": "PlotDNAError"})

@app.get("/v2/satellite-tile-image/{plot_id}")
def api_satellite_tile_image(
    plot_id: str,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Serve the cached satellite tile as a PNG image."""
    from fastapi.responses import Response
    try:
        from layer0.perception.satellite_rgb.tile_runtime import get_cached_tile, get_tile_metadata
        image_bytes = get_cached_tile(plot_id)
        if not image_bytes:
            raise HTTPException(status_code=404, detail="No cached tile for this plot")
        meta = get_tile_metadata(plot_id) or {}
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=604800",  # 7 days
                "X-Tile-Source": meta.get("source", "sentinel-2-l2a"),
                "X-Tile-Date": meta.get("fetched_date", ""),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v2/satellite-tile-meta/{plot_id}")
def api_satellite_tile_meta(
    plot_id: str,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Get metadata about a cached satellite tile."""
    try:
        from layer0.perception.satellite_rgb.tile_runtime import get_tile_metadata, _is_cache_valid
        meta = get_tile_metadata(plot_id)
        if not meta:
            return {"exists": False, "plot_id": plot_id}
        return {
            "exists": True,
            "plot_id": plot_id,
            "fresh": _is_cache_valid(plot_id),
            **meta,
        }
    except Exception as e:
        return {"exists": False, "plot_id": plot_id, "error": str(e)}


# ============================================================================
# /v2/plot-intelligence  Unified Dashboard Data Endpoint
# ============================================================================
# Single endpoint that collects ALL intelligence for the plot overview.
# The frontend calls this ONCE. AgriBrain handles all data collection.
# ============================================================================

class PlotIntelligenceRequest(BaseModel):
    """Request for plot intelligence data."""
    lat: float = 36.0
    lng: float = 3.0
    crop: Optional[str] = "generic"
    polygon: Optional[Any] = None
    expert_mode: bool = False
    days_past: int = 7
    days_future: int = 7
    plant_date: Optional[str] = None        # ISO date string (e.g. "2026-03-15")
    crop_administrative_status: Optional[str] = None  # Workflow state, never phenology evidence
    force_refresh_weather: bool = False
    plot_id: Optional[str] = None           # Plot ID for DNA-calibrated physics injection
    # GAP 2: User-declared ground truth from frontend
    irrigation_type: Optional[str] = None   # "Drip", "Sprinkler", "Rainfed", etc.
    soil_type: Optional[str] = None         # "Sandy", "Loam", "Clay", etc.
    soil_analysis: Optional[Dict] = None    # Lab results: {ph, nitrogen_ppm, ...}
    physical_constraints: Optional[List[str]] = None  # ["Slope present", "Salinity"]
    area_ha: Optional[float] = None         # Real plot area in hectares
    # GAP SENSOR: Live IoT field telemetry from DB
    sensor_readings: Optional[List[Dict]] = None  # [{device_id, type, latest: {temperature, soil_moisture, ...}}]


@app.post("/v2/plot-intelligence")
def api_plot_intelligence(
    req: PlotIntelligenceRequest,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """
    Unified Plot Intelligence Endpoint.
    Delegates data fetching & timeline to pi_helpers for testability.
    """
    if req.plot_id and req.plot_id.strip() != namespace.plot_id.strip():
        raise HTTPException(
            status_code=403,
            detail="Payload plot_id does not match authenticated token namespace",
        )
    if not req.plot_id:
        req.plot_id = namespace.plot_id
    import traceback
    import time as _time
    from datetime import timezone
    from app.pi_helpers import fetch_all_sources, build_timeline, compute_phenology, hargreaves_et0 as _hargreaves_et0
    
    _t0 = _time.perf_counter()
    lat, lng = req.lat, req.lng
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    # ---- Data Collection (delegated to pi_helpers) ----
    results = fetch_all_sources(lat, lng, req.days_past, req.days_future, plot_id=req.plot_id)
    _t_fetch = _time.perf_counter()
    print(f"[PERF] /v2/plot-intelligence: fetch_all_sources = {_t_fetch - _t0:.2f}s")

    weather_data  = results.get("weather")
    forecast_data = results.get("forecast")
    indices_data  = results.get("indices")
    sar_ts_data   = results.get("sar_ts")
    sar_data      = results.get("sar")
    soil_data     = results.get("soil")
    water_data    = results.get("water")
    hist_weather  = results.get("hist")
    ndvi_ts       = results.get("ndvi_ts")

    def _safe_float(v, default=None):
        if v is None:
            return default
        try:
            import math
            f = float(v)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (ValueError, TypeError):
            return default

    if indices_data and isinstance(indices_data, dict):
        indices_data = dict(indices_data)
        for k in ["ndvi", "evi", "ndwi", "ndmi"]:
            if k in indices_data:
                indices_data[k] = _safe_float(indices_data[k])
        results["indices"] = indices_data


    # ---- GAP 2: Override SoilGrids with user-declared lab data ----
    user_soil_override = False
    if req.soil_analysis and isinstance(req.soil_analysis, dict):
        has_values = any(v is not None and v != 0 for k, v in req.soil_analysis.items() if k != "sample_date")
        if has_values:
            user_soil_override = True
            # Merge user lab data into soil_data (overrides SoilGrids proxy)
            if not soil_data or not isinstance(soil_data, dict):
                soil_data = {}
            soil_data["user_declared"] = True
            soil_data["is_generic_fallback"] = False  # User data is NOT a fallback
            for k, v in req.soil_analysis.items():
                if v is not None:
                    soil_data[k] = v
            print(f"[PI] Using user-declared soil analysis (overrides SoilGrids)")

    # Attach irrigation/management context for engine use
    user_irrigation = req.irrigation_type
    user_soil_type = req.soil_type
    user_constraints = req.physical_constraints or []
    user_area_ha = req.area_ha

    # ---- GAP SENSOR: Process live IoT sensor telemetry ----
    sensor_context = {
        "count": 0,
        "active": 0,
        "types": [],
        "soil_moisture_pct": None,
        "soil_ec_ds_m": None,
        "field_temperature_c": None,
        "field_humidity_pct": None,
        "field_wind_speed_ms": None,
        "field_rainfall_mm": None,
        "data_source": "none",
    }
    if req.sensor_readings and isinstance(req.sensor_readings, list):
        sensor_context["count"] = len(req.sensor_readings)
        active_sensors = [s for s in req.sensor_readings if s.get("status") == "ACTIVE"]
        sensor_context["active"] = len(active_sensors)
        sensor_context["types"] = list(set(s.get("type", "") for s in req.sensor_readings))

        for sr in req.sensor_readings:
            latest = sr.get("latest", {})
            if not latest:
                continue
            sr_type = sr.get("type", "")

            # Soil moisture sensor  override satellite proxy
            if sr_type == "MOISTURE" and latest.get("soil_moisture") is not None:
                sensor_context["soil_moisture_pct"] = latest["soil_moisture"]
                sensor_context["data_source"] = "field_sensor"
                print(f"[PI] Sensor soil moisture: {latest['soil_moisture']}% (overrides satellite proxy)")

            # EC sensor  salinity context
            if sr_type == "EC" and latest.get("ec") is not None:
                sensor_context["soil_ec_ds_m"] = latest["ec"]
                print(f"[PI] Sensor EC: {latest['ec']} dS/m")

            # Weather station  supplement/override remote weather
            if sr_type == "WEATHER":
                if latest.get("temperature") is not None:
                    sensor_context["field_temperature_c"] = latest["temperature"]
                if latest.get("humidity") is not None:
                    sensor_context["field_humidity_pct"] = latest["humidity"]
                if latest.get("wind_speed") is not None:
                    sensor_context["field_wind_speed_ms"] = latest["wind_speed"]
                if latest.get("rainfall") is not None:
                    sensor_context["field_rainfall_mm"] = latest["rainfall"]
                sensor_context["data_source"] = "field_sensor"
                print(f"[PI] Field weather station active: T={latest.get('temperature')}C, H={latest.get('humidity')}%")

            # Temp sensor  field temperature
            if sr_type in ("TEMP", "MOISTURE") and latest.get("temperature") is not None:
                if sensor_context["field_temperature_c"] is None:
                    sensor_context["field_temperature_c"] = latest["temperature"]

        print(f"[PI] Sensor context: {sensor_context['active']}/{sensor_context['count']} active, types={sensor_context['types']}")


    # ---- Build Timeline (delegated to pi_helpers) ----
    timeline, ndvi_records, hist_records, forecast_records = build_timeline(
        results, lat, req.days_past, req.days_future,
        plant_date=req.plant_date,
        plot_id=req.plot_id,
    )

    # Derive real statuses from actual data presence
    temp_str = ""
    if weather_data and isinstance(weather_data, dict):
        t = weather_data.get("temperature", {})
        if isinstance(t, dict):
            temp_str = f"{t.get('current', '--')}C, Humidity {weather_data.get('humidity', '--')}%, Wind {weather_data.get('wind', {}).get('speed_ms', '--')} m/s"
        else:
            temp_str = f"{t}C" if t else "Active"

    raw_ndvi = indices_data.get("ndvi", 0.0) if indices_data else 0.0
    raw_evi = indices_data.get("evi", 0.0) if indices_data else 0.0
    try:
        ndvi_val = float(raw_ndvi) if raw_ndvi is not None else 0.0
    except (ValueError, TypeError):
        ndvi_val = 0.0
    try:
        evi_val = float(raw_evi) if raw_evi is not None else 0.0
    except (ValueError, TypeError):
        evi_val = 0.0

    # ── Kalman fallback: use propagated NDVI when S2 is missing ──────────
    # The Kalman filter produces daily gap-filled NDVI from weather-driven
    # crop growth models. When satellite coverage is absent, this is the
    # best available estimate — not 0.0.
    ndvi_from_kalman = False
    kalman_ndvi_confidence = 0.0
    if (ndvi_val == 0 or not indices_data) and ndvi_records:
        # Find today's or latest Kalman record
        today_str = now.strftime("%Y-%m-%d")
        kalman_today = next((r for r in reversed(ndvi_records)
                            if r.get("date") == today_str), None)
        if not kalman_today:
            kalman_today = ndvi_records[-1]  # Latest available
        if kalman_today:
            try:
                k_val = float(kalman_today.get("ndvi", 0.0))
            except (ValueError, TypeError):
                k_val = 0.0
            if k_val > 0.0:
                ndvi_val = k_val
                try:
                    kalman_ndvi_confidence = float(kalman_today.get("confidence", 0.5))
                except (ValueError, TypeError):
                    kalman_ndvi_confidence = 0.5
                ndvi_from_kalman = True
                print(f"[PI] Kalman fallback NDVI: {ndvi_val:.4f} "
                      f"(conf={kalman_ndvi_confidence:.3f}, "
                      f"days_since_obs={kalman_today.get('days_since_obs', '?')})")


    sources_active = sum(1 for x in [weather_data, indices_data, sar_data] if x)

    # GAP SENSOR: Count field sensors as an additional data source
    has_active_sensors = sensor_context["active"] > 0
    if has_active_sensors:
        sources_active += 1  # Field sensors count as a source

    # Derive today's ET0 from water balance records
    today_str = now.strftime("%Y-%m-%d")
    et0_today = 0.0
    if water_data and isinstance(water_data, dict):
        for rec in water_data.get("records", []):
            if rec.get("date") == today_str:
                et0_today = rec.get("et0") or 0.0
                break
        if et0_today == 0.0:
            # fallback: last historical record
            hist_recs = [r for r in water_data.get("records", []) if r.get("type") == "historical"]
            if hist_recs:
                et0_today = hist_recs[-1].get("et0") or 0.0

    # Biotic risk from weather (temp 20-30C + humidity >70% = high risk window)
    biotic_status = "Low"
    biotic_detail = "Low risk"
    temp_now = 15.0
    hum_now = 50
    if weather_data:
        temp_now = weather_data.get("temperature", {}).get("current", 15) if isinstance(weather_data.get("temperature"), dict) else 15
        hum_now = weather_data.get("humidity", 50)

    # GAP SENSOR: Field sensor temp/humidity override remote API (higher accuracy)
    if sensor_context.get("field_temperature_c") is not None:
        temp_now = sensor_context["field_temperature_c"]
        print(f"[PI] Using field sensor temperature: {temp_now}C (overrides remote API)")
    if sensor_context.get("field_humidity_pct") is not None:
        hum_now = sensor_context["field_humidity_pct"]
        print(f"[PI] Using field sensor humidity: {hum_now}% (overrides remote API)")

    if 20 <= temp_now <= 32 and hum_now >= 70:
        biotic_status = "High"
        biotic_detail = f"High: T={temp_now:.1f}C, RH={hum_now}%"
    elif 15 <= temp_now <= 32 and hum_now >= 55:
        biotic_status = "Moderate"
        biotic_detail = f"Moderate: T={temp_now:.1f}C, RH={hum_now}%"
    else:
        biotic_detail = f"Low: T={temp_now:.1f}C, RH={hum_now}%"
    
    # Tag data source for biotic risk
    if sensor_context.get("field_temperature_c") is not None or sensor_context.get("field_humidity_pct") is not None:
        biotic_detail += " [field sensor]"
            
    # Hargreaves ET0 Fallback -- use real temp extremes when available
    et0_is_fallback = False
    if et0_today == 0.0:
        et0_is_fallback = True
        if weather_data and isinstance(weather_data, dict):
            t_info = weather_data.get("temperature", {})
            t_max = t_info.get("max")
            t_min = t_info.get("min")
            # Only use synthetic as absolute last resort
            if t_max is None:
                t_max = temp_now + 5
            if t_min is None:
                t_min = temp_now - 5
        else:
            t_max = temp_now + 5
            t_min = temp_now - 5
            
        doy = now.timetuple().tm_yday
        et0_today = _hargreaves_et0(t_max, t_min, lat, doy)

    # Extract explicit rain probability for L0 expert mode
    rain_prob_today = 0
    if forecast_records and len(forecast_records) > 0:
        rain_prob_today = forecast_records[0].get("rain_prob", 0)

    # L4 Soil Fallback Logic (respects user-declared override)
    is_fallback = soil_data.get('is_generic_fallback') if isinstance(soil_data, dict) else False
    if user_soil_override:
        proxy_reason = "User Lab Analysis (Ground Truth)"
        conf_mod = 1.2  # Highest confidence  real lab data
        is_fallback = False
    elif is_fallback:
        proxy_reason = "Assumed Baseline (Regional Profile)"
        conf_mod = 0.1
    else:
        proxy_reason = "Regional Soil Survey Baseline"
        conf_mod = 1.0

    wind_str = f"{weather_data.get('wind', {}).get('speed_ms', '--')} m/s" if weather_data else "--"

    # ---- Helper functions for REAL computed values (no synthetic data) ----

    def _compute_canopy_cover(ndvi):
        """Beer-Lambert canopy cover from NDVI via LAI inversion.
        CC = 1 - exp(-k * LAI), where LAI ~ -ln(1 - NDVI) / 0.5 for k=0.5
        This is a physically-based conversion, not a linear fabrication."""
        import math
        if not ndvi or ndvi <= 0:
            return 0.0
        ndvi_c = min(max(ndvi, 0.01), 0.95)  # Clamp to avoid log(0)
        lai = -math.log(1.0 - ndvi_c) / 0.5
        cc = (1.0 - math.exp(-0.5 * lai)) * 100.0
        return round(min(cc, 99.0), 1)

    def _compute_spatial_variability(sar_ts, ndvi_timeseries):
        """Compute spatial variability from SAR temporal coefficient of variation.
        Returns 'Low', 'Moderate', or 'High' based on actual data spread."""
        def _to_floats(raw_vals):
            """Coerce values to float, skipping non-numeric."""
            result = []
            for v in raw_vals:
                try:
                    result.append(float(v))
                except (TypeError, ValueError):
                    continue
            return result

        if sar_ts and isinstance(sar_ts, dict):
            ts_list = sar_ts.get("timeseries", [])
            if ts_list and len(ts_list) >= 3:
                vv_raw = [e.get("vv_db") for e in ts_list if e.get("vv_db") is not None]
                vv_vals = _to_floats(vv_raw)
                if len(vv_vals) >= 3:
                    mean_vv = sum(vv_vals) / len(vv_vals)
                    if mean_vv != 0:
                        std_vv = (sum((v - mean_vv) ** 2 for v in vv_vals) / len(vv_vals)) ** 0.5
                        cv = abs(std_vv / mean_vv)
                        if cv > 0.15:
                            return "High"
                        elif cv > 0.08:
                            return "Moderate"
                        return "Low"
        # NDVI timeseries fallback
        if ndvi_timeseries and isinstance(ndvi_timeseries, dict):
            obs = ndvi_timeseries.get("data", [])
            if obs and len(obs) >= 3:
                ndvi_raw = [e.get("ndvi") for e in obs if e.get("ndvi") is not None]
                vals = _to_floats(ndvi_raw)
                if len(vals) >= 3:
                    mean_n = sum(vals) / len(vals)
                    if mean_n > 0:
                        std_n = (sum((v - mean_n) ** 2 for v in vals) / len(vals)) ** 0.5
                        cv = std_n / mean_n
                        if cv > 0.2:
                            return "High"
                        elif cv > 0.1:
                            return "Moderate"
                        return "Low"
        return "Unknown (insufficient data)"


    def _build_fusion_summary(wx, optical, sar):
        """Build an accurate fusion summary listing only sources that are actually present."""
        sources = []
        if optical:
            sources.append("satellite imagery (Sentinel-2)")
        if sar:
            sources.append("SAR radar (Sentinel-1)")
        if wx:
            sources.append("local weather")
        if len(sources) == 0:
            return "No data sources currently available. Awaiting satellite passes and weather feeds."
        elif len(sources) == 1:
            return f"Currently operating on {sources[0]} only. Other sources are temporarily unavailable."
        else:
            merged = ", ".join(sources[:-1]) + f" and {sources[-1]}"
            return f"Successfully merged {merged}."

    def _compute_yield_class(ndvi, has_indices, has_weather, biotic_risk):
        """Compute yield potential with honest confidence based on data availability."""
        if not ndvi or ndvi <= 0:
            return "Unknown", 0.1, "Insufficient data for yield estimation"
        cls = "High" if ndvi > 0.65 else "Moderate" if ndvi > 0.4 else "Low"
        # Confidence depends on data quality, not hardcoded
        conf = 0.3  # Base: NDVI-only proxy is low confidence
        reason = "NDVI empirical proxy only"
        if has_indices:
            if indices_data:
                conf += 0.25
                reason = "S2 NDVI direct observation"
            elif ndvi_from_kalman:
                conf += 0.20
                reason = "Kalman-propagated NDVI estimate"
        if has_weather:
            conf += 0.15
            reason += " + weather context"
        if biotic_risk == "High":
            cls = "Moderate" if cls == "High" else cls
            conf -= 0.1
            reason += " (downgraded: biotic pressure)"
        return cls, round(min(conf, 0.85), 2), reason

    # Engine card builder helper
    def _engine(id, name, icon, status, value, detail, expert_data=None):
        card = {
            "id": id, "name": name, "icon": icon,
            "status": status, "value": value, "detail": detail,
            # 'summary' always present so test assertions pass
            "summary": (expert_data or {}).get("farmer_summary") or detail or value,
            # 'data' always present for frontend consumption
            "data": expert_data or {},
        }
        if req.expert_mode and expert_data:
            card["expert"] = expert_data
        return card

    ndmi_raw = indices_data.get('ndmi') if indices_data else None
    try:
        ndmi_float = float(ndmi_raw) if ndmi_raw is not None else None
    except (ValueError, TypeError):
        ndmi_float = None

    engines = [
        _engine("L0", "Environment & Weather", "",
                "OK" if weather_data else "DEGRADED",
                temp_str or "No data",
                temp_str or "Awaiting weather data",
                {
                    "weather": weather_data, 
                    "data_freshness": "Live", 
                    "rain_prob": rain_prob_today, 
                    "temp_current": temp_now, 
                    "et0_today": et0_today,
                    "farmer_summary": f"Currently {temp_now:.1f}C with {rain_prob_today}% chance of rain. Weather data is updating live." if weather_data else "Awaiting live weather stream.",
                    "why_it_matters": "Real-time microclimate data drives all other agronomic models, from disease pressure to evapotranspiration.",
                    "expert_metrics": [
                        {"name": "Temperature", "value": f"{temp_now:.1f}C", "confidence": 0.95 if weather_data else 0.0, "reason": "Live API feed"},
                        {"name": "Humidity", "value": f"{hum_now}%", "confidence": 0.95 if weather_data else 0.0, "reason": "Live API feed"},
                        {"name": "Wind Speed", "value": f"{wind_str}", "confidence": 0.95 if weather_data else 0.0, "reason": "Live API feed"},
                        {"name": "Rain Probability", "value": f"{rain_prob_today}%", "confidence": 0.85 if forecast_records else 0.0, "reason": "NWP Forecast Model"},
                    ]
                }),
        _engine("L1", "Data Fusion", "Link",
                "OK" if sources_active >= 2 else "DEGRADED",
                "Multi-Source Fusion",
                f"{sources_active}/{4 if has_active_sensors else 3} sources active",
                {
                    "sources": {"weather": bool(weather_data), "optical": bool(indices_data), "sar": bool(sar_data), "field_sensors": has_active_sensors},
                    "sources_active": sources_active,
                    "farmer_summary": _build_fusion_summary(weather_data, indices_data, sar_data) + (" Field sensors are providing live ground-truth data." if has_active_sensors else ""),
                    "why_it_matters": "Combining multiple data sources reduces the error margin of any single sensor and bridges gaps during cloudy days.",
                    "expert_metrics": [
                        {"name": "Optical (S2)", "value": "Active" if indices_data else "Missing", "confidence": 0.9 if indices_data else 0.1, "reason": "Sentinel-2 L2A BOA Reflectance" if indices_data else "Cloud occlusion or gap"},
                        {"name": "Radar (S1)", "value": "Active" if sar_data else "Missing", "confidence": 0.85 if sar_data else 0.1, "reason": "Sentinel-1 GRD VV/VH" if sar_data else "Acquisition gap"},
                        {"name": "Weather", "value": "Active" if weather_data else "Missing", "confidence": 0.95 if weather_data else 0.1, "reason": "OpenMeteo Agronomic API" if weather_data else "API unreachable"},
                        {"name": "Field Sensors", "value": f"{sensor_context['active']} active" if has_active_sensors else "None", "confidence": 0.95 if has_active_sensors else 0.0, "reason": f"IoT ({', '.join(sensor_context['types'])})" if has_active_sensors else "No sensors registered"},
                    ]
                }),
        _engine("L2", "Vegetation Intelligence", "",
                "OK" if indices_data else ("OK" if ndvi_from_kalman else "DEGRADED"),
                "Active" if indices_data else ("Kalman Estimate" if ndvi_from_kalman else "No Data"),
                f"NDVI {ndvi_val:.2f}, EVI {evi_val:.2f}" if indices_data else (
                    f"NDVI {ndvi_val:.2f} (Kalman model, conf {kalman_ndvi_confidence:.0%})" if ndvi_from_kalman
                    else "No NDVI available (no satellite or Kalman data)"
                ),
                {
                    "ndvi": ndvi_val, "evi": evi_val, "ndvi_mean": ndvi_val,
                    "ndvi_source": "sentinel2" if indices_data else ("kalman" if ndvi_from_kalman else "none"),
                    "ndvi_support_type": "point" if indices_data else ("temporal_model" if ndvi_from_kalman else "none"),
                    "field_summary_eligible": False,
                    "support_coordinate": {"lat": lat, "lng": lng} if indices_data else None,
                    "observation_time": (
                        indices_data.get("observation_time")
                        or indices_data.get("scene_date")
                        or indices_data.get("date")
                        or indices_data.get("timestamp")
                    ) if indices_data else (kalman_today.get("date") if ndvi_from_kalman and kalman_today else None),
                    "kalman_confidence": kalman_ndvi_confidence if ndvi_from_kalman else None,
                    "canopy_cover_pct": _compute_canopy_cover(ndvi_val),
                    "spatial_variability": _compute_spatial_variability(sar_ts_data, ndvi_ts),
                    "ndmi": indices_data.get("ndmi") if indices_data else None,
                    "ndwi": indices_data.get("ndwi") if indices_data else None,
                    "farmer_summary": (
                        f"Point Sentinel-2 index at {lat:.4f}, {lng:.4f}: NDVI {ndvi_val:.2f}. This point observation is not a whole-field mean."
                        if indices_data
                        else f"Temporal crop-model estimate: NDVI {ndvi_val:.2f}. This is not a spatial field raster."
                        if ndvi_from_kalman
                        else "No Sentinel point index or temporal NDVI estimate is available."
                    ),
                    "why_it_matters": "This NDVI evidence describes its declared point or temporal support; field-wide conclusions require the field raster composite.",
                    "expert_metrics": [
                        {"name": "Mean NDVI", "value": f"{ndvi_val:.2f}",
                         "confidence": 0.9 if indices_data else (min(kalman_ndvi_confidence, 0.85) if ndvi_from_kalman else 0.1),
                         "reason": "Direct S2 point observation; not a field mean" if indices_data else (
                             f"Kalman filter propagation (days_since_obs={ndvi_records[-1].get('days_since_obs', '?') if ndvi_records else '?'})"
                             if ndvi_from_kalman else "No satellite or model data"
                         )},
                        {"name": "Canopy Cover", "value": f"{_compute_canopy_cover(ndvi_val)}%",
                         "confidence": 0.65 if indices_data else (0.6 if ndvi_from_kalman else 0.1),
                         "reason": "Beer-Lambert LAI inversion (k=0.5)"},
                        {"name": "Moisture (NDMI)", "value": f"{ndmi_float:.2f}" if ndmi_float is not None else "N/A",
                         "confidence": 0.9 if ndmi_float is not None else 0.0,
                         "reason": "Direct S2 observation" if ndmi_float is not None else "Requires SWIR bands, missing"},
                    ]
                }),

        _engine("L3", "Water Stress Engine", "",
                "OK" if water_data else "DEGRADED",
                "PM-Full" if water_data else "Hargreaves Fallback",
                f"ET0 {et0_today:.1f} mm/day" if water_data else f"ET0 {et0_today:.1f} mm/day (Awaiting PM model)",
                {
                    "et0_today": et0_today,
                    "deficit_mm": water_data.get("summary", {}).get("final_deficit_mm") if water_data else None,
                    "stress_index": water_data.get("summary", {}).get("stress_index") if water_data else None,
                    "farmer_summary": f"Your crop has a water deficit of {abs(water_data.get('summary', {}).get('final_deficit_mm') or 0):.1f}mm." if water_data and (water_data.get("summary", {}).get("final_deficit_mm") or 0) < -5 else "Soil moisture levels are adequate, no significant water stress detected.",
                    "why_it_matters": "Precise evapotranspiration tracking prevents both yield-destroying drought stress and wasteful over-irrigation.",
                    "expert_metrics": [
                        {"name": "Daily ET0", "value": f"{et0_today:.1f} mm", "confidence": 0.85 if water_data else 0.6, "reason": "Penman-Monteith full model" if water_data else "Hargreaves-Samani fallback"},
                        {"name": "Root Zone Deficit", "value": f"{((water_data or {}).get('summary', {}).get('final_deficit_mm') or 0):.1f} mm", "confidence": 0.8 if water_data else 0.3, "reason": "Continuous daily mass balance"},
                        {"name": "Stress Index (Ks)", "value": f"{((water_data or {}).get('summary', {}).get('stress_index') or 0):.2f}", "confidence": 0.75 if water_data else 0.2, "reason": "Soil water depletion fraction"},
                    ]
                }),
        _engine("L4", "Nutrient Analysis", "",
                "OK" if (soil_data and isinstance(soil_data, dict) and not is_fallback) else "DEGRADED",
                "Assumed Baseline" if is_fallback else ("Regional Survey Baseline" if soil_data else "No soil data"),
                f"pH {soil_data.get('ph', '--')} | {soil_data.get('texture_class', '').capitalize()} | OC {soil_data.get('organic_carbon', '--')} g/kg" if soil_data and isinstance(soil_data, dict) else "Awaiting soil data",
                {
                    **(soil_data or {}),
                    "farmer_summary": f"{'Note: Regional baseline assumptions applied.' if is_fallback else ''} Soil texture is classified as {soil_data.get('texture_class', 'unknown')} ({soil_data.get('sand', '--')}% sand, {soil_data.get('silt', '--')}% silt, {soil_data.get('clay', '--')}% clay), reflecting base drainage and water holding capacity. Baseline pH is {soil_data.get('ph', '--')} with ~{soil_data.get('organic_carbon', '--')} g/kg organic carbon from regional soil survey data." if soil_data and isinstance(soil_data, dict) else "No physical soil profile available for this field.",
                    "why_it_matters": "Base soil characteristics determine nutrient retention (CEC), fertilizer efficiency, and water holding capacity.",
                    "expert_metrics": [
                        {"name": "Soil pH (H2O)", "value": str(soil_data.get('ph', '--')) if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.35 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Total Nitrogen", "value": f"{soil_data.get('nitrogen', '--')} g/kg" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.30 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Organic Carbon", "value": f"{soil_data.get('organic_carbon', '--')} g/kg" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.40 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "CEC", "value": f"{soil_data.get('cec', '--')} meq/100g" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.35 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Bulk Density", "value": f"{soil_data.get('bdod', '--')} g/cm" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.45 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Clay %", "value": f"{soil_data.get('clay', '--')}%" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.50 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Sand %", "value": f"{soil_data.get('sand', '--')}%" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.50 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Silt %", "value": f"{soil_data.get('silt', '--')}%" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.50 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                    ]
                }),
        _engine("L5", "Biotic Pressure", "",
                "OK" if weather_data else "DEGRADED",
                f"{biotic_status} Risk" if weather_data else "No data",
                biotic_detail,
                {
                    "risk_level": biotic_status, "temp": temp_now, "humidity": hum_now,
                    "farmer_summary": f"Current weather (Temp: {temp_now:.1f}C, Humidity: {hum_now}%) creates a {biotic_status.lower()} risk for fungal infections." if weather_data else "Unable to calculate fungal risk due to missing weather data.",
                    "why_it_matters": "Fungal pathogens require specific temperature and leaf wetness windows to sporulate and infect.",
                    "expert_metrics": [
                        {"name": "Infection Risk", "value": biotic_status, "confidence": 0.55 if weather_data else 0.15, "reason": "Simplified Temp/RH threshold (not crop-specific disease model)" if weather_data else "Missing microclimate data"},
                        {"name": "Leaf Wetness Proxy", "value": f"{hum_now}% RH", "confidence": 0.5 if weather_data else 0.1, "reason": "RH proxy (no actual leaf wetness sensor)"},
                        {"name": "Temp Window", "value": f"{temp_now:.1f}C", "confidence": 0.95 if weather_data else 0.3, "reason": "Optimal fungal growth is 20-30C"},
                    ]
                }),
    ]

    # ---- Assimilation ----
    sources_used = [
        s for s in [
            weather_data and "OpenMeteo",
            indices_data and "Sentinel-2",
            sar_data and "Sentinel-1-SAR",
            sar_ts_data and "Sentinel-1-SAR-TS",
            water_data and "Water-Balance",
            soil_data and "Regional Soil Survey",
            forecast_data and "Weather-Forecast",
            ndvi_from_kalman and "Kalman-Filter",
        ] if s
    ]

    # ---- GAP B: Real L6-L9 engine cards ----
    # Compute now so L9 can reference sources_used
    _wb_summary = water_data.get("summary", {}) if water_data and isinstance(water_data.get("summary"), dict) else {}
    _deficit = _wb_summary.get("final_deficit_mm") or 0.0
    _stress_idx = _wb_summary.get("stress_index") or 0.0
    # This endpoint's NDVI is either a point Sentinel sample or a temporal
    # model estimate. Neither has field support, so it cannot authorize a
    # whole-field yield class.
    _yield_class = "Unknown"
    _yield_conf = 0.0
    _yield_reason = "No field-supported canopy raster or crop-calibrated yield model"
    _nlg_ok = bool(os.getenv("OPENROUTER_API_KEY"))

    _l6_has_ndvi = bool(indices_data) or ndvi_from_kalman
    _l6 = _engine(
        "L6", "Yield Estimation", "",
        "DEGRADED",
        "Field-supported yield unavailable",
        "Point or temporal NDVI is available, but no field-supported yield estimate is authorized.",
        {
            "ndvi": ndvi_val if _l6_has_ndvi else None,
            "ndvi_support_type": "point" if indices_data else ("temporal_model" if ndvi_from_kalman else "none"),
            "yield_class": _yield_class.upper(),
            "basis": "insufficient_field_support",
            "field_summary_eligible": False,
            "farmer_summary": "A point Sentinel index or temporal model estimate cannot establish whole-field yield. A field-supported canopy raster and crop calibration are required.",
            "why_it_matters": "Yield projections are withheld until their spatial support and crop calibration match the whole-field claim.",
            "expert_metrics": [
                {"name": "Yield Potential", "value": _yield_class, "confidence": _yield_conf, "reason": _yield_reason},
                {"name": "NDVI evidence", "value": f"{ndvi_val:.2f} NDVI" if _l6_has_ndvi else "N/A", "confidence": 0.9 if indices_data else (min(kalman_ndvi_confidence, 0.85) if ndvi_from_kalman else 0.0), "reason": "Point support only; not a field yield proxy" if indices_data else ("Temporal support only; not a field yield proxy" if ndvi_from_kalman else "No vegetation data available")},
            ]
        },
    )

    if _deficit < -20:
        _l7_label = "Irrigate: deficit detected"
        _l7_summary = f"Deficit {abs(_deficit):.0f}mm  schedule irrigation this week"
        _l7_farmer = f"Your field has lost {abs(_deficit):.0f}mm of water. We highly recommend scheduling an irrigation event soon to avoid yield loss."
    elif biotic_status == "High":
        _l7_label = "Scout field: biotic risk elevated"
        _l7_summary = f"Biotic risk {biotic_status.lower()}  scout for disease/pest signs"
        _l7_farmer = "Weather conditions are perfect for fungal disease. Please walk the field and inspect lower leaves for early signs of infection."
    else:
        _l7_label = "Monitor: conditions stable"
        _l7_summary = "No urgent interventions required this week"
        _l7_farmer = "Conditions are stable. No urgent interventions are required for irrigation or crop protection at this time."

    _l7 = _engine(
        "L7", "Planning & Calendar", "",
        "OK" if water_data else "DEGRADED",
        _l7_label, _l7_summary,
        {
            "water_deficit_mm": _deficit if _wb_summary else None, "biotic_risk": biotic_status,
            "farmer_summary": _l7_farmer,
            "why_it_matters": "A prioritized task list prevents critical timing errors in irrigation or fungicide application.",
            "expert_metrics": [
                {"name": "Primary Intervention", "value": _l7_label.split(":")[0], "confidence": 0.7 if water_data else 0.4, "reason": "Rule-based triage (decision tree, not a planning model)"},
                {"name": "Action Window", "value": "24-48 Hours" if "Irrigate" in _l7_label or "Scout" in _l7_label else "Next 7 Days", "confidence": 0.6 if forecast_data else 0.3, "reason": "Based on forecast" if forecast_data else "No forecast for timing"},
            ]
        },
    )

    if _deficit < -10:
        _l8_label = "Irrigation prescription ready"
        _l8_summary = f"Apply {abs(_deficit):.0f}mm irrigation (stress index {_stress_idx:.2f})"
        _l8_type = "IRRIGATION"
        _l8_farmer = f"Based on water balance, your field needs approximately {abs(_deficit):.0f}mm of irrigation."
    else:
        _l8_label = "Monitoring prescription active"
        _l8_summary = f"No urgent prescription. NDVI {ndvi_val:.2f} stable."
        _l8_type = "MONITOR"
        _l8_farmer = "No spatial prescription map is currently required. Maintain standard monitoring protocols."

    _l8 = _engine(
        "L8", "Prescriptive Actions", "",
        "OK" if (water_data or indices_data) else "DEGRADED",
        _l8_label, _l8_summary,
        {
            "prescription_type": _l8_type,
            "farmer_summary": _l8_farmer,
            "why_it_matters": "Translates agronomic analysis into actionable field-level recommendations.",
            "expert_metrics": [
                {"name": "Action Type", "value": _l8_type, "confidence": 0.7 if water_data else 0.3, "reason": "Derived from L3 water balance" if water_data else "Insufficient data"},
                {"name": "VRA Map", "value": "Not available", "confidence": 0.0, "reason": "Variable-rate application maps not yet implemented"},
            ]
        },
    )

    _l9 = _engine(
        "L9", "Interface & NLG", "",
        "OK" if _nlg_ok else "DEGRADED",
        "LLM online" if _nlg_ok else "LLM offline (no API key)",
        f"Natural language generation {'active' if _nlg_ok else 'degraded'}. "
        f"{len(sources_used)} data source{'s' if len(sources_used) != 1 else ''} wired into advisor context.",
        {
            "llm_available": _nlg_ok, "sources_in_context": len(sources_used),
            "farmer_summary": "AgriBrain Chat is fully loaded with your field's exact data. You can ask it to explain any of these insights in detail.",
            "why_it_matters": "A conversational interface allows you to query complex agronomic data without needing to interpret charts yourself.",
            "expert_metrics": [
                {"name": "LLM Engine", "value": os.getenv("OPENROUTER_MODEL", "openrouter/auto"), "confidence": 1.0 if _nlg_ok else 0.0, "reason": "OpenRouter API" if _nlg_ok else "No API key configured"},
                {"name": "Context Sources", "value": f"{len(sources_used)} active", "confidence": min(1.0, len(sources_used) / 5.0), "reason": "Active data feeds wired to advisor"},
                {"name": "Reasoning Mode", "value": "Enabled" if _nlg_ok else "Disabled", "confidence": 1.0 if _nlg_ok else 0.0, "reason": "Chain-of-thought routing"},
            ]
        },
    )

    engines.extend([_l6, _l7, _l8, _l9])
    
    # Compute real L10 quality from actual pipeline data
    _l10_gates = [
        bool(weather_data),          # G1: Weather online
        bool(forecast_data),         # G2: Forecast available
        bool(indices_data),          # G3: Optical indices
        bool(sar_data),              # G4: SAR data
        bool(soil_data),             # G5: Soil properties
        bool(water_data),            # G6: Water balance
        bool(hist_weather),          # G7: Historical weather
        bool(ndvi_ts),               # G8: NDVI timeseries
        len(ndvi_records) > 0,       # G9: Kalman output
        et0_today > 0,               # G10: ET0 computed
        sources_active >= 2,         # G11: Multi-source fusion
        not is_fallback,             # G12: Real soil (not generic)
        has_active_sensors,          # G13: Field sensor telemetry
    ]
    _l10_passed = sum(_l10_gates)
    _l10_quality = round(_l10_passed / len(_l10_gates), 3)
    _l10_mode = "NORMAL" if _l10_quality >= 0.7 else ("DEGRADED" if _l10_quality >= 0.4 else "CRITICAL")
    l10_data = {
        "overall_quality_score": _l10_quality,
        "hard_gates_passed": _l10_passed,
        "total_gates": len(_l10_gates),
        "spatial_anomaly_trustworthy": ndvi_val > 0.2,
        "degradation_mode": _l10_mode,
    }
    engines.append(_engine("L10", "SIRE Orchestrator", "",
                           "OK" if _l10_quality >= 0.7 else "DEGRADED", _l10_mode,
                           f"{_l10_passed}/{len(_l10_gates)} quality gates passed", l10_data))

    try:
        from layer10_sire.packetizer import enrich_engines_with_explainability
        engines = enrich_engines_with_explainability(engines)
    except Exception as e:
        print(f"[PI] Failed to enrich engines: {e}")

    assimilation = {
        "dataAge_days": 0,
        "sources_used": sources_used,
        "sources_count": len(sources_used),
        "freshness_score": min(1.0, len(sources_used) / 6.0),
        "assimilated": len(sources_used) >= 2,
        "raw_available": req.expert_mode,
    }

    # Crop phenology (delegated to pi_helpers)
    crop_phenology = compute_phenology(
        req.plant_date, req.crop_administrative_status, ndvi_val
    )

    # ---- DNA Provenance (from Kalman engine metadata) ----
    dna_status = None
    if req.plot_id:
        try:
            from layer0.calibration.dna_cache import load_dna_cache, get_dna_hash
            dna_hash = get_dna_hash(req.plot_id)
            dna_cached = load_dna_cache(req.plot_id)
            if dna_cached:
                dna_traits = dna_cached.get("traits", {})
                dna_quality = dna_cached.get("data_quality", {})
                dna_status = {
                    "sequenced": True,
                    "hash": dna_hash,
                    "traits": {
                        "theta_retention": dna_traits.get("theta_retention"),
                        "beta_resilience": dna_traits.get("beta_resilience"),
                        "alpha_vigor": dna_traits.get("alpha_vigor"),
                        "t_shift": dna_traits.get("t_shift"),
                    },
                    "data_quality_pct": dna_quality.get("weather_null_fill_pct", 0),
                    "ndvi_observations": dna_quality.get("ndvi_observations", 0),
                    "physics_injected": True,
                }
            else:
                dna_status = {"sequenced": False, "hash": None, "physics_injected": False}
        except Exception as e:
            print(f"[PI] DNA status lookup failed: {e}")
            dna_status = {"sequenced": False, "error": str(e)}

    # ---- Response ----
    response = {
        "success": True,
        "timestamp": now_str,
        "timeline": timeline,
        "engines": engines,
        "current": {
            "weather": weather_data,
            "indices": indices_data,
            "soil": soil_data,
            "waterBalance": water_data,
            "open_meteo_agri": results.get("open_meteo_agri"),
            "nasa_power": results.get("nasa_power"),
        },
        "assimilation": assimilation,
        "crop_phenology": crop_phenology,
        # DNA 4.0: Biophysical trait provenance
        "dna_status": dna_status,
        # GAP 2: User-declared management context (from DB  proxy  here)
        "user_inputs": {
            "irrigation_type": user_irrigation,
            "soil_type": user_soil_type,
            "soil_analysis": req.soil_analysis if user_soil_override else None,
            "soil_source": proxy_reason,
            "physical_constraints": user_constraints,
            "area_ha": user_area_ha,
        },
        # GAP SENSOR: Live field sensor telemetry context
        "sensor_context": sensor_context,
    }

    # ---- Expert Raw Data ----
    if req.expert_mode:
        response["rawData"] = {
            "weather_raw": weather_data,
            "forecast_raw": forecast_data,
            "sentinel2_raw": indices_data,
            "sentinel1_raw": sar_data,
            "sar_timeseries": sar_ts_data,
            "soilgrids_raw": soil_data,
            "water_balance_raw": water_data,
            "historical_weather": hist_weather,
            "user_soil_analysis": req.soil_analysis if user_soil_override else None,
            "sensor_readings_raw": req.sensor_readings or [],
        }

    _t_end = _time.perf_counter()
    print(f"[PERF] /v2/plot-intelligence: TOTAL = {_t_end - _t0:.2f}s")

    def _sanitize_nans(obj):
        import math
        if isinstance(obj, dict):
            return {k: _sanitize_nans(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_sanitize_nans(x) for x in obj]
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        return obj

    return _sanitize_nans(response)

@app.post("/v2/intent")
def api_v2_intent(req: V2IntentRequest):
    """
    Ultra-fast intent routing endpoint for live UI updates.
    """
    from layer9_interface.intent_router import route_intent
    import json
    
    history_obj = []
    if req.history:
        try:
            history_obj = json.loads(req.history)
        except Exception:
            pass
            
    decision = route_intent(req.query, history_obj)
    return decision


# ============================================================================
# Kalman-NDVI Surface Bridge
# ============================================================================
def _bridge_kalman_ndvi_to_surfaces(result: dict, ndvi_records: list, indices: dict):
    """
    Reconcile L10 spatial surfaces with Kalman temporal NDVI estimates.

    Problem: The L10 raster pipeline reads S2 composites which may be stale
    during cloud gaps (e.g. field NDVI=0.08 when crop is actually NDVI=0.35).
    The Kalman filter, which assimilates weather + S2, has a better daily estimate.

    Solution: Bias-correct the NDVI_CLEAN surface:
      corrected[r][c] = kalman_mean + (raw[r][c] - raw_mean) × spatial_scale
    This preserves the raster's spatial pattern while shifting the mean to the
    Kalman estimate — so the map accurately represents the crop's current state.
    """
    if not ndvi_records:
        return

    from datetime import datetime as _dt, timezone as _tz
    today = _dt.now(_tz.utc).strftime("%Y-%m-%d")

    # 1. Get best Kalman NDVI estimate for today
    kalman_rec = None
    for rec in reversed(ndvi_records):
        if rec.get("date", "") <= today:
            kalman_rec = rec
            break
    if not kalman_rec:
        return

    kalman_ndvi = kalman_rec.get("ndvi", 0)
    kalman_conf = kalman_rec.get("confidence", 0.5)
    kalman_src = kalman_rec.get("source", "kalman")

    # Cross-reference with Sentinel Hub direct index if available
    sh_ndvi = None
    if indices and isinstance(indices, dict):
        raw_sh = indices.get("ndvi")
        if raw_sh is not None:
            sh_ndvi = float(raw_sh)

    # Best estimate priority: use the highest-CONFIDENCE estimate, not the highest value.
    # A crop CAN decline (drought, senescence, pest). Taking the max would mask
    # real agronomic decline. Instead, trust the most reliable measurement:
    #   - SH direct has confidence 0.9 (latest composite, well-calibrated)
    #   - Kalman confidence varies with cloud-gap duration
    # When confidence is equal, prefer SH direct (most recent measurement).
    candidates = []
    if kalman_ndvi is not None and kalman_ndvi > 0.01:
        candidates.append(("kalman", kalman_ndvi, kalman_conf))
    if sh_ndvi is not None and sh_ndvi > 0.05:
        candidates.append(("sh_direct", sh_ndvi, 0.9))

    if not candidates:
        return

    # Sort by confidence (desc), then prefer SH direct for tie-breaking
    best_src, best_ndvi, best_conf = max(
        candidates, key=lambda x: (x[2], 1 if x[0] == "sh_direct" else 0)
    )
    print(f"[L10] Bridge candidates: {[(s, round(v,3), round(c,2)) for s,v,c in candidates]} -> best={best_src}({best_ndvi:.3f}, conf={best_conf:.2f})")

    if best_ndvi is None or best_ndvi < 0.01:
        return  # Nothing useful to bridge

    # 2. Find NDVI_CLEAN surface
    surfaces = result.get("surfaces", [])
    ndvi_surf = next((s for s in surfaces if s.get("type") == "NDVI_CLEAN"), None)
    if not ndvi_surf or not ndvi_surf.get("values"):
        return

    # ── Guard: Do NOT bridge when surface has real raster pixel data ──
    # When raster composites are successfully fetched from Sentinel Hub,
    # the NDVI_CLEAN surface contains actual pixel-level satellite values.
    # These are the NEWEST, HIGHEST-FIDELITY data source — they represent
    # the latest cloud-free composite. The Kalman/SH timeseries values are
    # field-level temporal estimates that may be STALE (old observations,
    # cloud-gap extrapolations). Bridging would destroy real pixel data
    # by shifting it to match a stale field-level estimate.
    #
    # Only bridge when grounding_class == "UNIFORM" (no real raster data —
    # all pixels are identical field-level broadcasts).
    grounding = ndvi_surf.get("grounding_class", "UNIFORM")
    if grounding and grounding != "UNIFORM":
        print(f"[L10] Bridge SKIPPED: surface has real raster data "
              f"(grounding={grounding}, mean={sum(v for row in ndvi_surf['values'] for v in row if v is not None) / max(1, sum(1 for row in ndvi_surf['values'] for v in row if v is not None)):.3f})")
        return

    vals = ndvi_surf["values"]
    H = len(vals)
    W = len(vals[0]) if H > 0 else 0
    if H == 0 or W == 0:
        return

    # 3. Compute raw surface stats
    flat = [v for row in vals for v in row if v is not None]
    if not flat:
        return
    raw_mean = sum(flat) / len(flat)

    # 3b. Additional uniformity check: even if tagged UNIFORM, verify
    # the surface actually lacks spatial variation before bridging.
    raw_std = (sum((v - raw_mean) ** 2 for v in flat) / len(flat)) ** 0.5
    raw_cv = raw_std / raw_mean if raw_mean > 0.01 else 0
    if raw_cv > 0.10:
        # Surface has meaningful spatial variation (CV > 10%) — likely has
        # real raster data even if grounding tag is missing/wrong.
        print(f"[L10] Bridge SKIPPED: surface has spatial variation "
              f"(CV={raw_cv:.1%}, std={raw_std:.3f}, mean={raw_mean:.3f})")
        return

    # 4. Only bridge if gap is agronomically meaningful (>0.05 NDVI units)
    gap = abs(best_ndvi - raw_mean)
    if gap < 0.05:
        return  # Surface and Kalman agree — no correction

    # 5. Additive mean-shift correction
    #    Preserve the exact spatial deviation pattern from the raster.
    #    Only shift the field mean to match the Kalman estimate.
    #    This is physically correct: the raster captures real within-field
    #    variation, the Kalman provides the true absolute level.
    #    (Multiplicative scaling amplifies noise and creates false gradients)
    mean_shift = best_ndvi - raw_mean

    for r in range(H):
        for c in range(W):
            if vals[r][c] is not None:
                corrected = vals[r][c] + mean_shift
                vals[r][c] = round(max(0.0, min(1.0, corrected)), 4)

    # 5b. Targeted boundary pixel correction.
    # Only correct boundary cells that are significantly below the interior mean.
    # Blanket neutralization destroys spatial variation on small grids (10×8).
    new_flat = [v for row in vals for v in row if v is not None]
    new_mean = sum(new_flat) / len(new_flat) if new_flat else best_ndvi

    boundary_cells = set()
    for r in range(H):
        for c in range(W):
            if vals[r][c] is None:
                continue
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if nr < 0 or nr >= H or nc < 0 or nc >= W:
                    boundary_cells.add((r, c))
                    break
                if vals[nr][nc] is None:
                    boundary_cells.add((r, c))
                    break

    # Interior stats for threshold
    interior = [vals[r][c] for r in range(H) for c in range(W)
                if vals[r][c] is not None and (r, c) not in boundary_cells]
    if interior:
        int_mean = sum(interior) / len(interior)
        int_std = (sum((v - int_mean) ** 2 for v in interior) / len(interior)) ** 0.5
        threshold = int_mean - max(int_std, 0.02)

        for r, c in boundary_cells:
            if vals[r][c] < threshold:
                vals[r][c] = round(int_mean, 4)

        # Apply same correction to other surfaces
        for surf in surfaces:
            if surf is ndvi_surf:
                continue
            sv = surf.get("values")
            if sv and len(sv) == H and len(sv[0]) == W:
                s_interior = [sv[rr][cc] for rr in range(H) for cc in range(W)
                              if sv[rr][cc] is not None and (rr, cc) not in boundary_cells]
                if s_interior:
                    si_mean = sum(s_interior) / len(s_interior)
                    si_std = (sum((v - si_mean) ** 2 for v in s_interior) / len(s_interior)) ** 0.5
                    si_thresh = si_mean - max(si_std, 0.02)
                    for r, c in boundary_cells:
                        if sv[r][c] is not None and sv[r][c] < si_thresh:
                            sv[r][c] = round(si_mean, 4)

    # 6. Recompute dependent surfaces
    new_flat = [v for row in vals for v in row if v is not None]
    new_mean = sum(new_flat) / len(new_flat) if new_flat else best_ndvi

    # NDVI_DEVIATION = per-cell minus field mean
    dev_surf = next((s for s in surfaces if s.get("type") == "NDVI_DEVIATION"), None)
    if dev_surf and dev_surf.get("values"):
        dv = dev_surf["values"]
        for r in range(H):
            for c in range(W):
                if vals[r][c] is not None:
                    dv[r][c] = round(vals[r][c] - new_mean, 4)

    # BASELINE_ANOMALY = recompute from corrected NDVI ratio
    ba_surf = next((s for s in surfaces if s.get("type") == "BASELINE_ANOMALY"), None)
    if ba_surf and ba_surf.get("values") and new_mean > 0:
        bv = ba_surf["values"]
        for r in range(H):
            for c in range(W):
                if vals[r][c] is not None and bv[r][c] is not None:
                    ratio = (vals[r][c] / new_mean) - 1.0
                    bv[r][c] = round(ratio * 0.15, 4)

    # 7. Tag provenance so the UI can show "Kalman-corrected"
    ndvi_surf["grounding_class"] = "KALMAN_CORRECTED"
    prov = ndvi_surf.get("provenance", {})
    prov["kalman_bridge"] = {
        "raw_mean": round(raw_mean, 4),
        "corrected_mean": round(new_mean, 4),
        "kalman_ndvi": round(best_ndvi, 4),
        "kalman_source": kalman_src,
        "kalman_confidence": round(kalman_conf, 3),
        "correction_gap": round(gap, 4),
    }
    ndvi_surf["provenance"] = prov

    print(f"[L10] Kalman NDVI bridge: surface {raw_mean:.3f} → {new_mean:.3f} "
          f"(best={best_ndvi:.3f}, src={best_src}, conf={best_conf:.0%})")


def _recalibrate_zones(result: dict):
    """
    Recalibrate zones after bridge correction and upscale.

    Zones were generated by L10 from pre-bridge surface values. After the Kalman
    bridge corrects NDVI and the upscale adjusts grid dimensions, zones need their
    severity, type, and labels refreshed from the corrected data.
    """
    surfaces = result.get("surfaces", [])
    zones = result.get("zones", [])
    if not surfaces or not zones:
        return

    # Find corrected NDVI surface
    ndvi_surf = next((s for s in surfaces if s.get("type") == "NDVI_CLEAN"), None)
    if not ndvi_surf or not ndvi_surf.get("values"):
        return

    vals = ndvi_surf["values"]
    H = len(vals)
    W = len(vals[0]) if H > 0 else 0
    if H == 0 or W == 0:
        return

    # Compute corrected field-wide stats
    flat = [v for row in vals for v in row if v is not None]
    if not flat:
        return
    field_mean = sum(flat) / len(flat)
    field_std = (sum((v - field_mean) ** 2 for v in flat) / len(flat)) ** 0.5

    # Find water stress surface for secondary classification
    water_surf = next((s for s in surfaces if s.get("type") == "WATER_STRESS_PROB"), None)

    # Uniformity guard: if CV < 15%, suppress management zones.
    # A "Mostly even" field has no meaningful spatial zones to report.
    cv = field_std / field_mean if field_mean > 0.01 else 0
    if cv < 0.15:
        mgmt_count = sum(1 for z in zones if z.get("zone_id", "").startswith("MZ_"))
        zones[:] = [z for z in zones if not z.get("zone_id", "").startswith("MZ_")]
        if mgmt_count > 0:
            print(f"[L10] Suppressed {mgmt_count} management zones: field is uniform (CV={cv:.2%})")

    recalibrated = 0
    zones_to_remove = []
    for zone in zones:
        cells = zone.get("cell_indices", [])
        if not cells:
            continue

        # Compute zone NDVI stats from corrected surface
        zone_ndvi = []
        for cell in cells:
            r, c = cell[0], cell[1]
            if 0 <= r < H and 0 <= c < W and vals[r][c] is not None:
                zone_ndvi.append(vals[r][c])

        if not zone_ndvi:
            continue

        zone_mean = sum(zone_ndvi) / len(zone_ndvi)
        zone_deviation = zone_mean - field_mean

        # Compute water stress in zone if available
        zone_water = 0.0
        if water_surf and water_surf.get("values"):
            wv = water_surf["values"]
            w_vals = []
            for cell in cells:
                r, c = cell[0], cell[1]
                if 0 <= r < len(wv) and 0 <= c < len(wv[0]) and wv[r][c] is not None:
                    w_vals.append(wv[r][c])
            if w_vals:
                zone_water = sum(w_vals) / len(w_vals)

        # Reclassify zone type based on corrected values
        zone_type = zone.get("zone_type", "")
        is_management = zone.get("zone_id", "").startswith("MZ_")

        if is_management:
            # Management zones: classify based on relative NDVI
            if zone_mean < field_mean - field_std:
                zone_type = "LOW_VIGOR"
            elif zone_mean > field_mean + field_std:
                zone_type = "HIGH_VIGOR"
            elif zone_water > 0.4:
                zone_type = "WATER_STRESS"
            else:
                zone_type = "MODERATE"

            # Compute meaningful severity for management zones
            # Scale: 0 = at field mean, 0.5 = 1 std away, 1.0 = 2+ std away
            # (1 std is common/expected, 2+ std is genuinely anomalous)
            severity = round(abs(zone_deviation) / max(0.01, 2 * field_std), 3)
            severity = min(1.0, severity)
        else:
            # Alert zones: recompute severity from corrected data
            severity = zone.get("severity", 0.5)
            # If zone is NDVI-derived, update severity from corrected values
            src = zone.get("source_surface_type", "")
            if src in ("NDVI_DEVIATION", "BASELINE_ANOMALY", "NDVI_CLEAN"):
                severity = round(abs(zone_deviation), 3)

        zone["zone_type"] = zone_type
        zone["severity"] = severity

        # Regenerate label from recalibrated severity and type
        type_nouns = {
            "LOW_VIGOR": "low-vigor patch",
            "HIGH_VIGOR": "high-vigor patch",
            "MODERATE": "moderate-vigor zone",
            "WATER_STRESS": "water-stress zone",
            "NUTRIENT_RISK": "nutrient-risk zone",
            "DISEASE_RISK": "disease-pressure zone",
            "BLOCKED_ZONE": "blocked-execution zone",
            "SCOUT_ZONE": "priority scouting zone",
            "LOW_CONFIDENCE": "low-confidence area",
        }
        noun = type_nouns.get(zone_type, "zone")

        # Severity adjective
        if severity >= 0.75:
            adj = "severe"
        elif severity >= 0.50:
            adj = "moderate"
        elif severity >= 0.25:
            adj = "mild"
        else:
            adj = "low"

        # Spatial anchor
        if cells:
            cr = sum(cell[0] for cell in cells) / len(cells)
            cc = sum(cell[1] for cell in cells) / len(cells)
            v = cr / max(1, H - 1)
            h_pos = cc / max(1, W - 1)
            ns = "North" if v < 0.35 else ("South" if v > 0.65 else "Central")
            ew = "west" if h_pos < 0.35 else ("east" if h_pos > 0.65 else "")
            anchor = (ns + "-" + ew).rstrip("-") if ew else ns
        else:
            anchor = "Field"

        # Field-wide check
        total = len(flat)
        if total > 0 and len(cells) / total > 0.6:
            zone["label"] = f"Field-wide {noun}"
        else:
            zone["label"] = f"{anchor} {adj} {noun}"

        zone["description"] = (
            f"{zone_type}: {len(cells)} cells, NDVI={zone_mean:.2f} "
            f"(field avg={field_mean:.2f})"
        )

        # Update surface_stats with corrected values
        zone["surface_stats"] = zone.get("surface_stats", {})
        zone["surface_stats"]["NDVI_CLEAN"] = {
            "mean": round(zone_mean, 4),
            "deviation": round(zone_deviation, 4),
        }
        if zone_water > 0:
            zone["surface_stats"]["WATER_STRESS_PROB"] = {
                "mean": round(zone_water, 4),
            }

        recalibrated += 1

    # Remove zones with negligible severity after recalibration
    # (these are boundary artifacts or uniform-field false positives)
    before_count = len(zones)
    zones[:] = [z for z in zones if z.get("severity", 0) >= 0.02]
    removed = before_count - len(zones)

    if recalibrated or removed:
        print(f"[L10] Recalibrated {recalibrated} zones, removed {removed} negligible zones "
              f"(field NDVI={field_mean:.3f}, std={field_std:.3f}, CV={cv:.1%})")


CATEGORICAL_SURFACES = {"RESOLUTION_COVERAGE", "EXPERIMENTAL_FINE_DETAIL_CANDIDATE", "ZONE_POLICY", "FALLBACK_REASON", "GROWTH_STAGE_CLASS"}


def _upscale_surfaces(result: dict, scale: int = 4):
    """
    Bilinear-upscale all L10 surfaces from coarse grid to smooth rendering grid.
    Except categorical surfaces which use nearest-neighbor upscaling to prevent value bleeding.

    A 10×8 grid (80 pixels) on a 25ha field = 3000m² per pixel, which looks
    extremely blocky on a map. Upscaling 4× to 40×32 (1280 pixels) gives smooth
    visual continuity while preserving the original spatial patterns.

    Uses bilinear interpolation (not nearest-neighbor) so transitions between
    cells are smooth — matching how real satellite rasters look.
    """
    surfaces = result.get("surfaces", [])
    if not surfaces:
        return

    # Get original grid dimensions
    first = surfaces[0].get("values", [])
    if not first:
        return
    orig_H = len(first)
    orig_W = len(first[0]) if orig_H > 0 else 0
    if orig_H >= 160 or orig_W >= 160:
        return  # Already detailed enough, skip upscaling to prevent timeouts (saves 40s+ CPU)
    if orig_H < 4 or orig_W < 4:
        return  # Too small to upscale

    new_H = orig_H * scale
    new_W = orig_W * scale

    def _nearest_upscale(grid, oH, oW, nH, nW):
        """Nearest neighbor interpolation upscale. None values propagate."""
        out = [[None] * nW for _ in range(nH)]
        for r in range(nH):
            for c in range(nW):
                src_r = int(r * oH / nH)
                src_c = int(c * oW / nW)
                src_r = max(0, min(src_r, oH - 1))
                src_c = max(0, min(src_c, oW - 1))
                out[r][c] = grid[src_r][src_c]
        return out

    def _bilinear_upscale(grid, oH, oW, nH, nW):
        """Bilinear interpolation upscale. None values propagate."""
        out = [[None] * nW for _ in range(nH)]
        for r in range(nH):
            for c in range(nW):
                # Map output pixel to input space (center-to-center mapping)
                src_r = (r + 0.5) * oH / nH - 0.5
                src_c = (c + 0.5) * oW / nW - 0.5

                r0 = int(src_r)
                c0 = int(src_c)
                r1 = min(r0 + 1, oH - 1)
                c1 = min(c0 + 1, oW - 1)
                r0 = max(0, r0)
                c0 = max(0, c0)

                fr = src_r - r0
                fc = src_c - c0

                # Get 4 neighbors
                v00 = grid[r0][c0]
                v01 = grid[r0][c1]
                v10 = grid[r1][c0]
                v11 = grid[r1][c1]

                # If any neighbor is None, use average of available valid values.
                # The frontend handles the field boundary visually (transparent
                # outside-polygon pixels) so we preserve data here for maximum
                # spatial coverage.
                vals = [v for v in [v00, v01, v10, v11] if v is not None]
                if not vals:
                    out[r][c] = None
                    continue
                if len(vals) < 4:
                    out[r][c] = round(sum(vals) / len(vals), 4)
                    continue

                # Bilinear blend
                val = (v00 * (1 - fr) * (1 - fc) +
                       v01 * (1 - fr) * fc +
                       v10 * fr * (1 - fc) +
                       v11 * fr * fc)
                out[r][c] = round(val, 4)
        return out

    # Pre-upscale boundary neutralization on original grid.
    # Sentinel-2 edge cells are mixed pixels (field + road/bare soil) with
    # artificially low values. Replace with surface mean BEFORE upscaling
    # so bilinear interpolation propagates corrected values.
    for surf in surfaces:
        # V65E: Bypass boundary neutralization for categorical surfaces
        stype = surf.get("semantic_type") or surf.get("type") or ""
        stype_name = stype.value if hasattr(stype, "value") else str(stype)
        if stype_name in CATEGORICAL_SURFACES:
            continue

        sv = surf.get("values")
        if not sv or len(sv) != orig_H:
            continue
        if not sv[0] or len(sv[0]) != orig_W:
            continue

        s_flat = [sv[r][c] for r in range(orig_H) for c in range(orig_W) if sv[r][c] is not None]
        if not s_flat:
            continue

        # Find ring-1 boundary cells (adjacent to None or grid edge)
        ring1 = set()
        for r in range(orig_H):
            for c in range(orig_W):
                if sv[r][c] is None:
                    continue
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if nr < 0 or nr >= orig_H or nc < 0 or nc >= orig_W:
                        ring1.add((r, c))
                        break
                    if sv[nr][nc] is None:
                        ring1.add((r, c))
                        break

        if not ring1:
            continue

        # Compute interior stats (non-boundary cells)
        interior_vals = [
            sv[r][c] for r in range(orig_H) for c in range(orig_W)
            if sv[r][c] is not None and (r, c) not in ring1
        ]
        if not interior_vals:
            continue  # All cells are boundary — nothing to correct against

        interior_mean = sum(interior_vals) / len(interior_vals)
        interior_std = (sum((v - interior_mean) ** 2 for v in interior_vals) / len(interior_vals)) ** 0.5

        # Only neutralize boundary cells that are SIGNIFICANTLY below interior
        # (> 1 std below = genuine mixed-pixel artifact). This preserves real
        # edge variation while fixing artificially low values.
        threshold = interior_mean - max(interior_std, 0.02)
        corrected = 0
        for r, c in ring1:
            if sv[r][c] < threshold:
                sv[r][c] = round(interior_mean, 4)
                corrected += 1

        if corrected:
            print(f"[L10] Boundary: corrected {corrected}/{len(ring1)} edge cells "
                  f"below threshold {threshold:.3f} (interior={interior_mean:.3f}±{interior_std:.3f})")

    # Upscale each surface with physics-guided boundary guiding
    # 1. Find and upscale NDVI_CLEAN first to act as physical boundary guide
    ndvi_surf = next((s for s in surfaces if s.get("semantic_type") in ("NDVI_CLEAN", "NDVI_CLEAN")), None)
    ndvi_upscaled = None
    if ndvi_surf:
        vals = ndvi_surf.get("values")
        if vals and len(vals) == orig_H and vals[0] and len(vals[0]) == orig_W:
            ndvi_upscaled = _bilinear_upscale(vals, orig_H, orig_W, new_H, new_W)
            
            # Clamp NDVI values to its render_range to ensure strict invariant compliance
            r_range = ndvi_surf.get("render_range")
            if r_range and len(r_range) == 2:
                min_r, max_r = r_range[0], r_range[1]
                for r in range(new_H):
                    for c in range(new_W):
                        if ndvi_upscaled[r][c] is not None:
                            ndvi_upscaled[r][c] = round(max(min_r, min(max_r, ndvi_upscaled[r][c])), 4)

            ndvi_surf["values"] = ndvi_upscaled
            ndvi_surf["grid_ref"] = f"{new_H}x{new_W}"

    # Semantic types representing biological/stress indicators that should not bleed into physical gaps (NDVI <= 0.15)
    BIOLOGICAL_AND_STRESS_TYPES = {
        "BIOTIC_PRESSURE", "SPREAD_LIKELIHOOD", "WEATHER_PRESSURE", "DISEASE_SPREAD_FORECAST",
        "WATER_STRESS_PROB", "SOIL_MOISTURE_PROXY", "DROUGHT_ACCUMULATION", "VPD_STRESS",
        "NUTRIENT_STRESS_PROB", "N_RESPONSE_POTENTIAL", "FERTILITY_LIMITATION", 
        "N_LEACHING_RISK", "N_VOLATILIZATION_RISK", "NUTRIENT_DEPLETION_RATE",
        "SALINITY_STRESS", "THERMAL_STRESS", "SOIL_COMPACTION",
        "YIELD_P50", "YIELD_P10", "YIELD_P90", "YIELD_GAP", "YIELD_PENALTY", 
        "YIELD_VALUE_AT_RISK", "PROFIT_SURFACE", "YIELD_TRAJECTORY",
        "CROP_SUITABILITY", "WATER_FEASIBILITY", "BIOTIC_FEASIBILITY", "ECONOMIC_SUITABILITY",
        "COMPOSITE_RISK", "SHOCK_RISK", "EXECUTION_RISK", "RISK_MOMENTUM",
        "EXECUTION_READINESS", "INTERVENTION_PRIORITY", "INTERVENTION_TIMING", "CONFLICT_RESOLUTION"
    }

    for surf in surfaces:
        # Skip if already upscaled above
        if ndvi_surf and surf is ndvi_surf:
            continue
        vals = surf.get("values")
        if not vals or len(vals) != orig_H:
            continue
        if not vals[0] or len(vals[0]) != orig_W:
            continue
        
        stype = surf.get("semantic_type") or surf.get("type") or ""
        stype_name = stype.value if hasattr(stype, "value") else str(stype)
        
        if stype_name in CATEGORICAL_SURFACES:
            up_vals = _nearest_upscale(vals, orig_H, orig_W, new_H, new_W)
        else:
            up_vals = _bilinear_upscale(vals, orig_H, orig_W, new_H, new_W)
            
            # Apply physics-guided suppression on non-vegetated physical boundaries (roads, bare soil, buildings)
            if ndvi_upscaled and stype_name in BIOLOGICAL_AND_STRESS_TYPES:
                for r in range(new_H):
                    for c in range(new_W):
                        if ndvi_upscaled[r][c] is not None and ndvi_upscaled[r][c] <= 0.15:
                            if up_vals[r][c] is not None:
                                up_vals[r][c] = 0.0

            # Clamp values to render_range to ensure strict invariant compliance
            r_range = surf.get("render_range")
            if r_range and len(r_range) == 2:
                min_r, max_r = r_range[0], r_range[1]
                for r in range(new_H):
                    for c in range(new_W):
                        if up_vals[r][c] is not None:
                            up_vals[r][c] = round(max(min_r, min(max_r, up_vals[r][c])), 4)

        surf["values"] = up_vals
        surf["grid_ref"] = f"{new_H}x{new_W}"

    # Upscale zone cell_indices to match new grid
    zones = result.get("zones", [])
    for zone in zones:
        old_cells = zone.get("cell_indices", [])
        if not old_cells:
            continue
        new_cells = []
        for cell in old_cells:
            r, c = cell[0], cell[1]
            # Each old cell maps to scale×scale new cells
            for dr in range(scale):
                for dc in range(scale):
                    new_cells.append([r * scale + dr, c * scale + dc])
        zone["cell_indices"] = new_cells

    # Update grid dimensions
    result["grid"] = {"height": new_H, "width": new_W}

    print(f"[L10] Upscaled surfaces: {orig_H}x{orig_W} -> {new_H}x{new_W} "
          f"({len(surfaces)} surfaces, {len(zones)} zones)")


# ============================================================================
# Crop Registry List Endpoint
# ============================================================================

@app.get("/v2/crops")
def api_v2_crops():
    """Return all registered crop types for the frontend crop picker."""
    try:
        from crop_database import CROP_REGISTRY

        # Emoji mapping by architecture
        ARCH_EMOJI = {
            "cereal": "🌾", "maize": "🌽", "rice": "🌾",
            "legume": "🫘", "root_tuber": "🥔", "vegetable": "🥬",
            "cucurbit": "🍉", "allium": "🧅", "brassica": "🥦",
            "leafy": "🥬", "solanaceae": "🍅", "perennial": "🌳",
            "tropical_tree": "🌴", "tropical_fruit": "🍌",
            "berry": "🫐", "nut": "🥜", "fiber": "🧵",
            "oilseed": "🌻", "sugar": "🍬", "stimulant": "☕",
            "spice": "🌶️", "forage": "🌿", "industrial": "🏭",
            "cover_crop": "🍀", "vine": "🍇", "cotton": "🧵",
        }

        crops = []
        for code, spec in CROP_REGISTRY.items():
            crops.append({
                "code": code,
                "nameAr": f"{spec.name_ar} ({spec.name})" if spec.name_ar else spec.name,
                "name_en": spec.name,
                "name_ar": spec.name_ar,
                "architecture": spec.architecture,
                "icon": ARCH_EMOJI.get(spec.architecture, "🌱"),
                "region_tags": list(spec.region_tags) if spec.region_tags else [],
            })
        return {"crops": crops, "count": len(crops)}
    except Exception as e:
        return {"crops": [], "count": 0, "error": str(e)}


# ============================================================================
# Crop Identification Endpoint
# ============================================================================

class CropIdentifyRequest(BaseModel):
    plot_id: str
    # Legacy context fields remain optional for backward-compatible callers;
    # the canonical endpoint never reacquires or rescans from them.
    lat: Optional[float] = None
    lng: Optional[float] = None
    area_ha: Optional[float] = None
    soil_type: Optional[str] = None
    irrigation: Optional[str] = None
    plot_name: Optional[str] = None
    previous_crops: Optional[list] = None

@app.post("/v2/crop-identify")
def api_v2_crop_identify(
    req: CropIdentifyRequest,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Return the canonical crop-posterior public DTO.

    This endpoint does not perform a live 212-species scoring run. It reads
    the namespace-bound worldline/snapshot and separates registry authority,
    EO crop-group support, and validated species confirmation.
    """
    try:
        # Crop identity has one truth path: the canonical plot worldline (or
        # the ASMAE snapshot that was committed from it). This endpoint never
        # reacquires a second, potentially different evidence snapshot.
        from services.agribrain.orchestrator_v2.pre_asmae_layer2a import (
            load_latest_crop_posterior_record,
        )
        from services.agribrain.world_model.canonical_worldline import (
            CanonicalWorldlineService,
        )
        from services.agribrain.layer05_asmae.plot_snapshot_store import (
            load_latest_plot_snapshot,
        )
        from services.agribrain.app.crop_identify_dto import (
            build_crop_identify_publication,
        )

        if namespace.plot_id != req.plot_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Header X-Plot-Id does not match request plot_id",
            )

        crop_record = load_latest_crop_posterior_record(
            CanonicalWorldlineService(),
            plot_namespace=namespace,
        )
        canonical = (
            dict(crop_record.posterior)
            if crop_record is not None else None
        )
        crop_worldline_event_id = (
            crop_record.worldline_event_id
            if crop_record is not None else None
        )
        snapshot = None
        if not isinstance(canonical, dict) or not canonical:
            snapshot = load_latest_plot_snapshot(namespace)
            scientific = (
                snapshot.get("asmae")
                or snapshot.get("scientific_result")
                or {}
                if isinstance(snapshot, dict)
                else {}
            )
            canonical = (
                scientific.get("refined_crop_posterior")
                or scientific.get("crop_posterior")
                or (snapshot.get("frontend_payload") or {}).get(
                    "crop_posterior"
                )
                if isinstance(snapshot, dict)
                else None
            )
            # A legacy snapshot may predate canonical crop-worldline
            # publication. Keep that absence explicit; never substitute the
            # generic ASMAE worldline event for a crop-posterior event.
            crop_worldline_event_id = (
                scientific.get("crop_worldline_event_id")
                or snapshot.get("crop_worldline_event_id")
                if isinstance(snapshot, dict)
                else None
            )
        if not isinstance(canonical, dict) or not canonical:
            unavailable = {
                "status": "canonical_snapshot_unavailable",
                "plot_id": req.plot_id,
                "top_crop": None,
                "top_group": "unknown",
                "crop_group_posterior": {"unknown": 1.0},
                "unknown_probability": 1.0,
                "species_probability_published": False,
                "reason": (
                    "Run plot intelligence to create the canonical "
                    "evidence-bound crop posterior."
                ),
            }
            return build_crop_identify_publication(
                unavailable,
                plot_id=req.plot_id,
                status="canonical_snapshot_unavailable",
                canonical_snapshot=False,
                reason=unavailable["reason"],
            )

        return build_crop_identify_publication(
            canonical,
            plot_id=req.plot_id,
            status="canonical",
            canonical_snapshot=True,
            worldline_event_id=crop_worldline_event_id,
            snapshot_ref=(
                snapshot.get("snapshot_ref") or snapshot.get("snapshot_id")
                if isinstance(snapshot, dict) else None
            ),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Canonical crop identity lookup failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "type": "CropIdentifyError",
                "error": "Canonical crop identity lookup failed",
            },
        ) from exc


class CropSuitabilityRequest(BaseModel):
    plot_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    # All biophysical fields are Optional — L0 auto-hydrates when None
    elevation_m: Optional[float] = None
    mean_temp_c: Optional[float] = None
    annual_rainfall_mm: Optional[float] = None
    et0_mm: Optional[float] = None
    soil_ph: Optional[float] = None
    soil_texture: Optional[str] = None
    soil_awc: Optional[float] = None
    soil_salinity_ds_m: Optional[float] = None
    slope_pct: Optional[float] = None
    irrigation_type: str = "rainfed"
    frost_days: Optional[int] = None
    heat_days_above_35: Optional[int] = None
    soil_depth_cm: Optional[float] = None

@app.post("/v2/crop-suitability")
def api_v2_crop_suitability(req: CropSuitabilityRequest):
    """Evaluate crop suitability with L0 auto-hydration (v5.1).

    Returns top-15 rainfed and irrigated candidates with FAO suitability
    classes (S1/S2/S3/N), limiting factor analysis, data_completeness,
    and hydration metadata.

    When biophysical fields are not provided, the endpoint auto-hydrates
    from L0 sources using this priority:
      1. Explicit request value
      2. Latest IntelligenceSnapshot
      3. L0 broker cached/live fetch
      4. Fallback default + warning
    """
    try:
        from layer3_decision.suitability_engine import CropSuitabilityEngine

        # --- Resolve coordinates ---
        resolved_lat = req.lat
        resolved_lng = req.lng

        if (resolved_lat is None or resolved_lng is None) and req.plot_id:
            # Try to resolve from plot record
            try:
                from pymongo import MongoClient
                import os
                mongo_url = os.environ.get("MONGODB_URI") or os.environ.get("DATABASE_URL", "")
                if mongo_url and "mongodb" in mongo_url:
                    client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
                    db_name = mongo_url.split("/")[-1].split("?")[0] if "/" in mongo_url else "agriwise"
                    db = client[db_name]
                    plot = db["Plot"].find_one({"_id": req.plot_id})
                    if plot and "farmId" in plot:
                        farm = db["Farm"].find_one({"_id": plot["farmId"]})
                        if farm:
                            resolved_lat = resolved_lat or farm.get("latitude")
                            resolved_lng = resolved_lng or farm.get("longitude")
            except Exception as e:
                print(f"[CropSuitability] Could not resolve plot coords: {e}")

        if resolved_lat is None or resolved_lng is None:
            return {"error": "Either plot_id or lat/lng is required", "rainfed": [], "irrigated": []}

        # --- L0 auto-hydration ---
        hydration = {
            "used_l0_broker": False,
            "used_snapshot": False,
            "used_live_fetch": False,
            "missing_fields": [],
            "fallback_fields": [],
        }
        warnings = []
        input_sources = {}  # field → source provenance

        # Explicit request values are highest priority
        mean_temp_c = req.mean_temp_c
        annual_rainfall_mm = req.annual_rainfall_mm
        et0_mm = req.et0_mm
        soil_ph = req.soil_ph
        soil_texture = req.soil_texture
        soil_awc = req.soil_awc
        soil_salinity = req.soil_salinity_ds_m
        slope_pct = req.slope_pct
        elevation_m = req.elevation_m
        frost_days = req.frost_days
        heat_days = req.heat_days_above_35

        for field, val in [
            ("mean_temp_c", mean_temp_c), ("annual_rainfall_mm", annual_rainfall_mm),
            ("soil_ph", soil_ph), ("soil_texture", soil_texture),
        ]:
            if val is not None:
                input_sources[field] = "explicit_request"

        # Priority 2: Try IntelligenceSnapshot
        snapshot_data = None
        try:
            from pymongo import MongoClient
            import os
            mongo_url = os.environ.get("MONGODB_URI") or os.environ.get("DATABASE_URL", "")
            if mongo_url and "mongodb" in mongo_url:
                client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
                db_name = mongo_url.split("/")[-1].split("?")[0] if "/" in mongo_url else "agriwise"
                db = client[db_name]
                query = {"plotId": req.plot_id} if req.plot_id else {
                    "lat": {"$gte": resolved_lat - 0.01, "$lte": resolved_lat + 0.01},
                    "lng": {"$gte": resolved_lng - 0.01, "$lte": resolved_lng + 0.01},
                }
                snapshot_data = db["IntelligenceSnapshot"].find_one(
                    query, sort=[("capturedAt", -1)]
                )
                if snapshot_data:
                    hydration["used_snapshot"] = True
        except Exception as e:
            print(f"[CropSuitability] Snapshot lookup failed: {e}")

        # Extract from snapshot
        if snapshot_data:
            current = snapshot_data.get("current", {}) or {}
            soil = current.get("soil", {}) or {}
            weather = current.get("open_meteo_agri", {}) or {}
            nasa = current.get("nasa_power", {}) or {}

            if mean_temp_c is None and weather.get("current", {}).get("temperature_2m") is not None:
                mean_temp_c = weather["current"]["temperature_2m"]
                input_sources["mean_temp_c"] = "snapshot_open_meteo"
            if annual_rainfall_mm is None and nasa.get("annualRainfall") is not None:
                annual_rainfall_mm = nasa["annualRainfall"]
                input_sources["annual_rainfall_mm"] = "snapshot_nasa_power"
            if soil_ph is None and soil.get("ph") is not None:
                soil_ph = soil["ph"]
                input_sources["soil_ph"] = "snapshot_soilgrids"
            if soil_texture is None:
                # Derive texture from clay/sand content
                s_clay = soil.get("clay")
                s_sand = soil.get("sand")
                if s_clay is not None and s_sand is not None:
                    if s_sand > 60:
                        soil_texture = "sandy_loam"
                    elif s_clay > 35:
                        soil_texture = "clay_loam"
                    else:
                        soil_texture = "loam"
                    input_sources["soil_texture"] = "snapshot_soilgrids_derived"
            if elevation_m is None and weather.get("elevation") is not None:
                elevation_m = weather["elevation"]
                input_sources["elevation_m"] = "snapshot_open_meteo"

        # Priority 3/4: L0 broker if critical fields still missing
        critical_missing = []
        if mean_temp_c is None:
            critical_missing.append("mean_temp_c")
        if annual_rainfall_mm is None:
            critical_missing.append("annual_rainfall_mm")
        if soil_ph is None:
            critical_missing.append("soil_ph")
        if soil_texture is None:
            critical_missing.append("soil_texture")

        if critical_missing:
            try:
                from layer0.data_gateway import broker as l0_broker
                sources_needed = []
                if mean_temp_c is None or annual_rainfall_mm is None:
                    sources_needed.extend(["open_meteo_agri", "nasa_power"])
                if soil_ph is None or soil_texture is None:
                    sources_needed.append("soilgrids")
                if sources_needed:
                    l0_results = l0_broker.get_bulk(
                        sources_needed, req.plot_id or "",
                        resolved_lat, resolved_lng,
                    )
                    hydration["used_l0_broker"] = True

                    # Extract from L0
                    om = l0_results.get("open_meteo_agri") or {}
                    np_data = l0_results.get("nasa_power") or {}
                    sg = l0_results.get("soilgrids") or {}

                    if mean_temp_c is None and om.get("current", {}).get("temperature_2m") is not None:
                        mean_temp_c = om["current"]["temperature_2m"]
                        input_sources["mean_temp_c"] = "l0_open_meteo"
                    if annual_rainfall_mm is None and np_data.get("annualRainfall") is not None:
                        annual_rainfall_mm = np_data["annualRainfall"]
                        input_sources["annual_rainfall_mm"] = "l0_nasa_power"
                    if soil_ph is None and sg.get("ph") is not None:
                        soil_ph = sg["ph"]
                        input_sources["soil_ph"] = "l0_soilgrids"
                    if soil_texture is None:
                        s_clay = sg.get("clay")
                        s_sand = sg.get("sand")
                        if s_clay is not None and s_sand is not None:
                            soil_texture = "sandy_loam" if s_sand > 60 else "clay_loam" if s_clay > 35 else "loam"
                            input_sources["soil_texture"] = "l0_soilgrids_derived"
                    if elevation_m is None and om.get("elevation") is not None:
                        elevation_m = om["elevation"]
                        input_sources["elevation_m"] = "l0_open_meteo"
            except Exception as e:
                print(f"[CropSuitability] L0 broker hydration failed: {e}")
                warnings.append(f"L0 broker hydration failed: {e}")

        # Priority 5: Fallback defaults + warnings
        fallback_fields = []
        if mean_temp_c is None:
            mean_temp_c = 20.0
            fallback_fields.append("mean_temp_c")
            input_sources["mean_temp_c"] = "fallback_default"
        if annual_rainfall_mm is None:
            annual_rainfall_mm = 400.0
            fallback_fields.append("annual_rainfall_mm")
            input_sources["annual_rainfall_mm"] = "fallback_default"
        if soil_ph is None:
            soil_ph = 7.0
            fallback_fields.append("soil_ph")
            input_sources["soil_ph"] = "fallback_default"
        if soil_texture is None:
            soil_texture = "loam"
            fallback_fields.append("soil_texture")
            input_sources["soil_texture"] = "fallback_default"
        if soil_awc is None:
            soil_awc = 0.15
            fallback_fields.append("soil_awc")
        if soil_salinity is None:
            soil_salinity = 0.0
        if slope_pct is None:
            slope_pct = 0.0
        if elevation_m is None:
            elevation_m = 0.0

        hydration["fallback_fields"] = fallback_fields
        hydration["missing_fields"] = [f for f in ["mean_temp_c", "annual_rainfall_mm", "soil_ph", "soil_texture"]
                                       if f in fallback_fields]

        # Compute overall confidence
        critical_fallbacks = [f for f in ["mean_temp_c", "annual_rainfall_mm", "soil_ph", "soil_texture"]
                              if f in fallback_fields]
        if len(critical_fallbacks) == 0:
            overall_confidence = "HIGH"
        elif len(critical_fallbacks) <= 1:
            overall_confidence = "MEDIUM"
        else:
            overall_confidence = "LOW"
            warnings.append(
                "Suitability is preliminary because required environmental fields are missing: "
                + ", ".join(critical_fallbacks)
            )

        # --- Run suitability engine ---
        engine = CropSuitabilityEngine()
        result = engine.evaluate(
            lat=resolved_lat,
            lng=resolved_lng,
            elevation_m=elevation_m,
            mean_temp_c=mean_temp_c,
            annual_rainfall_mm=annual_rainfall_mm,
            et0_mm=et0_mm,
            soil_ph=soil_ph,
            soil_texture=soil_texture,
            soil_awc=soil_awc,
            soil_salinity_ds_m=soil_salinity,
            slope_pct=slope_pct,
            irrigation_type=req.irrigation_type,
            frost_days=frost_days,
            heat_days_above_35=heat_days,
            soil_depth_cm=req.soil_depth_cm or 100.0,
        )

        print(f"[CropSuitability] Evaluated {result.total_evaluated} crops for "
              f"lat={resolved_lat:.2f} lng={resolved_lng:.2f} (confidence={overall_confidence})")
        print(f"  Top rainfed: {result.rainfed[0].name if result.rainfed else 'none'} "
              f"({result.rainfed[0].score if result.rainfed else 0})")
        print(f"  Hydration: snapshot={hydration['used_snapshot']}, broker={hydration['used_l0_broker']}, "
              f"fallbacks={fallback_fields}")

        response = result.to_dict()
        response["data_completeness"] = {
            "overall_confidence": overall_confidence,
            "used_fallbacks": len(fallback_fields) > 0,
            "input_sources": input_sources,
        }
        response["hydration"] = hydration
        response["warnings"] = warnings
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "rainfed": [], "irrigated": []}


class CropFeedbackRequest(BaseModel):
    plot_id: str
    confirmed_crop: str
    engine_prediction: str = ""
    engine_confidence: float = 0.0
    lat: Optional[float] = None
    lng: Optional[float] = None


@app.post("/v2/crop-feedback")
def api_v2_crop_feedback(
    req: CropFeedbackRequest,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Record crop feedback as an audit-only user assertion.
    """
    if req.plot_id and req.plot_id.strip() != namespace.plot_id.strip():
        raise HTTPException(
            status_code=403,
            detail="Payload plot_id does not match authenticated token namespace",
        )
    if not req.plot_id:
        req.plot_id = namespace.plot_id
    """

    This path does not create ground truth, update a learned prior, or make a
    record eligible for model training. Promotion requires a separate trusted
    verification and release-governance workflow.
    
    FIX BUG-4: Now retrieves cached phenology from the engine's last
    identification result instead of storing empty {}.
    """
    try:
        from layer2_veg_int.crop_ml import CropFeedbackStore
        from layer2_veg_int.crop_identification import crop_id_engine
        
        # IMP-5: Retrieve cached phenology from the engine's last result
        cached_phenology = {}
        cached_ndvi = None
        try:
            cache_key = f"{req.lat}_{req.lng}"
            cached = crop_id_engine._last_results.get(cache_key, {})
            cached_phenology = cached.get("phenology", {})
            cached_ndvi = cached.get("ndvi_series")
            if cached_phenology:
                print(f"[CropFeedback] Using cached phenology: {len(cached_phenology)} metrics")
        except Exception as e:
            print(f"[CropFeedback] Could not retrieve cached phenology: {e}")
        
        store = CropFeedbackStore()
        fpath = store.record_observation(
            plot_id=req.plot_id,
            confirmed_crop=req.confirmed_crop,
            engine_prediction=req.engine_prediction,
            engine_confidence=req.engine_confidence,
            phenology=cached_phenology,
            ndvi_series=cached_ndvi,
            lat=req.lat,
            lng=req.lng,
        )
        
        stats = store.get_accuracy_stats()
        print(f"[CropFeedback] Recorded: {req.confirmed_crop} for plot {req.plot_id[:8]} "
              f"(engine said {req.engine_prediction}). Total samples: {stats['total']}, "
              f"accuracy: {stats.get('accuracy', 'N/A')}, "
              f"phenology={'YES' if cached_phenology else 'NO'}")
        
        return {
            "status": "audit_recorded",
            "learning_eligible": False,
            "authority": "unverified_user_feedback",
            "total_samples": stats["total"],
            "engine_accuracy": stats.get("accuracy"),
            "has_phenology": bool(cached_phenology),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "status": "failed"}


import threading
import time
import os
from collections import OrderedDict

_plot_cache_locks = {}
_plot_cache_locks_lock = threading.Lock()
_surface_payload_memory_cache = OrderedDict()
_surface_payload_memory_cache_lock = threading.Lock()
_SURFACE_MEMORY_CACHE_MAX = 2


def _get_surface_memory_cache(path: str, mtime: float):
    with _surface_payload_memory_cache_lock:
        entry = _surface_payload_memory_cache.get(path)
        if not entry or entry[0] != mtime:
            return None
        _surface_payload_memory_cache.move_to_end(path)
        return dict(entry[1])


def _put_surface_memory_cache(path: str, mtime: float, payload: dict):
    with _surface_payload_memory_cache_lock:
        _surface_payload_memory_cache[path] = (mtime, payload)
        _surface_payload_memory_cache.move_to_end(path)
        while len(_surface_payload_memory_cache) > _SURFACE_MEMORY_CACHE_MAX:
            _surface_payload_memory_cache.popitem(last=False)

def get_plot_cache_lock(plot_id: str) -> threading.Lock:
    with _plot_cache_locks_lock:
        if plot_id not in _plot_cache_locks:
            _plot_cache_locks[plot_id] = threading.Lock()
        return _plot_cache_locks[plot_id]

class FileLock:
    def __init__(self, lock_path):
        self.lock_path = lock_path
        self.fd = None

    def acquire(self, timeout=300):
        start_time = time.time()
        while True:
            if os.path.exists(self.lock_path):
                try:
                    mtime = os.path.getmtime(self.lock_path)
                    if time.time() - mtime > 600:
                        print(f"[FileLock] Stale lock detected, clearing: {self.lock_path}")
                        os.remove(self.lock_path)
                except Exception:
                    pass
            try:
                self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                return True
            except FileExistsError:
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Could not acquire lock on {self.lock_path} within {timeout}s")
                time.sleep(0.5)

    def release(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            try:
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
            except Exception:
                pass
            self.fd = None

@app.post("/v2/run")
def api_v2_run(
    req: V2RunRequest,
    namespace: PlotNamespace = Depends(require_internal_service_request)
):
    """
    Unified entrypoint as a persistent FastAPI endpoint. 
    Replaces the slow subprocess.spawn("py", "run_entrypoint.py") approach.
    """
    import time as _time
    from orchestrator_v2.run_entrypoint import (
        _parse_context, run_chat_mode, run_full_mode, run_surfaces_mode
    )
    
    _t0 = _time.perf_counter()
    try:
        ctx = _parse_context(req.context)
        if namespace.plot_id != ctx.get("plot_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Header X-Plot-Id does not match request context plot_id"
            )
        
        # Construct mock args for run_chat_mode to read history/exp
        class MockArgs:
            history = req.history
            exp = req.exp
            userMode = req.userMode
            
        args = MockArgs()
        query = req.query.strip() if req.query else ""
        
        if req.mode == "chat":
            _plot_id = namespace.plot_id
            _clear_progress(namespace)  # Reset stale progress
            _update_progress(namespace, "Connecting to satellite network", "running")
            result = run_chat_mode(
                ctx, query, args,
                progress_cb=lambda stage, status, elapsed=0.0: _update_progress(namespace, stage, status, elapsed),
                authenticated_namespace=namespace
            )
            _update_progress(namespace, "Complete", "done")
            
            # Clear progress after short delay
            def _delayed_clear():
                import time
                time.sleep(5)
                _clear_progress(namespace)
            _threading.Thread(target=_delayed_clear, daemon=True).start()
        elif req.mode == "full":
            result = run_full_mode(ctx, query, authenticated_namespace=namespace)
        elif req.mode == "surfaces":
            # Extract plot_id & run_id for progress tracking
            _plot_id = namespace.plot_id
            _run_id = getattr(req, "run_id", None) or f"run-{_plot_id}"
            _publication_geometry_hash = str(ctx.get("geometry_hash") or "")
            if not _publication_geometry_hash:
                geometry_value = ctx.get("field_geometry") or ctx.get("polygon")
                if geometry_value:
                    import hashlib as _publication_hashlib
                    import json as _publication_json
                    _publication_geometry_hash = _publication_hashlib.sha256(
                        _publication_json.dumps(
                            geometry_value, sort_keys=True, default=str
                        ).encode("utf-8")
                    ).hexdigest()[:8]
            
            # --- Surfaces Cache Check ---
            import os
            import json
            import hashlib
            from layer10_sire.surface_contract import (
                RENDER_AUTHORIZATION_VERSION,
                SURFACES_SCHEMA_VERSION,
                validate_declared_publication_status,
            )
            
            SURFACES_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts", "surfaces_cache")
            
            # Policy keys to include in cache key/validation
            clamped_intensity = max(0.15, min(float(req.visual_intensity or 0.40), 0.75))
            intensity_str = f"{clamped_intensity:.2f}"
            
            policy_payload = {
                "schema_version": SURFACES_SCHEMA_VERSION,
                "ASMAE_ENABLED": os.environ.get("ASMAE_ENABLED", "false").lower(),
                "L10_ASMAE_SURFACES_ENABLED": os.environ.get("L10_ASMAE_SURFACES_ENABLED", "false").lower(),
                "L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED": os.environ.get("L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED", "false").lower(),
                "surface_ladder_policy_version": os.environ.get("SURFACE_LADDER_POLICY_VERSION", "v1"),
                "render_policy_version": os.environ.get("RENDER_POLICY_VERSION", "v1"),
                "mode_surface_plan_version": os.environ.get("MODE_SURFACE_PLAN_VERSION", "v1"),
                "display_grid_policy_version": os.environ.get("DISPLAY_GRID_POLICY_VERSION", "v1"),
                # One scientific snapshot contains authorization views for every
                # source policy; switching policy must not rerun L1-L10.
                "source_policy": "canonical",
            }
            policy_json = json.dumps(policy_payload, sort_keys=True)
            policy_hash = hashlib.md5(policy_json.encode()).hexdigest()[:12]

            def _is_terminal_no_data_payload(payload):
                """True only for an explicit, non-spatial terminal data-gap contract."""
                if not isinstance(payload, dict):
                    return False
                surfaces = payload.get("surfaces")
                if not isinstance(surfaces, list) or len(surfaces) != 0:
                    return False
                quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
                provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
                return bool(
                    payload.get("placeholder_only") is True
                    or payload.get("degradation_mode") == "DATA_GAP"
                    or quality.get("degradation_mode") == "DATA_GAP"
                    or provenance.get("degradation_mode") == "DATA_GAP"
                    or provenance.get("spatial_processing_short_circuited") is True
                )

            def _validate_surface_authority(payload):
                """Return (is_valid, reason) for cacheable/renderable L10 output."""
                if not isinstance(payload, dict):
                    return False, "payload_not_object"

                publication_ok, _derived_status, publication_reason = (
                    validate_declared_publication_status(payload)
                )
                if not publication_ok:
                    return False, publication_reason

                surfaces = payload.get("surfaces")
                if not isinstance(surfaces, list):
                    return False, "surfaces_missing_or_empty"
                terminal_no_data = _is_terminal_no_data_payload(payload)
                if not surfaces and not terminal_no_data:
                    return False, "surfaces_missing_or_empty"
                if payload.get("render_authorization_version") != RENDER_AUTHORIZATION_VERSION:
                    return False, "render_authorization_version_missing"
                if not isinstance(payload.get("render_authorizations"), dict) or not payload["render_authorizations"]:
                    return False, "render_authorizations_missing"
                if not isinstance(payload.get("asmae_proof"), dict) or not payload["asmae_proof"]:
                    return False, "asmae_proof_missing"
                if not isinstance(payload.get("mode_display_state"), dict) or not payload["mode_display_state"]:
                    return False, "mode_display_state_missing"
                if not isinstance(payload.get("source_policy_display_state"), dict) or not payload["source_policy_display_state"]:
                    return False, "source_policy_display_state_missing"

                # An upstream outage is a valid terminal state when it carries
                # a complete deny-by-default authority contract. It is returned
                # to the client, but intentionally never cached below.
                if terminal_no_data:
                    return True, "terminal_no_data"

                surface_types = {
                    s.get("type") or s.get("semantic_type")
                    for s in surfaces
                    if isinstance(s, dict)
                }
                if "NDVI_CLEAN" in surface_types:
                    required_masks = {
                        "OBSERVED_DATA_MASK_NDVI",
                        "GAP_FILL_MASK_NDVI",
                        "VALID_DATA_MASK_NDVI",
                    }
                    missing_masks = required_masks - surface_types
                    if missing_masks:
                        return False, "ndvi_masks_missing:" + ",".join(sorted(missing_masks))

                return True, "ok"
            
            surfaces_cache_path = os.path.join(SURFACES_CACHE_DIR, f"surfaces_{_plot_id}_{SURFACES_SCHEMA_VERSION}_{intensity_str}_{policy_hash}.json")
            CACHE_MAX_AGE = 4 * 3600  # 4 hours cache TTL
            
            def _check_and_return_cache():
                # A completed worker atomically publishes a frontend-ready
                # L1/L2/L10 snapshot. Prefer that canonical head over an older
                # route-local surface cache so completion is visible without
                # waiting for another full synchronous pipeline run.
                if not req.force_refresh:
                    try:
                        from services.agribrain.layer05_asmae.plot_snapshot_store import (
                            load_latest_plot_snapshot,
                        )
                        canonical = load_latest_plot_snapshot(
                            namespace, _publication_geometry_hash or None
                        )
                        candidate = (
                            dict(canonical.get("frontend_payload") or {})
                            if canonical else {}
                        )
                        age_seconds = (
                            canonical.get("snapshot_age_seconds")
                            if canonical else None
                        )
                        candidate_intensity = float(
                            candidate.get("visual_intensity")
                            or (candidate.get("provenance") or {}).get(
                                "visual_intensity", 0.40
                            )
                        )
                        authority_ok, _ = _validate_surface_authority(
                            candidate
                        )
                        from services.agribrain.eo.sentinel import _extract_ring_coordinates
                        poly_ring = _extract_ring_coordinates(ctx.get("field_geometry") or ctx.get("polygon"))
                        bounds_enclosed = True
                        if poly_ring and len(poly_ring) >= 3:
                            p_xs = [pt[0] for pt in poly_ring]
                            p_ys = [pt[1] for pt in poly_ring]
                            poly_min_x, poly_max_x = min(p_xs), max(p_xs)
                            poly_min_y, poly_max_y = min(p_ys), max(p_ys)
                            candidate_surfs = candidate.get("surfaces") or []
                            if candidate_surfs and isinstance(candidate_surfs, list):
                                s0 = candidate_surfs[0]
                                g_spec = s0.get("display_grid_spec") or s0.get("grid_spec") or candidate.get("grid_spec") or {}
                                g_bounds = g_spec.get("bounds") if isinstance(g_spec, dict) else None
                                if g_bounds and len(g_bounds) == 4:
                                    g_min_x, g_min_y, g_max_x, g_max_y = g_bounds
                                    if (g_min_x > poly_min_x + 1e-5 or g_max_x < poly_max_x - 1e-5 or
                                        g_min_y > poly_min_y + 1e-5 or g_max_y < poly_max_y - 1e-5):
                                        bounds_enclosed = False
                                        logger.info(
                                            f"Rejecting snapshot cache: grid bounds {g_bounds} do not enclose plot polygon [{poly_min_x}, {poly_min_y}, {poly_max_x}, {poly_max_y}]"
                                        )
                        if (
                            candidate
                            and authority_ok
                            and bounds_enclosed
                            and isinstance(age_seconds, (int, float))
                            and age_seconds < CACHE_MAX_AGE
                            and abs(candidate_intensity - clamped_intensity)
                            < 0.001
                            and candidate.get("intelligence_snapshot_id")
                            == canonical.get("snapshot_id")
                        ):
                            candidate.pop("layer10", None)
                            candidate["cache"] = {
                                "hit": True,
                                "schema_version": SURFACES_SCHEMA_VERSION,
                                "source": "canonical_worker_snapshot",
                            }
                            candidate["requested_source_policy"] = (
                                req.source_policy
                            )
                            return candidate
                    except Exception as canonical_cache_exc:
                        logger.debug(
                            "Canonical worker snapshot not reusable: %s",
                            canonical_cache_exc,
                        )
                if not req.force_refresh and os.path.exists(surfaces_cache_path):
                    cache_valid = False
                    try:
                        file_mtime = os.path.getmtime(surfaces_cache_path)
                        if (_time.time() - file_mtime) < CACHE_MAX_AGE:
                            print(f"[CACHE_HIT] Loading surfaces from file cache for plot {_plot_id}")
                            cached_result = _get_surface_memory_cache(surfaces_cache_path, file_mtime)
                            if cached_result is None:
                                with open(surfaces_cache_path, "r") as f:
                                    cached_result = json.load(f)
                                if isinstance(cached_result, dict):
                                    _put_surface_memory_cache(surfaces_cache_path, file_mtime, cached_result)
                            
                            if isinstance(cached_result, dict):
                                cached_ver = cached_result.get("version") or cached_result.get("cache", {}).get("schema_version")
                                surfs = cached_result.get("surfaces", [])
                                if cached_ver == SURFACES_SCHEMA_VERSION and isinstance(surfs, list) and len(surfs) > 0:
                                    cache_valid = True
                                    for s in surfs:
                                        if not isinstance(s, dict) or ("type" not in s and "semantic_type" not in s) or "grounding_class" not in s or ("values" not in s and "grid_b64" not in s):
                                            cache_valid = False
                                            break
                                        if "values" in s and s["values"] is not None:
                                            grid_vals = s["values"]
                                            if not isinstance(grid_vals, list) or len(grid_vals) == 0:
                                                cache_valid = False
                                                break
                                            row_len = len(grid_vals[0]) if isinstance(grid_vals[0], list) else 0
                                            for row in grid_vals:
                                                if not isinstance(row, list) or len(row) != row_len:
                                                    cache_valid = False
                                                    break
                                            if not cache_valid:
                                                break
                                    
                                    if cache_valid:
                                        if (
                                            cached_result.get("asmae_enabled") != policy_payload["ASMAE_ENABLED"] or
                                            cached_result.get("l10_asmae_surfaces_enabled") != policy_payload["L10_ASMAE_SURFACES_ENABLED"] or
                                            cached_result.get("l10_asmae_diagnostic_aliases_enabled") != policy_payload["L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED"] or
                                            cached_result.get("surface_ladder_policy_version") != policy_payload["surface_ladder_policy_version"] or
                                            cached_result.get("render_policy_version") != policy_payload["render_policy_version"] or
                                            cached_result.get("mode_surface_plan_version") != policy_payload["mode_surface_plan_version"] or
                                            cached_result.get("display_grid_policy_version") != policy_payload["display_grid_policy_version"] or
                                            cached_result.get("source_policy") != "canonical"
                                        ):
                                            cache_valid = False

                                    if cache_valid:
                                        from services.agribrain.eo.sentinel import _extract_ring_coordinates
                                        poly_ring = _extract_ring_coordinates(ctx.get("field_geometry") or ctx.get("polygon"))
                                        if poly_ring and len(poly_ring) >= 3:
                                            p_xs = [pt[0] for pt in poly_ring]
                                            p_ys = [pt[1] for pt in poly_ring]
                                            poly_min_x, poly_max_x = min(p_xs), max(p_xs)
                                            poly_min_y, poly_max_y = min(p_ys), max(p_ys)
                                            s0 = surfs[0] if surfs else {}
                                            g_spec = s0.get("display_grid_spec") or s0.get("grid_spec") or cached_result.get("grid_spec") or {}
                                            g_bounds = g_spec.get("bounds") if isinstance(g_spec, dict) else None
                                            if g_bounds and len(g_bounds) == 4:
                                                g_min_x, g_min_y, g_max_x, g_max_y = g_bounds
                                                if (g_min_x > poly_min_x + 1e-5 or g_max_x < poly_max_x - 1e-5 or
                                                    g_min_y > poly_min_y + 1e-5 or g_max_y < poly_max_y - 1e-5):
                                                    cache_valid = False
                                                    logger.info(
                                                        f"Rejecting file cache: grid bounds {g_bounds} do not enclose plot polygon [{poly_min_x}, {poly_min_y}, {poly_max_x}, {poly_max_y}]"
                                                    )

                                    # BC.10.18: Reject payloads missing render authorization fields
                                    if cache_valid:
                                        _render_auth_ver = cached_result.get("render_authorization_version", "")
                                        _render_auths = cached_result.get("render_authorizations")
                                        _asmae_proof = cached_result.get("asmae_proof")
                                        if (
                                            _render_auth_ver != RENDER_AUTHORIZATION_VERSION or
                                            not isinstance(_render_auths, dict) or
                                            len(_render_auths) == 0 or
                                            not isinstance(_asmae_proof, dict) or
                                            len(_asmae_proof) == 0
                                        ):
                                            print(f"[CACHE_REJECT] BC.10.18 authority fields missing or empty for plot {_plot_id} — forcing recompute")
                                            cache_valid = False

                                    if cache_valid:
                                        cache_valid, _authority_reason = _validate_surface_authority(cached_result)
                                        if not cache_valid:
                                            print(f"[CACHE_REJECT] BC.10.20R1 incomplete authority payload for plot {_plot_id}: {_authority_reason}; forcing recompute")
                                        elif _is_terminal_no_data_payload(cached_result):
                                            print(f"[CACHE_REJECT] Terminal no-data payload for plot {_plot_id} is not reusable; forcing recompute")
                                            cache_valid = False

                                    if cache_valid:
                                        # Legacy cache entries duplicated the complete L10
                                        # payload under `layer10`; all fields already exist
                                        # canonically at the top level.
                                        cached_result.pop("layer10", None)
                                        cached_result["cache"] = {"hit": True, "schema_version": SURFACES_SCHEMA_VERSION}
                                        cached_result["requested_source_policy"] = req.source_policy
                                        return cached_result
                            if not cache_valid:
                                try:
                                    os.remove(surfaces_cache_path)
                                except Exception:
                                    pass
                    except Exception:
                        try:
                            if os.path.exists(surfaces_cache_path):
                                os.remove(surfaces_cache_path)
                        except Exception:
                            pass
                return None

            def _commit_cached_result(cached_payload):
                committed = dict(cached_payload)
                # A cache hit is a new request for an existing immutable
                # scientific publication. Never relabel the scientific run.
                committed["request_run_id"] = _run_id
                committed["publication_run_id"] = (
                    committed.get("publication_run_id") or committed.get("run_id")
                )
                committed["provenance"] = dict(committed.get("provenance") or {})
                committed["provenance"]["request_run_id"] = _run_id
                _persist_run_result(
                    _run_id,
                    namespace,
                    committed,
                    _publication_geometry_hash,
                )
                _update_progress(
                    namespace, "Complete", "done",
                    round(_time.perf_counter() - _t0, 2), run_id=_run_id,
                )
                return committed

            # 1. Early cache check
            cached_res = _check_and_return_cache()
            if cached_res:
                return _commit_cached_result(cached_res)

            # 2. Acquire lock and compute
            lock_path = os.path.join(SURFACES_CACHE_DIR, f"surfaces_{_plot_id}_{SURFACES_SCHEMA_VERSION}.lock")
            os.makedirs(SURFACES_CACHE_DIR, exist_ok=True)
            
            _pi_executor = None
            with get_plot_cache_lock(_plot_id):
                file_lock = FileLock(lock_path)
                try:
                    file_lock.acquire(timeout=300)
                    
                    # Double check cache inside the lock
                    cached_res = _check_and_return_cache()
                    if cached_res:
                        return _commit_cached_result(cached_res)
                        
                    _update_progress(namespace, "Connecting to satellite network", "running", run_id=_run_id)

                    # L1 is the canonical source for the bridge. Starting a
                    # second provider fetch here duplicated I/O and contended
                    # with the orchestrator even when its result was unused.
                    _pi_future = None

                    _update_progress(namespace, "Acquiring Earth Observation imagery", "running", run_id=_run_id)

                    ctx["visual_intensity"] = clamped_intensity
                    ctx["user_mode"] = getattr(req, "userMode", "farmer")
                    # One scientific execution publishes the complete surface
                    # inventory.  The requested policy selects a client-side
                    # authorization view and never changes acquisition/model identity.
                    ctx["source_policy"] = "canonical"
                    ctx["requested_source_policy"] = req.source_policy or "satellite"

                    # Pass the progress callback to run_surfaces_mode
                    result = run_surfaces_mode(
                        ctx, query,
                        progress_cb=lambda stage, status, elapsed=0.0: _update_progress(namespace, stage, status, elapsed, run_id=_run_id),
                        authenticated_namespace=namespace
                    )
                    _t_surfaces = _time.perf_counter()
                    print(f"[PERF] /v2/run: run_surfaces_mode = {_t_surfaces - _t0:.2f}s")

                    # Never bridge, cache, or return a fallback payload that cannot
                    # satisfy the frontend render-authority contract.
                    _authority_ok, _authority_reason = _validate_surface_authority(result)
                    if not _authority_ok:
                        if _pi_executor is not None:
                            _pi_executor.shutdown(wait=False)
                            _pi_executor = None
                        _update_progress(namespace, "Surface authority unavailable", "failed", run_id=_run_id)
                        
                        l10_errors = (result.get("layer_results") or {}).get("layer_10", {}).get("errors") or []
                        if l10_errors:
                            raise HTTPException(
                                status_code=500,
                                detail=f"L10_EXECUTION_CONTRACT_ERROR: Layer 10 pipeline error: {'; '.join(l10_errors)}",
                            )
                        raise HTTPException(
                            status_code=503,
                            detail=f"Layer 10 authority contract incomplete: {_authority_reason}; result was not cached",
                        )

                    # ── Kalman NDVI Bridge ──────
                    _update_progress(namespace, "Calibrating vegetation indices", "running", run_id=_run_id)
                    try:
                        _l1_ndvi = result.get("_l1_kalman_ndvi")
                        _l1_sh = result.get("_l1_sh_indices")
                        if _l1_ndvi:
                            print(f"[API] Kalman bridge: Using direct L1 output from result (avoiding redundant fetch)")
                            _bridge_kalman_ndvi_to_surfaces(result, _l1_ndvi, _l1_sh)
                        else:
                            print("[API] Kalman bridge skipped: canonical L1 output had no NDVI records")
                    except Exception as e:
                        print(f"[API] Kalman bridge failed (non-fatal): {e}")
                    finally:
                        if _pi_executor is not None:
                            _pi_executor.shutdown(wait=False)
                            _pi_executor = None
                    _update_progress(namespace, "Calibrating vegetation indices", "done", round(_time.perf_counter() - _t_surfaces, 2), run_id=_run_id)

                    # ── Resolution Upscale (always applied) ─────────────────
                    _update_progress(namespace, "Enhancing spatial resolution", "running", run_id=_run_id)
                    try:
                        # Disabled for V92.4: upscaling is handled on-demand by grid contracts
                        # _upscale_surfaces(result, scale=4)
                        pass
                    except Exception as e:
                        print(f"[API] Surface upscale failed (non-fatal): {e}")
                    _update_progress(namespace, "Enhancing spatial resolution", "done", round(_time.perf_counter() - _t_surfaces, 2), run_id=_run_id)

                    # ── Zone Recalibration ──────────────────────────────────
                    _update_progress(namespace, "Finalizing scouting regions", "running", run_id=_run_id)
                    try:
                        _recalibrate_zones(result)
                    except Exception as e:
                        print(f"[API] Zone recalibration failed (non-fatal): {e}")
                    _update_progress(namespace, "Finalizing scouting regions", "done", round(_time.perf_counter() - _t_surfaces, 2), run_id=_run_id)
                    request_perf = result.setdefault("request_performance_ms", {})
                    request_perf["api_postprocess"] = round(
                        (_time.perf_counter() - _t_surfaces) * 1000.0, 3
                    )
                    request_perf["api_total_before_response_encoding"] = round(
                        (_time.perf_counter() - _t0) * 1000.0, 3
                    )

                    # Save scientific surfaces, but never persist a transient
                    # provider-outage/no-data response as reusable evidence.
                    if _is_terminal_no_data_payload(result):
                        print(f"[CACHE_SKIP] Terminal no-data payload for plot {_plot_id} was returned but not cached")
                    else:
                        try:
                            os.makedirs(SURFACES_CACHE_DIR, exist_ok=True)
                            tmp_path = f"{surfaces_cache_path}.tmp"
                            with open(tmp_path, "w") as f:
                                # Save a clean copy without internal large keys
                                clean_res = result.copy()
                                clean_res["version"] = SURFACES_SCHEMA_VERSION
                                clean_res["visual_intensity"] = float(clean_res.get("provenance", {}).get("visual_intensity", 0.40))
                                clean_res["asmae_enabled"] = policy_payload["ASMAE_ENABLED"]
                                clean_res["l10_asmae_surfaces_enabled"] = policy_payload["L10_ASMAE_SURFACES_ENABLED"]
                                clean_res["l10_asmae_diagnostic_aliases_enabled"] = policy_payload["L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED"]
                                clean_res["surface_ladder_policy_version"] = policy_payload["surface_ladder_policy_version"]
                                clean_res["render_policy_version"] = policy_payload["render_policy_version"]
                                clean_res["mode_surface_plan_version"] = policy_payload["mode_surface_plan_version"]
                                clean_res["display_grid_policy_version"] = policy_payload["display_grid_policy_version"]
                                clean_res["source_policy"] = policy_payload["source_policy"]
                                clean_res.pop("_l1_kalman_ndvi", None)
                                clean_res.pop("_l1_sh_indices", None)
                                json.dump(clean_res, f)
                                f.flush()
                                os.fsync(f.fileno())

                            # Atomic replace retry loop
                            for attempt in range(5):
                                try:
                                    os.replace(tmp_path, surfaces_cache_path)
                                    _put_surface_memory_cache(
                                        surfaces_cache_path,
                                        os.path.getmtime(surfaces_cache_path),
                                        clean_res,
                                    )
                                    print(f"[CACHE_STORE] Saved computed surfaces atomically to cache for plot {_plot_id}")
                                    break
                                except OSError as e:
                                    if attempt == 4:
                                        raise
                                    print(f"[CACHE] Retry atomic replace due to error: {e}. Sleeping 100ms...")
                                    import time as _sleep_time
                                    _sleep_time.sleep(0.1)
                        except Exception as ce:
                            print(f"[CACHE] surfaces cache save failed: {ce}")
                            try:
                                if os.path.exists(tmp_path):
                                    os.remove(tmp_path)
                            except Exception:
                                pass

                    # Clean result for the response
                    result.pop("_l1_kalman_ndvi", None)
                    result.pop("_l1_sh_indices", None)
                    result["requested_source_policy"] = req.source_policy
                    result["source_policy"] = "canonical"
                    result["cache"] = {"hit": False, "schema_version": SURFACES_SCHEMA_VERSION}
                    result["run_id"] = result.get("run_id") or _run_id
                    result["publication_run_id"] = (
                        result.get("publication_run_id") or result["run_id"]
                    )
                    result["request_run_id"] = _run_id
                    result["provenance"] = dict(result.get("provenance") or {})
                    result["provenance"]["request_run_id"] = _run_id

                    # Result publication is the commit point. A client may now
                    # safely observe terminal progress and retrieve the exact
                    # payload even if the original HTTP response was lost.
                    _persist_run_result(
                        _run_id,
                        namespace,
                        result,
                        _publication_geometry_hash,
                    )
                    _update_progress(
                        namespace, "Complete", "done",
                        round(_time.perf_counter() - _t0, 2), run_id=_run_id,
                    )

                finally:
                    file_lock.release()

            # Keep the terminal record addressable by plot and run id. The
            # durable result is the commit point and clients may reconnect well
            # after the original request finishes; clearing this mapping after
            # five seconds caused the UI to report an unretrievable result.
        else:
            raise HTTPException(status_code=400, detail=f"Unknown mode: {req.mode}")
        
        _t_total = _time.perf_counter()
        print(f"[PERF] /v2/run: TOTAL ({req.mode}) = {_t_total - _t0:.2f}s")
            
        return result

    except HTTPException as exc:
        target_ns = locals().get("namespace") or locals().get("_plot_id")
        if target_ns:
            _terminalize_progress(
                target_ns,
                "failed",
                run_id=locals().get("_run_id"),
                failure=_request_failure_from_exception(exc),
            )
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        target_ns = locals().get("namespace") or locals().get("_plot_id")
        if target_ns:
            _terminalize_progress(
                target_ns,
                "failed",
                run_id=locals().get("_run_id"),
                failure=_request_failure_from_exception(e),
            )
        raise HTTPException(status_code=500, detail={"error": str(e), "type": "AgriBrainRunError"})

@app.post("/v2/sandbox/run")
def api_v2_sandbox_run(req: V2SandboxRequest):
    """
    Exposes the What-If Biophysical Simulation Sandbox over a high-fidelity REST API.
    Directly runs Liebig and Penman forward-propagation equations with explicit parameters.
    """
    from orchestrator_v2.run_entrypoint import _parse_context
    from layer9_interface.engines.what_if_sandbox import what_if_sandbox
    try:
        ctx = _parse_context(req.context)
        overrides = {
            "temp_offset": req.temp_offset,
            "rain_volume": req.rain_volume,
            "irrigation_mode": req.irrigation_mode,
            "nitrogen_applied": req.nitrogen_applied
        }
        sim_results = what_if_sandbox.project(query="", context=ctx, overrides=overrides)
        return {"success": True, "data": sim_results}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "type": "SandboxExecutionError"})

# ============================================================================
# Direct Specialized AI Endpoints
# ============================================================================

@app.post("/ai/disease_risk")
def disease_risk(req: SpecializedAIRequest):
    """Direct access to Disease Risk AI"""
    context = req.context.copy()
    context["crop"] = req.crop
    return disease_risk_ai.predict(context)

@app.post("/ai/phenology")
def phenology(req: SpecializedAIRequest):
    """Direct access to Phenology AI"""
    context = req.context.copy()
    context["crop"] = req.crop
    return phenology_ai.predict(context)

@app.post("/ai/spray_window")
def spray_window(req: SpecializedAIRequest):
    """Direct access to Spray Window AI"""
    return spray_window_ai.predict(req.context)

@app.post("/ai/water_stress")
def water_stress(req: SpecializedAIRequest):
    """Direct access to Water Stress AI"""
    context = req.context.copy()
    context["crop"] = req.crop
    return water_stress_ai.predict(context)

# ============================================================================
# Pipeline & Training Endpoints
# ============================================================================

class PipelineRunRequest(BaseModel):
    """Request to run a training pipeline"""
    config: Optional[Dict[str, Any]] = None

@app.post("/pipeline/{ai_name}/run")
def run_pipeline(ai_name: str, req: PipelineRunRequest = None):
    """Trigger a training pipeline for specified AI"""
    try:
        from pipelines.disease_risk_pipeline import create_pipeline
        
        pipeline = create_pipeline(ai_name)
        if not pipeline:
            raise HTTPException(status_code=404, detail=f"Pipeline not found for: {ai_name}")
        
        config = req.config if req else {}
        run = pipeline.execute(config)
        
        return {
            "status": "completed" if run.status.value == "completed" else "failed",
            "run_id": run.run_id,
            "stages": run.stages,
            "artifacts": run.artifacts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/{ai_name}/status")
def pipeline_status(ai_name: str):
    """Get pipeline status and run history"""
    from pathlib import Path
    pipeline_dir = Path(__file__).parent.parent / "pipelines" / ai_name / "runs"
    
    if not pipeline_dir.exists():
        return {"ai_name": ai_name, "runs": [], "message": "No runs yet"}
    
    runs = []
    for run_dir in sorted(pipeline_dir.iterdir(), reverse=True)[:10]:
        state_file = run_dir / "run_state.json"
        if state_file.exists():
            with open(state_file) as f:
                runs.append(json.load(f))
    
    return {"ai_name": ai_name, "runs": runs}

@app.get("/models")
def list_models():
    """List all registered trained models"""
    from core.pipeline import model_registry
    return model_registry.list_models()

@app.get("/models/{model_name}")
def get_model(model_name: str, version: str = None):
    """Get specific model info"""
    from core.pipeline import model_registry
    model = model_registry.get_model(model_name, version)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")
    return model

# ============================================================================
# Data Collector Endpoints
# ============================================================================

class PlotRegistrationRequest(BaseModel):
    """Request to register a plot for data collection"""
    farm_id: Optional[str] = None
    plot_id: str
    coordinates: Dict[str, float]
    crop: str
    area: Optional[float] = 0

@app.post("/collector/register-plot")
def register_plot(
    req: PlotRegistrationRequest,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Register a new plot for automatic data collection.
    """
    farm_id = namespace.farm_id
    if req.plot_id and req.plot_id.strip() != namespace.plot_id.strip():
        raise HTTPException(
            status_code=403,
            detail="Payload plot_id does not match authenticated token namespace",
        )
    if req.farm_id and req.farm_id.strip() != namespace.farm_id.strip():
        raise HTTPException(
            status_code=403,
            detail="Payload farm_id does not match authenticated token namespace",
        )

    # Now also triggers the BootstrapEngine to pre-fetch ALL data sources
    # (weather, satellite, soil, etc.) so the first dashboard load is instant.
    from core.data_collector import data_collector
    
    result = data_collector.register_plot(
        farm_id=farm_id,
        plot_id=req.plot_id,
        coordinates=req.coordinates,
        crop=req.crop,
        area=req.area
    )

    # Trigger background bootstrap (pre-fetch all data sources)
    bootstrap_result = None
    try:
        from layer0.data_gateway.bootstrap_engine import BootstrapEngine
        from layer0.data_gateway import broker
        import threading

        lat = req.coordinates.get("lat", 0)
        lng = req.coordinates.get("lng", 0)

        def _bg_bootstrap():
            try:
                engine = BootstrapEngine(broker)
                engine.bootstrap_plot(
                    req.plot_id, lat, lng,
                    plot_info={"crop_type": req.crop, "area_ha": req.area},
                    skip_bulk=True,  # Defer heavy historical to refresh worker
                )
            except Exception as e:
                print(f"[BOOTSTRAP] Background bootstrap failed for {req.plot_id[:8]}: {e}")

        threading.Thread(target=_bg_bootstrap, daemon=True, name=f"bootstrap-{req.plot_id[:8]}").start()
        print(f"[BOOTSTRAP] Background bootstrap started for plot {req.plot_id[:8]}")
    except Exception as e:
        print(f"[BOOTSTRAP] Bootstrap setup failed (non-fatal): {e}")

    return {
        "status": "registered",
        "plot": result,
        "message": "Plot registered. Data pre-fetch started in background."
    }

@app.post("/collector/snapshot/{farm_id}/{plot_id}")
def capture_snapshot(
    farm_id: str,
    plot_id: str,
    data_type: str = "weather",
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Manually trigger a data snapshot for a plot"""
    from core.data_collector import data_collector
    
    if data_type == "weather":
        result = data_collector.capture_weather_snapshot(farm_id, plot_id)
    elif data_type == "satellite":
        result = data_collector.capture_satellite_snapshot(farm_id, plot_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown data_type: {data_type}")
    
    if result:
        return {"status": "captured", "observation": result}
    else:
        raise HTTPException(status_code=404, detail="Plot not found or capture failed")

@app.post("/collector/collect-all")
def collect_all_weather():
    """Trigger weather collection for ALL registered plots"""
    from core.data_collector import data_collector
    result = data_collector.collect_all_weather()
    return result

@app.get("/collector/status")
def collector_status():
    """Get overall data collection status"""
    from core.data_collector import data_collector
    return data_collector.get_status()

@app.get("/data/{farm_id}/{plot_id}/observations")
def get_plot_observations(
    farm_id: str,
    plot_id: str,
    start_date: str = None,
    end_date: str = None,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Get collected observations for a plot"""
    from core.data_collector import data_collector
    return data_collector.get_plot_data(farm_id, plot_id, start_date, end_date)

# ============================================================================
# Data Gateway Diagnostics & Observability Dashboard
# ============================================================================
from app.cache_admin import router as cache_admin_router
app.include_router(cache_admin_router)


# ============================================================================
# V61D - Visual Basemap Tile Proxy Routing
# ============================================================================

@app.get("/v2/visual-tile/{provider}/{z}/{x}/{y}")
def api_v2_visual_tile(provider: str, z: int, x: int, y: int, scene_id: Optional[str] = ""):
    """
    V61E: Proxy / render visual satellite tiles or return HTTP 302 redirects.
    """
    from fastapi.responses import Response, RedirectResponse
    from visual_sources.tile_proxy import render_tile
    try:
        res = render_tile(provider, z, x, y, scene_id or "")
        if isinstance(res, str):
            # HTTP 302 Redirect directly to TiTiler
            return RedirectResponse(url=res, status_code=302)
        return Response(content=res, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tile rendering failed: {e}")



# Startup has been refactored to use the FastAPI lifespan context manager at the top.


# ═══════════════════════════════════════════════════════════════════════════
# v6.0B — Crop Label Confirmation Endpoint
# ═══════════════════════════════════════════════════════════════════════════

class CropLabelRequest(BaseModel):
    """Request body for POST /v2/crop-label."""
    plot_id: str
    crop_code: str
    planting_date: Optional[str] = None
    harvest_date: Optional[str] = None
    label_source: str = "farmer_confirmed"
    created_by: Optional[str] = None
    notes: Optional[str] = None
    synthetic: Optional[bool] = False


@app.post("/v2/crop-label")
def api_v2_crop_label(
    req: CropLabelRequest,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Submit an authenticated, unverified farmer crop declaration.

    Browser-supplied authority fields are ignored. This endpoint records a
    LOW-confidence farmer declaration for audit and registry conditioning;
    it does not create a verified or training-eligible ground-truth label.

    The canonical runtime mutation is the authenticated ``CropCycle`` update.
    ``ConfirmedCropLabel`` is a derivative audit/training-candidate record and
    never becomes ground truth merely because this endpoint wrote it.
    """
    store = None
    try:
        if namespace.plot_id != req.plot_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Header X-Plot-Id does not match request plot_id",
            )

        from layer2_veg_int.labels.label_schema import (
            CropLabel,
            validate_crop_code,
            canonicalize_geometry_hash,
            get_hierarchy_targets,
        )
        from layer2_veg_int.labels.label_quality import compute_label_quality
        from layer2_veg_int.crop_science_data import get_crop_group
        from services.agribrain.app.crop_label_authority import (
            derive_farmer_crop_label_authority,
        )
        from services.agribrain.app.crop_runtime_declaration import (
            normalize_declared_crop_code,
            persist_farmer_crop_declaration,
        )

        server_authority = derive_farmer_crop_label_authority(namespace)

        if req.planting_date is not None or req.harvest_date is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Crop identity confirmation cannot assert planting or "
                    "harvest dates; use the typed crop-cycle workflow"
                ),
            )

        normalized_crop_code = normalize_declared_crop_code(req.crop_code)
        # 1. Validate crop_code — reject unknown (no wheat default)
        if not validate_crop_code(normalized_crop_code):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown crop_code '{normalized_crop_code}'. "
                       f"Must be from the 212-crop registry.",
            )

        # 3. Resolve crop group
        crop_group = get_crop_group(normalized_crop_code)

        # 4. Bind the declaration to the canonical runtime CropCycle. Generic
        # PlotObservation rows are not a valid crop-model tensor, so this
        # endpoint never auto-attaches a feature snapshot.
        geometry_hash = "NO_GEOMETRY"
        warnings = []
        fv_snapshot = None
        fv_ref = "crop_model_input_receipt_required"
        runtime_declaration = None

        try:
            from bson import ObjectId
            from layer2_veg_int.labels.label_store import MongoLabelStore

            mongo_url = os.environ.get("MONGODB_URI") or os.environ.get("DATABASE_URL", "")
            if not mongo_url or "mongodb" not in mongo_url:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Canonical crop-cycle store is unavailable",
                )
            store = MongoLabelStore(mongo_url)
            db = store.db

            runtime_receipt = persist_farmer_crop_declaration(
                db,
                namespace=namespace,
                crop_code=normalized_crop_code,
            )
            runtime_declaration = runtime_receipt.to_dict()

            try:
                query_id = ObjectId(req.plot_id)
            except Exception:
                query_id = req.plot_id
                warnings.append("plot_id_not_objectid_string_fallback")
            plot_doc = db["Plot"].find_one({"_id": query_id})
            if plot_doc and plot_doc.get("geoJson"):
                geometry_hash = canonicalize_geometry_hash(plot_doc["geoJson"])
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Canonical crop declaration persistence failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Canonical crop declaration persistence failed",
            ) from e

        # 5. Create label
        label = CropLabel(
            label_id="",  # Auto-generated UUID
            plot_id=req.plot_id,
            geometry_hash=geometry_hash,
            crop_code=normalized_crop_code,
            crop_group=crop_group,
            label_source=server_authority["label_source"],
            label_confidence=server_authority["label_confidence"],
            planting_date=None,
            harvest_date=None,
            created_by=server_authority["created_by"],
            notes=req.notes,
            feature_vector_snapshot=fv_snapshot,
            feature_vector_ref=fv_ref,
            synthetic=False,
            authority_validated=False,
            tenant_id=namespace.tenant_id,
            farm_id=namespace.farm_id,
            crop_cycle_id=runtime_declaration["crop_cycle_id"],
            runtime_declaration_receipt=runtime_declaration,
            # This is an audit claim, not independent verification of a
            # hierarchy target for model training.
            supported_hierarchy_levels=[],
        )

        # 6. Compute quality
        quality = compute_label_quality(label)

        # 7. Hierarchy targets
        hierarchy = get_hierarchy_targets(normalized_crop_code, crop_group)

        # Store a derivative audit record. Canonical runtime state has already
        # committed, so an audit-store failure is surfaced but must not make
        # the browser believe the CropCycle declaration failed.
        label_id = None
        conflict_info = None
        audit_record_status = "failed"
        try:
            label_id, conflict = store.save_label(label)
            audit_record_status = conflict.action or "insert"
            if conflict.conflict_type:
                conflict_info = {
                    "conflict_type": conflict.conflict_type,
                    "existing_label_id": conflict.existing_label_id,
                    "action": conflict.action,
                    "warnings": conflict.warnings,
                }
        except Exception:
            logger.exception(
                "Crop declaration audit record persistence failed"
            )
            warnings.append("crop_label_audit_record_not_persisted")

        return {
            "label_id": label_id,
            "crop_code": normalized_crop_code,
            "crop_group": crop_group,
            "hierarchy_targets": hierarchy,
            "quality": {
                "overall": quality.overall_quality,
                "tier": quality.quality_tier,
                "warnings": quality.quality_warnings + warnings,
            },
            "conflict_info": conflict_info,
            "label_schema_version": label.label_schema_version,
            "runtime_declaration": runtime_declaration,
            "audit_record": {
                "status": audit_record_status,
                "role": "unverified_training_candidate_only",
                "label_id": label_id,
            },
            "hierarchy_targets_role": "registry_derived_display_only",
            "authority": {
                "label_source": server_authority["label_source"],
                "label_confidence": server_authority["label_confidence"],
                "verification_status": server_authority[
                    "verification_status"
                ],
                "training_eligible": server_authority["training_eligible"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Label creation failed: {e}")
    finally:
        if store is not None:
            try:
                store.client.close()
            except Exception:
                logger.warning("Crop label Mongo client close failed")


@app.get("/v2/crop-model/readiness")
def api_crop_model_readiness(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """Retrieve fail-closed audit-label readiness for training.

    Restricted to admins using AGRIBRAIN_ADMIN_TOKEN.
    """
    admin_token = os.environ.get("AGRIBRAIN_ADMIN_TOKEN")
    is_prod = (os.environ.get("NODE_ENV") == "production" or os.environ.get("ENVIRONMENT") == "production" or os.environ.get("ENV") == "production" or os.environ.get("APP_ENV") == "production")
    
    if is_prod and not admin_token:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: AGRIBRAIN_ADMIN_TOKEN is missing in production environment."
        )
        
    effective_token = admin_token or "dev_admin_token"
    import hmac
    if not x_admin_token or not hmac.compare_digest(x_admin_token, effective_token):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid Admin Token"
        )

    store = None
    try:
        from layer2_veg_int.labels.label_store import MongoLabelStore
        from layer2_veg_int.labels.label_quality import compute_label_quality
        from layer2_veg_int.labels.label_schema import (
            TRAINING_ELIGIBLE_LABEL_SOURCES,
        )
        from services.agribrain.app.crop_training_snapshot_authority import (
            assess_crop_training_snapshot,
        )

        db_uri = os.environ.get("MONGODB_URI") or os.environ.get("DATABASE_URL", "")
        store = MongoLabelStore(db_uri)
        all_labels = store.get_all_labels(active_only=False)

        real_labels_active = []
        synthetic_count = 0
        real_count = 0

        for l in all_labels:
            is_synthetic = getattr(l, "synthetic", False)
            if not is_synthetic and l.notes and "synthetic" in l.notes.lower():
                is_synthetic = True

            if is_synthetic:
                synthetic_count += 1
            else:
                real_count += 1
                if l.is_active:
                    real_labels_active.append(l)

        # Real active label metrics
        total_real = len(real_labels_active)
        labels_with_fv = sum(1 for l in real_labels_active if l.feature_vector_snapshot is not None)
        missing_fv = total_real - labels_with_fv

        # Count authority- and lineage-complete dataset candidates. This is a
        # dataset sufficiency metric, not production release authorization.
        eligible_samples = 0
        by_group = {}
        by_tier = {}

        for l in real_labels_active:
            q = compute_label_quality(l)
            tier = q.quality_tier
            by_tier[tier] = by_tier.get(tier, 0) + 1
            
            group = l.crop_group or "unknown"
            by_group[group] = by_group.get(group, 0) + 1

            partitions = (
                getattr(l, "tenant_id", None),
                getattr(l, "farm_id", None),
                getattr(l, "crop_cycle_id", None),
                getattr(l, "region_partition", None),
                getattr(l, "season_partition", None),
                getattr(l, "sensor_regime", None),
            )
            training_input = assess_crop_training_snapshot(
                feature_vector_snapshot=l.feature_vector_snapshot,
                crop_model_input_receipt=getattr(
                    l, "crop_model_input_receipt", None
                ),
                tenant_id=getattr(l, "tenant_id", None),
                farm_id=getattr(l, "farm_id", None),
                plot_id=l.plot_id,
                crop_cycle_id=getattr(l, "crop_cycle_id", None),
                expected_receipt_hash=getattr(
                    l, "crop_model_input_receipt_hash", None
                ),
            )
            if (
                tier in ("A", "B", "C")
                and l.feature_vector_snapshot is not None
                and l.label_source in TRAINING_ELIGIBLE_LABEL_SOURCES
                and getattr(l, "authority_validated", False) is True
                and l.label_confidence == "HIGH"
                and bool(l.geometry_hash)
                and l.geometry_hash != "NO_GEOMETRY"
                and bool(l.layer1_run_id)
                and all(partitions)
                and training_input.eligible
            ):
                eligible_samples += 1

        from services.agribrain.app.crop_label_authority import (
            assess_crop_dataset_release_readiness,
        )

        release_readiness = assess_crop_dataset_release_readiness(
            eligible_samples
        )
        dataset_training_ready = release_readiness[
            "dataset_training_ready"
        ]
        recommendations = []
        if not dataset_training_ready:
            recommendations.append(
                "Collect independently verified, lineage-complete labels for dataset construction."
            )
            recommendations.append(
                f"Need at least {max(0, 50 - eligible_samples)} more authority-valid "
                "active labels (Tier C or higher with complete partitions)."
            )
        else:
            recommendations.append(
                "Dataset threshold met; production remains blocked until "
                "external release validation succeeds."
            )

        return {
            "real_labels": total_real,
            "synthetic_labels": synthetic_count,
            "labels_with_feature_vectors": labels_with_fv,
            "labels_missing_feature_vectors": missing_fv,
            "eligible_training_samples": eligible_samples,
            **release_readiness,
            "recommendations": recommendations,
            "distributions": {
                "by_crop_group": by_group,
                "by_quality_tier": by_tier,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Readiness query failed: {e}")
    finally:
        if store is not None:
            try:
                store.client.close()
            except Exception:
                logger.warning("Crop readiness Mongo client close failed")


# ═══════════════════════════════════════════════════════════════════════════
# v6.0C — Hierarchical Model Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class ModelTrainRequest(BaseModel):
    dry_run: bool = True
    min_quality_tier: str = "C"
    max_samples: Optional[int] = None
    include_historical: bool = False
    include_synthetic: bool = False


@app.post("/v2/crop-model/train")
def api_train_crop_model(
    req: ModelTrainRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """Train the diagnostic hierarchy from authority-validated crop labels.
    
    Restricted to admin users using AGRIBRAIN_ADMIN_TOKEN.
    """
    admin_token = os.environ.get("AGRIBRAIN_ADMIN_TOKEN")
    is_prod = (os.environ.get("NODE_ENV") == "production" or os.environ.get("ENVIRONMENT") == "production" or os.environ.get("ENV") == "production" or os.environ.get("APP_ENV") == "production")
    
    if is_prod and not admin_token:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: AGRIBRAIN_ADMIN_TOKEN is missing in production environment."
        )
        
    effective_token = admin_token or "dev_admin_token"
    import hmac
    if not x_admin_token or not hmac.compare_digest(x_admin_token, effective_token):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid Admin Token"
        )
        
    try:
        from layer2_veg_int.labels.label_store import MongoLabelStore
        from layer2_veg_int.labels.dataset_builder import TrainingDatasetBuilder
        from layer2_veg_int.labels.classifier import HierarchicalCropClassifier
        
        db_uri = os.environ.get("MONGODB_URI") or os.environ.get("DATABASE_URL", "")
        store = MongoLabelStore(db_uri)
        builder = TrainingDatasetBuilder(store)
        
        # Build training set
        dataset = builder.build_dataset(
            min_quality_tier=req.min_quality_tier,
            target_level="L3",
            include_historical=req.include_historical,
            include_synthetic=req.include_synthetic,
        )
        
        samples = dataset.samples
        if req.max_samples and len(samples) > req.max_samples:
            samples = samples[:req.max_samples]
            
        if not samples:
            return {
                "status": "not_trained",
                "reason": "not_enough_labeled_samples_for_L3"
            }
            
        classifier = HierarchicalCropClassifier()
        metadata = classifier.train(samples, dry_run=req.dry_run)
        
        # Reload classifier in engine if trained
        if not req.dry_run and metadata.get("level_status", {}).get("L0") == "trained":
            from layer2_veg_int.crop_identification import crop_id_engine
            if hasattr(crop_id_engine, "_ml_classifier"):
                crop_id_engine._ml_classifier.load()
                
        return {
            "status": "success" if not req.dry_run else "dry_run",
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model training failed: {e}")


@app.get("/v2/crop-model/status")
def api_crop_model_status():
    """Get the current status of the trained hierarchical crop models."""
    try:
        from layer2_veg_int.labels.classifier import HierarchicalCropClassifier
        classifier = HierarchicalCropClassifier()
        meta_path = os.path.join(classifier.model_dir, "model_metadata.json")
        
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return {
                "status": "trained",
                "metadata": meta
            }
        else:
            return {
                "status": "untrained",
                "metadata": None
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status query failed: {e}")


class ModelEvaluateRequest(BaseModel):
    min_quality_tier: str = "C"
    include_historical: bool = False
    crop_groups: Optional[List[str]] = None
    min_feature_completeness: float = 0.3
    dry_run: bool = False
    save_report: bool = True
    include_synthetic: bool = False


@app.post("/v2/crop-model/evaluate")
def api_evaluate_crop_model(
    req: ModelEvaluateRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """Evaluate the hierarchy on authority-validated crop labels.
    
    Restricted to admin users using AGRIBRAIN_ADMIN_TOKEN.
    """
    admin_token = os.environ.get("AGRIBRAIN_ADMIN_TOKEN")
    is_prod = (os.environ.get("NODE_ENV") == "production" or os.environ.get("ENVIRONMENT") == "production" or os.environ.get("ENV") == "production" or os.environ.get("APP_ENV") == "production")
    
    if is_prod and not admin_token:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: AGRIBRAIN_ADMIN_TOKEN is missing in production environment."
        )
        
    effective_token = admin_token or "dev_admin_token"
    import hmac
    if not x_admin_token or not hmac.compare_digest(x_admin_token, effective_token):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid Admin Token"
        )
        
    try:
        from layer2_veg_int.labels.label_store import MongoLabelStore
        from layer2_veg_int.labels.dataset_builder import TrainingDatasetBuilder
        from layer2_veg_int.labels.classifier import HierarchicalCropClassifier
        from layer2_veg_int.labels.evaluator import CropModelEvaluator
        
        db_uri = os.environ.get("MONGODB_URI") or os.environ.get("DATABASE_URL", "")
        store = MongoLabelStore(db_uri)
        builder = TrainingDatasetBuilder(store)
        
        # Build evaluation dataset
        dataset = builder.build_dataset(
            min_quality_tier=req.min_quality_tier,
            target_level="L3",
            crop_groups=req.crop_groups,
            include_historical=req.include_historical,
            min_feature_completeness=req.min_feature_completeness,
            include_synthetic=req.include_synthetic,
        )
        
        classifier = HierarchicalCropClassifier()
        if not classifier.load():
            raise HTTPException(
                status_code=400,
                detail="Evaluation failed: Hierarchical classifier models are not trained/loaded."
            )
            
        evaluator = CropModelEvaluator(classifier)
        
        dataset_filters = {
            "min_quality_tier": req.min_quality_tier,
            "include_historical": req.include_historical,
            "crop_groups": req.crop_groups,
            "min_feature_completeness": req.min_feature_completeness
        }
        
        report = evaluator.evaluate(dataset.samples, dataset_filters=dataset_filters)
        
        # Include summary details
        report["summary"]["excluded_sample_count"] = dataset.excluded_samples
        report["manifest"]["excluded_sample_count"] = dataset.excluded_samples
        report["manifest"]["exclusion_reasons"] = dataset.exclusion_reasons
        
        # Save report if not dry_run and save_report is True
        if not req.dry_run and req.save_report:
            os.makedirs(classifier.model_dir, exist_ok=True)
            report_json_path = os.path.join(classifier.model_dir, "evaluation_report.json")
            report_csv_path = os.path.join(classifier.model_dir, "evaluation_report.csv")
            
            with open(report_json_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
                
            csv_str = CropModelEvaluator.export_csv(report)
            with open(report_csv_path, "w", newline="", encoding="utf-8") as f:
                f.write(csv_str)
                
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model evaluation failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
