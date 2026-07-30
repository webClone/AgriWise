from __future__ import annotations
import os
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

# Standard models root
AGRIBRAIN_ROOT = Path(__file__).resolve().parents[1]
MODELS_ROOT = AGRIBRAIN_ROOT / "artifacts" / "models"

ALLOWED_STATUSES = {
    "candidate",
    "shadow",
    "evaluation",
    "approved_shadow_expert",
    "approved_supporting_expert_future",
    "revoked"
}

ALLOWED_TRANSITIONS = {
    ("candidate", "shadow"),
    ("shadow", "evaluation"),
    ("evaluation", "approved_shadow_expert"),
    ("approved_shadow_expert", "evaluation"),
    ("evaluation", "shadow"),
    ("candidate", "revoked"),
    ("shadow", "revoked"),
    ("evaluation", "revoked"),
    ("approved_shadow_expert", "revoked"),
}

def validate_model_path(model_id: str, artifact_path: str) -> None:
    if not model_id or not isinstance(model_id, str) or model_id.strip() == "":
        raise ValueError("empty_model_id")
    if "/" in model_id or "\\" in model_id or ".." in model_id or ":" in model_id:
        raise ValueError("unsafe_model_id_path_traversal")
        
    if not artifact_path or not isinstance(artifact_path, str) or artifact_path.strip() == "":
        raise ValueError("empty_artifact_path")
        
    # Block path traversal
    if ".." in artifact_path:
        raise ValueError("unsafe_artifact_path_traversal")
        
    # Block absolute paths (starts with drive letter, or absolute path indicators, or root slashes)
    if os.path.isabs(artifact_path) or ":" in artifact_path or artifact_path.startswith("/") or artifact_path.startswith("\\"):
        raise ValueError("absolute_artifact_path_forbidden")
        
    # Check expected extensions
    ext = Path(artifact_path).suffix.lower()
    if ext in (".pkl", ".pickle"):
        raise ValueError("pickle_artifacts_forbidden")
    if ext not in (".json", ".npz"):
        raise ValueError(f"unexpected_file_extension: {ext}")

class ModelRegistry:
    @staticmethod
    def save_manifest(model_id: str, manifest: Dict[str, Any]) -> None:
        validate_model_path(model_id, manifest.get("parameters_ref", "models/dummy.json"))
        
        # Guard against pickle
        ref = manifest.get("parameters_ref", "")
        if ".pkl" in ref or ".pickle" in ref:
            raise ValueError("pickle_artifacts_forbidden")
            
        manifest["model_schema_version"] = "v88_model_registry_v1"
        manifest["created_by_v88_shadow_pipeline"] = True
        
        # Determine artifact format
        ext = Path(ref).suffix.lower().replace(".", "")
        if ext not in ("json", "npz"):
            raise ValueError(f"unexpected_file_extension: .{ext}")
        manifest["artifact_format"] = ext
        
        if not manifest.get("artifact_hash"):
            raise ValueError("missing_artifact_hash")
        if not manifest.get("training_dataset_hash"):
            raise ValueError("missing_training_dataset_hash")
            
        status = manifest.get("status", "candidate")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"invalid_status: {status}")
            
        manifest_path = MODELS_ROOT / model_id / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    @staticmethod
    def get_approved_models() -> List[str]:
        if not MODELS_ROOT.exists():
            return []
        approved = []
        for p in MODELS_ROOT.iterdir():
            if p.is_dir() and (p / "manifest.json").exists():
                try:
                    manifest = ModelRegistry.load_manifest(p.name)
                    if manifest.get("status") == "approved_shadow_expert":
                        approved.append(p.name)
                except Exception:
                    pass
        return approved

    @staticmethod
    def load_manifest(model_id: str) -> Dict[str, Any]:
        validate_model_path(model_id, "dummy.json")
        manifest_path = MODELS_ROOT / model_id / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Model manifest not found: {model_id}")
            
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        ref = manifest.get("parameters_ref", "")
        # Re-run safety path validation on stored parameters_ref
        validate_model_path(model_id, ref)
        
        status = manifest.get("status", "candidate")
        param_path = MODELS_ROOT.parent / ref
        
        # Require file existence for active statuses
        if status in ("shadow", "evaluation", "approved_shadow_expert", "approved_supporting_expert_future"):
            if not param_path.exists():
                raise FileNotFoundError("model_artifact_missing")
            
        # Verify artifact hash if file exists
        if param_path.exists():
            with open(param_path, "rb") as f:
                content = f.read()
            computed_hash = hashlib.sha256(content).hexdigest()
            if computed_hash != manifest.get("artifact_hash"):
                raise ValueError("corrupt_artifact_hash_mismatch")
                
        return manifest

    @staticmethod
    def transition_status(
        model_id: str,
        new_status: str,
        metrics: Optional[Dict[str, Any]] = None,
        holdout_metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        manifest = ModelRegistry.load_manifest(model_id)
        old_status = manifest.get("status", "candidate")
        
        if new_status not in ALLOWED_STATUSES:
            raise ValueError(f"invalid_status: {new_status}")
            
        # Transition transition check
        if (old_status, new_status) not in ALLOWED_TRANSITIONS:
            raise ValueError(f"invalid_status_transition: {old_status} -> {new_status}")
            
        # Transition checks: evaluation requires metrics
        if new_status == "evaluation":
            if not metrics:
                raise ValueError("metrics_required_for_evaluation")
            manifest["evaluation_metrics"] = metrics
            
        # approved requires holdout metrics
        if new_status == "approved_shadow_expert":
            if not holdout_metrics:
                raise ValueError("holdout_metrics_required_for_approval")
            manifest["holdout_metrics"] = holdout_metrics
            
        manifest["status"] = new_status
        ModelRegistry.save_manifest(model_id, manifest)

def predict_expert(model_id: str, means: Dict[str, Any]) -> Dict[str, List[float]]:
    manifest = ModelRegistry.load_manifest(model_id)
    status = manifest.get("status")
    if status == "revoked":
        return {nid: list(state) for nid, state in means.items()}
        
    ref = manifest.get("parameters_ref", "")
    param_path = MODELS_ROOT.parent / ref
    
    if not param_path.exists():
        raise FileNotFoundError("model_artifact_missing")
        
    weights = [1.0] + [0.0] * 12
    if ref.endswith(".json"):
        with open(param_path, "r", encoding="utf-8") as f:
            weights = json.load(f).get("weights", weights)
    elif ref.endswith(".npz"):
        import numpy as np
        try:
            with np.load(param_path, allow_pickle=False) as data:
                for key in data.files:
                    arr = data[key]
                    if arr.dtype == object or arr.dtype.hasobject:
                        raise ValueError("NPZ object arrays forbidden")
                weights = data["weights"].tolist() if "weights" in data else weights
        except ValueError as e:
            err_msg = str(e)
            if "Object arrays" in err_msg or "allow_pickle" in err_msg or "pickle" in err_msg or "NPZ object arrays forbidden" in err_msg:
                raise ValueError("NPZ object arrays forbidden")
            raise
                
    predictions = {}
    for nid, state in means.items():
        pred = list(state)
        if isinstance(pred, list) and len(pred) > 0:
            pred[0] = float(pred[0] * weights[0])
        predictions[nid] = pred
    return predictions

