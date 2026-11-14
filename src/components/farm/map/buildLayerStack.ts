import { SurfaceData, ZoneData, MapMode, MODE_ZONE_SURFACE_MAP } from "@/hooks/useLayer10";
import {
  getRenderableZonesForMode,
  buildMapLayerModel,
  isManagementZone,
  type PlotMapEvidenceState,
  type UserOverlayToggles,
  type OverlayToggles,
  type OverlayAvailability,
  type ModeAvailability,
  type OverlayKind,
  OVERLAY_SURFACE_MAP,
} from "@/lib/agribrain/plot-map-evidence-state";
import { getSemanticSurfaceLayerLayer } from "./layers/SemanticSurfaceLayer";
import { getRenderAuthorization } from "@/lib/agribrain/source-policy-display-resolver";
import { getContourSurfaceLayer } from "./layers/ContourSurfaceLayer";
import { getUncertaintyGridLayer } from "./layers/UncertaintyGridLayer";
import { getUniformEvidenceTintLayer } from "./layers/UniformEvidenceTintLayer";
import { formatZoneGeoJson } from "./layers/zones/zoneUtils";
import { getUnifiedZoneLayer } from "./layers/zones/UnifiedZoneLayer";
import { getZoneGlowLayers } from "./layers/zones/ZoneGlowLayer";
import { SolidPolygonLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { buildPolygonMask } from "./utils/buildPolygonMask";
import {
  finalizeRenderMaterialization,
  resolveRenderMaterialization,
  type RenderMaterializationResult,
} from "@/lib/agribrain/render-materialization";

type ViewerMode = "farmer" | "expert";

type ZoneRing = [number, number][];

function zoneLayerIdPart(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, "-").slice(0, 80) || "unknown";
}

function signedRingArea(ring: ZoneRing): number {
  let area = 0;
  for (let index = 0; index < ring.length - 1; index++) {
    const current = ring[index];
    const next = ring[index + 1];
    area += current[0] * next[1] - next[0] * current[1];
  }
  return area / 2;
}

function orientation(a: [number, number], b: [number, number], c: [number, number]): number {
  return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}

function segmentsIntersect(
  a: [number, number],
  b: [number, number],
  c: [number, number],
  d: [number, number],
): boolean {
  const epsilon = 1e-12;
  const abC = orientation(a, b, c);
  const abD = orientation(a, b, d);
  const cdA = orientation(c, d, a);
  const cdB = orientation(c, d, b);
  return (
    ((abC > epsilon && abD < -epsilon) || (abC < -epsilon && abD > epsilon))
    && ((cdA > epsilon && cdB < -epsilon) || (cdA < -epsilon && cdB > epsilon))
  );
}

function validateZoneRing(rawRing: ZoneRing): { ring: ZoneRing; area: number } | null {
  if (rawRing.length < 4) return null;
  const ring = rawRing.filter((point, index) => {
    if (!Number.isFinite(point[0]) || !Number.isFinite(point[1])) return false;
    if (Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90) return false;
    const previous = rawRing[index - 1];
    return !previous || Math.abs(previous[0] - point[0]) > 1e-12 || Math.abs(previous[1] - point[1]) > 1e-12;
  });
  if (ring.length < 4) return null;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (Math.abs(first[0] - last[0]) > 1e-10 || Math.abs(first[1] - last[1]) > 1e-10) {
    return null;
  }

  const edgeCount = ring.length - 1;
  for (let left = 0; left < edgeCount; left++) {
    for (let right = left + 1; right < edgeCount; right++) {
      const adjacent = Math.abs(left - right) <= 1 || (left === 0 && right === edgeCount - 1);
      if (adjacent) continue;
      if (segmentsIntersect(ring[left], ring[left + 1], ring[right], ring[right + 1])) {
        return null;
      }
    }
  }

  const signedArea = signedRingArea(ring);
  if (!Number.isFinite(signedArea) || Math.abs(signedArea) <= 1e-14) return null;
  if (signedArea < 0) {
    const reversed = ring.slice(0, -1).reverse();
    reversed.push(reversed[0]);
    return { ring: reversed, area: Math.abs(signedArea) };
  }
  return { ring, area: signedArea };
}

import { normalizeMode } from "@/lib/agribrain/source-policy-display-resolver";

export function policyAllowsSurface(
  policy: string,
  surfaceType: string,
  layerRole: "base" | "overlay" | "candidate",
  renderAuthorizations?: any,
  mode?: string
): boolean {
  // BC.10.18: Deny-by-default when render authorization is absent.
  // The frontend may never promote backend authority — no local inference allowed.
  if (!renderAuthorizations) return false;

  const normMode = mode ? normalizeMode(mode) : "canopy";
  const auth = renderAuthorizations?.[policy]?.[normMode]?.[layerRole]?.[surfaceType];
  return auth?.authorized ?? false;
}

export function hasFiniteValues(s: any): boolean {
  if (!s || !s.values) return false;
  return s.values.some((row: any) => row && row.some((v: any) => v !== null && v !== undefined && isFinite(v)));
}

type RenderPolicy = {
  showContours: boolean;
  showUncertaintyGlyphs: boolean;
  showTrustLayer: boolean;
  maxZones: number;
  minAreaFraction: number;
  allowedZoneFamilies: Array<"diagnostic" | "action" | "trust" | "agronomic" | "management">;
  quantizeBands: number | null;
  detailMode: "farmer" | "expert";
};

const RENDER_POLICIES: Record<string, Record<ViewerMode, RenderPolicy>> = {
  // Canopy: beauty-only observation lens. Management zones visible.
  vegetation: {  // Compatibility alias → canopy
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 5,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["agronomic", "management"],
      quantizeBands: null,  // V63B: smooth continuous ramp, legend stays discrete
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 10,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["agronomic", "diagnostic", "management"],
      quantizeBands: null,
      detailMode: "expert",
    },
  },
  canopy: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 5,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["agronomic", "management"],
      quantizeBands: null,  // V63B: smooth continuous ramp
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 10,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["agronomic", "diagnostic", "management"],
      quantizeBands: null,
      detailMode: "expert",
    },
  },

  // Veg Attention: interpreted anomaly lens. Zones + contours active.
  veg_attention: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 15,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic"],
      quantizeBands: null,  // V63B: smooth continuous ramp
      detailMode: "farmer",
    },
    expert: {
      showContours: true,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic", "trust"],
      quantizeBands: null,
      detailMode: "expert",
    },
  },

  water_stress: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 15,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic", "action"],
      quantizeBands: null,  // V63B: smooth continuous ramp
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic", "action", "trust"],
      quantizeBands: null,
      detailMode: "expert",
    },
  },

  nutrient_risk: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 15,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic"],
      quantizeBands: null,  // V63B: smooth continuous ramp
      detailMode: "farmer",
    },
    expert: {
      showContours: true,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic", "trust"],
      quantizeBands: null,
      detailMode: "expert",
    },
  },
  
  composite_risk: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 15,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic", "action"],
      quantizeBands: null,  // V63B: smooth continuous ramp
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic", "action", "trust"],
      quantizeBands: null,
      detailMode: "expert",
    },
  },

  salinity: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 15,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic", "agronomic"],
      quantizeBands: null,  // V63B: smooth continuous ramp
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["diagnostic", "agronomic", "trust"],
      quantizeBands: null,
      detailMode: "expert",
    },
  },

  uncertainty: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 15,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["trust"],
      quantizeBands: null,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: true,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.0001,
      allowedZoneFamilies: ["trust"],
      quantizeBands: null,
      detailMode: "expert",
    },
  },

  // V61B: Resolution Coverage — pure categorical raster, no zones or overlays
  resolution_coverage: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 0,
      minAreaFraction: 0,
      allowedZoneFamilies: [],
      quantizeBands: null,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 0,
      minAreaFraction: 0,
      allowedZoneFamilies: [],
      quantizeBands: null,
      detailMode: "expert",
    },
  },
};

