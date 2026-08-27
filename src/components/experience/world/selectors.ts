import worldData from "./illustrative-world.v1.json";
import type { IllustrativeWorld, WorldFarm, WorldPlot, WorldPortfolio, WorldRegion } from "./schema";
import { validateIllustrativeWorld } from "./validation";
import { ILLUSTRATIVE_RUN } from "../scientific-run/selectors";

export const ILLUSTRATIVE_WORLD = worldData as unknown as IllustrativeWorld;

// Validate on module load
const valResult = validateIllustrativeWorld(ILLUSTRATIVE_WORLD);
if (!valResult.valid) {
  console.error("[AgriWise World Validator Error]", valResult.errors);
}

/* ── Precomputed Prepared World Cache ──────────────────────── */

export interface BoundingBox {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface PreparedEntity {
  id: string;
  name: string;
  bounds: [[number, number], [number, number]]; // [[west, south], [east, north]]
  centroid: [number, number]; // [lng, lat]
  hullCoordinates: [number, number][];
  cumulativeLengths: number[];
  totalLength: number;
}

class PreparedWorldCache {
  plotMap = new Map<string, WorldPlot>();
  farmMap = new Map<string, WorldFarm>();
  portfolioMap = new Map<string, WorldPortfolio>();
  regionMap = new Map<string, WorldRegion>();
  
  preparedPlots = new Map<string, PreparedEntity>();
  preparedFarms = new Map<string, PreparedEntity>();
  preparedPortfolios = new Map<string, PreparedEntity>();
  preparedRegions = new Map<string, PreparedEntity>();
  preparedCountry!: PreparedEntity;

  constructor(world: IllustrativeWorld) {
    // 1. Index Entities
    world.plots.forEach((p) => {
      this.plotMap.set(p.id, p);
      this.preparedPlots.set(p.id, this.createPreparedPlot(p));
    });

    world.farms.forEach((f) => {
      this.farmMap.set(f.id, f);
    });

    world.portfolios.forEach((pf) => {
      this.portfolioMap.set(pf.id, pf);
    });

    world.regions.forEach((r) => {
      this.regionMap.set(r.id, r);
      this.preparedRegions.set(r.id, this.createPreparedRegion(r));
    });

    // 2. Precompute Derived Farm Hulls & Bounds
    world.farms.forEach((f) => {
      this.preparedFarms.set(f.id, this.createDerivedFarm(f));
    });

    // 3. Precompute Derived Portfolio Centroids & Bounds
    world.portfolios.forEach((pf) => {
      this.preparedPortfolios.set(pf.id, this.createDerivedPortfolio(pf));
    });

    // 4. Country
    this.preparedCountry = this.createPreparedPolygon(
      world.country.id,
      world.country.name,
      world.country.coordinates
    );
  }

  private getBoundsAndCentroid(coords: [number, number][]): {
    bounds: [[number, number], [number, number]];
    centroid: [number, number];
  } {
    let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
    let sumX = 0, sumY = 0;

    for (const [lng, lat] of coords) {
      if (lng < w) w = lng;
      if (lng > e) e = lng;
      if (lat < s) s = lat;
      if (lat > n) n = lat;
      sumX += lng;
      sumY += lat;
    }

    const count = coords.length || 1;
    return {
      bounds: [[w, s], [e, n]],
      centroid: [sumX / count, sumY / count],
    };
  }

  private computeLengths(coords: [number, number][]): {
    cumulativeLengths: number[];
    totalLength: number;
  } {
    const cumulativeLengths: number[] = [0];
    let totalLength = 0;
    for (let i = 1; i < coords.length; i++) {
      const [x1, y1] = coords[i - 1];
      const [x2, y2] = coords[i];
      const dist = Math.hypot(x2 - x1, y2 - y1);
      totalLength += dist;
      cumulativeLengths.push(totalLength);
    }
    return { cumulativeLengths, totalLength };
  }

