"""Canonical frontend-ready plot snapshots produced after ASMAE completion."""

from __future__ import annotations

import hashlib
import copy
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from services.agribrain.common.plot_namespace import PlotNamespace, _coerce_namespace
from services.agribrain.common.surface_hashing import compute_surface_inventory_hash
from services.agribrain.layer10_sire.surface_contract import (
    SURFACES_SCHEMA_VERSION,
    VALID_PUBLICATION_STATUSES,
    classify_surface_publication,
    validate_declared_publication_status,
)

PLOT_SNAPSHOT_CONTRACT_VERSION = "canonical_plot_snapshot_v1"
PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION = "canonical_plot_snapshot_publication_receipt_v1"
PLOT_PUBLICATION_CONTRACT_VERSION = "canonical_plot_frontend_publication_v1"
PLOT_SNAPSHOT_ROOT = (
    Path(__file__).resolve().parents[1] / "artifacts" / "plot_snapshots"
)

_ASMAE_RUNTIME_FIELDS = frozenset({
    "snapshot_ref",
    "snapshot_status",
    "snapshot_age_days",
    "snapshot_published_at",
    "worldline_event_id",
    "worldline_publish_error",
    "snapshot_publish_error",
    "archive_refresh",
    "archive_refresh_error",
})

# These identities are frozen by the authenticated orchestrator before the
# external worker starts.  Older immutable science nodes do not contain the
# worldline event IDs because those IDs are publication-authority bindings,
# not outputs of the numerical ASMAE kernel.  They must survive the exact-node
# reload used by canonical publication, while any disagreement with a newer
# science node remains a hard integrity failure.
_ASMAE_FROZEN_LINEAGE_FIELDS = (
    "crop_posterior_lineage",
    "crop_worldline_event_id",
    "phenology_worldline_event_id",
    "crop_evidence_ledger_hash",
    "crop_influence_manifest_hash",
)


def _plot_key(namespace: PlotNamespace) -> str:
    return hashlib.sha256(namespace.stable_key().encode("utf-8")).hexdigest()[:32]


def _plot_dir(namespace: PlotNamespace) -> Path:
    return PLOT_SNAPSHOT_ROOT / _plot_key(namespace)


def _head_path(namespace: PlotNamespace) -> Path:
    return _plot_dir(namespace) / "head.json"


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


def _immutable_asmae_payload(
    result: Dict[str, Any],
    *,
    plot_id: str,
    geometry_hash: str,
    snapshot_id: str,
) -> Dict[str, Any]:
    """Bind canonical publication to the immutable ASMAE science node.

    Runner-side worldline/archive fields are attached after the science node
    is written. They are operational receipts, not part of the immutable
    scientific payload. Loading the exact node makes first publication and a
    reintegration retry byte-equivalent instead of order-dependent.
    """
    immutable = copy.deepcopy(result)
    snapshot_ref = str(result.get("snapshot_ref") or "").strip()
    if snapshot_ref:
        from .snapshot_store import SnapshotIntegrityError, load_snapshot_exact

        try:
            exact = load_snapshot_exact(
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                snapshot_ref=snapshot_ref,
                snapshot_id=snapshot_id,
            )
        except SnapshotIntegrityError as exc:
            raise ValueError(
                "canonical publication has no valid immutable ASMAE source"
            ) from exc
        if exact is None:
            raise ValueError(
                "canonical publication immutable ASMAE source is unavailable"
            )
        immutable = exact
        for key in _ASMAE_FROZEN_LINEAGE_FIELDS:
            frozen_value = result.get(key)
            exact_value = immutable.get(key)
            if (
                frozen_value not in (None, "")
                and exact_value not in (None, "")
                and exact_value != frozen_value
            ):
                raise ValueError(
                    f"canonical publication immutable {key} mismatch"
                )
            if exact_value in (None, "") and frozen_value not in (None, ""):
                immutable[key] = copy.deepcopy(frozen_value)
    for key in _ASMAE_RUNTIME_FIELDS:
        immutable.pop(key, None)
    return immutable


