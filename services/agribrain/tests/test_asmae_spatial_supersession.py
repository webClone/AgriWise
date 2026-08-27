from services.agribrain.layer05_asmae.spatial_supersession import (
    attach_spatial_supersession,
    build_spatial_supersession_state,
    spatial_refresh_block_reason,
)


def _snapshot(**changes):
    value = {
        "snapshot_id": "snapshot-1",
        "geometry_hash": "geometry-1",
        "snapshot_age_days": 0.5,
        "plot_state_artifact": {
            "content_hash": "temporal-older",
            "as_of": "2026-07-27T00:00:00+00:00",
        },
    }
    value.update(changes)
    return value


def test_stalled_job_is_not_reported_as_pending():
    assert spatial_refresh_block_reason({"status": "stalled"}) == "spatial_refresh_stalled"
    state = build_spatial_supersession_state(
        current_result={"plot_state_artifact": {"content_hash": "temporal-now"}},
        candidate_snapshot=_snapshot(),
        active_job={"job_id": "job-2", "status": "stalled"},
        current_geometry_hash="geometry-1",
        snapshot_accepted=True,
    )
    assert state["current_temporal_belief_id"] == "temporal-now"
    assert state["last_successful_spatial_belief_id"] == "snapshot-1"
    assert state["active_spatial_job_status"] == "stalled"
    assert state["supersession_reason"] == "active_spatial_job_lease_expired"


def test_geometry_mismatch_is_explicit_and_attached_to_evidence():
    state = build_spatial_supersession_state(
        current_result={"plot_state_artifact": {"content_hash": "temporal-now"}},
        candidate_snapshot=_snapshot(geometry_hash="geometry-old"),
        active_job=None,
        current_geometry_hash="geometry-new",
        snapshot_accepted=False,
    )
    result = attach_spatial_supersession({"asmae_evidence_state": {}}, state)
    assert state["spatial_compatibility"] == "incompatible_geometry"
    assert result["asmae_evidence_state"]["spatial_supersession"] == state
    assert result["last_successful_spatial_belief_id"] == "snapshot-1"


def test_stale_snapshot_is_retained_but_not_current():
    state = build_spatial_supersession_state(
        current_result={"plot_state_artifact": {"content_hash": "temporal-now"}},
        candidate_snapshot=_snapshot(snapshot_age_days=3.0),
        active_job={"job_id": "job-3", "status": "queued"},
        current_geometry_hash="geometry-1",
        snapshot_accepted=True,
        snapshot_stale=True,
    )
    assert state["spatial_compatibility"] == "compatible_but_stale"
    assert state["spatial_snapshot_age"] == 3.0
    assert state["supersession_reason"] == "newer_spatial_refresh_in_progress"
