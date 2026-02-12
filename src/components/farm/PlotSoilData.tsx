"use client";

import { Leaf, Cpu } from "lucide-react";
import SoilAnalysisHistory from "./SoilAnalysisHistory";
import SensorList from "./SensorList";

interface PlotSoilDataProps {
  plotId: string;
  soilAnalyses: any[];
  sensors: any[];
}

export default function PlotSoilData({ plotId, soilAnalyses, sensors }: PlotSoilDataProps) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      
      {/* Header */}
      <div className="bg-slate-50 dark:bg-slate-950 px-6 py-4 border-b border-slate-100 dark:border-slate-800">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
           <Leaf className="text-amber-500" size={18} />
           Soil & Physical Properties
        </h3>
        <p className="text-xs text-slate-500 mt-1">
            Track soil composition and connected sensor streams.
        </p>
      </div>

      <div className="p-6 space-y-8">
        
        {/* Soil Analysis History */}
        <section>
            <SoilAnalysisHistory plotId={plotId} analyses={soilAnalyses || []} />
        </section>

        <hr className="border-slate-100 dark:border-slate-800" />

        {/* Sensors */}
        <section>
            <SensorList plotId={plotId} sensors={sensors || []} />
        </section>

      </div>
    </div>
  );
}
