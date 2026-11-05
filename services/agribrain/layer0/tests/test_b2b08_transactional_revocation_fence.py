"""Unit tests for B2B-08 in-transaction revocation fencing in MongoIrrigationIdempotencyStore."""
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from services.agribrain.layer0.mongo_irrigation_idempotency import MongoIrrigationIdempotencyStore
from services.agribrain.layer0.verified_irrigation_contract import (
    IrrigationIdempotencyReservation,
    VerifiedDeliveredIrrigationGrant,
)

UTC = timezone.utc


class MockTransactionSession:
    def __init__(self):
        self.aborted = False
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.aborted = True
        else:
            self.committed = True

    def start_transaction(self):
        return self


def make_mock_grant(key_id="l3-key-1", receipt_id="rec-1", replay_key="rep-1"):
    return VerifiedDeliveredIrrigationGrant(
        domain="akaloris/layer0/verified-delivered-irrigation/v3",
        version="v3",
        algorithm="Ed25519",
        key_id=key_id,
        issuer_id="l3-issuer",
        purpose="verified_delivered_irrigation",
        receipt_id=receipt_id,
        tenant_id="t1",
        plot_id="p1",
        geometry_hash="geom1",
        geometry_version=2,
        zone_id="plot",
        delivery_start="2026-05-01T12:00:00Z",
        delivery_end="2026-05-01T14:00:00Z",
        delivered_volume_liters=1000.0,
        wetted_area_m2=100.0,
        delivery_efficiency_fraction=0.9,
        net_infiltrated_depth_mm=9.0,
        conversion_calibration_id="meter-1",
        depth_uncertainty_sigma_mm=0.5,
        source_evidence_cas_root="cas-1",
        replay_idempotency_key=replay_key,
        revocation_revision_anchor=0,
        issued_at="2026-05-01T14:05:00Z",
        expires_at="2026-05-01T20:00:00Z",
        signature=b"test-sig-bytes-0000000000000000000000000000000000000000000000000000000000000000",
    )


def test_in_transaction_revocation_fence_aborts_commit_if_key_revoked():
    db = MagicMock()
    client = MagicMock()
    session = MockTransactionSession()
    client.start_session.return_value = session
    db.client = client
    
    receipts_coll = MagicMock()
    states_coll = MagicMock()
    rev_coll = MagicMock()
    rev_coll.count_documents.return_value = 1
    
    # matched_count = 0 means key wasn't active (revoked or missing)
    fence_res = MagicMock()
    fence_res.matched_count = 0
    rev_coll.update_one.return_value = fence_res
    
    def get_coll(name):
        if name == "Layer0IrrigationReceiptConsumption":
            return receipts_coll
        elif name == "Layer0IrrigationCommittedState":
            return states_coll
        elif name == "Layer0RevocationLedger":
            return rev_coll
        return MagicMock()
        
    db.__getitem__.side_effect = get_coll
    
    store = MongoIrrigationIdempotencyStore(db)
    
    receipts_coll.find_one.return_value = {
        "_id": "rec-revoked", "key_id": "l3-revoked-key",
        "replay_key": "rep-1", "evidence_fingerprint": "fp1",
        "claim_nonce": "nonce-revoked", "status": "STAGED",
    }
    
    res = IrrigationIdempotencyReservation(
        store=store,
        receipt_id="rec-revoked",
        replay_key="rep-1",
        tenant_id="t1",
        plot_id="p1",
        geometry_hash="geom1",
        geometry_version=2,
        day="2026-05-01",
        evidence_fingerprint="fp1",
    )
    res.claim_nonce = "nonce-revoked"
    res.zone_id = "plot"
    store._pending_receipts[res.receipt_id] = res
    store._pending_replay_keys[res.replay_key] = res
    
    snap = {
        "tenant_id": "t1", "plot_id": "p1", "zone_id": "plot",
        "geometry_hash": "geom1", "geometry_version": 2, "day": "2026-05-01",
        "state": {"lai": 1.0}, "covariance": [[0.1] * 9 for _ in range(9)],
    }
    
    with pytest.raises(RuntimeError, match="irrigation_state_commit_unconfirmed") as exc:
        store.commit_many([res], state_snapshot=snap)
    assert "issuer_key_revoked_or_missing_in_transaction" in str(exc.value.__cause__)
    assert session.aborted is True


def test_in_transaction_revocation_fence_passes_when_key_active():
    db = MagicMock()
    client = MagicMock()
    session = MockTransactionSession()
    client.start_session.return_value = session
    db.client = client
    
    receipts_coll = MagicMock()
    states_coll = MagicMock()
    rev_coll = MagicMock()
    rev_coll.count_documents.return_value = 1
    
    fence_res = MagicMock()
    fence_res.matched_count = 1
    rev_coll.update_one.return_value = fence_res
    rev_coll.find_one.return_value = None  # receipt not individually revoked
    
    update_res = MagicMock()
    update_res.matched_count = 1
    receipts_coll.update_one.return_value = update_res
    
    def get_coll(name):
        if name == "Layer0IrrigationReceiptConsumption":
            return receipts_coll
        elif name == "Layer0IrrigationCommittedState":
            return states_coll
        elif name == "Layer0RevocationLedger":
            return rev_coll
        return MagicMock()
        
    db.__getitem__.side_effect = get_coll
    
    store = MongoIrrigationIdempotencyStore(db)
    
    receipts_coll.find_one.return_value = {
        "_id": "rec-active", "key_id": "l3-active-key",
        "replay_key": "rep-1", "evidence_fingerprint": "fp1",
        "claim_nonce": "nonce-active", "status": "STAGED",
    }
    
    res = IrrigationIdempotencyReservation(
        store=store,
        receipt_id="rec-active",
        replay_key="rep-1",
        tenant_id="t1",
        plot_id="p1",
        geometry_hash="geom1",
        geometry_version=2,
        day="2026-05-01",
        evidence_fingerprint="fp1",
    )
    res.claim_nonce = "nonce-active"
    res.zone_id = "plot"
    store._pending_receipts[res.receipt_id] = res
    store._pending_replay_keys[res.replay_key] = res
    
    snap = {
        "tenant_id": "t1", "plot_id": "p1", "zone_id": "plot",
        "geometry_hash": "geom1", "geometry_version": 2, "day": "2026-05-01",
        "state": {"lai": 1.0}, "covariance": [[0.1] * 9 for _ in range(9)],
    }
    
    store.commit_many([res], state_snapshot=snap)
    assert session.committed is True
    assert rev_coll.update_one.called
    assert receipts_coll.update_one.called
    assert states_coll.insert_one.called
    assert res.status == "COMMITTED"


