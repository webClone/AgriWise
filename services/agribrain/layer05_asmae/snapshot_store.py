"""Canonical latest-snapshot store used by latency-bounded visual requests."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


SNAPSHOT_CONTRACT_VERSION = "asmae_latest_snapshot_v2"
SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "asmae_snapshots"
SNAPSHOT_NODE_DIR = SNAPSHOT_DIR / "nodes"


class SnapshotIntegrityError(ValueError):
    """An immutable ASMAE snapshot reference failed its identity contract."""


def _plot_key(plot_id: str) -> str:
    return hashlib.sha256(str(plot_id).encode("utf-8")).hexdigest()[:32]


def _path(plot_id: str) -> Path:
    return SNAPSHOT_DIR / f"{_plot_key(plot_id)}.json"


def _output_content_hash(result: Dict[str, Any]) -> str:
    plot_state = result.get("plot_state_artifact") or {}
    return str(result.get("content_hash") or plot_state.get("content_hash") or "")


def _read_envelope(path: Path) -> Optional[Dict[str, Any]]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _validate_envelope(
    envelope: Dict[str, Any],
    *,
    snapshot_id: Optional[str] = None,
    plot_id: Optional[str] = None,
    geometry_hash: Optional[str] = None,
) -> bool:
    """Validate identity fields before accepting an immutable snapshot node."""
    if envelope.get("contract_version") != SNAPSHOT_CONTRACT_VERSION:
        return False
    node_snapshot_id = str(envelope.get("snapshot_id") or "")
    result = envelope.get("result")
    node_plot_id = str(envelope.get("plot_id") or "")
    node_geometry_hash = str(envelope.get("geometry_hash") or "")
    if not node_snapshot_id or not isinstance(result, dict):
        return False
    if str(result.get("plot_id") or "") != node_plot_id:
        return False
    if str(envelope.get("output_content_hash") or "") != _output_content_hash(result):
        return False
    if compute_snapshot_id(result, geometry_hash=node_geometry_hash) != node_snapshot_id:
        return False
    if snapshot_id is not None and node_snapshot_id != str(snapshot_id):
        return False
    if plot_id is not None and node_plot_id != str(plot_id):
        return False
    if geometry_hash is not None and node_geometry_hash != str(geometry_hash):
        return False
    return True


def _node_path_for(snapshot_id: str) -> Path:
    clean_id = str(snapshot_id or "")
    if not clean_id.startswith("ASMAE-SNAPSHOT-") or any(
        marker in clean_id for marker in ("/", "\\", "..")
    ):
        raise SnapshotIntegrityError("invalid immutable ASMAE snapshot id")
    return SNAPSHOT_NODE_DIR / f"{clean_id}.json"


def _snapshot_id_from_ref(snapshot_ref: str) -> str:
    ref = str(snapshot_ref or "")
    candidate = Path(ref).name
    snapshot_id = candidate[:-5] if candidate.endswith(".json") else candidate
    # A reference must name exactly one content-addressed node; the mutable
    # per-plot latest head is deliberately not accepted here.
    if not snapshot_id.startswith("ASMAE-SNAPSHOT-"):
        raise SnapshotIntegrityError("snapshot_ref does not identify an immutable node")
    return snapshot_id


def compute_snapshot_id(
    result: Dict[str, Any], *, geometry_hash: str
) -> str:
    """Content-address one completed ASMAE evidence snapshot."""
    plot_state = result.get("plot_state_artifact") or {}
    identity = {
        "contract_version": SNAPSHOT_CONTRACT_VERSION,
        "plot_id": str(result.get("plot_id", "")),
        "geometry_hash": str(geometry_hash or ""),
        "output_content_hash": str(
            result.get("content_hash")
            or plot_state.get("content_hash")
            or ""
        ),
        "crop_posterior_lineage": str(
            result.get("crop_posterior_lineage", "") or ""
        ),
        "crop_influence_manifest_hash": str(
            result.get("crop_influence_manifest_hash", "") or ""
        ),
        "crop_evidence_ledger_hash": str(
            result.get("crop_evidence_ledger_hash", "") or ""
        ),
        "as_of": str(plot_state.get("as_of", "") or ""),
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"ASMAE-SNAPSHOT-{digest[:32]}"


def publish_latest_snapshot(
    result: Dict[str, Any],
    *,
    context_hash: str,
    geometry_hash: str,
) -> str:
    """Publish an immutable evidence node and atomically advance its head.

    The returned reference is always the write-once content-addressed node.
    The per-plot latest file is only a discovery head and must never be bound
    into a worker record or used for durable scientific lineage.
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(str(result.get("plot_id", "")))
    previous = _read_envelope(path) or {}
    snapshot_id = compute_snapshot_id(result, geometry_hash=geometry_hash)
    # The caller and every downstream layer receive the exact same identity.
    result["snapshot_id"] = snapshot_id
    result["intelligence_snapshot_id"] = snapshot_id
    candidate_envelope = {
        "contract_version": SNAPSHOT_CONTRACT_VERSION,
        "snapshot_id": snapshot_id,
        "plot_id": result.get("plot_id"),
        "geometry_hash": geometry_hash,
        "context_hash": context_hash,
        "output_content_hash": _output_content_hash(result),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "supersedes_snapshot_id": previous.get("snapshot_id"),
        "result": result,
    }
    SNAPSHOT_NODE_DIR.mkdir(parents=True, exist_ok=True)
    node_path = _node_path_for(snapshot_id)
    # Content-addressed nodes are write-once.  O_EXCL closes the exists/replace
    # race between two workers publishing the same scientific result.
    try:
        descriptor = os.open(
            node_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        )
    except FileExistsError:
        envelope = _read_envelope(node_path)
        if not envelope or not _validate_envelope(
            envelope,
            snapshot_id=snapshot_id,
            plot_id=str(result.get("plot_id", "")),
            geometry_hash=geometry_hash,
        ):
            raise SnapshotIntegrityError(
                "existing immutable ASMAE snapshot node failed validation"
            )
    else:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(candidate_envelope, handle, sort_keys=True, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        envelope = candidate_envelope

    # Reuse the immutable node exactly as it was committed.  A later latest
    # head is allowed to move, but it can never replace or rewrite this node.
    head_envelope = dict(envelope)
    head_envelope["supersedes_snapshot_id"] = previous.get("snapshot_id")
    temporary = path.with_suffix(
        path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    temporary.write_text(
        json.dumps(head_envelope, sort_keys=True, default=str), encoding="utf-8"
    )
    os.replace(temporary, path)
    return str(node_path)


def load_snapshot_exact(
    *,
    plot_id: str,
    geometry_hash: str,
    snapshot_ref: Optional[str] = None,
    snapshot_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Load exactly one validated immutable node for a plot/grid identity.

    Callers must provide a content-addressed ``snapshot_ref`` or
    ``snapshot_id``.  Passing both is permitted only when they agree.  This
    intentionally cannot follow the mutable latest head.
    """
    if not plot_id or not geometry_hash:
        raise SnapshotIntegrityError("exact snapshot loading requires plot and geometry")
    ref_id = _snapshot_id_from_ref(snapshot_ref) if snapshot_ref else None
    if snapshot_id and ref_id and str(snapshot_id) != ref_id:
        raise SnapshotIntegrityError("snapshot_ref and snapshot_id do not agree")
    requested_id = str(snapshot_id or ref_id or "")
    if not requested_id:
        raise SnapshotIntegrityError("exact snapshot loading requires snapshot_ref or snapshot_id")
    node_path = _node_path_for(requested_id)
    envelope = _read_envelope(node_path)
    if not envelope or not _validate_envelope(
        envelope,
        snapshot_id=requested_id,
        plot_id=str(plot_id),
        geometry_hash=str(geometry_hash),
    ):
        return None
    result = dict(envelope["result"])
    try:
        published = datetime.fromisoformat(
            str(envelope.get("published_at", "")).replace("Z", "+00:00")
        )
        age_days = max(
            0.0,
            (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds()
            / 86400.0,
        )
    except (ValueError, TypeError):
        age_days = None
    result["snapshot_status"] = "immutable_exact"
    result["snapshot_age_days"] = age_days
    result["snapshot_ref"] = str(node_path)
    result["snapshot_id"] = requested_id
    result["intelligence_snapshot_id"] = requested_id
    result.setdefault("geometry_hash", envelope.get("geometry_hash"))
    result.setdefault("snapshot_published_at", envelope.get("published_at"))
    return result


def load_latest_snapshot(plot_id: str, geometry_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = _path(plot_id)
    envelope = _read_envelope(path)
    if not envelope or not _validate_envelope(
        envelope,
        plot_id=str(plot_id),
    ):
        return None
    stored_geometry = str(envelope.get("geometry_hash") or "")
    if geometry_hash and stored_geometry != geometry_hash:
        return None
    result = load_snapshot_exact(
        plot_id=str(plot_id),
        geometry_hash=stored_geometry,
        snapshot_id=str(envelope.get("snapshot_id") or ""),
    )
    if result is None:
        return None
    result["snapshot_status"] = "latest_known_good"
    return result


def snapshot_is_compatible(
    plot_id: str,
    *,
    geometry_hash: str,
    snapshot_id: Optional[str],
    crop_posterior_lineage: str = "",
) -> bool:
    if not snapshot_id:
        return False
    try:
        snapshot = load_snapshot_exact(
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            snapshot_id=snapshot_id,
        )
    except SnapshotIntegrityError:
        return False
    if not snapshot:
        return False
    if crop_posterior_lineage and snapshot.get(
        "crop_posterior_lineage"
    ) != crop_posterior_lineage:
        return False
    return True
