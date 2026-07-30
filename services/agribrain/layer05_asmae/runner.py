"""
ASMAE Runner.

Entry point for ASMAE execution. Handles:
  - Always-on diagnostic computation and independent authority gating
  - Input validation
  - Mode routing
  - Engine instantiation
  - Output serialization
  - Error handling

No ASMAE production claim runs without rollout authority.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import ASMAE_FEATURE_FLAG, ASMAE_MODES, archive_status_ok
from .contracts import validate_contract
from .engine import ASMAEEngine
from .schema import ASMAEInput, ASMAEOutput
from .cache import (
    get_asmae_cache_key,
    deserialize_cached_asmae,
    serialize_and_cache_asmae,
    save_ht_matrix_artifact,
)
from .evidence_capability import prepare_capability_execution_context
from core.observability import observability_registry

logger = logging.getLogger(__name__)


class ASMAERunner:
    """ASMAE execution runner.

    Wraps the ASMAEEngine with permission resolution, input validation,
    and error handling. This is the only public entry point.

    Usage:
        runner = ASMAERunner()
        result = runner.execute(plot_id, run_id, context_dict)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._engine = ASMAEEngine(config=self.config)
        if not self.config.get("disable_job_recovery", False):
            try:
                from .background_jobs import recover_pending_jobs
                recover_pending_jobs()
            except Exception as exc:
                logger.warning("ASMAE job recovery scan failed: %s", exc)

    def is_enabled(self, plot_id: Optional[str] = None) -> bool:
        """Whether scientific computation is allowed (not authority)."""
        return self.execution_permissions(plot_id).get("compute_allowed", False)

    def execution_permissions(self, plot_id: Optional[str] = None) -> Dict[str, Any]:
        """Resolve computation and claim permissions independently."""
        from rollout.rollout_policy import (
            should_render_l10_asmae,
            should_run_asmae,
            should_run_asmae_authority,
            should_run_asmae_visual_shadow,
        )

        valid_plot = bool(plot_id and isinstance(plot_id, str) and plot_id.strip())
        emergency_kill = bool(
            self.config.get("ASMAE_EMERGENCY_KILL_SWITCH", False)
        ) or os.environ.get(
            "ASMAE_EMERGENCY_KILL_SWITCH", "false"
        ).strip().lower() in {"true", "1", "yes", "on"}
        # Diagnostic evidence inspection is always on for a valid plot. The
        # rollout registry governs claims and mutation, not whether science is
        # allowed to inspect the plot's evidence.
        compute_allowed = valid_plot and not emergency_kill
        production_allowed = valid_plot and should_run_asmae_authority(str(plot_id))
        diagnostic_allowed = compute_allowed
        # Diagnostic visualization is an evidence product, not production
        # authority. Every valid, non-killed plot may display a properly
        # labelled spatial posterior; rollout still gates production claims.
        visual_allowed = bool(compute_allowed)
        from rollout.asmae_rollout_registry import (
            ROLLOUT_CONTRACT_VERSION,
            get_rollout_phase,
            get_rollout_state,
        )
        return {
            "compute_allowed": compute_allowed,
            "diagnostic_allowed": diagnostic_allowed,
            "advisory_allowed": diagnostic_allowed,
            "plot_state_publication_allowed": diagnostic_allowed,
            "production_authority_allowed": production_allowed,
            "visual_authority_allowed": visual_allowed,
            "training_export_allowed": production_allowed,
            "permission_contract_version": ROLLOUT_CONTRACT_VERSION,
            "authority_phase": get_rollout_phase(str(plot_id)) if valid_plot else "disabled",
            "rollout_state": get_rollout_state(str(plot_id)) if valid_plot else "not_registered",
            "emergency_kill_active": emergency_kill,
        }

    def _disabled_response(self, plot_id: str, run_id: str) -> Dict[str, Any]:
        """Build and audit the canonical rollout-gate response."""
        from rollout.asmae_rollout_registry import get_rollout_phase, get_rollout_state

        if not plot_id or not isinstance(plot_id, str) or not plot_id.strip():
            execution_status = "rollout_skipped"
            skip_reason = "empty_or_missing_plot_id"
            user_reason = "ASMAE execution requires a valid plot identifier"
        else:
            execution_status = "backend_disabled"
            skip_reason = "global_emergency_kill_switch"
            user_reason = "ASMAE computation is paused by the global emergency kill switch"

        phase = get_rollout_phase(plot_id) if plot_id and isinstance(plot_id, str) and plot_id.strip() else "disabled"
        rollout_state = get_rollout_state(plot_id) if plot_id and isinstance(plot_id, str) and plot_id.strip() else "not_registered"
        try:
            from rollout.validation_ledger import record_asmae_run
            record_asmae_run({
                "plot_id": plot_id or "missing",
                "run_id": run_id,
                "rollout_phase": phase,
                "execution_status": execution_status,
                "visual_status": "not_applicable",
                "skip_reason": skip_reason,
                "eligible_for_asmae_learn": False,
                "cache_status": "bypass",
                "latency_ms": 0.0,
            })
        except Exception as ex:
            logger.error("Failed to write to validation ledger on skip: %s", ex)

        return {
            "status": "disabled",
            "reason": user_reason,
            "plot_id": plot_id,
            "run_id": run_id,
            "asmae_skipped": True,
            "skip_reason": skip_reason,
            "authority_block_reason": skip_reason,
            "rollout_phase": phase,
            "rollout_state": rollout_state,
        }

    def execute(
        self,
        plot_id: str,
        run_id: str,
        context: Dict[str, Any],
        mode: str = "shadow",
    ) -> Dict[str, Any]:
        """Execute ASMAE pipeline with caching, budgets, and observability."""
        # Rollout permission is resolved before reading, adapting, generating,
        # or persisting any real/proxy scene products.
        permissions = self.execution_permissions(plot_id)
        context["_asmae_execution_permissions"] = permissions
        if not permissions["compute_allowed"]:
            logger.info("ASMAE disabled for plot %s by rollout policy", plot_id)
            return self._disabled_response(plot_id, run_id)

        try:
            from .history.worldline_service import PlotWorldlineService

            PlotWorldlineService().hydrate_context(plot_id, context)
        except Exception as exc:
            # Worldline read failure cannot erase current evidence, but is
            # retained as an explicit diagnostic.
            logger.exception("ASMAE worldline hydration failed")
            context["worldline_hydration_error"] = str(exc)

        # Freeze atomic evidence before any input construction, cache lookup,
        # validation, snapshot selection, or worker enqueue.  The normalized
        # context is the only evidence surface the scientific pipeline may
        # execute, and its plan hash is part of durable job identity.
        prepared_context, _ = prepare_capability_execution_context(context)
        context.clear()
        context.update(prepared_context)

        # A latency-bounded visual request never executes the spatial chain.
        # It serves the last completed snapshot (or the cheap resilient
        # plot-state posterior) and queues one deduplicated standard refresh.
        if mode == "quick_visual" and not context.get("is_background_run"):
            try:
                inp = self._build_input(plot_id, run_id, context, mode)
                result = self._serve_quick_visual(
                    inp, context, permissions
                )
                if result.get("quick_visual_source") != "completed_snapshot":
                    result["crop_posterior_lineage"] = context.get(
                        "crop_posterior_lineage"
                    )
                    result["crop_posterior"] = context.get(
                        "crop_posterior", {}
                    )
                    result["crop_lineage_id"] = context.get(
                        "crop_lineage_id"
                    )
                else:
                    result.setdefault("crop_posterior_lineage", None)
                result["orchestrator_parent_run_id"] = context.get(
                    "orchestrator_parent_run_id"
                )
                return result
            except Exception as exc:
                logger.exception("ASMAE quick visual state hydration failed")
                return {
                    "status": "error",
                    "plot_id": plot_id,
                    "run_id": run_id,
                    "reason": "quick_visual_state_hydration_failed:{}".format(exc),
                }

        # Determine if this is an unregistered plot running diagnostic-only shadow run
        from rollout.rollout_policy import should_run_asmae_authority, should_run_asmae_visual_shadow
        is_unregistered_shadow = (
            plot_id is not None
            and not should_run_asmae_authority(plot_id)
            and should_run_asmae_visual_shadow(plot_id)
        )
        if is_unregistered_shadow:
            mode = "quick_visual"

        # Check if scene stack is empty/incomplete or contains no real_raster packages
        l0_packages = context.setdefault("layer0_source_packages", {})
        from layer05_asmae.geometry.scene_stack_builder import _extract_packages
        from layer05_asmae.geometry.layer0_package_adapter import adapt_layer0_package_to_scene_candidate
        
        s2_pkgs = _extract_packages(l0_packages, "sentinel2")
        s1_pkgs = _extract_packages(l0_packages, "sentinel1")
        
        composites = context.get("raster_composites", {})
        s2_candidates_raw = [adapt_layer0_package_to_scene_candidate(p, "sentinel2", composites) for p in s2_pkgs]
        s1_candidates_raw = [adapt_layer0_package_to_scene_candidate(p, "sentinel1", composites) for p in s1_pkgs]
        
        has_real_s2 = any(c.reality == "real_raster" for c in s2_candidates_raw)
        has_real_s1 = any(c.reality == "real_raster" for c in s1_candidates_raw)
        has_any_real = has_real_s2 or has_real_s1
        
        if (is_unregistered_shadow or mode == "quick_visual") and (not has_any_real) and composites:
            from datetime import date
            try:
                start_date_parsed = date.fromisoformat(context.get("start_date", date.today().isoformat()))
                end_date_parsed = date.fromisoformat(context.get("end_date", date.today().isoformat()))
            except Exception:
                start_date_parsed = date.today()
                end_date_parsed = date.today()
            
            # Wipe out old keys to avoid mixing pseudo and scalar packages
            keys_to_delete = [
                "asmae_sentinel2_raw", "sentinel2", "s2", "sentinel2_packages", "s2_packages",
                "asmae_sentinel1_raw", "sentinel1", "s1", "sentinel1_packages", "s1_packages"
            ]
            for k in keys_to_delete:
                l0_packages.pop(k, None)
                
            pseudo_data = self._generate_pseudo_scenes(plot_id, run_id, composites, start_date_parsed, end_date_parsed)
            l0_packages.update(pseudo_data)
            context["is_pseudo"] = True

        # Define budgets per mode
        budget_map = {
            "quick_visual": 150.0,
            "standard": 1000.0,
        }
        budget_ms = budget_map.get(mode, 5000.0)

        # ── Feature flag gate ────────────────────────────────────────
        # ── Mode validation ──────────────────────────────────────────
        if mode not in ASMAE_MODES:
            return {
                "status": "error",
                "reason": f"Invalid mode '{mode}'. Must be one of: {ASMAE_MODES}",
                "plot_id": plot_id,
                "run_id": run_id,
            }

        # ── Input construction ───────────────────────────────────────
        try:
            inp = self._build_input(plot_id, run_id, context, mode)
        except Exception as e:
            logger.error("ASMAE input construction failed: %s", e)
            return {
                "status": "error",
                "reason": f"Input construction failed: {e}",
                "plot_id": plot_id,
                "run_id": run_id,
            }

        # ── Caching: Try loading cached output dictionary ────────────
        cache_status = "miss"
        if mode == "scientific_refresh":
            cache_status = "bypass"
            logger.info("Bypassing ASMAE cache read for scientific_refresh mode")
        else:
            cached_result = deserialize_cached_asmae(inp)
            if cached_result is not None:
                logger.info("ASMAE cache HIT for plot %s", plot_id)
                observability_registry.record(
                    step="asmae",
                    mode=mode,
                    cache_status="hit",
                    latency_ms=0.0,
                    budget_ms=budget_ms,
                    storage_kb=len(json.dumps(cached_result)) / 1024.0,
                )
                
                # Policy B — cache hit creates a new instance wrapper
                original_run_id = cached_result.get("run_id")
                original_generated_at = cached_result.get("generated_at")
                
                cached_result["cache_status"] = "hit"
                cached_result["run_id"] = run_id
                cached_result["cache_source_run_id"] = original_run_id
                cached_result["cached_output_content_hash"] = cached_result.get("content_hash")
                cached_result["cache_key"] = get_asmae_cache_key(inp)
                cached_result["original_generated_at"] = original_generated_at
                cached_result["current_served_at"] = datetime.now(timezone.utc).isoformat()
                cached_result = self._apply_execution_authority(cached_result, permissions)
                
                # Recompute artifact_instance_hash for the current run instance
                new_instance_payload = {
                    "output_content_hash": cached_result.get("content_hash"),
                    "plot_id": cached_result.get("plot_id"),
                    "run_id": run_id,
                    "generated_at": original_generated_at,
                }
                raw = json.dumps(new_instance_payload, sort_keys=True, default=str).encode("utf-8")
                cached_result["artifact_instance_hash"] = hashlib.sha256(raw).hexdigest()
                cached_result["crop_posterior_lineage"] = (
                    inp.crop_posterior_lineage
                )
                cached_result["crop_posterior"] = inp.crop_posterior
                cached_result["crop_lineage_id"] = context.get(
                    "crop_lineage_id"
                )
                cached_result["orchestrator_parent_run_id"] = context.get(
                    "orchestrator_parent_run_id"
                )

                # A standard cache hit is still a completed scientific job.
                # Republish it under the current snapshot contract so an old
                # cache entry can never strand worker reintegration.
                if mode in {"standard", "scientific_refresh"}:
                    commit_fence = context.get('_worker_commit_fence')
                    if callable(commit_fence):
                        commit_fence()
                    from .cache import stable_value_hash
                    from .snapshot_store import publish_latest_snapshot

                    snapshot_context = {
                        key: value for key, value in context.items()
                        if key not in {
                            "run_id", "request_id", "served_at",
                            "is_background_run",
                            "_asmae_execution_permissions",
                            '_worker_commit_fence',
                        }
                    }
                    cached_result["snapshot_ref"] = publish_latest_snapshot(
                        cached_result,
                        context_hash=stable_value_hash(snapshot_context),
                        geometry_hash=inp.geometry_hash,
                    )
                    cached_result["snapshot_status"] = "published"
                    try:
                        from .history.worldline_service import (
                            PlotWorldlineService,
                        )
                        event = PlotWorldlineService().commit_asmae_result(
                            cached_result,
                            geometry_hash=inp.geometry_hash,
                            snapshot_ref=cached_result["snapshot_ref"],
                        )
                        cached_result["worldline_event_id"] = event.get(
                            "event_id"
                        )
                    except Exception as snapshot_event_exc:
                        logger.exception(
                            "Failed to commit cached ASMAE worldline event"
                        )
                        cached_result["worldline_publish_error"] = str(
                            snapshot_event_exc
                        )
                
                # Record in validation ledger
                try:
                    from rollout.validation_ledger import record_asmae_run
                    from rollout.asmae_rollout_registry import get_rollout_phase
                    from rollout.rollout_policy import should_render_l10_asmae
                    l0_pkg = context.get("layer0_state_package")
                    l0_hash = ""
                    if l0_pkg:
                        if isinstance(l0_pkg, dict):
                            l0_hash = l0_pkg.get("output_hash", "")
                        else:
                            l0_hash = getattr(l0_pkg, "output_hash", "")
                    if not l0_hash:
                        l0_hash = hashlib.sha256(str(l0_pkg).encode("utf-8")).hexdigest()
                        
                    visual_status = "visual_enabled" if should_render_l10_asmae(plot_id) else "visual_disabled"
                    
                    ledger_rec = {
                        "plot_id": plot_id,
                        "run_id": run_id,
                        "rollout_phase": get_rollout_phase(plot_id),
                        "execution_status": "cache_hit",
                        "visual_status": visual_status,
                        "geometry_hash": inp.geometry_hash or "empty_geom_hash",
                        "layer0_output_hash": l0_hash,
                        "asmae_content_hash": cached_result.get("content_hash"),
                        "asmae_artifact_instance_hash": cached_result.get("artifact_instance_hash"),
                        "cache_status": "hit",
                        "latency_ms": 0.0,
                        "artifact_total_bytes": len(json.dumps(cached_result)),
                        "state_summary": {
                            "vigor_mean": cached_result.get("state_summary", {}).get("vigor_mean", 0.0),
                            "canopy_water_mean": cached_result.get("state_summary", {}).get("canopy_water_mean", 0.0),
                            "salinity_stress_mean": cached_result.get("state_summary", {}).get("salinity_stress_mean", 0.0),
                        },
                        "trust_summary": {
                            "confidence_mean": cached_result.get("trust_summary", {}).get("confidence_mean", 1.0),
                            "uncertainty_mean": cached_result.get("trust_summary", {}).get("uncertainty_mean", 0.0),
                            "bma_status": cached_result.get("trust_summary", {}).get("bma_status", "success"),
                            "bma_disagreement": cached_result.get("trust_summary", {}).get("bma_disagreement", 0.0),
                        },
                        "warnings": cached_result.get("warnings", []),
                    }
                    record_asmae_run(ledger_rec)
                except Exception as ex:
                    logger.error("Failed to write to validation ledger on cache hit: %s", ex)
                return cached_result

        # ── Contract validation ──────────────────────────────────────────────
        fatal_violations, spatial_violations, capability_plan = (
            self._validate_contracts(context)
        )

        if fatal_violations:
            logger.warning(
                "ASMAE fatal contract violations for %s: %s",
                plot_id, fatal_violations,
            )
            if mode != "shadow":
                return {
                    "status": "error",
                    "reason": "Contract violations",
                    "violations": fatal_violations,
                    "plot_id": plot_id,
                    "run_id": run_id,
                }

        if spatial_violations:
            logger.warning(
                "ASMAE spatial-capability violations for %s (%d): %s",
                plot_id, len(spatial_violations), spatial_violations[:5],
            )
            # Spatial violations degrade, but do not abort, the job.
            context["_spatial_capability_degraded"] = True
            context["_spatial_capability_violations"] = spatial_violations
            context["_spatial_scene_count_accepted"] = (
                len(capability_plan.spatial_scenes) if capability_plan else 0
            )
        elif capability_plan is not None:
            context["_spatial_capability_degraded"] = False
            context["_spatial_scene_count_accepted"] = (
                len(capability_plan.spatial_scenes)
            )

        # ── Engine execution ─────────────────────────────────────────
        start_time = time.perf_counter()
        try:
            logger.info(
                "ASMAE run starting: plot=%s run=%s mode=%s",
                plot_id, run_id, mode,
            )
            output = self._engine.run(inp)
            
            # Intercept returned chain integrity failures / budget overruns in quick_visual mode
            if mode == "quick_visual" and not context.get("is_background_run") and output.diagnostics and output.diagnostics.get("chain_integrity_error"):
                err_msg = output.diagnostics.get("chain_integrity_message", "BUDGET OVERRUN")
                raise RuntimeError(err_msg)
            
            # Save all operators constructed during the run to disk as NPZ
            operator_refs = []
            for op in getattr(self._engine, "_operators", []):
                if hasattr(op, "H_matrix") and op.H_matrix is not None:
                    ref = save_ht_matrix_artifact(op.operator_id, op.H_matrix)
                    if ref:
                        operator_refs.append(ref)
            output.observation_operator_refs = operator_refs

            logger.info(
                "ASMAE run complete: plot=%s run=%s resolution=%dm",
                plot_id, run_id,
                output.resolution_decision.selected_effective_resolution_m
                if output.resolution_decision else 10,
            )
            
            serialized = self._apply_execution_authority(
                self._serialize_output(output), permissions,
            )
            serialized["crop_posterior_lineage"] = (
                inp.crop_posterior_lineage
            )
            serialized["crop_posterior"] = inp.crop_posterior
            serialized["crop_lineage_id"] = context.get("crop_lineage_id")
            serialized["orchestrator_parent_run_id"] = context.get(
                "orchestrator_parent_run_id"
            )
            
            # Identity tracking on cache miss / bypass
            serialized["cache_status"] = cache_status
            serialized["cache_source_run_id"] = None
            serialized["cached_output_content_hash"] = serialized.get("content_hash")
            serialized["cache_key"] = get_asmae_cache_key(inp)
            serialized["original_generated_at"] = serialized.get("generated_at")
            serialized["current_served_at"] = serialized.get("generated_at")

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Write computed results to cache
            serialized_size = len(json.dumps(serialized))
            commit_fence = context.get('_worker_commit_fence')
            if callable(commit_fence):
                commit_fence()
            serialize_and_cache_asmae(inp, serialized.copy())
            if mode in {"standard", "scientific_refresh"}:
                try:
                    from .cache import stable_value_hash
                    from .snapshot_store import publish_latest_snapshot

                    snapshot_context = {
                        key: value for key, value in context.items()
                        if key not in {
                            "run_id", "request_id", "served_at",
                            "is_background_run", "_asmae_execution_permissions",
                            '_worker_commit_fence',
                        }
                    }
                    serialized["snapshot_ref"] = publish_latest_snapshot(
                        serialized,
                        context_hash=stable_value_hash(snapshot_context),
                        geometry_hash=inp.geometry_hash,
                    )
                    serialized["snapshot_status"] = "published"
                    from .history.worldline_service import PlotWorldlineService

                    worldline = PlotWorldlineService()
                    event = worldline.commit_asmae_result(
                        serialized,
                        geometry_hash=inp.geometry_hash,
                        snapshot_ref=serialized["snapshot_ref"],
                    )
                    serialized["worldline_event_id"] = event.get("event_id")
                except Exception as exc:
                    logger.exception("Failed to publish canonical ASMAE snapshot")
                    serialized["snapshot_publish_error"] = str(exc)

                # Archive lifecycle errors are downstream diagnostics. They
                # must never retroactively label an atomically published
                # snapshot as failed.
                if (
                    context.get("is_background_run")
                    and serialized.get("snapshot_ref")
                ):
                    try:
                        from .history.worldline_service import (
                            PlotWorldlineService,
                        )

                        worldline = PlotWorldlineService()
                        archive_head = worldline.latest_payload(
                            inp.plot_id, "ARCHIVE_POSTERIOR_VALIDATED"
                        )
                        if not archive_head:
                            serialized["archive_refresh"] = (
                                worldline.refresh_archive_from_context(
                                    plot_id=inp.plot_id,
                                    geometry_hash=inp.geometry_hash,
                                    context=context,
                                )
                            )
                    except Exception as archive_exc:
                        logger.exception("ASMAE archive refresh failed")
                        serialized["archive_refresh_error"] = str(
                            archive_exc
                        )

            observability_registry.record(
                step="asmae",
                mode=mode,
                cache_status=cache_status,
                latency_ms=elapsed_ms,
                budget_ms=budget_ms,
                storage_kb=serialized_size / 1024.0,
            )

            # Record in validation ledger
            try:
                from rollout.validation_ledger import record_asmae_run
                from rollout.asmae_rollout_registry import get_rollout_phase
                from rollout.rollout_policy import should_render_l10_asmae
                from .cache import CACHE_DIR, ARTIFACTS_DIR
                l0_pkg = context.get("layer0_state_package")
                l0_hash = ""
                if l0_pkg:
                    if isinstance(l0_pkg, dict):
                        l0_hash = l0_pkg.get("output_hash", "")
                    else:
                        l0_hash = getattr(l0_pkg, "output_hash", "")
                if not l0_hash:
                    l0_hash = hashlib.sha256(str(l0_pkg).encode("utf-8")).hexdigest()
                    
                cache_key = get_asmae_cache_key(inp)
                json_cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")
                npz_cache_path = os.path.join(ARTIFACTS_DIR, "asmae_rasters", f"raster_{cache_key}.npz")
                
                art_json_size = 0
                if os.path.exists(json_cache_path):
                    art_json_size = os.path.getsize(json_cache_path)
                art_npz_size = 0
                if os.path.exists(npz_cache_path):
                    art_npz_size = os.path.getsize(npz_cache_path)
                    
                visual_status = "visual_enabled" if should_render_l10_asmae(plot_id) else "visual_disabled"
                
                ledger_rec = {
                    "plot_id": plot_id,
                    "run_id": run_id,
                    "rollout_phase": get_rollout_phase(plot_id),
                    "execution_status": "executed",
                    "visual_status": visual_status,
                    "geometry_hash": inp.geometry_hash or "empty_geom_hash",
                    "layer0_output_hash": l0_hash,
                    "asmae_content_hash": serialized.get("content_hash"),
                    "asmae_artifact_instance_hash": serialized.get("artifact_instance_hash"),
                    "cache_status": cache_status,
                    "latency_ms": elapsed_ms,
                    "artifact_json_bytes": art_json_size,
                    "artifact_npz_bytes": art_npz_size,
                    "artifact_total_bytes": art_json_size + art_npz_size,
                    "state_summary": {
                        "vigor_mean": serialized.get("state_summary", {}).get("vigor_mean", 0.0),
                        "canopy_water_mean": serialized.get("state_summary", {}).get("canopy_water_mean", 0.0),
                        "salinity_stress_mean": serialized.get("state_summary", {}).get("salinity_stress_mean", 0.0),
                    },
                    "trust_summary": {
                        "confidence_mean": serialized.get("trust_summary", {}).get("confidence_mean", 1.0),
                        "uncertainty_mean": serialized.get("trust_summary", {}).get("uncertainty_mean", 0.0),
                        "bma_status": serialized.get("trust_summary", {}).get("bma_status", "success"),
                        "bma_disagreement": serialized.get("trust_summary", {}).get("bma_disagreement", 0.0),
                    },
                    "warnings": serialized.get("warnings", []),
                }
                record_asmae_run(ledger_rec)
            except Exception as ex:
                logger.error("Failed to write to validation ledger on fresh run: %s", ex)

            return serialized

        except Exception as e:
            if getattr(e, 'worker_lease_lost', False):
                raise
            import traceback as _traceback
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            
            # Intercept budget overrun / failure in quick_visual mode to engage progressive fallback
            if mode == "quick_visual" and not context.get("is_background_run"):
                logger.warning("ASMAE quick_visual failed or timed out: %s. Engaging progressive fallback.", e)
                try:
                    fallback_res = self._progressive_visual_fallback_output(inp, context)
                    
                    # Cache the fallback result
                    serialize_and_cache_asmae(inp, fallback_res.copy())
                    
                    # Spawn background standard ASMAE computation
                    self._run_background_standard_asmae(plot_id, run_id, context)
                    
                    # Record in validation ledger as progressive fallback
                    try:
                        from rollout.validation_ledger import record_asmae_run
                        from rollout.asmae_rollout_registry import get_rollout_phase
                        from rollout.rollout_policy import should_render_l10_asmae
                        
                        visual_status = "visual_enabled" if should_render_l10_asmae(plot_id) else "visual_disabled"
                        
                        ledger_rec = {
                            "plot_id": plot_id,
                            "run_id": run_id,
                            "rollout_phase": get_rollout_phase(plot_id),
                            "execution_status": "executed_progressive_fallback",
                            "visual_status": visual_status,
                            "geometry_hash": inp.geometry_hash or "empty_geom_hash",
                            "cache_status": "progressive_fallback",
                            "latency_ms": elapsed_ms,
                            "error_message": str(e),
                        }
                        record_asmae_run(ledger_rec)
                    except Exception as ex:
                        logger.error("Failed to write to validation ledger on fallback: %s", ex)
                        
                    return fallback_res
                except Exception as fe:
                    logger.error("Failed to generate progressive fallback: %s", fe, exc_info=True)

            observability_registry.record(
                step="asmae",
                mode=mode,
                cache_status="error",
                latency_ms=elapsed_ms,
                budget_ms=budget_ms,
                extra_details={"error": str(e)},
            )
            logger.error("ASMAE engine failed: %s", e, exc_info=True)
            
            # Log failed run to validation ledger
            try:
                from rollout.validation_ledger import record_asmae_run
                from rollout.asmae_rollout_registry import get_rollout_phase
                ledger_rec = {
                    "plot_id": plot_id,
                    "run_id": run_id,
                    "rollout_phase": get_rollout_phase(plot_id) if (plot_id and isinstance(plot_id, str) and plot_id.strip()) else "disabled",
                    "execution_status": "failed",
                    "visual_status": "not_applicable",
                    "error_message": str(e),
                    "eligible_for_asmae_learn": False,
                    "cache_status": cache_status,
                    "latency_ms": elapsed_ms,
                }
                record_asmae_run(ledger_rec)
            except Exception as ex:
                logger.error("Failed to write to validation ledger on failure: %s", ex)

            return {
                "status": "error",
                "reason": f"Engine execution failed: {e}",
                "failure_diagnostics": {
                    "stage": "engine_execution",
                    "exception_type": type(e).__name__,
                    "message": str(e),
                    "traceback": _traceback.format_exc(limit=20),
                },
                "plot_id": plot_id,
                "run_id": run_id,
            }

    def _build_input(
        self,
        plot_id: str,
        run_id: str,
        context: Dict[str, Any],
        mode: str,
    ) -> ASMAEInput:
        """Construct ASMAEInput from orchestrator context."""
        from datetime import date
        from layer05_asmae.history.weather_archive_adapter import normalize_weather_archive

        weather_raw = context.get("weather_archive")
        if weather_raw is None:
            weather_raw = context.get("weather_context")
        if weather_raw is None:
            weather_raw = context.get("weather_consensus")
        if weather_raw is None:
            weather_raw = context.get("weather_records")
        weather = normalize_weather_archive(weather_raw)

        return ASMAEInput(
            plot_id=plot_id,
            run_id=run_id,
            polygon_geojson=context.get("polygon_geojson", {}),
            geometry_hash=context.get("geometry_hash", ""),
            start_date=date.fromisoformat(
                context.get("start_date", date.today().isoformat())
            ),
            end_date=date.fromisoformat(
                context.get("end_date", date.today().isoformat())
            ),
            layer0_source_packages=context.get("layer0_source_packages", {}),
            layer0_state_package=context.get("layer0_state_package"),
            layer1_context_package=context.get("layer1_context_package"),
            coarse_layer_outputs=context.get("coarse_layer_outputs", {}),
            raster_composites=context.get("raster_composites", {}),
            historical_scene_refs=context.get("historical_scene_refs", []),
            archive_metrics=context.get("archive_metrics", {}),
            archive_baselines=context.get("archive_baselines", {}),
            archive_bma=context.get("archive_bma", {}),
            retrovalidation_residuals=context.get("retrovalidation_residuals", {}),
            phenology_envelopes=context.get("phenology_envelopes", {}),
            archive_metrics_status=context.get("archive_metrics_status") or "unavailable",
            archive_metrics_hash=context.get("archive_metrics_hash"),
            archive_posterior=context.get("archive_posterior", {}),
            plot_timeseries=context.get("plot_timeseries", []),
            crop_context=context.get("crop_context", {}),
            crop_posterior=context.get("crop_posterior", {}),
            crop_posterior_lineage=context.get(
                "crop_posterior_lineage"
            ),
            soil_context=context.get("soil_context", {}),
            management_events=context.get("management_events", []),
            user_observations=context.get("user_observations", []),
            mode=mode,
            is_pseudo=context.get("is_pseudo", False),
            source_policy=context.get("source_policy"),
            asmae_scene_fetch_telemetry=context.get("asmae_scene_fetch_telemetry"),
            evidence_capability_contract_version=str(
                context.get("evidence_capability_contract_version", "unknown")
            ),
            capability_plan_hash=str(context.get("capability_plan_hash", "")),
            execution_permissions=context.get("_asmae_execution_permissions", {}),
            permission_contract_version=str(
                context.get("_asmae_execution_permissions", {}).get(
                    "permission_contract_version", "unknown"
                )
            ),
            authority_phase=str(
                context.get("_asmae_execution_permissions", {}).get(
                    "authority_phase", "disabled"
                )
            ),
            rollout_state=str(
                context.get("_asmae_execution_permissions", {}).get(
                    "rollout_state", "not_registered"
                )
            ),
            # Normalized Weather Archive fields (BC.10.17 P0.7)
            weather_archive_status=weather["weather_archive_status"],
            weather_source_reality=weather["weather_source_reality"],
            weather_daily_series=weather["weather_daily_series"],
            weather_archive_hash=weather["weather_archive_hash"],
            missing_variables=weather["missing_variables"],
            variable_completeness=weather["variable_completeness"],
            resource_memory_limit_mb=context.get("resource_memory_limit_mb"),
        )

    def _validate_contracts(
        self, context: Dict[str, Any]
    ) -> tuple:
        """Validate dict and canonical object inputs against live contracts.

        Returns:
            (fatal_violations, spatial_violations, capability_plan)

        ``fatal_violations`` abort the entire job.
        ``spatial_violations`` degrade spatial capability only — the temporal
        posterior, archive and prior conditioning continue.
        ``capability_plan`` is an immutable CapabilityPlan for manifest identity.
        """
        from .evidence_capability import build_capability_plan, CapabilityPlan

        fatal_violations: list = []
        spatial_violations: list = []
        capability_plan: Optional[CapabilityPlan] = None

        def public_mapping(value: Any) -> Dict[str, Any]:
            if isinstance(value, dict):
                mapped = dict(value)
                if (
                    mapped.get("__asmae_manifest_type__") == "object_v1"
                    and isinstance(mapped.get("fields"), dict)
                ):
                    return dict(mapped["fields"])
                return mapped
            if hasattr(value, "__dict__"):
                return {
                    key: item for key, item in vars(value).items()
                    if not key.startswith("_")
                }
            return {}

        # ── Layer 0: field-based capability classification ────────────────
        # No family-name substring matching. The classifier inspects explicit
        # fields (transform, width, height, scene_id, crs, obs_type, …).
        # Only SPATIAL_PROVIDER_SCENE nodes are validated against the spatial
        # scene contract. Temporal observations are never sent through it.
        l0 = context.get("layer0_source_packages", {})
        raster_composites = context.get("raster_composites", {}) or {}
        if not isinstance(l0, dict):
            fatal_violations.append("layer0_source_packages must be a mapping")
        else:
            capability_plan = build_capability_plan(
                l0, raster_composites, context.get("plot_timeseries") or []
            )

            # Validate only classified spatial scenes against the spatial contract
            for node in capability_plan.spatial_scenes:
                # The immutable node binds the exact raw value. Positional
                # rescans can silently bind a different scene after filtering.
                raw_pkg = node.raw_value
                if raw_pkg is None:
                    spatial_violations.append(
                        f"layer0_source_packages.{node.source_family}"
                        f"[{node.evidence_node_id}]: bound scene is missing"
                    )
                    continue

                d = public_mapping(raw_pkg)
                # If the package already carries all required keys use it directly
                scene_contract = d if all(
                    k in d for k in (
                        "scene_id", "sensor", "acquisition_time", "crs",
                        "transform", "width", "height", "band_refs",
                        "mask_refs", "qa_score",
                    )
                ) else None

                if scene_contract is None:
                    from .geometry.layer0_package_adapter import (
                        adapt_layer0_package_to_scene_candidate,
                    )
                    family_lower = node.source_family.lower()
                    source = (
                        "sentinel1"
                        if ("sentinel1" in family_lower or "s1" in family_lower)
                        else "sentinel2"
                    )
                    candidate = adapt_layer0_package_to_scene_candidate(
                        raw_pkg, source, raster_composites
                    )
                    if not candidate or not candidate.scene_id or not candidate.crs:
                        # Adapter cannot produce a spatial scene from this package
                        spatial_violations.append(
                            f"layer0_source_packages.{node.source_family}"
                            f"[{node.evidence_node_id}]: adapter returned no scene"
                        )
                        continue
                    scene_contract = {
                        "scene_id": candidate.scene_id,
                        "sensor": "S1" if source == "sentinel1" else "S2",
                        "acquisition_time": (
                            candidate.acquisition_datetime.isoformat()
                            if hasattr(candidate.acquisition_datetime, "isoformat")
                            else candidate.acquisition_datetime
                        ),
                        "crs": candidate.crs,
                        "transform": candidate.transform,
                        "width": candidate.width,
                        "height": candidate.height,
                        "band_refs": candidate.band_refs or candidate.band_arrays,
                        "mask_refs": candidate.mask_refs or {},
                        "qa_score": (candidate.qa_metrics or {}).get(
                            "valid_fraction"
                        ),
                    }

                for violation in validate_contract("layer0_to_asmae", scene_contract):
                    spatial_violations.append(
                        f"layer0_source_packages.{node.source_family}"
                        f"[{node.evidence_node_id}]: {violation}"
                    )

        # ── Layer 1 — fatal if present but unreadable ─────────────────────
        l1 = context.get("layer1_context_package")
        if l1 is not None:
            l1_mapping = public_mapping(l1)
            if not l1_mapping:
                fatal_violations.append(
                    "layer1_context_package is not contract-readable"
                )
            else:
                fatal_violations.extend(
                    f"layer1_context_package: {item}"
                    for item in validate_contract("layer1_to_asmae", l1_mapping)
                )

        coarse = context.get("coarse_layer_outputs")
        if coarse is not None:
            coarse_mapping = public_mapping(coarse)
            if not coarse_mapping:
                fatal_violations.append(
                    "coarse_layer_outputs is not contract-readable"
                )
            else:
                fatal_violations.extend(
                    f"coarse_layer_outputs: {item}"
                    for item in validate_contract(
                        "coarse_priors_to_asmae", coarse_mapping
                    )
                )

        return fatal_violations, spatial_violations, capability_plan


    def _serialize_output(self, output: ASMAEOutput) -> Dict[str, Any]:
        """Serialize ASMAEOutput to dict for storage/API.

        V79A: Uses diagnostics to determine status and production_usable.
        """
        diag = output.diagnostics or {}

        # V79A: status override from diagnostics
        if diag.get("status_override"):
            status = diag["status_override"]
        elif diag.get("skeleton"):
            status = "partial"
        elif diag.get("scene_stack_mode") == "no_scenes":
            status = "partial"
        elif diag.get("scene_stack_mode") == "degraded_mean_only":
            status = "partial"
        elif diag.get("production_usable") is False:
            status = "partial"
        else:
            status = "success"

        production_usable = diag.get("production_usable", False)
        layer1_export_allowed = diag.get("layer1_export_allowed", False)
        state_update_allowed = diag.get("state_update_allowed", False)
        weak_label_export_allowed = diag.get("weak_label_export_allowed", False)
        visual_allowed = diag.get("visual_allowed", False)
        diagnostic_only = diag.get("diagnostic_only", True)

        rd = output.resolution_decision
        return {
            "status": status,
            "production_usable": production_usable,
            "layer1_export_allowed": layer1_export_allowed,
            "state_update_allowed": state_update_allowed,
            "weak_label_export_allowed": weak_label_export_allowed,
            "visual_allowed": visual_allowed,
            "diagnostic_only": diagnostic_only,
            "state_availability": diag.get("state_availability", "UNAVAILABLE"),
            "authority_level": diag.get("authority_level", "DIAGNOSTIC_ONLY"),
            "posterior_available": bool(diag.get("posterior_available", False)),
            "schema_version": output.schema_version,
            "plot_id": output.plot_id,
            "run_id": output.run_id,
            "generated_at": output.generated_at.isoformat()
                if output.generated_at else None,
            "resolution_decision": {
                "selected_effective_resolution_m": rd.selected_effective_resolution_m,
                "selected_visual_resolution_m": rd.selected_visual_resolution_m,
                "candidate_resolutions_tested_m": rd.candidate_resolutions_tested_m,
                "safe_for_1m_claim": rd.safe_for_1m_claim,
                "demoted_candidates": rd.demoted_candidates,
            } if rd else None,
            "raster_maps": output.raster_maps,
            "uncertainty_maps": output.uncertainty_maps,
            "confidence_maps": output.confidence_maps,
            "retrovalidation_maps": output.retrovalidation_maps,
            "bma_maps": output.bma_maps,
            "microzone_graph_ref": output.microzone_graph_ref,
            "state_timeline_ref": output.state_timeline_ref,
            "observation_operator_refs": output.observation_operator_refs,
            "weak_labels": output.weak_labels,
            "certification": {
                "certification_level": output.certification.certification_level,
                "max_certified_resolution_m": output.certification.max_certified_resolution_m,
                "retro_score": output.certification.retro_score,
            } if output.certification else None,
            "content_hash": output.content_hash(),
            "artifact_instance_hash": output.artifact_instance_hash(),
            "diagnostics": output.diagnostics,
            "provenance": output.provenance,
            "grid_spec": getattr(output, "grid_spec", {}),
            "asmae_evidence_state": getattr(output, "asmae_evidence_state", {}),
            "asmae_feature_pack": getattr(output, "asmae_feature_pack", {}),
            "one_meter_advisory_coverage_pct": diag.get("one_meter_advisory_coverage_pct", 0.0),
            "one_meter_certified_coverage_pct": diag.get("one_meter_certified_coverage_pct", 0.0),
            "model_assisted_2_5m_coverage_pct": diag.get("model_assisted_2_5m_coverage_pct", 0.0),
            "generalized_5m_coverage_pct": diag.get("generalized_5m_coverage_pct", 0.0),
            "one_meter_advisory_mask": diag.get("one_meter_advisory_mask"),
            "model_assisted_2_5m_mask": diag.get("model_assisted_2_5m_mask"),
            "generalized_5m_mask": diag.get("generalized_5m_mask"),
            "effective_resolution_map": diag.get("effective_resolution_map"),
            "approval_reasons_by_cell": diag.get("approval_reasons_by_cell"),
            "asmae_proof": getattr(output, "asmae_proof", {}),
            "plot_state_artifact": getattr(output, "plot_state_artifact", {}),
        }

    def _apply_execution_authority(
        self,
        result: Dict[str, Any],
        permissions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolve authority identically for fresh and cached artifacts."""
        result = dict(result)
        diagnostic_allowed = bool(permissions.get("diagnostic_allowed", False))
        production_allowed = bool(permissions.get("production_authority_allowed", False))
        visual_allowed = bool(permissions.get("visual_authority_allowed", False))
        training_allowed = bool(permissions.get("training_export_allowed", False))

        production_usable = bool(result.get("production_usable", False)) and production_allowed
        result["production_usable"] = production_usable
        result["layer1_export_allowed"] = bool(result.get("layer1_export_allowed", False)) and production_allowed
        result["state_update_allowed"] = bool(result.get("state_update_allowed", False)) and production_allowed
        result["weak_label_export_allowed"] = bool(result.get("weak_label_export_allowed", False)) and training_allowed
        result["visual_allowed"] = bool(result.get("visual_allowed", False)) and visual_allowed
        result["diagnostic_only"] = not production_usable
        result["advisory_allowed"] = diagnostic_allowed and bool(permissions.get("advisory_allowed", False))
        result["plot_state_publication_allowed"] = bool(
            permissions.get("plot_state_publication_allowed", False)
        )
        if not training_allowed:
            result["weak_labels"] = []

        diagnostics = result.get("diagnostics")
        if isinstance(diagnostics, dict):
            diagnostics["production_usable"] = result["production_usable"]
            diagnostics["layer1_export_allowed"] = result["layer1_export_allowed"]
            diagnostics["state_update_allowed"] = result["state_update_allowed"]
            diagnostics["weak_label_export_allowed"] = result["weak_label_export_allowed"]
            diagnostics["visual_allowed"] = result["visual_allowed"]
            diagnostics["diagnostic_only"] = result["diagnostic_only"]
            diagnostics["prescription_driver_allowed"] = production_usable
            diagnostics["authority_resolution"] = {
                "permission_contract_version": permissions.get("permission_contract_version"),
                "authority_phase": permissions.get("authority_phase"),
                "rollout_state": permissions.get("rollout_state"),
                "resolved_on_serve": True,
            }
        evidence = result.get("asmae_evidence_state")
        if isinstance(evidence, dict):
            evidence["production_usable"] = production_usable
            evidence["authority"] = "production" if production_usable else "diagnostic"

        artifact = result.get("plot_state_artifact")
        if isinstance(artifact, dict) and artifact:
            from .plot_state import intersect_artifact_authority

            scientific_usable = bool(
                (result.get("diagnostics") or {}).get(
                    "scientific_production_usable",
                    artifact.get("production_usable", False),
                )
            )
            artifact = intersect_artifact_authority(
                artifact,
                production_allowed=production_allowed,
                scientific_production_usable=scientific_usable,
            )
            result["plot_state_artifact"] = artifact
            result["state_availability"] = artifact.get(
                "state_availability", result.get("state_availability", "UNAVAILABLE")
            )
            result["authority_level"] = artifact.get(
                "authority_level", "NONE"
            )
            result["posterior_available"] = bool(artifact.get("posterior"))
            if isinstance(evidence, dict):
                evidence["state_availability"] = result["state_availability"]
                evidence["authority_level"] = result["authority_level"]
                evidence["posterior_available"] = result["posterior_available"]

        result["execution_permissions"] = dict(permissions)
        result["authority_resolved_at"] = datetime.now(timezone.utc).isoformat()
        return result

    def _generate_pseudo_scenes(self, plot_id: str, run_id: str, raster_composites: dict, start_date, end_date) -> dict:
        """BC.10.13 — Generates proxy scene packages from valid raster composites.

        HARD RULES:
        1. If NDVI composite is missing or empty → returns no S2 packages.
        2. If SAR composite is missing or empty  → returns no S1 packages.
        3. No constant band arrays (0.1, 0.15, 0.2, 0.25, 0.3, 0.35).
        4. Only bands derivable from available composites are written.
        5. NIR/RED reconstruction requires NDVI composite + fixed NIR anchor.
           NDVI alone cannot uniquely reconstruct reflectance anchors; using
           a fixed NIR ≈ 0.40 is explicitly acknowledged as an approximation.
        """
        import numpy as np
        import os
        from types import SimpleNamespace
        from datetime import datetime, timedelta, timezone
        from layer0.archive.raster_store import RasterStore

        ndvi_data = raster_composites.get("NDVI") or raster_composites.get("NDVI_CLEAN") or {}
        pixel_array = ndvi_data.get("pixel_array") or ndvi_data.get("values")

        # RULE 1 — no NDVI → no S2 packages at all.
        have_ndvi = (
            pixel_array
            and isinstance(pixel_array, list)
            and len(pixel_array) > 0
            and isinstance(pixel_array[0], list)
            and len(pixel_array[0]) > 0
        )

        pseudo_dir = os.path.join(
            "services", "agribrain", "artifacts", "pseudo_scenes",
            f"{plot_id}_{run_id}"
        )
        raster_store = RasterStore()
        end_dt = datetime.combine(end_date, datetime.min.time(), timezone.utc)

        # ── S2 pseudo packages ──────────────────────────────────────────────
        s2_packages = []
        if have_ndvi:
            H = len(pixel_array)
            W = len(pixel_array[0])
            grid_spec = ndvi_data.get("grid_spec") or {}

            ndvi_arr = np.clip(np.array(pixel_array, dtype=np.float32), -0.99, 0.99)

            # Do not fabricate fake optical bands (B04/B08) from NDVI (BC.10.17 P0.10)
            bands_s2: dict[str, np.ndarray] = {
                "ndvi": ndvi_arr,
            }

            ndmi_data = raster_composites.get("NDMI") or {}
            ndmi_pixel = ndmi_data.get("pixel_array") or ndmi_data.get("values")
            if (ndmi_pixel and isinstance(ndmi_pixel, list)
                    and len(ndmi_pixel) == H and isinstance(ndmi_pixel[0], list)
                    and len(ndmi_pixel[0]) == W):
                ndmi_arr = np.clip(np.array(ndmi_pixel, dtype=np.float32), -0.99, 0.99)
                bands_s2["ndmi"] = ndmi_arr

            qual_data = raster_composites.get("QUALITY") or {}
            qual_pixel = qual_data.get("pixel_array") or qual_data.get("values")
            if (qual_pixel and isinstance(qual_pixel, list)
                    and len(qual_pixel) == H and isinstance(qual_pixel[0], list)
                    and len(qual_pixel[0]) == W):
                bands_s2["SCL"] = np.array(qual_pixel, dtype=np.float32)

            os.makedirs(pseudo_dir, exist_ok=True)

            # One aggregate composite is one independent observation. Its
            # timestamp is an as-of time, never an invented acquisition date.
            for i in range(1):
                scene_id = "composite_observation_s2"
                acq_dt = end_dt

                local_refs: dict[str, str] = {}
                for b_name, arr_data in bands_s2.items():
                    path = os.path.join(pseudo_dir, f"{scene_id}_{b_name}.npz")
                    raster_store.save_band(path, arr_data)
                    local_refs[b_name] = path

                metadata = SimpleNamespace(
                    scene_id=scene_id,
                    acquisition_datetime=acq_dt,
                    crs=grid_spec.get("crs", "EPSG:4326"),
                    band_list=list(bands_s2.keys()),
                    width=W,
                    height=H,
                    transform=grid_spec.get("transform", (10.0, 0.0, 0.0, 0.0, -10.0, 0.0)),
                    temporal_basis="aggregate",
                    independent_observation_count=1,
                )
                qa = SimpleNamespace(
                    quality_class=SimpleNamespace(value="good"),
                    valid_fraction=1.0,
                    usable=True,
                )
                pkg = SimpleNamespace(
                    metadata=metadata,
                    source_reality="raster_composite_proxy",
                    packets=[{
                        "cloud_cover": 0.0,
                        "data_status": "composite_derived",
                        "source_reality": "raster_composite_proxy",
                        "usable": True,
                        "usable_for_1m_approval": False,
                        "diagnostic_only": True,
                        "temporal_basis": "aggregate",
                        "independent_observation_count": 1,
                        "ndvi_mean": float(np.mean(ndvi_arr)),
                        "ndmi_mean": float(np.mean(np.array(ndmi_pixel, dtype=np.float32)) if ndmi_pixel else 0.0),
                    }],
                    qa=qa,
                    local_cache_refs=local_refs,
                    cloud_cover=0.0,
                    production_usable=False,
                    diagnostic_only=True,
                    real_provider_product=False,
                )
                s2_packages.append(pkg)

        # ── S1 pseudo packages ──────────────────────────────────────────────
        s1_packages = []
        sar_data = raster_composites.get("SAR") or {}
        sar_pixel = sar_data.get("pixel_array") or sar_data.get("values")

        # RULE 2 — no SAR composite → no S1 packages.
        have_sar = (
            sar_pixel
            and isinstance(sar_pixel, list)
            and len(sar_pixel) > 0
            and isinstance(sar_pixel[0], list)
            and len(sar_pixel[0]) > 0
        )
        if have_sar:
            Hs = len(sar_pixel)
            Ws = len(sar_pixel[0])
            sar_gs = sar_data.get("grid_spec") or {}
            vv_arr = np.array(sar_pixel, dtype=np.float32)

            os.makedirs(pseudo_dir, exist_ok=True)

            for i in range(1):
                scene_id = "composite_observation_s1"
                acq_dt = end_dt

                local_refs = {}
                for b_name, arr_data in {"VV": vv_arr}.items():
                    path = os.path.join(pseudo_dir, f"{scene_id}_{b_name}.npz")
                    raster_store.save_band(path, arr_data)
                    local_refs[b_name] = path

                metadata = SimpleNamespace(
                    scene_id=scene_id,
                    acquisition_datetime=acq_dt,
                    crs=sar_gs.get("crs", "EPSG:4326"),
                    band_list=["VV"],
                    width=Ws,
                    height=Hs,
                    transform=sar_gs.get("transform", (10.0, 0.0, 0.0, 0.0, -10.0, 0.0)),
                    temporal_basis="aggregate",
                    independent_observation_count=1,
                )
                qa = SimpleNamespace(
                    quality_class=SimpleNamespace(value="good"),
                    valid_fraction=1.0,
                    usable=True,
                )
                pkg = SimpleNamespace(
                    metadata=metadata,
                    source_reality="raster_composite_proxy",
                    packets=[{
                        "data_status": "composite_derived",
                        "source_reality": "raster_composite_proxy",
                        "usable": True,
                        "usable_for_1m_approval": False,
                        "diagnostic_only": True,
                        "temporal_basis": "aggregate",
                        "independent_observation_count": 1,
                        "vv_db_mean": float(np.mean(vv_arr)),
                    }],
                    qa=qa,
                    local_cache_refs=local_refs,
                    production_usable=False,
                    diagnostic_only=True,
                    real_provider_product=False,
                )
                s1_packages.append(pkg)

        return {
            "experimental_s2_proxy": s2_packages,
            "experimental_s1_proxy": s1_packages,
        }

    def _progressive_visual_fallback_output(
        self, inp: ASMAEInput, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return structured unavailability; never fabricate a fallback grid."""
        logger.info("ASMAE quick visual unavailable for plot %s", inp.plot_id)
        now_str = datetime.now(timezone.utc).isoformat()
        latest_snapshot = (
            context.get("latest_certified_snapshot_ref")
            or (getattr(inp, "archive_posterior", {}) or {}).get("artifact_ref")
        )
        failure_reason = context.get(
            "asmae_failure_reason", "asmae_quick_visual_timeout"
        )
        identity = {
            "plot_id": inp.plot_id,
            "run_id": inp.run_id,
            "reason": failure_reason,
            "latest_certified_snapshot_ref": latest_snapshot,
        }
        content_hash = hashlib.sha256(
            json.dumps(identity, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return {
            "status": "unavailable",
            "production_usable": False,
            "layer1_export_allowed": False,
            "state_update_allowed": False,
            "weak_label_export_allowed": False,
            "visual_allowed": False,
            "diagnostic_only": True,
            "state_availability": "UNAVAILABLE",
            "authority_level": "NONE",
            "posterior_available": False,
            "schema_version": "asmae_v3_resilient_evidence_chain",
            "plot_id": inp.plot_id,
            "run_id": inp.run_id,
            "generated_at": now_str,
            "resolution_decision": None,
            "raster_maps": {},
            "uncertainty_maps": {},
            "confidence_maps": {},
            "retrovalidation_maps": {},
            "bma_maps": {},
            "microzone_graph_ref": "",
            "state_timeline_ref": "",
            "observation_operator_refs": [],
            "weak_labels": [],
            "certification": None,
            "content_hash": content_hash,
            "artifact_instance_hash": hashlib.sha256(
                f"{inp.plot_id}_{inp.run_id}".encode("utf-8")
            ).hexdigest(),
            "diagnostics": {
                "progressive_fallback": False,
                "synthetic_raster_emitted": False,
                "fallback_reason": failure_reason,
                "production_usable": False,
                "visual_allowed": False,
                "diagnostic_only": True,
                "posterior_available": False,
                "state_availability": "UNAVAILABLE",
                "stage_status": {
                    "current_scene_assimilation": "failed",
                    "plot_level_state": "unavailable",
                    "spatial_raster": "unavailable",
                },
                "latest_certified_snapshot_ref": latest_snapshot,
                "refresh_job_status": context.get(
                    "asmae_refresh_job_status", "not_queued"
                ),
            },
            "provenance": {
                "completed_at": now_str,
                "failure_stages": context.get(
                    "asmae_failure_stages", [failure_reason]
                ),
            },
            "grid_spec": {},
            "one_meter_advisory_coverage_pct": 0.0,
            "one_meter_certified_coverage_pct": 0.0,
            "model_assisted_2_5m_coverage_pct": 0.0,
            "generalized_5m_coverage_pct": 0.0,
            "one_meter_advisory_mask": None,
            "model_assisted_2_5m_mask": None,
            "generalized_5m_mask": None,
            "effective_resolution_map": None,
            "approval_reasons_by_cell": None,
            "cache_status": "miss",
            "cache_source_run_id": None,
            "cache_key": get_asmae_cache_key(inp),
            "original_generated_at": now_str,
            "current_served_at": now_str,
            "asmae_evidence_state": {
                "state": "unavailable",
                "state_availability": "UNAVAILABLE",
                "scene_stack_mode": "unavailable",
                "posterior_available": False,
                "production_usable": False,
                "current_spatial_assimilation": False,
                "real_asmae_evidence": False,
                "allowed_outputs": [],
                "reason": failure_reason,
                "authority": "none",
            },
            "asmae_feature_pack": {"state_proof": []},
            "asmae_proof": {
                "state_availability": "UNAVAILABLE",
                "authority_level": "NONE",
                "synthetic_raster_emitted": False,
                "feature_proof": {
                    "requested": [],
                    "available": [],
                    "assimilated": [],
                    "missing": [],
                    "drop_reasons": {"spatial_raster": failure_reason},
                },
            },
        }

    def _run_background_standard_asmae(self, plot_id: str, run_id: str, context: Dict[str, Any]):
        """Persist and enqueue a restart-recoverable external standard job."""
        from .background_jobs import enqueue_standard_job

        prepared_context, _ = prepare_capability_execution_context(context)

        return enqueue_standard_job(
            plot_id=plot_id,
            run_id=run_id,
            context=prepared_context,
            config=self.config,
        )

    def _serve_quick_visual(
        self,
        inp: ASMAEInput,
        context: Dict[str, Any],
        permissions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Serve a completed snapshot or a cheap, strictly non-spatial state."""
        from .snapshot_store import load_latest_snapshot
        from .background_jobs import latest_compatible_job, latest_job_for_plot
        from .job_manifest import JOB_RUNNER_CONTRACT_VERSION
        from .spatial_supersession import (
            attach_spatial_supersession,
            build_spatial_supersession_state,
            spatial_refresh_block_reason,
        )

        refresh = None
        candidate_snapshot = load_latest_snapshot(inp.plot_id)
        snapshot = candidate_snapshot
        if (
            snapshot
            and str(snapshot.get("geometry_hash") or "")
            != str(inp.geometry_hash or "")
        ):
            snapshot = None
        compatible_job = latest_compatible_job(
            inp.plot_id,
            geometry_hash=inp.geometry_hash,
            capability_plan_hash=str(context.get("capability_plan_hash", "")),
            worker_contract_version=JOB_RUNNER_CONTRACT_VERSION,
        )
        expected_snapshot_id = str(
            context.get("expected_asmae_snapshot_id", "") or ""
        )
        reintegration_snapshot = bool(
            context.get("asmae_worker_reintegration") is True
            and expected_snapshot_id
            and snapshot
            and str(snapshot.get("snapshot_id", "")) == expected_snapshot_id
        )
        if not (
            snapshot
            and (
                reintegration_snapshot
                or (
                    compatible_job
                    and compatible_job.get("status") == "completed"
                    and str(compatible_job.get("final_snapshot_id", ""))
                    == str(snapshot.get("snapshot_id", ""))
                )
                or (
                    snapshot.get("geometry_hash") == inp.geometry_hash
                    and bool(snapshot.get("surfaces"))
                )
            )
        ):
            # Plot snapshots from older evidence/worker contracts are never
            # presented as current completed ASMAE results.
            snapshot = None
        max_age_days = float(self.config.get("asmae_snapshot_max_age_days", 1.0))
        if snapshot is not None:
            result = dict(snapshot)
            age = result.get("snapshot_age_days")
            stale = not isinstance(age, (int, float)) or float(age) > max_age_days
            artifact = dict(result.get("plot_state_artifact") or {})
            if stale and artifact:
                artifact["state_availability"] = "LAST_KNOWN_GOOD_STALE"
                artifact["current_spatial_assimilation"] = False
                artifact["production_usable"] = False
                artifact["stale_age_days"] = age
                artifact["reason"] = "latest_known_good_snapshot_is_stale"
                from .plot_state import intersect_artifact_authority
                artifact = intersect_artifact_authority(
                    artifact,
                    production_allowed=False,
                    scientific_production_usable=False,
                )
                result["plot_state_artifact"] = artifact
                result["state_availability"] = "LAST_KNOWN_GOOD_STALE"
                result["authority_level"] = artifact["authority_level"]
                result["production_usable"] = False
                result["state_update_allowed"] = False
                result["layer1_export_allowed"] = False
                result["weak_label_export_allowed"] = False
                result["snapshot_status"] = "stale"
            if stale or context.get("force_asmae_refresh"):
                refresh = self._run_background_standard_asmae(
                    inp.plot_id, inp.run_id, context
                )
            # A request may reference an immutable snapshot, but cannot rename
            # the execution that produced it.
            result["publication_run_id"] = result.get("run_id")
            result["request_run_id"] = inp.run_id
            result["quick_visual_source"] = "completed_snapshot"
            result["refresh_job"] = refresh
            active_job = latest_job_for_plot(inp.plot_id)
            attach_spatial_supersession(
                result,
                build_spatial_supersession_state(
                    current_result=result,
                    candidate_snapshot=candidate_snapshot,
                    active_job=active_job,
                    current_geometry_hash=inp.geometry_hash,
                    snapshot_accepted=True,
                    snapshot_stale=stale,
                ),
            )
            return self._apply_execution_authority(result, permissions)

        # No completed snapshot exists. Compute only the inexpensive resilient
        # plot posterior; this path cannot construct operators, a graph, or a
        # raster.
        from .provenance import ASMAEProvenance

        provenance = ASMAEProvenance(
            run_id=inp.run_id,
            plot_id=inp.plot_id,
            geometry_hash=inp.geometry_hash,
            mode="quick_visual",
            started_at=datetime.now(timezone.utc),
        )
        refresh = self._run_background_standard_asmae(
            inp.plot_id, inp.run_id, context
        )
        durable_job = latest_job_for_plot(inp.plot_id)
        refresh_status = str((refresh or {}).get("status", "") or (durable_job or {}).get("status", ""))
        refresh_truth = durable_job or refresh
        if refresh_status in ("failed", "degraded", "error"):
            self._engine._spatial_block_reason = "spatial_refresh_failed"
            self._engine._spatial_refresh_failure_code = str(
                (refresh or {}).get("failure_code") or (refresh or {}).get("reason") or (durable_job or {}).get("error") or "failed"
            )
        else:
            self._engine._spatial_block_reason = spatial_refresh_block_reason(
                refresh_truth
            )

        output = self._engine._no_scene_output(inp, provenance, None)
        result = self._serialize_output(output)
        result["quick_visual_source"] = "resilient_plot_state"
        result["snapshot_status"] = "missing"
        result["refresh_job"] = refresh
        result["cache_status"] = "bypass"
        result["current_served_at"] = datetime.now(timezone.utc).isoformat()
        attach_spatial_supersession(
            result,
            build_spatial_supersession_state(
                current_result=result,
                candidate_snapshot=candidate_snapshot,
                active_job=refresh_truth,
                current_geometry_hash=inp.geometry_hash,
                snapshot_accepted=False,
            ),
        )
        return self._apply_execution_authority(result, permissions)



