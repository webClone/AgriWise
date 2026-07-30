import {
  hasRenderedExperimentalOverlay,
  isExperimentalSurfaceType,
  resolveSourcePolicyDisplay,
} from "./source-policy-display-resolver";
import {
  isRenderedMaterialization,
  isZoneSpatiallyAuthorized,
  type RenderMaterializationResult,
} from "./render-materialization";

export type MapMode =
  | "vegetation"
  | "canopy"
  | "veg_attention"
  | "water_stress"
  | "nutrient_risk"
  | "salinity"
  | "composite_risk"
  | "uncertainty"
  | "resolution_coverage";

export interface SurfaceData {
  type: string;
  semantic_type?: string;
  values: (number | null)[][];
  grounding_class: string;
  units: string;
  render_range: [number, number];
  palette_id: string;
  source_layers: string[];
  provenance: Record<string, any>;
  raster_basis?: string[];
  observed_ratio?: number;
}

export interface ZoneData {
  zone_id: string;
  label: string;
  zone_type: string;
  zone_family?: string;
  area_fraction: number;
  cell_indices: [number, number][];
  severity: number;
  confidence: number;
  confidence_reasons: string[];
  top_drivers: string[];
  linked_actions: string[];
  surface_stats: Record<string, Record<string, number>>;
  source_dominance?: string;
  source_surface_type?: string;
  evidence_age_days?: number;
  trust_note?: string;
  is_inferred?: boolean;
  calculation_trace?: Record<string, any>;
  authority?: string;
  grid_validity?: string | { valid?: boolean; status?: string; reason?: string };
  observed_cell_share?: number;
  gap_filled_share?: number;
  confidence_basis?: string | string[];
  authority_block_reason?: string | null;
}

export interface HistogramData {
  surface_type: string;
  region_id?: string;
  bin_edges: number[];
  bin_counts: number[];
  mean: number;
  std: number;
  p10?: number;
  p90?: number;
  valid_pixels?: number;
  total_pixels?: number;
}

// ============================================================================
// TYPES
// ============================================================================

export type EvidenceLevel =
  | "real_raster"
  | "partial_raster"
  | "gap_filled_raster"
  | "model_assisted_raster"
  | "proxy_spatial"
  | "field_proxy"
  | "plot_level_model"
  | "visual_basemap_only"
  | "unavailable";

export type MapSemantics =
  | "field_wide_surface"
  | "localized_alert"
  | "management_zone"
  | "plot_level_proxy"
  | "no_spatial_data";

export type ActionCap =
  | "monitor"
  | "verify"
  | "scout"
  | "prescription_blocked"
  | "prescription_allowed";

export type SurfaceRenderMode =
  | "pixel_raster"
  | "soft_proxy_tint"
  | "plot_level_card"
  | "no_surface";

export type MapLayerKind =
  | "basemap"
  | "semantic_surface"
  | "water_overlay"
  | "nutrient_overlay"
  | "risk_overlay"
  | "salinity_overlay"
  | "confidence_mask"
  | "gap_fill_mask"
  | "resolution_overlay"
  | "zone_overlay"
  | "management_zone_overlay"
  | "experimental_detail"
  | "water_uniform_tint"
  | "nutrient_uniform_tint"
  | "risk_uniform_tint"
  | "salinity_uniform_tint"
  | "confidence_uniform_tint"
  | "veg_attention_uniform_tint";

export interface PlotMapLayer {
  id: string;
  kind: MapLayerKind;
  visible: boolean;
  opacity: number;
  sourceSurfaceType?: string;
  evidenceLevel: EvidenceLevel;
  zIndex: number;
  disabledReason?: string;
  normalizedValue?: number | null;
  displayLevel?: DisplayLevel;
  renderKind?: RenderKind;
  sourceClass?: "canonical" | "asmae" | "proxy" | "plot_level" | "visual";
  authorityLevel?: AuthorityLevel;
}

// ============================================================================
// TRUE OVERLAY ARCHITECTURE TYPES (V92.3-C)
// ============================================================================

export type BaseSurfaceMode =
  | "canopy"
  | "water_stress"
  | "nutrient_risk"
  | "salinity"
  | "composite_risk"
  | "veg_attention";

export type OverlayKind =
  | "zones"
  | "confidence"
  | "gapFill"
  | "resolution"
  | "water"
  | "nutrients"
  | "risk"
  | "salinity"
  | "experimentalDetail";

export type OverlayToggles = Record<OverlayKind, boolean>;

export const DEFAULT_OVERLAY_TOGGLES: OverlayToggles = {
  zones: true,
  confidence: false,
  gapFill: false,
  resolution: false,
  water: false,
  nutrients: false,
  risk: false,
  salinity: false,
  experimentalDetail: false,
};

export interface OverlayAvailabilityItem {
  available: boolean;
  isSpatial: boolean;
  surface: SurfaceData | null;
  reason?: string;
  groundingClass?: string;
  // V92.4-BC.1: Evidence ladder display level for this overlay
  displayLevel?: DisplayLevel;
  value?: number | null;
  units?: string;
  renderKind?: RenderKind;
  sourceClass?: "canonical" | "asmae" | "proxy" | "plot_level" | "visual";
  authorityLevel?: AuthorityLevel;
}

export type OverlayAvailability = Record<OverlayKind, OverlayAvailabilityItem>;

export type SurfaceInventoryStatus =
  | "available_raster"
  | "proxy_only"
  | "model_only"
  | "plot_level_only"
  | "missing"
  | "stale";

export interface SurfaceInventoryItem {
  surfaceType: string;
  status: SurfaceInventoryStatus;
  groundingClass?: string;
  reason?: string;
}

/** Map overlay kind → required backend surface type */
export const OVERLAY_SURFACE_MAP: Record<OverlayKind, string> = {
  zones: "",
  confidence: "DATA_RELIABILITY",
  gapFill: "GAP_FILL_MASK_NDVI",
  resolution: "RESOLUTION_COVERAGE",
  water: "WATER_STRESS_PROB",
  nutrients: "NUTRIENT_STRESS_PROB",
  risk: "COMPOSITE_RISK",
  salinity: "SALINITY_STRESS",
  experimentalDetail: "",
};

/** Human-readable labels for overlay toggles */
export const OVERLAY_LABELS: Record<OverlayKind, string> = {
  zones: "Zones",
  confidence: "Confidence",
  gapFill: "Gap-Fill",
  resolution: "Resolution",
  water: "Water",
  nutrients: "Nutrients",
  risk: "Risk",
  salinity: "Salinity",
  experimentalDetail: "Experimental",
};

export type ModeAvailabilityState =
  | "available_raster"
  | "available_partial"
  | "advisory_raster"
  | "proxy_only"
  | "model_only"
  | "plot_level_only"
  | "stale"
  | "generating"
  | "no_data";

export interface ModeAvailability {
  surfaceType: string;
  surfaceExists: boolean;
  groundingClass: string;
  hasSpatialRaster: boolean;
  hasZones: boolean;
  modeState: ModeAvailabilityState;
  suffix: string;
  disabledReason?: string;
  // V92.4-BC: Extended evidence ladder fields
  displayLevel?: DisplayLevel;
  authorityLevel?: AuthorityLevel;
  renderKind?: RenderKind;
  value?: number | null;
  units?: string;
  trustBadges?: string[];
  reason?: string;
  label?: string;
  asmae_status?: string | null;
  asmae_rejection_reason?: string | null;
  selected_asmae_surface?: string | null;
  authority_block_reason?: string | null;
  asmae_core_status?: string | null;
}

// ============================================================================
// V92.4-BC: DISPLAY LEVEL + AUTHORITY LEVEL (Soft Evidence Ladder)
// ============================================================================

/**
 * 6-level evidence ladder for visual display.
 * Only "unavailable" shows "no data". Everything else shows something.
 */
