"""
Layer 0: User Input Schema — Canonical dataclasses for farmer/agronomist-declared data.

All user-provided metadata (plot registration, soil analysis, irrigation events,
management events) is defined here. The UserInputAdapter converts these into
ObservationPackets for pipeline ingestion.

Uncertainty model: All user inputs carry uncertainty, but near ground truth.
  - Soil lab analysis: σ_clay=2%, σ_pH=0.15, σ_OM=0.3%  (high-quality lab)
  - Irrigation amounts: σ = 10% of declared amount (farmer self-report)
  - Plot geometry: treated as ground truth (digitized by user)
  - Crop type/dates: treated as ground truth (farmer declaration)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ============================================================================
# Plot Registration (one-time setup)
# ============================================================================

@dataclass
class PlotRegistration:
    """One-time plot setup by the user."""
    plot_id: str
    polygon_wkt: str                       # WKT geometry of the plot boundary
    area_ha: float                         # Declared area in hectares

    crop_type: str                         # "corn", "wheat", "soybean", etc.
    variety: Optional[str] = None          # Crop variety/cultivar
    planting_date: Optional[str] = None    # YYYY-MM-DD
    expected_harvest_date: Optional[str] = None

    irrigation_type: str = "rainfed"       # "drip", "pivot", "flood", "sprinkler", "rainfed"
    management_goal: str = "yield_max"     # "yield_max", "cost_min", "sustainable"
    constraints: Dict[str, Any] = field(default_factory=dict)
    # e.g. {"water_quota_mm": 500, "organic": True, "budget_limit": 1000}

    # Metadata
    registered_at: Optional[datetime] = None
    registered_by: str = "farmer"          # "farmer", "agronomist", "operator"

    def completeness_score(self) -> float:
        """0-1 score of how complete the registration is."""
        fields = [
            self.polygon_wkt, self.area_ha > 0, self.crop_type,
            self.planting_date, self.irrigation_type != "rainfed",
            self.variety, self.expected_harvest_date,
        ]
        filled = sum(1 for f in fields if f)
        return filled / len(fields)


# ============================================================================
# Soil Analysis (lab results)
# ============================================================================

# Lab measurement uncertainty (σ values for Gaussian noise model)
SOIL_LAB_SIGMA = {
    "clay_pct": 2.0,          # ±2% absolute
    "sand_pct": 2.0,
    "silt_pct": 2.0,
    "organic_matter_pct": 0.3, # ±0.3%
    "ph": 0.15,                # ±0.15 pH units
    "ec_ds_m": 0.05,           # ±0.05 dS/m
    "nitrogen_ppm": 5.0,       # ±5 ppm
    "phosphorus_ppm": 3.0,     # ±3 ppm
    "potassium_ppm": 10.0,     # ±10 ppm
    "cec": 1.0,                # ±1 meq/100g
}


@dataclass
class SoilAnalysis:
    """Lab soil analysis provided by user."""
    plot_id: str
    sample_date: str                       # YYYY-MM-DD
    depth_cm: float = 30.0                 # Sampling depth (0-30 typical)

    # Texture
    clay_pct: Optional[float] = None
    sand_pct: Optional[float] = None
    silt_pct: Optional[float] = None

    # Organic matter
    organic_matter_pct: Optional[float] = None

    # Chemistry
    ph: Optional[float] = None
    ec_ds_m: Optional[float] = None        # Electrical conductivity

    # Nutrients
    nitrogen_ppm: Optional[float] = None
    phosphorus_ppm: Optional[float] = None
    potassium_ppm: Optional[float] = None
    cec: Optional[float] = None            # Cation Exchange Capacity

    # Metadata
    lab_name: Optional[str] = None
    analysis_method: str = "standard"      # "standard", "spectral", "field_kit"

    def texture_class(self) -> str:
        """Derive USDA texture class from particle sizes."""
        if self.clay_pct is None or self.sand_pct is None:
            return ""
        clay, sand = self.clay_pct, self.sand_pct
        if clay >= 40:
            return "clay"
        elif clay >= 27 and sand <= 20:
            return "silty_clay"
        elif clay >= 27:
            return "clay_loam"
        elif sand >= 85:
            return "sand"
        elif sand >= 70:
            return "sandy_loam"
        elif clay <= 12 and sand <= 50:
            return "silt_loam"
        else:
            return "loam"

    def completeness_score(self) -> float:
        """0-1 score of how complete the analysis is."""
        fields = [
            self.clay_pct is not None, self.sand_pct is not None,
            self.organic_matter_pct is not None, self.ph is not None,
            self.ec_ds_m is not None, self.nitrogen_ppm is not None,
            self.phosphorus_ppm is not None, self.potassium_ppm is not None,
        ]
        return sum(fields) / len(fields)

    def get_sigma(self, variable: str) -> float:
        """Get measurement uncertainty for a variable."""
        base = SOIL_LAB_SIGMA.get(variable, 1.0)
        # Field kit has 2x the uncertainty of a standard lab
        if self.analysis_method == "field_kit":
            return base * 2.0
        return base


# ============================================================================
# Irrigation Event
# ============================================================================

# Irrigation self-report uncertainty: 10% of declared amount
IRRIGATION_SIGMA_FRACTION = 0.10


@dataclass
class IrrigationEvent:
    """User-declared irrigation application."""
    plot_id: str
    timestamp: datetime
    amount_mm: float                       # Declared amount
    method: str = "drip"                   # "drip", "flood", "sprinkler", "pivot"
    duration_hours: Optional[float] = None
    zone_id: Optional[str] = None          # Optional: specific zone irrigated
    source: str = "user_declared"

    @property
    def sigma_mm(self) -> float:
        """Uncertainty in declared amount (10% of amount, min 1mm)."""
        return max(1.0, self.amount_mm * IRRIGATION_SIGMA_FRACTION)


# ============================================================================
# Management Event
# ============================================================================

VALID_EVENT_TYPES = (
    "sowing", "emergence", "fertilizer", "pesticide", "herbicide",
    "harvest", "tillage", "pruning", "thinning", "cover_crop",
    "mowing", "field_observation",
)


@dataclass
class ManagementEvent:
    """Any user-declared management event."""
    plot_id: str
    timestamp: datetime
    event_type: str                        # One of VALID_EVENT_TYPES
    details: Dict[str, Any] = field(default_factory=dict)
    # Type-specific data, e.g.:
    #   sowing:     {"seed_rate_kg_ha": 80, "seed_depth_cm": 5}
    #   fertilizer: {"product": "urea", "rate_kg_ha": 150, "method": "broadcast"}
    #   pesticide:  {"product": "lambda-cyhalothrin", "rate_l_ha": 0.5}
    #   harvest:    {"yield_t_ha": 8.5, "moisture_pct": 14}
    #   tillage:    {"depth_cm": 25, "type": "chisel"}

    notes: str = ""
    source: str = "user_declared"

    def validate(self) -> List[str]:
        """Return list of validation warnings."""
        warnings = []
        if self.event_type not in VALID_EVENT_TYPES:
            warnings.append(f"Unknown event type: {self.event_type}")
        if self.event_type == "fertilizer" and "rate_kg_ha" not in self.details:
            warnings.append("Fertilizer event missing rate_kg_ha")
        if self.event_type == "sowing" and "seed_rate_kg_ha" not in self.details:
            warnings.append("Sowing event missing seed_rate_kg_ha")
        return warnings


# ============================================================================
# User Input Package (complete bundle)
# ============================================================================

@dataclass
class UserInputPackage:
    """Complete user input bundle for a plot.

    This is the canonical container that the UserInputAdapter consumes
    to produce ObservationPackets for the Layer 0 pipeline.
    """
    plot_registration: PlotRegistration
    soil_analyses: List[SoilAnalysis] = field(default_factory=list)
    irrigation_events: List[IrrigationEvent] = field(default_factory=list)
    management_events: List[ManagementEvent] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        """Summary statistics for diagnostics."""
        return {
            "plot_id": self.plot_registration.plot_id,
            "crop": self.plot_registration.crop_type,
            "irrigation": self.plot_registration.irrigation_type,
            "registration_completeness": round(self.plot_registration.completeness_score(), 2),
            "soil_analyses_count": len(self.soil_analyses),
            "irrigation_events_count": len(self.irrigation_events),
            "management_events_count": len(self.management_events),
            "total_irrigation_mm": round(sum(e.amount_mm for e in self.irrigation_events), 1),
        }
