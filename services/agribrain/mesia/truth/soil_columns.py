"""MESIA Soil Column Truth Facility & Hysteresis Modeling — R6 §1.4 & §10.1 (E1).

Models controlled, replicated soil columns across >=5 textures, bulk density,
volumetric moisture, EC/salinity, temperature, depth strata, wetting/drying hysteresis,
and independent gravimetric + TDR/FDR ground-truth comparison.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SoilTextureClass(str, Enum):
    """USDA standard soil texture classes."""
    SAND = "SAND"
    LOAMY_SAND = "LOAMY_SAND"
    SANDY_LOAM = "SANDY_LOAM"
    LOAM = "LOAM"
    SILT_LOAM = "SILT_LOAM"
    SANDY_CLAY_LOAM = "SANDY_CLAY_LOAM"
    CLAY_LOAM = "CLAY_LOAM"
    SILTY_CLAY = "SILTY_CLAY"
    CLAY = "CLAY"


class HysteresisBranch(str, Enum):
    """Wetting or drying moisture retention hysteresis curve."""
    MAIN_DRYING = "MAIN_DRYING"          # Drainage / desorption from saturation
    MAIN_WETTING = "MAIN_WETTING"        # Imbibition / sorption from dry state
    SCANNING_DRYING = "SCANNING_DRYING"  # Intermediate drying scanning curve
    SCANNING_WETTING = "SCANNING_WETTING"# Intermediate wetting scanning curve


@dataclass(frozen=True)
class SoilStratumMeasurement:
    """Truth measurement at a specific depth stratum."""

    depth_top_cm: float
    depth_bottom_cm: float
    volumetric_water_content: float
    """m3/m3 (theta in [0.0, 0.6])."""

    bulk_density_g_cm3: float
    electrical_conductivity_ds_m: float
    temperature_c: float
    gravimetric_water_content: Optional[float] = None
    """kg/kg from oven dry reference."""

    sensor_probe_reading: Optional[float] = None
    """In-situ calibrated probe reading."""

    @property
    def gravimetric_probe_error(self) -> Optional[float]:
        """Difference between in-situ probe reading and gravimetric truth."""
        if self.sensor_probe_reading is not None and self.gravimetric_water_content is not None:
            # Volumetric approx = gravimetric * bulk_density
            expected_vwc = self.gravimetric_water_content * self.bulk_density_g_cm3
            return abs(self.sensor_probe_reading - expected_vwc)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "depth_top_cm": self.depth_top_cm,
            "depth_bottom_cm": self.depth_bottom_cm,
            "volumetric_water_content": self.volumetric_water_content,
            "bulk_density_g_cm3": self.bulk_density_g_cm3,
            "electrical_conductivity_ds_m": self.electrical_conductivity_ds_m,
            "temperature_c": self.temperature_c,
            "gravimetric_water_content": self.gravimetric_water_content,
            "sensor_probe_reading": self.sensor_probe_reading,
            "gravimetric_probe_error": self.gravimetric_probe_error,
        }


@dataclass(frozen=True)
class SoilColumnExperimentRecord:
    """Complete observation record of a controlled soil column experiment."""

    column_id: str
    texture_class: SoilTextureClass
    replicate_index: int
    measured_at: datetime

    hysteresis_branch: HysteresisBranch
    hysteresis_cycle_number: int

    strata: List[SoilStratumMeasurement] = field(default_factory=list)
    surface_crust_present: bool = False
    standing_water_depth_mm: float = 0.0

    experiment_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_id": self.column_id,
            "texture_class": self.texture_class.value,
            "replicate_index": self.replicate_index,
            "measured_at": self.measured_at.isoformat(),
            "hysteresis_branch": self.hysteresis_branch.value,
            "hysteresis_cycle_number": self.hysteresis_cycle_number,
            "strata": [s.to_dict() for s in self.strata],
            "surface_crust_present": self.surface_crust_present,
            "standing_water_depth_mm": self.standing_water_depth_mm,
            "experiment_notes": self.experiment_notes,
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
