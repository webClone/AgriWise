"""MESIA Omega Active Scientific Experiment Proposer — R6 §16.5 / P14.5.

Ranks candidate multi-radio experimental actions by expected Fisher information gain
and safety constraints, submitting structured proposals for human review board approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.agribrain.scientific_contracts.authority import AuthorityScope, AuthorityVector
from services.agribrain.scientific_contracts.exceptions import ContractViolation


@dataclass(frozen=True)
class ProposedScientificExperiment:
    """Scientific experiment proposed by Omega.

    Invariants (WP12 / P05.1):
    1. Reclassified as AuthorityScope.RESEARCH_ONLY.
    2. regulatory_safety_approved defaults to False.
    3. requires_human_signoff is mandatory True.
    4. Never receives PRESCRIPTION_DRIVER or MACHINE_EXECUTION authority receipts.
    """

    experiment_id: str
    target_plot_id: str
    hypothesis_ref: str
    action_type: str  # e.g., 'MULTI_FREQUENCY_TOMOGRAPHY_SWEEP'
    target_bands: List[str]
    expected_information_gain_bits: float
    regulatory_safety_approved: bool = False
    requires_human_signoff: bool = True
    authority_scope: AuthorityScope = AuthorityScope.RESEARCH_ONLY
    status: str = "PROPOSED"  # PROPOSED | APPROVED | REJECTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "target_plot_id": self.target_plot_id,
            "hypothesis_ref": self.hypothesis_ref,
            "action_type": self.action_type,
            "target_bands": list(self.target_bands),
            "expected_information_gain_bits": self.expected_information_gain_bits,
            "regulatory_safety_approved": self.regulatory_safety_approved,
            "requires_human_signoff": self.requires_human_signoff,
            "authority_scope": self.authority_scope.value,
            "status": self.status,
        }


def verify_omega_proposal_authority(
    proposal: ProposedScientificExperiment,
    requested_authority: Optional[AuthorityVector] = None,
) -> bool:
    """Verify that an Omega experiment proposal respects operational isolation boundaries.

    Invariant: Omega experiment proposals never receive PRESCRIPTION_DRIVER
    or MACHINE_EXECUTION authority receipts without safety court verification.
    """
    if proposal.authority_scope == AuthorityScope.RESEARCH_ONLY:
        if requested_authority is not None:
            if requested_authority.prescription_driver_allowed:
                raise ContractViolation(
                    "Omega research proposal cannot receive prescription_driver_allowed authority"
                )
            if requested_authority.machine_execution_allowed:
                raise ContractViolation(
                    "Omega research proposal cannot receive machine_execution_allowed authority"
                )

    if not proposal.regulatory_safety_approved:
        if requested_authority and requested_authority.machine_execution_allowed:
            raise ContractViolation(
                "Cannot authorize machine execution on an unapproved research proposal"
            )

    return True


class OmegaExperimentProposer:
    """Ranks and proposes active discriminating scientific experiments."""

    @staticmethod
    def propose_discriminating_experiment(
        experiment_id: str,
        plot_id: str,
        hypothesis: Any,
    ) -> ProposedScientificExperiment:
        """Design an active RF probing experiment scaled to the severity of the anomaly."""
        
        # Scale experiment aggression based on how surprising the hypothesis is
        kl_bits = getattr(hypothesis, "kl_divergence_bits", 2.0)
        
        if kl_bits > 10.0:
            action_type = "MULTI_FREQUENCY_TOMOGRAPHY_SWEEP"
            target_bands = ["868_MHZ_LORA", "2450_MHZ_WIFI", "5180_MHZ_WIFI", "60_GHZ_MMWAVE"]
            gain = kl_bits * 0.8
        elif kl_bits > 5.0:
            action_type = "DUAL_BAND_TRANSMISSION"
            target_bands = ["868_MHZ_LORA", "2450_MHZ_WIFI"]
            gain = kl_bits * 0.6
        else:
            action_type = "SINGLE_BAND_VERIFICATION"
            target_bands = ["2450_MHZ_WIFI"]
            gain = kl_bits * 0.4

        return ProposedScientificExperiment(
            experiment_id=experiment_id,
            target_plot_id=plot_id,
            hypothesis_ref=hypothesis.hypothesis_id if hasattr(hypothesis, "hypothesis_id") else str(hypothesis),
            action_type=action_type,
            target_bands=target_bands,
            expected_information_gain_bits=gain,
            regulatory_safety_approved=False,
            requires_human_signoff=True,  # Mandatory human-in-the-loop (Principle P-08)
            authority_scope=AuthorityScope.RESEARCH_ONLY,
            status="PROPOSED",
        )
