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

    start = None
    end = None
    
    # 1. Context
    date_range_ctx = ctx.get("date_range")
    if isinstance(date_range_ctx, dict):
        start = date_range_ctx.get("start") or date_range_ctx.get("start_date")
        end = date_range_ctx.get("end") or date_range_ctx.get("end_date")
    if not start or not end:
        start = ctx.get("start_date") or ctx.get("start")
        end = ctx.get("end_date") or ctx.get("end")
        
    # 2. Window
    if not start or not end:
        window_ctx = ctx.get("window")
        if isinstance(window_ctx, dict):
            start = window_ctx.get("start") or window_ctx.get("start_date")
            end = window_ctx.get("end") or window_ctx.get("end_date")
            
    # 3. Fallback
    if not start or not end:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=14)
        start = start_dt.strftime("%Y-%m-%d")
        end = end_dt.strftime("%Y-%m-%d")
    
    # Ensure they are strings, possibly convert from datetime objects or formatting if needed
    if isinstance(start, datetime):
        start = start.strftime("%Y-%m-%d")
    if isinstance(end, datetime):
        end = end.strftime("%Y-%m-%d")

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
            "start": start,
            "end": end,
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
            "ground_truth_context": ctx.get("ground_truth_context", {}),  # V61B
            "visual_intensity": ctx.get("visual_intensity", 0.40),
            "user_mode": ctx.get("user_mode", "farmer"),
            "source_policy": ctx.get("source_policy"),
        },
        policy_snapshot={},
    )


def _attach_snapshot_identity(run: dict, inputs, artifact) -> dict:
    """Attach the canonical snapshot identity contract to every run mode."""
    from layer10_sire.surface_contract import (
        RENDER_AUTHORIZATION_VERSION,
        SURFACES_SCHEMA_VERSION,
    )

    provenance = run.get("provenance") if isinstance(run.get("provenance"), dict) else {}
    agribrain_run_id = (
        run.get("agribrain_run_id")
        or run.get("run_id")
        or getattr(artifact, "run_id", None)
    )
    run["intelligence_snapshot_id"] = (
        run.get("intelligence_snapshot_id")
        or provenance.get("intelligence_snapshot_id")
        or agribrain_run_id
    )
    run["agribrain_run_id"] = agribrain_run_id
    run["generated_at"] = (
        run.get("generated_at")
        or run.get("timestamp")
        or (run.get("audit") or {}).get("timestamp_utc")
    )
    run["source_window"] = [
        inputs.date_range.get("start", ""),
        inputs.date_range.get("end", ""),
    ]
    run["surface_schema_version"] = SURFACES_SCHEMA_VERSION
    run["temporal_evidence_contract_version"] = "temporal_evidence_admission_v1"
    run["render_authorization_version"] = (
        run.get("render_authorization_version") or RENDER_AUTHORIZATION_VERSION
    )
    return run


