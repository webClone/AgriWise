"""Unit tests for Layer 0 Operational Recovery, Reconciliation & Legacy Quarantine."""
from datetime import datetime, timedelta, timezone
import pytest

from services.agribrain.layer0.operational_reconciliation import (
    OperationalReconciliationError,
    audit_staged_assessments,
    compute_operator_authorization_signature,
    migrate_legacy_receipt_evidence_fingerprint,
    quarantine_legacy_receipts,
    reconcile_staged_assessment,
    scan_unfingerprinted_legacy_receipts,
    verify_operator_authorization,
)
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_DOMAIN,
    VERIFIED_IRRIGATION_PURPOSE,
    VerifiedDeliveredIrrigationGrant,
    physical_evidence_fingerprint,
)

UTC = timezone.utc
SECRET = "test-operator-auth-secret-key-12345"


class MockCursor:
    def __init__(self, docs):
        self._docs = list(docs)
    def __iter__(self):
        return iter(self._docs)


class MockCollection:
    def __init__(self, initial=None):
        self.docs = {d["_id"]: dict(d) for d in (initial or [])}

    def find(self, query=None):
        query = query or {}
        matches = []
        for d in self.docs.values():
            match = True
            for k, v in query.items():
                if k == "$or":
                    or_match = False
                    for sub in v:
                        for sk, sv in sub.items():
                            if isinstance(sv, dict) and "$exists" in sv:
                                exists = sk in d
                                if exists == sv["$exists"]:
                                    or_match = True
                            elif d.get(sk) == sv:
                                or_match = True
                    if not or_match:
                        match = False
                elif isinstance(v, dict):
                    if "$in" in v and d.get(k) not in v["$in"]:
                        match = False
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        match = False
                elif d.get(k) != v:
                    match = False
            if match:
                matches.append(dict(d))
        return MockCursor(matches)

    def find_one(self, query=None):
        res = list(self.find(query))
        return dict(res[0]) if res else None

    def count_documents(self, query=None):
        return len(list(self.find(query)))

    def update_one(self, query, update):
        target = self.find_one(query)
        if not target:
            return MockUpdateResult(0)
        doc = self.docs[target["_id"]]
        if "$set" in update:
            doc.update(update["$set"])
        if "$unset" in update:
            for k in update["$unset"]:
                doc.pop(k, None)
        return MockUpdateResult(1)

    def update_many(self, query, update):
        targets = list(self.find(query))
        for t in targets:
            self.update_one({"_id": t["_id"]}, update)
        return MockUpdateResult(len(targets))


class MockUpdateResult:
    def __init__(self, count):
        self.matched_count = count
        self.modified_count = count


