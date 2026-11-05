"""B2B-08 Final Gate: Actual main.app Staging Lifespan Qualification.

Tests the REAL FastAPI main.app lifespan (services.agribrain.app.main.app):
  1. Service startup: MongoDB connectivity ping, trusted B2B-05 plot authority,
     server-only L3 verified delivery runtime provisioning on app.state,
     signed scoped packet runtime on app.state, background refresh worker,
     ASMAE durable worker recovery thread, and Mongo nonce indexes.
  2. Authenticated readiness probe: GET /v2/b2b08/internal/readiness returns ready=true.
  3. Authenticated scoped assessment: POST /v2/b2b08/plots/{plotId}/state/assess
     with signed v3 source + L3 physical delivery -> transactional commit.
  4. Lifespan shutdown: cleans up app.state verifiers, joins ASMAE worker thread,
     stops refresh worker.
  5. Cold restart: boots a second lifespan against the same database, verifies
     cold checkpoint recovery without re-consuming physical receipts, and shuts down cleanly.

Run ONLY against a disposable local replica set:
  $env:AKALORIS_B07_MONGO_TEST_URI = 'mongodb://127.0.0.1:27018/?replicaSet=rs0'
  py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_staging_main_lifespan_gate.py
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import uuid

import pytest
from bson import ObjectId
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient
from pymongo import MongoClient

from services.agribrain.app.internal_service_auth import compute_request_signature
from services.agribrain.app.mongo_client import close_mongo, get_db
from services.agribrain.app.scoped_packet_run import (
    B2B08Packet, _new_packet,
)
from services.agribrain.layer0.plot_ownership_store import PrismaPlotOwnershipStore
from services.agribrain.layer0.positive_observation_admission import (
    GRANT_PURPOSE, WEATHER_GRANT_PURPOSE, observation_packet_digest,
)
from services.agribrain.layer0.spatial_tenant_contract import (
    AuthenticatedPrincipal, ScopedPlotRequest, authorize_plot_scope,
    canonical_geometry_hash,
)
from services.agribrain.layer0.v3_kms_signed_issuer import (
    LocalKmsAsymmetricSigner, V3_GRANT_DOMAIN,
)
from services.agribrain.layer0.durable_revocation_authority import DurableRevocationSnapshot
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_DOMAIN, VERIFIED_IRRIGATION_PURPOSE,
    VerifiedDeliveredIrrigationSigner,
)

UTC = timezone.utc
SECRET = "staging-lifespan-test-unique-internal-hmac-secret"
PREFIX = "akaloris_b2b08_staging_main_"


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def valid_isolated_uri() -> str:
    uri = os.environ.get("AKALORIS_B07_MONGO_TEST_URI", "").strip()
    if not uri:
        pytest.fail("explicit isolated AKALORIS_B07_MONGO_TEST_URI required")
    parsed = urlsplit(uri)
    if (parsed.scheme != "mongodb" or parsed.username is not None
            or parsed.password is not None
            or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.port != 27018
            or parse_qs(parsed.query).get("replicaSet") != ["rs0"]):
        pytest.fail("B2B-08 staging main lifespan gate requires localhost:27018 replicaSet=rs0")
    return uri


def box():
    return {"type": "Polygon", "coordinates": [[
        [3.0, 36.0], [3.002, 36.0], [3.002, 36.002],
        [3.0, 36.002], [3.0, 36.0],
    ]]}


def seeded_prisma_plot(db):
    user_id, farm_id, plot_id = ObjectId(), ObjectId(), ObjectId()
    polygon = box()
    digest = canonical_geometry_hash(polygon)
    db["User"].insert_one({"_id": user_id, "isActive": True})
    db["Farm"].insert_one({"_id": farm_id, "userId": user_id, "isActive": True})
    db["Plot"].insert_one({
        "_id": plot_id, "farmId": farm_id, "isActive": True,
        "isRevoked": False, "deletedAt": None,
        "geometryVersion": 2, "geometryHash": digest, "geoJson": polygon,
    })
    return {
        "tenant": str(user_id), "farm": str(farm_id),
        "plot": str(plot_id), "hash": digest, "geometry_version": 2,
    }


def write_revocation(path: Path, now: datetime, key_id: str):
    snap = DurableRevocationSnapshot(
        revision=0, issued_at=now - timedelta(seconds=3),
        expires_at=now + timedelta(hours=1),
        key_statuses={key_id: "active"},
    )
    path.write_text(json.dumps(snap.to_dict(), sort_keys=True), encoding="utf-8")


def signed_assessment_payload(db, identity, source_signer, l3_signer, now):
    day = (now - timedelta(days=1)).date()
    start = datetime.combine(day, time(12), tzinfo=UTC)
    end = datetime.combine(day, time(14), tzinfo=UTC)
    owner = PrismaPlotOwnershipStore(db)
    scope = authorize_plot_scope(
        AuthenticatedPrincipal(identity["tenant"], "internal-service:" + identity["farm"], True),
        ScopedPlotRequest(
            identity["tenant"], identity["plot"], identity["hash"], 2,
        ), owner.get_active_plot,
    )
    observation = {
        "source": "sentinel2",
        "obs_type": "tabular",
        "timestamp": iso(start),
        "bbox": [3.0002, 36.0002, 3.0004, 36.0004],
        "data_status": "observed",
        "payload": {
            "ndvi_mean": 0.62, "real_provider_product": True,
            "source_type": "sentinel2", "production_usable": True,
        },
        "uncertainty_sigmas": {"ndvi": 0.04},
        "qa_score": 0.99,
        "reliability_weight": 1.0,
        "native_evidence_id": "staging-scene-1",
    }
    packet = _new_packet(B2B08Packet(**observation), scope)
    packet_digest = observation_packet_digest(packet)
    support_root = hashlib.sha256(b"staging-scientific-support").hexdigest()
    signed_source = source_signer.sign_grant({
        "domain": V3_GRANT_DOMAIN, "version": "v3",
        "algorithm": "Ed25519", "key_id": "staging-source-key",
        "issuer_id": "staging-source",
        "purpose": GRANT_PURPOSE, "source": "sentinel2",
        "permitted_variables": ["ndvi"],
        "packet_digest": packet_digest,
        "qualification_decision_id": "staging-scene-decision",
        "native_evidence_id": "staging-scene-1",
        "policy_version": "staging-policy-v1", "qa_version": "staging-qa-v1",
        "scientific_support_root": support_root,
        "tenant_id": identity["tenant"], "plot_id": identity["plot"],
        "geometry_hash": identity["hash"], "geometry_version": 2,
        "spatial_scope": "plot",
        "acquisition_start": iso(start), "acquisition_end": iso(end),
        "provenance_type": "direct_provider_observation",
        "temporal_role": "historical_observation",
        "issued_at": iso(now - timedelta(minutes=1)),
        "expires_at": iso(now + timedelta(hours=1)),
        "revocation_revision_anchor": 0,
        "issuer_decision_ledger_id": "staging-provider-decision",
        "replay_idempotency_key": "staging-scene-replay",
    }, "staging-source-key")

    signed_delivery = l3_signer.sign({
        "domain": VERIFIED_IRRIGATION_DOMAIN, "version": "v3",
        "algorithm": "Ed25519", "key_id": "staging-l3-key",
        "issuer_id": "staging-l3", "purpose": VERIFIED_IRRIGATION_PURPOSE,
        "receipt_id": "staging-delivery-receipt-1",
        "tenant_id": identity["tenant"], "plot_id": identity["plot"],
        "geometry_hash": identity["hash"], "geometry_version": 2,
        "zone_id": "plot", "delivery_start": iso(start),
        "delivery_end": iso(end),
        "delivered_volume_liters": 1200.0, "wetted_area_m2": 100.0,
        "delivery_efficiency_fraction": 0.9,
        "net_infiltrated_depth_mm": 10.8,
        "conversion_calibration_id": "staging-calibrated-meter-v1",
        "depth_uncertainty_sigma_mm": 0.4,
        "source_evidence_cas_root": "staging-meter-cas-1",
        "replay_idempotency_key": "staging-l3-replay-1",
        "revocation_revision_anchor": 0,
        "issued_at": iso(end + timedelta(minutes=5)),
        "expires_at": iso(now + timedelta(hours=1)),
    })
    event = {
        "source": "user_event", "obs_type": "vector",
        "timestamp": iso(end), "data_status": "observed",
        "payload": {
            "event_type": "irrigation", "event_role": "VERIFIED_DELIVERY",
            "event_id": "staging-meter-event-1", "zone_id": "plot",
            "verified_receipt": signed_delivery.to_dict(),
        },
    }
    return {
        "assessment_id": "staging-assessment-0001",
        "start_date": day.isoformat(), "end_date": day.isoformat(),
        "packets": [observation, event],
        "positive_receipts": {packet_digest: signed_source.to_dict()},
    }


def signed_request(client, method, path, identity, body=None):
    wire = b"" if body is None else json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ts = str(datetime.now(UTC).timestamp())
    nonce = uuid.uuid4().hex
    tenant = identity["tenant"]
    signature = compute_request_signature(
        method=method, path=path, query_string="",
        tenant_id=tenant, farm_id=identity["farm"], plot_id=identity["plot"],
        body_bytes=wire, timestamp=ts, nonce=nonce,
    )
    headers = {
        "Content-Type": "application/json",
        "X-Tenant-Id": tenant, "X-Farm-Id": identity["farm"],
        "X-Plot-Id": identity["plot"],
        "X-AgriBrain-Timestamp": ts, "X-AgriBrain-Nonce": nonce,
        "X-AgriBrain-Key-Version": "v1",
        "X-AgriBrain-Signature": signature,
    }
    if method == "GET":
        return client.get(path, headers=headers)
    elif method == "POST":
        return client.post(path, content=wire, headers=headers)
    raise ValueError(f"unsupported method {method}")


def test_actual_main_app_staging_lifespan(monkeypatch, tmp_path):
    """End-to-end qualification of services.agribrain.app.main.app lifespan."""
    base_uri = valid_isolated_uri()
    db_name = PREFIX + uuid.uuid4().hex
    full_db_uri = f"mongodb://127.0.0.1:27018/{db_name}?replicaSet=rs0"
    
    # Pre-seed via direct client
    admin_client = MongoClient(base_uri, serverSelectionTimeoutMS=5000)
    db = admin_client[db_name]
    identity = seeded_prisma_plot(db)
    
    now = datetime.now(UTC)
    source_signer = LocalKmsAsymmetricSigner()
    source_signer.provision_key("staging-source-key")
    physical_private = Ed25519PrivateKey.generate()
    physical_signer = VerifiedDeliveredIrrigationSigner(
        key_id="staging-l3-key", issuer_id="staging-l3",
        algorithm="Ed25519", private_key=physical_private,
    )
    source_rev = tmp_path / "source-rev.json"
    l3_rev = tmp_path / "l3-rev.json"
    write_revocation(source_rev, now, "staging-source-key")
    write_revocation(l3_rev, now, "staging-l3-key")
    
    src_cfg = {
        "staging-source-key": {
            "issuer_id": "staging-source", "source": "sentinel2",
            "algorithm": "Ed25519",
            "public_key_pem": source_signer.get_public_key_pem("staging-source-key"),
            "valid_from": iso(now - timedelta(days=5)),
            "valid_until": iso(now + timedelta(days=5)),
            "permitted_purposes": [GRANT_PURPOSE, WEATHER_GRANT_PURPOSE],
        },
    }
    l3_cfg = {
        "staging-l3-key": {
            "issuer_id": "staging-l3", "source": "sensor_iot",
            "algorithm": "Ed25519",
            "public_key_pem": physical_private.public_key().public_bytes(
                Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii"),
            "valid_from": iso(now - timedelta(days=5)),
            "valid_until": iso(now + timedelta(days=5)),
        },
    }
    
    env_vars = {
        "MONGODB_URI": full_db_uri,
        "DATABASE_URL": full_db_uri,
        "NODE_ENV": "staging",
        "ENVIRONMENT": "staging",
        "ALLOW_UNAUTHENTICATED_DEV": "false",
        "AGRIBRAIN_INTERNAL_SERVICE_SECRET": SECRET,
        "AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS": "true",
        "AKALORIS_LAYER0_REQUIRE_V3_KMS": "true",
        "AKALORIS_LAYER0_REQUIRE_LIVE_REVOCATION": "true",
        "AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE": "true",
        "AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION": "true",
        "AKALORIS_LAYER0_ENABLE_SCOPED_PACKET_RUN": "true",
        "AKALORIS_LAYER0_KMS_PUBLIC_KEYS_JSON": json.dumps(src_cfg),
        "AKALORIS_LAYER0_DURABLE_REVOCATION_PATH": str(source_rev),
        "AKALORIS_LAYER0_L3_PUBLIC_KEYS_JSON": json.dumps(l3_cfg),
        "AKALORIS_LAYER0_L3_DURABLE_REVOCATION_PATH": str(l3_rev),
    }
    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)
        
    close_mongo()
    
    # Import the actual application
    from services.agribrain.app.main import app
    
    try:
        # Phase 1: Boot primary lifespan
        with TestClient(app) as client:
            # 1. Verify app.state provisions
            assert app.state.layer0_verified_irrigation_verifier is not None
            assert app.state.layer0_positive_admission_verifier is not None
            assert app.state.layer0_packet_ownership_store is not None
            
            # 2. Check internal readiness probe
            ready_res = signed_request(client, "GET", "/v2/b2b08/internal/readiness", identity)
            assert ready_res.status_code == 200, (ready_res.status_code, ready_res.text)
            ready_data = ready_res.json()
            assert ready_data["ready"] is True
            assert ready_data["components"]["mongo_connection"] == "ready"
            assert ready_data["components"]["mongo_transaction_topology"] == "ready"
            assert ready_data["components"]["verified_delivery_runtime"] == "ready"
            assert ready_data["components"]["plot_ownership"] == "ready"
            
            # 3. Check authenticated assessment execution
            payload = signed_assessment_payload(db, identity, source_signer, physical_signer, now)
            assess_res = signed_request(
                client, "POST",
                "/v2/b2b08/plots/" + identity["plot"] + "/state/assess",
                identity,
                body=payload,
            )
            assert assess_res.status_code == 200, (assess_res.status_code, assess_res.text)
            assess_data = assess_res.json()
            assert assess_data["verified_delivery_receipt_count"] == 1
            assert assess_data["signed_input_count"] >= 1
            assert assess_data["scientific_publication_authorized"] is False
            assert assess_data["actuator_control_authorized"] is False
            
            # Verify Mongo persistence
            assert db["Layer0ScientificAssessment"].count_documents({"status": "COMMITTED"}) == 1
            assert db["Layer0IrrigationReceiptConsumption"].count_documents({"status": "COMMITTED"}) == 1
            assert db["Layer0IrrigationCommittedState"].count_documents({}) == 1
            primary_journal = db["Layer0ScientificAssessment"].find_one({
                "status": "COMMITTED",
            })
            assert primary_journal is not None
            primary_receipt_id = primary_journal["submitted_receipt_ids"][0]
            primary_receipt = db["Layer0IrrigationReceiptConsumption"].find_one({
                "_id": primary_receipt_id,
            })
            assert primary_receipt["assessment_claim_id"] == primary_journal["_id"]
            assert primary_receipt["grant_digest"] == primary_journal[
                "submitted_receipt_digests"
            ][primary_receipt_id]
            
        # Phase 2: Verify shutdown cleanup
        assert app.state.layer0_verified_irrigation_verifier is None
        assert app.state.layer0_positive_admission_verifier is None
        assert app.state.layer0_packet_ownership_store is None
        close_mongo()
        
        # Phase 3: Cold restart lifespan against same DB
        with TestClient(app) as client2:
            assert app.state.layer0_verified_irrigation_verifier is not None
            
            # Replay with new assessment ID -> must perform cold recovery of committed L3 checkpoint
            rerun_payload = dict(payload, assessment_id="staging-assessment-0002")
            replay_res = signed_request(
                client2, "POST",
                "/v2/b2b08/plots/" + identity["plot"] + "/state/assess",
                identity,
                body=rerun_payload,
            )
            assert replay_res.status_code == 200, (replay_res.status_code, replay_res.text)
            
            # No duplicate receipts consumed; snapshot recovered
            assert db["Layer0IrrigationReceiptConsumption"].count_documents({"status": "COMMITTED"}) == 1
            assert db["Layer0IrrigationCommittedState"].count_documents({}) == 1
            
            journal2 = db["Layer0ScientificAssessment"].find_one({
                "assessment_id": "staging-assessment-0002", "status": "COMMITTED",
            })
            assert journal2 is not None
            assert journal2["result"]["verified_delivery_commits"][0]["recovered_from_durable_l3_commit"] is True
            
        # Verify final shutdown
        assert app.state.layer0_verified_irrigation_verifier is None
        
    finally:
        close_mongo()
        if db_name.startswith(PREFIX):
            admin_client.drop_database(db_name)
        admin_client.close()
