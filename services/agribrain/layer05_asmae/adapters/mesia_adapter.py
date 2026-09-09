"""ASMAE Adapter for MESIA (Multi-Emission Spectrum Intelligence & Agriculture).

Converts MESIA BehaviourLikelihood proposals and Layer 0 evidence records into
native ASMAE ObservationEvent records with appropriate AuthorityVector restrictions.
Principle P-08: MESIA provides evidence proposals, ASMAE owns the biological posterior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..observation.contracts import ObservationEvent
from ..state.authority import AuthorityVector
from services.agribrain.mesia.contracts.behaviour import BehaviourLikelihood
from services.agribrain.mesia.assimilation.asmae_operator import ASMAEInnovationProposal
from services.agribrain.mesia.assimilation.layer0_spine import (
    EvidenceAdmissionStatus,
    Layer0EvidenceRecord,
)


class MesiaAsmaeAdapter:
    """Bridges MESIA Likelihood Proposals into ASMAE Observation Events.

    Enforces Principle P-08 (MESIA emits proposals; ASMAE owns posterior) and
    Principle P-10 (Fail-closed authority gating).
    """

    @staticmethod
    def to_asmae_observation_event(
        record: Layer0EvidenceRecord,
        plot_id: str,
        is_qualified_for_decision: bool = False,
    ) -> Optional[ObservationEvent]:
        """Convert an admitted Layer 0 MESIA evidence record into an ASMAE ObservationEvent."""
        if not record.is_usable_for_assimilation:
            return None

        proposal = record.proposal
        now = datetime.now(timezone.utc)

        # Principle P-08 Invariant: MESIA never claims state authority directly
        if proposal.authority_scope != "evidence_proposal":
            raise ValueError(
                f"Principle P-08 Violation: MESIA authority_scope must be 'evidence_proposal', got '{proposal.authority_scope}'"
            )

        # Gated Authority (Principles P-09 & P-10):
        # Only admit state_update if explicitly qualified by a CapabilityAuthorityRecord.
        # When admitted, ASMAE observation operator and Kalman gain weight the innovation.
        if is_qualified_for_decision:
            authority = AuthorityVector(
                visualization_allowed=True,
                state_update_allowed=True,
                diagnosis_allowed=True,
            )
            provider = "MESIA_OBSERVATORY"
            processing_level = "L0_QUALIFIED_INNOVATION"
        else:
            authority = AuthorityVector(
                visualization_allowed=False,
                state_update_allowed=False,
                diagnosis_allowed=False,
            )
            provider = "MESIA_QUALIFICATION_PENDING"
            processing_level = "L0_PROPOSAL_CONTAINED"

        return ObservationEvent(
            observation_id=f"asmae-mesia-{proposal.proposal_id}",
            source_family=f"MESIA_{proposal.target_state_variable.upper()}",
            sensor_id=f"mesia_radio_{proposal.microzone_id}",
            acquisition_time=proposal.created_at,
            valid_time=now,
            spatial_support_ref=f"microzone:{proposal.microzone_id}:{proposal.depth_stratum}",
            quality_ref=f"support:{proposal.confidence_support:.2f}:var:{proposal.observation_variance:.3f}",
            observation_operator_ref="mesia.assimilation.asmae_operator.ASMAEObservationOperator",
            uncertainty_model_ref="mesia.behaviour.likelihood_engine.BehaviourLikelihoodEngine",
            crs_epsg=4326,
            native_resolution_m=10.0,
            authority=authority,
            scene_id=proposal.native_lineage_hash[:16],
            provider=provider,
            processing_level=processing_level,
        )
