"""L0-004B2 bounded issuer revocation and registered zone-grant controls.

Uses only test secrets and a local trusted snapshot fixture. Neither test
establishes real provider science, a deployed KMS, or tenant plot authority.
"""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json

import pytest

from services.agribrain.layer0.issuer_revocation import (
    IssuerRevocationSnapshot, TrustedRevocationGate,
)
from services.agribrain.layer0.positive_observation_admission import (
    PositiveObservationAdmissionVerifier, GRANT_DOMAIN, GRANT_PURPOSE,
    ZONE_GRANT_DOMAIN, WEATHER_GRANT_PURPOSE,
    observation_packet_digest, _canonical_bytes,
)
from services.agribrain.layer0.production_admission import load_server_issuer_verifier
from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType, UncertaintyModel,
)


SECRET = b"Y" * 32  # Test fixture only
RUN = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def snapshot(revision=1, status="active", now=RUN, key="s2-key"):
    return IssuerRevocationSnapshot(
        revision=revision,
        issued_at=now - timedelta(seconds=30),
        expires_at=now + timedelta(seconds=90),
        key_statuses={key: status},
    )


def test_revocation_allows_only_current_authorized_keys():
    gate = TrustedRevocationGate(lambda: snapshot())
    assert gate.check("s2-key", RUN)[0] is True
    assert gate.last_accepted_revision == 1
    assert len(gate.last_snapshot_digest) == 64
    assert gate.check("unknown", RUN)[0] is False


@pytest.mark.parametrize("status", ["revoked", "retired"])
def test_revoked_or_retired_keys_are_denied(status):
    gate = TrustedRevocationGate(lambda: snapshot(status=status))
    assert gate.check("s2-key", RUN) == (False, "issuer_revoked_or_retired")


def test_stale_missing_or_future_snapshot_fails_closed():
    cases = [
        IssuerRevocationSnapshot(
            revision=1,
            issued_at=RUN - timedelta(minutes=20),
            expires_at=RUN + timedelta(minutes=2),
            key_statuses={"s2-key": "active"},
        ),
        IssuerRevocationSnapshot(
            revision=1,
            issued_at=RUN + timedelta(minutes=1),
            expires_at=RUN + timedelta(minutes=4),
            key_statuses={"s2-key": "active"},
        ),
        None,
    ]
    for item in cases:
        gate = TrustedRevocationGate(lambda: item)
        assert gate.check("s2-key", RUN)[0] is False


def test_revocation_change_immediately_blocks_old_key():
    current = {"value": snapshot(1, "active")}
    gate = TrustedRevocationGate(lambda: current["value"])
    assert gate.check("s2-key", RUN)[0] is True
    current["value"] = snapshot(2, "revoked")
    assert gate.check("s2-key", RUN)[0] is False
    current["value"] = snapshot(1, "active")
    assert gate.check("s2-key", RUN)[1] == "revocation_snapshot_rollback"


def test_same_revision_conflicting_snapshot_is_denied():
    current = {"value": snapshot(2, "active")}
    gate = TrustedRevocationGate(lambda: current["value"])
    assert gate.check("s2-key", RUN)[0] is True
    current["value"] = snapshot(2, "revoked")
    assert gate.check("s2-key", RUN)[1] == "revocation_snapshot_revision_conflict"


def test_revocation_backend_exceptions_do_not_authorize():
    def offline():
        raise OSError("backend down")
    gate = TrustedRevocationGate(offline)
    assert gate.check("s2-key", RUN)[1] == "revocation_authority_unavailable"


def packet(scope="plot", zone_id="z-1", zone_hash="zg-1"):
    payload = {"ndvi_mean": 0.74}
    if scope == "zone":
        payload.update(zone_id=zone_id, zone_geometry_hash=zone_hash)
    return ObservationPacket(
        source=ObservationSource.SENTINEL2, obs_type=ObservationType.TABULAR,
        timestamp=RUN - timedelta(hours=1),
        plot_id="plot-A", geometry_hash="geom-A", geometry_version=2,
        spatial_scope=scope, payload=payload,
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.04}),
    )