interface BuildLayerStackOptions {
  plotId?: string;
  activeMode?: string;
  surfaceData?: SurfaceData | null;
  surfaceColors?: [string, string, string] | null;
  confidenceSurface?: SurfaceData | null;
  reliabilitySurface?: SurfaceData | null;
  deviationSurface?: SurfaceData | null;
  plotGeoJson?: GeoJSON.Feature<GeoJSON.Geometry> | null;
  l10Zones?: ZoneData[] | null;
  selectedZone?: string | null;
  hoveredZoneId?: string | null;
  detailMode?: "farmer" | "expert";
  paletteId?: string;
  transectPoints?: [number, number][] | null;
  hoveredSampleCoordinate?: [number, number] | null;
  onZoneClick?: (zoneId: string) => void;
  onZoneHover?: (zoneId: string | null) => void;
  showExperimental1m?: boolean;
  showCandidateMask?: boolean;
  isLowConfidence?: boolean;
  experimental1mSurface?: SurfaceData | null;
  renderMode?: string;
  evidenceState: PlotMapEvidenceState;
  userOverlayToggles?: UserOverlayToggles;
  // V92.3-C: Multi-overlay support
  overlaySurfaces?: Record<string, SurfaceData | null>;
  overlayToggles?: OverlayToggles;
  overlayAvailability?: OverlayAvailability;
  zoom?: number;
  // V92.4-BC: Mode evidence ladder availability
  modeAvailability?: ModeAvailability;
  candidateMaskSurface?: SurfaceData | null;
  canopySource?: string;
  activeDisplay?: any;
  shouldShowPlotLevel?: boolean;
  activeSurfaceType?: string;
  renderAuthorizations?: any;
  renderAuthorizationVersion?: string;
  baseMaterialization?: RenderMaterializationResult | null;
  experimentalMaterialization?: RenderMaterializationResult | null;
}

// V92.3-C: Distinct color ramps for each overlay kind so they stack visually
const OVERLAY_COLOR_RAMPS: Record<string, [string, string, string]> = {
  WATER_STRESS_PROB:    ["#1a5276", "#f39c12", "#e74c3c"],  // blue → amber → red
  NUTRIENT_STRESS_PROB: ["#27ae60", "#f1c40f", "#c0392b"],  // green → yellow → red
  COMPOSITE_RISK:       ["#2ecc71", "#e67e22", "#e74c3c"],  // green → orange → red
  SALINITY_STRESS:      ["#0d9488", "#22d3ee", "#ef4444"],  // teal → cyan → red
  RESOLUTION_COVERAGE:  ["#06b6d4", "#f59e0b", "#64748b"],  // cyan → amber → slate
  DATA_RELIABILITY:     ["#e74c3c", "#f1c40f", "#2ecc71"],  // red → yellow → green
  // ASMAE aliases mapping
  CANOPY_ASMAE_VIGOR:               ["#8B0000", "#FFD700", "#006400"],
  WATER_ASMAE_CANOPY_WATER:         ["#c0392b", "#f1c40f", "#1a5276"],
  WATER_ASMAE_ROOT_ZONE_WATER:      ["#c0392b", "#f1c40f", "#1a5276"],
  NUTRIENT_ASMAE_CHLOROPHYLL_PROXY: ["#c0392b", "#f1c40f", "#27ae60"],
  SALINITY_ASMAE_STRESS:            ["#0d9488", "#22d3ee", "#ef4444"],
  RISK_ASMAE_DIAGNOSTIC:            ["#2ecc71", "#e67e22", "#e74c3c"],
  ASMAE_POSTERIOR_CONCENTRATION:    ["#e74c3c", "#f1c40f", "#2ecc71"],
  RESOLUTION_ASMAE_EFFECTIVE:       ["#06b6d4", "#f59e0b", "#64748b"],
  // V92.4-BC.2: Veg Attention ASMAE aliases
  VEG_ATTENTION_ASMAE_DIAGNOSTIC:   ["#8B4513", "#FFDEAD", "#228B22"],
  VEG_ATTENTION_ASMAE_CONFLICT:     ["#8B4513", "#FFDEAD", "#228B22"],
  VEG_ATTENTION_ASMAE_DISAGREEMENT: ["#8B4513", "#FFDEAD", "#228B22"],
  // Canonical ASMAE 13 states
  ASMAE_VIGOR:                      ["#8B0000", "#FFD700", "#006400"],
  ASMAE_LAI:                        ["#8B0000", "#FFD700", "#006400"],
  ASMAE_CHLOROPHYLL:                ["#c0392b", "#f1c40f", "#27ae60"],
  ASMAE_CANOPY_WATER:               ["#c0392b", "#f1c40f", "#1a5276"],
  ASMAE_ROOT_ZONE_WATER:            ["#c0392b", "#f1c40f", "#1a5276"],
  ASMAE_SURFACE_WETNESS_EVENT:      ["#c0392b", "#f1c40f", "#1a5276"],
  ASMAE_STRUCTURE:                  ["#8B0000", "#FFD700", "#006400"],
  ASMAE_BARE_SOIL:                  ["#fef3c7", "#a16207", "#451a03"],
  ASMAE_SALINITY_STRESS:            ["#0d9488", "#22d3ee", "#ef4444"],
  ASMAE_THERMAL_STRESS:             ["#fff7ed", "#fb923c", "#9a3412"],
  ASMAE_BIOTIC_CONFOUNDER_RISK:     ["#fff7bc", "#fc8d59", "#b91c1c"],
  ASMAE_PHENOLOGY_PROGRESS:         ["#8B0000", "#FFD700", "#006400"],
  ASMAE_STRESS_MEMORY:              ["#fff7bc", "#fc8d59", "#b91c1c"],
};

