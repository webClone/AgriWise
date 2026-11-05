"""Targeted B2B-08B cross-journal scientific lineage tests."""
from copy import deepcopy
import pytest
from services.agribrain.app.scientific_commit_lineage import (
    ScientificCommitLineageError, attest_delivery_commit_lineage,
)
from services.agribrain.layer0.mongo_irrigation_idempotency import _scope_state_id

SCOPE = {"tenant_id": "t1", "plot_id": "p1", "zone_id": "plot",
         "geometry_hash": "gh1", "geometry_version": 2, "day": "2026-11-05"}


class Collection:
    def __init__(self, docs):
        self.docs = docs
    def find_one(self, query):
        return next((deepcopy(x) for x in self.docs
                     if all(x.get(k) == v for k, v in query.items())), None)


class Database:
    def __init__(self, receipts=("r1",)):
        snapshot_id = _scope_state_id(SCOPE)
        self.tables = {
            "Layer0IrrigationCommittedState": Collection([{
                "_id": snapshot_id, **SCOPE,
                "state": {"day": SCOPE["day"], "values": [0.3]},
                "receipt_ids": list(receipts),
            }]),
            "Layer0IrrigationReceiptConsumption": Collection([{
                "_id": r, **SCOPE, "status": "COMMITTED",
                "state_snapshot_id": snapshot_id,
                "evidence_fingerprint": "fingerprint-" + r,
            } for r in receipts]),
        }
    def __getitem__(self, key):
        return self.tables[key]


def provenance(ids=("r1",), applied=1, recovered=False, status="APPLIED"):
    return [{"day": SCOPE["day"], "zones": {"plot": {"provenance": {
        "verified_delivery_receipts": list(ids),
        "physical_management_events_applied": applied,
        "recovered_from_durable_l3_commit": recovered,
        "event_forcing_status": status,
    }}}}]


def attest(db, records):
    return attest_delivery_commit_lineage(
        db, tenant_id="t1", plot_id="p1",
        geometry_hash="gh1", geometry_version=2, provenance_log=records,
    )


def test_no_irrigation_has_no_durable_lookup():
    class NoRead:
        def __getitem__(self, key):
            raise AssertionError(key)
    assert attest(NoRead(), provenance((), 0, False, "DEFERRED_UNTIL_TRUSTED_L3_SUPPORT")) == []


def test_applied_receipt_attested_to_exact_snapshot():
    links = attest(Database(), provenance())
    assert links[0]["state_snapshot_id"] == _scope_state_id(SCOPE)
    assert links[0]["receipt_ids"] == ["r1"]
    assert links[0]["evidence_fingerprints"] == ["fingerprint-r1"]


def test_cold_recovery_is_read_only():
    links = attest(Database(), provenance(
        applied=0, recovered=True, status="RECOVERED_COMMITTED_CHECKPOINT"
    ))
    assert links[0]["recovered_from_durable_l3_commit"] is True


def test_two_independent_deliveries_one_transaction():
    links = attest(Database(("r1", "r2")), provenance(("r1", "r2"), 2))
    assert links[0]["receipt_ids"] == ["r1", "r2"]


@pytest.mark.parametrize("failure", ["missing_state", "foreign_tenant",
                                      "receipt_mismatch", "legacy_receipt"])
def test_unverifiable_commits_fail_closed(failure):
    db = Database()
    if failure == "missing_state":
        db.tables["Layer0IrrigationCommittedState"].docs.clear()
    elif failure == "foreign_tenant":
        db.tables["Layer0IrrigationCommittedState"].docs[0]["tenant_id"] = "foreign"
    elif failure == "receipt_mismatch":
        db.tables["Layer0IrrigationCommittedState"].docs[0]["receipt_ids"] = ["other"]
    else:
        db.tables["Layer0IrrigationReceiptConsumption"].docs[0].pop("evidence_fingerprint")
    with pytest.raises(ScientificCommitLineageError):
        attest(db, provenance())


@pytest.mark.parametrize("bad", [
    provenance(applied=0), provenance(applied=2),
    provenance((), 1), provenance(("r1", "r1"), 2),
    provenance(applied=1, recovered=True, status="RECOVERED_COMMITTED_CHECKPOINT"),
    provenance(applied=0, recovered=True, status="APPLIED"),
])
def test_inconsistent_claims_fail_closed(bad):
    with pytest.raises(ScientificCommitLineageError):
        attest(Database(), bad)


def test_duplicate_day_or_missing_provenance_fails_closed():
    for records in (None, provenance() + provenance()):
        with pytest.raises(ScientificCommitLineageError):
            attest(Database(), records)
