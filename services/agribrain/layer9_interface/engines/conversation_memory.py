"""
Engine 3: Conversation Memory v9.6.0

Lightweight session tracking with sliding window of recent turns.
Thread-safe, no external DB dependency.
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
    """In-memory session context tracker with thread-safe access."""

    def __init__(self):
        self._sessions = {}  # session_id -> SessionContext
        self._lock = threading.Lock()

    def get_or_create(self, session_id: Optional[str] = None) -> SessionContext:
        with self._lock:
            if not session_id:
                session_id = uuid.uuid4().hex[:12]
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext(
                    session_id=session_id,
                    persona=PersonaConfig(),
                )
            return self._sessions[session_id]

    def record_turn(self, session: SessionContext, turn: ConversationTurn):
        with self._lock:
            session.turns.append(turn)
            if len(session.turns) > _MAX_TURNS:
                session.turns = session.turns[-_MAX_TURNS:]

    def get_active_context(self, session: SessionContext) -> dict:
        """Return recent context for follow-up query resolution."""
        with self._lock:
            recent = session.turns[-5:] if session.turns else []
            return {
                "recent_intents": [t.resolved_intent.value for t in recent],
                "recent_engines": [t.engine_used for t in recent],
                "active_crop": session.active_crop,
                "active_zone": session.active_zone,
                "turn_count": len(session.turns),
            }


conversation_memory = ConversationMemoryEngine()
