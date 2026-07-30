"""
History schemas for ASMAE Historical Ingestion.
Defines types for historical Kalman inputs/outputs and crop-season segmentation.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

@dataclass
class HistoricalSceneMetadata:
    scene_id: str
    sensor: str                  # S1, S2
    acquisition_time: datetime
    cloud_cover: Optional[float]
    valid_fraction: float
    local_path: Dict[str, str]   # maps band name to local cached file path

@dataclass
class CropSeasonSegment:
    season_id: str
    start_date: datetime
    end_date: datetime
    is_active_crop: bool
    scenes: List[HistoricalSceneMetadata] = field(default_factory=list)

@dataclass
class HistoricalSmootherOutput:
    plot_id: str
    geometry_hash: str
    timestamps: List[datetime]
    states_smoothed: List[Any]  # smoothed state vectors (EKS outputs)
    covariances_smoothed: List[Any] # smoothed state covariance matrices
    diagnostics: Dict[str, Any] = field(default_factory=dict)
