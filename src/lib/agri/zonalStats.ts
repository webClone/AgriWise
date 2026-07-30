/**
 * zonalStats.ts
 * Pure functions for computing zonal statistics over a 2D raster grid.
 * All inputs are typed strictly — no fallbacks to zone.severity.
 */

/** Compute the mean of raster cells at the specified [row, col] indices. Returns null if no valid cells. */
export function computeZonalMean(
  values: (number | null)[][],
  cells: [number, number][]
): number | null {
  let sum = 0;
  let count = 0;
  for (const [r, c] of cells) {
    const v = values[r]?.[c];
    if (v !== null && v !== undefined && !Number.isNaN(v)) {
      sum += v;
      count++;
    }
  }
  return count > 0 ? sum / count : null;
}

/** Compute the standard deviation of raster cells at the specified indices. Returns null if <2 valid cells. */
export function computeZonalStd(
  values: (number | null)[][],
  cells: [number, number][]
): number | null {
  const mean = computeZonalMean(values, cells);
  if (mean === null) return null;
  let sumSq = 0;
  let count = 0;
  for (const [r, c] of cells) {
    const v = values[r]?.[c];
    if (v !== null && v !== undefined && !Number.isNaN(v)) {
      sumSq += (v - mean) ** 2;
      count++;
    }
  }
  return count >= 2 ? Math.sqrt(sumSq / count) : null;
}

/** Compute P10 (10th percentile) over the given cells. Returns null if no valid cells. */
export function computeZonalP10(
  values: (number | null)[][],
  cells: [number, number][]
): number | null {
  return _percentile(values, cells, 0.1);
}

/** Compute P90 (90th percentile) over the given cells. Returns null if no valid cells. */
export function computeZonalP90(
  values: (number | null)[][],
  cells: [number, number][]
): number | null {
  return _percentile(values, cells, 0.9);
}

/** Count valid (non-null, non-NaN) cells. */
export function countValidZonalCells(
  values: (number | null)[][],
  cells: [number, number][]
): number {
  let count = 0;
  for (const [r, c] of cells) {
    const v = values[r]?.[c];
    if (v !== null && v !== undefined && !Number.isNaN(v)) count++;
  }
  return count;
}

function _percentile(
  values: (number | null)[][],
  cells: [number, number][],
  p: number
): number | null {
  const vals: number[] = [];
  for (const [r, c] of cells) {
    const v = values[r]?.[c];
    if (v !== null && v !== undefined && !Number.isNaN(v)) vals.push(v);
  }
  if (vals.length === 0) return null;
  vals.sort((a, b) => a - b);
  const idx = Math.max(0, Math.min(vals.length - 1, Math.floor(vals.length * p)));
  return vals[idx];
}
