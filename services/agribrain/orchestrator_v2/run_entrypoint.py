"""
Unified AgriBrain Run Entrypoint
=================================
Single Python entry point for ALL farmer-facing API routes.

Modes:
  chat     — Detect intent, run pipeline, return ChatPayload (backward compat)
  full     — Run full pipeline, return AgriBrainRun JSON
  surfaces — Run pipeline + Layer 10, return AgriBrainRun with surfaces

Usage:
  py run_entrypoint.py --context <base64_json> [--query <text>] [--mode full|chat|surfaces]
"""
import sys
import os
import json
import argparse
import io
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv
load_dotenv(override=True)


def _parse_context(raw: str) -> dict:
    """Decode base64 or raw JSON context."""
    import base64
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return json.loads(raw)


def _build_inputs(ctx: dict, query: str = ""):
    """Build OrchestratorInput from frontend context dict."""
    from orchestrator_v2.schema import OrchestratorInput

    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)

    import hashlib
    import json
    poly = ctx.get("polygon")
    geom_hash = ctx.get("geometry_hash")
    if not geom_hash:
        if poly:
            geom_raw = json.dumps(poly, sort_keys=True).encode("utf-8")
            geom_hash = hashlib.sha256(geom_raw).hexdigest()[:8]
        else:
            geom_hash = "UNKNOWN_GEO"

    import uuid
    from datetime import timezone
    
    user_evidence = []
    
    # 1. Photos -> User Observations
    for photo in ctx.get("photos", []):
        try:
            ts = photo.get("date") or datetime.now(timezone.utc).isoformat()
            user_evidence.append({
                "id": str(photo.get("id", uuid.uuid4())),
                "source_type": "user_observation",
                "timestamp": ts,
                "location_scope": "point",
                "payload": {"type": "photo", "url": photo.get("url")}
            })
        except: pass

    # 2. Soil Analyses -> Soil Evidence
    for soil in ctx.get("soilAnalyses", []):
        try:
            ts = soil.get("date") or datetime.now(timezone.utc).isoformat()
            user_evidence.append({
                "id": str(soil.get("id", uuid.uuid4())),
                "source_type": "soil",
                "timestamp": ts,
                "location_scope": "plot",
                "payload": soil
            })
        except: pass

    # 3. Sensors -> Sensor Evidence
    sensors_raw = ctx.get("sensors", [])
    # Handle legacy flat dict format: wrap in list
    if isinstance(sensors_raw, dict):
        sensors_raw = [sensors_raw]
    # Only iterate if it's a list of sensor objects
    if isinstance(sensors_raw, list):
        for sensor in sensors_raw:
            if not isinstance(sensor, dict):
                continue
            try:
                ts = sensor.get("lastSync") or datetime.now(timezone.utc).isoformat()
                user_evidence.append({
                    "id": str(sensor.get("id", uuid.uuid4())),
                    "source_type": "sensor",
                    "timestamp": ts,
                    "location_scope": "point",
                    "payload": sensor
                })
            except: pass

    # Merge sensor_summary (flat dict) for backward compat in operational_context
    sensor_summary = ctx.get("sensor_summary", {})
    if isinstance(sensors_raw, list) and sensors_raw and not sensor_summary:
        # Build summary from the array if route didn't provide one
        for s in sensors_raw:
            if isinstance(s, dict):
                if s.get("soilMoisture") is not None:
                    sensor_summary["soil_moisture"] = s["soilMoisture"]
                if s.get("temperature") is not None:
                    sensor_summary["temperature"] = s["temperature"]
                if s.get("humidity") is not None:
                    sensor_summary["humidity"] = s["humidity"]

    return OrchestratorInput(
        plot_id=ctx.get("plot_id", "UNKNOWN"),
        geometry_hash=geom_hash,
        date_range={
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
        },
        crop_config={
            "crop": ctx.get("crop", "unknown"),
            "stage": ctx.get("stage", "unknown"),
        },
        operational_context={
            "lat": ctx.get("lat", 0.0),
            "lng": ctx.get("lng", 0.0),
            "sensors": sensors_raw,
            "sensor_summary": sensor_summary,
            "soil_type": ctx.get("soil_type"),
            "irrigation_type": ctx.get("irrigation_type"),
            "polygon_coords": poly,  # Pass through the real polygon
            "user_evidence": user_evidence, # Pass structured evidence!
        },
        policy_snapshot={},
    )


