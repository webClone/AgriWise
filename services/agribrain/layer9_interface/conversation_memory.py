"""
conversation_memory.py - Persistent Farmer Conversation Memory
================================================================

Tracks multi-turn conversations with intelligent context carry-over:
  - Farmer profile learning (experience level, preferences, known facts)
  - Topic threading (tracks what's been discussed to avoid repetition)
  - Open loop tracking (unanswered questions, pending actions)
  - Contextual priming (reminds LLM of relevant past discussions)
  - Automatic experience level calibration based on farmer's vocabulary
"""

import os
import json
import time
import re
import hashlib
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class TopicThread:
    """A topic that was discussed in the conversation."""
    topic: str
    first_mentioned: float
    last_mentioned: float
    turn_count: int = 1
    resolved: bool = False
    summary: str = ""


@dataclass
class OpenLoop:
    """An unresolved action or question."""
    id: str
    description: str
    created_at: float
    category: str  # "action", "question", "follow_up"
    resolved: bool = False
    resolved_at: Optional[float] = None


@dataclass
class FarmerProfile:
    """Learned farmer profile from conversation patterns."""
    experience_level: str = "INTERMEDIATE"  # BEGINNER, INTERMEDIATE, EXPERT
    preferred_language: str = "en"
    known_facts: Dict[str, str] = field(default_factory=dict)
    interests: List[str] = field(default_factory=list)
    vocabulary_complexity: float = 0.5  # 0.0 = simple, 1.0 = expert
    total_interactions: int = 0
    first_interaction: Optional[float] = None
    last_interaction: Optional[float] = None


@dataclass
class ConversationState:
    """Full state of a conversation session."""
    plot_id: str
    session_id: str
    farmer_profile: FarmerProfile = field(default_factory=FarmerProfile)
    topic_threads: List[TopicThread] = field(default_factory=list)
    open_loops: List[OpenLoop] = field(default_factory=list)
    recent_intents: List[str] = field(default_factory=list)
    turn_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)


