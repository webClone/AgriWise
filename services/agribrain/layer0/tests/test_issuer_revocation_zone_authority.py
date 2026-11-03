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
