"""Bounded 2026-11-03 audit counterexamples for Layer 0 admission.

Verify the *canonical* packet-to-state path, not just a free-standing
observation validator. Zero effective scene quality must not influence state.
"""
from datetime import datetime, timezone

import pytest

from services.agribrain.layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType, QAMetadata,
    UncertaintyModel,
)
from services.agribrain.layer0.state_engine import Layer0StateEngine
from services.agribrain.layer0.kalman_engine import KalmanObservation


DAY = "2026-11-01"
STAMP = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


def _packet(*, value=0.8, quality=1.0, reliability=1.0):
    return ObservationPacket(
        source=ObservationSource.SENTINEL2,
        obs_type=ObservationType.TABULAR,
        timestamp=STAMP,
        plot_id="plot-A",
        payload={
            "ndvi_mean": value,
            "real_provider_product": True,
            "production_usable": True,
            "state_update_allowed": True,
            "diagnostic_only": False,
            "spatial_scope_blocked": False,
        },
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.04}),
        qa=QAMetadata(scene_score=quality),
        reliability_weight=reliability,
    )


class _Validator:
    source_reliability = {}
    def validate_day(self, *args):
        pass
    def get_conflict_summary(self, **kwargs):
        return []


def _run(packets):
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
    result = engine.run_from_packets(
        plot_id="plot-A",
        packets=packets,
        start_date=DAY,
        end_date=DAY,
        run_timestamp=datetime(2026, 11, 1, 23, tzinfo=timezone.utc),
    )
    zone = result.provenance["provenance_log"][0]["zones"]["plot"]
    return (
        zone["state"]["lai_proxy"],
        zone["uncertainty"]["lai_proxy"],
        zone["provenance"]["n_obs"],
        result.health_report["state_packets_excluded_by_status"],
    )


def test_qa_zero_does_not_perturb_real_state_or_covariance():
    control = _run([])
    packet = _packet(quality=0.0)
    assert packet.effective_weight() == 0.0
    candidate = _run([packet])
    assert candidate[:3] == control[:3]
    assert candidate[3]["skipped_observation_low_effective_quality"] == 1


@pytest.mark.parametrize("quality,reliability", [
    (0.0, 1.0), (1.0, 0.0), (0.02, 1.0), (float("nan"), 1.0),
])
def test_unqualified_effective_weights_rejected(quality, reliability):
    control = _run([])
    actual = _run([_packet(quality=quality, reliability=reliability)])
    assert actual[:3] == control[:3]
    assert actual[2] == 0


def test_quality_weights_actual_innovation_not_just_acceptance_flag():
    full = _packet(quality=1.0, reliability=1.0)
    partial = _packet(quality=0.5, reliability=1.0)
    assert full.effective_weight() == pytest.approx(1.0)
    assert partial.effective_weight() == pytest.approx(0.5)
    full_state = _run([full])
    partial_state = _run([partial])
    initial = _run([])
    assert full_state[2] == partial_state[2] == 1
    assert initial[0] < partial_state[0] < full_state[0]


def test_genuine_physical_zero_remains_admissible():
    zero = _run([_packet(value=0.0, quality=1.0)])
    baseline = _run([])
    assert zero[2] == 1
    assert zero[0] != baseline[0]


def test_kalman_variance_respects_small_accepted_qa_weight():
    obs = KalmanObservation(obs_type="ndvi", value=0.0, sigma=0.04, reliability=0.05)
    assert obs.R == pytest.approx(0.04**2 / 0.05)
    with pytest.raises(ValueError):
        KalmanObservation("ndvi", 0.3, sigma=0.04, reliability=0.0).R
