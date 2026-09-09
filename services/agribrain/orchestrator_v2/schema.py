# -*- coding: utf-8 -*-
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

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.common.crop_cycle_context import (
    CanonicalCropCycleContextV2,
)

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

@dataclass(frozen=True, kw_only=True)
class OrchestratorInput:
    """
    Frozen input snapshot. EVERYTHING needed to reproduce the run.
    """
    plot_namespace: Optional[PlotNamespace] = None
    geometry_hash: str = "UNKNOWN_GEO"
    date_range: Dict[str, str] = field(default_factory=lambda: {"start": "", "end": ""})
    crop_config: Dict[str, Any] = field(default_factory=dict)
    operational_context: Dict[str, Any] = field(default_factory=dict)
    policy_snapshot: Dict[str, Any] = field(default_factory=dict)
    plot_id: str = ""
    tenant_id: str = ""
    farm_id: str = ""
    field_geometry: Optional[Dict[str, Any]] = None
    polygon_geojson: Optional[Dict[str, Any]] = None
    evidence_set_hash: Optional[str] = None
    worldline_head_hash: Optional[str] = None
    scene_manifest_hash: Optional[str] = None
    weather_set_hash: Optional[str] = None
    management_event_hash: Optional[str] = None
    crop_posterior_hash: Optional[str] = None
    intent: Optional[Any] = None
    authority_version: Optional[str] = None
    calibration_version: Optional[str] = None
    model_version: Optional[str] = None
    crop_cycle_context: Optional[CanonicalCropCycleContextV2] = None

    def __post_init__(self):
        if not self.plot_namespace or not isinstance(self.plot_namespace, PlotNamespace):
            t_id = str(self.tenant_id or "").strip()
            f_id = str(self.farm_id or "").strip()
            p_id = str(self.plot_id or "").strip()
            if t_id and f_id and p_id:
                object.__setattr__(self, "plot_namespace", PlotNamespace(
                    tenant_id=t_id,
                    farm_id=f_id,
                    plot_id=p_id,
                ))

        if not self.plot_namespace or not isinstance(self.plot_namespace, PlotNamespace) or not self.plot_namespace.is_valid():
            raise ValueError(f"OrchestratorInput requires valid non-empty PlotNamespace: {self.plot_namespace}")

        object.__setattr__(self, "tenant_id", self.plot_namespace.tenant_id)
        object.__setattr__(self, "farm_id", self.plot_namespace.farm_id)
        object.__setattr__(self, "plot_id", self.plot_namespace.plot_id)

        cycle_context = self.crop_cycle_context
        if isinstance(cycle_context, dict):
            cycle_context = CanonicalCropCycleContextV2.from_mapping(
                cycle_context
            )
            object.__setattr__(self, "crop_cycle_context", cycle_context)
        if cycle_context is not None:
            if not isinstance(cycle_context, CanonicalCropCycleContextV2):
                raise ValueError("crop_cycle_context must use the V2 contract")
            if cycle_context.plot_namespace != self.plot_namespace:
                raise ValueError(
                    "crop_cycle_context namespace must match OrchestratorInput"
                )



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
    artifact_hash: str = "" # SHA256 of canonical artifact
    timestamp_utc: str = ""
    orchestrator_version: str = "2.0.0"
    layer_versions: Dict[str, str] = field(default_factory=dict)
    parents: Dict[str, str] = field(default_factory=dict)
    replay_uri: str = "" # Where it was saved
    primary_acquisition: str = "layer0"
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    intent_scope: Optional[str] = None

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
    diagnostic_integration: Optional[Dict[str, Any]] = None
    intent_scope: Optional[str] = None
    
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
            "intent_scope": self.intent_scope or self.meta.intent_scope,
            "artifact_ref": self.meta.replay_uri,
            "diagnostic_integration_status": (
                (self.diagnostic_integration or {}).get("status", "unavailable")
            )
        }
