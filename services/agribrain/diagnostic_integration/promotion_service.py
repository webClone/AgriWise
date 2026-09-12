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
from services.agribrain.scientific_contracts.evidence_receipt import EvidenceReceipt
from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .contracts import (
    DiagnosticContribution,
    IdentifiabilityClass,
    canonical_data,
    canonical_hash,
)


from enum import Enum


class PromotionTier(str, Enum):
    """Authority tiers for diagnostic contributions in operational workflows."""
    DIAGNOSTIC_SUPPORT = "DIAGNOSTIC_SUPPORT"             # Explain possible cause (read-only)
    SCOUTING_RECOMMENDATION = "SCOUTING_RECOMMENDATION"   # Request field scouting / ground verification
    SCENARIO_INPUT = "SCENARIO_INPUT"                     # Simulate candidate futures
    GENERAL_ADVISORY = "GENERAL_ADVISORY"                 # Bounded non-exact agronomic advice
    EXACT_PRESCRIPTION = "EXACT_PRESCRIPTION"             # Select variable-rate intervention (fertilizer/water/spray)
    MACHINE_EXECUTION = "MACHINE_EXECUTION"               # Direct executable machine command


@dataclass(frozen=True)
class PromotionResult:
    """Immutable audit record of diagnostic promotion decisions."""

    promoted_contributions: Tuple[DiagnosticContribution, ...]
    promoted_ids: Tuple[str, ...]
    exclusions: Mapping[str, Tuple[str, ...]]
    promoted_count: int
    evaluated_count: int
    policy_snapshot_hash: str
    promotion_tiers: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "promoted_ids": list(self.promoted_ids),
            "promoted_count": self.promoted_count,
            "evaluated_count": self.evaluated_count,
            "exclusions": dict(self.exclusions),
            "policy_snapshot_hash": self.policy_snapshot_hash,
            "promotion_tiers": dict(self.promotion_tiers),
        }


