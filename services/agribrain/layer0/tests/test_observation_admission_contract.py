"""Layer 0 admission and packet-to-state regression coverage."""
from datetime import datetime, timezone
import math

from services.agribrain.layer0.kalman_engine import KalmanObservation, ZoneKalmanFilter
from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType, UncertaintyModel,
)
from services.agribrain.layer0.state_engine import Layer0StateEngine


def test_diagnostic_observation_cannot_update_state():
    filt = ZoneKalmanFilter("plot")
    filt.initialize("2026-11-01")
    initial = filt.state.values.copy()
    weights = filt.update([KalmanObservation(
        obs_type="ndvi", value=0.9, sigma=0.02, reliability=1.0,
        diagnostic_only=True, state_update_allowed=False,
    )])
    assert filt.state.values == initial
    assert weights == {}
    assert filt.last_obs_day is None
    assert filt.days_since_obs == 0
    assert filt.last_update_admitted_count == 0


def test_invalid_measurement_is_rejected_without_polluting_state():
    filt = ZoneKalmanFilter("plot")
    filt.initialize("2026-11-01")
    initial = filt.state.values.copy()
    weights = filt.update([
        KalmanObservation("ndvi", math.nan, sigma=0.02),
        KalmanObservation("ndvi", 0.7, sigma=0.0),
        KalmanObservation("ndvi", 0.7, sigma=0.02, reliability=math.inf),
    ])
    assert weights == {}
    assert filt.state.values == initial
    assert filt.last_update_admitted_count == 0


def test_packet_dispatch_uses_registered_types_and_own_sigmas(monkeypatch):
    engine = Layer0StateEngine()
    assert engine._has_kalman
    received = {}

    def capture_run(**kwargs):
        received.update(kwargs)
        class Stub:
            all_packets = []
            health_report = {}
            def _generate_output_hash(self):
                return "test"
        return Stub()

    monkeypatch.setattr(engine, "run", capture_run)
    p = ObservationPacket(
        source=ObservationSource.SENTINEL1,
        obs_type=ObservationType.TABULAR,
        timestamp=datetime(2026, 11, 1, tzinfo=timezone.utc),
        payload={"vv_db_mean": -12.0, "vh_db_mean": -17.0,
                 "surface_wetness_proxy_mean": 0.3},
        uncertainty=UncertaintyModel(sigmas={
            "vv_db": 1.5, "vh_db": 2.0, "surface_wetness_proxy": 0.12
        }),
    )
    result = engine.run_from_packets("plot", [p], "2026-11-01", "2026-11-01")
    obs = received["observations_by_day"]["2026-11-01"]["plot"]
    assert [(o.obs_type, o.sigma) for o in obs] == [
        ("vv", 1.5), ("vh", 2.0), ("sar_moisture_proxy", 0.12)
    ]
    assert result.health_report["state_packets_excluded_by_status"]["skipped_observation_no_sigma"] == 0


def test_packet_missing_sigma_cannot_be_assimilated(monkeypatch):
    engine = Layer0StateEngine()
    assert engine._has_kalman
    received = {}

    def capture_run(**kwargs):
        received.update(kwargs)
        class Stub:
            all_packets = []
            health_report = {}
            def _generate_output_hash(self):
                return "test"
        return Stub()

    monkeypatch.setattr(engine, "run", capture_run)
    p = ObservationPacket(
        source=ObservationSource.SENTINEL2,
        obs_type=ObservationType.TABULAR,
        timestamp=datetime(2026, 11, 1, tzinfo=timezone.utc),
        payload={"ndvi_mean": 0.65},
        uncertainty=UncertaintyModel(sigmas={}),
    )
    result = engine.run_from_packets("plot", [p], "2026-11-01", "2026-11-01")
    assert received["observations_by_day"]["2026-11-01"]["plot"] == []
    assert result.health_report["state_packets_excluded_by_status"]["skipped_observation_no_sigma"] == 1
