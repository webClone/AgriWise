"""
AgriBrainRun — Canonical JSON Contract
=======================================
Converts the internal RunArtifact into the single JSON object
that ALL farmer-facing routes consume.

This is the ONLY shape the frontend should ever see.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from services.agribrain.orchestrator_v2.schema import RunArtifact, LayerStatus
from services.agribrain.scientific_contracts.prescription_authorization import (
    AuthorizedActionV1,
    PrescriptionAuthorizationEnvelopeV1,
    PrescriptionAuthorizationEnvelopeV2,
    PRESCRIPTION_AUTHORIZATION_ENVELOPE_V2,
    canonical_hash,
    selected_entries_exist,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from layer9_interface.fallback_actions import build_fallback_guidance_map


def artifact_to_run(artifact: RunArtifact,
                    surfaces: Optional[List[Dict]] = None,
                    chat_payload: Optional[Dict] = None,
                    layer10_detail: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Convert a RunArtifact (+ optional L10 surfaces and chat payload)
    into the canonical AgriBrainRun JSON.

    This is the SINGLE serialization point for all API responses.
    """
    # Auto-serialize Layer 10 if not explicitly provided but available in the artifact
    if not layer10_detail and artifact.layer_10 and artifact.layer_10.output:
        try:
            from services.agribrain.orchestrator_v2.run_entrypoint import _serialize_l10_output
            layer10_detail = _serialize_l10_output(artifact.layer_10.output)
            if not surfaces:
                surfaces = layer10_detail.get("surfaces", [])
        except Exception as e:
            import sys
            print(f"[Schema] Auto L10 serialization failed: {e}", file=sys.stderr)

    # ---- Layer Summaries (with per-layer confidence) ----
    layer_summaries = {}
    for lid in ["layer_1", "layer_2", "layer_3", "layer_4",
                "layer_5", "layer_6", "layer_7", "layer_8",
                "layer_9", "layer_10"]:
        lr = getattr(artifact, lid, None)
        if lr is None:
            layer_summaries[lid] = {"status": "SKIPPED", "errors": [], "confidence": 0.0}
            continue

        # Extract per-layer confidence from quality_metrics if available
        confidence = 1.0
        quality_scored = False
        sources = []
        if lr.output:
            qm = getattr(lr.output, "quality_metrics", None)
            if qm:
                confidence = getattr(qm, "decision_reliability", 1.0)
                quality_scored = True
            # Extract data sources
            sources = _get_layer_sources(lid, lr.output)

            # V91.2: L1 confidence from data_health object, not hardcoded 1.0
            if lid == "layer_1":
                dh = getattr(lr.output, "data_health", None)
                if dh:
                    confidence = getattr(dh, "overall", 0.0) or 0.0
                else:
                    prov = getattr(lr.output, "provenance", {}) or {}
                    if isinstance(prov, dict):
                        confidence = float(
                            prov.get("data_health_overall",
                                     prov.get("confidence_ceiling", 0.0)) or 0.0
                        )

        if lr.status.value == "FAILED":
            confidence = 0.0
        elif lr.status.value == "DEGRADED":
            confidence = min(confidence, 0.7)

        layer_summaries[lid] = {
            "status": lr.status.value if hasattr(lr.status, "value") else str(lr.status),
            "run_id": lr.run_id,
            "errors": lr.errors,
            "degradation_flags": lr.degradation_flags,
            "confidence": round(confidence, 3),
            "quality_scored": quality_scored,
            "sources": sources,
        }

    # ---- Global Quality ----
    gq = artifact.global_quality
    quality = {
        "reliability": gq.reliability_score,
        "degradation_modes": [m.value if hasattr(m, "value") else str(m) for m in gq.modes],
        "missing_drivers": gq.missing_drivers,
        "critical_errors": gq.critical_errors,
        "critical_failure": gq.critical_failure,
        "alerts": gq.critical_errors[:3],  # top 3 for UI badge
        # V91.2: Surface L1 health for UI
        "data_health_status": _extract_l1_health_status(artifact),
        "confidence_ceiling": _extract_l1_confidence_ceiling(artifact),
    }

    # ---- Authorized L8 boundary ----
    # Validate once, then use the same exact envelope for both recommendations
    # and execution-plan visibility.  L3--L5 action-shaped fields are shadow
    # evidence and must never be reconstructed here.
    authorization, authorization_error = _validated_authorization(artifact)
    safe_layer10_detail = (
        layer10_detail or {}
        if authorization is not None
        else _redact_unauthorized_action_content(layer10_detail or {})
    )
    safe_surfaces = (
        surfaces or []
        if authorization is not None
        else _redact_unauthorized_action_content(surfaces or [])
    )

    # ---- Unified Plan ----
    plan = {"tasks": []}
    if authorization is not None and artifact.final_execution_plan:
        try:
            plan = _serialize_plan(artifact.final_execution_plan)
        except Exception:
            plan = {"tasks": [], "error": "plan_serialization_failed"}

    # ---- Recommendations (only from the verified L8 authorization envelope) ----
    recommendations = _extract_recommendations(artifact, authorization)

    # ---- Explanations (from chat adapter or ARF) ----
    explanations = chat_payload or {}
    if authorization is None:
        explanations = _diagnostic_only_explanations(explanations)

    # ---- Provenance Summary ----
    provenance = _build_provenance(layer_summaries)
    if hasattr(artifact, "inputs") and hasattr(artifact.inputs, "date_range"):
        provenance["resolved_date_range"] = artifact.inputs.date_range

    # ---- Audit ----
    _pa = artifact.meta.primary_acquisition
    _fb = artifact.meta.fallback_used
    _fb_reason = artifact.meta.fallback_reason

    # Derive fusion_engine and pipeline_mode from RunMeta
    _fusion_engine = "layer1_v1" if _pa == "layer0" and not _fb else "legacy_data_fusion"
    _pipeline_mode = (
        "layer0_layer1_v1_primary" if _pa == "layer0" and not _fb
        else "legacy_fallback"
    )

    audit = {
        "orchestrator_run_id": artifact.meta.orchestrator_run_id,
        "artifact_hash": artifact.meta.artifact_hash,
        "timestamp_utc": artifact.meta.timestamp_utc,
        "orchestrator_version": artifact.meta.orchestrator_version,
        "layer_versions": artifact.meta.layer_versions,
        "lineage_map": artifact.lineage_map,
        "provenance": provenance,
        # V63A: Pipeline provenance — proves which acquisition path was used
        "primary_acquisition": _pa,
        "fusion_engine": _fusion_engine,
        "pipeline_mode": _pipeline_mode,
        "fallback_used": _fb,
        "fallback_reason": _fb_reason,
        "prescription_authorization": {
            "status": "AUTHORIZED" if authorization is not None else "BLOCKED",
            "envelope_hash": authorization.content_hash if authorization else None,
            "reason": authorization_error,
        },
    }

    # ---- Layer 9 Interface Output ----
    l9_output = {}
    if authorization is not None and artifact.layer_9 and artifact.layer_9.output:
        l9_output = _serialize_layer9_output(artifact.layer_9.output)
    elif artifact.layer_9 and artifact.layer_9.output:
        l9_output = {
            "prescription_status": "BLOCKED",
            "reason": authorization_error,
        }

    # ---- Fallback Guidance ----
    zone_states = safe_layer10_detail.get("quality", {}).get("zone_state_by_surface", {})
    # Fix B: has_plot_data should be True whenever ANY layer above L0 produced usable output.
    # Previously: only checked surfaces list length OR layer_1.status=="OK".
    # Bug: DEGRADED layers still produce plot-level fallback metrics (weather, L2 stats, soil),
    #      so "insufficient_data" banner fires incorrectly when L1 is DEGRADED but L2 is OK.
    # V91.2: has_plot_data must also check that L1 has real evidence, not just status
    has_l1_evidence = True
    if artifact.layer_1 and artifact.layer_1.output:
        _prov = getattr(artifact.layer_1.output, "provenance", {}) or {}
        if isinstance(_prov, dict):
            _ec = _prov.get("evidence_count", _prov.get("v1_evidence_count"))
            if _ec is not None and _ec == 0:
                has_l1_evidence = False

    has_plot_data = has_l1_evidence and bool(
        (surfaces and len(surfaces) > 0)  # spatial surfaces were produced
        or any(
            layer_summaries.get(lid, {}).get("status") in ("OK", "DEGRADED")
            for lid in ["layer_1", "layer_2", "layer_3", "layer_4", "layer_5"]
        )
    )


    # ── Satellite Vision Evidence Upgrade ──
    # If the LLM satellite vision pipeline has analyzed this plot's tile,
    # upgrade vegetation zone states from "no_data"/"low_confidence" to
    # "field_wide" — we have real satellite ground-truth even if raster zones
    # didn't form due to confidence thresholds.
    # Cached LLM interpretation is narrative-only.  It cannot create raster
    # support or promote no_data/low_confidence states to field_wide.

    # Compute surface means for cross-referencing (avoids banner/sidebar contradictions)
    surface_means = {}
    for surf in safe_surfaces:
        stype = surf.get("type", "")
        vals_flat = []
        for row in surf.get("values", []):
            if isinstance(row, list):
                for v in row:
                    if v is not None and isinstance(v, (int, float)):
                        vals_flat.append(v)
        if vals_flat:
            surface_means[stype] = sum(vals_flat) / len(vals_flat)

    fallback_guidance = build_fallback_guidance_map(zone_states, has_plot_data,
                                                     surface_means=surface_means)

    res = {
        "run_id": artifact.meta.orchestrator_run_id,
        "plot_id": artifact.inputs.plot_id,
        "time_window": artifact.inputs.date_range,
        "intent": explanations.get("assistant_mode", "FULL"),
        "layer_results": layer_summaries,
        "global_quality": quality,
        "unified_plan": plan,
        "surfaces": safe_surfaces,
        "layer10": safe_layer10_detail,
        "fallback_guidance": fallback_guidance,
        "explanations": explanations,
        "recommendations": recommendations,
        "top_findings": artifact.top_findings,
        "interface": l9_output,
        "diagnostic_integration": artifact.diagnostic_integration or {
            "status": "unavailable",
        },
        "audit": audit,
    }

    # Enrich canonical run with Layer 10 fields if available
    if safe_layer10_detail:
        res["timestamp"] = safe_layer10_detail.get("timestamp") or audit.get("timestamp_utc", "")
        res["zones"] = safe_layer10_detail.get("zones") or []
        res["histograms"] = safe_layer10_detail.get("histograms") or {
            "field": [], "zone": [], "delta": [], "uncertainty": []
        }
        res["quicklooks"] = safe_layer10_detail.get("quicklooks") or {}
        res["raster_pack"] = safe_layer10_detail.get("raster_pack") or []
        res["vector_pack"] = safe_layer10_detail.get("vector_pack") or []
        res["tile_manifest"] = safe_layer10_detail.get("tile_manifest") or {}
        res["quality"] = safe_layer10_detail.get("quality") or {}
        res["provenance"] = safe_layer10_detail.get("provenance") or {}
        res["grid"] = safe_layer10_detail.get("grid") or {"height": 0, "width": 0}
        res["explainability_pack"] = safe_layer10_detail.get("explainability_pack") or {}
        res["scenario_pack"] = (
            safe_layer10_detail.get("scenario_pack") or []
            if authorization is not None else []
        )
        res["history_pack"] = (
            safe_layer10_detail.get("history_pack") or []
            if authorization is not None else []
        )
        # V92.4: Thread mode_surface_plan and surface_inventory to frontend
        res["mode_surface_plan"] = safe_layer10_detail.get("mode_surface_plan") or {}
        res["surface_inventory"] = safe_layer10_detail.get("surface_inventory") or {}
        # V92.4-BC: Thread mode_display_state
        res["mode_display_state"] = safe_layer10_detail.get("mode_display_state") or {}

    cycle_id = None
    if getattr(artifact, "inputs", None) and getattr(artifact.inputs, "crop_cycle_context", None):
        cycle_id = getattr(artifact.inputs.crop_cycle_context, "crop_cycle_id", None)
    if not cycle_id and getattr(artifact, "inputs", None) and hasattr(artifact.inputs, "crop_cycle_id"):
        cycle_id = getattr(artifact.inputs, "crop_cycle_id", None)
    if cycle_id:
        cycle_id_str = str(cycle_id).strip()
        res["crop_cycle_id"] = cycle_id_str
        res["cropCycleId"] = cycle_id_str

    return res