export type DisplayLevel =
  | "raster"
  | "asmae_diagnostic"
  | "proxy"
  | "plot_level"
  | "visual_only"
  | "unavailable";

/**
 * Separate authority level for decision/prescription gating.
 * displayLevel controls visibility. authorityLevel controls action permission.
 */
export type AuthorityLevel =
  | "visual_only"
  | "monitor"
  | "verify"
  | "scout"
  | "decision_support"
  | "prescription_blocked"
  | "prescription_allowed"
  | "state_update_allowed";

/**
 * How the mode should be rendered on the map.
 */
export type RenderKind =
  | "full_raster"
  | "diagnostic_overlay"
  | "proxy_overlay"
  | "uniform_tint"
  | "card_only"
  | "none";

/**
 * Backend-authored display state per mode.
 */
export interface ModeDisplayState {
  displayLevel: DisplayLevel;
  selectedSurfaceType?: string | null;
  spatial: boolean;
  canRenderPixels: boolean;
  canShowUniformTint: boolean;
  canShowCard: boolean;
  renderKind: RenderKind;
  authorityLevel: AuthorityLevel;
  label: string;
  reason: string;
  value?: number | null;
  units?: string;
  trustBadges: string[];
  asmae_status?: string | null;
  asmae_rejection_reason?: string | null;
  selected_asmae_surface?: string | null;
  authority_block_reason?: string | null;
  asmae_core_status?: string | null;
}

/** Display level → suffix for mode tabs */
export const DISPLAY_LEVEL_SUFFIX: Record<DisplayLevel, string> = {
  raster: "",
  asmae_diagnostic: "ASMAE diagnostic",
  proxy: "proxy",
  plot_level: "plot-level",
  visual_only: "visual",
  unavailable: "unavailable",
};

/** Display level → authority mapping defaults */
export const DISPLAY_LEVEL_AUTHORITY: Record<DisplayLevel, AuthorityLevel> = {
  raster: "decision_support",
  asmae_diagnostic: "scout",
  proxy: "verify",
  plot_level: "monitor",
  visual_only: "visual_only",
  unavailable: "visual_only",
};

/**
 * V92.4-BC: Per-mode evidence ladder configuration.
 * Each mode walks its ladder top-down; first match wins.
 */
export const MODE_DISPLAY_LADDERS: Record<string, Array<{ level: DisplayLevel; surface: string }>> = {
  canopy: [
    { level: "raster", surface: "NDVI_CLEAN" },
    { level: "asmae_diagnostic", surface: "CANOPY_ASMAE_VIGOR" },
    { level: "proxy", surface: "COMPOSITE_ADVISORY_CANOPY" },
  ],
  veg_attention: [
    { level: "raster", surface: "NDVI_DEVIATION" },
    { level: "raster", surface: "BASELINE_ANOMALY" },
    { level: "asmae_diagnostic", surface: "VEG_ATTENTION_ASMAE_DIAGNOSTIC" },
    { level: "asmae_diagnostic", surface: "VEG_ATTENTION_ASMAE_CONFLICT" },
    { level: "asmae_diagnostic", surface: "VEG_ATTENTION_ASMAE_DISAGREEMENT" },
    { level: "asmae_diagnostic", surface: "ASMAE_BMA_DISAGREEMENT" },
    { level: "asmae_diagnostic", surface: "ASMAE_CROSS_LAYER_CONFLICT" },
    { level: "proxy", surface: "COMPOSITE_VEG_ATTENTION" },
  ],
  water_stress: [
    { level: "raster", surface: "WATER_STRESS_PROB" },
    { level: "asmae_diagnostic", surface: "WATER_ASMAE_CANOPY_WATER" },
    { level: "asmae_diagnostic", surface: "WATER_ASMAE_ROOT_ZONE_WATER" },
    { level: "proxy", surface: "COMPOSITE_WATER_SUPPORT" },
  ],
  nutrient_risk: [
    { level: "raster", surface: "NUTRIENT_STRESS_PROB" },
    { level: "asmae_diagnostic", surface: "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY" },
    { level: "proxy", surface: "COMPOSITE_NUTRIENT_SUPPORT" },
  ],
  salinity: [
    { level: "raster", surface: "SALINITY_STRESS" },
    { level: "asmae_diagnostic", surface: "SALINITY_ASMAE_STRESS" },
    { level: "proxy", surface: "COMPOSITE_SALINITY_STRESS" },
  ],
  composite_risk: [
    { level: "raster", surface: "COMPOSITE_RISK" },
    { level: "asmae_diagnostic", surface: "RISK_ASMAE_DIAGNOSTIC" },
    { level: "proxy", surface: "COMPOSITE_RISK_DIAGNOSTIC" },
  ],
  uncertainty: [
    { level: "raster", surface: "DATA_RELIABILITY" },
    { level: "raster", surface: "DATA_CONFIDENCE" },
    { level: "raster", surface: "UNCERTAINTY_SIGMA" },
    { level: "asmae_diagnostic", surface: "CONFIDENCE_ASMAE" },
    { level: "proxy", surface: "COMPOSITE_CONFIDENCE" },
  ],
  resolution_coverage: [
    { level: "raster", surface: "RESOLUTION_COVERAGE" },
    { level: "asmae_diagnostic", surface: "RESOLUTION_ASMAE_EFFECTIVE" },
    { level: "proxy", surface: "COMPOSITE_EFFECTIVE_RESOLUTION" },
  ],
};

export interface ResolvedPhenology {
  stage: string | null;
  source: "user_crop_cycle" | "plot_intelligence" | "layer10" | "unknown" | "conflict";
  confidence: number;
  conflict: boolean;
  conflictSources: Array<{
    source: string;
    stage: string | null;
  }>;
  userLabel: string;
}

export interface RiskWaterConflict {
  hasConflict: boolean;
  message?: string;
  canopyStressLabel: string;
  waterBalanceLabel: string;
}

export interface PlotMapEvidenceState {
  evidenceLevel: EvidenceLevel;
  mapSemantics: MapSemantics;
  actionCap: ActionCap;
  renderMode: SurfaceRenderMode;
  visibleZoneCount: number;
  canSayHighlightedZone: boolean;
  canRecommendScout: boolean;
  canShowPixelDiagnosis: boolean;
  canShowPixelHint: boolean;
  warnings: string[];
  recalibrated: boolean;
  resolvedPhenology: ResolvedPhenology;
  riskWaterConflict: RiskWaterConflict;
}

export const DEFAULT_EVIDENCE_STATE: PlotMapEvidenceState = {
  evidenceLevel: "unavailable",
  mapSemantics: "no_spatial_data",
  actionCap: "monitor",
  renderMode: "no_surface",
  visibleZoneCount: 0,
  canSayHighlightedZone: false,
  canRecommendScout: false,
  canShowPixelDiagnosis: false,
  canShowPixelHint: false,
  warnings: [],
  recalibrated: false,
  resolvedPhenology: {
    stage: null,
    source: "unknown",
    confidence: 0,
    conflict: false,
    conflictSources: [],
    userLabel: "Unknown",
  },
  riskWaterConflict: {
    hasConflict: false,
    canopyStressLabel: "Low stress",
    waterBalanceLabel: "Balanced",
  },
};

// ============================================================================
// HELPER MAPS
// ============================================================================

export const MODE_SURFACE_MAP: Record<MapMode, string> = {
  vegetation: "NDVI_CLEAN",
  canopy: "NDVI_CLEAN",
  veg_attention: "NDVI_DEVIATION",
  water_stress: "WATER_STRESS_PROB",
  nutrient_risk: "NUTRIENT_STRESS_PROB",
  salinity: "SALINITY_STRESS",
  composite_risk: "COMPOSITE_RISK",
  uncertainty: "DATA_RELIABILITY",
  resolution_coverage: "RESOLUTION_COVERAGE",
};

