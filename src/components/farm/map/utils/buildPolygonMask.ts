import { buildPolygonMask as buildPolygonMaskImpl } from "./buildPolygonMask.mjs";

export interface RasterMask {
  data: Uint8Array;
  width: number;
  height: number;
}

export function buildPolygonMask(
  plotId: string | undefined,
  width: number,
  height: number,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson: any | null | undefined,
  /** Geographic extent of the raster grid. Plot bounds are not a substitute. */
  gridBounds?: [number, number, number, number] | null,
): RasterMask | null {
  return buildPolygonMaskImpl(plotId, width, height, plotGeoJson, gridBounds) as RasterMask | null;
}
