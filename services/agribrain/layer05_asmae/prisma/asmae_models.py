"""
V79A Phase 13: ASMAE Persistence DTOs.

Python dataclass DTOs for ASMAE artifact persistence.
These are the Python-side mirror of eventual Prisma schema models.

NOTE: Real Prisma migration (prisma/schema.prisma) is deferred.
These DTOs are sufficient for V80 Layer 1 integration readiness.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ASMAEArtifact:
    """Persistable ASMAE run artifact.

    One row per ASMAE run. Links to resolution decision,
    weak labels, and validation events.
    """
    id: str
    plot_id: str
    run_id: str
    schema_version: str
    status: str  # "success" | "partial" | "error"
    production_usable: bool
    resolution_m: int
    output_content_hash: str
    artifact_instance_hash: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    # Pipeline summary
    scene_stack_mode: str = "unknown"
    n_scenes_processed: int = 0
    enkf_mode: str = "unknown"
    radiometric_mode: str = "unknown"
    retro_status: str = "unknown"
    bma_status: str = "unknown"
    retro_score: float = 0.0
    bma_mean_disagreement: float = 0.0
    weak_label_count: int = 0
    weak_label_positive_weight_count: int = 0

    # Refs
    diagnostics_ref: str = ""
    provenance_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "plot_id": self.plot_id,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "status": self.status,
            "production_usable": self.production_usable,
            "resolution_m": self.resolution_m,
            "output_content_hash": self.output_content_hash,
            "artifact_instance_hash": self.artifact_instance_hash,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "scene_stack_mode": self.scene_stack_mode,
            "n_scenes_processed": self.n_scenes_processed,
            "enkf_mode": self.enkf_mode,
            "radiometric_mode": self.radiometric_mode,
            "retro_status": self.retro_status,
            "bma_status": self.bma_status,
            "retro_score": self.retro_score,
            "bma_mean_disagreement": self.bma_mean_disagreement,
            "weak_label_count": self.weak_label_count,
            "weak_label_positive_weight_count": self.weak_label_positive_weight_count,
        }


@dataclass
class ASMAEResolutionDecisionRecord:
    """Persistable resolution decision record.

    One row per resolution evaluation. Used for auditing
    resolution selection history per plot.
    """
    id: str
    plot_id: str
    run_id: str
    selected_m: int
    candidates_tested: List[int] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)
    safe_for_1m_claim: bool = False
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "plot_id": self.plot_id,
            "run_id": self.run_id,
            "selected_m": self.selected_m,
            "candidates_tested": self.candidates_tested,
            "reason_codes": self.reason_codes,
            "safe_for_1m_claim": self.safe_for_1m_claim,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class ValidationEvent:
    """Persistable validation event for ASMAE-Learn tracking."""
    id: str
    plot_id: str
    run_id: str
    event_type: str  # "retrovalidation" | "external" | "field_observation"
    retro_score: float = 0.0
    retro_status: str = "unknown"
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlotLearningMemory:
    """Persistable per-plot learning memory for ASMAE-Learn."""
    id: str
    plot_id: str
    n_runs: int = 0
    n_validations: int = 0
    best_retro_score: float = 0.0
    best_certified_resolution_m: int = 10
    last_run_id: str = ""
    last_run_at: Optional[datetime] = None
    drift_detected: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WeakTrainingLabel:
    """Persistable weak training label for ASMAE-Learn export."""
    id: str
    plot_id: str
    run_id: str
    microzone_id: str
    state_name: str
    state_index: int
    estimate: float
    uncertainty: float
    training_weight: float
    label_type: str = "weak_assimilated_reference"
    retro_score: float = 0.0
    bma_disagreement: float = 0.0
    certification_level: str = "provisional"
    resolution_m: int = 10
    zero_weight_reasons: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
