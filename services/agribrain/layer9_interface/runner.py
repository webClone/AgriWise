"""
Layer 9 Interface Runner v9.6.1 -- 15-Engine Pipeline
=====================================================

Orchestrates the full engine pipeline with intent-based dispatch.
Preserves run_layer9() function signature for backward compatibility.
"""
import time, logging
from typing import Any, Optional, Dict, List
from dataclasses import asdict

from layer9_interface.schema import (
    Layer9Input, InterfaceOutput, PersonaConfig, ExpertiseLevel,
    ConversationTurn, ResponseEnvelope, UserIntent,
    Alert, AlertType, AlertSeverity, TaskBoard,
)

# --- Engine imports ---
from layer9_interface.engines.context_assembly import context_assembly
from layer9_interface.engines.intent_router import intent_router
from layer9_interface.engines.conversation_memory import conversation_memory
from layer9_interface.engines.advisory_engine import advisory_engine
from layer9_interface.engines.qa_engine import qa_engine
from layer9_interface.engines.report_engine import report_engine
from layer9_interface.engines.alert_engine import alert_engine
from layer9_interface.engines.coach_engine import coach_engine
from layer9_interface.engines.spatial_narrator import spatial_narrator
from layer9_interface.engines.task_manager import task_manager
from layer9_interface.engines.data_request import data_request_engine
from layer9_interface.engines.reminder_engine import reminder_engine
from layer9_interface.engines.policy_enforcer import policy_enforcer
from layer9_interface.engines.response_quality import response_quality_engine
from layer9_interface.engines.telemetry_collector import telemetry_collector
from layer9_interface.hallucination_guard import HallucinationGuard
from layer9_interface.engines import INTENT_ENGINE_MAP

logger = logging.getLogger(__name__)


