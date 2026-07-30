import { bbox as turfBbox, pointOnFeature } from "@turf/turf";

export type PlotPoint = { lat: number; lng: number };

export type PlotSpatialContext = PlotPoint & {
  polygon: unknown | null;
};

export type Wgs84Bounds = [number, number, number, number];

export function isValidWgs84Point(point: PlotPoint | null | undefined): point is PlotPoint {
  return Boolean(
    point
      && Number.isFinite(point.lat)
      && Number.isFinite(point.lng)
      && point.lat >= -90
      && point.lat <= 90
      && point.lng >= -180
      && point.lng <= 180,
  );
}

export function parsePlotGeoJson(value: unknown): unknown | null {
  if (!value) return null;
  if (typeof value !== "string") return value;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function asFeature(value: any): any | null {
  if (!value || typeof value !== "object") return null;
  if (value.type === "Feature" && value.geometry) return value;
  if (value.type === "Polygon" || value.type === "MultiPolygon") {
    return { type: "Feature", properties: {}, geometry: value };
  }
  if (value.geometry) return asFeature(value.geometry);
  return null;
}

/** Return a deterministic point guaranteed to lie on/in the plot geometry. */
export function getPlotRepresentativePoint(
  geoJson: any,
  fallback?: PlotPoint,
): PlotPoint | null {
  try {
    const feature = asFeature(geoJson);
    if (feature) {
      const turfPoint = pointOnFeature(feature as any);
      const [lng, lat] = turfPoint.geometry.coordinates;
      const location = { lat, lng };
      if (isValidWgs84Point(location)) return location;
    }
  } catch {
    // The caller's explicit fallback is preferable to an invented coordinate.
  }
  if (isValidWgs84Point(fallback)) {
    return fallback;
  }
  return null;
}

/** Resolve the only spatial payload an upstream scientific service may receive. */
export function getAuthoritativePlotSpatialContext(
  geoJson: unknown,
  farmLatitude: number | null | undefined,
  farmLongitude: number | null | undefined,
): PlotSpatialContext | null {
  const polygon = parsePlotGeoJson(geoJson);
  const farmPoint = {
    lat: Number(farmLatitude),
    lng: Number(farmLongitude),
  };
  const point = getPlotRepresentativePoint(
    polygon,
    isValidWgs84Point(farmPoint) ? farmPoint : undefined,
  );
  return point ? { ...point, polygon } : null;
}

/** Return an authoritative WGS84 envelope, or a small farm-point envelope. */
export function getPlotWgs84Bounds(
  geoJson: unknown,
  fallback?: PlotPoint,
): Wgs84Bounds | null {
  const parsed = parsePlotGeoJson(geoJson);
  try {
    if (parsed && typeof parsed === "object") {
      const values = turfBbox(parsed as any);
      const bounds = values.map(Number) as Wgs84Bounds;
      if (
        bounds.length === 4
        && bounds.every(Number.isFinite)
        && bounds[0] >= -180
        && bounds[2] <= 180
        && bounds[1] >= -90
        && bounds[3] <= 90
        && bounds[0] <= bounds[2]
        && bounds[1] <= bounds[3]
      ) return bounds;
    }
  } catch {
    // A valid explicit farm point can still provide a bounded visual vicinity.
  }
  if (!isValidWgs84Point(fallback)) return null;
  const margin = 0.02;
  return [
    Math.max(-180, fallback.lng - margin),
    Math.max(-90, fallback.lat - margin),
    Math.min(180, fallback.lng + margin),
    Math.min(90, fallback.lat + margin),
  ];
}

/** Bound provider tiles to the requested plot's local vicinity. */
export function isLocalPlotBounds(
  requested: Wgs84Bounds,
  plotBounds: Wgs84Bounds,
  marginDegrees = 0.1,
): boolean {
  if (
    requested.some((value) => !Number.isFinite(value))
    || requested[0] < -180
    || requested[2] > 180
    || requested[1] < -90
    || requested[3] > 90
    || requested[0] >= requested[2]
    || requested[1] >= requested[3]
    || requested[2] - requested[0] > 0.5
    || requested[3] - requested[1] > 0.5
  ) return false;
  return !(
    requested[2] < plotBounds[0] - marginDegrees
    || requested[0] > plotBounds[2] + marginDegrees
    || requested[3] < plotBounds[1] - marginDegrees
    || requested[1] > plotBounds[3] + marginDegrees
  );
}
