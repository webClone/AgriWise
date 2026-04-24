
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from datetime import datetime

# Import Upstream Schemas for Type Hinting
from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.layer2_veg_int.schema import VegIntOutput
from services.agribrain.layer3_decision.schema import DecisionOutput, ExecutionPlan, DegradationMode
from services.agribrain.layer4_nutrients.schema import NutrientIntelligenceOutput
from services.agribrain.layer5_bio.schema import BioThreatIntelligenceOutput
from services.agribrain.layer6_exec.schema import Layer6Output, ExecutionState
from services.agribrain.layer10_sire.schema import Layer10Output

# Enums

class LayerStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class GlobalDegradation(str, Enum):
    NORMAL = "NORMAL"
    NO_OPTICAL = "NO_OPTICAL" # Weather only
    NO_SAR = "NO_SAR"
    LOW_SAR_CADENCE = "LOW_SAR_CADENCE"
    PARTIAL_DATA = "PARTIAL_DATA"
    CRITICAL_FAILURE = "CRITICAL_FAILURE" # Unsafe to proceed

# Data Structures

@dataclass(frozen=True)
class OrchestratorInput:
    """
    Frozen input snapshot. EVERYTHING needed to reproduce the run.
    """
    plot_id: str
    geometry_hash: str # SHA256 of WKT/GeoJSON
    date_range: Dict[str, str] # {start, end}
    
    # Context
    crop_config: Dict[str, Any] # Crop type, variety, planting date
    operational_context: Dict[str, Any] # Equipment, budget, workforce
    policy_snapshot: Dict[str, Any] # Regulatory rules, quotas
    
    # Raw Input References (optional, if passing big objects)
    # usually we rely on the runner to fetch L1 inputs or pass them in
    
@dataclass
class LayerResult:
    """
    Generic container for a layer's output.
    """
    layer_id: str
    status: LayerStatus
    output: Optional[Any] # The specific LayerXOutput object
    errors: List[str] = field(default_factory=list)
    degradation_flags: List[str] = field(default_factory=list)
    run_id: str = "" # The specific Lx-{hash}

@dataclass
class GlobalQuality:
    """
    aggregated quality metrics.
    """
    modes: List[GlobalDegradation] # Set of active modes
    reliability_score: float # 0.0 - 1.0 (Weighted)
    missing_drivers: List[str]
    critical_errors: List[str]
    critical_failure: bool = False

@dataclass
class RunMeta:
    """
    Top-level run metadata.
    """
    orchestrator_run_id: str # AGB2-{hash}
    artifact_hash: str # SHA256 of canonical artifact (excluding volatile fields)
    timestamp_utc: str
    orchestrator_version: str
    layer_versions: Dict[str, str]
    parents: Dict[str, str] = field(default_factory=dict) # layer_id -> run_id
    replay_uri: str = "" # Where it was saved

@dataclass
class RunArtifact:
    """
    The One True Artifact.
    """
    meta: RunMeta
    inputs: OrchestratorInput
    global_quality: GlobalQuality
    
    # Layer Outputs (Raw)
    layer_1: Optional[LayerResult] = None
    layer_2: Optional[LayerResult] = None
    layer_3: Optional[LayerResult] = None
    layer_4: Optional[LayerResult] = None
    layer_5: Optional[LayerResult] = None
    layer_6: Optional[LayerResult] = None
    layer_7: Optional[LayerResult] = None
    layer_8: Optional[LayerResult] = None
    layer_10: Optional[LayerResult] = None  # SIRE (spatial rendering)
    layer_9: Optional[LayerResult] = None   # Interface (after L10)
    
    # Unified Results
    final_execution_plan: Optional[ExecutionPlan] = None
    top_findings: List[str] = field(default_factory=list)
    
    # Audit
    lineage_map: Dict[str, str] = field(default_factory=dict) # {L1: id, L2: id...}
    layer_lineage: List[Dict[str, str]] = field(default_factory=list) # Detailed audit {layer, inputs_ref, code_ref}

    def to_summary_json(self) -> Dict[str, Any]:
        """Lightweight summary for API responses."""
        return {
            "run_id": self.meta.orchestrator_run_id,
            "status": "CRITICAL_FAILURE" if self.global_quality.critical_failure else "OK",
            "modes": [m.value for m in self.global_quality.modes],
            "reliability": self.global_quality.reliability_score,
            "plan_tasks": len(self.final_execution_plan.tasks) if self.final_execution_plan else 0,
            "findings": self.top_findings,
            "artifact_ref": self.meta.replay_uri
        }
