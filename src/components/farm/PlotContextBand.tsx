"use client";

import { Leaf, Thermometer, Wind, CloudRain, ChevronLeft, LayoutDashboard, Database, UserCog, Brain, Headset } from "lucide-react";
import Link from "next/link";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import { useParams, usePathname } from "next/navigation";


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
  farmId?: string;
}

export default function PlotContextBand({ plotName, plotArea, cropName, cropStage, telemetry, farmId }: PlotContextBandProps) {
  const l10 = useLayer10();

  const BASE_LABELS: Record<string, string> = {
    canopy: "Canopy",
    vegetation: "Canopy",
    veg_attention: "Veg. Attention",
    water_stress: "Water",
    nutrient_risk: "Nutrients",
    salinity: "Salinity",
    composite_risk: "Risk"
  };

  const activeOverlayLabels: string[] = [];
  const overlayMap: Record<string, string> = {
    water: "Water",
    nutrients: "Nutrients",
    risk: "Risk",
    salinity: "Salinity",
    zones: "Zones",
    confidence: "Confidence",
    resolution: "Resolution",
    experimentalDetail: "Experimental",
    gapFill: "Gap-Fill"
  };

  if (l10 && l10.overlayToggles) {
    (Object.keys(l10.overlayToggles) as Array<keyof typeof l10.overlayToggles>).forEach((k) => {
      if (k !== "zones" && l10.overlayToggles[k]) {
        activeOverlayLabels.push(overlayMap[k] || k);
      }
    });
  }

  const baseLabel = BASE_LABELS[l10.baseSurfaceMode] || l10.baseSurfaceMode || "Canopy";
  let chipText = baseLabel;
  if (activeOverlayLabels.length > 0) {
    if (activeOverlayLabels.length <= 2) {
      chipText = `${baseLabel} · ${activeOverlayLabels.join(" · ")}`;
    } else {
      chipText = `${baseLabel} +${activeOverlayLabels.length} overlays`;
    }
  }

  const handleChipClick = () => {
    if (piAvailable && pi) {
      pi.setShowAnalysisSidebar(true);
      pi.setActiveSidebarTab("layers");
    }
  };
  
  // Try to use plot intelligence context (may not be available on non-plot pages)
  let piAvailable = false;
  let pi: any = null;
  let detailMode: "farmer" | "expert" = "farmer";
  let setDetailMode: ((m: "farmer" | "expert") => void) | null = null;
  let dataView: "assimilated" | "raw" = "assimilated";
  let setDataView: ((v: "assimilated" | "raw") => void) | null = null;
  // GAP F: live weather from PI pipeline
  let liveTemp: number | null = null;
  let liveRain: number | null = null;
  let liveWind: number | null = null;
  // GAP A: real agronomic stage
  let liveCropStage: string | null = null;

  try {
    pi = usePlotIntelligence();
    piAvailable = true;
    detailMode = pi.detailMode;
    setDetailMode = pi.setDetailMode;
    dataView = pi.dataView;
    setDataView = pi.setDataView;

    // GAP F: read live weather from PI pipeline (refreshes after client-side fetch)
    if (pi.currentWeather) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const w = pi.currentWeather as Record<string, any>;
      const tempObj = w.temperature;
      liveTemp = (typeof tempObj === "object" && tempObj !== null)
        ? (tempObj.current ?? null)
        : (typeof tempObj === "number" ? tempObj : null);
      liveRain = (typeof w.rain === "number" ? w.rain : null)
        ?? (typeof w.precipitation === "number" ? w.precipitation : null);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      liveWind = (w.wind as any)?.speed_ms ?? (typeof w.wind_speed === "number" ? w.wind_speed : null);
    }

    // GAP A: use real agronomic stage computed by the Python phenology model
    if (pi.cropPhenology?.stage) {
      liveCropStage = pi.cropPhenology.stage;
    }
  } catch {
    // Not inside PlotIntelligenceProvider — that's fine, use defaults
  }

  if (l10.isDecideMode) return null;

  // Navigation items
  const params = useParams();
  const pathname = usePathname();
  const navFarmId = (params?.id as string) || farmId;
  const navPlotId = params?.plotId as string;
  const baseUrl = navFarmId && navPlotId ? `/farm/${navFarmId}/plot/${navPlotId}` : "";

  const navItems = [
    { label: "Overview", icon: LayoutDashboard, href: baseUrl },
    { label: "Raw Data", icon: Database, href: `${baseUrl}/raw-data` },
    { label: "User Inputs", icon: UserCog, href: `${baseUrl}/user-inputs` },
    { label: "AgriBrain", icon: Brain, href: `${baseUrl}/analysis` },
    { label: "Live Help", icon: Headset, href: `${baseUrl}/live-assistance` },
  ];

  // Determine active nav item
  const lastSegment = pathname?.split('/').pop() || '';
  const isOverview = !['raw-data', 'user-inputs', 'analysis', 'live-assistance'].includes(lastSegment);

  // Effective values — prefer live PI data, fall back to SSR telemetry prop
  const effectiveTemp = liveTemp ?? telemetry?.temp;
  const effectiveRain = liveRain ?? telemetry?.rain ?? 0;
  const effectiveWind = liveWind ?? telemetry?.windSpeed ?? 0;
  const effectiveCropStage = liveCropStage ?? cropStage;

  const WeatherIcon = effectiveTemp !== undefined
    ? (effectiveRain > 0 ? CloudRain : effectiveWind > 20 ? Wind : Thermometer)
    : null;

  return (
    <div id="plot-context-band" className="mx-auto w-max h-[72px] mt-4 flex items-center justify-between gap-4 sm:gap-6 bg-[#080C19]/92 backdrop-blur-xl border border-white/10 px-4 rounded-full shadow-2xl relative z-50 transition-all" suppressHydrationWarning={true}>
        
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
        <div className="flex items-center gap-3 pe-2" suppressHydrationWarning={true}>
            <div className="flex items-center justify-center p-1.5 rounded-full bg-emerald-500/10 text-emerald-400" suppressHydrationWarning={true}>
                <Leaf size={16} strokeWidth={2.5} />
            </div>
            <div className="flex items-baseline gap-2" suppressHydrationWarning={true}>
                <h1 className="text-sm font-semibold tracking-wide text-zinc-100">{plotName}</h1>
                <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
                    {cropName} • {plotArea.toFixed(1)} ha
                </span>
                {/* GAP A: show real phenology stage if available, else DB status */}
                 {l10.evidenceState?.resolvedPhenology ? (
                     <span className={`text-[9px] font-medium tracking-wider px-2 py-0.5 rounded-full ${
                       l10.evidenceState.resolvedPhenology.conflict 
                         ? "text-red-400/70 bg-red-500/8 border border-red-500/20" 
                         : "text-emerald-400/70 bg-emerald-500/8"
                     }`} title={l10.evidenceState.resolvedPhenology.conflict ? l10.evidenceState.resolvedPhenology.userLabel : undefined}>
                       {l10.evidenceState.resolvedPhenology.conflict ? "⚠️ Stage Conflict" : l10.evidenceState.resolvedPhenology.userLabel}
                     </span>
                 ) : effectiveCropStage ? (
                     <span className="text-[9px] font-medium tracking-wider text-emerald-400/70 bg-emerald-500/8 px-2 py-0.5 rounded-full">
                       {effectiveCropStage}
                     </span>
                 ) : null}
            </div>
        </div>

        {/* COMPACT DIVIDER */}
        <div className="w-px h-6 bg-white/10 hidden sm:block" suppressHydrationWarning={true} />

        {/* SECTION 2: CURRENT LAYER CHIP */}
        {l10 && l10.data ? (
            <div className="flex items-center gap-3" suppressHydrationWarning={true}>
                <button
                    onClick={handleChipClick}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/20 text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer"
                >
                    ⚙️ {chipText}
                </button>

                {/* VISIBLE ZONE STATE CHIP */}
                <div className="hidden md:flex items-center" suppressHydrationWarning={true}>
                    {(() => {
                        // Canopy mode: pure observational — no zone-state chip
                        if (l10.activeMode === "canopy" || l10.activeMode === "vegetation") {
                            const hasMgmtZones = l10.data?.zones?.some(z => z.zone_id?.startsWith("MZ_")) || false;
                            return (
                                <div className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border text-teal-400 bg-teal-500/10 border-teal-500/20">
                                    {hasMgmtZones ? "Scouting regions" : "Canopy view"}
                                </div>
                            );
                        }

                        const mapSemantics = l10.evidenceState?.mapSemantics;
                        const visibleZoneCount = l10.evidenceState?.visibleZoneCount ?? 0;
                        
                        let stateLabel = "No zones";
                        let stateColor = "text-zinc-400 bg-white/5 border-transparent";
                        
                        if (mapSemantics === "plot_level_proxy") {
                            stateLabel = "Plot-level estimate";
                            stateColor = "text-zinc-500 bg-zinc-500/5 border-zinc-500/20 border-dashed";
                        } else if (mapSemantics === "field_wide_surface") {
                            stateLabel = "Field-wide condition";
                            stateColor = "text-amber-400 bg-amber-500/10 border-amber-500/20";
                        } else if (mapSemantics === "localized_alert") {
                            stateLabel = `${visibleZoneCount} localized zone${visibleZoneCount > 1 ? 's' : ''}`;
                            stateColor = "text-indigo-400 bg-indigo-500/10 border-indigo-500/20";
                        } else if (mapSemantics === "management_zone") {
                            stateLabel = "Scouting regions";
                            stateColor = "text-teal-400 bg-teal-500/10 border-teal-500/20";
                        } else if (mapSemantics === "no_spatial_data") {
                            stateLabel = "No spatial data";
                            stateColor = "text-zinc-500 bg-zinc-500/5 border-zinc-500/20 border-dashed";
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
             <div className="w-[200px] h-8 hidden sm:block" suppressHydrationWarning={true} />
        )}

        {/* SECTION 3: PAGE NAVIGATION */}
        {baseUrl && (
            <>
                <div className="w-px h-6 bg-white/10 hidden sm:block" suppressHydrationWarning={true} />
                <div className="hidden sm:flex items-center gap-0.5 bg-white/5 rounded-full p-0.5" suppressHydrationWarning={true}>
                    {navItems.map((item) => {
                        const isActive = item.href === baseUrl ? isOverview : pathname?.endsWith(item.href.split('/').pop() || '') || false;
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider transition-all ${
                                    isActive
                                        ? "bg-indigo-500/15 text-indigo-400 border border-indigo-500/20"
                                        : "text-zinc-500 hover:text-zinc-300 border border-transparent"
                                }`}
                            >
                                <item.icon size={12} />
                                {item.label}
                            </Link>
                        );
                    })}
                </div>
            </>
        )}

        {/* SECTION 4: WEATHER — live from PI pipeline, falls back to SSR telemetry */}
        {effectiveTemp !== undefined && WeatherIcon && (
            <>
                <div className="w-px h-6 bg-white/10 hidden sm:block" suppressHydrationWarning={true} />
                <div className="flex items-center gap-2 ps-2" suppressHydrationWarning={true}>
                    <div className="flex flex-col items-center leading-tight" suppressHydrationWarning={true}>
                      <span className="text-sm font-bold text-white">{Math.round(effectiveTemp)}°</span>
                      {/* show "live" when PI has refreshed, "now" for SSR snapshot */}
                      <span className="text-[8px] font-medium text-zinc-500 uppercase tracking-wide">
                        {liveTemp !== null ? "live" : "now"}
                      </span>
                    </div>
                    <div className={`flex items-center justify-center p-1.5 rounded-full ${effectiveRain > 0 ? "text-blue-400 bg-blue-500/10" : "text-zinc-400 bg-zinc-500/10"}`} suppressHydrationWarning={true}>
                        <WeatherIcon size={14} />
                    </div>
                </div>
            </>
        )}
    </div>
  );
}
