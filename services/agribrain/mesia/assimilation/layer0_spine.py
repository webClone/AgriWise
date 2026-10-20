from __future__ import annotations
try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real
"""MESIA Layer 0 Canonical Evidence Spine — R6 §11.7 / P9.7.

Manages evidence lifecycle admission, absence, quarantine, and invalidation
into AgriBrain's Layer 0 canonical evidence spine.
"""


from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .asmae_operator import ASMAEInnovationProposal


class EvidenceAdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"            # Valid, verified, and admitted to Layer 0
    QUARANTINED = "QUARANTINED"      # Calibration drift or epoch transition hold
    INVALIDATED = "INVALIDATED"      # Hard out-of-tolerance failure
    ABSENT = "ABSENT"                # Expected emission missing / blind band
    REVOKED = "REVOKED"              # Capability authority withdrawn


@dataclass(frozen=True)
class Layer0EvidenceRecord:
    """Immutable entry in AgriBrain's Layer 0 evidence spine."""

    record_id: str
    status: EvidenceAdmissionStatus
    proposal: ASMAEInnovationProposal
    admission_notes: str
    is_usable_for_assimilation: bool


class Layer0EvidenceSpine:
    """Manages admission gates for Layer 0 evidence."""

    @staticmethod
    def evaluate_admission(
        proposal: ASMAEInnovationProposal,
        is_calibration_valid: bool = False,
        is_epoch_active: bool = False,
    ) -> Layer0EvidenceRecord:
        """Evaluate admission criteria before ingestion into ASMAE state estimator.

        CONTAINMENT (Audit Finding #6): Defaults to fail-closed.
        Callers must explicitly prove calibration validity and epoch status.
        Calibration and epoch failures take precedence over observation absence:
        an uncalibrated sensor is INVALIDATED regardless of whether it also has
        missing innovation, because the root cause is calibration failure.
        """
        if not is_calibration_valid:
            return Layer0EvidenceRecord(
                record_id=f"l0-rec-{proposal.proposal_id}",
                status=EvidenceAdmissionStatus.INVALIDATED,
                proposal=proposal,
                admission_notes="Calibration state invalid or expired",
                is_usable_for_assimilation=False,
            )

        if not is_epoch_active:
            return Layer0EvidenceRecord(
                record_id=f"l0-rec-{proposal.proposal_id}",
                status=EvidenceAdmissionStatus.QUARANTINED,
                proposal=proposal,
                admission_notes="Epoch transition in progress; quarantined pending re-baselining",
                is_usable_for_assimilation=False,
            )

        # Numeric qualification: finite innovation, strictly positive support and variance
        fin_innov = finite_real(proposal.innovation_value)
        fin_support = finite_real(proposal.confidence_support)
        fin_var = finite_real(proposal.observation_variance)

        if (
            fin_innov is None
            or fin_support is None
            or fin_support <= 0.0
            or fin_var is None
            or fin_var <= 0.0
        ):
            return Layer0EvidenceRecord(
                record_id=f"l0-rec-{proposal.proposal_id}",
                status=EvidenceAdmissionStatus.ABSENT,
                proposal=proposal,
                admission_notes="Observation missing, non-finite, or confidence support / variance is non-positive",
                is_usable_for_assimilation=False,
            )

        return Layer0EvidenceRecord(
            record_id=f"l0-rec-{proposal.proposal_id}",
            status=EvidenceAdmissionStatus.ADMITTED,
            proposal=proposal,
            admission_notes="Proposal meets all Layer 0 integrity gates",
            is_usable_for_assimilation=True,
        )
