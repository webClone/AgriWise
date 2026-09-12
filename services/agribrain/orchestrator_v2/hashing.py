import hashlib
import json
from typing import Dict, Any, Optional

from services.agribrain.orchestrator_v2.schema import OrchestratorInput


def _canonical_json(obj: Any) -> str:
    """Produces consistent JSON string for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _hash_payload(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class StructuredRunIdentity:
    """Structured identity contract distinguishing request, execution, and scientific reproducibility."""
    run_id: str
    request_id: str
    execution_id: str
    scientific_run_id: Optional[str]
    incomplete_run_id: Optional[str]
    is_scientifically_complete: bool
    missing_evidence_keys: Tuple[str, ...]
    identity_tier: str  # "SCIENTIFIC_FROZEN" | "INCOMPLETE_MONITORING_ONLY"
    reproducibility_allowed: bool
    prescription_allowed: bool
    forecast_evaluation_allowed: bool


def derive_structured_run_identity(
    inputs: OrchestratorInput,
    layer_versions: Dict[str, str],
    orch_version: str,
    intent: Optional[Any] = None,
    seed: int = 42,
    request_id: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> StructuredRunIdentity:
    """Derive deterministic structured identity binding physical evidence dimensions.

    Differentiates fully frozen, reproducible scientific runs (AGB2-{h}) from
    partially ungrounded monitoring runs (AGB2-INC-{h}).
    """
    resolved_intent = "DECISION"
    if intent is not None:
        resolved_intent = str(getattr(intent, "value", intent)).upper()
    elif hasattr(inputs, "intent") and getattr(inputs, "intent", None) is not None:
        resolved_intent = str(getattr(inputs.intent, "value", inputs.intent)).upper()

    missing_keys = []

    def _get_hash(key: str, default_marker: str) -> str:
        val = getattr(inputs, key, None)
        if val and str(val).strip():
            return str(val).strip()
        missing_keys.append(key)
        return default_marker

    # 1. Inputs (Frozen dataclass to dict) - strictly bind physical evidence without request-attribute masking
    input_data = {
        "plot": inputs.plot_id,
        "geo": inputs.geometry_hash,
        "dates": inputs.date_range,
        "crop": inputs.crop_config,
        "crop_cycle_context": (
            inputs.crop_cycle_context.to_dict()
            if inputs.crop_cycle_context is not None and hasattr(inputs.crop_cycle_context, "to_dict") else None
        ),
        "intent": resolved_intent,
        "ops": inputs.operational_context,
        "policy": inputs.policy_snapshot,
        "evidence": _get_hash("evidence_set_hash", "MISSING_EVIDENCE_SET"),
        "worldline": _get_hash("worldline_head_hash", "MISSING_WORLDLINE_HEAD"),
        "scene_manifest": _get_hash("scene_manifest_hash", "MISSING_SCENE_MANIFEST"),
        "weather": _get_hash("weather_set_hash", "MISSING_WEATHER_EVIDENCE"),
        "management": _get_hash("management_event_hash", "MISSING_MANAGEMENT_EVENT"),
        "crop_posterior": _get_hash("crop_posterior_hash", "MISSING_CROP_POSTERIOR"),
        "authority_version": getattr(inputs, "authority_version", None) or orch_version,
        "calibration_version": getattr(inputs, "calibration_version", None) or "v1.0",
        "model_version": getattr(inputs, "model_version", None) or orch_version,
        "seed": seed,
    }

    # 2. Versions
    version_data = {
        "orch": orch_version,
        "layers": layer_versions
    }

    # 3. Hash
    raw = _canonical_json(input_data) + "|" + _canonical_json(version_data)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    req_id = request_id or getattr(inputs, "request_id", None) or f"REQ-{h[:8]}"
    exec_id = execution_id or getattr(inputs, "execution_id", None) or f"EXEC-{h[:8]}"

    is_complete = (len(missing_keys) == 0)
    if is_complete:
        run_id = f"AGB2-{h}"
        return StructuredRunIdentity(
            run_id=run_id,
            request_id=req_id,
            execution_id=exec_id,
            scientific_run_id=run_id,
            incomplete_run_id=None,
            is_scientifically_complete=True,
            missing_evidence_keys=(),
            identity_tier="SCIENTIFIC_FROZEN",
            reproducibility_allowed=True,
            prescription_allowed=True,
            forecast_evaluation_allowed=True,
        )
    else:
        run_id = f"AGB2-INC-{h}"
        return StructuredRunIdentity(
            run_id=run_id,
            request_id=req_id,
            execution_id=exec_id,
            scientific_run_id=None,
            incomplete_run_id=run_id,
            is_scientifically_complete=False,
            missing_evidence_keys=tuple(missing_keys),
            identity_tier="INCOMPLETE_MONITORING_ONLY",
            reproducibility_allowed=False,
            prescription_allowed=False,
            forecast_evaluation_allowed=False,
        )


def generate_orchestrator_run_id(
    inputs: OrchestratorInput,
    layer_versions: Dict[str, str],
    orch_version: str,
    intent: Optional[Any] = None,
    seed: int = 42,
) -> str:
    """Derive deterministic Run ID binding all scientific identity dimensions."""
    identity = derive_structured_run_identity(
        inputs=inputs,
        layer_versions=layer_versions,
        orch_version=orch_version,
        intent=intent,
        seed=seed,
    )
    return identity.run_id


generate_scientific_run_id = generate_orchestrator_run_id
