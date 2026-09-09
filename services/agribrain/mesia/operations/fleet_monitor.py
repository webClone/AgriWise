"""MESIA Fleet Operations & Health Monitoring — R6 §15.3 / P13.3.

Monitors observatory cluster uptime, battery autonomy, solar charging, packet loss,
and automated calibration expiry schedules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class NodeHealthSnapshot:
    """Telemetry and operational state of a physical observatory node."""

    node_id: str
    battery_level_pct: float
    solar_input_watts: float
    temperature_celsius: float
    packet_loss_pct: float
    calibration_age_days: int
    is_healthy: bool
    requires_maintenance: bool


class FleetOperationsMonitor:
    """Evaluates fleet telemetry across multi-site agricultural deployments."""

    @staticmethod
    def evaluate_node_health(
        node_id: str,
        battery_pct: float,
        solar_watts: float,
        temp_c: float,
        packet_loss: float,
        cal_days: int,
    ) -> NodeHealthSnapshot:
        """Assess whether an observatory node is operational or degraded."""
        import math

        # 1. Temperature-accelerated battery degradation (Arrhenius Law approximation)
        # Assuming nominal operation at 25C. Every 10C above 25C halves battery lifespan.
        acceleration_factor = 2.0 ** (max(0.0, temp_c - 25.0) / 10.0)
        effective_cal_days = cal_days * acceleration_factor

        # 2. Weibull Reliability Survival Probability R(t) = exp(-(t / eta)^beta)
        # Using shape parameter beta=1.5 (wear-out phase) and characteristic life eta=180 days
        beta = 1.5
        eta = 180.0
        survival_prob = math.exp(-((effective_cal_days / eta) ** beta))

        # 3. Dynamic Thresholds
        # Battery threshold raises if packet loss is high (needs more power to retransmit)
        min_battery = 20.0 + (packet_loss * 2.0)
        
        is_ok = (battery_pct >= min_battery) and (survival_prob > 0.50) and (temp_c <= 65.0)
        needs_maint = not is_ok or (survival_prob < 0.70) or (packet_loss > 5.0)

        return NodeHealthSnapshot(
            node_id=node_id,
            battery_level_pct=battery_pct,
            solar_input_watts=solar_watts,
            temperature_celsius=temp_c,
            packet_loss_pct=packet_loss,
            calibration_age_days=cal_days,
            is_healthy=is_ok,
            requires_maintenance=needs_maint,
        )
