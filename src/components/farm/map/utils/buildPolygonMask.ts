export interface RasterMask {
  data: Uint8Array;
  width: number;
  height: number;
}

const maskCache = new Map<string, RasterMask>();

/**
 * Builds a 2D masked array using the Point-In-Polygon Ray-Casting algorithm.
 * 
 * Returns a typed Uint8Array (0 = outside, 1 = inside) representing the raster grid
 * mapping directly to the physical field boundaries. This significantly optimizes rendering
 * by evaluating the polygon collision only ONCE prior to loops.
 */
export function buildPolygonMask(
  plotId: string | undefined, // Added plotId for caching
  width: number, 
  height: number, 
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson: any | null | undefined
): RasterMask | null {
  if (!plotGeoJson || width <= 0 || height <= 0) return null;

  const cacheKey = `${plotId}-${width}-${height}`;
  if (plotId && maskCache.has(cacheKey)) {
    return maskCache.get(cacheKey) || null;
  }

  try {
    const coords = plotGeoJson.geometry.type === 'MultiPolygon' 
      ? plotGeoJson.geometry.coordinates[0][0] 
      : plotGeoJson.geometry.coordinates[0];
  
    if (!coords || coords.length === 0) return null;
  
    let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    coords.forEach((c: any) => {
      if (c[0] < minLng) minLng = c[0];
      if (c[0] > maxLng) maxLng = c[0];
      if (c[1] < minLat) minLat = c[1];
      if (c[1] > maxLat) maxLat = c[1];
    });
  
    // Pre-allocate binary mask
    const mask = new Uint8Array(width * height);
    
    const latDiff = maxLat - minLat;
    const lngDiff = maxLng - minLng;
  
    const isInside = (pt: [number, number], polygon: number[][]) => {
      let inside = false;
      for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
          const xi = polygon[i][0], yi = polygon[i][1];
          const xj = polygon[j][0], yj = polygon[j][1];
          
          const intersect = ((yi > pt[1]) !== (yj > pt[1]))
              && (pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi);
          if (intersect) inside = !inside;
      }
      return inside;
    };
  
    let ptr = 0;
    for (let r = 0; r < height; r++) {
      for (let c = 0; c < width; c++) {
        // Physical center of the cell
        const lat = maxLat - (r / height) * latDiff - (latDiff / (2 * height));
        const lng = minLng + (c / width) * lngDiff + (lngDiff / (2 * width));
        
        mask[ptr++] = isInside([lng, lat], coords) ? 1 : 0;
      }
    }
  
    const result = { data: mask, width, height };
    if (plotId) {
      if (maskCache.size > 20) maskCache.clear(); // rough eviction
      maskCache.set(cacheKey, result);
    }
    
    return result;
  } catch (e) {
    console.error("Failed building polygon mask", e);
    return null;
  }
}
