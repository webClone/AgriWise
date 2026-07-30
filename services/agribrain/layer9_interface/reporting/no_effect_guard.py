import hashlib
import json
import copy
from pathlib import Path
from typing import Dict, Any, Optional

AGRIBRAIN_ROOT = Path(__file__).resolve().parents[2]
LEDGER_DIR = AGRIBRAIN_ROOT / "artifacts" / "validation_ledger"
PLOT_MEMORY_DIR = AGRIBRAIN_ROOT / "artifacts" / "plot_memory"
MODELS_DIR = AGRIBRAIN_ROOT / "artifacts" / "models"
SURFACES_CACHE_DIR = AGRIBRAIN_ROOT / "artifacts" / "surfaces_cache"

def hash_file(path: Path) -> str:
    if not path.exists():
        return "not_exists"
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "read_error"

def hash_directory(path: Path) -> str:
    if not path.exists():
        return "not_exists"
    # Recursively get all files and sort them to be deterministic
    files = sorted([f for f in path.glob("**/*") if f.is_file()])
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode("utf-8"))
        h.update(hash_file(f).encode("utf-8"))
    return h.hexdigest()

def hash_object(obj: Any) -> str:
    if obj is None:
        return "none"
    try:
        if hasattr(obj, "to_dict"):
            serialized = json.dumps(obj.to_dict(), sort_keys=True, default=str)
        elif hasattr(obj, "__dataclass_fields__"):
            from dataclasses import asdict
            serialized = json.dumps(asdict(obj), sort_keys=True, default=str)
        elif isinstance(obj, dict):
            serialized = json.dumps(obj, sort_keys=True, default=str)
        else:
            serialized = str(obj)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    except Exception:
        return str(id(obj))

class NoEffectGuard:
    """Context manager to ensure reporting layer runs side-effect free."""
    
    def __init__(self, context_dict: Optional[Dict[str, Any]] = None):
        self.context = context_dict or {}
        self.snapshots: Dict[str, str] = {}

    def __enter__(self):
        self.take_snapshot()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.assert_unchanged()

    def take_snapshot(self):
        # 1. Validation ledger directory
        self.snapshots["ledger"] = hash_directory(LEDGER_DIR)
        
        # 2. Plot memory directory
        self.snapshots["plot_memory"] = hash_directory(PLOT_MEMORY_DIR)
        
        # 3. Model registry directory
        self.snapshots["model_registry"] = hash_directory(MODELS_DIR)
        
        # 4. Layer 10 cache directory
        self.snapshots["layer10_cache"] = hash_directory(SURFACES_CACHE_DIR)
        
        # 5. In-memory objects
        self.snapshots["bma_weights"] = hash_object(self.context.get("bma_weights"))
        self.snapshots["asmae_output"] = hash_object(self.context.get("asmae_output"))
        self.snapshots["layer8_actions"] = hash_object(self.context.get("layer8_actions"))

    def assert_unchanged(self):
        # Compare current state with snapshots
        if self.snapshots["ledger"] != hash_directory(LEDGER_DIR):
            raise RuntimeError("Validation ledger was mutated during report generation!")
        if self.snapshots["plot_memory"] != hash_directory(PLOT_MEMORY_DIR):
            raise RuntimeError("Plot memory was mutated during report generation!")
        if self.snapshots["model_registry"] != hash_directory(MODELS_DIR):
            raise RuntimeError("Model registry was mutated during report generation!")
        if self.snapshots["layer10_cache"] != hash_directory(SURFACES_CACHE_DIR):
            raise RuntimeError("Layer 10 cache was mutated during report generation!")
        
        if self.snapshots["bma_weights"] != hash_object(self.context.get("bma_weights")):
            raise RuntimeError("BMA weights were mutated during report generation!")
        if self.snapshots["asmae_output"] != hash_object(self.context.get("asmae_output")):
            raise RuntimeError("ASMAE output was mutated during report generation!")
        if self.snapshots["layer8_actions"] != hash_object(self.context.get("layer8_actions")):
            raise RuntimeError("Layer 8 actions were mutated during report generation!")
