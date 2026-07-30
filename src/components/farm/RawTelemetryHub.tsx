"use client";

import React, { useState, useEffect } from "react";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";

interface RawTelemetryHubProps {
  plotId: string;
  farmId: string;
}

export default function RawTelemetryHub({ plotId, farmId }: RawTelemetryHubProps) {
  const pi = usePlotIntelligence();
  const data = pi?.data;
  
  useEffect(() => {
    if (pi && !data && !pi.loading) {
      pi.fetchIntelligence(plotId, farmId);
    }
  }, [pi, data, plotId, farmId]);

  const [activeTab, setActiveTab] = useState<"weather" | "soil" | "eo" | "water" | "phenology" | "sensors">("weather");

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 bg-[#0B1015]/60 backdrop-blur-xl rounded-2xl border border-white/5">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-sm text-slate-500 font-mono tracking-widest uppercase">Syncing Raw Telemetry...</p>
      </div>
    );
  }

  // ── STRICT RAW DATA ONLY ─────────────────────────────────────────────
  // Backend rawData keys (from main.py lines 1354-1363):
  //   weather_raw, forecast_raw, sentinel2_raw, sentinel1_raw,
  //   sar_timeseries, soilgrids_raw, water_balance_raw, historical_weather
  const raw = (data.rawData || {}) as Record<string, any>;
  const weatherRaw   = raw.weather_raw || {};
  const forecastRaw  = raw.forecast_raw || {};
  const s2Raw        = raw.sentinel2_raw || {};
  const s1Raw        = raw.sentinel1_raw || {};
  const sarTs        = raw.sar_timeseries || {};
  const soilRaw      = raw.soilgrids_raw || {};
  const waterRaw     = raw.water_balance_raw || {};
  const histWeather  = raw.historical_weather || {};
  const cropPheno    = data.cropPhenology;

  // Sources active badge
  const sourcesActive = [
    Object.keys(weatherRaw).length > 0 && "OpenMeteo",
    Object.keys(s2Raw).length > 0 && "Sentinel-2",
    Object.keys(s1Raw).length > 0 && "Sentinel-1",
    Object.keys(soilRaw).length > 0 && "SoilGrids",
    Object.keys(waterRaw).length > 0 && "Water-Balance",
    Object.keys(forecastRaw).length > 0 && "Forecast",
    (data.sensorContext?.count ?? 0) > 0 && "Field Sensors",
  ].filter(Boolean) as string[];

  const renderValue = (val: any, unit: string = "") => {
    if (val === null || val === undefined || val === "" || val === "--") return <span className="text-slate-600 italic">—</span>;
    if (typeof val === "number") return <span className="text-white font-semibold">{Number.isInteger(val) ? val : val.toFixed(2)}{unit}</span>;
    return <span className="text-white font-semibold">{String(val)}{unit}</span>;
  };

  const tabs = [
    { id: "weather",  label: "Meteorological",           icon: "🌤️", count: Object.keys(weatherRaw).length },
    { id: "soil",     label: "Soil (ISRIC/SoilGrids)",   icon: "🌱", count: Object.keys(soilRaw).length },
    { id: "eo",       label: "Earth Observation",        icon: "🛰️", count: Object.keys(s2Raw).length + Object.keys(s1Raw).length },
    { id: "water",    label: "Water Balance",            icon: "💧", count: Object.keys(waterRaw).length },
    { id: "phenology",label: "Phenology & GDD",          icon: "🌾", count: cropPheno ? 1 : 0 },
    { id: "sensors",  label: "Field Sensors (IoT)",      icon: "📡", count: data.sensorContext?.count || 0 },
  ];

  // Water balance records
  const wbRecords = waterRaw.records || [];
  const wbSummary = waterRaw.summary || {};

  // Forecast days
  const forecastDays = forecastRaw.forecast || [];

  // SAR timeseries entries
  const sarEntries = sarTs.timeseries || [];

  return (
    <div className="bg-[#0B1015]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden flex flex-col" style={{ minHeight: 600 }}>
      
      {/* Header */}
      <div className="p-6 border-b border-white/5 flex items-center justify-between shrink-0 bg-slate-900/40">
        <div>
          <h2 className="text-xl font-light text-white tracking-wide flex items-center gap-3">
            📡 Deep Telemetry Hub
          </h2>
          <p className="text-xs text-slate-500 mt-1 uppercase tracking-widest">
            Unprocessed Data Streams &middot; Direct Source Access &middot; {sourcesActive.length} Sources Active
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {sourcesActive.map(s => (
            <span key={s} className="text-[9px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full font-mono uppercase tracking-widest border border-emerald-500/20">
              {s}
            </span>
          ))}
          {sourcesActive.length === 0 && (
            <span className="text-[9px] bg-rose-500/10 text-rose-400 px-2 py-0.5 rounded-full font-mono uppercase tracking-widest border border-rose-500/20">
              No Raw Data
            </span>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Sidebar Nav */}
        <div className="w-56 border-r border-white/5 bg-black/20 flex flex-col p-3 gap-1.5 shrink-0 overflow-y-auto">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-3 px-3 py-3 rounded-xl transition-all text-left ${activeTab === tab.id ? 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-300' : 'hover:bg-white/5 border border-transparent text-slate-400'}`}
            >
              <span className="text-base">{tab.icon}</span>
              <div className="flex flex-col">
                <span className="text-xs font-medium tracking-wide">{tab.label}</span>
                <span className="text-[9px] text-slate-600">{tab.count > 0 ? `${tab.count} fields` : 'No data'}</span>
              </div>
            </button>
          ))}
        </div>

        {/* Data View */}
        <div className="flex-1 p-6 overflow-y-auto custom-scrollbar bg-slate-900/20">
          
          {/* ─── METEOROLOGICAL ─── */}
          {activeTab === "weather" && (
            <div className="space-y-6 animate-fade-in">
              <SectionHeader title="Surface Weather (Live)" badge="OpenMeteo API" />
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <DataCard label="Temperature" value={renderValue(weatherRaw.temperature?.current, "°C")} source="OpenMeteo" />
                <DataCard label="Feels Like" value={renderValue(weatherRaw.temperature?.feels_like, "°C")} source="OpenMeteo" />
                <DataCard label="Temp Min" value={renderValue(weatherRaw.temperature?.min, "°C")} source="OpenMeteo" />
                <DataCard label="Temp Max" value={renderValue(weatherRaw.temperature?.max, "°C")} source="OpenMeteo" />
                <DataCard label="Humidity" value={renderValue(weatherRaw.humidity, "%")} source="OpenMeteo" />
                <DataCard label="Pressure" value={renderValue(weatherRaw.pressure, " hPa")} source="OpenMeteo" />
                <DataCard label="Wind Speed" value={renderValue(weatherRaw.wind?.speed_ms, " m/s")} source="OpenMeteo" />
                <DataCard label="Wind Direction" value={renderValue(weatherRaw.wind?.direction_deg, "°")} source="OpenMeteo" />
                <DataCard label="Wind Gust" value={renderValue(weatherRaw.wind?.gust_ms, " m/s")} source="OpenMeteo" />
                <DataCard label="Clouds" value={renderValue(weatherRaw.clouds_percent, "%")} source="OpenMeteo" />
                <DataCard label="UV Index" value={renderValue(weatherRaw.uv_index)} source="OpenMeteo" />
                <DataCard label="Visibility" value={renderValue(weatherRaw.visibility_m, " m")} source="OpenMeteo" />
                <DataCard label="Condition" value={renderValue(weatherRaw.weather?.condition)} source="OpenMeteo" />
                <DataCard label="Description" value={renderValue(weatherRaw.weather?.description)} source="OpenMeteo" />
              </div>

              {forecastDays.length > 0 && (
                <>
                  <SectionHeader title={`Forecast (${forecastDays.length} days)`} badge="NWP Model" />
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr className="text-slate-500 border-b border-white/5">
                          <th className="text-left py-2 px-3">Date</th>
                          <th className="text-right py-2 px-3">Min</th>
                          <th className="text-right py-2 px-3">Max</th>
                          <th className="text-right py-2 px-3">Rain%</th>
                          <th className="text-right py-2 px-3">Humidity</th>
                          <th className="text-left py-2 px-3">Condition</th>
                        </tr>
                      </thead>
                      <tbody>
                        {forecastDays.slice(0, 7).map((d: any, i: number) => (
                          <tr key={i} className="border-b border-white/5 text-slate-300 hover:bg-white/5">
                            <td className="py-2 px-3 text-slate-400">{d.date}</td>
                            <td className="text-right py-2 px-3">{d.temp_min != null ? `${d.temp_min}°` : '—'}</td>
                            <td className="text-right py-2 px-3">{d.temp_max != null ? `${d.temp_max}°` : '—'}</td>
                            <td className="text-right py-2 px-3 text-blue-400">{d.pop != null ? `${Math.round(d.pop * 100)}%` : '—'}</td>
                            <td className="text-right py-2 px-3">{d.humidity != null ? `${d.humidity}%` : '—'}</td>
                            <td className="py-2 px-3">{d.weather || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ─── SOIL ─── */}
          {activeTab === "soil" && (
            <div className="space-y-6 animate-fade-in">
              <SectionHeader title="Soil Properties" badge="ISRIC SoilGrids v2.0" />
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <DataCard label="pH (H₂O)" value={renderValue(soilRaw.ph)} source="ISRIC SoilGrids" />
                <DataCard label="Texture Class" value={renderValue(soilRaw.texture_class)} source="ISRIC SoilGrids" />
                <DataCard label="Clay" value={renderValue(soilRaw.clay, "%")} source="ISRIC SoilGrids" />
                <DataCard label="Sand" value={renderValue(soilRaw.sand, "%")} source="ISRIC SoilGrids" />
                <DataCard label="Silt" value={renderValue(soilRaw.silt, "%")} source="ISRIC SoilGrids" />
                <DataCard label="Organic Carbon" value={renderValue(soilRaw.organic_carbon, " g/kg")} source="ISRIC SoilGrids" />
                <DataCard label="Total Nitrogen" value={renderValue(soilRaw.nitrogen, " g/kg")} source="ISRIC SoilGrids" />
                <DataCard label="CEC" value={renderValue(soilRaw.cec, " meq/100g")} source="ISRIC SoilGrids" />
                <DataCard label="Bulk Density" value={renderValue(soilRaw.bdod, " g/cm³")} source="ISRIC SoilGrids" />
              </div>
              {soilRaw.is_generic_fallback && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-xs text-amber-400">
                  ⚠️ Generic baseline — no satellite soil coverage for this region. Values are global model estimates.
                </div>
              )}
            </div>
          )}

          {/* ─── EARTH OBSERVATION ─── */}
          {activeTab === "eo" && (
            <div className="space-y-6 animate-fade-in">
              <SectionHeader title="Optical Indices (Sentinel-2 L2A)" badge="Copernicus" />
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <DataCard label="NDVI" value={renderValue(s2Raw.ndvi)} source="Sentinel-2 L2A" />
                <DataCard label="EVI" value={renderValue(s2Raw.evi)} source="Sentinel-2 L2A" />
                <DataCard label="NDMI" value={renderValue(s2Raw.ndmi)} source="Sentinel-2 L2A (SWIR)" />
                <DataCard label="NDWI" value={renderValue(s2Raw.ndwi)} source="Sentinel-2 L2A" />
                <DataCard label="SAVI" value={renderValue(s2Raw.savi)} source="Sentinel-2 L2A" />
                <DataCard label="Cloud Mask" value={renderValue(s2Raw.cloud_mask != null ? `${s2Raw.cloud_mask}%` : null)} source="SCL Band" />
              </div>

              <SectionHeader title="SAR Radar (Sentinel-1 GRD)" badge="Copernicus" />
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <DataCard label="VH Backscatter" value={renderValue(s1Raw.vh, " dB")} source="Sentinel-1 GRD" />
                <DataCard label="VV Backscatter" value={renderValue(s1Raw.vv, " dB")} source="Sentinel-1 GRD" />
                <DataCard label="VH/VV Ratio" value={renderValue(s1Raw.vh && s1Raw.vv ? (s1Raw.vh / s1Raw.vv).toFixed(3) : null)} source="Derived" />
                <DataCard label="Soil Moisture Proxy" value={renderValue(s1Raw.soil_moisture)} source="SAR Inversion" />
              </div>

              {sarEntries.length > 0 && (
                <>
                  <SectionHeader title={`SAR Time Series (${sarEntries.length} obs)`} badge="Temporal" />
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr className="text-slate-500 border-b border-white/5">
                          <th className="text-left py-2 px-3">Date</th>
                          <th className="text-right py-2 px-3">VV (dB)</th>
                          <th className="text-right py-2 px-3">VH (dB)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sarEntries.slice(-10).map((e: any, i: number) => (
                          <tr key={i} className="border-b border-white/5 text-slate-300 hover:bg-white/5">
                            <td className="py-2 px-3 text-slate-400">{e.date || '—'}</td>
                            <td className="text-right py-2 px-3">{e.vv_db != null ? e.vv_db.toFixed(2) : '—'}</td>
                            <td className="text-right py-2 px-3">{e.vh_db != null ? e.vh_db.toFixed(2) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ─── WATER BALANCE ─── */}
          {activeTab === "water" && (
            <div className="space-y-6 animate-fade-in">
              <SectionHeader title="Water Balance Summary" badge="PM / Hargreaves" />
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <DataCard label="Final Deficit" value={renderValue(wbSummary.final_deficit_mm, " mm")} source="Daily Mass Balance" />
                <DataCard label="Stress Index (Ks)" value={renderValue(wbSummary.stress_index)} source="Depletion Fraction" />
                <DataCard label="Total ET" value={renderValue(wbSummary.total_et_mm, " mm")} source="Cumulative" />
                <DataCard label="Total Rainfall" value={renderValue(wbSummary.total_rain_mm, " mm")} source="Observed" />
                <DataCard label="Total Irrigation" value={renderValue(wbSummary.total_irrigation_mm, " mm")} source="Logged" />
              </div>

              {wbRecords.length > 0 && (
                <>
                  <SectionHeader title={`Daily Records (${wbRecords.length})`} badge="Time Series" />
                  <div className="overflow-x-auto max-h-[300px]">
                    <table className="w-full text-xs font-mono">
                      <thead className="sticky top-0 bg-[#0B1015]">
                        <tr className="text-slate-500 border-b border-white/5">
                          <th className="text-left py-2 px-3">Date</th>
                          <th className="text-left py-2 px-3">Type</th>
                          <th className="text-right py-2 px-3">ET₀ (mm)</th>
                          <th className="text-right py-2 px-3">Rain (mm)</th>
                          <th className="text-right py-2 px-3">Balance (mm)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {wbRecords.map((r: any, i: number) => (
                          <tr key={i} className="border-b border-white/5 text-slate-300 hover:bg-white/5">
                            <td className="py-2 px-3 text-slate-400">{r.date || '—'}</td>
                            <td className="py-2 px-3">
                              <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase ${r.type === 'forecast' ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-700/50 text-slate-400'}`}>
                                {r.type || '—'}
                              </span>
                            </td>
                            <td className="text-right py-2 px-3">{r.et0 != null ? r.et0.toFixed(1) : '—'}</td>
                            <td className="text-right py-2 px-3 text-blue-400">{r.rain != null ? r.rain.toFixed(1) : '—'}</td>
                            <td className="text-right py-2 px-3">{r.balance != null ? r.balance.toFixed(1) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ─── PHENOLOGY ─── */}
          {activeTab === "phenology" && (
            <div className="space-y-6 animate-fade-in">
              <SectionHeader title="Crop Growth Stage" badge="Phenology Engine" />
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <DataCard label="Stage" value={renderValue(cropPheno?.stage)} source="Calendar / NDVI" />
                <DataCard label="Days After Planting" value={renderValue(cropPheno?.dap, " days")} source="Plant Date" />
                <DataCard label="Plant Date" value={renderValue(cropPheno?.plant_date)} source="User Input" />
                <DataCard label="Stage Basis" value={renderValue(cropPheno?.basis)} source="Determination Method" />
              </div>
              {!cropPheno && (
                <div className="bg-slate-800/40 border border-white/5 rounded-xl p-4 text-xs text-slate-500">
                  No phenology data available. Set a plant date in Crop Cycle settings to enable DAP-based growth stage tracking.
                </div>
              )}
            </div>
          )}

          {/* ─── FIELD SENSORS ─── */}
          {activeTab === "sensors" && (
            <div className="space-y-6 animate-fade-in">
              <SectionHeader title="IoT Ground Truth" badge="Field Sensors" />
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <DataCard label="Registered Sensors" value={renderValue(data.sensorContext?.count)} source="IoT Platform" />
                <DataCard label="Active Status" value={renderValue(data.sensorContext?.active)} source="Connectivity" />
                <DataCard label="Soil Moisture" value={renderValue(data.sensorContext?.soil_moisture_pct, "%")} source="IoT Field Reading" />
                <DataCard label="Soil EC" value={renderValue(data.sensorContext?.soil_ec_ds_m, " dS/m")} source="IoT Field Reading" />
                <DataCard label="Canopy Temp" value={renderValue(data.sensorContext?.field_temperature_c, "°C")} source="IoT Field Reading" />
                <DataCard label="Local Humidity" value={renderValue(data.sensorContext?.field_humidity_pct, "%")} source="IoT Field Reading" />
              </div>
              {(!data.sensorContext || data.sensorContext.count === 0) && (
                <div className="bg-slate-800/40 border border-white/5 rounded-xl p-4 text-xs text-slate-500">
                  No physical or virtual IoT sensors are currently linked to this plot. Register a device to enable local data fusion.
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────────────────── */

function SectionHeader({ title, badge }: { title: string; badge: string }) {
  return (
    <div className="flex items-center justify-between border-b border-white/5 pb-2">
      <h3 className="text-base font-light text-slate-200">{title}</h3>
      <span className="text-[9px] bg-slate-800/80 text-slate-400 px-2 py-0.5 rounded font-mono uppercase tracking-widest border border-white/5">
        {badge}
      </span>
    </div>
  );
}

function DataCard({ label, value, subValue, source }: { label: string; value: React.ReactNode; subValue?: React.ReactNode; source: string }) {
  return (
    <div className="bg-black/20 border border-white/5 rounded-xl p-4 flex flex-col justify-between min-h-[100px]">
      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-2">{label}</span>
      <div className="flex items-end gap-2 my-1">
        <div className="text-xl font-mono tracking-tight">{value}</div>
        {subValue && <div className="text-base font-mono text-slate-500 mb-0.5">/ {subValue}</div>}
      </div>
      <div className="text-[9px] text-indigo-400/60 uppercase tracking-widest border-t border-white/5 pt-2 mt-auto">
        src: {source}
      </div>
    </div>
  );
}
