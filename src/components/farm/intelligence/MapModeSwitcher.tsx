"use client";

import { MapMode, MODE_CONFIG } from "@/hooks/useLayer10";

interface MapModeSwitcherProps {
  activeMode: MapMode;
  detailMode: "farmer" | "expert";
  onModeChange: (mode: MapMode) => void;
  onDetailModeChange: (mode: "farmer" | "expert") => void;
  loading?: boolean;
}

const MODES: MapMode[] = ["vegetation", "water_stress", "nutrient_risk", "composite_risk", "uncertainty"];

export default function MapModeSwitcher({ activeMode, detailMode, onModeChange, onDetailModeChange, loading }: MapModeSwitcherProps) {
  return (
    <div className="mode-switcher" id="map-mode-switcher">
      {MODES.map((mode) => {
        const config = MODE_CONFIG[mode];
        const isActive = activeMode === mode;

        return (
          <button
            key={mode}
            id={`mode-btn-${mode}`}
            className={`mode-btn ${isActive ? "active" : ""}`}
            onClick={() => onModeChange(mode)}
            disabled={loading}
            title={config.label}
          >
            <span
              className="mode-dot"
              style={{
                backgroundColor: isActive ? config.colors[2] : config.colors[1],
              }}
            />
            <span>{config.icon}</span>
            <span className="hidden sm:inline">{config.label}</span>
          </button>
        );
      })}

      {/* Pipeline badge */}
      <div className="ml-auto flex items-center gap-2 px-2">
        <label className="flex items-center cursor-pointer gap-2 group">
          <div className="relative">
            <input 
              type="checkbox" 
              className="sr-only" 
              checked={detailMode === "expert"}
              onChange={(e) => onDetailModeChange(e.target.checked ? "expert" : "farmer")}
              disabled={loading}
            />
            <div className={`w-8 h-4 rounded-full transition-colors ${detailMode === "expert" ? "bg-indigo-500" : "bg-slate-700"}`}></div>
            <div className={`absolute left-0.5 top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${detailMode === "expert" ? "translate-x-4" : "translate-x-0"}`}></div>
          </div>
          <span className={`text-[10px] font-bold uppercase tracking-wider ${detailMode === "expert" ? "text-indigo-400" : "text-slate-400"}`}>
            {detailMode}
          </span>
        </label>
        
        <div className="w-px h-4 bg-slate-700 mx-1"></div>
        
        <div className="flex items-center gap-1.5 opacity-50">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] font-mono text-slate-500">SIRE v10.5</span>
        </div>
      </div>
    </div>
  );
}
