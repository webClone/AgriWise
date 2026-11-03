"""L0-004A signed state-observation admission: negative and positive controls.

The trusted issuer key here is a test-only fixture. Production key provisioning
and mandatory strict mode are separate migration/qualification work.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac

import pytest

from services.agribrain.layer0.positive_observation_admission import (
    PositiveObservationAdmissionVerifier, GRANT_DOMAIN, GRANT_PURPOSE,
    observation_packet_digest, _canonical_bytes,
)
from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType, UncertaintyModel,
)
from services.agribrain.layer0.state_engine import Layer0StateEngine


KEY = b"T" * 32  # test-only key, never usable for production
STAMP = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
RUN = datetime(2026, 11, 1, 23, tzinfo=timezone.utc)
DAY = "2026-11-01"


def _packet(source=ObservationSource.SENTINEL2):
    return ObservationPacket(
        source=source, obs_type=ObservationType.TABULAR,
        timestamp=STAMP, plot_id="plot-A",
        geometry_hash="geom-A", geometry_version=2,
        spatial_scope="plot",
        payload={"ndvi_mean": 0.8, "production_usable": True,
                 "state_update_allowed": True,
                 "real_provider_product": True},
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.04}),
    )


def _grant(packet, **overrides):
    params = {
        "domain": GRANT_DOMAIN,
        "purpose": GRANT_PURPOSE,
        "key_id": "s2-current",
        "source": packet.source.value,
        "plot_id": "plot-A",
        "geometry_hash": "geom-A",
        "geometry_version": 2,
        "spatial_scope": "plot",
        "packet_digest": observation_packet_digest(packet),
        "issued_at": (STAMP + timedelta(hours=1)).isoformat(),
        "expires_at": (RUN + timedelta(hours=1)).isoformat(),
    }
    params.update(overrides)
    return {
        "grant": params,
        "mac": hmac.new(KEY, _canonical_bytes(params), hashlib.sha256).hexdigest(),
    }


def _verifier():
    return PositiveObservationAdmissionVerifier({"s2-current": ("sentinel2", KEY)})


def _verify(packet, receipt, **kwargs):
    ctx = {
        "plot_id": "plot-A",
        "geometry_hash": "geom-A",
        "geometry_version": 2,
        "run_timestamp": RUN,
    }
    ctx.update(kwargs)
    return _verifier().verify(receipt, packet, **ctx)


def test_detached_positive_grant_is_valid_only_for_exact_source_and_scope():
    packet = _packet()
    assert _verify(packet, _grant(packet)) == (True, "verified_positive_source_grant")


@pytest.mark.parametrize("overrides", [
    {"domain": "akaloris/other"},
    {"purpose": "weather_forcing"},
    {"source": "sentinel1"},
    {"plot_id": "plot-B"},
    {"geometry_hash": "geom-B"},
    {"geometry_version": 3},
    {"spatial_scope": "zone"},
    {"expires_at": (STAMP + timedelta(minutes=2)).isoformat()},
    {"issued_at": (RUN + timedelta(hours=2)).isoformat()},
])
def test_reissued_wrong_domain_role_scope_or_time_not_admitted(overrides):
    packet = _packet()
    accepted, reason = _verify(packet, _grant(packet, **overrides))
    assert not accepted, reason


def test_packet_mutation_invalidates_original_signed_digest():
    packet = _packet()
    receipt = _grant(packet)
    packet.payload["ndvi_mean"] = 0.12
    assert _verify(packet, receipt)[0] is False


def test_qa_mutation_invalidates_original_signed_digest():
    packet = _packet()
    receipt = _grant(packet)
    packet.qa.scene_score = 0.4
    assert _verify(packet, receipt)[0] is False


def test_reliability_mutation_invalidates_original_signed_digest():
    packet = _packet()
    receipt = _grant(packet)
    packet.reliability_weight = 0.4
    assert _verify(packet, receipt)[0] is False


def test_forged_mac_or_untrusted_key_rejected():
    packet = _packet()
    receipt = _grant(packet)
    receipt["mac"] = "f" * 64
    assert _verify(packet, receipt)[0] is False
    different_key = PositiveObservationAdmissionVerifier({
        "s2-current": ("sentinel2", b"X" * 32)
    })
    assert different_key.verify(receipt, packet, plot_id="plot-A",
                                geometry_hash="geom-A", geometry_version=2,
                                run_timestamp=RUN)[0] is False


def test_wrong_issuer_source_rejected_even_if_payload_labels_provider():
    packet = _packet(source=ObservationSource.SENTINEL1)
    receipt = _grant(packet)
    assert _verify(packet, receipt)[0] is False


@pytest.mark.parametrize("context", [
    {"plot_id": ""},
    {"geometry_hash": ""},
    {"geometry_version": None},
    {"geometry_version": True},
])
def test_missing_affirmative_caller_scope_fail_closed(context):
    packet = _packet()
    assert _verify(packet, _grant(packet), **context)[0] is False


def test_naive_or_future_packet_timestamp_is_not_authoritative():
    packet = _packet()
    packet.timestamp = datetime(2026, 11, 1, 10)  # no timezone
    assert _verify(packet, _grant(_packet()))[0] is False
    future = _packet()
    future.timestamp = RUN + timedelta(days=1)
    assert _verify(future, _grant(_packet()))[0] is False


class _StubState:
    def __init__(self):
        self.all_packets = []
        self.health_report = {}
        self.output_hash = ""
    def _generate_output_hash(self):
        return hashlib.sha256(_canonical_bytes(self.health_report)).hexdigest()


def _run_capture(monkeypatch, packet, *, verifier=None, receipts=None):
    engine = Layer0StateEngine(positive_admission_verifier=verifier)
    assert engine._has_kalman
    received = {}

    def capture_run(**kwargs):
        received.update(kwargs)
        return _StubState()

    monkeypatch.setattr(engine, "run", capture_run)
    result = engine.run_from_packets(
        plot_id="plot-A", packets=[packet], start_date=DAY, end_date=DAY,
        geometry_hash="geom-A", geometry_version=2, run_timestamp=RUN,
        positive_admission_receipts=receipts,
    )
    observations = received["observations_by_day"].get(DAY, {}).get("plot", [])
    return result, observations


def test_strict_no_receipt_never_grants_kalman_state(monkeypatch):
    p = _packet()
    result, observations = _run_capture(
        monkeypatch, p, verifier=_verifier(), receipts=None,
    )
    assert observations == []
    assert result.health_report["state_packets_excluded_by_status"][
        "skipped_missing_positive_source_grant"
    ] == 1
    assert result.health_report["positive_source_admission_mode"] == "SIGNED_STATE_INPUTS"


def test_strict_valid_detached_receipt_grants_once(monkeypatch):
    p = _packet()
    digest = observation_packet_digest(p)
    result, observations = _run_capture(
        monkeypatch, p, verifier=_verifier(), receipts={digest: _grant(p)},
    )
    assert len(observations) == 1
    assert observations[0].obs_type == "ndvi"
    assert observations[0].value == 0.8
    assert result.health_report["state_packets_excluded_by_status"][
        "skipped_missing_positive_source_grant"
    ] == 0


def test_strict_payload_flags_cannot_substitute_for_signature(monkeypatch):
    p = _packet()
    bad_grant = _grant(p)
    bad_grant["mac"] = "0" * 64
    result, observations = _run_capture(
        monkeypatch, p, verifier=_verifier(),
        receipts={observation_packet_digest(p): bad_grant},
    )
    assert observations == []
    assert result.health_report["state_packets_excluded_by_status"][
        "skipped_invalid_positive_source_grant"
    ] == 1


def test_legacy_mode_is_visibly_unverified_and_health_is_in_output_hash(monkeypatch):
    p = _packet()
    result, observations = _run_capture(monkeypatch, p)
    assert len(observations) == 1  # compatibility mode is NOT a verified grant
    assert result.health_report["positive_source_admission_mode"] == "LEGACY_UNVERIFIED"
    assert result.output_hash == result._generate_output_hash()
    result.health_report["state_packets_excluded_by_status"][
        "skipped_missing_positive_source_grant"
    ] += 1
    assert result.output_hash != result._generate_output_hash()


def _weather_packet():
    return ObservationPacket(
        source=ObservationSource.WEATHER_STATION,
        obs_type=ObservationType.TABULAR,
        timestamp=STAMP, plot_id="plot-A", geometry_hash="geom-A",
        geometry_version=2, spatial_scope="plot",
        payload={"temp_min": 11.0, "temp_max": 21.0,
                 "precipitation": 0.0, "et0": 3.0},
    )


def _weather_run(monkeypatch, receipt):
    p = _weather_packet()
    verifier = PositiveObservationAdmissionVerifier({
        "s2-current": (p.source.value, KEY),
    })
    engine = Layer0StateEngine(positive_admission_verifier=verifier)
    inputs = {}

    def capture_run(**kwargs):
        inputs.update(kwargs)
        return _StubState()

    monkeypatch.setattr(engine, "run", capture_run)
    out = engine.run_from_packets(
        plot_id="plot-A", packets=[p], start_date=DAY, end_date=DAY,
        geometry_hash="geom-A", geometry_version=2,
        run_timestamp=RUN,
        positive_admission_receipts=(
            {} if receipt is None else {observation_packet_digest(p): receipt}
        ),
    )
    return out, inputs


def test_weather_cannot_change_state_forcing_without_signed_grant(monkeypatch):
    out, inputs = _weather_run(monkeypatch, None)
    assert inputs["daily_weather"] == {}
    assert out.health_report["state_packets_excluded_by_status"][
        "skipped_missing_positive_source_grant"
    ] == 1


def test_observation_purpose_grant_cannot_authorize_weather(monkeypatch):
    packet = _weather_packet()
    out, inputs = _weather_run(monkeypatch, _grant(packet))
    assert inputs["daily_weather"] == {}
    assert out.health_report["state_packets_excluded_by_status"][
        "skipped_invalid_positive_source_grant"
    ] == 1


def test_distinct_signed_weather_purpose_authorizes_exact_forcing(monkeypatch):
    from services.agribrain.layer0.positive_observation_admission import (
        WEATHER_GRANT_PURPOSE,
    )
    packet = _weather_packet()
    out, inputs = _weather_run(
        monkeypatch, _grant(packet, purpose=WEATHER_GRANT_PURPOSE)
    )
    assert inputs["daily_weather"][DAY] == {
        "temp_min": 11.0,
        "temp_max": 21.0,
        "precipitation": 0.0,
        "et0": 3.0,
    }
    assert out.health_report["positive_source_admission_mode"] == "SIGNED_STATE_INPUTS"
    assert out.health_report["positive_admitted_weather_digests"] == [
        observation_packet_digest(packet)
    ]