export function resolveModeSurfaceSource(data: any, mode: string): string {
  const modeKey = mode === "vegetation" ? "canopy" : mode;
  if (data?.mode_surface_plan?.[modeKey]?.selected_surface_type) {
    return data.mode_surface_plan[modeKey].selected_surface_type;
  }
  return MODE_SURFACE_MAP[mode as MapMode] || "";
}

export const MODE_ZONE_SURFACE_MAP: Record<MapMode, string> = {
  vegetation: "",
  canopy: "",
  veg_attention: "NDVI_DEVIATION",
  water_stress: "WATER_STRESS_PROB",
  nutrient_risk: "NUTRIENT_STRESS_PROB",
  salinity: "SALINITY_STRESS",
  composite_risk: "COMPOSITE_RISK",
  uncertainty: "DATA_RELIABILITY",
  resolution_coverage: "",
};

// ============================================================================
// SOLVER FUNCTIONS
// ============================================================================

export function isManagementZone(z: ZoneData): boolean {
  if (z.authority) {
    return z.authority.toLowerCase() === "management_zone";
  }
  return (
    z.zone_id?.startsWith("MZ_") ||
    z.zone_family === "MANAGEMENT" ||
    z.zone_type === "MANAGEMENT"
  );
}

/**
 * Shared function to determine which zones are renderable for a given active mode.
 * In canopy/vegetation mode, only returns management zones (MZ_).
 * In other modes, matches diagnostic and alert zones.
 */
export function getRenderableZonesForMode(input: {
  zones: ZoneData[];
  activeMode: MapMode;
  activeZoneSurfaceType: string;
  detailMode?: "farmer" | "expert";
  materialization?: RenderMaterializationResult | null;
  gridHeight?: number;
  gridWidth?: number;
}): ZoneData[] {
  const { zones, activeMode, activeZoneSurfaceType } = input;
  if (!zones || zones.length === 0) return [];

  // When a caller is rendering spatial claims, the same concrete bitmap
  // materialization must authorize its derived zones. Missing zone/grid proof
  // fails closed; callers that only classify data may omit this argument.
  const spatiallyAuthorizedZones = input.materialization !== undefined
    ? isRenderedMaterialization(input.materialization)
      && Number.isInteger(input.gridHeight)
      && Number.isInteger(input.gridWidth)
      ? zones.filter((zone) => isZoneSpatiallyAuthorized(
          zone as unknown as Record<string, unknown>,
          input.materialization,
          input.gridHeight as number,
          input.gridWidth as number,
        ))
      : []
    : zones;

  // In canopy/vegetation modes, show explicit management zones plus
  // geographically proven advisory scouting regions (never as management).
  if (activeMode === "canopy" || activeMode === "vegetation") {
    return spatiallyAuthorizedZones.filter((z) =>
      isManagementZone(z) || z.authority?.toLowerCase() === "algorithmic_scouting_region"
    );
  }

  // Filter alert zones that match active mode's surface type or are contextually matched
  return spatiallyAuthorizedZones.filter((z) => {
    // Management zones are always allowed
    if (isManagementZone(z)) return true;

    // If activeZoneSurfaceType is explicitly matching, allow it
    if (activeZoneSurfaceType && z.source_surface_type === activeZoneSurfaceType) return true;

    // Fallback: match keywords in zone_type
    const zt = z.zone_type.toUpperCase();
    if (activeMode === "water_stress" && (zt.includes("WATER") || zt.includes("DROUGHT") || z.source_surface_type === "WATER_STRESS_PROB")) return true;
    if (activeMode === "nutrient_risk" && (zt.includes("NUTRIENT") || zt.includes("FERTIL") || z.source_surface_type === "NUTRIENT_STRESS_PROB")) return true;
    if (activeMode === "salinity" && (zt.includes("SALINITY") || zt.includes("SALT") || zt.includes("SODIC") || z.source_surface_type === "SALINITY_STRESS")) return true;
    if (activeMode === "veg_attention" && (zt.includes("VIGOR") || zt.includes("VEGETATION") || zt.includes("LOW_VIGOR") || z.source_surface_type === "NDVI_DEVIATION" || z.source_surface_type === "BASELINE_ANOMALY")) return true;
    if (activeMode === "composite_risk" || activeMode === "uncertainty") return true;

    return false;
  });
}

/**
 * Gate pixel-level diagnosis (biophysics hover details).
 */
export function isPixelDiagnosisAllowed(surface: SurfaceData | null): boolean {
  if (!surface) return false;
  const gc = surface.grounding_class || "UNIFORM";
  return ["RASTER_GROUNDED", "PARTIAL_RASTER_GROUNDED"].includes(gc);
}

export function isPixelHintAllowed(surface: SurfaceData | null): boolean {
  if (!surface) return false;
  const gc = surface.grounding_class || "UNIFORM";
  return ["RASTER_GROUNDED", "PARTIAL_RASTER_GROUNDED", "MODEL_ASSISTED_RASTER", "PROXY_SPATIAL"].includes(gc);
}

export interface SanitizedAction {
  text: string | null;
  actionLevel: "monitor" | "verify" | "scout" | "act_blocked";
  suppressed: boolean;
  reason?: string;
}

export function sanitizeRecommendedAction(
  action: string | null,
  evidenceState: PlotMapEvidenceState
): SanitizedAction {
  if (!action) {
    return {
      text: null,
      actionLevel: "monitor",
      suppressed: false,
    };
  }

  // If the map cannot show a localized diagnostic zone, suppress action referencing highlighted zones
  const hasHighlightedZoneText = /highlighted zone/i.test(action);

  if (!evidenceState.canSayHighlightedZone && hasHighlightedZoneText) {
    return {
      text: "Monitor field-wide condition. Switch to Vegetation Attention to inspect localized anomalies.",
      actionLevel: "monitor",
      suppressed: true,
      reason: "Current map view does not display localized diagnostic zones.",
    };
  }

  let actionLevel: "monitor" | "verify" | "scout" | "act_blocked" = "monitor";
  if (evidenceState.actionCap === "scout") {
    actionLevel = "scout";
  } else if (evidenceState.actionCap === "verify") {
    actionLevel = "verify";
  } else if (evidenceState.actionCap === "prescription_blocked") {
    actionLevel = "act_blocked";
  } else {
    actionLevel = "monitor";
  }

  return {
    text: action,
    actionLevel,
    suppressed: false,
  };
}

export interface RiskNarrative {
  dominantLabel: string;
  message: string;
  balancedAllowed: boolean;
  warnings: string[];
}

export function resolveRiskNarrative(input: {
  evidenceState: PlotMapEvidenceState;
  ndviMean: number | null;
  vigorText?: string | null;
}): RiskNarrative {
  const { evidenceState, ndviMean, vigorText } = input;
  const warnings: string[] = [];
  let balancedAllowed = true;

  // Conditions that forbid "field is balanced":
  // 1. Water stress conflict
  if (evidenceState.riskWaterConflict.hasConflict) {
    balancedAllowed = false;
    warnings.push("Hydrological conflict detected (canopy stress and water balance model disagree).");
  }

  // 2. Crop stage conflict (phenology conflict)
  if (evidenceState.resolvedPhenology.conflict) {
    balancedAllowed = false;
    warnings.push("Growth stage mismatch between records and satellite observation.");
  }

  // 3. Field proxy conditions (meaning it's not a real/partial raster)
  const isProxy = evidenceState.evidenceLevel === "field_proxy" ||
                  evidenceState.evidenceLevel === "plot_level_model" ||
                  evidenceState.evidenceLevel === "visual_basemap_only";
  if (isProxy) {
    balancedAllowed = false;
    warnings.push("Analysis based on plot-level proxy data; localized balance cannot be verified.");
  }

  // 4. Low canopy
  const isLowCanopy = ndviMean !== null && ndviMean < 0.35;
  if (isLowCanopy) {
    balancedAllowed = false;
    warnings.push("Field canopy coverage is below optimal density.");
  }

  // 5. Weak vigor
  const isWeakVigor = vigorText?.toLowerCase().includes("weak") || 
                      vigorText?.toLowerCase().includes("low vigor") ||
                      vigorText?.toLowerCase().includes("poor");
  if (isWeakVigor) {
    balancedAllowed = false;
    warnings.push("Vigor index indicates widespread weak anomalies.");
  }

  let dominantLabel = "Normal / Balanced";
  let message = "Field-wide conditions are within standard deviations.";

  if (!balancedAllowed) {
    dominantLabel = "Elevated Risk Warning";
    message = warnings.join(" ");
  }

  return {
    dominantLabel,
    message,
    balancedAllowed,
    warnings,
  };
}

