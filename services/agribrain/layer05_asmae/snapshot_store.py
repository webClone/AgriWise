"""Canonical latest-snapshot store used by latency-bounded visual requests."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


SNAPSHOT_CONTRACT_VERSION = "asmae_latest_snapshot_v2"
SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "asmae_snapshots"
SNAPSHOT_NODE_DIR = SNAPSHOT_DIR / "nodes"


def _plot_key(plot_id: str) -> str:
    return hashlib.sha256(str(plot_id).encode("utf-8")).hexdigest()[:32]


def _path(plot_id: str) -> Path:
    return SNAPSHOT_DIR / f"{_plot_key(plot_id)}.json"


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
    """Publish an immutable evidence node and atomically advance its head."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(str(result.get("plot_id", "")))
    previous = {}
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    snapshot_id = compute_snapshot_id(result, geometry_hash=geometry_hash)
    # The caller and every downstream layer receive the exact same identity.
    result["snapshot_id"] = snapshot_id
    result["intelligence_snapshot_id"] = snapshot_id
    envelope = {
        "contract_version": SNAPSHOT_CONTRACT_VERSION,
        "snapshot_id": snapshot_id,
        "plot_id": result.get("plot_id"),
        "geometry_hash": geometry_hash,
        "context_hash": context_hash,
        "output_content_hash": result.get("content_hash"),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "supersedes_snapshot_id": previous.get("snapshot_id"),
        "result": result,
    }
    SNAPSHOT_NODE_DIR.mkdir(parents=True, exist_ok=True)
    node_path = SNAPSHOT_NODE_DIR / f"{snapshot_id}.json"
    # Content-addressed nodes are write-once.  O_EXCL closes the exists/replace
    # race between two workers publishing the same scientific result.
    try:
        descriptor = os.open(
            node_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        )
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(envelope, handle, sort_keys=True, default=str)
            handle.flush()
            os.fsync(handle.fileno())
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(envelope, sort_keys=True, default=str), encoding="utf-8")
    os.replace(temporary, path)
    return str(path)


def load_latest_snapshot(plot_id: str, geometry_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = _path(plot_id)
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if envelope.get("contract_version") != SNAPSHOT_CONTRACT_VERSION:
        return None
    if geometry_hash and envelope.get("geometry_hash") not in {"", geometry_hash}:
        return None
    result = envelope.get("result")
    if not isinstance(result, dict):
        return None
    try:
        published = datetime.fromisoformat(str(envelope.get("published_at", "")).replace("Z", "+00:00"))
        age_days = max(0.0, (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 86400.0)
    except (ValueError, TypeError):
        age_days = None
    result = dict(result)
    result["snapshot_status"] = "latest_known_good"
    result["snapshot_age_days"] = age_days
    result["snapshot_ref"] = str(path)
    result["snapshot_id"] = envelope.get("snapshot_id")
    result["intelligence_snapshot_id"] = envelope.get("snapshot_id")
    result.setdefault("geometry_hash", envelope.get("geometry_hash"))
    result.setdefault("snapshot_published_at", envelope.get("published_at"))
    return result


def snapshot_is_compatible(
    plot_id: str,
    *,
    geometry_hash: str,
    snapshot_id: Optional[str],
    crop_posterior_lineage: str = "",
) -> bool:
    snapshot = load_latest_snapshot(plot_id, geometry_hash)
    if not snapshot or not snapshot_id:
        return False
    if snapshot.get("snapshot_id") != snapshot_id:
        return False
    if crop_posterior_lineage and snapshot.get(
        "crop_posterior_lineage"
    ) != crop_posterior_lineage:
        return False
    return True
