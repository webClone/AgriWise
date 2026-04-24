"use client";

import { Leaf, Thermometer, Wind, CloudRain, ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useLayer10 } from "@/hooks/useLayer10";
import ModeLens from "@/components/farm/intelligence/ModeLens";


interface PlotContextBandProps {
  plotName: string;
  plotArea: number;
  cropName: string;
  cropStage?: string;
  telemetry?: {
    temp: number;
    humidity: number;
    rain: number;
    windSpeed: number;
    deltaT: number;
  };
  farmId?: string; // Passed from layout if available
}

export default function PlotContextBand({ plotName, plotArea, cropName, cropStage, telemetry, farmId }: PlotContextBandProps) {
  const l10 = useLayer10();

  if (l10.isDecideMode) return null;

  const WeatherIcon = telemetry
    ? (telemetry.rain > 0 ? CloudRain : telemetry.windSpeed > 20 ? Wind : Thermometer)
    : null;

  return (
    <div className="mx-auto w-max h-[72px] mt-4 flex items-center justify-between gap-4 sm:gap-6 bg-[#0B1015]/75 backdrop-blur-xl border border-white/10 px-4 rounded-full shadow-2xl relative z-50 transition-all">
        
        {/* SECTION 0: BACK */}
        {farmId && (
            <Link 
                href={`/farm/${farmId}`}
                className="flex items-center justify-center w-10 h-10 rounded-full hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
                title="Back to Farm"
            >
                <ChevronLeft size={20} />
            </Link>
        )}

        {/* SECTION 1: IDENTITY — always present */}
        <div className="flex items-center gap-3 pr-2">
            <div className="flex items-center justify-center p-1.5 rounded-full bg-emerald-500/10 text-emerald-400">
                <Leaf size={16} strokeWidth={2.5} />
            </div>
            <div className="flex items-baseline gap-2">
                <h1 className="text-sm font-semibold tracking-wide text-zinc-100">{plotName}</h1>
                <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
                    {cropName} • {plotArea.toFixed(1)} ha
                </span>
                {cropStage && (
                    <span className="text-[9px] font-medium tracking-wider text-emerald-400/70 bg-emerald-500/8 px-2 py-0.5 rounded-full">{cropStage}</span>
                )}
            </div>
        </div>

        {/* COMPACT DIVIDER */}
        <div className="w-px h-6 bg-white/10 hidden sm:block" />

        {/* SECTION 2: MODE LENS & ZONE STATE */}
        {l10 && l10.data ? (
            <div className="flex items-center gap-3">
                <ModeLens 
                    activeMode={l10.activeMode}
                    onModeChange={l10.setActiveMode}
                    screenState={l10.selectedZone ? "diagnose" : "observe"}
                    onBackToField={() => l10.setSelectedZone(null)}
                />

                {/* VISIBLE ZONE STATE CHIP */}
                <div className="hidden md:flex items-center">
                    {(() => {
                        // Canopy mode: pure observational \u2014 no zone-state chip
                        if (l10.activeMode === "canopy" || l10.activeMode === "vegetation") {
                            return (
                                <div className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border text-teal-400 bg-teal-500/10 border-teal-500/20">
                                    Canopy view
                                </div>
                            );
                        }

                        const surfaceState = l10.data?.quality?.zone_state_by_surface?.[l10.activeZoneSurfaceType] || "none";
                        const allZones = l10.data?.zones || [];
                        
                        let stateLabel = "No zones";
                        let stateColor = "text-zinc-400 bg-white/5";
                        
                        if (surfaceState === "field_wide") {
                            stateLabel = "1 field-wide condition";
                            stateColor = "text-amber-400 bg-amber-500/10 border-amber-500/20";
                        } else if (surfaceState === "localized") {
                            const surfaceZones = allZones.filter(z => z.source_surface_type === l10.activeZoneSurfaceType);
                            const count = surfaceZones.length || allZones.length;
                            stateLabel = `${count} localized zone${count > 1 ? 's' : ''}`;
                            stateColor = "text-indigo-400 bg-indigo-500/10 border-indigo-500/20";
                        } else if (surfaceState === "low_confidence") {
                            stateLabel = "Low spatial confidence";
                            stateColor = "text-rose-400 bg-rose-500/10 border-rose-500/20";
                        } else if (surfaceState === "no_data") {
                            stateLabel = "No spatial data";
                            stateColor = "text-zinc-500 bg-zinc-500/5 border-zinc-500/20 border-dashed";
                        } else {
                            stateLabel = "No localized zones";
                            stateColor = "text-zinc-400 bg-white/5 border-transparent";
                        }

                        return (
                            <div className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${stateColor}`}>
                                {stateLabel}
                            </div>
                        );
                    })()}
                </div>
            </div>
        ) : (
             <div className="w-[200px] h-8 hidden sm:block" />
        )}

        {/* SECTION 3: WEATHER — graceful degradation */}
        {telemetry && WeatherIcon && (
            <>
                <div className="w-px h-6 bg-white/10 hidden sm:block" />
                <div className="flex items-center gap-2 pl-2">
                    <span className="text-sm font-medium text-white">{Math.round(telemetry.temp)}°</span>
                    <div className={`flex items-center justify-center p-1.5 rounded-full ${telemetry.rain > 0 ? "text-blue-400 bg-blue-500/10" : "text-zinc-400 bg-zinc-500/10"}`}>
                        <WeatherIcon size={14} />
                    </div>
                </div>
            </>
        )}
    </div>
  );
}
