"""B2B-08C-II opt-in signed HTTP -> scientific L3 -> Mongo -> cold restart.

This uses a REAL TestClient HTTP route, the REAL B2B-08 server verifier
bootstraps, REAL Prisma Plot/Farm/User ownership and Mongo transactions.
Only the ASGI application's outer lifespan is isolated to avoid starting
unrelated production refresh workers. This does NOT test the entire main.py
lifespan; that remains a separate staging deployment acceptance gate.

Run ONLY against a disposable local replica set:
  $env:AKALORIS_B07_MONGO_TEST_URI = 'mongodb://127.0.0.1:27018/?replicaSet=rs0'
  py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_signed_http_connected_gate.py
"""
from __future__ import annotations

from contextlib import asynccontextmanager
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
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo import MongoClient

from services.agribrain.app.internal_service_auth import (
    compute_request_signature, init_mongo_nonce_indexes,
)
from services.agribrain.app.production_delivery_runtime import (
    bootstrap_server_verified_irrigation,
)
from services.agribrain.app.scoped_packet_run import (
    B2B08Packet, _new_packet, bootstrap_server_packet_runtime,
    router as assessment_router,
)
from services.agribrain.layer0.plot_ownership_store import PrismaPlotOwnershipStore
from services.agribrain.layer0.positive_observation_admission import observation_packet_digest
from services.agribrain.layer0.spatial_tenant_contract import (
    AuthenticatedPrincipal, ScopedPlotRequest, authorize_plot_scope,
    canonical_geometry_hash,
)
from services.agribrain.layer0.v3_kms_signed_issuer import (
    LocalKmsAsymmetricSigner, V3_GRANT_DOMAIN, GRANT_PURPOSE,
)
from services.agribrain.layer0.durable_revocation_authority import DurableRevocationSnapshot
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_DOMAIN, VERIFIED_IRRIGATION_PURPOSE,
    VerifiedDeliveredIrrigationSigner,
)

UTC = timezone.utc
SECRET = "isolated-b2b08-http-test-unique-internal-hmac-secret"
PREFIX = "akaloris_b2b08_http_"


def iso(dt):
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def valid_isolated_uri():
    uri = os.environ.get("AKALORIS_B07_MONGO_TEST_URI", "").strip()
    if not uri:
        pytest.fail("explicit isolated AKALORIS_B07_MONGO_TEST_URI required")
    parsed = urlsplit(uri)
    if (parsed.scheme != "mongodb" or parsed.username is not None
            or parsed.password is not None
            or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.port != 27018
            or parse_qs(parsed.query).get("replicaSet") != ["rs0"]):
        pytest.fail("B2B-08 signed HTTP gate requires localhost:27018 replicaSet=rs0")
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
    # Simulated completed authoritative geometry edit: current v2/geometry.
    db["Plot"].insert_one({
        "_id": plot_id, "farmId": farm_id, "isActive": True,
        "isRevoked": False, "deletedAt": None,
        "geometryVersion": 2, "geometryHash": digest, "geoJson": polygon,
    })
    return {
        "tenant": str(user_id), "farm": str(farm_id),
        "plot": str(plot_id), "hash": digest, "geometry_version": 2,
    }


def write_revocation(path, now, key_id):
    snap = DurableRevocationSnapshot(
        revision=0, issued_at=now - timedelta(seconds=3),
        expires_at=now + timedelta(hours=1),
        key_statuses={key_id: "active"},
    )
    path.write_text(json.dumps(snap.to_dict(), sort_keys=True), encoding="utf-8")


