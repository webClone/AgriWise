"use client";

import type { MapMode, HistogramData } from "@/hooks/useLayer10";
import { MODE_CONFIG } from "@/hooks/useLayer10";

interface IntelligenceLegendProps {
  mode: MapMode;
  groundingClass?: string;
  valueRange?: [number, number];
  histogram?: HistogramData | null;
  confidenceScore?: number;
}

export default function IntelligenceLegend({
  mode,
  groundingClass,
  valueRange,
  histogram,
  confidenceScore,
}: IntelligenceLegendProps) {
  const config = MODE_CONFIG[mode];

  const groundingLabel = groundingClass === "RASTER_GROUNDED" ? "Raster" :
    groundingClass === "ZONE_GROUNDED" ? "Zone" :
    groundingClass === "PROXY_SPATIAL" ? "Proxy" : "Uniform";

  const confidenceLabel = (confidenceScore ?? 0) >= 0.8 ? "High" :
    (confidenceScore ?? 0) >= 0.5 ? "Medium" : "Low";

  const confidenceColor = (confidenceScore ?? 0) >= 0.8 ? "#22c55e" :
    (confidenceScore ?? 0) >= 0.5 ? "#eab308" : "#ef4444";

  // Mini histogram sparkline
  const maxCount = histogram ? Math.max(...histogram.bin_counts, 1) : 1;

  return (
    <div className="intelligence-legend glass-panel" id="intelligence-legend">
      {/* Mode header */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-sm">{config.icon}</span>
          <span className="text-[11px] font-semibold text-slate-200">{config.label}</span>
        </div>
        <div className={`grounding-badge ${groundingLabel.toLowerCase()}`}>
          {groundingLabel}
        </div>
      </div>

      {/* Gradient bar with semantic labels */}
      <div className="relative mb-1">
        <div className="flex justify-between text-[9px] text-slate-500 mb-0.5" dir="ltr">
          <span className="font-medium tracking-wide">{mode === "vegetation" ? "Low vigor" : mode === "uncertainty" ? "Certain" : "Low risk"}</span>
          <span className="font-medium tracking-wide">{mode === "vegetation" ? "High vigor" : mode === "uncertainty" ? "Uncertain" : "High risk"}</span>
        </div>
        <div
          className="legend-gradient"
          style={{
            background: `linear-gradient(90deg, ${config.colors[0]}, ${config.colors[1]}, ${config.colors[2]})`,
          }}
        />
        {/* Percentile markers */}
        {histogram && (
          <div className="flex justify-between text-[8px] text-slate-600 mt-0.5">
            <span>P10: {histogram.p10?.toFixed(2) || "—"}</span>
            <span>Med: {((histogram.mean) || 0).toFixed(2)}</span>
            <span>P90: {histogram.p90?.toFixed(2) || "—"}</span>
          </div>
        )}
      </div>

      {/* Value range */}
      {valueRange && (
        <div className="flex justify-between text-[9px] text-slate-500">
          <span>{valueRange[0].toFixed(2)}</span>
          <span>{valueRange[1].toFixed(2)}</span>
        </div>
      )}

      {/* Mini histogram */}
      {histogram && (
        <div className="mt-1.5 pt-1.5 border-t border-slate-700/30">
          <div className="flex items-end gap-px h-4 mb-0.5" title="Field distribution">
            {histogram.bin_counts.map((count, i) => {
              const h = Math.max(0.5, (count / maxCount) * 16);
              const t = i / Math.max(histogram.bin_counts.length - 1, 1);
              return (
                <div
                  key={i}
                  className="rounded-sm flex-1"
                  style={{
                    height: h,
                    backgroundColor: `color-mix(in srgb, ${config.colors[0]} ${(1 - t) * 100}%, ${config.colors[2]} ${t * 100}%)`,
                    opacity: 0.7,
                  }}
                />
              );
            })}
          </div>
          <div className="text-[8px] text-slate-600 text-center">
            {histogram.valid_pixels ?? 0}/{histogram.total_pixels ?? 0} valid
          </div>
        </div>
      )}

      {/* Confidence badge */}
      <div className="flex items-center gap-1 mt-1">
        <div
          className="w-1.5 h-1.5 rounded-full"
          style={{ backgroundColor: confidenceColor }}
        />
        <span className="text-[9px] text-slate-500">
          Confidence: {confidenceLabel}
        </span>
      </div>
    </div>
  );
}
