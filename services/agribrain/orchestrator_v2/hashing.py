
import hashlib
import json
from typing import Dict, Any

from orchestrator_v2.schema import OrchestratorInput

def _canonical_json(obj: Any) -> str:
    """Produces consistent JSON string for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)

def generate_orchestrator_run_id(
    inputs: OrchestratorInput,
    layer_versions: Dict[str, str],
    orch_version: str
) -> str:
    """
    Derive deterministic Run ID.
    Formula: AGB2-SHA256(Inputs + LayerVersions + OrchVersion)[:12]
    """
    
    # 1. Inputs (Frozen dataclass to dict)
    input_data = {
        "plot": inputs.plot_id,
        "geo": inputs.geometry_hash,
        "dates": inputs.date_range,
        "crop": inputs.crop_config,
        "ops": inputs.operational_context,
        "policy": inputs.policy_snapshot
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
