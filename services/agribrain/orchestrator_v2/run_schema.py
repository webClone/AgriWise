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
    }

    # ---- Layer 9 Interface Output ----
    l9_output = {}
    if artifact.layer_9 and artifact.layer_9.output:
        l9_output = _serialize_layer9_output(artifact.layer_9.output)

    # ---- Fallback Guidance ----
    zone_states = layer10_detail.get("quality", {}).get("zone_state_by_surface", {}) if layer10_detail else {}
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
    try:
        from layer0.perception.satellite_rgb.tile_runtime import get_cached_vision
        vision = get_cached_vision(artifact.inputs.plot_id)
        if vision and vision.get("confidence", 0) > 0.3:
            veg_keys = ["NDVI_CLEAN", "NDVI_DEVIATION", "BASELINE_ANOMALY"]
            for vkey in veg_keys:
                if zone_states.get(vkey) in ("no_data", "low_confidence", "unknown"):
                    zone_states[vkey] = "field_wide"
    except Exception:
        pass  # Vision cache is non-fatal enrichment

    # Compute surface means for cross-referencing (avoids banner/sidebar contradictions)
    surface_means = {}
    for surf in (surfaces or []):
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
        "surfaces": surfaces or [],
        "layer10": layer10_detail or {},
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
    if layer10_detail:
        res["timestamp"] = layer10_detail.get("timestamp") or audit.get("timestamp_utc", "")
        res["zones"] = layer10_detail.get("zones") or []
        res["histograms"] = layer10_detail.get("histograms") or {
            "field": [], "zone": [], "delta": [], "uncertainty": []
        }
        res["quicklooks"] = layer10_detail.get("quicklooks") or {}
        res["raster_pack"] = layer10_detail.get("raster_pack") or []
        res["vector_pack"] = layer10_detail.get("vector_pack") or []
        res["tile_manifest"] = layer10_detail.get("tile_manifest") or {}
        res["quality"] = layer10_detail.get("quality") or {}
        res["provenance"] = layer10_detail.get("provenance") or {}
        res["grid"] = layer10_detail.get("grid") or {"height": 0, "width": 0}
        res["explainability_pack"] = layer10_detail.get("explainability_pack") or {}
        res["scenario_pack"] = layer10_detail.get("scenario_pack") or []
        res["history_pack"] = layer10_detail.get("history_pack") or []
        # V92.4: Thread mode_surface_plan and surface_inventory to frontend
        res["mode_surface_plan"] = layer10_detail.get("mode_surface_plan") or {}
        res["surface_inventory"] = layer10_detail.get("surface_inventory") or {}
        # V92.4-BC: Thread mode_display_state
        res["mode_display_state"] = layer10_detail.get("mode_display_state") or {}

    return res


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
