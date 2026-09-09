"""MESIA Sentinel & Independent Reference Fixtures — R6 §1.1, F5 & P8.

Models independent instrument sentinel references: cable loopbacks, 50-ohm loads,
calibrated noise sources, RF-absorbing negative control fixtures, and reference targets.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SentinelFixtureType(str, Enum):
    """Type of reference sentinel fixture."""
    CABLE_LOOPBACK = "CABLE_LOOPBACK"
    MATCHED_50_OHM_LOAD = "MATCHED_50_OHM_LOAD"
    CALIBRATED_NOISE_SOURCE = "CALIBRATED_NOISE_SOURCE"
    RF_ABSORBER_CHAMBER = "RF_ABSORBER_CHAMBER"
    RADAR_CALIBRATION_SPHERE = "RADAR_CALIBRATION_SPHERE"
    REFERENCE_RESONANT_TAG = "REFERENCE_RESONANT_TAG"


@dataclass(frozen=True)
class SentinelVerificationResult:
    """Outcome of a sentinel fixture health & baseline measurement check."""

    sentinel_id: str
    fixture_type: SentinelFixtureType
    verified_at: datetime
    nominal_baseline_value: float
    measured_value: float
    unit: str
    tolerance: float

    @property
    def deviation(self) -> float:
        return abs(self.measured_value - self.nominal_baseline_value)

    @property
    def is_healthy(self) -> bool:
        return self.deviation <= self.tolerance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentinel_id": self.sentinel_id,
            "fixture_type": self.fixture_type.value,
            "verified_at": self.verified_at.isoformat(),
            "nominal_baseline_value": self.nominal_baseline_value,
            "measured_value": self.measured_value,
            "deviation": self.deviation,
            "tolerance": self.tolerance,
            "unit": self.unit,
            "is_healthy": self.is_healthy,
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
