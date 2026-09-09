"""
Unit tests for Layer 9 Intent Router and Conversation Memory.
"""
import pytest
from layer9_interface.schema import (
    UserIntent, ExpertiseLevel, ConversationTurn, SessionContext,
)
from layer9_interface.engines.intent_router import intent_router
from layer9_interface.engines.conversation_memory import conversation_memory


def test_intent_router_intent_classification():
    """Verify that intent_router correctly classifies various agronomic queries."""
    cases = [
        ("Hello, good morning! How are you?", UserIntent.GREETING),
        ("Give me an overview of the field status and health", UserIntent.OVERVIEW),
        ("What is wrong with the crop? Any yellow blight or disease symptoms?", UserIntent.DIAGNOSE),
        ("What should I spray on the wheat and what is the recommended dose?", UserIntent.ACTION_DETAIL),
        ("Compare drip irrigation versus pivot between zone north and south", UserIntent.COMPARE),
        ("When should I irrigate? What is the calendar schedule window?", UserIntent.SCHEDULE),
        ("Please generate an agronomic summary report for export", UserIntent.REPORT),
        ("Show me the spatial zone map and spatial variability", UserIntent.SPATIAL),
        ("Show my pending tasks and todo checklist for today", UserIntent.TASK_MGMT),
        ("I want to upload a new soil photo and sensor sample", UserIntent.DATA_REQUEST),
        ("Remind me before the spray window closes", UserIntent.REMINDER),
    ]

    for query, expected_intent in cases:
        res = intent_router.classify(query)
        assert res.primary_intent == expected_intent, f"Query '{query}' classified as {res.primary_intent}, expected {expected_intent}"
        assert 0.0 <= res.confidence <= 1.0


def test_intent_router_expertise_detection():
    """Verify linguistic detection of user expertise levels."""
    cases = [
        ("I am a beginner, my plants look sick, please give me simple advice", ExpertiseLevel.NOVICE),
        ("How is the field looking today?", ExpertiseLevel.FARMER),
        ("Analyze the NDVI and Sentinel-2 SAR VV/VH threshold for canopy mask", ExpertiseLevel.TECHNICIAN),
        ("Review the BBCH phenology stage and Mitscherlich-Baule nutrient absorption curve", ExpertiseLevel.AGRONOMIST),
        ("Evaluate the Bayesian posterior confidence interval and Penman-Monteith regression R^2", ExpertiseLevel.RESEARCHER),
    ]

    for query, expected_exp in cases:
        res = intent_router.classify(query)
        assert res.detected_expertise == expected_exp, f"Query '{query}' detected as {res.detected_expertise}, expected {expected_exp}"


def test_conversation_memory_session_and_turns():
    """Verify session creation, turn recording, and pronoun resolution."""
    plot_id = "plot_test_901"
    session = conversation_memory.get_or_create(plot_id=plot_id)
    assert session is not None
    assert session.plot_id == plot_id

    # Record turns
    turn1 = ConversationTurn(
        turn_id="turn_1",
        user_query="How is the wheat doing?",
        resolved_intent=UserIntent.OVERVIEW,
        engine_used="advisory",
        response_latency_ms=120.0,
        quality_score=0.95,
        detected_expertise=ExpertiseLevel.FARMER,
    )
    conversation_memory.record_turn(session, turn1, response="The wheat crop is at vegetative stage with 32% soil moisture.")
    assert len(session.turns) >= 1

    # Check pronoun resolution
    session.active_crop = "wheat"
    query_with_pronoun = "How much water does it need?"
    resolved = conversation_memory.resolve_pronouns(query_with_pronoun, session)
    assert isinstance(resolved, str)
    assert len(resolved) > 0
