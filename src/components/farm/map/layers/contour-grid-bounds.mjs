import { buildPolygonMask } from "../utils/buildPolygonMask.mjs";

/**
 * Resolves the geographic bounding box [minLng, minLat, maxLng, maxLat]
 * for contour rendering.
 *
 * 1. Priority 1: Caller-provided validated gridBounds.
 * 2. Priority 2: SurfaceData grid_spec bounds (committed raster specification).
 * 3. Priority 3: Fallback to full polygon/MultiPolygon envelope across all islands.
 */
export function resolveContourGridBounds(gridBounds, surfaceData, plotGeoJson) {
  if (
    gridBounds &&
    Array.isArray(gridBounds) &&
    gridBounds.length === 4 &&
    gridBounds.every(Number.isFinite) &&
    gridBounds[2] > gridBounds[0] &&
    gridBounds[3] > gridBounds[1]
  ) {
    return [gridBounds[0], gridBounds[1], gridBounds[2], gridBounds[3]];
  }

  // Priority 2: surfaceData.grid_spec.bounds
  const spec =
    surfaceData?.grid_spec ||
    surfaceData?.display_grid_spec ||
    surfaceData?.provenance?.grid_spec ||
    surfaceData?.provenance?.display_grid_spec;
  if (spec && Array.isArray(spec.bounds) && spec.bounds.length === 4) {
    const [minLng, minLat, maxLng, maxLat] = spec.bounds.map(Number);
    if (
      Number.isFinite(minLng) &&
      Number.isFinite(minLat) &&
      Number.isFinite(maxLng) &&
      Number.isFinite(maxLat) &&
      maxLng > minLng &&
      maxLat > minLat
    ) {
      return [minLng, minLat, maxLng, maxLat];
    }
  }

  // Priority 3: Fallback across ALL MultiPolygon islands and rings
  const geom = plotGeoJson?.geometry || plotGeoJson;
  if (!geom || !geom.coordinates) return null;

  let allCoords = [];
  if (geom.type === "Polygon") {
    allCoords = (geom.coordinates || []).flat();
  } else if (geom.type === "MultiPolygon") {
    allCoords = (geom.coordinates || []).flat(2);
  }

  if (allCoords.length === 0) return null;

  let minLng = Infinity;
  let maxLng = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  const rawMinLng = Math.min(...allCoords.map((c) => c[0]));
  const rawMaxLng = Math.max(...allCoords.map((c) => c[0]));
  const crossesAntiMeridian = rawMaxLng - rawMinLng > 180;

  for (const c of allCoords) {
    let lng = c[0];
    if (crossesAntiMeridian && lng < 0) lng += 360;
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
    if (c[1] < minLat) minLat = c[1];
    if (c[1] > maxLat) maxLat = c[1];
  }

  if (
    !Number.isFinite(minLng) ||
    !Number.isFinite(minLat) ||
    !Number.isFinite(maxLng) ||
    !Number.isFinite(maxLat) ||
    maxLng <= minLng ||
    maxLat <= minLat
  ) {
    return null;
  }

  return [minLng, minLat, maxLng, maxLat];
}

/**
 * Builds the array of contour grid points [{ position: [lng, lat], value }]
 * by mapping 2D raster cells into the validated geographic gridBounds,
 * masked against field boundary (MultiPolygon & holes).
 */
export function generateContourGridData({
  plotId,
  surfaceData,
  plotGeoJson,
  gridBounds,
}) {
  if (!surfaceData || !plotGeoJson || !surfaceData.values) return [];

  const h = surfaceData.values.length;
  if (h === 0) return [];
  const w = surfaceData.values[0].length;
  if (w === 0) return [];

  const resolvedBounds = resolveContourGridBounds(gridBounds, surfaceData, plotGeoJson);
  if (!resolvedBounds) {
    console.warn(`[ContourSurfaceLayer] Could not resolve valid raster grid bounds for plot ${plotId}; failing closed.`);
    return [];
  }

  const [minLng, minLat, maxLng, maxLat] = resolvedBounds;
  const latDiff = maxLat - minLat;
  const lngDiff = maxLng - minLng;
  const crossesAntiMeridian = lngDiff > 180;

  // Mask must use the same raster grid bounds as the contour coordinates
  const mask = buildPolygonMask(plotId, w, h, plotGeoJson, resolvedBounds);
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
        let lng = minLng + (c / w) * lngDiff + lngDiff / (2 * w);
        const lat = maxLat - (r / h) * latDiff - latDiff / (2 * h);

        if (crossesAntiMeridian && lng > 180) {
          lng -= 360;
        }

        gridData.push({
          position: [lng, lat],
          value: val,
        });
      }
      maskPtr++;
    }
  }

  return gridData;
}
