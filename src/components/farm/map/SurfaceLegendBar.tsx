"use client";

import type { MapMode } from "@/hooks/useLayer10";
import type { EvidenceLevel } from "@/lib/agribrain/plot-map-evidence-state";


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
    stopLabels: string[];
  }
> = {
  vegetation: {
    label: "Canopy (NDVI)",
    unit: "NDVI index",
    lowColor: "rgb(255, 0, 0)",
    midColor: "rgb(255, 255, 0)",
    highColor: "rgb(0, 204, 0)",
    lowLabel: "Bare / Stressed",
    midLabel: "Moderate",
    highLabel: "Dense / Healthy",
    stopLabels: ["Very Low", "Low", "Moderate", "Good", "Healthy"],
  },
  canopy: {
    label: "Canopy (NDVI)",
    unit: "NDVI index",
    lowColor: "rgb(255, 0, 0)",
    midColor: "rgb(255, 255, 0)",
    highColor: "rgb(0, 204, 0)",
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
  salinity: {
    label: "Salinity Stress",
    unit: "Probability",
    lowColor: "rgb(13, 148, 136)",
    midColor: "rgb(34, 211, 238)",
    highColor: "rgb(239, 68, 68)",
    lowLabel: "Non-Saline",
    midLabel: "Moderate",
    highLabel: "Severe",
    stopLabels: ["None", "Mild", "Moderate", "High", "Severe"],
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
    label: "Data Reliability",
    unit: "score",
    lowColor: "rgb(215, 48, 39)",
    midColor: "rgb(254, 224, 139)",
    highColor: "rgb(26, 152, 80)",
    lowLabel: "Unreliable",
    midLabel: "Moderate",
    highLabel: "Fully Reliable",
    stopLabels: ["Poor", "Low", "Moderate", "High", "Excellent"],
  },
  resolution_coverage: {
    label: "Resolution Coverage",
    unit: "evidence class",
    lowColor: "rgb(6, 182, 212)",
    midColor: "rgb(20, 184, 166)",
    highColor: "rgb(100, 116, 139)",
    lowLabel: "External ground truth",
    midLabel: "2m–5m model-assisted",
    highLabel: "Native 10m evidence",
    stopLabels: ["3cm external", "Fine-detail advisory", "2m modeled", "3m modeled", "5m modeled", "Native 10m"],
  },
};

const GROUNDING_LABEL: Record<string, string> = {
  RASTER_GROUNDED: "pixel-level observation",
  PARTIAL_RASTER_GROUNDED: "pixel-level observation with gaps",
  MODEL_ASSISTED_RASTER: "estimated local signal",
  ZONE_GROUNDED: "Zone-grounded",
  PROXY_SPATIAL: "scouting hint",
  UNIFORM: "plot-level estimate",
  BROADCAST: "plot-level estimate",
};

const GROUNDING_COLOR: Record<string, string> = {
  RASTER_GROUNDED: "#34d399",
  PARTIAL_RASTER_GROUNDED: "#059669",
  MODEL_ASSISTED_RASTER: "#10b981",
  ZONE_GROUNDED: "#a78bfa",
  PROXY_SPATIAL: "#38bdf8",
  UNIFORM: "#fbbf24",
};

const EVIDENCE_LEVEL_LABEL: Record<string, string> = {
  real_raster: "Provider raster",
  partial_raster: "Partial raster",
  gap_filled_raster: "Gap-filled raster",
  model_assisted_raster: "Model-assisted raster",
  proxy_spatial: "Spatial proxy",
  field_proxy: "Field proxy",
  plot_level_model: "Plot-level model",
  visual_basemap_only: "Visual basemap only",
  asmae_diagnostic: "ASMAE Diagnostic Raster",
  composite_advisory: "Composite Advisory Raster",
  unavailable: "No data",
};

const EVIDENCE_LEVEL_COLOR: Record<string, string> = {
  real_raster: "#34d399",
  partial_raster: "#059669",
  gap_filled_raster: "#10b981",
  model_assisted_raster: "#0d9488",
  proxy_spatial: "#38bdf8",
  field_proxy: "#fbbf24",
  plot_level_model: "#f59e0b",
  visual_basemap_only: "#94a3b8",
  asmae_diagnostic: "#34d399",
  composite_advisory: "#a78bfa",
  unavailable: "#64748b",
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
  evidenceLevel?: EvidenceLevel;
  coverageRatio?: number | null;
  minVal?: number | null;
  maxVal?: number | null;
}

export default function SurfaceLegendBar({
  activeMode,
  detailMode = "farmer",
  groundingClass = "UNIFORM",
  evidenceLevel,
  coverageRatio = null,
  minVal = null,
  maxVal = null,
}: SurfaceLegendBarProps) {
  const meta = MODE_META[activeMode];
  const stretchLabel =
    detailMode === "expert"
      ? "P01–P99 per-field stretch"
      : "P02–P98 per-field stretch";

  const gcLabel = evidenceLevel
    ? (EVIDENCE_LEVEL_LABEL[evidenceLevel] ?? "Unknown")
    : (GROUNDING_LABEL[groundingClass] ?? "Unknown");

  const gcColor = evidenceLevel
    ? (EVIDENCE_LEVEL_COLOR[evidenceLevel] ?? "#fbbf24")
    : (GROUNDING_COLOR[groundingClass] ?? "#fbbf24");

  const partial = coverageRatio !== null && coverageRatio < 0.7;
  const isDiscrete = detailMode === "farmer";

  // Continuous gradient
  const gradient = `linear-gradient(to right, ${meta.lowColor}, ${meta.midColor}, ${meta.highColor})`;

  // Display range if available
  const rangeText =
    minVal !== null && maxVal !== null
      ? `${minVal.toFixed(3)} – ${maxVal.toFixed(3)}`
      : null;

  // Compute discrete stop colors dynamically based on stopLabels length
  const numStops = meta.stopLabels.length;
  const stopColors = Array.from({ length: numStops }, (_, i) => {
    const t = numStops > 1 ? i / (numStops - 1) : 0.0;
    return rampColor(meta, t);
  });

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
