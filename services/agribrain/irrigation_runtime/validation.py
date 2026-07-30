"""
Irrigation Runtime — Closed-Loop Validation v1.0.0

Post-irrigation soil moisture verification engine. Uses the sensor_runtime
pipeline to measure actual moisture response after irrigation and compares
against the expected response based on applied volume, soil properties,
and Total Available Water (TAW).

Pipeline:
  IrrigationEvent COMPLETED
    → 30min validation window opens
    → Query soil_moisture_vwc from linked sensors
    → Compute expected VWC rise (volume / TAW / root depth)
    → Compare actual vs expected
    → Generate ValidationReport
    → Feed calibration proposal to L6

Outcomes:
  CONFIRMED:       actual_rise >= 50% of expected (within tolerance)
  UNDER_DELIVERY:  actual_rise < 50% of expected
  OVER_DELIVERY:   actual_rise > 150% of expected
  NO_RESPONSE:     no detectable moisture change
  SENSOR_OFFLINE:  validation sensors unreachable
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from irrigation_runtime.schemas import (
    IrrigationEvent,
    IrrigationSystemType,
    ValidationOutcome,
    ValidationReport,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Soil Parameters for VWC Estimation
# ============================================================================

# Typical TAW (Total Available Water) by soil texture (mm/m depth)
SOIL_TAW_MM_PER_M = {
    "sand": 80,
    "loamy_sand": 100,
    "sandy_loam": 130,
    "loam": 170,
    "silt_loam": 200,
    "silt": 210,
    "sandy_clay_loam": 140,
    "clay_loam": 180,
    "silty_clay_loam": 190,
    "sandy_clay": 130,
    "silty_clay": 170,
    "clay": 150,
}

# Field capacity VWC by soil texture (fraction)
SOIL_FIELD_CAPACITY = {
    "sand": 0.12,
    "loamy_sand": 0.15,
    "sandy_loam": 0.22,
    "loam": 0.30,
    "silt_loam": 0.34,
    "silt": 0.36,
    "sandy_clay_loam": 0.28,
    "clay_loam": 0.35,
    "silty_clay_loam": 0.38,
    "sandy_clay": 0.32,
    "silty_clay": 0.40,
    "clay": 0.42,
}


class IrrigationValidator:
    """Post-irrigation closed-loop moisture verification.

    Compares actual soil moisture change against predicted response
    to detect under/over-delivery and calibrate future applications.
    """

    def __init__(self):
        self._validation_window_minutes = 30
        self._pending_validations: Dict[str, Dict[str, Any]] = {}
        self._reports: List[ValidationReport] = []

        # Outcome thresholds
        self._under_delivery_ratio = 0.50   # actual < 50% of expected
        self._over_delivery_ratio = 1.50    # actual > 150% of expected
        self._min_detectable_rise = 0.005   # 0.5% VWC minimum

    # ================================================================
    # Validation Window Management
    # ================================================================

    def open_validation_window(
        self,
        event: IrrigationEvent,
        pre_irrigation_vwc: float,
        soil_type: str = "loam",
        root_depth_m: float = 0.6,
        sensor_device_ids: Optional[List[str]] = None,
    ) -> str:
        """Open a validation window for a completed irrigation event.

        Args:
            event: The completed IrrigationEvent
            pre_irrigation_vwc: Soil moisture VWC before irrigation
            soil_type: Soil texture classification
            root_depth_m: Effective root zone depth (m)
            sensor_device_ids: IDs of soil moisture sensors to monitor

        Returns:
            Validation window ID
        """
        window_id = f"VAL-{uuid.uuid4().hex[:12]}"

        # Calculate expected VWC rise
        expected_rise = self._estimate_vwc_rise(
            volume_mm=event.target_volume_mm,
            soil_type=soil_type,
            root_depth_m=root_depth_m,
            efficiency=event.application_efficiency,
        )

        self._pending_validations[window_id] = {
            "event_id": event.event_id,
            "plot_id": event.plot_id,
            "zone_id": event.zone_id,
            "pre_irrigation_vwc": pre_irrigation_vwc,
            "expected_vwc_rise": expected_rise,
            "soil_type": soil_type,
            "root_depth_m": root_depth_m,
            "sensor_device_ids": sensor_device_ids or [],
            "window_opened_at": datetime.now(timezone.utc),
            "window_closes_at": datetime.now(timezone.utc) + timedelta(
                minutes=self._validation_window_minutes
            ),
            "readings": [],
        }

        logger.info(
            "Validation window opened for event %s: expecting +%.3f VWC "
            "(volume=%.1fmm, soil=%s, root=%.1fm)",
            event.event_id, expected_rise,
            event.target_volume_mm, soil_type, root_depth_m,
        )

        return window_id

    def add_reading(
        self,
        window_id: str,
        vwc_reading: float,
        sensor_id: str = "",
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a soil moisture reading to the validation window.

        Called each time a sensor_runtime update arrives for a monitored sensor.
        """
        window = self._pending_validations.get(window_id)
        if not window:
            return

        window["readings"].append({
            "vwc": vwc_reading,
            "sensor_id": sensor_id,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        })

    def close_validation_window(self, window_id: str) -> Optional[ValidationReport]:
        """Close a validation window and generate the report.

        Should be called after the validation window duration has elapsed.
        """
        window = self._pending_validations.pop(window_id, None)
        if not window:
            return None

        readings = window["readings"]
        pre_vwc = window["pre_irrigation_vwc"]
        expected_rise = window["expected_vwc_rise"]

        if not readings:
            # No sensor data received
            report = self._create_report(
                window,
                outcome=ValidationOutcome.SENSOR_OFFLINE,
                post_vwc=pre_vwc,
                actual_rise=0.0,
            )
            self._reports.append(report)
            return report

        # Calculate post-irrigation VWC (average of last 3 readings)
        sorted_readings = sorted(readings, key=lambda r: r["timestamp"])
        recent = sorted_readings[-min(3, len(sorted_readings)):]
        post_vwc = sum(r["vwc"] for r in recent) / len(recent)
        actual_rise = post_vwc - pre_vwc

        # Determine outcome
        outcome = self._determine_outcome(actual_rise, expected_rise)

        # Build report
        report = self._create_report(
            window,
            outcome=outcome,
            post_vwc=post_vwc,
            actual_rise=actual_rise,
            reading_count=len(readings),
        )

        self._reports.append(report)

        logger.info(
            "Validation complete for event %s: %s "
            "(expected +%.3f, actual +%.3f, ratio=%.2f)",
            window["event_id"], outcome.value,
            expected_rise, actual_rise,
            actual_rise / expected_rise if expected_rise > 0 else 0,
        )

        return report

    # ================================================================
    # VWC Estimation
    # ================================================================

    def _estimate_vwc_rise(
        self,
        volume_mm: float,
        soil_type: str,
        root_depth_m: float,
        efficiency: float,
    ) -> float:
        """Estimate expected VWC rise from irrigation volume.

        Uses a simple bucket model:
          Δθ = (V_net × efficiency) / (root_depth_mm)

        Where:
          - V_net is net irrigation volume (mm)
          - efficiency is application efficiency
          - root_depth_mm is root zone depth in mm
        """
        # Net volume reaching the root zone
        net_volume_mm = volume_mm * efficiency

        # Root zone depth in mm
        root_depth_mm = root_depth_m * 1000

        # VWC rise (volumetric)
        # 1mm of water over 1m² = 1 liter = 0.001 m³
        # VWC = volume of water / volume of soil
        # For a root zone: Δθ = V_mm / root_depth_mm
        vwc_rise = net_volume_mm / root_depth_mm

        # Clamp to realistic range
        field_capacity = SOIL_FIELD_CAPACITY.get(soil_type, 0.30)
        max_rise = field_capacity * 0.5  # Can't exceed half of FC in one event

        return min(vwc_rise, max_rise)

    def _determine_outcome(
        self,
        actual_rise: float,
        expected_rise: float,
    ) -> ValidationOutcome:
        """Classify the irrigation delivery outcome."""
        if expected_rise <= 0:
            return ValidationOutcome.NO_RESPONSE

        if actual_rise < self._min_detectable_rise:
            return ValidationOutcome.NO_RESPONSE

        ratio = actual_rise / expected_rise

        if ratio < self._under_delivery_ratio:
            return ValidationOutcome.UNDER_DELIVERY
        elif ratio > self._over_delivery_ratio:
            return ValidationOutcome.OVER_DELIVERY
        else:
            return ValidationOutcome.CONFIRMED

    # ================================================================
    # Report Generation
    # ================================================================

    def _create_report(
        self,
        window: Dict[str, Any],
        outcome: ValidationOutcome,
        post_vwc: float,
        actual_rise: float,
        reading_count: int = 0,
    ) -> ValidationReport:
        """Build a full validation report."""
        pre_vwc = window["pre_irrigation_vwc"]
        expected_rise = window["expected_vwc_rise"]

        # Delivery efficiency
        delivery_eff = actual_rise / expected_rise if expected_rise > 0 else 0.0

        # Calibration adjustment: how much to adjust future volume
        # > 1.0 means we need to apply more, < 1.0 means less
        if delivery_eff > 0:
            calibration_adj = 1.0 / delivery_eff
        else:
            calibration_adj = 1.5  # Increase by 50% if no response

        # Confidence based on reading count
        if reading_count >= 5:
            confidence = 0.95
        elif reading_count >= 3:
            confidence = 0.85
        elif reading_count >= 1:
            confidence = 0.70
        else:
            confidence = 0.10

        return ValidationReport(
            report_id=f"RPT-{uuid.uuid4().hex[:12]}",
            event_id=window["event_id"],
            plot_id=window["plot_id"],
            zone_id=window["zone_id"],
            outcome=outcome,
            pre_irrigation_vwc=round(pre_vwc, 4),
            post_irrigation_vwc=round(post_vwc, 4),
            expected_vwc_rise=round(expected_rise, 4),
            actual_vwc_rise=round(actual_rise, 4),
            irrigation_completed_at=window["window_opened_at"].isoformat(),
            validation_window_start=window["window_opened_at"].isoformat(),
            validation_window_end=window["window_closes_at"].isoformat(),
            sensor_readings_count=reading_count,
            sensor_device_ids=window["sensor_device_ids"],
            delivery_efficiency_actual=round(delivery_eff, 3),
            calibration_adjustment=round(calibration_adj, 3),
            confidence=confidence,
        )

    # ================================================================
    # Calibration Feedback
    # ================================================================

    def get_calibration_proposal(
        self,
        plot_id: str,
        n_recent: int = 5,
    ) -> Dict[str, Any]:
        """Generate a calibration proposal from recent validation reports.

        Averages delivery efficiency across recent events to propose
        an adjustment factor for future irrigation volumes.
        """
        plot_reports = [r for r in self._reports if r.plot_id == plot_id]
        recent = plot_reports[-n_recent:]

        if not recent:
            return {"adjustment_factor": 1.0, "confidence": 0.0, "sample_count": 0}

        # Filter to reports with sufficient confidence
        valid = [r for r in recent if r.confidence >= 0.7 and r.delivery_efficiency_actual > 0]
        if not valid:
            return {"adjustment_factor": 1.0, "confidence": 0.3, "sample_count": 0}

        avg_efficiency = sum(r.delivery_efficiency_actual for r in valid) / len(valid)
        avg_adjustment = 1.0 / avg_efficiency if avg_efficiency > 0 else 1.0

        # Clamp adjustment to ±50%
        avg_adjustment = max(0.5, min(1.5, avg_adjustment))

        avg_confidence = sum(r.confidence for r in valid) / len(valid)

        outcome_counts = {}
        for r in valid:
            key = r.outcome.value
            outcome_counts[key] = outcome_counts.get(key, 0) + 1

        return {
            "adjustment_factor": round(avg_adjustment, 3),
            "confidence": round(avg_confidence, 2),
            "sample_count": len(valid),
            "avg_delivery_efficiency": round(avg_efficiency, 3),
            "outcome_distribution": outcome_counts,
            "recommendation": (
                "Increase volume" if avg_adjustment > 1.1
                else "Decrease volume" if avg_adjustment < 0.9
                else "Maintain current volume"
            ),
        }

    # ================================================================
    # History
    # ================================================================

    def get_reports(
        self,
        plot_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ValidationReport]:
        """Get validation reports, optionally filtered by plot."""
        reports = self._reports
        if plot_id:
            reports = [r for r in reports if r.plot_id == plot_id]
        return reports[-limit:]

    def get_pending_validations(self) -> List[Dict[str, Any]]:
        """Get all open validation windows."""
        return [
            {
                "window_id": wid,
                "event_id": w["event_id"],
                "expected_rise": w["expected_vwc_rise"],
                "readings_count": len(w["readings"]),
                "closes_at": w["window_closes_at"].isoformat(),
            }
            for wid, w in self._pending_validations.items()
        ]


# Singleton
irrigation_validator = IrrigationValidator()
