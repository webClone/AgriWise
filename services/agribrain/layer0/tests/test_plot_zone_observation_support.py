"""L0-003: plot-level evidence must not become a zone-local measurement.

No spatial downscaling or correlation model is claimed here. The plot state
can assimilate a plot observation; a separate zone needs its own admitted
zone-specific observation before incrementing local n_obs.
"""
from datetime import datetime, timezone

from services.agribrain.layer0.kalman_engine import KalmanObservation
from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType,
    UncertaintyModel,
)
from services.agribrain.layer0.state_engine import Layer0StateEngine


DAY = "2026-11-01"


class _Validator:
    source_reliability = {}
    def validate_day(self, *args):
        pass
    def get_conflict_summary(self, **kwargs):
        return []


def _engine():
    instance = Layer0StateEngine()
    assert instance._has_kalman
    instance._ValidationGraph = _Validator
    instance._layer0_audit = lambda **kwargs: {"test_adapter": True}
    return instance


def _day_zones(result):
    return result.provenance["provenance_log"][0]["zones"]


def test_plot_observation_is_not_cloned_into_unmeasured_zone():
    observations = {DAY: {"plot": [
        KalmanObservation("ndvi", value=0.8, sigma=0.04, source="sentinel2")
    ]}}
    result = _engine().run(
        plot_id="plot-A", start_date=DAY, end_date=DAY,
        daily_weather={}, events_by_day={},
        observations_by_day=observations, zone_ids=["zone-unobserved"],
    )
    zones = _day_zones(result)
    assert zones["plot"]["provenance"]["n_obs"] == 1
    assert zones["zone-unobserved"]["provenance"]["n_obs"] == 0
    assert zones["plot"]["state"]["lai_proxy"] > zones["zone-unobserved"]["state"]["lai_proxy"]
    assert "zone-unobserved" not in observations[DAY]


def test_explicit_zone_evidence_updates_only_its_own_zone():
    observations = {DAY: {"zone-evidence": [
        KalmanObservation("ndvi", value=0.75, sigma=0.04, source="sentinel2")
    ]}}
    result = _engine().run(
        plot_id="plot-A", start_date=DAY, end_date=DAY,
        daily_weather={}, events_by_day={},
        observations_by_day=observations, zone_ids=["zone-evidence", "zone-empty"],
    )
    zones = _day_zones(result)
    assert zones["plot"]["provenance"]["n_obs"] == 0
    assert zones["zone-evidence"]["provenance"]["n_obs"] == 1
    assert zones["zone-empty"]["provenance"]["n_obs"] == 0


def test_canonical_plot_packet_cannot_claim_extra_zone_observations():
    packet = ObservationPacket(
        source=ObservationSource.SENTINEL2,
        obs_type=ObservationType.TABULAR,
        timestamp=datetime(2026, 11, 1, 12, tzinfo=timezone.utc),
        plot_id="plot-A", spatial_scope="plot",
        payload={"ndvi_mean": 0.8},
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.04}),
    )
    result = _engine().run_from_packets(
        plot_id="plot-A", packets=[packet],
        start_date=DAY, end_date=DAY,
        zone_ids=["zone-no-local-evidence"],
        run_timestamp=datetime(2026,11,1,23,tzinfo=timezone.utc),
    )
    zones = _day_zones(result)
    assert zones["plot"]["provenance"]["n_obs"] == 1
    assert zones["zone-no-local-evidence"]["provenance"]["n_obs"] == 0