  private createPreparedPlot(p: WorldPlot): PreparedEntity {
    const { bounds, centroid } = this.getBoundsAndCentroid(p.coordinates);
    const { cumulativeLengths, totalLength } = this.computeLengths(p.coordinates);
    return {
      id: p.id,
      name: p.name,
      bounds,
      centroid,
      hullCoordinates: p.coordinates,
      cumulativeLengths,
      totalLength,
    };
  }

  private createPreparedRegion(r: WorldRegion): PreparedEntity {
    const { bounds, centroid } = this.getBoundsAndCentroid(r.coordinates);
    const { cumulativeLengths, totalLength } = this.computeLengths(r.coordinates);
    return {
      id: r.id,
      name: r.name,
      bounds,
      centroid,
      hullCoordinates: r.coordinates,
      cumulativeLengths,
      totalLength,
    };
  }

  private createPreparedPolygon(id: string, name: string, coords: [number, number][]): PreparedEntity {
    const { bounds, centroid } = this.getBoundsAndCentroid(coords);
    const { cumulativeLengths, totalLength } = this.computeLengths(coords);
    return {
      id,
      name,
      bounds,
      centroid,
      hullCoordinates: coords,
      cumulativeLengths,
      totalLength,
    };
  }

  private computeConvexHull(points: [number, number][]): [number, number][] {
    if (points.length <= 3) return points;

    // Sort points lexicographically
    const sorted = [...points].sort((a, b) => (a[0] !== b[0] ? a[0] - b[0] : a[1] - b[1]));

    const cross = (o: [number, number], a: [number, number], b: [number, number]) =>
      (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);

    // Build lower hull
    const lower: [number, number][] = [];
    for (const p of sorted) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
        lower.pop();
      }
      lower.push(p);
    }

    // Build upper hull
    const upper: [number, number][] = [];
    for (let i = sorted.length - 1; i >= 0; i--) {
      const p = sorted[i];
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
        upper.pop();
      }
      upper.push(p);
    }

    // Omit last point of each half because it's repeated at start of other half
    upper.pop();
    lower.pop();

    const hull = lower.concat(upper);
    if (hull.length > 0) {
      hull.push(hull[0]); // Close ring
    }
    return hull;
  }

  private createDerivedFarm(f: WorldFarm): PreparedEntity {
    // Prefer authored envelope if available, otherwise compute convex hull of child plots
    let farmHull: [number, number][];
    let coordsForBounds: [number, number][];

    if (f.envelopeCoordinates && f.envelopeCoordinates.length > 2) {
      farmHull = f.envelopeCoordinates;
      coordsForBounds = f.envelopeCoordinates;
    } else {
      const childCoords: [number, number][] = [];
      for (const pId of f.plotIds) {
        const plot = this.plotMap.get(pId);
        if (plot) childCoords.push(...plot.coordinates);
      }
      coordsForBounds = childCoords;
      farmHull = this.computeConvexHull(childCoords);
    }

    const { bounds, centroid } = this.getBoundsAndCentroid(coordsForBounds);
    const { cumulativeLengths, totalLength } = this.computeLengths(farmHull);

    return {
      id: f.id,
      name: f.name,
      bounds,
      centroid,
      hullCoordinates: farmHull,
      cumulativeLengths,
      totalLength,
    };
  }

  private createDerivedPortfolio(pf: WorldPortfolio): PreparedEntity {
    const childCoords: [number, number][] = [];
    for (const fId of pf.farmIds) {
      const preparedFarm = this.preparedFarms.get(fId);
      if (preparedFarm) childCoords.push(...preparedFarm.hullCoordinates);
    }

    const { bounds, centroid } = this.getBoundsAndCentroid(childCoords);
    const portfolioHull = this.computeConvexHull(childCoords);
    const { cumulativeLengths, totalLength } = this.computeLengths(portfolioHull);

    return {
      id: pf.id,
      name: pf.name,
      bounds,
      centroid,
      hullCoordinates: portfolioHull,
      cumulativeLengths,
      totalLength,
    };
  }
}

