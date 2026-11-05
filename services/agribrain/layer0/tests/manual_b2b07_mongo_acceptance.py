"""Explicit operator-invoked B07-SEC MongoDB replica-set acceptance.

DO NOT include this in ordinary fast suite discovery. It requires a throwaway
test database on an actual transaction-capable MongoDB replica set. Set only:
    AKALORIS_B07_MONGO_TEST_URI=mongodb://.../?replicaSet=...
Then:
    py -m pytest -q services/agribrain/layer0/tests/manual_b2b07_mongo_acceptance.py

Creates a fresh "akaloris_b2b07_gate_<random>" database and DROPS ONLY THAT
unique database on completion. Never specify a production connection string.
No application Plot/Farm/User collections are touched. This checks the
store-level transaction boundary and end-to-end signed L3→Kalman workflow.
"""
from __future__ import annotations

import multiprocessing
import os
import uuid

import pytest
from pymongo import MongoClient

from services.agribrain.layer0.mongo_irrigation_idempotency import (
    MongoIrrigationIdempotencyStore,
)
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_DOMAIN,
    VERIFIED_IRRIGATION_PURPOSE,
    VerifiedDeliveredIrrigationGrant,
    VerifiedDeliveredIrrigationReceipt,
    VerifiedDeliveredIrrigationSigner,
)
from services.agribrain.layer0.v3_kms_signed_issuer import KmsPublicKeyRegistry
from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationAuthority,
    DurableRevocationSnapshot,
)
from services.agribrain.layer0.production_admission import configure_server_delivery_verifier
from services.agribrain.layer0.kalman_engine import ZoneKalmanFilter


DAY = "2026-11-01"


def _grant(receipt_id="b07-real", replay_key="b07-real-replay"):
    return VerifiedDeliveredIrrigationGrant(
        domain=VERIFIED_IRRIGATION_DOMAIN,
        version="v3", algorithm="Ed25519",
        key_id="integration-fixture-public-key",
        issuer_id="integration-fixture-l3-authority",
        purpose=VERIFIED_IRRIGATION_PURPOSE,
        receipt_id=receipt_id,
        tenant_id="isolated-test-tenant",
        plot_id="isolated-test-plot",
        geometry_hash="isolated-test-polygon",
        geometry_version=1,
        zone_id="plot",
        delivery_start="2026-11-01T12:00:00Z",
        delivery_end="2026-11-01T14:00:00Z",
        delivered_volume_liters=1000.0,
        wetted_area_m2=100.0,
        delivery_efficiency_fraction=0.9,
        net_infiltrated_depth_mm=9.0,
        conversion_calibration_id="integration-fixture-calibration",
        depth_uncertainty_sigma_mm=0.5,
        source_evidence_cas_root="integration-fixture-evidence",
        replay_idempotency_key=replay_key,
        revocation_revision_anchor=0,
        issued_at="2026-11-01T14:05:00Z",
        expires_at="2026-12-31T14:05:00Z",
    )


def _snapshot():
    return {
        "tenant_id": "isolated-test-tenant",
        "plot_id": "isolated-test-plot",
        "zone_id": "plot",
        "geometry_hash": "isolated-test-polygon",
        "geometry_version": 1,
        "day": DAY,
        "state": {
            "day": DAY,
            "values": [0.1] * 9,
            "variance": [1.0] * 9,
            "last_obs_day": None,
            "days_since_obs": 1.0,
        },
        "covariance": [
            [float(i == j) for j in range(9)] for i in range(9)
        ],
        "provenance": {
            "verified_delivery_receipts": ["b07-real"],
            "scientific_publication_authorized": False,
            "actuator_control_authorized": False,
        },
    }


def _worker(uri, db_name, barrier, q):
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        store = MongoIrrigationIdempotencyStore(client[db_name])
        barrier.wait(timeout=20)
        r = store.stage_reservation(_grant(), DAY)
        store.commit_many([r], state_snapshot=_snapshot())
        q.put("committed")
    except ValueError as exc:
        if "duplicate_receipt_or_replay_key" in str(exc):
            q.put("duplicate_denied")
        else:
            q.put("unexpected_value_error:" + str(exc))
    except Exception as exc:
        q.put("error:" + type(exc).__name__ + ":" + str(exc))
    finally:
        client.close()