def _diagnostic_only_explanations(value: Any) -> Dict[str, Any]:
    """Keep non-prescriptive chat context when no action envelope exists."""

    if not isinstance(value, dict):
        return {}
    allowed = {
        "assistant_mode", "assistant_style", "global_quality", "summary",
        "diagnoses", "citations", "questions_for_user", "memory", "ui_hints",
        "visuals", "data_inventory",
    }
    result = {key: value[key] for key in allowed if key in value}
    result["actions"] = []
    result["plan"] = {"tasks": []}
    result["prescription_status"] = "BLOCKED"
    return result


_ACTION_KEY_TOKENS = (
    "action", "prescription", "recommendation", "schedule", "zone_plan",
    "execution_plan", "task", "dosage", "dose", "rate_kg", "timing_window",
)


def _redact_unauthorized_action_content(value: Any) -> Any:
    """Remove action-shaped L10 fields while retaining diagnostic surfaces."""

    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            token = str(key).lower()
            if any(blocked in token for blocked in _ACTION_KEY_TOKENS):
                continue
            result[key] = _redact_unauthorized_action_content(item)
        return result
    if isinstance(value, list):
        return [_redact_unauthorized_action_content(item) for item in value]
    return value


def _serialize_plan(plan) -> Dict[str, Any]:
    """Serialize ExecutionPlan to JSON-safe dict.
    TaskNode fields: task_id, type, instructions, required_inputs,
    completion_signal, depends_on.
    """
    tasks = []
    for t in getattr(plan, "tasks", []):
        tasks.append({
            "id": getattr(t, "task_id", ""),
            "type": getattr(t, "type", ""),
            "instructions": getattr(t, "instructions", ""),
            "required_inputs": getattr(t, "required_inputs", []),
            "completion_signal": getattr(t, "completion_signal", ""),
            "depends_on": getattr(t, "depends_on", []),
            "target_zones": getattr(t, "target_zones", []),
            "target_points": getattr(t, "target_points", []),
        })
    
    # Serialize edges (list/tuple or dict format)
    edges = []
    for e in getattr(plan, "edges", []):
        if isinstance(e, dict):
            edges.append(e)
        elif isinstance(e, (list, tuple)):
            edges.append({"from": e[0], "to": e[1]} if len(e) >= 2 else e)
        else:
            edges.append(e)
    
    return {
        "tasks": tasks,
        "edges": edges,
        "total_tasks": len(tasks),
        "recommended_start_date": getattr(plan, "recommended_start_date", ""),
        "review_date": getattr(plan, "review_date", ""),
    }


