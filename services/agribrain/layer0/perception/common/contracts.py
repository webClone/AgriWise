"""
Shared perception engine contracts.

Defines the base input/output types that ALL perception engines must use.
This is the strict contract layer — every engine produces PerceptionEngineOutput
which the shared packet_adapter converts into ObservationPackets.

Rules enforced by these contracts:
  - No direct agronomic recommendation
  - No direct overwrite of full plot state
  - Every output has uncertainty (sigma)
  - Every output has source-specific QA
  - Every output has provenance
  - Every output can be cross-checked by ValidationGraph
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PerceptionEngineFamily(str, Enum):
    """The four perception engine families."""
    SATELLITE_RGB = "satellite_rgb"
    FARMER_PHOTO = "farmer_photo"
    DRONE = "drone"
    IP_CAMERA = "ip_camera"


@dataclass
class PerceptionVariable:
    """
    A single extracted variable from perception inference.
    
    This is the fundamental unit of perception output.
    Each variable has a value, uncertainty, and confidence.
    """
    name: str                        # e.g. "vegetation_fraction", "rgb_anomaly_score"
    value: float                     # estimated quantity
    sigma: float                     # uncertainty standard deviation
    confidence: float                # model confidence 0–1
    feasibility_gated: bool = False  # True if this variable was checked for feasibility
    feasible: bool = True            # False if feasibility check blocked emission
    unit: str = ""                   # e.g. "fraction", "degrees", "score"
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_emittable(self) -> bool:
        """Whether this variable should be emitted (feasibility check passed)."""
        if self.feasibility_gated:
            return self.feasible
        return True


@dataclass
class PerceptionArtifact:
    """
    A perception-generated artifact (mask, heatmap, confidence map).
    
    Artifacts are auxiliary outputs that support visualization or
    downstream cross-checking, but are not direct Kalman observations.
    """
    artifact_type: str     # "vegetation_mask", "anomaly_map", "confidence_map"
    data_ref: str          # URI, path, or inline key
    mime_type: str = "application/octet-stream"
    shape: Optional[Tuple[int, int]] = None  # (height, width) if raster
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QAResult:
    """
    Base QA result returned by every engine's QA module.
    
    This is the structured quality gate. If usable=False, the engine
    may still emit outputs with very low reliability, but downstream
    layers will nearly ignore them.
    """
    usable: bool = True
    qa_score: float = 1.0           # 0–1 overall quality
    reliability_weight: float = 1.0  # 0–1 Kalman trust weight
    sigma_inflation: float = 1.0     # Multiply base sigma by this
    flags: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerceptionEngineInput:
    """
    Base input for any perception engine.
    
    Engine-specific subclasses add their own fields
    (e.g. SatelliteRGBEngineInput adds ground_resolution_m, plot_polygon).
    """
    plot_id: str = ""
    timestamp: Optional[datetime] = None
    geometry_scope: str = "plot"     # "plot", "zone", "pixel"
    bbox: Optional[Tuple[float, float, float, float]] = None  # (min_lng, min_lat, max_lng, max_lat)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ZoneOutput:
    """Per-zone perception outputs for zone-capable engines."""
    zone_id: str = ""
    variables: Dict[str, float] = field(default_factory=dict)
    # e.g. {"canopy_fraction": 0.65, "anomaly_score": 0.12, "structural_uniformity": 0.85}
    confidence: float = 0.5


@dataclass
class PerceptionEngineOutput:
    """
    Base output from any perception engine.
    
    This is what the shared packet_adapter consumes to produce
    ObservationPackets. Every engine must fill this contract.
    """
    # Identity
    engine_family: PerceptionEngineFamily = PerceptionEngineFamily.SATELLITE_RGB
    plot_id: str = ""
    timestamp: Optional[datetime] = None
    geometry_scope: str = "plot"

    # QA
    qa_score: float = 1.0
    reliability_weight: float = 1.0
    sigma_inflation: float = 1.0
    qa_flags: List[str] = field(default_factory=list)  # Engine-specific QA flags

    # Variables (the core observation products)
    variables: List[PerceptionVariable] = field(default_factory=list)

    # Zone-level outputs (for zone-capable engines)
    zone_outputs: List[ZoneOutput] = field(default_factory=list)

    # Artifacts (masks, heatmaps, confidence maps)
    artifacts: List[PerceptionArtifact] = field(default_factory=list)

    # Provenance
    provenance_chain: List[str] = field(default_factory=list)
    model_versions: Dict[str, str] = field(default_factory=dict)

    # Content hash for caching
    image_content_hash: str = ""

    def get_emittable_variables(self) -> List[PerceptionVariable]:
        """Return only variables that passed feasibility gating."""
        return [v for v in self.variables if v.is_emittable]
