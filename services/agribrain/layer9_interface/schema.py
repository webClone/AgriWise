"""
Layer 9 Schema: UI/LLM Intelligence — Structured Output Contract v9.6.0

Layer 9 is a 15-engine intelligence orchestration surface.
It is a deterministic renderer + policy enforcer with adaptive persona.
It must NEVER invent rates, dates, zones, diagnoses, or economics.

Output:
  - InterfaceOutput: summary, zone_cards, alerts, explanations,
    disclaimers, citations, render_hints
  - All content comes from upstream layers (L3-L8, L10)
  - Operational outputs: tasks, data_requests, reminders
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import time
import uuid


# ============================================================================
# Core Enums (preserved from v9.0)
# ============================================================================

class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    DATA_QUALITY = "DATA_QUALITY"
    WEATHER = "WEATHER"
    DISEASE = "DISEASE"
    NUTRITION = "NUTRITION"
    WATER = "WATER"
    SYSTEM = "SYSTEM"


class BadgeColor(str, Enum):
    GREEN = "GREEN"      # grade A/B, healthy
    YELLOW = "YELLOW"    # grade C, moderate
    RED = "RED"          # grade D/F, critical
    GRAY = "GRAY"        # insufficient data


class PhrasingMode(str, Enum):
    CONFIDENT = "CONFIDENT"      # grade A/B
    HEDGED = "HEDGED"            # grade C
    RESTRICTED = "RESTRICTED"    # grade D/F


# ============================================================================
# New Enums (v9.6)
# ============================================================================

class ExpertiseLevel(str, Enum):
    """Drives adaptive tone across all engines."""
    NOVICE = "NOVICE"           # warm, emoji-friendly, metaphor-heavy
    FARMER = "FARMER"           # practical, direct, local terms
    TECHNICIAN = "TECHNICIAN"   # professional, precise, reasoning chains
    AGRONOMIST = "AGRONOMIST"   # peer-to-peer, data-rich, scientific
    RESEARCHER = "RESEARCHER"   # academic, citation-heavy, raw data


class UserIntent(str, Enum):
    """Intent taxonomy for the ML-ready router."""
    OVERVIEW = "OVERVIEW"
    DIAGNOSE = "DIAGNOSE"
    ACTION_DETAIL = "ACTION_DETAIL"
    COMPARE = "COMPARE"
    SCHEDULE = "SCHEDULE"
    REPORT = "REPORT"
    SPATIAL = "SPATIAL"
    COACHING = "COACHING"
    TASK_MGMT = "TASK_MGMT"
    DATA_REQUEST = "DATA_REQUEST"
    REMINDER = "REMINDER"
    GREETING = "GREETING"
    UNKNOWN = "UNKNOWN"


class TaskStatus(str, Enum):
    """Field task lifecycle status."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    SKIPPED = "SKIPPED"


class DataRequestType(str, Enum):
    """Types of data the system can request from the farmer."""
    SOIL_PHOTO = "SOIL_PHOTO"
    PEST_PHOTO = "PEST_PHOTO"
    SENSOR_READING = "SENSOR_READING"
    WEATHER_OBS = "WEATHER_OBS"
    YIELD_ESTIMATE = "YIELD_ESTIMATE"


class ReminderTrigger(str, Enum):
    """What triggers a reminder to fire."""
    TIME = "TIME"
    WEATHER_WINDOW = "WEATHER_WINDOW"
    PHENOLOGY_STAGE = "PHENOLOGY_STAGE"
    DATA_STALENESS = "DATA_STALENESS"
    TASK_OVERDUE = "TASK_OVERDUE"


class AlertChannel(str, Enum):
    """Delivery channel for alerts/reminders."""
    PUSH = "PUSH"
    SMS = "SMS"
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"


# ============================================================================
# Core Data Structures (preserved from v9.0)
# ============================================================================

@dataclass
class Alert:
    """Structured alert tied to evidence."""
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    trigger_evidence_id: str        # reference to upstream evidence
    action_required: bool = False


