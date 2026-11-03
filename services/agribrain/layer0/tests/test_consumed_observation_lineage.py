"""L0-LINEAGE-01: native signed input identity must equal consumed Kalman order.

All signatures are test fixtures. This proves no double-counting of a
transport retry and deterministic nonlinear update order, not calibration.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

import pytest

from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType, UncertaintyModel,
)
from services.agribrain.layer0.positive_observation_admission import (
    GRANT_DOMAIN, GRANT_PURPOSE, PositiveObservationAdmissionVerifier,
    _canonical_bytes, observation_packet_digest,
)
from services.agribrain.layer0.production_admission import Layer0AdmissionRequiredError
from services.agribrain.layer0.state_engine import Layer0StateEngine

KEY = b"L" * 32
STAMP = datetime(2026, 11, 3, 10, tzinfo=timezone.utc)
RUN = datetime(2026, 11, 3, 18, tzinfo=timezone.utc)


def _packet(value, *, version=1, decision=None):
    payload = {"ndvi_mean": value, "real_provider_product": True,
               "production_usable": True, "state_update_allowed": True}
    if decision is not None:
        payload["qualification_decision_id"] = decision
    return ObservationPacket(
        source=ObservationSource.SENTINEL2,
        obs_type=ObservationType.TABULAR, timestamp=STAMP,
        plot_id="plot-A", geometry_hash="geometry-A",
        geometry_version=version, spatial_scope="plot",
        payload=payload, uncertainty=UncertaintyModel(sigmas={"ndvi": 0.04}),
    )


def _grant(packet, *, version=1):
    grant = {
        "domain": GRANT_DOMAIN, "purpose": GRANT_PURPOSE,
        "key_id": "s2-key", "source": "sentinel2",
        "plot_id": "plot-A", "geometry_hash": "geometry-A",
        "geometry_version": version, "spatial_scope": "plot",
        "packet_digest": observation_packet_digest(packet),
        "issued_at": (STAMP + timedelta(hours=1)).isoformat(),
        "expires_at": (RUN + timedelta(hours=1)).isoformat(),
    }
    return {"grant": grant, "mac": hmac.new(
        KEY, _canonical_bytes(grant), hashlib.sha256
    ).hexdigest()}


def _run(monkeypatch, packets):
    monkeypatch.setenv("NODE_ENV", "test")
    for name in ("ENV", "APP_ENV", "ENVIRONMENT", "AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS"):
        monkeypatch.delenv(name, raising=False)
    engine = Layer0StateEngine(
        positive_admission_verifier=PositiveObservationAdmissionVerifier({
            "s2-key": ("sentinel2", KEY),
        })
    )
    receipts = {
        observation_packet_digest(packet): _grant(packet)
        for packet in packets
    }
    return engine.run_from_packets(
        plot_id="plot-A", packets=packets, start_date="2026-11-03",
        end_date="2026-11-03", geometry_hash="geometry-A",
        geometry_version=1, run_timestamp=RUN,
        positive_admission_receipts=receipts,
    )


def _numerical(package):
    return json.dumps({
        "daily_state": package.daily_state,
        "state_uncertainty": package.state_uncertainty,
    }, sort_keys=True, default=str)


def test_identical_signed_retry_keeps_full_state_covariance_and_input_root(monkeypatch):
    p = _packet(0.8)
    once = _run(monkeypatch, [p])
    retried = _run(monkeypatch, [p, p])
    assert _numerical(once) == _numerical(retried)
    assert once.input_hash == retried.input_hash
    one_manifest = once.provenance["positive_state_input_manifest"]
    assert one_manifest == retried.provenance["positive_state_input_manifest"]
    assert len(one_manifest["ordered_observation_updates"]) == 1
    assert one_manifest["domain"].endswith("/v2")
    assert retried.health_report["state_packets_excluded_by_status"][
        "skipped_duplicate_observation"
    ] == 1
    assert retried.health_report["signed_state_input_count"] == 1


def test_signed_independent_packet_permutations_have_same_execution_and_root(monkeypatch):
    a, b = _packet(0.2), _packet(0.8)
    assert a.packet_id == b.packet_id  # legacy ID is NOT independent evidence
    assert observation_packet_digest(a) != observation_packet_digest(b)
    ab = _run(monkeypatch, [a, b])
    ba = _run(monkeypatch, [b, a])
    assert _numerical(ab) == _numerical(ba)
    assert ab.input_hash == ba.input_hash
    entries = ab.provenance["positive_state_input_manifest"]["ordered_observation_updates"]
    assert entries == ba.provenance["positive_state_input_manifest"]["ordered_observation_updates"]
    assert len(entries) == 2
    assert {entry["value"] for entry in entries} == {0.2, 0.8}


def test_changed_observation_value_changes_consumed_manifest_root(monkeypatch):
    first = _run(monkeypatch, [_packet(0.2)])
    second = _run(monkeypatch, [_packet(0.8)])
    assert first.input_hash != second.input_hash


def test_reused_immutable_qualification_id_with_conflicting_content_rejects(monkeypatch):
    a = _packet(0.2, decision="qualified-product-123")
    b = _packet(0.8, decision="qualified-product-123")
    with pytest.raises(Layer0AdmissionRequiredError, match="Conflicting signed qualification"):
        _run(monkeypatch, [a, b])


@pytest.mark.parametrize("version", [True, 1.0, False, "1"])
def test_signed_packet_geometry_version_aliases_are_rejected(version):
    p = _packet(0.8, version=version)
    verifier = PositiveObservationAdmissionVerifier({"s2-key": ("sentinel2", KEY)})
    valid, reason = verifier.verify(
        _grant(p), p, plot_id="plot-A", geometry_hash="geometry-A",
        geometry_version=1, run_timestamp=RUN,
    )
    assert not valid, reason


@pytest.mark.parametrize("version", [True, 1.0, False, "1"])
def test_signed_grant_geometry_version_aliases_are_rejected(version):
    p = _packet(0.8)
    verifier = PositiveObservationAdmissionVerifier({"s2-key": ("sentinel2", KEY)})
    valid, reason = verifier.verify(
        _grant(p, version=version), p, plot_id="plot-A",
        geometry_hash="geometry-A", geometry_version=1, run_timestamp=RUN,
    )
    assert not valid, reason


def test_exact_integer_geometry_version_still_admitted():
    p = _packet(0.8)
    verifier = PositiveObservationAdmissionVerifier({"s2-key": ("sentinel2", KEY)})
    assert verifier.verify(
        _grant(p), p, plot_id="plot-A", geometry_hash="geometry-A",
        geometry_version=1, run_timestamp=RUN,
    )[0]


def test_canonical_update_order_uses_utc_not_local_offset_strings(monkeypatch):
    from datetime import timezone as tz
    a = _packet(0.2)
    b = _packet(0.8)
    a.timestamp = datetime(2026, 11, 3, 9, tzinfo=tz(timedelta(hours=3)))
    b.timestamp = datetime(2026, 11, 3, 7, tzinfo=tz(timedelta(hours=-2)))
    result = _run(monkeypatch, [b, a])
    ordered = result.provenance["positive_state_input_manifest"]["ordered_observation_updates"]
    assert [entry["timestamp"] for entry in ordered] == [
        "2026-11-03T06:00:00+00:00",
        "2026-11-03T09:00:00+00:00",
    ]
