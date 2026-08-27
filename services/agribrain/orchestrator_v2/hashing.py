
import hashlib
import json
from typing import Dict, Any

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
    orch_version: str
) -> str:
    """
    Derive deterministic Run ID binding all 13 scientific identity hashes.
    Formula: AGB2-SHA256(Inputs + LayerVersions + OrchVersion)[:12]
    """
    def _get_hash(key: str, fallback_obj: Any) -> str:
        val = getattr(inputs, key, None)
        if val and str(val).strip():
            return str(val).strip()
        return _hash_payload(fallback_obj)

    # 1. Inputs (Frozen dataclass to dict)
    input_data = {
        "plot": inputs.plot_id,
        "geo": inputs.geometry_hash,
        "dates": inputs.date_range,
        "crop": inputs.crop_config,
        "crop_cycle_context": (
            inputs.crop_cycle_context.to_dict()
            if inputs.crop_cycle_context is not None else None
        ),
        "ops": inputs.operational_context,
        "policy": inputs.policy_snapshot,
        "evidence": _get_hash("evidence_set_hash", inputs.operational_context),
        "worldline": _get_hash("worldline_head_hash", inputs.geometry_hash),
        "scene_manifest": _get_hash("scene_manifest_hash", inputs.date_range),
        "weather": _get_hash("weather_set_hash", {"plot": inputs.plot_id, "dates": inputs.date_range}),
        "management": _get_hash("management_event_hash", inputs.crop_config),
        "crop_posterior": _get_hash("crop_posterior_hash", inputs.crop_config),
        "authority_version": _get_hash("authority_version", orch_version),
        "calibration_version": _get_hash("calibration_version", layer_versions),
        "model_version": _get_hash("model_version", orch_version),
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
