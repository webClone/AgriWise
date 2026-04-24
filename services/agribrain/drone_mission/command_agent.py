"""
Drone Command Agent.

Translates high-level goals into concrete mission intents.
Acts as the API boundary for user commands or Layer 0 triggers.

V1.5B: Also accepts AnomalyReport and re-fly requests.
"""

from typing import Dict, Any, List, Optional, Tuple
from .schemas import MissionIntent, MissionType, FlightMode, FlightPlan
from .mission_selector import select_mission_for_anomaly
from .anomaly_bridge import AnomalyReport, MissionSuggestion, MissionSuggestionEngine
from .refly_planner import ReflyPlanner, WeakZone
from .mission_history import MissionHistory


class DroneCommandAgent:
    """Agent that fields requests for drone deployments."""

    def __init__(self, history: Optional[MissionHistory] = None):
        self._suggestion_engine = MissionSuggestionEngine()
        self._refly_planner = ReflyPlanner()
        self._history = history or MissionHistory()

    @property
    def history(self) -> MissionHistory:
        return self._history

    def process_anomaly_trigger(
        self, 
        plot_id: str, 
        polygon_geojson: Dict[str, Any], 
        anomaly_type: str, 
        crop_type: str,
        zone_id: str = None
    ) -> MissionIntent:
        """Process an automated trigger from another engine (e.g., Satellite RGB)."""
        return select_mission_for_anomaly(plot_id, polygon_geojson, anomaly_type, crop_type, zone_id)

    def process_anomaly_report(self, report: AnomalyReport) -> MissionSuggestion:
        """Process a structured AnomalyReport and return a MissionSuggestion.
        
        Uses the MissionSuggestionEngine for severity/confidence/recency gating.
        """
        recent = self._history.get_recent_anomaly_timestamps(report.plot_id)
        return self._suggestion_engine.evaluate(report, recent)

    def process_refly_request(
        self,
        qa_score: float,
        coverage_completeness: float,
        spatial_maps: List = None,
        plot_polygon: Dict[str, Any] = None,
        plot_id: str = "unknown",
    ) -> Optional[FlightPlan]:
        """Evaluate whether a re-fly is needed and generate a plan if so."""
        weak_zones = self._refly_planner.identify_weak_zones(
            qa_score, coverage_completeness, spatial_maps,
        )
        if not weak_zones or not plot_polygon:
            return None
        return self._refly_planner.plan_refly(weak_zones, plot_polygon, plot_id=plot_id)
        
    def process_user_command(
        self,
        plot_id: str,
        polygon_geojson: Dict[str, Any],
        command_text: str,
        crop_type: str,
        target_zone_id: str = None
    ) -> MissionIntent:
        """Process a direct natural language or UI command from the user."""
        cmd = command_text.lower()
        
        mode = FlightMode.MAPPING_MODE
        m_type = MissionType.FULL_PLOT_MAP
        gsd = 3.0
        
        if "inspect zone" in cmd or "re-fly" in cmd or "close" in cmd or "symptom" in cmd:
            mode = FlightMode.COMMAND_REVISIT_MODE
            m_type = MissionType.CONCERN_ZONE_COMMAND
            gsd = 0.5
        elif "weed" in cmd:
            m_type = MissionType.WEED_MAP
            gsd = 1.5
        elif "row" in cmd or "stand" in cmd or "gap" in cmd:
            if crop_type in ("orchard", "citrus", "olive"):
                m_type = MissionType.ORCHARD_AUDIT
                gsd = 2.5
            else:
                m_type = MissionType.ROW_AUDIT
                gsd = 2.0
        elif "rapid" in cmd or "quick" in cmd:
            m_type = MissionType.RAPID_SCOUT
            gsd = 5.0
            
        intent = MissionIntent(
            intent_id=f"cmd_{plot_id}_manual",
            plot_id=plot_id,
            mission_type=m_type,
            flight_mode=mode,
            polygon_geojson=polygon_geojson,
            target_zone_id=target_zone_id,
            target_gsd_cm=gsd,
            required_overlap_pct=75.0 if mode == FlightMode.MAPPING_MODE else 60.0,
            trigger_source="user_command",
            crop_type=crop_type
        )
        return intent

