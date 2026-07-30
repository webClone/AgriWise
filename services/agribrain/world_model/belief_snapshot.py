"""R5.0: Belief state snapshot contract.

Design rules:
  1. Every belief state carries a per-variable support ledger.
  2. Parameter and memory distributions are tracked separately.
  3. Authority vector is role-specific, not a single level.
  4. Schema version is embedded for future migration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from services.agribrain.scientific_contracts.authority import AuthorityVector, ScientificProductEnvelope
from services.agribrain.scientific_contracts.resolution import ResolutionContract
from services.agribrain.scientific_contracts.state_schema_ref import STATE_SCHEMA_VERSION


BELIEF_SNAPSHOT_SCHEMA_VERSION = "belief_snapshot_v1"


@dataclass(frozen=True)
class BeliefStateSnapshot:
    """Immutable snapshot of ASMAE belief state for a plot.

    This is the primary output of an ASMAE assimilation run.
    It represents the posterior distribution over the agricultural
    state at a specific point in time, with per-variable support
    and authority metadata.
    """
    belief_id: str
    plot_id: str
    geometry_version: str
    as_of: datetime
    authority: AuthorityVector
    parent_belief_id: Optional[str] = None

    # State distributions (references to numpy artifact files)
    state_distribution_ref: Optional[str] = None
    parameter_distribution_ref: Optional[str] = None
    memory_distribution_ref: Optional[str] = None

    # Per-variable support
    support_ledger: Optional[PerVariableSupportLedger] = None

    # Model provenance
    model_version: str = ""
    calibration_version: str = ""
    evidence_cutoff: Optional[datetime] = None

    # Resolution
    resolution: Optional[ResolutionContract] = None

    # Schema
    schema_version: str = BELIEF_SNAPSHOT_SCHEMA_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for name in ("belief_id", "plot_id", "geometry_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.as_of, datetime):
            raise ValueError("as_of must be a datetime")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if not isinstance(self.authority, AuthorityVector):
            raise ValueError("authority must be an AuthorityVector")
        if self.evidence_cutoff is not None:
            if not isinstance(self.evidence_cutoff, datetime):
                raise ValueError("evidence_cutoff must be a datetime")
            if (
                self.evidence_cutoff.tzinfo is None
                or self.evidence_cutoff.utcoffset() is None
            ):
                raise ValueError("evidence_cutoff must be timezone-aware")
            if self.evidence_cutoff > self.as_of:
                raise ValueError("evidence_cutoff cannot be after as_of")
        if self.resolution is not None and not isinstance(
            self.resolution, ResolutionContract
        ):
            raise ValueError("resolution must be a ResolutionContract")

    def to_dict(self) -> Dict[str, Any]:
        """Serializable representation."""
        return {
            "belief_id": self.belief_id,
            "plot_id": self.plot_id,
            "geometry_version": self.geometry_version,
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "parent_belief_id": self.parent_belief_id,
            "state_distribution_ref": self.state_distribution_ref,
            "parameter_distribution_ref": self.parameter_distribution_ref,
            "memory_distribution_ref": self.memory_distribution_ref,
            "support_ledger": (
                self.support_ledger.to_dict() if self.support_ledger else None
            ),
            "model_version": self.model_version,
            "calibration_version": self.calibration_version,
            "evidence_cutoff": (
                self.evidence_cutoff.isoformat() if self.evidence_cutoff else None
            ),
            "authority": {
                "visualization_allowed": self.authority.visualization_allowed,
                "state_update_allowed": self.authority.state_update_allowed,
                "diagnosis_allowed": self.authority.diagnosis_allowed,
                "training_allowed": self.authority.training_allowed,
                "prescription_driver_allowed": self.authority.prescription_driver_allowed,
                "insurance_allowed": self.authority.insurance_allowed,
                "machine_execution_allowed": self.authority.machine_execution_allowed,
            },
            "resolution": self.resolution.to_dict() if self.resolution else None,
            "schema_version": self.schema_version,
            "state_schema_version": self.state_schema_version,
        }
