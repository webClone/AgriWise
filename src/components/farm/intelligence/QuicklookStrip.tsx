"use client";

import type { MapMode, Layer10Result } from "@/hooks/useLayer10";
import { MODE_CONFIG, MODE_SURFACE_MAP } from "@/hooks/useLayer10";

interface QuicklookStripProps {
  data: Layer10Result;
  activeMode: MapMode;
  onModeChange: (mode: MapMode) => void;
}

const MODES_ORDER: MapMode[] = ["vegetation", "water_stress", "nutrient_risk", "composite_risk", "uncertainty"];

export default function QuicklookStrip({ data, activeMode, onModeChange }: QuicklookStripProps) {
  return (
    <div className="quicklook-strip" id="quicklook-strip">
      {MODES_ORDER.map((mode) => {
        const config = MODE_CONFIG[mode];
        const surfaceType = MODE_SURFACE_MAP[mode];
        const hasQuicklook = !!data.quicklooks[surfaceType];
        const isActive = activeMode === mode;

        return (
          <button
            key={mode}
            className={`quicklook-thumb ${isActive ? "active" : ""}`}
            onClick={() => onModeChange(mode)}
            title={`${config.label}${hasQuicklook ? "" : " (no data)"}`}
            id={`quicklook-${mode}`}
          >
            <div
              className="w-full h-full"
              style={{
                background: `linear-gradient(135deg, ${config.colors[0]}, ${config.colors[1]}, ${config.colors[2]})`,
                opacity: hasQuicklook ? 1 : 0.4,
              }}
            />
            {/* Mode icon overlay */}
            <div className="absolute inset-0 flex items-center justify-center text-sm opacity-80">
              {config.icon}
            </div>
          </button>
        );
      })}

      {/* Info label */}
      <div className="flex items-center ml-2 pl-2 border-l border-slate-700/50">
        <span className="text-[10px] text-slate-500 whitespace-nowrap">
          {data.surfaces.length} surfaces · {data.zones.length} zones
        </span>
      </div>
    </div>
  );
}
