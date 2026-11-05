"""B2B-08B: signed, tenant-owned Layer 0 packet assessment admission.

No caller may supply principal, tenant/farm authority, geometry epoch,
trusted verifier, physical-delivery authorization, or state-grant eligibility.
The HTTP body supplies only source claims to be independently checked by
v3 KMS and L3 delivery verifiers. FULL_CONTAINED is computed from trusted
plot geometry and an explicit packet bbox, never accepted as a body flag.

This is a scientific assessment endpoint, NOT a publisher, actuator or SIRE.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
import secrets
from typing import Any, Mapping

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from services.agribrain.app.plot_scope_context import (
    current_authenticated_plot_principal,
    require_b2b05_internal_request,
)
from services.agribrain.app.production_delivery_runtime import (
    _truth_flag,
    create_server_layer0_state_engine,
)
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer0.production_admission import (
    Layer0AdmissionRequiredError,
    load_server_issuer_verifier,
    live_revocation_required,
    require_trusted_verifier,
    signed_inputs_required,
    v3_kms_required,
)
from services.agribrain.layer0.spatial_tenant_contract import (
    ScopedPlotRequest,
    SpatialTenantDenied,
    authorize_plot_scope,
    verify_pixel_footprint,
)

router = APIRouter()
ENABLE_FLAG = "AKALORIS_LAYER0_ENABLE_SCOPED_PACKET_RUN"
_RUN_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{7,79}$")


class StrictModel(BaseModel):
    class Config:
        extra = "forbid"


class B2B08Packet(StrictModel):
    source: str
    obs_type: str
    timestamp: datetime
    bbox: tuple[float, float, float, float] | None = None
    data_status: str = "observed"
    payload: dict[str, Any] = Field(default_factory=dict)
    uncertainty_sigmas: dict[str, float] = Field(default_factory=dict)
    qa_score: float = 1.0
    reliability_weight: float = 1.0
    provenance_chain: list[str] = Field(default_factory=list)
    provenance_software_version: str = "akaloris-internal-packet-v1"
    native_evidence_id: str | None = None


class B2B08Assessment(StrictModel):
    assessment_id: str = Field(min_length=8, max_length=80)
    start_date: str
    end_date: str
    packets: list[B2B08Packet] = Field(default_factory=list, max_length=64)
    positive_receipts: dict[str, dict[str, Any]] = Field(default_factory=dict)


def signed_packet_run_enabled() -> bool:
    return _truth_flag(os.getenv(ENABLE_FLAG), ENABLE_FLAG)


def bootstrap_server_packet_runtime(app: Any, *, ownership_store: Any) -> None:
    """Called at lifespan startup. No HTTP-controlled initialization."""
    app.state.layer0_positive_admission_verifier = None
    app.state.layer0_packet_ownership_store = None
    if not signed_packet_run_enabled():
        return
    if not (
        signed_inputs_required()
        and v3_kms_required()
        and live_revocation_required()
        and _truth_flag(
            os.getenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE"),
            "AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE",
        )
    ):
        raise Layer0AdmissionRequiredError(
            "signed packet runtime requires trusted v3, live revocation and plot scope"
        )
    if ownership_store is None or not callable(
        getattr(ownership_store, "get_active_plot", None)
    ):
        raise Layer0AdmissionRequiredError(
            "signed packet runtime requires server plot ownership store"
        )
    verifier = load_server_issuer_verifier()
    require_trusted_verifier(verifier)
    # Do not leak a partially provisioned runtime if the issuer loader fails.
    app.state.layer0_positive_admission_verifier = verifier
    app.state.layer0_packet_ownership_store = ownership_store


def _parse_window(start: str, end: str) -> tuple[str, str]:
    try:
        a = datetime.strptime(start, "%Y-%m-%d").date()
        b = datetime.strptime(end, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("invalid_assessment_utc_window") from None
    n = (b - a).days
    if n < 0 or n > 30:
        raise ValueError("assessment_window_outside_31_day_limit")
    return a.isoformat(), b.isoformat()


def _new_packet(spec: B2B08Packet, scope: Any):
    """Derive scope and support from server-fetched geometry, not body flags."""
    from shapely.geometry import box, mapping
    from services.agribrain.layer0.observation_packet import (
        DataStatus, ObservationPacket, ObservationSource, ObservationType,
        Provenance, QAMetadata, UncertaintyModel,
    )

    if spec.timestamp.tzinfo is None or spec.timestamp.utcoffset() is None:
        raise ValueError("naive_packet_timestamp")
    if spec.timestamp.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError("future_packet_timestamp")
    if not isinstance(spec.payload, dict):
        raise ValueError("invalid_packet_payload")
    if any(k in spec.payload for k in (
        "eligible_for_state_grant", "source_qualified",
        "scientific_publication_authorized", "actuator_control_authorized",
        "physical_delivery_verified",
    )):
        raise ValueError("packet_claims_forbidden_authority")

    source = ObservationSource(spec.source)
    kind = ObservationType(spec.obs_type)
    is_event = source in (ObservationSource.USER_EVENT, ObservationSource.SENSOR_IOT) and (
        spec.payload.get("event_type") is not None
    )
    if is_event and (kind != ObservationType.VECTOR or
                     spec.payload.get("zone_id", "plot") != "plot"):
        raise ValueError("unsupported_event_zone_or_type")
    if not is_event and spec.bbox is None:
        raise ValueError("explicit_measurement_footprint_required")

    if spec.bbox is not None:
        raw_bbox = list(spec.bbox)
        if any(
            isinstance(n, bool) or not math.isfinite(n)
            for n in raw_bbox
        ):
            raise ValueError("nonfinite_packet_footprint")
        west, south, east, north = raw_bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("invalid_packet_footprint_bounds")
        footprint = mapping(box(*raw_bbox))
    else:
        # User events have no measured pixel support. This only binds their
        # plot scope; a real physical delivery still requires signed L3
        # evidence independent of the event or geometry claim.
        footprint = json.loads(scope.geometry_json)

    if (
        isinstance(spec.qa_score, bool) or
        not math.isfinite(spec.qa_score) or
        not 0 <= spec.qa_score <= 1 or
        isinstance(spec.reliability_weight, bool) or
        not math.isfinite(spec.reliability_weight) or
        not 0 <= spec.reliability_weight <= 1
    ):
        raise ValueError("invalid_packet_quality")
    if any(
        isinstance(v, bool) or not math.isfinite(v) or v <= 0
        for v in spec.uncertainty_sigmas.values()
    ):
        raise ValueError("invalid_packet_uncertainty")

    packet = ObservationPacket(
        source=source,
        obs_type=kind,
        timestamp=spec.timestamp.astimezone(timezone.utc),
        geometry_type="bbox" if spec.bbox else "polygon",
        bbox=spec.bbox,
        plot_id=scope.plot_id,
        crs="EPSG:4326",
        spatial_scope="plot",
        data_status=DataStatus.from_value(spec.data_status),
        payload=dict(spec.payload),
        qa=QAMetadata(scene_score=spec.qa_score),
        uncertainty=UncertaintyModel(sigmas=dict(spec.uncertainty_sigmas)),
        provenance=Provenance(
            processing_chain=list(spec.provenance_chain),
            software_version=spec.provenance_software_version,
            native_evidence_id=spec.native_evidence_id,
        ),
        reliability_weight=spec.reliability_weight,
    )
    support = verify_pixel_footprint(scope, footprint)
    packet.bind_spatial_context(scope, support)
    return packet


def _assert_farm_namespace(db: Any, plot_id: str, farm_id: str,
                           geometry_hash: str, geometry_version: int):
    try:
        query = {
            "_id": ObjectId(plot_id),
            "farmId": ObjectId(farm_id),
            "geometryHash": geometry_hash,
            "geometryVersion": geometry_version,
            "isActive": True,
            "isRevoked": False,
        }
        if db["Plot"].find_one(query, {"_id": 1}) is None:
            raise ValueError("farm plot membership changed")
    except Exception:
        raise Layer0AdmissionRequiredError(
            "trusted_plot_farm_namespace_denied"
        ) from None


def _run_assessment(
    app: Any, namespace: PlotNamespace, body: B2B08Assessment,
) -> dict[str, Any]:
    """Execute in threadpool with contextvars propagated from signed auth."""
    if not signed_packet_run_enabled():
        raise HTTPException(503, "signed_packet_runtime_disabled")
    store = getattr(app.state, "layer0_packet_ownership_store", None)
    verifier = getattr(app.state, "layer0_positive_admission_verifier", None)
    if store is None or verifier is None:
        raise HTTPException(503, "signed_packet_runtime_unavailable")
    require_trusted_verifier(verifier)
    from app.mongo_client import get_db
    db = get_db()
    if db is None:
        raise HTTPException(503, "state_journal_mongodb_unavailable")

    principal = current_authenticated_plot_principal()
    if namespace.tenant_id != principal.tenant_id:
        raise HTTPException(403, "authenticated_tenant_mismatch")
    record = store.get_active_plot(namespace.plot_id)
    if record is None:
        raise HTTPException(403, "trusted_plot_scope_denied")
    scope = authorize_plot_scope(
        principal,
        ScopedPlotRequest(
            principal.tenant_id, namespace.plot_id,
            record.geometry_hash, record.geometry_version,
        ),
        store.get_active_plot,
    )
    _assert_farm_namespace(
        db, namespace.plot_id, namespace.farm_id,
        scope.geometry_hash, scope.geometry_version,
    )

    if not _RUN_ID.fullmatch(body.assessment_id):
        raise HTTPException(422, "invalid_assessment_id")
    start_date, end_date = _parse_window(body.start_date, body.end_date)
    packets = [_new_packet(pkt, scope) for pkt in body.packets]
    for pkt in packets:
        day = pkt.timestamp.date().isoformat()
        if day < start_date or day > end_date:
            raise ValueError("packet_outside_assessment_window")

    # A missing positive grant cannot be promoted by packet body claims.
    # A complete signed L3 delivery is independently verified by B2B-07.
    digest = hashlib.sha256(
        json.dumps(
            {"tenant": scope.tenant_id, "plot": scope.plot_id,
             "epoch": scope.geometry_version, "hash": scope.geometry_hash,
             "assessment_id": body.assessment_id},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    claim = secrets.token_hex(16)
    journal = db["Layer0ScientificAssessment"]
    journal.create_index(
        [("tenant_id", 1), ("plot_id", 1),
         ("geometry_version", 1), ("status", 1)]
    )
    try:
        journal.insert_one({
            "_id": digest,
            "tenant_id": scope.tenant_id,
            "plot_id": scope.plot_id,
            "geometry_hash": scope.geometry_hash,
            "geometry_version": scope.geometry_version,
            "assessment_id": body.assessment_id,
            "claim_nonce": claim,
            "status": "STAGED",
            "started_at": datetime.now(timezone.utc),
            "scientific_publication_authorized": False,
            "actuator_control_authorized": False,
        })
    except DuplicateKeyError:
        # A prior staged/committed run might already have applied signed
        # irrigation. Never re-run it automatically after an uncertain exit.
        raise HTTPException(409, "assessment_claim_already_exists") from None

    engine = create_server_layer0_state_engine(
        app, plot_ownership_store=store,
        principal_provider=current_authenticated_plot_principal,
        positive_admission_verifier=verifier,
    )
    try:
        pkg = engine.run_from_packets(
            plot_id=scope.plot_id,
            packets=packets,
            start_date=start_date,
            end_date=end_date,
            geometry_hash=scope.geometry_hash,
            geometry_version=scope.geometry_version,
            tenant_id=scope.tenant_id,
            scope_hash=scope.scope_hash,
            positive_admission_receipts=body.positive_receipts,
        )
        # A concurrent geometry CAS or owner revocation blocks publication of
        # a new scientific result, even if a consumed physical receipt has
        # already been durably journaled for manual recovery.
        verified = authorize_plot_scope(
            current_authenticated_plot_principal(),
            ScopedPlotRequest(
                scope.tenant_id, scope.plot_id,
                scope.geometry_hash, scope.geometry_version,
            ),
            store.get_active_plot,
        )
        if verified != scope:
            raise Layer0AdmissionRequiredError(
                "assessment_scope_changed_before_durable_summary"
            )
        _assert_farm_namespace(
            db, namespace.plot_id, namespace.farm_id,
            scope.geometry_hash, scope.geometry_version,
        )
        if pkg.scientific_publication_authorized or pkg.actuator_control_authorized:
            raise Layer0AdmissionRequiredError("scientific_state_authority_violation")
        if not isinstance(pkg.input_hash, str) or not pkg.input_hash:
            raise Layer0AdmissionRequiredError("signed_input_manifest_absent")
        # B2B-08B: reconcile only server-generated scientific L3
        # provenance against the actual committed state/receipt journals.
        from services.agribrain.app.scientific_commit_lineage import (
            attest_delivery_commit_lineage,
        )
        delivery_links = attest_delivery_commit_lineage(
            db,
            tenant_id=scope.tenant_id,
            plot_id=scope.plot_id,
            geometry_hash=scope.geometry_hash,
            geometry_version=scope.geometry_version,
            provenance_log=pkg.provenance.get("provenance_log"),
        )
        summary = {
            "assessment_id": body.assessment_id,
            "state_run_id": pkg.run_id,
            "input_hash": pkg.input_hash,
            "output_hash": pkg.output_hash,
            "signed_input_count": pkg.health_report.get("signed_state_input_count", 0),
            "excluded_by_status": pkg.health_report.get("state_packets_excluded_by_status", {}),
            "state_uncertainty": pkg.state_uncertainty,
            "q_temporal_contract": "declared_unforced_or_temporal_rate_process_q",
            "source_manifest": pkg.provenance.get("positive_state_input_manifest"),
            "verified_delivery_commits": delivery_links,
            "verified_delivery_receipt_count": sum(
                len(link["receipt_ids"]) for link in delivery_links
            ),
            "scientific_publication_authorized": False,
            "actuator_control_authorized": False,
        }
        result = journal.update_one(
            {"_id": digest, "claim_nonce": claim, "status": "STAGED"},
            {"$set": {
                "status": "COMMITTED", "committed_at": datetime.now(timezone.utc),
                "result": summary,
            }},
        )
        if result.matched_count != 1:
            raise Layer0AdmissionRequiredError("assessment_journal_commit_unconfirmed")
        return {
            "assessment_id": body.assessment_id,
            "state_run_id": pkg.run_id,
            "input_hash": pkg.input_hash,
            "output_hash": pkg.output_hash,
            "signed_input_count": summary["signed_input_count"],
            "verified_delivery_receipt_count": summary["verified_delivery_receipt_count"],
            "scientific_publication_authorized": False,
            "actuator_control_authorized": False,
        }
    except Exception:
        # A partial L3 commitment may exist. Keep STAGED claim and rely on
        # the B2B-07 committed state journal for explicit recovery; deleting
        # the claim here could permit duplicate physical consumption.
        raise


@router.post("/v2/b2b08/plots/{plot_id}/state/assess")
async def assess_signed_plot_state(
    plot_id: str,
    body: B2B08Assessment,
    request: Request,
    namespace: PlotNamespace = Depends(require_b2b05_internal_request),
):
    """Internal-service only; never exposes server trust-root configuration."""
    if namespace.plot_id != plot_id:
        raise HTTPException(403, "plot_namespace_mismatch")
    # The authenticated dependency yields a request-local principal, never
    # an untrusted header-only identity or local development fallback.
    try:
        current_authenticated_plot_principal()
    except SpatialTenantDenied:
        raise HTTPException(401, "signed_plot_principal_required") from None
    try:
        return await run_in_threadpool(_run_assessment, request.app, namespace, body)
    except HTTPException:
        raise
    except (Layer0AdmissionRequiredError, SpatialTenantDenied):
        raise HTTPException(403, "signed_scoped_assessment_denied") from None
    except (ValueError, TypeError):
        raise HTTPException(422, "invalid_signed_assessment_input") from None
    except Exception:
        raise HTTPException(503, "signed_assessment_runtime_unavailable") from None
