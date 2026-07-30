"use client";

import { useMemo } from "react";
import { type Layer10Result, type MapMode, useLayer10, MAP_SEMANTICS_LABELS } from "@/hooks/useLayer10";
import { generateFieldSentence, MICRO_LEGEND } from "./fieldInsightAdapter";
import { MODE_CONFIG } from "@/hooks/useLayer10";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";

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

  // Farmer/Expert toggle from PlotIntelligence
  let piDetailMode: "farmer" | "expert" = "farmer";
  let piSetDetailMode: ((m: "farmer" | "expert") => void) | null = null;
  try {
    const pi = usePlotIntelligence();
    piDetailMode = pi.detailMode;
    piSetDetailMode = pi.setDetailMode;
  } catch { /* not in provider */ }

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
    <div className="mx-auto w-max max-w-[90vw] flex items-center justify-between gap-4 sm:gap-6 bg-[#080C19]/92 backdrop-blur-xl border border-white/10 p-2 ps-4 pe-2 rounded-full shadow-2xl mb-4 pointer-events-auto" id="field-insight-bar">
      
      {/* ── Map Semantics Badge (Patch 5) ── */}
      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-slate-400 shrink-0">
        {MAP_SEMANTICS_LABELS[l10.mapSemantics]}
      </span>

      {/* ── Standard Localized / Insight View ── */}
      {/* Fix D: canopy/vegetation mode is purely observational — never show the
           fallback guidance block, even if NDVI_CLEAN has no spatial zones.
           Fallback guidance is only useful for action modes (water, nutrient, risk). */}
      {(!l10.fallbackGuidance || activeMode === "canopy" || activeMode === "vegetation") && (
        <>
          {/* Sentence */}
          <div className="flex-1 min-w-0" dir="ltr">
            <p className="text-sm font-medium text-white/90 truncate text-left max-w-[400px]" title={insight.sentence}>
              {insight.sentence}
            </p>
          </div>

          <div className="flex items-center gap-2">
              {/* Micro legend compact chip */}
              <div className="flex items-center gap-1.5 px-3 py-1 bg-white/5 rounded-full border border-white/5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[0] }} title={legend.low} />
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[1] }} title={legend.mid} />
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[2] }} title={legend.high} />
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2 border-s border-white/10 ps-2 ms-1">
                  {insight.hasIssues && insight.topZoneId && (
                      <button
                          className="flex items-center justify-center px-4 py-1.5 text-sm font-semibold rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-white/5"
                          onClick={() => onInspect(insight.topZoneId!)}
                          id="insight-bar-inspect"
                      >
                          Diagnose
                      </button>
                  )}

            {/* Farmer/Expert Toggle */}
            {piSetDetailMode && (
              <div className="flex items-center gap-0.5 bg-white/5 rounded-full p-0.5">
                <button
                    onClick={() => piSetDetailMode!("farmer")}
                    className={`px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider transition-all ${
                        piDetailMode === "farmer"
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                            : "text-zinc-500 hover:text-zinc-300 border border-transparent"
                    }`}
                >
                    🌾 Farmer
                </button>
                <button
                    onClick={() => piSetDetailMode!("expert")}
                    className={`px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider transition-all ${
                        piDetailMode === "expert"
                            ? "bg-indigo-500/15 text-indigo-400 border border-indigo-500/20"
                            : "text-zinc-500 hover:text-zinc-300 border border-transparent"
                    }`}
                >
                    🔬 Expert
                </button>
              </div>
            )}
              </div>
          </div>
        </>
      )}

      {/* ── Fallback Action Block (Fix 6 + Fix 7: water cross-reference) ── */}
      {/* Fix D part 2: exclude canopy/vegetation — they are observational modes, never action. */}
      {l10.fallbackGuidance && activeMode !== "canopy" && activeMode !== "vegetation" && (() => {
        // Fix 7: Cross-reference water fallback guidance with actual surface data
        // to prevent "no stress" banner when sidebar shows 64mm deficit
        let guidanceWhy = l10.fallbackGuidance.why;
        let guidanceStep = l10.fallbackGuidance.recommended_next_step;
        let guidanceBasis = l10.fallbackGuidance.data_basis;
        
        if (activeMode === "water_stress" && data) {
          const waterSurf = data.surfaces?.find(s => s.type === "WATER_STRESS_PROB");
          if (waterSurf) {
            const vals = waterSurf.values.flat().filter((v): v is number => v != null && !isNaN(v));
            const mean = vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
            if (mean > 0.5 && guidanceBasis === "no_concerning_zones") {
              guidanceWhy = `Field-wide water stress detected (probability ${Math.round(mean * 100)}%). Stress is broadly distributed — no localized hotspots.`;
              guidanceStep = "Increase irrigation frequency or volume; check soil moisture sensors if available";
              guidanceBasis = "surface_cross_reference";
            } else if (mean > 0.25 && guidanceBasis === "no_concerning_zones") {
              guidanceWhy = `Moderate water stress indicated (probability ${Math.round(mean * 100)}%). Soil moisture may be declining.`;
              guidanceStep = "Monitor soil moisture closely; consider advancing next irrigation";
              guidanceBasis = "surface_cross_reference";
            }
          }
        }

        return (
        <div className="flex items-center gap-4">
          <div className="flex flex-col max-w-[450px] min-w-0" dir="ltr">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400 mb-0.5 text-left">
              {l10.fallbackGuidance.action_mode.replace(/_/g, " ")} • {guidanceBasis.replace(/_/g, " ")}
            </span>
            <p className="text-sm font-medium text-white/90 truncate text-left w-full" title={guidanceWhy}>
              {guidanceWhy}
            </p>
            <p className="text-[13px] text-slate-400 truncate mt-0.5 text-left w-full" title={`Recommended: ${guidanceStep}`}>
              <span className="text-indigo-400 font-semibold mr-1">Recommended:</span>
              {guidanceStep}
            </p>
          </div>

          <div className="flex items-center gap-2 border-s border-white/10 ps-4 ms-2">

            {/* Farmer/Expert Toggle */}
            {piSetDetailMode && (
              <div className="flex items-center gap-0.5 bg-white/5 rounded-full p-0.5">
                <button
                    onClick={() => piSetDetailMode!("farmer")}
                    className={`px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider transition-all ${
                        piDetailMode === "farmer"
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                            : "text-zinc-500 hover:text-zinc-300 border border-transparent"
                    }`}
                >
                    🌾 Farmer
                </button>
                <button
                    onClick={() => piSetDetailMode!("expert")}
                    className={`px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider transition-all ${
                        piDetailMode === "expert"
                            ? "bg-indigo-500/15 text-indigo-400 border border-indigo-500/20"
                            : "text-zinc-500 hover:text-zinc-300 border border-transparent"
                    }`}
                >
                    🔬 Expert
                </button>
              </div>
            )}
          </div>
        </div>
      );})()}
    </div>
  );
}
