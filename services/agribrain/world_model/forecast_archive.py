"""R5.0: Forecast artifact and evaluation contracts.

Design rules:
  1. Forecast origin_time and valid_time are IMMUTABLE after creation.
  2. Future observations create ForecastEvaluations, not forecast mutations.
  3. Different weather/management scenarios produce different forecast identities.
  4. No post-origin evidence enters forecast initialization.
  5. Evaluation is in observation space, not hidden state space.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


FORECAST_SCHEMA_VERSION = "forecast_artifact_v1"
EVALUATION_SCHEMA_VERSION = "forecast_evaluation_v1"


class EvaluationSpace(Enum):
    """In what space the forecast was evaluated."""
    OBSERVATION_SPACE = "observation_space"
    INDEPENDENT_REFERENCE = "independent_reference"
    POSTERIOR_DIAGNOSTIC = "posterior_diagnostic"


class DomainStatus(Enum):
    """Whether the forecast was in-domain for the evaluated region/crop."""
    IN_DOMAIN = "in_domain"
    PARTIAL_SUPPORT = "partial_support"
    OUT_OF_DOMAIN = "out_of_domain"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ForecastArtifact:
    """Immutable forecast artifact.

    Once created, origin_time and valid_time cannot change.
    Different weather/management scenarios produce different forecast IDs.
    """
    forecast_id: str
    origin_belief_id: str
    origin_time: datetime
    valid_time: datetime
    horizon_days: float

    # Scenario identity
    weather_scenario_id: str = ""
    management_scenario_id: str = ""

    # Distribution references
    state_distribution_ref: Optional[str] = None
    observation_projection_ref: Optional[str] = None

    # Provenance
    model_version: str = ""
    calibration_version: str = ""

    # Schema
    schema_version: str = FORECAST_SCHEMA_VERSION

    def validate(self) -> None:
        """Check forecast immutability invariants."""
        if self.valid_time <= self.origin_time:
            raise ValueError(
                f"valid_time ({self.valid_time}) must be after "
                f"origin_time ({self.origin_time})"
            )
        actual_horizon = (
            self.valid_time - self.origin_time
        ).total_seconds() / 86400.0
        if abs(actual_horizon - self.horizon_days) > 1.0:
            raise ValueError(
                f"horizon_days ({self.horizon_days}) inconsistent with "
                f"origin-valid gap ({actual_horizon:.1f} days)"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "origin_belief_id": self.origin_belief_id,
            "origin_time": self.origin_time.isoformat(),
            "valid_time": self.valid_time.isoformat(),
            "horizon_days": self.horizon_days,
            "weather_scenario_id": self.weather_scenario_id,
            "management_scenario_id": self.management_scenario_id,
            "state_distribution_ref": self.state_distribution_ref,
            "observation_projection_ref": self.observation_projection_ref,
            "model_version": self.model_version,
            "calibration_version": self.calibration_version,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ForecastEvaluation:
    """Immutable evaluation of a forecast against later evidence.

    Created when new observations arrive AFTER a forecast's origin_time.
    The forecast itself is NEVER mutated.
    """
    evaluation_id: str
    forecast_id: str
    reference_evidence_ids: Tuple[str, ...] = ()
    evaluation_space: EvaluationSpace = EvaluationSpace.OBSERVATION_SPACE

    # Metrics (per-variable)
    metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Calibration
    calibration_bin: Optional[str] = None
    domain_status: DomainStatus = DomainStatus.UNKNOWN

    # Metadata
    evaluated_at: Optional[datetime] = None
    schema_version: str = EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "forecast_id": self.forecast_id,
            "reference_evidence_ids": list(self.reference_evidence_ids),
            "evaluation_space": self.evaluation_space.value,
            "metrics": dict(self.metrics),
            "calibration_bin": self.calibration_bin,
            "domain_status": self.domain_status.value,
            "evaluated_at": (
                self.evaluated_at.isoformat() if self.evaluated_at else None
            ),
            "schema_version": self.schema_version,
        }