def environment(monkeypatch, now, tmp_path):
    source = LocalKmsAsymmetricSigner()
    source.provision_key("isolated-http-source-key")
    physical_private = Ed25519PrivateKey.generate()
    physical = VerifiedDeliveredIrrigationSigner(
        key_id="isolated-http-l3-key", issuer_id="isolated-http-l3",
        algorithm="Ed25519", private_key=physical_private,
    )
    source_rev = tmp_path / "source-revocation.json"
    physical_rev = tmp_path / "l3-revocation.json"
    write_revocation(source_rev, now, "isolated-http-source-key")
    write_revocation(physical_rev, now, "isolated-http-l3-key")
    src_cfg = {
        "isolated-http-source-key": {
            "issuer_id": "isolated-http-source", "source": "sentinel2",
            "algorithm": "Ed25519",
            "public_key_pem": source.get_public_key_pem("isolated-http-source-key"),
            "valid_from": iso(now - timedelta(days=5)),
            "valid_until": iso(now + timedelta(days=5)),
            "permitted_purposes": [GRANT_PURPOSE],
        },
    }
    l3_cfg = {
        "isolated-http-l3-key": {
            "issuer_id": "isolated-http-l3", "source": "sensor_iot",
            "algorithm": "Ed25519",
            "public_key_pem": physical_private.public_key().public_bytes(
                Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii"),
            "valid_from": iso(now - timedelta(days=5)),
            "valid_until": iso(now + timedelta(days=5)),
        },
    }
    flags = {
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
        "AKALORIS_LAYER0_L3_DURABLE_REVOCATION_PATH": str(physical_rev),
    }
    for k, v in flags.items():
        monkeypatch.setenv(k, v)
    return source, physical, source_rev, physical_rev


def signed_assessment_payload(db, identity, source_signer, l3_signer, now):
    from services.agribrain.app.scoped_packet_run import _new_packet
    day = (now - timedelta(days=1)).date()
    start = datetime.combine(day, time(12), tzinfo=UTC)
    end = datetime.combine(day, time(14), tzinfo=UTC)
    owner = PrismaPlotOwnershipStore(db)
    scope = authorize_plot_scope(
        AuthenticatedPrincipal(identity["tenant"], "internal-service:"+identity["farm"], True),
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
            "ndvi_mean": 0.61, "real_provider_product": True,
            "source_type": "sentinel2", "production_usable": True,
        },
        "uncertainty_sigmas": {"ndvi": 0.04},
        "qa_score": 0.99,
        "reliability_weight": 1.0,
        "native_evidence_id": "isolated-scene-1",
    }
    packet = _new_packet(B2B08Packet(**observation), scope)
    packet_digest = observation_packet_digest(packet)
    support_root = hashlib.sha256(b"isolated-scientific-support").hexdigest()
    signed_source = source_signer.sign_grant({
        "domain": V3_GRANT_DOMAIN, "version": "v3",
        "algorithm": "Ed25519", "key_id": "isolated-http-source-key",
        "issuer_id": "isolated-http-source",
        "purpose": GRANT_PURPOSE, "source": "sentinel2",
        "permitted_variables": ["ndvi"],
        "packet_digest": packet_digest,
        "qualification_decision_id": "isolated-scene-decision",
        "native_evidence_id": "isolated-scene-1",
        "policy_version": "isolated-policy-v1", "qa_version": "isolated-qa-v1",
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
        "issuer_decision_ledger_id": "isolated-provider-decision",
        "replay_idempotency_key": "isolated-scene-replay",
    }, "isolated-http-source-key")

    signed_delivery = l3_signer.sign({
        "domain": VERIFIED_IRRIGATION_DOMAIN, "version": "v3",
        "algorithm": "Ed25519", "key_id": "isolated-http-l3-key",
        "issuer_id": "isolated-http-l3", "purpose": VERIFIED_IRRIGATION_PURPOSE,
        "receipt_id": "isolated-http-delivery-1",
        "tenant_id": identity["tenant"], "plot_id": identity["plot"],
        "geometry_hash": identity["hash"], "geometry_version": 2,
        "zone_id": "plot", "delivery_start": iso(start),
        "delivery_end": iso(end),
        "delivered_volume_liters": 1000.0, "wetted_area_m2": 100.0,
        "delivery_efficiency_fraction": 0.9,
        "net_infiltrated_depth_mm": 9.0,
        "conversion_calibration_id": "isolated-measured-meter-v1",
        "depth_uncertainty_sigma_mm": 0.5,
        "source_evidence_cas_root": "isolated-meter-record-1",
        "replay_idempotency_key": "isolated-l3-replay-1",
        "revocation_revision_anchor": 0,
        "issued_at": iso(end + timedelta(minutes=5)),
        "expires_at": iso(now + timedelta(hours=1)),
    })
    event = {
        "source": "user_event", "obs_type": "vector",
        "timestamp": iso(end), "data_status": "observed",
        "payload": {
            "event_type": "irrigation", "event_role": "VERIFIED_DELIVERY",
            "event_id": "isolated-meter-event-1", "zone_id": "plot",
            "verified_receipt": signed_delivery.to_dict(),
        },
    }
    return {
        "assessment_id": "isolated-assessment-0001",
        "start_date": day.isoformat(), "end_date": day.isoformat(),
        "packets": [observation, event],
        "positive_receipts": {packet_digest: signed_source.to_dict()},
    }


def signed_post(client, identity, body, *, nonce=None, tenant=None):
    path = "/v2/b2b08/plots/" + identity["plot"] + "/state/assess"
    wire = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ts = str(datetime.now(UTC).timestamp())
    nonce = nonce or uuid.uuid4().hex
    tenant = tenant or identity["tenant"]
    signature = compute_request_signature(
        method="POST", path=path, query_string="",
        tenant_id=tenant, farm_id=identity["farm"], plot_id=identity["plot"],
        body_bytes=wire, timestamp=ts, nonce=nonce,
    )
    return client.post(path, content=wire, headers={
        "Content-Type": "application/json",
        "X-Tenant-Id": tenant, "X-Farm-Id": identity["farm"],
        "X-Plot-Id": identity["plot"],
        "X-AgriBrain-Timestamp": ts, "X-AgriBrain-Nonce": nonce,
        "X-AgriBrain-Key-Version": "v1",
        "X-AgriBrain-Signature": signature,
    })


