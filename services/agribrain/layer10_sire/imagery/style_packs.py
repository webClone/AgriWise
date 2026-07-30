"""
Imagery Style Packs — Agronomic visualization templates
========================================================

6 built-in style packs for map-native rendering:
  1. TRUE_COLOR_REALITY — natural look
  2. AGRO_POP — vibrant vegetation emphasis
  3. CANOPY_INSPECTION — structural detail
  4. WATER_STRESS_CONTRAST — drought-focused
  5. ORCHARD_OBJECTS — individual tree rendering
  6. UNCERTAINTY_DEBUG — trust visualization
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class StylePackId(str, Enum):
    TRUE_COLOR_REALITY = "TRUE_COLOR_REALITY"
    AGRO_POP = "AGRO_POP"
    CANOPY_INSPECTION = "CANOPY_INSPECTION"
    WATER_STRESS_CONTRAST = "WATER_STRESS_CONTRAST"
    ORCHARD_OBJECTS = "ORCHARD_OBJECTS"
    UNCERTAINTY_DEBUG = "UNCERTAINTY_DEBUG"


@dataclass
class ColorRamp:
    """Color ramp for surface rendering."""
    name: str
    stops: List[Dict[str, Any]]  # [{value, color}, ...]

    def interpolate(self, value: float) -> str:
        """Get hex color for a value by linear interpolation."""
        if not self.stops:
            return "#808080"
        if value <= self.stops[0]["value"]:
            return self.stops[0]["color"]
        if value >= self.stops[-1]["value"]:
            return self.stops[-1]["color"]

        for i in range(len(self.stops) - 1):
            s0, s1 = self.stops[i], self.stops[i + 1]
            if s0["value"] <= value <= s1["value"]:
                t = (value - s0["value"]) / (s1["value"] - s0["value"])
                return _lerp_hex(s0["color"], s1["color"], t)

        return self.stops[-1]["color"]


@dataclass
class StylePack:
    """Complete rendering style pack."""
    pack_id: StylePackId
    name: str
    description: str

    # Surface-specific color ramps
    color_ramps: Dict[str, ColorRamp] = field(default_factory=dict)

    # Enhancement parameters
    contrast: float = 1.0       # 0.5–2.0
    saturation: float = 1.0     # 0.5–2.0
    brightness: float = 1.0     # 0.5–2.0
    gamma: float = 1.0          # 0.5–2.0
    clahe_clip: float = 0.0     # 0 = off, 1–4 = typical CLAHE values
    haze_removal: float = 0.0   # 0–1

    # Overlay settings
    show_grid_lines: bool = False
    show_zone_boundaries: bool = True
    zone_border_opacity: float = 0.6
    object_markers: bool = False
    object_marker_style: str = "circle"  # circle, cross, dot

    # Resolution-dependent rendering
    min_resolution_m: float = 0.0
    label_zones: bool = True


# === Pre-built style packs ===

STYLE_PACKS = {
    StylePackId.TRUE_COLOR_REALITY: StylePack(
        pack_id=StylePackId.TRUE_COLOR_REALITY,
        name="True Color Reality",
        description="Natural-looking field view with minimal enhancement",
        color_ramps={
            "NDVI_CLEAN": ColorRamp("natural_green", [
                {"value": 0.0, "color": "#8B7355"},
                {"value": 0.3, "color": "#C4A77D"},
                {"value": 0.5, "color": "#90B560"},
                {"value": 0.7, "color": "#4D8C2A"},
                {"value": 0.9, "color": "#1B5E20"},
            ]),
        },
        contrast=1.05,
        saturation=0.95,
        brightness=1.0,
        show_zone_boundaries=False,
    ),
    StylePackId.AGRO_POP: StylePack(
        pack_id=StylePackId.AGRO_POP,
        name="Agro Pop",
        description="Vibrant vegetation emphasis for presentations and quick assessment",
        color_ramps={
            "NDVI_CLEAN": ColorRamp("vivid_green", [
                {"value": 0.0, "color": "#D32F2F"},
                {"value": 0.3, "color": "#FF9800"},
                {"value": 0.5, "color": "#FFEB3B"},
                {"value": 0.7, "color": "#66BB6A"},
                {"value": 0.9, "color": "#1B5E20"},
            ]),
            "WATER_STRESS_PROB": ColorRamp("stress_fire", [
                {"value": 0.0, "color": "#E8F5E9"},
                {"value": 0.3, "color": "#FFF9C4"},
                {"value": 0.6, "color": "#FF8F00"},
                {"value": 0.9, "color": "#B71C1C"},
            ]),
        },
        contrast=1.3,
        saturation=1.5,
        brightness=1.05,
        clahe_clip=2.0,
    ),
    StylePackId.CANOPY_INSPECTION: StylePack(
        pack_id=StylePackId.CANOPY_INSPECTION,
        name="Canopy Inspection",
        description="High-contrast structural view for canopy assessment",
        color_ramps={
            "NDVI_CLEAN": ColorRamp("binary_canopy", [
                {"value": 0.0, "color": "#37474F"},
                {"value": 0.3, "color": "#78909C"},
                {"value": 0.5, "color": "#A5D6A7"},
                {"value": 0.7, "color": "#2E7D32"},
                {"value": 0.9, "color": "#004D25"},
            ]),
        },
        contrast=1.8,
        saturation=0.6,
        clahe_clip=3.0,
        object_markers=True,
        object_marker_style="cross",
        min_resolution_m=5.0,
    ),
    StylePackId.WATER_STRESS_CONTRAST: StylePack(
        pack_id=StylePackId.WATER_STRESS_CONTRAST,
        name="Water Stress Contrast",
        description="Drought-focused view emphasizing moisture patterns",
        color_ramps={
            "WATER_STRESS_PROB": ColorRamp("drought_heat", [
                {"value": 0.0, "color": "#1565C0"},
                {"value": 0.25, "color": "#4FC3F7"},
                {"value": 0.5, "color": "#FFEB3B"},
                {"value": 0.75, "color": "#EF6C00"},
                {"value": 1.0, "color": "#B71C1C"},
            ]),
            "DROUGHT_ACCUMULATION": ColorRamp("dry_days", [
                {"value": 0, "color": "#1565C0"},
                {"value": 7, "color": "#66BB6A"},
                {"value": 14, "color": "#FFEB3B"},
                {"value": 21, "color": "#EF6C00"},
                {"value": 30, "color": "#B71C1C"},
            ]),
        },
        contrast=1.4,
        saturation=1.3,
        show_zone_boundaries=True,
        zone_border_opacity=0.8,
    ),
    StylePackId.ORCHARD_OBJECTS: StylePack(
        pack_id=StylePackId.ORCHARD_OBJECTS,
        name="Orchard Objects",
        description="Individual tree and gap visualization for orchard management",
        color_ramps={
            "NDVI_CLEAN": ColorRamp("orchard_detail", [
                {"value": 0.0, "color": "#3E2723"},
                {"value": 0.35, "color": "#795548"},
                {"value": 0.5, "color": "#8BC34A"},
                {"value": 0.7, "color": "#33691E"},
                {"value": 0.9, "color": "#1B5E20"},
            ]),
        },
        contrast=2.0,
        saturation=0.7,
        clahe_clip=4.0,
        object_markers=True,
        object_marker_style="circle",
        min_resolution_m=3.0,
        show_grid_lines=True,
    ),
    StylePackId.UNCERTAINTY_DEBUG: StylePack(
        pack_id=StylePackId.UNCERTAINTY_DEBUG,
        name="Uncertainty Debug",
        description="Trust visualization for diagnostic review",
        color_ramps={
            "UNCERTAINTY_SIGMA": ColorRamp("sigma_heat", [
                {"value": 0.0, "color": "#1565C0"},
                {"value": 0.1, "color": "#66BB6A"},
                {"value": 0.2, "color": "#FFEB3B"},
                {"value": 0.3, "color": "#EF6C00"},
                {"value": 0.5, "color": "#B71C1C"},
            ]),
            "DATA_RELIABILITY": ColorRamp("trust_cold", [
                {"value": 0.0, "color": "#B71C1C"},
                {"value": 0.3, "color": "#EF6C00"},
                {"value": 0.6, "color": "#FFEB3B"},
                {"value": 0.8, "color": "#66BB6A"},
                {"value": 1.0, "color": "#1565C0"},
            ]),
            "SOURCE_DOMINANCE": ColorRamp("source_spectral", [
                {"value": 0.0, "color": "#9E9E9E"},
                {"value": 0.3, "color": "#7B1FA2"},
                {"value": 0.5, "color": "#1976D2"},
                {"value": 0.7, "color": "#00BCD4"},
                {"value": 1.0, "color": "#4CAF50"},
            ]),
        },
        contrast=1.0,
        saturation=0.5,
        show_zone_boundaries=True,
        zone_border_opacity=0.4,
        label_zones=True,
    ),
}


def get_style_pack(pack_id: StylePackId) -> Optional[StylePack]:
    """Retrieve a style pack by ID."""
    return STYLE_PACKS.get(pack_id)


def list_style_packs() -> List[Dict[str, str]]:
    """List available style packs."""
    return [
        {"id": sp.pack_id.value, "name": sp.name, "description": sp.description}
        for sp in STYLE_PACKS.values()
    ]


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    """Linear interpolation between two hex colors."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02X}{g:02X}{b:02X}"
