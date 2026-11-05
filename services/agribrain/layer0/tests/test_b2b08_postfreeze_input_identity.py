"""Focused, offline contracts for post-freeze physical checkpoint inputs."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.agribrain.layer0.event_forcing_admission import extract_irrigation_receipt
from services.agribrain.layer0.irrigation_checkpoint_inputs import (
    CheckpointInputConflict, checkpoint_input_digest,
)
from services.agribrain.layer0.kalman_engine import KalmanObservation


def digest(*, precipitation=0.0, observations=None, events=None):
    state = SimpleNamespace(
        day="2026-11-03", values=[0.1] * 9, variance=[0.03] * 9,
    )
    covariance = SimpleNamespace(P=[
        [0.1 if i == j else 0.0 for j in range(9)]
        for i in range(9)
    ])
    return checkpoint_input_digest(
        day="2026-11-04", zone_id="plot",
        weather={"temp_max": 20.0, "temp_min": 10.0,
                 "precipitation": precipitation, "et0": 3.0},
        observations=observations or [], events=events or [],
        prior_state=state, prior_covariance=covariance,
        last_obs_day="2026-11-03", days_since_obs=0,
    )


def event(receipt_id):
    return {
        "source": "user_event", "plot_id": "p1",
        "geometry_hash": "g1", "geometry_version": 1,
        "timestamp": datetime(2026, 11, 4, 14, tzinfo=timezone.utc),
        "packet_id": "ephemeral-transport-value",
        "payload": {"event_type": "irrigation", "event_role": "REPORTED",
                    "event_id": receipt_id, "verified_receipt": {
                        "grant": {"receipt_id": receipt_id},
                        "signature": "fake-only-for-digest-test",
                    }},
    }


def test_exact_input_retry_is_deterministic_and_ignores_transport_packet_id():
    original = event("r1")
    other = event("r1")
    other["packet_id"] = "different-http-transport-generated-id"
    assert digest(events=[original]) == digest(events=[other])


def test_new_rain_and_second_delivery_change_durable_identity():
    baseline = digest(events=[event("r1")])
    assert digest(precipitation=20, events=[event("r1")]) != baseline
    assert digest(events=[event("r1"), event("r2")]) != baseline


def test_scientific_observation_change_alters_durable_identity():
    a = KalmanObservation(obs_type="ndvi", value=0.61, sigma=0.04)
    b = KalmanObservation(obs_type="ndvi", value=0.81, sigma=0.04)
    assert digest(observations=[a]) != digest(observations=[b])


def test_nonfinite_weather_fails_closed():
    with pytest.raises(CheckpointInputConflict, match="nonfinite_checkpoint_input"):
        digest(precipitation=float("nan"))


def test_reported_label_does_not_hide_a_signed_irrigation_receipt():
    e = event("r1")
    assert extract_irrigation_receipt(e) == e["payload"]["verified_receipt"]
    e["payload"]["event_role"] = "VERIFIED_DELIVERY"
    assert extract_irrigation_receipt(e) == e["payload"]["verified_receipt"]
    e["payload"]["event_type"] = "fertilizer"
    assert extract_irrigation_receipt(e) is None
