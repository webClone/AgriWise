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
    <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "linear-gradient(180deg, rgba(11,16,21,0.9) 0%, rgba(8,12,25,0.95) 100%)" }}>
      
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/[0.04]">
        <h3 className="font-semibold text-white flex items-center gap-2 text-sm">
           <Leaf className="text-amber-500" size={18} />
           Soil & Physical Properties
        </h3>
        <p className="text-[10px] text-slate-500 mt-1">
            Enables nutrient optimization & salinity risk detection.
        </p>
      </div>

      <div className="p-6 space-y-8">
        
        {/* Soil Analysis History */}
        <section>
            <SoilAnalysisHistory plotId={plotId} analyses={soilAnalyses || []} />
        </section>

        <hr className="border-white/[0.04]" />

        {/* Sensors */}
        <section>
            <SensorList plotId={plotId} sensors={sensors || []} />
        </section>

      </div>
    </div>
  );
}
