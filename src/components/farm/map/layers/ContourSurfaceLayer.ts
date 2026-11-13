"use client";

import { ContourLayer } from "@deck.gl/aggregation-layers";
import { SurfaceData } from "@/hooks/useLayer10";
import { buildPolygonMask } from "../utils/buildPolygonMask";

export function getContourSurfaceLayer({
  id = "surface-contours",
  plotId,
  surfaceData,
  plotGeoJson,
  visible = true
}: {
  id?: string;
  plotId?: string;
  surfaceData?: SurfaceData | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson?: any;
  visible?: boolean;
}) {
  if (!visible || !surfaceData || !plotGeoJson || !surfaceData.values) return null;

  const h = surfaceData.values.length;
  if (h === 0) return null;
  const w = surfaceData.values[0].length;
  if (w === 0) return null;

  // Extract coords for bounding box
  const coords = plotGeoJson.geometry.type === 'MultiPolygon'
    ? plotGeoJson.geometry.coordinates[0][0]
    : plotGeoJson.geometry.coordinates[0];

  let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
  const lngs = coords.map((c: any) => c[0]);
  const rawMinLng = Math.min(...lngs);
  const rawMaxLng = Math.max(...lngs);
  const crossesAntiMeridian = (rawMaxLng - rawMinLng) > 180;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  coords.forEach((c: any) => {
    let lng = c[0];
    if (crossesAntiMeridian && lng < 0) {
      lng += 360;
    }
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
    if (c[1] < minLat) minLat = c[1];
    if (c[1] > maxLat) maxLat = c[1];
  });

  const latDiff = maxLat - minLat;
  const lngDiff = maxLng - minLng;

  // Utilize globally cached high-perf binary polygon mask for this plot.
  // Fail-closed: contour generation strictly requires a valid field boundary mask.
  const mask = buildPolygonMask(plotId, w, h, plotGeoJson);
  if (!mask) {
    console.warn(`[ContourSurfaceLayer] Critical: Polygon boundary mask unavailable for plot ${plotId}; failing closed.`);
    return [];
  }

  const gridData = [];
  let maskPtr = 0;
  for (let r = 0; r < h; r++) {
    for (let c = 0; c < w; c++) {
      const val = surfaceData.values[r][c];

      // Strict gating: drop the pixel if NO-DATA or masked out of field boundary
      if (val !== null && val !== undefined && mask.data[maskPtr] === 1) {
        let lng = minLng + (c / w) * lngDiff + (lngDiff / (2 * w));
        const lat = maxLat - (r / h) * latDiff - (latDiff / (2 * h));
        
        if (crossesAntiMeridian && lng > 180) {
          lng -= 360;
        }

        gridData.push({
          position: [lng, lat],
          value: val // Send the actual raw value over to deck's CPU contour generation
        });
      }
      maskPtr++;
    }
  }

  // To build contour thresholds, we look at the render range
  const [minV, maxV] = surfaceData.render_range || [0, 1];
  const step = (maxV - minV) / 5;
  const thresholds = [];
  for(let i=1; i<5; i++) {
    thresholds.push(minV + step * i);
  }

  return new ContourLayer({
    id,
    data: gridData,
    pickable: false,
    getPosition: (d: { position: [number, number]; value: number }) => d.position,
    getWeight: (d: { position: [number, number]; value: number }) => d.value,
    contours: thresholds.map((t, idx) => ({
      threshold: t,
      // Slightly more opaque as value increases
      color: [255, 255, 255, 70 + (idx * 30)], 
      strokeWidth: 2
    })),
    // Roughly 10 meter aggregate cells for smooth contours
    cellSize: 10,
  });
}
