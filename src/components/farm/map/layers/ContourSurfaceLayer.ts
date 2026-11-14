"use client";

import { ContourLayer } from "@deck.gl/aggregation-layers";
import { SurfaceData } from "@/hooks/useLayer10";
import { buildPolygonMask } from "../utils/buildPolygonMask";
import { generateContourGridData, resolveContourGridBounds } from "./contour-grid-bounds.mjs";

export { resolveContourGridBounds, generateContourGridData };

export function getContourSurfaceLayer({
  id = "surface-contours",
  plotId,
  surfaceData,
  plotGeoJson,
  gridBounds,
  visible = true,
}: {
  id?: string;
  plotId?: string;
  surfaceData?: SurfaceData | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson?: any;
  gridBounds?: [number, number, number, number] | null;
  visible?: boolean;
}) {
  if (!visible || !surfaceData || !plotGeoJson || !surfaceData.values) return null;

  const h = surfaceData.values.length;
  if (h === 0) return null;
  const w = surfaceData.values[0].length;
  if (w === 0) return null;

  // Resolve bounds from validated raster grid specification.
  // Must encompass the full MultiPolygon raster extent rather than solely the first island.
  const resolvedBounds = resolveContourGridBounds(gridBounds, surfaceData, plotGeoJson);
  if (!resolvedBounds) {
    console.warn(`[ContourSurfaceLayer] Could not resolve valid raster grid bounds for plot ${plotId}; failing closed.`);
    return [];
  }

  // Utilize globally cached high-perf binary polygon mask for this plot.
  // Fail-closed: contour generation strictly requires a valid field boundary mask.
  const typedBounds = resolvedBounds as [number, number, number, number];
  const mask = buildPolygonMask(plotId, w, h, plotGeoJson, typedBounds);
  if (!mask) {
    console.warn(`[ContourSurfaceLayer] Critical: Polygon boundary mask unavailable for plot ${plotId}; failing closed.`);
    return [];
  }

  const gridData = generateContourGridData({
    plotId,
    surfaceData,
    plotGeoJson,
    gridBounds,
  });

  if (!gridData || gridData.length === 0) {
    return [];
  }

  // To build contour thresholds, we look at the render range
  const [minV, maxV] = surfaceData.render_range || [0, 1];
  const step = (maxV - minV) / 5;
  const thresholds = [];
  for (let i = 1; i < 5; i++) {
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
      color: [255, 255, 255, 70 + idx * 30],
      strokeWidth: 2,
    })),
    // Roughly 10 meter aggregate cells for smooth contours
    cellSize: 10,
  });
}
