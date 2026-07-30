"""Completion-triggered ASMAE -> L1/L2/L10 snapshot reintegration."""

from __future__ import annotations

from typing import Any, Dict, Mapping


REINTEGRATION_CONTRACT_VERSION = "asmae_orchestrator_reintegration_v1"


def _mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            str(key): item for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return {}


def _asmae_from_artifact(artifact: Any) -> Dict[str, Any]:
    layer = getattr(artifact, "layer_1", None)
    output = getattr(layer, "output", None)
    raw = getattr(output, "asmae_output", None)
    if raw is None:
        package = getattr(output, "_context_package", None)
        raw = getattr(package, "asmae_output", None)
    return _mapping(raw)


def rebuild_canonical_plot_snapshot(
    *,
    asmae_result: Mapping[str, Any],
    context: Mapping[str, Any],
    job_id: str,
    manifest_hash: str,
) -> Dict[str, Any]:
    """Re-run downstream layers around one completed ASMAE snapshot.

    The full spatial ASMAE engine is not run again: the reintegration input is
    forced to ``quick_visual`` and consumes the just-published immutable
    snapshot.  Acquisition/L1/L2/L10 are rebuilt so the map and status panels
    share one identity rather than waiting for the next user request.
    """
    result = dict(asmae_result or {})
    snapshot_id = str(result.get("snapshot_id", "") or "")
    if not snapshot_id:
        raise ValueError("completed ASMAE result has no snapshot_id")
    reintegration = _mapping(context.get("orchestrator_reintegration"))
    if reintegration.get("contract_version") != REINTEGRATION_CONTRACT_VERSION:
        raise ValueError("orchestrator reintegration contract is unavailable")
    raw_input = _mapping(reintegration.get("input"))
    required = {
        "plot_id",
        "geometry_hash",
        "date_range",
        "crop_config",
        "operational_context",
        "policy_snapshot",
    }
    missing = sorted(required - set(raw_input))
    if missing:
        raise ValueError(
            "orchestrator reintegration input is incomplete: "
            + ",".join(missing)
        )
    if str(raw_input.get("plot_id")) != str(result.get("plot_id")):
        raise ValueError("reintegration plot identity mismatch")
    if str(raw_input.get("geometry_hash") or "") != str(
        context.get("geometry_hash") or ""
    ):
        raise ValueError("reintegration geometry identity mismatch")

    from orchestrator_v2.intents import Intent
    from orchestrator_v2.runner import run_orchestrator
    from orchestrator_v2.schema import OrchestratorInput

    operational = _mapping(raw_input.get("operational_context"))
    operational.update(
        {
            "asmae_mode": "quick_visual",
            "force_asmae_refresh": False,
            "asmae_worker_reintegration": True,
            "disable_crop_refinement_reschedule": True,
            "expected_asmae_snapshot_id": snapshot_id,
            # Rebuild the policy the user actually queued with the scientific
            # job.  The captured orchestrator input may predate the source
            # policy switch (for example, an initial satellite fallback).
            "source_policy": str(
                context.get("source_policy")
                or operational.get("source_policy")
                or "satellite"
            ),
        }
    )
    orchestrator_input = OrchestratorInput(
        plot_id=str(raw_input["plot_id"]),
        geometry_hash=str(raw_input.get("geometry_hash") or ""),
        date_range=_mapping(raw_input.get("date_range")),
        crop_config=_mapping(raw_input.get("crop_config")),
        operational_context=operational,
        policy_snapshot=_mapping(raw_input.get("policy_snapshot")),
    )
    artifact = run_orchestrator(
        orchestrator_input,
        intent=Intent.UNKNOWN,
        skip_l9=True,
    )
    if not getattr(artifact, "layer_1", None):
        raise ValueError("downstream reintegration produced no Layer 1")
    if not getattr(artifact, "layer_2", None):
        raise ValueError("downstream reintegration produced no Layer 2")
    if not getattr(artifact, "layer_10", None):
        raise ValueError("downstream reintegration produced no Layer 10")
    embedded_asmae = _asmae_from_artifact(artifact)
    embedded_snapshot_id = str(
        embedded_asmae.get("snapshot_id")
        or embedded_asmae.get("intelligence_snapshot_id")
        or ""
    )
    if embedded_snapshot_id != snapshot_id:
        raise ValueError(
            "downstream layers did not consume the completed ASMAE snapshot"
        )

    from orchestrator_v2.run_entrypoint import (
        _attach_snapshot_identity,
        _serialize_l10_output,
    )
    from orchestrator_v2.run_schema import artifact_to_run

    layer10_output = getattr(artifact.layer_10, "output", None)
    layer10_payload = (
        _serialize_l10_output(layer10_output) if layer10_output else {}
    )
    frontend = artifact_to_run(
        artifact,
        surfaces=list(layer10_payload.get("surfaces") or []),
        layer10_detail=layer10_payload,
    )
    frontend.pop("layer10", None)
    # Preserve the complete render-authority contract that the surface route
    # exposes, including state/spatial availability as distinct dimensions.
    for key, value in layer10_payload.items():
        if key not in {"surfaces"}:
            frontend[key] = value
    frontend = _attach_snapshot_identity(
        frontend, orchestrator_input, artifact
    )
    if frontend.get("intelligence_snapshot_id") != snapshot_id:
        raise ValueError("frontend snapshot identity was not propagated")
    frontend["worker_reintegration"] = {
        "contract_version": REINTEGRATION_CONTRACT_VERSION,
        "job_id": job_id,
        "manifest_hash": manifest_hash,
        "status": "completed",
    }

    from .plot_snapshot_store import publish_canonical_plot_snapshot

    head = publish_canonical_plot_snapshot(
        plot_id=orchestrator_input.plot_id,
        geometry_hash=orchestrator_input.geometry_hash,
        snapshot_id=snapshot_id,
        asmae_result=result,
        frontend_payload=frontend,
        job_id=job_id,
        manifest_hash=manifest_hash,
    )

    from .history.worldline_service import PlotWorldlineService

    plot_state = _mapping(result.get("plot_state_artifact"))
    worldline_time = str(
        plot_state.get("as_of") or result.get("as_of") or ""
    ).strip()
    authority_ref = str(
        plot_state.get("authority_level")
        or result.get("authority_level")
        or ""
    ).strip()
    if not worldline_time:
        raise ValueError("canonical snapshot worldline time is unavailable")
    if not authority_ref:
        raise ValueError("canonical snapshot authority is unavailable")

    event = PlotWorldlineService().commit_event(
        plot_id=orchestrator_input.plot_id,
        event_type="CANONICAL_PLOT_SNAPSHOT",
        geometry_hash=orchestrator_input.geometry_hash,
        authority=authority_ref,
        effective_at=worldline_time,
        observation_or_valid_time=worldline_time,
        parent_event_ids=[
            str(value) for value in [result.get("worldline_event_id")]
            if value
        ],
        payload={
            "snapshot_id": snapshot_id,
            "snapshot_ref": head.get("node_ref"),
            "asmae_content_hash": result.get("content_hash"),
            "crop_posterior_lineage": result.get(
                "crop_posterior_lineage"
            ),
            "job_id": job_id,
            "manifest_hash": manifest_hash,
            "orchestrator_run_id": artifact.meta.orchestrator_run_id,
            "orchestrator_artifact_hash": artifact.meta.artifact_hash,
            "layer_run_ids": dict(artifact.lineage_map or {}),
        },
    )
    return {
        "status": "completed",
        "snapshot_id": snapshot_id,
        "snapshot_ref": head.get("node_ref"),
        "worldline_event_id": event.get("event_id"),
        "orchestrator_run_id": artifact.meta.orchestrator_run_id,
        "layer_run_ids": dict(artifact.lineage_map or {}),
    }
