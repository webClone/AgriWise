"use client";

import React, { useState, useMemo } from "react";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import dynamic from "next/dynamic";

const OpenSatelliteMap = dynamic(() => import("./OpenSatelliteMap"), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-[#0B1015] animate-pulse rounded-xl" />,
});

interface Props { lat: number; lng: number; geoJson?: any; plotId: string; farmId: string; }

const LAYERS = [
  { id: "ndvi", label: "NDVI", group: "index", color: "emerald" },
  { id: "evi", label: "EVI", group: "index", color: "teal" },
  { id: "savi", label: "SAVI", group: "index", color: "lime" },
  { id: "moisture-index", label: "NDMI", group: "index", color: "blue" },
  { id: "none", label: "True Color", group: "visual", color: "slate" },
  { id: "false-color", label: "False Color", group: "visual", color: "slate" },
  { id: "agriculture", label: "Agriculture", group: "visual", color: "slate" },
  { id: "barren-soil", label: "Barren Soil", group: "visual", color: "slate" },
] as const;

function vigorColor(v: number) {
  if (v >= 0.6) return { bg: "bg-emerald-500", text: "text-emerald-400", glow: "shadow-emerald-500/20" };
  if (v >= 0.35) return { bg: "bg-amber-500", text: "text-amber-400", glow: "shadow-amber-500/20" };
  return { bg: "bg-rose-500", text: "text-rose-400", glow: "shadow-rose-500/20" };
}