def _extract_recommendations(
    artifact: RunArtifact,
    authorization: Optional[PrescriptionAuthorizationEnvelopeV1] = None,
) -> List[Dict[str, Any]]:
    """
    Serialize exact actions from a previously verified L8 authorization.

    This function intentionally never reads L3, L4, L5, L6, or L7 action
    fields.  Those layers can contribute scientific evidence, but L8 alone
    selects an action and the authorization envelope alone permits publication.
    """
    if authorization is None:
        return []

    recs = [{
        "action_id": action.action_id,
        "action": action.action_type,
        "source": "L8_AUTHORIZED_ACTION",
        "priority": action.priority_score,
        "urgency": action.urgency_score,
        "confidence": action.confidence,
        "rationale": action.rationale,
        "rate": dict(action.rate),
        "timing": dict(action.timing),
        "zone_targets": list(action.zone_targets),
        "requires_confirmation": action.requires_confirmation,
        "machine_execution_allowed": action.machine_execution_allowed,
        "authorization_envelope_hash": authorization.content_hash,
        "prescription_manifest_hash": authorization.prescription_manifest_hash,
    } for action in authorization.actions]

    # Sort by urgency: CRITICAL > HIGH > MEDIUM > LOW
    urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    recs.sort(key=lambda r: urgency_order.get(r.get("urgency", "LOW"), 4))

    return recs


