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
    # Anomaly detector categories (BUG-2 fix)
    MOISTURE = "MOISTURE"
    VEGETATION = "VEGETATION"
    TEMPERATURE = "TEMPERATURE"
    PEST = "PEST"


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
    plot_id: str = "UNKNOWN"


@dataclass
class IntentClassification:
    """Result of the intent router."""
    primary_intent: UserIntent = UserIntent.UNKNOWN
    confidence: float = 0.0
    fallback_intent: UserIntent = UserIntent.OVERVIEW
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    detected_expertise: ExpertiseLevel = ExpertiseLevel.FARMER
    secondary_intents: List[UserIntent] = field(default_factory=list)


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
    image_data_b64: Optional[str] = None
    plot_id: str = "UNKNOWN"
    
    # Decadal biophysical and operational context (v9.8 advanced calibration)
    plot_dna: Optional[Dict[str, Any]] = field(default_factory=dict)
    biophysical_history: Optional[Dict[str, Any]] = field(default_factory=dict)
    user_events: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # Extra outputs from other layers (v9.7 advanced integration)
    l1_fusion_data: Optional[Dict[str, Any]] = field(default_factory=dict)
    l2_vegetation_data: Optional[Dict[str, Any]] = field(default_factory=dict)
    l4_nutrient_data: Optional[Dict[str, Any]] = field(default_factory=dict)
    l5_disease_data: Optional[Dict[str, Any]] = field(default_factory=dict)
    l6_execution_data: Optional[Dict[str, Any]] = field(default_factory=dict)
    l7_planning_data: Optional[Dict[str, Any]] = field(default_factory=dict)
    l10_sire_data: Optional[Dict[str, Any]] = field(default_factory=dict)


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

    def to_dict(self) -> Dict[str, Any]:
        """Convert standard dataclass to dict, preserving Pydantic-compatible structures."""
        from dataclasses import asdict
        return asdict(self)

    def to_json(self) -> str:
        """Convert standard dataclass to JSON string."""
        import json
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterfaceOutput":
        """Reconstruct InterfaceOutput from dict, performing type-safety parsing and dynamic fallbacks."""
        # Custom parsing logic to ensure complete Pydantic-like safety bounds checking
        summary = str(data.get("summary", ""))
        
        zone_cards = []
        for z in data.get("zone_cards", []):
            if isinstance(z, dict):
                zone_cards.append(ZoneCard(
                    zone_id=z.get("zone_id", ""),
                    top_action=z.get("top_action"),
                    confidence_badge=BadgeColor(z.get("confidence_badge", BadgeColor.GRAY)),
                    key_metrics=z.get("key_metrics", {}),
                    status_text=z.get("status_text", "")
                ))
            elif isinstance(z, ZoneCard):
                zone_cards.append(z)
                
        alerts = []
        for a in data.get("alerts", []):
            if isinstance(a, dict):
                alerts.append(Alert(
                    alert_type=AlertType(a.get("alert_type", AlertType.SYSTEM)),
                    severity=AlertSeverity(a.get("severity", AlertSeverity.INFO)),
                    message=a.get("message", ""),
                    trigger_evidence_id=a.get("trigger_evidence_id", ""),
                    action_required=bool(a.get("action_required", False))
                ))
            elif isinstance(a, Alert):
                alerts.append(a)
                
        explanations = []
        for e in data.get("explanations", []):
            if isinstance(e, dict):
                explanations.append(Explanation(
                    statement=e.get("statement", ""),
                    evidence_id=e.get("evidence_id", ""),
                    source_layer=e.get("source_layer", ""),
                    confidence=float(e.get("confidence", 1.0))
                ))
            elif isinstance(e, Explanation):
                explanations.append(e)

        disclaimers = []
        for d in data.get("disclaimers", []):
            if isinstance(d, dict):
                disclaimers.append(Disclaimer(
                    text=d.get("text", ""),
                    reason=d.get("reason", ""),
                    severity=AlertSeverity(d.get("severity", AlertSeverity.WARNING))
                ))
            elif isinstance(d, Disclaimer):
                disclaimers.append(d)

        citations = []
        for c in data.get("citations", []):
            if isinstance(c, dict):
                citations.append(Citation(
                    source_layer=c.get("source_layer", ""),
                    reference_id=c.get("reference_id", ""),
                    timestamp=c.get("timestamp", ""),
                    value=c.get("value"),
                    description=c.get("description", "")
                ))
            elif isinstance(c, Citation):
                citations.append(c)

        rh = data.get("render_hints")
        if isinstance(rh, dict):
            render_hints = RenderHint(
                badge_color=BadgeColor(rh.get("badge_color", BadgeColor.GRAY)),
                show_uncertainty_overlay=bool(rh.get("show_uncertainty_overlay", False)),
                show_conflict_icon=bool(rh.get("show_conflict_icon", False)),
                highlight_zones=list(rh.get("highlight_zones", []))
            )
        elif isinstance(rh, RenderHint):
            render_hints = rh
        else:
            render_hints = RenderHint(badge_color=BadgeColor.GRAY)

        # Operational tasks/requests/reminders
        task_board = None
        tb = data.get("task_board")
        if isinstance(tb, dict):
            tasks = []
            for t in tb.get("tasks", []):
                if isinstance(t, dict):
                    tasks.append(FieldTask(
                        task_id=t.get("task_id", ""),
                        title=t.get("title", ""),
                        action_type=t.get("action_type", ""),
                        zone_id=t.get("zone_id", ""),
                        priority=float(t.get("priority", 0.0)),
                        status=TaskStatus(t.get("status", TaskStatus.PENDING)),
                        due_date=t.get("due_date", ""),
                        created_from=t.get("created_from", ""),
                        notes=t.get("notes", "")
                    ))
                elif isinstance(t, FieldTask):
                    tasks.append(t)
            task_board = TaskBoard(
                tasks=tasks,
                overdue_count=int(tb.get("overdue_count", 0)),
                completed_today=int(tb.get("completed_today", 0)),
                completion_rate_7d=float(tb.get("completion_rate_7d", 0.0))
            )
        elif isinstance(tb, TaskBoard):
            task_board = tb

        data_requests = []
        for dr in data.get("data_requests", []):
            if isinstance(dr, dict):
                data_requests.append(DataRequest(
                    request_id=dr.get("request_id", ""),
                    data_type=DataRequestType(dr.get("data_type", DataRequestType.SOIL_PHOTO)),
                    reason=dr.get("reason", ""),
                    impact_description=dr.get("impact_description", ""),
                    urgency=float(dr.get("urgency", 0.5)),
                    accuracy_gain_estimate=float(dr.get("accuracy_gain_estimate", 0.0))
                ))
            elif isinstance(dr, DataRequest):
                data_requests.append(dr)

        reminders = []
        for r in data.get("reminders", []):
            if isinstance(r, dict):
                reminders.append(Reminder(
                    reminder_id=r.get("reminder_id", ""),
                    title=r.get("title", ""),
                    message=r.get("message", ""),
                    trigger_type=ReminderTrigger(r.get("trigger_type", ReminderTrigger.TIME)),
                    trigger_condition=r.get("trigger_condition", ""),
                    channel=AlertChannel(r.get("channel", AlertChannel.IN_APP)),
                    is_recurring=bool(r.get("is_recurring", False)),
                    snooze_count=int(r.get("snooze_count", 0))
                ))
            elif isinstance(r, Reminder):
                reminders.append(r)

        return cls(
            summary=summary,
            zone_cards=zone_cards,
            alerts=alerts,
            explanations=explanations,
            disclaimers=disclaimers,
            citations=citations,
            render_hints=render_hints,
            phrasing_mode=PhrasingMode(data.get("phrasing_mode", PhrasingMode.CONFIDENT)),
            follow_up_questions=list(data.get("follow_up_questions", [])),
            task_board=task_board,
            data_requests=data_requests,
            reminders=reminders,
            llm_prompt=str(data.get("llm_prompt", "")),
            llm_response=str(data.get("llm_response", ""))
        )
