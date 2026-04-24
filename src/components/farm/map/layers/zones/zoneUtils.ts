import { ZoneData } from "@/hooks/useLayer10";

export interface DeckZoneFeature {
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  geometry: any;
  properties: {
    zoneId: string;
    zoneType: string;
    zoneFamily: "diagnostic" | "action" | "trust";
    severity: number;
    confidence: number;
    topDrivers: string[];
    isSelected: boolean;
    isHovered: boolean;
    hasSourceDominance: boolean;
    areaFraction: number;
    isInferred: boolean;
    calculationTrace?: Record<string, unknown>;
    centroid: [number, number]; // [lng, lat] for label placement
    label?: string;
    evidenceAgeDays?: number | null;
  };
}

export function categorizeZoneFamily(zoneType: string, backendFamily?: string): "diagnostic" | "action" | "trust" {
  // Prefer explicit backend family when available
  if (backendFamily) {
    const f = backendFamily.toUpperCase();
    if (f === "TRUST") return "trust";
    if (f === "DECISION") return "action";
    // AGRONOMIC and STRUCTURAL both map to diagnostic
    return "diagnostic";
  }
  // Fallback to string inference
  const t = zoneType.toLowerCase();
  
  if (t.includes("uncertain") || t.includes("verify") || t.includes("trust") || t.includes("confidence")) {
    return "trust";
  }
  
  if (t.includes("action") || t.includes("improve") || t.includes("intervene")) {
    return "action";
  }
  
  return "diagnostic";
}

// ── Point type ───────────────────────────────────────────────────────────────
type Pt = [number, number];

// ── Sutherland-Hodgman polygon clipping ──────────────────────────────────────

function _lineIntersect(a: Pt, b: Pt, c: Pt, d: Pt): Pt {
  const a1 = b[1] - a[1], b1 = a[0] - b[0], c1 = a1 * a[0] + b1 * a[1];
  const a2 = d[1] - c[1], b2 = c[0] - d[0], c2 = a2 * c[0] + b2 * c[1];
  const det = a1 * b2 - a2 * b1;
  if (Math.abs(det) < 1e-14) return a;
  return [(c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det];
}

function _isInside(p: Pt, edgeStart: Pt, edgeEnd: Pt): boolean {
  return (edgeEnd[0] - edgeStart[0]) * (p[1] - edgeStart[1]) -
         (edgeEnd[1] - edgeStart[1]) * (p[0] - edgeStart[0]) >= 0;
}

function sutherlandHodgmanClip(subject: Pt[], clip: Pt[]): Pt[] {
  if (subject.length === 0 || clip.length === 0) return [];

  let output = [...subject];
  for (let i = 0; i < clip.length; i++) {
    if (output.length === 0) return [];
    const edgeStart = clip[i];
    const edgeEnd = clip[(i + 1) % clip.length];
    const input = output;
    output = [];

    for (let j = 0; j < input.length; j++) {
      const curr = input[j];
      const prev = input[(j + input.length - 1) % input.length];
      const currInside = _isInside(curr, edgeStart, edgeEnd);
      const prevInside = _isInside(prev, edgeStart, edgeEnd);

      if (currInside) {
        if (!prevInside) {
          output.push(_lineIntersect(prev, curr, edgeStart, edgeEnd));
        }
        output.push(curr);
      } else if (prevInside) {
        output.push(_lineIntersect(prev, curr, edgeStart, edgeEnd));
      }
    }
  }
  return output;
}

// ── Geometry smoothing pipeline ──────────────────────────────────────────────

/**
 * Chaikin's corner-cutting algorithm — smooths a polygon by replacing each
 * vertex with two points at 25%/75% along each edge. Each iteration doubles
 * vertex count and rounds corners progressively.
 */
function chaikinSmooth(ring: Pt[], iterations: number = 2): Pt[] {
  let pts = ring;
  for (let iter = 0; iter < iterations; iter++) {
    const smoothed: Pt[] = [];
    const n = pts.length;
    for (let i = 0; i < n; i++) {
      const curr = pts[i];
      const next = pts[(i + 1) % n];
      // Q = 3/4 * curr + 1/4 * next
      smoothed.push([
        0.75 * curr[0] + 0.25 * next[0],
        0.75 * curr[1] + 0.25 * next[1],
      ]);
      // R = 1/4 * curr + 3/4 * next
      smoothed.push([
        0.25 * curr[0] + 0.75 * next[0],
        0.25 * curr[1] + 0.75 * next[1],
      ]);
    }
    pts = smoothed;
  }
  return pts;
}

/**
 * Douglas-Peucker simplification — removes redundant vertices from a polygon
 * ring while preserving shape within the given epsilon tolerance.
 */
function douglasPeuckerSimplify(ring: Pt[], epsilon: number): Pt[] {
  if (ring.length <= 3) return ring;

  // Find the point farthest from the line between first and last
  let maxDist = 0;
  let maxIdx = 0;
  const first = ring[0];
  const last = ring[ring.length - 1];

  for (let i = 1; i < ring.length - 1; i++) {
    const d = _pointLineDistance(ring[i], first, last);
    if (d > maxDist) {
      maxDist = d;
      maxIdx = i;
    }
  }

  if (maxDist > epsilon) {
    const left = douglasPeuckerSimplify(ring.slice(0, maxIdx + 1), epsilon);
    const right = douglasPeuckerSimplify(ring.slice(maxIdx), epsilon);
    return [...left.slice(0, -1), ...right];
  }

  return [first, last];
}

function _pointLineDistance(p: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return Math.sqrt((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2);
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / lenSq));
  const projX = a[0] + t * dx;
  const projY = a[1] + t * dy;
  return Math.sqrt((p[0] - projX) ** 2 + (p[1] - projY) ** 2);
}

