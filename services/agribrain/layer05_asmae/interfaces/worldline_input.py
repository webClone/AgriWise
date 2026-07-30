"""R5.0: Worldline input — ASMAE consumes an immutable snapshot reference.

Design rules:
  1. ASMAE must consume an exact WorldlineSnapshotRef, not perform a
     "latest" lookup during a scientific run.
  2. The ref is frozen (immutable) after creation.
  3. Evidence set cannot change between run identity creation and execution.
  4. The snapshot_hash ensures deterministic replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class WorldlineSnapshotRef:
    """Immutable reference to a specific worldline state.

    ASMAE consumes this exact object at the start of a scientific run.
    It must NOT perform an internal "latest" lookup, which would allow
    the evidence set to change between run identity creation and execution.
    """
    tenant_id: str
    namespace: str
    plot_id: str
    geometry_version: str
    head_event_id: str
    as_of_time: datetime
    evidence_cutoff_time: datetime
    snapshot_hash: str
    schema_version: str = "worldline_snapshot_ref_v2"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Check snapshot reference invariants."""
        if not self.tenant_id or not str(self.tenant_id).strip():
            raise ValueError("tenant_id is required")
        if not self.namespace or not str(self.namespace).strip():
            raise ValueError("namespace is required")
        if not self.plot_id or not str(self.plot_id).strip():
            raise ValueError("plot_id is required")
        if not self.geometry_version:
            raise ValueError("geometry_version is required")
        if not self.head_event_id:
            raise ValueError("head_event_id is required")
        if not self.snapshot_hash:
            raise ValueError("snapshot_hash is required")
        for name in ("as_of_time", "evidence_cutoff_time"):
            value = getattr(self, name)
            if not isinstance(value, datetime):
                raise ValueError(f"{name} must be a datetime")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.evidence_cutoff_time > self.as_of_time:
            raise ValueError(
                f"evidence_cutoff_time ({self.evidence_cutoff_time}) "
                f"cannot be after as_of_time ({self.as_of_time})"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "namespace": self.namespace,
            "plot_id": self.plot_id,
            "geometry_version": self.geometry_version,
            "head_event_id": self.head_event_id,
            "as_of_time": self.as_of_time.isoformat(),
            "evidence_cutoff_time": self.evidence_cutoff_time.isoformat(),
            "snapshot_hash": self.snapshot_hash,
            "schema_version": self.schema_version,
        }


def create_snapshot_ref(
    *,
    tenant_id: str,
    namespace: str,
    plot_id: str,
    geometry_version: str,
    head_event_id: str,
    as_of_time: datetime,
    evidence_cutoff_time: datetime,
    snapshot_hash: str,
) -> WorldlineSnapshotRef:
    """Create and validate a WorldlineSnapshotRef.

    This is the only sanctioned way ASMAE obtains a worldline reference.
    The orchestrator or world model service creates this BEFORE the
    ASMAE run begins.
    """
    ref = WorldlineSnapshotRef(
        tenant_id=tenant_id,
        namespace=namespace,
        plot_id=plot_id,
        geometry_version=geometry_version,
        head_event_id=head_event_id,
        as_of_time=as_of_time,
        evidence_cutoff_time=evidence_cutoff_time,
        snapshot_hash=snapshot_hash,
    )
    return ref
