"""
Drone API Routes — FastAPI router for drone mission orchestration.

Endpoints:
  GET  /api/drone/suggest/{plot_id}              — Get mission suggestions from anomaly bridge
  POST /api/drone/plan                           — Generate FlightPlan from MissionIntent
  POST /api/drone/dispatch                       — Dispatch a mission (mock driver)
  GET  /api/drone/missions                       — List all missions
  GET  /api/drone/missions/{execution_id}        — Get mission state + summary
  POST /api/drone/missions/{execution_id}/control — Pause/Resume/Abort/RTL
  GET  /api/drone/missions/{execution_id}/report  — Get post-mission execution report
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drone", tags=["drone"])


# ============================================================================
# In-process singletons (lazy-init to avoid import cost on startup)
# ============================================================================

_planner = None
_dispatcher = None
_mission_history = None
_suggestion_engine = None


def _get_planner():
    global _planner
    if _planner is None:
        from drone_mission.planner import DroneMissionPlanner
        _planner = DroneMissionPlanner()
    return _planner


def _get_dispatcher():
    global _dispatcher
    if _dispatcher is None:
        from drone_control.dispatcher import Dispatcher
        _dispatcher = Dispatcher()
    return _dispatcher


def _get_mission_history():
    global _mission_history
    if _mission_history is None:
        from drone_mission.mission_history import MissionHistory
        _mission_history = MissionHistory()
    return _mission_history


def _get_suggestion_engine():
    global _suggestion_engine
    if _suggestion_engine is None:
        from drone_mission.anomaly_bridge import MissionSuggestionEngine
        _suggestion_engine = MissionSuggestionEngine()
    return _suggestion_engine


# ============================================================================
# Request / Response Models
# ============================================================================

class PlanRequest(BaseModel):
    """Generate a flight plan from mission intent."""
    plot_id: str
    mission_type: str = "full_plot_map"
    flight_mode: str = "mapping_mode"
    polygon_geojson: Dict[str, Any]
    target_zone_id: Optional[str] = None
    target_gsd_cm: float = 2.0
    required_overlap_pct: float = 70.0
    trigger_source: str = "manual"
    crop_type: Optional[str] = None
    drone_profile: str = "standard_prosumer"


class DispatchRequestModel(BaseModel):
    """Dispatch a planned mission."""
    plot_id: str
    plan_id: str
    mission_id: Optional[str] = None
    vehicle_id: str = "sim_drone_01"
    driver_type: str = "mock"
    operator_id: str = "default"
    # Include the full plan data so we don't need server-side plan cache
    flight_plan_data: Optional[Dict[str, Any]] = None
    intent_data: Optional[Dict[str, Any]] = None


class ControlRequest(BaseModel):
    """Live mission control command."""
    plot_id: str
    action: str  # "pause", "resume", "abort", "rtl"
    reason: str = ""


class SuggestionRequest(BaseModel):
    """Anomaly report for mission suggestion."""
    source: str = "satellite_anomaly"
    plot_id: str
    anomaly_type: str
    severity: float
    confidence: float
    polygon_geojson: Dict[str, Any]
    zone_id: Optional[str] = None
    crop_type: Optional[str] = None


# ============================================================================
# In-memory plan cache (plans live between plan and dispatch)
# ============================================================================

_plan_cache: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Routes
# ============================================================================

@router.get("/suggest/{plot_id}")
def get_suggestions(plot_id: str):
    """Get anomaly-based mission suggestions for a plot.

    In a full integration, this would pull recent anomaly reports from
    the Layer 10 zone extractor and L3 diagnostics. For now, it returns
    any suggestions that have been submitted via POST /suggest.
    """
    suggestions = _plan_cache.get(f"suggestions_{plot_id}", [])
    return {
        "plot_id": plot_id,
        "suggestions": suggestions,
        "count": len(suggestions),
    }


@router.post("/suggest")
def submit_anomaly(req: SuggestionRequest):
    """Submit an anomaly report and get a mission suggestion back."""
    from drone_mission.anomaly_bridge import AnomalyReport

    report = AnomalyReport(
        source=req.source,
        plot_id=req.plot_id,
        anomaly_type=req.anomaly_type,
        severity=req.severity,
        confidence=req.confidence,
        polygon_geojson=req.polygon_geojson,
        timestamp=datetime.now(),
        zone_id=req.zone_id,
        crop_type=req.crop_type,
    )

    engine = _get_suggestion_engine()
    history = _get_mission_history()

    # Get recent timestamps for recency suppression
    timestamps = history.get_anomaly_timestamps(req.plot_id)
    suggestion = engine.evaluate(report, timestamps)

    # Serialize suggestion
    result = {
        "intent_id": suggestion.intent.intent_id,
        "mission_type": suggestion.intent.mission_type.value,
        "flight_mode": suggestion.intent.flight_mode.value,
        "urgency_score": suggestion.urgency_score,
        "reason": suggestion.reason,
        "suppressed": suggestion.suppressed,
        "suppression_reason": suggestion.suppression_reason,
        "target_gsd_cm": suggestion.intent.target_gsd_cm,
        "polygon_geojson": suggestion.intent.polygon_geojson,
        "plot_id": req.plot_id,
    }

    # Cache for the suggestions list
    key = f"suggestions_{req.plot_id}"
    if key not in _plan_cache:
        _plan_cache[key] = []
    # Keep last 10 suggestions
    _plan_cache[key] = ([result] + _plan_cache[key])[:10]

    return result


@router.post("/plan")
def plan_mission(req: PlanRequest):
    """Generate a FlightPlan from a MissionIntent."""
    from drone_mission.schemas import MissionIntent, MissionType, FlightMode

    try:
        mission_type = MissionType(req.mission_type)
    except ValueError:
        raise HTTPException(400, f"Unknown mission_type: {req.mission_type}. "
                            f"Valid: {[m.value for m in MissionType]}")

    try:
        flight_mode = FlightMode(req.flight_mode)
    except ValueError:
        raise HTTPException(400, f"Unknown flight_mode: {req.flight_mode}. "
                            f"Valid: {[m.value for m in FlightMode]}")

    intent = MissionIntent(
        intent_id=f"intent_{uuid.uuid4().hex[:8]}",
        plot_id=req.plot_id,
        mission_type=mission_type,
        flight_mode=flight_mode,
        polygon_geojson=req.polygon_geojson,
        target_zone_id=req.target_zone_id,
        target_gsd_cm=req.target_gsd_cm,
        required_overlap_pct=req.required_overlap_pct,
        trigger_source=req.trigger_source,
        crop_type=req.crop_type,
    )

    planner = _get_planner()
    plan = planner.plan_mission(intent, req.drone_profile)

    # Serialize waypoints
    waypoints_data = [
        {"lat": w.lat, "lon": w.lon, "alt_m": w.alt_m, "action": w.action}
        for w in plan.waypoints
    ]

    plan_data = {
        "plan_id": plan.plan_id,
        "intent_id": plan.intent_id,
        "drone_profile": plan.drone_profile,
        "pattern": plan.pattern.value,
        "waypoint_count": len(plan.waypoints),
        "waypoints": waypoints_data,
        "estimated_flight_time_min": round(plan.estimated_flight_time_min, 2),
        "estimated_image_count": plan.estimated_image_count,
        "achieved_gsd_cm": plan.achieved_gsd_cm,
        "flight_altitude_m": round(plan.flight_altitude_m, 2),
        "is_feasible": plan.is_feasible,
        "infeasibility_reason": plan.infeasibility_reason,
    }

    # Cache plan + intent for dispatch
    _plan_cache[plan.plan_id] = {
        "plan": plan,
        "intent": intent,
        "plan_data": plan_data,
    }

    return plan_data


@router.post("/dispatch")
def dispatch_mission(req: DispatchRequestModel):
    """Dispatch a planned mission to a drone (default: mock driver)."""
    from drone_control.schemas import DispatchRequest

    # Retrieve cached plan
    cached = _plan_cache.get(req.plan_id)
    if cached is None:
        raise HTTPException(404, f"Plan {req.plan_id} not found. Call POST /api/drone/plan first.")

    plan = cached["plan"]
    intent = cached["intent"]
    if getattr(intent, "plot_id", "") != req.plot_id:
        raise HTTPException(404, f"Plan {req.plan_id} not found for plot")
    mission_id = req.mission_id or f"mission_{uuid.uuid4().hex[:8]}"

    dispatch_req = DispatchRequest(
        mission_id=mission_id,
        flight_plan=plan,
        intent=intent,
        vehicle_id=req.vehicle_id,
        driver_type=req.driver_type,
        operator_id=req.operator_id,
    )

    dispatcher = _get_dispatcher()
    result = dispatcher.dispatch(dispatch_req)

    # Record in history
    history = _get_mission_history()
    try:
        from drone_mission.mission_history import MissionRecord
        record = MissionRecord(
            execution_id=result.execution_id,
            mission_id=mission_id,
            plot_id=intent.plot_id,
            mission_type=intent.mission_type.value,
            flight_mode=intent.flight_mode.value,
            status=result.state.value,
            success=result.success,
            timestamp=datetime.now(),
            plan_id=plan.plan_id,
        )
        history.record(record)
    except Exception as e:
        logger.warning(f"Failed to record mission history: {e}")

    response = {
        "execution_id": result.execution_id,
        "mission_id": mission_id,
        "success": result.success,
        "state": result.state.value,
        "failure_reason": result.failure_reason or None,
        "failure_stage": result.failure_stage or None,
    }

    if result.compiled_mission:
        cm = result.compiled_mission
        response["compiled_mission"] = {
            "waypoint_count": len(cm.waypoints),
            "flight_altitude_m": cm.flight_altitude_m,
            "estimated_captures": cm.estimated_captures,
            "pattern": cm.pattern,
            "mission_type": cm.mission_type,
        }

    return response


@router.get("/missions")
def list_missions(plot_id: str, limit: int = 20):
    """List recent missions for one explicitly bound plot."""
    history = _get_mission_history()

    # MissionHistory stores records in-memory
    all_records = getattr(history, '_records', [])
    filtered = [r for r in all_records if getattr(r, 'plot_id', '') == plot_id]

    # Most recent first
    filtered.sort(key=lambda r: getattr(r, 'timestamp', datetime.min), reverse=True)
    filtered = filtered[:limit]

    missions = []
    for r in filtered:
        missions.append({
            "execution_id": getattr(r, 'execution_id', ''),
            "mission_id": getattr(r, 'mission_id', ''),
            "plot_id": getattr(r, 'plot_id', ''),
            "mission_type": getattr(r, 'mission_type', ''),
            "flight_mode": getattr(r, 'flight_mode', ''),
            "status": getattr(r, 'status', ''),
            "success": getattr(r, 'success', False),
            "timestamp": getattr(r, 'timestamp', datetime.now()).isoformat(),
        })

    return {"missions": missions, "count": len(missions)}


@router.get("/missions/{execution_id}")
def get_mission(execution_id: str, plot_id: str):
    """Get mission state and summary."""
    dispatcher = _get_dispatcher()

    # Try active session first
    session = dispatcher.get_session(execution_id)
    if session:
        session_plot_id = getattr(getattr(getattr(session, "request", None), "intent", None), "plot_id", "")
        if session_plot_id != plot_id:
            raise HTTPException(404, f"Mission {execution_id} not found for plot")
        state = session.state.value
        telemetry_summary = {}
        if session.ingestor and hasattr(session.ingestor, '_packets'):
            packets = session.ingestor._packets
            if packets:
                last = packets[-1]
                telemetry_summary = {
                    "battery_pct": last.state.battery_pct,
                    "altitude_m": last.state.altitude_m,
                    "groundspeed_m_s": last.state.groundspeed_m_s,
                    "capture_count": last.capture_count,
                    "mission_progress_pct": last.mission_progress_pct,
                    "current_waypoint": last.current_waypoint_index,
                    "total_waypoints": last.total_waypoints,
                    "lat": last.state.latitude,
                    "lng": last.state.longitude,
                }

        return {
            "execution_id": execution_id,
            "state": state,
            "is_terminal": session.is_terminal,
            "telemetry": telemetry_summary,
            "mission_id": session.mission_id,
        }

    # Check history
    history = _get_mission_history()
    all_records = getattr(history, '_records', [])
    record = next(
        (r for r in all_records
         if getattr(r, 'execution_id', '') == execution_id
         and getattr(r, 'plot_id', '') == plot_id),
        None
    )
    if record:
        return {
            "execution_id": execution_id,
            "state": getattr(record, 'status', 'unknown'),
            "is_terminal": True,
            "telemetry": {},
            "mission_id": getattr(record, 'mission_id', ''),
        }

    raise HTTPException(404, f"Mission {execution_id} not found")


@router.post("/missions/{execution_id}/control")
def control_mission(execution_id: str, req: ControlRequest):
    """Send a control command to an active mission."""
    dispatcher = _get_dispatcher()
    session = dispatcher.get_session(execution_id)

    if session is None:
        raise HTTPException(404, f"No active session for {execution_id}")
    session_plot_id = getattr(getattr(getattr(session, "request", None), "intent", None), "plot_id", "")
    if session_plot_id != req.plot_id:
        raise HTTPException(404, f"Mission {execution_id} not found for plot")
    if session.is_terminal:
        raise HTTPException(409, f"Mission {execution_id} already in terminal state: {session.state.value}")

    action = req.action.lower()
    reason = req.reason or f"API control: {action}"
    success = False

    if action == "pause":
        success = dispatcher.pause(execution_id, reason)
    elif action == "resume":
        success = dispatcher.resume(execution_id)
    elif action == "abort":
        success = dispatcher.abort(execution_id, reason)
    elif action == "rtl":
        success = dispatcher.rtl(execution_id, reason)
    else:
        raise HTTPException(400, f"Unknown action: {action}. Valid: pause, resume, abort, rtl")

    return {
        "execution_id": execution_id,
        "action": action,
        "success": success,
        "new_state": session.state.value,
    }


@router.get("/missions/{execution_id}/report")
def get_mission_report(execution_id: str, plot_id: str):
    """Get post-mission execution report."""
    from drone_control.execution_reporter import ExecutionReporter

    dispatcher = _get_dispatcher()
    session = dispatcher.get_session(execution_id)

    if session is None:
        raise HTTPException(404, f"No session found for {execution_id}")
    session_plot_id = getattr(getattr(getattr(session, "request", None), "intent", None), "plot_id", "")
    if session_plot_id != plot_id:
        raise HTTPException(404, f"Mission {execution_id} not found for plot")

    reporter = ExecutionReporter()
    try:
        report = reporter.generate(session)
    except Exception as e:
        raise HTTPException(500, f"Failed to generate report: {e}")

    return {
        "execution_id": report.execution_id,
        "mission_id": report.mission_id,
        "plot_id": report.plot_id,
        "final_state": report.final_state.value if hasattr(report.final_state, 'value') else str(report.final_state),
        "success": report.success,
        "duration_s": report.duration_s,
        "planned_waypoints": report.planned_waypoints,
        "completed_waypoints": report.completed_waypoints,
        "battery_used_pct": report.battery_used_pct,
        "expected_captures": report.expected_captures,
        "actual_captures": report.actual_captures,
        "capture_completeness_pct": report.capture_completeness_pct,
        "coverage_estimate_pct": report.coverage_estimate_pct,
        "warnings_count": len(report.warnings_triggered),
        "media_handoff_status": report.media_handoff_status,
    }