def test_real_replica_set_two_processes_one_commit_and_atomic_failure():
    uri = os.environ.get("AKALORIS_B07_MONGO_TEST_URI", "").strip()
    if not uri:
        pytest.fail(
            "AKALORIS_B07_MONGO_TEST_URI is required for explicit live acceptance"
        )
    name = "akaloris_b2b07_gate_" + uuid.uuid4().hex
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        database = client[name]
        database.command("ping")
        # A real transaction commit must work; standalone Mongo is rejected.
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        barrier = ctx.Barrier(2)
        p1 = ctx.Process(target=_worker, args=(uri, name, barrier, q))
        p2 = ctx.Process(target=_worker, args=(uri, name, barrier, q))
        p1.start()
        p2.start()
        p1.join(45)
        p2.join(45)
        if p1.is_alive():
            p1.terminate()
            p1.join()
        if p2.is_alive():
            p2.terminate()
            p2.join()
        assert p1.exitcode == 0 and p2.exitcode == 0
        outcomes = sorted([q.get(timeout=10), q.get(timeout=10)])
        assert outcomes == ["committed", "duplicate_denied"]

        receipts = database["Layer0IrrigationReceiptConsumption"]
        snapshots = database["Layer0IrrigationCommittedState"]
        assert receipts.count_documents({"status": "COMMITTED"}) == 1
        assert snapshots.count_documents({}) == 1

        # Fault injection through unique snapshot ID: Mongo must roll back
        # the receipt update when the state-document insert conflicts.
        store = MongoIrrigationIdempotencyStore(database)
        late = store.stage_reservation(
            _grant("b07-late", "b07-late-replay"), DAY,
        )
        with pytest.raises(RuntimeError, match="irrigation_state_commit_unconfirmed"):
            store.commit_many([late], state_snapshot=_snapshot())
        assert receipts.find_one({"_id": "b07-late"})["status"] == "STAGED"
        store._rollback_reservation(late)
        assert receipts.find_one({"_id": "b07-late"}) is None
        assert receipts.count_documents({"status": "COMMITTED"}) == 1
        assert snapshots.count_documents({}) == 1

        # A new client/worker can recover the committed checkpoint without
        # making the original receipt available for physical reapplication.
        independent = MongoIrrigationIdempotencyStore(database)
        recovered = independent.recover_snapshot(
            tenant_id="isolated-test-tenant",
            plot_id="isolated-test-plot",
            zone_id="plot", geometry_hash="isolated-test-polygon",
            geometry_version=1, day=DAY,
        )
        assert recovered is not None
        assert recovered["receipt_ids"] == ["b07-real"]
        with pytest.raises(ValueError, match="duplicate_receipt_or_replay_key"):
            independent.stage_reservation(_grant(), DAY)
    finally:
        # Unique name ensures the cleanup cannot target existing user data.
        if name.startswith("akaloris_b2b07_gate_"):
            client.drop_database(name)
        client.close()