// V92.3-C.1: Map surface type strings to SemanticSurfaceLayer-compatible mode names
// SemanticSurfaceLayer uses MODE_RAMPS keyed by lowercase mode names like "water_stress",
// not by surface type strings like "WATER_STRESS_PROB".
const SURFACE_TYPE_TO_MODE: Record<string, string> = {
  WATER_STRESS_PROB: "water_stress",
  NUTRIENT_STRESS_PROB: "nutrient_risk",
  COMPOSITE_RISK: "composite_risk",
  SALINITY_STRESS: "salinity",
  RESOLUTION_COVERAGE: "resolution_coverage",
  DATA_RELIABILITY: "uncertainty",
  GAP_FILL_MASK: "gap_fill",
  // ASMAE aliases mapping
  CANOPY_ASMAE_VIGOR: "canopy",
  WATER_ASMAE_CANOPY_WATER: "water_stress",
  WATER_ASMAE_ROOT_ZONE_WATER: "water_stress",
  NUTRIENT_ASMAE_CHLOROPHYLL_PROXY: "nutrient_risk",
  SALINITY_ASMAE_STRESS: "salinity",
  RISK_ASMAE_DIAGNOSTIC: "composite_risk",
  ASMAE_POSTERIOR_CONCENTRATION: "uncertainty",
  RESOLUTION_ASMAE_EFFECTIVE: "resolution_coverage",
  // V92.4-BC.2: Veg Attention ASMAE aliases
  VEG_ATTENTION_ASMAE_DIAGNOSTIC: "veg_attention",
  VEG_ATTENTION_ASMAE_CONFLICT: "veg_attention",
  VEG_ATTENTION_ASMAE_DISAGREEMENT: "veg_attention",
  // Canonical ASMAE 13 states
  ASMAE_VIGOR: "canopy",
  ASMAE_LAI: "canopy",
  ASMAE_CHLOROPHYLL: "nutrient_risk",
  ASMAE_CANOPY_WATER: "water_stress",
  ASMAE_ROOT_ZONE_WATER: "water_stress",
  ASMAE_SURFACE_WETNESS_EVENT: "water_stress",
  ASMAE_STRUCTURE: "canopy",
  ASMAE_BARE_SOIL: "canopy",
  ASMAE_SALINITY_STRESS: "salinity",
  ASMAE_THERMAL_STRESS: "composite_risk",
  ASMAE_BIOTIC_CONFOUNDER_RISK: "composite_risk",
  ASMAE_PHENOLOGY_PROGRESS: "canopy",
  ASMAE_STRESS_MEMORY: "composite_risk",
};

// V92.3-C.1: Resolve per-overlay render mode from the overlay surface's grounding class.
// Overlays should NOT inherit the base evidenceState.renderMode because base may be FIELD_PROXY
// while the overlay has real spatial data.
function resolveOverlayRenderMode(surfaceData: SurfaceData | null | undefined): string {
  if (!surfaceData) return "standard";
  const gc = (surfaceData.grounding_class || "").toUpperCase();
  if (gc === "RASTER_GROUNDED" || gc === "PIXEL_GROUNDED" || gc === "SENTINEL_REAL") {
    return "standard";
  }
  if (gc === "MODEL_SYNTHETIC" || gc === "COMPUTED") {
    return "soft_proxy_tint";
  }
  if (gc === "UNIFORM" || gc === "BROADCAST" || gc === "FIELD_PROXY") {
    return "soft_proxy_tint";
  }
  // Default: if grounding is unknown, assume standard since we already gate non-spatial out
  return "standard";
}

