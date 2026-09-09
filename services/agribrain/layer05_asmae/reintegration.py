"""Completion-triggered ASMAE -> L1/L2/L10 snapshot reintegration."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


REINTEGRATION_CONTRACT_VERSION = "asmae_orchestrator_reintegration_v2_terminal_publication"


def _mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            str(key): item for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return {}


def _canonical_worldline_namespace(
    context: Mapping[str, Any], plot_namespace: Any
) -> str:
    """Resolve the one namespace used by the ASMAE and snapshot events.

    Canonical worldlines are scoped by ``tenant / farm / plot``.  A legacy
    ``"default"`` namespace here makes an otherwise valid ASMAE event look
    missing during reintegration because the parent lives under the farm
    namespace.  Fail closed if a durable manifest tries to bind a different
    namespace instead of silently creating a second worldline.
    """
    farm_id = str(getattr(plot_namespace, "farm_id", "") or "").strip()
    declared = str(context.get("worldline_namespace") or farm_id).strip()
    if not farm_id:
        raise ValueError("reintegration farm namespace is unavailable")
    if declared != farm_id:
        raise ValueError("reintegration worldline namespace mismatch")
    return farm_id


def _asmae_from_artifact(artifact: Any) -> Dict[str, Any]:
    layer = getattr(artifact, "layer_1", None)
    output = getattr(layer, "output", None)
    raw = getattr(output, "asmae_output", None)
    if raw is None:
        package = getattr(output, "_context_package", None)
        raw = getattr(package, "asmae_output", None)
    return _mapping(raw)


def _mark_completed_publication(frontend: Dict[str, Any], job_id: str) -> None:
    """Ensure an immutable completed snapshot cannot retain queued/running UI state."""
    def mark_supersession_complete(value: Any) -> None:
        if not isinstance(value, dict):
            return
        value["active_spatial_job_id"] = job_id
        value["active_spatial_job_status"] = "completed"
        value["supersession_reason"] = "completed_snapshot_current"

    display = frontend.get("source_policy_display_state")
    if isinstance(display, dict):
        plot_state = display.get("asmaePlotState")
        if isinstance(plot_state, dict):
            plot_state["activeSpatialJobId"] = job_id
            plot_state["activeSpatialJobStatus"] = "completed"
            plot_state["activeSpatialJobStage"] = "complete"
            plot_state["activeSpatialJobProgressPct"] = 100
            mark_supersession_complete(plot_state.get("spatialSupersession"))
            plot_state.pop("spatialRefreshFailure", None)
    for key in ("asmae_evidence_state", "core_asmae_evidence_state", "spatial_supersession"):
        state = frontend.get(key)
        if isinstance(state, dict):
            state["active_spatial_job_id"] = job_id
            state["active_spatial_job_status"] = "completed"
            state["active_spatial_job_stage"] = "complete"
            state["active_spatial_job_progress_pct"] = 100
            mark_supersession_complete(state.get("spatial_supersession"))


def _published_run_lineage(frontend: Mapping[str, Any]) -> Dict[str, Any]:
    """Read the exact run lineage frozen into a frontend publication."""
    payload = _mapping(frontend)
    audit = _mapping(payload.get("audit"))
    raw_layers = audit.get("lineage_map")
    if not isinstance(raw_layers, Mapping):
        raw_layers = payload.get("layer_run_ids")
    if not isinstance(raw_layers, Mapping):
        raw_layers = {}
    return {
        "orchestrator_run_id": str(
            audit.get("orchestrator_run_id")
            or payload.get("orchestrator_run_id")
            or payload.get("agribrain_run_id")
            or payload.get("run_id")
            or ""
        ),
        "orchestrator_artifact_hash": str(
            audit.get("artifact_hash")
            or payload.get("orchestrator_artifact_hash")
            or ""
        ),
        "layer_run_ids": {
            str(key): str(value)
            for key, value in raw_layers.items()
            if value is not None
        },
    }


def _commit_canonical_snapshot_event(
    *,
    result: Mapping[str, Any],
    plot_namespace: Any,
    geometry_hash: str,
    worldline_namespace: str,
    head: Mapping[str, Any],
    job_id: str,
    manifest_hash: str,
    parent_event_id: str = "",
    run_lineage: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Commit the final worldline edge from immutable publication metadata."""
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
    if result.get("production_usable") is not True:
        authority_ref = "DIAGNOSTIC_NO_STATE_UPDATE"
    if not worldline_time:
        raise ValueError("canonical snapshot worldline time is unavailable")
    if not authority_ref:
        raise ValueError("canonical snapshot authority is unavailable")

    lineage = _mapping(run_lineage)
    parent = str(
        parent_event_id or result.get("worldline_event_id") or ""
    ).strip()
    return PlotWorldlineService().commit_event(
        plot_id=str(getattr(plot_namespace, "plot_id", "") or ""),
        event_type="CANONICAL_PLOT_SNAPSHOT",
        geometry_hash=str(geometry_hash or ""),
        authority=authority_ref,
        effective_at=worldline_time,
        observation_or_valid_time=worldline_time,
        tenant_id=str(getattr(plot_namespace, "tenant_id", "") or ""),
        namespace=worldline_namespace,
        parent_event_ids=[parent] if parent else [],
        payload={
            "snapshot_id": result.get("snapshot_id"),
            "snapshot_ref": head.get("node_ref") or head.get("snapshot_ref"),
            "asmae_content_hash": result.get("content_hash"),
            "crop_posterior_lineage": result.get("crop_posterior_lineage"),
            "crop_worldline_event_id": result.get(
                "crop_worldline_event_id"
            ),
            "phenology_worldline_event_id": result.get(
                "phenology_worldline_event_id"
            ),
            "job_id": job_id,
            "manifest_hash": manifest_hash,
            "publication_receipt_ref": head.get("publication_receipt_ref"),
            "publication_receipt_hash": head.get("publication_receipt_hash"),
            "orchestrator_run_id": lineage.get("orchestrator_run_id"),
            "orchestrator_artifact_hash": lineage.get(
                "orchestrator_artifact_hash"
            ),
            "layer_run_ids": dict(lineage.get("layer_run_ids") or {}),
        },
    )