def run_chat_mode(ctx: dict, query: str, args) -> dict:
    """
    Chat mode — runs pipeline and returns canonical AgriBrainRun.
    The ChatPayload is embedded inside explanations, not returned raw.
    Greeting/general early exits also use the canonical envelope.
    """
    from orchestrator_v2.intents import detect_intent, Intent

    plot_id = ctx.get("plot_id", "UNKNOWN")
    intent = detect_intent(query, has_context=(plot_id != "UNKNOWN"))

    # Greeting early exit — canonical envelope
    if intent == Intent.GREETING:
        return _canonical_early_exit("GREETING_ONLY", "WELCOME", _greeting_arf(args.exp), args.exp)

    # General knowledge early exit — canonical envelope
    if intent == Intent.GENERAL:
        return _canonical_early_exit("GENERAL_KNOWLEDGE", "GENERAL", _general_arf(query, args.exp), args.exp)

    # Full pipeline → canonical AgriBrainRun
    from orchestrator_v2.runner import run_orchestrator, run_for_chat
    from orchestrator_v2.run_schema import artifact_to_run

    inputs = _build_inputs(ctx, query)

    history = []
    if getattr(args, "history", None):
        try:
            import base64
            # Next.js API route encodes JSON as base64 or passes real JSON string
            try:
                decoded_hist = base64.b64decode(args.history).decode("utf-8")
            except Exception:
                decoded_hist = args.history
            history = json.loads(decoded_hist)
        except Exception:
            pass

    f = io.StringIO()
    with redirect_stdout(f):
        chat_payload, artifact = run_for_chat(inputs, user_query=query, history=history, user_mode=getattr(args, "userMode", "farmer"))

    cp_dict = json.loads(json.dumps(chat_payload, default=lambda o: o.__dict__))

    return artifact_to_run(artifact, chat_payload=cp_dict)


def run_full_mode(ctx: dict, query: str = "") -> dict:
    """
    Full mode — runs orchestrator, returns canonical AgriBrainRun JSON.
    Used by /api/agribrain/run and /api/agribrain/analyze replacement.
    """
    from orchestrator_v2.runner import run_orchestrator
    from orchestrator_v2.run_schema import artifact_to_run
    from orchestrator_v2.intents import detect_intent

    inputs = _build_inputs(ctx, query)
    intent = detect_intent(query, has_context=True) if query else None

    # If query exists, we use run_for_chat to get date resolution + payload in one shot
    if query:
        from orchestrator_v2.runner import run_for_chat
        f = io.StringIO()
        with redirect_stdout(f):
            cp, artifact = run_for_chat(inputs, user_query=query, user_mode=getattr(args, "userMode", "farmer") if 'args' in locals() else "farmer")
        chat_payload = json.loads(json.dumps(cp, default=lambda o: o.__dict__))
    else:
        f = io.StringIO()
        with redirect_stdout(f):
            artifact = run_orchestrator(inputs, intent=intent, user_query=query)
        chat_payload = None

    return artifact_to_run(artifact, chat_payload=chat_payload)


def _enum_value(x):
    return x.value if hasattr(x, "value") else x


def _serialize_histogram(h):
    """Serialize histogram — preserve None for missing p10/p90 instead of faking 0.0."""
    raw_p10 = getattr(h, "p10", None)
    raw_p90 = getattr(h, "p90", None)
    return {
        "surface_type": _enum_value(getattr(h, "surface_type", "")),
        "region_id": getattr(h, "region_id", ""),
        "bin_edges": list(getattr(h, "bin_edges", []) or []),
        "bin_counts": list(getattr(h, "bin_counts", []) or []),
        "mean": float(getattr(h, "mean", 0.0) or 0.0),
        "std": float(getattr(h, "std", 0.0) or 0.0),
        "p10": float(raw_p10) if raw_p10 is not None else None,
        "p90": float(raw_p90) if raw_p90 is not None else None,
        "valid_pixels": int(getattr(h, "valid_pixels", 0) or 0),
        "total_pixels": int(getattr(h, "total_pixels", 0) or 0),
    }


