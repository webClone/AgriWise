"""Scientific Contracts — ASMAEObservationPayload — R5.0 / WP07.

Defines the strongly-typed physical observation payload for ASMAE assimilation.
Enforces physical units, depth strata, measurement variance, and truth class.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .numeric import finite_real


@dataclass(frozen=True)
class ASMAEObservationPayload:
    """Strongly-typed physical observation payload for ASMAE Kalman assimilation."""

    observation_id: str
    target_state_variable: str           # E.g. "root_zone_water", "canopy_water"
    microzone_id: str
    depth_stratum: str                   # "SURFACE_0_5CM", "ROOT_ZONE_5_30CM"
    observation_value: float             # Physical value y
    observation_units: str               # Must match target state units ("volumetric fraction [0,1]")
    observation_variance: float          # R variance in units^2
    forward_operator_id: str             # Operator used to map state to measurement
    calibration_certificate_id: str      # Required for operational promotion
    truth_class: str                     # "DERIVED_MODEL_INFERRED", "MEASURED_NATIVE"
    knowledge_cutoff: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observation_id:
            raise ValueError("observation_id must not be empty")
        value = finite_real(self.observation_value)
        variance = finite_real(self.observation_variance)
        if value is None:
            raise ValueError("observation_value must be a finite real scalar")
        if variance is None or variance <= 0.0:
            raise ValueError("observation_variance must be a finite strictly positive real scalar")
        object.__setattr__(self, "observation_value", value)
        object.__setattr__(self, "observation_variance", variance)
        if not isinstance(self.observation_units, str) or not self.observation_units.strip():
            raise ValueError("observation_units must not be empty")
        if self.target_state_variable == "root_zone_water":
            if self.observation_units != "volumetric fraction [0,1]":
                raise ValueError(
                    f"Invalid units for root_zone_water: expected 'volumetric fraction [0,1]', got {self.observation_units!r}"
                )
            if not (0.0 <= value <= 0.65):
                raise ValueError(
                    f"Physical boundary violation for root_zone_water: value {self.observation_value} is outside realistic soil porosity range [0.0, 0.65]"
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "target_state_variable": self.target_state_variable,
            "microzone_id": self.microzone_id,
            "depth_stratum": self.depth_stratum,
            "observation_value": self.observation_value,
            "observation_units": self.observation_units,
            "observation_variance": self.observation_variance,
            "forward_operator_id": self.forward_operator_id,
            "calibration_certificate_id": self.calibration_certificate_id,
            "truth_class": self.truth_class,
            "knowledge_cutoff": self.knowledge_cutoff.isoformat() if isinstance(self.knowledge_cutoff, datetime) else str(self.knowledge_cutoff),
            "metadata": self.metadata,
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
