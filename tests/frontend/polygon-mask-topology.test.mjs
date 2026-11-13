import test from "node:test";
import assert from "node:assert/strict";
import { buildPolygonMask } from "../../src/components/farm/map/utils/buildPolygonMask.mjs";

test("P01-G03: Polygon hole is masked out (value = 0 inside hole)", () => {
  // A 10x10 outer box from (0,0) to (10,10)
  // An inner hole from (3,3) to (7,7)
  const geoJsonWithHole = {
    type: "Polygon",
    geometryHash: "hash-v1",
    coordinates: [
      // Outer ring
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
        [0, 0],
      ],
      // Hole
      [
        [3, 3],
        [7, 3],
        [7, 7],
        [3, 7],
        [3, 3],
      ],
    ],
  };

  const gridBounds = [0, 0, 10, 10]; // minLng, minLat, maxLng, maxLat
  const mask = buildPolygonMask("plot-hole-test", 10, 10, geoJsonWithHole, gridBounds);

  assert.ok(mask !== null, "Mask should be computed successfully");
  assert.equal(mask.width, 10);
  assert.equal(mask.height, 10);

  // In a 10x10 raster over [0,0,10,10]:
  // Cell (c=1, r=1) corresponds to lat ~ 8.5, lng ~ 1.5 -> Inside outer, outside hole -> 1
  // Cell (c=5, r=5) corresponds to lat ~ 4.5, lng ~ 5.5 -> Inside hole -> 0
  const insideOuterIndex = 1 * 10 + 1; // (r=1, c=1)
  const insideHoleIndex = 5 * 10 + 5;  // (r=5, c=5)

  assert.equal(mask.data[insideOuterIndex], 1, "Cell outside the hole should be filled (1)");
  assert.equal(mask.data[insideHoleIndex], 0, "Cell inside the interior hole must be masked out (0)");
});

test("P01-G03: MultiPolygon fills second island", () => {
  // Island 1: [0, 0] to [4, 4]
  // Island 2: [6, 6] to [10, 10]
  const multiPoly = {
    type: "MultiPolygon",
    geometryHash: "multi-v1",
    coordinates: [
      // Island 1
      [
        [
          [0, 0],
          [4, 0],
          [4, 4],
          [0, 4],
          [0, 0],
        ],
      ],
      // Island 2
      [
        [
          [6, 6],
          [10, 6],
          [10, 10],
          [6, 10],
          [6, 6],
        ],
      ],
    ],
  };

  const gridBounds = [0, 0, 10, 10];
  const mask = buildPolygonMask("plot-multi-test", 10, 10, multiPoly, gridBounds);

  assert.ok(mask !== null, "MultiPolygon mask should be computed");

  // In 10x10:
  // Island 1 is bottom-left (r=8, c=2 corresponds to lat ~ 1.5, lng ~ 2.5) -> 1
  // Gap in between: (r=5, c=5 corresponds to lat ~ 4.5, lng ~ 5.5) -> 0
  // Island 2 is top-right (r=1, c=8 corresponds to lat ~ 8.5, lng ~ 8.5) -> 1
  const island1Index = 8 * 10 + 2;
  const gapIndex = 5 * 10 + 5;
  const island2Index = 1 * 10 + 8;

  assert.equal(mask.data[island1Index], 1, "First island must be filled (1)");
  assert.equal(mask.data[gapIndex], 0, "Space between islands must be 0");
  assert.equal(mask.data[island2Index], 1, "Second island must be filled (1)");
});

test("P01-G03: Geometry version/hash invalidates cached mask", () => {
  const plotId = "cached-plot-1";
  const bounds = [0, 0, 10, 10];

  // Initial version: full box [0,0] to [10,10]
  const v1 = {
    type: "Polygon",
    geometryHash: "sha256:v1111111111111111111111111111111",
    coordinates: [
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
        [0, 0],
      ],
    ],
  };

  const mask1 = buildPolygonMask(plotId, 4, 4, v1, bounds);
  assert.equal(mask1.data[0], 1, "v1 corner is inside");

  // Updated version: reduced box [5,5] to [10,10] (corner 0,0 is now outside)
  const v2 = {
    type: "Polygon",
    geometryHash: "sha256:v2222222222222222222222222222222",
    coordinates: [
      [
        [5, 5],
        [10, 5],
        [10, 10],
        [5, 10],
        [5, 5],
      ],
    ],
  };

  const mask2 = buildPolygonMask(plotId, 4, 4, v2, bounds);
  // Bottom-left cell (r=3, c=0) in [0,0,10,10] is lat ~ 1.25, lng ~ 1.25
  const bottomLeftIdx = 3 * 4 + 0;
  assert.equal(mask1.data[bottomLeftIdx], 1, "v1 bottom-left was inside");
  assert.equal(mask2.data[bottomLeftIdx], 0, "v2 bottom-left must be outside (0), cache invalidated");
});

