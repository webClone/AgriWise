"""Small orchestration facade for the diagnostic integration foundation."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Tuple

from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .adapters import AdapterContext
from .contracts import DiagnosticContribution, InfluenceUse, canonical_hash
from .dependency_graph import DependencyGraph
from .influence import InfluenceManifest, InfluenceManifestBuilder
from .ledger import ContributionLedger
from .registry import DiagnosticRegistry, build_default_registry
from .tribunal import ConsistencyTribunal, TribunalVerdict


@dataclass(frozen=True)
class DiagnosticIntegrationResult:
    input_belief_id: str
    tribunal_verdict: TribunalVerdict
    influence_manifest: InfluenceManifest
    ledger_head_hash: str
    dependency_graph_hash: str

    def to_dict(self) -> dict:
        return {
            "input_belief_id": self.input_belief_id,
            "tribunal_verdict": self.tribunal_verdict.to_dict(),
            "influence_manifest": self.influence_manifest.to_dict(),
            "ledger_head_hash": self.ledger_head_hash,
            "dependency_graph_hash": self.dependency_graph_hash,
        }


class DiagnosticIntegrationRuntime:
    """Run-scoped coordinator. It does not mutate the canonical belief state."""

    def __init__(
        self,
        registry: DiagnosticRegistry | None = None,
        ledger: ContributionLedger | None = None,
        graph: DependencyGraph | None = None,
        tribunal: ConsistencyTribunal | None = None,
        manifest_builder: InfluenceManifestBuilder | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.ledger = ledger or ContributionLedger()
        self.graph = graph or DependencyGraph()
        self.tribunal = tribunal or ConsistencyTribunal()
        self.manifest_builder = manifest_builder or InfluenceManifestBuilder()
        self._belief_id: str | None = None
        self._lock = RLock()

    def ingest_layer(
        self,
        layer_id: str,
        output: Any,
        context: AdapterContext,
        engine_id: str = "generic",
    ) -> Tuple[DiagnosticContribution, ...]:
        contributions = self.registry.adapt(layer_id, output, context, engine_id)
        with self._lock:
            if self._belief_id is not None and context.input_belief_id != self._belief_id:
                raise ContractViolation(
                    "diagnostic runtime cannot ingest multiple belief identities"
                )
            self.graph.validate_many(contributions)
            self.ledger.validate_many(contributions)
            ledger_entries = list(self.ledger._entries)
            ledger_by_id = dict(self.ledger._by_id)
            graph_dependencies = dict(self.graph._dependencies)
            graph_families = dict(self.graph._families)
            graph_evidence = dict(self.graph._evidence)
            try:
                self.ledger.append_many(contributions)
                self.graph.add_many(contributions)
            except Exception:
                self.ledger._entries = ledger_entries
                self.ledger._by_id = ledger_by_id
                self.graph._dependencies = graph_dependencies
                self.graph._families = graph_families
                self.graph._evidence = graph_evidence
                raise
            self._belief_id = context.input_belief_id
        return contributions

    def finalize(
        self,
        input_belief_id: str,
        requested_use: InfluenceUse = InfluenceUse.DIAGNOSIS,
    ) -> DiagnosticIntegrationResult:
        belief_id = str(input_belief_id or "").strip()
        if not belief_id:
            raise ContractViolation("diagnostic finalization requires input_belief_id")
        with self._lock:
            if self._belief_id is not None and belief_id != self._belief_id:
                raise ContractViolation("diagnostic finalization belief identity mismatch")
            contributions = self.ledger.contributions(belief_id)
            if not contributions:
                raise ContractViolation(f"no diagnostic contributions for belief {belief_id}")
            self.ledger.verify()
            self.graph.validate()
            verdict = self.tribunal.adjudicate(contributions, self.graph)
            manifest = self.manifest_builder.build(
                verdict, contributions, self.graph, requested_use
            )
            return DiagnosticIntegrationResult(
                input_belief_id=belief_id,
                tribunal_verdict=verdict,
                influence_manifest=manifest,
                ledger_head_hash=self.ledger.head_hash,
                dependency_graph_hash=canonical_hash(self.graph.to_dict()),
            )


def build_default_runtime() -> DiagnosticIntegrationRuntime:
    return DiagnosticIntegrationRuntime(registry=build_default_registry())
