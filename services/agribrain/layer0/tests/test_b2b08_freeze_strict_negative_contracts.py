"""B2B-08-F4: negative contracts for the former production bypasses."""
from datetime import datetime, timezone

import pytest

from services.agribrain.layer0.production_admission import (
    Layer0AdmissionRequiredError, configure_server_delivery_verifier,
)
from services.agribrain.layer0.operational_reconciliation import (
    OperationalReconciliationError,
    compute_operator_authorization_signature,
    get_trusted_reconciliation_secret,
    migrate_legacy_receipt_evidence_fingerprint,
    reconcile_staged_assessment,
)


def test_factory_rejects_explicit_false_before_provisioning():
    with pytest.raises(Layer0AdmissionRequiredError, match="transactional_revocation_required_in_production"):
        configure_server_delivery_verifier(
            database=None, public_key_registry=None, revocation_authority=None,
            require_transactional_revocation=False,
        )


def test_operator_secret_cannot_be_supplied_by_caller_without_server_root(monkeypatch):
    monkeypatch.delenv("AKALORIS_RECONCILIATION_HMAC_SECRET", raising=False)
    with pytest.raises(OperationalReconciliationError, match="unconfigured_reconciliation_authority_secret"):
        get_trusted_reconciliation_secret("self-signed-secret")


def _reconcile(db, monkeypatch):
    secret = "independent-operator-server-secret"
    monkeypatch.setenv("AKALORIS_RECONCILIATION_HMAC_SECRET", secret)
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat().replace("+00:00", "Z")
    signature = compute_operator_authorization_signature(
        "operator-1", "ABORT_AND_ROLLBACK", "assessment-1",
        timestamp, secret,
    )
    return reconcile_staged_assessment(
        db, "assessment-1", "ABORT_AND_ROLLBACK",
        operator_principal="operator-1",
        rationale="Conservative reconciliation of a signed staged claim",
        authorization_signature=signature, authorization_timestamp=timestamp,
        now=now,
    )


class _AssessmentCollection:
    def __init__(self, receipt_ids=()):
        self.receipt_ids = list(receipt_ids)
    def find_one(self, _query, **_kwargs):
        return {
            "_id": "claim-1", "assessment_id": "assessment-1",
            "tenant_id": "t", "plot_id": "p", "geometry_hash": "geom",
            "geometry_version": 2, "status": "STAGED",
            "claim_nonce": "nonce-1",
            "submitted_receipt_ids": self.receipt_ids,
            "submitted_receipt_digests": {r: "digest-"+r for r in self.receipt_ids},
            "assessment_start_date": "2026-05-01",
            "assessment_end_date": "2026-05-01",
        }


def test_reconciliation_denies_absent_transaction_even_with_zero_receipts(monkeypatch):
    class NoSessionDatabase:
        client = None
        def __getitem__(self, key):
            return _AssessmentCollection()
    with pytest.raises(OperationalReconciliationError, match="transactional_mongodb_required"):
        _reconcile(NoSessionDatabase(), monkeypatch)


def test_reconciliation_denies_receipt_claimed_by_different_assessment(monkeypatch):
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def start_transaction(self): return self
    class Client:
        def start_session(self): return Session()
    class ReceiptCollection:
        def find_one(self, query, **kwargs):
            return {
                "_id": "receipt-1", "tenant_id": "t", "plot_id": "p",
                "geometry_hash": "geom", "geometry_version": 2,
                "assessment_claim_id": "another-assessment",
                "grant_digest": "digest-receipt-1", "day": "2026-05-01",
            }
        def update_many(self, *_args, **_kwargs):
            pytest.fail("foreign receipt must never be rolled back")
    class DB:
        client = Client()
        def __getitem__(self, key):
            if key == "Layer0ScientificAssessment":
                return _AssessmentCollection(["receipt-1"])
            return ReceiptCollection()
    with pytest.raises(OperationalReconciliationError, match="receipt_not_bound_to_assessment"):
        _reconcile(DB(), monkeypatch)


def test_legacy_evidence_cannot_migrate_without_independent_authenticator():
    class Receipts:
        def find_one(self, query):
            return {
                "_id": "legacy-1", "tenant_id": "t", "plot_id": "p",
                "zone_id": "plot", "geometry_hash": "geom",
                "geometry_version": 2,
                "source_evidence_cas_root": "a" * 64,
                "delivery_start": "2026-05-01T12:00:00Z",
                "delivery_end": "2026-05-01T14:00:00Z",
            }
        def update_one(self, *_args, **_kwargs):
            pytest.fail("unverified migration attempted database mutation")
    class DB:
        def __getitem__(self, key): return Receipts()
    with pytest.raises(OperationalReconciliationError, match="historical_evidence_authenticator_required"):
        migrate_legacy_receipt_evidence_fingerprint(
            DB(), "legacy-1", source_evidence_cas_root="a" * 64,
            delivery_interval=("2026-05-01T12:00:00Z", "2026-05-01T14:00:00Z"),
            operator_principal="operator-1",
            rationale="No independent source evidence verification available",
        )
