"""B2B-08 post-freeze I01/I03 + two integration boundaries.

Explicit, destructive ONLY to a uniquely named test database on a
DEDICATED localhost:27018 rs0 instance. Never run against production.

PowerShell:
  $env:AKALORIS_B07_MONGO_TEST_URI="mongodb://127.0.0.1:27018/?replicaSet=rs0"
  py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_postfreeze_observation_only_connected_gate.py

Signed irrigation MUST remain disabled in the independent pilot. These
isolated test runtime signers do not authorize actuator dispatch.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from copy import deepcopy
import threading
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient
from pymongo import MongoClient

from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationAuthority, DurableRevocationSnapshot,
)
from services.agribrain.layer0.irrigation_checkpoint_inputs import (
    CheckpointInputConflict,
)
from services.agribrain.layer0.kalman_engine import ZoneKalmanFilter
from services.agribrain.layer0.production_admission import (
    configure_server_delivery_verifier,
)
from services.agribrain.layer0.v3_kms_signed_issuer import KmsPublicKeyRegistry
from services.agribrain.layer0.verified_irrigation_contract import (
    VerifiedDeliveredIrrigationSigner,
)
from services.agribrain.layer0.tests.manual_b2b08_irrigation_connected_gate import (
    WEATHER, _event, _filter, _grant,
)
from services.agribrain.layer0.tests.manual_b2b08_signed_http_connected_gate import (
    application, environment, seeded_prisma_plot,
)
from services.agribrain.layer0.tests.manual_b2b08_signed_http_connected_gate import (
    valid_isolated_uri, signed_assessment_payload, signed_post,
)
from services.agribrain.layer0.operational_reconciliation import (
    compute_operator_authorization_signature,
    reconcile_staged_assessment,
)

UTC = timezone.utc
PREFIX = "akaloris_b08_postfreeze_"


def test_postfreeze_connected_safety_and_positive_controls(monkeypatch, tmp_path):
    uri = valid_isolated_uri()
    db_name = PREFIX + uuid.uuid4().hex
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        db = client[db_name]
        assert db.command("hello").get("setName") == "rs0"
        now = datetime.now(UTC)
        day = (now - timedelta(days=1)).date()
        day_str = day.isoformat()
        event_at = datetime.combine(day, time(14), tzinfo=UTC)
        key = Ed25519PrivateKey.generate()
        registry = KmsPublicKeyRegistry()
        registry.register_public_key(
            key_id="b08-integration-key", issuer_id="b08-integration-l3",
            source="sensor_iot", algorithm="Ed25519",
            public_key_pem_or_bytes=key.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw,
            ),
            valid_from=now - timedelta(days=5),
            valid_until=now + timedelta(days=5),
        )
        authority = DurableRevocationAuthority(
            DurableRevocationSnapshot(
                revision=0,
                issued_at=now - timedelta(seconds=5),
                expires_at=now + timedelta(days=1),
                key_statuses={"b08-integration-key": "active"},
            ),
            max_snapshot_age_seconds=300,
        )
        signer = VerifiedDeliveredIrrigationSigner(
            key_id="b08-integration-key", issuer_id="b08-integration-l3",
            algorithm="Ed25519", private_key=key,
        )
        verifier = configure_server_delivery_verifier(
            database=db, public_key_registry=registry,
            revocation_authority=authority,
        )
        assert verifier.idempotency_store._require_transactional_revocation is True

        def signed(plot, rid, suffix):
            return signer.sign(_grant(
                day=day, now=now, plot=plot, receipt_id=rid,
                replay_id="replay-" + suffix,
                evidence="meter-cas-" + suffix,
            ))

        def event(receipt, plot, suffix):
            return _event(
                receipt, event_id="event-" + suffix, plot=plot,
                timestamp=event_at,
            )

        # POSITIVE: two different source evidence records on a fresh plot
        # produce TWO genuine L3 applications and one durable snapshot.
        plot_two = "plot-two-positive"
        events_two = [
            event(signed(plot_two, "two-receipt-1", "two-1"), plot_two, "two-1"),
            event(signed(plot_two, "two-receipt-2", "two-2"), plot_two, "two-2"),
        ]
        first = _filter(verifier, plot_two, day, now)
        applied = first.step(day_str, WEATHER, events=events_two)
        assert applied["physical_management_events_applied"] == 2
        original_state = list(first.state.values)
        original_receipts = db["Layer0IrrigationReceiptConsumption"].count_documents({
            "plot_id": plot_two, "status": "COMMITTED",
        })
        assert original_receipts == 2
        assert db["Layer0IrrigationCommittedState"].count_documents({
            "plot_id": plot_two,
        }) == 1

        # POSITIVE: exact cold inputs must preserve the real committed water
        # without staging or applying any of the receipts a second time.
        cold_exact = _filter(verifier, plot_two, day, now)
        recovered = cold_exact.step(day_str, dict(WEATHER), events=events_two)
        assert recovered["recovered_from_durable_l3_commit"] is True
        assert recovered["physical_management_events_applied"] == 0
        assert cold_exact.state.values == original_state
        assert db["Layer0IrrigationReceiptConsumption"].count_documents({
            "plot_id": plot_two, "status": "COMMITTED",
        }) == original_receipts

        # NEGATIVE I03: a fresh signed second delivery and changed rainfall
        # cannot reuse yesterday's checkpoint for the same scope/day.
        plot_conflict = "plot-changed-input"
        first_delivery = event(
            signed(plot_conflict, "conflict-receipt-1", "conflict-1"),
            plot_conflict, "conflict-1",
        )
        added_delivery = event(
            signed(plot_conflict, "conflict-receipt-2", "conflict-2"),
            plot_conflict, "conflict-2",
        )
        first_filter = _filter(verifier, plot_conflict, day, now)
        first_filter.step(day_str, WEATHER, events=[first_delivery])
        old_state = list(first_filter.state.values)
        weather_changed = dict(WEATHER, precipitation=20.0)

        for wx, evs in [
            (weather_changed, [first_delivery]),
            (WEATHER, [first_delivery, added_delivery]),
            (weather_changed, [first_delivery, added_delivery]),
        ]:
            cold = _filter(verifier, plot_conflict, day, now)
            with pytest.raises(CheckpointInputConflict,
                               match="committed_irrigation_checkpoint_input_conflict"):
                cold.step(day_str, wx, events=evs)
            assert cold.state.values != old_state
        assert db["Layer0IrrigationReceiptConsumption"].count_documents({
            "_id": "conflict-receipt-2",
        }) == 0
        assert db["Layer0IrrigationReceiptConsumption"].count_documents({
            "plot_id": plot_conflict, "status": "COMMITTED",
        }) == 1

        # NEGATIVE I01: a genuine signature is not proof of a completed
        # physical interval if the attestation precedes delivery_end.
        premature = signer.sign(_grant(
            day=day, now=now, plot="plot-timing",
            receipt_id="premature-receipt", replay_id="premature-replay",
            evidence="premature-meter-record",
            issued_at=event_at - timedelta(hours=1),
        ))
        with pytest.raises(ValueError, match="receipt_attested_before_delivery_completion"):
            verifier.verify_and_admit(
                premature, expected_day=day_str,
                expected_plot_id="plot-timing", expected_zone_id="plot",
                expected_geometry_hash="isolated-b08-geometry",
                expected_geometry_version=1,
                expected_tenant_id="isolated-b08-tenant", cutoff=now,
            )
        assert db["Layer0IrrigationReceiptConsumption"].count_documents({
            "_id": "premature-receipt",
        }) == 0

        # NEGATIVE individual revocation race: the second party writes the
        # same receipt:<id> record while commit is in-flight. The receipt
        # fence must conflict and abort BOTH receipt and state publication.
        plot_race = "plot-receipt-revocation-race"
        raced = signed(plot_race, "raced-receipt-1", "race-1")
        res = verifier.idempotency_store.stage_reservation(raced.grant, day_str)
        assert db["Layer0RevocationLedger"].find_one({
            "_id": "receipt:raced-receipt-1",
        })["status"] == "active"
        snapshot = {
            "tenant_id": raced.grant.tenant_id,
            "plot_id": raced.grant.plot_id,
            "zone_id": raced.grant.zone_id,
            "geometry_hash": raced.grant.geometry_hash,
            "geometry_version": raced.grant.geometry_version,
            "day": day_str,
            "input_digest": "isolated-race-input",
            "state": {"day": day_str, "values": [0.0] * 9},
            "covariance": [[0.0] * 9 for _ in range(9)],
        }
        entered, revoked = threading.Event(), threading.Event()
        errors = []

        def pause_before_key_fence(session, key_id):
            entered.set()
            if not revoked.wait(5):
                raise TimeoutError("individual_revocation_writer_timed_out")

        verifier.idempotency_store._before_revocation_fence_hook = pause_before_key_fence
        def commit_in_thread():
            try:
                verifier.idempotency_store.commit_many([res], state_snapshot=snapshot)
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=commit_in_thread, daemon=True)
        worker.start()
        assert entered.wait(5), "did not reach transaction fence"
        db["Layer0RevocationLedger"].update_one(
            {"_id": "receipt:raced-receipt-1"},
            {"$set": {"status": "revoked", "revoked_at": now}},
        )
        revoked.set()
        worker.join(6)
        assert not worker.is_alive()
        assert len(errors) == 1
        assert "irrigation_state_commit_unconfirmed" in str(errors[0])
        assert (
            "WriteConflict" in str(errors[0].__cause__)
            or "receipt_revoked_or_missing_in_transaction" in str(errors[0].__cause__)
        )
        assert db["Layer0IrrigationCommittedState"].count_documents({
            "plot_id": plot_race,
        }) == 0
        assert db["Layer0IrrigationReceiptConsumption"].count_documents({
            "_id": "raced-receipt-1", "status": "COMMITTED",
        }) == 0
        verifier.idempotency_store._before_revocation_fence_hook = None

        # NEGATIVE crash boundary with POSITIVE operator recovery:
        # a valid REPORTED-labelled receipt is still the L3 receipt admitted
        # by the filter. Force failure just AFTER physical commit, before
        # final HTTP journal publication; the journal must have the same
        # receipt grant digest and permit exact operator reconciliation.
        source_signer, l3_signer, _, _ = environment(monkeypatch, now, tmp_path)
        identity = seeded_prisma_plot(db)
        body = signed_assessment_payload(db, identity, source_signer, l3_signer, now)
        body["packets"][1]["payload"]["event_role"] = "REPORTED"
        from app import mongo_client as mongo_module
        monkeypatch.setattr(mongo_module, "get_db", lambda: db)
        from services.agribrain.app import scientific_commit_lineage as lineage
        with TestClient(application(db)) as http:
            def interrupt_after_physical_commit(*_args, **_kwargs):
                raise RuntimeError("controlled_crash_after_scientific_commit")
            with monkeypatch.context() as m:
                m.setattr(lineage, "attest_delivery_commit_lineage",
                          interrupt_after_physical_commit)
                failed = signed_post(http, identity, body)
            assert failed.status_code == 503, failed.text

        journal = db["Layer0ScientificAssessment"].find_one({
            "assessment_id": body["assessment_id"],
        })
        assert journal is not None and journal["status"] == "STAGED"
        assert journal["submitted_receipt_ids"] == ["isolated-http-delivery-1"]
        consumed = db["Layer0IrrigationReceiptConsumption"].find_one({
            "_id": "isolated-http-delivery-1", "status": "COMMITTED",
        })
        assert consumed is not None
        assert consumed["assessment_claim_id"] == journal["_id"]
        assert consumed["grant_digest"] == journal[
            "submitted_receipt_digests"
        ]["isolated-http-delivery-1"]

        secret = "connected-operator-hmac-secret-for-exact-recovery"
        monkeypatch.setenv("AKALORIS_RECONCILIATION_HMAC_SECRET", secret)
        at = datetime.now(UTC)
        ts = at.isoformat().replace("+00:00", "Z")
        signature = compute_operator_authorization_signature(
            "isolated-operator", "COMPLETE_RECONCILED",
            body["assessment_id"], ts, secret,
        )
        completion = reconcile_staged_assessment(
            db, body["assessment_id"], "COMPLETE_RECONCILED",
            operator_principal="isolated-operator",
            rationale="Reconcile verified transaction after controlled crash",
            authorization_signature=signature,
            authorization_timestamp=ts, now=at,
        )
        assert completion["status"] == "COMMITTED"
        assert completion["result"]["verified_delivery_receipt_count"] == 1
        assert db["Layer0IrrigationReceiptConsumption"].count_documents({
            "_id": "isolated-http-delivery-1", "status": "COMMITTED",
        }) == 1
        assert db["Layer0ScientificAssessment"].find_one({
            "assessment_id": body["assessment_id"],
        })["result"]["scientific_publication_authorized"] is False

        # The HTTP surface must return an explicit 409 rather than silently
        # recycling a committed result for a new valid physical delivery.
        changed = deepcopy(body)
        changed["assessment_id"] = "isolated-assessment-changed-0002"
        more_event = deepcopy(body["packets"][1])
        more_event["payload"]["event_id"] = "isolated-meter-event-second"
        old_claim = more_event["payload"]["verified_receipt"]["grant"]
        new_claim = dict(old_claim)
        new_claim.update({
            "receipt_id": "isolated-http-delivery-second",
            "replay_idempotency_key": "isolated-l3-replay-second",
            "source_evidence_cas_root": "isolated-meter-record-second",
        })
        more_event["payload"]["verified_receipt"] = (
            l3_signer.sign(new_claim).to_dict()
        )
        changed["packets"].append(more_event)
        with TestClient(application(db)) as http:
            changed_response = signed_post(http, identity, changed)
            assert changed_response.status_code == 409, (
                changed_response.status_code, changed_response.text,
            )
            assert changed_response.json()["detail"] == (
                "committed_irrigation_checkpoint_input_conflict"
            )
        assert db["Layer0IrrigationReceiptConsumption"].count_documents({
            "_id": "isolated-http-delivery-second",
        }) == 0
    finally:
        if db_name.startswith(PREFIX):
            client.drop_database(db_name)
        client.close()
