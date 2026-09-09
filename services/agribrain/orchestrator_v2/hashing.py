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


def generate_orchestrator_run_id(
    inputs: OrchestratorInput,
    layer_versions: Dict[str, str],
    orch_version: str,
    intent: Optional[Any] = None,
    seed: int = 42,
) -> str:
    """
    Derive deterministic Run ID binding all scientific identity dimensions.
    Formula: AGB2-SHA256(Inputs + LayerVersions + OrchVersion)[:12]
    """
    resolved_intent = "DECISION"
    if intent is not None:
        resolved_intent = str(getattr(intent, "value", intent)).upper()
    elif hasattr(inputs, "intent") and getattr(inputs, "intent", None) is not None:
        resolved_intent = str(getattr(inputs.intent, "value", inputs.intent)).upper()

    def _get_hash(key: str, default_marker: str) -> str:
        val = getattr(inputs, key, None)
        if val and str(val).strip():
            return str(val).strip()
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
        "authority_version": _get_hash("authority_version", orch_version),
        "calibration_version": _get_hash("calibration_version", "v1.0"),
        "model_version": _get_hash("model_version", orch_version),
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
    
    return f"AGB2-{h}"


generate_scientific_run_id = generate_orchestrator_run_id