def _validated_authorization(
    artifact: RunArtifact,
) -> tuple[Optional[PrescriptionAuthorizationEnvelopeV1], Optional[str]]:
    """Verify all lineage bindings required by the public action boundary."""

    try:
        if not artifact.layer_8 or artifact.layer_8.status != LayerStatus.OK:
            raise ContractViolation("L8 output is unavailable or degraded")
        l8_output = artifact.layer_8.output
        if l8_output is None:
            raise ContractViolation("L8 output is unavailable")
        raw = getattr(l8_output, "authorization_envelope", None)
        if raw is None:
            raise ContractViolation("L8 authorization envelope is missing")
        # V2 is NOT a subtype of legacy export authority. It is a candidate
        # contract until the authenticated current-publication binding,
        # validated uncertainty and receipt promotion are wired end-to-end.
        if (isinstance(raw, PrescriptionAuthorizationEnvelopeV2)
                or getattr(raw, "schema_version", None) == PRESCRIPTION_AUTHORIZATION_ENVELOPE_V2
                or (isinstance(raw, dict) and
                    raw.get("schema_version") == PRESCRIPTION_AUTHORIZATION_ENVELOPE_V2)):
            raise ContractViolation("V2 publication binding gate is not yet wired for action export")
        envelope = (
            raw
            if isinstance(raw, PrescriptionAuthorizationEnvelopeV1)
            else PrescriptionAuthorizationEnvelopeV1.from_mapping(raw)
        )

        gate = (artifact.diagnostic_integration or {}).get("prescription_gate") or {}
        manifest = gate.get("influence_manifest") or {}
        tribunal = gate.get("tribunal_verdict") or {}
        if gate.get("status") != "completed":
            raise ContractViolation("Prescription gate did not complete cleanly")
        if manifest.get("requested_use") != "PRESCRIPTION_DRIVER":
            raise ContractViolation("Prescription manifest has the wrong requested use")
        if envelope.input_belief_id != str(gate.get("input_belief_id") or ""):
            raise ContractViolation("Authorization belief identity mismatch")
        if envelope.tribunal_content_hash != str(tribunal.get("content_hash") or ""):
            raise ContractViolation("Authorization tribunal hash mismatch")
        if envelope.prescription_manifest_hash != str(manifest.get("content_hash") or ""):
            raise ContractViolation("Authorization manifest hash mismatch")
        if not selected_entries_exist(envelope, manifest.get("entries") or []):
            raise ContractViolation("Authorization references unavailable manifest entries")
        if envelope.policy_snapshot_hash != canonical_hash(artifact.inputs.policy_snapshot):
            raise ContractViolation("Authorization policy snapshot hash mismatch")
        if envelope.l8_run_id != str(getattr(l8_output, "run_id", "") or ""):
            raise ContractViolation("Authorization L8 run identity mismatch")
        l8_actions = {
            str(getattr(action, "action_id", "") or ""): action
            for action in (getattr(l8_output, "actions", None) or [])
        }
        for approved in envelope.actions:
            source = l8_actions.get(approved.action_id)
            if source is None:
                raise ContractViolation("Authorization action is absent from L8 output")
            expected = AuthorizedActionV1.from_l8_action(source)
            if approved.to_dict() != expected.to_dict():
                raise ContractViolation("Authorization action differs from exact L8 selection")

        l8_content_hash = ""
        audit = getattr(l8_output, "audit", None)
        for check in getattr(audit, "policy_checks", []) if audit else []:
            if isinstance(check, dict) and check.get("check") == "content_hash":
                l8_content_hash = str(check.get("value") or "")
        if envelope.l8_content_hash != l8_content_hash:
            raise ContractViolation("Authorization L8 content hash mismatch")
        if artifact.final_execution_plan is None:
            raise ContractViolation("Final execution plan is missing")
        plan_hash = canonical_hash(_serialize_plan(artifact.final_execution_plan))
        if envelope.final_execution_plan_hash != plan_hash:
            raise ContractViolation("Authorization final-plan hash mismatch")
        return envelope, None
    except (ContractViolation, TypeError, ValueError) as exc:
        return None, str(exc)


