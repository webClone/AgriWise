"use client";

import { 
  Sprout, 
  Calendar, 
  Activity,
  Info
} from "lucide-react";
import { useLayer10 } from "@/hooks/useLayer10";

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

  const l10 = useLayer10();
  const phenology = l10.evidenceState.resolvedPhenology;
  const stage = phenology.stage || "UNKNOWN";
  const recordedPlantDate = currentCycle?.startDate
    ? new Date(currentCycle.startDate).toLocaleDateString()
    : null;

  // Readiness is configuration completeness, not a yield-model confidence.
  const dataReadiness = Math.max(0, Math.min(100, Math.round(readinessScore)));
  const readinessTier = dataReadiness >= 80 ? 'High' : dataReadiness >= 50 ? 'Moderate' : 'Low';

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
                <span className={`w-1.5 h-1.5 rounded-full ${phenology.stage ? "bg-emerald-500" : "bg-slate-600"}`} />
                <span className="text-[8px] text-slate-600 font-mono uppercase tracking-wider bg-white/[0.03] px-1.5 py-0.5 rounded">
                  Layer 2 · {phenology.authority}
                </span>
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
                  {recordedPlantDate || "Planting date not recorded"}
                </span>
              </div>

              {/* Metrics Grid — REAL data */}
              <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-3">
                {/* Administrative start date; never converted into phenology. */}
                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <p className="text-[9px] uppercase font-bold text-emerald-400/70 mb-1.5 flex items-center gap-1">
                    <Calendar size={11} /> Recorded Start Date
                  </p>
                  <p className="text-sm font-bold font-mono text-white">
                    {recordedPlantDate || <span className="text-slate-600 italic">Not recorded</span>}
                  </p>
                </div>

                {/* Content-addressed Layer-2 phenology publication. */}
                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <p className="text-[9px] uppercase font-bold text-emerald-400/70 mb-1.5 flex items-center gap-1">
                    <Info size={11} /> Layer 2 Receipt
                  </p>
                  <p className="text-xs font-mono text-white" title={phenology.posteriorHash || phenology.userLabel}>
                    {phenology.receiptValid && phenology.posteriorHash
                      ? phenology.posteriorHash.slice(0, 12)
                      : phenology.userLabel}
                  </p>
                </div>

                {/* Configuration readiness; never presented as model confidence. */}
                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04] col-span-2 md:col-span-1 group relative">
                  <div className="absolute bottom-full mb-2 hidden group-hover:block w-48 bg-slate-800 text-slate-200 text-[10px] p-2 rounded-lg shadow-lg z-50 border border-white/10">
                    <p className="font-bold mb-1 text-slate-100">Readiness checks:</p>
                    <ul className="list-disc pl-3 space-y-0.5 text-slate-400">
                      <li>Soil recency</li>
                      <li>Live monitoring coverage</li>
                      <li>Crop parameter completeness</li>
                    </ul>
                  </div>
                  <p className="text-[9px] uppercase font-bold text-emerald-400/70 mb-1.5 flex items-center gap-1 cursor-help">
                    <Activity size={11} /> Data Readiness <Info size={8} className="text-emerald-400/50" />
                  </p>
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold font-mono ${dataReadiness >= 80 ? 'text-emerald-400' : dataReadiness >= 50 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {dataReadiness}%
                    </span>
                    <span className="text-[10px] text-slate-600">{readinessTier}</span>
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