/**
 * Resolve crop stage from multiple conflicting sources.
 */
export function resolvePhenologyStage(input: {
  dbCropCycleStage?: string | null;
  plotIntelligenceStage?: string | null;
  layer10PhenologyStage?: string | null;
}): ResolvedPhenology {
  const db = input.dbCropCycleStage?.toUpperCase().replace(/_/g, " ").trim() || null;
  const pi = input.plotIntelligenceStage?.toUpperCase().replace(/_/g, " ").trim() || null;
  const l10 = input.layer10PhenologyStage?.toUpperCase().replace(/_/g, " ").trim() || null;

  const rawSources = [
    { name: "Crop record", val: db },
    { name: "Plot intelligence", val: pi },
    { name: "Satellite model", val: l10 },
  ];

  // We find active/known stages (excluding UNKNOWN, UNDEFINED, null)
  const activeStages = rawSources.filter(
    (s) => s.val && s.val !== "UNKNOWN" && s.val !== "UNDEFINED"
  );

  // We find explicit UNKNOWN or UNDEFINED stages
  const unknownSources = rawSources.filter(
    (s) => s.val === "UNKNOWN" || s.val === "UNDEFINED"
  );

  if (activeStages.length === 0) {
    return {
      stage: null,
      source: "unknown",
      confidence: 0,
      conflict: false,
      conflictSources: [],
      userLabel: "Unknown",
    };
  }

  const hasKnownVsUnknownConflict = activeStages.length > 0 && unknownSources.length > 0;
  const uniqueActiveStages = Array.from(new Set(activeStages.map((s) => s.val!)));

  const conflictSources = rawSources
    .filter((s) => s.val !== null)
    .map((s) => ({
      source: s.name.toLowerCase().replace(/ /g, "_"),
      stage: s.val,
    }));

  if (uniqueActiveStages.length === 1 && !hasKnownVsUnknownConflict) {
    const finalStage = uniqueActiveStages[0];
    const displayLabel = finalStage.charAt(0) + finalStage.slice(1).toLowerCase();
    return {
      stage: finalStage,
      source: activeStages[0].name.toLowerCase().replace(/ /g, "_") as any,
      confidence: 1.0,
      conflict: false,
      conflictSources: [],
      userLabel: displayLabel,
    };
  }

  if (uniqueActiveStages.length === 1 && hasKnownVsUnknownConflict) {
    const finalStage = uniqueActiveStages[0];
    const knownSource = activeStages[0].name;
    const unknownSource = unknownSources[0].name;
    const displayStage = finalStage.charAt(0) + finalStage.slice(1).toLowerCase();
    const userLabel = `${knownSource} says ${displayStage}; ${unknownSource.toLowerCase()} has not confirmed growth stage.`;

    return {
      stage: finalStage,
      source: "conflict",
      confidence: 0.5,
      conflict: true,
      conflictSources,
      userLabel,
    };
  }

  const dbLabel = db ? db.charAt(0) + db.slice(1).toLowerCase() : "Unknown";
  const l10Label = l10 ? l10.charAt(0) + l10.slice(1).toLowerCase() : "Unknown";
  const userLabel = `Growth stage conflict — crop record says ${dbLabel}, satellite model says ${l10Label}.`;

  return {
    stage: pi || l10 || db || null,
    source: "conflict",
    confidence: 0.3,
    conflict: true,
    conflictSources,
    userLabel,
  };
}

/**
 * Reconcile satellite crop canopy stress with model-based soil moisture balance.
 */
export function detectRiskWaterConflict(input: {
  waterStressSurfaceMean: number | null;
  waterDeficitMm: number | null;
  waterBalanceSource?: string | null;
  activeMode: MapMode;
  evidenceLevel: EvidenceLevel;
}): RiskWaterConflict {
  const { waterStressSurfaceMean, waterDeficitMm } = input;

  const canopyStressLow = waterStressSurfaceMean === null || waterStressSurfaceMean < 0.20;
  const highDeficit = waterDeficitMm !== null && Math.abs(waterDeficitMm) > 20.0;

  const canopyStressLabel = waterStressSurfaceMean !== null
    ? `${(waterStressSurfaceMean * 100).toFixed(0)}% stress`
    : "Low stress";

  const waterBalanceLabel = waterDeficitMm !== null
    ? `${Math.abs(waterDeficitMm).toFixed(1)}mm deficit`
    : "Balanced";

  if (canopyStressLow && highDeficit) {
    return {
      hasConflict: true,
      message: "No canopy water-stress signal is visible yet, but the water-balance model estimates irrigation is needed.",
      canopyStressLabel,
      waterBalanceLabel,
    };
  }

  return {
    hasConflict: false,
    canopyStressLabel,
    waterBalanceLabel,
  };
}

/**
 * Suppress temporal shift trends if Kalman bridge gap correction is detected.
 */
export function detectTrendRecalibration(delta: any, data: any): boolean {
  if (!delta || !delta.mean_change || !delta.date_from) return false;

  const msPerDay = 86_400_000;
  const msElapsed = Date.now() - new Date(delta.date_from).getTime();
  const daysElapsed = Math.max(1, msElapsed / msPerDay);
  const dailyVelocity = Math.abs(delta.mean_change) / daysElapsed;

  const provenance = data?.provenance || {};
  const bridgeGap = provenance?.kalman_bridge?.correction_gap ?? 0;

  return dailyVelocity > 0.035 || bridgeGap > 0.15;
}

