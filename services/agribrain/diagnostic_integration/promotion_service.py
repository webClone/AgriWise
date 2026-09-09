"""
Diagnostic Promotion Service — Promotes tribunal-accepted diagnoses to prescriptive capability.

Finding #1 / Monograph Section 3.1:
Diagnostic adapters deliberately strip prescription authority (prescription_driver_allowed=False)
to prevent uncalibrated diagnostic hunches from commanding physical machinery.
DiagnosticPromotionService acts as the explicit, policy-governed authority bridge:
it evaluates tribunal-accepted contributions against confidence thresholds, identifiability
standards, and policy scope rules to grant elevated PRESCRIPTION_DRIVER capability receipts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from services.agribrain.scientific_contracts.authority import AuthorityVector
from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .contracts import (
    DiagnosticContribution,
    IdentifiabilityClass,
    canonical_data,
    canonical_hash,
)


@dataclass(frozen=True)
class PromotionResult:
    """Immutable audit record of diagnostic promotion decisions."""

    promoted_contributions: Tuple[DiagnosticContribution, ...]
    promoted_ids: Tuple[str, ...]
    exclusions: Mapping[str, Tuple[str, ...]]
    promoted_count: int
    evaluated_count: int
    policy_snapshot_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "promoted_ids": list(self.promoted_ids),
            "promoted_count": self.promoted_count,
            "evaluated_count": self.evaluated_count,
            "exclusions": dict(self.exclusions),
            "policy_snapshot_hash": self.policy_snapshot_hash,
        }


class DiagnosticPromotionService:
    """Evaluates accepted diagnostic tribunal contributions against policy rules

    to promote eligible diagnoses to PRESCRIPTION_DRIVER capability.
    Diagnostic adapters themselves remain unable to self-authorize.
    """

    def __init__(self, default_min_confidence: float = 0.70) -> None:
        self.default_min_confidence = default_min_confidence

    def promote_to_prescription_eligibility(
        self,
        accepted_contributions: Iterable[DiagnosticContribution],
        policy_snapshot: Optional[Dict[str, Any]] = None,
        evidence_receipts: Optional[Dict[str, Any]] = None,
    ) -> PromotionResult:
        """Evaluate contributions and elevate eligible diagnoses to prescription driver status.

        Promotion Criteria:
        1. Target variable must be in policy-approved prescriptive scope (if specified).
        2. Minimum epistemic confidence threshold must be satisfied (policy or default 0.70).
        3. Identifiability class must be IDENTIFIED or PARTIALLY_IDENTIFIED (reject HEURISTIC / CONFOUNDED).
        4. No active block reasons in contribution lineage.
        """
        policy = policy_snapshot or {}
        min_conf = float(policy.get("min_prescription_confidence", self.default_min_confidence))
        allowed_targets = policy.get("allowed_target_variables")

        promoted: List[DiagnosticContribution] = []
        exclusions: Dict[str, Tuple[str, ...]] = {}
        evaluated_count = 0

        for contrib in accepted_contributions:
            evaluated_count += 1
            cid = contrib.contribution_id

            # Check 1: Active block reasons in lineage
            if contrib.block_reasons:
                exclusions[cid] = (f"PROMOTION_DENIED_BLOCK_REASONS:{','.join(contrib.block_reasons)}",)
                continue

            # Check 2: Identifiability standard
            if contrib.identifiability_class == IdentifiabilityClass.HEURISTIC:
                exclusions[cid] = ("PROMOTION_DENIED_HEURISTIC_ONLY",)
                continue
            if contrib.identifiability_class == IdentifiabilityClass.CONFOUNDED:
                exclusions[cid] = ("PROMOTION_DENIED_CONFOUNDED",)
                continue

            # Check 3: Minimum epistemic confidence
            if float(contrib.confidence) < min_conf:
                exclusions[cid] = (
                    f"PROMOTION_DENIED_LOW_CONFIDENCE:{contrib.confidence:.3f}<{min_conf:.3f}",
                )
                continue

            # Check 4: Policy scope check
            if allowed_targets is not None:
                allowed_set = set(allowed_targets)
                if contrib.target_state not in allowed_set:
                    exclusions[cid] = (
                        f"PROMOTION_DENIED_OUT_OF_POLICY_SCOPE:{contrib.target_state}",
                    )
                    continue

            # All checks satisfied: grant elevated PRESCRIPTION_DRIVER authority
            elevated_authority = AuthorityVector(
                visualization_allowed=True,
                diagnosis_allowed=True,
                state_update_allowed=contrib.authority.state_update_allowed,
                training_allowed=contrib.authority.training_allowed,
                prescription_driver_allowed=True,
                machine_execution_allowed=False,  # Execution requires downstream L8 cryptographic authorization
            )
            promoted_contrib = contrib.with_authority(elevated_authority)
            promoted.append(promoted_contrib)

        policy_hash = canonical_hash(dict(policy))
        return PromotionResult(
            promoted_contributions=tuple(promoted),
            promoted_ids=tuple(c.contribution_id for c in promoted),
            exclusions=exclusions,
            promoted_count=len(promoted),
            evaluated_count=evaluated_count,
            policy_snapshot_hash=policy_hash,
        )