@dataclass
class ZoneCard:
    """Per-zone summary for UI."""
    zone_id: str
    top_action: Optional[str]       # action_type from L8
    confidence_badge: BadgeColor
    key_metrics: Dict[str, Any]     # {ndvi: 0.6, sm: 0.3, risk: "LOW"}
    status_text: str = ""           # one-line summary


@dataclass
class Explanation:
    """Evidence-backed 'because...' statement."""
    statement: str                  # "Because NDVI dropped 15% in 7 days..."
    evidence_id: str                # reference to source
    source_layer: str               # "L3", "L5", etc.
    confidence: float = 1.0


@dataclass
class Citation:
    """Pointer to upstream data source."""
    source_layer: str
    reference_id: str
    timestamp: str = ""
    value: Optional[float] = None
    description: str = ""


@dataclass
class RenderHint:
    """UI directives for the frontend."""
    badge_color: BadgeColor
    show_uncertainty_overlay: bool = False
    show_conflict_icon: bool = False
    highlight_zones: List[str] = field(default_factory=list)


@dataclass
class Disclaimer:
    """Policy-generated disclaimer."""
    text: str
    reason: str                     # "low_audit_grade", "missing_data", "conflict"
    severity: AlertSeverity = AlertSeverity.WARNING


# ============================================================================
# Persona & Conversation (v9.6)
# ============================================================================

@dataclass
class PersonaConfig:
    """Controls adaptive tone across all engines."""
    expertise_level: ExpertiseLevel = ExpertiseLevel.FARMER
    warmth_factor: float = 0.7       # 0=clinical, 1=very warm
    emoji_enabled: bool = True
    use_metaphors: bool = True
    max_explanation_depth: int = 2   # levels of "why" to include
    preferred_units: str = "metric"  # "metric" or "imperial"
    language_code: str = "en"


@dataclass
class ConversationTurn:
    """Tracks one exchange in a session."""
    turn_id: str = ""
    user_query: str = ""
    resolved_intent: UserIntent = UserIntent.UNKNOWN
    engine_used: str = ""
    response_latency_ms: float = 0.0
    quality_score: float = 0.0
    detected_expertise: ExpertiseLevel = ExpertiseLevel.FARMER


@dataclass
class SessionContext:
    """Conversation memory for follow-up resolution."""
    session_id: str = ""
    turns: List[ConversationTurn] = field(default_factory=list)
    field_context_hash: str = ""
    active_crop: str = ""
    active_zone: str = ""
    persona: PersonaConfig = field(default_factory=PersonaConfig)


@dataclass
class IntentClassification:
    """Result of the intent router."""
    primary_intent: UserIntent = UserIntent.UNKNOWN
    confidence: float = 0.0
    fallback_intent: UserIntent = UserIntent.OVERVIEW
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    detected_expertise: ExpertiseLevel = ExpertiseLevel.FARMER


# ============================================================================
# Operational Data Structures (v9.6)
# ============================================================================

@dataclass
class FieldTask:
    """A trackable field task auto-generated from L8 actions."""
    task_id: str = ""
    title: str = ""
    action_type: str = ""
    zone_id: str = ""
    priority: float = 0.0
    status: TaskStatus = TaskStatus.PENDING
    due_date: str = ""
    created_from: str = ""        # L8 action_id
    notes: str = ""

    def __post_init__(self):
        if not self.task_id:
            self.task_id = f"task_{uuid.uuid4().hex[:8]}"


@dataclass
class TaskBoard:
    """Summary view of all field tasks."""
    tasks: List[FieldTask] = field(default_factory=list)
    overdue_count: int = 0
    completed_today: int = 0
    completion_rate_7d: float = 0.0


@dataclass
class DataRequest:
    """A proactive request for data from the farmer."""
    request_id: str = ""
    data_type: DataRequestType = DataRequestType.SOIL_PHOTO
    reason: str = ""
    impact_description: str = ""
    urgency: float = 0.5            # 0=low, 1=critical
    accuracy_gain_estimate: float = 0.0  # expected improvement

    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"dreq_{uuid.uuid4().hex[:8]}"