def run_chat_mode(ctx: dict, query: str, args, progress_cb=None) -> dict:
    """
    Chat mode — runs pipeline and returns canonical AgriBrainRun.
    The ChatPayload is embedded inside explanations, not returned raw.
    Greeting/general early exits also use the canonical envelope.
    """
    plot_id = ctx.get("plot_id", "UNKNOWN")

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

    if progress_cb:
        progress_cb("Routing query intent", "running")

    # Run high-fidelity intent router to find target engines and show them to the user
    routed_engines = []
    try:
        from layer9_interface.intent_router import route_intent
        decision = route_intent(query, history)
        routed_engines = decision.get("engines", [])
    except Exception as e:
        print(f"Failed to run intent router: {e}")

    from orchestrator_v2.intents import detect_intent, Intent
    intent = detect_intent(query, has_context=(plot_id != "UNKNOWN"))

    if progress_cb:
        progress_cb("Routing query intent", "done")
        if routed_engines:
            progress_cb(f"Routing to engines: {', '.join(routed_engines)}", "running")

    # Greeting early exit — canonical envelope
    if intent == Intent.GREETING:
        if progress_cb:
            if routed_engines:
                progress_cb(f"Routing to engines: {', '.join(routed_engines)}", "done")
            progress_cb("Complete", "done")
        return _canonical_early_exit("GREETING_ONLY", "WELCOME", _greeting_arf(args.exp), args.exp)

    # General knowledge early exit — canonical envelope
    if intent == Intent.GENERAL:
        if progress_cb:
            if routed_engines:
                progress_cb(f"Routing to engines: {', '.join(routed_engines)}", "done")
            progress_cb("Complete", "done")
        return _canonical_early_exit("GENERAL_KNOWLEDGE", "GENERAL", _general_arf(query, args.exp), args.exp)

    # Full pipeline → canonical AgriBrainRun
    from orchestrator_v2.runner import run_orchestrator, run_for_chat
    from orchestrator_v2.run_schema import artifact_to_run

    inputs = _build_inputs(ctx, query)

    # Set intent routing engines to done before starting pipeline
    if progress_cb and routed_engines:
        progress_cb(f"Routing to engines: {', '.join(routed_engines)}", "done")

    f = io.StringIO()
    with redirect_stdout(f):
        chat_payload, artifact = run_for_chat(
            inputs, user_query=query, history=history,
            user_mode=getattr(args, "userMode", "farmer"),
            progress_cb=progress_cb
        )

    cp_dict = json.loads(json.dumps(chat_payload, default=lambda o: o.__dict__))

    run = artifact_to_run(artifact, chat_payload=cp_dict)
    return _attach_snapshot_identity(run, inputs, artifact)


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

    run = artifact_to_run(artifact, chat_payload=chat_payload)
    return _attach_snapshot_identity(run, inputs, artifact)


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


def _grid_spec_to_dict(raw_gs):
    if not raw_gs:
        return None
    if isinstance(raw_gs, dict):
        return raw_gs
    if hasattr(raw_gs, "__dict__"):
        return {
            "crs": getattr(raw_gs, "crs", ""),
            "transform": list(getattr(raw_gs, "transform", []) or []),
            "width": getattr(raw_gs, "width", 0),
            "height": getattr(raw_gs, "height", 0),
            "bounds": list(getattr(raw_gs, "bounds", []) or []),
            "resolution": getattr(raw_gs, "resolution", 10.0),
        }
    return None


def _provenance_get(provenance, key, default=None):
    if isinstance(provenance, dict):
        return provenance.get(key, default)
    return getattr(provenance, key, default)


def _surface_attr_or_provenance(surface, provenance, key, *aliases):
    value = getattr(surface, key, None)
    if value is not None:
        return value
    for candidate in (key, *aliases):
        value = _provenance_get(provenance, candidate, None)
        if value is not None:
            return value
    return None