export const PREPARED_WORLD = new PreparedWorldCache(ILLUSTRATIVE_WORLD);

/** Slice precomputed entity boundary coordinates by progress 0.0 -> 1.0 */
export function slicePathByProgress(entity: PreparedEntity, progress: number): [number, number][] {
  if (progress <= 0 || entity.hullCoordinates.length === 0) return [];
  if (progress >= 1) return entity.hullCoordinates;

  const targetDist = progress * entity.totalLength;
  const sliced: [number, number][] = [entity.hullCoordinates[0]];

  for (let i = 1; i < entity.hullCoordinates.length; i++) {
    const currDist = entity.cumulativeLengths[i];
    if (currDist < targetDist) {
      sliced.push(entity.hullCoordinates[i]);
    } else {
      const prevDist = entity.cumulativeLengths[i - 1];
      const segLen = currDist - prevDist;
      const segT = segLen > 0 ? (targetDist - prevDist) / segLen : 0;
      const [x1, y1] = entity.hullCoordinates[i - 1];
      const [x2, y2] = entity.hullCoordinates[i];
      sliced.push([x1 + (x2 - x1) * segT, y1 + (y2 - y1) * segT]);
      break;
    }
  }

  return sliced;
}

/* ── Typed Selectors ───────────────────────────────────────── */

export function selectPlot(plotId: string): WorldPlot | undefined {
  return PREPARED_WORLD.plotMap.get(plotId);
}

export function selectFarm(farmId: string): WorldFarm | undefined {
  return PREPARED_WORLD.farmMap.get(farmId);
}

export function selectPortfolio(portfolioId: string): WorldPortfolio | undefined {
  return PREPARED_WORLD.portfolioMap.get(portfolioId);
}

export function selectRegion(regionId: string): WorldRegion | undefined {
  return PREPARED_WORLD.regionMap.get(regionId);
}

export function selectPreparedEntity(entityId: string): PreparedEntity | undefined {
  return (
    PREPARED_WORLD.preparedPlots.get(entityId) ||
    PREPARED_WORLD.preparedFarms.get(entityId) ||
    PREPARED_WORLD.preparedPortfolios.get(entityId) ||
    PREPARED_WORLD.preparedRegions.get(entityId) ||
    (entityId === ILLUSTRATIVE_WORLD.country.id ? PREPARED_WORLD.preparedCountry : undefined)
  );
}

/**
 * Returns parent lineage chain: [plotId, farmId, portfolioId, regionId, countryId]
 */
export function selectPlotLineage(plotId: string): [string, string, string, string, string] {
  if (plotId === ILLUSTRATIVE_WORLD.meta.primaryPlotId) {
    return ILLUSTRATIVE_WORLD.meta.primaryLineage;
  }

  const plot = PREPARED_WORLD.plotMap.get(plotId);
  const farm = plot ? PREPARED_WORLD.farmMap.get(plot.farmId) : undefined;
  const portfolio = farm ? PREPARED_WORLD.portfolioMap.get(farm.portfolioId) : undefined;
  const region = portfolio ? PREPARED_WORLD.regionMap.get(portfolio.regionId) : undefined;

  return [
    plotId,
    farm?.id || "FARM-04",
    portfolio?.id || "PORTFOLIO-02",
    region?.id || "REGION-MITIDJA",
    ILLUSTRATIVE_WORLD.country.id,
  ];
}

/**
 * Selector combining world geometry with scientific run state
 */
export function selectPlotVisualState(plotId: string) {
  const plot = selectPlot(plotId);
  const manifest = ILLUSTRATIVE_RUN.manifest;

  return {
    plotId: plot?.id || plotId,
    name: plot?.name || manifest.cropContext.cropName,
    crop: manifest.cropContext.cropName,
    status: manifest.demoStatus,
    coordinates: plot?.coordinates || [],
  };
}
