import test from "node:test";
import assert from "node:assert/strict";
import { validateSurfaceGrid } from "../../src/lib/agribrain/render-materialization.mjs";

test("Batch B: validateSurfaceGrid accepts valid north-up, unrotated affine transforms", () => {
  const width = 10;
  const height = 10;
  const minLng = 2.650;
  const maxLng = 2.660;
  const minLat = 36.500;
  const maxLat = 36.510;

  const dx = (maxLng - minLng) / width;   // 0.001 (positive)
  const dy = -(maxLat - minLat) / height; // -0.001 (negative, north-up)
  const x0 = minLng;
  const y0 = maxLat;

  const surface = {
    surface_id: "surf-test-valid",
    values: Array(height).fill(null).map(() => Array(width).fill(0.42)),
    grid_spec: {
      crs: "EPSG:4326",
      bounds: [minLng, minLat, maxLng, maxLat],
      width,
      height,
      transform: [x0, dx, 0, y0, 0, dy],
    },
  };

  const res = validateSurfaceGrid(surface);
  assert.equal(res.valid, true);
  assert.equal(res.reason, "grid_valid");
  assert.deepEqual(res.bounds, [minLng, minLat, maxLng, maxLat]);
  assert.equal(res.width, width);
  assert.equal(res.height, height);

  // Cell centers agreement check:
  // For column c and row r, verify that GDAL affine cell center equals bounds-based interpolation center
  for (let r = 0; r < height; r++) {
    for (let c = 0; c < width; c++) {
      const affineLng = x0 + (c + 0.5) * dx;
      const affineLat = y0 + (r + 0.5) * dy;

      const interpLng = minLng + ((c + 0.5) / width) * (maxLng - minLng);
      const interpLat = maxLat - ((r + 0.5) / height) * (maxLat - minLat);

      assert.ok(Math.abs(affineLng - interpLng) < 1e-9, `Column ${c} lng center mismatch`);
      assert.ok(Math.abs(affineLat - interpLat) < 1e-9, `Row ${r} lat center mismatch`);
    }
  }
});

test("Batch B: validateSurfaceGrid rejects south-up affine transforms (dy > 0)", () => {
  const width = 10;
  const height = 10;
  const minLng = 2.650;
  const maxLng = 2.660;
  const minLat = 36.500;
  const maxLat = 36.510;

  const dx = (maxLng - minLng) / width;
  const dy = (maxLat - minLat) / height; // Positive dy -> south-up!
  const x0 = minLng;
  const y0 = minLat;

  const surface = {
    surface_id: "surf-test-south-up",
    values: Array(height).fill(null).map(() => Array(width).fill(0.42)),
    grid_spec: {
      crs: "EPSG:4326",
      bounds: [minLng, minLat, maxLng, maxLat],
      width,
      height,
      transform: [x0, dx, 0, y0, 0, dy],
    },
  };

  const res = validateSurfaceGrid(surface);
  assert.equal(res.valid, false);
  assert.equal(res.reason, "grid_spec_affine_orientation_not_north_up");
});

test("Batch B: validateSurfaceGrid rejects rotated or sheared affine transforms (rx != 0 or ry != 0)", () => {
  const width = 10;
  const height = 10;
  const minLng = 2.650;
  const maxLng = 2.660;
  const minLat = 36.500;
  const maxLat = 36.510;

  const dx = (maxLng - minLng) / width;
  const dy = -(maxLat - minLat) / height;
  const x0 = minLng;
  const y0 = maxLat;

  // Case 1: rx != 0 (rotated)
  const surfaceRotated = {
    surface_id: "surf-test-rotated",
    values: Array(height).fill(null).map(() => Array(width).fill(0.42)),
    grid_spec: {
      crs: "EPSG:4326",
      bounds: [minLng, minLat, maxLng, maxLat],
      width,
      height,
      transform: [x0, dx, 0.0005, y0, 0, dy],
    },
  };
  const resRot = validateSurfaceGrid(surfaceRotated);
  assert.equal(resRot.valid, false);
  assert.equal(resRot.reason, "grid_spec_affine_rotated_or_sheared");

  // Case 2: ry != 0 (sheared)
  const surfaceSheared = {
    surface_id: "surf-test-sheared",
    values: Array(height).fill(null).map(() => Array(width).fill(0.42)),
    grid_spec: {
      crs: "EPSG:4326",
      bounds: [minLng, minLat, maxLng, maxLat],
      width,
      height,
      transform: [x0, dx, 0, y0, 0.0005, dy],
    },
  };
  const resShear = validateSurfaceGrid(surfaceSheared);
  assert.equal(resShear.valid, false);
  assert.equal(resShear.reason, "grid_spec_affine_rotated_or_sheared");
});

test("Batch B: validateSurfaceGrid rejects dimension-inconsistent raster extent endpoints", () => {
  const width = 10;
  const height = 10;
  const minLng = 2.650;
  const maxLng = 2.660;
  const minLat = 36.500;
  const maxLat = 36.510;

  // dx is too small: 10 * 0.0005 = 0.005 instead of span 0.010!
  const dxInconsistent = 0.0005;
  const dy = -(maxLat - minLat) / height;
  const x0 = minLng;
  const y0 = maxLat;

  const surface = {
    surface_id: "surf-test-extent-mismatch",
    values: Array(height).fill(null).map(() => Array(width).fill(0.42)),
    grid_spec: {
      crs: "EPSG:4326",
      bounds: [minLng, minLat, maxLng, maxLat],
      width,
      height,
      transform: [x0, dxInconsistent, 0, y0, 0, dy],
    },
  };

  const res = validateSurfaceGrid(surface);
  assert.equal(res.valid, false);
  assert.equal(res.reason, "grid_spec_affine_extent_mismatch");
});

test("Batch B: validateSurfaceGrid rejects malformed or non-finite affine transforms", () => {
  const surfaceInvalid = {
    surface_id: "surf-test-invalid",
    values: [[0.5, 0.6], [0.7, 0.8]],
    grid_spec: {
      crs: "EPSG:4326",
      bounds: [2.65, 36.50, 2.66, 36.51],
      width: 2,
      height: 2,
      transform: [2.65, 0.005, NaN, 36.51, 0, -0.005],
    },
  };
  const res = validateSurfaceGrid(surfaceInvalid);
  assert.equal(res.valid, false);
  assert.equal(res.reason, "grid_spec_affine_invalid");
});