def run_layer9(
    orch_inputs: Any,
    l8_output: Optional[Any] = None,
    l3_output: Optional[Any] = None,
    l6_output: Optional[Any] = None,
    l10_output: Optional[Any] = None,
    l1_conflicts: Optional[List[Dict[str, Any]]] = None,
    l1_output: Optional[Any] = None,
    l2_output: Optional[Any] = None,
    l4_output: Optional[Any] = None,
    l5_output: Optional[Any] = None,
    l7_output: Optional[Any] = None,
) -> InterfaceOutput:
    """
    Run Layer 9 interface rendering -- 15-engine pipeline.

    Signature is BACKWARD COMPATIBLE with the orchestrator.
    """
    t0 = time.time()
    engine_trace: List[str] = []
    latencies: Dict[str, float] = {}

    # ==================================================================
    # 1. Context Assembly Engine
    # ==================================================================
    t1 = time.time()
    l9_input, spatial_explanations = context_assembly.assemble(
        orch_inputs, l8_output, l3_output, l6_output, l10_output, l1_conflicts,
        l1_output, l2_output, l4_output, l5_output, l7_output,
    )
    latencies["context_assembly"] = (time.time() - t1) * 1000
    engine_trace.append("context_assembly")

    # ==================================================================
    # 3. Conversation Memory (Plot-specific persistent context anchoring)
    # ==================================================================
    plot_id = getattr(l9_input, "plot_id", "UNKNOWN")
    if plot_id == "UNKNOWN":
        if l9_input.l2_vegetation_data and isinstance(l9_input.l2_vegetation_data, dict):
            plot_id = l9_input.l2_vegetation_data.get("plot_id", "UNKNOWN")
            
    session = conversation_memory.get_or_create(plot_id=plot_id)
    engine_trace.append("conversation_memory")

    # ==================================================================
    # 2. Intent Router Engine & Contextual Pronoun Resolution
    # ==================================================================
    classification = None
    persona = PersonaConfig()  # default

    if l9_input.user_query:
        # Perform contextual pronoun resolution (anaphora grounding) using conversation memory threads
        resolved_query = conversation_memory.resolve_pronouns(l9_input.user_query, session)
        if resolved_query != l9_input.user_query:
            logger.info(f"Contextual pronoun resolution: '{l9_input.user_query}' -> '{resolved_query}'")
            l9_input.user_query = resolved_query

        t2 = time.time()
        classification = intent_router.classify(l9_input.user_query)
        persona = intent_router.build_persona(classification.detected_expertise)
        
        # Apply calibrated expertise from conversation memory profile if loaded
        if session.persona and session.persona.expertise_level:
            persona.expertise_level = session.persona.expertise_level
            
        # Automate user profile calibration and updates (language, crop variety, active soil zone)
        intent_router.update_user_profile(session, l9_input.user_query, classification)
        
        latencies["intent_router"] = (time.time() - t2) * 1000
        engine_trace.append("intent_router")

    # ==================================================================
    # 4. Policy Enforcer -- build core output (always runs)
    # ==================================================================
    t4 = time.time()
    output = policy_enforcer.build_output(l9_input, spatial_explanations)
    latencies["policy_enforcer"] = (time.time() - t4) * 1000
    engine_trace.append("policy_enforcer")

    # ==================================================================
    # 7. Parallel Background Engines execution (Alert, Task, Data, Reminder)
    # ==================================================================
    t_bg_start = time.time()
    
    def run_with_timing(fn, *args, **kwargs):
        t_start = time.time()
        res = fn(*args, **kwargs)
        duration = (time.time() - t_start) * 1000
        return res, duration

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        f_alert = executor.submit(run_with_timing, alert_engine.generate_alerts, l9_input, persona) if classification else None
        f_task = executor.submit(run_with_timing, task_manager.sync, l9_input, persona)
        f_data = executor.submit(run_with_timing, data_request_engine.scan, l9_input, persona)
        f_reminder = executor.submit(run_with_timing, reminder_engine.check, l9_input, persona, task_manager._task_store)
        
        # Bug 4 Fix: robust exception handling for concurrent futures
        persona_alerts = []
        alert_duration = 0.0
        if f_alert:
            try:
                persona_alerts, alert_duration = f_alert.result()
            except Exception as e:
                logger.error(f"Error in alert_engine.generate_alerts background thread: {e}", exc_info=True)

        task_board = TaskBoard()
        task_duration = 0.0
        try:
            task_board, task_duration = f_task.result()
        except Exception as e:
            logger.error(f"Error in task_manager.sync background thread: {e}", exc_info=True)

        data_requests = []
        data_duration = 0.0
        try:
            data_requests, data_duration = f_data.result()
        except Exception as e:
            logger.error(f"Error in data_request_engine.scan background thread: {e}", exc_info=True)

        reminders = []
        reminder_duration = 0.0
        try:
            reminders, reminder_duration = f_reminder.result()
        except Exception as e:
            logger.error(f"Error in reminder_engine.check background thread: {e}", exc_info=True)

    bg_ms = (time.time() - t_bg_start) * 1000
    latencies["background_parallel_engines"] = bg_ms
    
    # Assign concurrent engine outputs
    output.task_board = task_board
    output.data_requests = data_requests
    output.reminders = reminders
    
    # Attach background results to l9_input so they can be injected into QA/advisory engine contexts
    l9_input.task_board = task_board
    l9_input.data_requests = data_requests
    l9_input.reminders = reminders
    
    # Map and append persona_alerts to output.alerts (Bug 2 Fix)
    for a in persona_alerts:
        if isinstance(a, dict):
            ev_id = a.get("trigger_evidence_id") or a.get("evidence_id") or ""
            alert_obj = Alert(
                alert_type=AlertType(a.get("alert_type", AlertType.SYSTEM)),
                severity=AlertSeverity(a.get("severity", AlertSeverity.INFO)),
                message=a.get("message", ""),
                trigger_evidence_id=ev_id,
                action_required=(a.get("severity") == "CRITICAL")
            )
            output.alerts.append(alert_obj)
        elif isinstance(a, Alert):
            output.alerts.append(a)

    # Call policy_enforcer.enforce_invariants and append gate violations to alerts (Bug 3 Fix)
    try:
        violations = policy_enforcer.enforce_invariants(l9_input)
        for v in violations:
            gate = v.get("gate", "policy_compliance")
            sev = v.get("severity", "MEDIUM")
            detail = v.get("detail", "Safety policy violation detected.")
            alert_sev = AlertSeverity.CRITICAL if sev == "HIGH" else AlertSeverity.WARNING
            output.alerts.append(Alert(
                alert_type=AlertType.SYSTEM,
                severity=alert_sev,
                message=detail,
                trigger_evidence_id=f"policy_{gate}",
                action_required=(alert_sev == AlertSeverity.CRITICAL)
            ))
    except Exception as e:
        logger.error(f"Error enforcing policy invariants: {e}", exc_info=True)
    
    # Maintain exact individual latency telemetry instead of faked division (Gap Fix)
    latencies["alert_engine"] = alert_duration
    latencies["task_manager"] = task_duration
    latencies["data_request"] = data_duration
    latencies["reminder"] = reminder_duration
    
    engine_trace.extend(["alert", "task_manager", "data_request", "reminder"])

    # ==================================================================
    # 6. Intent-based specialized engine dispatch (GAP-4 fix: try-except)
    # ==================================================================
    phrasing = output.phrasing_mode
    engine_payload: Dict[str, Any] = {}

    if classification:
        intent = classification.primary_intent
        t6 = time.time()

        try:
            if intent in (UserIntent.OVERVIEW, UserIntent.DIAGNOSE,
                          UserIntent.ACTION_DETAIL,
                          UserIntent.SCHEDULE):
                engine_payload = advisory_engine.generate(l9_input, persona, phrasing)
                engine_trace.append("advisory")

            elif intent == UserIntent.COMPARE:
                # GAP-2 fix: Route COMPARE to what-if sandbox when scenario context exists
                try:
                    from layer9_interface.engines.what_if_sandbox import what_if_sandbox
                    scenario_ctx = {
                        "sensors": l9_input.l1_fusion_data or {},
                        "plot": l9_input.l2_vegetation_data or {},
                    }
                    sandbox_result = what_if_sandbox.project(
                        l9_input.user_query or "compare scenarios",
                        scenario_ctx,
                    )
                    if sandbox_result and sandbox_result.get("projections"):
                        engine_payload = sandbox_result
                        engine_trace.append("what_if_sandbox")
                    else:
                        engine_payload = advisory_engine.generate(l9_input, persona, phrasing)
                        engine_trace.append("advisory")
                except Exception as e_sandbox:
                    logger.warning(f"What-if sandbox failed, falling back to advisory: {e_sandbox}")
                    engine_payload = advisory_engine.generate(l9_input, persona, phrasing)
                    engine_trace.append("advisory")

            elif intent == UserIntent.REPORT:
                engine_payload = report_engine.generate(l9_input, persona)
                engine_trace.append("report")

            elif intent == UserIntent.SPATIAL:
                engine_payload = spatial_narrator.narrate(l9_input, persona)
                engine_trace.append("spatial_narrator")

            elif intent == UserIntent.COACHING:
                engine_payload = coach_engine.generate_coaching(l9_input, persona)
                engine_trace.append("coach")

            elif intent == UserIntent.TASK_MGMT:
                engine_payload = qa_engine.answer(
                    l9_input.user_query or "", l9_input, persona)
                engine_trace.append("task_manager_intent")

            elif intent == UserIntent.DATA_REQUEST:
                engine_payload = qa_engine.answer(
                    l9_input.user_query or "", l9_input, persona)
                engine_trace.append("data_request_intent")

            elif intent == UserIntent.REMINDER:
                engine_payload = qa_engine.answer(
                    l9_input.user_query or "", l9_input, persona)
                engine_trace.append("reminder_intent")

            elif intent in (UserIntent.GREETING, UserIntent.UNKNOWN):
                engine_payload = qa_engine.answer(
                    l9_input.user_query or "", l9_input, persona)
                engine_trace.append("qa")

        except Exception as e_dispatch:
            # GAP-4 fix: Catch any engine crash and provide graceful degradation
            logger.error(f"Engine dispatch failed for intent {intent}: {e_dispatch}", exc_info=True)
            engine_trace.append("dispatch_error")

            # GAP-12 fix: Graceful fallback using knowledge graph when LLM/engine is offline
            try:
                from layer9_interface.engines.agronomic_knowledge_graph import (
                    get_irrigation_recommendation, get_disease_risk, lookup_crop,
                )
                crop_name = ""
                if l9_input.l2_vegetation_data and isinstance(l9_input.l2_vegetation_data, dict):
                    crop_name = l9_input.l2_vegetation_data.get("crop", "wheat")
                crop_info = lookup_crop(crop_name or "wheat")
                fallback_lines = [f"[AgriBrain — Offline Fallback] Engine temporarily unavailable."]
                if crop_info:
                    fallback_lines.append(f"Crop: {crop_info.crop}, optimal pH: {crop_info.optimal_ph_low}-{crop_info.optimal_ph_high}")
                    fallback_lines.append(f"Stress threshold: {crop_info.stress_threshold}%, Field capacity: {crop_info.field_capacity}%")
                engine_payload = {"answer": "\n".join(fallback_lines), "engine": "knowledge_graph_fallback"}
                engine_trace.append("knowledge_graph_fallback")
            except Exception:
                engine_payload = {"answer": "[AgriBrain] Analysis temporarily unavailable. Please try again.", "engine": "error_fallback"}

        latencies["dispatch"] = (time.time() - t6) * 1000

    # Attach engine payload to output for downstream use
    output.llm_response = str(engine_payload) if engine_payload else ""

    # ==================================================================
    # 5. Hallucination Guard (Bug 1 Fix - relocated post-generation)
    # ==================================================================
    t5 = time.time()
    n_flags = 0
    if output.llm_response:
        guard = HallucinationGuard.from_layer9_input({
            "actions": l9_input.actions,
            "schedule": l9_input.schedule,
            "zone_plan": l9_input.zone_plan,
            "diagnoses": l9_input.diagnoses,
            "outcome_forecast": l9_input.outcome_forecast,
            "l2_vegetation_data": l9_input.l2_vegetation_data,
            "l1_fusion_data": l9_input.l1_fusion_data,
        })
        cleaned_response, flags = guard.validate(output.llm_response)
        output.llm_response = cleaned_response
        n_flags = len(flags)
        if n_flags > 0:
            logger.warning(f"HallucinationGuard flagged {n_flags} claim(s) in LLM response: {flags}")
            
    latencies["hallucination_guard"] = (time.time() - t5) * 1000
    engine_trace.append("hallucination_guard")

    # ==================================================================
    # 10. Response Quality Scoring
    # ==================================================================
    t10 = time.time()
    quality = response_quality_engine.score(l9_input, output, n_flags, persona)
    latencies["response_quality"] = (time.time() - t10) * 1000
    engine_trace.append("response_quality")

    # ==================================================================
    # 11. Telemetry Collection
    # ==================================================================
    t11 = time.time()
    telemetry = telemetry_collector.collect(
        l9_input, classification, quality, latencies,
    )
    latencies["telemetry"] = (time.time() - t11) * 1000
    engine_trace.append("telemetry")

    # Emit telemetry to persistent JSONL file
    telemetry_collector.emit(telemetry, session_id=session.session_id)

    # ==================================================================
    # Record conversation turn
    # ==================================================================
    if l9_input.user_query and classification:
        turn = ConversationTurn(
            user_query=l9_input.user_query,
            resolved_intent=classification.primary_intent,
            engine_used=INTENT_ENGINE_MAP.get(classification.primary_intent, "qa"),
            response_latency_ms=(time.time() - t0) * 1000,
            quality_score=quality.groundedness_score,
            detected_expertise=classification.detected_expertise,
        )
        conversation_memory.record_turn(session, turn, response=output.summary)

        # Analyze turn for feedback learning (Feedback Learning Gap Fix)
        try:
            from layer9_interface.engines.feedback_learning import get_feedback_engine
            feedback_engine = get_feedback_engine()
            hist = []
            for t in session.turns:
                hist.append({"role": "user", "content": t.user_query})
            feedback_engine.analyze_turn(l9_input.user_query, classification.primary_intent.value, output.summary, hist)
            engine_trace.append("feedback_learning")
        except Exception as e:
            logger.warning(f"Feedback learning engine failed: {e}")

    total_ms = (time.time() - t0) * 1000
    logger.info(
        "L9 pipeline: %d engines, %.0fms, quality=%.2f",
        len(engine_trace), total_ms, quality.groundedness_score,
    )

    # Attach metadata for test inspection
    output._engine_trace = engine_trace
    output._engine_payload = engine_payload
    output._classification = classification
    output._quality = quality
    output._telemetry = telemetry
    output._latencies = latencies
    output._resolved_query = l9_input.user_query
    output._l9_input = l9_input

    return output
