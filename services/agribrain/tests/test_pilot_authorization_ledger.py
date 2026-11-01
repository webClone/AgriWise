"""Phase 1E-A quarantine registry and revocation regression tests.

Fixtures deliberately patch the trusted reader and do not exercise any real
farm authorization. All positive-looking records remain QUARANTINED.
"""
from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.orchestrator_v2.pilot_authorization_ledger import (
    PilotCandidateLedger, SCHEMA_VERSION,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.tests.test_pilot_prescription_authorization_v2 import (
    v2, head, digest,
)

NOW = "2026-11-01T15:00:00Z"
LATE = "2026-11-02T18:20:00Z"
NS = PlotNamespace("tenant-a", "farm-a", "6ab14f59ad442f274c3f2a62")
KEY = b"32-byte-minimum-non-production-test-key-EXPLICIT"


def trusted():
    publication = head()
    publication["proof_attestation_valid"] = True
    publication["proof_attestation_hash"] = digest("signed-attestation")
    publication["admitted_evidence_root_hash"] = digest("physical-admission")
    publication["bounded_uncertainty_receipt_hash"] = v2().uncertainty_receipt_hash
    publication["scientific_posterior_hash"] = digest("posterior")
    publication["proof_attestation"] = {
        "admitted_evidence_root_hash": publication["admitted_evidence_root_hash"],
        "bounded_uncertainty_receipt_hash": publication["bounded_uncertainty_receipt_hash"],
        "scientific_posterior_hash": publication["scientific_posterior_hash"],
    }
    return publication


def ledger(tmp_path, key=KEY, key_id="pilot-test-v1"):
    return PilotCandidateLedger(tmp_path / "durable" / "ledger.sqlite", key_id=key_id, signing_key=key)


def register(store, *, publication=None, envelope=None):
    candidate = envelope if envelope is not None else v2()
    current = trusted() if publication is None else publication
    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=current,
    ) as reader:
        record = store.register_quarantined_candidate(
            namespace=NS, geometry_hash=candidate.geometry_hash,
            crop_cycle_id=candidate.crop_cycle_id,
            envelope=candidate, now=NOW,
        )
        reader.assert_called_once_with(
            NS, expected_snapshot_id=candidate.snapshot_id,
            expected_geometry_hash=candidate.geometry_hash,
            expected_crop_cycle_id=candidate.crop_cycle_id,
            require_proof_attestation=True,
        )
    return record


def inspect(store, record_id, *, publication=None, now=NOW, namespace=NS):
    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=trusted() if publication is None else publication,
    ):
        return store.inspect_candidate(record_id, now=now, namespace=namespace)


def test_quarantine_record_is_signed_stored_reopened_and_never_exportable(tmp_path):
    s = ledger(tmp_path)
    record = register(s)
    assert record["schema_version"] == SCHEMA_VERSION
    assert record["state"] == "QUARANTINED"
    assert record["hmac"] and len(record["hmac"]) == 64
    reopened = ledger(tmp_path)
    metadata = inspect(reopened, record["candidate_id"])
    assert metadata["state"] == "QUARANTINED"
    assert metadata["valid_export_authorization"] is False
    assert metadata["authorized_actions"] == []
    with pytest.raises(ContractViolation, match="quarantined"):
        reopened.authorize_export(record["candidate_id"])


def test_durable_revocation_survives_reopen_and_cannot_be_undone(tmp_path):
    s = ledger(tmp_path)
    id_ = register(s)["candidate_id"]
    s.revoke(id_, reason="sensor drift alert", at=NOW)
    s.revoke(id_, reason="cannot undo", at=NOW)
    with pytest.raises(ContractViolation, match="revoked"):
        inspect(ledger(tmp_path), id_)
    with sqlite3.connect(s.path) as conn:
        reasons = conn.execute(
            "SELECT reason FROM revocations WHERE candidate_id=?", (id_,)
        ).fetchall()
    assert reasons == [("sensor drift alert",)]


def test_registry_denies_unsigned_or_missing_records(tmp_path):
    s = ledger(tmp_path)
    with pytest.raises(ContractViolation, match="Unknown or unavailable"):
        inspect(s, "unknown")
    with pytest.raises(ContractViolation, match="unknown"):
        s.revoke("unknown", reason="test", at=NOW)
    with pytest.raises(ContractViolation, match="32-byte"):
        ledger(tmp_path / "bad", key=b"short")
    with pytest.raises(ContractViolation, match="32-byte"):
        ledger(tmp_path / "bad2", key=b"")


