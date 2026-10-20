from __future__ import annotations
try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real
"""MESIA ASMAE Observation Operator — R6 §11.6 / P9.6.

Translates qualified BehaviourLikelihood proposals into state innovations and observation
covariances for ASMAE assimilation while strictly enforcing Principle P-08.
"""


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
    innovation_value: Optional[float]  # y - h(x_prior), None if absent
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
        """Construct calibrated innovation proposal.

        Monograph Finding #15: Never treats dimensionless likelihood scores as volumetric water content.
        Preserves missingness: does not fabricate a 0.0 innovation when observation is absent.
        """
        # Principle P-08 check: MESIA never claims state authority
        if likelihood.authority_scope != "evidence_proposal":
            raise ValueError(f"Principle P-08 violation: MESIA authority_scope must be 'evidence_proposal', got {likelihood.authority_scope}")

        fin_innov = finite_real(likelihood.innovation)
        fin_cov = finite_real(likelihood.covariance)
        fin_support = finite_real(likelihood.support)

        innovation = float(fin_innov) if fin_innov is not None else None
        if likelihood.covariance is None:
            variance = 0.25  # documented model default for truly absent covariance
        elif fin_cov is not None and fin_cov > 0.0:
            variance = float(fin_cov)
        else:
            variance = None  # Explicit invalid, boolean, or non-positive covariance fails closed
        support = float(fin_support) if (fin_support is not None and fin_support > 0.0) else 0.0

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

    @staticmethod
    def from_calibrated_inversion(
        inverted_vwc: float,
        prior_state_vwc: float,
        variance: float,
        support: float,
        microzone_id: str,
        depth_stratum: str = "ROOT_ZONE_5_30CM",
        native_lineage_hash: str = "",
        proposal_id: Optional[str] = None,
        target_state_variable: str = "root_zone_water",
    ) -> ASMAEInnovationProposal:
        """Construct innovation proposal from calibrated physical inversion (e.g. Topp dielectric model).

        Ensures physical units match target variable and obeys realistic moisture bounds.
        """
        if target_state_variable == "root_zone_water" and not (0.0 <= inverted_vwc <= 0.65):
            raise ValueError(
                f"Physical boundary violation: inverted VWC {inverted_vwc} outside realistic soil range [0.0, 0.65]"
            )
        if variance <= 0.0:
            raise ValueError(f"observation_variance must be strictly positive, got {variance}")

        now = datetime.now(timezone.utc)
        pid = proposal_id or f"innov-inv-{now.strftime('%Y%m%d%H%M%S')}"
        return ASMAEInnovationProposal(
            proposal_id=pid,
            target_state_variable=target_state_variable,
            microzone_id=microzone_id,
            depth_stratum=depth_stratum,
            innovation_value=round(inverted_vwc - prior_state_vwc, 6),
            observation_variance=variance,
            confidence_support=support,
            authority_scope="evidence_proposal",
            native_lineage_hash=native_lineage_hash,
            likelihood_ref="calibrated_physical_inversion",
            created_at=now,
        )

    @staticmethod
    def from_ensemble_likelihood(
        observed_feature: float,
        ensemble_states: List[float],
        forward_operator_fn: Any,
        observation_variance: float = 0.01,
    ) -> List[float]:
        """Evaluate observation likelihood across ensemble members to update particle weights.

        Guarantees likelihood space integration without subtracting probabilities from moisture.
        """
        import math
        weights = []
        for state in ensemble_states:
            predicted_obs = forward_operator_fn(state)
            error = observed_feature - predicted_obs
            w = math.exp(-0.5 * (error ** 2) / max(1e-6, observation_variance))
            weights.append(w)
        total = sum(weights) or 1.0
        return [round(w / total, 6) for w in weights]