/**
 * Merge adjacent cells into contiguous outlines using a marching-squares-style
 * boundary tracing algorithm. Returns one outline polygon per connected group.
 *
 * For each connected component of cells:
 *   1. Build a cell occupancy set
 *   2. Walk the boundary edges (edges between occupied and unoccupied cells)
 *   3. Convert cell-edge coordinates to geo coordinates
 *   4. Clip against field polygon, smooth, and simplify
 */
function mergeAndOutlineCells(
  cellIndices: [number, number][],
  gridH: number,
  gridW: number,
  minLng: number,
  maxLng: number,
  minLat: number,
  maxLat: number,
  fieldRing: Pt[]
): Pt[][] {
  if (cellIndices.length === 0) return [];

  const latStep = (maxLat - minLat) / gridH;
  const lngStep = (maxLng - minLng) / gridW;

  // Build occupancy set for O(1) lookup
  const occupied = new Set<string>();
  for (const [r, c] of cellIndices) {
    occupied.add(`${r},${c}`);
  }

  // ── Find connected components via flood-fill ──
  const visited = new Set<string>();
  const components: [number, number][][] = [];

  for (const [r, c] of cellIndices) {
    const key = `${r},${c}`;
    if (visited.has(key)) continue;

    // BFS flood-fill
    const component: [number, number][] = [];
    const queue: [number, number][] = [[r, c]];
    visited.add(key);

    while (queue.length > 0) {
      const [cr, cc] = queue.shift()!;
      component.push([cr, cc]);

      // 4-connected neighbors
      for (const [dr, dc] of [[0, 1], [0, -1], [1, 0], [-1, 0]] as [number, number][]) {
        const nr = cr + dr;
        const nc = cc + dc;
        const nk = `${nr},${nc}`;
        if (occupied.has(nk) && !visited.has(nk)) {
          visited.add(nk);
          queue.push([nr, nc]);
        }
      }
    }

    components.push(component);
  }

  // ── Trace boundary for each component ──
  const outlines: Pt[][] = [];

  for (const component of components) {
    if (component.length === 0) continue;

    const compSet = new Set<string>(component.map(([r, c]) => `${r},${c}`));

    // Collect all boundary edge segments
    // Each segment is a pair of grid-corner coordinates [col, row] in grid space
    type Edge = { x1: number; y1: number; x2: number; y2: number };
    const edges: Edge[] = [];

    for (const [r, c] of component) {
      // Top edge (between row r and r-1)
      if (!compSet.has(`${r - 1},${c}`)) {
        edges.push({ x1: c, y1: r, x2: c + 1, y2: r });
      }
      // Bottom edge
      if (!compSet.has(`${r + 1},${c}`)) {
        edges.push({ x1: c + 1, y1: r + 1, x2: c, y2: r + 1 });
      }
      // Left edge
      if (!compSet.has(`${r},${c - 1}`)) {
        edges.push({ x1: c, y1: r + 1, x2: c, y2: r });
      }
      // Right edge
      if (!compSet.has(`${r},${c + 1}`)) {
        edges.push({ x1: c + 1, y1: r, x2: c + 1, y2: r + 1 });
      }
    }

    if (edges.length === 0) continue;

    // Chain edges into a ring by matching endpoints
    const edgeMap = new Map<string, Edge[]>();
    for (const e of edges) {
      const startKey = `${e.x1},${e.y1}`;
      if (!edgeMap.has(startKey)) edgeMap.set(startKey, []);
      edgeMap.get(startKey)!.push(e);
    }

    // Walk edges to form ordered ring(s)
    const usedEdges = new Set<number>();
    const rings: Pt[][] = [];

    for (let startIdx = 0; startIdx < edges.length; startIdx++) {
      if (usedEdges.has(startIdx)) continue;

      const ring: Pt[] = [];
      let currentEdge = edges[startIdx];
      usedEdges.add(startIdx);
      ring.push(gridToGeo(currentEdge.x1, currentEdge.y1, minLng, maxLat, lngStep, latStep));

      const startPt = `${currentEdge.x1},${currentEdge.y1}`;
      let endPt = `${currentEdge.x2},${currentEdge.y2}`;
      let iterations = 0;
      const maxIter = edges.length + 10;

      while (endPt !== startPt && iterations < maxIter) {
        iterations++;
        ring.push(gridToGeo(currentEdge.x2, currentEdge.y2, minLng, maxLat, lngStep, latStep));

        // Find next edge starting from current endpoint
        const candidates = edgeMap.get(endPt);
        if (!candidates) break;

        let found = false;
        for (const candidate of candidates) {
          const idx = edges.indexOf(candidate);
          if (idx >= 0 && !usedEdges.has(idx)) {
            usedEdges.add(idx);
            currentEdge = candidate;
            endPt = `${candidate.x2},${candidate.y2}`;
            found = true;
            break;
          }
        }
        if (!found) break;
      }

      if (ring.length >= 3) {
        rings.push(ring);
      }
    }

    // Take the largest ring as the main outline
    if (rings.length === 0) continue;
    const mainRing = rings.reduce((a, b) => a.length >= b.length ? a : b);

    // Clip against field polygon
    const clipped = sutherlandHodgmanClip(mainRing, fieldRing);
    if (clipped.length < 3) continue;

    // Smooth with Chaikin (2 iterations)
    const smoothed = chaikinSmooth(clipped, 3);

    // Compute adaptive epsilon based on cell size for simplification
    const cellDiag = Math.sqrt(lngStep ** 2 + latStep ** 2);
    const epsilon = cellDiag * 0.08; // Keep shape accuracy within 8% of cell diagonal

    // Simplify to remove excessive vertices from smoothing
    const simplified = douglasPeuckerSimplify(smoothed, epsilon);

    if (simplified.length >= 3) {
      outlines.push(simplified);
    }
  }

  return outlines;
}

