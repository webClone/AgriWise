"""
Irrigation Runtime — Scheduler v1.0.0

Merges L8 prescriptive ActionCards (type=IRRIGATE) with weather forecasts,
water quotas, phenology constraints, and operational context to produce
prioritized IrrigationScheduleEntry queues.

Pipeline:
  L8 ActionCard → weather gate → quota gate → phenology gate
    → timing optimizer → IrrigationScheduleEntry queue

Scheduling Rules:
  1. Rain deferral: postpone if forecast rain > 10mm in next 24h
  2. Frost protection: defer if air temp < 2°C
  3. Water quota: block if season/daily quota exhausted
  4. Phenology: adjust volume based on growth stage water demand
  5. Time window: prefer early morning (04:00-08:00) or late evening
  6. Deficit strategy: reduce volume proportionally when quota is scarce
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from irrigation_runtime.schemas import (
    AutomationMode,
    CommandPriority,
    EventStatus,
    IrrigationEvent,
    IrrigationScheduleEntry,
    IrrigationSystemType,
    WaterBudget,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Application Efficiency by System Type
# ============================================================================

SYSTEM_EFFICIENCY = {
    IrrigationSystemType.DRIP: 0.95,
    IrrigationSystemType.SUBSURFACE_DRIP: 0.97,
    IrrigationSystemType.MICRO_SPRAY: 0.90,
    IrrigationSystemType.SPRINKLER: 0.80,
    IrrigationSystemType.CENTER_PIVOT: 0.85,
    IrrigationSystemType.LINEAR_MOVE: 0.88,
    IrrigationSystemType.FLOOD: 0.60,
}


class IrrigationScheduler:
    """Merges agronomic intelligence with operational constraints.

    Converts L8 IRRIGATE ActionCards into validated, prioritized
    IrrigationScheduleEntry records that the CommandDispatcher can execute.
    """

    def __init__(self):
        self._schedule_queue: List[IrrigationScheduleEntry] = []
        self._water_budgets: Dict[str, WaterBudget] = {}
        # plot_id → WaterBudget

        # Configuration
        self.rain_threshold_mm: float = 10.0      # Defer if rain > this
        self.frost_threshold_c: float = 2.0       # Defer if temp < this
        self.preferred_time_start: str = "04:00"   # Optimal start time
        self.preferred_time_end: str = "08:00"     # Optimal end time
        self.deficit_threshold: float = 0.3        # Apply deficit strategy below 30% quota

    # ================================================================
    # Budget Management
    # ================================================================

    def set_water_budget(self, plot_id: str, budget: WaterBudget) -> None:
        """Register or update a water budget for a plot."""
        self._water_budgets[plot_id] = budget
        logger.info("Water budget set for plot %s: %.0f/%.0f mm remaining",
                     plot_id, budget.season_remaining_mm, budget.season_quota_mm)

    def get_water_budget(self, plot_id: str) -> Optional[WaterBudget]:
        """Get the current water budget for a plot."""
        return self._water_budgets.get(plot_id)

    # ================================================================
    # ActionCard → Schedule Entry Conversion
    # ================================================================

    def schedule_from_action_card(
        self,
        action_card: Dict[str, Any],
        weather_forecast: Optional[Dict[str, Any]] = None,
        sensor_readings: Optional[Dict[str, float]] = None,
        phenology: Optional[Dict[str, Any]] = None,
        automation_mode: AutomationMode = AutomationMode.SEMI_AUTO,
    ) -> IrrigationScheduleEntry:
        """Convert an L8 ActionCard (IRRIGATE) to a schedule entry.

        Applies weather, quota, phenology, and timing gates.

        Args:
            action_card: L8 ActionCard dict with action_type=IRRIGATE
            weather_forecast: {rain_mm_24h, rain_mm_48h, min_temp_c, ...}
            sensor_readings: Current sensor values (air_temperature_c, etc.)
            phenology: {bbch_stage, water_demand_factor, ...}
            automation_mode: The farmer's chosen automation level

        Returns:
            IrrigationScheduleEntry (may have deferred_reason if blocked)
        """
        plot_id = action_card.get("plot_id", "")
        zone_id = action_card.get("zone_id", action_card.get("target_zone", ""))
        device_id = action_card.get("device_id", "")
        action_id = action_card.get("action_id", "")

        # Base volume from L8 recommendation
        raw_volume_mm = float(action_card.get("rate_min", 0) or action_card.get("volume_mm", 0))
        system_type_str = action_card.get("system_type", "DRIP")
        try:
            system_type = IrrigationSystemType(system_type_str)
        except ValueError:
            system_type = IrrigationSystemType.DRIP

        urgency = action_card.get("urgency", "NORMAL")
        reason = action_card.get("reason", action_card.get("rationale", ""))

        # Create base entry
        entry = IrrigationScheduleEntry(
            schedule_id=f"SCH-{uuid.uuid4().hex[:12]}",
            plot_id=plot_id,
            zone_id=zone_id,
            device_id=device_id,
            system_type=system_type,
            target_volume_mm=raw_volume_mm,
            scheduled_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            optimal_time=self.preferred_time_start,
            time_window_start=self.preferred_time_start,
            time_window_end=self.preferred_time_end,
            source_action_id=action_id,
            urgency=urgency,
            reason=reason,
            automation_mode=automation_mode,
        )

        # ─── Gate 1: Weather ─────────────────────────────────────
        if weather_forecast:
            entry = self._apply_weather_gate(entry, weather_forecast)

        # ─── Gate 2: Frost Protection ────────────────────────────
        if sensor_readings:
            entry = self._apply_frost_gate(entry, sensor_readings)

        # ─── Gate 3: Water Quota ─────────────────────────────────
        budget = self._water_budgets.get(plot_id)
        if budget:
            entry = self._apply_quota_gate(entry, budget)

        # ─── Gate 4: Phenology Adjustment ────────────────────────
        if phenology:
            entry = self._apply_phenology_adjustment(entry, phenology)

        # ─── Gate 5: System Efficiency ───────────────────────────
        efficiency = SYSTEM_EFFICIENCY.get(system_type, 0.85)
        # Gross volume = net volume / efficiency
        gross_volume = entry.target_volume_mm / efficiency
        entry.target_volume_mm = round(gross_volume, 2)

        # ─── Duration Calculation ────────────────────────────────
        entry.target_duration_minutes = self._estimate_duration(entry)

        # ─── Auto-approve for FULL_AUTO ──────────────────────────
        if automation_mode == AutomationMode.FULL_AUTO and entry.safety_ok:
            entry.approval_status = "APPROVED"
            entry.approved_by = "SYSTEM_AUTO"
            entry.approved_at = datetime.now(timezone.utc).isoformat()

        self._schedule_queue.append(entry)
        logger.info(
            "Scheduled irrigation: %s (plot=%s, zone=%s, volume=%.1fmm, "
            "urgency=%s, approval=%s)",
            entry.schedule_id, plot_id, zone_id,
            entry.target_volume_mm, urgency, entry.approval_status,
        )

        return entry

    # ================================================================
    # Gate Implementations
    # ================================================================

    def _apply_weather_gate(
        self,
        entry: IrrigationScheduleEntry,
        forecast: Dict[str, Any],
    ) -> IrrigationScheduleEntry:
        """Defer irrigation if significant rain is forecast."""
        rain_24h = forecast.get("rain_mm_24h", 0.0)
        rain_48h = forecast.get("rain_mm_48h", 0.0)
        entry.rain_forecast_mm = rain_24h

        if rain_24h >= self.rain_threshold_mm:
            entry.weather_ok = False
            entry.deferred_reason = (
                f"Rain forecast: {rain_24h:.1f}mm in next 24h "
                f"(threshold: {self.rain_threshold_mm}mm)"
            )
            entry.approval_status = "DEFERRED"
            logger.info("Weather deferral for %s: %s",
                        entry.schedule_id, entry.deferred_reason)
        elif rain_48h >= self.rain_threshold_mm * 1.5:
            # Reduce volume if moderate rain coming in 48h
            reduction = min(0.5, rain_48h / (self.rain_threshold_mm * 3))
            entry.target_volume_mm *= (1.0 - reduction)
            logger.info("Volume reduced by %.0f%% for %s (rain in 48h: %.1fmm)",
                        reduction * 100, entry.schedule_id, rain_48h)

        return entry

    def _apply_frost_gate(
        self,
        entry: IrrigationScheduleEntry,
        sensor_readings: Dict[str, float],
    ) -> IrrigationScheduleEntry:
        """Defer irrigation if frost risk detected."""
        air_temp = sensor_readings.get("air_temperature_c")
        if air_temp is not None and air_temp < self.frost_threshold_c:
            entry.safety_ok = False
            entry.deferred_reason = (
                f"Frost risk: {air_temp:.1f}°C (threshold: {self.frost_threshold_c}°C)"
            )
            entry.approval_status = "DEFERRED"
            logger.info("Frost deferral for %s: %s",
                        entry.schedule_id, entry.deferred_reason)

        return entry

    def _apply_quota_gate(
        self,
        entry: IrrigationScheduleEntry,
        budget: WaterBudget,
    ) -> IrrigationScheduleEntry:
        """Enforce water quota constraints."""
        can_irrigate, reason = budget.can_irrigate(entry.target_volume_mm)

        if not can_irrigate:
            # Check if deficit strategy can help
            quota_ratio = budget.season_remaining_mm / budget.season_quota_mm
            if quota_ratio > 0 and quota_ratio < self.deficit_threshold:
                # Apply deficit irrigation: reduce volume to fit budget
                deficit_volume = min(entry.target_volume_mm, budget.daily_remaining_mm)
                if deficit_volume > 0:
                    logger.info(
                        "Deficit irrigation for %s: reduced %.1f → %.1fmm",
                        entry.schedule_id, entry.target_volume_mm, deficit_volume,
                    )
                    entry.target_volume_mm = deficit_volume
                    entry.quota_ok = True
                    return entry

            entry.quota_ok = False
            entry.deferred_reason = reason
            entry.approval_status = "DEFERRED"
            logger.warning("Quota block for %s: %s", entry.schedule_id, reason)
        else:
            entry.quota_ok = True

        return entry

    def _apply_phenology_adjustment(
        self,
        entry: IrrigationScheduleEntry,
        phenology: Dict[str, Any],
    ) -> IrrigationScheduleEntry:
        """Adjust volume based on crop growth stage water demand."""
        water_demand_factor = phenology.get("water_demand_factor", 1.0)
        bbch_stage = phenology.get("bbch_stage", 0)

        # Scale volume by phenology demand factor
        entry.target_volume_mm *= water_demand_factor
        entry.phenology_ok = True

        # Critical stages get higher urgency
        if bbch_stage in range(60, 80):  # Flowering to fruit development
            if entry.urgency == "NORMAL":
                entry.urgency = "HIGH"
                logger.info("Urgency elevated to HIGH for %s (BBCH %d, flowering/fruit)",
                            entry.schedule_id, bbch_stage)

        return entry

    def _estimate_duration(self, entry: IrrigationScheduleEntry) -> float:
        """Estimate irrigation duration from volume and system type.

        Uses typical application rates for each system type.
        """
        # Typical application rates (mm/hour)
        app_rates = {
            IrrigationSystemType.DRIP: 4.0,
            IrrigationSystemType.SUBSURFACE_DRIP: 3.5,
            IrrigationSystemType.MICRO_SPRAY: 8.0,
            IrrigationSystemType.SPRINKLER: 12.0,
            IrrigationSystemType.CENTER_PIVOT: 15.0,
            IrrigationSystemType.LINEAR_MOVE: 15.0,
            IrrigationSystemType.FLOOD: 30.0,
        }
        rate = app_rates.get(entry.system_type, 10.0)
        duration_hours = entry.target_volume_mm / rate
        return round(duration_hours * 60, 1)  # Convert to minutes

    # ================================================================
    # Queue Management
    # ================================================================

    def get_pending_schedule(self, plot_id: Optional[str] = None) -> List[IrrigationScheduleEntry]:
        """Get pending schedule entries, optionally filtered by plot."""
        entries = [e for e in self._schedule_queue
                   if e.approval_status in ("PENDING", "APPROVED")]
        if plot_id:
            entries = [e for e in entries if e.plot_id == plot_id]
        return sorted(entries, key=lambda e: (
            {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}.get(e.urgency, 2),
            e.scheduled_date,
            e.optimal_time,
        ))

    def get_deferred_schedule(self) -> List[IrrigationScheduleEntry]:
        """Get all deferred entries with their reasons."""
        return [e for e in self._schedule_queue if e.approval_status == "DEFERRED"]

    def approve_entry(self, schedule_id: str, approved_by: str) -> bool:
        """Farmer approves a scheduled irrigation event."""
        for entry in self._schedule_queue:
            if entry.schedule_id == schedule_id:
                entry.approval_status = "APPROVED"
                entry.approved_by = approved_by
                entry.approved_at = datetime.now(timezone.utc).isoformat()
                logger.info("Schedule %s approved by %s", schedule_id, approved_by)
                return True
        return False

    def reject_entry(self, schedule_id: str) -> bool:
        """Farmer rejects a scheduled irrigation event."""
        for entry in self._schedule_queue:
            if entry.schedule_id == schedule_id:
                entry.approval_status = "REJECTED"
                logger.info("Schedule %s rejected", schedule_id)
                return True
        return False

    def create_event_from_entry(self, entry: IrrigationScheduleEntry) -> IrrigationEvent:
        """Convert an approved schedule entry to an executable event."""
        event = IrrigationEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:12]}",
            plot_id=entry.plot_id,
            zone_id=entry.zone_id,
            device_id=entry.device_id,
            system_type=entry.system_type,
            automation_mode=entry.automation_mode,
            status=EventStatus.QUEUED,
            target_volume_mm=entry.target_volume_mm,
            target_duration_minutes=entry.target_duration_minutes,
            scheduled_start=f"{entry.scheduled_date}T{entry.scheduled_time or entry.optimal_time}:00Z",
            source_action_id=entry.source_action_id,
            source_schedule_id=entry.schedule_id,
            approved_by=entry.approved_by,
            approved_at=entry.approved_at,
            application_efficiency=SYSTEM_EFFICIENCY.get(entry.system_type, 0.85),
        )
        event.transition(EventStatus.QUEUED, "Created from schedule entry")

        entry.event_id = event.event_id
        logger.info("Created event %s from schedule %s",
                     event.event_id, entry.schedule_id)
        return event

    def clear_completed(self) -> int:
        """Remove completed/cancelled entries from the queue."""
        before = len(self._schedule_queue)
        self._schedule_queue = [
            e for e in self._schedule_queue
            if e.approval_status not in ("REJECTED",)
            and not e.event_id  # Keep entries without events
        ]
        removed = before - len(self._schedule_queue)
        return removed
