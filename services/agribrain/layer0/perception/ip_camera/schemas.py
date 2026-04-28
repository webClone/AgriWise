from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from layer0.perception.common.contracts import (
    PerceptionEngineInput,
    PerceptionEngineOutput,
    QAResult
)


class SceneChangeType(str, Enum):
    CAMERA_SHIFT = "camera_shift"
    LIGHTING_SHIFT = "lighting_shift"
    CROP_CHANGE = "crop_change"
    UNKNOWN = "unknown"


@dataclass
class IPCameraSceneContext:
    """Computed context about the visible scene."""
    visible_crop_fraction: float = 0.0
    visible_soil_fraction: float = 0.0
    shadow_fraction: float = 0.0
    background_fraction: float = 0.0
    
    # Registration quality tracking
    registration_confidence: float = 1.0
    
    # Baseline comparison results
    camera_pose_drift_score: float = 0.0  # 0 = no drift, 1 = severely moved
    scene_change_type: SceneChangeType = SceneChangeType.UNKNOWN
    lighting_match_confidence: float = 1.0  # How well this matches the baseline's lighting


@dataclass
class IPCameraQAResult(QAResult):
    """Camera specific QA checks."""
    blur_score: float = 0.0
    exposure_score: float = 1.0
    lens_occlusion_score: float = 0.0
    rain_on_lens_detected: bool = False
    night_low_light: bool = False
    camera_moved: bool = False


@dataclass
class IPCameraEngineInput(PerceptionEngineInput):
    camera_id: str = ""
    frame_ref: str = ""
    camera_registration_ref: str = ""
    frame_manifest_ref: Optional[str] = None
    
    # Optional contexts passed down
    weather_context: Dict[str, Any] = field(default_factory=dict)
    satellite_context: Dict[str, Any] = field(default_factory=dict)
    expected_crop_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CameraValidationResult:
    """Auditable result of a single cross-check."""
    check_name: str
    expected_signal: str
    observed_signal: str
    agreement: bool
    agreement_reason: str
    confidence: float
    affected_upstream_source: str  # e.g., "weather-driven-moisture", "satellite-ndvi"


@dataclass
class IPCameraEngineOutput(PerceptionEngineOutput):
    scene_context: Optional[IPCameraSceneContext] = None
    weather_consistency_score: float = 1.0
    satellite_consistency_score: float = 1.0
    
    # Structured auditable validations
    validation_checks: List[CameraValidationResult] = field(default_factory=list)