def test_in_transaction_revocation_fence_fails_closed_on_probe_error():
    db = MagicMock()
    client = MagicMock()
    session = MockTransactionSession()
    client.start_session.return_value = session
    db.client = client
    
    receipts_coll = MagicMock()
    states_coll = MagicMock()
    rev_coll = MagicMock()
    rev_coll.count_documents.side_effect = RuntimeError("db connection drop")
    
    def get_coll(name):
        if name == "Layer0IrrigationReceiptConsumption":
            return receipts_coll
        elif name == "Layer0IrrigationCommittedState":
            return states_coll
        elif name == "Layer0RevocationLedger":
            return rev_coll
        return MagicMock()
        
    db.__getitem__.side_effect = get_coll
    
    store = MongoIrrigationIdempotencyStore(db)
    
    receipts_coll.find_one.return_value = {
        "_id": "rec-1", "key_id": "l3-key",
        "replay_key": "rep-1", "evidence_fingerprint": "fp1",
        "claim_nonce": "nonce-1", "status": "STAGED",
    }
    
    res = IrrigationIdempotencyReservation(
        store=store,
        receipt_id="rec-1",
        replay_key="rep-1",
        tenant_id="t1",
        plot_id="p1",
        geometry_hash="geom1",
        geometry_version=2,
        day="2026-05-01",
        evidence_fingerprint="fp1",
    )
    res.claim_nonce = "nonce-1"
    res.zone_id = "plot"
    store._pending_receipts[res.receipt_id] = res
    store._pending_replay_keys[res.replay_key] = res
    
    snap = {
        "tenant_id": "t1", "plot_id": "p1", "zone_id": "plot",
        "geometry_hash": "geom1", "geometry_version": 2, "day": "2026-05-01",
        "state": {"lai": 1.0}, "covariance": [[0.1] * 9 for _ in range(9)],
    }
    
    with pytest.raises(RuntimeError, match="irrigation_state_commit_unconfirmed") as exc:
        store.commit_many([res], state_snapshot=snap)
    assert "revocation_ledger_probe_failed" in str(exc.value.__cause__)
    assert session.aborted is True


def test_in_transaction_revocation_fence_aborts_if_receipt_revoked():
    db = MagicMock()
    client = MagicMock()
    session = MockTransactionSession()
    client.start_session.return_value = session
    db.client = client
    
    receipts_coll = MagicMock()
    states_coll = MagicMock()
    rev_coll = MagicMock()
    rev_coll.count_documents.return_value = 1
    
    fence_res = MagicMock()
    fence_res.matched_count = 1
    rev_coll.update_one.return_value = fence_res
    rev_coll.find_one.return_value = {"_id": "receipt:rec-1", "status": "revoked"}
    
    def get_coll(name):
        if name == "Layer0IrrigationReceiptConsumption":
            return receipts_coll
        elif name == "Layer0IrrigationCommittedState":
            return states_coll
        elif name == "Layer0RevocationLedger":
            return rev_coll
        return MagicMock()
        
    db.__getitem__.side_effect = get_coll
    
    store = MongoIrrigationIdempotencyStore(db)
    
    receipts_coll.find_one.return_value = {
        "_id": "rec-1", "key_id": "l3-key",
        "replay_key": "rep-1", "evidence_fingerprint": "fp1",
        "claim_nonce": "nonce-1", "status": "STAGED",
    }
    
    res = IrrigationIdempotencyReservation(
        store=store,
        receipt_id="rec-1",
        replay_key="rep-1",
        tenant_id="t1",
        plot_id="p1",
        geometry_hash="geom1",
        geometry_version=2,
        day="2026-05-01",
        evidence_fingerprint="fp1",
    )
    res.claim_nonce = "nonce-1"
    res.zone_id = "plot"
    store._pending_receipts[res.receipt_id] = res
    store._pending_replay_keys[res.replay_key] = res
    
    snap = {
        "tenant_id": "t1", "plot_id": "p1", "zone_id": "plot",
        "geometry_hash": "geom1", "geometry_version": 2, "day": "2026-05-01",
        "state": {"lai": 1.0}, "covariance": [[0.1] * 9 for _ in range(9)],
    }
    
    with pytest.raises(RuntimeError, match="irrigation_state_commit_unconfirmed") as exc:
        store.commit_many([res], state_snapshot=snap)
    assert "receipt_revoked_in_transaction" in str(exc.value.__cause__)
    assert session.aborted is True
