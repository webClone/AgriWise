"""MESIA Canopy & Surface Truth Fixtures — R6 §1.5 & §10.2.

Provides ground-truth models for vegetation canopy, leaf wetness duration,
soil surface roughness, residue, and environmental wind motion fixtures.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CanopySurfaceTruthRecord:
    """Ground-truth context for canopy structure, moisture, and surface state."""

    record_id: str
    plot_or_fixture_id: str
    measured_at: datetime

    # Canopy State
    leaf_area_index: Optional[float] = None
    """m2/m2."""

    canopy_height_m: Optional[float] = None
    canopy_water_content_kg_m2: Optional[float] = None
    leaf_wetness_fraction: float = 0.0
    """[0.0, 1.0] (0 = dry, 1 = dripping wet)."""

    # Surface Roughness & Boundary
    surface_rms_roughness_height_cm: Optional[float] = None
    """s (RMS height standard deviation)."""

    correlation_length_cm: Optional[float] = None
    """l (autocorrelation length)."""

    standing_water_fraction: float = 0.0
    crop_residue_cover_fraction: float = 0.0

    # Dynamic / Motion Context
    wind_speed_m_s: Optional[float] = None
    wind_gust_m_s: Optional[float] = None
    canopy_motion_detected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "plot_or_fixture_id": self.plot_or_fixture_id,
            "measured_at": self.measured_at.isoformat(),
            "leaf_area_index": self.leaf_area_index,
            "canopy_height_m": self.canopy_height_m,
            "canopy_water_content_kg_m2": self.canopy_water_content_kg_m2,
            "leaf_wetness_fraction": self.leaf_wetness_fraction,
            "surface_rms_roughness_height_cm": self.surface_rms_roughness_height_cm,
            "correlation_length_cm": self.correlation_length_cm,
            "standing_water_fraction": self.standing_water_fraction,
            "crop_residue_cover_fraction": self.crop_residue_cover_fraction,
            "wind_speed_m_s": self.wind_speed_m_s,
            "wind_gust_m_s": self.wind_gust_m_s,
            "canopy_motion_detected": self.canopy_motion_detected,
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