def _serialize_delta_histogram(d):
    return {
        "surface_type": _enum_value(getattr(d, "surface_type", "")),
        "date_from": getattr(d, "date_from", ""),
        "date_to": getattr(d, "date_to", ""),
        "bin_edges": list(getattr(d, "bin_edges", []) or []),
        "bin_counts": list(getattr(d, "bin_counts", []) or []),
        "mean_change": float(getattr(d, "mean_change", 0.0) or 0.0),
        "shift_direction": getattr(d, "shift_direction", "STABLE"),
    }


def _serialize_l10_output(l10_out):
    surfaces = []
    for s in getattr(l10_out, "surface_pack", []) or []:
        surfaces.append({
            "type": _enum_value(getattr(s, "semantic_type", "")),
            "semantic_type": _enum_value(getattr(s, "semantic_type", "")),
            "values": getattr(s, "values", []) or [],
            "grounding_class": getattr(s, "grounding_class", None) or "UNIFORM",
            "units": getattr(s, "units", "") or "",
            "render_range": list(getattr(s, "render_range", [0, 1]) or [0, 1]),
            "palette_id": _enum_value(getattr(s, "palette_id", "viridis")),
            "source_layers": list(getattr(s, "source_layers", []) or []),
            "provenance": getattr(s, "provenance", {}) or {},
        })

    zones = []
    for z in getattr(l10_out, "zone_pack", []) or []:
        # WS5: Use human-readable label from labeler.py, fall back to description
        human_label = getattr(z, "label", "") or getattr(z, "description", "") or getattr(z, "zone_id", "")
        zones.append({
            "zone_id": getattr(z, "zone_id", ""),
            "label": human_label,
            "zone_type": _enum_value(getattr(z, "zone_type", "")),
            "zone_family": _enum_value(getattr(z, "zone_family", "")),
            "area_fraction": float(getattr(z, "area_fraction", 0.0) or getattr(z, "area_pct", 0.0) or 0.0),
            "cell_indices": list(getattr(z, "cell_indices", []) or []),
            "severity": float(getattr(z, "severity", 0.0) or 0.0),
            "confidence": float(getattr(z, "confidence", 0.0) or 0.0),
            "confidence_reasons": list(getattr(z, "confidence_reasons", []) or []),
            "top_drivers": list(getattr(z, "top_drivers", []) or []),
            "linked_actions": list(getattr(z, "linked_actions", []) or []),
            "surface_stats": getattr(z, "surface_stats", {}) or {},
            "source_dominance": (getattr(z, "uncertainty_summary", {}) or {}).get("source_dominance"),
            "evidence_age_days": (getattr(z, "time_window", {}) or {}).get("age_days"),
            "trust_note": (getattr(z, "uncertainty_summary", {}) or {}).get("trust_note"),
            "is_inferred": (getattr(z, "uncertainty_summary", {}) or {}).get("is_inferred"),
            "source_surface_type": _enum_value(getattr(z, "source_surface_type", "")),
            "calculation_trace": {
                "linked_findings": getattr(z, "linked_findings", []) or [],
                "zone_family": _enum_value(getattr(z, "zone_family", "")),
            },
        })

    hb = getattr(l10_out, "histogram_bundle", None)
    histograms = {
        "field": [_serialize_histogram(h) for h in getattr(hb, "field_histograms", []) or []],
        "zone": [_serialize_histogram(h) for h in getattr(hb, "zone_histograms", []) or []],
        "delta": [_serialize_delta_histogram(d) for d in getattr(hb, "delta_histograms", []) or []],
        "uncertainty": [_serialize_histogram(h) for h in getattr(hb, "uncertainty_histograms", []) or []],
    }

    qr = getattr(l10_out, "quality_report", None)
    quality = {
        "degradation_mode": _enum_value(getattr(qr, "degradation_mode", "NORMAL")),
        "reliability_score": float(getattr(qr, "reliability_score", 0.0) or 0.0),
        "surfaces_generated": int(getattr(qr, "surfaces_generated", len(surfaces)) or len(surfaces)),
        "zones_generated": int(getattr(qr, "zones_generated", len(zones)) or len(zones)),
        "grid_alignment_ok": bool(getattr(qr, "grid_alignment_ok", True)),
        "detail_conservation_ok": bool(getattr(qr, "detail_conservation_ok", True)),
        "zone_state_by_surface": getattr(qr, "zone_state_by_surface", {}) or {},
        "warnings": list(getattr(qr, "warnings", []) or []),
    }

    if surfaces and surfaces[0]["values"]:
        grid_height = len(surfaces[0]["values"])
        grid_width = len(surfaces[0]["values"][0]) if surfaces[0]["values"][0] else 0
    else:
        grid_height = 0
        grid_width = 0

    # Serialization for Phase B Explainability Pack
    explainability_pack = {}
    for key, pack in getattr(l10_out, "explainability_pack", {}).items():
        explainability_pack[key] = {
            "summary": pack.summary,
            "top_drivers": [
                {"name": d.name, "value": d.value, "role": d.role, "description": d.description, "formatted_value": d.formatted_value}
                for d in pack.top_drivers
            ],
            "equations": [
                {"label": eq.label, "expression": eq.expression, "plain_language": eq.plain_language}
                for eq in pack.equations
            ],
            "charts": pack.charts,
            "provenance": {
                "sources": pack.provenance.sources,
                "timestamps": pack.provenance.timestamps,
                "model_version": pack.provenance.model_version,
                "run_id": pack.provenance.run_id,
                "degraded_reasons": pack.provenance.degraded_reasons,
            },
            "confidence": {
                "score": pack.confidence.score,
                "penalties": [
                    {"reason": p.reason, "impact": p.impact}
                    for p in pack.confidence.penalties
                ],
                "quality_scored_layers": pack.confidence.quality_scored_layers,
            }
        }

    return {
        "timestamp": getattr(l10_out, "timestamp", ""),
        "surfaces": surfaces,
        "zones": zones,
        "histograms": histograms,
        "quicklooks": getattr(l10_out, "quicklooks", {}) or {},
        "raster_pack": getattr(l10_out, "raster_pack", []) or [],
        "vector_pack": getattr(l10_out, "vector_pack", []) or [],
        "tile_manifest": getattr(l10_out, "tile_manifest", {}) or {},
        "quality": quality,
        "provenance": getattr(l10_out, "provenance", {}) or {},
        "grid": {"height": grid_height, "width": grid_width},
        "explainability_pack": explainability_pack,
        "scenario_pack": getattr(l10_out, "scenario_pack", []) or [],
        "history_pack": getattr(l10_out, "history_pack", []) or [],
    }

