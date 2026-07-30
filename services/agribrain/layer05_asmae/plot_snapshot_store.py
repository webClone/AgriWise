"""Canonical frontend-ready plot snapshots produced after ASMAE completion."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


PLOT_SNAPSHOT_CONTRACT_VERSION = "canonical_plot_snapshot_v1"
PLOT_SNAPSHOT_ROOT = (
    Path(__file__).resolve().parents[1] / "artifacts" / "plot_snapshots"
)


def _plot_key(plot_id: str) -> str:
    return hashlib.sha256(str(plot_id).encode("utf-8")).hexdigest()[:32]


def _plot_dir(plot_id: str) -> Path:
    return PLOT_SNAPSHOT_ROOT / _plot_key(plot_id)


def _head_path(plot_id: str) -> Path:
    return _plot_dir(plot_id) / "head.json"


def _read(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    ).encode("utf-8")


def _atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        path.name
        + f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(_json_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        last_error: Optional[OSError] = None
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                return
            except OSError as exc:
                last_error = exc
                if attempt == 5:
                    break
                time.sleep(0.02 * (2 ** attempt))
        assert last_error is not None
        raise last_error
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def publish_canonical_plot_snapshot(
    *,
    plot_id: str,
    geometry_hash: str,
    snapshot_id: str,
    asmae_result: Dict[str, Any],
    frontend_payload: Dict[str, Any],
    job_id: str,
    manifest_hash: str,
) -> Dict[str, Any]:
    """Write one immutable node, then atomically supersede the plot head."""
    if not str(plot_id).strip():
        raise ValueError("plot_id is required")
    if not str(snapshot_id).startswith("ASMAE-SNAPSHOT-"):
        raise ValueError("canonical snapshot_id is invalid")
    if asmae_result.get("snapshot_id") != snapshot_id:
        raise ValueError("ASMAE result snapshot identity mismatch")
    if frontend_payload.get("intelligence_snapshot_id") != snapshot_id:
        raise ValueError("downstream snapshot identity mismatch")

    directory = _plot_dir(plot_id)
    node_dir = directory / "nodes"
    node_dir.mkdir(parents=True, exist_ok=True)
    node_path = node_dir / f"{snapshot_id}.json"
    prior_head = _read(_head_path(plot_id))
    envelope = {
        "contract_version": PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_id": snapshot_id,
        "plot_id": plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "supersedes_snapshot_id": prior_head.get("snapshot_id"),
        "job_id": str(job_id),
        "manifest_hash": str(manifest_hash),
        "asmae_content_hash": asmae_result.get("content_hash"),
        "crop_posterior_lineage": asmae_result.get(
            "crop_posterior_lineage"
        ),
        "asmae": asmae_result,
        "frontend_payload": frontend_payload,
    }
    encoded = _json_bytes(envelope)
    envelope["node_hash"] = hashlib.sha256(encoded).hexdigest()

    # O_EXCL makes the content-addressed node truly append-only even when two
    # workers finish the same deduplicated job at once.
    try:
        descriptor = os.open(
            str(node_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
        )
    except FileExistsError:
        existing = _read(node_path)
        if existing.get("snapshot_id") != snapshot_id:
            raise ValueError("immutable plot snapshot collision")
        envelope = existing
    else:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_json_bytes(envelope))
            handle.flush()
            os.fsync(handle.fileno())

    head = {
        "contract_version": PLOT_SNAPSHOT_CONTRACT_VERSION,
        "plot_id": plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "snapshot_id": snapshot_id,
        "node_ref": str(node_path),
        "node_hash": envelope.get("node_hash"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic(_head_path(plot_id), head)
    return head


def load_latest_plot_snapshot(
    plot_id: str,
    geometry_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    head = _read(_head_path(plot_id))
    if head.get("contract_version") != PLOT_SNAPSHOT_CONTRACT_VERSION:
        return None
    if geometry_hash and head.get("geometry_hash") != geometry_hash:
        return None
    node_ref = Path(str(head.get("node_ref", "")))
    expected_root = _plot_dir(plot_id).resolve()
    try:
        node_path = node_ref.resolve()
        node_path.relative_to(expected_root)
    except (OSError, ValueError):
        return None
    node = _read(node_path)
    if (
        node.get("contract_version") != PLOT_SNAPSHOT_CONTRACT_VERSION
        or node.get("plot_id") != plot_id
        or node.get("snapshot_id") != head.get("snapshot_id")
    ):
        return None
    try:
        recorded = datetime.fromisoformat(
            str(node.get("recorded_at", "")).replace("Z", "+00:00")
        )
        node["snapshot_age_seconds"] = max(
            0.0,
            (datetime.now(timezone.utc) - recorded.astimezone(timezone.utc))
            .total_seconds(),
        )
    except (ValueError, TypeError):
        node["snapshot_age_seconds"] = None
    node["snapshot_ref"] = str(node_path)
    return node
