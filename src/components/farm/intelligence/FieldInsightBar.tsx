"use client";

import { useMemo } from "react";
import { type Layer10Result, type MapMode, useLayer10, MAP_SEMANTICS_LABELS } from "@/hooks/useLayer10";
import { generateFieldSentence, MICRO_LEGEND } from "./fieldInsightAdapter";
import { MODE_CONFIG } from "@/hooks/useLayer10";

interface FieldInsightBarProps {
  data: Layer10Result | null;
  activeMode: MapMode;
  loading: boolean;
  onInspect: (zoneId: string) => void;
}

export default function FieldInsightBar({
  data,
  activeMode,
  loading,
  onInspect,
}: FieldInsightBarProps) {
  const l10 = useLayer10();

  const insight = useMemo(() => {
    if (!data) return null;
    return generateFieldSentence(data, activeMode, {
      plotDataAvailable: !!l10?.plotDataAvailable,
      spatialSurfaceAvailable: !!l10?.spatialSurfaceAvailable,
      localizedZoneAvailable: !!l10?.localizedZoneAvailable,
    });
  }, [data, activeMode, l10?.plotDataAvailable, l10?.spatialSurfaceAvailable, l10?.localizedZoneAvailable]);

  const legend = MICRO_LEGEND[activeMode] || MICRO_LEGEND.vegetation;
  const colors = MODE_CONFIG[activeMode]?.colors || ["#22c55e", "#eab308", "#ef4444"];

  if (loading) {
    return (
      <div className="aw-insight-bar" id="field-insight-bar">
        <div className="aw-insight-bar__loading">
          <div className="aw-insight-bar__pulse" />
          <span>Analyzing your field…</span>
        </div>
      </div>
    );
  }

  if (l10?.isDecideMode) return null;

  if (!data || !insight) return null;

  return (
    <div className="mx-auto w-max max-w-[90vw] flex items-center justify-between gap-4 sm:gap-6 bg-[#0B1015]/80 backdrop-blur-xl border border-white/10 p-2 pl-4 pr-2 rounded-full shadow-2xl mb-4 pointer-events-auto" id="field-insight-bar">
      
      {/* ── Map Semantics Badge (Patch 5) ── */}
      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-slate-400 shrink-0">
        {MAP_SEMANTICS_LABELS[l10.mapSemantics]}
      </span>

      {/* ── Standard Localized / Insight View ── */}
      {!l10.fallbackGuidance && (
        <>
          {/* Sentence */}
          <p className="text-sm font-medium text-white/90 truncate max-w-[400px]">
            {insight.sentence}
          </p>

          <div className="flex items-center gap-2">
              {/* Micro legend compact chip */}
              <div className="flex items-center gap-1.5 px-3 py-1 bg-white/5 rounded-full border border-white/5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[0] }} title={legend.low} />
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[1] }} title={legend.mid} />
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[2] }} title={legend.high} />
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2 border-l border-white/10 pl-2 ml-1">
                  {insight.hasIssues && insight.topZoneId && (
                      <button
                          className="flex items-center justify-center px-4 py-1.5 text-sm font-semibold rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-white/5"
                          onClick={() => onInspect(insight.topZoneId!)}
                          id="insight-bar-inspect"
                      >
                          Diagnose
                      </button>
                  )}
                  
                  <button
                      className="flex items-center justify-center px-4 py-1.5 text-sm font-semibold rounded-full bg-indigo-500 hover:bg-indigo-400 text-white transition-colors"
                      onClick={() => l10.setIsDecideMode(true)}
                      id="insight-bar-decide"
                  >
                      Decide with AgriBrain
                  </button>
              </div>
          </div>
        </>
      )}

      {/* ── Fallback Action Block (Fix 6) ── */}
      {l10.fallbackGuidance && (
        <div className="flex items-center gap-4">
          <div className="flex flex-col max-w-[450px]">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400 mb-0.5">
              {l10.fallbackGuidance.action_mode.replace(/_/g, " ")} • {l10.fallbackGuidance.data_basis.replace(/_/g, " ")}
            </span>
            <p className="text-sm font-medium text-white/90 truncate">
              {l10.fallbackGuidance.why}
            </p>
            <p className="text-[13px] text-slate-400 truncate mt-0.5">
              <span className="text-indigo-400 font-semibold mr-1">Recommended:</span>
              {l10.fallbackGuidance.recommended_next_step}
            </p>
          </div>

          <div className="flex items-center gap-2 border-l border-white/10 pl-4 ml-2">
            <button
                className="flex items-center justify-center px-4 py-1.5 text-sm font-semibold rounded-full bg-indigo-500 hover:bg-indigo-400 text-white transition-colors shrink-0"
                onClick={() => l10.setIsDecideMode(true)}
            >
                AgriBrain Advice
            </button>
            {(l10.fallbackGuidance.action_mode === "insufficient_data" || l10.fallbackGuidance.action_mode === "plot_level_only") && (
              <button
                  className="flex items-center justify-center px-4 py-1.5 text-sm font-semibold rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-white/5 shrink-0"
              >
                  + Add Evidence
              </button>
            )}
          </div>
        </div>
      )}

    </div>
  );
}
