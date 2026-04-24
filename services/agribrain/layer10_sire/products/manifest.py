"""
Render Manifest Builder — Generate frontend-consumable map mode definitions
"""
from typing import List
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, RenderManifest,
    MapModeDef, RenderMode, PaletteId, LegendEntry,
)

# Surface → Mode mapping
SURFACE_TO_MODE = {
    SurfaceType.NDVI_CLEAN: RenderMode.VIGOR,
    SurfaceType.NDVI_DEVIATION: RenderMode.VIGOR,
    SurfaceType.WATER_STRESS_PROB: RenderMode.WATER_STRESS,
    SurfaceType.NUTRIENT_STRESS_PROB: RenderMode.NUTRIENT,
    SurfaceType.BIOTIC_PRESSURE: RenderMode.DISEASE,
    SurfaceType.YIELD_P50: RenderMode.YIELD,
    SurfaceType.CROP_SUITABILITY: RenderMode.SUITABILITY,
    SurfaceType.COMPOSITE_RISK: RenderMode.RISK,
    SurfaceType.UNCERTAINTY_SIGMA: RenderMode.UNCERTAINTY,
    SurfaceType.SOURCE_DOMINANCE: RenderMode.SOURCE_DOMINANCE,
}

# Default legends
DEFAULT_LEGENDS = {
    RenderMode.VIGOR: [
        LegendEntry("Low Vigor", "#D32F2F", (0.0, 0.3)),
        LegendEntry("Moderate", "#FFC107", (0.3, 0.6)),
        LegendEntry("Healthy", "#4CAF50", (0.6, 0.8)),
        LegendEntry("Very Healthy", "#1B5E20", (0.8, 1.0)),
    ],
    RenderMode.WATER_STRESS: [
        LegendEntry("No Stress", "#2196F3", (0.0, 0.3)),
        LegendEntry("Moderate", "#FF9800", (0.3, 0.6)),
        LegendEntry("Severe", "#D32F2F", (0.6, 1.0)),
    ],
    RenderMode.RISK: [
        LegendEntry("Low Risk", "#4CAF50", (0.0, 0.3)),
        LegendEntry("Moderate", "#FF9800", (0.3, 0.6)),
        LegendEntry("High Risk", "#D32F2F", (0.6, 1.0)),
    ],
    RenderMode.UNCERTAINTY: [
        LegendEntry("High Confidence", "#1565C0", (0.0, 0.1)),
        LegendEntry("Moderate", "#90A4AE", (0.1, 0.3)),
        LegendEntry("Low Confidence", "#E0E0E0", (0.3, 1.0)),
    ],
}

# Palette mapping
MODE_PALETTE = {
    RenderMode.VIGOR: PaletteId.VIGOR_GREEN,
    RenderMode.WATER_STRESS: PaletteId.STRESS_RED,
    RenderMode.NUTRIENT: PaletteId.NUTRIENT_YELLOW,
    RenderMode.DISEASE: PaletteId.DISEASE_ORANGE,
    RenderMode.YIELD: PaletteId.YIELD_BLUE,
    RenderMode.SUITABILITY: PaletteId.VIGOR_GREEN,
    RenderMode.RISK: PaletteId.RISK_HEAT,
    RenderMode.UNCERTAINTY: PaletteId.UNCERTAINTY_GRAY,
    RenderMode.SOURCE_DOMINANCE: PaletteId.SOURCE_SPECTRAL,
    RenderMode.DECISION_HALO: PaletteId.DECISION_CATEGORICAL,
}


def build_render_manifest(
    surfaces: List[SurfaceArtifact], inp: Layer10Input
) -> RenderManifest:
    """Build the frontend render manifest from available surfaces."""
    # Determine which modes are available
    available_modes_set = set()
    surface_ids_by_mode = {}

    for s in surfaces:
        mode = SURFACE_TO_MODE.get(s.semantic_type)
        if mode is not None:
            available_modes_set.add(mode)
            if mode not in surface_ids_by_mode:
                surface_ids_by_mode[mode] = []
            surface_ids_by_mode[mode].append(s.surface_id)

    # Build mode definitions
    mode_defs = []
    for mode in RenderMode:
        if mode not in available_modes_set:
            # Still define it, but disabled
            mode_defs.append(MapModeDef(
                mode=mode,
                display_name=mode.value.replace("_", " ").title(),
                surface_ids=[],
                palette_id=MODE_PALETTE.get(mode, PaletteId.RAW_GRAYSCALE),
                legend=DEFAULT_LEGENDS.get(mode, []),
                enabled=False,
                description=f"{mode.value} mode (no data available)",
            ))
        else:
            mode_defs.append(MapModeDef(
                mode=mode,
                display_name=mode.value.replace("_", " ").title(),
                surface_ids=surface_ids_by_mode.get(mode, []),
                palette_id=MODE_PALETTE.get(mode, PaletteId.RAW_GRAYSCALE),
                legend=DEFAULT_LEGENDS.get(mode, []),
                enabled=True,
                description=f"{mode.value} map mode",
                requires_resolution_m=5.0 if mode == RenderMode.PLANT_NEAR else None,
            ))

    # Determine default active mode
    active = RenderMode.VIGOR if RenderMode.VIGOR in available_modes_set else (
        list(available_modes_set)[0] if available_modes_set else RenderMode.VIGOR
    )

    return RenderManifest(
        available_modes=mode_defs,
        active_mode=active,
        style_pack=inp.render_profile,
        show_confidence_fog=RenderMode.UNCERTAINTY in available_modes_set,
        show_zone_boundaries=True,
    )
