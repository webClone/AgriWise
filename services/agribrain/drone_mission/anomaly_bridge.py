"""
Anomaly Bridge.

Translates structured anomaly reports from any Layer 0 perception engine
into drone mission suggestions.  The bridge is engine-agnostic: Satellite RGB,
Farmer Photo, Drone RGB, or future engines all feed the same contract.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import hashlib
import json

from .schemas import MissionIntent, MissionType, FlightMode


# ============================================================================
# Anomaly Report — the universal trigger contract
# ============================================================================

@dataclass
class AnomalyReport:
    """Structured anomaly evidence from any Layer 0 perception engine.
    
    The `report_id` is a stable identity key used for deduplication and
    recency suppression.  Callers should either supply a deterministic ID
    or leave it blank and let __post_init__ compute a content hash.
    """
    source: str                           # "satellite_rgb", "farmer_photo", "drone_rgb"
    plot_id: str
    anomaly_type: str                     # "vegetation_drop", "weed_pressure_high", etc.
    severity: float                       # 0.0–1.0
    confidence: float                     # 0.0–1.0
    polygon_geojson: Dict[str, Any]
    timestamp: datetime

    zone_id: Optional[str] = None
    crop_type: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    # Stable identity key — auto-generated from content if not supplied
    report_id: str = ""

    def __post_init__(self):
        if not self.report_id:
            # Deterministic hash from immutable content fields
            blob = json.dumps({
                "source": self.source,
                "plot_id": self.plot_id,
                "anomaly_type": self.anomaly_type,
                "zone_id": self.zone_id or "",
                "ts": self.timestamp.isoformat(),
            }, sort_keys=True)
            self.report_id = hashlib.sha256(blob.encode()).hexdigest()[:16]


# ============================================================================
# Mission Suggestion — the output contract
# ============================================================================

@dataclass
class MissionSuggestion:
    """A recommended drone deployment with justification."""
    intent: MissionIntent
    urgency_score: float                  # 0.0–1.0 priority ranking
    reason: str                           # Human-readable justification
    source_anomaly_id: str                # report_id of the originating anomaly
    suppressed: bool = False              # True if suppressed by recency/budget
    suppression_reason: str = ""


# ============================================================================
# Mission Suggestion Engine
# ============================================================================

# Anomaly type → (MissionType, FlightMode, target_gsd_cm)
_ANOMALY_TO_MISSION = {
    "vegetation_drop":      (MissionType.ROW_AUDIT,           FlightMode.MAPPING_MODE,          2.0),
    "missing_plants":       (MissionType.ROW_AUDIT,           FlightMode.MAPPING_MODE,          2.0),
    "weed_pressure_high":   (MissionType.WEED_MAP,            FlightMode.MAPPING_MODE,          1.5),
    "disease_suspected":    (MissionType.CONCERN_ZONE_COMMAND, FlightMode.COMMAND_REVISIT_MODE, 0.5),
    "chlorosis_patch":      (MissionType.CONCERN_ZONE_COMMAND, FlightMode.COMMAND_REVISIT_MODE, 0.5),
    "canopy_decline":       (MissionType.FULL_PLOT_MAP,       FlightMode.MAPPING_MODE,          3.0),
    "orchard_gap":          (MissionType.ORCHARD_AUDIT,       FlightMode.MAPPING_MODE,          2.5),
}

# Severity gate — below this, the anomaly is too minor to warrant a flight
_MIN_SEVERITY = 0.3
# Confidence gate — below this, wait for corroboration
_MIN_CONFIDENCE = 0.4
# Recency gate — do not re-inspect the same anomaly within this many days
_RECENCY_DAYS = 3


class MissionSuggestionEngine:
    """Evaluates anomaly reports and suggests drone missions when warranted."""

    def evaluate(
        self,
        report: AnomalyReport,
        recent_mission_timestamps: Optional[Dict[str, datetime]] = None,
    ) -> MissionSuggestion:
        """Evaluate an anomaly report and return a MissionSuggestion.
        
        Args:
            report: The anomaly report to evaluate.
            recent_mission_timestamps: Map of anomaly_key → last-inspected timestamp.
                Key format: "{plot_id}:{anomaly_type}:{zone_id or ''}"
        
        Returns:
            MissionSuggestion (may be suppressed).
        """
        recent = recent_mission_timestamps or {}

        # Determine mission type
        mapping = _ANOMALY_TO_MISSION.get(report.anomaly_type)
        if mapping is None:
            # Unknown anomaly type — default to rapid scout
            m_type = MissionType.RAPID_SCOUT
            mode = FlightMode.MAPPING_MODE
            gsd = 5.0
        else:
            m_type, mode, gsd = mapping

        # Build the intent
        intent = MissionIntent(
            intent_id=f"auto_{report.report_id}",
            plot_id=report.plot_id,
            mission_type=m_type,
            flight_mode=mode,
            polygon_geojson=report.polygon_geojson,
            target_zone_id=report.zone_id,
            target_gsd_cm=gsd,
            required_overlap_pct=75.0 if mode == FlightMode.MAPPING_MODE else 60.0,
            trigger_source=f"anomaly_{report.source}",
            crop_type=report.crop_type,
        )

        # Compute urgency
        staleness_factor = 1.0  # Could be refined with recency
        urgency = report.severity * report.confidence * staleness_factor

        # Suppression checks
        suppressed = False
        suppression_reason = ""

        # 1. Severity gate
        if report.severity < _MIN_SEVERITY:
            suppressed = True
            suppression_reason = f"Severity {report.severity:.2f} below threshold {_MIN_SEVERITY}"

        # 2. Confidence gate
        elif report.confidence < _MIN_CONFIDENCE:
            suppressed = True
            suppression_reason = f"Confidence {report.confidence:.2f} below threshold {_MIN_CONFIDENCE}"

        # 3. Recency gate
        else:
            key = f"{report.plot_id}:{report.anomaly_type}:{report.zone_id or ''}"
            last_inspected = recent.get(key)
            if last_inspected is not None:
                days_since = (report.timestamp - last_inspected).total_seconds() / 86400.0
                if days_since < _RECENCY_DAYS:
                    suppressed = True
                    suppression_reason = (
                        f"Same anomaly inspected {days_since:.1f} days ago "
                        f"(recency gate = {_RECENCY_DAYS} days)"
                    )

        reason = (
            f"Auto-suggested {m_type.value} from {report.source} "
            f"anomaly '{report.anomaly_type}' "
            f"(severity={report.severity:.2f}, confidence={report.confidence:.2f})"
        )

        return MissionSuggestion(
            intent=intent,
            urgency_score=urgency,
            reason=reason,
            source_anomaly_id=report.report_id,
            suppressed=suppressed,
            suppression_reason=suppression_reason,
        )
