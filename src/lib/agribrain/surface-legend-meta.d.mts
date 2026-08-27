export interface LegendSurfaceLike {
  type?: string;
  semantic_type?: string;
  units?: string;
  palette_id?: string;
  values?: Array<Array<number | null>>;
  render_range?: [number, number];
}

export interface SurfaceLegendMeta {
  label: string;
  unit: string;
  lowColor: string;
  midColor: string;
  highColor: string;
  lowLabel: string;
  midLabel: string;
  highLabel: string;
  stopLabels: string[];
}

export function resolveCommittedSurfaceLegend(
  surface: LegendSurfaceLike | null | undefined,
  fallback: SurfaceLegendMeta,
  visualLens?: string,
): SurfaceLegendMeta;

export function resolveSurfacePalette(
  surface: LegendSurfaceLike | null | undefined,
  fallback?: [string, string, string] | null,
  visualLens?: string,
): [string, string, string] | null;

export interface SurfaceDisplayScale {
  min: number;
  max: number;
  declaredMin: number;
  declaredMax: number;
  policy: "field_percentile" | "declared_physical_range";
  lowPercentile: number | null;
  highPercentile: number | null;
  labels: [string, string, string] | null;
}

export function resolveSurfaceDisplayScale(
  surface: LegendSurfaceLike | null | undefined,
  options?: { activeMode?: string; detailMode?: "farmer" | "expert" },
): SurfaceDisplayScale;