/** Convert grid-space corner coordinate to geo coordinate */
function gridToGeo(
  gridCol: number, gridRow: number,
  minLng: number, maxLat: number,
  lngStep: number, latStep: number
): Pt {
  return [
    minLng + gridCol * lngStep,  // longitude
    maxLat - gridRow * latStep,  // latitude (grid row 0 = top = maxLat)
  ];
}

// ── Public API ───────────────────────────────────────────────────────────────

/**
 * Convert cell indices into smoothed, merged MultiPolygon coordinates.
 * Replaces the old per-cell rectangle approach with organic contour shapes.
 */
export function cellIndicesToMultiPolygon(
  cellIndices: [number, number][],
  gridH: number,
  gridW: number,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson: any
): number[][][][] {
  if (cellIndices.length === 0 || !plotGeoJson) return [];

  // Extract field polygon ring (without closing dup) for clipping
  const rawCoords: number[][] = plotGeoJson.geometry.type === 'MultiPolygon'
    ? plotGeoJson.geometry.coordinates[0][0]
    : plotGeoJson.geometry.coordinates[0];

  // Remove closing duplicate if present
  const fieldRing: Pt[] = rawCoords.length > 0 &&
    rawCoords[0][0] === rawCoords[rawCoords.length - 1][0] &&
    rawCoords[0][1] === rawCoords[rawCoords.length - 1][1]
    ? rawCoords.slice(0, -1).map(c => [c[0], c[1]] as Pt)
    : rawCoords.map(c => [c[0], c[1]] as Pt);

  let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
  fieldRing.forEach((c) => {
    if (c[0] < minLng) minLng = c[0];
    if (c[0] > maxLng) maxLng = c[0];
    if (c[1] < minLat) minLat = c[1];
    if (c[1] > maxLat) maxLat = c[1];
  });

  // Merge cells into contiguous outlines, then smooth
  const outlines = mergeAndOutlineCells(
    cellIndices, gridH, gridW,
    minLng, maxLng, minLat, maxLat,
    fieldRing
  );

  // Convert to GeoJSON MultiPolygon coordinate format
  return outlines.map(outline => {
    // Close ring for GeoJSON
    const ring = [...outline.map(p => [p[0], p[1]]), [outline[0][0], outline[0][1]]];
    return [ring];
  });
}

