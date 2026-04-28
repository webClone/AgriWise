"""
SoilGrids V1 Schemas.

11 core properties × 6 depths, with uncertainty quantiles.
All values are soil_prior, NEVER soil_measurement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


# Canonical property IDs — matches SoilGrids layer naming
SOILGRIDS_CORE_PROPERTIES = [
    "bdod", "clay", "silt", "sand", "cfvo",
    "phh2o", "soc", "cec", "nitrogen",
    "wv003", "wv1500",
]

SOILGRIDS_OPTIONAL_PROPERTIES = ["wv0010", "ocd", "ocs"]

SOILGRIDS_DEPTH_LABELS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]

# Layer thickness in mm for AWC calculations
SOILGRIDS_DEPTH_THICKNESS_MM = {
    "0-5cm": 50,
    "5-15cm": 100,
    "15-30cm": 150,
    "30-60cm": 300,
    "60-100cm": 400,
    "100-200cm": 1000,
}

# Unit conversion factors: raw_value / factor = output_value
SOILGRIDS_UNIT_CONVERSIONS = {
    "bdod": {"factor": 100, "raw_unit": "cg/cm³", "output_unit": "kg/dm³"},
    "clay": {"factor": 10, "raw_unit": "g/kg", "output_unit": "%"},
    "silt": {"factor": 10, "raw_unit": "g/kg", "output_unit": "%"},
    "sand": {"factor": 10, "raw_unit": "g/kg", "output_unit": "%"},
    "cfvo": {"factor": 10, "raw_unit": "cm³/100cm³", "output_unit": "vol%"},
    "phh2o": {"factor": 10, "raw_unit": "pH×10", "output_unit": "pH"},
    "soc": {"factor": 10, "raw_unit": "dg/kg", "output_unit": "g/kg"},
    "cec": {"factor": 10, "raw_unit": "mmol(c)/kg", "output_unit": "cmol(c)/kg"},
    "nitrogen": {"factor": 100, "raw_unit": "cg/kg", "output_unit": "g/kg"},
    "wv003": {"factor": 10, "raw_unit": "0.1 vol%", "output_unit": "vol%"},
    "wv1500": {"factor": 10, "raw_unit": "0.1 vol%", "output_unit": "vol%"},
}

# Alias mapping for external data that uses non-canonical names
SOILGRIDS_PROPERTY_ALIASES = {
    "wv0033": "wv003",
    "bulk_density": "bdod",
    "ph_h2o": "phh2o",
    "organic_carbon": "soc",
}


class SoilGridsQualityClass(Enum):
    """SoilGrids profile quality."""
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


@dataclass
class SoilGridsPropertyValue:
    """A single property value at a single depth with uncertainty."""
    property_id: str = ""
    depth_label: str = ""

    mean: Optional[float] = None
    q005: Optional[float] = None  # 5th percentile
    q050: Optional[float] = None  # median
    q095: Optional[float] = None  # 95th percentile

    unit: str = ""
    raw_value: Optional[float] = None
    conversion_factor: float = 1.0

    label: Literal["soil_prior"] = "soil_prior"


@dataclass
class SoilGridsDepthLayer:
    """All properties at one depth interval."""
    depth_label: str = ""
    thickness_mm: int = 0
    properties: Dict[str, SoilGridsPropertyValue] = field(default_factory=dict)

    def get(self, prop_id: str) -> Optional[float]:
        """Get mean value for a property."""
        pv = self.properties.get(prop_id)
        return pv.mean if pv else None


@dataclass
class SoilGridsProfile:
    """Full 6-depth SoilGrids profile."""
    latitude: float = 0.0
    longitude: float = 0.0
    coordinate_crs: str = "EPSG:4326"

    depth_layers: Dict[str, SoilGridsDepthLayer] = field(default_factory=dict)

    source_resolution_m: float = 250.0
    provider: str = "ISRIC SoilGrids"
    license: str = "CC-BY 4.0"
    label: Literal["soil_prior"] = "soil_prior"

    soilgrids_version: str = ""
    access_method: Literal[
        "mocked_fixture", "wcs_tile", "rest_api", "webdav"
    ] = "mocked_fixture"


@dataclass
class SoilGridsDerivedHydraulics:
    """Derived hydraulic properties from SoilGrids profile."""
    # AWC proxy (volumetric)
    awc_volumetric_proxy_by_depth: Dict[str, float] = field(default_factory=dict)

    # AWC in mm per layer (with coarse-fragment correction)
    awc_mm_by_layer: Dict[str, float] = field(default_factory=dict)
    coarse_fragment_correction_applied: bool = False

    # Root-zone aggregated AWC (mm)
    root_zone_awc_mm_0_30: Optional[float] = None
    root_zone_awc_mm_0_60: Optional[float] = None
    root_zone_awc_mm_0_100: Optional[float] = None

    # Texture classification
    texture_class: str = ""  # USDA triangle

    # Risk/capacity indicators
    drainage_risk: str = ""       # low / medium / high
    water_holding_capacity_class: str = ""  # low / medium / high
    infiltration_risk_class: str = ""       # low / medium / high
    compaction_risk_proxy: str = ""         # low / medium / high
    nutrient_buffering_proxy: str = ""      # low / medium / high
    lime_ph_risk_proxy: str = ""            # acidic / neutral / alkaline

    # Labels
    label: Literal["derived_proxy"] = "derived_proxy"


@dataclass
class SoilGridsQAResult:
    """SoilGrids quality assessment."""
    quality_class: SoilGridsQualityClass = SoilGridsQualityClass.GOOD

    has_all_required_properties: bool = False
    depth_completeness: float = 0.0  # fraction of 6 depths present
    property_completeness: float = 0.0  # fraction of 11 properties present (avg across depths)
    texture_sum_consistent: bool = False
    uncertainty_ratio_ok: bool = True  # (Q95-Q05)/mean < 0.5
    water_property_available: bool = False  # wv003 + wv1500 both present
    provider_status: str = ""  # "available" / "unavailable" / "mocked"
    resolution_m: float = 250.0

    flags: List[str] = field(default_factory=list)
    reason: str = ""
