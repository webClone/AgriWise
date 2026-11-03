"""L0-02C1/C2: management evidence admission and conservative forwarding.

No role string, declared volume, or unverified receipt field grants a
physical water impulse. C3 must integrate a trusted support-aware L3 operator.
"""
from datetime import datetime, timezone
import copy

import pytest

from services.agribrain.layer0.event_forcing_admission import (
    classify_management_event_evidence,
)
from services.agribrain.layer0.kalman_engine import ZoneKalmanFilter
from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType,
)
from services.agribrain.layer0.state_engine import Layer0StateEngine


DAY = "2026-11-01"
AT = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 11, 1, 23, tzinfo=timezone.utc)
WEATHER = {"temp_min": 10.0, "temp_max": 20.0, "precipitation": 0.0, "et0": 3.0}


def evidence(role="USER_REPORTED_EXPOSURE", amount=24.0, event_id="event-1",
             plot="plot-A", geometry="geom-A", zone="plot", timestamp=AT):
    return {
        "payload": {"event_type": "irrigation", "event_id": event_id,
                    "event_role": role, "amount_mm": amount, "zone_id": zone},
        "packet_id": event_id, "content_hash": "content-" + event_id,
        "source": "user_event", "plot_id": plot, "geometry_hash": geometry,
        "timestamp": timestamp,
    }


def route(events, zone="plot", seen=None):
    return classify_management_event_evidence(
        events, day=DAY, plot_id="plot-A", zone_id=zone,
        geometry_hash="geom-A", cutoff=CUTOFF, seen_ids=seen,
    )


@pytest.mark.parametrize("role,reason", [
    ("PLANNED_SCENARIO", "planned_not_delivered"),
    ("USER_REPORTED_EXPOSURE", "reported_not_verified"),
    ("VERIFIED_DELIVERY", "claimed_verification_requires_trusted_L3_receipt"),
    ("UNKNOWN", "unknown_delivery_role"),
])
def test_role_label_never_grants_physical_delivery(role, reason):
    record = route([evidence(role=role)])[0]
    assert record["status"] == "DEFERRED"
    assert record["reason"] == reason
    assert record["physical_delivery_verified"] is False
    assert record["state_update_allowed"] is False


def test_genuine_reported_zero_retained_not_treated_as_missing():
    record = route([evidence(amount=0.0)])[0]
    assert record["status"] == "DEFERRED"
    assert record["reason"] == "reported_not_verified"


@pytest.mark.parametrize("bad_event,reason", [
    (evidence(plot="plot-B"), "unbound_or_foreign_plot"),
    (evidence(geometry="geom-B"), "unbound_or_foreign_geometry"),
    (evidence(zone="foreign-zone"), "event_outside_zone"),
    (evidence(amount=-1.0), "invalid_irrigation_amount"),
    (evidence(amount=float("inf")), "invalid_irrigation_amount"),
    (evidence(amount=True), "invalid_irrigation_amount"),
    (evidence(timestamp=datetime(2026, 11, 2, 12, tzinfo=timezone.utc)), "unqualified_event_time"),
    (evidence(timestamp=datetime(2026, 11, 1, 12)), "unqualified_event_time"),
])
def test_invalid_foreign_and_unsupported_evidence_is_rejected(bad_event, reason):
    result = route([bad_event])[0]
    assert result["status"] == "REJECTED"
    assert result["reason"] == reason


def test_duplicate_evidence_fenced_within_one_run():
    first = evidence(event_id="same", amount=10.0)
    second = evidence(event_id="same", amount=40.0)
    output = route([first, second])
    assert output[0]["status"] == "DEFERRED"
    assert output[1]["status"] == "REJECTED"
    assert output[1]["reason"] == "duplicate_event_identity"


def test_later_than_available_cutoff_is_rejected():
    output = classify_management_event_evidence(
        [evidence(timestamp=datetime(2026,11,1,20,tzinfo=timezone.utc))],
        day=DAY, plot_id="plot-A", zone_id="plot", geometry_hash="geom-A",
        cutoff=datetime(2026,11,1,18,tzinfo=timezone.utc),
    )
    assert output[0]["reason"] == "future_or_unavailable_event"


def _filter():
    f = ZoneKalmanFilter("plot")
    f.initialize(DAY)
    f.parent_plot_id = "plot-A"
    f.expected_geometry_hash = "geom-A"
    f.evidence_cutoff = CUTOFF
    return f


@pytest.mark.parametrize("role", [
    "PLANNED_SCENARIO", "USER_REPORTED_EXPOSURE", "VERIFIED_DELIVERY"
])
def test_normal_weather_never_promotes_event_role_to_irrigation(role):
    baseline = _filter()
    baseline_record = baseline.step(DAY, WEATHER, events=[])
    candidate = _filter()
    record = candidate.step(DAY, WEATHER, events=[evidence(role=role)])
    assert candidate.state.values == pytest.approx(baseline.state.values)
    assert candidate.covariance.P == baseline.covariance.P
    assert record["physical_management_events_applied"] == 0
    assert record["management_event_evidence"][0]["status"] == "DEFERRED"
    assert record["weather_availability"] == "COMPLETE"


def test_partial_weather_not_treated_as_measured_or_populated_with_defaults():
    filt = _filter()
    previous = filt.state.values[:]
    record = filt.step(DAY, {"et0": 3.0}, events=[evidence()])
    assert record["weather_availability"] == "PARTIAL"
    assert record["weather_update_mode"] == "missing_weather_high_uncertainty"
    assert record["physical_management_events_applied"] == 0
    assert filt.state.values == previous


def test_real_zero_weather_remains_complete():
    filt = _filter()
    record = filt.step(DAY, {
        "temp_max": 0.0, "temp_min": 0.0, "precipitation": 0.0, "et0": 0.0
    })
    assert record["weather_availability"] == "COMPLETE"
    assert record["weather_update_mode"] == "measured"


def test_direct_raw_predict_event_fails_before_any_state_or_covariance_mutation():
    filt = _filter()
    old_values = filt.state.values[:]
    old_cov = copy.deepcopy(filt.covariance.P)
    with pytest.raises(ValueError, match="trusted L3"):
        filt.predict(DAY, WEATHER, [evidence()["payload"]])
    assert filt.state.values == old_values
    assert filt.covariance.P == old_cov


def test_packet_to_state_transport_retains_identity_and_scope(monkeypatch):
    engine = Layer0StateEngine()
    assert engine._has_kalman
    inputs = {}

    def capture_run(**kwargs):
        inputs.update(kwargs)
        class Stub:
            all_packets = []
            health_report = {}
            def _generate_output_hash(self):
                return "test"
        return Stub()

    monkeypatch.setattr(engine, "run", capture_run)
    pkt = ObservationPacket(
        source=ObservationSource.USER_EVENT,
        obs_type=ObservationType.VECTOR,
        timestamp=AT, plot_id="plot-A", geometry_hash="geom-A",
        payload={"event_type":"irrigation", "amount_mm": 24.0,
                 "event_role":"USER_REPORTED_EXPOSURE"},
    )
    engine.run_from_packets(
        plot_id="plot-A", packets=[pkt], start_date=DAY, end_date=DAY,
    )
    transported = inputs["events_by_day"][DAY][0]
    assert transported["payload"]["amount_mm"] == 24.0
    assert transported["packet_id"] == pkt.packet_id
    assert transported["content_hash"] == pkt.content_hash
    assert transported["plot_id"] == "plot-A"
    assert transported["geometry_hash"] == "geom-A"
    assert transported["timestamp"] == AT
