"""L0-002 bounded negative packet-identity admission controls.

This slice blocks explicit foreign identities and forbids packet-driven
inference of caller geometry. It is NOT yet the affirmative plot/geometry
grant contract: empty packet identity and empty caller geometry remain
legacy-compatible, pending producer/authorization audit.
"""
from datetime import datetime, timezone

import pytest

from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType, UncertaintyModel,
)
from services.agribrain.layer0.state_engine import Layer0StateEngine


DAY = "2026-11-01"
STAMP = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


class _Validator:
    source_reliability = {}
    def validate_day(self, *args):
        pass
    def get_conflict_summary(self, **kwargs):
        return []


def _engine():
    engine = Layer0StateEngine()
    assert engine._has_kalman
    engine._ValidationGraph = _Validator
    engine._layer0_audit = lambda **kwargs: {
        "test_adapter": True,
        "structural_audit": {
            "status": "PASS",
            "checks_run": 1,
            "checks_failed": 0,
        },
    }
    return engine


def _packet(plot="plot-A", geometry="geom-A", version=2, source=ObservationSource.SENTINEL2):
    return ObservationPacket(
        source=source, obs_type=ObservationType.TABULAR,
        timestamp=STAMP, plot_id=plot, geometry_hash=geometry,
        geometry_version=version,
        payload=(
            {"ndvi_mean": 0.8}
            if source == ObservationSource.SENTINEL2
            else {"temp_max": 21.0, "temp_min": 11.0,
                  "precipitation": 0.0, "et0": 3.0}
        ),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.04}),
    )


def _run(packets, geometry_hash="geom-A", geometry_version=2):
    result = _engine().run_from_packets(
        plot_id="plot-A", packets=packets,
        start_date=DAY, end_date=DAY,
        geometry_hash=geometry_hash, geometry_version=geometry_version,
        run_timestamp=datetime(2026, 11, 1, 23, tzinfo=timezone.utc),
    )
    zone = result.provenance["provenance_log"][0]["zones"]["plot"]
    return result, zone


@pytest.mark.parametrize("packet,excluded_key", [
    (_packet(plot="plot-B"), "skipped_foreign_plot"),
    (_packet(geometry="geom-B"), "skipped_foreign_geometry"),
    (_packet(geometry=""), "skipped_foreign_geometry"),
    (_packet(version=3), "skipped_foreign_geometry_version"),
    (_packet(version=None), "skipped_foreign_geometry_version"),
])
def test_explicitly_foreign_observation_never_changes_state(packet, excluded_key):
    baseline, before = _run([])
    result, zone = _run([packet])
    assert zone["state"] == before["state"]
    assert zone["uncertainty"] == before["uncertainty"]
    assert zone["provenance"]["n_obs"] == 0
    assert result.health_report["state_packets_excluded_by_status"][excluded_key] == 1


def test_matching_plot_geometry_and_version_can_assimilate():
    _, baseline = _run([])
    result, zone = _run([_packet()])
    assert zone["provenance"]["n_obs"] == 1
    assert zone["state"]["lai_proxy"] > baseline["state"]["lai_proxy"]
    assert result.geometry_hash == "geom-A"
    assert result.geometry_version == 2


def test_foreign_weather_packet_not_transported_into_forcing():
    inputs = {}
    engine = _engine()

    def capture_run(**kwargs):
        inputs.update(kwargs)
        class Stub:
            all_packets = []
            health_report = {}
            def _generate_output_hash(self):
                return "test"
        return Stub()

    engine.run = capture_run
    out = engine.run_from_packets(
        plot_id="plot-A",
        packets=[_packet(plot="plot-B", source=ObservationSource.WEATHER_STATION)],
        start_date=DAY, end_date=DAY,
        geometry_hash="geom-A", geometry_version=2,
    )
    assert inputs["daily_weather"] == {}
    assert out.health_report["state_packets_excluded_by_status"]["skipped_foreign_plot"] == 1


def test_caller_geometry_not_inferred_from_untrusted_packet():
    out, zone = _run([_packet()], geometry_hash="", geometry_version=None)
    assert out.geometry_hash == ""
    assert out.geometry_version is None
    # Observation admission without a positively bound caller geometry is a
    # separate open item; this test checks absence of false *output identity*.
