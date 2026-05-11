"use client";

import type { MapMode } from "@/hooks/useLayer10";

/**
 * SurfaceLegendBar — WS7 (v2)
 *
 * Larger, more readable legend with:
 *  - Discrete 5-step stops in farmer mode, continuous ramp in expert mode
 *  - Mode-specific low/mid/high labels
 *  - No-data swatch to explain gray-hatched inside-field gaps
 *  - Grounding class badge + stretch disclosure
 *  - Coverage warning when field coverage < 70%
 */

const MODE_META: Record<
  MapMode,
  {
    label: string;
    unit: string;
    // Colors must match SemanticSurfaceLayer MODE_RAMPS
    lowColor: string;
    midColor: string;
    highColor: string;
    lowLabel: string;
    midLabel: string;
    highLabel: string;
    // 5 discrete stop labels for farmer mode
    stopLabels: [string, string, string, string, string];
  }
> = {
  vegetation: {
    label: "Canopy (NDVI)",
    unit: "NDVI index",
    lowColor: "rgb(140, 81, 10)",
    midColor: "rgb(220, 200, 120)",
    highColor: "rgb(35, 139, 69)",
    lowLabel: "Bare / Stressed",
    midLabel: "Moderate",
    highLabel: "Dense / Healthy",
    stopLabels: ["Very Low", "Low", "Moderate", "Good", "Healthy"],
  },
  canopy: {
    label: "Canopy (NDVI)",
    unit: "NDVI index",
    lowColor: "rgb(140, 81, 10)",
    midColor: "rgb(220, 200, 120)",
    highColor: "rgb(35, 139, 69)",
    lowLabel: "Bare / Stressed",
    midLabel: "Moderate",
    highLabel: "Dense / Healthy",
    stopLabels: ["Very Low", "Low", "Moderate", "Good", "Healthy"],
  },
  veg_attention: {
    label: "Vegetation Anomaly",
    unit: "Deviation",
    lowColor: "rgb(139, 69, 19)",
    midColor: "rgb(245, 245, 220)",
    highColor: "rgb(34, 139, 34)",
    lowLabel: "Below Mean",
    midLabel: "At Mean",
    highLabel: "Above Mean",
    stopLabels: ["Strong −", "Below", "Normal", "Above", "Strong +"],
  },
  water_stress: {
    label: "Water Stress",
    unit: "Probability",
    lowColor: "rgb(33, 102, 172)",
    midColor: "rgb(253, 212, 158)",
    highColor: "rgb(178, 24, 43)",
    lowLabel: "No Stress",
    midLabel: "Moderate",
    highLabel: "High Stress",
    stopLabels: ["None", "Low", "Moderate", "High", "Severe"],
  },
  nutrient_risk: {
    label: "Nutrient Risk",
    unit: "Probability",
    lowColor: "rgb(26, 152, 80)",
    midColor: "rgb(254, 224, 139)",
    highColor: "rgb(215, 48, 39)",
    lowLabel: "Adequate",
    midLabel: "Watch",
    highLabel: "Deficient",
    stopLabels: ["Adequate", "OK", "Watch", "Risk", "Deficient"],
  },
  composite_risk: {
    label: "Composite Risk",
    unit: "0–1 risk score",
    lowColor: "rgb(255, 255, 191)",
    midColor: "rgb(252, 141, 89)",
    highColor: "rgb(215, 48, 39)",
    lowLabel: "Low Risk",
    midLabel: "Medium",
    highLabel: "High Risk",
    stopLabels: ["Low", "Low-Med", "Medium", "Med-High", "High"],
  },
  uncertainty: {
    label: "Uncertainty (σ)",
    unit: "Sigma",
    lowColor: "rgb(247, 247, 247)",
    midColor: "rgb(150, 150, 150)",
    highColor: "rgb(37, 37, 37)",
    lowLabel: "Low Uncertainty",
    midLabel: "Moderate",
    highLabel: "High Uncertainty",
    stopLabels: ["Very Low", "Low", "Moderate", "High", "Very High"],
  },
};

const GROUNDING_LABEL: Record<string, string> = {
  RASTER_GROUNDED: "Pixel-exact",
  ZONE_GROUNDED: "Zone-grounded",
  PROXY_SPATIAL: "Proxy estimate",
  UNIFORM: "Field proxy",
};

const GROUNDING_COLOR: Record<string, string> = {
  RASTER_GROUNDED: "#34d399",
  ZONE_GROUNDED: "#a78bfa",
  PROXY_SPATIAL: "#38bdf8",
  UNIFORM: "#fbbf24",
};

/** Interpolate between two RGB strings at position t (0–1) */
function lerpColor(c1: string, c2: string, t: number): string {
  const parse = (c: string) => {
    const m = c.match(/\d+/g);
    return m ? m.map(Number) : [0, 0, 0];
  };
  const a = parse(c1);
  const b = parse(c2);
  const r = Math.round(a[0] + (b[0] - a[0]) * t);
  const g = Math.round(a[1] + (b[1] - a[1]) * t);
  const bl = Math.round(a[2] + (b[2] - a[2]) * t);
  return `rgb(${r}, ${g}, ${bl})`;
}

