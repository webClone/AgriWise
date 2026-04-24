"use client";

import type { MapMode, Layer10Result } from "@/hooks/useLayer10";
import { MODE_CONFIG, MODE_SURFACE_MAP } from "@/hooks/useLayer10";

interface AnalysisStripProps {
  data: Layer10Result;
  activeMode: MapMode;
}

export default function AnalysisStrip({ data, activeMode }: AnalysisStripProps) {
  const config = MODE_CONFIG[activeMode];
  const surfaceType = MODE_SURFACE_MAP[activeMode];
  const histogram = data.histograms.field.find(h => h.surface_type === surfaceType);
  const surface = data.surfaces.find(s => s.type === surfaceType);
  const delta = data.histograms.delta.find(d => d.surface_type === surfaceType);

  // Grounding class label
  const grounding = surface?.grounding_class || "UNIFORM";
  const groundingLabel = grounding === "RASTER_GROUNDED" ? "Raster" :
    grounding === "ZONE_GROUNDED" ? "Zone" :
    grounding === "PROXY_SPATIAL" ? "Proxy" : "Uniform";

  // Trend label from delta
  const trend = delta
    ? (delta.mean_change > 0.02 ? "↑ Improving" :
       delta.mean_change < -0.02 ? "↓ Degrading" : "→ Stable")
    : "→ Stable";

  const trendColor = delta
    ? (delta.mean_change > 0.02 ? "#22c55e" :
       delta.mean_change < -0.02 ? "#ef4444" : "#94a3b8")
    : "#94a3b8";

  // Mini histogram sparkline (8 bins max)
  const maxCount = histogram ? Math.max(...histogram.bin_counts, 1) : 1;

  return (
    <div className="analysis-strip" id="analysis-strip">
      {/* Mode badge */}
      <div className="flex items-center gap-1.5">
        <span className="text-sm">{config.icon}</span>
        <span className="text-[11px] font-medium text-slate-200">{config.label}</span>
      </div>

      {/* Divider */}
      <div className="w-px h-4 bg-slate-700/50" />

      {/* Trend */}
      <span className="text-[11px] font-medium" style={{ color: trendColor }}>
        {trend}
      </span>

      {/* Divider */}
      <div className="w-px h-4 bg-slate-700/50" />

      {/* Stats */}
      {histogram && (
        <div className="flex items-center gap-2 text-[10px] text-slate-400">
          <span>μ={histogram.mean.toFixed(2)}</span>
          <span>σ={histogram.std.toFixed(2)}</span>
          {histogram.p10 !== undefined && histogram.p90 !== undefined && (
            <span className="text-slate-500">P10={histogram.p10.toFixed(2)} P90={histogram.p90.toFixed(2)}</span>
          )}
        </div>
      )}

      {/* Divider */}
      <div className="w-px h-4 bg-slate-700/50" />

      {/* Zone count */}
      <span className="text-[10px] text-slate-400">
        {data.zones.length} zone{data.zones.length !== 1 ? "s" : ""}
      </span>

      {/* Mini histogram sparkline */}
      {histogram && (
        <>
          <div className="w-px h-4 bg-slate-700/50" />
          <div className="flex items-end gap-px h-3" title="Field distribution">
            {histogram.bin_counts.slice(0, 10).map((count, i) => {
              const h = Math.max(1, (count / maxCount) * 12);
              const t = i / Math.max(histogram.bin_counts.length - 1, 1);
              return (
                <div
                  key={i}
                  className="rounded-sm"
                  style={{
                    width: 3,
                    height: h,
                    backgroundColor: `color-mix(in srgb, ${config.colors[0]} ${(1 - t) * 100}%, ${config.colors[2]} ${t * 100}%)`,
                    opacity: 0.8,
                  }}
                />
              );
            })}
          </div>
        </>
      )}

      {/* Divider */}
      <div className="w-px h-4 bg-slate-700/50" />

      {/* Grounding badge */}
      <div className={`grounding-badge ${groundingLabel.toLowerCase()}`}>
        {groundingLabel}
      </div>

      {/* Quality Separation (Ticket 6) */}
      <div className="ml-auto flex items-center gap-3">
        {/* Coverage */}
        <div className="flex flex-col items-end justify-center" title={`${data.quality.surfaces_generated} distinct surfaces ingested`}>
          <span className="text-[9px] text-slate-500 uppercase tracking-widest leading-none">Coverage</span>
          <span className="text-[10px] font-medium text-slate-300">
             {data.quality.surfaces_generated} L10 Layers
          </span>
        </div>
        <div className="w-px h-6 bg-slate-700/50" />
        
        {/* Trust */}
        <div className="flex flex-col items-end justify-center">
          <span className="text-[9px] text-slate-500 uppercase tracking-widest leading-none">Trust</span>
          <span className={`text-[10px] font-bold flex items-center gap-1 ${data.quality.reliability_score >= 0.8 ? "text-emerald-500" : data.quality.reliability_score >= 0.5 ? "text-amber-500" : "text-rose-500"}`}>
            {data.quality.reliability_score >= 0.8 ? "High" : data.quality.reliability_score >= 0.5 ? "Medium" : "Low"}
            <span className="font-normal opacity-70">({Math.round(data.quality.reliability_score * 100)}%)</span>
          </span>
        </div>
        <div className="w-px h-6 bg-slate-700/50" />

        {/* Confidence (Derived from Error Bounds) */}
        <div className="flex flex-col items-end justify-center pr-2">
          <span className="text-[9px] text-slate-500 uppercase tracking-widest leading-none">Render Tier</span>
          <span className="text-[10px] font-bold text-slate-300">
             {data.quality.grid_alignment_ok ? "Aligned" : "Degraded"}
          </span>
        </div>
      </div>
    </div>
  );
}
