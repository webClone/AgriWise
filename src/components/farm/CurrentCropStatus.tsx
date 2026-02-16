"use client";

import { 
  Sprout, 
  Calendar, 
  TrendingUp,
  Activity,
  Info
} from "lucide-react";

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

  // Dynamic Yield Confidence based on Readiness
  const yieldConfidence = Math.round(readinessScore * 0.95);
  const confidenceTier = yieldConfidence >= 80 ? 'High' : yieldConfidence >= 50 ? 'Moderate' : 'Low';

  return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col">
          <div className="bg-emerald-50/50 dark:bg-emerald-900/10 px-6 py-4 border-b border-emerald-100/50 dark:border-emerald-800/50 flex justify-between items-center">
            <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <Sprout className="text-emerald-500" size={18} />
                Current Crop Status
            </h3>
            <button className="text-[10px] font-bold bg-white dark:bg-slate-800 text-emerald-600 dark:text-emerald-400 px-2 py-1 rounded border border-emerald-200 dark:border-emerald-700 hover:bg-emerald-50 transition-colors uppercase tracking-wider">
                Log New Cycle
            </button>
          </div>
          
          <div className="p-6 flex-1 flex items-center">
            {currentCycle ? (
              <div className="flex flex-col md:flex-row items-center gap-6 w-full">
                <div className="flex items-center gap-6 w-full md:w-auto">
                    <div className="w-20 h-20 bg-emerald-100 dark:bg-emerald-900/30 rounded-2xl flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0 border border-emerald-200 dark:border-emerald-800">
                        <Sprout size={40} />
                    </div>
                </div>
                
                <div className="flex-1 min-w-0 w-full">
                    <div className="flex items-center gap-2 mb-1">
                        <div className="flex flex-col">
                            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-widest">
                                Vegetative Stage
                            </span>
                            <span className="text-[9px] font-medium text-emerald-600/60 dark:text-emerald-400/60">
                                Next: Flowering (~18 days)
                            </span>
                        </div>
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse mt-1" />
                    </div>
                    <h4 className="text-3xl font-bold text-slate-800 dark:text-slate-100 truncate">
                        {currentCycle.cropCode || "Unknown Crop"}
                    </h4>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 flex items-center gap-2">
                        <span className="font-medium text-slate-700 dark:text-slate-300">Variety:</span> {currentCycle.variety || "Not specified"}
                        <span className="text-slate-300 dark:text-slate-600 mx-1">|</span>
                        <Calendar size={14} className="text-slate-400" />
                        Planted: {currentCycle.startDate ? new Date(currentCycle.startDate).toLocaleDateString() : "Unknown"}
                    </p>

                    {/* Predictive Insights - Refined for compact display if needed */}
                    <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-4">
                        <div className="bg-emerald-50/50 dark:bg-emerald-900/10 rounded-lg p-3 border border-emerald-100/50 dark:border-emerald-800/20">
                            <p className="text-[10px] uppercase font-bold text-emerald-600/70 dark:text-emerald-400 mb-1 flex items-center gap-1">
                                <Calendar size={12} /> Est. Harvest
                            </p>
                            <p className="text-sm font-bold text-slate-700 dark:text-slate-200">
                                45 Days <span className="text-[10px] font-normal text-slate-500">(Oct 12)</span>
                            </p>
                        </div>
                        <div className="bg-emerald-50/50 dark:bg-emerald-900/10 rounded-lg p-3 border border-emerald-100/50 dark:border-emerald-800/20">
                            <p className="text-[10px] uppercase font-bold text-emerald-600/70 dark:text-emerald-400 mb-1 flex items-center gap-1">
                                <TrendingUp size={12} /> GDD Progress
                            </p>
                            <div className="flex items-center gap-2">
                                <div className="flex-1 h-1.5 bg-emerald-200 dark:bg-emerald-800 rounded-full overflow-hidden">
                                    <div className="h-full bg-emerald-500 w-[65%]" />
                                </div>
                                <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300">65%</span>
                            </div>
                        </div>
                        <div className="bg-emerald-50/50 dark:bg-emerald-900/10 rounded-lg p-3 border border-emerald-100/50 dark:border-emerald-800/20 group relative col-span-2 md:col-span-1">
                            <div className="absolute bottom-full mb-2 hidden group-hover:block w-48 bg-slate-800 text-slate-200 text-[10px] p-2 rounded shadow-lg z-50">
                                <p className="font-bold mb-1 text-slate-100">Confidence influenced by:</p>
                                <ul className="list-disc pl-3 space-y-0.5 text-slate-300">
                                    <li>Soil recency</li>
                                    <li>Live monitoring coverage</li>
                                    <li>Crop parameter completeness</li>
                                </ul>
                            </div>
                            <p className="text-[10px] uppercase font-bold text-emerald-600/70 dark:text-emerald-400 mb-1 flex items-center gap-1 cursor-help">
                                <Activity size={12} /> Yield Confidence <Info size={8} className="text-emerald-400" />
                            </p>
                            <div className="flex items-center gap-2">
                                <span className={`text-sm font-bold ${yieldConfidence >= 80 ? 'text-emerald-600' : yieldConfidence >= 50 ? 'text-amber-600' : 'text-slate-600'} dark:text-slate-200`}>{yieldConfidence}%</span>
                                <span className="text-[10px] font-normal text-slate-500">
                                    - {confidenceTier}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
              </div>
            ) : (
                <div className="w-full text-center py-4">
                    <p className="text-slate-400 italic">No active crop cycle found for this plot.</p>
                </div>
            )}
          </div>
      </div>
  );
}
