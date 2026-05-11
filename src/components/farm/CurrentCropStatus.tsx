"use client";

import { 
  Sprout, 
  Calendar, 
  TrendingUp,
  Activity,
  Info
} from "lucide-react";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";

interface CropCycle {
  id: string;
  cropCode: string;
  variety?: string | null;
  startDate?: string | Date | null;
  [key: string]: any;
}

interface CurrentCropStatusProps {
  cycles: CropCycle[];
  readinessScore: number;
}

export default function CurrentCropStatus({ 
  cycles, 
  readinessScore
}: CurrentCropStatusProps) {
  const currentCycle = cycles[0] || null;

  // Pull REAL phenology data from backend
  let stage = "Unknown";
  let dap: number | null = null;
  let plantDate: string | null = null;
  let basis: string | null = null;

  try {
    const pi = usePlotIntelligence();
    if (pi?.data?.cropPhenology) {
      const pheno = pi.data.cropPhenology;
      if (pheno.stage) stage = pheno.stage;
      if (pheno.dap != null) dap = pheno.dap;
      if (pheno.plant_date) plantDate = pheno.plant_date;
      if (pheno.basis) basis = pheno.basis;
    }
  } catch { /* not in provider */ }

  // Compute real GDD progress (approximate from DAP if available)
  const gddProgress = dap != null ? Math.min(100, Math.round((dap / 120) * 100)) : null;

  // Dynamic Yield Confidence based on Readiness
  const yieldConfidence = Math.round(readinessScore * 0.95);
  const confidenceTier = yieldConfidence >= 80 ? 'High' : yieldConfidence >= 50 ? 'Moderate' : 'Low';

  return (
    <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "linear-gradient(135deg, rgba(16,185,129,0.04) 0%, rgba(11,16,21,0.9) 40%)" }}>
      <div className="px-6 py-4 border-b border-white/[0.04] flex justify-between items-center">
        <h3 className="font-semibold text-white flex items-center gap-2 text-sm">
          <Sprout className="text-emerald-500" size={18} />
          Current Crop Status
        </h3>
        <button className="text-[10px] font-bold bg-emerald-500/10 text-emerald-400 px-3 py-1.5 rounded-lg border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors uppercase tracking-wider">
          Log New Cycle
        </button>
      </div>
        
      <div className="p-6">
        {currentCycle ? (
          <div className="flex flex-col md:flex-row items-start gap-6 w-full">
            {/* Icon */}
            <div className="w-16 h-16 rounded-xl bg-emerald-500/10 border border-emerald-500/15 flex items-center justify-center text-emerald-400 shrink-0">
              <Sprout size={32} />
            </div>
            
            <div className="flex-1 min-w-0 w-full">
              {/* Stage badge — REAL from backend */}
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest">
                  {stage}
                </span>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                {basis && (
                  <span className="text-[8px] text-slate-600 font-mono uppercase tracking-wider bg-white/[0.03] px-1.5 py-0.5 rounded">
                    via {basis}
                  </span>
                )}
              </div>

              {/* Crop name */}
              <h4 className="text-2xl font-bold text-white truncate">
                {currentCycle.cropCode || "Unknown Crop"}
              </h4>

              {/* Details row */}
              <div className="text-sm text-slate-500 mt-1 flex items-center gap-3 flex-wrap">
                <span className="flex items-center gap-1.5">
                  <span className="text-slate-400">Variety:</span>
                  {currentCycle.variety || "Not specified"}
                </span>
                <span className="text-white/10">|</span>
                <span className="flex items-center gap-1.5">
                  <Calendar size={13} className="text-slate-600" />
                  {plantDate || (currentCycle.startDate ? new Date(currentCycle.startDate).toLocaleDateString() : "Unknown")}
                </span>
                {dap != null && (
                  <>
                    <span className="text-white/10">|</span>
                    <span className="text-emerald-400 font-mono font-bold text-xs">{dap} DAP</span>
                  </>
                )}
              </div>

              {/* Metrics Grid — REAL data */}
              <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-3">
                {/* DAP / Growth Progress */}
                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <p className="text-[9px] uppercase font-bold text-emerald-400/70 mb-1.5 flex items-center gap-1">
                    <Calendar size={11} /> Days After Planting
                  </p>
                  <p className="text-lg font-bold font-mono text-white">
                    {dap != null ? (
                      <>{dap} <span className="text-xs font-normal text-slate-500">days</span></>
                    ) : (
                      <span className="text-slate-600 text-sm italic">No plant date</span>
                    )}
                  </p>
                </div>

                {/* GDD Progress — computed from real DAP */}
                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <p className="text-[9px] uppercase font-bold text-emerald-400/70 mb-1.5 flex items-center gap-1">
                    <TrendingUp size={11} /> Growth Progress
                  </p>
                  {gddProgress != null ? (
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 rounded-full transition-all duration-700" style={{ width: `${gddProgress}%` }} />
                      </div>
                      <span className="text-xs font-bold font-mono text-white">{gddProgress}%</span>
                    </div>
                  ) : (
                    <span className="text-slate-600 text-sm italic">—</span>
                  )}
                </div>

                {/* Yield Confidence */}
                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04] col-span-2 md:col-span-1 group relative">
                  <div className="absolute bottom-full mb-2 hidden group-hover:block w-48 bg-slate-800 text-slate-200 text-[10px] p-2 rounded-lg shadow-lg z-50 border border-white/10">
                    <p className="font-bold mb-1 text-slate-100">Confidence influenced by:</p>
                    <ul className="list-disc pl-3 space-y-0.5 text-slate-400">
                      <li>Soil recency</li>
                      <li>Live monitoring coverage</li>
                      <li>Crop parameter completeness</li>
                    </ul>
                  </div>
                  <p className="text-[9px] uppercase font-bold text-emerald-400/70 mb-1.5 flex items-center gap-1 cursor-help">
                    <Activity size={11} /> Yield Confidence <Info size={8} className="text-emerald-400/50" />
                  </p>
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold font-mono ${yieldConfidence >= 80 ? 'text-emerald-400' : yieldConfidence >= 50 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {yieldConfidence}%
                    </span>
                    <span className="text-[10px] text-slate-600">{confidenceTier}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="w-full text-center py-6">
            <p className="text-slate-500 text-sm">No active crop cycle found for this plot.</p>
          </div>
        )}
      </div>
    </div>
  );
}
