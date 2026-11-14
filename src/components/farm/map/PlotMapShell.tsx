"use client";

import { useMemo, useState, useRef, useEffect, useCallback } from "react";
import Map, { Source, Layer } from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";
import "maplibre-gl/dist/maplibre-gl.css";
import { SurfaceData, ZoneData, useLayer10, type MapMode } from "@/hooks/useLayer10";
import { usePlotFit } from "./usePlotFit";
import { SCENE_PROVIDERS, SceneProfile, getDynamicStyle } from "./sceneProviders";
import { buildLayerStack } from "./buildLayerStack";
import { resolveSurfaceBounds } from "./layers/SemanticSurfaceLayer";
import ZoneChip from "./layers/zones/ZoneChip";
import { formatZoneGeoJson, computeZoneCentroid, DeckZoneFeature } from "./layers/zones/zoneUtils";
import NdviDebugOverlay from "./layers/NdviDebugOverlay";
import PlotScientificLegend from "./PlotScientificLegend";
import { hasRenderedExperimentalOverlay, isAsmaeSurfaceType, isCompositeAdvisorySurface, isExperimentalSurfaceType } from "@/lib/agribrain/source-policy-display-resolver";
import {
  resolveCropStageLabels,
  resolvePixelInspectorTitle,
} from "@/lib/agribrain/pixel-inspector-authority.mjs";
import {
  createCommittedRenderReceipt,
  isRenderedMaterialization,
} from "@/lib/agribrain/render-materialization";
import { getWorkspaceEntityPinsLayers } from "./layers/WorkspaceEntityPinsLayer";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";

function hasStaleGatewayEvidence(rawData: Record<string, unknown> | undefined): boolean {
  for (const value of Object.values(rawData || {})) {
    if (!value || typeof value !== "object") continue;
    const state = (value as Record<string, unknown>).gateway_evidence_state;
    if (
      state &&
      typeof state === "object" &&
      (state as Record<string, unknown>).status === "stale_available"
    ) return true;
  }
  return false;
}

interface PlotMapShellProps {
  farms: Record<string, unknown>[];
  plots: Record<string, unknown>[];
  activeMode?: string;
  cropName?: string;
  surfaceData?: SurfaceData | null;
  surfaceColors?: [string, string, string] | null;
  confidenceSurface?: SurfaceData | null;
  reliabilitySurface?: SurfaceData | null;
  deviationSurface?: SurfaceData | null;
  gridHeight?: number;
  gridWidth?: number;
  l10Zones?: ZoneData[] | null;
  selectedZone?: string | null;
  detailMode?: "farmer" | "expert";
  onZoneClick?: (zoneId: string) => void;
  visualSource?: any; // V61D
  showExperimental1m?: boolean;
  showCandidateMask?: boolean;
  experimental1mSurface?: SurfaceData | null;
  candidateMaskSurface?: SurfaceData | null;
  paletteId?: "standard" | "thermal" | "chlorophyll" | "chroma";
  onPaletteChange?: (palette: "standard" | "thermal" | "chlorophyll" | "chroma") => void;
  workspaceEntities?: WorkspaceFeatureEnvelope[];
  selectedEntityId?: string | null;
  onEntityClick?: (entity: WorkspaceFeatureEnvelope) => void;
}

