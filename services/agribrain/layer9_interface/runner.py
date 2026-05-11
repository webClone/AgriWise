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
    )
    latencies["context_assembly"] = (time.time() - t1) * 1000
    engine_trace.append("context_assembly")

    # ==================================================================
    # 2. Intent Router Engine (if user query present)
    # ==================================================================
    classification = None
    persona = PersonaConfig()  # default

    if l9_input.user_query:
        t2 = time.time()
        classification = intent_router.classify(l9_input.user_query)
        persona = intent_router.build_persona(classification.detected_expertise)
        latencies["intent_router"] = (time.time() - t2) * 1000
        engine_trace.append("intent_router")

    # ==================================================================
    # 3. Conversation Memory
    # ==================================================================
    session = conversation_memory.get_or_create()
    engine_trace.append("conversation_memory")

    # ==================================================================
    # 4. Policy Enforcer -- build core output (always runs)
    # ==================================================================
    t4 = time.time()
    output = policy_enforcer.build_output(l9_input, spatial_explanations)
    latencies["policy_enforcer"] = (time.time() - t4) * 1000
    engine_trace.append("policy_enforcer")

    # ==================================================================
    # 5. Hallucination Guard
    # ==================================================================
    t5 = time.time()
    guard = HallucinationGuard.from_layer9_input({
        "actions": l9_input.actions,
        "schedule": l9_input.schedule,
        "zone_plan": l9_input.zone_plan,
        "diagnoses": l9_input.diagnoses,
        "outcome_forecast": l9_input.outcome_forecast,
    })
    _, flags = guard.validate(output.summary)
    n_flags = len(flags)
    latencies["hallucination_guard"] = (time.time() - t5) * 1000
    engine_trace.append("hallucination_guard")

    # ==================================================================
    # 6. Intent-based specialized engine dispatch
    # ==================================================================
    phrasing = output.phrasing_mode
    engine_payload: Dict[str, Any] = {}

    if classification:
        intent = classification.primary_intent
        t6 = time.time()

        if intent in (UserIntent.OVERVIEW, UserIntent.DIAGNOSE,
                      UserIntent.ACTION_DETAIL, UserIntent.COMPARE,
                      UserIntent.SCHEDULE):
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
            # task_manager runs below for everyone, but we mark intent
            engine_trace.append("task_manager_intent")

        elif intent == UserIntent.DATA_REQUEST:
            engine_trace.append("data_request_intent")

        elif intent == UserIntent.REMINDER:
            engine_trace.append("reminder_intent")

        elif intent in (UserIntent.GREETING, UserIntent.UNKNOWN):
            engine_payload = qa_engine.answer(
                l9_input.user_query or "", l9_input, persona)
            engine_trace.append("qa")

        latencies["dispatch"] = (time.time() - t6) * 1000

        # Also run alert engine when there's a query
        t_alert = time.time()
        persona_alerts = alert_engine.generate_alerts(l9_input, persona)
        latencies["alert_engine"] = (time.time() - t_alert) * 1000
        engine_trace.append("alert")

    # Attach engine payload to output for downstream use
    output.llm_response = str(engine_payload) if engine_payload else ""

    # ==================================================================
    # 7. Task Manager Sync (background -- every invocation)
    # ==================================================================
    t7 = time.time()
    task_board = task_manager.sync(l9_input, persona)
    output.task_board = task_board
    latencies["task_manager"] = (time.time() - t7) * 1000
    engine_trace.append("task_manager")

    # ==================================================================
    # 8. Data Request Scan (background -- every invocation)
    # ==================================================================
    t8 = time.time()
    data_requests = data_request_engine.scan(l9_input, persona)
    output.data_requests = data_requests
    latencies["data_request"] = (time.time() - t8) * 1000
    engine_trace.append("data_request")

    # ==================================================================
    # 9. Reminder Check (background -- every invocation)
    # ==================================================================
    t9 = time.time()
    reminders = reminder_engine.check(
        l9_input, persona, task_store=task_manager._task_store,
    )
    output.reminders = reminders
    latencies["reminder"] = (time.time() - t9) * 1000
    engine_trace.append("reminder")

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
        conversation_memory.record_turn(session, turn)

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

    return output
