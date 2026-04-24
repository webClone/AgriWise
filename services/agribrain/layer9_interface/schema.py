"""
Layer 9 Schema: UI/LLM Intelligence — Structured Output Contract

Layer 9 is a deterministic renderer + policy enforcer, NOT a creative assistant.
It must NEVER invent rates, dates, zones, diagnoses, or economics.

Output:
  - InterfaceOutput: summary, zone_cards, alerts, explanations,
    disclaimers, citations, render_hints
  - All content comes from upstream layers (L3-L8)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


# ============================================================================
# Enums
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
# Data Structures
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
# I/O
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
    
    # For LLM — not displayed directly
    llm_prompt: str = ""
    llm_response: str = ""
