"""
ML Pipeline Framework
Full pipeline: ingest → features → train → infer → report
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import hashlib
import traceback

# Pipeline storage
PIPELINE_ROOT = Path(__file__).parent.parent / "pipelines"
PIPELINE_ROOT.mkdir(exist_ok=True)


class PipelineStage(Enum):
    INGEST = "ingest"
    FEATURES = "features"
    TRAIN = "train"
    INFER = "infer"
    REPORT = "report"


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineRun:
    """Tracks a single pipeline execution."""
    
    def __init__(self, pipeline_id: str, run_id: Optional[str] = None):
        self.pipeline_id = pipeline_id
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.stages: Dict[str, Dict] = {}
        self.status = StageStatus.PENDING
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.artifacts: Dict[str, str] = {}
        
        # Run directory
        self.run_dir = PIPELINE_ROOT / pipeline_id / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
    
    def start_stage(self, stage: PipelineStage):
        """Mark stage as running."""
        self.stages[stage.value] = {
            "status": StageStatus.RUNNING.value,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "metrics": {},
            "error": None
        }
        self._save()
    
    def complete_stage(self, stage: PipelineStage, metrics: Dict = None):
        """Mark stage as completed."""
        if stage.value in self.stages:
            self.stages[stage.value]["status"] = StageStatus.COMPLETED.value
            self.stages[stage.value]["completed_at"] = datetime.now().isoformat()
            self.stages[stage.value]["metrics"] = metrics or {}
        self._save()
    
    def fail_stage(self, stage: PipelineStage, error: str):
        """Mark stage as failed."""
        if stage.value in self.stages:
            self.stages[stage.value]["status"] = StageStatus.FAILED.value
            self.stages[stage.value]["completed_at"] = datetime.now().isoformat()
            self.stages[stage.value]["error"] = error
        self.status = StageStatus.FAILED
        self._save()
    
    def add_artifact(self, name: str, path: str):
        """Register an artifact produced by the pipeline."""
        self.artifacts[name] = path
        self._save()
    
    def _save(self):
        """Persist run state to disk."""
        state = {
            "pipeline_id": self.pipeline_id,
            "run_id": self.run_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stages": self.stages,
            "artifacts": self.artifacts
        }
        with open(self.run_dir / "run_state.json", "w") as f:
            json.dump(state, f, indent=2)


class BasePipeline(ABC):
    """Base class for ML pipelines."""
    
    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self.pipeline_dir = PIPELINE_ROOT / pipeline_id
        self.pipeline_dir.mkdir(parents=True, exist_ok=True)
        
        # Model registry
        self.models_dir = self.pipeline_dir / "models"
        self.models_dir.mkdir(exist_ok=True)
    
    @abstractmethod
    def ingest(self, run: PipelineRun, config: Dict) -> Dict:
        """Stage 1: Ingest raw data from sources."""
        pass
    
    @abstractmethod
    def features(self, run: PipelineRun, data: Dict, config: Dict) -> Dict:
        """Stage 2: Feature engineering and transformation."""
        pass
    
    @abstractmethod
    def train(self, run: PipelineRun, features: Dict, config: Dict) -> Dict:
        """Stage 3: Train model on features."""
        pass
    
    @abstractmethod
    def infer(self, run: PipelineRun, model: Any, inputs: Dict) -> Dict:
        """Stage 4: Run inference with trained model."""
        pass
    
    @abstractmethod
    def report(self, run: PipelineRun, results: Dict) -> Dict:
        """Stage 5: Generate reports and metrics."""
        pass
    
    def execute(self, config: Dict = None) -> PipelineRun:
        """Execute full pipeline."""
        config = config or {}
        run = PipelineRun(self.pipeline_id)
        run.started_at = datetime.now().isoformat()
        run.status = StageStatus.RUNNING
        
        try:
            # Stage 1: Ingest
            run.start_stage(PipelineStage.INGEST)
            data = self.ingest(run, config.get("ingest", {}))
            run.complete_stage(PipelineStage.INGEST, {"records": len(data.get("records", []))})
            
            # Stage 2: Features
            run.start_stage(PipelineStage.FEATURES)
            features = self.features(run, data, config.get("features", {}))
            run.complete_stage(PipelineStage.FEATURES, {"feature_count": len(features.get("columns", []))})
            
            # Stage 3: Train
            run.start_stage(PipelineStage.TRAIN)
            model_result = self.train(run, features, config.get("train", {}))
            run.complete_stage(PipelineStage.TRAIN, model_result.get("metrics", {}))
            
            # Stage 4: Infer (validation)
            run.start_stage(PipelineStage.INFER)
            predictions = self.infer(run, model_result.get("model"), features.get("validation", {}))
            run.complete_stage(PipelineStage.INFER, {"predictions": len(predictions.get("results", []))})
            
            # Stage 5: Report
            run.start_stage(PipelineStage.REPORT)
            report = self.report(run, {
                "model": model_result,
                "predictions": predictions,
                "features": features
            })
            run.complete_stage(PipelineStage.REPORT, report)
            
            run.status = StageStatus.COMPLETED
            run.completed_at = datetime.now().isoformat()
            
        except Exception as e:
            current_stage = next(
                (s for s, v in run.stages.items() if v["status"] == StageStatus.RUNNING.value),
                "unknown"
            )
            run.fail_stage(PipelineStage(current_stage), str(e) + "\n" + traceback.format_exc())
        
        return run
    
    def get_latest_model(self) -> Optional[Path]:
        """Get path to latest trained model."""
        models = sorted(self.models_dir.glob("*.json"), reverse=True)
        return models[0] if models else None


class ModelRegistry:
    """Central registry for trained models."""
    
    def __init__(self):
        self.registry_path = PIPELINE_ROOT / "model_registry.json"
        self._load()
    
    def _load(self):
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                self.registry = json.load(f)
        else:
            self.registry = {"models": {}}
    
    def _save(self):
        with open(self.registry_path, "w") as f:
            json.dump(self.registry, f, indent=2)
    
    def register(self, model_name: str, model_path: str, metrics: Dict, version: str = None):
        """Register a trained model."""
        version = version or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if model_name not in self.registry["models"]:
            self.registry["models"][model_name] = {"versions": {}, "latest": None}
        
        self.registry["models"][model_name]["versions"][version] = {
            "path": model_path,
            "metrics": metrics,
            "registered_at": datetime.now().isoformat()
        }
        self.registry["models"][model_name]["latest"] = version
        self._save()
        
        return version
    
    def get_model(self, model_name: str, version: str = None) -> Optional[Dict]:
        """Get model info by name and version."""
        if model_name not in self.registry["models"]:
            return None
        
        version = version or self.registry["models"][model_name]["latest"]
        return self.registry["models"][model_name]["versions"].get(version)
    
    def list_models(self) -> Dict:
        """List all registered models."""
        return {
            name: {
                "latest": info["latest"],
                "version_count": len(info["versions"])
            }
            for name, info in self.registry["models"].items()
        }


# Global model registry
model_registry = ModelRegistry()
