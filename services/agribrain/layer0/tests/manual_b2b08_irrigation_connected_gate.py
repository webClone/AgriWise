"""B2B-08 irrigation integration: ONE connected four-defect acceptance gate.

Explicit opt-in, not collected by ordinary pytest test_*.py discovery.
Run against a dedicated local MongoDB replica set with:
    AKALORIS_B07_MONGO_TEST_URI=mongodb://127.0.0.1:27018/?replicaSet=rs0
    py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_irrigation_connected_gate.py

The gate creates and destroys exactly one randomly named test database.
Use only an isolated test cluster; never point at production.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import os
import uuid

import pytest
from pymongo import MongoClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationAuthority, DurableRevocationSnapshot,
)
from services.agribrain.layer0.kalman_engine import ZoneKalmanFilter
from services.agribrain.layer0.mongo_irrigation_idempotency import (
    MongoIrrigationIdempotencyStore,
)
from services.agribrain.layer0.production_admission import (
    configure_server_delivery_verifier,
)
from services.agribrain.layer0.state_vector import IDX_SM_0_10, ProcessModel
from services.agribrain.layer0.v3_kms_signed_issuer import KmsPublicKeyRegistry
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_DOMAIN, VERIFIED_IRRIGATION_PURPOSE,
    VerifiedDeliveredIrrigationSigner, VerifiedDeliveredIrrigationVerifier,
)

UTC = timezone.utc
WEATHER = {"temp_min": 10.0, "temp_max": 20.0, "precipitation": 0.0, "et0": 3.0}


def _iso(stamp):
    return stamp.isoformat().replace("+00:00", "Z")


def _grant(*, day, now, plot, receipt_id, replay_id, evidence,
           start_hour=12, end_hour=14, volume=1000.0,
           issued_at=None, expires_at=None):
    t0 = datetime.combine(day, time(start_hour, 0), tzinfo=UTC)
    t1 = datetime.combine(day, time(end_hour, 0), tzinfo=UTC)
    issued = issued_at or t1 + timedelta(minutes=5)
    expires = expires_at or now + timedelta(days=2)
    return {
        "domain": VERIFIED_IRRIGATION_DOMAIN,
        "version": "v3",
        "algorithm": "Ed25519",
        "key_id": "b08-integration-key",
        "issuer_id": "b08-integration-l3",
        "purpose": VERIFIED_IRRIGATION_PURPOSE,
        "receipt_id": receipt_id,
        "tenant_id": "isolated-b08-tenant",
        "plot_id": plot,
        "geometry_hash": "isolated-b08-geometry",
        "geometry_version": 1,
        "zone_id": "plot",
        "delivery_start": _iso(t0),
        "delivery_end": _iso(t1),
        "delivered_volume_liters": volume,
        "wetted_area_m2": 100.0,
        "delivery_efficiency_fraction": 0.9,
        "net_infiltrated_depth_mm": volume * 0.9 / 100.0,
        "conversion_calibration_id": "calibrated-meter-fixture-v1",
        "depth_uncertainty_sigma_mm": 0.5,
        "source_evidence_cas_root": evidence,
        "replay_idempotency_key": replay_id,
        "revocation_revision_anchor": 0,
        "issued_at": _iso(issued),
        "expires_at": _iso(expires),
    }


def _event(receipt, *, event_id, plot, timestamp):
    return {
        "payload": {
            "event_type": "irrigation", "event_role": "VERIFIED_DELIVERY",
            "event_id": event_id, "verified_receipt": receipt.to_dict(),
            "zone_id": "plot",
        },
        "plot_id": plot,
        "geometry_hash": "isolated-b08-geometry",
        "timestamp": timestamp,
        "packet_id": "pkt-" + event_id,
    }


def _filter(verifier, plot, day, cutoff, *, same_day_prior=False):
    engine = ZoneKalmanFilter("plot")
    engine.initialize(day.isoformat() if same_day_prior else (
        day - timedelta(days=1)).isoformat())
    engine.tenant_id = "isolated-b08-tenant"
    engine.parent_plot_id = plot
    engine.geometry_version = 1
    engine.expected_geometry_hash = "isolated-b08-geometry"
    engine.delivery_verifier = verifier
    engine.evidence_cutoff = cutoff
    return engine


def test_connected_cutoff_revocation_retry_evidence_and_restart_recovery(monkeypatch):
    uri = os.environ.get("AKALORIS_B07_MONGO_TEST_URI", "").strip()
    if not uri:
        pytest.fail("explicit AKALORIS_B07_MONGO_TEST_URI is required")
    now = datetime.now(UTC)
    day = (now - timedelta(days=1)).date()
    cutoff = now
    name = "akaloris_b2b08_irrigation_" + uuid.uuid4().hex
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    try:
        database = client[name]
        hello = database.command("hello")
        assert hello.get("setName") or hello.get("msg") == "isdbgrid"
        private = Ed25519PrivateKey.generate()
        registry = KmsPublicKeyRegistry()
        registry.register_public_key(
            key_id="b08-integration-key",
            issuer_id="b08-integration-l3",
            source="sensor_iot",
            algorithm="Ed25519",
            public_key_pem_or_bytes=private.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw,
            ),
            valid_from=now - timedelta(days=5),
            valid_until=now + timedelta(days=5),
        )
        signer = VerifiedDeliveredIrrigationSigner(
            key_id="b08-integration-key",
            issuer_id="b08-integration-l3",
            algorithm="Ed25519",
            private_key=private,
        )
        snapshot = DurableRevocationSnapshot(
            revision=0, issued_at=now - timedelta(seconds=10),
            expires_at=now + timedelta(days=1),
            key_statuses={"b08-integration-key": "active"},
        )
        authority = DurableRevocationAuthority(
            snapshot, max_snapshot_age_seconds=300,
        )
        verifier = configure_server_delivery_verifier(
            database=database, public_key_registry=registry,
            revocation_authority=authority,
        )

        def signed(plot, ident, replay, evidence, **kwargs):
            return signer.sign(_grant(
                day=day, now=now, plot=plot,
                receipt_id=ident, replay_id=replay, evidence=evidence,
                **kwargs,
            ))

        def admit(receipt, plot="plot-a", cutoff_time=cutoff, which=verifier):
            return which.verify_and_admit(
                receipt, expected_day=day.isoformat(),
                expected_plot_id=plot, expected_zone_id="plot",
                expected_geometry_hash="isolated-b08-geometry",
                expected_geometry_version=1,
                expected_tenant_id="isolated-b08-tenant",
                cutoff=cutoff_time,
            )

        # 1. Issue-time and expiry are checked against assessment; revocation
        # snapshot age is checked at live authorization time, not delivery day.
        late_receipt = signed("plot-a", "late-issue", "late-replay", "late-evidence")
        late_cutoff = datetime.combine(day, time(14, 2), tzinfo=UTC)
        with pytest.raises(ValueError, match="receipt_issued_after_assessment_cutoff"):
            admit(late_receipt, cutoff_time=late_cutoff)
        expired = signed(
            "plot-a", "expired", "expired-replay", "expired-evidence",
            expires_at=now - timedelta(seconds=1),
        )
        with pytest.raises(ValueError, match="receipt_expired"):
            admit(expired)
        stale = DurableRevocationAuthority(
            DurableRevocationSnapshot(
                revision=0,
                issued_at=now - timedelta(hours=2),
                expires_at=now + timedelta(days=1),
                key_statuses={"b08-integration-key": "active"},
            ), max_snapshot_age_seconds=30,
        )
        stale_verifier = VerifiedDeliveredIrrigationVerifier(
            registry, stale,
            MongoIrrigationIdempotencyStore(database),
        )
        with pytest.raises(ValueError, match="stale_revocation_snapshot"):
            admit(late_receipt, which=stale_verifier)
        assert database["Layer0IrrigationReceiptConsumption"].count_documents({}) == 0

        # 2. One accepted delivery changes water. Its source evidence cannot
        # be re-issued as an additional physical quantity using new IDs.
        receipt = signed("plot-a", "delivery-a1", "replay-a1", "meter-source-a")
        t_end = datetime.combine(day, time(14, 0), tzinfo=UTC)
        first = _filter(verifier, "plot-a", day, cutoff)
        baseline = _filter(None, "plot-control", day, cutoff)
        baseline.step(day.isoformat(), WEATHER)
        value_before = baseline.state.values[IDX_SM_0_10]
        actual = first.step(day.isoformat(), WEATHER, None, [
            _event(receipt, event_id="event-a1", plot="plot-a", timestamp=t_end),
        ])
        first_value = first.state.values[IDX_SM_0_10]
        assert first_value > value_before
        assert actual["physical_management_events_applied"] == 1

        duplicate = signed("plot-a", "delivery-a2", "replay-a2", "meter-source-a")
        with pytest.raises(ValueError, match="duplicate_receipt_or_replay_key"):
            admit(duplicate)
        assert database["Layer0IrrigationReceiptConsumption"].count_documents({
            "status": "COMMITTED", "plot_id": "plot-a",
        }) == 1

        # 3. A fresh worker must recover original water balance, not return
        # a silently downgraded plain estimate from duplicate event rejection.
        verifier2 = configure_server_delivery_verifier(
            database=database, public_key_registry=registry,
            revocation_authority=authority,
        )
        cold = _filter(verifier2, "plot-a", day, cutoff)
        recovered = cold.step(day.isoformat(), WEATHER, None, [
            _event(receipt, event_id="event-a1-retry", plot="plot-a", timestamp=t_end),
        ])
        assert recovered["recovered_from_durable_l3_commit"] is True
        assert recovered["physical_management_events_applied"] == 0
        assert cold.state.values[IDX_SM_0_10] == pytest.approx(first_value, abs=1e-12)

        # 4. Preflight zero-duration failure must leave no staged receipt;
        # a correctly initialized retry of identical signed evidence works.
        retry = signed("plot-retry", "delivery-retry", "replay-retry", "meter-retry")
        invalid = _filter(verifier, "plot-retry", day, cutoff, same_day_prior=True)
        with pytest.raises(ValueError, match="temporal gap"):
            invalid.step(day.isoformat(), WEATHER, None, [
                _event(retry, event_id="retry-invalid", plot="plot-retry", timestamp=t_end),
            ])
        assert database["Layer0IrrigationReceiptConsumption"].find_one({
            "_id": "delivery-retry",
        }) is None
        retry_filter = _filter(verifier, "plot-retry", day, cutoff)
        success = retry_filter.step(day.isoformat(), WEATHER, None, [
            _event(retry, event_id="retry-valid", plot="plot-retry", timestamp=t_end),
        ])
        assert success["physical_management_events_applied"] == 1

        # Positive control: two genuinely distinct physical deliveries with
        # different evidence roots/intervals contribute independently.
        both = _filter(verifier, "plot-positive", day, cutoff)
        pos1 = signed(
            "plot-positive", "pos-1", "pos-replay-1", "meter-positive-1",
            start_hour=11, end_hour=12, volume=300.0,
        )
        pos2 = signed(
            "plot-positive", "pos-2", "pos-replay-2", "meter-positive-2",
            start_hour=13, end_hour=14, volume=500.0,
        )
        positive = both.step(day.isoformat(), WEATHER, None, [
            _event(pos1, event_id="pos-event-1", plot="plot-positive",
                   timestamp=datetime.combine(day, time(12, 0), tzinfo=UTC)),
            _event(pos2, event_id="pos-event-2", plot="plot-positive",
                   timestamp=t_end),
        ])
        assert positive["physical_management_events_applied"] == 2
        assert database["Layer0IrrigationReceiptConsumption"].count_documents({
            "status": "COMMITTED", "plot_id": "plot-positive",
        }) == 2
        assert both.state.values[IDX_SM_0_10] > value_before

        # 5. Revocation AFTER numerical prediction and BEFORE journal write
        # must abort without state publication or physical receipt consumption.
        revoked_receipt = signed(
            "plot-revoked", "pos-revoked", "pos-revoked-replay", "meter-revoked",
        )
        prior = _filter(verifier, "plot-revoked", day, cutoff)
        original_values = list(prior.state.values)
        original_predict = ProcessModel.predict
        fired = {"value": False}

        def trigger_revocation(model, *args, **kwargs):
            if not fired["value"]:
                fired["value"] = True
                rev = DurableRevocationSnapshot(
                    revision=1, issued_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                    key_statuses={"b08-integration-key": "active"},
                    revoked_plots=("plot-revoked",),
                    previous_digest=authority.current_snapshot.snapshot_digest,
                )
                authority.load_snapshot(rev)
            return original_predict(model, *args, **kwargs)

        with monkeypatch.context() as scoped:
            scoped.setattr(ProcessModel, "predict", trigger_revocation)
            with pytest.raises(ValueError, match="plot_scope_revoked"):
                prior.step(day.isoformat(), WEATHER, None, [
                    _event(revoked_receipt, event_id="revoked-event",
                           plot="plot-revoked", timestamp=t_end),
                ])
        assert fired["value"]
        assert prior.state.values == original_values
        assert prior.state.day == (day - timedelta(days=1)).isoformat()
        assert database["Layer0IrrigationReceiptConsumption"].find_one({
            "_id": "pos-revoked",
        }) is None
        assert database["Layer0IrrigationCommittedState"].count_documents({
            "plot_id": "plot-revoked",
        }) == 0
    finally:
        # Never use this against production; drop ONLY the unique test DB.
        if name.startswith("akaloris_b2b08_irrigation_"):
            client.drop_database(name)
        client.close()