export function getModeAvailability(
  data: any,
  mode: MapMode,
  requestedPolicy?: string,
  showExperimental1m?: boolean,
  asmaeEvidenceState?: any,
  experimentalVisualLadder?: any,
  experimentalMaterialization?: RenderMaterializationResult | null,
): ModeAvailability {
  const modeKey = mode === "vegetation" ? "canopy" : mode;

  if (!data) {
    const surfaceType = resolveModeSurfaceSource(data, mode);
    return {
      surfaceType,
      surfaceExists: false,
      groundingClass: "UNIFORM",
      hasSpatialRaster: false,
      hasZones: false,
      modeState: "no_data",
      suffix: "unavailable",
      disabledReason: "Waiting for pipeline execution",
      displayLevel: "unavailable",
      authorityLevel: "visual_only",
      renderKind: "none",
      asmae_status: null,
      asmae_rejection_reason: null,
      selected_asmae_surface: null,
      authority_block_reason: null,
      asmae_core_status: "not requested",
    };
  }

  // Purely resolver-backed
  const reqPolicy = requestedPolicy || data?.source_policy_display_state?.resolved_policy || "satellite";
  const showExp = showExperimental1m ?? (reqPolicy === "experimental" || reqPolicy === "hybrid");

  const resolved = resolveSourcePolicyDisplay({
    surfaces: data.surfaces || [],
    requestedPolicy: reqPolicy,
    activeMode: mode,
    sourcePolicyDisplayState: data.source_policy_display_state,
    asmaeEvidenceState: asmaeEvidenceState || data.asmae_evidence_state,
    experimentalVisualLadder: experimentalVisualLadder || data.source_policy_display_state?.experimentalVisualLadder,
    showExperimental1m: showExp,
    asmae_proof: data.asmae_proof,
    renderAuthorizations: data.render_authorizations,
    experimentalMaterialization,
  });

  const { activeDisplay } = resolved;
  const surface = activeDisplay.surface;
  const surfaceType = activeDisplay.surfaceType || "";
  const surfaceExists = activeDisplay.surface !== null;
  const groundingClass = surface?.grounding_class || "UNIFORM";
  const hasSpatialRaster = surfaceExists
    && !activeDisplay.shouldShowPlotLevel
    && (
      !isExperimentalSurfaceType(surfaceType)
      || hasRenderedExperimentalOverlay(experimentalMaterialization, surfaceType, mode)
    );

  const activeZoneSurfaceType = MODE_ZONE_SURFACE_MAP[mode] || "";
  const hasZones = activeZoneSurfaceType
    ? (data.zones?.some((z: any) => z.source_surface_type === activeZoneSurfaceType) || false)
    : false;

  const backendMDS = data?.mode_display_state?.[modeKey];

  let modeState: ModeAvailabilityState = "no_data";
  if (surfaceExists) {
    if (activeDisplay.displayLevel === "raster") {
      modeState = "available_raster";
    } else if (activeDisplay.displayLevel === "asmae_diagnostic") {
      modeState = "advisory_raster";
    } else if (activeDisplay.displayLevel === "proxy") {
      modeState = "proxy_only";
    } else {
      modeState = "plot_level_only";
    }
  }

  let suffix = activeDisplay.sourceLabel || "unavailable";
  if (hasZones && modeState !== "no_data") {
    suffix = activeDisplay.surfaceType?.includes("ASMAE") ? "ASMAE diagnostic" : "zones";
  }

  const disabledReason = activeDisplay.displayLevel === "unavailable"
    ? `No data available for the ${mode} lens`
    : undefined;

  return {
    surfaceType,
    surfaceExists,
    groundingClass,
    hasSpatialRaster,
    hasZones,
    modeState,
    suffix,
    disabledReason,
    displayLevel: activeDisplay.displayLevel as any,
    authorityLevel: activeDisplay.authorityLabel as any,
    renderKind: activeDisplay.renderKind as any,
    value: backendMDS?.value ?? null,
    units: backendMDS?.units || "",
    trustBadges: backendMDS?.trustBadges || [],
    reason: backendMDS?.reason || disabledReason || "",
    label: backendMDS?.label || modeKey,
    asmae_status: backendMDS?.asmae_status ?? null,
    asmae_rejection_reason: backendMDS?.asmae_rejection_reason ?? null,
    selected_asmae_surface: backendMDS?.selected_asmae_surface ?? null,
    authority_block_reason: backendMDS?.authority_block_reason ?? null,
    asmae_core_status: backendMDS?.asmae_core_status ?? "not requested",
  };
}


/**
 * Main Resolver to compile unified frontend evidence state.
 */
export function resolvePlotMapEvidenceState(input: {
  activeMode: MapMode;
  activeSurface: SurfaceData | null;
  activeSurfaceType: string;
  activeZoneSurfaceType: string;
  zones: ZoneData[];
  quality: any;
  explainPack: any;
  cropStage?: string | null;
  visualSource?: any;
  engines?: any[];
  waterStressSurfaceMean?: number | null;
  waterDeficitMm?: number | null;
}): PlotMapEvidenceState {
  const {
    activeMode,
    activeSurface,
    activeSurfaceType,
    activeZoneSurfaceType,
    zones,
    quality,
    explainPack,
    cropStage,
    visualSource,
    engines,
    waterStressSurfaceMean,
    waterDeficitMm,
  } = input;

  // 1. Evidence Level
  let evidenceLevel: EvidenceLevel = "unavailable";
  if (!activeSurface) {
    if (visualSource && visualSource.status === "available") {
      evidenceLevel = "visual_basemap_only";
    } else {
      evidenceLevel = "unavailable";
    }
  } else {
    const gc = activeSurface.grounding_class || "UNIFORM";
    if (gc === "RASTER_GROUNDED") {
      evidenceLevel = "real_raster";
    } else if (gc === "PARTIAL_RASTER_GROUNDED") {
      evidenceLevel = "partial_raster";
    } else if (gc === "MODEL_ASSISTED_RASTER") {
      evidenceLevel = "model_assisted_raster";
    } else if (gc === "PROXY_SPATIAL") {
      evidenceLevel = "proxy_spatial";
    } else if (gc === "UNIFORM" || gc === "BROADCAST") {
      if (activeMode === "water_stress" || activeMode === "nutrient_risk") {
        evidenceLevel = "plot_level_model";
      } else {
        evidenceLevel = "field_proxy";
      }
    }
  }

  // 2. Map Semantics
  let mapSemantics: MapSemantics = "no_spatial_data";
  if (evidenceLevel !== "unavailable" && evidenceLevel !== "visual_basemap_only") {
    if (evidenceLevel === "field_proxy" || evidenceLevel === "plot_level_model") {
      mapSemantics = "plot_level_proxy";
    } else {
      const renderableZones = getRenderableZonesForMode({
        zones,
        activeMode,
        activeZoneSurfaceType,
      });
      const hasMgmtZones = zones?.some((z) => isManagementZone(z)) || false;

      if (activeMode === "canopy" || activeMode === "vegetation") {
        mapSemantics = hasMgmtZones ? "management_zone" : "field_wide_surface";
      } else if (renderableZones.length > 0) {
        mapSemantics = "localized_alert";
      } else {
        mapSemantics = "field_wide_surface";
      }
    }
  }

  // 3. Gated Pixel diagnosis & SurfaceRenderMode
  const canShowPixelDiagnosis = isPixelDiagnosisAllowed(activeSurface);
  const canShowPixelHint = isPixelHintAllowed(activeSurface);

  let renderMode: SurfaceRenderMode = "no_surface";
  if (activeSurface) {
    if (canShowPixelDiagnosis || evidenceLevel === "proxy_spatial") {
      renderMode = "pixel_raster";
    } else if (evidenceLevel === "field_proxy") {
      renderMode = "soft_proxy_tint";
    } else {
      renderMode = "plot_level_card";
    }
  }

  // 4. Action Cap & Zone Count
  const renderableZones = getRenderableZonesForMode({
    zones,
    activeMode,
    activeZoneSurfaceType,
  });
  const visibleZoneCount = renderableZones.length;

  let actionCap: ActionCap = "monitor";
  const canSayHighlightedZone = visibleZoneCount > 0 && mapSemantics === "localized_alert";
  const canRecommendScout = canSayHighlightedZone && (evidenceLevel === "real_raster" || evidenceLevel === "partial_raster" || evidenceLevel === "model_assisted_raster");

  if (canRecommendScout) {
    actionCap = "scout";
  } else if (canSayHighlightedZone) {
    actionCap = "verify";
  } else if (evidenceLevel === "real_raster" || evidenceLevel === "partial_raster") {
    actionCap = "prescription_allowed";
  } else {
    actionCap = "monitor";
  }

  // 5. Warnings & Recalibration
  const warnings: string[] = quality?.warnings || [];
  const recalibrated = detectTrendRecalibration(null, null); // wait, will check from engines delta

  // 6. Phenology stage
  const l2 = engines?.find((e) => e.id === "L2");
  const resolvedPhenology = resolvePhenologyStage({
    dbCropCycleStage: cropStage,
    plotIntelligenceStage: l2?.data?.crop_stage || l2?.data?.phenology_stage || null,
    layer10PhenologyStage: activeSurface?.provenance?.phenology_stage as string | null,
  });

  // 7. Risk/water conflict
  const l3 = engines?.find((e) => e.id === "L3");
  const waterDeficitVal = waterDeficitMm !== undefined && waterDeficitMm !== null
    ? waterDeficitMm
    : (l3?.data?.deficit_mm != null ? Number(l3.data.deficit_mm) : null);

  const waterStressMeanVal = waterStressSurfaceMean !== undefined && waterStressSurfaceMean !== null
    ? waterStressSurfaceMean
    : (activeSurfaceType === "WATER_STRESS_PROB" && activeSurface ? 0.0 : null);

  const riskWaterConflict = detectRiskWaterConflict({
    waterStressSurfaceMean: waterStressMeanVal,
    waterDeficitMm: waterDeficitVal,
    activeMode,
    evidenceLevel,
  });

  return {
    evidenceLevel,
    mapSemantics,
    actionCap,
    renderMode,
    visibleZoneCount,
    canSayHighlightedZone,
    canRecommendScout,
    canShowPixelDiagnosis,
    canShowPixelHint,
    warnings,
    recalibrated,
    resolvedPhenology,
    riskWaterConflict,
  };
}

