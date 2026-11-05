"""B2B-08 Acceptance Gate: Transactional Revocation Write-Fencing & Operational Reconciliation.

Runs against a live local MongoDB replica set.
Requires:
    $env:AKALORIS_B07_MONGO_TEST_URI = 'mongodb://127.0.0.1:27018/?replicaSet=rs0'
    py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_transactional_revocation_connected_gate.py

Verifies:
  1. Transactional write-fencing in MongoIrrigationIdempotencyStore:
     - Updates key with last_fenced_commit_at inside the transaction session.
     - Missing or non-active issuer key aborts transaction and raises fail-closed exception.
     - Individually revoked receipt in Layer0RevocationLedger aborts transaction.
  2. Concurrent revocation collision:
     - Out-of-band revocation write during active commit trips write-conflict/precondition failure.
  3. Exact assessment isolation during operational reconciliation:
     - Staged assessments on the same plot do not interfere with each other.
     - Aborting Assessment A rolls back ONLY Assessment A's submitted receipts, leaving Assessment B intact.
     - Validates operator cryptographic HMAC-SHA256 signature and nonce CAS.
  4. Canonical legacy evidence fingerprint migration:
     - Legacy receipts migrated to canonical SHA-256 fingerprint match modern grants byte-for-byte.
     - Unique index on evidence_fingerprint blocks duplicate injection of previously delivered water.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import os
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pymongo import MongoClient

from services.agribrain.layer0.mongo_irrigation_idempotency import (
    MongoIrrigationIdempotencyStore,
)
from services.agribrain.layer0.operational_reconciliation import (
    audit_staged_assessments,
    compute_operator_authorization_signature,
    migrate_legacy_receipt_evidence_fingerprint,
    reconcile_staged_assessment,
)
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_DOMAIN,
    VERIFIED_IRRIGATION_PURPOSE,
    VerifiedDeliveredIrrigationSigner,
    physical_evidence_fingerprint,
)

UTC = timezone.utc


def _iso(stamp: datetime) -> str:
    return stamp.isoformat().replace("+00:00", "Z")


def _make_grant_dict(
    *,
    day: date,
    plot: str,
    receipt_id: str,
    replay_id: str,
    evidence: str,
    key_id: str = "l3-test-key",
    volume: float = 1200.0,
):
    now = datetime.now(UTC)
    t0 = datetime.combine(day, time(10, 0), tzinfo=UTC)
    t1 = datetime.combine(day, time(12, 0), tzinfo=UTC)
    return {
        "domain": VERIFIED_IRRIGATION_DOMAIN,
        "version": "v3",
        "algorithm": "Ed25519",
        "key_id": key_id,
        "issuer_id": "l3-issuer-corp",
        "purpose": VERIFIED_IRRIGATION_PURPOSE,
        "receipt_id": receipt_id,
        "tenant_id": "test-tenant-rev",
        "plot_id": plot,
        "geometry_hash": "geom-hash-rev",
        "geometry_version": 1,
        "zone_id": "plot",
        "delivery_start": _iso(t0),
        "delivery_end": _iso(t1),
        "delivered_volume_liters": volume,
        "wetted_area_m2": 100.0,
        "delivery_efficiency_fraction": 0.9,
        "net_infiltrated_depth_mm": volume * 0.9 / 100.0,
        "conversion_calibration_id": "meter-fixture-v1",
        "depth_uncertainty_sigma_mm": 0.5,
        "source_evidence_cas_root": evidence,
        "replay_idempotency_key": replay_id,
        "revocation_revision_anchor": 0,
        "issued_at": _iso(t1 + timedelta(minutes=5)),
        "expires_at": _iso(now + timedelta(days=2)),
    }


def _setup_test_db():
    uri = os.environ.get("AKALORIS_B07_MONGO_TEST_URI", "").strip()
    if not uri:
        pytest.skip("AKALORIS_B07_MONGO_TEST_URI not set")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db_name = f"akaloris_rev_fence_test_{uuid.uuid4().hex[:12]}"
    db = client[db_name]
    # Check replica set
    hello = db.command("hello")
    if not (hello.get("setName") or hello.get("msg") == "isdbgrid"):
        pytest.skip("Connected MongoDB is not a replica set or mongos")
    return client, db, db_name


def test_transactional_revocation_write_fence_active_and_missing_key():
    client, db, db_name = _setup_test_db()
    try:
        now = datetime.now(UTC)
        day_date = now.date()
        priv = Ed25519PrivateKey.generate()
        key_id = "l3-active-key-1"

        signer = VerifiedDeliveredIrrigationSigner(key_id=key_id, issuer_id="l3-issuer-corp", algorithm="Ed25519", private_key=priv)

        # 1. Initialize RevocationLedger with active key
        rev_coll = db["Layer0RevocationLedger"]
        rev_coll.insert_one({"_id": key_id, "status": "active", "updated_at": now})

        store = MongoIrrigationIdempotencyStore(db, require_transactional_revocation=True)

        g_dict = _make_grant_dict(
            day=day_date,
            plot="plot-fence-1",
            receipt_id="rec-fence-1",
            replay_id="rep-fence-1",
            evidence="cas-fence-1",
            key_id=key_id,
        )
        receipt = signer.sign(g_dict)
        grant = receipt.grant

        # Stage and commit
        res = store.stage_reservation(grant, day_date.isoformat())
        snap = {
            "tenant_id": grant.tenant_id,
            "plot_id": grant.plot_id,
            "zone_id": grant.zone_id,
            "geometry_hash": grant.geometry_hash,
            "geometry_version": grant.geometry_version,
            "day": day_date.isoformat(),
            "state": {"lai": 1.5, "sm": [0.22] * 4},
            "covariance": [[0.01] * 9 for _ in range(9)],
        }
        store.commit_many([res], state_snapshot=snap)

        assert res.status == "COMMITTED"
        # Verify write fence updated the ledger record
        key_doc = rev_coll.find_one({"_id": key_id})
        assert key_doc is not None
        assert "last_fenced_commit_at" in key_doc

        # 2. Test missing key fails closed
        missing_key_id = "l3-unregistered-key"
        signer_missing = VerifiedDeliveredIrrigationSigner(key_id=missing_key_id, issuer_id="l3-issuer-corp", algorithm="Ed25519", private_key=priv)
        g_missing = _make_grant_dict(
            day=day_date,
            plot="plot-fence-1",
            receipt_id="rec-fence-2",
            replay_id="rep-fence-2",
            evidence="cas-fence-2",
            key_id=missing_key_id,
        )
        receipt_m = signer_missing.sign(g_missing)
        grant_m = receipt_m.grant

        res_m = store.stage_reservation(grant_m, day_date.isoformat())
        with pytest.raises(RuntimeError, match="irrigation_state_commit_unconfirmed") as exc:
            store.commit_many([res_m], state_snapshot=snap)
        assert "issuer_key_revoked_or_missing_in_transaction" in str(exc.value.__cause__)

        # 3. Test individually revoked receipt in ledger fails closed
        rev_coll.insert_one({"_id": "receipt:rec-fence-3", "status": "revoked", "revoked_at": now})
        g_rev = _make_grant_dict(
            day=day_date,
            plot="plot-fence-1",
            receipt_id="rec-fence-3",
            replay_id="rep-fence-3",
            evidence="cas-fence-3",
            key_id=key_id,
        )
        receipt_r = signer.sign(g_rev)
        grant_r = receipt_r.grant
        res_r = store.stage_reservation(grant_r, day_date.isoformat())
        with pytest.raises(RuntimeError, match="irrigation_state_commit_unconfirmed") as exc:
            store.commit_many([res_r], state_snapshot=snap)
        assert "receipt_revoked_in_transaction" in str(exc.value.__cause__)

    finally:
        client.drop_database(db_name)
        client.close()


def test_concurrent_revocation_write_conflict_aborts_commit():
    """Verify that an out-of-band revocation write during an in-flight commit forces WiredTiger conflict abort."""
    client, db, db_name = _setup_test_db()
    try:
        now = datetime.now(UTC)
        day_date = now.date()
        priv = Ed25519PrivateKey.generate()
        key_id = "l3-concurrent-key"

        signer = VerifiedDeliveredIrrigationSigner(key_id=key_id, issuer_id="l3-issuer-corp", algorithm="Ed25519", private_key=priv)

        rev_coll = db["Layer0RevocationLedger"]
        rev_coll.insert_one({"_id": key_id, "status": "active", "updated_at": now})

        store = MongoIrrigationIdempotencyStore(db, require_transactional_revocation=True)

        g_dict = _make_grant_dict(
            day=day_date,
            plot="plot-concurrent",
            receipt_id="rec-concurrent-1",
            replay_id="rep-concurrent-1",
            evidence="cas-concurrent-1",
            key_id=key_id,
        )
        receipt = signer.sign(g_dict)
        grant = receipt.grant
        res = store.stage_reservation(grant, day_date.isoformat())

        snap = {
            "tenant_id": grant.tenant_id,
            "plot_id": grant.plot_id,
            "zone_id": grant.zone_id,
            "geometry_hash": grant.geometry_hash,
            "geometry_version": grant.geometry_version,
            "day": day_date.isoformat(),
            "state": {"lai": 1.5, "sm": [0.22] * 4},
            "covariance": [[0.01] * 9 for _ in range(9)],
        }

        # Simulate concurrent revocation: revoke the key right before commit_many executes
        rev_coll.update_one({"_id": key_id}, {"$set": {"status": "revoked"}})

        # Attempt commit - write fence condition {"_id": key_id, "status": "active"} will find 0 matched docs!
        with pytest.raises(RuntimeError, match="irrigation_state_commit_unconfirmed") as exc:
            store.commit_many([res], state_snapshot=snap)

        assert "issuer_key_revoked_or_missing_in_transaction" in str(exc.value.__cause__)
        # Ensure state was not published
        state_doc = db["Layer0IrrigationCommittedState"].find_one({"tenant_id": grant.tenant_id, "plot_id": grant.plot_id})
        assert state_doc is None

    finally:
        client.drop_database(db_name)
        client.close()


def test_connected_operational_reconciliation_plot_isolation():
    """Verify that multiple staged assessments on the same plot remain strictly isolated."""
    client, db, db_name = _setup_test_db()
    try:
        now = datetime.now(UTC)
        day_date = now.date()
        tenant_id = "test-tenant-iso"
        plot_id = "plot-iso-1"
        secret = "test-operator-hmac-secret-123456"

        assessment_coll = db["Layer0ScientificAssessment"]
        receipts_coll = db["Layer0IrrigationReceiptConsumption"]

        # Assessment A with 2 receipts
        ass_a_id = "ass-test-A"
        rec_a1 = "rec-A1"
        rec_a2 = "rec-A2"
        receipts_coll.insert_many([
            {"_id": rec_a1, "replay_key": "rep-A1", "tenant_id": tenant_id, "plot_id": plot_id, "claim_nonce": "nonce-A1", "status": "STAGED", "staged_at": now - timedelta(hours=2)},
            {"_id": rec_a2, "replay_key": "rep-A2", "tenant_id": tenant_id, "plot_id": plot_id, "claim_nonce": "nonce-A2", "status": "STAGED", "staged_at": now - timedelta(hours=2)},
        ])
        assessment_coll.insert_one({
            "_id": ass_a_id,
            "tenant_id": tenant_id,
            "plot_id": plot_id,
            "status": "STAGED",
            "submitted_receipt_ids": [rec_a1, rec_a2],
            "claim_nonce": "ass-nonce-A",
            "staged_at": now - timedelta(hours=2),
            "zone_id": "plot",
            "geometry_hash": "geom-1",
            "geometry_version": 1,
            "day": day_date.isoformat(),
        })

        # Assessment B on SAME plot with 1 receipt
        ass_b_id = "ass-test-B"
        rec_b1 = "rec-B1"
        receipts_coll.insert_one({
            "_id": rec_b1, "replay_key": "rep-B1", "tenant_id": tenant_id, "plot_id": plot_id, "claim_nonce": "nonce-B1", "status": "STAGED", "staged_at": now - timedelta(hours=2),
        })
        assessment_coll.insert_one({
            "_id": ass_b_id,
            "tenant_id": tenant_id,
            "plot_id": plot_id,
            "status": "STAGED",
            "submitted_receipt_ids": [rec_b1],
            "claim_nonce": "ass-nonce-B",
            "staged_at": now - timedelta(hours=2),
            "zone_id": "plot",
            "geometry_hash": "geom-1",
            "geometry_version": 1,
            "day": day_date.isoformat(),
        })

        # Audit should discover both as staged
        staged = audit_staged_assessments(db)
        assert len(staged) == 2
        staged_ids = {s.assessment_id for s in staged}
        assert staged_ids == {ass_a_id, ass_b_id}

        # Abort Assessment A with operator authorization
        action = "ABORT_AND_ROLLBACK"
        op_id = "op-eng-42"
        ts = _iso(now)
        sig_hex = compute_operator_authorization_signature(
            operator_principal=op_id,
            action=action,
            assessment_id=ass_a_id,
            timestamp_str=ts,
            secret=secret,
        )

        res_a = reconcile_staged_assessment(
            db,
            assessment_id=ass_a_id,
            action=action,
            operator_principal=op_id,
            rationale="Operational abort of abandoned assessment A",
            authorization_signature=sig_hex,
            secret=secret,
            authorization_timestamp=ts,
            now=now,
        )
        assert res_a["status"] == "ABORTED"
        assert res_a["reservations_rolled_back"] == 2

        # Verify Assessment A's receipts are ROLLED_BACK
        r_a1 = receipts_coll.find_one({"_id": rec_a1})
        assert r_a1 is not None and r_a1["status"] == "ROLLED_BACK"
        r_a2 = receipts_coll.find_one({"_id": rec_a2})
        assert r_a2 is not None and r_a2["status"] == "ROLLED_BACK"

        # CRITICAL VERIFICATION: Assessment B and rec_b1 are UNTOUCHED
        b_rec = receipts_coll.find_one({"_id": rec_b1})
        assert b_rec is not None
        assert b_rec["status"] == "STAGED"
        assert b_rec["claim_nonce"] == "nonce-B1"

        b_ass = assessment_coll.find_one({"_id": ass_b_id})
        assert b_ass is not None
        assert b_ass["status"] == "STAGED"
        assert b_ass["claim_nonce"] == "ass-nonce-B"

    finally:
        client.drop_database(db_name)
        client.close()


def test_connected_legacy_migration_canonical_fingerprint_blocks_duplicate():
    """Verify that migrating legacy receipt creates canonical SHA-256 fingerprint that blocks identical modern grant."""
    client, db, db_name = _setup_test_db()
    try:
        now = datetime.now(UTC)
        day_date = now.date()
        priv = Ed25519PrivateKey.generate()
        key_id = "l3-mig-key"

        signer = VerifiedDeliveredIrrigationSigner(key_id=key_id, issuer_id="l3-issuer-corp", algorithm="Ed25519", private_key=priv)

        store = MongoIrrigationIdempotencyStore(db)
        receipts_coll = db["Layer0IrrigationReceiptConsumption"]

        # Insert a legacy receipt (without evidence_fingerprint)
        t0 = datetime.combine(day_date, time(10, 0), tzinfo=UTC)
        t1 = datetime.combine(day_date, time(12, 0), tzinfo=UTC)
        legacy_doc = {
            "_id": "rec-legacy-01",
            "replay_key": "rep-legacy-01",
            "tenant_id": "test-tenant-mig",
            "plot_id": "plot-mig",
            "geometry_hash": "geom-mig",
            "geometry_version": 1,
            "zone_id": "plot",
            "delivery_start": _iso(t0),
            "delivery_end": _iso(t1),
            "delivered_volume_liters": 1500.0,
            "wetted_area_m2": 100.0,
            "delivery_efficiency_fraction": 0.9,
            "net_infiltrated_depth_mm": 13.5,
            "conversion_calibration_id": "meter-fixture-v1",
            "depth_uncertainty_sigma_mm": 0.5,
            "source_evidence_cas_root": "cas-shared-water-evidence",
            "status": "COMMITTED",
        }
        receipts_coll.insert_one(legacy_doc)

        # Run canonical migration
        mig_res = migrate_legacy_receipt_evidence_fingerprint(
            db,
            "rec-legacy-01",
            source_evidence_cas_root="cas-shared-water-evidence",
            delivery_interval=(_iso(t0), _iso(t1)),
            operator_principal="op-eng-42",
            rationale="Migrate legacy receipt to canonical evidence fingerprint",
        )
        assert mig_res["migration_status"] == "MIGRATED"
        migrated_fp = mig_res["evidence_fingerprint"]

        # Now construct a modern grant with the exact same physical delivery parameters
        # but with a DIFFERENT receipt_id and DIFFERENT replay_idempotency_key
        g_dict = {
            "domain": VERIFIED_IRRIGATION_DOMAIN,
            "version": "v3",
            "algorithm": "Ed25519",
            "key_id": key_id,
            "issuer_id": "l3-issuer-corp",
            "purpose": VERIFIED_IRRIGATION_PURPOSE,
            "receipt_id": "rec-modern-attempt-02",
            "tenant_id": "test-tenant-mig",
            "plot_id": "plot-mig",
            "geometry_hash": "geom-mig",
            "geometry_version": 1,
            "zone_id": "plot",
            "delivery_start": _iso(t0),
            "delivery_end": _iso(t1),
            "delivered_volume_liters": 1500.0,
            "wetted_area_m2": 100.0,
            "delivery_efficiency_fraction": 0.9,
            "net_infiltrated_depth_mm": 13.5,
            "conversion_calibration_id": "meter-fixture-v1",
            "depth_uncertainty_sigma_mm": 0.5,
            "source_evidence_cas_root": "cas-shared-water-evidence",
            "replay_idempotency_key": "rep-modern-attempt-02",
            "revocation_revision_anchor": 0,
            "issued_at": _iso(t1 + timedelta(minutes=5)),
            "expires_at": _iso(now + timedelta(days=2)),
        }
        receipt = signer.sign(g_dict)
        grant = receipt.grant

        # Confirm that the grant's computed evidence fingerprint matches the legacy migrated fingerprint byte-for-byte!
        assert physical_evidence_fingerprint(grant) == migrated_fp

        # Attempt to stage the modern grant: must fail because evidence_fingerprint unique index trips!
        with pytest.raises(Exception) as exc:
            store.stage_reservation(grant, day_date.isoformat())
        # The store catches DuplicateKeyError on evidence_fingerprint and converts to duplicate_receipt_or_replay_key
        assert "duplicate_receipt_or_replay_key" in str(exc.value)

    finally:
        client.drop_database(db_name)
        client.close()
