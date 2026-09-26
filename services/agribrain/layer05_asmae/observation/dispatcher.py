"""ASMAE Observation Dispatcher — Layer 0.5 Observation Boundary / WP07 / Finding #14.

Receives, validates, and routes observation events from Layer 0, MESIA, and external sensors
into ASMAE's ensemble Kalman filter assimilation pipeline.
Provides a durable file-backed queue with per-plot FIFO ordering, atomic lease acquisition,
and a two-phase transactional commit to CanonicalWorldlineService.
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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from .contracts import ObservationEvent
from ..state.authority import AuthorityVector
from services.agribrain.scientific_contracts.observation import ASMAEObservationPayload
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    WorldlineEventProposal,
)
from services.agribrain.world_model.event_identity import ExternalParentRef

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_ROOT = (
    Path(__file__).resolve().parents[2] / "artifacts" / "observation_queue"
)


def compute_idempotency_key(
    plot_id: str,
    capture_manifest_id: str,
    observation_timestamp: Union[str, datetime],
) -> str:
    """Compute deterministic SHA-256 idempotency key for observation assimilation."""
    ts_str = (
        observation_timestamp.isoformat()
        if hasattr(observation_timestamp, "isoformat")
        else str(observation_timestamp)
    )
    raw = f"{plot_id}:{capture_manifest_id}:{ts_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ObservationAbstentionReceipt:
    """Durable audit record documenting why an observation was abstained from state assimilation."""

    observation_id: str
    source_family: str
    reason: str
    timestamp: datetime
    raw_payload_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "source_family": self.source_family,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "raw_payload_ref": self.raw_payload_ref,
        }


@dataclass(frozen=True)
class AssimilationReceipt:
    """Durable audit record of an ensemble Kalman filter state assimilation."""

    receipt_id: str
    plot_id: str
    observation_id: str
    candidate_node_id: str
    innovation_vector: Tuple[float, ...]
    covariance_min_eigenvalue: float
    assimilated_at: datetime
    status: str = "COMMITTED"
    worldline_event_id: Optional[str] = None
    spatial_support_ref: str = ""
    target_state_variable: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "plot_id": self.plot_id,
            "observation_id": self.observation_id,
            "candidate_node_id": self.candidate_node_id,
            "innovation_vector": list(self.innovation_vector),
            "covariance_min_eigenvalue": self.covariance_min_eigenvalue,
            "assimilated_at": self.assimilated_at.isoformat(),
            "status": self.status,
            "worldline_event_id": self.worldline_event_id,
            "spatial_support_ref": self.spatial_support_ref,
            "target_state_variable": self.target_state_variable,
        }


class ASMAEObservationDispatcher:
    """Central observation routing, durable queueing, and admission engine for ASMAE."""

    def __init__(self, queue_root: Optional[Union[str, Path]] = None) -> None:
        self._pending_admitted: List[ObservationEvent] = []
        self._abstention_log: List[ObservationAbstentionReceipt] = []
        self._queue_root = Path(queue_root) if queue_root else DEFAULT_QUEUE_ROOT
        self._mem_lock = threading.RLock()

    def _plot_queue_dir(self, plot_id: str) -> Path:
        p_clean = str(plot_id or "default_plot").strip()
        safe_name = hashlib.sha256(p_clean.encode("utf-8")).hexdigest()[:16]
        target = (self._queue_root / safe_name).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return target

    @contextmanager
    def _plot_lock(self, plot_dir: Path, timeout_seconds: float = 10.0):
        lock_file = plot_dir / "queue.lock"
        start_time = time.time()
        fd = None
        while time.time() - start_time < timeout_seconds:
            try:
                fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    if lock_file.exists() and time.time() - lock_file.stat().st_mtime > 60.0:
                        lock_file.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                time.sleep(0.01)
        if fd is None:
            raise TimeoutError(f"Could not acquire queue lock for {plot_dir}")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            yield
        finally:
            try:
                lock_file.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    def dispatch_event(
        self,
        event: ObservationEvent,
        plot_id: Optional[str] = None,
        capture_manifest_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch a validated ObservationEvent into ASMAE's durable queue and assimilation pipeline."""
        now = datetime.now(timezone.utc)

        # Resolve plot_id and capture_manifest_id
        resolved_plot_id = plot_id or "default_plot"
        if not plot_id and event.spatial_support_ref:
            for part in event.spatial_support_ref.split(":"):
                if "_MZ_" in part:
                    candidate = part.split("_MZ_")[0]
                    if candidate:
                        resolved_plot_id = candidate
                        break
                elif "plot" in part.lower() or part.startswith("MZ_"):
                    resolved_plot_id = part.split("_MZ_")[0]
                    break

        resolved_manifest_id = capture_manifest_id or event.quality_ref or event.observation_id
        obs_ts = event.valid_time or event.acquisition_time or now

        idempotency_key = compute_idempotency_key(
            resolved_plot_id, resolved_manifest_id, obs_ts
        )

        plot_dir = self._plot_queue_dir(resolved_plot_id)

        with self._plot_lock(plot_dir):
            # Check existing items for idempotency
            for existing_file in sorted(plot_dir.glob("*.json")):
                if existing_file.name.endswith(f"_{idempotency_key}.json") or existing_file.name == f"{idempotency_key}.json":
                    try:
                        existing_data = json.loads(existing_file.read_text(encoding="utf-8"))
                        status = existing_data.get("status")
                        if status == "ABSTAINED":
                            return {
                                "status": "abstained_uncalibrated",
                                "observation_id": event.observation_id,
                                "reason": existing_data.get("reason", "Previously abstained"),
                                "receipt": existing_data.get("receipt", {}),
                                "idempotency_key": idempotency_key,
                                "idempotent": True,
                            }
                        if status == "COMMITTED":
                            return {
                                "status": "already_assimilated",
                                "observation_id": event.observation_id,
                                "receipt": existing_data.get("receipt", {}),
                                "idempotency_key": idempotency_key,
                                "idempotent": True,
                            }
                        if status in ("QUEUED", "LEASED"):
                            return {
                                "status": "admitted_for_assimilation",
                                "observation_id": event.observation_id,
                                "source_family": event.source_family,
                                "queue_position": 1,
                                "idempotency_key": idempotency_key,
                                "idempotent": True,
                            }
                    except Exception:
                        pass

            # Gate on authority: only update state if explicitly authorized
            if not event.authority.state_update_allowed:
                receipt = ObservationAbstentionReceipt(
                    observation_id=event.observation_id,
                    source_family=event.source_family,
                    reason="Authority vector prohibits state_update: qualification unverified or in containment mode",
                    timestamp=now,
                    raw_payload_ref=event.spatial_support_ref,
                )
                with self._mem_lock:
                    self._abstention_log.append(receipt)

                ts_micro = int(time.time() * 1e6)
                item_file = plot_dir / f"{ts_micro:018d}_{idempotency_key}.json"
                record = {
                    "idempotency_key": idempotency_key,
                    "plot_id": resolved_plot_id,
                    "capture_manifest_id": resolved_manifest_id,
                    "observation_timestamp": obs_ts.isoformat(),
                    "enqueued_at": now.isoformat(),
                    "status": "ABSTAINED",
                    "reason": receipt.reason,
                    "receipt": receipt.to_dict(),
                    "observation_id": event.observation_id,
                    "source_family": event.source_family,
                }
                self._atomic_write_json(item_file, record)

                return {
                    "status": "abstained_uncalibrated",
                    "observation_id": event.observation_id,
                    "reason": receipt.reason,
                    "receipt": receipt.to_dict(),
                    "idempotency_key": idempotency_key,
                }

            with self._mem_lock:
                self._pending_admitted.append(event)
            logger.info("Admitted observation %s for ASMAE assimilation", event.observation_id)

            ts_micro = int(time.time() * 1e6)
            item_file = plot_dir / f"{ts_micro:018d}_{idempotency_key}.json"
            record = {
                "idempotency_key": idempotency_key,
                "plot_id": resolved_plot_id,
                "capture_manifest_id": resolved_manifest_id,
                "observation_timestamp": obs_ts.isoformat(),
                "enqueued_at": now.isoformat(),
                "status": "QUEUED",
                "lease_id": None,
                "leased_at": None,
                "lease_expires_at": None,
                "observation_id": event.observation_id,
                "source_family": event.source_family,
                "sensor_id": event.sensor_id,
                "spatial_support_ref": event.spatial_support_ref,
                "quality_ref": event.quality_ref,
                "observation_operator_ref": event.observation_operator_ref,
                "uncertainty_model_ref": event.uncertainty_model_ref,
            }
            self._atomic_write_json(item_file, record)

            return {
                "status": "admitted_for_assimilation",
                "observation_id": event.observation_id,
                "source_family": event.source_family,
                "queue_position": len(self._pending_admitted),
                "idempotency_key": idempotency_key,
            }

    def dispatch_payload(
        self,
        payload: ASMAEObservationPayload,
        plot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert a strongly-typed ASMAEObservationPayload into an ObservationEvent and dispatch."""
        now = datetime.now(timezone.utc)
        is_calibrated = bool(payload.calibration_certificate_id and payload.calibration_certificate_id.strip())

        authority = AuthorityVector(
            visualization_allowed=True,
            state_update_allowed=is_calibrated,
            diagnosis_allowed=True,
        )

        event = ObservationEvent(
            observation_id=payload.observation_id,
            source_family=f"MESIA_{payload.target_state_variable.upper()}",
            sensor_id=f"mesia_{payload.microzone_id}",
            acquisition_time=payload.knowledge_cutoff,
            valid_time=now,
            spatial_support_ref=f"microzone:{payload.microzone_id}:{payload.depth_stratum}",
            quality_ref=f"var:{payload.observation_variance:.4f}",
            observation_operator_ref=payload.forward_operator_id,
            uncertainty_model_ref="gum_metrology_budget",
            authority=authority,
            provider="MESIA_OBSERVATORY",
            processing_level="CALIBRATED_PHYSICAL_INVERSION" if is_calibrated else "UNQUALIFIED_PROPOSAL",
        )
        return self.dispatch_event(
            event,
            plot_id=plot_id or payload.microzone_id.split("_MZ_")[0],
            capture_manifest_id=payload.calibration_certificate_id or payload.observation_id,
        )

    def lease_next_observation(
        self,
        plot_id: str,
        lease_duration_seconds: float = 60.0,
        worker_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Atomically lease the next pending observation in FIFO order for this plot."""
        plot_dir = self._plot_queue_dir(plot_id)
        now = datetime.now(timezone.utc)

        with self._plot_lock(plot_dir):
            for file_path in sorted(plot_dir.glob("*.json")):
                if file_path.name.endswith(".lock") or ".tmp" in file_path.name:
                    continue
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                except Exception:
                    continue

                status = data.get("status")
                is_eligible = False

                if status == "QUEUED":
                    is_eligible = True
                elif status == "LEASED":
                    exp = data.get("lease_expires_at")
                    if exp:
                        try:
                            exp_dt = datetime.fromisoformat(exp)
                            if exp_dt < now:
                                is_eligible = True
                        except ValueError:
                            is_eligible = True

                if is_eligible:
                    lease_id = uuid.uuid4().hex
                    data["status"] = "LEASED"
                    data["lease_id"] = lease_id
                    data["leased_at"] = now.isoformat()
                    data["lease_expires_at"] = (
                        now + timedelta(seconds=lease_duration_seconds)
                    ).isoformat()
                    data["worker_id"] = worker_id or str(os.getpid())
                    data["_file_path"] = str(file_path)

                    self._atomic_write_json(file_path, data)
                    return data

        return None

    def release_lease(
        self,
        plot_id: str,
        idempotency_key: str,
        lease_id: Optional[str] = None,
    ) -> bool:
        """Release an active lease back into QUEUED status."""
        plot_dir = self._plot_queue_dir(plot_id)
        with self._plot_lock(plot_dir):
            for file_path in sorted(plot_dir.glob("*.json")):
                if file_path.name.endswith(f"_{idempotency_key}.json") or file_path.name == f"{idempotency_key}.json":
                    try:
                        data = json.loads(file_path.read_text(encoding="utf-8"))
                        if lease_id and data.get("lease_id") != lease_id:
                            return False
                        data["status"] = "QUEUED"
                        data["lease_id"] = None
                        data["leased_at"] = None
                        data["lease_expires_at"] = None
                        self._atomic_write_json(file_path, data)
                        return True
                    except Exception:
                        return False
        return False

    def complete_lease(
        self,
        plot_id: str,
        idempotency_key: str,
        lease_id: Optional[str] = None,
        receipt: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Complete an observation assimilation and mark queue entry COMMITTED."""
        plot_dir = self._plot_queue_dir(plot_id)
        now = datetime.now(timezone.utc)
        with self._plot_lock(plot_dir):
            for file_path in sorted(plot_dir.glob("*.json")):
                if file_path.name.endswith(f"_{idempotency_key}.json") or file_path.name == f"{idempotency_key}.json":
                    try:
                        data = json.loads(file_path.read_text(encoding="utf-8"))
                        if lease_id and data.get("lease_id") != lease_id:
                            return False
                        data["status"] = "COMMITTED"
                        data["completed_at"] = now.isoformat()
                        if receipt:
                            data["receipt"] = receipt
                        self._atomic_write_json(file_path, data)
                        return True
                    except Exception:
                        return False
        return False

    def commit_assimilation(
        self,
        *,
        plot_id: str,
        candidate_node_id: str,
        assimilation_receipt: AssimilationReceipt,
        geometry_hash: str,
        error_covariance: Optional[Any] = None,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        epsilon: float = 1e-6,
        idempotency_key: Optional[str] = None,
        lease_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Two-phase transactional commit for state assimilation into CanonicalWorldlineService.

        Phase 1: Verify signed innovation residual and positive semi-definiteness of covariance.
        Phase 2: Propose and commit to CanonicalWorldlineService referencing candidate node.
        """
        # Phase 1: Verify Innovation and Covariance Invariants
        if not assimilation_receipt.innovation_vector:
            raise ContractViolation("Innovation vector must not be empty")

        for idx, val in enumerate(assimilation_receipt.innovation_vector):
            if not isinstance(val, (int, float)) or not np.isfinite(val):
                raise ContractViolation(f"Invalid non-finite innovation at index {idx}: {val}")

        # Covariance positive semi-definiteness verification
        if error_covariance is not None:
            cov_mat = np.array(error_covariance, dtype=float)
            if cov_mat.ndim != 2 or cov_mat.shape[0] != cov_mat.shape[1]:
                raise ContractViolation(f"Error covariance must be a square 2D matrix, got shape {cov_mat.shape}")
            eigvals = np.linalg.eigvalsh(cov_mat)
            min_eig = float(np.min(eigvals))
            if min_eig < -epsilon:
                raise ContractViolation(
                    f"Covariance positive semi-definiteness violated: min eigenvalue {min_eig:.6e} < -{epsilon:.6e}"
                )

        if assimilation_receipt.covariance_min_eigenvalue < -epsilon:
            raise ContractViolation(
                f"Assimilation receipt covariance min eigenvalue violated: "
                f"{assimilation_receipt.covariance_min_eigenvalue:.6e} < -{epsilon:.6e}"
            )

        # Phase 2: Commit proposal referencing parent candidate node
        canonical_service = CanonicalWorldlineService()
        event_path = canonical_service._event_path(plot_id, candidate_node_id, tenant_id, namespace)
        if event_path.exists():
            parent_ref = candidate_node_id
        else:
            parent_ref = ExternalParentRef(
                external_namespace="asmae_candidate_node",
                external_event_id=str(candidate_node_id),
                evidence_ref=assimilation_receipt.receipt_id or str(candidate_node_id),
            )

        proposal = WorldlineEventProposal(
            event_type="ASMAE_ASSIMILATION_COMMITTED",
            payload=assimilation_receipt.to_dict(),
            parent_event_ids=(parent_ref,),
            geometry_version=geometry_hash,
            evidence_set_hash=assimilation_receipt.receipt_id,
            model_version="asmae_enkf_v0.5.0",
            authority_ref="PRODUCTION_ASSIMILATED",
            authority_contract_version="authority_v1",
            observation_or_valid_time=assimilation_receipt.assimilated_at.isoformat(),
        )

        committed_event = canonical_service.commit_proposal(
            plot_id=plot_id,
            proposal=proposal,
            tenant_id=tenant_id,
            namespace=namespace,
            effective_at=assimilation_receipt.assimilated_at,
        )

        res_dict = {
            "status": "committed",
            "plot_id": plot_id,
            "event_id": committed_event["event_id"],
            "worldline_event_id": committed_event["event_id"],
            "candidate_node_id": candidate_node_id,
            "receipt": assimilation_receipt.to_dict(),
        }

        # If queue tracking was provided, complete the lease
        if idempotency_key:
            self.complete_lease(
                plot_id=plot_id,
                idempotency_key=idempotency_key,
                lease_id=lease_id,
                receipt=res_dict,
            )

        return res_dict

    def get_pending_observations(self) -> List[ObservationEvent]:
        """Return all admitted observations awaiting Kalman filter update."""
        with self._mem_lock:
            return list(self._pending_admitted)

    def get_abstention_receipts(self) -> List[ObservationAbstentionReceipt]:
        """Return all durable abstention receipts recorded during this session."""
        with self._mem_lock:
            return list(self._abstention_log)

    def clear(self) -> None:
        """Clear the pending admission queue and abstention logs."""
        with self._mem_lock:
            self._pending_admitted.clear()
            self._abstention_log.clear()