def _get_layer_sources(lid: str, output) -> List[str]:
    """
    Identify what data sources a layer used.
    Grounded in output attributes — no guessing.
    """
    sources = []

    if lid == "layer_1":
        ts = getattr(output, "plot_timeseries", None)
        if ts and len(ts) > 0:
            sources.append("Open-Meteo (ERA5-Land)")
        static = getattr(output, "static", {})
        if isinstance(static, dict):
            if static.get("clay") or static.get("sand") or static.get("ph"):
                sources.append("SoilGrids (ISRIC)")
            if static.get("soil_moisture"):
                sources.append("Open-Meteo (Soil Moisture)")
        if getattr(output, "ndvi", None) or getattr(output, "optical_data", None):
            sources.append("Sentinel-2 (Copernicus)")
        if getattr(output, "sar_data", None):
            sources.append("Sentinel-1 (SAR)")
    elif lid == "layer_2":
        sources.append("Vegetation indices (computed from L1)")
    elif lid == "layer_3":
        sources.append("Decision engine (L1+L2 fusion)")
    elif lid == "layer_4":
        sources.append("Nutrient model (L1+L2+L3)")
    elif lid == "layer_5":
        sources.append("Bio-threat model (L1+L2+L3+L4)")
    elif lid == "layer_6":
        sources.append("Execution state (plan tracking)")
    elif lid == "layer_10":
        sources.append("Spatial renderer (SIRE)")

    return sources


