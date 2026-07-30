"""Bounded, auditable influence manifests derived from tribunal verdicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, Mapping, Tuple

from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .contracts import (
    ContributionRole,
    DiagnosticContribution,
    InfluenceUse,
    authority_allows,
    canonical_data,
    canonical_hash,
    immutable_data,
)
from .dependency_graph import DependencyGraph
from .tribunal import TribunalVerdict


@dataclass(frozen=True)
class InfluenceEntry:
    contribution_id: str
    layer_id: str
    target_state: str
    contribution_role: ContributionRole
    signed_weight: float
    raw_confidence: float
    dependency_families: Tuple[str, ...]
    input_evidence_ids: Tuple[str, ...]
    input_contribution_ids: Tuple[str, ...]
    authority: Mapping[str, bool]

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependency_families", tuple(self.dependency_families))
        object.__setattr__(self, "input_evidence_ids", tuple(self.input_evidence_ids))
        object.__setattr__(self, "input_contribution_ids", tuple(self.input_contribution_ids))
        object.__setattr__(self, "authority", immutable_data(self.authority))

    def to_dict(self) -> dict:
        return canonical_data(self)


@dataclass(frozen=True)
class InfluenceManifest:
    input_belief_id: str
    requested_use: InfluenceUse
    tribunal_content_hash: str
    entries: Tuple[InfluenceEntry, ...]
    excluded_contribution_ids: Tuple[str, ...]
    exclusion_reasons: Mapping[str, Tuple[str, ...]]
    family_influence_limit: float
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "diagnostic_influence_manifest_v1"
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.input_belief_id:
            raise ContractViolation("InfluenceManifest requires input_belief_id")
        if not isinstance(self.requested_use, InfluenceUse):
            raise ContractViolation("InfluenceManifest requires typed requested_use")
        if not 0.0 < self.family_influence_limit <= 1.0:
            raise ContractViolation("family_influence_limit must be within (0, 1]")
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "excluded_contribution_ids", tuple(self.excluded_contribution_ids))
        object.__setattr__(self, "exclusion_reasons", immutable_data(self.exclusion_reasons))
        expected = canonical_hash(self.identity_payload())
        if self.content_hash and self.content_hash != expected:
            raise ContractViolation("InfluenceManifest content_hash does not match content")
        object.__setattr__(self, "content_hash", expected)

    def identity_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "input_belief_id": self.input_belief_id,
            "requested_use": self.requested_use,
            "tribunal_content_hash": self.tribunal_content_hash,
            "entries": [entry.to_dict() for entry in self.entries],
            "excluded_contribution_ids": self.excluded_contribution_ids,
            "exclusion_reasons": self.exclusion_reasons,
            "family_influence_limit": self.family_influence_limit,
        }

    def to_dict(self) -> dict:
        return {
            **canonical_data(self.identity_payload()),
            "generated_at": self.generated_at,
            "content_hash": self.content_hash,
        }


class InfluenceManifestBuilder:
    """Limit correlated child beliefs so they cannot amplify shared evidence."""

    def __init__(self, family_influence_limit: float = 0.35) -> None:
        if not 0.0 < family_influence_limit <= 1.0:
            raise ContractViolation("family_influence_limit must be within (0, 1]")
        self.family_influence_limit = float(family_influence_limit)

    def build(
        self,
        verdict: TribunalVerdict,
        contributions: Iterable[DiagnosticContribution],
        graph: DependencyGraph,
        requested_use: InfluenceUse = InfluenceUse.DIAGNOSIS,
    ) -> InfluenceManifest:
        if not isinstance(requested_use, InfluenceUse):
            raise ContractViolation("influence manifest requires typed requested_use")
        values = {item.contribution_id: item for item in contributions}
        if any(item.input_belief_id != verdict.input_belief_id for item in values.values()):
            raise ContractViolation("influence manifest cannot mix belief identities")
        referenced = set(verdict.accepted_contribution_ids) | set(verdict.blocked_contribution_ids)
        if referenced - set(values):
            raise ContractViolation("tribunal verdict references unavailable contributions")
        graph.validate()
        for contribution_id in referenced:
            graph.dependencies(contribution_id)

        exclusions: Dict[str, Tuple[str, ...]] = {
            item: ("TRIBUNAL_BLOCKED",) for item in verdict.blocked_contribution_ids
        }
        eligible = []
        for contribution_id in verdict.accepted_contribution_ids:
            contribution = values[contribution_id]
            if not authority_allows(contribution.authority, requested_use):
                exclusions[contribution_id] = (f"AUTHORITY_DENIES_{requested_use.value}",)
            else:
                eligible.append(contribution)

        effective_families = {
            contribution.contribution_id: graph.dependency_families(contribution.contribution_id)
            for contribution in eligible
        }
        effective_evidence = {
            contribution.contribution_id: graph.evidence_ids(
                contribution.contribution_id,
            )
            for contribution in eligible
        }
        family_members: Dict[str, set[str]] = {}
        for contribution in eligible:
            for family in effective_families[contribution.contribution_id]:
                family_members.setdefault(family, set()).add(contribution.contribution_id)
        evidence_members: Dict[str, set[str]] = {}
        for contribution in eligible:
            for evidence_id in effective_evidence[contribution.contribution_id]:
                evidence_members.setdefault(evidence_id, set()).add(
                    contribution.contribution_id,
                )

        weights: Dict[str, float] = {}
        for contribution in eligible:
            family_caps = [
                self.family_influence_limit / len(family_members[family])
                for family in effective_families[contribution.contribution_id]
            ]
            evidence_caps = [
                self.family_influence_limit / len(evidence_members[evidence_id])
                for evidence_id in effective_evidence[contribution.contribution_id]
            ]
            weights[contribution.contribution_id] = min(
                contribution.confidence,
                *family_caps,
                *evidence_caps,
            )

        by_target: Dict[str, list[str]] = {}
        for contribution in eligible:
            by_target.setdefault(contribution.target_state, []).append(contribution.contribution_id)
        for ids in by_target.values():
            total = sum(abs(weights[item]) for item in ids)
            if total > 1.0:
                scale = 1.0 / total
                for item in ids:
                    weights[item] *= scale

        entries = []
        for contribution in sorted(eligible, key=lambda item: item.contribution_id):
            sign = -1.0 if contribution.contribution_role is ContributionRole.CONTRADICTING else 1.0
            entries.append(
                InfluenceEntry(
                    contribution_id=contribution.contribution_id,
                    layer_id=contribution.layer_id,
                    target_state=contribution.target_state,
                    contribution_role=contribution.contribution_role,
                    signed_weight=sign * weights[contribution.contribution_id],
                    raw_confidence=contribution.confidence,
                    dependency_families=effective_families[contribution.contribution_id],
                    input_evidence_ids=contribution.input_evidence_ids,
                    input_contribution_ids=contribution.input_contribution_ids,
                    authority=canonical_data(contribution.authority),
                )
            )

        return InfluenceManifest(
            input_belief_id=verdict.input_belief_id,
            requested_use=requested_use,
            tribunal_content_hash=verdict.content_hash,
            entries=tuple(entries),
            excluded_contribution_ids=tuple(sorted(exclusions)),
            exclusion_reasons={key: exclusions[key] for key in sorted(exclusions)},
            family_influence_limit=self.family_influence_limit,
        )
