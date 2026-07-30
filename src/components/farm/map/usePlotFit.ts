"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { WebMercatorViewport } from "@deck.gl/core";
import * as turf from '@turf/turf';

// Clean the plot geometry
const simplifyPlotGeometry = (geojson: any) => {
  if (!geojson || !geojson.type) return geojson;
  
  return turf.simplify(geojson, {
    tolerance: 0.00001,     // Perfect for typical Algerian field sizes (adjust 0.00001–0.00005 if needed)
    highQuality: true
  });
};

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

interface UsePlotFitOptions {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  primaryPlot?: any; 
  paddingPct?: number; 
  defaultZoom?: number;
  activeMode?: string;
}

export function usePlotFit({ primaryPlot, paddingPct = 0.15, defaultZoom = 15, activeMode }: UsePlotFitOptions) {
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [viewState, setViewState] = useState<ViewState>({
    longitude: 3.05,
    latitude: 36.75,
    zoom: defaultZoom,
    pitch: 45,
    bearing: 0
  });

  // 1. Process Geometry to find center and bounding box
  const { plotGeoJson, bounds, center } = useMemo(() => {
    let geo = null;
    let minLng = -180, maxLng = 180, minLat = -90, maxLat = 90;
    let lat = 36.75, lng = 3.05;

    if (primaryPlot?.geoJson) {
      try {
        const parsed = typeof primaryPlot.geoJson === 'string' 
          ? JSON.parse(primaryPlot.geoJson) 
          : primaryPlot.geoJson;
        
        if (parsed?.geometry?.coordinates) {
          geo = simplifyPlotGeometry(parsed);
        }
        
        const coords = geo?.geometry?.type === 'MultiPolygon' 
            ? geo.geometry.coordinates[0][0] 
            : geo?.geometry?.coordinates[0];
        
        if (coords && coords.length > 0) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const lats = coords.map((c: any) => c[1]);
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const lngs = coords.map((c: any) => c[0]);
            
            minLng = Math.min(...lngs);
            maxLng = Math.max(...lngs);
            minLat = Math.min(...lats);
            maxLat = Math.max(...lats);

            lat = (minLat + maxLat) / 2;
            lng = (minLng + maxLng) / 2;
        }
      } catch (e) {
        console.error("GeoJSON parse error", e);
      }
    }

    return { 
      plotGeoJson: geo, 
      bounds: [[minLng, minLat], [maxLng, maxLat]] as [[number, number], [number, number]],
      center: { lat, lng }
    };
  }, [primaryPlot]);

  // 2. Compute fit based on dimensions and bounds
  const fitToPlot = useCallback((currentWidth: number, currentHeight: number) => {
    if (currentWidth <= 0 || currentHeight <= 0) return;
    if (bounds[0][0] === -180) return; // No valid bounds computed

    const effectivePaddingPct = activeMode === 'INSPECTION' ? paddingPct : 0.05;
    const dynamicPadding = Math.min(currentWidth, currentHeight) * effectivePaddingPct;
    const pitch = activeMode === 'INSPECTION' ? 45 : 0;

    try {
      const viewport = new WebMercatorViewport({ width: currentWidth, height: currentHeight });
      const fitted = viewport.fitBounds(bounds, { padding: dynamicPadding });
      
      setViewState(prev => ({
        ...prev,
        longitude: center.lng,
        latitude: center.lat,
        zoom: fitted.zoom,
        pitch
      }));
    } catch {
      // Fallback
      setViewState(prev => ({
        ...prev,
        longitude: center.lng,
        latitude: center.lat,
        zoom: 17.5,
        pitch
      }));
    }
  }, [bounds, center, paddingPct, activeMode]);

  // 3. Auto-fit when dimensions or primary plot changes
  useEffect(() => {
    if (dimensions.width > 0 && dimensions.height > 0) {
      fitToPlot(dimensions.width, dimensions.height);
    }
  }, [dimensions, fitToPlot]);

  return {
    viewState,
    setViewState,
    setDimensions,
    fitToPlot,
    plotGeoJson,
    bounds,
    center
  };
}
