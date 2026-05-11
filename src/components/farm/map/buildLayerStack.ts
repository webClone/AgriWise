import { SurfaceData, ZoneData, MapMode, MODE_ZONE_SURFACE_MAP } from "@/hooks/useLayer10";
import { getSemanticSurfaceLayerLayer } from "./layers/SemanticSurfaceLayer";
import { getContourSurfaceLayer } from "./layers/ContourSurfaceLayer";
import { getUncertaintyGridLayer } from "./layers/UncertaintyGridLayer";
import { formatZoneGeoJson } from "./layers/zones/zoneUtils";
import { getUnifiedZoneLayer } from "./layers/zones/UnifiedZoneLayer";
import { getZoneGlowLayers } from "./layers/zones/ZoneGlowLayer";
import { SolidPolygonLayer, PathLayer } from "@deck.gl/layers";
import { buildPolygonMask } from "./utils/buildPolygonMask";

type ViewerMode = "farmer" | "expert";

type RenderPolicy = {
  showContours: boolean;
  showUncertaintyGlyphs: boolean;
  showTrustLayer: boolean;
  maxZones: number;
  minAreaFraction: number;
  allowedZoneFamilies: Array<"diagnostic" | "action" | "trust" | "agronomic">;
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
      minAreaFraction: 0.01,
      allowedZoneFamilies: ["agronomic"],
      quantizeBands: 5,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 10,
      minAreaFraction: 0.005,
      allowedZoneFamilies: ["agronomic", "diagnostic"],
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
      minAreaFraction: 0.01,
      allowedZoneFamilies: ["agronomic"],
      quantizeBands: 5,
      detailMode: "farmer",
    },
    expert: {
      showContours: false,
      showUncertaintyGlyphs: false,
      showTrustLayer: false,
      maxZones: 10,
      minAreaFraction: 0.005,
      allowedZoneFamilies: ["agronomic", "diagnostic"],
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
      return "diagnostic" as const;
  };

  const ranked = visibleZones
    .filter((z) => {
      let fam: "diagnostic" | "action" | "trust" | "agronomic" = "diagnostic";
      if (z.zone_family) {
        const f = z.zone_family.toUpperCase();
        fam = f === "TRUST" ? "trust" : f === "DECISION" ? "action" : f === "AGRONOMIC" ? "agronomic" : "diagnostic";
      } else {
        fam = categorizeLocal(z.zone_type);
      }
      return policy.allowedZoneFamilies.includes(fam);
    })
    .filter((z) => {
      // Management zones (MZ_ prefix) are mode-agnostic — always pass through
      if (z.zone_id?.startsWith("MZ_")) return true;
      // Alert zones must match the active mode's zone surface type
      const modeZoneSurface = MODE_ZONE_SURFACE_MAP[activeMode as MapMode];
      return z.source_surface_type === modeZoneSurface;
    })
    .filter((z) => z.zone_id?.startsWith("MZ_") || z.area_fraction >= policy.minAreaFraction || z.zone_id === selectedZone)
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



  // Surface opacity — dim slightly when inspecting a zone, but keep visible
  const surfaceOpacity = isInspecting ? 0.75 : 1.0;

  const surfaceLayers = [
    // 0. The vector clip mask layer for the Semantic Surface
    plotGeoJson ? new SolidPolygonLayer({
      id: "plot-clip-mask",
      data: [plotGeoJson],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      getPolygon: (d: any) => d.geometry.coordinates,
      getFillColor: [255, 255, 255, 255],
      operation: "mask"
    }) : null,

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

  if (visibleZones.length > 0 && surfaceData?.values && plotGeoJson) {
    const coords = plotGeoJson.geometry?.type === 'MultiPolygon'
      ? plotGeoJson.geometry.coordinates[0][0]
      : plotGeoJson.geometry?.coordinates?.[0];

    if (coords && coords.length >= 3) {
      let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
      for (const c of coords) {
        if (c[0] < minLng) minLng = c[0];
        if (c[0] > maxLng) maxLng = c[0];
        if (c[1] < minLat) minLat = c[1];
        if (c[1] > maxLat) maxLat = c[1];
      }
      const gridH = surfaceData.values.length;
      const gridW = surfaceData.values[0]?.length || 1;
      gMinLng = minLng; gMaxLng = maxLng; gMaxLat = maxLat;
      gLatStep = (maxLat - minLat) / gridH;
      gLngStep = (maxLng - minLng) / gridW;
      gridReady = true;

      // Build polygon mask to filter out cells outside field boundary
      const mask = buildPolygonMask(plotId, gridW, gridH, plotGeoJson);

      // Count total in-polygon cells for accurate percentage calculation
      let totalInPolygonCells = 0;
      if (mask) {
        for (let i = 0; i < mask.data.length; i++) {
          if (mask.data[i] === 1) totalInPolygonCells++;
        }
      } else {
        totalInPolygonCells = gridW * gridH;
      }

      // Track per-zone in-polygon cell counts
      const zoneCellCounts: Record<string, number> = {};

      for (const zone of visibleZones) {
        if (!zone.cell_indices || zone.cell_indices.length === 0) continue;
        let zoneInPolygonCount = 0;
        for (const cell of zone.cell_indices) {
          const r = cell[0], c = cell[1];
          // Skip cells outside the field polygon
          if (mask && r >= 0 && r < gridH && c >= 0 && c < gridW) {
            if (mask.data[r * gridW + c] === 0) continue;
          }
          zoneInPolygonCount++;
          const lng0 = gMinLng + c * gLngStep;
          const lng1 = gMinLng + (c + 1) * gLngStep;
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
      if (totalInPolygonCells > 0) {
        for (const zone of visibleZones) {
          const inPolygonCount = zoneCellCounts[zone.zone_id] || 0;
          zone.area_fraction = inPolygonCount / totalInPolygonCells;
        }
      }
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const zoneLayers: any[] = [];

  if (allZoneCells.length > 0) {
    // Layer 1: Invisible picking layer — cells are invisible but register hover/click
    zoneLayers.push(
      new SolidPolygonLayer({
        id: "l10-zone-pick",
        data: allZoneCells,
        getPolygon: (d: ZoneCellDatum) => d.polygon,
        getFillColor: [255, 255, 255, 30] as [number, number, number, number],
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
          const lng0 = cell.polygon[0][0];
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

      // Chaikin corner-cutting smoothing (3 iterations)
      const chaikin = (pts: [number, number][], iters: number): [number, number][] => {
        let p = pts;
        for (let it = 0; it < iters; it++) {
          const s: [number, number][] = [];
          const closed = p.length > 1 &&
            Math.abs(p[0][0] - p[p.length - 1][0]) < 1e-10 &&
            Math.abs(p[0][1] - p[p.length - 1][1]) < 1e-10;
          const n = closed ? p.length - 1 : p.length - 1;
          for (let i = 0; i < n; i++) {
            const a = p[i], b = p[(i + 1) % p.length];
            s.push([0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]]);
            s.push([0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]]);
          }
          if (closed && s.length > 0) s.push([s[0][0], s[0][1]]);
          p = s;
        }
        return p;
      };

      const smoothed = rings.map(r => chaikin(r, 3));
      const isSel = activeZoneId === selectedZone;

      if (smoothed.length > 0) {
        // Smooth filled polygon
        zoneLayers.push(
          new SolidPolygonLayer({
            id: "l10-zone-fill",
            data: smoothed,
            getPolygon: (ring: [number, number][]) => ring,
            getFillColor: isSel
              ? [0, 0, 0, 55] as [number, number, number, number]
              : [0, 0, 0, 30] as [number, number, number, number],
            pickable: false, filled: true, extruded: false,
          })
        );
        // Smooth boundary outline
        zoneLayers.push(
          new PathLayer({
            id: "l10-zone-boundary",
            data: smoothed,
            getPath: (ring: [number, number][]) => ring,
            getColor: isSel ? [255, 255, 255, 230] : [255, 255, 255, 170],
            getWidth: isSel ? 3 : 2,
            widthUnits: "pixels" as const,
            widthMinPixels: isSel ? 2 : 1,
            pickable: false,
          })
        );
      }
    }
  }

  return { surfaceLayers, zoneLayers };
}
