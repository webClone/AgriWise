"""R5.0: Standard Stage Receipt Contract.

Separates operational execution status from scientific usability, providing
immutable lineage, degradation records, and invariant violation reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class ScientificUsability(str, Enum):
    USABLE = "usable"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


@dataclass(frozen=True)
class StageReceipt:
    """Standard execution receipt separating execution status from scientific usability."""

    stage_id: str
    execution_status: ExecutionStatus = ExecutionStatus.SUCCESS
    scientific_usability: ScientificUsability = ScientificUsability.USABLE
    run_id: str = ""
    input_evidence_hashes: Tuple[str, ...] = ()
    output_payload_hash: str = ""
    missing_inputs: Tuple[str, ...] = ()
    degradation_reasons: Tuple[str, ...] = ()
    invariant_violations: Tuple[Dict[str, Any], ...] = ()
    audit_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "execution_status": self.execution_status.value,
            "scientific_usability": self.scientific_usability.value,
            "run_id": self.run_id,
            "input_evidence_hashes": list(self.input_evidence_hashes),
            "output_payload_hash": self.output_payload_hash,
            "missing_inputs": list(self.missing_inputs),
            "degradation_reasons": list(self.degradation_reasons),
            "invariant_violations": list(self.invariant_violations),
            "audit_metadata": dict(self.audit_metadata),
        }
