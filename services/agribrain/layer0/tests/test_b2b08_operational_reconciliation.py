"""Unit tests for Layer 0 Operational Recovery, Reconciliation & Legacy Quarantine."""
from datetime import datetime, timezone
import pytest

from services.agribrain.layer0.operational_reconciliation import (
    OperationalReconciliationError,
    audit_staged_assessments,
    migrate_legacy_receipt_evidence_fingerprint,
    quarantine_legacy_receipts,
    reconcile_staged_assessment,
    scan_unfingerprinted_legacy_receipts,
)

UTC = timezone.utc


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


def test_audit_staged_assessments_categorization():
    db = MockDatabase()
    db["Layer0ScientificAssessment"].docs = {
        "a1": {"_id": "a1", "assessment_id": "a1", "tenant_id": "t1", "plot_id": "p1", "status": "STAGED"},
        "a2": {"_id": "a2", "assessment_id": "a2", "tenant_id": "t2", "plot_id": "p2", "status": "STAGED"},
    }
    # a1 has stranded staged receipt, a2 has clean (no receipt)
    db["Layer0IrrigationReceiptConsumption"].docs = {
        "r1": {"_id": "r1", "tenant_id": "t1", "plot_id": "p1", "status": "STAGED"},
    }
    
    reports = audit_staged_assessments(db)
    assert len(reports) == 2
    r_map = {r.assessment_id: r for r in reports}
    assert r_map["a1"].disposition == "STRANDED_UNCOMMITTED_RESERVATIONS"
    assert r_map["a2"].disposition == "CLEAN_STAGED_NO_RESERVATIONS"


def test_reconcile_abort_and_rollback():
    db = MockDatabase()
    db["Layer0ScientificAssessment"].docs = {
        "a1": {"_id": "a1", "assessment_id": "a1", "tenant_id": "t1", "plot_id": "p1", "status": "STAGED"},
    }
    db["Layer0IrrigationReceiptConsumption"].docs = {
        "r1": {"_id": "r1", "tenant_id": "t1", "plot_id": "p1", "status": "STAGED"},
    }
    
    res = reconcile_staged_assessment(
        db, "a1", "ABORT_AND_ROLLBACK",
        operator_principal="ops-sec-lead",
        rationale="Timeout during upstream satellite acquisition, aborting safely",
    )
    assert res["status"] == "ABORTED"
    assert res["reservations_rolled_back"] == 1
    
    # Check Mongo updates
    assert db["Layer0ScientificAssessment"].docs["a1"]["status"] == "ABORTED"
    assert db["Layer0IrrigationReceiptConsumption"].docs["r1"]["status"] == "ROLLED_BACK"


def test_reconcile_requires_operator_and_rationale():
    db = MockDatabase()
    with pytest.raises(OperationalReconciliationError, match="operator_principal_required"):
        reconcile_staged_assessment(db, "a1", "ABORT_AND_ROLLBACK", operator_principal="", rationale="valid rationale here")
    with pytest.raises(OperationalReconciliationError, match="valid_rationale_min_10_chars_required"):
        reconcile_staged_assessment(db, "a1", "ABORT_AND_ROLLBACK", operator_principal="lead", rationale="short")


def test_scan_and_quarantine_legacy_unfingerprinted_receipts():
    db = MockDatabase()
    db["Layer0IrrigationReceiptConsumption"].docs = {
        "r_legacy1": {"_id": "r_legacy1", "tenant_id": "t1", "plot_id": "p1", "status": "COMMITTED"},
        "r_legacy2": {"_id": "r_legacy2", "tenant_id": "t1", "plot_id": "p1", "evidence_fingerprint": None},
        "r_modern": {"_id": "r_modern", "tenant_id": "t1", "plot_id": "p1", "evidence_fingerprint": "abc123def"},
    }
    
    unfingerprinted = scan_unfingerprinted_legacy_receipts(db)
    assert len(unfingerprinted) == 2
    
    quarantine_res = quarantine_legacy_receipts(
        db, operator_principal="data-eng-lead", rationale="Pre-B2B08 unmigrated legacy receipt quarantine",
    )
    assert quarantine_res["quarantined_count"] == 2
    assert db["Layer0IrrigationReceiptConsumption"].docs["r_legacy1"]["quarantine_status"] == "QUARANTINED"
    assert "quarantine_status" not in db["Layer0IrrigationReceiptConsumption"].docs["r_modern"]


def test_migrate_legacy_receipt_evidence_fingerprint():
    db = MockDatabase()
    db["Layer0IrrigationReceiptConsumption"].docs = {
        "r_leg": {
            "_id": "r_leg", "tenant_id": "t1", "plot_id": "p1",
            "zone_id": "plot", "geometry_hash": "hash1", "geometry_version": 2,
            "status": "COMMITTED",
        }
    }
    
    res = migrate_legacy_receipt_evidence_fingerprint(
        db, "r_leg",
        source_evidence_cas_root="cas://meter-snapshot-001",
        delivery_interval=("2026-05-01T12:00:00Z", "2026-05-01T14:00:00Z"),
        operator_principal="migration-runner",
        rationale="Authoritative physical flow-meter CSV hash verified from field gateway",
    )
    assert res["migration_status"] == "MIGRATED"
    assert len(res["evidence_fingerprint"]) == 64
    
    rec = db["Layer0IrrigationReceiptConsumption"].docs["r_leg"]
    assert rec["evidence_fingerprint"] == res["evidence_fingerprint"]
    assert rec["migration_status"] == "MIGRATED"
