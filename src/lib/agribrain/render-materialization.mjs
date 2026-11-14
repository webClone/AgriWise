/**
 * Akaloris / AgriBrain — Surface Materialization & Raster Grid Validation (ESM)
 */

export const RENDER_AUTHORIZATION_VERSION = "v924_bc10_22r5_render_identity_v1";

export function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function getGridSpec(s) {
  if (!s) return null;
  const prov = s.provenance;
  return (
    s.display_grid_spec ||
    s.grid_spec ||
    prov?.grid_spec ||
    prov?.display_grid_spec ||
    null
  );
}

/**
 * Validate surface grid dimensions, values, bounds, CRS, and affine transform.
 * Enforces Batch B requirements:
 * 1. Unrotated & unsheared (rx == 0, ry == 0)
 * 2. North-up orientation (dx > 0, dy < 0)
 * 3. Origin alignment with bounds (x0 ~ minLng, y0 ~ maxLat)
 * 4. Extent consistency (x0 + width * dx ~ maxLng, y0 + height * dy ~ minLat)
 */
export function validateSurfaceGrid(surface, plotGeoJson) {
  if (!surface || !surface.values || !Array.isArray(surface.values) || surface.values.length === 0) {
    return { valid: false, reason: "surface_values_empty", bounds: null, width: null, height: null };
  }
  const height = surface.values.length;
  const firstRow = surface.values[0];
  if (!Array.isArray(firstRow) || firstRow.length === 0) {
    return { valid: false, reason: "surface_values_first_row_empty", bounds: null, width: null, height };
  }
  const width = firstRow.length;
  const isUniformRowLen = surface.values.every((row) => Array.isArray(row) && row.length === width);
  if (!isUniformRowLen) {
    return { valid: false, reason: "surface_values_non_rectangular", bounds: null, width: null, height };
  }

  // Reject all-null support
  let hasValidCell = false;
  for (const row of surface.values) {
    for (const v of row) {
      if (finiteNumber(v)) {
        hasValidCell = true;
        break;
      }
    }
    if (hasValidCell) break;
  }
  if (!hasValidCell) {
    return { valid: false, reason: "surface_values_all_null", bounds: null, width, height };
  }

  const spec = getGridSpec(surface);
  if (!spec || !spec.bounds || !Array.isArray(spec.bounds) || spec.bounds.length !== 4) {
    return { valid: false, reason: "grid_spec_bounds_invalid", bounds: null, width, height };
  }

  // Dimension parity check: reject metadata dimensions mismatching array dimensions
  if (spec.width !== undefined && spec.width !== width) {
    return { valid: false, reason: "grid_spec_dimensions_mismatch", bounds: null, width, height };
  }
  if (spec.height !== undefined && spec.height !== height) {
    return { valid: false, reason: "grid_spec_dimensions_mismatch", bounds: null, width, height };
  }

  const [minLng, minLat, maxLng, maxLat] = spec.bounds.map(Number);
  if (!Number.isFinite(minLng) || !Number.isFinite(minLat) || !Number.isFinite(maxLng) || !Number.isFinite(maxLat)) {
    return { valid: false, reason: "grid_spec_bounds_non_finite", bounds: null, width, height };
  }
  if (minLng >= maxLng || minLat >= maxLat) {
    return { valid: false, reason: "grid_spec_bounds_collapsed", bounds: null, width, height };
  }

  // Reject metric display bounds or non-geographic CRS for map layer rendering
  const crsStr = String(spec.crs || "").toUpperCase();
  const isGeographic = crsStr === "EPSG:4326" || crsStr === "WGS84" || crsStr === "OGC:CRS84" || !spec.crs;
  if (!isGeographic) {
    return { valid: false, reason: "display_bounds_non_geographic_crs", bounds: null, width, height };
  }
  if (minLng < -180 || maxLng > 180 || minLat < -90 || maxLat > 90) {
    return { valid: false, reason: "grid_spec_bounds_metric_crs_mismatch", bounds: null, width, height };
  }

  // Cross-validate affine transform against dimensions and bounds if present (Batch B)
  if (spec.transform !== undefined) {
    if (
      !Array.isArray(spec.transform) ||
      spec.transform.length !== 6 ||
      !spec.transform.every((v) => typeof v === "number" && Number.isFinite(v))
    ) {
      return { valid: false, reason: "grid_spec_affine_invalid", bounds: null, width, height };
    }
    const [x0, dx, rx, y0, ry, dy] = spec.transform;

    // 1. Require unrotated, unsheared transform
    if (Math.abs(rx) > 1e-7 || Math.abs(ry) > 1e-7) {
      return { valid: false, reason: "grid_spec_affine_rotated_or_sheared", bounds: null, width, height };
    }

    // 2. Require north-up orientation: dx > 0 (west-to-east), dy < 0 (north-to-south)
    if (dx <= 0 || dy >= 0) {
      return { valid: false, reason: "grid_spec_affine_orientation_not_north_up", bounds: null, width, height };
    }

    // Numerical tolerance for origin and endpoint alignment
    const tolX = Math.max(dx * 0.1, 1e-5);
    const tolY = Math.max(Math.abs(dy) * 0.1, 1e-5);

    // 3. Origin check: x0 must match minLng, y0 must match maxLat (upper-left corner)
    if (Math.abs(x0 - minLng) > tolX || Math.abs(y0 - maxLat) > tolY) {
      return { valid: false, reason: "grid_spec_affine_bounds_mismatch", bounds: null, width, height };
    }

    // 4. Extent check: full raster extent endpoints must match declared bounds and dimensions
    const xEnd = x0 + width * dx;
    const yEnd = y0 + height * dy;
    if (Math.abs(xEnd - maxLng) > tolX || Math.abs(yEnd - minLat) > tolY) {
      return { valid: false, reason: "grid_spec_affine_extent_mismatch", bounds: null, width, height };
    }
  }

  return {
    valid: true,
    reason: "grid_valid",
    bounds: [minLng, minLat, maxLng, maxLat],
    width,
    height,
  };
}
