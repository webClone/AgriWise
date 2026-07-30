"""
Drone Control — Health Monitor.

Runtime safety intelligence. Evaluates each telemetry packet against
the failsafe policy and emits structured warnings with severity and
recommended action.
"""

from __future__ import annotations
from typing import List, Optional
import logging

from .schemas import (
    CompiledMission,
    FailsafeAction,
    FailsafePolicy,
    HealthSeverity,
    HealthWarning,
    TelemetryPacket,
)

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Runtime health monitor.
    
    Evaluates telemetry and detects safety conditions. Each detected
    condition produces a HealthWarning with severity and recommended action.
    """
    
    def __init__(self, policy: Optional[FailsafePolicy] = None):
        self._policy = policy or FailsafePolicy()
        self._warnings: List[HealthWarning] = []
        self._link_loss_count = 0
    
    @property
    def warnings(self) -> List[HealthWarning]:
        return list(self._warnings)
    
    def evaluate(
        self,
        packet: TelemetryPacket,
        mission: Optional[CompiledMission] = None,
    ) -> List[HealthWarning]:
        """Evaluate a telemetry packet for safety conditions.
        
        Returns list of new warnings (may be empty if nominal).
        """
        new_warnings: List[HealthWarning] = []
        state = packet.state
        policy = self._policy
        
        # 1. Battery checks
        if state.battery_pct <= policy.battery_emergency_pct:
            new_warnings.append(HealthWarning(
                condition="battery_emergency",
                severity=HealthSeverity.CRITICAL,
                message=f"Battery EMERGENCY: {state.battery_pct:.0f}% ≤ {policy.battery_emergency_pct:.0f}%",
                recommended_action=FailsafeAction.LAND_NOW,
                telemetry_sequence=packet.sequence,
            ))
        elif state.battery_pct <= policy.battery_critical_pct:
            new_warnings.append(HealthWarning(
                condition="battery_critical",
                severity=HealthSeverity.CRITICAL,
                message=f"Battery CRITICAL: {state.battery_pct:.0f}% ≤ {policy.battery_critical_pct:.0f}%",
                recommended_action=FailsafeAction.RTL,
                telemetry_sequence=packet.sequence,
            ))
        elif state.battery_pct <= policy.battery_warn_pct:
            new_warnings.append(HealthWarning(
                condition="battery_low",
                severity=HealthSeverity.HIGH,
                message=f"Battery LOW: {state.battery_pct:.0f}% ≤ {policy.battery_warn_pct:.0f}%",
                recommended_action=FailsafeAction.CONTINUE,
                telemetry_sequence=packet.sequence,
            ))
        
        # 2. GPS checks
        if not state.gps_fix:
            new_warnings.append(HealthWarning(
                condition="gps_loss",
                severity=HealthSeverity.CRITICAL,
                message="GPS fix lost",
                recommended_action=FailsafeAction.RTL,
                telemetry_sequence=packet.sequence,
            ))
        elif state.gps_satellites < policy.min_gps_satellites:
            new_warnings.append(HealthWarning(
                condition="gps_degraded",
                severity=HealthSeverity.HIGH,
                message=f"GPS degraded: {state.gps_satellites} sats < {policy.min_gps_satellites}",
                recommended_action=FailsafeAction.PAUSE,
                telemetry_sequence=packet.sequence,
            ))
        
        # 3. Wind checks
        if state.wind_estimate_m_s > policy.max_wind_gust_m_s:
            new_warnings.append(HealthWarning(
                condition="wind_extreme",
                severity=HealthSeverity.CRITICAL,
                message=f"Wind EXTREME: {state.wind_estimate_m_s:.1f}m/s > {policy.max_wind_gust_m_s:.1f}m/s",
                recommended_action=FailsafeAction.RTL,
                telemetry_sequence=packet.sequence,
            ))
        elif state.wind_estimate_m_s > policy.max_wind_m_s:
            new_warnings.append(HealthWarning(
                condition="wind_high",
                severity=HealthSeverity.HIGH,
                message=f"Wind HIGH: {state.wind_estimate_m_s:.1f}m/s > {policy.max_wind_m_s:.1f}m/s",
                recommended_action=FailsafeAction.PAUSE,
                telemetry_sequence=packet.sequence,
            ))
        
        # 4. Link quality checks
        if state.link_quality_pct < 1.0:
            self._link_loss_count += 1
            new_warnings.append(HealthWarning(
                condition="link_loss",
                severity=HealthSeverity.CRITICAL,
                message=f"Link LOST (count: {self._link_loss_count})",
                recommended_action=FailsafeAction.RTL,
                telemetry_sequence=packet.sequence,
            ))
        elif state.link_quality_pct < policy.link_warn_quality_pct:
            new_warnings.append(HealthWarning(
                condition="link_degraded",
                severity=HealthSeverity.MEDIUM,
                message=f"Link degraded: {state.link_quality_pct:.0f}% < {policy.link_warn_quality_pct:.0f}%",
                recommended_action=FailsafeAction.CONTINUE,
                telemetry_sequence=packet.sequence,
            ))
        else:
            self._link_loss_count = 0
        
        # 5. Off-track drift
        if packet.off_track_m > policy.max_drift_m:
            new_warnings.append(HealthWarning(
                condition="drift",
                severity=HealthSeverity.MEDIUM,
                message=f"Off-track drift: {packet.off_track_m:.1f}m > {policy.max_drift_m:.1f}m",
                recommended_action=FailsafeAction.PAUSE,
                telemetry_sequence=packet.sequence,
            ))
        
        # 6. Altitude deviation
        if abs(packet.altitude_deviation_m) > policy.max_altitude_deviation_m:
            new_warnings.append(HealthWarning(
                condition="altitude_deviation",
                severity=HealthSeverity.MEDIUM,
                message=f"Altitude deviation: {packet.altitude_deviation_m:.1f}m",
                recommended_action=FailsafeAction.CONTINUE,
                telemetry_sequence=packet.sequence,
            ))
        
        # 7. Capture failure (low overlap risk)
        if mission and mission.estimated_captures > 0:
            expected_at_progress = int(
                mission.estimated_captures * packet.mission_progress_pct / 100.0
            )
            missed = expected_at_progress - packet.capture_count
            
            if missed >= policy.max_missed_captures_abort:
                new_warnings.append(HealthWarning(
                    condition="capture_failure_critical",
                    severity=HealthSeverity.CRITICAL,
                    message=f"Missed {missed} captures (abort threshold: {policy.max_missed_captures_abort})",
                    recommended_action=FailsafeAction.ABORT,
                    telemetry_sequence=packet.sequence,
                ))
            elif missed >= policy.max_missed_captures:
                new_warnings.append(HealthWarning(
                    condition="capture_failure",
                    severity=HealthSeverity.HIGH,
                    message=f"Missed {missed} captures (warn threshold: {policy.max_missed_captures})",
                    recommended_action=FailsafeAction.CONTINUE,
                    telemetry_sequence=packet.sequence,
                ))
        
        # 8. Storage check
        if state.storage_available_mb < policy.min_storage_mb:
            new_warnings.append(HealthWarning(
                condition="storage_low",
                severity=HealthSeverity.CRITICAL,
                message=f"Storage low: {state.storage_available_mb}MB < {policy.min_storage_mb}MB",
                recommended_action=FailsafeAction.RTL,
                telemetry_sequence=packet.sequence,
            ))
        
        # Record
        self._warnings.extend(new_warnings)
        
        for w in new_warnings:
            if w.severity in (HealthSeverity.CRITICAL, HealthSeverity.HIGH):
                logger.warning(f"[HealthMonitor] {w.severity.value}: {w.message}")
        
        return new_warnings
