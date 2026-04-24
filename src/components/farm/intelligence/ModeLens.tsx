"use client";

import { ChevronLeft } from "lucide-react";
import { type MapMode, MODE_CONFIG } from "@/hooks/useLayer10";

interface ModeLensProps {
  activeMode: MapMode;
  onModeChange: (mode: MapMode) => void;
  screenState: "observe" | "diagnose";
  onBackToField?: () => void;
}

const MODES: MapMode[] = ["canopy", "veg_attention", "water_stress", "nutrient_risk", "composite_risk", "uncertainty"];

const MODE_SHORT: Record<MapMode, string> = {
  vegetation: "Canopy",
  canopy: "Canopy",
  veg_attention: "Veg. Attention",
  water_stress: "Water",
  nutrient_risk: "Nutrients",
  composite_risk: "Risk",
  uncertainty: "Confidence",
};

export default function ModeLens({
  activeMode,
  onModeChange,
  screenState,
  onBackToField
}: ModeLensProps) {
  return (
    <div className="flex items-center gap-1 bg-white/5 rounded-full p-1" id="mode-lens">
      {screenState === "diagnose" && onBackToField && (
        <>
          <button
            className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-full transition-all text-xs font-semibold tracking-wide text-zinc-400 hover:text-white hover:bg-white/10"
            onClick={onBackToField}
            title="Back to Field Overview"
          >
            <ChevronLeft size={14} />
            <span>Field</span>
          </button>
          <div className="w-px h-4 bg-white/10 mx-1" />
        </>
      )}
      {MODES.map((mode) => {
        const config = MODE_CONFIG[mode];
        const isActive = activeMode === mode;

        return (
          <button
            key={mode}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full transition-all text-xs font-semibold tracking-wide ${
                isActive 
                  ? "bg-white text-[#0B1015] shadow-sm" 
                  : "text-zinc-400 hover:text-white hover:bg-white/10"
            }`}
            onClick={() => onModeChange(mode)}
            title={MODE_SHORT[mode]}
            id={`mode-lens-${mode}`}
          >
            <span className="w-3 h-3 flex items-center justify-center opacity-80">{config.icon}</span>
            <span>{MODE_SHORT[mode]}</span>
          </button>
        );
      })}
    </div>
  );
}
