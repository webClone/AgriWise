"use client";

import { SolidPolygonLayer, PathLayer } from "@deck.gl/layers";
import type { DisplayLevel, RenderKind } from "@/lib/agribrain/plot-map-evidence-state";

/**
 * V92.4-BC: UniformEvidenceTintLayer
 * ==================================
 * A dedicated DeckGL SolidPolygonLayer for Level 4 (plot-level) evidence.
 *
 * Purpose:
 *   When no per-pixel raster is available for a mode, but a plot-level
 *   estimate exists (from L3, ASMAE aggregate, or proxy model), this layer
 *   fills the plot polygon with a uniform color tint at low opacity.
 *
 * Design rules (from user spec):
 *   - Do NOT reuse the boundary GeoJSON fill (that has selection semantics)
 *   - Render uniform plot tint at 20–35% opacity
 *   - Color derived from the mode's normalized estimate
 *   - No per-pixel hover values
 *   - No contour lines
 *   - Pickable: false (no interaction — it's visual evidence only)
 */

/** Color ramps per mode — same as SemanticSurfaceLayer for visual consistency */
const MODE_COLOR_RAMPS: Record<string, { low: [number, number, number]; mid: [number, number, number]; high: [number, number, number] }> = {
  canopy:         { low: [255, 0, 0],    mid: [255, 255, 0],   high: [0, 204, 0]     },
  vegetation:     { low: [255, 0, 0],    mid: [255, 255, 0],   high: [0, 204, 0]     },
  veg_attention:  { low: [139, 69, 19],  mid: [245, 245, 220], high: [34, 139, 34]   },
  water_stress:   { low: [33, 102, 172], mid: [253, 212, 158], high: [178, 24, 43]   },
  nutrient_risk:  { low: [26, 152, 80],  mid: [254, 224, 139], high: [215, 48, 39]   },
  salinity:       { low: [13, 148, 136], mid: [254, 224, 139], high: [239, 68, 68]   },
  composite_risk: { low: [255, 255, 191], mid: [252, 141, 89], high: [215, 48, 39]   },
  uncertainty:    { low: [247, 247, 247], mid: [150, 150, 150], high: [37, 37, 37]    },
  resolution_coverage: { low: [6, 182, 212], mid: [245, 158, 11], high: [100, 116, 139] },
};

function interpolateColor(
  t: number,
  low: [number, number, number],
  mid: [number, number, number],
  high: [number, number, number],
): [number, number, number] {
  const clamped = Math.max(0, Math.min(1, t));
  if (clamped <= 0.5) {
    const f = clamped * 2;
    return [
      Math.round(low[0] + (mid[0] - low[0]) * f),
      Math.round(low[1] + (mid[1] - low[1]) * f),
      Math.round(low[2] + (mid[2] - low[2]) * f),
    ];
  }
  const f = (clamped - 0.5) * 2;
  return [
    Math.round(mid[0] + (high[0] - mid[0]) * f),
    Math.round(mid[1] + (high[1] - mid[1]) * f),
    Math.round(mid[2] + (high[2] - mid[2]) * f),
  ];
}

export interface UniformEvidenceTintOptions {
  id?: string;
  /** The plot polygon GeoJSON feature */
  plotGeoJson: GeoJSON.Feature<GeoJSON.Geometry> | null | undefined;
  /** The active map mode key */
  mode: string;
  /** Normalized value 0..1 for color interpolation */
  normalizedValue: number | null | undefined;
  /** Display level from the evidence ladder */
  displayLevel: DisplayLevel;
  /** Render kind from the evidence ladder */
  renderKind: RenderKind;
  /** Whether this layer should be visible */
  visible?: boolean;
  /** Opacity 0..1 — defaults to 0.28 (within the 20-35% range) */
  opacity?: number;
}

/**
 * Creates the UniformEvidenceTintLayer for plot-level / proxy evidence.
 * Returns null if the mode doesn't need a uniform tint.
 */
export function getUniformEvidenceTintLayer(options: UniformEvidenceTintOptions) {
  const {
    id = "uniform-evidence-tint",
    plotGeoJson,
    mode,
    normalizedValue,
    displayLevel,
    renderKind,
    visible = true,
    opacity = 0.28,
  } = options;

  // Only render for plot_level / proxy / visual_only display levels
  // AND only when renderKind is "uniform_tint"
  if (!visible || !plotGeoJson) return null;
  if (renderKind !== "uniform_tint") return null;
  if (displayLevel !== "plot_level" && displayLevel !== "proxy" && displayLevel !== "visual_only") return null;

  // Resolve color from mode ramp
  const ramp = MODE_COLOR_RAMPS[mode] || MODE_COLOR_RAMPS.canopy;
  const t = normalizedValue != null && Number.isFinite(normalizedValue) ? normalizedValue : 0.5;
  const [r, g, b] = interpolateColor(t, ramp.low, ramp.mid, ramp.high);

  // Alpha: 20-35% opacity range (mapped to 0-255)
  const alpha = Math.round(Math.max(0, Math.min(1, opacity)) * 255);

  const layers: any[] = [];

  // 1. Uniform fill layer
  layers.push(
    new SolidPolygonLayer({
      id: `${id}-fill`,
      data: [plotGeoJson],
      getPolygon: (d: any) => d.geometry.coordinates,
      getFillColor: [r, g, b, alpha] as [number, number, number, number],
      pickable: false,
      filled: true,
      extruded: false,
    })
  );

  // 2. Subtle dashed border to indicate "plot-level" evidence
  // A thin border with reduced opacity to visually separate from zone borders
  layers.push(
    new PathLayer({
      id: `${id}-border`,
      data: [plotGeoJson],
      getPath: (d: any) => {
        const geom = d.geometry;
        const coords = geom.type === "MultiPolygon"
          ? geom.coordinates[0][0]
          : geom.coordinates[0];
        return coords;
      },
      getColor: [r, g, b, Math.round(alpha * 1.5)] as [number, number, number, number],
      getWidth: 1.5,
      widthUnits: "pixels" as const,
      widthMinPixels: 1,
      getDashArray: [6, 4],
      dashJustified: true,
      pickable: false,
    })
  );

  return layers;
}
