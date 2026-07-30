
import json
import os
from typing import Protocol, Any
from dataclasses import asdict

from services.agribrain.orchestrator_v2.schema import RunArtifact

class ArtifactStore(Protocol):
    def save(self, artifact: RunArtifact) -> str:
        ...
    def load(self, run_id: str) -> RunArtifact:
        ...

class LocalJsonStore:
    def __init__(self, base_path: str = "data/artifacts"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
        
    def save(self, artifact: RunArtifact) -> str:
        """
        Saves artifact to JSON. Returns URI.
        """
        rid = artifact.meta.orchestrator_run_id
        fpath = os.path.join(self.base_path, f"{rid}.json")
        
        # Serialize
        data = asdict(artifact)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
            
        return f"file:///{os.path.abspath(fpath)}"

    def load(self, run_id: str) -> Any:
        # Stub for loading logic
        fpath = os.path.join(self.base_path, f"{run_id}.json")
        with open(fpath, 'r') as f:
            return json.load(f)