def grant(p, scope="plot", **changes):
    content = {
        "domain": ZONE_GRANT_DOMAIN if scope == "zone" else GRANT_DOMAIN,
        "purpose": GRANT_PURPOSE,
        "key_id": "s2-key",
        "source": "sentinel2",
        "plot_id": "plot-A",
        "geometry_hash": "geom-A",
        "geometry_version": 2,
        "spatial_scope": scope,
        "packet_digest": observation_packet_digest(p),
        "issued_at": (RUN - timedelta(minutes=20)).isoformat(),
        "expires_at": (RUN + timedelta(hours=1)).isoformat(),
    }
    if scope == "zone":
        content.update(zone_id=p.payload["zone_id"],
                       zone_geometry_hash=p.payload["zone_geometry_hash"])
    content.update(changes)
    return {
        "grant": content,
        "mac": hmac.new(SECRET, _canonical_bytes(content), hashlib.sha256).hexdigest(),
    }


ZONE_REGISTRY = {
    "plot-A": {
        "geometry_hash": "geom-A",
        "geometry_version": 2,
        "zones": {"z-1": "zg-1"},
    },
}


def verifier(*, zones=None, policy=None):
    return PositiveObservationAdmissionVerifier(
        {"s2-key": ("sentinel2", SECRET)},
        trusted_zone_registry=zones,
        revocation_gate=policy,
    )


def check(v, p, receipt, purpose=GRANT_PURPOSE):
    return v.verify(
        receipt, p, plot_id="plot-A", geometry_hash="geom-A",
        geometry_version=2, run_timestamp=RUN, purpose=purpose,
    )


def test_v1_plot_receipt_remains_accepted():
    p = packet()
    assert check(verifier(), p, grant(p))[0] is True


def test_legacy_v1_zone_claim_rejected_even_if_correctly_signed():
    p = packet(scope="zone")
    legacy = grant(p, scope="plot", spatial_scope="zone")
    assert check(verifier(zones=ZONE_REGISTRY), p, legacy)[0] is False


def test_v2_zone_signature_requires_trusted_geometry_registration():
    p = packet(scope="zone")
    receipt = grant(p, scope="zone")
    assert check(verifier(zones=ZONE_REGISTRY), p, receipt)[0] is True
    assert check(verifier(zones=None), p, receipt)[1] == "unregistered_or_foreign_zone_geometry"


@pytest.mark.parametrize("zone_id,zone_hash", [
    ("z-2", "zg-1"), ("z-1", "zg-2"),
])
def test_forged_or_foreign_zone_claim_is_not_admitted(zone_id, zone_hash):
    p = packet("zone", zone_id, zone_hash)
    assert check(verifier(zones=ZONE_REGISTRY), p, grant(p, "zone"))[0] is False


def test_zone_signature_does_not_authorize_weather():
    p = packet(scope="zone")
    assert check(verifier(zones=ZONE_REGISTRY), p, grant(p, "zone"),
                 WEATHER_GRANT_PURPOSE)[0] is False


def test_zone_payload_mutation_breaks_signed_content():
    p = packet(scope="zone")
    receipt = grant(p, "zone")
    p.payload["zone_geometry_hash"] = "other"
    assert check(verifier(zones=ZONE_REGISTRY), p, receipt)[0] is False


def test_reissued_wrong_zone_hash_cannot_match_trusted_registry():
    p = packet(scope="zone")
    receipt = grant(p, "zone", zone_geometry_hash="wrong")
    assert check(verifier(zones=ZONE_REGISTRY), p, receipt)[0] is False


def test_verifier_requires_live_revocation_before_admitting_valid_mac():
    p = packet()
    current = {"value": snapshot(1)}
    v = verifier(policy=TrustedRevocationGate(lambda: current["value"]))
    receipt = grant(p)
    assert check(v, p, receipt)[0] is True
    current["value"] = snapshot(2, "revoked")
    assert check(v, p, receipt)[0] is False