def _build_provenance(layer_summaries: Dict) -> Dict[str, Any]:
    """
    Build a provenance summary for the entire run.
    Shows what data sources were used, what's verified, what's missing.
    """
    all_sources = set()
    quality_scored_layers = []
    degraded_layers = []
    failed_layers = []

    for lid, summary in layer_summaries.items():
        status = summary.get("status", "SKIPPED")
        for src in summary.get("sources", []):
            all_sources.add(src)
        if summary.get("quality_scored"):
            quality_scored_layers.append(lid)
        if status == "DEGRADED":
            degraded_layers.append(lid)
        elif status == "FAILED":
            failed_layers.append(lid)

    return {
        "data_sources": sorted(all_sources),
        "quality_scored_layers": quality_scored_layers,
        "degraded_layers": degraded_layers,
        "failed_layers": failed_layers,
        "total_sources": len(all_sources),
    }


def _serialize_layer9_output(l9_output) -> Dict[str, Any]:
    """
    Serialize Layer 9 InterfaceOutput into JSON-safe dict for canonical API.
    
    This surfaces zone_cards, alerts, disclaimers, render_hints, explanations,
    and phrasing_mode to the frontend — the missing delivery path.
    """
    if not l9_output:
        return {}
    
    # Zone cards
    zone_cards = []
    for zc in getattr(l9_output, "zone_cards", []):
        badge = getattr(zc, "confidence_badge", None)
        zone_cards.append({
            "zone_id": getattr(zc, "zone_id", ""),
            "top_action": getattr(zc, "top_action", None),
            "confidence_badge": badge.value if hasattr(badge, "value") else str(badge or ""),
            "key_metrics": getattr(zc, "key_metrics", {}),
            "status_text": getattr(zc, "status_text", ""),
        })
    
    # Alerts
    alerts = []
    for a in getattr(l9_output, "alerts", []):
        a_type = getattr(a, "alert_type", None)
        a_sev = getattr(a, "severity", None)
        alerts.append({
            "type": a_type.value if hasattr(a_type, "value") else str(a_type or ""),
            "severity": a_sev.value if hasattr(a_sev, "value") else str(a_sev or ""),
            "message": getattr(a, "message", ""),
            "evidence_id": getattr(a, "trigger_evidence_id", ""),
            "action_required": getattr(a, "action_required", False),
        })
    
    # Disclaimers
    disclaimers = []
    for d in getattr(l9_output, "disclaimers", []):
        d_sev = getattr(d, "severity", None)
        disclaimers.append({
            "text": getattr(d, "text", ""),
            "reason": getattr(d, "reason", ""),
            "severity": d_sev.value if hasattr(d_sev, "value") else str(d_sev or ""),
        })
    
    # Explanations
    explanations = []
    for e in getattr(l9_output, "explanations", []):
        explanations.append({
            "statement": getattr(e, "statement", ""),
            "evidence_id": getattr(e, "evidence_id", ""),
            "source_layer": getattr(e, "source_layer", ""),
            "confidence": getattr(e, "confidence", 0.0),
        })
    
    # Render hints
    rh = getattr(l9_output, "render_hints", None)
    render_hints = {}
    if rh:
        badge = getattr(rh, "badge_color", None)
        render_hints = {
            "badge_color": badge.value if hasattr(badge, "value") else str(badge or ""),
            "show_uncertainty_overlay": getattr(rh, "show_uncertainty_overlay", False),
            "show_conflict_icon": getattr(rh, "show_conflict_icon", False),
            "highlight_zones": getattr(rh, "highlight_zones", []),
        }
    
    # Phrasing mode
    pm = getattr(l9_output, "phrasing_mode", None)
    
    return {
        "summary": getattr(l9_output, "summary", ""),
        "zone_cards": zone_cards,
        "alerts": alerts,
        "disclaimers": disclaimers,
        "explanations": explanations,
        "render_hints": render_hints,
        "phrasing_mode": pm.value if hasattr(pm, "value") else str(pm or ""),
        "follow_up_questions": getattr(l9_output, "follow_up_questions", []),
    }


