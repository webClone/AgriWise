import test from "node:test";
import assert from "node:assert/strict";
import {
  generateContourGridData,
  resolveContourGridBounds,
} from "../../src/components/farm/map/layers/contour-grid-bounds.mjs";

test("P01-F03: Contour coordinates correctly georeference asymmetric MultiPolygon across full raster grid", () => {
  // Island 1: (10.0, 36.0) to (10.01, 36.01)
  // Island 2: (10.05, 36.05) to (10.06, 36.06) - strictly outside Island 1's envelope
  const multiPolygonGeoJson = {
    type: "Feature",
    geometry: {
      type: "MultiPolygon",
      coordinates: [
        // Island 1
        [
          [
            [10.0, 36.0],
            [10.01, 36.0],
            [10.01, 36.01],
            [10.0, 36.01],
            [10.0, 36.0],
          ],
        ],
        // Island 2 (completely outside Island 1 envelope)
        [
          [
            [10.05, 36.05],
            [10.06, 36.05],
            [10.06, 36.06],
            [10.05, 36.06],
            [10.05, 36.05],
          ],
        ],
      ],
    },
  };

  const gridBounds = [10.0, 36.0, 10.06, 36.06]; // [minLng, minLat, maxLng, maxLat]
  const w = 6;
  const h = 6;

  // Build a 6x6 grid where cell (r=5, c=0) corresponds to Island 1,
  // and cell (r=0, c=5) corresponds to Island 2.
  const values = Array.from({ length: h }, () => Array(w).fill(null));
  values[5][0] = 0.75; // Island 1 (bottom-left)
  values[0][5] = 0.85; // Island 2 (top-right)

  const surfaceData = {
    type: "NDVI_CLEAN",
    values,
    render_range: [0, 1],
    grid_spec: {
      bounds: gridBounds,
      width: w,
      height: h,
      crs: "EPSG:4326",
    },
  };

  // 1. With explicit gridBounds
  const data = generateContourGridData({
    plotId: "asymmetric-islands-explicit",
    surfaceData,
    plotGeoJson: multiPolygonGeoJson,
    gridBounds,
  });

  assert.equal(data.length, 2, "Both Island 1 and Island 2 cells should be within field boundary mask");

  const island1Point = data.find((d) => d.value === 0.75);
  const island2Point = data.find((d) => d.value === 0.85);

  assert.ok(island1Point, "Island 1 point must exist");
  assert.ok(island2Point, "Island 2 point must exist");

  // Verify Island 1 coordinates are near (10.005, 36.005)
  assert.ok(
    island1Point.position[0] >= 10.0 && island1Point.position[0] <= 10.015,
    `Island 1 lng must be in [10.0, 10.015], got ${island1Point.position[0]}`
  );
  assert.ok(
    island1Point.position[1] >= 36.0 && island1Point.position[1] <= 36.015,
    `Island 1 lat must be in [36.0, 36.015], got ${island1Point.position[1]}`
  );

  // CRITICAL CHECK FOR F03:
  // Island 2 coordinates must be in Island 2's true geographic location (> 10.04 lng, > 36.04 lat),
  // NEVER distorted or clamped into Island 1's bounds (which were <= 10.01)
  assert.ok(
    island2Point.position[0] >= 10.045 && island2Point.position[0] <= 10.065,
    `Island 2 lng must be in [10.045, 10.065], got ${island2Point.position[0]}`
  );
  assert.ok(
    island2Point.position[1] >= 36.045 && island2Point.position[1] <= 36.065,
    `Island 2 lat must be in [36.045, 36.065], got ${island2Point.position[1]}`
  );

  // 2. Without explicit gridBounds (resolved automatically from surfaceData.grid_spec)
  const dataResolved = generateContourGridData({
    plotId: "asymmetric-islands-resolved",
    surfaceData,
    plotGeoJson: multiPolygonGeoJson,
  });

  assert.equal(dataResolved.length, 2, "Resolved bounds must also yield 2 valid points");

  const resolvedIsland2 = dataResolved.find((d) => d.value === 0.85);
  assert.ok(
    resolvedIsland2.position[0] >= 10.045,
    `Resolved Island 2 lng must be > 10.045, got ${resolvedIsland2.position[0]}`
  );
  assert.ok(
    resolvedIsland2.position[1] >= 36.045,
    `Resolved Island 2 lat must be > 36.045, got ${resolvedIsland2.position[1]}`
  );

  // 3. Without grid_spec bounds: resolves from entire MultiPolygon envelope
  const surfaceWithoutGridSpec = {
    type: "NDVI_CLEAN",
    values,
    render_range: [0, 1],
  };
  const resolvedEnvelope = resolveContourGridBounds(null, surfaceWithoutGridSpec, multiPolygonGeoJson);
  assert.ok(resolvedEnvelope, "Envelope must resolve from full MultiPolygon geometry");
  assert.ok(resolvedEnvelope[0] <= 10.0, "Envelope minLng must cover Island 1");
  assert.ok(resolvedEnvelope[2] >= 10.06, "Envelope maxLng must cover Island 2");
});