class MockDatabase:
    def __init__(self):
        self.collections = {
            "Layer0ScientificAssessment": MockCollection(),
            "Layer0IrrigationReceiptConsumption": MockCollection(),
            "Layer0IrrigationCommittedState": MockCollection(),
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection()
        return self.collections[name]

    def command(self, cmd):
        return {"ok": 1}


def test_operator_authorization_verification():
    now = datetime.now(UTC)
    ts = now.isoformat().replace("+00:00", "Z")
    sig = compute_operator_authorization_signature("lead-op", "ABORT_AND_ROLLBACK", "a1", ts, SECRET)
    
    # Valid signature passes
    verify_operator_authorization("lead-op", "ABORT_AND_ROLLBACK", "a1", ts, sig, SECRET, now=now)
    
    # Tampered action fails
    with pytest.raises(OperationalReconciliationError, match="operator_authorization_signature_invalid"):
        verify_operator_authorization("lead-op", "COMPLETE_RECONCILED", "a1", ts, sig, SECRET, now=now)
        
    # Expired timestamp fails (> 300s)
    old_ts = (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    old_sig = compute_operator_authorization_signature("lead-op", "ABORT_AND_ROLLBACK", "a1", old_ts, SECRET)
    with pytest.raises(OperationalReconciliationError, match="authorization_timestamp_expired"):
        verify_operator_authorization("lead-op", "ABORT_AND_ROLLBACK", "a1", old_ts, old_sig, SECRET, now=now)


def test_audit_staged_assessments_assessment_specific_isolation():
    db = MockDatabase()
    # Two assessments on the SAME plot
    db["Layer0ScientificAssessment"].docs = {
        "a1": {
            "_id": "a1", "assessment_id": "a1", "tenant_id": "t1", "plot_id": "plot-shared",
            "status": "STAGED", "submitted_receipt_ids": ["rA"],
        },
        "a2": {
            "_id": "a2", "assessment_id": "a2", "tenant_id": "t1", "plot_id": "plot-shared",
            "status": "STAGED", "submitted_receipt_ids": ["rB"],
        },
    }
    # rA is staged, rB is committed
    db["Layer0IrrigationReceiptConsumption"].docs = {
        "rA": {"_id": "rA", "tenant_id": "t1", "plot_id": "plot-shared", "status": "STAGED"},
        "rB": {"_id": "rB", "tenant_id": "t1", "plot_id": "plot-shared", "status": "COMMITTED"},
    }
    
    reports = audit_staged_assessments(db)
    assert len(reports) == 2
    r_map = {r.assessment_id: r for r in reports}
    assert r_map["a1"].disposition == "STRANDED_UNCOMMITTED_RESERVATIONS"
    assert r_map["a1"].submitted_receipt_ids == ["rA"]
    assert r_map["a2"].disposition == "DURABLE_COMMIT_READY_FOR_RECONCILIATION"
    assert r_map["a2"].submitted_receipt_ids == ["rB"]


def test_reconcile_abort_and_rollback_leaves_unrelated_assessments_untouched():
    db = MockDatabase()
    # Two assessments on SAME plot
    db["Layer0ScientificAssessment"].docs = {
        "a1": {
            "_id": "a1", "assessment_id": "a1", "tenant_id": "t1", "plot_id": "plot-shared",
            "status": "STAGED", "claim_nonce": "nonce-A", "submitted_receipt_ids": ["rA"],
        },
        "a2": {
            "_id": "a2", "assessment_id": "a2", "tenant_id": "t1", "plot_id": "plot-shared",
            "status": "STAGED", "claim_nonce": "nonce-B", "submitted_receipt_ids": ["rB"],
        },
    }
    db["Layer0IrrigationReceiptConsumption"].docs = {
        "rA": {"_id": "rA", "tenant_id": "t1", "plot_id": "plot-shared", "status": "STAGED"},
        "rB": {"_id": "rB", "tenant_id": "t1", "plot_id": "plot-shared", "status": "STAGED"},
    }
    
    now = datetime.now(UTC)
    ts = now.isoformat().replace("+00:00", "Z")
    sig = compute_operator_authorization_signature("lead-op", "ABORT_AND_ROLLBACK", "a1", ts, SECRET)
    
    # Reconcile a1
    res = reconcile_staged_assessment(
        db, "a1", "ABORT_AND_ROLLBACK",
        operator_principal="lead-op",
        rationale="Upstream network timeout during satellite ingest",
        authorization_signature=sig,
        secret=SECRET,
        authorization_timestamp=ts,
        now=now,
    )
    assert res["status"] == "ABORTED"
    assert res["reservations_rolled_back"] == 1
    
    # Check that a1 was aborted and rA rolled back
    assert db["Layer0ScientificAssessment"].docs["a1"]["status"] == "ABORTED"
    assert db["Layer0IrrigationReceiptConsumption"].docs["rA"]["status"] == "ROLLED_BACK"
    
    # CRUCIAL: Check that a2 and rB on the same plot remain strictly STAGED!
    assert db["Layer0ScientificAssessment"].docs["a2"]["status"] == "STAGED"
    assert db["Layer0IrrigationReceiptConsumption"].docs["rB"]["status"] == "STAGED"


def test_reconcile_complete_reconciled_with_exact_lineage():
    db = MockDatabase()
    snap_id = "snap-exact-001"
    db["Layer0ScientificAssessment"].docs = {
        "a1": {
            "_id": "a1", "assessment_id": "a1", "tenant_id": "t1", "plot_id": "p1",
            "geometry_hash": "geom1", "geometry_version": 2,
            "status": "STAGED", "claim_nonce": "nonce-1", "submitted_receipt_ids": ["r1"],
        },
    }
    db["Layer0IrrigationReceiptConsumption"].docs = {
        "r1": {
            "_id": "r1", "tenant_id": "t1", "plot_id": "p1", "status": "COMMITTED",
            "state_snapshot_id": snap_id, "evidence_fingerprint": "fp1",
        },
    }
    db["Layer0IrrigationCommittedState"].docs = {
        snap_id: {
            "_id": snap_id, "tenant_id": "t1", "plot_id": "p1",
            "geometry_hash": "geom1", "geometry_version": 2, "day": "2026-05-01",
            "receipt_ids": ["r1"], "state": {"lai": 0.5},
        },
    }
    
    now = datetime.now(UTC)
    ts = now.isoformat().replace("+00:00", "Z")
    sig = compute_operator_authorization_signature("lead-op", "COMPLETE_RECONCILED", "a1", ts, SECRET)
    
    res = reconcile_staged_assessment(
        db, "a1", "COMPLETE_RECONCILED",
        operator_principal="lead-op",
        rationale="Journal crashed after state commit; reconciling completed assessment",
        authorization_signature=sig,
        secret=SECRET,
        authorization_timestamp=ts,
        now=now,
    )
    assert res["status"] == "COMMITTED"
    assert db["Layer0ScientificAssessment"].docs["a1"]["status"] == "COMMITTED"
    assert db["Layer0ScientificAssessment"].docs["a1"]["result"]["verified_delivery_receipt_count"] == 1


def test_legacy_migration_reproduces_exact_production_fingerprint():
    """Verify legacy migration produces the exact same fingerprint as physical_evidence_fingerprint."""
    db = MockDatabase()
    db["Layer0IrrigationReceiptConsumption"].docs = {
        "r_leg": {
            "_id": "r_leg", "tenant_id": "t1", "plot_id": "p1",
            "zone_id": "plot", "geometry_hash": "geom1", "geometry_version": 2,
            "status": "COMMITTED",
        }
    }
    
    cas_root = "cas://authoritative-flow-meter-evidence-001"
    interval = ("2026-05-01T12:00:00Z", "2026-05-01T14:00:00Z")
    
    res = migrate_legacy_receipt_evidence_fingerprint(
        db, "r_leg",
        source_evidence_cas_root=cas_root,
        delivery_interval=interval,
        operator_principal="data-lead",
        rationale="Audited physical meter log from gateway hardware",
    )
    
    # Construct a modern grant with the identical physical evidence
    modern_grant = VerifiedDeliveredIrrigationGrant(
        domain=VERIFIED_IRRIGATION_DOMAIN,
        version="v3",
        algorithm="Ed25519",
        key_id="k1",
        issuer_id="iss1",
        purpose=VERIFIED_IRRIGATION_PURPOSE,
        receipt_id="r_new_attempt",
        tenant_id="t1",
        plot_id="p1",
        geometry_hash="geom1",
        geometry_version=2,
        zone_id="plot",
        delivery_start=interval[0],
        delivery_end=interval[1],
        delivered_volume_liters=1000.0,
        wetted_area_m2=100.0,
        delivery_efficiency_fraction=0.9,
        net_infiltrated_depth_mm=9.0,
        conversion_calibration_id="meter-1",
        depth_uncertainty_sigma_mm=0.5,
        source_evidence_cas_root=cas_root,
        replay_idempotency_key="rep-new",
        revocation_revision_anchor=0,
        issued_at="2026-05-01T14:05:00Z",
        expires_at="2026-05-01T20:00:00Z",
    )
    
    prod_fingerprint = physical_evidence_fingerprint(modern_grant)
    assert res["evidence_fingerprint"] == prod_fingerprint, (
        f"Migration fingerprint mismatch: {res['evidence_fingerprint']} != {prod_fingerprint}"
    )
    assert db["Layer0IrrigationReceiptConsumption"].docs["r_leg"]["evidence_fingerprint"] == prod_fingerprint
