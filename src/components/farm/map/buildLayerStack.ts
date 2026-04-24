import { SurfaceData, ZoneData, MapMode, MODE_ZONE_SURFACE_MAP } from "@/hooks/useLayer10";
import { getSemanticSurfaceLayerLayer } from "./layers/SemanticSurfaceLayer";
import { getContourSurfaceLayer } from "./layers/ContourSurfaceLayer";
import { getUncertaintyGridLayer } from "./layers/UncertaintyGridLayer";
import { formatZoneGeoJson } from "./layers/zones/zoneUtils";
import { getUnifiedZoneLayer } from "./layers/zones/UnifiedZoneLayer";
import { getZoneGlowLayers } from "./layers/zones/ZoneGlowLayer";

type ViewerMode = "farmer" | "expert";

type RenderPolicy = {
  showContours: boolean;
  showUncertaintyGlyphs: boolean;
  showTrustLayer: boolean;
  maxZones: number;
  minAreaFraction: number;
  allowedZoneFamilies: Array<"diagnostic" | "action" | "trust">;
  quantizeBands: number | null;
  detailMode: "farmer" | "expert";
};

const RENDER_POLICIES: Record<string, Record<ViewerMode, RenderPolicy>> = {
  // Canopy: beauty-only observation lens. No zones rendered.
  vegetation: {  // Compatibility alias → canopy
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 0,
      minAreaFraction: 1,
      allowedZoneFamilies: [],
      quantizeBands: 5,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 0,
      minAreaFraction: 1,
      allowedZoneFamilies: [],
      quantizeBands: null,
      detailMode: "expert",
    },
  },
  canopy: {
    farmer: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 0,
      minAreaFraction: 1,
      allowedZoneFamilies: [],
      quantizeBands: 5,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 0,
      minAreaFraction: 1,
      allowedZoneFamilies: [],
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
      minAreaFraction: 0.01,
      allowedZoneFamilies: ["diagnostic"],
      quantizeBands: 5,
      detailMode: "farmer",
    },
    expert: {
      showContours: true,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.005,
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
      minAreaFraction: 0.01,
      allowedZoneFamilies: ["diagnostic", "action"],
      quantizeBands: 5,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.005,
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
      minAreaFraction: 0.01,
      allowedZoneFamilies: ["diagnostic"],
      quantizeBands: 5,
      detailMode: "farmer",
    },
    expert: {
      showContours: true,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.005,
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
      minAreaFraction: 0.01,
      allowedZoneFamilies: ["diagnostic", "action"],
      quantizeBands: 5,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.005,
      allowedZoneFamilies: ["diagnostic", "action", "trust"],
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
      minAreaFraction: 0.01,
      allowedZoneFamilies: ["trust"],
      quantizeBands: null,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: true,
      showTrustLayer: true,
      maxZones: 30,
      minAreaFraction: 0.005,
      allowedZoneFamilies: ["trust"],
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
  onZoneClick?: (zoneId: string) => void;
  onZoneHover?: (zoneId: string | null) => void;
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
    onZoneClick,
    onZoneHover,
  } = options;

  const defaultColors: [string, string, string] = ["#8B0000", "#FFD700", "#006400"];
  
  // Resolve Render Policy
  const safeMode = activeMode && RENDER_POLICIES[activeMode] ? activeMode : "vegetation";
  const policy = RENDER_POLICIES[safeMode][detailMode];

  // Is any zone currently selected? (for inspection-mode dimming)
  const isInspecting = !!selectedZone;

  // 0. Zone Rendering Policy (Phase 2H) 
  // Drop visual clutter by filtering zones specifically against the mode policy
  let visibleZones = l10Zones || [];
  
  // Map our unified category (diagnostic, action, trust) which exists in categorizedZoneFamily
  const categorizeLocal = (type: string) => {
      const t = type.toLowerCase();
      if (t.includes("uncertain") || t.includes("verify") || t.includes("trust")) return "trust";
      if (t.includes("action") || t.includes("improve") || t.includes("intervene")) return "action";
      return "diagnostic";
  };

  const ranked = visibleZones
    .filter((z) => {
      let fam: "diagnostic" | "action" | "trust" = "diagnostic";
      if (z.zone_family) {
        const f = z.zone_family.toUpperCase();
        fam = f === "TRUST" ? "trust" : f === "DECISION" ? "action" : "diagnostic";
      } else {
        fam = categorizeLocal(z.zone_type);
      }
      return policy.allowedZoneFamilies.includes(fam);
    })
    .filter((z) => z.source_surface_type === MODE_ZONE_SURFACE_MAP[activeMode as MapMode])
    .filter((z) => z.area_fraction >= policy.minAreaFraction || z.zone_id === selectedZone)
    .sort((a, b) => {
      const aScore = (a.severity ?? 0) * (a.area_fraction ?? 0);
      const bScore = (b.severity ?? 0) * (b.area_fraction ?? 0);
      return bScore - aScore;
    });

  visibleZones = ranked.slice(0, policy.maxZones);
  
  if (selectedZone && !visibleZones.some(z => z.zone_id === selectedZone)) {
      const selected = ranked.find(z => z.zone_id === selectedZone);
      if (selected) visibleZones.push(selected);
  }

  // Build base GeoJSON shared across zone layers (unified + glow)
  const featureCollection = visibleZones.length > 0 
    ? formatZoneGeoJson(
        visibleZones, 
        selectedZone,
        surfaceData?.values?.length || 8, 
        surfaceData?.values?.[0]?.length || 8, 
        plotGeoJson,
        hoveredZoneId,
      )
    : null;

  // Surface opacity — V2.3: Higher observe-mode opacity so zones are visible at a glance
  const surfaceOpacity = isInspecting ? 0.08 : 0.65;

  return [
    // 1. Base Intelligence Surface (Raster mapped to bounds)
    getSemanticSurfaceLayerLayer({
      id: "l10-surface-base",
      plotId,
      surfaceData: surfaceData,
      surfaceColors: surfaceColors || defaultColors,
      plotGeoJson: plotGeoJson || undefined,
      confidenceSurface: confidenceSurface || undefined,
      opacity: surfaceOpacity,
      detailMode: policy.detailMode,
      quantizeBands: policy.quantizeBands,
      mode: activeMode,
      reliabilitySurface: reliabilitySurface || undefined,
      deviationSurface: deviationSurface || undefined,
    }),
    
    // 2. Intelligence Topography (Contours)
    surfaceData?.type === "NDVI_CLEAN" || surfaceData?.type === "NUTRIENT_STRESS_PROB" 
      ? getContourSurfaceLayer({
          id: "l10-surface-contours",
          plotId,
          surfaceData: surfaceData,
          plotGeoJson: plotGeoJson || undefined,
          visible: policy.showContours
        }) 
      : null,
      
    // 3. Secondary Evidence (Uncertainty Grid)
    activeMode === 'uncertainty' || activeMode === 'inspection'
      ? getUncertaintyGridLayer({
          id: "l10-uncertainty-markers",
          plotId,
          confidenceSurface: confidenceSurface || undefined,
          plotGeoJson: plotGeoJson || undefined,
          visible: policy.showUncertaintyGlyphs
        })
      : null,
    
    // 4. Zone Glow Layers (dual-layer halo: outer + inner, renders UNDER main zones)
    ...getZoneGlowLayers({
      id: "l10-zone-glow",
      featureCollection,
      visible: true,
    }),

    // 5. Unified Zone Layer (replaces 3 separate family layers)
    getUnifiedZoneLayer({
      id: "l10-zones",
      featureCollection,
      visible: true,
      detailMode: policy.detailMode,
      isInspecting,
      onHover: (info: { object?: { properties: { zoneId: string } } }) => {
        if (onZoneHover) {
          onZoneHover(info.object?.properties?.zoneId ?? null);
        }
      },
      onClick: (info: { object?: { properties: { zoneId: string } } }) => {
        if (info.object && onZoneClick) {
          onZoneClick(info.object.properties.zoneId);
        }
      },
    }),
  ].filter(Boolean);
}
