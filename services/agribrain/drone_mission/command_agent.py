"""
Drone Command Agent.

Translates high-level goals into concrete mission intents.
Acts as the API boundary for user commands or Layer 0 triggers.

V1.5B: Also accepts AnomalyReport and re-fly requests.
V2:    Native dispatch through drone_control/CommandGateway.
"""

from typing import Dict, Any, List, Optional, Tuple
from .schemas import MissionIntent, MissionType, FlightMode, FlightPlan
from .mission_selector import select_mission_for_anomaly
from .anomaly_bridge import AnomalyReport, MissionSuggestion, MissionSuggestionEngine
from .refly_planner import ReflyPlanner, WeakZone
from .mission_history import MissionHistory
from .planner import DroneMissionPlanner

import logging

logger = logging.getLogger(__name__)


class DroneCommandAgent:
    """Agent that fields requests for drone deployments.
    
    V2: Can optionally dispatch directly through drone_control/CommandGateway
    when a gateway is provided. Otherwise returns intents for manual dispatch.
    """

    def __init__(self, history: Optional[MissionHistory] = None, gateway=None):
        self._suggestion_engine = MissionSuggestionEngine()
        self._refly_planner = ReflyPlanner()
        self._history = history or MissionHistory()
        self._planner = DroneMissionPlanner()
        self._gateway = gateway  # Optional: drone_control.CommandGateway

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

    # ====================================================================
    # Native dispatch integration (V2)
    # ====================================================================

    def dispatch_from_anomaly(
        self,
        report: AnomalyReport,
        vehicle_id: str = "default",
        driver_type: str = "mock",
    ) -> Optional[Dict[str, Any]]:
        """End-to-end: anomaly → suggestion → plan → dispatch.
        
        This is the native integration path from drone_mission into
        drone_control. Returns dispatch result dict or None if
        suggestion was suppressed or no gateway is configured.
        """
        if self._gateway is None:
            logger.warning("[CommandAgent] No gateway configured — cannot dispatch")
            return None
        
        # 1. Evaluate anomaly
        suggestion = self.process_anomaly_report(report)
        
        if suggestion.suppressed:
            logger.info(
                f"[CommandAgent] Anomaly suppressed: {suggestion.suppression_reason}"
            )
            return {
                "dispatched": False,
                "reason": suggestion.suppression_reason,
                "anomaly_id": report.report_id,
            }
        
        # 2. Plan
        intent = suggestion.intent
        flight_plan = self._planner.plan_mission(intent)
        
        if not flight_plan.is_feasible:
            logger.warning(
                f"[CommandAgent] Plan not feasible: {flight_plan.infeasibility_reason}"
            )
            return {
                "dispatched": False,
                "reason": f"Plan not feasible: {flight_plan.infeasibility_reason}",
                "anomaly_id": report.report_id,
            }
        
        # 3. Dispatch
        from ..drone_control.schemas import DispatchRequest, WeatherSnapshot, FailsafePolicy
        
        request = DispatchRequest(
            flight_plan=flight_plan,
            intent=intent,
            driver_type=driver_type,
            vehicle_profile=getattr(flight_plan, 'drone_profile', 'standard_prosumer'),
            weather=WeatherSnapshot(),
            failsafe_policy=FailsafePolicy(),
        )
        
        result = self._gateway.dispatch_mission(
            mission_id=f"auto_{report.report_id}",
            vehicle_id=vehicle_id,
            request=request,
        )
        
        logger.info(
            f"[CommandAgent] Dispatched {result.execution_id}: "
            f"success={result.success}, state={result.state.value}"
        )
        
        return {
            "dispatched": True,
            "success": result.success,
            "execution_id": result.execution_id,
            "state": result.state.value,
            "anomaly_id": report.report_id,
        }

    def dispatch_from_intent(
        self,
        intent: MissionIntent,
        vehicle_id: str = "default",
        driver_type: str = "mock",
    ) -> Optional[Dict[str, Any]]:
        """Direct dispatch from a MissionIntent (user command or manual trigger).
        
        Returns dispatch result dict or None if no gateway.
        """
        if self._gateway is None:
            logger.warning("[CommandAgent] No gateway configured — cannot dispatch")
            return None
        
        # Plan
        flight_plan = self._planner.plan_mission(intent)
        
        if not flight_plan.is_feasible:
            return {
                "dispatched": False,
                "reason": f"Plan not feasible: {flight_plan.infeasibility_reason}",
                "intent_id": intent.intent_id,
            }
        
        # Dispatch
        from ..drone_control.schemas import DispatchRequest, WeatherSnapshot, FailsafePolicy
        
        request = DispatchRequest(
            flight_plan=flight_plan,
            intent=intent,
            driver_type=driver_type,
            vehicle_profile=getattr(flight_plan, 'drone_profile', 'standard_prosumer'),
            weather=WeatherSnapshot(),
            failsafe_policy=FailsafePolicy(),
        )
        
        result = self._gateway.dispatch_mission(
            mission_id=f"manual_{intent.intent_id}",
            vehicle_id=vehicle_id,
            request=request,
        )
        
        return {
            "dispatched": True,
            "success": result.success,
            "execution_id": result.execution_id,
            "state": result.state.value,
            "intent_id": intent.intent_id,
        }