def publish_canonical_plot_snapshot(
    *,
    namespace: Optional[Union[PlotNamespace, str]] = None,
    tenant_id: str = "",
    farm_id: str = "",
    plot_id: str = "",
    geometry_hash: str,
    snapshot_id: str,
    asmae_result: Dict[str, Any],
    frontend_payload: Dict[str, Any],
    job_id: str,
    manifest_hash: str,
    execution_identity: Optional[Dict[str, Any]] = None,
    snapshot_kind: str = "asmae",
) -> Dict[str, Any]:
    """Write one immutable node, then atomically supersede the plot head."""
    ns = _coerce_namespace(namespace or plot_id, tenant_id=tenant_id, farm_id=farm_id)

    normalized_kind = str(snapshot_kind or "").strip().lower()
    if normalized_kind == "asmae":
        if not str(snapshot_id).startswith("ASMAE-SNAPSHOT-"):
            raise ValueError("canonical ASMAE snapshot_id is invalid")
        if asmae_result.get("snapshot_id") != snapshot_id:
            raise ValueError("ASMAE result snapshot identity mismatch")
    elif normalized_kind == "layer10_terminal":
        if not str(snapshot_id).startswith("L10-"):
            raise ValueError("canonical Layer 10 snapshot_id is invalid")
        if asmae_result.get("snapshot_id") != snapshot_id:
            raise ValueError("Layer 10 result snapshot identity mismatch")
    else:
        raise ValueError("canonical snapshot kind is invalid")
    if frontend_payload.get("intelligence_snapshot_id") != snapshot_id:
        raise ValueError("downstream snapshot identity mismatch")

    scientific_result = (
        _immutable_asmae_payload(
            asmae_result,
            plot_id=ns.plot_id,
            geometry_hash=str(geometry_hash or ""),
            snapshot_id=snapshot_id,
        )
        if normalized_kind == "asmae"
        else copy.deepcopy(asmae_result)
    )

    directory = _plot_dir(ns)
    node_dir = directory / "nodes"
    node_dir.mkdir(parents=True, exist_ok=True)

    node_path = node_dir / f"{snapshot_id}.json"
    logical_node_ref = str(node_path)
    prior_head = _read(_head_path(ns))

    # The frontend payload is part of both immutable artifacts.  Finalize a
    # private copy before either hash is computed and never mutate it again.
    immutable_frontend_payload = copy.deepcopy(frontend_payload)
    if normalized_kind == "asmae":
        from services.agribrain.layer05_asmae.reintegration import _mark_completed_publication
        _mark_completed_publication(immutable_frontend_payload, str(job_id))
        evidence_lineage = immutable_frontend_payload.get(
            "scientific_evidence_lineage"
        )
        evidence_lineage = (
            evidence_lineage if isinstance(evidence_lineage, dict) else {}
        )
        for key in (
            "crop_posterior_lineage",
            "crop_worldline_event_id",
            "phenology_worldline_event_id",
        ):
            expected = str(scientific_result.get(key) or "").strip()
            if not expected or str(evidence_lineage.get(key) or "") != expected:
                raise ValueError(
                    f"canonical ASMAE publication {key} mismatch"
                )

    surfaces = immutable_frontend_payload.get("surface_pack") or immutable_frontend_payload.get("surfaces") or []
    if (
        normalized_kind == "asmae"
        and scientific_result.get("visual_allowed") is True
        and bool(scientific_result.get("raster_maps"))
        and not surfaces
    ):
        raise ValueError(
            "canonical ASMAE publication has raster evidence but no surfaces"
        )
    if isinstance(surfaces, list):
        inv_hash = compute_surface_inventory_hash(surfaces)
        immutable_frontend_payload["surface_inventory_hash"] = inv_hash

    envelope: Dict[str, Any] = {
        "contract_version": PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": normalized_kind,
        "snapshot_id": snapshot_id,
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "supersedes_snapshot_id": prior_head.get("snapshot_id"),
        "job_id": str(job_id),
        "manifest_hash": str(manifest_hash),
        "crop_posterior_lineage": scientific_result.get("crop_posterior_lineage"),
        "crop_worldline_event_id": scientific_result.get(
            "crop_worldline_event_id"
        ),
        "phenology_worldline_event_id": scientific_result.get(
            "phenology_worldline_event_id"
        ),
        "crop_evidence_ledger_hash": scientific_result.get(
            "crop_evidence_ledger_hash"
        ),
        "crop_influence_manifest_hash": scientific_result.get(
            "crop_influence_manifest_hash"
        ),
        "frontend_payload": immutable_frontend_payload,
    }
    if normalized_kind == "asmae":
        envelope["asmae_content_hash"] = scientific_result.get("content_hash")
        envelope["asmae"] = scientific_result
    else:
        envelope["scientific_content_hash"] = scientific_result.get("content_hash")
        envelope["scientific_result"] = scientific_result

    hashable_envelope = {k: v for k, v in envelope.items() if not k.endswith("_ref")}
    envelope["node_hash"] = hashlib.sha256(_json_bytes(hashable_envelope)).hexdigest()

    try:
        descriptor = os.open(str(node_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        existing = _read(node_path)
        comparable_keys = (
            (
                "contract_version", "snapshot_kind", "snapshot_id",
                "tenant_id", "farm_id", "plot_id", "geometry_hash",
                "asmae_content_hash", "crop_posterior_lineage",
                "crop_worldline_event_id", "phenology_worldline_event_id",
                "crop_evidence_ledger_hash", "crop_influence_manifest_hash",
                "asmae",
            )
            if normalized_kind == "asmae"
            else (
                "contract_version", "snapshot_kind", "snapshot_id",
                "tenant_id", "farm_id", "plot_id", "geometry_hash",
                "scientific_content_hash", "crop_posterior_lineage",
                "crop_worldline_event_id", "phenology_worldline_event_id",
                "crop_evidence_ledger_hash", "crop_influence_manifest_hash",
                "scientific_result",
            )
        )
        if any(
            (
                (existing.get(key) or "asmae") != envelope.get(key)
                if key == "snapshot_kind" and normalized_kind == "asmae"
                else existing.get(key) != envelope.get(key)
            )
            for key in comparable_keys
        ):
            raise ValueError("immutable plot snapshot collision")
        existing_hashable = {
            key: value for key, value in existing.items() if key != "node_hash"
        }
        if existing.get("node_hash") != hashlib.sha256(
            _json_bytes(existing_hashable)
        ).hexdigest():
            raise ValueError("existing immutable plot snapshot hash is invalid")
        envelope = existing
    else:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_json_bytes(envelope))
            handle.flush()
            os.fsync(handle.fileno())

    publication_dir = directory / "publications"
    publication_dir.mkdir(parents=True, exist_ok=True)
    safe_job_id = hashlib.sha256(str(job_id).encode("utf-8")).hexdigest()[:32]
    publication_path = publication_dir / f"{safe_job_id}.json"
    logical_publication_ref = str(publication_path)

    publication = {
        "contract_version": PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": normalized_kind,
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "snapshot_id": snapshot_id,
        "job_id": str(job_id),
        "manifest_hash": str(manifest_hash),
        "crop_posterior_lineage": envelope.get("crop_posterior_lineage"),
        "crop_worldline_event_id": envelope.get("crop_worldline_event_id"),
        "phenology_worldline_event_id": envelope.get(
            "phenology_worldline_event_id"
        ),
        "node_ref": logical_node_ref,
        "node_hash": envelope.get("node_hash"),
        "frontend_payload": immutable_frontend_payload,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    hashable_pub = {k: v for k, v in publication.items() if not k.endswith("_ref")}
    publication["publication_hash"] = hashlib.sha256(_json_bytes(hashable_pub)).hexdigest()

    try:
        publication_descriptor = os.open(str(publication_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        existing_publication = _read(publication_path)
        if (
            existing_publication.get("job_id") != str(job_id)
            or existing_publication.get("manifest_hash") != str(manifest_hash)
            or existing_publication.get("snapshot_id") != snapshot_id
            or existing_publication.get("node_hash") != envelope.get("node_hash")
            or existing_publication.get("frontend_payload") != immutable_frontend_payload
        ):
            raise ValueError("immutable plot frontend publication collision")
        existing_hashable = {
            key: value for key, value in existing_publication.items()
            if not key.endswith("_ref") and key != "publication_hash"
        }
        if existing_publication.get("publication_hash") != hashlib.sha256(
            _json_bytes(existing_hashable)
        ).hexdigest():
            raise ValueError("existing frontend publication hash is invalid")
        publication = existing_publication
    else:
        with os.fdopen(publication_descriptor, "wb") as handle:
            handle.write(_json_bytes(publication))
            handle.flush()
            os.fsync(handle.fileno())

    # Receipt construction is deliberately last: node -> publication ->
    # receipt.  This avoids the former mutation cycle where receipt fields
    # changed the already-hashed frontend payload.
    receipt_dir = directory / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{safe_job_id}.json"
    logical_receipt_ref = str(receipt_path)
    identity = dict(execution_identity or {})
    receipt = {
        "contract_version": PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": normalized_kind,
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "snapshot_id": snapshot_id,
        "node_ref": logical_node_ref,
        "node_hash": envelope.get("node_hash"),
        "source_node_job_id": envelope.get("job_id"),
        "source_node_manifest_hash": envelope.get("manifest_hash"),
        "job_id": str(job_id),
        "manifest_hash": str(manifest_hash),
        "crop_posterior_lineage": envelope.get("crop_posterior_lineage"),
        "crop_worldline_event_id": envelope.get("crop_worldline_event_id"),
        "phenology_worldline_event_id": envelope.get(
            "phenology_worldline_event_id"
        ),
        "worker_contract_version": identity.get("worker_contract_version"),
        "capability_contract_version": identity.get("capability_contract_version"),
        "capability_plan_hash": identity.get("capability_plan_hash"),
        "frontend_publication_ref": logical_publication_ref,
        "frontend_publication_hash": publication.get("publication_hash"),
        "equivalence_reason": "scientific_content_hash_equivalent",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    hashable_receipt = {
        key: value for key, value in receipt.items() if not key.endswith("_ref")
    }
    receipt["receipt_hash"] = hashlib.sha256(
        _json_bytes(hashable_receipt)
    ).hexdigest()

    try:
        receipt_descriptor = os.open(str(receipt_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        existing_receipt = _read(receipt_path)
        comparable = {k: receipt.get(k) for k in receipt if k not in {"recorded_at", "receipt_hash"}}
        existing_comparable = {k: existing_receipt.get(k) for k in receipt if k not in {"recorded_at", "receipt_hash"}}
        if comparable != existing_comparable:
            raise ValueError("immutable plot snapshot publication receipt collision")
        receipt = existing_receipt
    else:
        with os.fdopen(receipt_descriptor, "wb") as handle:
            handle.write(_json_bytes(receipt))
            handle.flush()
            os.fsync(handle.fileno())

    head = {
        "contract_version": PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": normalized_kind,
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "snapshot_id": snapshot_id,
        "node_ref": logical_node_ref,
        "node_hash": envelope.get("node_hash"),
        "publication_job_id": str(job_id),
        "publication_manifest_hash": str(manifest_hash),
        "crop_posterior_lineage": envelope.get("crop_posterior_lineage"),
        "crop_worldline_event_id": envelope.get("crop_worldline_event_id"),
        "phenology_worldline_event_id": envelope.get(
            "phenology_worldline_event_id"
        ),
        "publication_receipt_ref": logical_receipt_ref,
        "publication_receipt_hash": receipt.get("receipt_hash"),
        "frontend_publication_ref": logical_publication_ref,
        "frontend_publication_hash": publication.get("publication_hash"),
        "surface_inventory_hash": publication.get("frontend_payload", {}).get("surface_inventory_hash"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic(_head_path(ns), head)
    return head


def publish_canonical_layer10_snapshot(
    *,
    namespace: PlotNamespace,
    geometry_hash: str,
    frontend_payload: Dict[str, Any],
    request_run_id: str,
) -> Dict[str, Any]:
    """Publish a validated terminal L10 result when no ASMAE head exists yet.

    A degraded provider-backed result is still a legitimate scientific
    publication.  Keeping it outside the canonical head made the browser wait
    forever even though L10 had completed successfully.  This bridge preserves
    the same immutable node/publication/receipt/head ordering used by ASMAE
    without falsely marking unavailable ASMAE evidence as completed.
    """
    ns = _coerce_namespace(namespace)
    payload = copy.deepcopy(frontend_payload)
    snapshot_id = str(payload.get("intelligence_snapshot_id") or "")
    if snapshot_id.startswith("ASMAE-SNAPSHOT-"):
        existing = load_latest_plot_snapshot(ns, geometry_hash or None)
        if existing and existing.get("snapshot_id") == snapshot_id:
            return {
                "snapshot_id": snapshot_id,
                "node_hash": existing.get("node_hash"),
                "frontend_publication_hash": existing.get("frontend_publication_hash"),
                "publication_receipt_hash": existing.get("publication_receipt_hash"),
                "surface_inventory_hash": existing.get("surface_inventory_hash"),
            }
        raise ValueError("ASMAE frontend payload has no matching canonical head")
    if not snapshot_id.startswith("L10-"):
        raise ValueError("terminal Layer 10 payload has no canonical snapshot identity")

    surfaces = payload.get("surfaces") or payload.get("surface_pack") or []
    if not isinstance(surfaces, list):
        raise ValueError("terminal Layer 10 surface inventory is invalid")
    inventory_hash = compute_surface_inventory_hash(surfaces)
    payload["surface_inventory_hash"] = inventory_hash
    scientific_identity = {
        "snapshot_id": snapshot_id,
        "plot_id": ns.plot_id,
        "publication_id": str(payload.get("publication_id") or ""),
        "publication_status": str(payload.get("publication_status") or ""),
        "surface_inventory_hash": inventory_hash,
        "surface_schema_version": str(payload.get("surface_schema_version") or ""),
        "render_authorization_version": str(payload.get("render_authorization_version") or ""),
        "resolved_crop_stage": str(payload.get("resolved_crop_stage") or "UNKNOWN"),
        "phenology_context": copy.deepcopy(payload.get("phenology_context") or {}),
        "source_policy": str(payload.get("source_policy") or "canonical"),
        "crop_posterior_lineage": (
            (payload.get("asmae_feature_pack") or {}).get("crop_posterior_lineage")
            if isinstance(payload.get("asmae_feature_pack"), dict)
            else None
        ),
        "crop_evidence_ledger_hash": (
            (payload.get("asmae_feature_pack") or {}).get(
                "crop_evidence_ledger_hash"
            )
            if isinstance(payload.get("asmae_feature_pack"), dict)
            else None
        ),
        "crop_influence_manifest_hash": (
            (payload.get("asmae_feature_pack") or {}).get(
                "crop_influence_manifest_hash"
            )
            if isinstance(payload.get("asmae_feature_pack"), dict)
            else None
        ),
    }
    scientific_identity["content_hash"] = hashlib.sha256(
        _json_bytes(scientific_identity)
    ).hexdigest()
    manifest_identity = {
        "namespace": {
            "tenant_id": ns.tenant_id,
            "farm_id": ns.farm_id,
            "plot_id": ns.plot_id,
        },
        "geometry_hash": str(geometry_hash or ""),
        "request_run_id": str(request_run_id),
        "scientific_content_hash": scientific_identity["content_hash"],
    }
    manifest_hash = hashlib.sha256(_json_bytes(manifest_identity)).hexdigest()
    return publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=str(geometry_hash or ""),
        snapshot_id=snapshot_id,
        asmae_result=scientific_identity,
        frontend_payload=payload,
        job_id=str(request_run_id),
        manifest_hash=manifest_hash,
        execution_identity={
            "worker_contract_version": "synchronous_layer10_terminal_publication_v1",
            "capability_contract_version": str(
                payload.get("render_authorization_version") or ""
            ),
        },
        snapshot_kind="layer10_terminal",
    )


def load_latest_plot_snapshot(
    namespace: Union[PlotNamespace, str],
    geometry_hash: Optional[str] = None,
    tenant_id: str = "",
    farm_id: str = "",
) -> Optional[Dict[str, Any]]:
    ns = _coerce_namespace(namespace, tenant_id=tenant_id, farm_id=farm_id)
    head = _read(_head_path(ns))
    if head.get("contract_version") != PLOT_SNAPSHOT_CONTRACT_VERSION:
        return None
    if geometry_hash and head.get("geometry_hash") != geometry_hash:
        return None

    snapshot_id = head.get("snapshot_id")
    if not snapshot_id:
        return None

    directory = _plot_dir(ns)
    node_path = directory / "nodes" / f"{snapshot_id}.json"
    if not node_path.exists():
        return None

    node = _read(node_path)
    if (
        node.get("contract_version") != PLOT_SNAPSHOT_CONTRACT_VERSION
        or node.get("plot_id") != ns.plot_id
        or node.get("tenant_id") != ns.tenant_id
        or node.get("farm_id") != ns.farm_id
        or node.get("snapshot_id") != snapshot_id
    ):
        return None

    try:
        recorded = datetime.fromisoformat(
            str(node.get("recorded_at", "")).replace("Z", "+00:00")
        )
        node["snapshot_age_seconds"] = max(
            0.0,
            (datetime.now(timezone.utc) - recorded.astimezone(timezone.utc)).total_seconds(),
        )
    except (ValueError, TypeError):
        node["snapshot_age_seconds"] = None

    safe_job_id = hashlib.sha256(str(head.get("publication_job_id", "")).encode("utf-8")).hexdigest()[:32]
    pub_path = directory / "publications" / f"{safe_job_id}.json"
    publication = _read(pub_path)

    receipt_path = directory / "receipts" / f"{safe_job_id}.json"
    receipt = _read(receipt_path)

    node["snapshot_ref"] = f"nodes/{snapshot_id}.json"
    node["publication_receipt_ref"] = head.get("publication_receipt_ref")
    node["publication_receipt_hash"] = head.get("publication_receipt_hash")
    node["publication_job_id"] = head.get("publication_job_id")
    node["frontend_publication_hash"] = head.get("frontend_publication_hash")
    node["surface_inventory_hash"] = head.get("surface_inventory_hash")

    publication_frontend = publication.get("frontend_payload") or {}
    payload_surfaces = publication_frontend.get("surfaces") or publication_frontend.get("surface_pack") or []

    # SHA-256 cryptographic recomputation validation
    hashable_node = {k: v for k, v in node.items() if not k.endswith("_ref") and k not in ("node_hash", "snapshot_age_seconds", "snapshot_ref", "publication_receipt_ref", "publication_receipt_hash", "publication_job_id", "frontend_publication_hash", "surface_inventory_hash", "validation")}
    computed_node_hash = hashlib.sha256(_json_bytes(hashable_node)).hexdigest()

    computed_pub_hash = None
    if publication:
        hashable_pub = {k: v for k, v in publication.items() if not k.endswith("_ref") and k != "publication_hash"}
        computed_pub_hash = hashlib.sha256(_json_bytes(hashable_pub)).hexdigest()

    computed_receipt_hash = None
    if receipt:
        hashable_receipt = {
            k: v for k, v in receipt.items()
            if not k.endswith("_ref") and k != "receipt_hash"
        }
        computed_receipt_hash = hashlib.sha256(_json_bytes(hashable_receipt)).hexdigest()

    try:
        computed_inv_hash = (
            compute_surface_inventory_hash(payload_surfaces)
            if isinstance(payload_surfaces, list)
            else None
        )
    except (TypeError, ValueError):
        # Immutable legacy/malformed publications remain readable for audit,
        # but can never validate as the canonical browser authority.
        computed_inv_hash = None

    derived_publication_status, contract_reason = classify_surface_publication(
        publication_frontend
    )
    declared_status_valid, _, declared_status_reason = (
        validate_declared_publication_status(publication_frontend)
    )
    published_schema_version = str(
        publication_frontend.get("surface_schema_version")
        or publication_frontend.get("schema_version")
        or publication_frontend.get("version")
        or (publication_frontend.get("provenance") or {}).get(
            "surface_schema_version"
        )
        or ""
    )

    validation_flags = {
        "nodeValid": bool(node.get("node_hash") and node.get("node_hash") == head.get("node_hash") and node.get("node_hash") == computed_node_hash),
        "publicationValid": bool(publication.get("publication_hash") and publication.get("publication_hash") == head.get("frontend_publication_hash") and publication.get("publication_hash") == computed_pub_hash),
        "receiptValid": bool(receipt.get("receipt_hash") and receipt.get("receipt_hash") == head.get("publication_receipt_hash") and receipt.get("receipt_hash") == computed_receipt_hash),
        "inventoryValid": bool(head.get("surface_inventory_hash") and computed_inv_hash and head.get("surface_inventory_hash") == computed_inv_hash),
        "bindingValid": bool(
            head.get("snapshot_id") == snapshot_id
            and head.get("plot_id") == ns.plot_id
            and head.get("tenant_id") == ns.tenant_id
            and head.get("farm_id") == ns.farm_id
            and publication.get("snapshot_id") == snapshot_id
            and publication.get("node_hash") == node.get("node_hash")
            and receipt.get("snapshot_id") == snapshot_id
            and receipt.get("node_hash") == node.get("node_hash")
            and receipt.get("frontend_publication_hash")
            == publication.get("publication_hash")
        ),
        "lineageValid": bool(
            node.get("snapshot_kind") != "asmae"
            or (
                node.get("crop_posterior_lineage")
                and node.get("crop_worldline_event_id")
                and node.get("phenology_worldline_event_id")
                and publication.get("crop_posterior_lineage")
                == node.get("crop_posterior_lineage")
                and publication.get("crop_worldline_event_id")
                == node.get("crop_worldline_event_id")
                and publication.get("phenology_worldline_event_id")
                == node.get("phenology_worldline_event_id")
                and receipt.get("crop_posterior_lineage")
                == node.get("crop_posterior_lineage")
                and receipt.get("crop_worldline_event_id")
                == node.get("crop_worldline_event_id")
                and receipt.get("phenology_worldline_event_id")
                == node.get("phenology_worldline_event_id")
            )
        ),
        # Integrity-valid does not mean scientifically current. These contract
        # flags are deliberately separate so callers can refresh a stale head
        # without misreporting it as cryptographic corruption.
        "schemaValid": published_schema_version == SURFACES_SCHEMA_VERSION,
        "contractValid": derived_publication_status in VALID_PUBLICATION_STATUSES,
        "publicationStatusValid": declared_status_valid,
    }
    node["validation"] = validation_flags
    node["contract_validation"] = {
        "current_surface_schema_version": SURFACES_SCHEMA_VERSION,
        "published_surface_schema_version": published_schema_version,
        "derived_publication_status": derived_publication_status,
        "contract_reason": contract_reason,
        "declared_status_reason": declared_status_reason,
    }
    node["refresh_required"] = bool(
        all(
            validation_flags[key]
            for key in (
                "nodeValid",
                "publicationValid",
                "receiptValid",
                "inventoryValid",
                "bindingValid",
                "lineageValid",
            )
        )
        and not all(
            validation_flags[key]
            for key in (
                "schemaValid",
                "contractValid",
                "publicationStatusValid",
            )
        )
    )
    # Return the job-bound frontend publication only after the immutable node
    # hash has been recomputed.  It is a separate hashed artifact, not a
    # mutation of the node.
    if publication_frontend:
        node["frontend_payload"] = publication_frontend

    return node


def load_plot_snapshot_by_id(
    snapshot_id: str,
    namespace: Optional[PlotNamespace] = None,
    tenant_id: str = "",
    farm_id: str = "",
    plot_id: str = "",
) -> Optional[Dict[str, Any]]:
    if not snapshot_id:
        return None

    if namespace is not None and namespace.is_valid():
        ns = namespace
    elif tenant_id and farm_id and plot_id:
        ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    else:
        return None

    node_path = _plot_dir(ns) / "nodes" / f"{snapshot_id}.json"
    if not node_path.exists():
        return None

    node = _read(node_path)
    if (
        node.get("snapshot_id") == snapshot_id
        and node.get("tenant_id") == ns.tenant_id
        and node.get("farm_id") == ns.farm_id
        and node.get("plot_id") == ns.plot_id
    ):
        return node

    return None
