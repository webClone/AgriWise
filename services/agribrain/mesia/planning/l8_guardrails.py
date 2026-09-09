"""MESIA L8 Policy Guardrails Engine — R6 §14.5 / P12.5.

Enforces AgriBrain Layer 8 policy constraints, uncertainty thresholds,
and human confirmation requirements before MESIA outputs affect irrigation actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .capability_cards import CapabilityCard, CAPABILITY_CARD_CATALOGUE


@dataclass(frozen=True)
class PolicyGuardrailCheck:
    """Outcome of evaluating Layer 8 policy guardrails."""

    is_allowed: bool
    capability_id: str
    requested_action: str
    observed_uncertainty_vwc: float
    max_tolerated_uncertainty_vwc: float
    requires_human_confirmation: bool
    rejection_reason: Optional[str] = None


class L8PolicyGuardrails:
    """Enforces safety and policy guardrails on agricultural actions."""

    @staticmethod
    def evaluate_action_guardrail(
        capability_id: str,
        requested_action: str,  # e.g., 'TRIGGER_IRRIGATION_VALVE'
        observed_uncertainty: float = 0.02,
        max_tolerated_uncertainty: float = 0.04,
    ) -> PolicyGuardrailCheck:
        """Check if action is permitted under capability card rules and uncertainty bounds."""
        card = CAPABILITY_CARD_CATALOGUE.get(capability_id)
        if not card:
            return PolicyGuardrailCheck(
                is_allowed=False,
                capability_id=capability_id,
                requested_action=requested_action,
                observed_uncertainty_vwc=observed_uncertainty,
                max_tolerated_uncertainty_vwc=max_tolerated_uncertainty,
                requires_human_confirmation=True,
                rejection_reason=f"Unknown capability card {capability_id}",
            )

        if not card.is_qualified:
            return PolicyGuardrailCheck(
                is_allowed=False,
                capability_id=capability_id,
                requested_action=requested_action,
                observed_uncertainty_vwc=observed_uncertainty,
                max_tolerated_uncertainty_vwc=max_tolerated_uncertainty,
                requires_human_confirmation=True,
                rejection_reason=f"Capability {capability_id} is not qualified for autonomous decisions",
            )

        if observed_uncertainty > max_tolerated_uncertainty:
            return PolicyGuardrailCheck(
                is_allowed=False,
                capability_id=capability_id,
                requested_action=requested_action,
                observed_uncertainty_vwc=observed_uncertainty,
                max_tolerated_uncertainty_vwc=max_tolerated_uncertainty,
                requires_human_confirmation=True,
                rejection_reason=f"Uncertainty {observed_uncertainty:.3f} exceeds threshold {max_tolerated_uncertainty:.3f}",
            )

        return PolicyGuardrailCheck(
            is_allowed=True,
            capability_id=capability_id,
            requested_action=requested_action,
            observed_uncertainty_vwc=observed_uncertainty,
            max_tolerated_uncertainty_vwc=max_tolerated_uncertainty,
            requires_human_confirmation=False,
            rejection_reason=None,
        )
