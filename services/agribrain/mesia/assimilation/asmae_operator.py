"""MESIA ASMAE Observation Operator — R6 §11.6 / P9.6.

Translates qualified BehaviourLikelihood proposals into state innovations and observation
covariances for ASMAE assimilation while strictly enforcing Principle P-08.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.behaviour import BehaviourLikelihood


@dataclass(frozen=True)
class ASMAEInnovationProposal:
    """Calibrated innovation proposal submitted to ASMAE evidence spine."""

    proposal_id: str
    target_state_variable: str
    microzone_id: str
    depth_stratum: str
    innovation_value: float  # y - h(x_prior)
    observation_variance: float  # R covariance
    confidence_support: float
    authority_scope: str  # Must be "evidence_proposal" (Principle P-08)
    native_lineage_hash: str
    likelihood_ref: str
    created_at: datetime

    def content_hash(self) -> str:
        d = {
            "proposal_id": self.proposal_id,
            "target_state_variable": self.target_state_variable,
            "microzone_id": self.microzone_id,
            "depth_stratum": self.depth_stratum,
            "innovation_value": self.innovation_value,
            "observation_variance": self.observation_variance,
            "confidence_support": self.confidence_support,
            "authority_scope": self.authority_scope,
            "native_lineage_hash": self.native_lineage_hash,
            "likelihood_ref": self.likelihood_ref,
            "created_at": self.created_at.isoformat(),
        }
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ASMAEObservationOperator:
    """Translates MESIA behaviour likelihoods into ASMAE innovation proposals."""

    @staticmethod
    def create_innovation(
        likelihood: BehaviourLikelihood,
        prior_state_vwc: float,
        microzone_id: str,
        depth_stratum: str = "ROOT_ZONE_5_30CM",
    ) -> ASMAEInnovationProposal:
        """Construct calibrated innovation proposal."""
        # Principle P-08 check: MESIA never claims state authority
        if likelihood.authority_scope != "evidence_proposal":
            raise ValueError(f"Principle P-08 violation: MESIA authority_scope must be 'evidence_proposal', got {likelihood.authority_scope}")

        measured_vwc = likelihood.likelihood_value if likelihood.likelihood_value is not None else prior_state_vwc
        innovation = measured_vwc - prior_state_vwc
        variance = likelihood.covariance if likelihood.covariance is not None else 0.25
        support = likelihood.support if likelihood.support is not None else 0.80

        now = datetime.now(timezone.utc)

        return ASMAEInnovationProposal(
            proposal_id=f"innov-{likelihood.likelihood_id}",
            target_state_variable=likelihood.target_variable,
            microzone_id=microzone_id,
            depth_stratum=depth_stratum,
            innovation_value=innovation,
            observation_variance=variance,
            confidence_support=support,
            authority_scope="evidence_proposal",
            native_lineage_hash=likelihood.native_observation_ref,
            likelihood_ref=likelihood.likelihood_id,
            created_at=now,
        )
