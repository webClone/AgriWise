"use client";

import { ChevronLeft } from "lucide-react";
import { useLayer10, type MapMode, MODE_CONFIG } from "@/hooks/useLayer10";
import type { BaseSurfaceMode, OverlayKind } from "@/lib/agribrain/plot-map-evidence-state";
import { OVERLAY_LABELS } from "@/lib/agribrain/plot-map-evidence-state";

interface ModeLensProps {
  activeMode: MapMode;
  onModeChange: (mode: MapMode) => void;
  screenState: "observe" | "diagnose";
  onBackToField?: () => void;
}

// V92.3-C: Base surface modes (mutually exclusive radio selection)
const BASE_MODES: { mode: BaseSurfaceMode; mapMode: MapMode }[] = [
  { mode: "canopy", mapMode: "canopy" },
  { mode: "veg_attention", mapMode: "veg_attention" },
  { mode: "water_stress", mapMode: "water_stress" },
  { mode: "nutrient_risk", mapMode: "nutrient_risk" },
  { mode: "salinity", mapMode: "salinity" },
  { mode: "composite_risk", mapMode: "composite_risk" },
];

const MODE_SHORT: Record<MapMode, string> = {
  vegetation: "Canopy",
  canopy: "Canopy",
  veg_attention: "Veg. Attention",
  water_stress: "Water",
  nutrient_risk: "Nutrients",
  salinity: "Salinity",
  composite_risk: "Risk",
  uncertainty: "Confidence",
  resolution_coverage: "Resolution",
};

const TESTID_MAP: Record<MapMode, string> = {
  vegetation: "map-mode-canopy",
  canopy: "map-mode-canopy",
  veg_attention: "map-mode-veg_attention",
  water_stress: "map-mode-water",
  nutrient_risk: "map-mode-nutrients",
  salinity: "map-mode-salinity",
  composite_risk: "map-mode-risk",
  uncertainty: "map-mode-confidence",
  resolution_coverage: "map-mode-resolution",
};

// V92.3-C: Overlay toggle kinds (independent checkboxes)
const OVERLAY_TOGGLE_KINDS: OverlayKind[] = [
  "zones", "confidence", "water", "nutrients", "risk", "salinity", "resolution", "gapFill", "experimentalDetail",
];

const OVERLAY_ICONS: Record<OverlayKind, string> = {
  zones: "◻",
  confidence: "🔍",
  gapFill: "🧩",
  resolution: "📐",
  water: "💧",
  nutrients: "🧪",
  risk: "⚠️",
  salinity: "🧂",
  experimentalDetail: "🔬",
};

