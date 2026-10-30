"use client";
import Image from "next/image";
import Link from "next/link";
import { ChevronLeft, Layers3, Thermometer, CloudRain, Wind } from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import "./plot-context-akaloris.css";

interface PlotContextBandProps {
  plotName: string;
  plotArea: number;
  cropName: string;
  telemetry?: { temp: number; humidity: number; rain: number; windSpeed: number; deltaT: number };
  farmId?: string;
}
const NAV = [
  { text: "Overview", suffix: "" },
  { text: "Raw Data", suffix: "raw-data" },
  { text: "User Inputs", suffix: "user-inputs" },
  { text: "AgriBrain", suffix: "analysis" },
  { text: "Live Help", suffix: "live-assistance" },
];
const BASE: Record<string,string> = {
 canopy: "Canopy", vegetation:"Canopy", veg_attention:"Vegetation attention",
 water_stress:"Water stress", nutrient_risk:"Nutrients", salinity:"Salinity", composite_risk:"Combined risk",
};
const OVERLAYS: Record<string,string> = {
 water:"Water", nutrients:"Nutrients", risk:"Risk", salinity:"Salinity",
 confidence:"Confidence", resolution:"Resolution", experimentalDetail:"Experimental", gapFill:"Gap fill",
};
export default function PlotContextBand({ plotName, plotArea, cropName, telemetry, farmId }:PlotContextBandProps){
 const l10=useLayer10();
 const pi=usePlotIntelligence();
 const params=useParams();
 const pathname=usePathname();
 const id=(params?.id as string)||farmId||"";
 const plotId=(params?.plotId as string)||"";
 const baseUrl=id&&plotId?`/farm/${id}/plot/${plotId}`:"";
 const extras=Object.entries(l10.overlayToggles||{}).filter(([key,value])=>key!=="zones"&&value).map(([key])=>OVERLAYS[key]||key);
 const base=BASE[l10.baseSurfaceMode]||l10.baseSurfaceMode||"Canopy";
 const activeLabel=extras.length===0?base:extras.length<=2?`${base} · ${extras.join(" · ")}`:`${base} +${extras.length} overlays`;
 const rawWeather=pi.currentWeather as Record<string, unknown>|null|undefined;
 const temperature=rawWeather?.temperature;
 const temp=typeof temperature==="number"?temperature:temperature&&typeof temperature==="object"&&typeof (temperature as Record<string,unknown>).current==="number"?(temperature as Record<string,number>).current:telemetry?.temp;
 const rain=typeof rawWeather?.rain==="number"?rawWeather.rain:typeof rawWeather?.precipitation==="number"?rawWeather.precipitation:telemetry?.rain;
 const windObject=rawWeather?.wind;
 const wind=windObject&&typeof windObject==="object"&&typeof (windObject as Record<string,unknown>).speed_ms==="number"?(windObject as Record<string,number>).speed_ms:typeof rawWeather?.wind_speed==="number"?rawWeather.wind_speed:telemetry?.windSpeed;
 const WeatherIcon=typeof rain==="number"&&rain>0?CloudRain:typeof wind==="number"&&wind>20?Wind:Thermometer;
 const phenology=l10.evidenceState?.resolvedPhenology;
 // No top strip in fullscreen decision mode; preserve existing workspace behavior.
 if(l10.isDecideMode)return null;
 return <div id="plot-context-band" className="akaloris-plot-context">
   <div className="akaloris-plot-context-main">
    {id&&<Link className="akaloris-plot-back" href={`/farm/${id}`} aria-label="Back to farm" title="Back to farm"><ChevronLeft size={18}/></Link>}
    <Image className="akaloris-plot-mark" src="/brand/akaloris/akaloris_A_monogram_exploration.png" alt="Akaloris" width={34} height={27}/>
    <div className="akaloris-plot-identity"><strong title={plotName}>{plotName}</strong><span>{cropName} <span aria-hidden="true">·</span> {Number.isFinite(plotArea)?plotArea.toFixed(1)+" ha":"Area unavailable"}</span></div>
    {phenology&&<span className="akaloris-plot-chip" title={phenology.userLabel}>{phenology.stage?phenology.userLabel:"Stage unknown"}</span>}
    {l10.data&&<button className="akaloris-plot-layer" type="button" onClick={()=>{pi.setShowAnalysisSidebar(true);pi.setActiveSidebarTab("layers");}}><Layers3 size={14}/>{activeLabel}</button>}
    {typeof temp==="number"&&Number.isFinite(temp)&&<div className="akaloris-plot-weather" title={rawWeather?"Weather from current intelligence context":"Latest available weather context"}><WeatherIcon size={16}/><strong>{Math.round(temp)}°</strong><span>{rawWeather?"Weather context":"Weather snapshot"}</span></div>}
   </div>
   {baseUrl&&<nav className="akaloris-plot-navigation" aria-label="Plot workspace navigation">{NAV.map(({text,suffix})=>{const href=suffix?`${baseUrl}/${suffix}`:baseUrl;const active=suffix?pathname===href:pathname===baseUrl||pathname===baseUrl+"/";return <Link key={text} href={href} aria-current={active?"page":undefined} className={active?"active":""}>{text}</Link>;})}</nav>}
 </div>;
}