def _serialize_l10_output(l10_out):
    from layer10_sire.surface_contract import (
        SURFACES_SCHEMA_VERSION,
        build_default_asmae_proof,
        build_no_data_mode_display_state,
        build_no_data_render_authorizations,
        build_no_data_source_policy_display_state,
        RENDER_AUTHORIZATION_VERSION,
    )
    if getattr(l10_out, "placeholder_only", False) or (isinstance(getattr(l10_out, "provenance", None), dict) and getattr(l10_out, "provenance", {}).get("placeholder_only")):
        no_data_reason = "insufficient_evidence"
        source_policy_state = getattr(l10_out, "source_policy_display_state", {}) or {}
        requested_policy = source_policy_state.get("requested_policy", "satellite")
        return {
            "schema_version": SURFACES_SCHEMA_VERSION,
            "version": SURFACES_SCHEMA_VERSION,
            "surface_schema_version": SURFACES_SCHEMA_VERSION,
            "run_id": getattr(l10_out, "run_id", ""),
            "publication_run_id": getattr(l10_out, "publication_run_id", "") or getattr(l10_out, "run_id", ""),
            "request_run_id": getattr(l10_out, "request_run_id", ""),
            "publication_id": getattr(l10_out, "publication_id", ""),
            "publication_status": getattr(l10_out, "publication_status", "INVALID_PUBLICATION"),
            "status": "degraded",
            "degradation_mode": "DATA_GAP",
            "warning_codes": ["INSUFFICIENT_EVIDENCE"],
            "rendered_scientific_surfaces": 0,
            "placeholder_only": True,
            "timestamp": getattr(l10_out, "timestamp", ""),
            "surfaces": [],
            "zones": [],
            "histograms": {
                "field": [], "zone": [], "delta": [], "uncertainty": []
            },
            "quicklooks": {},
            "raster_pack": [],
            "vector_pack": [],
            "tile_manifest": {},
            "quality": {
                "degradation_mode": "DATA_GAP",
                "reliability_score": 0.0,
                "surfaces_generated": 0,
                "zones_generated": 0,
                "grid_alignment_ok": False,
                "detail_conservation_ok": False,
                "warnings": ["INSUFFICIENT_EVIDENCE"],
            },
            "provenance": {
                "status": "degraded",
                "degradation_mode": "DATA_GAP",
                "warning_codes": ["INSUFFICIENT_EVIDENCE"],
                "rendered_scientific_surfaces": 0,
                "placeholder_only": True
            },
            "asmae_evidence_state": getattr(l10_out, "asmae_evidence_state", {
                "state": "unavailable",
                "real_asmae_evidence": False,
                "reason": "placeholder_l10_output"
            }),
            "core_asmae_evidence_state": getattr(l10_out, "core_asmae_evidence_state", {}) or getattr(l10_out, "asmae_evidence_state", {}) or {
                "state": "unavailable", "authority": "none", "reason": "placeholder_l10_output"
            },
            "publication_surface_state": getattr(l10_out, "publication_surface_state", {}) or {
                "state": "terminal_no_data_publication",
                "authority": "display_inventory_only",
                "surface_available": False,
                "reason": no_data_reason,
            },
            "publication_demotion": getattr(l10_out, "publication_demotion", {}) or {
                "applied": True, "reason": no_data_reason
            },
            "asmae_feature_pack": getattr(l10_out, "asmae_feature_pack", {}) or {},
            "mode_display_state": getattr(l10_out, "mode_display_state", {}) or build_no_data_mode_display_state(no_data_reason),
            "source_policy_display_state": source_policy_state or build_no_data_source_policy_display_state(requested_policy, no_data_reason),
            "grid": {"height": 0, "width": 0},
            "explainability_pack": {},
            "scenario_pack": [],
            "history_pack": [],
            # BC.10.18 — authority fields must be present even on degraded output
            "render_authorizations": build_no_data_render_authorizations(),
            "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
            "asmae_proof": build_default_asmae_proof(),
            "surface_behavior_proof": {},
            "display_trace": {},
        }

    surfaces = []
    for s in getattr(l10_out, "surface_pack", []) or []:
        # V92.4: Serialize grid_spec on each surface for GIS alignment
        provenance = getattr(s, "provenance", {}) or {}
        gs_dict = _grid_spec_to_dict(getattr(s, "grid_spec", None))
        surfaces.append({
            "type": _enum_value(getattr(s, "semantic_type", "")),
            "semantic_type": _enum_value(getattr(s, "semantic_type", "")),
            "values": getattr(s, "values", []) or [],
            "grounding_class": getattr(s, "grounding_class", None) or "UNIFORM",
            "raster_basis": list(getattr(s, "raster_basis", []) or []),
            "observed_ratio": float(getattr(s, "observed_ratio", 0.0) or 0.0),
            "units": getattr(s, "units", "") or "",
            "render_range": list(getattr(s, "render_range", [0, 1]) or [0, 1]),
            "palette_id": _enum_value(getattr(s, "palette_id", "viridis")),
            "source_layers": list(getattr(s, "source_layers", []) or []),
            "provenance": provenance,
            "grid_spec": gs_dict,
            "render_kind": _surface_attr_or_provenance(s, provenance, "render_kind", "renderKind"),
            "display_level": _surface_attr_or_provenance(s, provenance, "display_level", "displayLevel"),
            "display_grid_spec": _grid_spec_to_dict(_surface_attr_or_provenance(s, provenance, "display_grid_spec", "displayGridSpec")),
            "source_grid_spec": _grid_spec_to_dict(_surface_attr_or_provenance(s, provenance, "source_grid_spec", "sourceGridSpec")),
            "source_reality": _surface_attr_or_provenance(s, provenance, "source_reality", "sourceReality"),
            "diagnostic_only": _surface_attr_or_provenance(s, provenance, "diagnostic_only", "diagnosticOnly"),
            "state_update_allowed": _surface_attr_or_provenance(s, provenance, "state_update_allowed", "stateUpdateAllowed"),
            "prescription_driver_allowed": _surface_attr_or_provenance(s, provenance, "prescription_driver_allowed", "prescriptionDriverAllowed"),
            "confidence": _surface_attr_or_provenance(s, provenance, "confidence"),
            "uncertainty": _surface_attr_or_provenance(s, provenance, "uncertainty"),
            "authority_block_reason": _surface_attr_or_provenance(s, provenance, "authority_block_reason", "authorityBlockReason"),
            "surface_role": _surface_attr_or_provenance(
                s, provenance, "surface_role", "surfaceRole"
            ) or (
                "render_dependency"
                if _enum_value(getattr(s, "semantic_type", "")) in {
                    "OBSERVED_DATA_MASK_NDVI", "GAP_FILL_MASK_NDVI", "VALID_DATA_MASK_NDVI"
                }
                else "agronomic_surface"
            ),
        })

    zones = []
    for z in getattr(l10_out, "zone_pack", []) or []:
        # WS5: Use human-readable label from labeler.py, fall back to description
        human_label = getattr(z, "label", "") or getattr(z, "description", "") or getattr(z, "zone_id", "")
        grid_validity = str(getattr(z, "grid_validity", "unknown") or "unknown")
        authority = str(getattr(z, "authority", "algorithmic_scouting_region") or "algorithmic_scouting_region")
        authority_block_reason = getattr(z, "authority_block_reason", None)
        spatial_geometry_authorized = (
            grid_validity == "valid"
            and not authority_block_reason
            and authority != "plot_level_heterogeneity_notice"
        )
        serialized_authority = (
            authority if spatial_geometry_authorized else "plot_level_heterogeneity_notice"
        )
        serialized_cells = (
            list(getattr(z, "cell_indices", []) or [])
            if spatial_geometry_authorized
            else []
        )
        if not spatial_geometry_authorized and not authority_block_reason:
            authority_block_reason = f"spatial_zone_not_authorized:{grid_validity}"
        zones.append({
            "zone_id": getattr(z, "zone_id", ""),
            "label": human_label,
            "zone_type": _enum_value(getattr(z, "zone_type", "")),
            "zone_family": _enum_value(getattr(z, "zone_family", "")),
            "area_fraction": float(getattr(z, "area_pct", 0.0) or 0.0),
            "cell_indices": serialized_cells,
            "bbox": list(getattr(z, "bbox", []) or []) if spatial_geometry_authorized else None,
            "area_m2": float(getattr(z, "area_m2", 0.0) or 0.0),
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
            "authority": serialized_authority,
            "source_authority": authority,
            "grid_validity": grid_validity,
            "observed_cell_share": float(getattr(z, "observed_cell_share", 0.0) or 0.0),
            "gap_filled_share": float(getattr(z, "gap_filled_share", 0.0) or 0.0),
            "confidence_basis": list(getattr(z, "confidence_basis", []) or []),
            "authority_block_reason": authority_block_reason,
            "spatial_geometry_authorized": spatial_geometry_authorized,
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
            },
            "recommended_action": getattr(pack, "recommended_action", None),
            "driver_confidence": getattr(pack, "driver_confidence", None),
            "action_level": getattr(pack, "action_level", None)
        }

    # BC.10.18 — render authorization authority fields
    _raw_render_auth = getattr(l10_out, "render_authorizations", None)
    _render_auth = _raw_render_auth if (isinstance(_raw_render_auth, dict) and len(_raw_render_auth) > 0) else build_no_data_render_authorizations()
    _mode_display_state = getattr(l10_out, "mode_display_state", {}) or {}
    _source_policy_display_state = getattr(l10_out, "source_policy_display_state", {}) or {}
    _no_data_reason = (
        getattr(l10_out, "provenance", {}).get("spatial_processing_block_reason")
        if isinstance(getattr(l10_out, "provenance", None), dict)
        else None
    ) or "insufficient_evidence"
    if not _mode_display_state:
        _mode_display_state = build_no_data_mode_display_state(_no_data_reason)
    if not _source_policy_display_state:
        _source_policy_display_state = build_no_data_source_policy_display_state(
            "satellite", _no_data_reason
        )
    _raw_asmae_proof = getattr(l10_out, "asmae_proof", None)
    # Never emit empty asmae_proof — use default structure
    _asmae_proof = _raw_asmae_proof if (isinstance(_raw_asmae_proof, dict) and len(_raw_asmae_proof) > 0) else build_default_asmae_proof()

    return {
        "schema_version": SURFACES_SCHEMA_VERSION,
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "run_id": getattr(l10_out, "run_id", ""),
        "publication_run_id": getattr(l10_out, "publication_run_id", "") or getattr(l10_out, "run_id", ""),
        "request_run_id": getattr(l10_out, "request_run_id", ""),
        "publication_id": getattr(l10_out, "publication_id", ""),
        "publication_status": getattr(l10_out, "publication_status", "INVALID_PUBLICATION"),
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
        "ground_truth_summary": getattr(l10_out, "ground_truth_summary", {}) or {},  # V61B
        "visual_source": getattr(l10_out, "visual_source", {}) or {},  # V61D
        # V92.4: Mode surface plan and surface inventory — previously silently dropped
        "mode_surface_plan": getattr(l10_out, "mode_surface_plan", {}) or {},
        "surface_inventory": getattr(l10_out, "surface_inventory", {}) or {},
        # V92.4-BC: Backend-authoritative display state per mode
        "mode_display_state": _mode_display_state,
        "asmae_evidence_state": getattr(l10_out, "asmae_evidence_state", {}) or {},
        "core_asmae_evidence_state": getattr(l10_out, "core_asmae_evidence_state", {}) or getattr(l10_out, "asmae_evidence_state", {}) or {},
        "publication_surface_state": getattr(l10_out, "publication_surface_state", {}) or {},
        "publication_demotion": getattr(l10_out, "publication_demotion", {}) or {},
        "asmae_plot_state_artifact": getattr(l10_out, "asmae_plot_state_artifact", {}) or {},
        "asmae_feature_pack": getattr(l10_out, "asmae_feature_pack", {}) or {},
        "source_policy_display_state": _source_policy_display_state,
        "surface_behavior_proof": getattr(l10_out, "surface_behavior_proof", {}) or {},
        "display_trace": getattr(l10_out, "display_trace", {}) or {},
        # BC.10.18 — authority fields: render_authorizations and asmae_proof must survive serialization
        "render_authorizations": _render_auth,
        "render_authorization_version": getattr(
            l10_out, "render_authorization_version", RENDER_AUTHORIZATION_VERSION
        ) or RENDER_AUTHORIZATION_VERSION,
        "asmae_proof": _asmae_proof,
    }

