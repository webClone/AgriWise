"use client";

import { Leaf, Ruler, Droplets, Thermometer, Wind, CloudRain, Activity } from "lucide-react";

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
    vpd: number;
    soilTension: number;
    leafWetness: number;
  };
}

export default function PlotContextBand({ plotName, plotArea, cropName, cropStage, telemetry }: PlotContextBandProps) {
  
  if (!telemetry) {
     return (
        <div className="w-full h-16 bg-slate-900/50 rounded-xl animate-pulse flex items-center px-6 gap-4 border border-slate-800">
            <div className="h-6 w-32 bg-slate-800 rounded"></div>
            <div className="h-6 w-24 bg-slate-800 rounded ml-auto"></div>
        </div>
     );
  }

  // Physics Color Logic
  const isDeltaTOptimal = telemetry.deltaT >= 2 && telemetry.deltaT <= 8;
  const isVpdOptimal = telemetry.vpd >= 0.4 && telemetry.vpd <= 1.2;

  // Weather Icon Logic (Simplified)
  const WeatherIcon = telemetry.rain > 0 ? CloudRain : telemetry.windSpeed > 20 ? Wind : Thermometer;

  return (
    <div className="w-full flex flex-col md:flex-row items-center gap-4 bg-slate-900/80 backdrop-blur-md border border-slate-800/50 p-3 rounded-xl shadow-lg relative z-10">
        
        {/* SECTION 1: IDENTITY */}
        <div className="flex items-center gap-3 min-w-fit px-2">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 text-emerald-500">
                <Leaf size={20} />
            </div>
            <div>
                <h1 className="text-lg font-bold text-white leading-tight">{plotName}</h1>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                    <span className="flex items-center gap-1"><Ruler size={10}/> {plotArea} ha</span>
                    <span className="w-1 h-1 rounded-full bg-slate-600"></span>
                    <span className="text-emerald-400 font-medium">{cropName}</span>
                    {cropStage && (
                        <>
                            <span className="w-1 h-1 rounded-full bg-slate-600"></span>
                            <span>{cropStage}</span>
                        </>
                    )}
                </div>
            </div>
        </div>

        {/* COMPACT DIVIDER (Desktop) */}
        <div className="hidden md:block w-px h-8 bg-slate-800 mx-2"></div>

        {/* SECTION 2: TELEMETRY (Physics Engine) */}
        <div className="flex-1 w-full grid grid-cols-2 md:flex md:items-center gap-2 md:gap-6 justify-center md:justify-start">
            
            {/* Delta T */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950/30 border border-slate-800/50">
                <div className={`p-1 rounded bg-slate-800 ${isDeltaTOptimal ? 'text-emerald-400' : 'text-amber-400'}`}>
                    <Activity size={14} />
                </div>
                <div>
                    <div className="text-[10px] text-slate-500 uppercase font-bold leading-none mb-0.5">Delta T</div>
                    <div className={`text-sm font-mono font-bold leading-none ${isDeltaTOptimal ? 'text-slate-200' : 'text-amber-400'}`}>
                        {telemetry.deltaT.toFixed(1)}°
                    </div>
                </div>
            </div>

            {/* VPD */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950/30 border border-slate-800/50">
                 <div className={`p-1 rounded bg-slate-800 ${isVpdOptimal ? 'text-blue-400' : 'text-amber-400'}`}>
                    <Droplets size={14} />
                </div>
                <div>
                    <div className="text-[10px] text-slate-500 uppercase font-bold leading-none mb-0.5">VPD</div>
                    <div className="text-sm font-mono font-bold text-slate-200 leading-none">
                        {telemetry.vpd} <span className="text-[9px] font-normal text-slate-500">kPa</span>
                    </div>
                </div>
            </div>

            {/* Soil Tension */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950/30 border border-slate-800/50">
                 <div className="p-1 rounded bg-slate-800 text-amber-500">
                    <Activity size={14} />
                </div>
                <div>
                    <div className="text-[10px] text-slate-500 uppercase font-bold leading-none mb-0.5">Tension</div>
                    <div className="text-sm font-mono font-bold text-slate-200 leading-none">
                        {(telemetry.soilTension/1000).toFixed(1)} <span className="text-[9px] font-normal text-slate-500">MPa</span>
                    </div>
                </div>
            </div>

        </div>

        {/* SECTION 3: WEATHER CONTEXT */}
        <div className="flex items-center gap-4 min-w-fit pl-4 md:border-l border-slate-800/50">
            <div className="text-right">
                <div className="text-2xl font-bold text-white leading-none tracking-tight">{Math.round(telemetry.temp)}°</div>
                <div className="text-[10px] text-slate-400 font-medium">
                   {telemetry.rain > 0 ? `${telemetry.rain}mm Rain` : 'No Rain'}
                </div>
            </div>
            <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400 border border-blue-500/20">
                <WeatherIcon size={20} />
            </div>
        </div>

    </div>
  );
}