def run_surfaces_mode(ctx: dict, query: str = "") -> dict:
    """
    Surfaces mode — runs orchestrator and returns canonical AgriBrainRun
    enriched with full Layer 10 frontend payload.
    """
    from orchestrator_v2.runner import run_orchestrator
    from orchestrator_v2.run_schema import artifact_to_run
    from orchestrator_v2.intents import Intent

    inputs = _build_inputs(ctx, query)

    f = io.StringIO()
    with redirect_stdout(f):
        artifact = run_orchestrator(inputs, intent=Intent.UNKNOWN, user_query=query)

    l10_payload = {
        "timestamp": "",
        "surfaces": [],
        "zones": [],
        "histograms": {
            "field": [],
            "zone": [],
            "delta": [],
            "uncertainty": [],
        },
        "quicklooks": {},
        "raster_pack": [],
        "vector_pack": [],
        "tile_manifest": {},
        "quality": {
            "degradation_mode": "NORMAL",
            "reliability_score": 0.0,
            "surfaces_generated": 0,
            "zones_generated": 0,
            "grid_alignment_ok": True,
            "detail_conservation_ok": True,
            "warnings": [],
        },
        "provenance": {},
        "grid": {"height": 0, "width": 0},
        "explainability_pack": {},
        "scenario_pack": [],
        "history_pack": [],
    }

    if artifact.layer_10 and artifact.layer_10.output:
        l10_payload = _serialize_l10_output(artifact.layer_10.output)

    run = artifact_to_run(artifact, surfaces=l10_payload["surfaces"], layer10_detail=l10_payload)

    # Enrich canonical run with Layer 10 frontend bundle
    run["timestamp"] = l10_payload["timestamp"] or run["audit"].get("timestamp_utc", "")
    run["zones"] = l10_payload["zones"]
    run["histograms"] = l10_payload["histograms"]
    run["quicklooks"] = l10_payload["quicklooks"]
    run["raster_pack"] = l10_payload["raster_pack"]
    run["vector_pack"] = l10_payload["vector_pack"]
    run["tile_manifest"] = l10_payload["tile_manifest"]
    run["quality"] = l10_payload["quality"]
    run["provenance"] = l10_payload["provenance"]
    run["grid"] = l10_payload["grid"]
    
    # Phase B & C Mock Payload Enrichment
    run["explainability_pack"] = l10_payload.get("explainability_pack", {})
    run["scenario_pack"] = l10_payload.get("scenario_pack", [])
    run["history_pack"] = l10_payload.get("history_pack", [])

    return run


