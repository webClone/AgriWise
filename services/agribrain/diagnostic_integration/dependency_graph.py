"""Contribution dependency DAG and shared-family inspection."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Tuple

from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .contracts import DiagnosticContribution


def validate_dependency_map(dependencies: Mapping[str, Iterable[str]]) -> None:
    normalized = {str(node): tuple(str(parent) for parent in parents) for node, parents in dependencies.items()}
    all_nodes = set(normalized)
    for node, parents in normalized.items():
        if node in parents:
            raise ContractViolation(f"diagnostic dependency self-cycle: {node}")
        missing = set(parents) - all_nodes
        if missing:
            raise ContractViolation(
                f"diagnostic dependency graph has absent parents for {node}: {sorted(missing)}"
            )
    state: Dict[str, int] = {}

    def visit(node: str, path: Tuple[str, ...]) -> None:
        mark = state.get(node, 0)
        if mark == 1:
            raise ContractViolation("diagnostic dependency cycle: " + " -> ".join((*path, node)))
        if mark == 2:
            return
        state[node] = 1
        for parent in normalized[node]:
            visit(parent, (*path, node))
        state[node] = 2

    for node in sorted(normalized):
        visit(node, ())


class DependencyGraph:
    def __init__(self) -> None:
        self._dependencies: Dict[str, Tuple[str, ...]] = {}
        self._families: Dict[str, Tuple[str, ...]] = {}
        self._evidence: Dict[str, Tuple[str, ...]] = {}

    def validate_many(self, contributions: Iterable[DiagnosticContribution]) -> None:
        candidate_dependencies = dict(self._dependencies)
        candidate_families = dict(self._families)
        candidate_evidence = dict(self._evidence)
        for contribution in contributions:
            node = contribution.contribution_id
            if node in candidate_dependencies:
                raise ContractViolation(f"duplicate diagnostic graph node: {node}")
            missing = set(contribution.input_contribution_ids) - set(candidate_dependencies)
            if missing:
                raise ContractViolation(
                    f"diagnostic graph node {node} has absent parents: {sorted(missing)}"
                )
            candidate_dependencies[node] = contribution.input_contribution_ids
            candidate_families[node] = contribution.dependency_families
            candidate_evidence[node] = contribution.input_evidence_ids
        validate_dependency_map(candidate_dependencies)

    def add(self, contribution: DiagnosticContribution) -> None:
        self.add_many((contribution,))

    def add_many(self, contributions: Iterable[DiagnosticContribution]) -> None:
        values = tuple(contributions)
        if not values:
            raise ContractViolation("diagnostic graph cannot add an empty batch")
        self.validate_many(values)
        for contribution in values:
            self._dependencies[contribution.contribution_id] = contribution.input_contribution_ids
            self._families[contribution.contribution_id] = contribution.dependency_families
            self._evidence[contribution.contribution_id] = contribution.input_evidence_ids

    def dependencies(self, contribution_id: str) -> Tuple[str, ...]:
        if contribution_id not in self._dependencies:
            raise ContractViolation(f"unknown diagnostic graph node: {contribution_id}")
        return self._dependencies[contribution_id]

    def ancestry(self, contribution_id: str) -> Tuple[str, ...]:
        self.dependencies(contribution_id)
        found: set[str] = set()

        def collect(node: str) -> None:
            for parent in self._dependencies[node]:
                if parent not in found:
                    found.add(parent)
                    collect(parent)

        collect(contribution_id)
        return tuple(sorted(found))

    def shared_families(self, first_id: str, second_id: str) -> Tuple[str, ...]:
        if first_id not in self._families or second_id not in self._families:
            raise ContractViolation("unknown diagnostic graph node")
        first_nodes = {first_id, *self.ancestry(first_id)}
        second_nodes = {second_id, *self.ancestry(second_id)}
        first = {family for node in first_nodes for family in self._families[node]}
        second = {family for node in second_nodes for family in self._families[node]}
        return tuple(sorted(first & second))

    def evidence_ids(
        self, contribution_id: str, *, include_ancestry: bool = True
    ) -> Tuple[str, ...]:
        if contribution_id not in self._evidence:
            raise ContractViolation(f"unknown diagnostic graph node: {contribution_id}")
        nodes = {contribution_id}
        if include_ancestry:
            nodes.update(self.ancestry(contribution_id))
        return tuple(sorted({
            evidence_id for node in nodes for evidence_id in self._evidence[node]
        }))

    def shared_evidence(self, first_id: str, second_id: str) -> Tuple[str, ...]:
        first = set(self.evidence_ids(first_id))
        second = set(self.evidence_ids(second_id))
        return tuple(sorted(first & second))

    def dependency_families(
        self, contribution_id: str, *, include_ancestry: bool = True
    ) -> Tuple[str, ...]:
        if contribution_id not in self._families:
            raise ContractViolation(f"unknown diagnostic graph node: {contribution_id}")
        nodes = {contribution_id}
        if include_ancestry:
            nodes.update(self.ancestry(contribution_id))
        return tuple(sorted({family for node in nodes for family in self._families[node]}))

    def topological_order(self) -> Tuple[str, ...]:
        validate_dependency_map(self._dependencies)
        emitted: set[str] = set()
        order = []
        while len(order) < len(self._dependencies):
            ready = sorted(
                node
                for node, parents in self._dependencies.items()
                if node not in emitted and set(parents) <= emitted
            )
            if not ready:
                raise ContractViolation("diagnostic dependency graph cannot be topologically ordered")
            order.extend(ready)
            emitted.update(ready)
        return tuple(order)

    def validate(self) -> None:
        validate_dependency_map(self._dependencies)
        nodes = set(self._dependencies)
        if set(self._families) != nodes or set(self._evidence) != nodes:
            raise ContractViolation("diagnostic graph metadata is incomplete")

    def to_dict(self) -> dict:
        self.validate()
        return {
            "dependencies": {key: list(self._dependencies[key]) for key in sorted(self._dependencies)},
            "dependency_families": {key: list(self._families[key]) for key in sorted(self._families)},
            "input_evidence_ids": {key: list(self._evidence[key]) for key in sorted(self._evidence)},
            "topological_order": list(self.topological_order()),
        }