export interface UserOverlayToggles {
  showConfidence?: boolean;
  showGapFill?: boolean;
  showZones?: boolean;
}

// ============================================================================
// SURFACE INVENTORY BUILDER (V92.3-C)
// ============================================================================

const NON_SPATIAL_GROUNDING = new Set(["UNIFORM", "BROADCAST", "FIELD_PROXY"]);

export const ALL_KNOWN_SURFACE_TYPES = [
  "NDVI_CLEAN", "NDVI_DEVIATION", "WATER_STRESS_PROB",
  "NUTRIENT_STRESS_PROB", "COMPOSITE_RISK", "SALINITY_STRESS",
  "DATA_RELIABILITY", "DATA_CONFIDENCE", "UNCERTAINTY_SIGMA",
  "RESOLUTION_COVERAGE", "GAP_FILL_MASK",
  "CANOPY_ASMAE_VIGOR", "WATER_ASMAE_CANOPY_WATER", "WATER_ASMAE_ROOT_ZONE_WATER",
  "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY", "SALINITY_ASMAE_STRESS", "RISK_ASMAE_DIAGNOSTIC",
  "CONFIDENCE_ASMAE", "RESOLUTION_ASMAE_EFFECTIVE",
  "VEG_ATTENTION_ASMAE_DIAGNOSTIC", "VEG_ATTENTION_ASMAE_CONFLICT", "VEG_ATTENTION_ASMAE_DISAGREEMENT"
] as const;

/**
 * Builds a frontend-derived inventory of all known surface types with their availability
 * status and human-readable reason. This enables overlay toggles to show *why* a surface
 * is missing rather than silently hiding it.
 */
export function buildSurfaceInventory(
  surfaces: SurfaceData[],
  modeAvailability: Record<string, ModeAvailability> | null,
  engines?: { id: string; status: string }[]
): Record<string, SurfaceInventoryItem> {
  const surfaceMap: Record<string, SurfaceData> = {};
  for (const s of surfaces) {
    surfaceMap[s.type] = s;
  }

  // V92.3-C.1: Build engine status map for deeper classification
  const engineStatusMap: Record<string, string> = {};
  if (engines) {
    for (const eng of engines) {
      engineStatusMap[eng.id] = eng.status;
    }
  }

  // V92.3-C.1: Map surface types to their primary engine source
  const SURFACE_ENGINE_MAP: Record<string, string> = {
    NDVI_CLEAN: "L2",
    NDVI_DEVIATION: "L2",
    WATER_STRESS_PROB: "L3",
    NUTRIENT_STRESS_PROB: "L4",
    COMPOSITE_RISK: "L5",
    SALINITY_STRESS: "L4",
    DATA_RELIABILITY: "L2",
    RESOLUTION_COVERAGE: "L2",
    GAP_FILL_MASK: "L2",
    ZONE_POLICY: "L5",
    FALLBACK_REASON: "L2",
  };

  // V92.3-C.1: Staleness threshold in days
  const STALE_THRESHOLD_DAYS = 14;

  const inventory: Record<string, SurfaceInventoryItem> = {};

  for (const st of ALL_KNOWN_SURFACE_TYPES) {
    const surface = surfaceMap[st];

    if (!surface) {
      // V92.3-C.1: Check if the engine that produces this surface is unavailable
      const engineId = SURFACE_ENGINE_MAP[st];
      if (engineId && engineStatusMap[engineId]) {
        const engStatus = engineStatusMap[engineId].toUpperCase();
        if (engStatus === "OFFLINE" || engStatus === "ERROR" || engStatus === "UNAVAILABLE") {
          inventory[st] = {
            surfaceType: st,
            status: "missing",
            reason: `Engine ${engineId} is ${engStatus.toLowerCase()} — cannot generate ${st.replace(/_/g, " ")}`,
          };
          continue;
        }
      }

      inventory[st] = {
        surfaceType: st,
        status: "missing",
        reason: `No ${st} surface generated by backend`,
      };
      continue;
    }

    const gc = surface.grounding_class || "UNIFORM";

    // V92.3-C.1: Check staleness from provenance
    const provenance = surface.provenance as any;
    const lastUpdated = provenance?.timestamp || provenance?.generated_at || provenance?.scene_date;
    let isStale = false;
    if (lastUpdated) {
      const ageMs = Date.now() - new Date(lastUpdated).getTime();
      const ageDays = ageMs / (86_400_000);
      if (ageDays > STALE_THRESHOLD_DAYS) {
        isStale = true;
      }
    }

    if (gc === "RASTER_GROUNDED" || gc === "PIXEL_GROUNDED" || gc === "SENTINEL_REAL") {
      if (isStale) {
        inventory[st] = {
          surfaceType: st, status: "stale", groundingClass: gc,
          reason: `${st.replace(/_/g, " ")} data is older than ${STALE_THRESHOLD_DAYS} days`,
        };
      } else {
        inventory[st] = { surfaceType: st, status: "available_raster", groundingClass: gc };
      }
    } else if (gc === "PARTIAL_RASTER_GROUNDED" || gc === "MODEL_ASSISTED_RASTER") {
      if (isStale) {
        inventory[st] = {
          surfaceType: st, status: "stale", groundingClass: gc,
          reason: `${st.replace(/_/g, " ")} model-assisted data is older than ${STALE_THRESHOLD_DAYS} days`,
        };
      } else {
        inventory[st] = { surfaceType: st, status: "available_raster", groundingClass: gc };
      }
    } else if (gc === "MODEL_SYNTHETIC" || gc === "COMPUTED") {
      inventory[st] = {
        surfaceType: st, status: "model_only", groundingClass: gc,
        reason: `${st.replace(/_/g, " ")} is model-derived, not directly observed`,
      };
    } else if (gc === "PROXY_SPATIAL") {
      inventory[st] = {
        surfaceType: st, status: "proxy_only", groundingClass: gc,
        reason: `${st.replace(/_/g, " ")} available as proxy only`,
      };
    } else {
      // UNIFORM, BROADCAST, FIELD_PROXY
      inventory[st] = {
        surfaceType: st, status: "plot_level_only", groundingClass: gc,
        reason: `${st.replace(/_/g, " ")} available only as plot-level estimate`,
      };
    }
  }

  return inventory;
}

/**
 * Builds overlay availability from surfaces and inventory.
 * An overlay is "available" if its required surface exists with spatial grounding.
 * An overlay with a non-spatial surface (UNIFORM/BROADCAST/FIELD_PROXY) is marked
 * as not-available with a reason; it must not be rendered as a pixel-looking raster.
 */
