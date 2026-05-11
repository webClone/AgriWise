"use client";

import { useMemo, useState, useRef, useEffect, useCallback } from "react";
import Map, { Source, Layer } from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";
import "maplibre-gl/dist/maplibre-gl.css";
import { SurfaceData, ZoneData } from "@/hooks/useLayer10";
import { usePlotFit } from "./usePlotFit";
import { SCENE_PROVIDERS, SceneProfile } from "./sceneProviders";
import { buildLayerStack } from "./buildLayerStack";
import ZoneChip from "./layers/zones/ZoneChip";
import { formatZoneGeoJson, computeZoneCentroid, DeckZoneFeature } from "./layers/zones/zoneUtils";

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
}

export default function PlotMapShell(props: PlotMapShellProps) {
  const {
    plots,
    activeMode,
    surfaceData,
    surfaceColors,
    confidenceSurface,
    reliabilitySurface,
    deviationSurface,
    l10Zones,
    selectedZone,
    detailMode = "farmer",
    onZoneClick,
  } = props;

  const primaryPlot = plots?.[0];
  const containerRef = useRef<HTMLDivElement>(null);
  
  // 1. Derive scene profile from map state (no stateful toggling)
  const sceneProfile: SceneProfile = useMemo(() => {
    if (!surfaceData || !activeMode) return "agro";  // No analysis active → full satellite
    return "analysis";  // Analysis layer active → dim basemap
  }, [surfaceData, activeMode]);

  // 2. Hover state for zone interactions
  const [hoveredZoneId, setHoveredZoneId] = useState<string | null>(null);

  // 3. Drive Camera using externalized Plot Fit logic
  const { viewState, setViewState, plotGeoJson, setDimensions } = usePlotFit({ primaryPlot, activeMode });

  useEffect(() => {
    if (!containerRef.current) return;
    
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry && entry.contentRect.width > 0 && entry.contentRect.height > 0) {
        setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    
    observer.observe(containerRef.current);
    
    return () => {
      observer.disconnect();
    };
  }, [setDimensions]);

  // Stable hover callback
  const handleZoneHover = useCallback((zoneId: string | null) => {
    setHoveredZoneId(zoneId);
  }, []);

  // 4. Build Layers dynamically using pure external helper
  const plotId = (primaryPlot?._id || primaryPlot?.id) as string | undefined;
  
  const { surfaceLayers, zoneLayers } = useMemo(() => buildLayerStack({
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
    onZoneClick,
    onZoneHover: handleZoneHover,
  }), [plotId, activeMode, surfaceData, surfaceColors, confidenceSurface, reliabilitySurface, deviationSurface, plotGeoJson, l10Zones, selectedZone, hoveredZoneId, detailMode, onZoneClick, handleZoneHover]);

  // Combine all layers — zones render on top of surfaces
  const allLayers = useMemo(() => [...surfaceLayers, ...zoneLayers], [surfaceLayers, zoneLayers]);

  // 5. Compute hovered zone centroid for floating chip
  const hoveredZoneData = useMemo(() => {
    if (!hoveredZoneId || !l10Zones || !surfaceData || !plotGeoJson) return null;
    
    const zone = l10Zones.find(z => z.zone_id === hoveredZoneId);
    if (!zone || zone.zone_id === selectedZone) return null;

    const fc = formatZoneGeoJson(
      [zone],
      null,
      surfaceData.values?.length || 8,
      surfaceData.values?.[0]?.length || 8,
      plotGeoJson,
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
  }, [hoveredZoneId, l10Zones, selectedZone, surfaceData, plotGeoJson]);

  // 6. Compute SELECTED zone centroid for persistent pinned chip on map
  const selectedZoneData = useMemo(() => {
    if (!selectedZone || !l10Zones || !surfaceData || !plotGeoJson) return null;
    
    const zone = l10Zones.find(z => z.zone_id === selectedZone);
    if (!zone) return null;

    const fc = formatZoneGeoJson(
      [zone],
      selectedZone,
      surfaceData.values?.length || 8,
      surfaceData.values?.[0]?.length || 8,
      plotGeoJson,
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
  }, [selectedZone, l10Zones, surfaceData, plotGeoJson]);

  return (
    <div ref={containerRef} className="absolute inset-0 w-full h-full bg-slate-950 overflow-hidden">
      <DeckGL
        style={{ mixBlendMode: 'multiply' }}
        viewState={viewState}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onViewStateChange={({ viewState }) => setViewState(viewState as any)}
        controller={true}
        layers={allLayers}
        getCursor={({ isHovering }) => isHovering ? "pointer" : "grab"}
      >
        <Map
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          mapStyle={SCENE_PROVIDERS[sceneProfile] as any}
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
              {/* Dual-stroke adaptive boundary: outer shadow + inner highlight */}
              {/* Outer: dark translucent shadow — reads on pale basemaps */}
              <Layer
                id="plot-glow-layer"
                type="line"
                paint={{
                  'line-color': 'rgba(20, 25, 30, 0.30)',
                  'line-width': selectedZone ? 2.5 : 3.5,
                  'line-blur': 3,
                  'line-opacity': selectedZone ? 0.25 : 0.50,
                }}
              />
              {/* Inner: light crisp hairline — reads on dark overlays */}
              <Layer
                id="plot-outline-layer"
                type="line"
                paint={{
                  'line-color': 'rgba(230, 235, 240, 0.65)',
                  'line-width': selectedZone ? 0.75 : 1.25,
                  'line-opacity': selectedZone ? 0.35 : 0.75,
                }}
              />
            </Source>
          )}
        </Map>
      </DeckGL>

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