def run_surfaces_mode(ctx: dict, query: str = "", progress_cb=None) -> dict:
    """
    Surfaces mode — runs orchestrator and returns canonical AgriBrainRun
    enriched with full Layer 10 frontend payload.
    
    Args:
        progress_cb: Optional callback(stage: str, status: str, elapsed: float)
                     for real-time frontend progress reporting.
    """
    from layer10_sire.surface_contract import (
        SURFACES_SCHEMA_VERSION,
        build_default_asmae_proof,
        RENDER_AUTHORIZATION_VERSION,
    )
    import time as _time
    _t0 = _time.perf_counter()

    def _progress(stage, status, elapsed=0.0):
        if progress_cb:
            try:
                progress_cb(stage, status, elapsed)
            except Exception:
                pass

    from orchestrator_v2.runner import run_orchestrator
    from orchestrator_v2.run_schema import artifact_to_run
    from orchestrator_v2.intents import Intent

    inputs = _build_inputs(ctx, query)

    _progress("Fusing satellite & weather data", "running")

    import os
    old_val = os.environ.get("L10_DISABLE_LIVE_VISUAL_PROVIDERS_IN_SURFACE_RUN")
    os.environ["L10_DISABLE_LIVE_VISUAL_PROVIDERS_IN_SURFACE_RUN"] = "true"
    try:
        f = io.StringIO()
        with redirect_stdout(f):
            artifact = run_orchestrator(inputs, intent=Intent.UNKNOWN, user_query=query, skip_l9=True, progress_cb=progress_cb)
    finally:
        if old_val is not None:
            os.environ["L10_DISABLE_LIVE_VISUAL_PROVIDERS_IN_SURFACE_RUN"] = old_val
        else:
            os.environ.pop("L10_DISABLE_LIVE_VISUAL_PROVIDERS_IN_SURFACE_RUN", None)

    _t_orch = _time.perf_counter()
    print(f"[PERF] run_surfaces_mode: orchestrator (L1-L10) = {_t_orch - _t0:.2f}s")

    _progress("Preparing spatial intelligence map", "running")

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

    _t_serial = _time.perf_counter()
    print(f"[PERF] run_surfaces_mode: serialize = {_t_serial - _t_orch:.2f}s")

    run = artifact_to_run(artifact, surfaces=l10_payload["surfaces"], layer10_detail=l10_payload)
    # artifact_to_run also exposes every Layer 10 field at the top level. Keep
    # one canonical copy; the nested duplicate added ~10 MB to every response.
    run.pop("layer10", None)

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
    run["schema_version"] = l10_payload.get("schema_version", SURFACES_SCHEMA_VERSION)
    run["version"] = l10_payload.get("version", SURFACES_SCHEMA_VERSION)
    # The published envelope belongs to the immutable orchestrator science
    # run. Layer 10's component run remains available in provenance.
    run["publication_run_id"] = run["run_id"]
    run["request_run_id"] = l10_payload.get("request_run_id", "")
    run["publication_id"] = l10_payload.get("publication_id", "")
    run["publication_status"] = l10_payload.get("publication_status", "INVALID_PUBLICATION")
    
    # Phase B & C Mock Payload Enrichment
    run["explainability_pack"] = l10_payload.get("explainability_pack", {})
    run["scenario_pack"] = l10_payload.get("scenario_pack", [])
    run["history_pack"] = l10_payload.get("history_pack", [])
    run["ground_truth_summary"] = l10_payload.get("ground_truth_summary", {})  # V61B
    run["visual_source"] = l10_payload.get("visual_source", {})  # V61D
    # V92.4: Thread mode_surface_plan and surface_inventory through surfaces mode
    run["mode_surface_plan"] = l10_payload.get("mode_surface_plan", {})
    run["surface_inventory"] = l10_payload.get("surface_inventory", {})
    # V92.4-BC: Thread mode_display_state
    run["mode_display_state"] = l10_payload.get("mode_display_state", {})
    run["asmae_evidence_state"] = l10_payload.get("asmae_evidence_state", {})
    run["core_asmae_evidence_state"] = l10_payload.get("core_asmae_evidence_state", {}) or run["asmae_evidence_state"]
    run["publication_surface_state"] = l10_payload.get("publication_surface_state", {})
    run["publication_demotion"] = l10_payload.get("publication_demotion", {})
    run["asmae_plot_state_artifact"] = l10_payload.get("asmae_plot_state_artifact", {})
    run["asmae_feature_pack"] = l10_payload.get("asmae_feature_pack", {})
    run["source_policy_display_state"] = l10_payload.get("source_policy_display_state", {})
    run["surface_behavior_proof"] = l10_payload.get("surface_behavior_proof", {})
    run["display_trace"] = l10_payload.get("display_trace", {})
    # Never emit empty asmae_proof — prefer canonical default structure
    _raw_asmae = l10_payload.get("asmae_proof", None)
    run["asmae_proof"] = _raw_asmae if (isinstance(_raw_asmae, dict) and len(_raw_asmae) > 0) else build_default_asmae_proof()
    # BC.10.18 — render authorization must be threaded through run_surfaces_mode
    run["render_authorizations"] = l10_payload.get("render_authorizations", {})
    run["render_authorization_version"] = l10_payload.get(
        "render_authorization_version", RENDER_AUTHORIZATION_VERSION
    ) or RENDER_AUTHORIZATION_VERSION
    provenance_snapshot_id = (run.get("provenance") or {}).get("intelligence_snapshot_id")
    agribrain_run_id = run.get("run_id") or run.get("agribrain_run_id") or getattr(artifact, "run_id", None)
    run["intelligence_snapshot_id"] = provenance_snapshot_id or agribrain_run_id
    run["agribrain_run_id"] = agribrain_run_id
    run["generated_at"] = run.get("timestamp")
    run["source_window"] = [inputs.date_range.get("start", ""), inputs.date_range.get("end", "")]
    run["surface_schema_version"] = SURFACES_SCHEMA_VERSION
    run["provenance"] = dict(run.get("provenance") or {})
    run["provenance"].update({
        "layer10_component_run_id": l10_payload.get("run_id", ""),
        "publication_run_id": run["publication_run_id"],
        "publication_id": run["publication_id"],
        "publication_status": run["publication_status"],
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
    })
    run["temporal_evidence_contract_version"] = "temporal_evidence_admission_v1"

    # ── Extract Kalman NDVI + SH indices from L1 output ──────────────
    # Avoids the need for a redundant fetch_all_sources() call (~15s).
    # The bridge function in main.py will use these instead.
    _l1_ndvi_records = []
    _l1_sh_indices = {}
    if artifact.layer_1 and artifact.layer_1.output:
        tensor = artifact.layer_1.output
        # 1. Build ndvi_records from L0 daily_state (Kalman filtered)
        if hasattr(tensor, 'daily_state') and tensor.daily_state:
            for zone_id, states in tensor.daily_state.items():
                if not isinstance(states, list):
                    continue
                for st in states:
                    if isinstance(st, dict) and st.get("ndvi_mean") is not None:
                        _l1_ndvi_records.append({
                            "date": st.get("date", ""),
                            "ndvi": st["ndvi_mean"],
                            "confidence": st.get("confidence", 0.7),
                            "source": "kalman",
                        })
        # Fallback: use plot_timeseries if daily_state is empty
        if not _l1_ndvi_records and hasattr(tensor, 'plot_timeseries') and tensor.plot_timeseries:
            for rec in tensor.plot_timeseries:
                if isinstance(rec, dict):
                    ndvi_val = rec.get("ndvi_smoothed") or rec.get("ndvi_mean")
                    if ndvi_val is not None:
                        _l1_ndvi_records.append({
                            "date": rec.get("date", ""),
                            "ndvi": float(ndvi_val),
                            "confidence": 0.85 if rec.get("is_observed") else 0.5,
                            "source": "sentinel-2" if rec.get("is_observed") else "kalman",
                        })
        # 2. Extract latest observed NDVI as SH index proxy
        if hasattr(tensor, 'plot_timeseries') and tensor.plot_timeseries:
            for rec in reversed(tensor.plot_timeseries):
                if isinstance(rec, dict) and rec.get("is_observed") and rec.get("ndvi_mean") is not None:
                    _l1_sh_indices["ndvi"] = float(rec["ndvi_mean"])
                    _l1_sh_indices["date"] = rec.get("date", "")
                    _l1_sh_indices["source"] = "sentinel-2-l2a"
                    break

    run["_l1_kalman_ndvi"] = _l1_ndvi_records
    run["_l1_sh_indices"] = _l1_sh_indices

    _t_total = _time.perf_counter()
    run["request_performance_ms"] = {
        "orchestrator_l1_l10": round((_t_orch - _t0) * 1000.0, 3),
        "payload_assembly": round((_t_total - _t_orch) * 1000.0, 3),
        "surfaces_mode_total": round((_t_total - _t0) * 1000.0, 3),
    }
    print(f"[PERF] run_surfaces_mode: TOTAL = {_t_total - _t0:.2f}s")

    return _attach_snapshot_identity(run, inputs, artifact)


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
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    GEMINI_KEY = os.getenv("GEMINI_API_KEY")
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"

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

    if use_local:
        try:
            from layer9_interface.engines.local_vlm import local_vlm_client
            backend = local_vlm_client.detect_backend()
            if backend:
                res = local_vlm_client.query(query, system_prompt=sys_prompt)
                if res and "answer" in res:
                    if "direct_answer" in res:
                        arf_dict = res
                        arf_dict.pop("engine", None)
                        return arf_dict
                    else:
                        from orchestrator_v2.arf_schema import ARFResponse, LearningModule
                        return ARFResponse(
                            headline="General Agronomy Concept",
                            direct_answer=res.get("answer", ""),
                            suitability_score="N/A",
                            confidence_badge="HIGH",
                            confidence_reason="Local VLM inference",
                            what_it_means="Conceptual knowledge",
                            reasoning_cards=[],
                            recommendations=[],
                            learning=LearningModule(
                                level=exp_level,
                                micro_lesson=res.get("answer", ""),
                                definitions={}
                            ),
                            followups=[],
                            internal_memory_updates=None
                        ).dict()
        except Exception as e:
            print(f"[LLM] Local VLM query failed inside _general_arf: {e}")

    if use_local:
        return {
            "headline": "Local VLM Offline",
            "direct_answer": "The local VLM is currently offline or busy. I cannot process this general agronomy question right now.",
            "suitability_score": "N/A",
            "confidence_badge": "LOW",
            "confidence_reason": "Local inference unavailable",
            "what_it_means": "My offline models are loaded but the query engine is not responding.",
            "reasoning_cards": [],
            "recommendations": [],
            "learning": {
                "level": exp_level,
                "micro_lesson": "Please check if the local llama-server or Ollama is running and properly listening on port 8080 or 11434.",
                "definitions": {}
            },
            "followups": [],
            "internal_memory_updates": None
        }

    if not API_KEY and not GROQ_KEY and not GEMINI_KEY:
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
    try:
        rj_run = {}
        choices_run = None
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        
        try:
            if GROQ_API_KEY and not use_local:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
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
                    print(f"[LLM] Groq returned {resp.status_code}")
        except Exception as e:
            print(f"[LLM] Groq network error: {e}")

        if not choices_run and API_KEY and not use_local:
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

        if not choices_run and os.environ.get("GEMINI_API_KEY") and not use_local:
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