def _is_reusable_publication(
    head: Mapping[str, Any],
    *,
    snapshot_id: str,
    job_id: str,
    manifest_hash: str,
) -> bool:
    """Return true only for this job's fully validated immutable publication."""
    if (
        head.get("snapshot_kind") != "asmae"
        or head.get("snapshot_id") != snapshot_id
        or str(head.get("job_id") or head.get("publication_job_id") or "")
        != str(job_id)
        or str(
            head.get("manifest_hash")
            or head.get("publication_manifest_hash")
            or ""
        )
        != str(manifest_hash)
    ):
        return False
    validation = _mapping(head.get("validation"))
    return all(
        validation.get(key) is True
        for key in (
            "nodeValid",
            "publicationValid",
            "receiptValid",
            "inventoryValid",
            "bindingValid",
            "lineageValid",
            "schemaValid",
            "contractValid",
            "publicationStatusValid",
        )
    )


def rebuild_canonical_plot_snapshot(
    *,
    asmae_result: Mapping[str, Any],
    context: Mapping[str, Any],
    job_id: str,
    manifest_hash: str,
    parent_event_id: str = "",
) -> Dict[str, Any]:
    """Re-run downstream layers around one completed ASMAE snapshot.

    The full spatial ASMAE engine is not run again: the reintegration input is
    forced to ``quick_visual`` and consumes the just-published immutable
    snapshot.  Acquisition/L1/L2/L10 are rebuilt so the map and status panels
    share one identity rather than waiting for the next user request.
    """
    result = dict(asmae_result or {})
    # Scientific completion is bound to the crop/phenology evidence heads that
    # were frozen into the durable job.  Carry those identities through every
    # publication artifact; downstream reintegration must never silently swap
    # them for content-equivalent events created by a later orchestrator run.
    result.setdefault(
        "crop_worldline_event_id",
        context.get("crop_worldline_event_id"),
    )
    result.setdefault(
        "phenology_worldline_event_id",
        context.get("phenology_worldline_event_id"),
    )
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

    from services.agribrain.common.plot_namespace import (
        _coerce_namespace,
    )
    raw_namespace = raw_input.get("plot_namespace")
    plot_namespace = _coerce_namespace(
        raw_namespace if isinstance(raw_namespace, Mapping) else str(raw_input.get("plot_id") or ""),
        tenant_id=str(raw_input.get("tenant_id") or context.get("tenant_id") or ""),
        farm_id=str(raw_input.get("farm_id") or context.get("farm_id") or ""),
    )
    durable_namespace = _coerce_namespace(
        context.get("plot_namespace")
        if isinstance(context.get("plot_namespace"), Mapping)
        else str(context.get("plot_id") or result.get("plot_id") or ""),
        tenant_id=str(context.get("tenant_id") or ""),
        farm_id=str(context.get("farm_id") or ""),
    )
    if plot_namespace != durable_namespace:
        raise ValueError("reintegration durable namespace mismatch")
    if plot_namespace.plot_id != str(result.get("plot_id") or ""):
        raise ValueError("reintegration result namespace mismatch")
    worldline_namespace = _canonical_worldline_namespace(
        context, plot_namespace
    )

    # A worker may crash after atomically publishing node/publication/receipt
    # but before committing the final worldline edge or terminal job record.
    # Reuse that exact validated publication on retry. Re-running downstream
    # layers would create new run IDs and collide with the immutable job-bound
    # frontend publication even though the scientific snapshot is identical.
    from .plot_snapshot_store import load_latest_plot_snapshot

    existing_head = load_latest_plot_snapshot(
        plot_namespace, str(raw_input.get("geometry_hash") or "")
    )
    if existing_head and _is_reusable_publication(
        existing_head,
        snapshot_id=snapshot_id,
        job_id=job_id,
        manifest_hash=manifest_hash,
    ):
        lineage = _published_run_lineage(
            _mapping(existing_head.get("frontend_payload"))
        )
        event = _commit_canonical_snapshot_event(
            result=result,
            plot_namespace=plot_namespace,
            geometry_hash=str(raw_input.get("geometry_hash") or ""),
            worldline_namespace=worldline_namespace,
            head=existing_head,
            job_id=job_id,
            manifest_hash=manifest_hash,
            parent_event_id=parent_event_id,
            run_lineage=lineage,
        )
        return {
            "status": "completed",
            "snapshot_id": snapshot_id,
            "snapshot_ref": existing_head.get("node_ref")
            or existing_head.get("snapshot_ref"),
            "publication_receipt_ref": existing_head.get(
                "publication_receipt_ref"
            ),
            "publication_receipt_hash": existing_head.get(
                "publication_receipt_hash"
            ),
            "worldline_event_id": event.get("event_id"),
            "orchestrator_run_id": lineage.get("orchestrator_run_id"),
            "layer_run_ids": dict(lineage.get("layer_run_ids") or {}),
            "publication_reused": True,
            "crop_worldline_event_id": result.get(
                "crop_worldline_event_id"
            ),
            "phenology_worldline_event_id": result.get(
                "phenology_worldline_event_id"
            ),
        }

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
            "asmae_replay_crop_posterior": dict(
                context.get("crop_posterior") or {}
            ),
            "asmae_replay_crop_posterior_lineage": str(
                context.get("crop_posterior_lineage") or ""
            ),
            "asmae_replay_crop_lineage_id": str(
                context.get("crop_lineage_id") or ""
            ),
            "asmae_replay_crop_worldline_event_id": str(
                context.get("crop_worldline_event_id") or ""
            ),
            "asmae_replay_phenology_posterior": dict(
                context.get("phenology_posterior") or {}
            ),
            "asmae_replay_phenology_posterior_hash": str(
                context.get("phenology_posterior_hash") or ""
            ),
            "asmae_replay_phenology_worldline_event_id": str(
                context.get("phenology_worldline_event_id") or ""
            ),
            "asmae_replay_crop_evidence_ledger": dict(
                context.get("crop_evidence_ledger") or {}
            ),
            "asmae_replay_crop_evidence_ledger_hash": str(
                context.get("crop_evidence_ledger_hash") or ""
            ),
            "asmae_replay_crop_influence_manifest": dict(
                context.get("crop_influence_manifest") or {}
            ),
            "asmae_replay_crop_influence_manifest_hash": str(
                context.get("crop_influence_manifest_hash") or ""
            ),
            "asmae_replay_pre_asmae_layer2a_context": {
                key: context.get(key)
                for key in (
                    "pre_asmae_layer2a_status",
                    "pre_asmae_layer2a_reason",
                    "pre_asmae_layer2a_input_receipt",
                    "pre_asmae_layer2a_input_receipt_hash",
                    "phenology_posterior",
                    "phenology_posterior_hash",
                    "crop_season_evidence_receipt",
                    "crop_season_evidence_receipt_hash",
                    "crop_active_acquisition_plan",
                    "crop_active_acquisition_plan_hash",
                    "layer2a_run_id",
                )
                if context.get(key) is not None
            },
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
    # The completed worker must be re-integrated against the exact admitted
    # temporal evidence it executed.  A fresh gateway request may be unavailable
    # or may have advanced in time; neither is allowed to erase or replace the
    # frozen weather forcings behind this snapshot.
    replay_timeseries = [
        dict(row) for row in (context.get("plot_timeseries") or [])
        if isinstance(row, Mapping)
    ]
    if replay_timeseries:
        operational["asmae_replay_plot_timeseries"] = replay_timeseries
        operational["asmae_replay_capability_plan_hash"] = str(
            context.get("capability_plan_hash") or ""
        )
    field_geometry = _mapping(raw_input.get("field_geometry"))
    polygon_geojson = _mapping(raw_input.get("polygon_geojson"))
    if (
        result.get("visual_allowed") is True
        and bool(result.get("raster_maps"))
        and not field_geometry
        and not polygon_geojson
    ):
        raise ValueError(
            "reintegration frozen field geometry is unavailable"
        )
    orchestrator_input = OrchestratorInput(
        plot_namespace=plot_namespace,
        geometry_hash=str(raw_input.get("geometry_hash") or ""),
        date_range=_mapping(raw_input.get("date_range")),
        crop_config=_mapping(raw_input.get("crop_config")),
        operational_context=operational,
        policy_snapshot=_mapping(raw_input.get("policy_snapshot")),
        field_geometry=field_geometry or None,
        polygon_geojson=polygon_geojson or None,
        evidence_set_hash=str(raw_input.get("evidence_set_hash") or "") or None,
        worldline_head_hash=str(raw_input.get("worldline_head_hash") or "") or None,
        scene_manifest_hash=str(raw_input.get("scene_manifest_hash") or "") or None,
        crop_cycle_context=raw_input.get("crop_cycle_context"),
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
    layer2_output = getattr(artifact.layer_2, "output", None)
    layer2_provenance = _mapping(
        getattr(layer2_output, "provenance", None)
    )
    expected_crop_lineage = str(
        result.get("crop_posterior_lineage") or ""
    )
    if (
        not expected_crop_lineage
        or str(layer2_provenance.get("crop_posterior_lineage") or "")
        != expected_crop_lineage
    ):
        raise ValueError(
            "downstream Layer 2 did not preserve frozen crop lineage"
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
    canonical_layer10_payload = frontend.pop("layer10", {})
    # Preserve the complete render-authority contract that the surface route
    # exposes, including state/spatial availability as distinct dimensions.
    # Only overlay the authorization-aware copy returned by artifact_to_run;
    # the raw component payload may contain shadow action-shaped content.
    for key, value in canonical_layer10_payload.items():
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
    frontend["scientific_evidence_lineage"] = {
        "crop_posterior_lineage": expected_crop_lineage,
        "crop_worldline_event_id": result.get(
            "crop_worldline_event_id"
        ),
        "phenology_worldline_event_id": result.get(
            "phenology_worldline_event_id"
        ),
        "replay_mode": "exact_frozen_worldline_events",
    }
    _mark_completed_publication(frontend, job_id)

    from .job_manifest import JOB_RUNNER_CONTRACT_VERSION
    from .plot_snapshot_store import publish_canonical_plot_snapshot

    head = publish_canonical_plot_snapshot(
        namespace=orchestrator_input.plot_namespace,
        plot_id=orchestrator_input.plot_id,
        tenant_id=orchestrator_input.tenant_id,
        farm_id=orchestrator_input.farm_id,
        geometry_hash=orchestrator_input.geometry_hash,
        snapshot_id=snapshot_id,
        asmae_result=result,
        frontend_payload=frontend,
        job_id=job_id,
        manifest_hash=manifest_hash,
        execution_identity={
            "worker_contract_version": JOB_RUNNER_CONTRACT_VERSION,
            "capability_contract_version": str(
                context.get("evidence_capability_contract_version") or ""
            ),
            "capability_plan_hash": str(context.get("capability_plan_hash") or ""),
        },
    )
    run_lineage = {
        "orchestrator_run_id": artifact.meta.orchestrator_run_id,
        "orchestrator_artifact_hash": artifact.meta.artifact_hash,
        "layer_run_ids": dict(artifact.lineage_map or {}),
        "crop_worldline_event_id": result.get("crop_worldline_event_id"),
        "phenology_worldline_event_id": result.get(
            "phenology_worldline_event_id"
        ),
    }
    event = _commit_canonical_snapshot_event(
        result=result,
        plot_namespace=plot_namespace,
        geometry_hash=orchestrator_input.geometry_hash,
        worldline_namespace=worldline_namespace,
        head=head,
        job_id=job_id,
        manifest_hash=manifest_hash,
        parent_event_id=parent_event_id,
        run_lineage=run_lineage,
    )
    return {
        "status": "completed",
        "snapshot_id": snapshot_id,
        "snapshot_ref": head.get("node_ref"),
        "publication_receipt_ref": head.get("publication_receipt_ref"),
        "publication_receipt_hash": head.get("publication_receipt_hash"),
        "worldline_event_id": event.get("event_id"),
        "orchestrator_run_id": artifact.meta.orchestrator_run_id,
        "layer_run_ids": dict(artifact.lineage_map or {}),
        "crop_worldline_event_id": result.get(
            "crop_worldline_event_id"
        ),
        "phenology_worldline_event_id": result.get(
            "phenology_worldline_event_id"
        ),
    }
