"""
Drone Control — Preflight Gate.

Validates dispatch feasibility before mission upload. Preserves the
hard gate already established in drone_mission/safety_rules.py:
leaf-level full-plot missions are rejected.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple
import logging
import math

from .schemas import (
    DispatchRequest,
    FailsafePolicy,
    VehicleState,
    WeatherSnapshot,
)

logger = logging.getLogger(__name__)


@dataclass
class PreflightCheck:
    """Result of a single preflight check."""
    name: str
    passed: bool
    message: str = ""


@dataclass 
class PreflightResult:
    """Aggregated preflight result."""
    passed: bool = True
    checks: List[PreflightCheck] = field(default_factory=list)
    
    @property
    def failure_reasons(self) -> List[str]:
        return [c.message for c in self.checks if not c.passed]
    
    @property
    def summary(self) -> str:
        failed = [c for c in self.checks if not c.passed]
        if not failed:
            return "All preflight checks passed"
        return "; ".join(c.message for c in failed)


class PreflightGate:
    """Pre-dispatch validation.
    
    Checks are ordered by severity. If any critical check fails,
    the entire preflight fails.
    """
    
    def evaluate(
        self,
        request: DispatchRequest,
        vehicle_state: VehicleState,
    ) -> PreflightResult:
        """Run all preflight checks.
        
        Args:
            request: The dispatch request
            vehicle_state: Current vehicle state
            
        Returns:
            PreflightResult with all check outcomes
        """
        result = PreflightResult()
        policy = request.failsafe_policy
        
        # Run checks in order
        checks = [
            self._check_mode_feasibility(request),
            self._check_battery(vehicle_state, policy, request),
            self._check_gps(vehicle_state, policy),
            self._check_wind(request.weather, policy),
            self._check_storage(vehicle_state),
            self._check_launch_point(request),
            self._check_camera(vehicle_state),
            self._check_connection(vehicle_state),
        ]
        
        result.checks = checks
        result.passed = all(c.passed for c in checks)
        
        if not result.passed:
            logger.warning(f"[Preflight] FAILED: {result.summary}")
        else:
            logger.info("[Preflight] All checks passed")
        
        return result
    
    def _check_mode_feasibility(self, request: DispatchRequest) -> PreflightCheck:
        """Enforce mode-specific feasibility rules.
        
        Hard gate: leaf-level GSD (< 1.0 cm) over full-plot is rejected.
        Leaf-level is reserved for Command/Revisit mode.
        """
        intent = request.intent
        if intent is None:
            return PreflightCheck(name="mode_feasibility", passed=True, message="No intent — skipped")
        
        flight_mode = getattr(intent, 'flight_mode', None)
        if flight_mode is None:
            return PreflightCheck(name="mode_feasibility", passed=True, message="No flight mode — skipped")
        
        mode_val = flight_mode.value if hasattr(flight_mode, 'value') else str(flight_mode)
        mission_type = getattr(intent, 'mission_type', None)
        mission_type_val = mission_type.value if hasattr(mission_type, 'value') else str(mission_type) if mission_type else ""
        target_gsd = getattr(intent, 'target_gsd_cm', 2.0)
        
        # Hard gate: leaf-level full-plot mapping is impossible
        if mode_val == "mapping_mode" and target_gsd < 1.0:
            return PreflightCheck(
                name="mode_feasibility",
                passed=False,
                message=(
                    f"MAPPING_MODE rejects GSD < 1.0cm (requested {target_gsd}cm). "
                    f"Leaf-level mapping over entire plots is unrealistic. "
                    f"Use COMMAND_REVISIT_MODE for close-up inspection."
                ),
            )
        
        return PreflightCheck(name="mode_feasibility", passed=True, message="Mode feasible")
    
    def _check_battery(
        self,
        state: VehicleState,
        policy: FailsafePolicy,
        request: DispatchRequest,
    ) -> PreflightCheck:
        """Check battery is sufficient for the mission."""
        # Must be above critical threshold before even starting
        if state.battery_pct < policy.battery_critical_pct:
            return PreflightCheck(
                name="battery",
                passed=False,
                message=f"Battery {state.battery_pct:.0f}% below critical threshold {policy.battery_critical_pct:.0f}%",
            )
        
        # Estimate mission battery consumption
        plan = request.flight_plan
        if plan:
            est_time_min = getattr(plan, 'estimated_flight_time_min', 0)
            # Rough: ~1.5% per minute for prosumer drones
            estimated_usage = est_time_min * 1.5
            remaining_after = state.battery_pct - estimated_usage
            
            if remaining_after < policy.battery_critical_pct:
                return PreflightCheck(
                    name="battery",
                    passed=False,
                    message=(
                        f"Battery {state.battery_pct:.0f}% insufficient for "
                        f"estimated {est_time_min:.1f}min flight. "
                        f"Estimated remaining: {remaining_after:.0f}% "
                        f"(critical: {policy.battery_critical_pct:.0f}%)"
                    ),
                )
        
        return PreflightCheck(name="battery", passed=True, message=f"Battery OK ({state.battery_pct:.0f}%)")
    
    def _check_gps(self, state: VehicleState, policy: FailsafePolicy) -> PreflightCheck:
        """Check GPS fix quality."""
        if not state.gps_fix:
            return PreflightCheck(name="gps", passed=False, message="No GPS fix")
        
        if state.gps_satellites < policy.min_gps_satellites:
            return PreflightCheck(
                name="gps",
                passed=False,
                message=f"GPS satellites {state.gps_satellites} below minimum {policy.min_gps_satellites}",
            )
        
        if state.gps_hdop > policy.min_gps_fix_quality:
            return PreflightCheck(
                name="gps",
                passed=False,
                message=f"GPS HDOP {state.gps_hdop:.1f} exceeds maximum {policy.min_gps_fix_quality:.1f}",
            )
        
        return PreflightCheck(name="gps", passed=True, message=f"GPS OK ({state.gps_satellites} sats, HDOP {state.gps_hdop:.1f})")
    
    def _check_wind(self, weather: WeatherSnapshot, policy: FailsafePolicy) -> PreflightCheck:
        """Check wind conditions."""
        if weather.wind_speed_m_s > policy.max_wind_m_s:
            return PreflightCheck(
                name="wind",
                passed=False,
                message=f"Wind {weather.wind_speed_m_s:.1f}m/s exceeds safe threshold {policy.max_wind_m_s:.1f}m/s",
            )
        
        if weather.wind_gust_m_s > policy.max_wind_gust_m_s:
            return PreflightCheck(
                name="wind",
                passed=False,
                message=f"Wind gusts {weather.wind_gust_m_s:.1f}m/s exceed safe threshold {policy.max_wind_gust_m_s:.1f}m/s",
            )
        
        if weather.precipitation:
            return PreflightCheck(
                name="wind",
                passed=False,
                message="Active precipitation — flight unsafe",
            )
        
        return PreflightCheck(name="wind", passed=True, message=f"Wind OK ({weather.wind_speed_m_s:.1f}m/s)")
    
    def _check_storage(self, state: VehicleState) -> PreflightCheck:
        """Check available storage on vehicle."""
        if state.storage_available_mb < 500:
            return PreflightCheck(
                name="storage",
                passed=False,
                message=f"Storage {state.storage_available_mb}MB below 500MB minimum",
            )
        return PreflightCheck(name="storage", passed=True, message=f"Storage OK ({state.storage_available_mb}MB)")
    
    def _check_launch_point(self, request: DispatchRequest) -> PreflightCheck:
        """Check launch point sanity."""
        if request.launch_lat == 0.0 and request.launch_lon == 0.0:
            # Not set — acceptable for mock, warning for real
            if request.driver_type != "mock":
                return PreflightCheck(
                    name="launch_point",
                    passed=False,
                    message="Launch point not set (lat=0, lon=0)",
                )
        return PreflightCheck(name="launch_point", passed=True, message="Launch point OK")
    
    def _check_camera(self, state: VehicleState) -> PreflightCheck:
        """Check camera readiness."""
        if not state.camera_ready:
            return PreflightCheck(name="camera", passed=False, message="Camera not ready")
        return PreflightCheck(name="camera", passed=True, message="Camera OK")
    
    def _check_connection(self, state: VehicleState) -> PreflightCheck:
        """Check vehicle connection."""
        if state.link_quality_pct < 10:
            return PreflightCheck(
                name="connection",
                passed=False,
                message=f"Link quality {state.link_quality_pct:.0f}% too low",
            )
        return PreflightCheck(name="connection", passed=True, message="Connection OK")