@dataclass
class Reminder:
    """A time-sensitive smart reminder."""
    reminder_id: str = ""
    title: str = ""
    message: str = ""
    trigger_type: ReminderTrigger = ReminderTrigger.TIME
    trigger_condition: str = ""
    channel: AlertChannel = AlertChannel.IN_APP
    is_recurring: bool = False
    snooze_count: int = 0

    def __post_init__(self):
        if not self.reminder_id:
            self.reminder_id = f"rem_{uuid.uuid4().hex[:8]}"


# ============================================================================
# Quality & Telemetry (v9.6)
# ============================================================================

@dataclass
class ResponseQuality:
    """Scores every response for ML feedback loops."""
    groundedness_score: float = 1.0    # 1.0 - hallucination_rate
    completeness_score: float = 1.0    # fraction of relevant data referenced
    coherence_score: float = 1.0       # template structure compliance
    naturalness_score: float = 1.0     # human-likeness of language
    hallucination_flags: int = 0


@dataclass
class TelemetryVector:
    """ML-ready feature vector from every L9 invocation."""
    intent_distribution: Dict[str, float] = field(default_factory=dict)
    data_quality_features: Dict[str, float] = field(default_factory=dict)
    response_features: Dict[str, float] = field(default_factory=dict)
    expertise_signals: Dict[str, float] = field(default_factory=dict)
    engine_latencies: Dict[str, float] = field(default_factory=dict)
    experiment_id: str = ""
    variant: str = ""


@dataclass
class ResponseEnvelope:
    """Full wrapper around InterfaceOutput with engine metadata."""
    output: Optional[Any] = None          # InterfaceOutput
    intent_classification: Optional[IntentClassification] = None
    engine_trace: List[str] = field(default_factory=list)
    telemetry: Optional[TelemetryVector] = None
    quality: Optional[ResponseQuality] = None
    persona_used: Optional[PersonaConfig] = None
    task_board: Optional[TaskBoard] = None
    data_requests: List[DataRequest] = field(default_factory=list)
    reminders: List[Reminder] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


# ============================================================================
# I/O (preserved from v9.0)
# ============================================================================

@dataclass
class Layer9Input:
    """Strict input from upstream layers."""
    # Structured data only — L9 MUST NOT re-derive anything
    audit_grade: str                        # from L0
    source_reliability: Dict[str, float]    # from L0
    conflicts: List[Dict[str, Any]]         # from L0 validation graph
    
    diagnoses: List[Dict[str, Any]]         # from L3
    actions: List[Dict[str, Any]]           # from L8 ActionCards (serialized)
    schedule: List[Dict[str, Any]]          # from L8 ScheduledActions (serialized)
    zone_plan: Dict[str, Any]               # from L8
    
    outcome_forecast: Dict[str, Any] = field(default_factory=dict)
    user_query: Optional[str] = None


@dataclass
class InterfaceOutput:
    """
    Layer 9 structured output — deterministic, verifiable.
    
    Invariants:
      - No numeric values not present in upstream data
      - No dates not present in schedule
      - Blocked actions described as blocked, never suggested
      - Disclaimers present when audit_grade <= C
    """
    summary: str
    zone_cards: List[ZoneCard]
    alerts: List[Alert]
    explanations: List[Explanation]
    disclaimers: List[Disclaimer]
    citations: List[Citation]
    render_hints: RenderHint
    
    phrasing_mode: PhrasingMode = PhrasingMode.CONFIDENT
    follow_up_questions: List[str] = field(default_factory=list)
    
    # Operational outputs (v9.6)
    task_board: Optional[TaskBoard] = None
    data_requests: List[DataRequest] = field(default_factory=list)
    reminders: List[Reminder] = field(default_factory=list)
    
    # For LLM — not displayed directly
    llm_prompt: str = ""
    llm_response: str = ""
