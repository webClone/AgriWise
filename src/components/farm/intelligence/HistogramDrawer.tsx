"use client";

import { useMemo } from "react";
import type { HistogramData, DeltaHistogramData } from "@/hooks/useLayer10";

interface HistogramDrawerProps {
  histogram: HistogramData | null;
  delta: DeltaHistogramData | null;
  colors: [string, string, string];
  expanded: boolean;
  onToggle: () => void;
  surfaceLabel: string;
}

function interpolateColor(t: number, colors: [string, string, string]): string {
  const hexToRgb = (hex: string) => {
    const h = hex.replace("#", "");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  };
  const rgbToHex = (r: number, g: number, b: number) =>
    "#" + [r, g, b].map(v => Math.round(v).toString(16).padStart(2, "0")).join("");

  const [low, mid, high] = colors.map(hexToRgb);
  let r: number, g: number, b: number;
  if (t <= 0.5) {
    const f = t * 2;
    r = low[0] + f * (mid[0] - low[0]);
    g = low[1] + f * (mid[1] - low[1]);
    b = low[2] + f * (mid[2] - low[2]);
  } else {
    const f = (t - 0.5) * 2;
    r = mid[0] + f * (high[0] - mid[0]);
    g = mid[1] + f * (high[1] - mid[1]);
    b = mid[2] + f * (high[2] - mid[2]);
  }
  return rgbToHex(r, g, b);
}

export default function HistogramDrawer({
  histogram,
  delta,
  colors,
  expanded,
  onToggle,
  surfaceLabel,
}: HistogramDrawerProps) {
  const maxCount = useMemo(() => {
    if (!histogram) return 1;
    return Math.max(...histogram.bin_counts, 1);
  }, [histogram]);

  if (!histogram) return null;

  const shiftBadge = delta?.shift_direction;
  const shiftColor =
    shiftBadge === "IMPROVING" ? "text-emerald-400" :
    shiftBadge === "DEGRADING" ? "text-red-400" : "text-slate-400";

  return (
    <div
      className={`intelligence-panel histogram-drawer ${expanded ? "expanded" : "collapsed"}`}
      id="histogram-drawer"
    >
      {/* Collapsed Header / Toggle */}
      <button
        className="w-full flex items-center justify-between px-4 py-2.5 text-left"
        onClick={onToggle}
        id="histogram-toggle"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold text-slate-300">📊 {surfaceLabel}</span>

          {/* Inline sparkline when collapsed */}
          {!expanded && (
            <div className="histogram-sparkline">
              {histogram.bin_counts.map((count, i) => (
                <div
                  key={i}
                  className="spark-bar"
                  style={{
                    height: `${(count / maxCount) * 100}%`,
                    backgroundColor: interpolateColor(i / histogram.bin_counts.length, colors),
                  }}
                />
              ))}
            </div>
          )}

          <span className="text-[10px] text-slate-500">
            μ={histogram.mean.toFixed(3)} · σ={histogram.std.toFixed(3)}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {delta && (
            <span className={`text-[10px] font-bold ${shiftColor}`}>
              {shiftBadge === "IMPROVING" ? "↑" : shiftBadge === "DEGRADING" ? "↓" : "→"} {shiftBadge}
            </span>
          )}
          <svg
            className={`w-4 h-4 text-slate-500 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-4 pb-4">
          {/* Main Histogram */}
          <div className="histogram-container mb-3">
            {histogram.bin_counts.map((count, i) => {
              const t = i / histogram.bin_counts.length;
              return (
                <div
                  key={i}
                  className="histogram-bar"
                  style={{
                    height: `${(count / maxCount) * 100}%`,
                    backgroundColor: interpolateColor(t, colors),
                  }}
                  title={`Bin ${i}: ${count} pixels (${histogram.bin_edges[i]?.toFixed(3)} – ${histogram.bin_edges[i + 1]?.toFixed(3)})`}
                />
              );
            })}
          </div>

          {/* Value Range Labels */}
          <div className="flex justify-between text-[9px] text-slate-500 mb-3">
            <span>{histogram.bin_edges[0]?.toFixed(2)}</span>
            <span>{histogram.bin_edges[Math.floor(histogram.bin_edges.length / 2)]?.toFixed(2)}</span>
            <span>{histogram.bin_edges[histogram.bin_edges.length - 1]?.toFixed(2)}</span>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-4 gap-2">
            {[
              { label: "Mean", value: histogram.mean.toFixed(3) },
              { label: "Std", value: histogram.std.toFixed(3) },
              { label: "P10", value: histogram.p10?.toFixed(3) || "–" },
              { label: "P90", value: histogram.p90?.toFixed(3) || "–" },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-800/40 rounded p-1.5 text-center">
                <div className="text-[10px] font-bold text-slate-300">{value}</div>
                <div className="text-[8px] text-slate-500">{label}</div>
              </div>
            ))}
          </div>

          {/* Delta Section */}
          {delta && (
            <div className="mt-3 bg-slate-800/30 rounded-lg p-3 border border-slate-700/30">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                  Temporal Change
                </span>
                <span className={`text-[10px] font-bold ${shiftColor}`}>
                  {delta.date_from} → {delta.date_to}
                </span>
              </div>
              <div className="text-xs text-slate-300">
                Mean Δ: <span className={`font-bold ${shiftColor}`}>
                  {delta.mean_change > 0 ? "+" : ""}{delta.mean_change.toFixed(4)}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
