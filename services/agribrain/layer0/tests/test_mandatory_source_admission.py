"""L0-004B1 — mandatory production scientific-state admission regression.

These tests prove server policy, guarded entrypoint, live receipt cut-off and
configuration isolation. They do NOT constitute a deployed issuer, KMS,
physical observation verification or pilot publication authorization.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

import pytest

from services.agribrain.layer0.production_admission import (
    Layer0AdmissionRequiredError,
    signed_inputs_required,
    load_server_issuer_verifier,
)
from services.agribrain.layer0.positive_observation_admission import (
    PositiveObservationAdmissionVerifier, GRANT_DOMAIN, GRANT_PURPOSE,
    _canonical_bytes, observation_packet_digest,
)
from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType, UncertaintyModel,
)
from services.agribrain.layer0.runner import Layer0Runner
from services.agribrain.layer0.state_engine import Layer0StateEngine


SECRET = b"S" * 32  # TEST FIXTURE ONLY — never for production deployment


def _strict(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "production")
    monkeypatch.delenv("AKALORIS_LAYER0_ISSUER_KEYS_JSON", raising=False)


def _verifier():
    return PositiveObservationAdmissionVerifier({"sentinel2-active": ("sentinel2", SECRET)})


def _packet(stamp=None):
    stamp = stamp or (datetime.now(timezone.utc) - timedelta(hours=2))
    return ObservationPacket(
        source=ObservationSource.SENTINEL2,
        obs_type=ObservationType.TABULAR,
        timestamp=stamp, plot_id="plot-a", geometry_hash="geometry-a",
        geometry_version=7, spatial_scope="plot",
        payload={"ndvi_mean": 0.75, "production_usable": True,
                 "real_provider_product": True},
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.06}),
    )


def _grant(packet, issued=None, expiry=None):
    now = datetime.now(timezone.utc)
    grant = {
        "domain": GRANT_DOMAIN,
        "purpose": GRANT_PURPOSE,
        "key_id": "sentinel2-active",
        "source": "sentinel2",
        "plot_id": "plot-a",
        "geometry_hash": "geometry-a",
        "geometry_version": 7,
        "spatial_scope": "plot",
        "packet_digest": observation_packet_digest(packet),
        "issued_at": (issued or (now - timedelta(hours=1))).isoformat(),
        "expires_at": (expiry or (now + timedelta(hours=1))).isoformat(),
    }
    return {
        "grant": grant,
        "mac": hmac.new(SECRET, _canonical_bytes(grant), hashlib.sha256).hexdigest(),
    }


class _StubState:
    def __init__(self):
        self.all_packets = []
        self.health_report = {}
        self.output_hash = ""
    def _generate_output_hash(self):
        return hashlib.sha256(_canonical_bytes(self.health_report)).hexdigest()


def _capture_packet_run(engine, packet, receipt, monkeypatch, run_time=None):
    capture = {}
    def fake_run(**kwargs):
        capture.update(kwargs)
        return _StubState()
    monkeypatch.setattr(engine, "run", fake_run)
    day = packet.timestamp.date().isoformat()
    output = engine.run_from_packets(
        plot_id="plot-a", packets=[packet],
        start_date=day, end_date=day,
        geometry_hash="geometry-a", geometry_version=7,
        run_timestamp=run_time or datetime.now(timezone.utc),
        positive_admission_receipts={
            observation_packet_digest(packet): receipt
        } if receipt is not None else {},
    )
    observations = capture["observations_by_day"].get(day, {}).get("plot", [])
    return output, observations, capture


def test_production_and_staging_cannot_disable_signed_policy(monkeypatch):
    for name in ("production", "staging", "prod"):
        monkeypatch.setenv("NODE_ENV", name)
        monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "false")
        assert signed_inputs_required() is True


def test_research_policy_can_opt_in_without_promoting_default(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "test")
    for key in ("ENVIRONMENT", "ENV", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", raising=False)
    assert signed_inputs_required() is False
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "true")
    assert signed_inputs_required() is True


def test_production_runner_without_trust_root_fails_at_construction(monkeypatch):
    _strict(monkeypatch)
    with pytest.raises(Layer0AdmissionRequiredError, match="issuer keys"):
        Layer0Runner()
    with pytest.raises(Layer0AdmissionRequiredError, match="no trusted"):
        Layer0StateEngine()


def test_wrong_verifier_object_cannot_turn_on_mandatory_mode(monkeypatch):
    _strict(monkeypatch)
    with pytest.raises(Layer0AdmissionRequiredError, match="trusted verifier type"):
        Layer0StateEngine(positive_admission_verifier=object())


def test_env_registry_provisions_trusted_verifier_without_request_keys(monkeypatch):
    _strict(monkeypatch)
    config = {
        "sentinel2-active": {
            "source": "sentinel2",
            "secret_b64": base64.b64encode(SECRET).decode("ascii"),
        }
    }
    monkeypatch.setenv("AKALORIS_LAYER0_ISSUER_KEYS_JSON", json.dumps(config))
    runner = Layer0Runner()
    assert isinstance(
        runner.state_engine._positive_observation_admission_verifier,
        PositiveObservationAdmissionVerifier,
    )


@pytest.mark.parametrize("raw", [
    "{}", "null", "{invalid}", '{"id":{"source":"sentinel2","secret_b64":"foo"}}',
    '{"x":{"source":"sentinel2","secret_b64":"not-base64"}}',
    '{"x":{"source":"sentinel2","secret_b64":"AAAAAAAA"}}',
    '{"x":{"source":"sentinel2","secret_b64":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="},"x":{}}',
])
def test_invalid_or_duplicate_registry_never_provisions_verifier(monkeypatch, raw):
    _strict(monkeypatch)
    monkeypatch.setenv("AKALORIS_LAYER0_ISSUER_KEYS_JSON", raw)
    with pytest.raises(Layer0AdmissionRequiredError):
        load_server_issuer_verifier()


def test_direct_unverified_scalar_entry_cannot_bypass_strict_policy(monkeypatch):
    _strict(monkeypatch)
    engine = Layer0StateEngine(positive_admission_verifier=_verifier())
    with pytest.raises(Layer0AdmissionRequiredError, match="Direct"):
        engine.run(
            plot_id="plot-a",
            start_date="2026-11-01", end_date="2026-11-01",
            daily_weather={}, observations_by_day={}, events_by_day={},
            geometry_hash="geometry-a", geometry_version=7,
        )


def test_strict_packet_entry_accepts_only_signed_current_input(monkeypatch):
    _strict(monkeypatch)
    packet = _packet()
    engine = Layer0StateEngine(positive_admission_verifier=_verifier())
    output, observations, capture = _capture_packet_run(
        engine, packet, _grant(packet), monkeypatch
    )
    assert len(observations) == 1
    assert observations[0].value == 0.75
    assert output.health_report["positive_source_admission_mode"] == (
        "MANDATORY_SIGNED_STATE_INPUTS"
    )
    assert capture["_packet_run_capability"] is engine._Layer0StateEngine__packet_run_capability


def test_historical_run_timestamp_cannot_resurrect_expired_signature(monkeypatch):
    _strict(monkeypatch)
    # Construct an otherwise valid historical receipt: acquisition predates
    # issuance, the replay timestamp falls inside its signed lifetime, and
    # only the trusted current wall clock determines that it has expired.
    now = datetime.now(timezone.utc)
    packet = _packet(now - timedelta(days=5))
    issued = now - timedelta(days=4)
    expiry = now - timedelta(days=3)
    old_replay_time = issued + timedelta(hours=1)
    engine = Layer0StateEngine(positive_admission_verifier=_verifier())
    output, observations, _ = _capture_packet_run(
        engine, packet, _grant(packet, issued=issued, expiry=expiry),
        monkeypatch, run_time=old_replay_time,
    )
    assert observations == []
    assert output.health_report["state_packets_excluded_by_status"][
        "skipped_invalid_positive_source_grant"
    ] == 1


def test_production_legacy_input_with_self_claimed_flags_is_not_admitted(monkeypatch):
    _strict(monkeypatch)
    engine = Layer0StateEngine(positive_admission_verifier=_verifier())
    packet = _packet()
    output, observations, _ = _capture_packet_run(engine, packet, None, monkeypatch)
    assert observations == []
    assert output.health_report["state_packets_excluded_by_status"][
        "skipped_missing_positive_source_grant"
    ] == 1


def test_historical_acquisition_can_precede_trusted_grant_issuance(monkeypatch):
    _strict(monkeypatch)
    # Archived satellite observation can be acquired before authenticated QA
    # and later receipt issuance. The live wall clock must still be valid.
    packet = _packet(datetime.now(timezone.utc) - timedelta(days=20))
    receipt = _grant(packet)
    assert packet.timestamp < datetime.fromisoformat(receipt["grant"]["issued_at"])
    output, observations, _ = _capture_packet_run(
        Layer0StateEngine(positive_admission_verifier=_verifier()),
        packet, receipt, monkeypatch
    )
    assert len(observations) == 1


def test_one_development_env_cannot_override_another_production_env(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "false")
    assert signed_inputs_required() is True


def test_long_lived_legacy_engine_rechecks_hardened_runtime_policy(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "test")
    for key in ("ENVIRONMENT", "ENV", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", raising=False)
    engine = Layer0StateEngine()
    assert engine._has_kalman
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "true")
    packet = _packet()
    with pytest.raises(Layer0AdmissionRequiredError):
        engine.run_from_packets(
            plot_id="plot-a", packets=[packet],
            start_date=packet.timestamp.date().isoformat(),
            end_date=packet.timestamp.date().isoformat(),
            geometry_hash="geometry-a", geometry_version=7,
        )