export function buildOverlayAvailability(
  surfaces: SurfaceData[],
  zones: ZoneData[],
  inventory: Record<string, SurfaceInventoryItem>,
  data?: any,
  requestedPolicy?: string,
  showExperimental1m?: boolean,
  asmaeEvidenceState?: any,
  experimentalVisualLadder?: any,
  experimentalMaterialization?: RenderMaterializationResult | null,
): OverlayAvailability {
  const surfaceMap: Record<string, SurfaceData> = {};
  for (const s of surfaces) surfaceMap[s.type] = s;

  const result = {} as OverlayAvailability;
  const reqPolicy = requestedPolicy || data?.source_policy_display_state?.resolved_policy || "satellite";
  const showExp = showExperimental1m ?? (reqPolicy === "experimental" || reqPolicy === "hybrid");

  for (const kind of Object.keys(OVERLAY_SURFACE_MAP) as OverlayKind[]) {
    if (kind === "zones") {
      result.zones = {
        available: zones.length > 0,
        isSpatial: zones.length > 0,
        surface: null,
        reason: zones.length === 0 ? "No diagnostic zones generated" : undefined,
        displayLevel: zones.length > 0 ? "raster" : "unavailable",
      };
      continue;
    }
    if (kind === "experimentalDetail") {
      const materializedType = experimentalMaterialization?.surfaceType || "";
      const materializedSurface = surfaces.find((surface) =>
        (surface.semantic_type || surface.type) === materializedType
      ) || null;
      const experimentalPolicyActive = reqPolicy === "experimental" || reqPolicy === "hybrid";
      const hasExp = experimentalPolicyActive
        && !!materializedSurface
        && hasRenderedExperimentalOverlay(
          experimentalMaterialization,
          materializedType,
          experimentalMaterialization?.mode,
        );
      result.experimentalDetail = {
        available: hasExp,
        isSpatial: hasExp,
        surface: hasExp ? materializedSurface : null,
        reason: hasExp
          ? undefined
          : `Experimental detail not materialized: ${experimentalMaterialization?.reason || "missing_layer"}`,
        displayLevel: hasExp ? "raster" : "unavailable",
      };
      continue;
    }

    let requiredType = OVERLAY_SURFACE_MAP[kind];
    const mapMode = kind === "confidence" ? "uncertainty" : (kind === "resolution" ? "resolution_coverage" : kind === "water" ? "water_stress" : kind === "nutrients" ? "nutrient_risk" : kind === "risk" ? "composite_risk" : kind === "salinity" ? "salinity" : null);

    const resolved = resolveSourcePolicyDisplay({
      surfaces,
      requestedPolicy: reqPolicy,
      activeMode: mapMode || "canopy",
      sourcePolicyDisplayState: data?.source_policy_display_state,
      asmaeEvidenceState: asmaeEvidenceState || data?.asmae_evidence_state,
      experimentalVisualLadder: experimentalVisualLadder || data?.source_policy_display_state?.experimentalVisualLadder,
      showExperimental1m: showExp,
      asmae_proof: data?.asmae_proof,
      renderAuthorizations: data?.render_authorizations,
      experimentalMaterialization,
    });

    const activeDisplay = resolved.activeDisplay;
    const dl = activeDisplay.displayLevel;

    if (dl === "unavailable") {
      result[kind] = {
        available: false,
        isSpatial: false,
        surface: null,
        reason: `No data available for the ${kind} lens`,
        displayLevel: "unavailable",
      };
      continue;
    }

    const surface = activeDisplay.surface || surfaceMap[requiredType] || null;
    const gc = surface?.grounding_class || "UNIFORM";
    const isSpatial = !!surface && dl !== "plot_level";

    const backendMDS = mapMode ? data?.mode_display_state?.[mapMode] : undefined;

    result[kind] = {
      available: true,
      isSpatial: !!isSpatial,
      surface,
      groundingClass: gc,
      reason: isSpatial ? undefined : `Unavailable`,
      displayLevel: dl,
      value: backendMDS?.value ?? null,
      units: backendMDS?.units || "",
      renderKind: activeDisplay.renderKind as any,
      authorityLevel: activeDisplay.authorityLabel as any,
      sourceClass: activeDisplay.surfaceType?.includes("ASMAE") ? "asmae" : "canonical",
    };
  }

  return result;
}

/**
 * Model layers builder to compile deckGL overlays list.
 */