def test_real_replica_set_signed_l3_delivery_to_scoped_kalman_assessment():
    uri = os.environ.get("AKALORIS_B07_MONGO_TEST_URI", "").strip()
    if not uri:
        pytest.fail("AKALORIS_B07_MONGO_TEST_URI is required for explicit live acceptance")
    name = "akaloris_b2b07_kalman_" + uuid.uuid4().hex
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    cutoff = datetime(2026, 11, 1, 23, 59, 59, tzinfo=timezone.utc)
    weather = {"temp_min": 10.0, "temp_max": 20.0, "precipitation": 0.0, "et0": 3.0}

    try:
        database = client[name]
        database.command("ping")

        # 1. Generate L3 keypair and register in trusted registry
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_bytes = priv.public_key().public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )

        t_base = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
        authority_time = datetime.now(timezone.utc)
        registry = KmsPublicKeyRegistry()
        registry.register_public_key(
            key_id="l3-meter-real-1",
            issuer_id="akaloris-l3-irrigation-authority",
            source="sensor_iot",
            algorithm="Ed25519",
            public_key_pem_or_bytes=pub_bytes,
            valid_from=t_base - timedelta(days=30),
            valid_until=t_base + timedelta(days=365),
        )

        snap = DurableRevocationSnapshot(
            revision=0,
            issued_at=authority_time - timedelta(seconds=10),
            expires_at=authority_time + timedelta(days=1),
            key_statuses={"l3-meter-real-1": "active"},
        )
        revocation_authority = DurableRevocationAuthority(snap, max_snapshot_age_seconds=86400)

        # 2. Configure server delivery verifier with real MongoDB database
        verifier = configure_server_delivery_verifier(
            database=database,
            public_key_registry=registry,
            revocation_authority=revocation_authority,
        )

        # 3. Create signed L3 delivery receipt
        grant_dict = {
            "domain": VERIFIED_IRRIGATION_DOMAIN,
            "version": "v3",
            "algorithm": "Ed25519",
            "key_id": "l3-meter-real-1",
            "issuer_id": "akaloris-l3-irrigation-authority",
            "purpose": VERIFIED_IRRIGATION_PURPOSE,
            "receipt_id": "b07-real-l3-e2e",
            "tenant_id": "isolated-test-tenant",
            "plot_id": "isolated-test-plot",
            "geometry_hash": "isolated-test-polygon",
            "geometry_version": 1,
            "zone_id": "plot",
            "delivery_start": "2026-11-01T12:00:00Z",
            "delivery_end": "2026-11-01T14:00:00Z",
            "delivered_volume_liters": 1000.0,
            "wetted_area_m2": 100.0,
            "delivery_efficiency_fraction": 0.9,
            "net_infiltrated_depth_mm": 9.0,
            "conversion_calibration_id": "cal-meter-mag-9000-v1",
            "depth_uncertainty_sigma_mm": 0.5,
            "source_evidence_cas_root": "bafybeihdwdcefghijk456789abcdef",
            "replay_idempotency_key": "b07-real-l3-replay",
            "revocation_revision_anchor": 0,
            "issued_at": "2026-11-01T14:05:00Z",
            "expires_at": "2026-12-31T14:05:00Z",
            "scientific_publication_authorized": False,
            "actuator_control_authorized": False,
        }
        signer = VerifiedDeliveredIrrigationSigner(
            key_id="l3-meter-real-1",
            issuer_id="akaloris-l3-irrigation-authority",
            algorithm="Ed25519",
            private_key=priv,
        )
        receipt = signer.sign(grant_dict)

        event = {
            "payload": {
                "event_type": "irrigation",
                "event_id": "event-e2e-1",
                "event_role": "VERIFIED_DELIVERY",
                "verified_receipt": receipt.to_dict(),
                "zone_id": "plot",
            },
            "packet_id": "pkt-event-e2e-1",
            "plot_id": "isolated-test-plot",
            "geometry_hash": "isolated-test-polygon",
            "timestamp": datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc),
        }

        # 4. Initialize scoped ZoneKalmanFilter
        filt = ZoneKalmanFilter("plot")
        filt.initialize("2026-10-31")
        filt.parent_plot_id = "isolated-test-plot"
        filt.expected_geometry_hash = "isolated-test-polygon"
        filt.geometry_version = 1
        filt.tenant_id = "isolated-test-tenant"
        filt.evidence_cutoff = cutoff
        filt.delivery_verifier = verifier

        # Baseline without irrigation
        baseline = ZoneKalmanFilter("plot")
        baseline.initialize("2026-10-31")
        baseline.step(DAY, weather, None, None)

        # 5. Advance filter with signed delivery event
        prov = filt.step(DAY, weather, None, [event])

        # Assert physical delivery was admitted and applied
        assert prov["physical_management_events_applied"] == 1
        assert filt.state.sm_0_10 > baseline.state.sm_0_10
        assert filt.state.day == DAY

        # Assert separation of scientific state and authority
        assert prov["scientific_publication_authorized"] is False
        assert prov["actuator_control_authorized"] is False

        # Assert persisted state and receipt in MongoDB replica set
        receipts_col = database["Layer0IrrigationReceiptConsumption"]
        snapshots_col = database["Layer0IrrigationCommittedState"]
        doc = receipts_col.find_one({"_id": "b07-real-l3-e2e"})
        assert doc is not None
        assert doc["status"] == "COMMITTED"
        assert doc["replay_key"] == "b07-real-l3-replay"
        assert snapshots_col.count_documents({}) == 1

        # 6. Replay from a second filter instance must be strictly blocked by live DB
        filt_replay = ZoneKalmanFilter("plot")
        filt_replay.initialize("2026-10-31")
        filt_replay.parent_plot_id = "isolated-test-plot"
        filt_replay.expected_geometry_hash = "isolated-test-polygon"
        filt_replay.geometry_version = 1
        filt_replay.tenant_id = "isolated-test-tenant"
        filt_replay.evidence_cutoff = cutoff
        filt_replay.delivery_verifier = verifier

        replayed_event = {
            "payload": {
                "event_type": "irrigation",
                "event_id": "event-e2e-replay",
                "event_role": "VERIFIED_DELIVERY",
                "verified_receipt": receipt.to_dict(),
                "zone_id": "plot",
            },
            "packet_id": "pkt-event-e2e-replay",
            "plot_id": "isolated-test-plot",
            "geometry_hash": "isolated-test-polygon",
            "timestamp": datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc),
        }
        prov_replay = filt_replay.step(DAY, weather, None, [replayed_event])
        assert prov_replay["physical_management_events_applied"] == 0
        assert receipts_col.count_documents({"status": "COMMITTED"}) == 1

        # 7. Independent worker can recover committed state checkpoint from MongoDB
        fresh_verifier = configure_server_delivery_verifier(
            database=database,
            public_key_registry=registry,
            revocation_authority=revocation_authority,
        )
        recovered_filt = ZoneKalmanFilter("plot")
        recovered_filt.initialize("2026-10-31")
        recovered_filt.parent_plot_id = "isolated-test-plot"
        recovered_filt.expected_geometry_hash = "isolated-test-polygon"
        recovered_filt.geometry_version = 1
        recovered_filt.tenant_id = "isolated-test-tenant"
        recovered_filt.delivery_verifier = fresh_verifier

        assert recovered_filt.recover_committed_delivery_state(DAY) is True
        assert recovered_filt.state.values == pytest.approx(filt.state.values)
        assert recovered_filt.provenance_history[-1]["recovered_from_durable_l3_commit"] is True

    finally:
        if name.startswith("akaloris_b2b07_kalman_"):
            client.drop_database(name)
        client.close()