def test_protected_backend_files_refresh_revocation_without_client_input(monkeypatch, tmp_path):
    keys = {"s2-key": {
        "source": "sentinel2",
        "secret_b64": base64.b64encode(SECRET).decode("ascii"),
    }}
    path = tmp_path / "issuer-status.json"
    zones = tmp_path / "zone-registry.json"
    monkeypatch.setenv("AKALORIS_LAYER0_ISSUER_KEYS_JSON", json.dumps(keys))
    monkeypatch.setenv("AKALORIS_LAYER0_REVOCATION_SNAPSHOT_PATH", str(path))
    monkeypatch.setenv("AKALORIS_LAYER0_ZONE_REGISTRY_PATH", str(zones))
    zones.write_text(json.dumps(ZONE_REGISTRY), encoding="utf-8")

    now = datetime.now(timezone.utc)
    def save(revision, status):
        data = {
            "revision": revision,
            "issued_at": (now - timedelta(seconds=5)).isoformat(),
            "expires_at": (now + timedelta(minutes=2)).isoformat(),
            "key_statuses": {"s2-key": status},
        }
        path.write_text(json.dumps(data), encoding="utf-8")

    save(1, "active")
    v = load_server_issuer_verifier()
    p = packet(scope="zone")
    # Issue a live-compatible signature with today's actual verification clock.
    receipt = grant(p, "zone", expires_at=(now + timedelta(hours=1)).isoformat())
    valid, reason = v.verify(
        receipt, p, plot_id="plot-A", geometry_hash="geom-A",
        geometry_version=2, run_timestamp=now,
    )
    assert valid, reason
    save(2, "revoked")
    assert v.verify(
        receipt, p, plot_id="plot-A", geometry_hash="geom-A",
        geometry_version=2, run_timestamp=now,
    )[0] is False


def test_zonal_packet_must_also_be_named_in_caller_run(monkeypatch):
    from services.agribrain.layer0.state_engine import Layer0StateEngine
    p = packet(scope="zone")
    digest = observation_packet_digest(p)
    engine = Layer0StateEngine(positive_admission_verifier=verifier(zones=ZONE_REGISTRY))
    capture = {}
    class State:
        all_packets = []
        health_report = {}
        provenance = {}
        input_hash = ""
        output_hash = ""
        def _generate_output_hash(self):
            return hashlib.sha256(_canonical_bytes(self.health_report)).hexdigest()
    monkeypatch.setattr(engine, "run", lambda **kw: (capture.update(kw) or State()))
    result = engine.run_from_packets(
        plot_id="plot-A", packets=[p],
        start_date="2026-11-03", end_date="2026-11-03",
        geometry_hash="geom-A", geometry_version=2,
        positive_admission_receipts={digest: grant(p, "zone")},
        run_timestamp=RUN, zone_ids=[],
    )
    assert capture["observations_by_day"] == {}
    assert result.health_report["state_packets_excluded_by_status"][
        "skipped_unsupported_zone_in_run"
    ] == 1


def test_live_revocation_during_packet_run_aborts_before_state_build(monkeypatch):
    from services.agribrain.layer0.state_engine import Layer0StateEngine
    from services.agribrain.layer0.production_admission import Layer0AdmissionRequiredError
    p = packet()
    invocations = {"count": 0}
    def provider():
        invocations["count"] += 1
        if invocations["count"] == 1:
            return snapshot(1, "active")
        return snapshot(2, "revoked")
    signed = verifier(policy=TrustedRevocationGate(provider))
    engine = Layer0StateEngine(positive_admission_verifier=signed)
    def must_not_run(**kw):
        raise AssertionError("revoked source cannot reach state estimation")
    monkeypatch.setattr(engine, "run", must_not_run)
    with pytest.raises(Layer0AdmissionRequiredError, match="revocation"):
        engine.run_from_packets(
            plot_id="plot-A", packets=[p],
            start_date="2026-11-03", end_date="2026-11-03",
            geometry_hash="geom-A", geometry_version=2,
            run_timestamp=RUN,
            positive_admission_receipts={
                observation_packet_digest(p): grant(p)
            },
        )


