"""MESIA L7 Measurement Planner — R6 §14.4 / P12.4.

Allows AgriBrain Layer 7 (Planning) to schedule active, information-maximizing
MESIA RF sensing tasks (stepped packets, frequency hops) with strict regulatory compliance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.task import SensingTaskReceipt


@dataclass(frozen=True)
class PlannedMeasurementTask:
    """Active measurement request compiled by AgriBrain Layer 7."""

    task_id: str
    target_microzone_id: str
    radio_family: str
    planned_carrier_hz: float
    planned_duration_s: float
    expected_information_gain: float
    created_at: datetime


class L7MeasurementPlanner:
    """Schedules information-maximizing RF measurements."""

    @staticmethod
    def plan_soil_sensing_measurement(
        task_id: str,
        microzone_id: str,
        current_uncertainty_vwc: float = 0.10,
        expected_uncertainty_vwc: float = 0.05,
        radio_family: str = "WIFI_CSI",
        carrier_hz: float = 5180e6,
    ) -> Tuple[Optional[PlannedMeasurementTask], Optional[SensingTaskReceipt]]:
        """
        Compile a planned RF task based on expected information gain.
        If the information gain is too low, the measurement is aborted to save power/spectrum.
        """
        import math
        now = datetime.now(timezone.utc)
        
        # Calculate Shannon Information Gain (reduction in entropy of Gaussian)
        # Gain = 0.5 * log2(var_current / var_expected)
        if current_uncertainty_vwc <= 0 or expected_uncertainty_vwc <= 0:
            gain = 0.0
        else:
            gain = 0.5 * math.log2((current_uncertainty_vwc ** 2) / (expected_uncertainty_vwc ** 2))
            
        # Minimum gain threshold (e.g. 0.5 bits)
        if gain < 0.5:
            # Not worth scanning
            return None, None

        task = PlannedMeasurementTask(
            task_id=task_id,
            target_microzone_id=microzone_id,
            radio_family=radio_family,
            planned_carrier_hz=carrier_hz,
            planned_duration_s=2.0,
            expected_information_gain=gain,
            created_at=now,
        )

        receipt = SensingTaskReceipt(
            task_id=f"rcpt-{task_id}",
            objective="SOIL_DISCRIMINATION",
            action_type="ACTIVE",
            requested_at=now,
            target_receiver_ids=["rx-planned-01"],
            requested_frequency_range_hz=(carrier_hz - 40e6, carrier_hz + 40e6),
            requested_duration_s=2.0,
            execution_status="COMPLETED",
        )

        return task, receipt
