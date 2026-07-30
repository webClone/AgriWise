"""Fail-closed registry for diagnostic output adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Tuple

from services.agribrain.scientific_contracts.authority import (
    AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    AuthorityVector,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .adapters import ADAPTERS, AdapterContext
from .contracts import DiagnosticContribution, authority_is_subset


Adapter = Callable[[Any, AdapterContext], Tuple[DiagnosticContribution, ...]]


def normalize_layer_id(layer_id: str) -> str:
    token = str(layer_id or "").strip().upper().replace("LAYER", "L")
    if token.isdigit():
        token = f"L{token}"
    if token not in {f"L{number}" for number in range(2, 9)}:
        raise ContractViolation(f"unsupported diagnostic layer: {layer_id!r}")
    return token


@dataclass(frozen=True)
class DiagnosticEngineRegistration:
    layer_id: str
    engine_id: str
    adapter: Adapter
    target_prefixes: Tuple[str, ...]
    authority_ceiling: AuthorityVector = AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE

    def validate(self) -> None:
        normalize_layer_id(self.layer_id)
        if not str(self.engine_id or "").strip():
            raise ContractViolation("diagnostic registration requires engine_id")
        if not callable(self.adapter):
            raise ContractViolation("diagnostic registration requires a callable adapter")
        if not self.target_prefixes or any(not str(item).strip() for item in self.target_prefixes):
            raise ContractViolation("diagnostic registration requires target prefixes")
        if not isinstance(self.authority_ceiling, AuthorityVector):
            raise ContractViolation("diagnostic registration requires AuthorityVector ceiling")


class DiagnosticRegistry:
    """Explicit adapter registry; unknown engines and layers are rejected."""

    def __init__(self) -> None:
        self._registrations: Dict[Tuple[str, str], DiagnosticEngineRegistration] = {}

    def register(self, registration: DiagnosticEngineRegistration) -> None:
        registration.validate()
        layer_id = normalize_layer_id(registration.layer_id)
        engine_id = registration.engine_id.strip()
        key = (layer_id, engine_id)
        if key in self._registrations:
            raise ContractViolation(f"diagnostic engine already registered: {layer_id}/{engine_id}")
        self._registrations[key] = registration

    def resolve(self, layer_id: str, engine_id: str = "generic") -> DiagnosticEngineRegistration:
        key = (normalize_layer_id(layer_id), str(engine_id or "").strip())
        registration = self._registrations.get(key)
        if registration is None:
            raise ContractViolation(f"unregistered diagnostic engine: {key[0]}/{key[1]}")
        return registration

    def adapt(
        self,
        layer_id: str,
        output: Any,
        context: AdapterContext,
        engine_id: str = "generic",
    ) -> Tuple[DiagnosticContribution, ...]:
        registration = self.resolve(layer_id, engine_id)
        contributions = tuple(registration.adapter(output, context))
        if not contributions:
            raise ContractViolation("diagnostic adapter emitted no contribution")
        for contribution in contributions:
            contribution.validate()
            if contribution.layer_id != normalize_layer_id(layer_id):
                raise ContractViolation("diagnostic adapter emitted the wrong layer_id")
            if contribution.input_belief_id != context.input_belief_id:
                raise ContractViolation("diagnostic adapter changed the input belief identity")
            if set(contribution.input_evidence_ids) - set(context.input_evidence_ids):
                raise ContractViolation("diagnostic adapter introduced undeclared evidence")
            if set(contribution.input_contribution_ids) - set(context.input_contribution_ids):
                raise ContractViolation("diagnostic adapter introduced undeclared ancestry")
            if set(context.dependency_families) - set(contribution.dependency_families):
                raise ContractViolation("diagnostic adapter dropped context dependency families")
            if set(context.confounders) - set(contribution.confounders):
                raise ContractViolation("diagnostic adapter dropped context confounders")
            if set(context.block_reasons) - set(contribution.block_reasons):
                raise ContractViolation("diagnostic adapter dropped context block reasons")
            if not any(
                contribution.target_state == prefix or contribution.target_state.startswith(f"{prefix}.")
                for prefix in registration.target_prefixes
            ):
                raise ContractViolation(
                    f"target_state {contribution.target_state!r} is outside registered scope"
                )
            if not authority_is_subset(contribution.authority, registration.authority_ceiling):
                raise ContractViolation("diagnostic adapter exceeded its registered authority ceiling")
            if not authority_is_subset(contribution.authority, context.authority):
                raise ContractViolation("diagnostic adapter exceeded AdapterContext authority")
        return contributions

    def registrations(self) -> Tuple[DiagnosticEngineRegistration, ...]:
        return tuple(self._registrations[key] for key in sorted(self._registrations))


def build_default_registry() -> DiagnosticRegistry:
    registry = DiagnosticRegistry()
    prefixes = {
        "L2": ("condition", "state"),
        "L3": ("condition", "system"),
        "L4": ("condition", "system"),
        "L5": ("condition", "system"),
        "L6": ("execution",),
        "L7": ("planning",),
        "L8": ("action",),
    }
    for layer_id, adapter in ADAPTERS.items():
        registry.register(
            DiagnosticEngineRegistration(
                layer_id=layer_id,
                engine_id="generic",
                adapter=adapter,
                target_prefixes=prefixes[layer_id],
            )
        )
    return registry