class ConversationMemoryManager:
    """Manages persistent conversation memory across sessions."""

    MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "..", "data", "conversation_memory")

    # Vocabulary complexity indicators
    EXPERT_VOCAB = {
        "evapotranspiration", "penman", "monteith", "phenology", "vernalization",
        "photoperiod", "canopy", "lai", "backscatter", "spectral", "ndre",
        "stomatal", "transpiration", "osmotic", "cation", "anion", "chelate",
        "mycorrhiza", "rhizosphere", "auxin", "cytokinin", "abscisic",
        "pathogenesis", "sporulation", "virulence", "epidemiology",
        "radiometric", "multispectral", "hyperspectral", "lidar"
    }

    BEGINNER_INDICATORS = {
        "what is", "explain", "what does", "meaning of", "help me understand",
        "simple", "basic", "beginner", "new to", "first time"
    }

    def __init__(self):
        os.makedirs(self.MEMORY_DIR, exist_ok=True)

    def _state_path(self, plot_id: str) -> str:
        safe_id = re.sub(r'[^\w\-]', '_', plot_id)
        return os.path.join(self.MEMORY_DIR, f"{safe_id}_memory.json")

    def load_state(self, plot_id: str) -> ConversationState:
        """Load conversation state from disk."""
        path = self._state_path(plot_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                state = ConversationState(
                    plot_id=plot_id,
                    session_id=data.get("session_id", ""),
                    turn_count=data.get("turn_count", 0),
                    recent_intents=data.get("recent_intents", []),
                    created_at=data.get("created_at", time.time()),
                    last_updated=data.get("last_updated", time.time()),
                )
                # Reconstruct farmer profile
                fp = data.get("farmer_profile", {})
                state.farmer_profile = FarmerProfile(
                    experience_level=fp.get("experience_level", "INTERMEDIATE"),
                    preferred_language=fp.get("preferred_language", "en"),
                    known_facts=fp.get("known_facts", {}),
                    interests=fp.get("interests", []),
                    vocabulary_complexity=fp.get("vocabulary_complexity", 0.5),
                    total_interactions=fp.get("total_interactions", 0),
                    first_interaction=fp.get("first_interaction"),
                    last_interaction=fp.get("last_interaction"),
                )
                # Reconstruct topics
                for t in data.get("topic_threads", []):
                    state.topic_threads.append(TopicThread(**t))
                # Reconstruct open loops
                for ol in data.get("open_loops", []):
                    state.open_loops.append(OpenLoop(**ol))
                return state
            except Exception:
                pass
        return ConversationState(plot_id=plot_id, session_id=hashlib.md5(
            f"{plot_id}_{time.time()}".encode()).hexdigest()[:12])

    def save_state(self, state: ConversationState):
        """Persist conversation state to disk."""
        path = self._state_path(state.plot_id)
        state.last_updated = time.time()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(asdict(state), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def update_on_query(self, state: ConversationState, query: str,
                        intent: str, response: str) -> ConversationState:
        """Update conversation state after a query-response turn."""
        now = time.time()
        state.turn_count += 1
        state.recent_intents.append(intent)
        state.recent_intents = state.recent_intents[-10:]  # Keep last 10

        # Update farmer profile
        fp = state.farmer_profile
        fp.total_interactions += 1
        fp.last_interaction = now
        if fp.first_interaction is None:
            fp.first_interaction = now

        # Calibrate experience level from vocabulary
        self._calibrate_experience(fp, query)

        # Extract new facts from conversation
        self._extract_facts(fp, query, response)

        # Update topic threads
        self._update_topics(state, query, intent)

        # Detect and track open loops
        self._detect_open_loops(state, query, response, intent)

        self.save_state(state)
        return state

    def _calibrate_experience(self, profile: FarmerProfile, query: str):
        """Auto-calibrate farmer experience from their vocabulary."""
        ql = query.lower()
        words = set(re.findall(r'\b\w+\b', ql))

        expert_hits = len(words & self.EXPERT_VOCAB)
        beginner_hits = sum(1 for b in self.BEGINNER_INDICATORS if b in ql)

        if expert_hits >= 2:
            profile.vocabulary_complexity = min(1.0, profile.vocabulary_complexity + 0.1)
            if profile.vocabulary_complexity > 0.75:
                profile.experience_level = "EXPERT"
        elif beginner_hits >= 1:
            profile.vocabulary_complexity = max(0.0, profile.vocabulary_complexity - 0.05)
            if profile.vocabulary_complexity < 0.3:
                profile.experience_level = "BEGINNER"

    def _extract_facts(self, profile: FarmerProfile, query: str, response: str):
        """Extract known facts from farmer statements."""
        ql = query.lower()

        patterns = {
            "irrigation_type": r"(?:i use|we use|using|have)\s+(drip|flood|sprinkler|pivot)\s+irrigation",
            "crop_variety": r"(?:growing|planted|using)\s+([\w\-\s]+?)\s+(?:variety|cultivar|type)",
            "field_size": r"(\d+(?:\.\d+)?)\s*(?:hectares?|ha)\b",
            "soil_texture": r"(?:soil is|have)\s+(clay|sandy|loam|silt)",
        }
        for fact_key, pattern in patterns.items():
            match = re.search(pattern, ql)
            if match:
                profile.known_facts[fact_key] = match.group(1)

    def _update_topics(self, state: ConversationState, query: str, intent: str):
        """Track which topics have been discussed."""
        now = time.time()
        topic_name = f"{intent}_{self._extract_topic(query)}"

        found = False
        for t in state.topic_threads:
            if t.topic == topic_name:
                t.last_mentioned = now
                t.turn_count += 1
                found = True
                break

        if not found:
            state.topic_threads.append(TopicThread(
                topic=topic_name,
                first_mentioned=now,
                last_mentioned=now,
            ))

        # Keep only last 20 topics
        state.topic_threads = state.topic_threads[-20:]

    def _extract_topic(self, query: str) -> str:
        """Extract a short topic label from a query."""
        ql = query.lower()
        topic_keywords = {
            "irrigation": "water", "rain": "weather", "ndvi": "vegetation",
            "disease": "disease", "fungal": "disease", "pest": "pest",
            "nitrogen": "nutrient", "fertilizer": "nutrient",
            "soil": "soil", "temperature": "weather", "harvest": "planning",
            "plant": "planning", "spray": "protection",
        }
        for keyword, topic in topic_keywords.items():
            if keyword in ql:
                return topic
        return "general"

    def _detect_open_loops(self, state: ConversationState, query: str,
                           response: str, intent: str):
        """Detect unanswered questions or pending actions."""
        ql = query.lower()

        # Check if farmer is confirming a past recommendation
        confirm_patterns = ["i did", "done", "applied", "sprayed", "irrigated",
                           "yes i", "finished", "completed"]
        if any(c in ql for c in confirm_patterns):
            # Close matching open loops
            for ol in state.open_loops:
                if not ol.resolved and ol.category == "action":
                    ol.resolved = True
                    ol.resolved_at = time.time()

        # Detect new actions in the response
        action_patterns = ["should", "recommend", "apply", "schedule",
                          "consider", "check back"]
        rl = response.lower()
        if any(a in rl for a in action_patterns) and intent in ("DECISION", "NUTRIENT"):
            loop_id = hashlib.md5(f"{query}_{time.time()}".encode()).hexdigest()[:8]
            state.open_loops.append(OpenLoop(
                id=loop_id,
                description=query[:100],
                created_at=time.time(),
                category="action"
            ))

        # Keep only last 10 open loops
        state.open_loops = state.open_loops[-10:]

    def resolve_pronouns(self, query: str, state: ConversationState) -> str:
        """Resolve pronouns (anaphora grounding) like 'it', 'they', 'this', 'there' in the query using active thread context."""
        q_resolved = query.strip()
        q_lower = q_resolved.lower()
        
        # 1. Identify if pronouns are present
        pronoun_patterns = [r"\bit\b", r"\bthem\b", r"\bthey\b", r"\bthere\b", r"\bthis\b", r"\bthat\b"]
        has_pronoun = any(re.search(pat, q_lower) for pat in pronoun_patterns)
        if not has_pronoun:
            return q_resolved
            
        # 2. Extract active topic entity from memory threads
        active_crop = ""
        active_topic = ""
        active_zone = ""
        
        # Scan topic threads for keywords
        for t in reversed(state.topic_threads):
            topic_lbl = t.topic.lower()
            if "water" in topic_lbl or "irrigation" in topic_lbl:
                active_topic = "irrigation"
            elif "disease" in topic_lbl or "fungal" in topic_lbl or "pest" in topic_lbl:
                active_topic = "pest protection"
            elif "nutrient" in topic_lbl or "fertilizer" in topic_lbl:
                active_topic = "fertilizer application"
                
        # Scan known facts or profiles for active focus
        fp = state.farmer_profile
        if "crop_variety" in fp.known_facts:
            active_crop = fp.known_facts["crop_variety"]
        elif "soil_texture" in fp.known_facts:
            active_zone = f"the {fp.known_facts['soil_texture']} zone"
            
        # 3. Ground the pronouns based on the resolved context
        # "it" -> active crop or topic
        if re.search(r"\bit\b", q_lower):
            replacement = active_crop if active_crop else "the crop"
            q_resolved = re.sub(r"\bit\b", replacement, q_resolved, flags=re.IGNORECASE)
            
        # "there" / "this zone" -> active zone (existential lookbehind check)
        # Avoid replacing "there" in "Is there..." or "Are there..."
        if re.search(r"\bthere\b", q_lower):
            replacement = active_zone if active_zone else "in the active zone"
            q_resolved = re.sub(r"(?<!is\s)(?<!are\s)(?<!was\s)(?<!were\s)\bthere\b", replacement, q_resolved, flags=re.IGNORECASE)
            
        # "they" / "them" -> active topics
        if re.search(r"\bthey\b", q_lower) or re.search(r"\bthem\b", q_lower):
            replacement = active_topic if active_topic else "the recommendations"
            q_resolved = re.sub(r"\bthey\b", replacement, q_resolved, flags=re.IGNORECASE)
            q_resolved = re.sub(r"\bthem\b", replacement, q_resolved, flags=re.IGNORECASE)
            
        return q_resolved

    def build_context_primer(self, state: ConversationState) -> str:
        """Build a context primer string for the LLM system prompt."""
        parts = []

        fp = state.farmer_profile
        parts.append(f"[FARMER PROFILE]")
        parts.append(f"Experience: {fp.experience_level}")
        parts.append(f"Total interactions: {fp.total_interactions}")
        if fp.known_facts:
            facts = ", ".join(f"{k}: {v}" for k, v in fp.known_facts.items())
            parts.append(f"Known facts: {facts}")

        # Recent topics (avoid repetition)
        recent = [t.topic for t in state.topic_threads[-5:]]
        if recent:
            parts.append(f"Recent topics discussed: {', '.join(recent)}")

        # Open loops
        unresolved = [ol for ol in state.open_loops if not ol.resolved]
        if unresolved:
            parts.append(f"Pending actions ({len(unresolved)}):")
            for ol in unresolved[:3]:
                parts.append(f"  - {ol.description}")

        # Recent intents
        if state.recent_intents:
            parts.append(f"Recent question types: {', '.join(state.recent_intents[-5:])}")

        return "\n".join(parts)

    @staticmethod
    def format_farmer_profile(memory: Optional[Dict] = None) -> str:
        """Format farmer profile for the system prompt (backward compatible)."""
        if not memory:
            return "[FARMER PROFILE] No profile data available."

        parts = ["[FARMER PROFILE]"]
        if isinstance(memory, dict):
            exp = memory.get("experience_level", "INTERMEDIATE")
            parts.append(f"Experience Level: {exp}")
            known = memory.get("known_context", {})
            if known:
                for k, v in known.items():
                    if v:
                        parts.append(f"  {k}: {v}")
            loops = memory.get("open_loops", [])
            if loops:
                parts.append(f"Pending actions: {len(loops)}")
        return "\n".join(parts)


# Singleton
_manager = None

def get_memory_manager() -> ConversationMemoryManager:
    global _manager
    if _manager is None:
        _manager = ConversationMemoryManager()
    return _manager
