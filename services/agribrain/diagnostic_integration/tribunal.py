"""Deterministic consistency adjudication for diagnostic contributions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Mapping, Tuple

from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .contracts import (
    ContributionRole,
    DiagnosticContribution,
    IdentifiabilityClass,
    canonical_hash,
    immutable_data,
)
from .dependency_graph import DependencyGraph


class FindingSeverity(str, Enum):
    BLOCK = "BLOCK"
    CAUTION = "CAUTION"
    INFO = "INFO"


@dataclass(frozen=True)
class TribunalFinding:
    code: str
    severity: FindingSeverity
    contribution_ids: Tuple[str, ...]
    target_state: str
    message: str
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code or not self.message or not self.target_state:
            raise ContractViolation("TribunalFinding requires code, target_state and message")
        if not isinstance(self.severity, FindingSeverity):
            raise ContractViolation("TribunalFinding requires typed severity")
        object.__setattr__(self, "contribution_ids", tuple(self.contribution_ids))
        object.__setattr__(self, "details", immutable_data(self.details))

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "contribution_ids": list(self.contribution_ids),
            "target_state": self.target_state,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class TribunalVerdict:
    input_belief_id: str
    accepted_contribution_ids: Tuple[str, ...]
    blocked_contribution_ids: Tuple[str, ...]
    cautioned_contribution_ids: Tuple[str, ...]
    findings: Tuple[TribunalFinding, ...]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not str(self.input_belief_id or "").strip():
            raise ContractViolation("TribunalVerdict requires input_belief_id")
        object.__setattr__(self, "accepted_contribution_ids", tuple(self.accepted_contribution_ids))
        object.__setattr__(self, "blocked_contribution_ids", tuple(self.blocked_contribution_ids))
        object.__setattr__(self, "cautioned_contribution_ids", tuple(self.cautioned_contribution_ids))
        object.__setattr__(self, "findings", tuple(self.findings))
        if set(self.accepted_contribution_ids) & set(self.blocked_contribution_ids):
            raise ContractViolation("tribunal accepted and blocked contribution sets overlap")
        expected = canonical_hash(self.identity_payload())
        if self.content_hash and self.content_hash != expected:
            raise ContractViolation("TribunalVerdict content_hash does not match content")
        object.__setattr__(self, "content_hash", expected)

    def identity_payload(self) -> dict:
        return {
            "input_belief_id": self.input_belief_id,
            "accepted_contribution_ids": self.accepted_contribution_ids,
            "blocked_contribution_ids": self.blocked_contribution_ids,
            "cautioned_contribution_ids": self.cautioned_contribution_ids,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_dict(self) -> dict:
        return {
            **self.identity_payload(),
            "generated_at": self.generated_at,
            "content_hash": self.content_hash,
        }


class ConsistencyTribunal:
    """Fail-closed rules for authority, confounding and signal conflicts."""

    def __init__(self, contradiction_threshold: float = 0.6) -> None:
        if not 0.0 <= contradiction_threshold <= 1.0:
            raise ContractViolation("contradiction_threshold must be within [0, 1]")
        self.contradiction_threshold = float(contradiction_threshold)

    def adjudicate(
        self,
        contributions: Iterable[DiagnosticContribution],
        graph: DependencyGraph,
    ) -> TribunalVerdict:
        values = tuple(contributions)
        if not values:
            raise ContractViolation("consistency tribunal requires contributions")
        belief_ids = {value.input_belief_id for value in values}
        if len(belief_ids) != 1:
            raise ContractViolation("consistency tribunal cannot mix belief identities")
        graph.validate()
        ids = {value.contribution_id for value in values}
        if len(ids) != len(values):
            raise ContractViolation("consistency tribunal received duplicate contributions")
        for value in values:
            graph.dependencies(value.contribution_id)

        blocked: set[str] = set()
        cautioned: set[str] = set()
        findings: list[TribunalFinding] = []

        for contribution in sorted(values, key=lambda item: item.contribution_id):
            if not contribution.authority.diagnosis_allowed:
                blocked.add(contribution.contribution_id)
                findings.append(
                    TribunalFinding(
                        code="DIAGNOSIS_AUTHORITY_DENIED",
                        severity=FindingSeverity.BLOCK,
                        contribution_ids=(contribution.contribution_id,),
                        target_state=contribution.target_state,
                        message="Contribution authority does not permit diagnostic influence.",
                    )
                )
            if contribution.block_reasons:
                blocked.add(contribution.contribution_id)
                findings.append(
                    TribunalFinding(
                        code="CONTRIBUTION_EXPLICITLY_BLOCKED",
                        severity=FindingSeverity.BLOCK,
                        contribution_ids=(contribution.contribution_id,),
                        target_state=contribution.target_state,
                        message="Producer supplied one or more fail-closed block reasons.",
                        details={"block_reasons": list(contribution.block_reasons)},
                    )
                )
            if contribution.identifiability_class in {
                IdentifiabilityClass.CONFOUNDED,
                IdentifiabilityClass.HEURISTIC,
            }:
                cautioned.add(contribution.contribution_id)
                findings.append(
                    TribunalFinding(
                        code="LIMITED_IDENTIFIABILITY",
                        severity=FindingSeverity.CAUTION,
                        contribution_ids=(contribution.contribution_id,),
                        target_state=contribution.target_state,
                        message="Contribution is confounded or heuristic and cannot be treated as independent proof.",
                        details={
                            "identifiability_class": contribution.identifiability_class.value,
                            "confounders": list(contribution.confounders),
                        },
                    )
                )

        by_target: dict[str, list[DiagnosticContribution]] = {}
        for contribution in values:
            by_target.setdefault(contribution.target_state, []).append(contribution)

        for target_state, target_values in sorted(by_target.items()):
            ordered = sorted(target_values, key=lambda item: item.contribution_id)
            for position, first in enumerate(ordered):
                for second in ordered[position + 1 :]:
                    shared = graph.shared_families(first.contribution_id, second.contribution_id)
                    if shared:
                        cautioned.update((first.contribution_id, second.contribution_id))
                        findings.append(
                            TribunalFinding(
                                code="DEPENDENCY_FAMILY_OVERLAP",
                                severity=FindingSeverity.CAUTION,
                                contribution_ids=(first.contribution_id, second.contribution_id),
                                target_state=target_state,
                                message="Contributions share evidence ancestry and are not independent votes.",
                                details={"shared_dependency_families": list(shared)},
                            )
                        )
                    shared_evidence = graph.shared_evidence(
                        first.contribution_id, second.contribution_id,
                    )
                    if shared_evidence:
                        cautioned.update((first.contribution_id, second.contribution_id))
                        findings.append(
                            TribunalFinding(
                                code="EXACT_EVIDENCE_OVERLAP",
                                severity=FindingSeverity.CAUTION,
                                contribution_ids=(
                                    first.contribution_id,
                                    second.contribution_id,
                                ),
                                target_state=target_state,
                                message=(
                                    "Contributions reuse exact evidence identifiers "
                                    "and cannot count as independent votes."
                                ),
                                details={
                                    "shared_evidence_ids": list(shared_evidence),
                                },
                            )
                        )

            positive = [
                item
                for item in ordered
                if item.contribution_role in {ContributionRole.PRIMARY, ContributionRole.SUPPORTING}
                and item.confidence >= self.contradiction_threshold
                and item.contribution_id not in blocked
            ]
            negative = [
                item
                for item in ordered
                if item.contribution_role is ContributionRole.CONTRADICTING
                and item.confidence >= self.contradiction_threshold
                and item.contribution_id not in blocked
            ]
            if positive and negative:
                conflict_ids = tuple(sorted(item.contribution_id for item in (*positive, *negative)))
                blocked.update(conflict_ids)
                findings.append(
                    TribunalFinding(
                        code="UNRESOLVED_HIGH_CONFIDENCE_CONTRADICTION",
                        severity=FindingSeverity.BLOCK,
                        contribution_ids=conflict_ids,
                        target_state=target_state,
                        message="High-confidence supporting and contradicting signals remain unresolved.",
                        details={"threshold": self.contradiction_threshold},
                    )
                )

        by_id = {value.contribution_id: value for value in values}
        for contribution_id in graph.topological_order():
            if contribution_id not in by_id or contribution_id in blocked:
                continue
            blocked_parents = tuple(sorted(
                set(graph.dependencies(contribution_id)) & blocked
            ))
            if blocked_parents:
                blocked.add(contribution_id)
                contribution = by_id[contribution_id]
                findings.append(
                    TribunalFinding(
                        code="BLOCKED_ANCESTOR",
                        severity=FindingSeverity.BLOCK,
                        contribution_ids=(contribution_id, *blocked_parents),
                        target_state=contribution.target_state,
                        message=(
                            "Contribution descends from blocked diagnostic ancestry."
                        ),
                        details={"blocked_parent_ids": list(blocked_parents)},
                    )
                )

        accepted = tuple(sorted(ids - blocked))
        return TribunalVerdict(
            input_belief_id=next(iter(belief_ids)),
            accepted_contribution_ids=accepted,
            blocked_contribution_ids=tuple(sorted(blocked)),
            cautioned_contribution_ids=tuple(sorted(cautioned)),
            findings=tuple(findings),
        )