def test_registered_signed_zone_packet_reaches_only_matching_zone(monkeypatch):
    from services.agribrain.layer0.state_engine import Layer0StateEngine
    p = packet(scope="zone")
    digest = observation_packet_digest(p)
    engine = Layer0StateEngine(positive_admission_verifier=verifier(zones=ZONE_REGISTRY))
    capture = {}
    class State:
        all_packets = []
        health_report = {}
        provenance = {}
        input_hash = ""
        output_hash = ""
        def _generate_output_hash(self):
            return hashlib.sha256(_canonical_bytes({
                "input_hash": self.input_hash,
                "health_report": self.health_report,
                "provenance": self.provenance,
            })).hexdigest()
    monkeypatch.setattr(engine, "run", lambda **kw: (capture.update(kw) or State()))
    result = engine.run_from_packets(
        plot_id="plot-A", packets=[p],
        start_date="2026-11-03", end_date="2026-11-03",
        geometry_hash="geom-A", geometry_version=2, zone_ids=["z-1"],
        run_timestamp=RUN,
        positive_admission_receipts={digest: grant(p, "zone")},
    )
    assert len(capture["observations_by_day"]["2026-11-03"]["z-1"]) == 1
    assert result.health_report["signed_state_input_count"] == 1
    assert result.health_report["zone_authority_configured"] is True
    assert result.health_report["scientific_publication_authorized"] is False


def test_explicit_live_revocation_policy_fails_without_config(monkeypatch):
    from services.agribrain.layer0.production_admission import (
        Layer0AdmissionRequiredError, require_trusted_verifier,
    )
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "true")
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_LIVE_REVOCATION", "true")
    monkeypatch.setenv("AKALORIS_LAYER0_ISSUER_KEYS_JSON", json.dumps({
        "s2-key": {
            "source": "sentinel2",
            "secret_b64": base64.b64encode(SECRET).decode("ascii"),
        },
    }))
    monkeypatch.delenv("AKALORIS_LAYER0_REVOCATION_SNAPSHOT_PATH", raising=False)
    with pytest.raises(Layer0AdmissionRequiredError, match="revocation"):
        require_trusted_verifier(verifier())
    with pytest.raises(Layer0AdmissionRequiredError, match="revocation"):
        load_server_issuer_verifier()


def test_key_rotation_accepts_new_id_after_retiring_previous_id():
    keys = {
        "old-id": ("sentinel2", SECRET),
        "new-id": ("sentinel2", b"N" * 32),
    }
    current = {"value": IssuerRevocationSnapshot(
        revision=8,
        issued_at=RUN - timedelta(seconds=20),
        expires_at=RUN + timedelta(seconds=90),
        key_statuses={"old-id": "active", "new-id": "active"},
    )}
    gate = TrustedRevocationGate(lambda: current["value"])
    v = PositiveObservationAdmissionVerifier(keys, revocation_gate=gate)
    p = packet()
    old_receipt = grant(p, key_id="old-id")
    new_grant = grant(p, key_id="new-id")
    new_grant["mac"] = hmac.new(
        b"N" * 32, _canonical_bytes(new_grant["grant"]), hashlib.sha256
    ).hexdigest()
    assert check(v, p, old_receipt)[0]
    assert check(v, p, new_grant)[0]
    current["value"] = IssuerRevocationSnapshot(
        revision=9,
        issued_at=RUN - timedelta(seconds=10),
        expires_at=RUN + timedelta(seconds=90),
        key_statuses={"old-id": "retired", "new-id": "active"},
    )
    assert not check(v, p, old_receipt)[0]
    assert check(v, p, new_grant)[0]
