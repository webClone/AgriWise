"""L0-004B1 signed-input manifest and state output-root regression tests.

Receipt manifests preserve data lineage, but never independently grant
prescription/publication authority and are not empirical calibration proof.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac

from services.agribrain.layer0.positive_observation_admission import (
    PositiveObservationAdmissionVerifier,
    GRANT_DOMAIN, GRANT_PURPOSE, WEATHER_GRANT_PURPOSE,
    observation_packet_digest, _canonical_bytes,
)
from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType, UncertaintyModel,
)
from services.agribrain.layer0.source_package import Layer0StatePackage
from services.agribrain.layer0.state_engine import Layer0StateEngine


NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
STAMP = NOW - timedelta(hours=3)
DAY = STAMP.date().isoformat()
SECRET = b"R" * 32  # purely test fixture


def _packet(source, payload):
    return ObservationPacket(
        source=source, obs_type=ObservationType.TABULAR,
        timestamp=STAMP, plot_id="plot", geometry_hash="geom",
        geometry_version=4, spatial_scope="plot",
        payload=payload,
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.04}),
    )


def _receipt(packet, purpose):
    grant = {
        "domain": GRANT_DOMAIN,
        "purpose": purpose,
        "key_id": "key-" + packet.source.value,
        "source": packet.source.value,
        "plot_id": "plot",
        "geometry_hash": "geom",
        "geometry_version": 4,
        "spatial_scope": "plot",
        "packet_digest": observation_packet_digest(packet),
        "issued_at": (STAMP + timedelta(hours=1)).isoformat(),
        "expires_at": (NOW + timedelta(hours=2)).isoformat(),
    }
    return {"grant": grant, "mac": hmac.new(
        SECRET, _canonical_bytes(grant), hashlib.sha256
    ).hexdigest()}


class _State:
    def __init__(self):
        self.all_packets = []
        self.health_report = {}
        self.provenance = {}
        self.input_hash = ""
        self.output_hash = ""
    def _generate_output_hash(self):
        return hashlib.sha256(
            _canonical_bytes({
                "input_hash": self.input_hash,
                "health_report": self.health_report,
                "provenance": self.provenance,
            })
        ).hexdigest()


def _run(monkeypatch, packets):
    engine = Layer0StateEngine(positive_admission_verifier=(
        PositiveObservationAdmissionVerifier({
            "key-sentinel2": ("sentinel2", SECRET),
            "key-weather_station": ("weather_station", SECRET),
        })
    ))
    assert engine._has_kalman
    forwarded = {}

    def capture(**kwargs):
        forwarded.update(kwargs)
        return _State()

    monkeypatch.setattr(engine, "run", capture)
    purposes = {
        ObservationSource.SENTINEL2: GRANT_PURPOSE,
        ObservationSource.WEATHER_STATION: WEATHER_GRANT_PURPOSE,
    }
    receipts = {
        observation_packet_digest(p): _receipt(p, purposes[p.source])
        for p in packets
    }
    output = engine.run_from_packets(
        plot_id="plot", packets=packets,
        start_date=DAY, end_date=DAY,
        geometry_hash="geom", geometry_version=4,
        run_timestamp=NOW, positive_admission_receipts=receipts,
    )
    return output, forwarded


def test_signed_ndvi_input_is_immutable_hash_lineage_not_publication_authority(monkeypatch):
    packet = _packet(ObservationSource.SENTINEL2, {"ndvi_mean": 0.7})
    output, forwarded = _run(monkeypatch, [packet])
    assert len(forwarded["observations_by_day"][DAY]["plot"]) == 1
    digest = observation_packet_digest(packet)
    manifest = output.provenance["positive_state_input_manifest"]
    assert manifest["admitted_receipts"][0]["packet_digest"] == digest
    assert output.input_hash == hashlib.sha256(_canonical_bytes(manifest)).hexdigest()
    assert output.health_report["signed_state_input_count"] == 1
    assert output.health_report["state_output_role"] == "STATE_ESTIMATE"
    assert output.health_report["scientific_publication_authorized"] is False
    assert output.output_hash == output._generate_output_hash()


def test_modified_input_measurement_produces_different_verified_manifest_root(monkeypatch):
    first, _ = _run(monkeypatch, [
        _packet(ObservationSource.SENTINEL2, {"ndvi_mean": 0.7})
    ])
    second, _ = _run(monkeypatch, [
        _packet(ObservationSource.SENTINEL2, {"ndvi_mean": 0.8})
    ])
    assert first.input_hash != second.input_hash
    assert first.output_hash != second.output_hash


def test_partial_weather_is_not_rooted_as_applied_state_forcing(monkeypatch):
    packet = _packet(ObservationSource.WEATHER_STATION, {"et0": 3.0})
    output, forwarded = _run(monkeypatch, [packet])
    assert forwarded["daily_weather"][DAY] == {"et0": 3.0}
    assert output.health_report["positive_admitted_weather_digests"] == []
    assert output.health_report["signed_state_input_count"] == 0
    assert output.provenance["positive_state_input_manifest"][
        "effective_weather_field_sources"
    ] == {}
    assert output.health_report["scientific_publication_authorized"] is False


def test_complete_weather_binds_final_field_receipt(monkeypatch):
    weather = _packet(ObservationSource.WEATHER_STATION, {
        "temp_max": 22.0, "temp_min": 11.0,
        "precipitation": 0.0, "et0": 3.0,
    })
    output, forwarded = _run(monkeypatch, [weather])
    digest = observation_packet_digest(weather)
    assert forwarded["daily_weather"][DAY]["precipitation"] == 0.0
    assert output.health_report["positive_admitted_weather_digests"] == [digest]
    assert set(output.provenance["positive_state_input_manifest"][
        "effective_weather_field_sources"
    ][DAY].values()) == {digest}
    assert output.health_report["scientific_publication_authorized"] is False


def test_superseded_weather_packet_not_reported_as_effective_forcing(monkeypatch):
    earlier = _packet(ObservationSource.WEATHER_STATION, {
        "temp_max": 20.0, "temp_min": 10.0,
        "precipitation": 1.0, "et0": 2.0,
    })
    later = _packet(ObservationSource.WEATHER_STATION, {
        "temp_max": 24.0, "temp_min": 14.0,
        "precipitation": 2.0, "et0": 4.0,
    })
    output, forwarded = _run(monkeypatch, [earlier, later])
    assert forwarded["daily_weather"][DAY]["precipitation"] == 2.0
    assert output.health_report["positive_admitted_weather_digests"] == [
        observation_packet_digest(later)
    ]
    assert len(output.provenance["positive_state_input_manifest"][
        "admitted_receipts"
    ]) == 1


def test_real_state_package_output_hash_binds_verified_input_root():
    base = Layer0StatePackage(
        run_id="r", plot_id="plot", geometry_hash="geom",
        geometry_version=4,
        health_report={"state_output_role": "STATE_ESTIMATE"},
    )
    initial = base.output_hash
    base.input_hash = "a" * 64
    first = base._generate_output_hash()
    base.input_hash = "b" * 64
    second = base._generate_output_hash()
    assert len({initial, first, second}) == 3