test("P01 Hardening: Non-finite surface values (NaN, Infinity, -Infinity) are excluded from contour grid points", () => {
  const plotGeoJson = {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [10.0, 36.0],
          [10.1, 36.0],
          [10.1, 36.1],
          [10.0, 36.1],
          [10.0, 36.0],
        ],
      ],
    },
  };

  const values = [
    [0.5, NaN],
    [Infinity, -Infinity],
  ];

  const surfaceData = {
    type: "NDVI_CLEAN",
    values,
    render_range: [0, 1],
    grid_spec: {
      bounds: [10.0, 36.0, 10.1, 36.1],
      width: 2,
      height: 2,
      crs: "EPSG:4326",
    },
  };

  const gridData = generateContourGridData({
    plotId: "nonfinite-test",
    surfaceData,
    plotGeoJson,
  });

  // Only the single finite value (0.5) should be included
  assert.equal(gridData.length, 1, "Only finite surface values should be admitted into contour data");
  assert.equal(gridData[0].value, 0.5);
  assert.ok(Number.isFinite(gridData[0].position[0]));
  assert.ok(Number.isFinite(gridData[0].position[1]));
});

test("S02: Contour generation applies observed-pixel authorization and masking", () => {
  const plotGeoJson = {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [10.0, 36.0],
          [10.02, 36.0],
          [10.02, 36.02],
          [10.0, 36.02],
          [10.0, 36.0],
        ],
      ],
    },
  };

  const values = [
    [0.4, 0.8],
    [0.6, 0.9],
  ];

  const surfaceData = {
    type: "NDVI_CLEAN",
    values,
    render_range: [0, 1],
    grid_spec: {
      bounds: [10.0, 36.0, 10.02, 36.02],
      width: 2,
      height: 2,
      crs: "EPSG:4326",
    },
  };

  // 1. Unobserved pixel masking: only cells marked 1/true are included
  // Cell (0, 0) observed, Cell (0, 1) unobserved, Cell (1, 0) unobserved, Cell (1, 1) observed
  const observationMask = [
    [1, 0],
    [0, 1],
  ];

  const maskedGridData = generateContourGridData({
    plotId: "s02-mask-test",
    surfaceData,
    plotGeoJson,
    observationMask,
  });

  assert.equal(maskedGridData.length, 2, "Only the 2 observed pixels must be included");
  const valuesIncluded = maskedGridData.map((d) => d.value).sort();
  assert.deepEqual(valuesIncluded, [0.4, 0.9], "Unobserved pixels 0.8 and 0.6 must not influence contour generation");

  // 2. Negative control: requiresObservedMask is true but mask is missing -> fails closed
  const failClosedMissingMask = generateContourGridData({
    plotId: "s02-fail-closed-missing",
    surfaceData,
    plotGeoJson,
    requiresObservedMask: true,
  });
  assert.deepEqual(failClosedMissingMask, [], "Must fail closed (empty array) when required mask is missing");

  // 3. Negative control: requiresObservedMask is true and mask is empty -> fails closed
  const failClosedEmptyMask = generateContourGridData({
    plotId: "s02-fail-closed-empty",
    surfaceData,
    plotGeoJson,
    observationMask: [],
    requiresObservedMask: true,
  });
  assert.deepEqual(failClosedEmptyMask, [], "Must fail closed when required mask is empty array");

  // 4. Negative control: authorized is false -> fails closed
  const unauthorizedData = generateContourGridData({
    plotId: "s02-unauthorized",
    surfaceData,
    plotGeoJson,
    observationMask,
    authorized: false,
  });
  assert.deepEqual(unauthorizedData, [], "Must fail closed when authorized is false");

  // 5. Positive control: requiresObservedMask is true and mask is provided -> succeeds with observed cells
  const validRequiredMask = generateContourGridData({
    plotId: "s02-valid-required",
    surfaceData,
    plotGeoJson,
    observationMask,
    requiresObservedMask: true,
  });
  assert.equal(validRequiredMask.length, 2, "Must succeed and return observed cells when required mask is valid");
});
