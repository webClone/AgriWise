"""Explicit operator-invoked B07-SEC MongoDB replica-set acceptance.

DO NOT include this in ordinary fast suite discovery. It requires a throwaway
test database on an actual transaction-capable MongoDB replica set. Set only:
    AKALORIS_B07_MONGO_TEST_URI=mongodb://.../?replicaSet=...
Then:
    py -m pytest -q services/agribrain/layer0/tests/manual_b2b07_mongo_acceptance.py

Creates a fresh "akaloris_b2b07_gate_<random>" database and DROPS ONLY THAT
unique database on completion. Never specify a production connection string.
No application Plot/Farm/User collections are touched. This checks the
store-level transaction boundary; run real signed L3→Kalman workflow separately.
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
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_DOMAIN,
    VERIFIED_IRRIGATION_PURPOSE,
    VerifiedDeliveredIrrigationGrant,
)


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
        expires_at="2026-11-02T14:05:00Z",
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