# ---- Canonical Early Exit Envelope ----

def _canonical_early_exit(run_id: str, mode: str, arf_dict: dict, exp_level: str = "INTERMEDIATE") -> dict:
    """
    Build a canonical AgriBrainRun envelope for early exits (greeting, general).
    Same shape as pipeline responses — eliminates payload family divergence.
    """
    return {
        "run_id": run_id,
        "plot_id": "NONE",
        "time_window": {"start": "", "end": ""},
        "intent": mode,
        "layer_results": {},
        "global_quality": {
            "reliability": 1.0,
            "degradation_modes": [],
            "missing_drivers": [],
            "critical_errors": [],
            "critical_failure": False,
            "alerts": [],
        },
        "unified_plan": {"tasks": []},
        "surfaces": [],
        "explanations": {
            "assistant_mode": mode,
            "assistant_style": "TUTOR",
            "arf": arf_dict,
            "summary": {"headline": arf_dict.get("headline", ""), "explanation": arf_dict.get("direct_answer", "")},
        },
        "recommendations": [],
        "top_findings": [],
        "audit": {
            "orchestrator_run_id": run_id,
            "artifact_hash": "",
            "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
            "orchestrator_version": "2.1.0",
            "layer_versions": {},
            "lineage_map": {},
            "provenance": {"data_sources": [], "quality_scored_layers": [], "degraded_layers": [], "failed_layers": [], "total_sources": 0},
        },
    }


def _greeting_arf(exp_level: str = "INTERMEDIATE") -> dict:
    """Build greeting ARF dict."""
    from orchestrator_v2.arf_schema import ARFResponse, LearningModule

    return ARFResponse(
        headline="Hi 👋 I am AgriBrain.",
        direct_answer="I can help with crop health, irrigation decisions, pests/disease risk, and rainfall summaries.",
        suitability_score="N/A",
        confidence_badge="HIGH",
        confidence_reason="System online.",
        what_it_means="I am ready to analyze your field data context.",
        reasoning_cards=[],
        recommendations=[],
        learning=LearningModule(level=exp_level, micro_lesson="Ask me about rainfall, soil moisture, or crop health.", definitions={}),
        followups=[],
        internal_memory_updates=None,
    ).dict()