export function buildLayerStack(options: BuildLayerStackOptions) {
  const {
    plotId,
    activeMode,
    surfaceData,
    surfaceColors,
    confidenceSurface,
    reliabilitySurface,
    deviationSurface,
    plotGeoJson,
    l10Zones,
    selectedZone,
    hoveredZoneId,
    detailMode = "farmer",
    paletteId = "standard",
    transectPoints = null,
    hoveredSampleCoordinate = null,
    onZoneClick,
    onZoneHover,
    showExperimental1m = false,
    showCandidateMask = false,
    isLowConfidence = false,
    experimental1mSurface = null,
    candidateMaskSurface = null,
    renderMode,
    evidenceState,
    userOverlayToggles = {},
    overlaySurfaces = {},
    overlayToggles,
    overlayAvailability,
    zoom,
    modeAvailability,
    canopySource,
    activeDisplay,
    shouldShowPlotLevel,
    activeSurfaceType,
    renderAuthorizations,
    renderAuthorizationVersion,
    baseMaterialization: suppliedBaseMaterialization,
    experimentalMaterialization: suppliedExperimentalMaterialization,
  } = options;

  const defaultColors: [string, string, string] = ["#8B0000", "#FFD700", "#006400"];
  
  // Resolve Render Policy
  const safeMode = activeMode && RENDER_POLICIES[activeMode] ? activeMode : "vegetation";
  const policy = RENDER_POLICIES[safeMode][detailMode];
  const observedMaskSurface =
    overlaySurfaces["OBSERVED_DATA_MASK_NDVI"] ||
    overlaySurfaces["OBSERVED_MASK"] ||
    overlaySurfaces["VALID_DATA_MASK"] ||
    overlaySurfaces["OBSERVED_DATA_MASK"] ||
    overlaySurfaces["CANONICAL_OBSERVED_MASK"] ||
    null;
  const gapFillMaskSurface =
    overlaySurfaces["GAP_FILL_MASK_NDVI"] ||
    overlaySurfaces["GAP_FILL_MASK"] ||
    null;

  const getOverlayAuthorization = (surface: SurfaceData | null | undefined, mode: string) => {
    const surfaceType = surface?.semantic_type || surface?.type || "";
    return getRenderAuthorization(
      surfaceType,
      canopySource || "satellite",
      normalizeMode(mode),
      "overlay",
      renderAuthorizations
    );
  };

  const hybridOverlayAllowed = (surface: SurfaceData | null | undefined, mode: string) => {
    const auth = getOverlayAuthorization(surface, mode);
    return !!auth?.authorized && (auth.renderKind === "diagnostic_overlay" || auth.renderKind === "proxy_overlay");
  };

  // Is any zone currently selected? (for inspection-mode dimming)
  const isInspecting = !!selectedZone;

  // 0. Zone Rendering Policy (Phase 2H) 
  const activeZoneSurfaceType = MODE_ZONE_SURFACE_MAP[activeMode as MapMode] || "";
  
  // Wire buildMapLayerModel to drive DeckGL layer visibility
  const rawLayerModel = buildMapLayerModel({
    basemap: {},
    activeSurface: surfaceData || null,
    confidenceSurface: confidenceSurface || null,
    gapFillSurface: gapFillMaskSurface,
    zones: l10Zones || [],
    selectedZone: selectedZone || null,
    evidenceState,
    activeMode: activeMode as MapMode,
    activeZoneSurfaceType,
    detailMode,
    renderMode: evidenceState.renderMode,
    userOverlayToggles,
    overlayToggles,
    overlayAvailability,
  });

  const layerModel = rawLayerModel.filter(layer => {
    if (!layer.sourceSurfaceType) return true;
    const isCandidate = layer.kind.includes("candidate");
    const isOverlay = layer.kind.endsWith("_overlay") || layer.kind.endsWith("_uniform_tint") || layer.kind === "confidence_mask";
    const role = isCandidate ? "candidate" : (isOverlay ? "overlay" : "base");
    return policyAllowsSurface(canopySource || "satellite", layer.sourceSurfaceType, role, renderAuthorizations, activeMode);
  });

  const showSemanticSurface = layerModel.some((l) => l.kind === "semantic_surface" && l.visible);
  const showConfidenceMask = layerModel.some((l) => l.kind === "confidence_mask" && l.visible);
  const showMgmtOverlay = layerModel.some((l) => l.kind === "management_zone_overlay" && l.visible);
  const showAlertOverlay = layerModel.some((l) => l.kind === "zone_overlay" && l.visible);

  // A derived spatial claim is only allowed after a concrete DeckGL bitmap
  // exists. Authorization, grid validity, masks, and image creation are one
  // materialization contract shared with zones/sidebar/HUD.
  const normalizedActiveMode = normalizeMode(activeMode || "canopy");
  const baseLayerId = "l10-surface-semantic";
  const surfaceOpacity =
    showExperimental1m && isLowConfidence
      ? 0.82
      : isInspecting
        ? 0.75
        : 1.0;
  const surfaceTypeStr = String(surfaceData?.semantic_type || surfaceData?.type || "").trim().toUpperCase();
  const activeDisplayTypeStr = String(activeDisplay?.surfaceType || "").trim().toUpperCase();
  const activeSurfaceTypeStr = String(activeSurfaceType || "").trim().toUpperCase();
  const matchesActiveType = !activeDisplayTypeStr || activeDisplayTypeStr === surfaceTypeStr || activeSurfaceTypeStr === surfaceTypeStr;

  const shouldAttemptBaseMaterialization = !!(
    surfaceData
    && hasFiniteValues(surfaceData)
    && (
      !activeDisplay?.renderKind ||
      activeDisplay.renderKind === "full_raster" ||
      activeDisplay.renderKind === "diagnostic_overlay" ||
      activeDisplay.renderKind === "proxy_overlay"
    )
    && matchesActiveType
  );
  const basePreflight = suppliedBaseMaterialization || resolveRenderMaterialization({
    surface: surfaceData,
    plotGeoJson,
    policy: canopySource || "satellite",
    mode: normalizedActiveMode,
    role: "base",
    renderAuthorizationVersion,
    renderAuthorizations,
    observedMaskSurface,
    gapFillMaskSurface,
    modeDisplayState: {
      spatial: modeAvailability?.hasSpatialRaster,
      canRenderPixels: modeAvailability?.hasSpatialRaster,
      renderKind: activeDisplay?.renderKind,
      reason: activeDisplay?.reason || modeAvailability?.reason,
    },
    layerId: baseLayerId,
  });
  const baseRasterLayer = shouldAttemptBaseMaterialization
    && (basePreflight.reason === "image_layer_not_created" || basePreflight.status === "rendered")
    ? getSemanticSurfaceLayerLayer({
        id: baseLayerId,
        plotId,
        surfaceData,
        surfaceColors: surfaceColors || defaultColors,
        plotGeoJson: plotGeoJson || undefined,
        opacity: surfaceOpacity,
        detailMode: policy.detailMode,
        quantizeBands: policy.quantizeBands,
        mode: normalizedActiveMode,
        reliabilitySurface: reliabilitySurface || undefined,
        deviationSurface: deviationSurface || undefined,
        paletteId,
        renderMode: evidenceState.renderMode,
        zoom,
        gapFillSurface: gapFillMaskSurface,
        observedMaskSurface,
        renderKind: modeAvailability?.renderKind,
        displayLevel: modeAvailability?.displayLevel,
        applyTrustToBase: activeMode === "uncertainty",
        confidenceSurface: confidenceSurface || undefined,
        renderAuthorizations,
        policy: canopySource || "satellite",
        role: "base",
      })
    : null;
  const baseMaterialization = finalizeRenderMaterialization(
    basePreflight,
    baseRasterLayer,
    baseLayerId,
  );

  const experimentalEnabled = overlayToggles?.experimentalDetail
    ?? (canopySource === "experimental" || canopySource === "hybrid");
  const experimentalLayerId = "l10-surface-experimental-fine-detail";
  const experimentalPreflight = suppliedExperimentalMaterialization || resolveRenderMaterialization({
    surface: experimental1mSurface,
    plotGeoJson,
    policy: "experimental",
    mode: normalizedActiveMode,
    role: "overlay",
    renderAuthorizationVersion,
    renderAuthorizations,
    observedMaskSurface,
    gapFillMaskSurface,
    modeDisplayState: { spatial: true, canRenderPixels: true, renderKind: "proxy_overlay" },
    layerId: experimentalLayerId,
  });
  const experimentalRasterLayer = experimentalEnabled
    && experimental1mSurface
    && (experimentalPreflight.reason === "image_layer_not_created" || experimentalPreflight.status === "rendered")
    ? getSemanticSurfaceLayerLayer({
        id: experimentalLayerId,
        plotId,
        surfaceData: experimental1mSurface,
        surfaceColors: surfaceColors || defaultColors,
        plotGeoJson: plotGeoJson || undefined,
        opacity: surfaceOpacity,
        detailMode: policy.detailMode,
        quantizeBands: null,
        mode: normalizedActiveMode,
        paletteId,
        renderMode: resolveOverlayRenderMode(experimental1mSurface),
        zoom,
        gapFillSurface: gapFillMaskSurface,
        observedMaskSurface,
        renderKind: "proxy_overlay",
        displayLevel: "raster",
        applyTrustToBase: false,
        renderAuthorizations,
        policy: "experimental",
        role: "overlay",
      })
    : null;
  const experimentalMaterialization = experimentalRasterLayer
    ? finalizeRenderMaterialization(experimentalPreflight, experimentalRasterLayer, experimentalLayerId)
    : (suppliedExperimentalMaterialization?.status === "rendered" ? suppliedExperimentalMaterialization : (experimentalEnabled
      ? experimentalPreflight
      : experimentalPreflight.reason === "image_layer_not_created" ? {
          ...experimentalPreflight,
          status: "blocked_image_generation" as const,
          reason: "overlay_not_requested",
          layerId: null,
        } : experimentalPreflight));

  // Hybrid is a set of independently authorized and independently committed
  // overlays.  Keep the concrete DeckGL layers paired with preflight receipts
  // so the browser can later attest exactly which subset reached the map.
  const hybridOverlayLayers: NonNullable<ReturnType<typeof getSemanticSurfaceLayerLayer>>[] = [];
  const hybridOverlayMaterializations: RenderMaterializationResult[] = [];
  const hybridBaseType = surfaceData?.semantic_type || surfaceData?.type || "";
  if (
    activeMode === "canopy"
    && canopySource === "hybrid"
    && hybridBaseType !== "ASMAE_VISUAL_FUSION_CANOPY"
  ) {
    const hybridCandidates: Array<{
      surface: SurfaceData | null | undefined;
      mode: string;
      layerId: string;
      opacity: number;
      colors: [string, string, string];
    }> = [
      {
        surface: overlaySurfaces["CANOPY_ASMAE_VIGOR"],
        mode: "canopy",
        layerId: "l10-surface-hybrid-vigor",
        opacity: 0.5,
        colors: OVERLAY_COLOR_RAMPS["CANOPY_ASMAE_VIGOR"] || defaultColors,
      },
      {
        surface: overlaySurfaces["ASMAE_POSTERIOR_CONCENTRATION"],
        mode: "uncertainty",
        layerId: "l10-surface-hybrid-confidence",
        opacity: 0.3,
        colors: OVERLAY_COLOR_RAMPS["ASMAE_POSTERIOR_CONCENTRATION"] || defaultColors,
      },
      {
        surface: overlaySurfaces["ASMAE_BMA_DISAGREEMENT"]
          || overlaySurfaces["VEG_ATTENTION_ASMAE_DISAGREEMENT"],
        mode: "veg_attention",
        layerId: "l10-surface-hybrid-disagreement",
        opacity: 0.35,
        colors: OVERLAY_COLOR_RAMPS["VEG_ATTENTION_ASMAE_DISAGREEMENT"] || defaultColors,
      },
    ];

    for (const candidate of hybridCandidates) {
      if (!candidate.surface || !hybridOverlayAllowed(candidate.surface, candidate.mode)) continue;
      const authorization = getOverlayAuthorization(candidate.surface, candidate.mode);
      const preflight = resolveRenderMaterialization({
        surface: candidate.surface,
        plotGeoJson,
        policy: canopySource,
        mode: normalizeMode(candidate.mode),
        role: "overlay",
        renderAuthorizationVersion,
        renderAuthorizations,
        observedMaskSurface,
        gapFillMaskSurface,
        modeDisplayState: {
          spatial: true,
          canRenderPixels: true,
          renderKind: authorization.renderKind,
        },
        layerId: candidate.layerId,
      });
      const layer = preflight.reason === "image_layer_not_created" || preflight.status === "rendered"
        ? getSemanticSurfaceLayerLayer({
            id: candidate.layerId,
            plotId,
            surfaceData: candidate.surface,
            surfaceColors: candidate.colors,
            plotGeoJson: plotGeoJson || undefined,
            opacity: candidate.opacity,
            detailMode: policy.detailMode,
            quantizeBands: null,
            mode: candidate.mode,
            paletteId: "standard",
            renderMode: resolveOverlayRenderMode(candidate.surface),
            zoom,
            gapFillSurface: gapFillMaskSurface,
            observedMaskSurface,
            renderKind: authorization.renderKind,
            displayLevel: "asmae_diagnostic",
            renderAuthorizations,
            policy: canopySource,
            role: "overlay",
          })
        : null;
      const materialization = finalizeRenderMaterialization(
        preflight,
        layer,
        candidate.layerId,
      );
      hybridOverlayMaterializations.push(materialization);
      if (layer) hybridOverlayLayers.push(layer);
    }
  }

  const renderable = getRenderableZonesForMode({
    zones: l10Zones || [],
    activeMode: activeMode as MapMode,
    activeZoneSurfaceType,
    detailMode,
    materialization: baseMaterialization,
    gridHeight: baseMaterialization.gridHeight ?? undefined,
    gridWidth: baseMaterialization.gridWidth ?? undefined,
  });
  
  // Map our unified category (diagnostic, action, trust) which exists in categorizedZoneFamily
  const categorizeLocal = (type: string) => {
      const t = type.toLowerCase();
      if (t.includes("uncertain") || t.includes("verify") || t.includes("trust")) return "trust";
      if (t.includes("action") || t.includes("improve") || t.includes("intervene")) return "action";
      return "diagnostic" as const;
  };

  const ranked = renderable
    .filter((z) => {
      let fam: "diagnostic" | "action" | "trust" | "agronomic" | "management" = "diagnostic";
      if (z.zone_family) {
        const f = z.zone_family.toUpperCase();
        fam = f === "TRUST" ? "trust" : f === "DECISION" ? "action" : f === "AGRONOMIC" ? "diagnostic" : f === "MANAGEMENT" ? "management" : "diagnostic";
      } else {
        fam = categorizeLocal(z.zone_type);
      }
      return policy.allowedZoneFamilies.includes(fam);
    })
    .filter((z) => z.area_fraction >= policy.minAreaFraction || z.zone_id === selectedZone)
    .sort((a, b) => {
      const aScore = (a.severity ?? 0) * (a.area_fraction ?? 0);
      const bScore = (b.severity ?? 0) * (b.area_fraction ?? 0);
      return bScore - aScore;
    });

  let visibleZones = ranked.slice(0, policy.maxZones);
  
  if (selectedZone && !visibleZones.some(z => z.zone_id === selectedZone)) {
      const selected = ranked.find(z => z.zone_id === selectedZone);
      if (selected) visibleZones.push(selected);
  }

  // Filter visibleZones by the buildMapLayerModel layer configuration to keep counts strictly in sync
  visibleZones = visibleZones.filter((z) => {
    if (isManagementZone(z)) {
      return showMgmtOverlay;
    } else {
      return showAlertOverlay;
    }
  });

  // Build base GeoJSON shared across zone layers (unified + glow)
  const featureCollection = visibleZones.length > 0 
    ? formatZoneGeoJson(
        visibleZones, 
        selectedZone,
        surfaceData?.values?.length || 8, 
        surfaceData?.values?.[0]?.length || 8, 
        plotGeoJson,
        hoveredZoneId,
        baseMaterialization.gridBounds,
        baseMaterialization,
      )
    : null;

  // Surface opacity — dim slightly when inspecting a zone, but keep visible
  const surfaceLayers = [
    // 0. The vector clip mask layer for the Semantic Surface
    plotGeoJson && showSemanticSurface ? new SolidPolygonLayer({
      id: "plot-clip-mask",
      data: [plotGeoJson],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      getPolygon: (d: any) => (d.geometry || d).coordinates,
      getFillColor: [255, 255, 255, 255],
      operation: "mask"
    }) : null,

    // 0b. V92.4-BC: Uniform Evidence Tint Layer (Level 4 plot-level evidence)
    // Renders INSTEAD of the semantic surface when no per-pixel raster exists.
    // Fills the plot polygon with a single color derived from the mode's estimate.
    ...((): any[] => {
      if (!modeAvailability || !plotGeoJson) return [];

      const activeIsSpatial =
        activeSurfaceType &&
        !shouldShowPlotLevel &&
        activeDisplay?.renderKind !== "uniform_tint";

      const activeIsAsmaeOrExperimental =
        activeSurfaceType?.startsWith("ASMAE_") ||
        activeSurfaceType?.startsWith("EXPERIMENTAL_") ||
        activeSurfaceType === "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL";

      if (activeIsSpatial || activeIsAsmaeOrExperimental) {
        return [];
      }

      const { displayLevel, renderKind, value } = modeAvailability;
      if (renderKind !== "uniform_tint") return [];
      return getUniformEvidenceTintLayer({
        id: "l10-uniform-evidence-tint",
        plotGeoJson,
        mode: activeMode || "canopy",
        normalizedValue: value,
        displayLevel: displayLevel || "unavailable",
        renderKind: renderKind || "none",
        visible: true,
        opacity: 0.28,
      }) || [];
    })(),

    // 1a. Semantic Surface Raster Layer (base layer)
    baseRasterLayer,

    // 1b. Experimental fine-detail layer (controlled by showExperimental1m)
    experimentalRasterLayer,

    // 1c. Experimental fine-detail candidate mask (controlled by showCandidateMask)
    (() => {
      const candidateAllowed = policyAllowsSurface("experimental", candidateMaskSurface?.semantic_type || candidateMaskSurface?.type || "EXPERIMENTAL_FINE_DETAIL_CANDIDATE", "candidate", renderAuthorizations, normalizedActiveMode);
      return showCandidateMask && experimentalMaterialization.status === "rendered" && candidateAllowed && candidateMaskSurface
        ? getSemanticSurfaceLayerLayer({
            id: "l10-surface-candidate-mask",
            plotId,
            surfaceData: candidateMaskSurface,
            surfaceColors: ["#a855f7", "#06b6d4", "#64748b"],
            plotGeoJson: plotGeoJson || undefined,
            opacity: 0.35,
            detailMode: policy.detailMode,
            quantizeBands: null,
            mode: normalizedActiveMode,
            paletteId: "experimental_fine_detail",
            renderMode: resolveOverlayRenderMode(candidateMaskSurface),
            zoom,
            gapFillSurface: gapFillMaskSurface,
            observedMaskSurface,
            renderKind: "proxy_overlay",
            displayLevel: "raster",
            renderAuthorizations: renderAuthorizations,
            policy: "experimental",
            role: "candidate",
          })
        : null;
    })(),

    // 1d. Independently authorized ASMAE hybrid overlays.
    ...hybridOverlayLayers,

    // 1c. V92.3-C: Analytical overlay semantic layers (water, nutrients, risk, salinity)
    // Each visible overlay gets its own DeckGL layer with unique ID and color ramp
    ...(() => {
      const overlayLayers: any[] = [];
      if (!overlayToggles || !overlayAvailability) return overlayLayers;

      const overlayEntries = layerModel.filter(l =>
        ["water_overlay", "nutrient_overlay", "risk_overlay", "salinity_overlay", "resolution_overlay",
         "water_uniform_tint", "nutrient_uniform_tint", "risk_uniform_tint", "salinity_uniform_tint",
         "confidence_uniform_tint", "veg_attention_uniform_tint"].includes(l.kind) &&
        l.visible
      );

      for (const entry of overlayEntries) {
        if (entry.kind.endsWith("_uniform_tint")) {
          // Render as additive uniform tint
          const activeIsSpatial =
            activeSurfaceType &&
            !shouldShowPlotLevel &&
            activeDisplay?.renderKind !== "uniform_tint";

          const activeIsAsmaeOrExperimental =
            activeSurfaceType?.startsWith("ASMAE_") ||
            activeSurfaceType?.startsWith("EXPERIMENTAL_") ||
            activeSurfaceType === "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL";

          if (activeIsSpatial || activeIsAsmaeOrExperimental) {
            continue;
          }
          const overlayKey = entry.kind.replace("_uniform_tint", "");
          const mode = overlayKey === "water" ? "water_stress" : overlayKey === "nutrients" ? "nutrient_risk" : overlayKey === "risk" ? "composite_risk" : overlayKey === "salinity" ? "salinity" : overlayKey === "confidence" ? "uncertainty" : overlayKey;
          const layersArray = getUniformEvidenceTintLayer({
            id: entry.id,
            plotGeoJson,
            mode,
            normalizedValue: entry.normalizedValue ?? 0.5,
            displayLevel: "plot_level",
            renderKind: "uniform_tint",
            visible: entry.visible,
            opacity: entry.opacity,
          });
          if (layersArray) {
            overlayLayers.push(...layersArray);
          }
          continue;
        }

        const surfType = entry.sourceSurfaceType;
        if (!surfType) continue;
        const overlayData = overlaySurfaces[surfType];
        if (!overlayData) continue;
        const colors = OVERLAY_COLOR_RAMPS[surfType] || ["#8B0000", "#FFD700", "#006400"];
        // V92.3-C.1: Map surface type to SemanticSurfaceLayer mode name
        const overlayMode = SURFACE_TYPE_TO_MODE[surfType] || "vegetation";
        // V92.3-C.1: Resolve per-overlay render mode from the overlay's own grounding class
        const overlayRenderMode = resolveOverlayRenderMode(overlayData);

        const overlayDL = entry.displayLevel || "raster";
        const overlayAuth = getOverlayAuthorization(overlayData, overlayMode);
        if (!overlayAuth.authorized || overlayAuth.renderKind === "none" || overlayAuth.renderKind === "card_only") continue;
        const overlayRK = overlayAuth.renderKind || entry.renderKind || "diagnostic_overlay";

        overlayLayers.push(
          getSemanticSurfaceLayerLayer({
            id: `semantic-overlay-${surfType}`,
            plotId,
            surfaceData: overlayData,
            surfaceColors: colors,
            plotGeoJson: plotGeoJson || undefined,
            confidenceSurface: undefined,
            opacity: entry.opacity,
            detailMode: policy.detailMode,
            quantizeBands: null,
            mode: overlayMode,
            paletteId: "standard",
            renderMode: overlayRenderMode,
            zoom,
            gapFillSurface: gapFillMaskSurface,
            observedMaskSurface,
            renderKind: overlayRK,
            displayLevel: overlayDL,
            renderAuthorizations: renderAuthorizations,
            policy: canopySource || "satellite",
            role: "overlay",
          })
        );
      }
      return overlayLayers;
    })(),
    
    // 2. Intelligence Topography (Contours)
    (surfaceData?.type === "NDVI_CLEAN" || surfaceData?.type === "NUTRIENT_STRESS_PROB") &&
    baseMaterialization.status === "rendered" &&
    showSemanticSurface &&
    policyAllowsSurface(canopySource || "satellite", surfaceData?.semantic_type || surfaceData?.type || "", "base", renderAuthorizations, activeMode)
      ? getContourSurfaceLayer({
          id: "l10-surface-contours",
          plotId,
          surfaceData: surfaceData,
          plotGeoJson: plotGeoJson || undefined,
          gridBounds: baseMaterialization.gridBounds,
          visible: policy.showContours
        }) 
      : null,
      
    // 3. Secondary Evidence (Uncertainty Grid)
    showConfidenceMask &&
    baseMaterialization.status === "rendered" &&
    policyAllowsSurface(canopySource || "satellite", confidenceSurface?.semantic_type || confidenceSurface?.type || "COMPOSITE_CONFIDENCE", "overlay", renderAuthorizations, activeMode)
      ? getUncertaintyGridLayer({
          id: "l10-uncertainty-markers",
          plotId,
          confidenceSurface: confidenceSurface || undefined,
          plotGeoJson: plotGeoJson || undefined,
          visible: policy.showUncertaintyGlyphs
        })
      : null,
  ].filter(Boolean);

  // ── Zone Rendering: Per-cell polygons with hover-reveal ────────────────────
  // Each zone's cells are individual geographic rectangles.
  // ALL cells are pickable for hover detection — no overlapping bounding boxes.
  // Hovered/selected zones get bright white fill + edge (white survives multiply blend).

  type ZoneCellDatum = {
    polygon: [number, number][];
    zoneId: string;
    severity: number;
    confidence: number;
  };

  const allZoneCells: ZoneCellDatum[] = [];
  let gridReady = false;
  let gMinLng = 0, gMaxLng = 0, gMaxLat = 0;
  let gLatStep = 0, gLngStep = 0;

  const firstSpatialSurface = surfaceData || Object.values(overlaySurfaces || {}).find(s => s && s.values && s.values.length > 0);

  if (
    visibleZones.length > 0
    && firstSpatialSurface?.values
    && plotGeoJson
    && baseMaterialization.status === "rendered"
    && baseMaterialization.gridBounds
  ) {
    const geom = ((plotGeoJson as any).geometry || plotGeoJson) as any;
    const coords = geom?.type === 'MultiPolygon'
      ? geom.coordinates[0][0]
      : geom?.coordinates?.[0];

    if (coords && coords.length >= 3) {
      let minLng = baseMaterialization.gridBounds[0];
      const minLat = baseMaterialization.gridBounds[1];
      let maxLng = baseMaterialization.gridBounds[2];
      const maxLat = baseMaterialization.gridBounds[3];
      const crossesAntiMeridian = (maxLng - minLng) > 180;
      if (crossesAntiMeridian && minLng < 0) minLng += 360;
      if (crossesAntiMeridian && maxLng < 0) maxLng += 360;
      const gridH = baseMaterialization.gridHeight || 0;
      const gridW = baseMaterialization.gridWidth || 0;
      if (gridH <= 0 || gridW <= 0) return {
        surfaceLayers: [],
        zoneLayers: [],
        materialization: baseMaterialization,
        experimentalMaterialization,
        hybridOverlayMaterializations,
      };
      gMinLng = minLng; gMaxLng = maxLng; gMaxLat = maxLat;
      gLatStep = (maxLat - minLat) / gridH;
      gLngStep = (maxLng - minLng) / gridW;
      gridReady = true;

      // Build polygon mask to filter out cells outside field boundary
      const mask = buildPolygonMask(plotId, gridW, gridH, plotGeoJson, baseMaterialization.gridBounds);

      // Count total in-polygon cells for accurate percentage calculation.
      // Fail-closed: if the polygon boundary mask is unavailable, do NOT assume the full bounding box is inside.
      let totalInPolygonCells = 0;
      if (mask) {
        for (let i = 0; i < mask.data.length; i++) {
          if (mask.data[i] === 1) totalInPolygonCells++;
        }
      } else {
        console.warn(`[buildLayerStack] Polygon boundary mask unavailable for plot ${plotId}; rejecting fail-open zone calculation.`);
        totalInPolygonCells = 0;
      }

      // Track per-zone in-polygon cell counts
      const zoneCellCounts: Record<string, number> = {};

      for (const zone of visibleZones) {
        if (!zone.cell_indices || zone.cell_indices.length === 0) continue;
        let zoneInPolygonCount = 0;
        for (const cell of zone.cell_indices) {
          const r = cell[0], c = cell[1];
          if (!Number.isInteger(r) || !Number.isInteger(c) || r < 0 || r >= gridH || c < 0 || c >= gridW) {
            continue;
          }
          // Strictly require cells to be inside the field polygon mask (fail closed if mask is null)
          if (!mask || mask.data[r * gridW + c] === 0) continue;
          zoneInPolygonCount++;
          let lng0 = gMinLng + c * gLngStep;
          let lng1 = gMinLng + (c + 1) * gLngStep;
          if (crossesAntiMeridian) {
            if (lng0 > 180) lng0 -= 360;
            if (lng1 > 180) lng1 -= 360;
          }
          const lat0 = gMaxLat - (r + 1) * gLatStep;
          const lat1 = gMaxLat - r * gLatStep;
          allZoneCells.push({
            polygon: [[lng0, lat0], [lng1, lat0], [lng1, lat1], [lng0, lat1], [lng0, lat0]],
            zoneId: zone.zone_id,
            severity: zone.severity,
            confidence: zone.confidence,
          });
        }
        zoneCellCounts[zone.zone_id] = zoneInPolygonCount;
      }

      // Recompute area_fraction for each zone based on in-polygon cells
      const computedAreaFractions: Record<string, number> = {};
      if (totalInPolygonCells > 0) {
        for (const zone of visibleZones) {
          const inPolygonCount = zoneCellCounts[zone.zone_id] || 0;
          computedAreaFractions[zone.zone_id] = inPolygonCount / totalInPolygonCells;
        }
      }
      visibleZones = visibleZones.map((zone) => ({
        ...zone,
        area_fraction: computedAreaFractions[zone.zone_id] ?? zone.area_fraction,
      }));
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const zoneLayers: any[] = [];

  if (featureCollection) {
    const unifiedLayer = getUnifiedZoneLayer({
      id: "l10-zones-unified",
      featureCollection,
      visible: true,
      detailMode,
      isInspecting,
      onHover: (info) => {
        if (onZoneHover) {
          onZoneHover(info.object?.properties?.zoneId ?? null);
        }
      },
      onClick: (info) => {
        if (info.object && onZoneClick) {
          onZoneClick(info.object.properties.zoneId);
        }
      },
    });
    if (unifiedLayer) zoneLayers.push(unifiedLayer);

    const glowLayers = getZoneGlowLayers({
      id: "l10-zones-glow",
      featureCollection,
      visible: true,
    });
    glowLayers.forEach(lay => {
      if (lay) zoneLayers.push(lay);
    });
  }

  if (allZoneCells.length > 0) {
    // Layer 1: Invisible picking layer — cells are invisible but register hover/click
    zoneLayers.push(
      new SolidPolygonLayer({
        id: "l10-zone-pick",
        data: allZoneCells,
        getPolygon: (d: ZoneCellDatum) => d.polygon,
        getFillColor: [255, 255, 255, 0] as [number, number, number, number],
        pickable: true,
        filled: true,
        extruded: false,
        onHover: (info: { object?: ZoneCellDatum }) => {
          if (onZoneHover) {
            onZoneHover(info.object?.zoneId ?? null);
          }
        },
        onClick: (info: { object?: ZoneCellDatum }) => {
          if (info.object && onZoneClick) {
            onZoneClick(info.object.zoneId);
          }
        },
      })
    );

    // Layer 2: Smooth zone boundary for hovered/selected zones
    const activeZoneId = selectedZone || hoveredZoneId;
    if (activeZoneId && gridReady) {
      // Build a lookup set of cells in the active zone
      const activeCells = new Set<string>();
      for (const cell of allZoneCells) {
        if (cell.zoneId === activeZoneId) {
          let lng0 = cell.polygon[0][0];
          if ((gMaxLng - gMinLng) > 180 && lng0 < 0) lng0 += 360;
          const lat1 = cell.polygon[0][1];
          const c = Math.round((lng0 - gMinLng) / gLngStep);
          const r = Math.round((gMaxLat - lat1) / gLatStep) - 1;
          activeCells.add(`${r},${c}`);
        }
      }

      // Build adjacency graph of boundary vertices
      const toVK = (lng: number, lat: number) =>
        `${Math.round(lng * 1e8)},${Math.round(lat * 1e8)}`;
      const fromVK = (k: string): [number, number] => {
        const [a, b] = k.split(",").map(Number);
        return [a / 1e8, b / 1e8];
      };
      const adj = new Map<string, Set<string>>();
      const addE = (a: [number, number], b: [number, number]) => {
        const kA = toVK(a[0], a[1]), kB = toVK(b[0], b[1]);
        if (!adj.has(kA)) adj.set(kA, new Set());
        if (!adj.has(kB)) adj.set(kB, new Set());
        adj.get(kA)!.add(kB);
        adj.get(kB)!.add(kA);
      };

      for (const key of activeCells) {
        const [r, c] = key.split(",").map(Number);
        const lng0 = gMinLng + c * gLngStep;
        const lng1 = gMinLng + (c + 1) * gLngStep;
        const lat0 = gMaxLat - (r + 1) * gLatStep;
        const lat1 = gMaxLat - r * gLatStep;
        if (!activeCells.has(`${r - 1},${c}`)) addE([lng0, lat1], [lng1, lat1]);
        if (!activeCells.has(`${r + 1},${c}`)) addE([lng0, lat0], [lng1, lat0]);
        if (!activeCells.has(`${r},${c - 1}`)) addE([lng0, lat0], [lng0, lat1]);
        if (!activeCells.has(`${r},${c + 1}`)) addE([lng1, lat0], [lng1, lat1]);
      }

      // Chain edges into closed rings
      const rings: [number, number][][] = [];
      while (true) {
        let startKey: string | null = null;
        for (const [key, neighbors] of adj) {
          if (neighbors.size > 0) { startKey = key; break; }
        }
        if (!startKey) break;
        const ring: [number, number][] = [fromVK(startKey)];
        let cur = startKey;
        while (true) {
          const nb = adj.get(cur);
          if (!nb || nb.size === 0) break;
          const nxt = nb.values().next().value;
          if (!nxt) break;
          nb.delete(nxt);
          adj.get(nxt)?.delete(cur);
          if (nxt === startKey) { ring.push(fromVK(startKey)); break; }
          ring.push(fromVK(nxt));
          cur = nxt;
        }
        if (ring.length >= 4) rings.push(ring);
      }

      // Only materialize exact masked-cell boundaries. Smoothing can change
      // topology and produce a self-intersecting ring that DeckGL triangulates
      // into a field-spanning wedge.
      const validated = rings
        .map(validateZoneRing)
        .filter((value): value is { ring: ZoneRing; area: number } => value !== null);
      const expectedArea = activeCells.size * Math.abs(gLatStep * gLngStep);
      const materializedArea = validated.reduce((sum, value) => sum + value.area, 0);
      const areaRatio = expectedArea > 0 ? materializedArea / expectedArea : 0;
      const areaConserved = areaRatio >= 0.65 && areaRatio <= 1.35;
      const boundaryRings = areaConserved ? validated.map(value => value.ring) : [];
      const isSel = activeZoneId === selectedZone;

      if (boundaryRings.length > 0) {
        // Outline-only rendering keeps the evidence raster visible and avoids
        // polygon triangulation entirely.
        zoneLayers.push(
          new PathLayer({
            id: `l10-zone-boundary-${zoneLayerIdPart(activeZoneId)}`,
            data: boundaryRings,
            getPath: (ring: [number, number][]) => ring,
            getColor: isSel ? [34, 211, 238, 245] : [125, 211, 252, 190],
            getWidth: isSel ? 3 : 2,
            widthUnits: "pixels" as const,
            widthMinPixels: isSel ? 2 : 1,
            pickable: false,
          })
        );
      } else if (rings.length > 0) {
        console.warn("[ZoneMaterialization] zone_materialization_failed", {
          zoneId: activeZoneId,
          rawRingCount: rings.length,
          validatedRingCount: validated.length,
          expectedArea,
          materializedArea,
          areaRatio,
        });
      }
    }
  }

  if (transectPoints && transectPoints.length >= 2) {
    zoneLayers.push(
      new PathLayer({
        id: "l10-transect-glow",
        data: [{ path: transectPoints }],
        getPath: (d: any) => d.path,
        getColor: [234, 179, 8, 100] as [number, number, number, number],
        getWidth: 6,
        widthUnits: "pixels" as const,
        widthMinPixels: 4,
        pickable: false,
      })
    );

    zoneLayers.push(
      new PathLayer({
        id: "l10-transect-core",
        data: [{ path: transectPoints }],
        getPath: (d: any) => d.path,
        getColor: [254, 240, 138, 255] as [number, number, number, number],
        getWidth: 2,
        widthUnits: "pixels" as const,
        widthMinPixels: 1.5,
        pickable: false,
      })
    );

    zoneLayers.push(
      new ScatterplotLayer({
        id: "l10-transect-endpoints",
        data: [
          { coordinates: transectPoints[0], type: "A", color: [234, 179, 8] },
          { coordinates: transectPoints[1], type: "B", color: [239, 68, 68] },
        ],
        getPosition: (d: any) => d.coordinates,
        getFillColor: (d: any) => [...d.color, 255] as [number, number, number, number],
        getLineColor: [255, 255, 255, 255] as [number, number, number, number],
        lineWidthMinPixels: 1.5,
        radiusMinPixels: 5,
        radiusMaxPixels: 12,
        radiusScale: 1,
        radiusUnits: "pixels" as const,
        pickable: false,
        stroked: true,
        filled: true,
      })
    );
  }

  if (hoveredSampleCoordinate) {
    zoneLayers.push(
      new ScatterplotLayer({
        id: "l10-transect-hover-ping",
        data: [{ coordinates: hoveredSampleCoordinate }],
        getPosition: (d: any) => d.coordinates,
        getFillColor: [234, 179, 8, 80] as [number, number, number, number],
        getLineColor: [255, 255, 255, 255] as [number, number, number, number],
        lineWidthMinPixels: 2,
        radiusMinPixels: 8,
        radiusMaxPixels: 20,
        radiusScale: 1,
        radiusUnits: "pixels" as const,
        stroked: true,
        filled: true,
        pickable: false,
      })
    );
  }

  return {
    surfaceLayers,
    zoneLayers,
    materialization: baseMaterialization,
    experimentalMaterialization,
    hybridOverlayMaterializations,
  };
}