class DiagnosticPromotionService:
    """Evaluates accepted diagnostic tribunal contributions against policy rules
    and physical evidence receipts to promote eligible diagnoses to PRESCRIPTION_DRIVER capability.
    Diagnostic adapters themselves remain unable to self-authorize.
    """

    def __init__(self, default_min_confidence: float = 0.70) -> None:
        self.default_min_confidence = default_min_confidence

    def evaluate_promotion_tier(
        self,
        contrib: DiagnosticContribution,
        policy_snapshot: Optional[Dict[str, Any]] = None,
        evidence_receipts: Optional[Dict[str, Any]] = None,
    ) -> Tuple[PromotionTier, List[str]]:
        """Determine maximum safe promotion tier for a single contribution."""
        policy = policy_snapshot or {}
        min_conf = float(policy.get("min_prescription_confidence", self.default_min_confidence))
        reasons: List[str] = []

        if contrib.block_reasons:
            return PromotionTier.DIAGNOSTIC_SUPPORT, [f"BLOCKED:{r}" for r in contrib.block_reasons]

        if contrib.identifiability_class in (IdentifiabilityClass.HEURISTIC, IdentifiabilityClass.CONFOUNDED):
            return PromotionTier.DIAGNOSTIC_SUPPORT, [f"IDENTIFIABILITY:{contrib.identifiability_class.value}"]

        if float(contrib.confidence) < min_conf:
            if float(contrib.confidence) >= 0.50:
                return PromotionTier.SCOUTING_RECOMMENDATION, [f"MODERATE_CONFIDENCE:{contrib.confidence:.2f}"]
            return PromotionTier.DIAGNOSTIC_SUPPORT, [f"LOW_CONFIDENCE:{contrib.confidence:.2f}"]

        if contrib.identifiability_class == IdentifiabilityClass.PARTIALLY_IDENTIFIED:
            if not policy.get("allow_partial_identifiability_for_prescriptions", False):
                return PromotionTier.GENERAL_ADVISORY, ["PARTIALLY_IDENTIFIED_RESTRICTED_TO_ADVISORY"]

        require_receipts = bool(policy.get("require_evidence_receipts", False))
        if evidence_receipts is not None or require_receipts:
            receipts = evidence_receipts or {}
            ev_receipt = (
                receipts.get(contrib.contribution_id)
                or receipts.get(contrib.target_state)
                or receipts.get(getattr(contrib, "native_evidence_hash", None))
            )
            if ev_receipt is None and require_receipts:
                return PromotionTier.SCOUTING_RECOMMENDATION, ["MISSING_EVIDENCE_RECEIPT"]
            if ev_receipt is not None:
                if isinstance(ev_receipt, EvidenceReceipt):
                    action_class = policy.get("action_class", "EXACT_PRESCRIPTION")
                    is_valid, reason = ev_receipt.is_valid_for_action(action_class)
                    if not is_valid:
                        return PromotionTier.SCOUTING_RECOMMENDATION, [f"EVIDENCE_RECEIPT_INVALID:{reason}"]
                elif isinstance(ev_receipt, dict):
                    if ev_receipt.get("is_calibrated") is False or ev_receipt.get("calibration_valid") is False:
                        return PromotionTier.SCOUTING_RECOMMENDATION, ["UNCALIBRATED_EVIDENCE"]
                    if ev_receipt.get("is_expired") is True or ev_receipt.get("is_stale") is True:
                        return PromotionTier.SCOUTING_RECOMMENDATION, ["STALE_EVIDENCE"]
                    if ev_receipt.get("spatial_support_valid") is False:
                        return PromotionTier.SCOUTING_RECOMMENDATION, ["INVALID_SPATIAL_SUPPORT"]

        return PromotionTier.EXACT_PRESCRIPTION, []

    def promote_to_prescription_eligibility(
        self,
        accepted_contributions: Iterable[DiagnosticContribution],
        policy_snapshot: Optional[Dict[str, Any]] = None,
        evidence_receipts: Optional[Dict[str, Any]] = None,
    ) -> PromotionResult:
        """Evaluate contributions and elevate eligible diagnoses to prescription driver status.

        Promotion Criteria:
        1. No active block reasons in contribution lineage.
        2. Identifiability class must be IDENTIFIED (or PARTIALLY_IDENTIFIED with explicit policy override).
        3. Minimum epistemic confidence threshold must be satisfied (policy or default 0.70).
        4. Target variable must be in policy-approved prescriptive scope (if specified).
        5. Physical evidence receipts (if provided or required by policy) must be valid, calibrated, and fresh.
        """
        policy = policy_snapshot or {}
        min_conf = float(policy.get("min_prescription_confidence", self.default_min_confidence))
        allowed_targets = policy.get("allowed_target_variables")
        require_receipts = bool(policy.get("require_evidence_receipts", False))
        allow_partial = bool(policy.get("allow_partial_identifiability_for_prescriptions", False))

        promoted: List[DiagnosticContribution] = []
        exclusions: Dict[str, Tuple[str, ...]] = {}
        assigned_tiers: Dict[str, str] = {}
        evaluated_count = 0

        for contrib in accepted_contributions:
            evaluated_count += 1
            cid = contrib.contribution_id

            # Check 1: Active block reasons in lineage
            if contrib.block_reasons:
                exclusions[cid] = (f"PROMOTION_DENIED_BLOCK_REASONS:{','.join(contrib.block_reasons)}",)
                assigned_tiers[cid] = PromotionTier.DIAGNOSTIC_SUPPORT.value
                continue

            # Check 2: Identifiability standard
            if contrib.identifiability_class == IdentifiabilityClass.HEURISTIC:
                exclusions[cid] = ("PROMOTION_DENIED_HEURISTIC_ONLY",)
                assigned_tiers[cid] = PromotionTier.DIAGNOSTIC_SUPPORT.value
                continue
            if contrib.identifiability_class == IdentifiabilityClass.CONFOUNDED:
                exclusions[cid] = ("PROMOTION_DENIED_CONFOUNDED",)
                assigned_tiers[cid] = PromotionTier.DIAGNOSTIC_SUPPORT.value
                continue
            if contrib.identifiability_class == IdentifiabilityClass.PARTIALLY_IDENTIFIED and not allow_partial:
                exclusions[cid] = ("PROMOTION_DENIED_PARTIALLY_IDENTIFIED_REQUIRES_EXPLICIT_POLICY",)
                assigned_tiers[cid] = PromotionTier.SCOUTING_RECOMMENDATION.value
                continue

            # Check 3: Minimum epistemic confidence
            if float(contrib.confidence) < min_conf:
                exclusions[cid] = (
                    f"PROMOTION_DENIED_LOW_CONFIDENCE:{contrib.confidence:.3f}<{min_conf:.3f}",
                )
                assigned_tiers[cid] = PromotionTier.SCOUTING_RECOMMENDATION.value if float(contrib.confidence) >= 0.5 else PromotionTier.DIAGNOSTIC_SUPPORT.value
                continue

            # Check 4: Policy scope check
            if allowed_targets is not None:
                allowed_set = set(allowed_targets)
                if contrib.target_state not in allowed_set:
                    exclusions[cid] = (
                        f"PROMOTION_DENIED_OUT_OF_POLICY_SCOPE:{contrib.target_state}",
                    )
                    assigned_tiers[cid] = PromotionTier.GENERAL_ADVISORY.value
                    continue

            # Check 5: Physical Evidence Receipts Verification
            if evidence_receipts is not None or require_receipts:
                receipts = evidence_receipts or {}
                # Match receipt by contribution_id, target_state, or native_evidence_hash
                ev_receipt = (
                    receipts.get(cid)
                    or receipts.get(contrib.target_state)
                    or receipts.get(getattr(contrib, "native_evidence_hash", None))
                )
                if ev_receipt is None and require_receipts:
                    exclusions[cid] = ("PROMOTION_DENIED_MISSING_EVIDENCE_RECEIPT",)
                    assigned_tiers[cid] = PromotionTier.SCOUTING_RECOMMENDATION.value
                    continue
                elif ev_receipt is not None:
                    action_class = policy.get("action_class", "EXACT_PRESCRIPTION")
                    # Handle EvidenceReceipt contract instance
                    if isinstance(ev_receipt, EvidenceReceipt) or hasattr(ev_receipt, "is_valid_for_action"):
                        is_valid, reason = ev_receipt.is_valid_for_action(action_class)
                        if not is_valid:
                            exclusions[cid] = (f"PROMOTION_DENIED_{reason}",)
                            assigned_tiers[cid] = PromotionTier.SCOUTING_RECOMMENDATION.value
                            continue
                    elif isinstance(ev_receipt, dict):
                        if ev_receipt.get("is_calibrated") is False or ev_receipt.get("calibration_valid") is False:
                            exclusions[cid] = ("PROMOTION_DENIED_UNCALIBRATED_EVIDENCE",)
                            assigned_tiers[cid] = PromotionTier.SCOUTING_RECOMMENDATION.value
                            continue
                        if ev_receipt.get("is_expired") is True or ev_receipt.get("is_stale") is True:
                            exclusions[cid] = ("PROMOTION_DENIED_STALE_EVIDENCE",)
                            assigned_tiers[cid] = PromotionTier.SCOUTING_RECOMMENDATION.value
                            continue
                        if ev_receipt.get("spatial_support_valid") is False:
                            exclusions[cid] = ("PROMOTION_DENIED_INVALID_SPATIAL_SUPPORT",)
                            assigned_tiers[cid] = PromotionTier.SCOUTING_RECOMMENDATION.value
                            continue
                    elif hasattr(ev_receipt, "calibration_valid") and not ev_receipt.calibration_valid:
                        exclusions[cid] = ("PROMOTION_DENIED_UNCALIBRATED_EVIDENCE",)
                        assigned_tiers[cid] = PromotionTier.SCOUTING_RECOMMENDATION.value
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
            assigned_tiers[cid] = PromotionTier.EXACT_PRESCRIPTION.value

        policy_hash = canonical_hash(dict(policy))
        return PromotionResult(
            promoted_contributions=tuple(promoted),
            promoted_ids=tuple(c.contribution_id for c in promoted),
            exclusions=exclusions,
            promoted_count=len(promoted),
            evaluated_count=evaluated_count,
            policy_snapshot_hash=policy_hash,
            promotion_tiers=assigned_tiers,
        )