def _general_arf(query: str, exp_level: str = "INTERMEDIATE") -> dict:
    """Build general knowledge ARF dict via LLM fallback."""
    API_KEY = os.getenv("OPENROUTER_API_KEY")

    if not API_KEY:
        return {
            "headline": "Configuration Missing",
            "direct_answer": "My API key is not configured, so I am running in local-only mode.",
            "suitability_score": "N/A",
            "confidence_badge": "LOW",
            "confidence_reason": "API Unreachable",
            "what_it_means": "My core diagnostics can run, but my natural-language logic layer is offline.",
            "reasoning_cards": [],
            "recommendations": [],
            "learning": {
                "level": exp_level,
                "micro_lesson": "You can continue examining the map layers while the text engine is down.",
                "definitions": {}
            },
            "followups": [],
            "internal_memory_updates": None
        }

    import requests
    sys_prompt = f"""You are AgriBrain, an expert agronomist + teacher.
The user asked a General Knowledge question. Do not assume any specific field context.
Adapt teaching depth to Farmer Experience Level: {exp_level}.
Respond ONLY in valid JSON matching this schema:
{{
  "headline": "Brief title",
  "direct_answer": "Clear answer",
  "suitability_score": "N/A",
  "confidence_badge": "HIGH",
  "confidence_reason": "General established agronomic knowledge",
  "what_it_means": "Why this matters in farming",
  "reasoning_cards": [],
  "recommendations": [],
  "learning": {{"level": "{exp_level}", "micro_lesson": "Teaching point", "definitions": {{}}}},
  "followups": [],
  "internal_memory_updates": null
}}"""
    try:
        rj_run = {}
        choices_run = None
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "meta-llama/llama-3.3-70b-instruct:free",
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": query},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
                timeout=15,
            )
            if resp.status_code == 200:
                rj_run = resp.json()
                choices_run = rj_run.get("choices")
            else:
                print(f"[LLM] OpenRouter returned {resp.status_code}")
        except Exception as e:
            print(f"[LLM] OpenRouter network error: {e}")

        if not choices_run and os.environ.get("GEMINI_API_KEY"):
            print("[LLM] Falling back to Gemini API")
            try:
                gemini_resp = requests.post(
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    headers={"Authorization": f"Bearer {os.environ.get('GEMINI_API_KEY')}", "Content-Type": "application/json"},
                    json={
                        "model": "gemini-flash-latest",
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": query},
                        ],
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=15
                )
                print(f"[LLM-DEBUG] Gemini RUN HTTP {gemini_resp.status_code}")
                if gemini_resp.status_code == 200:
                    rj_run = gemini_resp.json()
                    choices_run = rj_run.get("choices")
                else:
                    print(f"[LLM-ERROR] Gemini RUN fallback returned {gemini_resp.status_code}: {gemini_resp.text}")
            except Exception as e:
                print(f"[LLM-ERROR] Gemini RUN fallback failed/timeout: {e}")

        if not choices_run:
            raise ValueError(f"No choices in LLM response: {rj_run.get('error', resp.status_code)}")
        raw = choices_run[0].get("message", {}).get("content", "{}").strip()
        raw_json = json.loads(raw)
        
        # --- ARF Sanitizer (General) ---
        recs = raw_json.get("recommendations", [])
        if isinstance(recs, list):
            sanitized_recs = []
            for r in recs:
                if isinstance(r, str):
                    sanitized_recs.append({
                        "type": "MONITOR",
                        "title": r,
                        "is_allowed": True,
                        "blocked_reasons": [],
                        "why_it_matters": "",
                        "how_to_do_it_steps": [],
                        "risk_if_wrong": "LOW"
                    })
                elif isinstance(r, dict):
                    sanitized_recs.append(r)
            raw_json["recommendations"] = sanitized_recs
            
        # Fix Gemini string followups
        f_ups = raw_json.get("followups", [])
        if isinstance(f_ups, list):
            sanitized_f = []
            for f in f_ups:
                if isinstance(f, str):
                    sanitized_f.append({"question": f, "why": "Context discovery"})
                elif isinstance(f, dict):
                    sanitized_f.append(f)
            raw_json["followups"] = sanitized_f
                
        fups = raw_json.get("followups", [])
        if isinstance(fups, list):
            sanitized_fups = []
            for f in fups:
                if isinstance(f, str):
                    sanitized_fups.append({"question": f, "why": "Clarifying context"})
                elif isinstance(f, dict):
                    sanitized_fups.append(f)
            raw_json["followups"] = sanitized_fups

        cards = raw_json.get("reasoning_cards", [])
        if isinstance(cards, list):
            sanitized_cards = []
            for c in cards:
                if isinstance(c, str):
                    sanitized_cards.append({
                        "type": "EVIDENCE",
                        "claim": c,
                        "evidence": "",
                        "uncertainty": ""
                    })
                elif isinstance(c, dict):
                    sanitized_cards.append(c)
            raw_json["reasoning_cards"] = sanitized_cards
                
        learning = raw_json.get("learning", {})
        if isinstance(learning, str):
            raw_json["learning"] = {
                "level": exp_level,
                "micro_lesson": learning,
                "definitions": {}
            }
        elif not learning or not isinstance(learning, dict):
            raw_json["learning"] = {
                "level": exp_level,
                "micro_lesson": (
                    "AgriBrain uses a multi-source data fusion approach: Sentinel-2 optical imagery "
                    "provides NDVI and canopy indices; Sentinel-1 SAR provides all-weather structural "
                    "signals; OpenMeteo provides ET0 and rainfall; SoilGrids provides root-zone "
                    "properties. A Kalman filter assimilates these into a continuous daily crop state, "
                    "interpolating through cloud gaps and missing passes."
                ),
                "definitions": {
                    "ET0": "Reference evapotranspiration — atmospheric water demand independent of crop type.",
                    "SAR": "Synthetic Aperture Radar — penetrates clouds and measures canopy structure and soil moisture."
                }
            }

        from orchestrator_v2.arf_schema import ARFResponse
        try:
            return ARFResponse(**raw_json).dict()
        except Exception as e:
            print(f"DEBUG: General Knowledge LLM schema validation failed: {e}")
            return {
                "headline": "General Assessment",
                "direct_answer": "I analyzed your question, but the response formatting requires fallback shaping.",
                "suitability_score": "N/A",
                "confidence_badge": "MED",
                "confidence_reason": "Structured explanation formatting failed",
                "what_it_means": "The intelligence engine executed, but the natural logic needs repair.",
                "reasoning_cards": [],
                "recommendations": [],
                "learning": {
                    "level": exp_level,
                    "micro_lesson": "You can still run plot diagnostics while my explanation module recovers.",
                    "definitions": {}
                },
                "followups": [],
                "internal_memory_updates": None
            }
    except Exception as e:
        print(f"DEBUG: General LLM Network Error: {e}")
        return {
            "headline": "Network Unreachable",
            "direct_answer": "I am experiencing temporary network issues reaching my reasoning engine. Please try again in a few moments.",
            "suitability_score": "N/A",
            "confidence_badge": "LOW",
            "confidence_reason": "API Unreachable",
            "what_it_means": "My core diagnostics can run, but my natural-language logic layer is temporarily offline.",
            "reasoning_cards": [],
            "recommendations": [],
            "learning": {
                "level": exp_level,
                "micro_lesson": "You can continue examining the map layers while the text engine is down.",
                "definitions": {}
            },
            "followups": [],
            "internal_memory_updates": None
        }


# ---- Main ----

def main():
    parser = argparse.ArgumentParser(description="AgriBrain Unified Run Entrypoint")
    parser.add_argument("--context", type=str, required=True, help="Base64 or raw JSON context")
    parser.add_argument("--query", type=str, default="", help="User query text")
    parser.add_argument("--mode", type=str, default="chat", choices=["chat", "full", "surfaces"], help="Execution mode")
    parser.add_argument("--history", type=str, default="", help="Base64-encoded chat history")
    parser.add_argument("--exp", type=str, default="INTERMEDIATE", help="Farmer experience level")
    parser.add_argument("--cid", type=str, default="local_dev_session", help="Conversation ID")
    args = parser.parse_args()

    try:
        ctx = _parse_context(args.context)
        query = args.query.strip() if args.query else ""

        if args.mode == "chat":
            result = run_chat_mode(ctx, query, args)
        elif args.mode == "full":
            result = run_full_mode(ctx, query)
        elif args.mode == "surfaces":
            result = run_surfaces_mode(ctx, query)
        else:
            result = {"error": f"Unknown mode: {args.mode}"}

        print(json.dumps(result, default=str, indent=2))

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": str(e), "type": "AgriBrainRunError"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
