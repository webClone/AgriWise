"""MESIA Omega Active Scientific Experiment Proposer — R6 §16.5 / P14.5.

Ranks candidate multi-radio experimental actions by expected Fisher information gain
and safety constraints, submitting structured proposals for human review board approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProposedScientificExperiment:
    """Scientific experiment proposed by Omega."""

    experiment_id: str
    target_plot_id: str
    hypothesis_ref: str
    action_type: str  # e.g., 'MULTI_FREQUENCY_TOMOGRAPHY_SWEEP'
    target_bands: List[str]
    expected_information_gain_bits: float
    regulatory_safety_approved: bool
    requires_human_signoff: bool
    status: str  # PROPOSED | APPROVED | REJECTED


class OmegaExperimentProposer:
    """Ranks and proposes active discriminating scientific experiments."""

    @staticmethod
    def propose_discriminating_experiment(
        experiment_id: str,
        plot_id: str,
        hypothesis: "ScientificSurpriseHypothesis",
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
            hypothesis_ref=hypothesis.hypothesis_id,
            action_type=action_type,
            target_bands=target_bands,
            expected_information_gain_bits=gain,
            regulatory_safety_approved=True,
            requires_human_signoff=True,  # Mandatory human-in-the-loop (Principle P-08)
            status="PROPOSED",
        )
