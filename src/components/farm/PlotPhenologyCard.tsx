"use client";

import { Sprout } from "lucide-react";
import { useLayer10 } from "@/hooks/useLayer10";

interface PlotPhenologyCardProps {
  lat: number;
  lng: number;
  crop: string;
}

/**
 * Canonical phenology receipt viewer.
 *
 * Location, crop calendars, DAP and GDD are useful Layer-2 inputs, but this
 * browser component is not permitted to turn them into a growth stage.
 */
export default function PlotPhenologyCard({ crop }: PlotPhenologyCardProps) {
  const l10 = useLayer10();
  const phenology = l10.evidenceState.resolvedPhenology;

  return (
    <div className="card fade-in p-6 border border-slate-200 dark:border-slate-700 bg-gradient-to-br from-teal-50 to-slate-50 dark:from-teal-950 dark:to-slate-900 text-slate-900 dark:text-white">
      <h3 className="m-0 mb-4 font-semibold flex items-center gap-2 text-lg">
        <Sprout size={18} /> Layer 2 Phenology
      </h3>
      <div className="rounded-xl border border-teal-100 dark:border-teal-900/30 bg-white/50 dark:bg-white/5 p-4">
        <div className="text-[0.65rem] text-slate-500 uppercase tracking-widest font-bold">
          {crop || "Unknown crop"} · canonical stage
        </div>
        <div className="mt-1 text-xl font-bold">
          {phenology.stage?.replaceAll("_", " ") || "UNKNOWN"}
        </div>
        <div className="mt-2 text-xs text-slate-500">
          {phenology.stage
            ? `Authority: ${phenology.authority}`
            : phenology.userLabel}
        </div>
        {phenology.receiptValid && phenology.posteriorHash && (
          <div className="mt-3 font-mono text-[10px] text-slate-500" title={phenology.posteriorHash}>
            Receipt {phenology.posteriorHash.slice(0, 16)}
          </div>
        )}
      </div>
    </div>
  );
}