export default function ModeLens({
  activeMode,
  onModeChange,
  screenState,
  onBackToField
}: ModeLensProps) {
  const l10 = useLayer10();
  const modeAvailability = l10.modeAvailability;
  const overlayAvailability = l10.overlayAvailability;

  return (
    <div className="flex flex-col gap-1" id="mode-lens">
      {/* Row 1: Surface Selector (mutually exclusive base modes) */}
      <div className="flex items-center gap-1 bg-white/5 rounded-full p-1">
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
        {BASE_MODES.map(({ mode, mapMode }) => {
          const config = MODE_CONFIG[mapMode];
          const isActive = l10.baseSurfaceMode === mode;
          const availability = modeAvailability?.[mapMode];
          const suffix = availability?.suffix;
          const displayLevel = availability?.displayLevel;

          // V92.4-BC: Display-level-aware suffix color
          const suffixColor = (() => {
            if (!displayLevel) return 'text-zinc-500';
            switch (displayLevel) {
              case 'raster': return 'text-emerald-400';
              case 'asmae_diagnostic': return 'text-amber-400';
              case 'proxy': return 'text-sky-400';
              case 'plot_level': return 'text-violet-400';
              case 'visual_only': return 'text-zinc-500';
              case 'unavailable': return 'text-red-400';
              default: return 'text-zinc-500';
            }
          })();

          return (
            <button
              key={mode}
              data-testid={TESTID_MAP[mapMode]}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full transition-all text-xs font-semibold tracking-wide ${
                  isActive 
                    ? "bg-white text-[#0B1015] shadow-sm" 
                    : displayLevel === "unavailable"
                      ? "text-zinc-600 hover:text-zinc-400 hover:bg-white/5"
                      : "text-zinc-400 hover:text-white hover:bg-white/10"
              }`}
              onClick={() => l10.setBaseSurfaceMode(mode)}
              title={availability?.reason || MODE_SHORT[mapMode]}
              id={`mode-lens-${mode}`}
            >
              <span className="w-3 h-3 flex items-center justify-center opacity-80">{config.icon}</span>
              <span>
                {MODE_SHORT[mapMode]}
                {suffix && (
                  <span className={`ml-1 text-[9px] ${isActive ? suffixColor : suffixColor}`}>
                    · {suffix}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      {/* Row 2: Overlay Layer Controls — visually distinct from surface selector */}
      <div className="flex items-center gap-1.5 bg-slate-800/60 border border-slate-700/40 rounded-lg px-2.5 py-1 flex-wrap" id="overlay-toggles">
        <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400 mr-1.5 flex items-center gap-1">
          <span className="text-xs">◇</span> Layers
        </span>
        <div className="w-px h-4 bg-zinc-600/50" />
        {OVERLAY_TOGGLE_KINDS.map((kind) => {
          const toggled = l10.overlayToggles[kind];
          const avail = overlayAvailability?.[kind];
          const isAvailable = avail?.available ?? false;
          const isSpatial = avail?.isSpatial ?? false;
          const reason = avail?.reason;
          const icon = OVERLAY_ICONS[kind];
          const label = OVERLAY_LABELS[kind];

          // Build suffix for non-spatial or missing surfaces
          let statusSuffix = "";
          if (!isAvailable) {
            statusSuffix = "no data";
          } else if (!isSpatial) {
            // Surface exists but is plot-level/proxy/model only
            const gc = avail?.groundingClass || "";
            if (gc === "UNIFORM" || gc === "BROADCAST" || gc === "FIELD_PROXY") {
              statusSuffix = "plot-level";
            } else {
              statusSuffix = "proxy";
            }
          }

          // V92.4-BC.1: Only truly unavailable overlays are disabled.
          // Plot-level and proxy overlays render uniform tint or card.
          const dl = avail?.displayLevel;
          const disabled = !isAvailable || dl === "unavailable";

          return (
            <button
              key={kind}
              data-testid={`overlay-toggle-${kind}`}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg transition-all text-[11px] font-semibold tracking-wide cursor-pointer select-none ${
                disabled
                  ? "opacity-35 cursor-not-allowed text-zinc-500"
                  : toggled
                    ? "bg-indigo-500/25 text-indigo-200 border border-indigo-400/40 shadow-sm shadow-indigo-500/10"
                    : "text-zinc-400 hover:text-white hover:bg-white/8 border border-transparent"
              }`}
              onClick={() => {
                if (!disabled) l10.setOverlayToggle(kind, !toggled);
              }}
              title={disabled ? (reason || `${label} unavailable`) : `Toggle ${label} overlay`}
              id={`overlay-${kind}`}
            >
              <span className="w-3 h-3 flex items-center justify-center text-[10px]">{icon}</span>
              <span>
                {label}
                {toggled && !disabled && <span className="ml-0.5 text-emerald-400">✓</span>}
                {statusSuffix && (
                  <span className="ml-1 text-[9px] text-zinc-500 font-normal">
                    · {statusSuffix}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      {/* V92.3-C: Overlay conflict warning */}
      {l10.overlayConflictWarning && (
        <div className="text-[9px] text-amber-400/80 font-medium px-2 py-0.5 bg-amber-500/8 rounded-full self-start" id="overlay-conflict-warning">
          ⚠️ {l10.overlayConflictWarning}
        </div>
      )}

      {/* V92.3-C: Active overlay summary chips */}
      {l10.activeOverlayCount > 0 && (
        <div className="flex items-center gap-1 px-2 text-[9px] text-zinc-500 font-medium" id="overlay-summary">
          <span>Visible:</span>
          <span className="text-zinc-300">{MODE_SHORT[activeMode]}</span>
          {OVERLAY_TOGGLE_KINDS.filter(k => l10.overlayToggles[k] && overlayAvailability?.[k]?.available && overlayAvailability?.[k]?.displayLevel !== "unavailable").map(k => (
            <span key={k} className="text-zinc-300">+ {OVERLAY_LABELS[k]}</span>
          ))}
        </div>
      )}
    </div>
  );
}
