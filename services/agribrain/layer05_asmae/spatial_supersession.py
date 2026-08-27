"""One explicit contract for temporal belief, spatial snapshot, and active job."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


ACTIVE_JOB_STATUSES = frozenset({"queued", "running"})
TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "superseded"})


def spatial_refresh_block_reason(job: Optional[Mapping[str, Any]]) -> str:
    status = str((job or {}).get("status") or "").lower()
    return {
        "queued": "spatial_refresh_pending",
        "running": "spatial_refresh_pending",
        "stalled": "spatial_refresh_stalled",
        "failed": "spatial_refresh_failed",
        "superseded": "spatial_refresh_superseded",
        "completed": "spatial_refresh_completed_without_compatible_snapshot",
        "not_eligible": "NOT_ELIGIBLE_NO_EXECUTABLE_SPATIAL_SCENE",
    }.get(status, "spatial_refresh_unavailable")


def _temporal_belief_id(result: Mapping[str, Any]) -> Optional[str]:
    artifact = result.get("plot_state_artifact")
    if isinstance(artifact, Mapping):
        for key in ("belief_id", "content_hash", "worldline_event_id"):
            value = artifact.get(key)
            if value:
                return str(value)
    evidence = result.get("asmae_evidence_state")
    if isinstance(evidence, Mapping):
        value = evidence.get("belief_id") or evidence.get("content_hash")
        if value:
            return str(value)
    return None


def _evidence_cutoff(snapshot: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not snapshot:
        return None
    artifact = snapshot.get("plot_state_artifact")
    evidence = snapshot.get("asmae_evidence_state")
    candidates = (
        snapshot.get("spatial_evidence_cutoff"),
        artifact.get("as_of") if isinstance(artifact, Mapping) else None,
        evidence.get("as_of") if isinstance(evidence, Mapping) else None,
        snapshot.get("generated_at"),
    )
    return next((str(value) for value in candidates if value), None)


def build_spatial_supersession_state(
    *,
    current_result: Mapping[str, Any],
    candidate_snapshot: Optional[Mapping[str, Any]],
    active_job: Optional[Mapping[str, Any]],
    current_geometry_hash: str,
    snapshot_accepted: bool,
    snapshot_stale: bool = False,
) -> Dict[str, Any]:
    """Describe competing temporal/spatial artifacts without silently choosing one."""
    snapshot = dict(candidate_snapshot or {})
    job = dict(active_job or {})
    snapshot_id = snapshot.get("snapshot_id") or snapshot.get(
        "intelligence_snapshot_id"
    )
    snapshot_geometry = str(snapshot.get("geometry_hash") or "")
    job_status = str(job.get("status") or "unavailable").lower()

    if not snapshot_id:
        compatibility = "missing"
    elif current_geometry_hash and snapshot_geometry != current_geometry_hash:
        compatibility = "incompatible_geometry"
    elif snapshot_stale:
        compatibility = "compatible_but_stale"
    elif snapshot_accepted:
        compatibility = "compatible_current"
    else:
        compatibility = "incompatible_current_contract"

    is_spatial_result = bool(current_result.get("current_spatial_assimilation") or current_result.get("spatial_raster_available"))
    if is_spatial_result and snapshot_accepted:
        job_status = "completed"

    if job_status == "stalled":
        supersession_reason = "active_spatial_job_lease_expired"
    elif job_status == "failed":
        supersession_reason = "active_spatial_job_failed"
    elif job_status == "superseded":
        supersession_reason = "active_spatial_job_superseded"
    elif job_status == "not_eligible":
        supersession_reason = "NOT_ELIGIBLE_NO_EXECUTABLE_SPATIAL_SCENE"
    elif is_spatial_result and snapshot_accepted:
        supersession_reason = "spatial_snapshot_current"
    elif job_status in ACTIVE_JOB_STATUSES:
        supersession_reason = "newer_spatial_refresh_in_progress"
    elif compatibility == "compatible_current":
        supersession_reason = "spatial_snapshot_current"
    elif compatibility == "compatible_but_stale":
        supersession_reason = "last_successful_spatial_snapshot_stale"
    elif compatibility == "incompatible_geometry":
        supersession_reason = "last_spatial_snapshot_geometry_mismatch"
    elif snapshot_id:
        supersession_reason = "last_spatial_snapshot_contract_mismatch"
    else:
        supersession_reason = "no_successful_spatial_snapshot"

    return {
        "contract_version": "asmae_spatial_supersession_v1",
        "current_temporal_belief_id": _temporal_belief_id(current_result),
        "last_successful_spatial_belief_id": str(snapshot_id) if snapshot_id else None,
        "active_spatial_job_id": str(job.get("job_id")) if job.get("job_id") else None,
        "active_spatial_job_status": job_status,
        "spatial_evidence_cutoff": _evidence_cutoff(snapshot),
        "spatial_snapshot_age": snapshot.get("snapshot_age_days"),
        "spatial_compatibility": compatibility,
        "supersession_reason": supersession_reason,
    }


def attach_spatial_supersession(
    result: Dict[str, Any],
    state: Mapping[str, Any],
) -> Dict[str, Any]:
    resolved = dict(state)
    result["spatial_supersession"] = resolved
    for key in (
        "current_temporal_belief_id",
        "last_successful_spatial_belief_id",
        "active_spatial_job_id",
        "active_spatial_job_status",
        "spatial_evidence_cutoff",
        "spatial_snapshot_age",
        "spatial_compatibility",
        "supersession_reason",
    ):
        result[key] = resolved.get(key)
    evidence = result.get("asmae_evidence_state")
    if not isinstance(evidence, dict):
        evidence = {}
        result["asmae_evidence_state"] = evidence
    evidence["spatial_supersession"] = resolved
    evidence["active_spatial_job_status"] = resolved.get(
        "active_spatial_job_status"
    )
    return result