test("P01-F01: Coordinate change WITHOUT any hash invalidates polygon mask cache", () => {
  const plotId = "coord-change-no-hash";
  const bounds = [0, 0, 10, 10];

  // Geom A: full box [0,0] to [10,10] with NO geometryHash/geometryVersion
  const geomA = {
    type: "Polygon",
    coordinates: [
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
        [0, 0],
      ],
    ],
  };

  const maskA = buildPolygonMask(plotId, 4, 4, geomA, bounds);
  assert.ok(maskA !== null);
  const bottomLeftIdx = 3 * 4 + 0;
  assert.equal(maskA.data[bottomLeftIdx], 1, "geomA bottom-left corner is inside (1)");

  // Geom B: coordinates moved to [5,5]-[10,10], still with NO geometryHash
  const geomB = {
    type: "Polygon",
    coordinates: [
      [
        [5, 5],
        [10, 5],
        [10, 10],
        [5, 10],
        [5, 5],
      ],
    ],
  };

  const maskB = buildPolygonMask(plotId, 4, 4, geomB, bounds);
  assert.ok(maskB !== null);
  assert.notEqual(maskA, maskB, "Mask reference must differ due to coordinate identity invalidation");
  assert.equal(maskB.data[bottomLeftIdx], 0, "geomB bottom-left corner must be outside (0), cache correctly invalidated");
});

test("P01-F01: Coordinate change with STALE/UNCHANGED hash invalidates polygon mask cache", () => {
  const plotId = "stale-hash-test";
  const bounds = [0, 0, 10, 10];
  const sameStaleHash = "sha256:same-stale-hash-v1";

  // Geom 1 with sameStaleHash: full box
  const geom1 = {
    type: "Polygon",
    geometryHash: sameStaleHash,
    coordinates: [
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
        [0, 0],
      ],
    ],
  };

  const mask1 = buildPolygonMask(plotId, 4, 4, geom1, bounds);
  const bottomLeftIdx = 3 * 4 + 0;
  assert.equal(mask1.data[bottomLeftIdx], 1, "geom1 bottom-left corner is inside (1)");

  // Geom 2 with THE EXACT SAME staleHash: coordinates moved
  const geom2 = {
    type: "Polygon",
    geometryHash: sameStaleHash,
    coordinates: [
      [
        [5, 5],
        [10, 5],
        [10, 10],
        [5, 10],
        [5, 5],
      ],
    ],
  };

  const mask2 = buildPolygonMask(plotId, 4, 4, geom2, bounds);
  assert.notEqual(mask1, mask2, "Mask reference must differ because coordinate hash changed");
  assert.equal(mask2.data[bottomLeftIdx], 0, "geom2 bottom-left must be 0 despite identical supplied hash");
});

test("P01-F01: Identical coordinates and bounds hit the mask cache", () => {
  const plotId = "cache-hit-test";
  const bounds = [0, 0, 10, 10];
  const geom = {
    type: "Polygon",
    coordinates: [
      [
        [1, 1],
        [8, 1],
        [8, 8],
        [1, 8],
        [1, 1],
      ],
    ],
  };

  const mask1 = buildPolygonMask(plotId, 6, 6, geom, bounds);
  const mask2 = buildPolygonMask(plotId, 6, 6, geom, bounds);
  assert.equal(mask1, mask2, "Identical request must return cached instance");
});

test("P01-F01: Grid bounds change invalidates polygon mask cache", () => {
  const plotId = "bounds-change-test";
  const geom = {
    type: "Polygon",
    coordinates: [
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
        [0, 0],
      ],
    ],
  };

  const bounds1 = [0, 0, 10, 10];
  const bounds2 = [0, 0, 20, 20];

  const mask1 = buildPolygonMask(plotId, 4, 4, geom, bounds1);
  const mask2 = buildPolygonMask(plotId, 4, 4, geom, bounds2);
  assert.notEqual(mask1, mask2, "Different bounds must produce different cache keys");
});

test("P01-F01: Invalid or empty geometry fails closed returning null", () => {
  assert.equal(buildPolygonMask("null-plot", 10, 10, null), null);
  assert.equal(buildPolygonMask("empty-plot", 10, 10, { type: "Polygon", coordinates: [] }), null);
  assert.equal(buildPolygonMask("invalid-dim", 0, 10, { type: "Polygon", coordinates: [[[0,0],[1,0],[1,1],[0,0]]] }), null);
});
