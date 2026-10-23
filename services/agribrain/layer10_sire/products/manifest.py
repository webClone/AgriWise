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
    SurfaceType.WATER_FEASIBILITY: RenderMode.SUITABILITY,
    SurfaceType.BIOTIC_FEASIBILITY: RenderMode.SUITABILITY,
    SurfaceType.ECONOMIC_SUITABILITY: RenderMode.SUITABILITY,
    SurfaceType.SUITABILITY_WINDOW: RenderMode.SUITABILITY,
    SurfaceType.SEASON_PROGRESS: RenderMode.SUITABILITY,
    SurfaceType.COMPOSITE_RISK: RenderMode.RISK,
    SurfaceType.UNCERTAINTY_SIGMA: RenderMode.UNCERTAINTY,
    SurfaceType.SOURCE_DOMINANCE: RenderMode.SOURCE_DOMINANCE,
    SurfaceType.SOIL_CARBON: RenderMode.SOIL_CARBON,
    SurfaceType.SOIL_COMPACTION: RenderMode.SOIL_COMPACTION,
    SurfaceType.THERMAL_STRESS: RenderMode.THERMAL_STRESS,
    SurfaceType.N_LEACHING_RISK: RenderMode.N_LOSS,
    SurfaceType.N_VOLATILIZATION_RISK: RenderMode.N_LOSS,

    # ASMAE surfaces (V82)
    SurfaceType.ASMAE_VIGOR: RenderMode.ASMAE_VIGOR,
    SurfaceType.ASMAE_LAI: RenderMode.ASMAE_LAI,
    SurfaceType.ASMAE_CHLOROPHYLL: RenderMode.ASMAE_CHLOROPHYLL,
    SurfaceType.ASMAE_CANOPY_WATER: RenderMode.ASMAE_CANOPY_WATER,
    SurfaceType.ASMAE_ROOT_ZONE_WATER: RenderMode.ASMAE_ROOT_ZONE_WATER,
    SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: RenderMode.ASMAE_SURFACE_WETNESS_EVENT,
    SurfaceType.ASMAE_STRUCTURE: RenderMode.ASMAE_STRUCTURE,
    SurfaceType.ASMAE_BARE_SOIL: RenderMode.ASMAE_BARE_SOIL,
    SurfaceType.ASMAE_SALINITY_STRESS: RenderMode.ASMAE_SALINITY_STRESS,
    SurfaceType.ASMAE_THERMAL_STRESS: RenderMode.ASMAE_THERMAL_STRESS,
    SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: RenderMode.ASMAE_BIOTIC_CONFOUNDER_RISK,
    SurfaceType.ASMAE_PHENOLOGY_PROGRESS: RenderMode.ASMAE_PHENOLOGY_PROGRESS,
    SurfaceType.ASMAE_STRESS_MEMORY: RenderMode.ASMAE_STRESS_MEMORY,
    SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: RenderMode.ASMAE_EFFECTIVE_RESOLUTION,
    SurfaceType.ASMAE_POSTERIOR_CONCENTRATION: RenderMode.ASMAE_POSTERIOR_CONCENTRATION,
    SurfaceType.ASMAE_CONFIDENCE: RenderMode.ASMAE_POSTERIOR_CONCENTRATION,
    SurfaceType.ASMAE_UNCERTAINTY: RenderMode.ASMAE_UNCERTAINTY,
    SurfaceType.ASMAE_RETROVALIDATION_SCORE: RenderMode.ASMAE_RETROVALIDATION_SCORE,
    SurfaceType.ASMAE_BMA_DISAGREEMENT: RenderMode.ASMAE_BMA_DISAGREEMENT,
    SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: RenderMode.ASMAE_CROSS_LAYER_CONFLICT,
    SurfaceType.ASMAE_EXPORT_ELIGIBILITY: RenderMode.ASMAE_EXPORT_ELIGIBILITY,
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
        LegendEntry("Low Stress", "#4CAF50", (0.0, 0.2)),
        LegendEntry("Moderate", "#FFC107", (0.2, 0.5)),
        LegendEntry("High Stress", "#D32F2F", (0.5, 1.0)),
    ],
    RenderMode.NUTRIENT: [
        LegendEntry("Deficient", "#D32F2F", (0.0, 0.4)),
        LegendEntry("Adequate", "#4CAF50", (0.4, 0.8)),
        LegendEntry("High", "#1B5E20", (0.8, 1.0)),
    ],
    RenderMode.DISEASE: [
        LegendEntry("Low Risk", "#4CAF50", (0.0, 0.3)),
        LegendEntry("Moderate", "#FFC107", (0.3, 0.7)),
        LegendEntry("High Risk", "#D32F2F", (0.7, 1.0)),
    ],
    RenderMode.YIELD: [
        LegendEntry("Below Target", "#D32F2F", (0.0, 0.7)),
        LegendEntry("On Target", "#4CAF50", (0.7, 1.0)),
        LegendEntry("Above Target", "#1B5E20", (1.0, 1.5)),
    ],
    RenderMode.SUITABILITY: [
        LegendEntry("Unsuitable", "#D32F2F", (0.0, 0.4)),
        LegendEntry("Marginal", "#FFC107", (0.4, 0.7)),
        LegendEntry("Optimal", "#4CAF50", (0.7, 1.0)),
    ],
    RenderMode.RISK: [
        LegendEntry("Low Risk", "#4CAF50", (0.0, 0.3)),
        LegendEntry("Moderate", "#FFC107", (0.3, 0.6)),
        LegendEntry("High Risk", "#D32F2F", (0.6, 1.0)),
    ],
    RenderMode.UNCERTAINTY: [
        LegendEntry("Low Uncertainty", "#4CAF50", (0.0, 0.25)),
        LegendEntry("Moderate", "#FFC107", (0.25, 0.5)),
        LegendEntry("High Uncertainty", "#D32F2F", (0.5, 1.0)),
    ],
    RenderMode.SOIL_CARBON: [
        LegendEntry("Low Carbon", "#8D6E63", (10.0, 30.0)),
        LegendEntry("Moderate", "#5D4037", (30.0, 60.0)),
        LegendEntry("High Carbon", "#3E2723", (60.0, 150.0)),
    ],
    RenderMode.SOIL_COMPACTION: [
        LegendEntry("Low Compaction", "#E8EAF6", (0.0, 0.3)),
        LegendEntry("Moderate", "#7986CB", (0.3, 0.7)),
        LegendEntry("Severe", "#283593", (0.7, 1.0)),
    ],
    RenderMode.THERMAL_STRESS: [
        LegendEntry("No Stress", "#FFF9C4", (0.0, 0.2)),
        LegendEntry("Moderate", "#FFB74D", (0.2, 0.6)),
        LegendEntry("Severe Stress", "#E65100", (0.6, 1.0)),
    ],
    RenderMode.N_LOSS: [
        LegendEntry("Low Risk", "#E8F5E9", (0.0, 0.3)),
        LegendEntry("Moderate", "#FFB74D", (0.3, 0.7)),
        LegendEntry("High Risk", "#C62828", (0.7, 1.0)),
    ],
    RenderMode.ASMAE_VIGOR: [
        LegendEntry("Low Vigor", "#D32F2F", (0.0, 0.3)),
        LegendEntry("Moderate", "#FFC107", (0.3, 0.6)),
        LegendEntry("Healthy", "#4CAF50", (0.6, 0.8)),
        LegendEntry("Very Healthy", "#1B5E20", (0.8, 1.0)),
    ],
    RenderMode.ASMAE_LAI: [
        LegendEntry("Sparse Canopy (<1.5)", "#E8F5E9", (0.0, 1.5)),
        LegendEntry("Moderate (1.5-3.5)", "#81C784", (1.5, 3.5)),
        LegendEntry("Dense Canopy (>3.5)", "#1B5E20", (3.5, 6.0)),
    ],
    RenderMode.ASMAE_CHLOROPHYLL: [
        LegendEntry("Low Chlorophyll", "#FFEBEE", (0.0, 30.0)),
        LegendEntry("Moderate", "#FFF9C4", (30.0, 50.0)),
        LegendEntry("High Chlorophyll", "#E8F5E9", (50.0, 80.0)),
    ],
    RenderMode.ASMAE_CANOPY_WATER: [
        LegendEntry("Dry Canopy", "#FFF3E0", (0.0, 0.3)),
        LegendEntry("Adequate", "#E1F5FE", (0.3, 0.7)),
        LegendEntry("Saturated", "#01579B", (0.7, 1.0)),
    ],
    RenderMode.ASMAE_ROOT_ZONE_WATER: [
        LegendEntry("Depleted Root Zone", "#FFF3E0", (0.0, 0.2)),
        LegendEntry("Adequate Moisture", "#E1F5FE", (0.2, 0.6)),
        LegendEntry("Field Capacity", "#01579B", (0.6, 1.0)),
    ],
    RenderMode.ASMAE_SURFACE_WETNESS_EVENT: [
        LegendEntry("Dry Surface", "#FAFAFA", (0.0, 0.1)),
        LegendEntry("Wetness Event", "#0288D1", (0.1, 1.0)),
    ],
    RenderMode.ASMAE_STRUCTURE: [
        LegendEntry("Uniform Structure", "#F5F5F5", (0.0, 0.4)),
        LegendEntry("Heterogeneous", "#616161", (0.4, 1.0)),
    ],
    RenderMode.ASMAE_BARE_SOIL: [
        LegendEntry("Full Canopy", "#E8F5E9", (0.0, 0.2)),
        LegendEntry("Partial Soil", "#D7CCC8", (0.2, 0.6)),
        LegendEntry("Bare Soil Exposed", "#4E342E", (0.6, 1.0)),
    ],
    RenderMode.ASMAE_SALINITY_STRESS: [
        LegendEntry("Low Salinity", "#E0F2F1", (0.0, 0.2)),
        LegendEntry("Moderate Salinity", "#4DB6AC", (0.2, 0.5)),
        LegendEntry("High Salinity Stress", "#004D40", (0.5, 1.0)),
    ],
    RenderMode.ASMAE_THERMAL_STRESS: [
        LegendEntry("Normal Temp", "#FFF3E0", (0.0, 0.3)),
        LegendEntry("Elevated Temp", "#FF8F00", (0.3, 0.7)),
        LegendEntry("Severe Heat Stress", "#BF360C", (0.7, 1.0)),
    ],
    RenderMode.ASMAE_BIOTIC_CONFOUNDER_RISK: [
        LegendEntry("Low Confounder Risk", "#FFF3E0", (0.0, 0.3)),
        LegendEntry("Moderate Risk", "#FF8F00", (0.3, 0.7)),
        LegendEntry("High Biotic Risk", "#E65100", (0.7, 1.0)),
    ],
    RenderMode.ASMAE_PHENOLOGY_PROGRESS: [
        LegendEntry("Early Vegetative", "#C8E6C9", (0.0, 0.3)),
        LegendEntry("Mid-Season", "#4CAF50", (0.3, 0.7)),
        LegendEntry("Late / Maturing", "#1B5E20", (0.7, 1.0)),
    ],
    RenderMode.ASMAE_STRESS_MEMORY: [
        LegendEntry("Low Stress Memory", "#E8F5E9", (0.0, 0.3)),
        LegendEntry("Moderate Memory", "#FFB74D", (0.3, 0.7)),
        LegendEntry("Severe Memory", "#D32F2F", (0.7, 1.0)),
    ],
    RenderMode.ASMAE_EFFECTIVE_RESOLUTION: [
        LegendEntry("Fine Resolution (0.03m)", "#E8F5E9", (0.03, 0.5)),
        LegendEntry("Mid-Res (1-3m)", "#FFF3E0", (0.5, 3.0)),
        LegendEntry("Coarse-Res (5-10m)", "#FFEBEE", (3.0, 10.0)),
    ],
    RenderMode.ASMAE_POSTERIOR_CONCENTRATION: [
        LegendEntry("Diffuse posterior", "#FFEBEE", (0.0, 0.6)),
        LegendEntry("Moderate concentration", "#FFF9C4", (0.6, 0.8)),
        LegendEntry("Concentrated posterior", "#E8F5E9", (0.8, 1.0)),
    ],
    RenderMode.ASMAE_UNCERTAINTY: [
        LegendEntry("Low Uncertainty", "#E8F5E9", (0.0, 0.2)),
        LegendEntry("Moderate", "#FFF9C4", (0.2, 0.4)),
        LegendEntry("High Uncertainty", "#FFEBEE", (0.4, 1.0)),
    ],
    RenderMode.ASMAE_RETROVALIDATION_SCORE: [
        LegendEntry("Low Score", "#FFEBEE", (0.0, 0.5)),
        LegendEntry("Moderate", "#FFF9C4", (0.5, 0.8)),
        LegendEntry("High Score", "#E8F5E9", (0.8, 1.0)),
    ],
    RenderMode.ASMAE_BMA_DISAGREEMENT: [
        LegendEntry("Low Disagreement", "#E8F5E9", (0.0, 0.2)),
        LegendEntry("Moderate", "#FFF9C4", (0.2, 0.4)),
        LegendEntry("High Disagreement", "#FFEBEE", (0.4, 1.0)),
    ],
    RenderMode.ASMAE_CROSS_LAYER_CONFLICT: [
        LegendEntry("Low Conflict", "#E8F5E9", (0.0, 0.25)),
        LegendEntry("Moderate", "#FFF9C4", (0.25, 0.45)),
        LegendEntry("High Conflict", "#FFEBEE", (0.45, 1.0)),
    ],
    RenderMode.ASMAE_EXPORT_ELIGIBILITY: [
        LegendEntry("Blocked", "#FFEBEE", (0.0, 0.5)),
        LegendEntry("Eligible", "#E8F5E9", (0.5, 1.0)),
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
    RenderMode.SOIL_CARBON: PaletteId.CARBON_BROWN,
    RenderMode.SOIL_COMPACTION: PaletteId.COMPACTION_PURPLE,
    RenderMode.THERMAL_STRESS: PaletteId.THERMAL_ORANGE,
    RenderMode.N_LOSS: PaletteId.STRESS_RED,

    # ASMAE Palettes (V82)
    RenderMode.ASMAE_VIGOR: PaletteId.VIGOR_GREEN,
    RenderMode.ASMAE_LAI: PaletteId.VIGOR_GREEN,
    RenderMode.ASMAE_CHLOROPHYLL: PaletteId.VIGOR_GREEN,
    RenderMode.ASMAE_CANOPY_WATER: PaletteId.YIELD_BLUE,
    RenderMode.ASMAE_ROOT_ZONE_WATER: PaletteId.YIELD_BLUE,
    RenderMode.ASMAE_SURFACE_WETNESS_EVENT: PaletteId.YIELD_BLUE,
    RenderMode.ASMAE_STRUCTURE: PaletteId.RAW_GRAYSCALE,
    RenderMode.ASMAE_BARE_SOIL: PaletteId.CARBON_BROWN,
    RenderMode.ASMAE_SALINITY_STRESS: PaletteId.SALINITY_TEAL,
    RenderMode.ASMAE_THERMAL_STRESS: PaletteId.THERMAL_ORANGE,
    RenderMode.ASMAE_BIOTIC_CONFOUNDER_RISK: PaletteId.STRESS_RED,
    RenderMode.ASMAE_PHENOLOGY_PROGRESS: PaletteId.VIGOR_GREEN,
    RenderMode.ASMAE_STRESS_MEMORY: PaletteId.STRESS_RED,
    RenderMode.ASMAE_EFFECTIVE_RESOLUTION: PaletteId.RAW_GRAYSCALE,
    RenderMode.ASMAE_POSTERIOR_CONCENTRATION: PaletteId.UNCERTAINTY_GRAY,
    RenderMode.ASMAE_UNCERTAINTY: PaletteId.UNCERTAINTY_GRAY,
    RenderMode.ASMAE_RETROVALIDATION_SCORE: PaletteId.UNCERTAINTY_GRAY,
    RenderMode.ASMAE_BMA_DISAGREEMENT: PaletteId.RISK_HEAT,
    RenderMode.ASMAE_CROSS_LAYER_CONFLICT: PaletteId.RISK_HEAT,
    RenderMode.ASMAE_EXPORT_ELIGIBILITY: PaletteId.RAW_GRAYSCALE,
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
