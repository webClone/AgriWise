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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  coords.forEach((c: any) => {
    if (c[0] < minLng) minLng = c[0];
    if (c[0] > maxLng) maxLng = c[0];
    if (c[1] < minLat) minLat = c[1];
    if (c[1] > maxLat) maxLat = c[1];
  });

  const latDiff = maxLat - minLat;
  const lngDiff = maxLng - minLng;

  // Utilize globally cached high-perf binary polygon mask for this plot
  const mask = buildPolygonMask(plotId, w, h, plotGeoJson);

  const gridData = [];
  let maskPtr = 0;
  for (let r = 0; r < h; r++) {
    for (let c = 0; c < w; c++) {
      const val = surfaceData.values[r][c];

      // Strict gating: we drop the pixel from contour consideration if NO-DATA or masked out
      if (val !== null && val !== undefined && (!mask || mask.data[maskPtr] === 1)) {
        const lng = minLng + (c / w) * lngDiff + (lngDiff / (2 * w));
        const lat = maxLat - (r / h) * latDiff - (latDiff / (2 * h));

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
