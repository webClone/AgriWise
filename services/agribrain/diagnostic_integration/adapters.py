"""Concrete adapters from the existing Layer 2--8 output schemas."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence, Tuple

from services.agribrain.scientific_contracts.authority import AuthorityVector
from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .contracts import (
    SCHEMA_VERSION,
    ContributionRole,
    DiagnosticContribution,
    IdentifiabilityClass,
    canonical_data,
)


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _enum(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _token(value: Any, fallback: str) -> str:
    text = str(_enum(value) or fallback).strip().lower()
    return "".join(char if char.isalnum() else "_" for char in text).strip("_") or fallback


def _condition_token(value: Any) -> str:
    token = _token(value, "unknown")
    aliases = {
        "excess_moisture": "waterlogging",
        "nutrient_deficiency_n": "nutrient_deficiency.n",
        "nutrient_deficiency_p": "nutrient_deficiency.p",
        "nutrient_deficiency_k": "nutrient_deficiency.k",
        "n_deficiency": "nutrient_deficiency.n",
        "p_deficiency": "nutrient_deficiency.p",
        "k_deficiency": "nutrient_deficiency.k",
    }
    return aliases.get(token, token)


def _tuple(values: Iterable[Any]) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        values = (values,)
    result = []
    for value in values or ():
        text = str(_enum(value) or "").strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _confidence(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(1.0, number))


def _diagnostic_authority(source: AuthorityVector) -> AuthorityVector:
    """Diagnostic adapters can only preserve visualization/diagnosis gates."""

    if not isinstance(source, AuthorityVector):
        raise ContractViolation("AdapterContext requires an explicit AuthorityVector")
    return AuthorityVector(
        visualization_allowed=source.visualization_allowed,
        diagnosis_allowed=source.diagnosis_allowed,
    )


@dataclass(frozen=True)
class AdapterContext:
    """Lineage and governance supplied by the orchestrator for one layer."""

    input_belief_id: str
    authority: AuthorityVector
    input_evidence_ids: Tuple[str, ...] = ()
    input_contribution_ids: Tuple[str, ...] = ()
    dependency_families: Tuple[str, ...] = ()
    confounders: Tuple[str, ...] = ()
    block_reasons: Tuple[str, ...] = ()
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not str(self.input_belief_id or "").strip():
            raise ContractViolation("AdapterContext requires input_belief_id")
        if not isinstance(self.authority, AuthorityVector):
            raise ContractViolation("AdapterContext requires an explicit AuthorityVector")
        for name in (
            "input_evidence_ids",
            "input_contribution_ids",
            "dependency_families",
            "confounders",
            "block_reasons",
        ):
            object.__setattr__(self, name, _tuple(getattr(self, name)))
        if not self.input_evidence_ids and not self.input_contribution_ids:
            raise ContractViolation("AdapterContext requires evidence or contribution ancestry")


def _run_id(output: Any, *names: str) -> str:
    for name in names:
        value = _get(output, name)
        if value:
            return str(value)
    meta = _get(output, "run_meta")
    if meta is not None and _get(meta, "run_id"):
        return str(_get(meta, "run_id"))
    provenance = _get(output, "provenance")
    if provenance is not None and _get(provenance, "run_id"):
        return str(_get(provenance, "run_id"))
    return "unversioned-output"


def _make(
    *,
    layer_id: str,
    context: AdapterContext,
    output_run_id: str,
    entity_key: str,
    target_state: str,
    confidence: float,
    payload: Mapping[str, Any],
    dependency_family: str,
    role: ContributionRole = ContributionRole.PRIMARY,
    identifiability: IdentifiabilityClass = IdentifiabilityClass.PARTIALLY_IDENTIFIED,
    confounders: Iterable[Any] = (),
    block_reasons: Iterable[Any] = (),
) -> DiagnosticContribution:
    authority = _diagnostic_authority(context.authority)
    blocks = list(context.block_reasons)
    blocks.extend(_tuple(block_reasons))
    if not authority.diagnosis_allowed:
        blocks.append("DIAGNOSIS_AUTHORITY_DENIED")
    blocks = list(_tuple(blocks))
    families = _tuple((dependency_family, *context.dependency_families))
    combined_confounders = _tuple(
        (*context.confounders, *_tuple(confounders)),
    )
    entity_payload = canonical_data(dict(payload))
    declared_evidence = (
        entity_payload.get("input_evidence_ids")
        or entity_payload.get("evidence_ids")
        or entity_payload.get("evidence_refs")
        or ()
    )
    evidence = _tuple(declared_evidence) if declared_evidence else context.input_evidence_ids
    if set(evidence) - set(context.input_evidence_ids):
        raise ContractViolation("adapter entity evidence exceeds AdapterContext lineage")
    declared_parents = entity_payload.get("input_contribution_ids") or ()
    parents = _tuple(declared_parents) if declared_parents else context.input_contribution_ids
    if set(parents) - set(context.input_contribution_ids):
        raise ContractViolation("adapter entity ancestry exceeds AdapterContext lineage")
    identity = {
        "schema_version": SCHEMA_VERSION,
        "layer_id": layer_id,
        "belief_id": context.input_belief_id,
        "output_run_id": output_run_id,
        "entity_key": entity_key,
        "target_state": target_state,
        "input_evidence_ids": evidence,
        "input_contribution_ids": parents,
        "contribution_role": role,
        "dependency_families": families,
        "identifiability_class": identifiability,
        "authority": canonical_data(authority),
        "confounders": combined_confounders,
        "block_reasons": tuple(blocks),
        "confidence": _confidence(confidence),
        "payload": entity_payload,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    supporting = evidence if role is not ContributionRole.CONTRADICTING else ()
    contradicting = evidence if role is ContributionRole.CONTRADICTING else ()
    return DiagnosticContribution(
        layer_id=layer_id,
        contribution_id=f"DC-{layer_id}-{digest}",
        input_belief_id=context.input_belief_id,
        input_evidence_ids=evidence,
        input_contribution_ids=parents,
        target_state=target_state,
        contribution_role=role,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        dependency_families=families,
        confounders=combined_confounders,
        identifiability_class=identifiability,
        authority=authority,
        block_reasons=tuple(blocks),
        confidence=_confidence(confidence),
        payload={"output_run_id": output_run_id, **entity_payload},
        generated_at=context.generated_at,
    )


def _fallback(
    layer_id: str,
    context: AdapterContext,
    run_id: str,
    target: str,
    reason: str,
    family: str,
) -> Tuple[DiagnosticContribution, ...]:
    return (
        _make(
            layer_id=layer_id,
            context=context,
            output_run_id=run_id,
            entity_key="empty",
            target_state=target,
            confidence=0.0,
            payload={"status": "no_contribution"},
            dependency_family=family,
            role=ContributionRole.SUPPORTING,
            identifiability=IdentifiabilityClass.HEURISTIC,
            block_reasons=(reason,),
        ),
    )


def adapt_layer2(output: Any, context: AdapterContext) -> Tuple[DiagnosticContribution, ...]:
    if output is None:
        raise ContractViolation("L2 adapter received no output")
    run_id = _run_id(output, "run_id")
    result = []
    for index, anomaly in enumerate(_get(output, "anomalies", ()) or ()):
        anomaly_type = _enum(_get(anomaly, "type", "unknown"))
        attribution = _get(anomaly, "attribution")
        likely_cause = str(_get(anomaly, "likely_cause", "UNKNOWN") or "UNKNOWN")
        confounders = ["UNKNOWN_CAUSE"] if likely_cause.upper() in {"UNKNOWN", "UNKNOWN_STRESS"} else []
        identifiability = (
            IdentifiabilityClass.CONFOUNDED
            if likely_cause.upper() in {"UNKNOWN", "UNKNOWN_STRESS"}
            else IdentifiabilityClass.PARTIALLY_IDENTIFIED
        )
        result.append(
            _make(
                layer_id="L2",
                context=context,
                output_run_id=run_id,
                entity_key=str(_get(anomaly, "anomaly_id", index)),
                target_state=f"condition.{_condition_token(anomaly_type)}",
                confidence=_get(anomaly, "confidence", 0.0),
                payload={
                    "anomaly_id": _get(anomaly, "anomaly_id", str(index)),
                    "anomaly_type": anomaly_type,
                    "severity": _get(anomaly, "severity", 0.0),
                    "likely_cause": likely_cause,
                    "date_range": _get(anomaly, "date_range", ()),
                    "attribution": attribution,
                },
                dependency_family="L2_VEGETATION_INFERENCE",
                identifiability=identifiability,
                confounders=confounders,
            )
        )
    if result:
        return tuple(result)
    health = _get(output, "health_index")
    if health is None:
        return _fallback("L2", context, run_id, "state.vegetation_status", "NO_L2_FINDINGS", "L2_VEGETATION_INFERENCE")
    return (
        _make(
            layer_id="L2",
            context=context,
            output_run_id=run_id,
            entity_key="health_index",
            target_state="state.vegetation_health",
            confidence=_get(health, "confidence", 0.0),
            payload={
                "overall_score": _get(health, "overall_score", 0.0),
                "ndvi_health": _get(health, "ndvi_health", 0.0),
                "water_stress_index": _get(health, "water_stress_index", 0.0),
                "vigor_trend": _get(health, "vigor_trend", "UNKNOWN"),
            },
            dependency_family="L2_VEGETATION_INFERENCE",
        ),
    )


def adapt_layer3(output: Any, context: AdapterContext) -> Tuple[DiagnosticContribution, ...]:
    if output is None:
        raise ContractViolation("L3 adapter received no output")
    run_id = _run_id(output, "run_id_l3", "run_id")
    result = []
    for index, diagnosis in enumerate(_get(output, "diagnoses", ()) or ()):
        problem_id = str(_get(diagnosis, "problem_id", index))
        result.append(
            _make(
                layer_id="L3",
                context=context,
                output_run_id=run_id,
                entity_key=problem_id,
                target_state=f"condition.{_condition_token(problem_id)}",
                confidence=_get(diagnosis, "confidence", 0.0),
                payload={
                    "problem_id": problem_id,
                    "probability": _get(diagnosis, "probability", 0.0),
                    "severity": _get(diagnosis, "severity", 0.0),
                    "drivers_used": _get(diagnosis, "drivers_used", ()),
                    "drivers_missing": _get(diagnosis, "drivers_missing", ()),
                    "evidence_trace": _get(diagnosis, "evidence_trace", ()),
                    "contra_trace": _get(diagnosis, "contra_trace", ()),
                },
                dependency_family="L3_DIAGNOSIS_INFERENCE",
                role=(
                    ContributionRole.PRIMARY
                    if _confidence(_get(diagnosis, "probability", 0.0)) >= 0.5
                    else ContributionRole.CONTRADICTING
                ),
                confounders=_get(diagnosis, "drivers_missing", ()) or (),
                identifiability=(
                    IdentifiabilityClass.IDENTIFIED
                    if _get(diagnosis, "evidence_trace", ()) and not _get(diagnosis, "drivers_missing", ())
                    else IdentifiabilityClass.PARTIALLY_IDENTIFIED
                ),
            )
        )
    return tuple(result) if result else _fallback(
        "L3", context, run_id, "system.diagnosis_status", "NO_L3_DIAGNOSES", "L3_DIAGNOSIS_INFERENCE"
    )


def adapt_layer4(output: Any, context: AdapterContext) -> Tuple[DiagnosticContribution, ...]:
    if output is None:
        raise ContractViolation("L4 adapter received no output")
    run_id = _run_id(output)
    states = _get(output, "nutrient_states", {}) or {}
    result = []
    for index, (key, state) in enumerate(states.items() if isinstance(states, Mapping) else enumerate(states)):
        nutrient = _enum(_get(state, "nutrient", key))
        result.append(
            _make(
                layer_id="L4",
                context=context,
                output_run_id=run_id,
                entity_key=str(nutrient or index),
                target_state=f"condition.nutrient_deficiency.{_token(nutrient, 'unknown')}",
                confidence=_get(state, "confidence", 0.0),
                payload={
                    "nutrient": nutrient,
                    "probability_deficient": _get(state, "probability_deficient", 0.0),
                    "state_index": _get(state, "state_index", 0.0),
                    "severity": _enum(_get(state, "severity", "UNKNOWN")),
                    "drivers_used": _get(state, "drivers_used", ()),
                    "evidence_trace": _get(state, "evidence_trace", ()),
                },
                dependency_family="L4_NUTRIENT_INFERENCE",
                role=(
                    ContributionRole.PRIMARY
                    if _confidence(_get(state, "probability_deficient", 0.0)) >= 0.5
                    else ContributionRole.CONTRADICTING
                ),
                confounders=_get(state, "confounders", ()) or (),
                identifiability=(
                    IdentifiabilityClass.CONFOUNDED
                    if _get(state, "confounders", ())
                    else IdentifiabilityClass.PARTIALLY_IDENTIFIED
                ),
            )
        )
    return tuple(result) if result else _fallback(
        "L4", context, run_id, "system.nutrient_status", "NO_L4_NUTRIENT_STATES", "L4_NUTRIENT_INFERENCE"
    )


def adapt_layer5(output: Any, context: AdapterContext) -> Tuple[DiagnosticContribution, ...]:
    if output is None:
        raise ContractViolation("L5 adapter received no output")
    run_id = _run_id(output)
    threats = _get(output, "threat_states", {}) or {}
    result = []
    for index, (key, state) in enumerate(threats.items() if isinstance(threats, Mapping) else enumerate(threats)):
        threat_id = _enum(_get(state, "threat_id", key))
        result.append(
            _make(
                layer_id="L5",
                context=context,
                output_run_id=run_id,
                entity_key=str(threat_id or index),
                target_state=f"condition.bio_threat.{_token(threat_id, 'unknown')}",
                confidence=_get(state, "confidence", 0.0),
                payload={
                    "threat_id": threat_id,
                    "threat_class": _enum(_get(state, "threat_class", "UNKNOWN")),
                    "probability": _get(state, "probability", 0.0),
                    "severity": _enum(_get(state, "severity", "UNKNOWN")),
                    "drivers_used": _get(state, "drivers_used", ()),
                    "evidence_trace": _get(state, "evidence_trace", ()),
                    "spread_pattern": _enum(_get(state, "spread_pattern", "UNKNOWN")),
                },
                dependency_family="L5_BIOTIC_INFERENCE",
                role=(
                    ContributionRole.PRIMARY
                    if _confidence(_get(state, "probability", 0.0)) >= 0.5
                    else ContributionRole.CONTRADICTING
                ),
                confounders=_get(state, "confounders", ()) or (),
                identifiability=(
                    IdentifiabilityClass.CONFOUNDED
                    if _get(state, "confounders", ())
                    else IdentifiabilityClass.PARTIALLY_IDENTIFIED
                ),
            )
        )
    return tuple(result) if result else _fallback(
        "L5", context, run_id, "system.bio_threat_status", "NO_L5_THREAT_STATES", "L5_BIOTIC_INFERENCE"
    )


def adapt_layer6(output: Any, context: AdapterContext) -> Tuple[DiagnosticContribution, ...]:
    if output is None:
        raise ContractViolation("L6 adapter received no output")
    run_id = _run_id(output)
    result = []
    for index, conflict in enumerate(_get(output, "conflict_log", ()) or ()):
        conflict_id = str(_get(conflict, "conflict_id", index))
        result.append(
            _make(
                layer_id="L6",
                context=context,
                output_run_id=run_id,
                entity_key=f"conflict:{conflict_id}",
                target_state=f"execution.conflict.{_token(_get(conflict, 'conflict_type', conflict_id), 'unknown')}",
                confidence=_get(_get(output, "quality_metrics"), "decision_reliability", 0.0),
                payload={
                    "conflict_id": conflict_id,
                    "conflict_type": _enum(_get(conflict, "conflict_type", "UNKNOWN")),
                    "source_a": _get(conflict, "source_a", {}),
                    "source_b": _get(conflict, "source_b", {}),
                    "resolution": _enum(_get(conflict, "resolution", "UNRESOLVED")),
                    "winning_source": _get(conflict, "winning_source", ""),
                },
                dependency_family="L6_CROSS_LAYER_CONFLICT",
                role=ContributionRole.CONTRADICTING,
                identifiability=IdentifiabilityClass.CONFOUNDED,
                confounders=("CROSS_LAYER_CONFLICT",),
            )
        )
    for index, metric in enumerate(_get(output, "outcome_report", ()) or ()):
        metric_id = _enum(_get(metric, "metric_id", index))
        result.append(
            _make(
                layer_id="L6",
                context=context,
                output_run_id=run_id,
                entity_key=f"outcome:{metric_id}",
                target_state=f"execution.outcome.{_token(metric_id, 'unknown')}",
                confidence=_get(metric, "confidence", 0.0),
                payload={
                    "metric_id": metric_id,
                    "delta_value": _get(metric, "delta_value", 0.0),
                    "method": _enum(_get(metric, "method", "UNKNOWN")),
                    "baseline_window": _get(metric, "baseline_window", {}),
                    "eval_window": _get(metric, "eval_window", {}),
                },
                dependency_family="L6_OUTCOME_EVALUATION",
                confounders=_get(metric, "confounders_present", ()) or (),
                identifiability=(
                    IdentifiabilityClass.CONFOUNDED
                    if _get(metric, "confounders_present", ())
                    else IdentifiabilityClass.PARTIALLY_IDENTIFIED
                ),
            )
        )
    return tuple(result) if result else _fallback(
        "L6", context, run_id, "execution.status", "NO_L6_DIAGNOSTIC_OUTPUTS", "L6_EXECUTION_SYNTHESIS"
    )


def adapt_layer7(output: Any, context: AdapterContext) -> Tuple[DiagnosticContribution, ...]:
    if output is None:
        raise ContractViolation("L7 adapter received no output")
    run_id = _run_id(output)
    reliability = _get(_get(output, "quality_metrics"), "decision_reliability", 0.0)
    result = []
    for index, option in enumerate(_get(output, "options", ()) or ()):
        crop = str(_get(option, "crop", index))
        component_states = [
            _get(option, name)
            for name in ("window", "soil", "water", "biotic", "rotation", "microclimate", "resilience")
            if _get(option, name) is not None
        ]
        component_confidences = [_confidence(_get(item, "confidence", reliability)) for item in component_states]
        confidence = min([_confidence(reliability), *component_confidences]) if component_confidences else reliability
        result.append(
            _make(
                layer_id="L7",
                context=context,
                output_run_id=run_id,
                entity_key=crop,
                target_state=f"planning.suitability.{_token(crop, 'unknown')}",
                confidence=confidence,
                payload={
                    "crop": crop,
                    "overall_rank_score": _get(option, "overall_rank_score", 0.0),
                    "suitability_percentage": _get(option, "suitability_percentage", 0.0),
                    "yield_distribution": _get(option, "yield_dist"),
                    "economic_outcome": _get(option, "econ"),
                    "component_states": component_states,
                },
                dependency_family="L7_PLANNING_SYNTHESIS",
                identifiability=IdentifiabilityClass.PARTIALLY_IDENTIFIED,
            )
        )
    return tuple(result) if result else _fallback(
        "L7", context, run_id, "planning.status", "NO_L7_OPTIONS", "L7_PLANNING_SYNTHESIS"
    )


def _l8_confidence(action: Any) -> float:
    explicit = _get(action, "driver_confidence")
    if explicit is not None:
        return _confidence(explicit)
    level = str(_enum(_get(action, "confidence", "LOW"))).upper()
    return {"HIGH": 0.85, "MODERATE": 0.6, "LOW": 0.3}.get(level, 0.0)


def adapt_layer8(output: Any, context: AdapterContext) -> Tuple[DiagnosticContribution, ...]:
    """Adapt action feasibility only; Layer 8 actions never become state truth."""

    if output is None:
        raise ContractViolation("L8 adapter received no output")
    run_id = _run_id(output, "run_id")
    result = []
    for index, action in enumerate(_get(output, "actions", ()) or ()):
        action_id = str(_get(action, "action_id", index))
        evidence = _get(action, "evidence", ()) or ()
        blocks = list(_get(action, "blocked_reason", ()) or ())
        if _get(action, "heuristic", False):
            blocks.append("HEURISTIC_ACTION_NOT_STATE_EVIDENCE")
        result.append(
            _make(
                layer_id="L8",
                context=context,
                output_run_id=run_id,
                entity_key=action_id,
                target_state=f"action.feasibility.{_token(action_id, 'unknown')}",
                confidence=_l8_confidence(action),
                payload={
                    "action_id": action_id,
                    "action_type": _enum(_get(action, "action_type", "UNKNOWN")),
                    "priority_score": _get(action, "priority_score", 0.0),
                    "is_allowed": bool(_get(action, "is_allowed", False)),
                    "requires_confirmation": bool(_get(action, "requires_confirmation", False)),
                    "evidence": evidence,
                    "primary_driver": _get(action, "primary_driver"),
                    "driver_source_family": _get(action, "driver_source_family"),
                },
                dependency_family="L8_ACTION_FEASIBILITY",
                role=ContributionRole.SUPPORTING,
                identifiability=(
                    IdentifiabilityClass.HEURISTIC
                    if _get(action, "heuristic", False)
                    else IdentifiabilityClass.PARTIALLY_IDENTIFIED
                ),
                block_reasons=blocks,
            )
        )
    return tuple(result) if result else _fallback(
        "L8", context, run_id, "action.status", "NO_L8_ACTIONS", "L8_ACTION_FEASIBILITY"
    )


ADAPTERS: Dict[str, Callable[[Any, AdapterContext], Tuple[DiagnosticContribution, ...]]] = {
    "L2": adapt_layer2,
    "L3": adapt_layer3,
    "L4": adapt_layer4,
    "L5": adapt_layer5,
    "L6": adapt_layer6,
    "L7": adapt_layer7,
    "L8": adapt_layer8,
}
