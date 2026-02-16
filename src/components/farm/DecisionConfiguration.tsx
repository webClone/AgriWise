"use client";

import { 
  Settings2, 
  Activity,
  Droplets, 
  Info,
  ChevronRight,
  Plus
} from "lucide-react";
import { useState, useEffect } from "react";

interface DecisionConfigurationProps {
  initialIrrigation: string | null;
  initialSoilType: string | null;
}

export default function DecisionConfiguration({ 
  initialIrrigation,
  initialSoilType 
}: DecisionConfigurationProps) {
  const [showRecalibrating, setShowRecalibrating] = useState(false);

  // Simulate model recalibration for demo effect
  useEffect(() => {
      const timer = setTimeout(() => setShowRecalibrating(true), 2000);
      const timer2 = setTimeout(() => setShowRecalibrating(false), 5000);
      return () => { clearTimeout(timer); clearTimeout(timer2); };
  }, []);

  return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col border-l-4 border-l-indigo-500 relative">
          <div className="absolute top-0 right-0 p-3 opacity-5">
            <Settings2 size={80} />
          </div>
          <div className="bg-slate-50 dark:bg-slate-950 px-6 py-4 border-b border-slate-100 dark:border-slate-800 relative z-10">
            <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <Settings2 className="text-indigo-500" size={18} />
                Decision Configuration
            </h3>
            <div className="flex items-center justify-between mt-1">
                <p className="text-[10px] text-slate-500 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse"></span>
                    Used in irrigation, nutrient & yield models
                </p>
                {showRecalibrating && (
                    <span className="text-[9px] font-bold text-indigo-500 flex items-center gap-1 animate-pulse bg-indigo-50 dark:bg-indigo-900/20 px-2 py-0.5 rounded-full border border-indigo-100 dark:border-indigo-800">
                        <Activity size={10} /> Model Recalibrated
                    </span>
                )}
            </div>
          </div>
          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between group cursor-pointer">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 rounded-lg group-hover:bg-indigo-100 transition-colors">
                        <Droplets size={16} />
                    </div>
                    <div>
                        <p className="text-[10px] text-slate-400 uppercase font-bold tracking-tight leading-none mb-1">Irrigation</p>
                        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{initialIrrigation || "Not Set"}</p>
                    </div>
                </div>
                <ChevronRight size={16} className="text-slate-300 group-hover:text-indigo-400 transition-colors" />
            </div>

            <div className="flex items-center justify-between group cursor-pointer">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 rounded-lg group-hover:bg-amber-100 transition-colors">
                        <Info size={16} />
                    </div>
                    <div>
                        <p className="text-[10px] text-slate-400 uppercase font-bold tracking-tight leading-none mb-1">Soil Type</p>
                        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{initialSoilType || "Undetermined"}</p>
                    </div>
                </div>
                <ChevronRight size={16} className="text-slate-300 group-hover:text-amber-400 transition-colors" />
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-dashed border-slate-200 dark:border-slate-800">
                 <div className="p-2 bg-slate-50 dark:bg-slate-800/50 rounded border border-slate-100 dark:border-slate-800">
                    <p className="text-[9px] text-slate-400 uppercase font-bold mb-1">Fertigation</p>
                    <p className="text-xs font-medium text-slate-600 dark:text-slate-300">Manual</p>
                 </div>
                 <div className="p-2 bg-slate-50 dark:bg-slate-800/50 rounded border border-slate-100 dark:border-slate-800">
                    <p className="text-[9px] text-slate-400 uppercase font-bold mb-1">Drainage</p>
                    <p className="text-xs font-medium text-slate-600 dark:text-slate-300">Natural</p>
                 </div>
                 <div className="p-2 bg-slate-50 dark:bg-slate-800/50 rounded border border-slate-100 dark:border-slate-800">
                    <p className="text-[9px] text-slate-400 uppercase font-bold mb-1">Density</p>
                    <p className="text-xs font-medium text-slate-600 dark:text-slate-300 flex items-center justify-between">
                        45k/ha <span className="text-[9px] text-emerald-500">Optimum</span>
                    </p>
                 </div>
                 <div className="p-2 bg-slate-50 dark:bg-slate-800/50 rounded border border-slate-100 dark:border-slate-800">
                    <p className="text-[9px] text-slate-400 uppercase font-bold mb-1">Maturity</p>
                    <p className="text-xs font-medium text-slate-600 dark:text-slate-300">Mid-Late</p>
                 </div>
            </div>

            <button className="w-full mt-2 py-2 text-xs font-bold text-slate-500 hover:text-indigo-500 transition-colors border border-dashed border-slate-200 dark:border-slate-800 rounded-lg flex items-center justify-center gap-1">
                <Plus size={14} /> Add Management Parameter
            </button>
          </div>
      </div>
  );
}