def application(db):
    # Bind the production route to an isolated ASGI lifespan. This invokes
    # exactly the real bootstrap functions used in main.py, while avoiding
    # unrelated background services on a disposable test database.
    @asynccontextmanager
    async def lifespan(app):
        from services.agribrain.app import internal_service_auth as auth
        init_mongo_nonce_indexes(db)
        app.state.layer0_verified_irrigation_verifier = (
            bootstrap_server_verified_irrigation(db)
        )
        bootstrap_server_packet_runtime(
            app, ownership_store=PrismaPlotOwnershipStore(db)
        )
        try:
            yield
        finally:
            app.state.layer0_verified_irrigation_verifier = None
            app.state.layer0_positive_admission_verifier = None
            app.state.layer0_packet_ownership_store = None
            auth._mongo_nonces_collection = None
            auth._in_memory_nonces.clear()

    app = FastAPI(lifespan=lifespan)
    app.include_router(assessment_router)
    return app


def test_authenticated_http_delivery_mongo_and_cold_restart(monkeypatch, tmp_path):
    uri = valid_isolated_uri()
    database_name = PREFIX + uuid.uuid4().hex
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    assert database_name.startswith(PREFIX)
    try:
        db = client[database_name]
        topology = db.command("hello")
        assert topology.get("setName") == "rs0"
        assert callable(getattr(client, "start_session", None))
        identity = seeded_prisma_plot(db)
        now = datetime.now(UTC)
        signer, l3, _, _ = environment(monkeypatch, now, tmp_path)
        from app import mongo_client as mongo_module
        monkeypatch.setattr(mongo_module, "get_db", lambda: db)
        body = signed_assessment_payload(db, identity, signer, l3, now)

        with TestClient(application(db)) as http:
            unsigned = http.post(
                "/v2/b2b08/plots/" + identity["plot"] + "/state/assess",
                json=body,
            )
            assert unsigned.status_code == 401
            foreign = signed_post(http, identity, body, tenant=str(ObjectId()))
            assert foreign.status_code == 403
            assert db["Layer0ScientificAssessment"].count_documents({}) == 0

            good = signed_post(http, identity, body)
            assert good.status_code == 200, (good.status_code, good.text)
            result = good.json()
            assert result["verified_delivery_receipt_count"] == 1
            assert result["signed_input_count"] >= 1
            assert result["scientific_publication_authorized"] is False
            assert result["actuator_control_authorized"] is False

            committed = db["Layer0ScientificAssessment"].find_one({
                "assessment_id": body["assessment_id"], "status": "COMMITTED",
            })
            assert committed is not None
            refs = committed["result"]["verified_delivery_commits"]
            assert len(refs) == 1 and refs[0]["receipt_ids"] == ["isolated-http-delivery-1"]
            assert len(refs[0]["evidence_fingerprints"]) == 1
            assert db["Layer0IrrigationReceiptConsumption"].count_documents({
                "status": "COMMITTED",
            }) == 1
            assert db["Layer0IrrigationCommittedState"].count_documents({}) == 1

            # A fresh, differently signed service request cannot re-execute
            # an assessment ID, even if the HTTP nonce itself is new.
            replay = signed_post(http, identity, body)
            assert replay.status_code == 409
            assert db["Layer0IrrigationReceiptConsumption"].count_documents({
                "status": "COMMITTED",
            }) == 1

        # Fresh ASGI lifespan: new delivery verifier, source verifier, and
        # ZoneKalmanFilter. Cold replay must use the original Mongo snapshot.
        with TestClient(application(db)) as restarted:
            rerun = dict(body, assessment_id="isolated-assessment-0002")
            recovered = signed_post(restarted, identity, rerun)
            assert recovered.status_code == 200, (
                recovered.status_code, recovered.text,
            )
            assert recovered.json()["verified_delivery_receipt_count"] == 1
            assert db["Layer0IrrigationReceiptConsumption"].count_documents({
                "status": "COMMITTED",
            }) == 1
            assert db["Layer0IrrigationCommittedState"].count_documents({}) == 1
            journal = db["Layer0ScientificAssessment"].find_one({
                "assessment_id": rerun["assessment_id"], "status": "COMMITTED",
            })
            assert journal is not None
            links = journal["result"]["verified_delivery_commits"]
            assert len(links) == 1
            assert links[0]["recovered_from_durable_l3_commit"] is True

            # Current ownership revocation must prevent any new scientific
            # assessment even when an existing L3 snapshot is available.
            db["Plot"].update_one(
                {"_id": ObjectId(identity["plot"])},
                {"$set": {"isRevoked": True}},
            )
            after_revoke = signed_post(
                restarted, identity,
                dict(body, assessment_id="isolated-assessment-0003"),
            )
            assert after_revoke.status_code == 403
            assert db["Layer0ScientificAssessment"].count_documents({
                "assessment_id": "isolated-assessment-0003",
            }) == 0
    finally:
        # No global drop; the only destructive action targets a fresh,
        # uniquely generated database, never the application's named DB.
        if database_name.startswith(PREFIX):
            client.drop_database(database_name)
        client.close()
