"""
Irrigation Runtime — L6 Execution Bridge v1.0.0

Bridges the Layer 6 strategic execution engine to the irrigation runtime.
Converts L8 ActionCards (type=IRRIGATE) into IrrigationCommands and feeds
execution results back as ExecutionState updates for the DAG audit trail.

Data Flow:
  L8 ActionCard (IRRIGATE)
    → irrigation_bridge.process_action_card()
    → IrrigationScheduler.schedule_from_action_card()
    → CommandDispatcher.submit_event()
    → ExecutionState update → L6 DAG audit
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IrrigationBridge:
    """Bridge between L6 Execution Layer and Irrigation Runtime.

    Responsibilities:
      1. Convert L8 ActionCards → IrrigationScheduleEntries
      2. Map rate ranges (mm) to physical flow_rate × duration
      3. Return execution results as TaskState updates
      4. Feed NormalizedEvidence to the L6 audit trail
    """

    def __init__(self):
        self._processed_actions: Dict[str, Dict] = {}

    def process_action_card(
        self,
        action_card: Dict[str, Any],
        weather_forecast: Optional[Dict[str, Any]] = None,
        sensor_readings: Optional[Dict[str, float]] = None,
        phenology: Optional[Dict[str, Any]] = None,
        automation_mode: str = "SEMI_AUTO",
    ) -> Dict[str, Any]:
        """Convert an L8 ActionCard into a scheduled irrigation entry.

        Args:
            action_card: L8 ActionCard dict (action_type must be IRRIGATE)
            weather_forecast: Current weather forecast data
            sensor_readings: Latest sensor readings
            phenology: Crop phenology context
            automation_mode: MANUAL, SEMI_AUTO, or FULL_AUTO

        Returns:
            Dict with schedule entry details and status
        """
        from irrigation_runtime.scheduler import IrrigationScheduler
        from irrigation_runtime.schemas import AutomationMode

        action_type = action_card.get("action_type", "")
        if action_type != "IRRIGATE":
            return {"error": f"Expected IRRIGATE action, got {action_type}"}

        # Parse automation mode
        try:
            mode = AutomationMode(automation_mode)
        except ValueError:
            mode = AutomationMode.SEMI_AUTO

        scheduler = IrrigationScheduler()
        entry = scheduler.schedule_from_action_card(
            action_card=action_card,
            weather_forecast=weather_forecast,
            sensor_readings=sensor_readings,
            phenology=phenology,
            automation_mode=mode,
        )

        result = {
            "schedule_id": entry.schedule_id,
            "plot_id": entry.plot_id,
            "zone_id": entry.zone_id,
            "device_id": entry.device_id,
            "target_volume_mm": entry.target_volume_mm,
            "target_duration_minutes": entry.target_duration_minutes,
            "scheduled_date": entry.scheduled_date,
            "optimal_time": entry.optimal_time,
            "approval_status": entry.approval_status,
            "automation_mode": entry.automation_mode.value,
            "weather_ok": entry.weather_ok,
            "quota_ok": entry.quota_ok,
            "phenology_ok": entry.phenology_ok,
            "safety_ok": entry.safety_ok,
            "deferred_reason": entry.deferred_reason,
            "source_action_id": entry.source_action_id,
        }

        self._processed_actions[entry.schedule_id] = result
        return result

    def convert_rate_to_physical(
        self,
        volume_mm: float,
        area_ha: float,
        system_efficiency: float,
        application_rate_mm_hr: float,
    ) -> Dict[str, float]:
        """Convert agronomic rate (mm) to physical delivery parameters.

        Args:
            volume_mm: Target application depth (mm)
            area_ha: Zone area in hectares
            system_efficiency: Application efficiency (0-1)
            application_rate_mm_hr: System application rate

        Returns:
            Dict with flow_rate_lpm, duration_minutes, total_volume_liters
        """
        # Gross volume accounting for efficiency losses
        gross_volume_mm = volume_mm / system_efficiency

        # Total volume in liters (1mm on 1ha = 10,000 liters)
        total_volume_liters = gross_volume_mm * area_ha * 10000

        # Duration
        duration_hours = gross_volume_mm / application_rate_mm_hr
        duration_minutes = duration_hours * 60

        # Required flow rate
        flow_rate_lpm = total_volume_liters / duration_minutes if duration_minutes > 0 else 0

        return {
            "gross_volume_mm": round(gross_volume_mm, 2),
            "total_volume_liters": round(total_volume_liters, 1),
            "duration_minutes": round(duration_minutes, 1),
            "flow_rate_lpm": round(flow_rate_lpm, 2),
        }

    def build_execution_evidence(
        self,
        event_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a NormalizedEvidence record for the L6 audit trail.

        Converts a completed IrrigationEvent into L6-compatible evidence.
        """
        return {
            "evidence_type": "IRRIGATION_RUNTIME",
            "source": "irrigation_runtime.dispatcher",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "event_id": event_dict.get("event_id", ""),
                "status": event_dict.get("status", ""),
                "target_volume_mm": event_dict.get("target_volume_mm", 0),
                "actual_volume_l": event_dict.get("actual_volume_l", 0),
                "actual_duration_minutes": event_dict.get("actual_duration_minutes", 0),
                "validation_outcome": event_dict.get("validation_outcome", "PENDING"),
                "safety_violations": event_dict.get("safety_violations", []),
                "emergency_stopped": event_dict.get("emergency_stopped", False),
            },
            "confidence": 0.95 if event_dict.get("status") == "COMPLETED" else 0.5,
        }