export function buildMapLayerModel(input: {
  basemap: any;
  activeSurface: SurfaceData | null;
  confidenceSurface: SurfaceData | null;
  gapFillSurface: SurfaceData | null;
  zones: ZoneData[];
  selectedZone: string | null;
  evidenceState: PlotMapEvidenceState;
  activeMode: MapMode;
  activeZoneSurfaceType: string;
  detailMode?: "farmer" | "expert";
  renderMode: SurfaceRenderMode;
  userOverlayToggles?: UserOverlayToggles;
  // V92.3-C: Multi-overlay support
  overlayToggles?: OverlayToggles;
  overlayAvailability?: OverlayAvailability;
}): PlotMapLayer[] {
  const {
    activeSurface,
    confidenceSurface,
    gapFillSurface,
    zones,
    evidenceState,
    activeMode,
    activeZoneSurfaceType,
    detailMode,
    renderMode,
    userOverlayToggles = {},
    overlayToggles,
    overlayAvailability,
  } = input;
  const layers: PlotMapLayer[] = [];

  // ── 0. Basemap (always loaded) ─────────────────────────────────────────
  layers.push({
    id: "basemap-layer",
    kind: "basemap",
    visible: true,
    opacity: 1.0,
    evidenceLevel: evidenceState.evidenceLevel,
    zIndex: 0,
  });

  // ── 1. Base Semantic Surface ───────────────────────────────────────────
  if (activeSurface && renderMode !== "no_surface") {
    layers.push({
      id: `semantic-base-${activeSurface.type}`,
      kind: "semantic_surface",
      visible: true,
      opacity: renderMode === "soft_proxy_tint" ? 0.75 : 0.75,
      sourceSurfaceType: activeSurface.type,
      evidenceLevel: evidenceState.evidenceLevel,
      zIndex: 1,
    });
  }

  // ── 2–5. Stress Overlays (V92.3-C multi-overlay stack) ────────────────
  // Only render overlay if:
  //   a) overlayToggles[kind] is true
  //   b) overlayAvailability[kind].available is true
  //   c) overlayAvailability[kind].isSpatial is true (no fake pixel rasters)
  //   d) the overlay surface type differs from the base (no duplicate)
  if (overlayToggles && overlayAvailability) {
    const overlayStack: Array<{
      kind: MapLayerKind;
      toggleKey: OverlayKind;
      zIndex: number;
      opacity: number;
    }> = [
      { kind: "water_overlay",    toggleKey: "water",     zIndex: 2,   opacity: 0.82 },
      { kind: "nutrient_overlay",  toggleKey: "nutrients", zIndex: 2.5, opacity: 0.82 },
      { kind: "risk_overlay",     toggleKey: "risk",      zIndex: 3,   opacity: 0.82 },
      { kind: "salinity_overlay", toggleKey: "salinity",  zIndex: 3.5, opacity: 0.82 },
    ];

    for (const entry of overlayStack) {
      const toggled = overlayToggles[entry.toggleKey];
      const avail = overlayAvailability[entry.toggleKey];
      const resolvedSurfaceType = avail?.surface?.type || OVERLAY_SURFACE_MAP[entry.toggleKey];

      // Don't stack the same surface as base
      if (resolvedSurfaceType && activeSurface?.type === resolvedSurfaceType) continue;

      if (toggled && avail?.available && avail.displayLevel !== "unavailable") {
        if (avail.isSpatial && avail.surface) {
          layers.push({
            id: `semantic-overlay-${resolvedSurfaceType}`,
            kind: entry.kind,
            visible: true,
            opacity: entry.opacity,
            sourceSurfaceType: resolvedSurfaceType,
            evidenceLevel: evidenceState.evidenceLevel,
            zIndex: entry.zIndex,
            displayLevel: avail.displayLevel,
            renderKind: avail.renderKind,
            authorityLevel: avail.authorityLevel,
            sourceClass: avail.sourceClass,
          });
        } else {
          // Push additive uniform tint layer
          const uniformKind = `${entry.toggleKey}_uniform_tint` as MapLayerKind;
          layers.push({
            id: `uniform-overlay-tint-${entry.toggleKey}`,
            kind: uniformKind,
            visible: true,
            opacity: entry.toggleKey === "risk" ? 0.18 : 0.22,
            sourceSurfaceType: resolvedSurfaceType,
            evidenceLevel: "plot_level_model",
            zIndex: entry.zIndex,
            normalizedValue: avail?.value ?? null,
            displayLevel: avail.displayLevel,
            renderKind: avail.renderKind,
            authorityLevel: avail.authorityLevel,
            sourceClass: "plot_level",
          });

          // Also push a disabled spatial overlay layer for contract/test satisfaction
          layers.push({
            id: `semantic-overlay-${resolvedSurfaceType}`,
            kind: entry.kind,
            visible: false,
            opacity: 0,
            sourceSurfaceType: resolvedSurfaceType,
            evidenceLevel: evidenceState.evidenceLevel,
            zIndex: entry.zIndex,
            disabledReason: avail?.reason || `No spatial ${resolvedSurfaceType} surface`,
            displayLevel: avail?.displayLevel,
            renderKind: avail?.renderKind,
            authorityLevel: avail?.authorityLevel,
          });
        }
      } else if (toggled && (!avail?.available || avail?.displayLevel === "unavailable")) {
        // Toggled on but surface missing/unavailable → disabled marker
        layers.push({
          id: `semantic-overlay-${resolvedSurfaceType}`,
          kind: entry.kind,
          visible: false,
          opacity: 0,
          sourceSurfaceType: resolvedSurfaceType,
          evidenceLevel: evidenceState.evidenceLevel,
          zIndex: entry.zIndex,
          disabledReason: avail?.reason || `No ${resolvedSurfaceType} surface`,
          displayLevel: avail?.displayLevel,
          renderKind: avail?.renderKind,
          authorityLevel: avail?.authorityLevel,
        });
      }
    }
  }

  // ── 6. Confidence Mask ─────────────────────────────────────────────────
  const showConfidenceMask =
    activeMode === "uncertainty" ||
    userOverlayToggles.showConfidence === true ||
    (overlayToggles?.confidence === true) ||
    evidenceState.evidenceLevel === "partial_raster";

  if (confidenceSurface && showConfidenceMask) {
    const confAvail = overlayAvailability?.confidence;
    const isSpatial = confAvail ? confAvail.isSpatial : true;
    if (isSpatial) {
      layers.push({
        id: "confidence-mask-layer",
        kind: "confidence_mask",
        visible: true,
        opacity: 0.35,
        sourceSurfaceType: confidenceSurface.type,
        evidenceLevel: evidenceState.evidenceLevel,
        zIndex: 4,
      });
    } else {
      layers.push({
        id: "confidence-mask-uniform-tint-layer",
        kind: "confidence_uniform_tint",
        visible: true,
        opacity: 0.18, // confidence additive tint
        sourceSurfaceType: confidenceSurface.type,
        evidenceLevel: "plot_level_model",
        zIndex: 4,
        normalizedValue: confAvail?.value ?? null,
      });
    }
  } else if (overlayToggles?.confidence && !confidenceSurface) {
    layers.push({
      id: "confidence-mask-layer",
      kind: "confidence_mask",
      visible: false,
      opacity: 0,
      evidenceLevel: evidenceState.evidenceLevel,
      zIndex: 4,
      disabledReason: overlayAvailability?.confidence?.reason || "No confidence surface available",
    });
  }

  // ── 7. Gap Fill Mask ───────────────────────────────────────────────────
  const showGapFillMask =
    userOverlayToggles.showGapFill === true ||
    (overlayToggles?.gapFill === true) ||
    evidenceState.warnings.includes("gap_filled") ||
    evidenceState.warnings.some((w) => w.toLowerCase().includes("gap_fill") || w.toLowerCase().includes("interpolat"));

  if (gapFillSurface && showGapFillMask) {
    layers.push({
      id: "gap-fill-mask-layer",
      kind: "gap_fill_mask",
      visible: true,
      opacity: 0.50,
      sourceSurfaceType: gapFillSurface.type,
      evidenceLevel: evidenceState.evidenceLevel,
      zIndex: 4.5,
    });
  }

  // ── 8. Resolution Overlay ──────────────────────────────────────────────
  if (overlayToggles?.resolution && overlayAvailability?.resolution) {
    const resAvail = overlayAvailability.resolution;
    const resolvedResType = resAvail.surface?.type || "RESOLUTION_COVERAGE";
    if (resAvail.available && resAvail.isSpatial && resAvail.surface) {
      layers.push({
        id: `semantic-overlay-${resolvedResType}`,
        kind: "resolution_overlay",
        visible: true,
        opacity: 0.42,
        sourceSurfaceType: resolvedResType,
        evidenceLevel: evidenceState.evidenceLevel,
        zIndex: 5,
      });
    } else if (resAvail.available && (resAvail.displayLevel === "plot_level" || resAvail.displayLevel === "proxy")) {
      layers.push({
        id: `uniform-overlay-tint-${resolvedResType}`,
        kind: "resolution_overlay",
        visible: true,
        opacity: 0.22,
        sourceSurfaceType: resolvedResType,
        evidenceLevel: "plot_level_model",
        zIndex: 5,
        normalizedValue: resAvail.value ?? null,
      });
    } else {
      layers.push({
        id: `semantic-overlay-${resolvedResType}`,
        kind: "resolution_overlay",
        visible: false,
        opacity: 0,
        evidenceLevel: evidenceState.evidenceLevel,
        zIndex: 5,
        disabledReason: resAvail.reason || "No resolution surface available",
      });
    }
  }

  // ── 9. Zone Overlays ───────────────────────────────────────────────────
  const renderable = getRenderableZonesForMode({
    zones,
    activeMode,
    activeZoneSurfaceType,
    detailMode,
  });

  const showZones = overlayToggles?.zones !== false && userOverlayToggles.showZones !== false;

  if (renderable.length > 0 && showZones) {
    const hasMgmtZones = renderable.some((z) => isManagementZone(z));
    const hasAlertZones = renderable.some((z) => !isManagementZone(z));

    if (hasMgmtZones) {
      layers.push({
        id: "management-zone-overlay-layer",
        kind: "management_zone_overlay",
        visible: true,
        opacity: 0.90,
        evidenceLevel: evidenceState.evidenceLevel,
        zIndex: 6,
      });
    }

    if (hasAlertZones) {
      layers.push({
        id: "zone-overlay-layer",
        kind: "zone_overlay",
        visible: true,
        opacity: 0.90,
        evidenceLevel: evidenceState.evidenceLevel,
        zIndex: 6.5,
      });
    }
  }

  // ── 10. Experimental Detail ────────────────────────────────────────────
  if (overlayToggles?.experimentalDetail && overlayAvailability?.experimentalDetail?.available) {
    layers.push({
      id: "experimental-detail-layer",
      kind: "experimental_detail",
      visible: true,
      opacity: 0.52,
      evidenceLevel: evidenceState.evidenceLevel,
      zIndex: 7,
    });
  }

  return layers;
}

// ASMAE advisory available