export default function RawSatelliteViewer({ lat, lng, geoJson, plotId, farmId }: Props) {
  const pi = usePlotIntelligence();
  const data = pi?.data;
  const [activeLayer, setActiveLayer] = useState("ndvi");
  const [timelineIdx, setTimelineIdx] = useState(-1);

  const raw = (data?.rawData || {}) as Record<string, any>;
  const s2 = raw.sentinel2_raw || {};
  const s1 = raw.sentinel1_raw || {};
  const sarTs = (raw.sar_timeseries?.timeseries || []) as any[];

  const ndviTimeline = useMemo(() =>
    (data?.timeline?.ndvi || []) as { date: string; ndvi: number; source?: string }[],
  [data?.timeline?.ndvi]);

  const indices = [
    { key: "ndvi", label: "NDVI", desc: "Vegetation density", val: s2.ndvi, src: "S2-L2A" },
    { key: "evi", label: "EVI", desc: "Enhanced vegetation", val: s2.evi, src: "S2-L2A" },
    { key: "ndmi", label: "NDMI", desc: "Moisture content", val: s2.ndmi, src: "S2-SWIR" },
    { key: "ndwi", label: "NDWI", desc: "Water presence", val: s2.ndwi, src: "S2-L2A" },
    { key: "savi", label: "SAVI", desc: "Soil-adj. vegetation", val: s2.savi, src: "S2-L2A" },
  ];

  const sarData = [
    { label: "VH", desc: "Cross-polarization", val: s1.vh, unit: "dB" },
    { label: "VV", desc: "Co-polarization", val: s1.vv, unit: "dB" },
    { label: "VH/VV", desc: "Depolarization ratio", val: s1.vh != null && s1.vv != null ? s1.vh / s1.vv : null, unit: "" },
  ];

  const timelineDates = ndviTimeline.map(t => t.date);
  const selectedDate = timelineIdx >= 0 && timelineIdx < timelineDates.length
    ? timelineDates[timelineIdx]
    : timelineDates[timelineDates.length - 1] || new Date().toISOString().split("T")[0];

  const trendStats = useMemo(() => {
    const vals = ndviTimeline.map(t => t.ndvi).filter(v => v != null && v > 0);
    if (vals.length === 0) return null;
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    const recent = vals.slice(-3), early = vals.slice(0, 3);
    const rAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const eAvg = early.reduce((a, b) => a + b, 0) / early.length;
    const dir = rAvg > eAvg + 0.02 ? "improving" : rAvg < eAvg - 0.02 ? "declining" : "stable";
    const low = vals.filter(v => v < 0.35).length, mid = vals.filter(v => v >= 0.35 && v < 0.6).length;
    const high = vals.filter(v => v >= 0.6).length, total = Math.max(low + mid + high, 1);
    return {
      avg, min: Math.min(...vals), max: Math.max(...vals), dir, delta: rAvg - eAvg, count: vals.length,
      lowPct: Math.round((low / total) * 100), midPct: Math.round((mid / total) * 100),
      highPct: 100 - Math.round((low / total) * 100) - Math.round((mid / total) * 100),
    };
  }, [ndviTimeline]);

  const activeVal = (() => {
    switch (activeLayer) {
      case "ndvi": return s2.ndvi; case "evi": return s2.evi;
      case "savi": return s2.savi; case "moisture-index": return s2.ndmi;
      default: return null;
    }
  })();
  const isIndex = LAYERS.find(l => l.id === activeLayer)?.group === "index";

  return (
    <div className="rounded-2xl overflow-hidden border border-white/[0.06] shadow-2xl" style={{ background: "linear-gradient(180deg, rgba(11,16,21,0.9) 0%, rgba(8,12,25,0.95) 100%)" }}>

      {/* ═══ TOP HEADER BAR ═══ */}
      <div className="px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 border border-indigo-500/20 flex items-center justify-center text-lg">🛰️</div>
          <div>
            <h2 className="text-[15px] font-semibold text-white tracking-wide">Satellite Intelligence</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="inline-flex items-center gap-1 text-[9px] font-mono uppercase tracking-widest text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Live
              </span>
              <span className="text-[10px] text-slate-600 font-mono">{lat.toFixed(4)}, {lng.toFixed(4)}</span>
            </div>
          </div>
        </div>
        {isIndex && activeVal != null && (
          <div className="text-right">
            <div className="text-[9px] text-slate-500 uppercase tracking-[0.2em] font-bold mb-0.5">{LAYERS.find(l => l.id === activeLayer)?.label}</div>
            <div className={`text-4xl font-mono font-black tracking-tighter ${vigorColor(activeVal).text}`}>
              {activeVal.toFixed(2)}
            </div>
          </div>
        )}
      </div>

      {/* ═══ LAYER TABS ═══ */}
      <div className="px-6 pb-3 flex items-center gap-1 flex-wrap">
        <div className="flex items-center gap-1 bg-white/[0.03] rounded-xl p-1 border border-white/[0.04]">
          {LAYERS.filter(l => l.group === "index").map(l => (
            <button key={l.id} onClick={() => setActiveLayer(l.id)}
              className={`px-3.5 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                activeLayer === l.id ? "bg-indigo-500/20 text-indigo-300 shadow-lg shadow-indigo-500/10" : "text-slate-500 hover:text-slate-300"
              }`}>{l.label}</button>
          ))}
        </div>
        <div className="w-px h-5 bg-white/5 mx-1" />
        <div className="flex items-center gap-1 bg-white/[0.03] rounded-xl p-1 border border-white/[0.04]">
          {LAYERS.filter(l => l.group === "visual").map(l => (
            <button key={l.id} onClick={() => setActiveLayer(l.id)}
              className={`px-3.5 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                activeLayer === l.id ? "bg-white/10 text-white shadow-lg" : "text-slate-600 hover:text-slate-400"
              }`}>{l.label}</button>
          ))}
        </div>
      </div>

      {/* ═══ MAP + SIDEBAR ═══ */}
      <div className="flex">
        <div className="flex-1 relative h-[420px]">
          <OpenSatelliteMap lat={lat} lng={lng} geoJson={geoJson} metric={activeLayer} provider="sentinel" date={selectedDate} />
          <div className="absolute top-4 left-4 z-10 bg-black/70 backdrop-blur-xl px-3 py-1.5 rounded-lg border border-white/10 text-xs font-mono flex items-center gap-2 pointer-events-none">
            <span className="text-slate-500">PASS</span>
            <span className="text-indigo-400 font-bold">{selectedDate}</span>
          </div>
          {isIndex && (
            <div className="absolute bottom-4 right-4 z-10 bg-black/70 backdrop-blur-xl p-2.5 rounded-lg border border-white/10 flex items-center gap-2 pointer-events-none">
              <span className="text-[8px] font-bold text-rose-400 uppercase">Low</span>
              <div className="flex h-2 w-24 rounded-full overflow-hidden bg-gradient-to-r from-rose-600 via-amber-500 to-emerald-500" />
              <span className="text-[8px] font-bold text-emerald-400 uppercase">High</span>
            </div>
          )}
        </div>

        {/* Index sidebar */}
        <div className="w-48 border-l border-white/[0.04] bg-black/20 p-3 flex flex-col gap-2 shrink-0">
          <div className="text-[8px] text-slate-600 uppercase tracking-[0.2em] font-bold px-1 mb-1">Optical Indices</div>
          {indices.map(idx => {
            const c = idx.val != null ? vigorColor(idx.val) : { text: "text-slate-700", bg: "", glow: "" };
            return (
              <div key={idx.key} className="bg-white/[0.02] rounded-lg p-2.5 border border-white/[0.04] hover:border-white/10 transition-all group cursor-default">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[9px] font-bold text-slate-400 uppercase">{idx.label}</span>
                  <span className={`text-sm font-mono font-bold ${c.text}`}>{idx.val != null ? idx.val.toFixed(3) : "—"}</span>
                </div>
                <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-700 ${c.bg}`} style={{ width: idx.val != null ? `${Math.min(100, idx.val * 100)}%` : "0%" }} />
                </div>
                <div className="text-[7px] text-slate-700 mt-1 group-hover:text-slate-500 transition-colors">{idx.desc} · {idx.src}</div>
              </div>
            );
          })}
          <div className="mt-auto pt-2 border-t border-white/[0.04]">
            <div className="text-[8px] text-slate-600 uppercase tracking-[0.2em] font-bold px-1 mb-1">SAR Radar</div>
            {sarData.map(s => (
              <div key={s.label} className="flex items-center justify-between px-1 py-1">
                <span className="text-[9px] text-slate-500">{s.label}</span>
                <span className="text-[10px] font-mono font-bold text-indigo-400">{s.val != null ? `${s.val.toFixed(2)} ${s.unit}` : "—"}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ═══ TIMELINE SCRUBBER ═══ */}
      {timelineDates.length > 1 && (
        <div className="px-6 py-3 border-t border-white/[0.04] flex items-center gap-4 bg-black/20">
          <span className="text-[9px] text-slate-600 font-mono w-20 shrink-0">{timelineDates[0]}</span>
          <div className="flex-1 relative h-6 flex items-center">
            <div className="absolute inset-x-0 h-1 bg-slate-800/80 rounded-full">
              <div className="h-full bg-gradient-to-r from-indigo-600 to-cyan-500 rounded-full transition-all" style={{ width: `${((timelineIdx >= 0 ? timelineIdx : timelineDates.length - 1) / Math.max(1, timelineDates.length - 1)) * 100}%` }} />
            </div>
            <input type="range" min={0} max={timelineDates.length - 1} value={timelineIdx >= 0 ? timelineIdx : timelineDates.length - 1}
              onChange={(e) => setTimelineIdx(Number(e.target.value))} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
          </div>
          <span className="text-[9px] text-slate-600 font-mono w-20 text-right shrink-0">{timelineDates[timelineDates.length - 1]}</span>
        </div>
      )}

      {/* ═══ ANALYSIS PANELS ═══ */}
      <div className="px-6 py-5 border-t border-white/[0.04] grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* ── NDVI TEMPORAL CHART ── */}
        <div className="rounded-xl border border-white/[0.06] p-5" style={{ background: "linear-gradient(135deg, rgba(16,185,129,0.04) 0%, transparent 50%)" }}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-xs font-semibold text-white">NDVI Temporal Profile</div>
              <div className="text-[9px] text-slate-600 mt-0.5">{trendStats?.count || 0} observations · Kalman filtered</div>
            </div>
            {trendStats && (
              <div className={`px-2 py-1 rounded-lg text-[9px] font-bold uppercase tracking-wider ${
                trendStats.dir === "improving" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                trendStats.dir === "declining" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
                "bg-slate-500/10 text-slate-400 border border-slate-500/20"
              }`}>
                {trendStats.dir === "improving" ? "↑" : trendStats.dir === "declining" ? "↓" : "→"} {trendStats.dir}
              </div>
            )}
          </div>
          <div className="flex items-end gap-[3px] h-28 mb-3">
            {ndviTimeline.map((t, i) => {
              const maxV = trendStats?.max || 1;
              const h = Math.max(6, (t.ndvi / maxV) * 100);
              const sel = timelineIdx === i;
              const c = vigorColor(t.ndvi);
              return (
                <div key={i} onClick={() => setTimelineIdx(i)} title={`${t.date}\n${t.ndvi.toFixed(4)}`}
                  className={`flex-1 rounded-t-sm cursor-pointer transition-all duration-200 ${c.bg} ${sel ? "opacity-100 ring-2 ring-white/60 shadow-lg " + c.glow : "opacity-40 hover:opacity-70"}`}
                  style={{ height: `${h}%`, minWidth: 3 }} />
              );
            })}
          </div>
          {trendStats && (
            <div className="grid grid-cols-3 gap-3 pt-3 border-t border-white/[0.04]">
              <div className="text-center"><div className="text-xs font-mono font-bold text-white">{trendStats.min.toFixed(3)}</div><div className="text-[8px] text-slate-600">Min</div></div>
              <div className="text-center"><div className="text-xs font-mono font-bold text-emerald-400">{trendStats.avg.toFixed(3)}</div><div className="text-[8px] text-slate-600">Average</div></div>
              <div className="text-center"><div className="text-xs font-mono font-bold text-white">{trendStats.max.toFixed(3)}</div><div className="text-[8px] text-slate-600">Max</div></div>
            </div>
          )}
        </div>

        {/* ── VIGOR DISTRIBUTION ── */}
        <div className="rounded-xl border border-white/[0.06] p-5" style={{ background: "linear-gradient(135deg, rgba(245,158,11,0.04) 0%, transparent 50%)" }}>
          <div className="text-xs font-semibold text-white mb-1">Canopy Vigor Distribution</div>
          <div className="text-[9px] text-slate-600 mb-5">Based on {trendStats?.count || 0} temporal samples</div>

          {trendStats ? (
            <>
              {/* Donut-style ring */}
              <div className="flex items-center justify-center mb-5">
                <svg width="120" height="120" viewBox="0 0 120 120" className="drop-shadow-lg">
                  <circle cx="60" cy="60" r="48" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="14" />
                  {/* Healthy arc */}
                  <circle cx="60" cy="60" r="48" fill="none" stroke="#10b981" strokeWidth="14" strokeLinecap="round"
                    strokeDasharray={`${trendStats.highPct * 3.01} 301.6`} strokeDashoffset="0" transform="rotate(-90 60 60)" className="transition-all duration-700" />
                  {/* Moderate arc */}
                  <circle cx="60" cy="60" r="48" fill="none" stroke="#f59e0b" strokeWidth="14" strokeLinecap="round"
                    strokeDasharray={`${trendStats.midPct * 3.01} 301.6`} strokeDashoffset={`-${trendStats.highPct * 3.01}`} transform="rotate(-90 60 60)" className="transition-all duration-700" />
                  {/* Stressed arc */}
                  <circle cx="60" cy="60" r="48" fill="none" stroke="#ef4444" strokeWidth="14" strokeLinecap="round"
                    strokeDasharray={`${trendStats.lowPct * 3.01} 301.6`} strokeDashoffset={`-${(trendStats.highPct + trendStats.midPct) * 3.01}`} transform="rotate(-90 60 60)" className="transition-all duration-700" />
                  <text x="60" y="56" textAnchor="middle" className="fill-white text-xl font-bold font-mono">{trendStats.highPct}%</text>
                  <text x="60" y="72" textAnchor="middle" className="fill-slate-500 text-[9px] uppercase tracking-widest">Healthy</text>
                </svg>
              </div>

              <div className="grid grid-cols-3 gap-2">
                {[
                  { pct: trendStats.lowPct, label: "Stressed", color: "rose" },
                  { pct: trendStats.midPct, label: "Moderate", color: "amber" },
                  { pct: trendStats.highPct, label: "Healthy", color: "emerald" },
                ].map(z => (
                  <div key={z.label} className={`rounded-lg p-2 text-center border border-${z.color}-500/10 bg-${z.color}-500/[0.04]`}>
                    <div className={`text-lg font-mono font-bold text-${z.color}-400`}>{z.pct}%</div>
                    <div className="text-[8px] text-slate-600 uppercase tracking-widest">{z.label}</div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-32 text-slate-600 text-xs">No temporal data</div>
          )}
        </div>

        {/* ── SAR RADAR PANEL ── */}
        <div className="rounded-xl border border-white/[0.06] p-5" style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.04) 0%, transparent 50%)" }}>
          <div className="text-xs font-semibold text-white mb-1">SAR Backscatter Profile</div>
          <div className="text-[9px] text-slate-600 mb-4">Sentinel-1 GRD · C-Band 5.405 GHz</div>

          {sarTs.length > 0 ? (
            <div className="flex items-end gap-[3px] h-24 mb-3">
              {sarTs.slice(-25).map((e: any, i: number) => {
                const vv = e.vv_db ?? -15;
                const vh = e.vh_db ?? -20;
                const normVV = Math.max(6, Math.min(100, ((vv + 25) / 15) * 100));
                const normVH = Math.max(4, Math.min(90, ((vh + 30) / 20) * 100));
                return (
                  <div key={i} className="flex-1 flex flex-col items-stretch gap-[1px] justify-end h-full" title={`${e.date}\nVV: ${vv.toFixed(1)} dB\nVH: ${vh.toFixed(1)} dB`}>
                    <div className="rounded-t-sm bg-indigo-400/50 hover:bg-indigo-400/80 transition-all cursor-default" style={{ height: `${normVV}%` }} />
                    <div className="rounded-t-sm bg-cyan-400/30 hover:bg-cyan-400/60 transition-all cursor-default" style={{ height: `${normVH * 0.5}%` }} />
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex items-center justify-center h-24 text-slate-600 text-xs italic">No SAR timeseries</div>
          )}

          {/* SAR values */}
          <div className="grid grid-cols-3 gap-2 pt-3 border-t border-white/[0.04]">
            {sarData.map(s => (
              <div key={s.label} className="bg-white/[0.02] rounded-lg p-2.5 text-center border border-white/[0.03]">
                <div className="text-sm font-mono font-bold text-indigo-400">{s.val != null ? s.val.toFixed(2) : "—"}</div>
                <div className="text-[8px] text-slate-600 mt-0.5">{s.label} {s.unit}</div>
                <div className="text-[7px] text-slate-700">{s.desc}</div>
              </div>
            ))}
          </div>

          {sarTs.length > 0 && (
            <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/[0.04]">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-sm bg-indigo-400/60" /><span className="text-[8px] text-slate-600">VV</span>
                <div className="w-2 h-2 rounded-sm bg-cyan-400/40 ml-2" /><span className="text-[8px] text-slate-600">VH</span>
              </div>
              <span className="text-[8px] text-slate-600 font-mono">{sarTs.length} obs</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
