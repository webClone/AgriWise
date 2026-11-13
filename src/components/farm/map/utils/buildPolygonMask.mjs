const maskCache = new Map();

function extractPolygons(geometry) {
  if (!geometry) return [];
  const geom = geometry.geometry || geometry;
  if (!geom.type || !geom.coordinates) return [];

  if (geom.type === "Polygon") {
    if (!Array.isArray(geom.coordinates) || geom.coordinates.length === 0) return [];
    return [
      {
        exterior: geom.coordinates[0] || [],
        holes: geom.coordinates.slice(1) || [],
      },
    ];
  }

  if (geom.type === "MultiPolygon") {
    if (!Array.isArray(geom.coordinates) || geom.coordinates.length === 0) return [];
    return geom.coordinates
      .map((polyCoords) => ({
        exterior: (Array.isArray(polyCoords) && polyCoords[0]) || [],
        holes: (Array.isArray(polyCoords) && polyCoords.slice(1)) || [],
      }))
      .filter((p) => p.exterior.length > 0);
  }

  return [];
}

function isPointInRing(pt, ring, crossesAntiMeridian) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    let xi = ring[i][0];
    let yi = ring[i][1];
    let xj = ring[j][0];
    let yj = ring[j][1];
    if (crossesAntiMeridian) {
      if (xi < 0) xi += 360;
      if (xj < 0) xj += 360;
    }

    const intersect = yi > pt[1] !== yj > pt[1] && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function isPointInPolygonWithHoles(pt, poly, crossesAntiMeridian) {
  // 1. Must be strictly inside exterior ring
  if (!isPointInRing(pt, poly.exterior, crossesAntiMeridian)) {
    return false;
  }
  // 2. Must NOT be inside any hole
  for (const hole of poly.holes) {
    if (isPointInRing(pt, hole, crossesAntiMeridian)) {
      return false;
    }
  }
  return true;
}

function isPointInPolygons(pt, polygons, crossesAntiMeridian) {
  for (const poly of polygons) {
    if (isPointInPolygonWithHoles(pt, poly, crossesAntiMeridian)) {
      return true;
    }
  }
  return false;
}

/**
 * Builds a 2D masked array using Point-In-Polygon Ray-Casting supporting
 * both Polygon with interior holes and MultiPolygon multi-island geometries.
 *
 * Returns a typed Uint8Array (0 = outside, 1 = inside) representing the raster grid
 * mapping directly to physical field boundaries.
 */
export function buildPolygonMask(plotId, width, height, plotGeoJson, gridBounds) {
  if (!plotGeoJson || width <= 0 || height <= 0) return null;

  const polygons = extractPolygons(plotGeoJson);
  if (polygons.length === 0) return null;

  // Geometry identity binding for the cache
  const geometryHash =
    plotGeoJson.geometryHash ||
    plotGeoJson.geometry_hash ||
    plotGeoJson.properties?.geometryHash ||
    plotGeoJson.properties?.geometry_hash ||
    plotGeoJson.geometryVersion ||
    plotGeoJson.properties?.geometryVersion ||
    "";
  const boundsKey = gridBounds?.map((value) => Number(value).toFixed(8)).join(",") || "plot-envelope";
  const cacheKey = `${plotId || "noid"}:${geometryHash}:${width}x${height}:${boundsKey}`;

  if (maskCache.has(cacheKey)) {
    return maskCache.get(cacheKey) || null;
  }

  try {
    let minLng = Infinity;
    let maxLng = -Infinity;
    let minLat = Infinity;
    let maxLat = -Infinity;
    let rawMinLng = Infinity;
    let rawMaxLng = -Infinity;

    for (const poly of polygons) {
      for (const pt of poly.exterior) {
        if (pt[0] < rawMinLng) rawMinLng = pt[0];
        if (pt[0] > rawMaxLng) rawMaxLng = pt[0];
      }
    }
    const crossesAntiMeridian = rawMaxLng - rawMinLng > 180;

    for (const poly of polygons) {
      for (const ring of [poly.exterior, ...poly.holes]) {
        for (const pt of ring) {
          let lng = pt[0];
          if (crossesAntiMeridian && lng < 0) {
            lng += 360;
          }
          if (lng < minLng) minLng = lng;
          if (lng > maxLng) maxLng = lng;
          if (pt[1] < minLat) minLat = pt[1];
          if (pt[1] > maxLat) maxLat = pt[1];
        }
      }
    }

    if (gridBounds) {
      const [gridMinLng, gridMinLat, gridMaxLng, gridMaxLat] = gridBounds.map(Number);
      if (
        [gridMinLng, gridMinLat, gridMaxLng, gridMaxLat].every(Number.isFinite) &&
        gridMaxLng > gridMinLng &&
        gridMaxLat > gridMinLat
      ) {
        minLng = gridMinLng;
        minLat = gridMinLat;
        maxLng = gridMaxLng;
        maxLat = gridMaxLat;
      } else {
        return null;
      }
    }

    // Pre-allocate binary mask
    const mask = new Uint8Array(width * height);
    const latDiff = maxLat - minLat;
    const lngDiff = maxLng - minLng;

    let ptr = 0;
    for (let r = 0; r < height; r++) {
      for (let c = 0; c < width; c++) {
        // Physical center of the cell
        const lat = maxLat - (r / height) * latDiff - latDiff / (2 * height);
        let lng = minLng + (c / width) * lngDiff + lngDiff / (2 * width);
        if (crossesAntiMeridian && lng < 0) {
          lng += 360;
        }

        mask[ptr++] = isPointInPolygons([lng, lat], polygons, crossesAntiMeridian) ? 1 : 0;
      }
    }

    const result = { data: mask, width, height };
    if (maskCache.size > 50) maskCache.clear();
    maskCache.set(cacheKey, result);

    return result;
  } catch (e) {
    console.error("Failed building polygon mask", e);
    return null;
  }
}
