"use client";

import React from "react";
import { useLayer10 } from "@/hooks/useLayer10";

interface WeatherIndices {
  ndvi_anomaly?: number;
  spi_1mo?: number;
  spei_3mo?: number;
}

export default function PlotRawMetricsPanel() {
  const { data } = useLayer10();
  
  // Extract trailing deltas from histogram bundle
  const ndviDeltas = data?.histograms?.delta?.filter((d) => d.surface_type === "NDVI_CLEAN") || [];
  const delta7 = ndviDeltas.find((d) => new Date(d.date_to).getTime() - new Date(d.date_from).getTime() <= 8 * 86400000)?.mean_change ?? 0;
  const delta14 = ndviDeltas.find((d) => new Date(d.date_to).getTime() - new Date(d.date_from).getTime() > 8 * 86400000)?.mean_change ?? 0;

  // Extract spatial uncertainty standard deviation
  const uncertaintySigma = data?.histograms?.uncertainty?.find((h) => h.surface_type === "UNCERTAINTY_SIGMA")?.mean ?? 0;
  
  // Extract trust/quality metrics to drive visual states
  const reliability = data?.quality?.reliability_score ?? 0;

  // Extract Provenance weather indices
  const weatherIndices = (data?.provenance?.weather_indices as WeatherIndices) || {};
  const ndviAnomaly = weatherIndices.ndvi_anomaly;
  const spi1Mo = weatherIndices.spi_1mo;
  const spei3Mo = weatherIndices.spei_3mo;
  
  // Determine text coloring dynamically
  const ndviColor = ndviAnomaly === undefined ? "text-slate-400 uppercase text-sm" : ndviAnomaly < -0.1 ? "text-rose-500" : ndviAnomaly > 0.1 ? "text-emerald-500" : "text-slate-700 dark:text-slate-300";
  const ndviLabel = ndviAnomaly === undefined ? "N/A" : ndviAnomaly < -0.1 ? "Severe Deficit" : ndviAnomaly > 0.1 ? "Above Average" : "Nominal Range";
  
  // Root-Zone Depletion from WATER_STRESS_PROB
  const waterStress = data?.histograms?.field?.find(h => h.surface_type === "WATER_STRESS_PROB")?.mean ?? 0;
  const depletionPct = Math.round(waterStress * 100);

  if (!data) {
    return (
      <div className="card fade-in h-full flex flex-col p-6 items-center justify-center min-h-[300px]">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-xs text-slate-500 font-mono">Syncing Telemetry...</p>
      </div>
    );
  }

  return (
    <div className="card fade-in h-full flex flex-col p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            📡 Deep Telemetry & Anomalies
          </h3>
          <p className="text-xs text-slate-500 mt-1">Multi-modal raw data ingestion anomalies and trackers.</p>
        </div>
        <span className="text-[10px] bg-indigo-100/50 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400 px-2.5 py-1 rounded-full font-mono uppercase tracking-widest border border-indigo-200 dark:border-indigo-800/50">
          L1/L2 RAW
        </span>
      </div>

      <div className="flex-1 grid grid-cols-2 gap-4">
        {/* NDVI Anomaly vs 5y */}
        <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50 flex flex-col justify-between">
          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            NDVI vs 5y Baseline
          </div>
          <div className="flex items-end justify-between mt-2">
            <span className={`text-3xl font-bold ${ndviColor}`}>{ndviAnomaly === undefined ? "N/A" : `${ndviAnomaly > 0 ? "+" : ""}${ndviAnomaly.toFixed(2)}`}</span>
            <span className={`text-[10px] ${ndviAnomaly === undefined ? "bg-slate-100 text-slate-400 dark:bg-slate-800" : ndviAnomaly < -0.1 ? "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400"} px-2 py-0.5 rounded uppercase tracking-wider font-bold mb-1`}>{ndviLabel}</span>
          </div>
        </div>

        {/* 7d/14d Deltas */}
        <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50">
          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
            Trailing Deltas
          </div>
          <div className="flex flex-col gap-2 mt-1 font-mono text-sm">
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-xs">7-Day:</span>
              <span className={`${delta7 < 0 ? 'text-rose-500 bg-rose-500/10' : 'text-emerald-500 bg-emerald-500/10'} font-bold px-2 py-0.5 rounded`}>
                {(delta7 > 0 ? "+" : "")}{(delta7 * 100).toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-xs">14-Day:</span>
              <span className={`${delta14 < 0 ? 'text-rose-500 bg-rose-500/10' : 'text-emerald-500 bg-emerald-500/10'} font-bold px-2 py-0.5 rounded`}>
                {(delta14 > 0 ? "+" : "")}{(delta14 * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Root-Zone Depletion */}
        <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50">
          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            Root-Zone Depletion
          </div>
          <div className="flex items-end justify-between mt-3 mb-2">
            <span className="text-2xl font-bold text-amber-500">{depletionPct}%</span>
            <span className="text-[9px] text-amber-500/80 uppercase tracking-widest font-bold">
              {depletionPct > 50 ? "Critical Threshold" : "Nominal"}
            </span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-slate-700/50 h-2 rounded-full overflow-hidden">
             <div className="bg-linear-to-r from-amber-400 to-amber-600 h-full transition-all duration-1000" style={{width: `${depletionPct}%`}}></div>
          </div>
        </div>

        {/* SPI / SPEI */}
        <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50">
          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg>
            Drought Indices
          </div>
          <div className="flex flex-col gap-2 mt-1 font-mono text-xs">
            <div className="flex justify-between items-center">
              <span className="text-slate-400">1-Mo SPI:</span>
              <span className={`${spi1Mo === undefined ? "text-slate-500" : spi1Mo < -1.0 ? "text-rose-500" : spi1Mo > 1.0 ? "text-emerald-500" : "text-amber-500"} font-bold`}>{spi1Mo === undefined ? "N/A" : `${spi1Mo > 0 ? "+" : ""}${spi1Mo.toFixed(1)}`} {spi1Mo !== undefined && <span className="text-[9px] uppercase opacity-70">({spi1Mo < -1.5 ? "Extreme" : spi1Mo < -1.0 ? "Severe" : "Normal"})</span>}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400">3-Mo SPEI:</span>
              <span className={`${spei3Mo === undefined ? "text-slate-500" : spei3Mo < -1.0 ? "text-rose-500" : spei3Mo > 1.0 ? "text-emerald-500" : "text-amber-500"} font-bold`}>{spei3Mo === undefined ? "N/A" : `${spei3Mo > 0 ? "+" : ""}${spei3Mo.toFixed(1)}`} {spei3Mo !== undefined && <span className="text-[9px] uppercase opacity-70">({spei3Mo < -1.5 ? "Extreme" : spei3Mo < -1.0 ? "Severe" : "Normal"})</span>}</span>
            </div>
          </div>
        </div>

        {/* Mixed-Pixel Uncertainty Tracker */}
        <div className="col-span-2 bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50 flex flex-col justify-between mt-2">
            <div className="flex justify-between items-center mb-3">
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider space-x-1.5 flex items-center">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
                  <span>Mixed-Pixel Uncertainty</span>
                </div>
                <span className="text-[9px] bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded-full font-bold uppercase tracking-widest border border-emerald-200 dark:border-emerald-800/50">
                  Nominal Error
                </span>
            </div>
            
            <div className="flex items-center gap-4">
                <div className="flex-1 bg-slate-200 dark:bg-slate-700/50 h-3 rounded-full overflow-hidden flex shadow-inner">
                    <div className="bg-emerald-500 transition-all duration-1000" style={{width: `${reliability * 100}%`}} title={`Pure Agricultural (${(reliability * 100).toFixed(0)}%)`}></div>
                    <div className="bg-amber-400 transition-all duration-1000" style={{width: `${(1 - reliability) * 80}%`}} title="Mixed Edge"></div>
                    <div className="bg-rose-500 transition-all duration-1000" style={{width: `${(1 - reliability) * 20}%`}} title="High Contamination"></div>
                </div>
                <div className="text-sm font-mono font-bold text-slate-400 bg-slate-200/50 dark:bg-slate-800 px-3 py-1 rounded-lg">
                  σ ±{uncertaintySigma.toFixed(2)}
                </div>
            </div>
            <p className="text-[10px] text-slate-400 mt-3 max-w-lg">
              Fraction of edge pixels overlapping non-agricultural boundaries (e.g., adjacent roads or bare soil). Values under 15% mixed contamination are considered acceptable for aggregated spatial means.
            </p>
        </div>
      </div>
    </div>
  );
}
