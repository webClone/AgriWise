"""
Engine 3: Conversation Memory v9.6.0

Lightweight session tracking with sliding window of recent turns.
Thread-safe, no external DB dependency.
Bridges with persistent ConversationMemoryManager.
"""
import uuid, logging, threading
from typing import Optional

from layer9_interface.schema import (
    SessionContext, ConversationTurn, PersonaConfig,
    UserIntent, ExpertiseLevel,
)

logger = logging.getLogger(__name__)

_MAX_TURNS = 20


class ConversationMemoryEngine:
    """In-memory session context tracker with thread-safe access and persistent plot anchoring."""

    def __init__(self):
        self._sessions = {}  # session_id -> SessionContext
        self._lock = threading.Lock()

    def get_or_create(self, session_id: Optional[str] = None, plot_id: Optional[str] = None) -> SessionContext:
        """Retrieve or initialize a SessionContext, optionally loading persistent plot memory."""
        with self._lock:
            # If session_id is missing, see if we have an active session for the plot
            if not session_id and plot_id and plot_id != "UNKNOWN":
                for s_id, s_ctx in self._sessions.items():
                    if getattr(s_ctx, "plot_id", None) == plot_id:
                        session_id = s_id
                        break

            if not session_id:
                session_id = uuid.uuid4().hex[:12]

            if session_id not in self._sessions:
                session = SessionContext(
                    session_id=session_id,
                    persona=PersonaConfig(),
                    plot_id=plot_id or "UNKNOWN"
                )

                # Bridge to persistent plot state
                if plot_id and plot_id != "UNKNOWN":
                    try:
                        from layer9_interface.conversation_memory import get_memory_manager
                        manager = get_memory_manager()
                        state = manager.load_state(plot_id)

                        # Sync persistent profile information to active context
                        session.active_crop = state.farmer_profile.known_facts.get("crop_variety", "")
                        session.active_zone = state.farmer_profile.known_facts.get("soil_texture", "")

                        # Calibrate expertise based on persistent profile learning
                        exp_map = {
                            "BEGINNER": ExpertiseLevel.NOVICE,
                            "INTERMEDIATE": ExpertiseLevel.FARMER,
                            "EXPERT": ExpertiseLevel.AGRONOMIST,
                        }
                        session.persona.expertise_level = exp_map.get(
                            state.farmer_profile.experience_level, ExpertiseLevel.FARMER
                        )
                        logger.info(f"Loaded persistent conversation memory for plot: {plot_id} (Expertise: {session.persona.expertise_level})")
                    except Exception as e:
                        logger.warning(f"Could not load persistent state for plot {plot_id}: {e}")

                self._sessions[session_id] = session

            return self._sessions[session_id]

    def record_turn(self, session: SessionContext, turn: ConversationTurn, response: str = ""):
        """Record the conversation turn in-memory and write to persistent storage."""
        with self._lock:
            session.turns.append(turn)
            if len(session.turns) > _MAX_TURNS:
                session.turns = session.turns[-_MAX_TURNS:]

            # Sync active context details
            if session.active_crop and not turn.detected_expertise == ExpertiseLevel.NOVICE:
                pass # keep it

            # Persist the conversation turn per plot
            plot_id = getattr(session, "plot_id", "UNKNOWN")
            if plot_id and plot_id != "UNKNOWN":
                try:
                    from layer9_interface.conversation_memory import get_memory_manager
                    manager = get_memory_manager()
                    state = manager.load_state(plot_id)

                    intent_str = turn.resolved_intent.value if hasattr(turn.resolved_intent, "value") else str(turn.resolved_intent)
                    manager.update_on_query(state, turn.user_query, intent_str, response)

                    # Update context from potential newly learned facts
                    session.active_crop = state.farmer_profile.known_facts.get("crop_variety", session.active_crop)
                    session.active_zone = state.farmer_profile.known_facts.get("soil_texture", session.active_zone)
                    logger.info(f"Persisted turn for plot: {plot_id}")
                except Exception as e:
                    logger.warning(f"Could not persist conversation turn for plot {plot_id}: {e}")

    def resolve_pronouns(self, query: str, session: SessionContext) -> str:
        """Resolve pronouns using active thread entities and persistent history."""
        plot_id = getattr(session, "plot_id", "UNKNOWN")
        if plot_id and plot_id != "UNKNOWN":
            try:
                from layer9_interface.conversation_memory import get_memory_manager
                manager = get_memory_manager()
                state = manager.load_state(plot_id)

                # Temporarily seed session overrides if present
                if session.active_crop:
                    state.farmer_profile.known_facts["crop_variety"] = session.active_crop
                if session.active_zone:
                    state.farmer_profile.known_facts["soil_texture"] = session.active_zone

                return manager.resolve_pronouns(query, state)
            except Exception as e:
                logger.warning(f"Failed to resolve pronouns via manager for plot {plot_id}: {e}")
        return query

    def get_active_context(self, session: SessionContext) -> dict:
        """Return recent context for follow-up query resolution."""
        with self._lock:
            recent = session.turns[-5:] if session.turns else []
            return {
                "recent_intents": [t.resolved_intent.value if hasattr(t.resolved_intent, "value") else str(t.resolved_intent) for t in recent],
                "recent_engines": [t.engine_used for t in recent],
                "active_crop": session.active_crop,
                "active_zone": session.active_zone,
                "turn_count": len(session.turns),
            }


conversation_memory = ConversationMemoryEngine()