# ============================================================================
# V91.2: L1 health extraction helpers
# Read from BOTH data_health object (primary) AND provenance dict (fallback)
# ============================================================================

def _extract_l1_health_status(artifact: RunArtifact) -> str:
    """Extract L1 data health status from data_health object or provenance."""
    if artifact.layer_1 and artifact.layer_1.output:
        out = artifact.layer_1.output
        dh = getattr(out, "data_health", None)
        if dh and getattr(dh, "status", None):
            return dh.status

        prov = getattr(out, "provenance", {}) or {}
        if isinstance(prov, dict):
            return prov.get("data_health_status") or prov.get("v1_data_health") or "unusable"
        else:
            return getattr(prov, "data_health_status", None) or "unusable"

    return "unusable"


def _extract_l1_confidence_ceiling(artifact: RunArtifact) -> float:
    """Extract L1 confidence ceiling from data_health object or provenance."""
    if artifact.layer_1 and artifact.layer_1.output:
        out = artifact.layer_1.output
        dh = getattr(out, "data_health", None)
        if dh and getattr(dh, "confidence_ceiling", None) is not None:
            return float(dh.confidence_ceiling)

        prov = getattr(out, "provenance", {}) or {}
        if isinstance(prov, dict):
            return float(
                prov.get("confidence_ceiling",
                         prov.get("data_health_overall", 0.0)) or 0.0
            )
        else:
            val = getattr(prov, "confidence_ceiling", None)
            return float(val) if val is not None else 0.0

    return 0.0