def test_registry_detects_tampered_signed_json(tmp_path):
    s = ledger(tmp_path)
    row = register(s)
    with sqlite3.connect(s.path) as conn:
        current = conn.execute(
            "SELECT record_json FROM candidates WHERE candidate_id=?",
            (row["candidate_id"],),
        ).fetchone()[0]
        data = json.loads(current)
        data["snapshot_id"] = "ASMAE-SNAPSHOT-foreign"
        conn.execute(
            "UPDATE candidates SET record_json=? WHERE candidate_id=?",
            (json.dumps(data), row["candidate_id"]),
        )
    with pytest.raises(ContractViolation, match="integrity or signature"):
        inspect(s, row["candidate_id"])


def test_candidate_denied_after_signing_key_rotation(tmp_path):
    s = ledger(tmp_path)
    row = register(s)
    rotated = ledger(tmp_path, key_id="pilot-test-v2", key=b"other-explicit-rotation-key-material-32bytes")
    with pytest.raises(ContractViolation, match="key is unavailable or rotated"):
        inspect(rotated, row["candidate_id"])
    wrong_secret = ledger(tmp_path, key_id="pilot-test-v1", key=b"other-explicit-rotation-key-material-32bytes")
    with pytest.raises(ContractViolation, match="integrity or signature"):
        inspect(wrong_secret, row["candidate_id"])


def test_unattested_head_cannot_create_candidate(tmp_path):
    s = ledger(tmp_path)
    publication = trusted()
    publication["proof_attestation_valid"] = False
    with pytest.raises(ContractViolation, match="no authenticated proof attestation"):
        register(s, publication=publication)
    publication = trusted()
    publication["proof_attestation_hash"] = None
    with pytest.raises(ContractViolation):
        register(s, publication=publication)


def test_head_root_and_uncertainty_drift_blocks_candidate_registration(tmp_path):
    s = ledger(tmp_path)
    publication = trusted()
    publication["bounded_uncertainty_receipt_hash"] = digest("wrong-root")
    with pytest.raises(ContractViolation):
        register(s, publication=publication)
    publication = trusted()
    publication["admitted_evidence_root_hash"] = digest("wrong-membership")
    with pytest.raises(ContractViolation):
        register(s, publication=publication)


def test_current_publication_supersession_or_root_change_denies_inspection(tmp_path):
    s = ledger(tmp_path)
    row = register(s)
    current = trusted()
    current["snapshot_id"] = "ASMAE-SNAPSHOT-superseding"
    with pytest.raises(ContractViolation, match="no longer matches current publication"):
        inspect(s, row["candidate_id"], publication=current)
    current = trusted()
    current["bounded_uncertainty_receipt_hash"] = digest("revoked-uncertainty")
    with pytest.raises(ContractViolation, match="no longer matches current publication"):
        inspect(s, row["candidate_id"], publication=current)


def test_namespace_expiry_and_before_issuance_fail(tmp_path):
    s = ledger(tmp_path)
    row = register(s)
    with pytest.raises(ContractViolation, match="another namespace"):
        inspect(s, row["candidate_id"], namespace=PlotNamespace("foreign", "farm-a", NS.plot_id))
    with pytest.raises(ContractViolation, match="expired"):
        inspect(s, row["candidate_id"], now=LATE)
    with pytest.raises(ContractViolation, match="not yet valid"):
        inspect(s, row["candidate_id"], now="2026-11-01T14:59:59.999999Z")


def test_v1_cannot_be_registered_as_pilot_candidate(tmp_path):
    from services.agribrain.tests.test_pilot_prescription_authorization_v2 import common
    from services.agribrain.scientific_contracts.prescription_authorization import (
        PrescriptionAuthorizationEnvelopeV1,
    )
    s = ledger(tmp_path)
    with pytest.raises(ContractViolation, match="requires V2"):
        s.register_quarantined_candidate(
            namespace=NS,
            geometry_hash=v2().geometry_hash, crop_cycle_id=v2().crop_cycle_id,
            envelope=PrescriptionAuthorizationEnvelopeV1(**common()), now=NOW,
        )


def test_emergency_plot_scope_block_is_durable_and_denies_future_records(tmp_path):
    s = ledger(tmp_path)
    candidate = register(s)
    s.block_scope(NS, reason="unresolved calibration drift", at=NOW)
    s.block_scope(NS, reason="attempt to unblock by duplicate", at=NOW)
    reopened = ledger(tmp_path)
    with pytest.raises(ContractViolation, match="administratively blocked"):
        inspect(reopened, candidate["candidate_id"])
    with pytest.raises(ContractViolation, match="administratively blocked"):
        register(reopened)
    with sqlite3.connect(reopened.path) as conn:
        reason = conn.execute(
            "SELECT reason FROM scope_blocks WHERE tenant_id=? AND farm_id=? AND plot_id=?",
            (NS.tenant_id, NS.farm_id, NS.plot_id),
        ).fetchone()[0]
    assert reason == "unresolved calibration drift"