/**
 * Compute the weighted centroid of a GeoJSON MultiPolygon feature.
 * Returns [lng, lat] for label placement.
 */
export function computeZoneCentroid(feature: DeckZoneFeature): [number, number] {
  const coords = feature.geometry?.coordinates;
  if (!coords || coords.length === 0) return [0, 0];

  let sumLng = 0, sumLat = 0, count = 0;

  for (const polygon of coords) {
    if (!polygon[0]) continue;
    const ring = polygon[0]; // exterior ring
    for (const pt of ring) {
      sumLng += pt[0];
      sumLat += pt[1];
      count++;
    }
  }

  return count > 0 ? [sumLng / count, sumLat / count] : [0, 0];
}

export function formatZoneGeoJson(
  zones: ZoneData[], 
  selectedZoneId?: string | null,
  gridH?: number,
  gridW?: number,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson?: any,
  hoveredZoneId?: string | null,
) {
  const activeZones = zones.filter(z => 
    z.cell_indices && z.cell_indices.length > 0 && gridH && gridW && plotGeoJson
  );
  
  const features = activeZones.map(z => {
    const multiPolygonCoords = cellIndicesToMultiPolygon(z.cell_indices, gridH!, gridW!, plotGeoJson);
    
    const feature: DeckZoneFeature = {
      type: "Feature",
      geometry: {
        type: "MultiPolygon",
        coordinates: multiPolygonCoords
      },
      properties: {
        zoneId: z.zone_id,
        zoneType: z.zone_type,
        zoneFamily: categorizeZoneFamily(z.zone_type, (z as unknown as Record<string, unknown>).zone_family as string | undefined),
        severity: z.severity,
        confidence: z.confidence,
        topDrivers: z.top_drivers,
        isSelected: z.zone_id === selectedZoneId,
        isHovered: z.zone_id === hoveredZoneId,
        hasSourceDominance: !!z.source_dominance && z.source_dominance !== "Mixed",
        areaFraction: z.area_fraction,
        isInferred: !!z.is_inferred,
        calculationTrace: z.calculation_trace,
        centroid: [0, 0], // placeholder — computed below
        label: z.label,
        evidenceAgeDays: z.evidence_age_days ?? null,
      }
    };

    // Compute centroid for label placement
    feature.properties.centroid = computeZoneCentroid(feature);

    return feature;
  });

  return {
    type: "FeatureCollection",
    features,
  };
}