export default function PlotMapShell(props: PlotMapShellProps) {
  const {
    plots,
    activeMode,
    cropName,
    surfaceData,
    surfaceColors,
    confidenceSurface,
    reliabilitySurface,
    deviationSurface,
    l10Zones,
    selectedZone,
    detailMode = "farmer",
    onZoneClick,
    visualSource,
    showExperimental1m = false,
    showCandidateMask = false,
    experimental1mSurface = null,
    candidateMaskSurface = null,
    paletteId = "standard",
    onPaletteChange,
    workspaceEntities = [],
    selectedEntityId = null,
    onEntityClick,
  } = props;

  const primaryPlot = plots?.[0];
  const containerRef = useRef<HTMLDivElement>(null);

  const l10 = useLayer10();
  const { commitBrowserRenderReceipt, clearBrowserRenderReceipt } = l10;
  const resolvedSurfaceType = String(l10.activeSurfaceType || surfaceData?.semantic_type || surfaceData?.type || "").toUpperCase();
  const resolvedIsAsmae = isAsmaeSurfaceType(resolvedSurfaceType);
  const resolvedIsComposite = isCompositeAdvisorySurface(resolvedSurfaceType);
  const resolvedIsExperimental = isExperimentalSurfaceType(resolvedSurfaceType);
  const isLowConfidence = l10.data?.quality?.degradation_mode === "DEGRADED" || 
                          (l10.data?.quality?.reliability_score !== undefined && l10.data.quality.reliability_score < 0.40);
  const canShowPixelDiagnosis = l10.canShowPixelDiagnosis ?? false;
  const canShowPixelHint = l10.canShowPixelHint ?? false;
  const canSamplePixel = l10.canSamplePixel ?? canShowPixelHint;
  const canInterpretForScouting = l10.canInterpretForScouting ?? canSamplePixel;
  const canInterpretDiagnostically = l10.canInterpretDiagnostically ?? canShowPixelDiagnosis;
  const inspectorDiagnosisAllowed = canInterpretDiagnostically || (resolvedIsAsmae && canSamplePixel);

  // 1. Derive scene profile from map state (no stateful toggling)
  const sceneProfile: SceneProfile = useMemo(() => {
    if (!surfaceData || !activeMode) return "agro";  // No analysis active → full satellite
    return "analysis";  // Analysis layer active → dim basemap
  }, [surfaceData, activeMode]);

  // Premium Custom Spatial Map States
  const [transectMode, setTransectMode] = useState(false);
  const [transectPoints, setTransectPoints] = useState<[number, number][]>([]);
  const [hoverCoord, setHoverCoord] = useState<{ lng: number; lat: number } | null>(null);
  const [hoveredSampleIndex, setHoveredSampleIndex] = useState<number | null>(null);
  const [showProxyBanner, setShowProxyBanner] = useState(false);
  // Track last hovered grid cell to avoid re-renders on sub-cell mouse movement
  const lastHoverCellRef = useRef<string | null>(null);

  useEffect(() => {
    if (canInterpretDiagnostically) {
      setShowProxyBanner(false);
    }
  }, [canInterpretDiagnostically]);

  // 2. Hover state for zone interactions
  const [hoveredZoneId, setHoveredZoneId] = useState<string | null>(null);

  // V65: Visual Tile Fallback status tracking & polling
  const [fallbackActive, setFallbackActive] = useState(false);

  useEffect(() => {
    if (!visualSource || !visualSource.scene_id) {
      setFallbackActive(false);
      return;
    }

    const sceneId = visualSource.scene_id;

    // Reset fallback status on scene change
    const resetStatus = async () => {
      try {
        await fetch(`/api/agribrain/visual-tile/status?scene_id=${encodeURIComponent(sceneId)}&reset=true`);
        setFallbackActive(false);
      } catch (err) {
        console.error("[Visual Tile Status] Failed to reset status:", err);
      }
    };

    const checkStatus = async () => {
      try {
        const res = await fetch(`/api/agribrain/visual-tile/status?scene_id=${encodeURIComponent(sceneId)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.active) {
            setFallbackActive(true);
            return true; // found active fallback
          }
        }
      } catch (err) {
        console.error("[Visual Tile Status] Failed to check status:", err);
      }
      return false;
    };

    resetStatus().then(() => {
      checkStatus();
    });

    // Schedule check after 1.5 seconds
    const initialTimeout = setTimeout(() => {
      checkStatus();
    }, 1500);

    // Poll every 5 seconds for 30 seconds
    let pollCount = 0;
    const interval = setInterval(async () => {
      pollCount++;
      const found = await checkStatus();
      if (found || pollCount >= 6) {
        clearInterval(interval);
      }
    }, 5000);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [visualSource]);

  // Debug overlay toggle
  const [debugNdvi, setDebugNdvi] = useState(false);

  // 3. Drive Camera using externalized Plot Fit logic
  const { viewState, setViewState, plotGeoJson, setDimensions } = usePlotFit({ primaryPlot, activeMode });

  // V61D: Compile dynamic basemap style when visualSource is available
  const mapStyle = useMemo(() => {
    if (visualSource && visualSource.tile_url) {
      const attribution = `Tiles &copy; ${visualSource.provider || "basemap"}`;

      let tileUrl = visualSource.tile_url;
      if (typeof window !== "undefined" && tileUrl.startsWith("/")) {
        tileUrl = window.location.origin + tileUrl;
      }

      const baseStyle = getDynamicStyle(tileUrl, attribution);

      if (sceneProfile === "analysis" && baseStyle.layers) {
        // Dim basemap so active analysis layers pop
        baseStyle.layers.forEach((layer: any) => {
          if (layer.type === "raster") {
            layer.paint = {
              "raster-opacity": 0.45
            };
          }
        });
      }
      return baseStyle;
    }
    return SCENE_PROVIDERS[sceneProfile];
  }, [visualSource, sceneProfile]);

  useEffect(() => {
    if (!containerRef.current) return;

    const syncCanvas = () => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const canvas = containerRef.current.querySelector<HTMLCanvasElement>("#deckgl-overlay");
      if (canvas && rect.width > 0 && rect.height > 0) {
        const dpr = window.devicePixelRatio || 1;
        const targetW = Math.round(rect.width * dpr);
        const targetH = Math.round(rect.height * dpr);
        if (canvas.width !== targetW || canvas.height !== targetH) {
          canvas.width = targetW;
          canvas.height = targetH;
        }
      }
    };

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry && entry.contentRect.width > 0 && entry.contentRect.height > 0) {
        setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
        syncCanvas();
      }
    });

    observer.observe(containerRef.current);
    window.addEventListener("resize", syncCanvas);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", syncCanvas);
    };
  }, [setDimensions]);

  // Stable hover callback
  const handleZoneHover = useCallback((zoneId: string | null) => {
    setHoveredZoneId(zoneId);
  }, []);

  // Compute precise grid boundaries and scaling mapping helper
  const gridBounds = useMemo(() => {
    if (!surfaceData) return null;
    const bounds = resolveSurfaceBounds(surfaceData, plotGeoJson);
    if (!bounds.every(Number.isFinite) || bounds[2] <= bounds[0] || bounds[3] <= bounds[1]) return null;
    let minLng = bounds[0];
    let minLat = bounds[1];
    let maxLng = bounds[2];
    let maxLat = bounds[3];
    let crossesAntiMeridian = false;

    if ((maxLng - minLng) > 180) {
      crossesAntiMeridian = true;
      if (minLng < 0) minLng += 360;
      if (maxLng < 0) maxLng += 360;
    }

    const gridH = surfaceData.values?.length || 8;
    const gridW = surfaceData.values?.[0]?.length || 8;
    const lngStep = (maxLng - minLng) / gridW;
    const latStep = (maxLat - minLat) / gridH;

    return {
      minLng,
      minLat,
      maxLng,
      maxLat,
      gridH,
      gridW,
      lngStep,
      latStep,
      crossesAntiMeridian,
    };
  }, [surfaceData, plotGeoJson]);

  // Convert hover coordinate to cell reading in O(1)
  const activeCellData = useMemo(() => {
    if (!hoverCoord || !gridBounds || !surfaceData?.values) return null;
    let { lng, lat } = hoverCoord;

    if (gridBounds.crossesAntiMeridian && lng < 0) {
      lng += 360;
    }

    if (
      lng >= gridBounds.minLng &&
      lng <= gridBounds.maxLng &&
      lat >= gridBounds.minLat &&
      lat <= gridBounds.maxLat
    ) {
      const col = Math.floor((lng - gridBounds.minLng) / gridBounds.lngStep);
      const row = Math.floor((gridBounds.maxLat - lat) / gridBounds.latStep);

      if (row >= 0 && row < gridBounds.gridH && col >= 0 && col < gridBounds.gridW) {
        const val = surfaceData.values[row]?.[col] ?? null;
        const sampleMask = (maskSurface: SurfaceData | null | undefined): number | null => {
          const maskValues = maskSurface?.values;
          const maskH = maskValues?.length || 0;
          const maskW = maskValues?.[0]?.length || 0;
          if (!maskH || !maskW) return null;
          const maskRow = Math.min(maskH - 1, Math.max(0, Math.floor((row + 0.5) * maskH / gridBounds.gridH)));
          const maskCol = Math.min(maskW - 1, Math.max(0, Math.floor((col + 0.5) * maskW / gridBounds.gridW)));
          const numeric = Number(maskValues?.[maskRow]?.[maskCol]);
          return Number.isFinite(numeric) ? numeric : null;
        };
        const validMask = l10.surfaceByType?.["VALID_DATA_MASK_NDVI"] || l10.surfaceByType?.["VALID_DATA_MASK"];
        const observedMask = l10.surfaceByType?.["OBSERVED_DATA_MASK_NDVI"] || l10.surfaceByType?.["OBSERVED_DATA_MASK"];
        const gapFillMask = l10.surfaceByType?.["GAP_FILL_MASK_NDVI"] || l10.surfaceByType?.["GAP_FILL_MASK"];
        const valid = sampleMask(validMask);
        if (valid !== null && valid <= 0) return null;
        if (valid === null && !Number.isFinite(Number(val))) return null;
        const observed = sampleMask(observedMask);
        const gapFilled = sampleMask(gapFillMask);
        const confidence = confidenceSurface?.values?.[row]?.[col] ?? null;
        const confidenceSemanticType = String(
          confidenceSurface?.semantic_type || confidenceSurface?.type || "",
        ).toUpperCase();
        const deviation = deviationSurface?.values?.[row]?.[col] ?? null;
        const units = (surfaceData as any)?.units || (surfaceData as any)?.provenance?.units || "";
        const surfaceProvenance = (surfaceData as any)?.provenance || {};
        const supportClass = surfaceProvenance.evidence_class || surfaceProvenance.support_class || "";
        const semanticType = surfaceData.semantic_type || surfaceData.type || "";
        const asmaeCell = isAsmaeSurfaceType(semanticType);
        const compositeCell = isCompositeAdvisorySurface(semanticType);
        const asmaeEvidenceClass = String(
          surfaceProvenance.support_class || surfaceProvenance.evidence_class || "unsupported",
        ).toLowerCase().replace(/[- ]/g, "_");
        return {
          row,
          col,
          val,
          confidence,
          confidenceSemanticType,
          deviation,
          units,
          supportClass,
          evidenceClass: asmaeCell || compositeCell
            ? asmaeEvidenceClass
            : gapFilled !== null && gapFilled > 0
            ? "gap_filled"
            : observed !== null && observed > 0
              ? "observed"
              : isExperimentalSurfaceType(surfaceData.semantic_type || surfaceData.type)
                ? "experimental"
                : "valid_unclassified",
          evidenceSource: compositeCell
            ? "Composite/model-prior feature bus"
            : asmaeCell
            ? asmaeEvidenceClass === "derived_diagnostic"
              ? "ASMAE diagnostic provenance"
              : "ASMAE state-support ledger"
            : "Provider pixel-support masks",
        };
      }
    }
    return null;
  }, [hoverCoord, gridBounds, surfaceData, confidenceSurface, deviationSurface, l10.surfaceByType]);

  // NOTE: Browser-side biophysical transforms (LAI, FAPAR, RWC, ECE, nitrogen)
  // were removed in R5.0 Phase 2. Those formulas lacked crop calibration,
  // growth-stage domain, uncertainty, and scientific authority contracts.
  // The raw NDVI value from activeCellData is the only provider measurement.

  // Generate 30 equidistant cross-sectional samples along the transect path
  const transectSamples = useMemo(() => {
    if (!inspectorDiagnosisAllowed) return null;
    if (transectPoints.length < 2 || !gridBounds || !surfaceData?.values) return null;
    const [ptA, ptB] = transectPoints;
    const samples = [];
    for (let i = 0; i < 30; i++) {
      const t = i / 29;
      const lng = ptA[0] + t * (ptB[0] - ptA[0]);
      const lat = ptA[1] + t * (ptB[1] - ptA[1]);

      let sampleLng = lng;
      if (gridBounds.crossesAntiMeridian && sampleLng < 0) {
        sampleLng += 360;
      }

      let val = null;
      if (
        sampleLng >= gridBounds.minLng &&
        sampleLng <= gridBounds.maxLng &&
        lat >= gridBounds.minLat &&
        lat <= gridBounds.maxLat
      ) {
        const col = Math.floor((sampleLng - gridBounds.minLng) / gridBounds.lngStep);
        const row = Math.floor((gridBounds.maxLat - lat) / gridBounds.latStep);
        if (row >= 0 && row < gridBounds.gridH && col >= 0 && col < gridBounds.gridW) {
          const observed = l10.surfaceByType?.["OBSERVED_DATA_MASK_NDVI"]?.values?.[row]?.[col];
          const gapFilled = l10.surfaceByType?.["GAP_FILL_MASK_NDVI"]?.values?.[row]?.[col];
          if (resolvedIsAsmae) {
            const rawVal = surfaceData.values[row]?.[col];
            if (rawVal !== null && rawVal !== undefined && Number.isFinite(rawVal)) {
              val = rawVal;
            }
          } else if (observed === 1 && gapFilled !== 1) {
            val = surfaceData.values[row]?.[col] ?? null;
          }
        }
      }
      samples.push({ i, lng, lat, val });
    }
    return samples;
  }, [transectPoints, gridBounds, surfaceData, inspectorDiagnosisAllowed, l10.surfaceByType, resolvedIsAsmae]);

  // Active transect points: pass the current hoverCoord as a preview for the second point
  const activeTransectPoints = useMemo<[number, number][]>(() => {
    if (transectPoints.length === 1 && hoverCoord) {
      return [transectPoints[0], [hoverCoord.lng, hoverCoord.lat]];
    }
    return transectPoints;
  }, [visualSource, sceneProfile]);

  // Hovered sample coordinate highlight halo
  const hoveredSampleCoordinate = useMemo<[number, number] | null>(() => {
    if (hoveredSampleIndex !== null && transectSamples?.[hoveredSampleIndex]) {
      const s = transectSamples[hoveredSampleIndex];
      return [s.lng, s.lat];
    }
    return null;
  }, [hoveredSampleIndex, transectSamples]);

  // 4. Build Layers dynamically using pure external helper
  const plotId = (primaryPlot?._id || primaryPlot?.id) as string | undefined;

  // V92.4: Build overlay surfaces dynamically from ALL resolved surfaces.
  // Previously whitelisted only canonical types (WATER_STRESS_PROB, etc.)
  // which missed ASMAE fallback surfaces the mode resolver selects.
  const overlaySurfaces = useMemo(() => {
    if (!l10.surfaceByType) return {};
    const map: Record<string, SurfaceData | null> = {};
    for (const [key, val] of Object.entries(l10.surfaceByType)) {
      map[key] = val || null;
    }
    return map;
  }, [l10.surfaceByType]);

  // V92.4-BC.1: Compute active mode's availability for uniform tint rendering
  const activeModeAvailability = useMemo(() => {
    const modeKey = (l10.baseSurfaceMode ?? activeMode) as string;
    return l10.modeAvailability?.[modeKey] ?? undefined;
  }, [l10.baseSurfaceMode, activeMode, l10.modeAvailability]);

  // 4a. Build SURFACE layers (heavy raster work — NOT affected by zone hover)
  const surfaceStack = useMemo(() => buildLayerStack({
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
    hoveredZoneId: null,  // Surface layers don't care about hover
    detailMode,
    paletteId,
    transectPoints: activeTransectPoints,
    hoveredSampleCoordinate,
    onZoneClick,
    onZoneHover: handleZoneHover,
    showExperimental1m,
    showCandidateMask,
    isLowConfidence,
    experimental1mSurface,
    candidateMaskSurface,
    renderMode: l10.evidenceState?.renderMode,
    evidenceState: l10.evidenceState,
    overlaySurfaces,
    overlayToggles: l10.overlayToggles,
    overlayAvailability: l10.overlayAvailability || undefined,
    modeAvailability: activeModeAvailability,
    zoom: viewState.zoom,
    canopySource: l10.canopySource,
    activeDisplay: l10.activeDisplay,
    shouldShowPlotLevel: l10.shouldShowPlotLevel,
    activeSurfaceType: l10.activeSurfaceType,
    renderAuthorizations: l10.data?.render_authorizations,
    renderAuthorizationVersion: l10.data?.render_authorization_version,
    baseMaterialization: l10.renderPlan.baseMaterialization,
    experimentalMaterialization: l10.renderPlan.overlayMaterialization,
  }), [
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
    detailMode,
    paletteId,
    activeTransectPoints,
    hoveredSampleCoordinate,
    onZoneClick,
    handleZoneHover,
    showExperimental1m,
    showCandidateMask,
    isLowConfidence,
    experimental1mSurface,
    candidateMaskSurface,
    l10.evidenceState,
    overlaySurfaces,
    l10.overlayToggles,
    l10.overlayAvailability,
    activeModeAvailability,
    viewState.zoom,
    l10.canopySource,
    l10.activeDisplay,
    l10.shouldShowPlotLevel,
    l10.activeSurfaceType,
    l10.data?.render_authorizations,
    l10.data?.render_authorization_version,
    l10.renderPlan,
  ]);
  const surfaceLayers = surfaceStack.surfaceLayers;
  const renderMaterialization = surfaceStack.materialization;
  const experimentalRenderMaterialization = surfaceStack.experimentalMaterialization;
  const hybridOverlayRenderMaterializations = surfaceStack.hybridOverlayMaterializations;

  // Publish post-commit browser receipt via DeckGL onAfterRender callback.
  // Cleanup receipt on unmount/view switch.
  useEffect(() => {
    const viewIdentity = l10.renderPlan.viewIdentity;
    return () => clearBrowserRenderReceipt(viewIdentity);
  }, [clearBrowserRenderReceipt, l10.renderPlan.viewIdentity]);

  // 4b. Build ZONE layers (lightweight — rebuilds on hover, which is fine)
  const zoneLayers = useMemo(() => buildLayerStack({
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
    detailMode,
    paletteId,
    transectPoints: activeTransectPoints,
    hoveredSampleCoordinate,
    onZoneClick,
    onZoneHover: handleZoneHover,
    renderMode: l10.evidenceState?.renderMode,
    evidenceState: l10.evidenceState,
    overlaySurfaces,
    overlayToggles: l10.overlayToggles,
    overlayAvailability: l10.overlayAvailability || undefined,
    modeAvailability: activeModeAvailability,
    zoom: viewState.zoom,
    canopySource: l10.canopySource,
    renderAuthorizations: l10.data?.render_authorizations,
    renderAuthorizationVersion: l10.data?.render_authorization_version,
    baseMaterialization: renderMaterialization,
    experimentalMaterialization: experimentalRenderMaterialization,
  }).zoneLayers, [
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
    detailMode,
    paletteId,
    activeTransectPoints,
    hoveredSampleCoordinate,
    onZoneClick,
    handleZoneHover,
    l10.evidenceState,
    overlaySurfaces,
    l10.overlayToggles,
    l10.overlayAvailability,
    activeModeAvailability,
    viewState.zoom,
    l10.canopySource,
    l10.data?.render_authorizations,
    l10.data?.render_authorization_version,
    renderMaterialization,
    experimentalRenderMaterialization,
  ]);

  // 4c. Build WORKSPACE ENTITY layers (sensors, cameras, field equipment pins)
  const entityLayers = useMemo(() => {
    if (!workspaceEntities || workspaceEntities.length === 0) return [];
    return getWorkspaceEntityPinsLayers({
      entities: workspaceEntities,
      selectedEntityId,
      onEntityClick,
    });
  }, [workspaceEntities, selectedEntityId, onEntityClick]);

  // 5. Compute hovered zone centroid for floating chip
  const hoveredZoneData = useMemo(() => {
    if (!hoveredZoneId || !l10Zones || !surfaceData || !plotGeoJson) return null;

    const zone = l10Zones.find(z => z.zone_id === hoveredZoneId);
    if (!zone || zone.zone_id === selectedZone) return null;

    const fc = formatZoneGeoJson(
      [zone],
      null,
      renderMaterialization.gridHeight || 0,
      renderMaterialization.gridWidth || 0,
      plotGeoJson,
      undefined,
      renderMaterialization.gridBounds,
      renderMaterialization,
    );

    if (!fc.features || fc.features.length === 0) return null;
    const feature = fc.features[0] as DeckZoneFeature;
    const centroid = computeZoneCentroid(feature);

    return {
      zoneId: zone.zone_id,
      label: zone.label || zone.zone_type?.replace(/_/g, " ") || zone.zone_id,
      confidence: zone.confidence,
      areaFraction: zone.area_fraction,
      severity: zone.severity ?? 0,
      primaryDriver: zone.top_drivers?.[0]?.replace(/_/g, " ") ?? null,
      centroid,
    };
  }, [hoveredZoneId, l10Zones, selectedZone, surfaceData, plotGeoJson, renderMaterialization]);

  // 6. Compute SELECTED zone centroid for persistent pinned chip on map
  const selectedZoneData = useMemo(() => {
    if (!selectedZone || !l10Zones || !surfaceData || !plotGeoJson) return null;

    const zone = l10Zones.find(z => z.zone_id === selectedZone);
    if (!zone) return null;

    const fc = formatZoneGeoJson(
      [zone],
      selectedZone,
      renderMaterialization.gridHeight || 0,
      renderMaterialization.gridWidth || 0,
      plotGeoJson,
      undefined,
      renderMaterialization.gridBounds,
      renderMaterialization,
    );

    if (!fc.features || fc.features.length === 0) return null;
    const feature = fc.features[0] as DeckZoneFeature;
    const centroid = computeZoneCentroid(feature);

    return {
      zoneId: zone.zone_id,
      label: zone.label || zone.zone_type?.replace(/_/g, " ") || zone.zone_id,
      confidence: zone.confidence,
      areaFraction: zone.area_fraction,
      severity: zone.severity ?? 0,
      primaryDriver: zone.top_drivers?.[0]?.replace(/_/g, " ") ?? null,
      centroid,
    };
  }, [selectedZone, l10Zones, surfaceData, plotGeoJson, renderMaterialization]);

  // Intercept map hover — only update when the hovered grid cell changes
  const handleMapHover = useCallback((info: any) => {
    const { coordinate } = info;
    if (coordinate && Array.isArray(coordinate)) {
      const lng = coordinate[0];
      const lat = coordinate[1];
      // Quantize to ~0.00001° (≈1m) to skip sub-cell moves
      const cellKey = `${(lng * 100000) | 0},${(lat * 100000) | 0}`;
      if (cellKey !== lastHoverCellRef.current) {
        lastHoverCellRef.current = cellKey;
        setHoverCoord({ lng, lat });
      }
    } else if (lastHoverCellRef.current !== null) {
      lastHoverCellRef.current = null;
      setHoverCoord(null);
    }
  }, []);

  // Intercept map click to define transect line
  const handleMapClick = useCallback((info: any) => {
    if (transectMode) {
      const { coordinate } = info;
      if (coordinate && Array.isArray(coordinate)) {
        const [lng, lat] = coordinate;
        if (transectPoints.length === 0 || transectPoints.length === 2) {
          setTransectPoints([[lng, lat]]);
        } else if (transectPoints.length === 1) {
          setTransectPoints([transectPoints[0], [lng, lat]]);
          setTransectMode(false);
        }
      }
    }
  }, [transectMode, transectPoints]);

  // Human readable title of active mode
  const modeTitle = useMemo(() => {
    const exactSurfaceTitle = resolvePixelInspectorTitle(resolvedSurfaceType, activeMode);
    if (exactSurfaceTitle) return exactSurfaceTitle;
    const isCanopy = activeMode === "vegetation" || activeMode === "canopy";
    if (isCanopy) {
      const stype = String(l10.activeSurfaceType || surfaceData?.semantic_type || surfaceData?.type || "").toUpperCase();
      if (isCompositeAdvisorySurface(stype)) return "Composite Scouting Canopy";
      if (isAsmaeSurfaceType(stype)) return "ASMAE Advisory Canopy";
      if (isExperimentalSurfaceType(stype)) return "Experimental Visual Canopy";
      if (stype === "NDVI_CLEAN" || stype === "NDVI") {
        const sourceReality = String(surfaceData?.source_reality || surfaceData?.provenance?.source_reality || "").toLowerCase();
        const staleSourceState = hasStaleGatewayEvidence(l10.data?.rawData);
        const baseTitle = sourceReality === "provider_temporal_composite_raster"
          ? staleSourceState
            ? "Last known satellite composite — refresh unavailable"
            : "Provider temporal composite NDVI"
          : "Satellite NDVI";
        const expectedExperimentalType = String(experimental1mSurface?.type || experimental1mSurface?.semantic_type || "");
        const experimentalRendered = hasRenderedExperimentalOverlay(
          experimentalRenderMaterialization,
          expectedExperimentalType || undefined,
          activeMode,
        );
        if (l10.canopySource === "asmae_diagnostic" && l10.data?.source_policy_display_state?.fallback_reason) return `${baseTitle} — ASMAE diagnostic unavailable`;
        if (l10.canopySource === "experimental") {
          return experimentalRendered
            ? `${baseTitle} + experimental scouting texture`
            : `${baseTitle} — experimental overlay unavailable`;
        }
        if (l10.canopySource === "hybrid") {
          return experimentalRendered
            ? `${baseTitle} + experimental scouting texture`
            : `${baseTitle} — hybrid overlay unavailable`;
        }
        return baseTitle;
      }
    }
    switch (activeMode) {
      case "vegetation":
      case "canopy":
        return "NDVI / Canopy Health";
      case "veg_attention":
        return "Vegetation Attention";
      case "water_stress":
        return "Water Stress / Aridity";
      case "nutrient_risk":
        return "Nutrient Stress Index";
      case "salinity":
        return "Soil Salinity (ECe)";
      case "composite_risk":
        return "Composite Biophysical Risk";
      case "uncertainty":
        return "Data Reliability / Confidence";
      case "resolution_coverage":
        return "Resolution Coverage";
      default:
        return "Biophysical Lens";
    }
  }, [
    activeMode,
    l10.canopySource,
    l10.activeSurfaceType,
    l10.data?.rawData,
    l10.data?.source_policy_display_state?.fallback_reason,
    surfaceData,
    experimental1mSurface,
    experimentalRenderMaterialization,
    resolvedSurfaceType,
  ]);
  const cropStageLabels = useMemo(() => resolveCropStageLabels(
    cropName,
    l10.evidenceState.resolvedPhenology.stage,
  ), [cropName, l10.evidenceState.resolvedPhenology.stage]);

  // Svg Cross-Section calculation variables
  const crossSectionChart = useMemo(() => {
    if (!transectSamples || transectSamples.length === 0) return null;
    const sampleValues = transectSamples.map(s => s.val).filter((v): v is number => v !== null);
    const minVal = sampleValues.length ? Math.min(...sampleValues) : 0;
    const maxVal = sampleValues.length ? Math.max(...sampleValues) : 1;
    const valRange = maxVal - minVal || 1;

    // Build SVG coordinates
    // We map 30 points across width [40, 760] and height [20, 110]
    const points = transectSamples.map((s, idx) => {
      const x = 40 + (idx / 29) * (760 - 40);
      const val = s.val !== null ? s.val : minVal;
      const y = 110 - ((val - minVal) / valRange) * (110 - 20);
      return { x, y, val: s.val, rawIndex: idx };
    });

    // Make filled path string
    const fillPath = `M 40,110 ` + points.map(p => `L ${p.x},${p.y}`).join(" ") + ` L 760,110 Z`;
    // Make line path string
    const linePath = `M ${points[0].x},${points[0].y} ` + points.slice(1).map(p => `L ${p.x},${p.y}`).join(" ");

    return {
      points,
      fillPath,
      linePath,
      minVal,
      maxVal,
    };
  }, [transectSamples]);

  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!transectSamples || transectSamples.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const width = rect.width;
    const fraction = x / width;
    const index = Math.max(0, Math.min(29, Math.round(fraction * 29)));
    setHoveredSampleIndex(index);
  };

  const handleSvgMouseLeave = () => {
    setHoveredSampleIndex(null);
  };

  const hoveredSample = (transectSamples && hoveredSampleIndex !== null)
    ? transectSamples[hoveredSampleIndex]
    : null;

  return (
    <div ref={containerRef} className="absolute inset-0 w-full h-full overflow-hidden deckgl-blend-screen bg-slate-950">
      <DeckGL
        id="deckgl-overlay"
        width="100%"
        height="100%"
        style={{ width: "100%", height: "100%", position: "absolute", top: "0px", left: "0px" }}
        viewState={viewState}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onViewStateChange={({ viewState }) => setViewState(viewState as any)}
        controller={true}
        layers={[...surfaceLayers, ...zoneLayers, ...entityLayers]}
        getCursor={({ isHovering }) => {

          if (transectMode) return "crosshair";
          return isHovering ? "pointer" : "grab";
        }}
        onHover={handleMapHover}
        onClick={handleMapClick}
        onAfterRender={() => {
          const committedLayerIds = new Set<string>();
          for (const layer of [...surfaceLayers, ...zoneLayers, ...entityLayers].flat(Infinity) as any[]) {
            if (layer?.id) committedLayerIds.add(String(layer.id));
          }
          const receiptDetails = {
            publicationId: l10.data?.publication_id || "",
            snapshotId: l10.data?.intelligence_snapshot_id || "",
            surfaceInventoryHash: l10.data?.surface_inventory_hash || "",
            renderAuthorizationVersion: l10.data?.render_authorization_version || "",
            sourceId: [
              l10.data?.intelligence_snapshot_id || "snapshot_missing",
              l10.data?.surface_inventory_hash || "inventory_missing",
            ].join("@"),
            mapInstanceId: "deckgl-overlay",
          };
          const committedBase = renderMaterialization.layerId
            ? createCommittedRenderReceipt(
                renderMaterialization,
                renderMaterialization.layerId,
                committedLayerIds,
                receiptDetails,
              )
            : renderMaterialization;
          const committedOverlay = experimentalRenderMaterialization.layerId
            ? createCommittedRenderReceipt(
                experimentalRenderMaterialization,
                experimentalRenderMaterialization.layerId,
                committedLayerIds,
                receiptDetails,
              )
            : experimentalRenderMaterialization;
          const committedHybridOverlays = hybridOverlayRenderMaterializations.map((materialization) =>
            materialization.layerId
              ? createCommittedRenderReceipt(
                  materialization,
                  materialization.layerId,
                  committedLayerIds,
                  receiptDetails,
                )
              : materialization,
          );
          commitBrowserRenderReceipt({
            viewIdentity: l10.renderPlan.viewIdentity,
            baseMaterialization: committedBase,
            overlayMaterialization: committedOverlay,
            hybridOverlayMaterializations: committedHybridOverlays,
            snapshotId: l10.data?.intelligence_snapshot_id || l10.data?.run_id || "",
            publicationId: l10.data?.publication_id || "",
            surfaceInventoryHash: l10.data?.surface_inventory_hash || "",
            renderAuthorizationVersion: l10.data?.render_authorization_version || "",
            committedAt: new Date().toISOString(),
          });
        }}
      >
        <Map
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          mapStyle={mapStyle as any}
          maplibreLogo={false}
          attributionControl={false}
          interactiveLayerIds={['plot-fill-layer']}
        >
          {/* --- MapLibre Native Vector Layers --- */}

          {/* Field Boundary Polygon */}
          {plotGeoJson && (
            <Source id="plot-boundary" type="geojson" data={plotGeoJson as import("geojson").Feature<import("geojson").Geometry, import("geojson").GeoJsonProperties>}>
              <Layer
                id="plot-fill-layer"
                type="fill"
                paint={{
                  'fill-color': 'transparent',
                }}
              />
              <Layer
                id="plot-stroke-layer"
                type="line"
                paint={{
                  'line-color': '#ffffff',
                  'line-width': 1.5,
                  'line-opacity': 0.85,
                }}
              />
            </Source>
          )}
        </Map>
      </DeckGL>

      <PlotScientificLegend
        layerName={activeMode || "Satellite context"}
        surface={surfaceData}
        scene={visualSource}
        degraded={isLowConfidence}
        canInterpret={canInterpretDiagnostically}
      />

      {/* --- PREMIUM CONTROL DOCK (Top-Right) --- */}
      <div 
        className="absolute z-40 flex flex-col gap-3 animate-fadeIn"
        style={{
          top: "340px",
          right: "344px",
        }}
      >
        <div className="backdrop-blur-md bg-slate-900/80 border border-white/10 rounded-xl p-3 shadow-2xl flex flex-col gap-2.5 min-w-[200px] transition-all">
          <div className="text-white/60 text-[10px] font-bold tracking-wider uppercase">
            Color Lens
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {[
              { id: "standard", label: "Standard", color: "bg-emerald-500" },
              { id: "thermal", label: "Thermal", color: "bg-orange-500" },
              { id: "chlorophyll", label: "Chluoro", color: "bg-pink-500" },
              { id: "chroma", label: "Chroma", color: "bg-indigo-500" },
            ].map(pal => (
              <button
                key={pal.id}
                onClick={() => onPaletteChange?.(pal.id as "standard" | "thermal" | "chlorophyll" | "chroma")}
                className={`px-2 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-all border flex items-center gap-1.5 select-none ${paletteId === pal.id
                    ? "bg-white/15 text-white border-white/35 shadow-lg"
                    : "bg-slate-950/40 text-white/70 border-white/5 hover:bg-white/5 hover:text-white"
                  }`}
              >
                <span className={`w-2 h-2 rounded-full ${pal.color}`} />
                {pal.label}
              </button>
            ))}
          </div>
          <div className="text-[8px] text-white/40 italic leading-tight mt-0.5">
            Color-only visualization; does not modify raw sensor bands.
          </div>

          <div className="h-px bg-white/10 my-1" />

          <div className="text-white/60 text-[10px] font-bold tracking-wider uppercase">
            Spatial Analysis
          </div>
          <button
            onClick={() => {
              if (!inspectorDiagnosisAllowed) {
                setShowProxyBanner(true);
                return;
              }
              setTransectMode(prev => !prev);
              if (!transectMode) {
                setTransectPoints([]);
              }
            }}
            className={`w-full py-2 rounded-lg text-xs font-semibold cursor-pointer border flex items-center justify-center gap-1.5 transition-all select-none ${!inspectorDiagnosisAllowed
                ? "opacity-40 cursor-not-allowed bg-slate-950/40 text-white/40 border-white/5"
                : transectMode
                ? "bg-yellow-400 text-slate-950 border-yellow-300 font-bold shadow-lg animate-pulse"
                : transectPoints.length > 0
                  ? "bg-yellow-400/10 text-yellow-400 border-yellow-400/35 hover:bg-yellow-400/20"
                  : "bg-slate-950/40 text-white/80 border-white/5 hover:bg-white/5 hover:text-white"
              }`}
            title={!inspectorDiagnosisAllowed ? "Cross-section requires inspector-authorized observed raster data" : "Draw a transect line on the map"}
          >
            📏 {transectMode ? "Placing A ➔ B..." : transectPoints.length > 0 ? "Reset Transect" : inspectorDiagnosisAllowed ? "Cross-Section" : "Cross-Section unavailable"}
          </button>
        </div>
      </div>

      {/* --- AGRONOMIC BIOPHYSICS HUD (Top-Left) --- */}
      {activeCellData && canSamplePixel && canInterpretForScouting && (
        <div 
          className="absolute backdrop-blur-md bg-slate-950/75 border border-white/10 rounded-xl p-4 shadow-2xl min-w-[280px] pointer-events-none animate-fadeIn transition-all"
          style={{
            top: "260px",
            left: "344px",
            zIndex: 40,
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
              🔍 Pixel Inspector
            </span>
            <span className="text-[10px] text-white/40 font-mono">
              Row {activeCellData.row} Col {activeCellData.col}
            </span>
          </div>

          <h3 className="text-white text-base font-semibold mb-3">
            {modeTitle}
          </h3>
          <div className="text-[10px] uppercase tracking-wide text-white/50 mb-2">
            {resolvedIsComposite
              ? `Composite scouting cell (${String(activeCellData.supportClass || "unsupported").replace(/_/g, " ")})`
              : resolvedIsAsmae
              ? `${canInterpretDiagnostically ? "ASMAE inspector-authorized" : "ASMAE scouting"} cell (${String(activeCellData.supportClass || "unsupported").replace(/_/g, " ")})`
              : activeCellData.evidenceClass === "observed"
                ? "Observed provider composite cell"
                : activeCellData.evidenceClass === "gap_filled"
                  ? "Gap-filled advisory cell"
                  : activeCellData.evidenceClass === "experimental"
                    ? "Experimental scouting cell"
                    : "Valid field cell"}
          </div>

          {!canInterpretDiagnostically ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/5 rounded-lg p-3 border border-white/5 col-span-2 text-xs">
                <div className="text-[10px] text-white/50 uppercase mb-1">
                  {(() => {
                    if (resolvedIsExperimental) {
                      return "Reading (visual index / scouting only)";
                    }
                    if (resolvedIsAsmae || resolvedIsComposite) {
                      return "Reading (advisory index / not certified pixel diagnosis)";
                    }
                    if (l10.canopySource === "hybrid") {
                      return resolvedIsAsmae ? "Reading (advisory index / not certified pixel diagnosis)" : "Reading (NDVI satellite fallback)";
                    }
                    return activeMode === "veg_attention" ? "Reading (Deviation)" : "Reading (NDVI)";
                  })()}
                </div>
                <div className="text-lg font-bold text-white font-mono flex items-baseline gap-1.5">
                  <span>{activeCellData.val !== null ? activeCellData.val.toFixed(3) : "N/A"}</span>
                  {activeCellData.units && <span className="text-xs text-white/70 font-normal">{activeCellData.units}</span>}
                  {activeCellData.supportClass && <span className="text-xs text-emerald-400/90 font-normal">({activeCellData.supportClass})</span>}
                </div>
                <div className="text-[10px] text-amber-400 mt-2 font-medium">Scouting sample only. The committed raster remains visible, but certified diagnostic interpretation and prescription use are not authorized.</div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
            {(() => {
              const v = activeCellData.val;
              const valStr = v !== null ? v.toFixed(3) : "N/A";
              
              if (activeMode === "canopy" || activeMode === "vegetation" || !activeMode) {
                return (
                  <>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">
                        {(() => {
                          if (resolvedIsExperimental) {
                            return "Reading (Visual Index / Scouting Only)";
                          }
                          if (resolvedIsAsmae || resolvedIsComposite) {
                            return "Reading (advisory index)";
                          }
                          if (l10.canopySource === "hybrid") {
                            return resolvedIsAsmae ? "Reading (advisory index)" : "Reading (NDVI satellite fallback)";
                          }
                          return "Reading (NDVI)";
                        })()}
                      </div>
                      <div className="text-lg font-bold text-white font-mono mt-0.5">{valStr}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Evidence Class</div>
                      <div className="text-sm font-bold text-emerald-300 font-mono mt-0.5">
                        {activeCellData.evidenceClass === "observed" ? "Observed"
                          : activeCellData.evidenceClass === "gap_filled" ? "Gap-filled"
                          : activeCellData.evidenceClass === "directly_assimilated" ? "Directly assimilated"
                          : activeCellData.evidenceClass === "proxy_assimilated" ? "Proxy-assimilated"
                          : activeCellData.evidenceClass === "indirectly_constrained" ? "Indirectly constrained"
                          : activeCellData.evidenceClass === "prior_constrained" ? "Prior-constrained"
                          : activeCellData.evidenceClass === "derived_diagnostic" ? "Derived diagnostic"
                          : activeCellData.evidenceClass === "composite_scouting" ? "Composite scouting"
                          : activeCellData.evidenceClass === "unsupported" ? "Unsupported"
                          : "Unclassified"}
                      </div>
                      <div className="text-[9px] text-white/30">{activeCellData.evidenceSource}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">
                        {activeCellData.confidenceSemanticType.includes("UNCERTAINTY_SIGMA")
                          ? "Multi-evidence uncertainty"
                          : activeCellData.confidenceSemanticType.includes("POSTERIOR_CONCENTRATION")
                            ? "Posterior concentration"
                            : "Reliability / Quality"}
                      </div>
                      <div className="text-sm font-bold text-yellow-300 font-mono mt-0.5">
                        {activeCellData.confidence !== null ? activeCellData.confidence.toFixed(2) : "N/A"}
                      </div>
                      <div className="text-[9px] text-white/30">
                        {activeCellData.confidenceSemanticType.includes("UNCERTAINTY_SIGMA")
                          ? "Model-derived spatial uncertainty index"
                          : activeCellData.confidenceSemanticType.includes("POSTERIOR_CONCENTRATION")
                            ? "Posterior concentration"
                            : "Surface quality score"}
                      </div>
                    </div>
                    {activeCellData.deviation !== null && (
                      <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                        <div className="text-[10px] text-white/50 uppercase">Deviation</div>
                        <div className="text-sm font-bold text-cyan-300 font-mono mt-0.5">
                          {activeCellData.deviation.toFixed(3)}
                        </div>
                        <div className="text-[9px] text-white/30">From field mean</div>
                      </div>
                    )}
                  </>
                );
              }
              
              if (activeMode === "veg_attention") {
                const deviation = v !== null ? v : 0;
                let impactClass = "Stable";
                let textColor = "text-white";
                if (deviation > 0.05) {
                  impactClass = "Optimal Vigor";
                  textColor = "text-emerald-400";
                } else if (deviation < -0.05) {
                  impactClass = "Vigor Decline";
                  textColor = "text-amber-500";
                }
                return (
                  <>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Deviation</div>
                      <div className="text-lg font-bold text-white font-mono mt-0.5">
                        {deviation > 0 ? "+" : ""}{deviation.toFixed(3)}
                      </div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Impact Class</div>
                      <div className={`text-sm font-bold mt-0.5 ${textColor}`}>{impactClass}</div>
                    </div>
                    {cropStageLabels.cropLabel && (
                      <div className="bg-white/5 rounded-lg p-2 border border-white/5 col-span-2">
                        <div className="text-[10px] text-white/50 uppercase">Crop Classification</div>
                        <div className="text-sm font-semibold text-slate-300 mt-0.5">{cropStageLabels.cropLabel}</div>
                        {cropStageLabels.growthStageLabel && (
                          <div className="text-xs text-slate-400 mt-0.5">{cropStageLabels.growthStageLabel}</div>
                        )}
                      </div>
                    )}
                  </>
                );
              }
              
              if (activeMode === "water_stress") {
                const vRaw = v !== null ? v : 0;
                const isProb = v !== null && v >= 0 && v <= 1.0 && (!activeCellData.units || activeCellData.units === "probability" || activeCellData.units === "index");
                const valDisplay = isProb ? `${(vRaw * 100).toFixed(0)}%` : `${vRaw.toFixed(2)}${activeCellData.units ? " " + activeCellData.units : ""}`;

                let deficiencyClass = "Optimal";
                let textColor = "text-emerald-400";
                if (isProb) {
                  if (vRaw > 0.7) {
                    deficiencyClass = "Severe Deficit";
                    textColor = "text-red-400";
                  } else if (vRaw > 0.4) {
                    deficiencyClass = "Mild Deficit";
                    textColor = "text-amber-400";
                  } else if (vRaw < 0.1) {
                    deficiencyClass = "High Moisture";
                    textColor = "text-cyan-400";
                  }
                } else {
                  deficiencyClass = resolvedIsAsmae || resolvedIsComposite
                    ? "Scouting state estimate"
                    : "Biophysical observation";
                  textColor = "text-cyan-300";
                }
                const ndmiProxy = isProb ? 0.8 - vRaw * 0.9 : vRaw;
                return (
                  <>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">{isProb ? "Stress Probability" : "Water Reading"}</div>
                      <div className="text-lg font-bold text-white font-mono mt-0.5">{valDisplay}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Moisture Class</div>
                      <div className={`text-sm font-bold mt-0.5 ${textColor}`}>{deficiencyClass}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5 col-span-2">
                      <div className="text-[10px] text-white/50 uppercase">{isProb ? "NDMI Basis Proxy" : "Raw Biophysical Value"}</div>
                      <div className="text-sm font-mono text-cyan-300 mt-0.5">{isProb ? ndmiProxy.toFixed(3) : `${vRaw.toFixed(3)} ${activeCellData.units || ""}`}</div>
                    </div>
                  </>
                );
              }
              
              if (activeMode === "nutrient_risk") {
                const vRaw = v !== null ? v : 0;
                const isProb = v !== null && v >= 0 && v <= 1.0 && (!activeCellData.units || activeCellData.units === "probability" || activeCellData.units === "index");
                const valDisplay = isProb ? `${(vRaw * 100).toFixed(0)}%` : `${vRaw.toFixed(2)}${activeCellData.units ? " " + activeCellData.units : ""}`;

                let deficiencyClass = "Adequate";
                let textColor = "text-emerald-400";
                if (isProb) {
                  if (vRaw > 0.7) {
                    deficiencyClass = "Critical Deficiency";
                    textColor = "text-red-400";
                  } else if (vRaw > 0.3) {
                    deficiencyClass = "Deficient Risk";
                    textColor = "text-amber-400";
                  }
                } else {
                  deficiencyClass = resolvedIsAsmae || resolvedIsComposite
                    ? "Scouting state estimate"
                    : "Biophysical observation";
                  textColor = "text-emerald-300";
                }
                return (
                  <>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">{isProb ? "Risk Probability" : "Nutrient Reading"}</div>
                      <div className="text-lg font-bold text-white font-mono mt-0.5">{valDisplay}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Deficiency Class</div>
                      <div className={`text-sm font-bold mt-0.5 ${textColor}`}>{deficiencyClass}</div>
                    </div>
                  </>
                );
              }
              
              if (activeMode === "salinity") {
                const vRaw = v !== null ? v : 0;
                const isProb = v !== null && v >= 0 && v <= 1.0 && (!activeCellData.units || activeCellData.units === "probability" || activeCellData.units === "index");
                const valDisplay = isProb ? `${(vRaw * 100).toFixed(0)}%` : `${vRaw.toFixed(2)}${activeCellData.units ? " " + activeCellData.units : ""}`;

                let salineClass = "Low Risk";
                let textColor = "text-emerald-400";
                if (isProb) {
                  if (vRaw > 0.7) {
                    salineClass = "Severe Risk";
                    textColor = "text-red-500";
                  } else if (vRaw > 0.4) {
                    salineClass = "Moderate Risk";
                    textColor = "text-amber-500";
                  } else if (vRaw > 0.1) {
                    salineClass = "Slight Risk";
                    textColor = "text-yellow-400";
                  }
                } else {
                  salineClass = "Salinity Measurement";
                  textColor = "text-cyan-300";
                }
                return (
                  <>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">{isProb ? "Salinity Stress Prob." : "Salinity Reading"}</div>
                      <div className="text-lg font-bold text-white font-mono mt-0.5">{valDisplay}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Salinity Risk Class</div>
                      <div className={`text-sm font-bold mt-0.5 ${textColor}`}>{salineClass}</div>
                    </div>
                  </>
                );
              }
              
              if (activeMode === "composite_risk") {
                const score = v !== null ? v : 0;
                let driver = "None";
                let textColor = "text-emerald-400";
                if (score > 0.6) {
                  driver = "Critical Driver Risk";
                  textColor = "text-red-500";
                } else if (score > 0.3) {
                  driver = "Elevated Driver Risk";
                  textColor = "text-amber-500";
                }
                return (
                  <>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Risk Score</div>
                      <div className="text-lg font-bold text-white font-mono mt-0.5">{score.toFixed(2)}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Driver Level</div>
                      <div className={`text-sm font-bold mt-0.5 ${textColor}`}>{driver}</div>
                    </div>
                  </>
                );
              }
              
              if (activeMode === "resolution_coverage") {
                const res = v !== null ? v : 10.0;
                let precision = "10m (Sentinel Fallback)";
                let textColor = "text-slate-400";
                if (res <= 0.05) {
                  precision = "Centimeter (UAV)";
                  textColor = "text-cyan-400";
                } else if (res <= 1.2) {
                  precision = "Meter (High-Res)";
                  textColor = "text-emerald-400";
                } else if (res <= 2.2) {
                  precision = "2m (WPM Simulated)";
                  textColor = "text-teal-400";
                } else if (res <= 3.2) {
                  precision = "3m (Adaptive Modeled)";
                  textColor = "text-blue-400";
                } else if (res <= 5.2) {
                  precision = "5m model-assisted (10m evidence)";
                  textColor = "text-amber-400";
                }
                return (
                  <>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Resolution</div>
                      <div className="text-lg font-bold text-white font-mono mt-0.5">{res >= 1 ? `${res.toFixed(1)}m` : `${(res * 100).toFixed(0)}cm`}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Precision Class</div>
                      <div className={`text-xs font-bold mt-1 ${textColor}`}>{precision}</div>
                    </div>
                  </>
                );
              }
              
              if (activeMode === "uncertainty") {
                const reliability = v !== null ? v : 1.0;
                const uncertainty = activeCellData.confidence !== null ? activeCellData.confidence : (1.0 - reliability);
                let trustLevel = "Excellent";
                let textColor = "text-emerald-400";
                if (reliability < 0.4) {
                  trustLevel = "Poor";
                  textColor = "text-red-500";
                } else if (reliability < 0.7) {
                  trustLevel = "Moderate";
                  textColor = "text-amber-500";
                }
                return (
                  <>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Reliability Score</div>
                      <div className="text-lg font-bold text-white font-mono mt-0.5">{(reliability * 100).toFixed(0)}%</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5">
                      <div className="text-[10px] text-white/50 uppercase">Uncertainty (σ)</div>
                      <div className="text-lg font-bold text-slate-300 font-mono mt-0.5">{uncertainty.toFixed(3)}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-2 border border-white/5 col-span-2">
                      <div className="text-[10px] text-white/50 uppercase">Trust Level</div>
                      <div className={`text-sm font-bold mt-0.5 ${textColor}`}>{trustLevel}</div>
                    </div>
                  </>
                );
              }
              
              return null;
            })()}
          </div>
          )}

          <div className="mt-3 text-[10px] text-white/40 flex items-center justify-between border-t border-white/5 pt-2">
            <span>Lat: {hoverCoord?.lat.toFixed(5)}</span>
            <span>Lng: {hoverCoord?.lng.toFixed(5)}</span>
          </div>
        </div>
      )}

      {/* V61D: Premium Visual Source Badge (floated to the right of the left status sidebar) */}
      {visualSource && (
        <div
          data-testid="visual-source-badge"
          className="absolute backdrop-blur-md bg-slate-950/80 border border-white/10 rounded-xl p-3 shadow-2xl flex items-center gap-2.5 min-w-[240px] pointer-events-auto select-none transition-all duration-300 hover:bg-slate-950"
          style={{
            top: "180px",
            left: "344px",
            zIndex: 40,
          }}
        >
          {(() => {
            const isUnavail = !visualSource.provider || visualSource.provider === "none" || visualSource.status === "unavailable";
            const dotColor = isUnavail ? 'bg-slate-400' : (visualSource.is_mock ? 'bg-amber-500' : 'bg-emerald-500');
            const title = isUnavail ? "Context basemap only" : (visualSource.is_mock ? "Synthetic Basemap Preview" : "Live visual basemap");
            const label = isUnavail ? "No plot-specific visual scene" : (visualSource.is_mock
              ? `Simulated ${visualSource.provider || "basemap"}${visualSource.native_resolution_m != null ? ` ${visualSource.native_resolution_m}m` : ''} · ${visualSource.scene_date ?? 'latest'}`
              : `Visual: ${visualSource.provider || "basemap"}${visualSource.native_resolution_m != null ? ` ${visualSource.native_resolution_m}m` : ''} · ${visualSource.scene_date ?? 'latest'}`);
            return (
              <>
                <span className={`w-2 h-2 rounded-full ${dotColor}`} />
                <div className="flex flex-col">
                  <span className="text-[9px] text-white/50 font-bold uppercase tracking-wider">{title}</span>
                  <span className="text-[11px] font-semibold text-white">{label}</span>
                  {visualSource.fallback_reason && (
                    <span className="text-[8px] text-white/40 italic mt-0.5 leading-tight">
                      {visualSource.fallback_reason}
                    </span>
                  )}
                  {fallbackActive && (
                    <span className="text-[9px] text-amber-400 font-bold mt-1 animate-pulse leading-tight">
                      ⚠️ Basemap tile unavailable — transparent fallback used
                    </span>
                  )}
                </div>
              </>
            );
          })()}
        </div>
      )}

      {/* --- CROSS-SECTION TRANSECT PROFILE PANEL (Bottom) --- */}
      {crossSectionChart && transectPoints.length === 2 && (
        <div className="absolute bottom-4 left-4 right-4 z-50 backdrop-blur-lg bg-slate-950/85 border border-white/10 rounded-xl p-4 shadow-2xl transition-all duration-300 animate-slideUp">
          <div className="flex justify-between items-center mb-3">
            <div className="flex items-center gap-2">
              <span className="text-yellow-400 text-lg">🔬</span>
              <h4 className="text-white font-semibold text-sm">
                Cross-Sectional Transect Analysis
              </h4>
              <span className="text-[10px] bg-yellow-400/20 text-yellow-300 px-2 py-0.5 rounded-full border border-yellow-400/20">
                Point A ➔ Point B
              </span>
            </div>
            <button
              onClick={() => {
                setTransectPoints([]);
                setHoveredSampleIndex(null);
              }}
              className="text-white/60 hover:text-white transition-colors cursor-pointer text-xs flex items-center gap-1 bg-white/5 hover:bg-white/10 px-2.5 py-1 rounded-lg border border-white/5"
            >
              Close ✕
            </button>
          </div>

          {/* SVG Area Chart */}
          <div className="relative w-full h-[120px] bg-slate-900/60 border border-white/5 rounded-lg overflow-visible">
            <svg
              className="w-full h-full cursor-crosshair"
              viewBox="0 0 800 120"
              preserveAspectRatio="none"
              onMouseMove={handleSvgMouseMove}
              onMouseLeave={handleSvgMouseLeave}
            >
              <defs>
                <linearGradient id="chart-area-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#facc15" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#facc15" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Gridlines */}
              <line x1="40" y1="20" x2="760" y2="20" stroke="rgba(255,255,255,0.06)" strokeDasharray="2,2" />
              <line x1="40" y1="65" x2="760" y2="65" stroke="rgba(255,255,255,0.06)" strokeDasharray="2,2" />
              <line x1="40" y1="110" x2="760" y2="110" stroke="rgba(255,255,255,0.12)" />

              {/* Filled Area */}
              <path d={crossSectionChart.fillPath} fill="url(#chart-area-grad)" />

              {/* Line path */}
              <path
                d={crossSectionChart.linePath}
                fill="none"
                stroke="#facc15"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Endpoints indicators */}
              <circle cx="40" cy={crossSectionChart.points[0].y} r="4.5" fill="#facc15" stroke="#fff" strokeWidth="1.5" />
              <circle cx="760" cy={crossSectionChart.points[29].y} r="4.5" fill="#ef4444" stroke="#fff" strokeWidth="1.5" />

              {/* Vertical Dotted Axis Markers */}
              <text x="35" y="118" fill="rgba(255,255,255,0.4)" fontSize="9" textAnchor="end">A</text>
              <text x="765" y="118" fill="rgba(255,255,255,0.4)" fontSize="9" textAnchor="start">B</text>

              {/* Axis value range labels */}
              <text x="32" y="24" fill="rgba(255,255,255,0.3)" fontSize="8" textAnchor="end">
                {crossSectionChart.maxVal.toFixed(2)}
              </text>
              <text x="32" y="113" fill="rgba(255,255,255,0.3)" fontSize="8" textAnchor="end">
                {crossSectionChart.minVal.toFixed(2)}
              </text>

              {/* Live hover vertical cursor line */}
              {hoveredSampleIndex !== null && crossSectionChart.points[hoveredSampleIndex] && (
                <>
                  <line
                    x1={crossSectionChart.points[hoveredSampleIndex].x}
                    y1="10"
                    x2={crossSectionChart.points[hoveredSampleIndex].x}
                    y2="110"
                    stroke="#facc15"
                    strokeWidth="1"
                    strokeDasharray="3,3"
                  />
                  <circle
                    cx={crossSectionChart.points[hoveredSampleIndex].x}
                    cy={crossSectionChart.points[hoveredSampleIndex].y}
                    r="6"
                    fill="#facc15"
                    stroke="#fff"
                    strokeWidth="2"
                    className="animate-ping"
                  />
                  <circle
                    cx={crossSectionChart.points[hoveredSampleIndex].x}
                    cy={crossSectionChart.points[hoveredSampleIndex].y}
                    r="4"
                    fill="#facc15"
                    stroke="#fff"
                    strokeWidth="1.5"
                  />
                </>
              )}
            </svg>

            {/* Hover Tooltip display */}
            {hoveredSample && hoveredSampleIndex !== null && (
              <div
                className="absolute z-50 backdrop-blur-md bg-slate-900/90 border border-yellow-400/40 rounded-lg p-2 text-[10px] font-mono shadow-xl text-white pointer-events-none flex flex-col gap-0.5"
                style={{
                  bottom: "105%",
                  // Center above the hovered point
                  left: `${Math.max(10, Math.min(90, (hoveredSampleIndex / 29) * 100))}%`,
                  transform: "translateX(-50%)",
                }}
              >
                <div className="text-yellow-400 font-bold flex items-center justify-between gap-4">
                  <span>Sample #{hoveredSampleIndex + 1}</span>
                  <span>{((hoveredSampleIndex / 29) * 100).toFixed(0)}% along path</span>
                </div>
                <div>
                  Value: <span className="font-bold text-white">
                    {hoveredSample.val !== null
                      ? hoveredSample.val.toFixed(4)
                      : "Out of Bounds"}
                  </span>
                </div>
                <div className="text-white/40 text-[8px] mt-0.5">
                  {hoveredSample.lat.toFixed(5)}°N, {hoveredSample.lng.toFixed(5)}°E
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {showProxyBanner && !canInterpretDiagnostically && (
        <div id="no-spatial-raster-banner" className="absolute bottom-4 left-4 right-4 z-50 backdrop-blur-lg bg-slate-950/85 border border-amber-500/20 rounded-xl p-4 shadow-2xl transition-all duration-300 animate-slideUp">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <span className="text-amber-500 text-lg">⚠️</span>
              <h4 className="text-white font-semibold text-sm">
                Cross-section unavailable for plot-level proxy
              </h4>
            </div>
            <button
              onClick={() => setShowProxyBanner(false)}
              className="text-white/60 hover:text-white transition-colors cursor-pointer text-xs bg-white/5 hover:bg-white/10 px-2.5 py-1 rounded-lg border border-white/5"
            >
              Close ✕
            </button>
          </div>
        </div>
      )}

      {/* V92.4-BC: Evidence-level-aware map banner
           Only shows for non-raster evidence levels. No banner for raster or asmae_diagnostic (those render on the map).
           plot_level → soft informational banner
           visual_only → minimal informational
           unavailable → prominent "no data" */}
      {l10.data && (() => {
        const modeKey = (l10.baseSurfaceMode || activeMode) as MapMode;
        const avail = l10.modeAvailability?.[modeKey === "vegetation" ? "canopy" : modeKey];
        const dl = avail?.displayLevel;

        // Don't show banner for raster or asmae_diagnostic (those render directly)
        if (!dl || dl === "raster" || dl === "asmae_diagnostic") return null;

        // Plot-level: soft informational banner (not alarming)
        if (dl === "plot_level" || dl === "proxy") {
          return (
            <div className="absolute top-3 left-1/2 transform -translate-x-1/2 z-40 backdrop-blur-md bg-violet-950/70 border border-violet-400/15 rounded-xl px-4 py-2.5 shadow-xl max-w-sm text-center pointer-events-none" id="plot-level-evidence-banner">
              <div className="text-violet-300 text-xs font-semibold mb-0.5">
                {avail?.label || "Plot-level estimate"}
              </div>
              <div className="text-white/60 text-[10px] leading-relaxed">
                {avail?.value != null && avail?.units
                  ? `Showing plot-wide ${avail.units}: ${typeof avail.value === 'number' ? avail.value.toFixed(1) : avail.value}`
                  : "Showing plot-level estimate. No pixel-level maps available for this mode."
                }
              </div>
              {avail?.trustBadges && avail.trustBadges.length > 0 && (
                <div className="flex items-center justify-center gap-1.5 mt-1.5">
                  {avail.trustBadges.map((badge: string, i: number) => (
                    <span key={i} className="text-[9px] text-violet-400/80 bg-violet-500/10 px-1.5 py-0.5 rounded-full">
                      {badge}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        }

        // Visual-only: minimal banner
        if (dl === "visual_only") {
          return (
            <div className="absolute top-3 left-1/2 transform -translate-x-1/2 z-40 backdrop-blur-md bg-slate-900/60 border border-slate-500/15 rounded-lg px-3 py-1.5 shadow-lg max-w-xs text-center pointer-events-none" id="visual-only-banner">
              <div className="text-zinc-400 text-[10px] font-medium">
                {avail?.label || "Visual context"} · No agronomic surface
              </div>
            </div>
          );
        }

        // Unavailable: prominent "no data" (but not alarming — it's just one mode)
        if (dl === "unavailable") {
          return (
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-40 backdrop-blur-lg bg-slate-950/80 border border-zinc-600/15 rounded-xl p-4 shadow-2xl max-w-sm text-center pointer-events-none" id="no-data-banner">
              <div className="text-zinc-400 text-sm font-bold mb-1">No data available</div>
              <div className="text-white/50 text-xs leading-relaxed">
                The {avail?.label?.toLowerCase() || "selected"} mode has no available evidence for this plot.
              </div>
              {l10.surfaceInventory && l10.activeSurfaceType && (
                <div className="text-white/30 text-[10px] mt-1.5 leading-snug">
                  {l10.surfaceInventory[l10.activeSurfaceType]?.reason || `No surface generated.`}
                </div>
              )}
            </div>
          );
        }

        return null;
      })()}

      {/* --- EXISTING DEBUG OVERLAYS & ZONE CHIPS --- */}
      <NdviDebugOverlay
        surfaceData={surfaceData}
        plotGeoJson={plotGeoJson}
        viewState={viewState}
        containerRef={containerRef}
        enabled={debugNdvi}
      />

      {/* Debug toggle button — always visible in bottom-left above SIRE badge */}
      <button
        onClick={() => setDebugNdvi(v => !v)}
        className="absolute bottom-12 left-2 z-50 flex items-center gap-1 px-2 py-1 rounded text-xs font-mono cursor-pointer select-none"
        style={{
          background: debugNdvi ? '#facc15' : 'rgba(0,0,0,0.7)',
          color: debugNdvi ? '#000' : '#facc15',
          border: '1px solid #facc15',
        }}
      >
        🔬 NDVI
      </button>

      {/* Stats panel when debug is active */}
      {debugNdvi && surfaceData?.values && (
        <div
          className="absolute z-50 font-mono text-xs rounded p-2 pointer-events-none"
          style={{
            bottom: '48px',
            left: '60px',
            background: 'rgba(0,0,0,0.85)',
            border: '1px solid #facc15',
            color: '#fff',
            minWidth: '200px',
          }}
        >
          <div style={{ color: '#facc15', fontWeight: 'bold', marginBottom: 4 }}>
            NDVI Surface Debug
          </div>
          <div>Surface: <span style={{ color: '#86efac' }}>{surfaceData.type}</span></div>
          <div>Grid: <span style={{ color: '#86efac' }}>{surfaceData.values.length} × {surfaceData.values[0]?.length ?? 0}</span></div>
          {(() => {
            const flat = surfaceData.values.flatMap(row => row.filter((v): v is number => v != null));
            if (!flat.length) return <div style={{ color: '#f87171' }}>No valid cells</div>;
            const mn = Math.min(...flat), mx = Math.max(...flat);
            const avg = flat.reduce((a, b) => a + b, 0) / flat.length;
            const std = Math.sqrt(flat.reduce((a, b) => a + (b - avg) ** 2, 0) / flat.length);
            return (
              <>
                <div>Min: <span style={{ color: '#f87171' }}>{mn.toFixed(4)}</span></div>
                <div>Max: <span style={{ color: '#86efac' }}>{mx.toFixed(4)}</span></div>
                <div>Mean: <span style={{ color: '#fde68a' }}>{avg.toFixed(4)}</span></div>
                <div>Std: <span style={{ color: '#c4b5fd' }}>{std.toFixed(4)}</span></div>
                <div>Cells: <span style={{ color: '#94a3b8' }}>{flat.length}</span></div>
                <div>visualContrastMode: <span style={{ color: '#38bdf8' }}>hybrid_absolute_local</span></div>
                <div>colorRange: <span style={{ color: '#38bdf8' }}>[-0.1, 1.0]</span></div>
                <div>valueStd: <span style={{ color: '#38bdf8' }}>{std.toFixed(4)}</span></div>
                <div>colorStdBefore: <span style={{ color: '#38bdf8' }}>{(std * 2.0).toFixed(4)}</span></div>
                <div>colorStdAfter: <span style={{ color: '#38bdf8' }}>{(std * 2.5).toFixed(4)}</span></div>
                <div>forceUniform: <span style={{ color: '#38bdf8' }}>{activeModeAvailability?.renderKind === "uniform_tint" || activeModeAvailability?.displayLevel === "plot_level" ? "true" : "false"}</span></div>
              </>
            );
          })()}
        </div>
      )}

      {hoveredZoneData && (
        <ZoneChip
          label={hoveredZoneData.label}
          confidence={hoveredZoneData.confidence}
          areaFraction={hoveredZoneData.areaFraction}
          severity={hoveredZoneData.severity}
          primaryDriver={hoveredZoneData.primaryDriver}
          centroid={hoveredZoneData.centroid}
          viewState={viewState}
        />
      )}

      {/* Render persistent pinned chip for selected zone */}
      {selectedZoneData && (
        <ZoneChip
          label={selectedZoneData.label}
          confidence={selectedZoneData.confidence}
          areaFraction={selectedZoneData.areaFraction}
          severity={selectedZoneData.severity}
          primaryDriver={selectedZoneData.primaryDriver}
          centroid={selectedZoneData.centroid}
          viewState={viewState}
        />
      )}
    </div>
  );
}
