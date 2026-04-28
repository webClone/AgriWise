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
from orchestrator_v2.schema import RunArtifact, LayerStatus
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
    }

    # ---- Unified Plan ----
    plan = {"tasks": []}
    if artifact.final_execution_plan:
        try:
            plan = _serialize_plan(artifact.final_execution_plan)
        except Exception:
            plan = {"tasks": [], "error": "plan_serialization_failed"}

    # ---- Recommendations (from L6/L7) ----
    recommendations = _extract_recommendations(artifact)

    # ---- Explanations (from chat adapter or ARF) ----
    explanations = chat_payload or {}

    # ---- Provenance Summary ----
    provenance = _build_provenance(layer_summaries)

    # ---- Audit ----
    audit = {
        "orchestrator_run_id": artifact.meta.orchestrator_run_id,
        "artifact_hash": artifact.meta.artifact_hash,
        "timestamp_utc": artifact.meta.timestamp_utc,
        "orchestrator_version": artifact.meta.orchestrator_version,
        "layer_versions": artifact.meta.layer_versions,
        "lineage_map": artifact.lineage_map,
        "provenance": provenance,
    }

    # ---- Layer 9 Interface Output ----
    l9_output = {}
    if artifact.layer_9 and artifact.layer_9.output:
        l9_output = _serialize_layer9_output(artifact.layer_9.output)

    # ---- Fallback Guidance ----
    zone_states = layer10_detail.get("quality", {}).get("zone_state_by_surface", {}) if layer10_detail else {}
    has_plot_data = len(surfaces or []) > 0 or layer_summaries.get("layer_1", {}).get("status") == "OK"
    fallback_guidance = build_fallback_guidance_map(zone_states, has_plot_data)

    return {
        "run_id": artifact.meta.orchestrator_run_id,
        "plot_id": artifact.inputs.plot_id,
        "time_window": artifact.inputs.date_range,
        "intent": explanations.get("assistant_mode", "FULL"),
        "layer_results": layer_summaries,
        "global_quality": quality,
        "unified_plan": plan,
        "surfaces": surfaces or [],
        "layer10": layer10_detail or {},
        "fallback_guidance": fallback_guidance,
        "explanations": explanations,
        "recommendations": recommendations,
        "top_findings": artifact.top_findings,
        "interface": l9_output,
        "audit": audit,
    }


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


def _extract_recommendations(artifact: RunArtifact) -> List[Dict[str, Any]]:
    """
    Extract ranked recommendations from L3/L6/L7.
    Returns a list sorted by urgency.
    """
    recs = []

    # From L3 diagnoses
    if artifact.layer_3 and artifact.layer_3.status == LayerStatus.OK and artifact.layer_3.output:
        l3 = artifact.layer_3.output
        for diag in getattr(l3, "diagnoses", []):
            for act in getattr(diag, "recommended_actions", []):
                recs.append({
                    "action": getattr(act, "action", str(act)),
                    "source": "L3_DECISION",
                    "urgency": getattr(act, "urgency", "MEDIUM"),
                    "confidence": getattr(diag, "confidence", 0.5),
                    "rationale": getattr(diag, "explanation", ""),
                })

    # From L4 nutrient prescriptions
    if artifact.layer_4 and artifact.layer_4.status == LayerStatus.OK and artifact.layer_4.output:
        l4 = artifact.layer_4.output
        for rx in getattr(l4, "prescriptions", []):
            action_id = getattr(rx, "action_id", "")
            action_str = action_id.value if hasattr(action_id, "value") else str(action_id)
            risk = getattr(rx, "risk_if_wrong", "")
            risk_str = risk.value if hasattr(risk, "value") else str(risk)
            rate = getattr(rx, "rate_kg_ha", None)
            timing = getattr(rx, "timing_window", None)
            is_allowed = getattr(rx, "is_allowed", True)
            recs.append({
                "action": action_str,
                "source": "L4_NUTRIENTS",
                "urgency": "HIGH" if rate and rate > 50 else "MEDIUM",
                "confidence": 0.7 if is_allowed else 0.3,
                "rationale": f"{action_str} at {rate:.0f} kg/ha" if rate else action_str,
                "rate_kg_ha": rate,
                "timing": {"start": getattr(timing, "start_date", ""), "end": getattr(timing, "end_date", "")} if timing else None,
                "risk_if_wrong": risk_str,
                "is_allowed": is_allowed,
                "blocked_reason": getattr(rx, "blocked_reason", []),
            })

    # Sort by urgency: CRITICAL > HIGH > MEDIUM > LOW
    urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    recs.sort(key=lambda r: urgency_order.get(r.get("urgency", "LOW"), 4))

    return recs


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

