"""
Layer 9 Engine Registry v9.6.0
"""
from layer9_interface.schema import UserIntent


# Engine name → module path mapping for trace logging
ENGINE_REGISTRY = {
    "context_assembly": "engines.context_assembly",
    "intent_router": "engines.intent_router",
    "conversation_memory": "engines.conversation_memory",
    "advisory": "engines.advisory_engine",
    "qa": "engines.qa_engine",
    "report": "engines.report_engine",
    "alert": "engines.alert_engine",
    "coach": "engines.coach_engine",
    "spatial_narrator": "engines.spatial_narrator",
    "task_manager": "engines.task_manager",
    "data_request": "engines.data_request",
    "reminder": "engines.reminder_engine",
    "policy_enforcer": "engines.policy_enforcer",
    "response_quality": "engines.response_quality",
    "telemetry": "engines.telemetry_collector",
}

# Intent → engine mapping for routing
INTENT_ENGINE_MAP = {
    UserIntent.OVERVIEW: "advisory",
    UserIntent.DIAGNOSE: "advisory",
    UserIntent.ACTION_DETAIL: "advisory",
    UserIntent.COMPARE: "advisory",
    UserIntent.SCHEDULE: "advisory",
    UserIntent.REPORT: "report",
    UserIntent.SPATIAL: "spatial_narrator",
    UserIntent.COACHING: "coach",
    UserIntent.TASK_MGMT: "task_manager",
    UserIntent.DATA_REQUEST: "data_request",
    UserIntent.REMINDER: "reminder",
    UserIntent.GREETING: "qa",
    UserIntent.UNKNOWN: "qa",
}
