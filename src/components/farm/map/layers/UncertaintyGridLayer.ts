"use client";

import { ScatterplotLayer } from "@deck.gl/layers";
import { SurfaceData } from "@/hooks/useLayer10";
import { buildPolygonMask } from "../utils/buildPolygonMask";

/**
 * Renders explicit visual markers (stipples/dots) in areas of HIGH uncertainty,
 * serving as a true secondary evidence layer overlaid on top of the main semantic surface.
 */
export function getUncertaintyGridLayer({
  id = "l10-uncertainty-markers",
  plotId,
  confidenceSurface,
  plotGeoJson,
  visible = true
}: {
  id?: string;
  plotId?: string;
  confidenceSurface?: SurfaceData | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson?: any;
  visible?: boolean;
}) {
  if (!visible || !confidenceSurface || !plotGeoJson || !confidenceSurface.values) return null;

  const h = confidenceSurface.values.length;
  if (h === 0) return null;
  const w = confidenceSurface.values[0].length;
  if (w === 0) return null;

  const coords = plotGeoJson.geometry.type === 'MultiPolygon' 
    ? plotGeoJson.geometry.coordinates[0][0] 
    : plotGeoJson.geometry.coordinates[0];

  let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  coords.forEach((c: any) => {
    if (c[0] < minLng) minLng = c[0];
    if (c[0] > maxLng) maxLng = c[0];
    if (c[1] < minLat) minLat = c[1];
    if (c[1] > maxLat) maxLat = c[1];
  });

  const latDiff = maxLat - minLat;
  const lngDiff = maxLng - minLng;
  
  const mask = buildPolygonMask(plotId, w, h, plotGeoJson);
  
  const markerData = [];
  for (let r = 0; r < h; r += 1) { // Process every pixel for a smooth continuous overlap
    for (let c = 0; c < w; c += 1) {
      const conf = confidenceSurface.values[r][c];
      
      const gridIdx = r * w + c;
      // Start applying subtle fog anywhere beneath 85% confidence, growing denser as trust drops
      if (conf !== null && conf !== undefined && conf < 0.85) { 
        const lng = minLng + (c / w) * lngDiff + (lngDiff / (2 * w));
        const lat = maxLat - (r / h) * latDiff - (latDiff / (2 * h));
        
        if (mask && mask.data[gridIdx] === 1) {
          markerData.push({
            position: [lng, lat],
            intensity: 1.0 - conf // Higher fog intensity for lower confidence
          });
        }
      }
    }
  }

  return new ScatterplotLayer({
    id,
    data: markerData,
    pickable: false,
    opacity: 0.25, // Soft fog base transparency
    stroked: false,
    filled: true,
    radiusScale: 1,
    radiusMinPixels: 12, // Substantial minimum radius ensures blobs overlap into a continuous cloud
    radiusMaxPixels: 35, // Clouds grow larger and blur further when zooming in
    getPosition: (d: { position: [number, number], intensity: number }) => d.position,
    // Radius swells as confidence drops
    getRadius: (d: { position: [number, number], intensity: number }) => Math.max(1, d.intensity * 25),
    // Deep slate-900 casts a shadow over the uncertainty, rather than glaring white/violet
    getFillColor: [15, 23, 42, 255], 
  });
}