/** Get color at position t (0–1) along the 3-stop ramp */
function rampColor(meta: typeof MODE_META[MapMode], t: number): string {
  if (t <= 0.5) {
    return lerpColor(meta.lowColor, meta.midColor, t * 2);
  }
  return lerpColor(meta.midColor, meta.highColor, (t - 0.5) * 2);
}

interface SurfaceLegendBarProps {
  activeMode: MapMode;
  detailMode?: "farmer" | "expert";
  groundingClass?: string;
  coverageRatio?: number | null;
  minVal?: number | null;
  maxVal?: number | null;
}

export default function SurfaceLegendBar({
  activeMode,
  detailMode = "farmer",
  groundingClass = "UNIFORM",
  coverageRatio = null,
  minVal = null,
  maxVal = null,
}: SurfaceLegendBarProps) {
  const meta = MODE_META[activeMode];
  const stretchLabel =
    detailMode === "expert"
      ? "P01–P99 per-field stretch"
      : "P02–P98 per-field stretch";

  const gcLabel = GROUNDING_LABEL[groundingClass] ?? "Unknown";
  const gcColor = GROUNDING_COLOR[groundingClass] ?? "#fbbf24";

  const partial = coverageRatio !== null && coverageRatio < 0.7;
  const isDiscrete = detailMode === "farmer";

  // Continuous gradient
  const gradient = `linear-gradient(to right, ${meta.lowColor}, ${meta.midColor}, ${meta.highColor})`;

  // Display range if available
  const rangeText =
    minVal !== null && maxVal !== null
      ? `${minVal.toFixed(3)} – ${maxVal.toFixed(3)}`
      : null;

  // Compute 5 discrete stop colors
  const stopColors = [0, 0.25, 0.5, 0.75, 1.0].map((t) => rampColor(meta, t));

  return (
    <div className="w-full">
      <div className="rounded-lg px-3 py-2 w-full">
        {/* Mode label + grounding badge */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold uppercase tracking-widest text-slate-200">
            {meta.label}
          </span>
          <span
            className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded"
            style={{
              color: gcColor,
              backgroundColor: gcColor + "22",
              border: `1px solid ${gcColor}44`,
            }}
          >
            {gcLabel}
          </span>
        </div>

        {/* Colour ramp — discrete stops or continuous */}
        {isDiscrete ? (
          /* 5 discrete color blocks with tick marks */
          <div className="flex w-full mb-1.5 gap-px">
            {stopColors.map((color, i) => (
              <div key={i} className="flex-1 flex flex-col items-center">
                <div
                  className="w-full h-4 first:rounded-l-md last:rounded-r-md"
                  style={{ backgroundColor: color }}
                />
                <div className="w-px h-1.5 bg-slate-500 mt-0.5" />
                <span className="text-[8px] text-slate-400 mt-0.5 leading-none">
                  {meta.stopLabels[i]}
                </span>
              </div>
            ))}
          </div>
        ) : (
          /* Continuous gradient for expert mode */
          <>
            <div
              className="h-4 rounded-md w-full mb-1.5"
              style={{ background: gradient }}
            />
            <div className="flex justify-between mb-1">
              <span className="text-[10px] font-semibold text-slate-300">{meta.lowLabel}</span>
              <span className="text-[10px] text-slate-400">{meta.midLabel}</span>
              <span className="text-[10px] font-semibold text-slate-300">{meta.highLabel}</span>
            </div>
          </>
        )}

        {/* No-data swatch */}
        <div className="flex items-center gap-2 mt-1.5 mb-1">
          <div
            className="w-5 h-3 rounded-sm border border-slate-600"
            style={{
              background: `repeating-linear-gradient(
                45deg,
                rgb(80,80,80),
                rgb(80,80,80) 2px,
                rgb(55,55,55) 2px,
                rgb(55,55,55) 4px
              )`,
            }}
          />
          <span className="text-[9px] text-slate-500">No data</span>
        </div>

        {/* Value range (if computed) */}
        {rangeText && (
          <div className="text-[9px] text-slate-500 text-center mb-0.5">
            {rangeText} {meta.unit}
          </div>
        )}

        {/* Stretch disclosure */}
        <div className="text-[8px] italic text-slate-600 text-center">
          {stretchLabel}
        </div>

        {/* Partial coverage warning */}
        {partial && (
          <div className="mt-1.5 flex items-center gap-1 bg-amber-500/10 border border-amber-500/20 rounded px-1.5 py-0.5">
            <span className="text-amber-400 text-[8px]">⚠</span>
            <span className="text-[8px] text-amber-400">
              {((coverageRatio ?? 0) * 100).toFixed(0)}% field coverage
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
