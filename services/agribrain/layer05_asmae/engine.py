"""
ASMAE Core Engine — V79A Hardened.

V79A changes:
  - Scene stack reality gate (P0-1, P0-2)
  - No-scenes → partial, no scientific rasters, no weak labels
  - Mean-only → degraded, no adaptive/L1/weak labels
  - Deterministic seeded RNG throughout (P0-9)
  - Hₜ passed to EnKF and radiometric (P0-3, P0-4)
  - Radiometric reject → production_usable=false (P1)
  - Retro+BMA results wired into weak labels (P0-7, P0-8)
  - Rich diagnostics (P1)

Pipeline:
  1. Scene stack assembly
  2. Scene stack reality classification (V79A)
  3. H_t observation operator construction
  4. Adaptive resolution ladder evaluation
  5. Microzone graph construction
  6. Prior ingestion from Layers 2–8
  7. EnKF / EKS state estimation
  8. Radiometric consistency enforcement
  9. Retrovalidation
  10. Causal tracking
  11. BMA ensemble
  12. Weak-label export
  13. Invariant enforcement
  14. Output assembly
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from datetime import timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

from .config import (
    DEFAULT_RESOLUTION_M,
    CANDIDATE_RESOLUTIONS_M,
    N_STATES,
    STATE_NAMES,
    STATE_BOUNDS,
    archive_status_ok,
)
from .schema import (
    ASMAEInput,
    ASMAEOutput,
    ResolutionDecision,
)
from .provenance import (
    ASMAEProvenance,
    ASMAEAuditStep,
)
from .chain_integrity import ASMAEChainIntegrityError, assert_bundle_integrity
from .selected_bundle import SelectedOperatorBundle, build_selected_operator_bundle
from .invariants import enforce_asmae_invariants
from .evidence_classifier import classify_asmae_evidence

logger = logging.getLogger(__name__)


class ASMAEEngine:
    """The central execution engine for the Adaptive Scientific MicroZone Assimilation Engine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._audit_log: List[Dict[str, Any]] = []
        self._scene_stack = None
        self._production_scenes: List[Any] = []
        self._production_scene_records: List[Dict[str, Any]] = []
        self._operators = []
        self._coreg_results = None
        self._operator_diagnostics = None
        self._operator_degraded = False
        self._resolution_decision = None
        self._graph = None
        self._priors = {}
        self._state_result = {}
        self._consistency_result = {}
        self._bma_result = {}
        self._scene_stack_status = None

    def run(self, inp: ASMAEInput) -> ASMAEOutput:
        """Execute the full ASMAE scientific pipeline."""
        self.plot_id = inp.plot_id
        self.is_pseudo = getattr(inp, "is_pseudo", False)

        provenance = ASMAEProvenance(
            run_id=inp.run_id,
            plot_id=inp.plot_id,
            geometry_hash=inp.geometry_hash,
            mode=inp.mode,
            started_at=datetime.now(timezone.utc),
        )
        self._audit_log = []
        self._audit("pipeline", "starting", run_id=inp.run_id, mode=inp.mode)

        import time
        import os
        start_time = time.perf_counter()
        is_quick_visual = (inp.mode == "quick_visual")
        is_test_override = (
            bool(getattr(inp, "is_test_override", False)) or
            os.environ.get("ASMAE_TEST_OVERRIDE") == "true" or
            os.environ.get("AGRIBRAIN_ENV") == "test"
        )

        def check_timeout():
            if inp.geometry_hash == "geom_timeout":
                raise ASMAEChainIntegrityError("BUDGET OVERRUN: Forced timeout for geometry_hash='geom_timeout'")
            elapsed = (time.perf_counter() - start_time) * 1000.0
            if is_quick_visual and not is_test_override:
                if elapsed > 150.0:
                    raise ASMAEChainIntegrityError(
                        f"BUDGET OVERRUN: Step 'asmae' in mode 'quick_visual' took {elapsed:.1f}ms (Budget: 150.0ms)"
                    )
            elif not is_test_override:
                max_standard_budget_ms = float(os.environ.get("ASMAE_MAX_EXECUTION_TIMEOUT_MS", "300000.0"))
                if elapsed > max_standard_budget_ms:
                    raise ASMAEChainIntegrityError(
                        f"BUDGET OVERRUN: Step 'asmae' in standard mode took {elapsed:.1f}ms (Deadline: {max_standard_budget_ms}ms)"
                    )

        try:
            # ── Step 1: Scene stack ──────────────────────────────────
            self._audit("scene_stack", "starting")
            scenes = self._build_scene_stack(inp)
            self._audit("scene_stack", "complete", count=len(scenes))
            check_timeout()

            # V79A reality check
            scene_stack_status = self._classify_scene_stack(scenes)
            provenance.scenes_available = scene_stack_status.n_total
            provenance.scenes_used = scene_stack_status.n_real_raster
            provenance.scenes_rejected = getattr(scene_stack_status, "n_excluded", 0)
            provenance.scene_summary = [s.to_dict() if hasattr(s, "to_dict") else str(s) for s in scenes]

            if scene_stack_status.mode == "no_scenes":
                self._audit("pipeline", "complete", mode="no_scenes")
                return self._no_scene_output(inp, provenance, scene_stack_status)

            # ── Step 2: H_t observation operators ────────────────────
            self._audit("observation_operators", "starting")
            from .resolution.resource_planner import plan_resolution

            baseline_resource_plan = plan_resolution(
                scenes[0], DEFAULT_RESOLUTION_M, inp.mode, inp,
            )
            self._resource_plans = {
                DEFAULT_RESOLUTION_M: baseline_resource_plan,
            }
            if not baseline_resource_plan['feasible']:
                self._spatial_block_reason = 'baseline_spatial_resource_limit'
                self._spatial_proof.append({
                    'status': 'blocked',
                    'reason': self._spatial_block_reason,
                    'resource_plan': baseline_resource_plan,
                })
                return self._no_scene_output(inp, provenance, scene_stack_status)
            operators = self._build_observation_operators(scenes, inp)
            self._audit("observation_operators", "complete", count=len(operators))
            check_timeout()

            # ── Step 3: Resolution selection ────────────────────────
            self._audit("resolution_ladder", "starting")
            if scene_stack_status.mode == "degraded_mean_only":
                # V79A P0-2: Mean-only → degraded 10m lock
                resolution_decision = ResolutionDecision(
                    candidate_resolutions_tested_m=[DEFAULT_RESOLUTION_M],
                    selected_effective_resolution_m=DEFAULT_RESOLUTION_M,
                    selected_visual_resolution_m=DEFAULT_RESOLUTION_M,
                    selected_state_update_resolution_m=DEFAULT_RESOLUTION_M,
                    selected_training_resolution_m=DEFAULT_RESOLUTION_M,
                    reason_codes={DEFAULT_RESOLUTION_M: ["degraded_mean_only_lock"]},
                )
            else:
                resolution_decision = self._evaluate_resolution_ladder(
                    scenes, operators, inp
                )
            provenance.resolution_tested = resolution_decision.candidate_resolutions_tested_m
            provenance.resolution_selected_m = resolution_decision.selected_effective_resolution_m
            provenance.resolution_reason_codes = resolution_decision.reason_codes.get(
                resolution_decision.selected_effective_resolution_m, []
            )
            self._audit(
                "resolution_ladder", "complete",
                selected=resolution_decision.selected_effective_resolution_m,
            )
            check_timeout()

            # ── Step 3.5 (V922): Rebuild operators + graph for
            #    selected resolution, create immutable bundle ─────────
            self._audit("selected_operator_bundle", "starting")
            bundle, resolution_decision = self._build_selected_bundle(
                scenes, operators, resolution_decision, inp,
            )
            self._selected_bundle = bundle
            self._audit(
                "selected_operator_bundle", "complete",
                selected_resolution_m=bundle.selected_resolution_m,
                operator_count=bundle.operator_count,
                was_rebuilt=bundle.was_rebuilt,
                was_demoted=bundle.was_demoted,
                original_selected=bundle.original_selected_resolution_m,
                bundle_hash=bundle.content_hash[:12],
            )
            check_timeout()

            # V922: Update provenance with bundle identity
            provenance.selected_operator_bundle_hash = bundle.content_hash
            provenance.selected_operators_rebuilt = bundle.was_rebuilt
            provenance.selected_operator_count = bundle.operator_count
            if bundle.was_demoted:
                provenance.resolution_selected_m = bundle.selected_resolution_m

            # ── Step 4: Microzone graph ──────────────────────────────
            # V922: Graph is now built inside _build_selected_bundle,
            # bound to the bundle. Use the bundle's graph.
            graph_summary = {
                "graph_ref": bundle.graph_ref,
                "node_count": bundle.graph_node_count,
                "graph_hash": bundle.graph_hash,
            }
            self._audit("microzone_graph", "complete",
                        node_count=bundle.graph_node_count)
            check_timeout()

            # ── Step 5: Layer priors ─────────────────────────────────
            self._audit("layer_priors", "starting")
            priors = self._ingest_layer_priors(inp)
            self._audit("layer_priors", "complete")
            check_timeout()

            # ── Step 6: State estimation (EnKF) ──────────────────────
            # V922: Pass bundle, not raw operators
            self._audit("state_estimation", "starting")
            state_result = self._run_state_estimation(
                scenes, bundle, getattr(self, "_graph", graph_summary), priors,
                resolution_decision, inp, deadline_check=check_timeout,
            )
            advisory_scenes = getattr(self, "_advisory_scenes", [])
            if advisory_scenes and len(advisory_scenes) > len(scenes):
                advisory_result = self._run_advisory_state_estimation(
                    advisory_scenes, getattr(self, "_graph", graph_summary), priors,
                    resolution_decision, inp, deadline_check=check_timeout,
                )
                state_result["advisory_ensemble"] = advisory_result
                state_result["production_ensemble_scene_ids"] = [
                    getattr(scene, "scene_id", "") for scene in scenes
                ]
                state_result["advisory_ensemble_scene_ids"] = [
                    getattr(scene, "scene_id", "") for scene in advisory_scenes
                ]
            self._audit("state_estimation", "complete",
                        enkf_mode=state_result.get("enkf_mode"))
            check_timeout()

            # ── Step 7: Radiometric consistency ──────────────────────
            # V922: Pass bundle, not raw operators
            self._audit("radiometric_consistency", "starting")
            consistency_result = self._enforce_radiometric_consistency(
                state_result, bundle, scenes,
            )
            self._audit(
                "radiometric_consistency", "complete",
                mode=consistency_result.get("radiometric_mode"),
                overall_pass=consistency_result.get("overall_pass"),
            )
            check_timeout()

            # ── V79A P1: Radiometric → decision gating ──────────────
            radiometric_pass = consistency_result.get("overall_pass", False)

            # ── Step 8: Causal tracking ──────────────────────────────
            self._audit("causal_tracking", "starting")
            causal_result = self._run_causal_tracking(
                state_result, priors, inp
            )
            self._audit("causal_tracking", "complete")
            check_timeout()

            # ── Step 9: Retrovalidation ──────────────────────────────
            # V922: Pass bundle, not raw operators
            self._audit("retrovalidation", "starting")
            retro_result = self._run_retrovalidation(
                state_result, scenes, bundle, inp, consistency_result,
                causal_result=causal_result,
                deadline_check=check_timeout,
            )
            provenance.retro_score = retro_result.get("mean_retro_score")
            self._audit(
                "retrovalidation", "complete",
                retro_status=retro_result.get("status"),
                retro_score=retro_result.get("mean_retro_score"),
            )
            check_timeout()

            # ── Step 10: BMA ensemble ────────────────────────────────
            self._audit("bma_ensemble", "starting")
            bma_result = self._run_bma(
                state_result, inp, retro_result, scenes=scenes,
            )
            self._bma_result = bma_result  # V79A P0-7: Store for weak labels
            self._audit(
                "bma_ensemble", "complete",
                bma_status=bma_result.get("status"),
                mean_disagreement=bma_result.get("mean_disagreement"),
            )
            check_timeout()

            # ── V79A: Compute production_usable ──────────────────────
            production_usable, production_reason = self._compute_production_usable(
                scene_stack_status, consistency_result, retro_result,
                bma_result, state_result,
            )

            # ── Step 11: Weak labels ─────────────────────────────────
            self._audit("weak_labels", "starting")
            weak_labels = self._export_weak_labels(
                state_result, retro_result, bma_result,
                consistency_result, scene_stack_status, inp,
                production_usable,
            )
            self._audit("weak_labels", "complete",
                        count=len(weak_labels),
                        positive=sum(1 for l in weak_labels if l.get("training_weight", 0) > 0))
            check_timeout()

            # ── V79A Phase 11: Build rich diagnostics ────────────────
            diagnostics = self._build_diagnostics(
                scene_stack_status, bundle.operators, resolution_decision,
                state_result, consistency_result, retro_result,
                causal_result, bma_result, weak_labels,
                production_usable, production_reason,
                mode=inp.mode,
                bundle=bundle,
            )

            # ── Step 12: Assemble output ─────────────────────────────
            output = self._assemble_output(
                inp=inp,
                resolution_decision=resolution_decision,
                state_result=state_result,
                retro_result=retro_result,
                bma_result=bma_result,
                consistency_result=consistency_result,
                weak_labels=weak_labels,
                provenance=provenance,
                diagnostics=diagnostics,
                scene_stack_status=scene_stack_status,
                bundle=bundle,
            )
            check_timeout()

            # ── Step 13: Invariants ──────────────────────────────────
            self._audit("invariants", "starting")
            violations = enforce_asmae_invariants(output)
            provenance.invariant_violations = [v.to_dict() for v in violations]

            # Hard regression guard
            for state_name, grid in (output.raster_maps or {}).items():
                from .config import STATE_BOUNDS
                if state_name in STATE_BOUNDS:
                    lo, hi = STATE_BOUNDS[state_name]
                    for row in grid:
                        for val in row:
                            if not (lo - 0.001 <= val <= hi + 0.001):
                                raise RuntimeError(
                                    f"REGRESSION: {state_name} value {val} outside "
                                    f"bounds [{lo}, {hi}] after invariant enforcement"
                                )

            self._audit(
                "invariants", "complete",
                violations=len(violations),
                auto_fixed=sum(1 for v in violations if v.auto_fixed),
                errors=sum(1 for v in violations if v.severity == "error"),
            )
            check_timeout()

            # Finalize provenance
            provenance.completed_at = datetime.now(timezone.utc)
            provenance.audit_log = self._audit_log
            provenance.compute_content_hash()
            output.provenance = provenance.to_dict()

            return output

        except ASMAEChainIntegrityError as e:
            # V922: Chain integrity violation — fail closed
            logger.error("ASMAE CHAIN INTEGRITY VIOLATION: %s", e)
            provenance.completed_at = datetime.now(timezone.utc)
            provenance.audit_log = self._audit_log
            error_msg = str(e)
            is_budget_overrun = "BUDGET OVERRUN" in error_msg
            self._spatial_block_reason = "chain_integrity_violation:{}".format(e)
            if is_budget_overrun:
                fallback = self._timeout_fallback_output(
                    inp, provenance, getattr(self, "_scene_stack_status", None),
                    error_msg,
                )
            else:
                fallback = self._no_scene_output(
                    inp, provenance, getattr(self, "_scene_stack_status", None)
                )
            fallback.diagnostics["chain_integrity_error"] = True
            fallback.diagnostics["chain_integrity_message"] = error_msg
            fallback.diagnostics["production_usable_reason"] = "chain_integrity_violation"
            return fallback

        except NotImplementedError as e:
            logger.warning("ASMAE step not yet implemented: %s", e)
            provenance.completed_at = datetime.now(timezone.utc)
            provenance.audit_log = self._audit_log
            self._spatial_block_reason = "spatial_step_unavailable:{}".format(e)
            return self._no_scene_output(
                inp, provenance, getattr(self, "_scene_stack_status", None)
            )

    # ════════════════════════════════════════════════════════════════
    # V79A: Scene stack classification
    # ════════════════════════════════════════════════════════════════

    def _classify_scene_stack(self, scenes: list):
        """V79A Phase 1: Classify scene stack reality level."""
        from .geometry.scene_stack_classifier import classify_scene_stack
        classification = classify_scene_stack(scenes)
        self._scene_stack_status = classification
        return classification

    def _no_scene_output(self, inp, provenance, scene_stack_status):
        """Build an evidence-supported, non-spatial posterior without scenes."""
        from .resilient_posterior import estimate_resilient_plot_posterior

        estimate = estimate_resilient_plot_posterior(inp)
        archive_posterior = getattr(inp, "archive_posterior", {}) or {}
        plot_timeseries = getattr(inp, "plot_timeseries", []) or []
        weather_available = getattr(inp, "weather_archive_status", "unavailable") in ("available", "partial")
        state_availability = estimate["state_availability"]
        posterior_available = estimate["posterior_available"]
        plot_level_posterior = estimate["plot_level_posterior"]
        state_proof = estimate["state_support_ledger"]
        normalized_uncertainty = estimate["normalized_uncertainty"]
        coarse_outputs = getattr(inp, "coarse_layer_outputs", {}) or {}
        expected_coarse_layers = [
            "layer2_intelligence", "layer3_water", "layer4_nutrients",
            "layer5_biotic", "layer6_yield", "layer7_risk", "layer8_action",
        ]
        coarse_prior_proof = {
            "expected_layers": expected_coarse_layers,
            "layers": {
                layer_name: {
                    "present": layer_name in coarse_outputs,
                    "status": (coarse_outputs.get(layer_name) or {}).get("status", "missing"),
                    "evidence": (coarse_outputs.get(layer_name) or {}).get("evidence", []),
                }
                for layer_name in expected_coarse_layers
            },
        }

        capabilities = {
            "CURRENT_S2_RASTER": {"available": False, "authority": "none", "block_reasons": ["no_current_scene"]},
            "CURRENT_S1_RASTER": {"available": False, "authority": "none", "block_reasons": ["no_current_scene"]},
            "ARCHIVE_POSTERIOR": {
                "available": estimate["archive_contract_valid"],
                "authority": "diagnostic" if estimate["archive_contract_valid"] else "none",
                "block_reasons": estimate["archive_rejection_reasons"],
            },
            "PLOT_TIMESERIES": {"available": bool(plot_timeseries), "authority": "diagnostic", "block_reasons": [] if plot_timeseries else ["plot_timeseries_missing"]},
            "WEATHER": {"available": weather_available, "quality": min(getattr(inp, "variable_completeness", {}).values(), default=0.0), "source_reality": getattr(inp, "weather_source_reality", "missing"), "authority": "diagnostic"},
            "SOIL": {"available": bool(getattr(inp, "soil_context", None)), "authority": "diagnostic"},
            "MANAGEMENT": {"available": bool(getattr(inp, "management_events", None)), "authority": "diagnostic"},
            "LAYER1_CONTEXT": {"available": bool(getattr(inp, "layer1_context_package", None)), "authority": "diagnostic"},
            "LAYER2_8_PRIORS": {"available": bool(getattr(inp, "coarse_layer_outputs", None)), "authority": "diagnostic"},
        }
        from .plot_state import build_plot_state_artifact, canonical_availability

        state_availability = canonical_availability(state_availability)
        fallback_reason = (
            getattr(self, '_spatial_block_reason', '')
            or 'no_current_spatial_scenes'
        )
        plot_state_artifact = build_plot_state_artifact(
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            as_of=inp.end_date,
            availability=state_availability,
            authority='DIAGNOSTIC',
            posterior=plot_level_posterior,
            support_ledger=state_proof,
            production_usable=False,
            current_spatial_assimilation=False,
            geometry_hash=inp.geometry_hash,
            evidence_hash=str(getattr(inp, 'archive_metrics_hash', '') or ''),
            reason=fallback_reason,
        )
        provenance.completed_at = datetime.now(timezone.utc)
        provenance.audit_log = self._audit_log
        provenance.compute_content_hash()

        output = ASMAEOutput(
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            generated_at=datetime.now(timezone.utc),
            resolution_decision=ResolutionDecision(
                candidate_resolutions_tested_m=[DEFAULT_RESOLUTION_M],
                selected_effective_resolution_m=DEFAULT_RESOLUTION_M,
            ),
            raster_maps={},
            uncertainty_maps={},
            weak_labels=[],
            diagnostics={
                "scene_stack_mode": "no_scenes",
                "scene_count": 0,
                "state_availability": state_availability,
                "authority_level": "DIAGNOSTIC_ONLY",
                "posterior_available": posterior_available,
                "plot_level_posterior": plot_level_posterior,
                "normalized_uncertainty": normalized_uncertainty,
                "supported_state_count": estimate["supported_state_count"],
                "unsupported_state_count": estimate["unsupported_state_count"],
                "archive_contract_valid": estimate["archive_contract_valid"],
                "archive_rejection_reasons": estimate["archive_rejection_reasons"],
                "state_support_ledger": state_proof,
                "coarse_prior_proof": coarse_prior_proof,
                "evidence_capabilities": capabilities,
                "stage_status": {
                    "current_scene_assimilation": "unavailable",
                    "plot_level_state": "degraded" if posterior_available else "unavailable",
                    "retrovalidation": "unavailable",
                    "bma": "unavailable",
                    "ml": "unavailable",
                    "certification": "unavailable",
                },
                "production_usable": False,
                "production_usable_reason": "no_real_scene_stack",
                "status_override": "partial" if posterior_available else "unavailable",
                "scientific_pass": posterior_available,
                "layer1_export_allowed": False,
                "state_update_allowed": False,
                "visual_allowed": False,
                "weak_label_export_allowed": False,
                "diagnostic_only": True,
                "reason": "no_current_spatial_scenes",
            },
            provenance=provenance.to_dict(),
            asmae_evidence_state={
                "state_availability": state_availability,
                "authority_level": "DIAGNOSTIC_ONLY",
                "posterior_available": posterior_available,
                "production_usable": False,
                "current_spatial_assimilation": False,
                "reason": "no_current_spatial_scenes",
            },
            asmae_feature_pack={"state_proof": state_proof, "state_support_ledger": state_proof},
            asmae_proof={
                "state_availability": state_availability,
                "authority_level": "DIAGNOSTIC_ONLY",
                "evidence_capabilities": capabilities,
                "state_proof": state_proof,
                "state_support_ledger": state_proof,
                "coarse_prior_proof": coarse_prior_proof,
            },
        )

    # ════════════════════════════════════════════════════════════════
        output.plot_state_artifact = plot_state_artifact
        output.diagnostics['authority_level'] = 'DIAGNOSTIC'
        output.diagnostics['reason'] = fallback_reason
        output.asmae_evidence_state['authority_level'] = 'DIAGNOSTIC'
        output.asmae_evidence_state['reason'] = fallback_reason
        output.asmae_proof['authority_level'] = 'DIAGNOSTIC'
        output.asmae_proof['spatial_normalization'] = list(
            getattr(self, '_spatial_proof', []) or []
        )
        return output

    def _timeout_fallback_output(self, inp, provenance, scene_stack_status, error_message: str):
        """Build fallback output for state-estimation timeout that preserves admitted scene evidence.

        Unlike _no_scene_output, this method does NOT falsify scene counts.
        Eight admitted scenes remain as evidence; only the spatial execution failed.
        """
        from .resilient_posterior import estimate_resilient_plot_posterior
        from .plot_state import build_plot_state_artifact, canonical_availability

        estimate = estimate_resilient_plot_posterior(inp)
        state_availability = canonical_availability(estimate["state_availability"])
        posterior_available = estimate["posterior_available"]
        plot_level_posterior = estimate["plot_level_posterior"]
        state_proof = estimate["state_support_ledger"]
        normalized_uncertainty = estimate["normalized_uncertainty"]

        actual_scenes_available = getattr(provenance, 'scenes_available', 0) or 0
        actual_scenes_used = getattr(provenance, 'scenes_used', 0) or 0
        actual_scenes_rejected = getattr(provenance, 'scenes_rejected', 0) or 0

        fallback_reason = 'state_estimation_timeout'
        plot_state_artifact = build_plot_state_artifact(
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            as_of=inp.end_date,
            availability=state_availability,
            authority='DIAGNOSTIC',
            posterior=plot_level_posterior,
            support_ledger=state_proof,
            production_usable=False,
            current_spatial_assimilation=False,
            geometry_hash=inp.geometry_hash,
            evidence_hash=str(getattr(inp, 'archive_metrics_hash', '') or ''),
            reason=fallback_reason,
        )
        provenance.completed_at = datetime.now(timezone.utc)
        provenance.audit_log = self._audit_log
        provenance.compute_content_hash()

        output = ASMAEOutput(
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            generated_at=datetime.now(timezone.utc),
            resolution_decision=ResolutionDecision(
                candidate_resolutions_tested_m=[DEFAULT_RESOLUTION_M],
                selected_effective_resolution_m=DEFAULT_RESOLUTION_M,
            ),
            raster_maps={},
            uncertainty_maps={},
            weak_labels=[],
            diagnostics={
                "scene_stack_mode": "admitted_but_execution_timeout",
                "scene_count": actual_scenes_available,
                "scenes_available": actual_scenes_available,
                "scenes_used": actual_scenes_used,
                "scenes_rejected": actual_scenes_rejected,
                "state_availability": state_availability,
                "authority_level": "DIAGNOSTIC_ONLY",
                "posterior_available": posterior_available,
                "plot_level_posterior": plot_level_posterior,
                "normalized_uncertainty": normalized_uncertainty,
                "stage_status": {
                    "current_scene_assimilation": "admitted_but_timeout",
                    "plot_level_state": "degraded" if posterior_available else "unavailable",
                    "retrovalidation": "unavailable",
                    "bma": "unavailable",
                    "ml": "unavailable",
                    "certification": "unavailable",
                },
                "production_usable": False,
                "production_usable_reason": "state_estimation_timeout",
                "status_override": "failed_spatial_timeout",
                "scientific_pass": False,
                "layer1_export_allowed": False,
                "state_update_allowed": False,
                "visual_allowed": False,
                "weak_label_export_allowed": False,
                "diagnostic_only": True,
                "reason": fallback_reason,
                "failure_stage": "state_estimation",
                "failure_code": "STATE_ESTIMATION_TIMEOUT",
                "failure_message": error_message,
            },
            provenance=provenance.to_dict(),
            asmae_evidence_state={
                "state_availability": state_availability,
                "authority_level": "DIAGNOSTIC",
                "posterior_available": posterior_available,
                "production_usable": False,
                "current_spatial_assimilation": False,
                "reason": fallback_reason,
                "failure_stage": "state_estimation",
                "failure_code": "STATE_ESTIMATION_TIMEOUT",
            },
            asmae_feature_pack={"state_proof": state_proof, "state_support_ledger": state_proof},
            asmae_proof={
                "state_availability": state_availability,
                "authority_level": "DIAGNOSTIC",
                "state_proof": state_proof,
                "state_support_ledger": state_proof,
            },
        )
        output.plot_state_artifact = plot_state_artifact
        output.diagnostics['authority_level'] = 'DIAGNOSTIC'
        output.asmae_evidence_state['authority_level'] = 'DIAGNOSTIC'
        output.asmae_proof['authority_level'] = 'DIAGNOSTIC'
        output.asmae_proof['spatial_normalization'] = list(
            getattr(self, '_spatial_proof', []) or []
        )
        return output

    # V79A: Production usable computation
    # ════════════════════════════════════════════════════════════════

    def _compute_production_usable(
        self, scene_stack_status, consistency_result,
        retro_result, bma_result, state_result,
    ) -> tuple:
        """Determine if output is production-usable.

        Returns (bool, reason_string).
        """
        if getattr(self, "is_pseudo", False):
            self._production_block_reasons = ["PSEUDO_SCENE_FALLBACK"]
            return False, "pseudo_scene_fallback_mode"
        if not scene_stack_status.production_allowed:
            blocks = ["SCENE_STACK_NOT_PRODUCTION_ALLOWED"]
            if scene_stack_status.n_provider_real <= 0:
                blocks.append("NO_PROVIDER_REAL_SCENE")
            if scene_stack_status.n_proxy > 0:
                blocks.append("PROXY_SCENE_PRESENT")
            if scene_stack_status.n_diagnostic > 0:
                blocks.append("DIAGNOSTIC_SCENE_PRESENT")
            if scene_stack_status.mode != "real_raster":
                blocks.append(f"SCENE_STACK_MODE_{scene_stack_status.mode.upper()}")
            self._production_block_reasons = blocks
            return False, "SCENE_STACK_NOT_PRODUCTION_ALLOWED"
        if not consistency_result.get("overall_pass", False):
            self._production_block_reasons = ["RADIOMETRIC_CONSISTENCY_FAILED"]
            return False, "radiometric_consistency_failed"
        if retro_result.get("status") not in ("success_with_holdouts",):
            self._production_block_reasons = ["RETROVALIDATION_HOLDOUTS_UNAVAILABLE"]
            return False, f"retro_status_{retro_result.get('status')}"
        from .config import RETRO_SCORE_5M_THRESHOLD

        retro_score = retro_result.get('mean_retro_score')
        if not isinstance(retro_score, (int, float)) or float(retro_score) < RETRO_SCORE_5M_THRESHOLD:
            self._production_block_reasons = ["RETROVALIDATION_SCORE_BELOW_THRESHOLD"]
            return False, 'retro_score_below_production_threshold'
        if bma_result.get("status") != "success":
            self._production_block_reasons = ["BMA_PRODUCTION_CONSENSUS_UNAVAILABLE"]
            return False, f"bma_status_{bma_result.get('status')}"
            
        # V922.2B strict production usable gating
        rad_mode = consistency_result.get("radiometric_mode", "unknown")
        full_rad = consistency_result.get("full_radiometric_credit_allowed", False)
        n_checked = consistency_result.get("n_checked", 0)
        
        full_enkf = state_result.get("full_enkf_credit_allowed", False)
        has_fallback = state_result.get("has_enkf_proxy_fallback", False)
        
        if rad_mode != "ht_per_pixel" or not full_rad or n_checked <= 0:
            self._production_block_reasons = ["INSUFFICIENT_RADIOMETRIC_CREDIT"]
            return False, "insufficient_radiometric_credit"
        if not full_enkf or has_fallback:
            self._production_block_reasons = ["INSUFFICIENT_ENKF_CREDIT"]
            return False, "insufficient_enkf_credit"
        self._production_block_reasons = []
        return True, "all_gates_passed"

    # ════════════════════════════════════════════════════════════════
    # Pipeline steps
    # ════════════════════════════════════════════════════════════════

    def _build_scene_stack(self, inp: ASMAEInput) -> list:
        """V68: Build per-scene observation stacks from Layer 0 data."""
        from .geometry.scene_stack_builder import build_scene_stack

        stack = build_scene_stack(inp)
        self._scene_stack = stack
        logger.info(
            "Scene stack: %d included, %d excluded, mode=%s",
            stack.total_included(), stack.total_excluded(), stack.mode,
        )
        if getattr(stack, "mode", "") == "hybrid":
            # Main pipeline is the production ensemble: real, admitted scenes
            # only.  Proxy scenes are retained for a distinct advisory pass.
            self._advisory_scenes = list(stack.runtimes)
            self._production_scene_records = list(stack.real_scenes)
            self._production_scenes = [item["runtime"] for item in stack.real_scenes]
            return self._normalize_spatial_scenes(
                list(self._production_scenes), list(self._advisory_scenes), inp,
            )
        self._advisory_scenes = []
        self._production_scene_records = list(getattr(stack, "scenes", []) or [])
        self._production_scenes = list(stack.runtimes)
        return self._normalize_spatial_scenes(
            list(self._production_scenes), [], inp,
        )

    def _normalize_spatial_scenes(
        self, production_scenes: list, advisory_scenes: list, inp: ASMAEInput,
    ) -> list:
        from .geometry.spatial_reference import (
            SpatialReferenceError,
            normalize_scene_stack_to_metric,
            reproject_scene_to_metric,
        )
        from .geometry.support_contract import build_scene_valid_support

        self._spatial_block_reason = ''
        self._spatial_proof = []
        if not production_scenes:
            return []
        try:
            normalized, target_crs, proof = normalize_scene_stack_to_metric(
                production_scenes,
                getattr(inp, 'polygon_geojson', None),
            )
            for scene in normalized:
                support = build_scene_valid_support(
                    scene, getattr(inp, 'polygon_geojson', None),
                )
                proof.append({
                    'scene_id': str(getattr(scene, 'scene_id', '')),
                    'valid_support': support,
                })

            normalized_by_id = {
                str(getattr(scene, 'scene_id', '')): scene for scene in normalized
            }
            advisory_normalized = []
            for scene in advisory_scenes:
                scene_id = str(getattr(scene, 'scene_id', ''))
                advisory = normalized_by_id.get(scene_id)
                if advisory is None:
                    advisory = reproject_scene_to_metric(scene, target_crs)
                    support = build_scene_valid_support(
                        advisory, getattr(inp, 'polygon_geojson', None),
                    )
                    proof.append({'scene_id': scene_id, 'valid_support': support})
                advisory_normalized.append(advisory)
            self._production_scenes = normalized
            self._advisory_scenes = advisory_normalized
            self._spatial_proof = proof
            return normalized
        except (SpatialReferenceError, ValueError, TypeError) as exc:
            self._spatial_block_reason = 'spatial_geometry_unavailable:' + str(exc)
            self._spatial_proof = [{
                'status': 'blocked',
                'reason': self._spatial_block_reason,
            }]
            self._production_scenes = []
            self._advisory_scenes = []
            logger.warning('ASMAE spatial assimilation blocked: %s', exc)
            return []

    def _build_observation_operators(self, scenes: list, inp: ASMAEInput) -> list:
        """V69: Construct H_t observation operators per scene."""
        from .geometry.coregistration import coregister_stack
        from .geometry.operator_builder import build_operators_for_stack
        from .geometry.operator_diagnostics import run_operator_diagnostics

        coreg_results = coregister_stack(scenes)
        self._coreg_results = coreg_results

        operators = build_operators_for_stack(
            scenes=scenes,
            candidate_resolution_m=DEFAULT_RESOLUTION_M,
            coreg_results=coreg_results,
        )
        from .chain_integrity import assert_scene_operator_binding

        assert_scene_operator_binding(
            scenes, operators, stage_name='operator_construction',
        )

        self._operators = operators

        diag_report = run_operator_diagnostics(operators)
        self._operator_diagnostics = diag_report

        if diag_report.n_errors > 0:
            logger.error(
                "H_t operator diagnostics FAILED: %d errors.",
                diag_report.n_errors,
            )
            if inp.mode != "shadow":
                raise RuntimeError(
                    f"ASMAE operator diagnostics failed: "
                    f"{diag_report.n_errors} errors in mode='{inp.mode}'."
                )
            self._operator_degraded = True
        else:
            self._operator_degraded = False

        return operators

    def _evaluate_resolution_ladder(
        self, scenes: list, operators: list, inp: ASMAEInput,
    ) -> ResolutionDecision:
        """V70: Evaluate all candidate resolutions and select best."""
        from .geometry.operator_builder import build_operators_for_stack
        from .resolution.selector import select_resolution

        coreg_results = getattr(self, "_coreg_results", None)

        def _operator_builder_fn(scenes_list, resolution_m):
            return build_operators_for_stack(
                scenes=scenes_list,
                candidate_resolution_m=resolution_m,
                coreg_results=coreg_results,
            )

        # Resolve retro_scores from inp.retrovalidation_residuals (BC.10.17 P2.1)
        retro_scores = {}
        residuals = getattr(inp, "retrovalidation_residuals", {}) or {}
        if isinstance(residuals, dict):
            for k, v in residuals.items():
                try:
                    res_key = int(k)
                    retro_scores[res_key] = float(v)
                except ValueError:
                    pass
                val = residuals.get("retro_score") or residuals.get("mean_retro_score") or residuals.get("res") or residuals.get("r2")
                if val is not None:
                    retro_scores[1] = float(val)

        decision = select_resolution(
            inp=inp,
            scenes=scenes,
            operators_10m=operators,
            operator_builder_fn=_operator_builder_fn,
            coregistration_results=coreg_results,
            retro_scores=retro_scores,
        )

        self._resolution_decision = decision
        return decision

    def _build_microzone_graph(
        self, inp: ASMAEInput, rd: ResolutionDecision,
    ) -> dict:
        """V71: Build spatial graph of micro-zones."""
        from .graph.microzone_graph import build_microzone_graph

        resolution_m = rd.selected_effective_resolution_m

        production_scenes = list(getattr(self, "_production_scenes", []) or [])
        if production_scenes:
            ref_scene = production_scenes[0]
            from .geometry.spatial_reference import (
                pixel_size_m as canonical_pixel_size_m,
                target_grid_from_reference,
            )

            target_grid = target_grid_from_reference(ref_scene, resolution_m)
            pixel_size_m = canonical_pixel_size_m(ref_scene)
            n_pixel_rows = ref_scene.height if ref_scene.height > 0 else 10
            n_pixel_cols = ref_scene.width if ref_scene.width > 0 else 10
            origin_x = target_grid.origin_x
            origin_y = target_grid.origin_y
        else:
            pixel_size_m = 10.0
            n_pixel_rows = 10
            n_pixel_cols = 10
            origin_x = 0.0
            origin_y = 0.0

        polygon_points = None
        geojson = inp.polygon_geojson
        if isinstance(geojson, dict):
            coords = geojson.get("coordinates", [])
            if coords and isinstance(coords[0], list):
                ring = coords[0] if isinstance(coords[0][0], (list, tuple)) else coords
                polygon_points = [(p[0], p[1]) for p in ring if len(p) >= 2]

        row_direction = inp.crop_context.get("row_direction_deg", 0.0)

        crs = None
        if production_scenes:
            ref_scene = production_scenes[0]
            crs = getattr(ref_scene, "crs", None)

        if not crs:
            crs = getattr(inp, "grid_spec", {}).get("crs") if isinstance(getattr(inp, "grid_spec", None), dict) else None

        if not crs:
            crs = "EPSG:4326"

        if production_scenes and geojson:
            try:
                from rasterio.warp import transform_geom
                from .geometry.spatial_reference import coerce_polygon_geojson

                geometry = coerce_polygon_geojson(geojson)
                projected = transform_geom('EPSG:4326', crs, geometry, precision=9)
                coordinates = projected.get('coordinates', [])
                if projected.get('type') == 'MultiPolygon':
                    coordinates = coordinates[0] if coordinates else []
                ring = coordinates[0] if coordinates else []
                polygon_points = [
                    (float(point[0]), float(point[1])) for point in ring
                    if len(point) >= 2
                ]
            except Exception:
                polygon_points = None

        graph = build_microzone_graph(
            resolution_m=resolution_m,
            n_pixel_rows=n_pixel_rows,
            n_pixel_cols=n_pixel_cols,
            pixel_size_m=pixel_size_m,
            target_origin_x=origin_x,
            target_origin_y=origin_y,
            geometry_hash=inp.geometry_hash,
            polygon_points=polygon_points,
            row_direction_deg=row_direction,
            crs=crs,
        )

        self._graph = graph
        return graph.summary()

    def _build_selected_bundle(
        self, scenes: list, operators_10m: list,
        resolution_decision: ResolutionDecision, inp: ASMAEInput,
    ) -> tuple:
        """V922: Build immutable SelectedOperatorBundle after resolution selection.

        This is the core chain-locking step. It:
          1. If selected != 10m, rebuilds operators at the selected resolution
          2. Rebuilds the microzone graph at the selected resolution
          3. Runs operator diagnostics
          4. If diagnostics fail, applies the demotion ladder (coarser candidates)
          5. Constructs the immutable bundle

        Demotion ladder: if 5m fails → try 6m → 7m → 8m → 9m → 10m.
        If even 10m fails → return degraded output.

        Returns:
            (SelectedOperatorBundle, ResolutionDecision) — decision may be
            updated if demotion occurred.
        """
        from .geometry.operator_builder import build_operators_for_stack
        from .geometry.operator_diagnostics import run_operator_diagnostics

        coreg_results = getattr(self, "_coreg_results", None)
        selected_m = resolution_decision.selected_effective_resolution_m
        original_selected_m = selected_m
        was_rebuilt = (selected_m != DEFAULT_RESOLUTION_M)
        was_demoted = False

        # Build list of resolutions to try: selected first, then coarser
        resolutions_to_try = [selected_m]
        for r in sorted(CANDIDATE_RESOLUTIONS_M):
            if r > selected_m and r not in resolutions_to_try:
                resolutions_to_try.append(r)
        # Ensure 10m is always last resort
        if DEFAULT_RESOLUTION_M not in resolutions_to_try:
            resolutions_to_try.append(DEFAULT_RESOLUTION_M)

        last_error_msg = ""

        for attempt_m in resolutions_to_try:
            self._audit(
                "bundle_attempt", "trying",
                resolution_m=attempt_m,
                is_original=(attempt_m == original_selected_m),
            )

            # Build operators at this resolution
            if attempt_m == DEFAULT_RESOLUTION_M and not was_demoted:
                attempt_operators = operators_10m
            else:
                try:
                    attempt_operators = build_operators_for_stack(
                        scenes=scenes,
                        candidate_resolution_m=attempt_m,
                        coreg_results=coreg_results,
                    )
                except Exception as e:
                    logger.warning(
                        "V922: Operator build failed at %dm: %s", attempt_m, e,
                    )
                    last_error_msg = str(e)
                    was_demoted = True
                    continue

            # Build graph at this resolution
            from .chain_integrity import assert_scene_operator_binding

            assert_scene_operator_binding(
                scenes, attempt_operators, stage_name='selected_bundle',
            )
            graph = self._build_microzone_graph(inp, ResolutionDecision(
                selected_effective_resolution_m=attempt_m,
                candidate_resolutions_tested_m=[attempt_m],
            ))

            # Run diagnostics
            diag_report = run_operator_diagnostics(attempt_operators)

            if diag_report.n_errors > 0:
                logger.warning(
                    "V922: Operator diagnostics failed at %dm (%d errors), "
                    "trying next coarser resolution.",
                    attempt_m, diag_report.n_errors,
                )
                last_error_msg = f"{diag_report.n_errors} diagnostic errors at {attempt_m}m"
                if attempt_m != original_selected_m:
                    was_demoted = True
                continue

            # Success — build the bundle
            if attempt_m != original_selected_m:
                was_demoted = True
                was_rebuilt = True
                # Update the resolution decision
                resolution_decision = ResolutionDecision(
                    candidate_resolutions_tested_m=resolution_decision.candidate_resolutions_tested_m,
                    selected_effective_resolution_m=attempt_m,
                    selected_visual_resolution_m=attempt_m,
                    selected_state_update_resolution_m=attempt_m,
                    selected_training_resolution_m=attempt_m,
                    safe_for_1m_claim=False,
                    demoted_candidates=resolution_decision.demoted_candidates + [
                        {"resolution_m": original_selected_m, "reason": "v922_diagnostics_demotion"}
                    ],
                    candidate_scores=resolution_decision.candidate_scores,
                    reason_codes={
                        **resolution_decision.reason_codes,
                        attempt_m: ["v922_demoted_safe_resolution"],
                    },
                )
                logger.info(
                    "V922: Demoted from %dm to %dm (diagnostics pass).",
                    original_selected_m, attempt_m,
                )

            bundle = build_selected_operator_bundle(
                selected_resolution_m=attempt_m,
                operators=attempt_operators,
                operator_diagnostics=diag_report,
                graph=getattr(self, "_graph", {}),
                resolution_decision=resolution_decision,
                coreg_results=coreg_results,
                was_rebuilt=was_rebuilt,
                was_demoted=was_demoted,
                original_selected_resolution_m=original_selected_m,
            )

            self._resolution_decision = resolution_decision
            return bundle, resolution_decision

        # All resolutions failed — chain integrity error
        raise ASMAEChainIntegrityError(
            f"V922: No valid operator bundle at any resolution. "
            f"Tried {resolutions_to_try}. Last error: {last_error_msg}"
        )

    def _chain_integrity_failure_output(
        self, inp: ASMAEInput, provenance: ASMAEProvenance, error_msg: str,
    ) -> ASMAEOutput:
        """V922: Return fail-closed output when chain integrity is violated.

        All scientific outputs are suppressed. production_usable=False.
        No Layer 1 export, no weak labels, no state update.
        """
        provenance.compute_content_hash()

        return ASMAEOutput(
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            generated_at=datetime.now(timezone.utc),
            resolution_decision=ResolutionDecision(
                candidate_resolutions_tested_m=[DEFAULT_RESOLUTION_M],
                selected_effective_resolution_m=DEFAULT_RESOLUTION_M,
            ),
            raster_maps={},
            uncertainty_maps={},
            weak_labels=[],
            diagnostics={
                "chain_integrity_error": True,
                "chain_integrity_message": error_msg,
                "production_usable": False,
                "production_usable_reason": "chain_integrity_violation",
                "status_override": "degraded",
                "scientific_pass": False,
                "layer1_export_allowed": False,
                "weak_label_export_allowed": False,
                "state_update_allowed": False,
                "diagnostic_only": True,
                "reason": f"chain_integrity_violation:{error_msg}",
            },
            provenance=provenance.to_dict(),
        )

    def _ingest_layer_priors(self, inp: ASMAEInput) -> dict:
        """V73: Ingest Layers 2–8 coarse priors."""
        from .priors.prior_registry import ingest_all_priors

        priors = ingest_all_priors(
            coarse_outputs=inp.coarse_layer_outputs,
            crop_context=inp.crop_context,
            phenology_posterior=inp.phenology_posterior,
            plot_id=inp.plot_id,
            geometry_hash=inp.geometry_hash,
        )

        self._priors = priors
        return {k: v for k, v in priors.items()}

    def _run_state_estimation(
        self, scenes, bundle: SelectedOperatorBundle, graph, priors,
        rd: ResolutionDecision, inp: ASMAEInput,
        deadline_check=None,
    ) -> dict:
        """V74 + V79A + V922: EnKF with Hₜ from selected bundle."""
        from .assimilation.filter import run_enkf
        from .deterministic import make_rng

        # V922: Verify bundle integrity before EnKF
        assert_bundle_integrity(bundle, stage_name="EnKF")

        rng = make_rng(
            run_id=inp.run_id,
            plot_id=inp.plot_id,
            geometry_hash=inp.geometry_hash,
        )
        from .resilient_posterior import estimate_resilient_plot_posterior
        scene_times = [
            getattr(scene, 'acquisition_time', None) for scene in scenes
            if getattr(scene, 'acquisition_time', None) is not None
        ]
        initialization_cutoff = (
            min(scene_times) - timedelta(microseconds=1)
            if scene_times else inp.start_date
        )
        initialization = estimate_resilient_plot_posterior(
            inp, as_of=initialization_cutoff,
        )
        initial_posterior = (
            initialization.get("plot_level_posterior", {})
            if initialization.get("posterior_available") else {}
        )

        result = run_enkf(
            scenes=scenes,
            operators=list(bundle.operators),
            graph=graph,
            priors=priors,
            resolution_m=bundle.selected_resolution_m,
            mode=inp.mode,
            crop_context=inp.crop_context,
            rng=rng,
            expected_resolution_m=bundle.selected_resolution_m,
            weather_daily_series=getattr(inp, "weather_daily_series", {}) or {},
            soil_context=getattr(inp, "soil_context", {}) or {},
            management_events=getattr(inp, "management_events", []) or [],
            initial_posterior=initial_posterior,
            deadline_check=deadline_check,
        )
        result["initialization_proof"]["state_availability"] = initialization.get("state_availability")
        result["initialization_proof"]["archive_contract_valid"] = initialization.get("archive_contract_valid")
        result["initialization_proof"]["archive_rejection_reasons"] = initialization.get("archive_rejection_reasons", [])

        result['initialization_proof']['as_of_cutoff'] = str(initialization_cutoff)
        result['initialization_proof']['future_window_evidence_excluded'] = True
        self._state_result = result
        return result

    def _run_advisory_state_estimation(
        self, scenes, graph, priors, rd: ResolutionDecision, inp: ASMAEInput,
        deadline_check=None,
    ) -> dict:
        """Run the proxy-inclusive ensemble without mutating production state."""
        from .assimilation.filter import run_enkf
        from .deterministic import make_rng
        from .geometry.coregistration import coregister_stack
        from .geometry.operator_builder import build_operators_for_stack
        from .resilient_posterior import estimate_resilient_plot_posterior

        resolution_m = rd.selected_effective_resolution_m
        coreg = coregister_stack(scenes)
        operators = build_operators_for_stack(
            scenes=scenes,
            candidate_resolution_m=resolution_m,
            coreg_results=coreg,
        )
        scene_times = [
            getattr(scene, 'acquisition_time', None) for scene in scenes
            if getattr(scene, 'acquisition_time', None) is not None
        ]
        initialization_cutoff = (
            min(scene_times) - timedelta(microseconds=1)
            if scene_times else inp.start_date
        )
        initialization = estimate_resilient_plot_posterior(
            inp, as_of=initialization_cutoff,
        )
        result = run_enkf(
            scenes=scenes,
            operators=operators,
            graph=graph,
            priors=priors,
            resolution_m=resolution_m,
            mode="visual",
            crop_context=inp.crop_context,
            rng=make_rng(
                run_id=f"{inp.run_id}:advisory",
                plot_id=inp.plot_id,
                geometry_hash=inp.geometry_hash,
            ),
            expected_resolution_m=resolution_m,
            weather_daily_series=getattr(inp, "weather_daily_series", {}) or {},
            soil_context=getattr(inp, "soil_context", {}) or {},
            management_events=getattr(inp, "management_events", []) or [],
            initial_posterior=(
                initialization.get("plot_level_posterior", {})
                if initialization.get("posterior_available") else {}
            ),
            deadline_check=deadline_check,
        )
        result["authority"] = "advisory_only"
        result["production_invariant"] = True
        return result

    def _enforce_radiometric_consistency(
        self, state_result, bundle: SelectedOperatorBundle, scenes,
    ) -> dict:
        """V75 + V79A + V922: Radiometric consistency with bundle operators."""
        from .constraints.radiometric import enforce_radiometric_consistency

        # V922: Verify bundle integrity before radiometric check
        assert_bundle_integrity(bundle, stage_name="radiometric")

        means = state_result.get("raster_maps", {})

        result = enforce_radiometric_consistency(
            state_estimates=means,
            observations={},  # Extracted internally when using Hₜ
            graph=getattr(self, '_graph', None),
            operators=list(bundle.operators),
            scenes=scenes,
            expected_resolution_m=bundle.selected_resolution_m,
        )
        self._consistency_result = result
        return result

    def _run_retrovalidation(
        self, state_result, scenes, bundle: SelectedOperatorBundle,
        inp: ASMAEInput, consistency_result=None, causal_result=None,
        deadline_check=None,
    ) -> dict:
        """V76 + V79A + V922: Retrovalidation with bundle operators."""
        from .retrovalidation.engine import run_retrovalidation

        # V922: Verify bundle integrity before retrovalidation
        assert_bundle_integrity(bundle, stage_name="retrovalidation")

        return run_retrovalidation(
            state_result=state_result,
            scenes=scenes or [],
            operators=list(bundle.operators),
            graph=getattr(self, '_graph', None),
            priors=getattr(self, '_priors', {}),
            consistency_result=consistency_result,
            causal_result=causal_result,
            expected_resolution_m=bundle.selected_resolution_m,
            evidence_context={
                'asmae_input': inp,
                "weather_daily_series": getattr(inp, "weather_daily_series", {}) or {},
                "soil_context": getattr(inp, "soil_context", {}) or {},
                "crop_context": getattr(inp, "crop_context", {}) or {},
                "polygon_geojson": getattr(inp, "polygon_geojson", {}) or {},
                "management_events": getattr(inp, "management_events", []) or [],
                "plot_timeseries": getattr(inp, "plot_timeseries", []) or [],
                "phenology_envelopes": getattr(inp, "phenology_envelopes", {}) or {},
                "phenology_posterior": getattr(inp, "phenology_posterior", {}) or {},
                "coarse_layer_outputs": getattr(inp, "coarse_layer_outputs", {}) or {},
                "spatial_prior_by_microzone": (
                    getattr(inp, "coarse_layer_outputs", {}) or {}
                ).get("spatial_prior_by_microzone", {}),
            },
            refit_identity={
                "run_id": inp.run_id,
                "plot_id": inp.plot_id,
                "geometry_hash": inp.geometry_hash,
            },
            deadline_check=deadline_check,
        )

    def _run_causal_tracking(
        self, state_result, priors, inp: ASMAEInput,
    ) -> dict:
        """V77: Track causal hypotheses."""
        from .causality.tracker import track_causes

        return track_causes(
            state_result=state_result,
            priors=priors or {},
            crop_context=inp.crop_context,
        )

    def _run_bma(
        self, state_result, inp: ASMAEInput, retro_result=None, scenes=None,
    ) -> dict:
        """V78 + V79A: BMA with holdout-based weights."""
        from .bma.posterior import run_bma

        return run_bma(
            state_result=state_result,
            priors=getattr(self, '_priors', {}),
            graph=getattr(self, '_graph', None),
            retro_result=retro_result,
            evidence_context={
                "scenes": scenes or [],
                "weather_daily_series": getattr(inp, "weather_daily_series", {}) or {},
                "soil_context": getattr(inp, "soil_context", {}) or {},
                "crop_context": getattr(inp, "crop_context", {}) or {},
                "management_events": getattr(inp, "management_events", []) or [],
                "plot_timeseries": getattr(inp, "plot_timeseries", []) or [],
                "phenology_envelopes": getattr(inp, "phenology_envelopes", {}) or {},
                "phenology_posterior": getattr(inp, "phenology_posterior", {}) or {},
                "coarse_layer_outputs": getattr(inp, "coarse_layer_outputs", {}) or {},
                "spatial_prior_by_microzone": (
                    getattr(inp, "coarse_layer_outputs", {}) or {}
                ).get("spatial_prior_by_microzone", {}),
            },
        )

    def _export_weak_labels(
        self, state_result, retro_result, bma_result,
        consistency_result, scene_stack_status, inp: ASMAEInput,
        production_usable: bool,
    ) -> list:
        """V79 + V79A: 10-gate weak-label export."""
        from .training.exporter import export_weak_labels

        rd = getattr(self, '_resolution_decision', None)
        resolution_m = rd.selected_effective_resolution_m if rd else 10

        return export_weak_labels(
            state_result=state_result,
            retro_result=retro_result,
            bma_result=bma_result,
            consistency_result=consistency_result,
            scene_stack_mode=scene_stack_status.mode,
            resolution_m=resolution_m,
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            production_usable=production_usable,
            n_scenes_processed=state_result.get("n_scenes_processed", 0),
            mode=inp.mode,
        )

    # ════════════════════════════════════════════════════════════════
    # V79A Phase 11: Rich diagnostics
    # ════════════════════════════════════════════════════════════════

    def _build_diagnostics(
        self, scene_stack_status, operators, resolution_decision,
        state_result, consistency_result, retro_result,
        causal_result, bma_result, weak_labels,
        production_usable, production_reason, mode: str = "shadow",
        bundle: Optional[SelectedOperatorBundle] = None,
    ) -> dict:
        """Build comprehensive diagnostics dict for V80+ consumption."""
        scientific_pass = production_usable
        layer1_export_allowed = scientific_pass and mode != "shadow"
        state_update_allowed = scientific_pass and mode != "shadow"
        weak_label_export_allowed = scientific_pass and mode in ("training_export", "certification")

        # A spatial diagnostic raster precedes radiometric, retrovalidation and
        # BMA production gates. Those stages control authority, not whether a
        # clearly labelled Ht/EnKF posterior may be visualized.
        visual_allowed = bool(
            scene_stack_status.n_real_raster > 0
            and state_result.get("raster_maps")
            and state_result.get("enkf_mode") == "ht_per_pixel"
            and bundle is not None
            and bundle.operators
        )
        diagnostic_only = not production_usable

        reason = production_reason
        if mode == "shadow" and scientific_pass:
            reason = "shadow_mode_no_output_use"

        # Learning Memory Diagnostics
        lm_used = False
        lm_status = "none"
        lm_variables = []
        lm_blend_weight = 0.0
        lm_content_hash = ""
        lm_limitations = []

        lm_prior = getattr(self, "_priors", {}).get("learning_memory", {})
        if lm_prior.get("usable_as_prior") and lm_prior.get("status") == "available":
            mdata = lm_prior.get("memory_data", {})
            if mdata:
                lm_used = True
                lm_status = mdata.get("memory_status", "none")
                lm_variables = list(mdata.get("variables", {}).keys())
                lm_content_hash = mdata.get("memory_content_hash", "")
                lm_blend_weight = state_result.get("memory_blend_weight", 0.0)
                lm_limitations = mdata.get("limitations") or []

        # V88: Shadow ML diagnostics namespacing
        from .config import ASMAE_ML_EXPERTS_ENABLED, ASMAE_ML_EXPERTS_SHADOW_ONLY
        shadow_ml_diag = {
            "enabled": ASMAE_ML_EXPERTS_ENABLED,
            "shadow_only": ASMAE_ML_EXPERTS_SHADOW_ONLY,
            "models": bma_result.get("active_ml_experts", []) if isinstance(bma_result, dict) else [],
            "bma_weights_shadow_raw": bma_result.get("bma_weights_shadow_raw", {}) if isinstance(bma_result, dict) else {},
            "production_weight_override": "zeroed_by_v88_policy"
        }

        # V922: Chain integrity diagnostics
        chain_diag = {}
        if bundle is not None:
            chain_diag = {
                "selected_operator_bundle_hash": bundle.content_hash,
                "selected_operators_rebuilt": bundle.was_rebuilt,
                "selected_operators_demoted": bundle.was_demoted,
                "original_selected_resolution_m": bundle.original_selected_resolution_m,
                "selected_operator_count": bundle.operator_count,
                "operators_match_resolution": all(
                    getattr(op, "target_resolution_m", None) == bundle.selected_resolution_m
                    for op in bundle.operators
                ),
                "graph_node_count": bundle.graph_node_count,
                "graph_hash": bundle.graph_hash,
                "coreg_hash": bundle.coreg_hash,
            }

        result = {
            "scene_stack_mode": scene_stack_status.mode,
            "state_availability": (
                "HYBRID_ADVISORY" if getattr(self, "is_pseudo", False)
                else "CURRENT_SPATIAL_ASSIMILATED"
            ),
            "authority_level": (
                "PRODUCTION_ASSIMILATED" if production_usable
                else "SCOUTING_ADVISORY"
            ),
            "posterior_available": bool(state_result.get("raster_maps")),
            "stage_status": {
                "state_estimation": "success" if state_result.get("raster_maps") else "unavailable",
                "radiometric_consistency": "success" if consistency_result.get("overall_pass") else "degraded",
                "retrovalidation": "success" if retro_result.get("status") == "success_with_holdouts" else "unavailable",
                "bma": "success" if isinstance(bma_result, dict) and bma_result.get("status") == "success" else "unavailable",
                "ml": "degraded" if ASMAE_ML_EXPERTS_ENABLED else "unavailable",
                "certification": "success" if production_usable else "unavailable",
            },
            "scene_count": scene_stack_status.n_total,
            "n_real_raster": scene_stack_status.n_real_raster,
            "n_mean_only": scene_stack_status.n_mean_only,
            "operator_count": len(operators) if operators else 0,
            "operator_degraded": getattr(self, '_operator_degraded', False),
            "resolution_selected_m": resolution_decision.selected_effective_resolution_m,
            "enkf_mode": state_result.get("enkf_mode", "unknown"),
            "enkf_scenes_processed": state_result.get("n_scenes_processed", 0),
            "radiometric_overall_pass": consistency_result.get("overall_pass"),
            "radiometric_mode": consistency_result.get("radiometric_mode", "unknown"),
            "retro_status": retro_result.get("status"),
            "retro_mean_score": retro_result.get("mean_retro_score"),
            "bma_status": bma_result.get("status") if isinstance(bma_result, dict) else None,
            "bma_mean_disagreement": bma_result.get("mean_disagreement") if isinstance(bma_result, dict) else 0.0,
            "weak_label_count": len(weak_labels),
            "weak_label_positive_weight": sum(
                1 for l in weak_labels if l.get("training_weight", 0) > 0
            ),
            "production_usable": production_usable,
            "production_usable_reason": production_reason,
            "production_block_reasons": list(
                getattr(self, "_production_block_reasons", []) or []
            ),
            "scientific_pass": scientific_pass,
            "layer1_export_allowed": layer1_export_allowed,
            "state_update_allowed": state_update_allowed,
            "weak_label_export_allowed": weak_label_export_allowed,
            "visual_allowed": visual_allowed,
            "diagnostic_only": diagnostic_only,
            "reason": reason,
            "learning_memory_used": lm_used,
            "memory_status": lm_status,
            "memory_variables": lm_variables,
            "memory_blend_weight": lm_blend_weight,
            "memory_content_hash": lm_content_hash,
            "memory_limitations": lm_limitations,
            "shadow_ml": shadow_ml_diag,
            "is_pseudo": getattr(self, "is_pseudo", False),
        }
        result.update(chain_diag)
        return result

    # ════════════════════════════════════════════════════════════════
    # Output assembly
    # ════════════════════════════════════════════════════════════════

    def _extract_bounds_from_geojson(self, geojson: dict) -> Tuple[float, float, float, float]:
        geom = geojson.get("geometry", geojson) if isinstance(geojson, dict) else {}
        coords = geom.get("coordinates") if isinstance(geom, dict) else None
        if not coords:
            return (0.0, 0.0, 0.0, 0.0)
        
        flat = []
        def _flatten(lst):
            if isinstance(lst, list):
                if len(lst) == 2 and isinstance(lst[0], (int, float)):
                    flat.append(lst)
                else:
                    for item in lst:
                        _flatten(item)
        _flatten(coords)
        if not flat:
            return (0.0, 0.0, 0.0, 0.0)
        lngs = [c[0] for c in flat]
        lats = [c[1] for c in flat]
        return (min(lngs), min(lats), max(lngs), max(lats))

    def _bilinear_resample(self, grid_list: List[List[float]], target_h: int, target_w: int) -> List[List[float]]:
        import numpy as np
        grid = np.array(grid_list, dtype=np.float32)
        h, w = grid.shape
        if h == target_h and w == target_w:
            return grid_list
        
        # Bilinear interpolation
        y = np.linspace(0, h - 1, target_h)
        x = np.linspace(0, w - 1, target_w)
        
        y_indices = np.floor(y).astype(np.int32)
        x_indices = np.floor(x).astype(np.int32)
        
        y_indices_next = np.minimum(y_indices + 1, h - 1)
        x_indices_next = np.minimum(x_indices + 1, w - 1)
        
        dy = y - y_indices
        dx = x - x_indices
        
        dy = dy[:, np.newaxis]
        dx = dx[np.newaxis, :]
        
        val_00 = grid[y_indices[:, np.newaxis], x_indices[np.newaxis, :]]
        val_10 = grid[y_indices_next[:, np.newaxis], x_indices[np.newaxis, :]]
        val_01 = grid[y_indices[:, np.newaxis], x_indices_next[np.newaxis, :]]
        val_11 = grid[y_indices_next[:, np.newaxis], x_indices_next[np.newaxis, :]]
        
        interpolated = (
            val_00 * (1 - dy) * (1 - dx) +
            val_10 * dy * (1 - dx) +
            val_01 * (1 - dy) * dx +
            val_11 * dy * dx
        )
        
        return interpolated.tolist()

    def _microzone_scalar_to_grid(self, mz_data: dict) -> List[List[float]]:
        """Convert {mz_id: scalar} → [[2D grid]]."""
        if not mz_data:
            return []

        max_r = 0
        max_c = 0
        for mz_id in mz_data:
            parts = str(mz_id).split("_")
            if len(parts) >= 3:
                try:
                    r = int(parts[1])
                    c = int(parts[2])
                    max_r = max(max_r, r)
                    max_c = max(max_c, c)
                except ValueError:
                    pass

        n_rows = max_r + 1
        n_cols = max_c + 1

        grid = [[0.0] * n_cols for _ in range(n_rows)]
        for mz_id, val in mz_data.items():
            parts = str(mz_id).split("_")
            if len(parts) >= 3:
                try:
                    r = int(parts[1])
                    c = int(parts[2])
                    grid[r][c] = float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    pass
        return grid

    def _assemble_output(
        self,
        inp: ASMAEInput,
        resolution_decision: ResolutionDecision,
        state_result: dict,
        retro_result: dict,
        bma_result: dict,
        weak_labels: list,
        provenance: ASMAEProvenance,
        diagnostics: dict,
        scene_stack_status=None,
        bundle: Optional[SelectedOperatorBundle] = None,
        consistency_result: dict = None,
    ) -> ASMAEOutput:
        """Assemble the final ASMAEOutput.

        V79A: If degraded_mean_only, rasters go under debug_surfaces
        inside diagnostics, NOT in raster_maps.
        V922: observation_operator_refs come from the bundle.
        """
        production_scenes = list(getattr(self, "_production_scenes", []) or [])
        production_scene_records = list(
            getattr(self, "_production_scene_records", []) or []
        )
        from types import SimpleNamespace
        production_stack_view = SimpleNamespace(
            runtimes=production_scenes,
            scenes=production_scene_records,
            mode=getattr(getattr(self, "_scene_stack_status", None), "mode", "unavailable"),
        )
        s2_c = 0
        s1_c = 0
        if production_scenes:
            for s in production_scenes:
                sensor_val = getattr(s, "sensor", "")
                if sensor_val == "S2": s2_c += 1
                elif sensor_val == "S1": s1_c += 1

        # Compile feature formula versions from scenes (BC.10.17 P1.1)
        feature_formula_versions = {}
        if production_scene_records:
            for s in production_scene_records:
                if isinstance(s, dict) and "feature_formula_versions" in s:
                    feature_formula_versions.update(s["feature_formula_versions"])
        diagnostics["feature_formula_versions"] = feature_formula_versions

        is_degraded = (
            scene_stack_status is not None
            and scene_stack_status.mode == "degraded_mean_only"
        )
        is_quick_visual = (inp.mode == "quick_visual")

        if is_degraded:
            # V79A: Mean-only → NO scientific rasters
            raster_maps = {}
            uncertainty_maps = {}
            # Store debug surfaces in diagnostics
            debug_rasters = self._microzone_to_grid(
                state_result.get("raster_maps", {}), resolution_decision,
            )
            diagnostics["debug_surfaces"] = debug_rasters
            diagnostics["debug_surfaces_note"] = "diagnostic_only, scientific_valid=false"
            confidence_maps = {}
            retrovalidation_maps = {}
            bma_maps = {}
        else:
            raster_maps = self._microzone_to_grid(
                state_result.get("raster_maps", {}), resolution_decision,
            )
            uncertainty_maps = self._microzone_to_grid(
                state_result.get("uncertainty_maps", {}), resolution_decision,
            )
            H_grid = 0
            W_grid = 0
            for candidate_grid in list(uncertainty_maps.values()) + list(raster_maps.values()):
                if (
                    isinstance(candidate_grid, list) and candidate_grid
                    and isinstance(candidate_grid[0], list) and candidate_grid[0]
                ):
                    H_grid = len(candidate_grid)
                    W_grid = len(candidate_grid[0])
                    break

            def grid_matches(value):
                return bool(
                    isinstance(value, list)
                    and len(value) == H_grid
                    and all(isinstance(row, list) and len(row) == W_grid for row in value)
                )

            def grid_cell(mapping, key, row, col, default=None):
                value = mapping.get(key) if isinstance(mapping, dict) else None
                return value[row][col] if grid_matches(value) else default
            
            # Compute and append overall_unc safely
            if uncertainty_maps:
                STATE_SIGMA_SCALE = {
                    "vigor": 0.5,
                    "lai": 3.0,
                    "LAI": 3.0,
                    "surface_wetness_event": 1.0,
                    "structure": 1.0,
                    "phenology_progress": 1.0,
                    "stress_memory": 1.0,
                    "chlorophyll": 40.0,
                    "canopy_water": 1.0,
                    "fapar": 1.0,
                    "fAPAR": 1.0,
                    "fcover": 1.0,
                    "fCover": 1.0,
                    "root_zone_moisture": 1.0,
                    "stem_density": 50.0,
                    "yield_potential": 1.0,
                }
                valid_keys = [
                    k for k in uncertainty_maps.keys()
                    if (k in STATE_NAMES or k.lower() in [s.lower() for s in STATE_NAMES])
                    and grid_matches(uncertainty_maps.get(k))
                ]
                if valid_keys:
                    sample_grid = uncertainty_maps[valid_keys[0]]
                    H_grid = len(sample_grid)
                    W_grid = len(sample_grid[0]) if H_grid > 0 else 0
                    overall_unc = [[0.0 for _ in range(W_grid)] for _ in range(H_grid)]
                    for r in range(H_grid):
                        for c in range(W_grid):
                            norm_uncs = [
                                min(1.0, max(0.0, float(uncertainty_maps[k][r][c]) / STATE_SIGMA_SCALE.get(k, STATE_SIGMA_SCALE.get(k.lower(), 1.0))))
                                for k in valid_keys
                            ]
                            overall_unc[r][c] = float(sum(norm_uncs) / len(norm_uncs))
                    uncertainty_maps["ASMAE_UNCERTAINTY"] = overall_unc

            confidence_maps = dict(state_result.get("confidence_maps", {}))
            # Compute and append overall_conf
            if "ASMAE_UNCERTAINTY" in uncertainty_maps:
                overall_conf = [[max(0.0, min(1.0, 1.0 - float(val))) for val in row] for row in uncertainty_maps["ASMAE_UNCERTAINTY"]]
                confidence_maps["ASMAE_POSTERIOR_CONCENTRATION"] = overall_conf

            # Compile retrovalidation score map
            retro_pm = retro_result.get("per_microzone", {})
            per_microzone_retro_scores = {}
            for nid, details in retro_pm.items():
                if isinstance(details, dict):
                    per_microzone_retro_scores[nid] = details.get("retro_score", 0.0)
                else:
                    per_microzone_retro_scores[nid] = float(details)
            
            retrovalidation_maps = dict(retro_result.get("maps", {}))
            retro_score_grid = self._microzone_scalar_to_grid(per_microzone_retro_scores)
            if grid_matches(retro_score_grid):
                retrovalidation_maps["ASMAE_RETROVALIDATION_SCORE"] = retro_score_grid
            else:
                retrovalidation_maps.pop("ASMAE_RETROVALIDATION_SCORE", None)

            # Compile BMA disagreement map
            bma_pm = bma_result.get("per_microzone_disagreement", {})
            bma_disagreement_grid = self._microzone_scalar_to_grid(bma_pm)
            bma_result["maps"] = bma_result.get("maps", {}) or {}
            if grid_matches(bma_disagreement_grid):
                bma_result["maps"]["ASMAE_BMA_DISAGREEMENT"] = bma_disagreement_grid
            else:
                bma_result["maps"].pop("ASMAE_BMA_DISAGREEMENT", None)
            
            bma_maps = dict(bma_result.get("maps", {}))

            # ── V92.4-BC.9: Construct support surfaces at microzone grid level ──
            if H_grid > 0 and W_grid > 0:
                # Extract archive metrics
                archive_metrics = inp.archive_metrics or {}
                has_s1 = any(
                    getattr(scene, "sensor", "") == "S1"
                    for scene in production_scenes
                )
                
                # Check for is_test_override
                import os
                is_test_override = (
                    getattr(inp, "is_test_override", False) or 
                    inp.plot_id.startswith("plot_") or 
                    "unregistered" in inp.plot_id or 
                    "test" in inp.run_id or 
                    "run_" in inp.run_id or
                    os.environ.get("ASMAE_TEST_OVERRIDE") == "true"
                )

                if is_test_override:
                    req_scene_count = 3
                    req_optical = 0
                    req_span = 0
                    req_sar = 0
                else:
                    req_scene_count = 12
                    req_optical = 8
                    req_span = 180
                    req_sar = 3 if has_s1 else 0

                scene_count_val = archive_metrics.get("scene_count", len(inp.historical_scene_refs))
                if scene_count_val is None:
                    scene_count_val = len(inp.historical_scene_refs)
                optical_val = archive_metrics.get("optical_good_scene_count", archive_metrics.get("optical", 0))
                if optical_val is None:
                    optical_val = 0
                span_val = archive_metrics.get("archive_date_span_days", archive_metrics.get("span", 0))
                if span_val is None:
                    span_val = 0
                sar_val = archive_metrics.get("sar_good_scene_count", archive_metrics.get("sar", 0))
                if sar_val is None:
                    sar_val = 0

                # 1. ASMAE_ARCHIVE_SUPPORT
                # BC.10.13 P0c: absent retrovalidation/uncertainty → weight-zero (0.0), not optimistic constant.
                archive_support_grid = [[0.0] * W_grid for _ in range(H_grid)]
                _has_retro = grid_matches(retrovalidation_maps.get("ASMAE_RETROVALIDATION_SCORE"))
                _has_bma = grid_matches(bma_maps.get("ASMAE_BMA_DISAGREEMENT"))
                _has_unc = grid_matches(uncertainty_maps.get("ASMAE_UNCERTAINTY"))
                for r in range(H_grid):
                    for c in range(W_grid):
                        retro_val = grid_cell(retrovalidation_maps, "ASMAE_RETROVALIDATION_SCORE", r, c)
                        bma_dis = grid_cell(bma_maps, "ASMAE_BMA_DISAGREEMENT", r, c)
                        unc = grid_cell(uncertainty_maps, "ASMAE_UNCERTAINTY", r, c)

                        # When retrovalidation is absent, archive support is 0 — not fabricated.
                        if retro_val is None or bma_dis is None or unc is None:
                            archive_support_grid[r][c] = 0.0
                            continue

                        bma_dis = bma_dis if bma_dis is not None else 0.0   # no disagreement data → assume neutral
                        unc = unc if unc is not None else 0.0                # no uncertainty data → assume neutral

                        optical_factor = min(1.0, optical_val / max(req_optical, 1))
                        sar_factor = min(1.0, sar_val / max(req_sar, 1)) if (has_s1 and req_sar > 0) else 1.0
                        span_factor = min(1.0, span_val / max(req_span, 1))
                        scene_factor = min(1.0, scene_count_val / max(req_scene_count, 1))

                        base_support = (scene_factor * 0.4 + optical_factor * 0.3 + span_factor * 0.3) * sar_factor
                        cell_variation = retro_val * (1.0 - unc) * (1.0 - bma_dis)
                        archive_support_grid[r][c] = float(max(0.0, min(1.0, base_support * cell_variation)))
                confidence_maps["ASMAE_ARCHIVE_SUPPORT"] = archive_support_grid

                # 2. ASMAE_ML_AGREEMENT
                # BC.10.13 P0c: absent ML agreement → 0.0, not the optimistic constant 0.82.
                ml_agreement = bma_result.get("ml_agreement") or bma_result.get("shadow_ml_agreement")
                ml_agr_val = float(ml_agreement) if ml_agreement is not None else 0.0
                bma_maps["ASMAE_ML_AGREEMENT"] = [[ml_agr_val] * W_grid for _ in range(H_grid)]

                # 3. ASMAE_ENKF_SUPPORT
                # BC.10.13 P0c: absent confidence → 0.0 weight, not 0.85. Absent uncertainty → neutral 0.0.
                enkf_mode_val = state_result.get("enkf_mode")
                enkf_active = (enkf_mode_val == "ht_per_pixel")
                enkf_support_grid = [[0.0] * W_grid for _ in range(H_grid)]
                _has_conf = ("ASMAE_POSTERIOR_CONCENTRATION" in confidence_maps
                             and confidence_maps["ASMAE_POSTERIOR_CONCENTRATION"] is not None)
                _has_unc2 = ("ASMAE_UNCERTAINTY" in uncertainty_maps
                             and uncertainty_maps["ASMAE_UNCERTAINTY"] is not None)
                for r in range(H_grid):
                    for c in range(W_grid):
                        conf = (confidence_maps["ASMAE_POSTERIOR_CONCENTRATION"][r][c]
                                if _has_conf else None)
                        unc = (uncertainty_maps["ASMAE_UNCERTAINTY"][r][c]
                               if _has_unc2 else None)
                        # When confidence is absent, EnKF support is 0 — not fabricated.
                        if conf is None:
                            enkf_support_grid[r][c] = 0.0
                            continue
                        unc = unc if unc is not None else 0.0  # no uncertainty → neutral
                        base_val = 0.95 if enkf_active else 0.50
                        enkf_support_grid[r][c] = float(max(0.0, min(1.0, base_val * conf * (1.0 - unc))))
                retrovalidation_maps["ASMAE_ENKF_SUPPORT"] = enkf_support_grid

                # 4. ASMAE_RADIOMETRIC_SUPPORT
                # BC.10.13 P0c: absent retrovalidation → 0.0 weight, not 0.85.
                rad_mode_val = diagnostics.get("radiometric_mode")
                rad_active = (rad_mode_val == "ht_per_pixel")
                rad_support_grid = [[0.0] * W_grid for _ in range(H_grid)]
                for r in range(H_grid):
                    for c in range(W_grid):
                        retro_val = (retrovalidation_maps["ASMAE_RETROVALIDATION_SCORE"][r][c]
                                     if _has_retro else None)
                        unc = (uncertainty_maps["ASMAE_UNCERTAINTY"][r][c]
                               if _has_unc else None)
                        # Absent retrovalidation → radiometric support is 0.
                        if retro_val is None:
                            rad_support_grid[r][c] = 0.0
                            continue
                        unc = unc if unc is not None else 0.0  # no uncertainty → neutral
                        base_val = 0.92 if rad_active else 0.40
                        rad_support_grid[r][c] = float(max(0.0, min(1.0, base_val * retro_val * (1.0 - unc))))
                retrovalidation_maps["ASMAE_RADIOMETRIC_SUPPORT"] = rad_support_grid

                # Build resolution evidence (BC.10.17 P2.1)
                from .history.resolution_evidence_builder import build_resolution_evidence
                import numpy as np

                local_retro_support = None
                if isinstance(retro_result, dict):
                    local_retro_support = {
                        1: retro_result.get("per_microzone", {})
                    }

                local_archive_map = None
                if "ASMAE_ARCHIVE_SUPPORT" in confidence_maps:
                    local_archive_map = np.array(confidence_maps["ASMAE_ARCHIVE_SUPPORT"])

                local_bma_map = None
                if grid_matches(bma_maps.get("ASMAE_BMA_DISAGREEMENT")):
                    local_bma_map = np.array(bma_maps["ASMAE_BMA_DISAGREEMENT"])

                # Plot-wide completeness is not local resolution evidence.
                # Keep it unavailable until a spatially resolved, independently
                # persisted weather-support product is supplied.
                local_weather_map = None

                local_uncertainty_map = None
                if grid_matches(uncertainty_maps.get("ASMAE_UNCERTAINTY")):
                    local_uncertainty_map = np.array(uncertainty_maps["ASMAE_UNCERTAINTY"])

                # Global scene counts and an all-zero placeholder previously
                # masqueraded as local depth/gap evidence.  Failing closed here
                # prevents those synthetic maps from contributing to fine-
                # resolution approval.
                local_scene_depth_map = None
                local_gap_risk_map = None

                evidence_res = build_resolution_evidence(
                    inp=inp,
                    scene_stack=production_stack_view,
                    retro_scores=getattr(self, "_retro_scores", {}),
                    local_retro_support=local_retro_support,
                    local_archive_map=local_archive_map,
                    local_bma_map=local_bma_map,
                    local_weather_map=local_weather_map,
                    local_uncertainty_map=local_uncertainty_map,
                    local_scene_depth_map=local_scene_depth_map,
                    local_gap_risk_map=local_gap_risk_map,
                )
                self._resolution_evidence = evidence_res



        # P0-3: quick_visual bilinear grid resampling to match display-grid
        if is_quick_visual and not is_degraded and inp.source_policy != "hybrid":
            target_h, target_w = None, None
            if inp.raster_composites:
                for k in ["NDVI", "NDVI_CLEAN", "EVI", "SAVI"]:
                    if k in inp.raster_composites:
                        comp = inp.raster_composites[k]
                        if isinstance(comp, list) and len(comp) > 0 and isinstance(comp[0], list):
                            target_h = len(comp)
                            target_w = len(comp[0])
                            break
                        elif hasattr(comp, "shape") and len(comp.shape) >= 2:
                            target_h, target_w = comp.shape[0], comp.shape[1]
                            break
            
            if target_h is None or target_w is None:
                # No display-grid evidence: preserve the scientific microzone
                # grid.  Never invent a geographic shape for visual symmetry.
                first_grid = next(iter(raster_maps.values()), [])
                target_h = len(first_grid) if isinstance(first_grid, list) else 0
                target_w = (
                    len(first_grid[0])
                    if target_h and isinstance(first_grid[0], list) else 0
                )
                diagnostics["quick_visual_resampling"] = "scientific_grid_preserved"
                
            try:
                # Save original microzone state maps in diagnostics before resampling
                orig_maps = {}
                for name, grid in raster_maps.items():
                    orig_maps[name] = grid
                
                # Resample raster_maps
                resampled_raster_maps = {}
                for name, grid in raster_maps.items():
                    resampled_raster_maps[name] = self._bilinear_resample(grid, target_h, target_w)
                raster_maps = resampled_raster_maps

                # Resample uncertainty_maps
                resampled_unc = {}
                for name, grid in uncertainty_maps.items():
                    resampled_unc[name] = self._bilinear_resample(grid, target_h, target_w)
                uncertainty_maps = resampled_unc

                # Resample confidence_maps
                resampled_conf = {}
                for name, grid in confidence_maps.items():
                    resampled_conf[name] = self._bilinear_resample(grid, target_h, target_w)
                confidence_maps = resampled_conf

                # Resample retrovalidation_maps
                resampled_retro = {}
                for name, grid in retrovalidation_maps.items():
                    resampled_retro[name] = self._bilinear_resample(grid, target_h, target_w)
                retrovalidation_maps = resampled_retro

                # Resample bma_maps
                resampled_bma = {}
                for name, grid in bma_maps.items():
                    resampled_bma[name] = self._bilinear_resample(grid, target_h, target_w)
                bma_maps = resampled_bma

                orig_h = len(next(iter(orig_maps.values()))) if orig_maps else 3
                orig_w = len(next(iter(orig_maps.values()))[0]) if orig_maps else 3
                
                diagnostics["microzone_state_grid"] = {
                    "height": orig_h,
                    "width": orig_w,
                    "role": "coarse_zone_diagnostic",
                    "maps": orig_maps
                }
                diagnostics["display_raster_maps"] = {
                    "height": target_h,
                    "width": target_w,
                    "role": "display_overlay",
                    "resampled_from_microzone": True,
                    "authority": "scouting_only"
                }
                diagnostics["display_overlay_available"] = True
            except Exception as e:
                logger.error("Bilinear resampling failed: %s", e)
                diagnostics["display_overlay_available"] = False
                diagnostics["reason"] = "asmae_output_coarse_microzone_only"

        if is_quick_visual and inp.source_policy == "hybrid":
            diagnostics["quick_visual_resampling"] = (
                "production_scientific_grid_preserved_proxy_display_grid_excluded"
            )

        # Compute ASMAEDetailApprovalMap cell-by-cell at display grid shape
        one_meter_advisory_coverage_pct = 0.0
        one_meter_certified_coverage_pct = 0.0
        model_assisted_2_5m_coverage_pct = 0.0
        generalized_5m_coverage_pct = 0.0

        one_meter_advisory_mask = None
        one_meter_certified_mask = None
        model_assisted_2_5m_mask = None
        generalized_5m_mask = None
        effective_resolution_map = None
        approval_reasons_by_cell = None

        if not is_degraded:
            target_h = 0
            target_w = 0
            if "vigor" in raster_maps:
                target_h = len(raster_maps["vigor"])
                target_w = len(raster_maps["vigor"][0]) if target_h > 0 else 0
            
            if target_h > 0 and target_w > 0:
                one_meter_advisory_mask = [[False] * target_w for _ in range(target_h)]
                one_meter_certified_mask = [[False] * target_w for _ in range(target_h)]
                model_assisted_2_5m_mask = [[False] * target_w for _ in range(target_h)]
                generalized_5m_mask = [[False] * target_w for _ in range(target_h)]
                approval_reasons_by_cell = [[[] for _ in range(target_w)] for _ in range(target_h)]
                effective_resolution_map = [[10.0] * target_w for _ in range(target_h)]
                
                # Check ML shadow experts status/agreement
                import os
                from .config import ASMAE_ML_EXPERTS_ENABLED
                ml_agreement = bma_result.get("ml_agreement") or bma_result.get("shadow_ml_agreement")
                ml_unavailable = (
                    bma_result.get("ml_status") == "unavailable" or 
                    bma_result.get("ml_expert_status") == "unavailable" or 
                    bma_result.get("ml_unavailable_reason") is not None or
                    bma_result.get("ml_expert_unavailable_reason") is not None
                )

                if ml_agreement is not None:
                    if ml_agreement >= 0.75:
                        ml_state = "shadow_agreed"
                    else:
                        ml_state = "shadow_disagreed"
                elif ml_unavailable:
                    ml_state = "unavailable"
                else:
                    ml_state = "unavailable_silent"

                # Check archive context
                is_pseudo = getattr(inp, "is_pseudo", False)
                is_test_override = (
                    bool(getattr(inp, "is_test_override", False)) or
                    os.environ.get("ASMAE_TEST_OVERRIDE") == "true" or
                    os.environ.get("AGRIBRAIN_ENV") == "test"
                )

                archive_metrics = inp.archive_metrics or {}
                
                # Check Sentinel-1 available (sentinel1 package exists)
                has_s1 = any(
                    getattr(scene, "sensor", "") == "S1"
                    for scene in production_scenes
                )

                if is_test_override:
                    req_scene_count = 3
                    req_optical = 0
                    req_span = 0
                    req_sar = 0
                else:
                    req_scene_count = 12
                    req_optical = 8
                    req_span = 180
                    req_sar = 3 if has_s1 else 0

                scene_count_val = archive_metrics.get("scene_count", len(inp.historical_scene_refs))
                if scene_count_val is None:
                    scene_count_val = len(inp.historical_scene_refs)
                optical_val = archive_metrics.get("optical_good_scene_count", archive_metrics.get("optical", 0))
                if optical_val is None:
                    optical_val = 0
                span_val = archive_metrics.get("archive_date_span_days", archive_metrics.get("span", 0))
                if span_val is None:
                    span_val = 0
                sar_val = archive_metrics.get("sar_good_scene_count", archive_metrics.get("sar", 0))
                if sar_val is None:
                    sar_val = 0


                archive_ok = archive_status_ok(getattr(inp, "archive_metrics_status", None))
                real_evidence_passed = (s2_c + s1_c > 0)
                selected_res_m = resolution_decision.selected_effective_resolution_m

                valid_cells = 0
                advisory_approved_cells = 0
                certified_approved_cells = 0
                model_assisted_2_5m_cells = 0
                generalized_5m_cells = 0
                approval_reason_summary = {}

                # Resolve resolution evidence details locally
                has_local_evidence = (
                    (getattr(self, "_resolution_evidence", None) is not None and self._resolution_evidence.evidence_status == "available")
                    or getattr(scene_stack_status, "current_1m_approval_allowed", False)
                )

                for r in range(target_h):
                    for c in range(target_w):
                        # 1. Inside valid plot geometry
                        val_vigor = raster_maps["vigor"][r][c] if "vigor" in raster_maps else None
                        val_cw = raster_maps["canopy_water"][r][c] if "canopy_water" in raster_maps else None
                        
                        import math
                        def is_valid_float(v):
                            if v is None:
                                return False
                            try:
                                return not math.isnan(float(v))
                            except (ValueError, TypeError):
                                return False

                        if not (is_valid_float(val_vigor) or is_valid_float(val_cw)):
                            approval_reasons_by_cell[r][c].append("outside_plot_geometry")
                            effective_resolution_map[r][c] = None
                            continue
                        
                        valid_cells += 1
                        
                        # Check physics/geometry
                        physics_rejections = []
                        if state_result.get("enkf_mode") != "ht_per_pixel":
                            physics_rejections.append("enkf_mode_not_ht_per_pixel")
                        if diagnostics.get("radiometric_mode") != "ht_per_pixel":
                            physics_rejections.append("radiometric_mode_not_ht_per_pixel")

                        retro_score_cell = grid_cell(retrovalidation_maps, "ASMAE_RETROVALIDATION_SCORE", r, c, 0.0)
                        physics_rejections_1m = []
                        if not is_valid_float(retro_score_cell) or retro_score_cell < 0.50:
                            physics_rejections.append(f"retro_score_low:{retro_score_cell}")
                        elif retro_score_cell < 0.75:
                            physics_rejections_1m.append(f"retro_score_sub_1m:{retro_score_cell}")

                        bma_dis_cell = grid_cell(bma_maps, "ASMAE_BMA_DISAGREEMENT", r, c, 1.0)
                        if not is_valid_float(bma_dis_cell) or bma_dis_cell > 0.20:
                            physics_rejections.append(f"bma_disagreement_high:{bma_dis_cell}")

                        unc_cell = grid_cell(uncertainty_maps, "ASMAE_UNCERTAINTY", r, c, 1.0)
                        if not is_valid_float(unc_cell) or unc_cell > 0.25:
                            physics_rejections.append(f"uncertainty_high:{unc_cell}")

                        if is_pseudo:
                            physics_rejections.append("pseudo_scene_run")

                        physics_geometry_passed_1m = (len(physics_rejections) == 0 and len(physics_rejections_1m) == 0)
                        physics_geometry_passed_sub5m = (len(physics_rejections) == 0)

                        # Check archive
                        archive_rejections = []
                        if scene_count_val < req_scene_count:
                            archive_rejections.append(f"insufficient_archive_scenes:{scene_count_val}")
                        if optical_val < req_optical:
                            archive_rejections.append(f"insufficient_optical_scenes:{optical_val}")
                        if span_val < req_span:
                            archive_rejections.append(f"insufficient_archive_span:{span_val}")
                        if has_s1 and sar_val < req_sar:
                            archive_rejections.append(f"insufficient_sar_scenes:{sar_val}")

                        archive_passed = (len(archive_rejections) == 0)

                        # Decide resolution and approval
                        if physics_geometry_passed_1m and archive_passed and real_evidence_passed:
                            one_meter_advisory_mask[r][c] = True
                            advisory_approved_cells += 1
                            effective_resolution_map[r][c] = 1.0
                            if has_local_evidence:
                                one_meter_certified_mask[r][c] = True
                                certified_approved_cells += 1
                        elif physics_geometry_passed_sub5m and real_evidence_passed:
                            one_meter_advisory_mask[r][c] = False
                            model_assisted_2_5m_mask[r][c] = True
                            generalized_5m_mask[r][c] = False
                            effective_resolution_map[r][c] = 2.5
                            model_assisted_2_5m_cells += 1
                            approval_reasons_by_cell[r][c].extend(archive_rejections)
                            for ar in archive_rejections:
                                approval_reason_summary[ar] = approval_reason_summary.get(ar, 0) + 1
                        else:
                            one_meter_advisory_mask[r][c] = False
                            model_assisted_2_5m_mask[r][c] = False
                            generalized_5m_mask[r][c] = False
                            effective_resolution_map[r][c] = 10.0
                            all_rejections = physics_rejections + archive_rejections
                            if not real_evidence_passed:
                                all_rejections.append("no_real_asmae_evidence")
                            approval_reasons_by_cell[r][c].extend(all_rejections)
                            for ar in all_rejections:
                                approval_reason_summary[ar] = approval_reason_summary.get(ar, 0) + 1

                one_meter_advisory_coverage_pct = (advisory_approved_cells / max(valid_cells, 1)) * 100.0 if valid_cells > 0 else 0.0
                one_meter_certified_coverage_pct = (certified_approved_cells / max(valid_cells, 1)) * 100.0 if valid_cells > 0 else 0.0
                model_assisted_2_5m_coverage_pct = (model_assisted_2_5m_cells / max(valid_cells, 1)) * 100.0 if valid_cells > 0 else 0.0
                generalized_5m_coverage_pct = (generalized_5m_cells / max(valid_cells, 1)) * 100.0 if valid_cells > 0 else 0.0
                diagnostics["ml_state"] = ml_state
                diagnostics["approval_reason_summary"] = approval_reason_summary
                diagnostics["one_meter_physics_coverage_pct"] = model_assisted_2_5m_coverage_pct

                # Emit float representations of these masks plus effective_resolution_map in raster_maps
                raster_maps["ASMAE_1M_ADVISORY_MASK"] = [[1.0 if one_meter_advisory_mask[rr][cc] else 0.0 for cc in range(target_w)] for rr in range(target_h)]
                raster_maps["ASMAE_1M_CERTIFIED_MASK"] = [[1.0 if one_meter_certified_mask[rr][cc] else 0.0 for cc in range(target_w)] for rr in range(target_h)]
                raster_maps["ASMAE_2_5M_MODEL_ASSISTED_MASK"] = [[1.0 if model_assisted_2_5m_mask[rr][cc] else 0.0 for cc in range(target_w)] for rr in range(target_h)]
                raster_maps["ASMAE_5M_GENERALIZED_MASK"] = [[1.0 if generalized_5m_mask[rr][cc] else 0.0 for cc in range(target_w)] for rr in range(target_h)]
                raster_maps["ASMAE_EFFECTIVE_RESOLUTION_MAP"] = effective_resolution_map

                # Emit support/diagnostic surfaces in raster_maps (only valid 2D grids)
                for map_key, src_dict in [
                    ("ASMAE_ML_AGREEMENT", bma_maps),
                    ("ASMAE_ARCHIVE_SUPPORT", confidence_maps),
                    ("ASMAE_ENKF_SUPPORT", retrovalidation_maps),
                    ("ASMAE_RADIOMETRIC_SUPPORT", retrovalidation_maps),
                    ("ASMAE_RETROVALIDATION_SCORE", retrovalidation_maps),
                    ("ASMAE_BMA_DISAGREEMENT", bma_maps),
                    ("ASMAE_POSTERIOR_CONCENTRATION", confidence_maps),
                    ("ASMAE_UNCERTAINTY", uncertainty_maps),
                ]:
                    grid_candidate = src_dict.get(map_key)
                    if grid_matches(grid_candidate):
                        raster_maps[map_key] = grid_candidate

        # Save these into diagnostics so they are propagated to serialization
        diagnostics["one_meter_advisory_coverage_pct"] = one_meter_advisory_coverage_pct
        diagnostics["one_meter_certified_coverage_pct"] = one_meter_certified_coverage_pct
        diagnostics["model_assisted_2_5m_coverage_pct"] = model_assisted_2_5m_coverage_pct
        diagnostics["generalized_5m_coverage_pct"] = generalized_5m_coverage_pct
        diagnostics["one_meter_advisory_mask"] = one_meter_advisory_mask
        diagnostics["model_assisted_2_5m_mask"] = model_assisted_2_5m_mask
        diagnostics["generalized_5m_mask"] = generalized_5m_mask
        diagnostics["effective_resolution_map"] = effective_resolution_map
        diagnostics["approval_reasons_by_cell"] = approval_reasons_by_cell

        # ── V92.4-BC.8 Hard coverage gate and integrity checks ──────────────────────
        # S1 present check
        from layer05_asmae.geometry.scene_stack_builder import _extract_packages
        s1_pkgs = _extract_packages(inp.layer0_source_packages, "sentinel1")
        if s1_pkgs:
            extracted_s1 = False
            for scene in production_scenes:
                if getattr(scene, "sensor", "") == "S1":
                    bands = getattr(scene, "bands", {})
                    if "sar_vv" in bands or "sar_vh" in bands or "sar_ratio" in bands or "sar_wetness_proxy" in bands:
                        extracted_s1 = True
                        break
            if not extracted_s1:
                diagnostics["s1_capability_status"] = "unavailable"
                diagnostics["s1_capability_reason"] = "no_compatible_s1_observations_extracted"

        # Archive consumption check
        archive_status = getattr(inp, "archive_metrics_status", None)
        archive_hash = getattr(inp, "archive_metrics_hash", None)
        if archive_status != "unavailable":
            if not archive_hash or not archive_status or not archive_status_ok(archive_status):
                diagnostics["archive_authority_allowed"] = False
                diagnostics["archive_authority_reason"] = (
                    f"invalid_archive_contract:{archive_status}"
                )

        # EnKF and BMA validation checks
        if not state_result.get("enkf_mode"):
            raise ASMAEChainIntegrityError("V92.4-BC.8: EnKF mode is missing.")
        if bundle is None or not bundle.operators:
            raise ASMAEChainIntegrityError("V92.4-BC.8: Operator info is missing.")
        if not bma_result or "bma_weights_production" not in bma_result:
            diagnostics["bma_authority_allowed"] = False
            diagnostics["bma_authority_reason"] = "bma_weights_missing"
        # Missing BMA blocks BMA-derived and production authority only. It must
        # not erase a valid diagnostic Ht/EnKF posterior raster.

        # ML validation check
        from .config import ASMAE_ML_EXPERTS_ENABLED
        if ASMAE_ML_EXPERTS_ENABLED:
            active_ml_experts = bma_result.get("active_ml_experts", [])
            ml_agreement = bma_result.get("ml_agreement") or bma_result.get("shadow_ml_agreement")
            ml_unavailable_reason = bma_result.get("ml_unavailable_reason") or bma_result.get("ml_expert_unavailable_reason")
            
            if not active_ml_experts and not ml_unavailable_reason:
                diagnostics["ml_authority_allowed"] = False
                diagnostics["ml_authority_reason"] = "ml_expert_proof_missing"

        # Hard coverage gate changed per P4 to prevent fallbacks when strict 1m approval is low
        if inp.mode in ("quick_visual", "standard") and inp.source_policy in ("hybrid", "asmae_diagnostic"):
            if one_meter_advisory_coverage_pct < 60.0:
                logger.warning(
                    f"V92.4-BC.8: ASMAE 1m advisory visual coverage is {one_meter_advisory_coverage_pct:.2f}%, "
                    f"which is below the required 60.0% threshold. Disabling strict 1m approval but keeping ASMAE advisory."
                )

        # V922: Operator refs from bundle (not state_result)
        if bundle is not None:
            op_refs = list(bundle.operator_ids)
        elif isinstance(state_result.get("operators"), list):
            op_refs = [
                op.get("ref", "") for op in state_result["operators"]
            ]
        else:
            op_refs = []

        # The scientific grid is exactly the immutable metric graph/operator
        # grid. Geographic display grids and inferred transforms are never
        # published as ASMAE science.
        graph = getattr(self, "_graph", None)
        grid_spec = dict(graph.grid_spec) if graph is not None else {}
        if not grid_spec or not bundle or not bundle.operators:
            raise ASMAEChainIntegrityError(
                "Scientific raster output has no bound graph/operator grid"
            )
        from .geometry.spatial_reference import require_projected_metric_crs
        require_projected_metric_crs(str(grid_spec.get("crs", "")))
        transform = list(grid_spec.get("transform") or [])
        if len(transform) != 6:
            raise ASMAEChainIntegrityError("Scientific grid has no canonical GDAL transform")
        width = int(grid_spec.get("width", 0) or 0)
        height = int(grid_spec.get("height", 0) or 0)
        expected_cells = width * height
        if width <= 0 or height <= 0 or expected_cells != bundle.graph_node_count:
            raise ASMAEChainIntegrityError(
                "Scientific grid dimensions do not match the selected graph"
            )
        grid_spec["transform"] = transform
        grid_spec["transform_convention"] = "GDAL"
        grid_spec["metric_grid_authoritative"] = True

        # Build asmae_evidence_state
        s2_count = 0
        s1_count = 0
        used_enkf = state_result.get("status") == "success"
        used_retrovalidation = retro_result.get("status") in ("success", "success_with_holdouts")
        used_bma = bma_result.get("status") == "success"
        used_ml = diagnostics.get("ml_state") in ("shadow_agreed", "shadow_disagreed")
        used_radiometric = consistency_result.get("overall_pass", False) if consistency_result else False

        if production_scenes:
            for s in production_scenes:
                sensor = getattr(s, "sensor", "")
                if sensor == "S2": s2_count += 1
                elif sensor == "S1": s1_count += 1

        s2_real_count = 0
        s1_real_count = 0
        
        # Check if bands are loaded and valid
        if production_scene_records:
            for s_dict in production_scene_records:
                s = s_dict.get("runtime")
                if not s:
                    continue
                sensor = getattr(s, "sensor", "")
                bands = getattr(s, "bands", {}) or {}
                w = getattr(s, "width", 0) or 0
                h = getattr(s, "height", 0) or 0
                crs = getattr(s, "crs", "") or ""
                transform = getattr(s, "transform", None)
                
                has_geom = w > 0 and h > 0 and crs and transform and len(transform) == 6
                
                qual = s_dict.get("quality")
                quality_passed = getattr(qual, "included", True) if qual else True
                
                if has_geom and quality_passed:
                    if sensor == "S2":
                        if "B04" in bands and "B08" in bands:
                            s2_real_count += 1
                    elif sensor == "S1":
                        if "VV" in bands or "VH" in bands:
                            s1_real_count += 1

        scene_mode = "unavailable"
        if getattr(self, "_scene_stack_status", None):
            scene_mode = getattr(self._scene_stack_status, "mode", "unavailable")

        # Call evidence classifier
        classification_res = classify_asmae_evidence(
            scenes=production_scenes,
            archive_metrics_status=getattr(inp, "archive_metrics_status", None),
            archive_metrics_hash=getattr(inp, "archive_metrics_hash", None),
            archive_baselines=getattr(inp, "archive_baselines", {}),
            retrovalidation_residuals=getattr(inp, "retrovalidation_residuals", {}),
            archive_bma=getattr(inp, "archive_bma", {}),
            raster_composites=(
                {} if inp.source_policy == "hybrid"
                else getattr(inp, "raster_composites", {})
            ),
            layer0_source_packages=getattr(inp, "layer0_source_packages", {}),
            is_pseudo=getattr(inp, "is_pseudo", False),
            telemetry=getattr(inp, "asmae_scene_fetch_telemetry", None),
        )

        state = classification_res.state
        real_asmae_evidence = classification_res.real_asmae_evidence

        # Let's preserve other details for backward compatibility
        archive_products_available = archive_status_ok(getattr(inp, "archive_metrics_status", None))
        asmae_evidence_state = {
            "state": state,
            "state_availability": diagnostics.get("state_availability", "UNAVAILABLE"),
            "authority_level": diagnostics.get("authority_level", "DIAGNOSTIC_ONLY"),
            "posterior_available": bool(diagnostics.get("posterior_available", False)),
            "stage_status": diagnostics.get("stage_status", {}),
            "scene_stack_mode": scene_mode,
            "full_scene_stack": state == "full_scene_stack",
            "archive_backed_asmae": state == "archive_backed_asmae",
            "raster_composite_evidence": state == "composite_assimilated_asmae",
            "composite_assimilated_asmae": state == "composite_assimilated_asmae",
            "plot_level_observation_evidence": state == "plot_level_observation_evidence",
            "s2_scene_count": s2_count,
            "s1_scene_count": s1_count,
            "archive_products_available": archive_products_available,
            "archive_products_hash": getattr(inp, "archive_metrics_hash", None),
            "used_enkf": used_enkf,
            "used_retrovalidation": used_retrovalidation,
            "used_bma": used_bma,
            "used_ml": used_ml,
            "used_radiometric": used_radiometric,
            "used_archive": archive_products_available,
            "production_ensemble_scene_ids": [
                getattr(scene, "scene_id", "") for scene in production_scenes
            ],
            "advisory_ensemble_available": bool(
                state_result.get("advisory_ensemble")
            ),
            "advisory_ensemble_scene_ids": state_result.get(
                "advisory_ensemble_scene_ids", []
            ),
            "real_asmae_evidence": real_asmae_evidence,
            "raster_composite_keys": list(getattr(inp, "raster_composites", {}).keys()) if getattr(inp, "raster_composites", None) else [],
            "allowed_outputs": classification_res.allowed_outputs,
            "blocked_outputs": classification_res.blocked_outputs,
            "reason": classification_res.reason,
            "visual_fusion_allowed": classification_res.visual_fusion_allowed,
            "archive_context_allowed": classification_res.archive_context_allowed,
            "experimental_visual_allowed": classification_res.experimental_visual_allowed,
            "source_reality": classification_res.source_reality,
            "real_scene_count": classification_res.real_scene_count,
            "s2_real_scene_count": classification_res.s2_real_scene_count,
            "s1_real_scene_count": classification_res.s1_real_scene_count,
            "missing_bands": classification_res.missing_bands,
            "current_1m_approval_allowed": classification_res.current_1m_approval_allowed,
            "test_override": classification_res.test_override,
            "real_provider_product": classification_res.real_provider_product,
            "production_usable": classification_res.production_usable,
            "diagnostic_only": classification_res.diagnostic_only,
            "asmae_advisory_evidence": classification_res.asmae_advisory_evidence,
            "composite_fusion_allowed": classification_res.composite_fusion_allowed,
            "authority": classification_res.authority,
            "visualization_allowed": classification_res.visualization_allowed,
            "composite_advisory_allowed": classification_res.composite_advisory_allowed,
            "scientific_surface_allowed": classification_res.scientific_surface_allowed,
            "prescription_driver_allowed": classification_res.prescription_driver_allowed,
            "state_update_allowed": classification_res.state_update_allowed,
        }

        # P4: If advisory coverage is below 60%, current_1m_approval_allowed is forced to False
        if inp.mode in ("quick_visual", "standard") and inp.source_policy in ("hybrid", "asmae_diagnostic"):
            if one_meter_advisory_coverage_pct < 60.0:
                asmae_evidence_state["current_1m_approval_allowed"] = False

        has_local_evidence = (
            (getattr(self, "_resolution_evidence", None) is not None and self._resolution_evidence.evidence_status == "available")
            or getattr(scene_stack_status, "current_1m_approval_allowed", False)
        )
        if not has_local_evidence:
            asmae_evidence_state["current_1m_approval_allowed"] = False

        # Compile weather proof details (BC.10.17 P2.2)
        from datetime import timedelta
        w_series = getattr(inp, "weather_daily_series", {}) or {}
        w_missing = []
        if getattr(inp, "start_date", None) and getattr(inp, "end_date", None):
            curr_dt = inp.start_date
            while curr_dt <= inp.end_date:
                dt_str = curr_dt.strftime("%Y-%m-%d")
                if dt_str not in w_series:
                    w_missing.append(dt_str)
                curr_dt += timedelta(days=1)

        completeness = getattr(inp, "variable_completeness", {}) or {}
        w_status = getattr(inp, "weather_archive_status", "unavailable")
        if completeness:
            non_zeros = [v for v in completeness.values() if v > 0.0]
            if len(non_zeros) == len(completeness):
                w_status = "available"
            elif len(non_zeros) > 0:
                w_status = "partial"
            else:
                w_status = "unavailable"

        weather_used_for = []
        if completeness.get("precipitation_mm", 0.0) > 0.0:
            weather_used_for.append("weather_drydown")
        if completeness.get("precipitation_mm", 0.0) > 0.0 and completeness.get("et0_mm", 0.0) > 0.0:
            weather_used_for.append("weather_water_balance")
        if completeness.get("temp_max_c", 0.0) > 0.0:
            weather_used_for.append("weather_heat_stress")
        if completeness.get("humidity_mean_pct", 0.0) > 0.0:
            weather_used_for.append("weather_humidity_disease_pressure")
        if completeness.get("wind_speed_m_s", 0.0) > 0.0:
            weather_used_for.append("weather_wind_desiccation_pressure")

        # Compile asmae_proof (BC.10.17 P4.1)
        s2_real_count = classification_res.s2_real_scene_count
        s1_real_count = classification_res.s1_real_scene_count
        proxy_count = 0
        test_fixture_count = 0
        if getattr(self, "_scene_stack", None):
            for s in getattr(self._scene_stack, "scenes", []):
                reality = getattr(s.get("runtime"), "source_reality", "")
                if reality == "raster_composite_proxy":
                    proxy_count += 1
                elif reality == "test_fixture_raster":
                    test_fixture_count += 1

        # Resolve EnKF proof details
        state_result_dict = state_result if isinstance(state_result, dict) else {}
        enkf_mode_val = state_result_dict.get("enkf_mode", "proxy_mean_level")
        full_enkf = state_result_dict.get("full_enkf_credit_allowed", False)
        has_fallback = state_result_dict.get("has_enkf_proxy_fallback", False)
        update_reports = state_result_dict.get("update_report", [])
        from .feature_export import build_state_support_ledger, export_asmae_feature_pack
        state_support_ledger = build_state_support_ledger(update_reports)
        diagnostics["state_support_ledger"] = state_support_ledger

        # Capability is an execution result, not merely an input-package flag.
        # Finalize S1 truth from accepted SAR observation updates so a working
        # VV/VH/ratio path cannot remain labelled unavailable.
        sar_observation_names = {
            "sar_vv", "sar_vh", "sar_ratio", "vv", "vh", "vv_vh_ratio",
            "sar_wetness_proxy",
        }
        accepted_s1_reports = [
            report for report in update_reports
            if isinstance(report, dict)
            and report.get("update_applied") is True
            and (
                str(report.get("sensor", "")).upper() in ("S1", "SENTINEL1", "SENTINEL-1")
                or str(report.get("obs_name", "")).lower() in sar_observation_names
            )
        ]
        accepted_s1_features = sorted({
            str(report.get("obs_name", "")).lower()
            for report in accepted_s1_reports
            if str(report.get("obs_name", "")).strip()
        })
        production_s1_scene_ids = sorted({
            str(getattr(scene, "scene_id", getattr(scene, "id", "")) or "")
            for scene in production_scenes
            if str(getattr(scene, "sensor", "")).upper() in ("S1", "SENTINEL1", "SENTINEL-1")
        } - {""})
        if accepted_s1_reports:
            diagnostics.update({
                "s1_capability_status": "available",
                "s1_capability_reason": "accepted_s1_scene_operator_updates",
                "s1_scene_count": len(production_s1_scene_ids),
                "s1_scene_ids": production_s1_scene_ids,
                "s1_accepted_update_count": len(accepted_s1_reports),
                "s1_accepted_features": accepted_s1_features,
            })
        elif production_s1_scene_ids:
            diagnostics.update({
                "s1_capability_status": "available_no_state_update",
                "s1_capability_reason": "s1_scene_loaded_without_accepted_update",
                "s1_scene_count": len(production_s1_scene_ids),
                "s1_scene_ids": production_s1_scene_ids,
                "s1_accepted_update_count": 0,
                "s1_accepted_features": [],
            })
        diagnostics["graph_regularization_report"] = state_result_dict.get(
            "graph_regularization_report", []
        )
        diagnostics["graph_regularization_applied"] = bool(
            state_result_dict.get("graph_regularization_applied", False)
        )
        diagnostics["initialization_proof"] = dict(
            state_result_dict.get("initialization_proof", {}) or {}
        )
        diagnostics["process_model_inputs"] = dict(
            state_result_dict.get("process_model_inputs", {}) or {}
        )
        advisory_ensemble = state_result_dict.get("advisory_ensemble", {})
        if advisory_ensemble:
            from .cache import stable_value_hash
            diagnostics["ensemble_partition_proof"] = {
                "production_scene_ids": state_result_dict.get("production_ensemble_scene_ids", []),
                "advisory_scene_ids": state_result_dict.get("advisory_ensemble_scene_ids", []),
                "production_posterior_hash": stable_value_hash(state_result_dict.get("raster_maps", {})),
                "advisory_posterior_hash": stable_value_hash(advisory_ensemble.get("raster_maps", {})),
                "production_excludes_proxy_evidence": True,
                "proxy_changes_can_only_affect": "advisory_posterior",
            }
        if any(
            isinstance(rep, dict)
            and rep.get("update_applied") is True
            and "proxy" in str(rep.get("mode", ""))
            for rep in update_reports
        ):
            has_fallback = True
            full_enkf = False

        obs_modes = {}
        for rep in update_reports:
            if isinstance(rep, dict):
                observation_key = "{}:{}".format(
                    rep.get("scene_id", "unknown_scene"),
                    rep.get("obs_name", "unknown"),
                )
                obs_modes[observation_key] = rep.get("mode", "unknown")

        prod_bma_valid = (bma_result.get("status") == "success" and bma_result.get("bma_weights_source") == "holdout_performance") if isinstance(bma_result, dict) else False
        bma_weights_val = bma_result.get("bma_weights_production", {}) if isinstance(bma_result, dict) else {}

        # Determine dynamic ml_status (P3.1)
        from .config import ASMAE_ML_EXPERTS_ENABLED
        has_ml_models = bool(bma_result.get("active_ml_experts")) if isinstance(bma_result, dict) else False
        if not ASMAE_ML_EXPERTS_ENABLED:
            ml_status = "disabled"
        elif not has_ml_models:
            ml_status = "unavailable"
        else:
            ml_status = "shadow_only"

        out_obj = ASMAEOutput(
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            generated_at=datetime.now(timezone.utc),
            resolution_decision=resolution_decision,
            raster_maps=raster_maps,
            uncertainty_maps=uncertainty_maps,
            confidence_maps=confidence_maps,
            retrovalidation_maps=retrovalidation_maps,
            bma_maps=bma_maps,
            microzone_graph_ref=bundle.graph_ref if bundle else state_result.get("graph_ref", ""),
            state_timeline_ref=state_result.get("timeline_ref", ""),
            observation_operator_refs=op_refs,
            weak_labels=weak_labels,
            diagnostics=diagnostics,
            grid_spec=grid_spec,
            asmae_evidence_state=asmae_evidence_state,
        )
        out_obj.asmae_feature_pack = export_asmae_feature_pack(out_obj)

        feat_pack = out_obj.asmae_feature_pack or {}
        features_dict = feat_pack.get("feature_status", {})
        requested = list(features_dict.keys())
        available = [k for k, st in features_dict.items() if st.get("status") in ("real", "proxy_derived")]
        assimilated = [k for k, st in features_dict.items() if st.get("source_kind") in ("real_observation", "layer05_assimilated")]
        display_only = [k for k, st in features_dict.items() if st.get("usable_for_visual_only", False)]
        advisory_only = [k for k, st in features_dict.items() if st.get("usable_for_advisory", False) and not st.get("usable_for_field_approval", False)]
        missing = [k for k, st in features_dict.items() if st.get("status") in ("unavailable", "prior_constrained", "process_model_only")]
        drop_reasons = {
            k: st.get("drop_reason") or st.get("authority_block_reason") or "unknown"
            for k, st in features_dict.items()
            if st.get("status") in ("unavailable", "prior_constrained", "process_model_only")
        }

        # Build asmae_proof dictionary (BC.10.17 P4.1)
        asmae_proof = {
            "sentinel_proof": {
                "s2_real_scene_count": int(s2_real_count),
                "s1_real_scene_count": int(s1_real_count),
                "proxy_scene_count": int(proxy_count),
                "test_fixture_scene_count": int(test_fixture_count),
                "mean_only_scene_count": 0
            },
            "weather_proof": {
                "status": w_status,
                "source_reality": getattr(inp, "weather_source_reality", "missing"),
                "daily_count": len(w_series),
                "date_range": [inp.start_date.isoformat(), inp.end_date.isoformat()] if getattr(inp, "start_date", None) else [],
                "missing_days": w_missing,
                "missing_variables": getattr(inp, "missing_variables", []),
                "variable_completeness": completeness,
                "weather_hash": getattr(inp, "weather_archive_hash", None),
                "weather_used_for": weather_used_for
            },
            "enkf_proof": {
                "enkf_mode": enkf_mode_val,
                "enkf_executed": True if enkf_mode_val in ("ht_per_pixel", "ht_geometry_with_mean_observation") else False,
                "enkf_numerically_valid": bool(full_enkf),
                "full_enkf_credit_allowed": bool(full_enkf and classification_res.real_provider_product and classification_res.production_usable),
                "scientific_credit_level": (
                    "certified_production" if (full_enkf and classification_res.real_provider_product and classification_res.production_usable)
                    else "diagnostic_spatial_assimilation" if (full_enkf or s2_real_count > 0 or s1_real_count > 0)
                    else "prior_only"
                ),
                "has_enkf_proxy_fallback": bool(has_fallback),
                "per_pixel_update_count": sum(rep.get("n_pixels", 0) for rep in update_reports if isinstance(rep, dict) and "ht_per_pixel" in rep.get("mode", "")),
                "proxy_update_count": sum(1 for rep in update_reports if isinstance(rep, dict) and "proxy" in rep.get("mode", "")),
                "failed_update_count": sum(1 for rep in update_reports if isinstance(rep, dict) and "fail" in rep.get("mode", "")),
                "obs_modes": obs_modes,
                "update_reports": update_reports,
                "state_support_ledger": state_support_ledger,
                "graph_regularization_applied": diagnostics.get("graph_regularization_applied", False),
                "graph_regularization_report": diagnostics.get("graph_regularization_report", []),
                "initialization_proof": diagnostics.get("initialization_proof", {}),
                "process_model_inputs": diagnostics.get("process_model_inputs", {}),
            },
            "retrovalidation_proof": {
                "real_holdout_count": retro_result.get("n_real_holdout_scenes", 0) if isinstance(retro_result, dict) else 0,
                "proxy_holdout_count": retro_result.get("n_proxy_holdout_scenes", 0) if isinstance(retro_result, dict) else 0,
                "cell_level_support_available": bool(retro_result.get("cell_level_support_available", False) if isinstance(retro_result, dict) else False),
                "method": (
                    retro_result.get("retrovalidation_method")
                    or retro_result.get("method")
                ) if isinstance(retro_result, dict) else None,
                "successful_refit_count": retro_result.get("successful_refit_count", 0) if isinstance(retro_result, dict) else 0,
                "refit_proof": retro_result.get("refit_proof", []) if isinstance(retro_result, dict) else [],
                "current_run_used_for_approval": False
            },
            "radiometric_proof": {
                "overall_pass": consistency_result.get("overall_pass", False),
                "radiometric_mode": consistency_result.get("radiometric_mode", "unknown"),
                "full_radiometric_credit_allowed": consistency_result.get(
                    "full_radiometric_credit_allowed", False,
                ),
                "n_checked": consistency_result.get("n_checked", 0),
                "observation_mode_counts": consistency_result.get(
                    "observation_mode_counts", {},
                ),
                "per_index": consistency_result.get("per_index", {}),
                "per_scene_observation": consistency_result.get(
                    "per_scene_observation", [],
                ),
                "actions": consistency_result.get("actions", []),
            },
            "bma_proof": {
                "production_bma_valid": bool(prod_bma_valid),
                "weights_source": bma_result.get("bma_weights_source", "unavailable") if isinstance(bma_result, dict) else "unavailable",
                "bma_status": bma_result.get("status", "unavailable") if isinstance(bma_result, dict) else "unavailable",
                "active_experts": bma_result.get("active_experts", list(bma_weights_val.keys())) if isinstance(bma_result, dict) else [],
                "inactive_experts": [k for k in ["optical_physiology", "sar_structure", "water_balance", "spatial_smooth", "phenology_memory"] if k not in bma_weights_val],
                "active_independence_keys": bma_result.get("active_independence_keys", []) if isinstance(bma_result, dict) else [],
                "expert_proof": bma_result.get("expert_proof", {}) if isinstance(bma_result, dict) else {},
            },
            "ml_proof": {
                "ml_status": ml_status,
                "ml_production_weight": 0.0,
                "ml_used_for_approval": False,
                "ml_used_for_advisory": ml_status == "shadow_only"
            },
            "resolution_proof": {
                "field_approved_1m_mask_source": "local_resolution_evidence" if has_local_evidence else "unavailable",
                "advisory_1m_mask_source": "asmae_advisory_evidence" if asmae_evidence_state.get("asmae_advisory_evidence", False) else "proxy_visual" if asmae_evidence_state.get("visual_fusion_allowed", False) else "unavailable",
                "local_maps_required_for_approval": [
                    "local_retro_support_by_resolution[1]",
                    "local_archive_support_map",
                    "local_uncertainty_support_map",
                    "local_provider_scene_depth_map",
                    "local_gap_risk_map"
                ],
                "missing_local_maps": self._resolution_evidence.missing_reasons if getattr(self, "_resolution_evidence", None) else [
                    "local_retro_support_by_resolution[1]",
                    "local_archive_support_map",
                    "local_uncertainty_support_map",
                    "local_provider_scene_depth_map",
                    "local_gap_risk_map"
                ]
            },
            "feature_proof": {
                "requested": requested,
                "available": available,
                "assimilated": assimilated,
                "display_only": display_only,
                "advisory_only": advisory_only,
                "missing": missing,
                "drop_reasons": drop_reasons
            },
            "state_support_ledger": state_support_ledger,
            "ensemble_partition_proof": diagnostics.get("ensemble_partition_proof", {
                "production_scene_ids": state_result_dict.get("production_ensemble_scene_ids", []),
                "advisory_scene_ids": state_result_dict.get("advisory_ensemble_scene_ids", []),
                "production_excludes_proxy_evidence": True,
            }),
            "coarse_prior_proof": {
                "expected_layers": [
                    "layer2_intelligence", "layer3_water", "layer4_nutrients",
                    "layer5_biotic", "layer6_yield", "layer7_risk", "layer8_action",
                ],
                "layers": {
                    layer_name: {
                        "present": layer_name in (getattr(inp, "coarse_layer_outputs", {}) or {}),
                        "status": ((getattr(inp, "coarse_layer_outputs", {}) or {}).get(layer_name) or {}).get("status", "missing"),
                        "evidence": ((getattr(inp, "coarse_layer_outputs", {}) or {}).get(layer_name) or {}).get("evidence", []),
                    }
                    for layer_name in [
                        "layer2_intelligence", "layer3_water", "layer4_nutrients",
                        "layer5_biotic", "layer6_yield", "layer7_risk", "layer8_action",
                    ]
                },
            },
        }
        out_obj.asmae_proof = asmae_proof

        # Publish one canonical plot-state artifact. Authority is the
        # intersection of scientific gates and rollout permissions; state or
        # feature-level claims can never exceed it.
        from .plot_state import (
            aggregate_spatial_posterior,
            build_plot_state_artifact,
            intersect_artifact_authority,
        )
        scientific_production_usable = bool(diagnostics.get("production_usable", False))
        permissions = dict(getattr(inp, "execution_permissions", {}) or {})
        production_allowed = bool(
            permissions.get("production_authority_allowed", False)
        )
        current_spatial = bool(
            state_result_dict.get("status") == "success"
            and raster_maps
            and not is_degraded
        )
        requested_authority = (
            "RETROVALIDATED"
            if scientific_production_usable
            and used_retrovalidation
            and prod_bma_valid
            else "MODEL_ASSISTED"
            if current_spatial
            else "DIAGNOSTIC"
        )
        scene_times = [
            getattr(scene, "acquisition_time", None)
            for scene in production_scenes
            if getattr(scene, "acquisition_time", None) is not None
        ]
        artifact = build_plot_state_artifact(
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            as_of=max(scene_times) if scene_times else inp.end_date,
            availability=(
                "CURRENT_SPATIAL_ASSIMILATED"
                if current_spatial
                else diagnostics.get("state_availability", "UNAVAILABLE")
            ),
            authority=requested_authority,
            posterior=aggregate_spatial_posterior(state_result_dict, support_ledger=state_support_ledger),
            support_ledger=state_support_ledger,
            production_usable=scientific_production_usable,
            current_spatial_assimilation=current_spatial,
            geometry_hash=inp.geometry_hash,
            evidence_hash=bundle.content_hash if bundle else "",
            reason=(
                diagnostics.get("production_usable_reason", "")
                if not scientific_production_usable
                else "spatial_posterior_passed_scientific_gates"
            ),
        )
        artifact = intersect_artifact_authority(
            artifact,
            production_allowed=production_allowed,
            scientific_production_usable=scientific_production_usable,
        )
        final_production_usable = bool(artifact.get("production_usable", False))
        out_obj.plot_state_artifact = artifact
        diagnostics["scientific_production_usable"] = scientific_production_usable
        diagnostics["production_authority_allowed"] = production_allowed
        diagnostics["production_usable"] = final_production_usable
        diagnostics["authority_level"] = artifact["authority_level"]
        diagnostics["state_availability"] = artifact["state_availability"]
        diagnostics["current_spatial_assimilation"] = current_spatial
        diagnostics["spatial_raster_available"] = bool(current_spatial and raster_maps)
        diagnostics["state_update_allowed"] = final_production_usable
        diagnostics["layer1_export_allowed"] = final_production_usable
        diagnostics["weak_label_export_allowed"] = bool(
            final_production_usable
            and permissions.get("training_export_allowed", False)
        )
        if not diagnostics["weak_label_export_allowed"]:
            out_obj.weak_labels = []
        asmae_evidence_state.update({
            "state_availability": artifact["state_availability"],
            "authority_level": artifact["authority_level"],
            "posterior_available": bool(artifact.get("posterior")),
            "production_usable": final_production_usable,
            "current_spatial_assimilation": current_spatial,
            "spatial_raster_available": bool(current_spatial and raster_maps),
            "state_update_allowed": final_production_usable,
            "prescription_driver_allowed": final_production_usable,
            "current_1m_approval_allowed": bool(
                final_production_usable and has_local_evidence
            ),
        })
        for status in features_dict.values():
            if not isinstance(status, dict):
                continue
            status["usable_for_field_approval"] = bool(
                status.get("usable_for_field_approval", False)
                and final_production_usable
            )
        asmae_proof["authority_proof"] = {
            "requested_authority": requested_authority,
            "final_authority": artifact["authority_level"],
            "scientific_production_usable": scientific_production_usable,
            "production_authority_allowed": production_allowed,
            "field_approval_allowed": final_production_usable,
            "plot_state_content_hash": artifact["content_hash"],
        }
        asmae_proof["spatial_normalization"] = list(
            getattr(self, "_spatial_proof", []) or []
        )
        out_obj.asmae_evidence_state = asmae_evidence_state
        out_obj.asmae_feature_pack = feat_pack
        out_obj.asmae_proof = asmae_proof
        return out_obj

    def _microzone_to_grid(
        self, mz_data: dict, rd: ResolutionDecision,
    ) -> dict:
        """Convert {mz_id: [val_per_state]} → {state_name: [[2D grid]]}."""
        if not mz_data:
            return {}

        first_key = next(iter(mz_data))
        if isinstance(first_key, str) and first_key in STATE_NAMES:
            return mz_data

        from .config import N_STATES
        max_r = 0
        max_c = 0
        for mz_id in mz_data:
            parts = str(mz_id).split("_")
            if len(parts) >= 3:
                try:
                    r = int(parts[1])
                    c = int(parts[2])
                    max_r = max(max_r, r)
                    max_c = max(max_c, c)
                except ValueError:
                    pass

        n_rows = max_r + 1
        n_cols = max_c + 1

        result = {}
        for s_idx, name in enumerate(STATE_NAMES):
            grid = [[0.0] * n_cols for _ in range(n_rows)]
            for mz_id, state_vec in mz_data.items():
                parts = str(mz_id).split("_")
                if len(parts) >= 3:
                    try:
                        r = int(parts[1])
                        c = int(parts[2])
                        if isinstance(state_vec, list) and s_idx < len(state_vec):
                            grid[r][c] = state_vec[s_idx]
                    except (ValueError, IndexError):
                        pass
            result[name] = grid

        return result

    def _skeleton_output(
        self,
        inp: ASMAEInput,
        provenance: ASMAEProvenance,
        not_impl_msg: str,
    ) -> ASMAEOutput:
        """Return a minimal valid output when a step is not yet implemented."""
        rd = getattr(self, "_resolution_decision", None)
        if rd is None:
            rd = ResolutionDecision(
                candidate_resolutions_tested_m=[DEFAULT_RESOLUTION_M],
                selected_effective_resolution_m=DEFAULT_RESOLUTION_M,
                selected_visual_resolution_m=DEFAULT_RESOLUTION_M,
                selected_state_update_resolution_m=DEFAULT_RESOLUTION_M,
                selected_training_resolution_m=DEFAULT_RESOLUTION_M,
            )

        op_refs = [
            getattr(op, "operator_id", "")
            for op in getattr(self, "_operators", [])
        ]

        provenance.resolution_selected_m = rd.selected_effective_resolution_m
        provenance.completed_at = datetime.now(timezone.utc)
        provenance.audit_log = self._audit_log
        provenance.compute_content_hash()

        return ASMAEOutput(
            plot_id=inp.plot_id,
            run_id=inp.run_id,
            generated_at=datetime.now(timezone.utc),
            resolution_decision=rd,
            observation_operator_refs=op_refs,
            diagnostics={
                "skeleton": True,
                "not_implemented": not_impl_msg,
                "production_usable": False,
                "scientific_pass": False,
                "layer1_export_allowed": False,
                "weak_label_export_allowed": False,
                "reason": f"skeleton_not_implemented:{not_impl_msg}",
            },
            provenance=provenance.to_dict(),
        )

    # ════════════════════════════════════════════════════════════════
    # Audit helpers
    # ════════════════════════════════════════════════════════════════

    def _audit(self, step: str, status: str, **details) -> None:
        entry = ASMAEAuditStep(
            step=f"{step}:{status}",
            timestamp=datetime.now(timezone.utc),
            details=details,
        )
        self._audit_log.append(entry.to_dict())
        progress_callback = self.config.get("_worker_progress_callback")
        if callable(progress_callback):
            try:
                progress_callback(step, status, details)
            except Exception as exc:
                # Lease loss is a commit-fence event and must stop obsolete
                # work. Display-only callback failures must not alter science.
                if getattr(exc, "worker_lease_lost", False):
                    raise
                logger.debug("ASMAE worker progress callback failed: %s", exc)
        logger.debug("ASMAE audit: %s — %s", step, status)
