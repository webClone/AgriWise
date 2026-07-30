"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Thermometer,
  Droplets,
  Sprout,
  Play,
  CheckCircle2,
  Info,
  Brain,
  Compass,
  ArrowRight,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface WhatIfSandboxUIProps {
  plotId: string;
  context: any;
}

export default function WhatIfSandboxUI({ plotId, context }: WhatIfSandboxUIProps) {
  // 1. Simulation Inputs State
  const [tempOffset, setTempOffset] = useState<number>(0);
  const [rainVolume, setRainVolume] = useState<number>(0);
  const [nitrogenApplied, setNitrogenApplied] = useState<number>(0);
  const [irrigationMode, setIrrigationMode] = useState<string>("default");

  // 2. Simulation Results State
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [activeChartTab, setActiveChartTab] = useState<"moisture" | "nitrogen" | "risk">("moisture");
  const [error, setError] = useState<string | null>(null);

  // 3. Execute Simulation Bridge API
  const handleRunSimulation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/agribrain/sandbox", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plotId,
          tempOffset,
          rainVolume,
          irrigationMode,
          nitrogenApplied,
        }),
      });
      const data = await res.json();
      if (data.success && data.data) {
        setResults(data.data);
      } else {
        setError(data.error || "Failed to execute sandbox simulation.");
      }
    } catch (err: any) {
      setError(err.message || "Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Convert Day 1-7 results into Recharts-friendly arrays
  const getChartData = () => {
    if (!results) return [];
    const sm = results.projections.soil_moisture;
    const nd = results.projections.nitrogen_deficit;
    const fr = results.projections.fungal_risk;

    return Array.from({ length: 7 }, (_, i) => ({
      name: `Day ${i + 1}`,
      "Soil Moisture (Base)": sm.baseline[i],
      "Soil Moisture (Sim)": sm.simulated[i],
      "Nitrogen Deficit (Base)": nd.baseline[i],
      "Nitrogen Deficit (Sim)": nd.simulated[i],
      "Fungal Risk (Base)": fr.baseline[i],
      "Fungal Risk (Sim)": fr.simulated[i],
    }));
  };

  const chartData = getChartData();

  // Dynamic slider color interpolation
  const getTempColor = () => {
    if (tempOffset > 0) return `rgb(${200 + tempOffset * 5}, ${120 - tempOffset * 10}, 100)`;
    if (tempOffset < 0) return `rgb(100, ${180 + tempOffset * 5}, ${220 - tempOffset * 2})`;
    return "rgb(156, 163, 175)";
  };

  const getRainColor = () => {
    return `rgb(${50 + rainVolume * 1.5}, ${130 + rainVolume * 0.8}, ${220 + rainVolume * 0.35})`;
  };

  const getNitrogenColor = () => {
    return `rgb(${16 + nitrogenApplied * 0.8}, ${185 + nitrogenApplied * 0.25}, ${129 - nitrogenApplied * 0.2})`;
  };

  return (
    <div className="flex flex-col lg:flex-row gap-8 w-full min-h-full pb-20 selection:bg-indigo-500/30 text-slate-100">
      
      {/* ── LEFT PANEL: SIMULATOR CONTROLS ── */}
      <div className="w-full lg:w-[42%] flex flex-col gap-6 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl shadow-2xl shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Compass className="w-5 h-5" />
          </div>
          <div>
            <h3 className="m-0 text-base font-semibold tracking-wide text-white">Simulation Setup</h3>
            <p className="text-xs text-slate-400 mt-0.5">Customize environmental offsets & operational inputs</p>
          </div>
        </div>

        <hr className="border-white/5 my-1" />

        {/* 1. Temp Offset Slider */}
        <div className="flex flex-col gap-2.5">
          <div className="flex justify-between items-center text-sm">
            <span className="flex items-center gap-2 font-medium text-slate-300">
              <Thermometer className="w-4 h-4 text-orange-400" /> Temperature Offset
            </span>
            <span className="font-mono font-bold text-[13px] px-2.5 py-0.5 rounded bg-slate-800 border border-white/5 transition-all" style={{ color: getTempColor() }}>
              {tempOffset > 0 ? `+${tempOffset}` : tempOffset}°C
            </span>
          </div>
          <input
            type="range"
            min="-10"
            max="10"
            step="1"
            value={tempOffset}
            onChange={(e) => setTempOffset(Number(e.target.value))}
            className="w-full h-1.5 rounded-lg bg-slate-850 appearance-none cursor-pointer accent-indigo-500 transition-colors"
          />
          <div className="flex justify-between text-[10px] font-mono text-slate-500 px-1">
            <span>-10°C (Cold Spell)</span>
            <span>Baseline</span>
            <span>+10°C (Heatwave)</span>
          </div>
        </div>

        {/* 2. Rainfall Target Slider */}
        <div className="flex flex-col gap-2.5">
          <div className="flex justify-between items-center text-sm">
            <span className="flex items-center gap-2 font-medium text-slate-300">
              <Droplets className="w-4 h-4 text-blue-400" /> Precipitation Volume
            </span>
            <span className="font-mono font-bold text-[13px] px-2.5 py-0.5 rounded bg-slate-800 border border-white/5 text-blue-400" style={{ color: getRainColor() }}>
              {rainVolume} mm
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={rainVolume}
            onChange={(e) => setRainVolume(Number(e.target.value))}
            className="w-full h-1.5 rounded-lg bg-slate-850 appearance-none cursor-pointer accent-blue-500"
          />
          <div className="flex justify-between text-[10px] font-mono text-slate-500 px-1">
            <span>0mm (Dry)</span>
            <span>50mm</span>
            <span>100mm (Heavy Deluge)</span>
          </div>
        </div>

        {/* 3. Nitrogen Application Slider */}
        <div className="flex flex-col gap-2.5">
          <div className="flex justify-between items-center text-sm">
            <span className="flex items-center gap-2 font-medium text-slate-300">
              <Sprout className="w-4 h-4 text-emerald-400" /> Nitrogen Fertilizer (Urea)
            </span>
            <span className="font-mono font-bold text-[13px] px-2.5 py-0.5 rounded bg-slate-800 border border-white/5 text-emerald-400" style={{ color: getNitrogenColor() }}>
              {nitrogenApplied} kg/ha
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="200"
            step="10"
            value={nitrogenApplied}
            onChange={(e) => setNitrogenApplied(Number(e.target.value))}
            className="w-full h-1.5 rounded-lg bg-slate-850 appearance-none cursor-pointer accent-emerald-500"
          />
          <div className="flex justify-between text-[10px] font-mono text-slate-500 px-1">
            <span>None</span>
            <span>100 kg/ha</span>
            <span>200 kg/ha (Intense Feed)</span>
          </div>
        </div>

        {/* 4. Irrigation Schedule Selector */}
        <div className="flex flex-col gap-2.5">
          <span className="text-sm font-medium text-slate-300">Irrigation Operation Override</span>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              { id: "default", label: "Default Scheduled" },
              { id: "none", label: "Stop Irrigation" },
              { id: "run", label: "Single Run (15mm)" },
              { id: "daily", label: "Daily Run (5mm/d)" },
            ].map((opt) => (
              <button
                key={opt.id}
                onClick={() => setIrrigationMode(opt.id)}
                className={`py-3 px-2 text-center rounded-xl border font-semibold transition-all duration-150 active:scale-95 ${
                  irrigationMode === opt.id
                    ? "bg-indigo-600 border-indigo-500 text-white shadow-md shadow-indigo-600/15"
                    : "bg-slate-850 hover:bg-slate-800 border-white/5 text-slate-400 hover:text-slate-200"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Execute Action Button */}
        <div className="mt-2 relative">
          <button
            onClick={handleRunSimulation}
            disabled={loading}
            className={`w-full py-4 rounded-xl flex items-center justify-center gap-2 font-bold tracking-wide transition-all duration-150 active:scale-98 ${
              loading
                ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-white/5"
                : "bg-gradient-to-r from-indigo-500 to-blue-600 hover:from-indigo-600 hover:to-blue-700 text-white shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/35 border border-indigo-400/20"
            }`}
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-1" />
                Propagating State-Space Model...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                Propagate Yield Simulation
              </>
            )}
          </button>
          {!loading && (
            <span className="absolute inline-flex h-full w-full rounded-xl bg-indigo-500/10 opacity-30 animate-ping pointer-events-none -inset-px" style={{ animationDuration: '2.5s' }} />
          )}
        </div>

        {error && (
          <div className="p-3.5 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs flex gap-2">
            <span className="mt-0.5">⚠️</span>
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* ── RIGHT PANEL: DYNAMIC SIMULATION COMPARISON ── */}
      <div className="flex-1 flex flex-col gap-6">
        <AnimatePresence mode="wait">
          {!results ? (
            /* 1. Placeholder state: Invite simulation run */
            <motion.div
              key="placeholder"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              className="flex-1 flex flex-col items-center justify-center p-12 rounded-2xl border border-white/10 border-dashed bg-slate-900/20 text-center"
            >
              <div className="w-16 h-16 rounded-2xl bg-indigo-500/5 border border-indigo-500/10 flex items-center justify-center text-indigo-400/70 mb-6">
                <Brain className="w-8 h-8 animate-pulse" />
              </div>
              <h4 className="text-lg font-light text-slate-200">Interactive Yield Simulator Ready</h4>
              <p className="text-slate-500 text-sm max-w-sm mt-2 leading-relaxed">
                Adjust the environmental offsets on the left and click **Propagate Yield Simulation** to execute offline biophysical differential loops.
              </p>
            </motion.div>
          ) : (
            /* 2. Simulation Results Dashboard */
            <motion.div
              key="results"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="flex flex-col gap-6 w-full"
            >
              {/* Projections Headline and Badges */}
              <div className="flex flex-col gap-3 p-5 rounded-2xl border border-white/10 bg-slate-900/40">
                <div className="flex justify-between items-start flex-wrap gap-4">
                  <div>
                    <span className="text-[10px] uppercase font-bold tracking-widest bg-indigo-500/15 border border-indigo-500/20 text-indigo-300 px-2.5 py-1 rounded">
                      Model Propagated
                    </span>
                    <h3 className="m-0 text-xl font-light text-slate-100 tracking-wide mt-2.5">
                      7-Day Biophysical Outcrop Projections
                    </h3>
                  </div>
                  
                  {/* Suitability score derived */}
                  <div className="flex gap-2">
                    <div className="flex flex-col items-end px-3 py-1.5 bg-slate-900/80 rounded-xl border border-white/5">
                      <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold">Horizon</span>
                      <span className="text-sm font-mono font-bold text-slate-300">7 Days Forward</span>
                    </div>
                  </div>
                </div>

                <hr className="border-white/5" />

                {/* Day 7 Delta Highlights */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 mt-1">
                  {/* Moisture Delta */}
                  <div className="p-4 rounded-xl bg-slate-900/60 border border-white/5 flex flex-col gap-1">
                    <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Soil Moisture Delta (Day 7)</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className={`text-xl font-mono font-bold ${results.projections.soil_moisture.delta_day7 > 0 ? "text-emerald-400" : results.projections.soil_moisture.delta_day7 < 0 ? "text-rose-400" : "text-slate-400"}`}>
                        {results.projections.soil_moisture.delta_day7 > 0 ? "+" : ""}{results.projections.soil_moisture.delta_day7}%
                      </span>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {results.projections.soil_moisture.simulated[6]}% simulated
                      </span>
                    </div>
                  </div>
                  {/* Nitrogen Delta */}
                  <div className="p-4 rounded-xl bg-slate-900/60 border border-white/5 flex flex-col gap-1">
                    <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">N Deficit Delta (Day 7)</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className={`text-xl font-mono font-bold ${results.projections.nitrogen_deficit.delta_day7 < 0 ? "text-emerald-400" : results.projections.nitrogen_deficit.delta_day7 > 0 ? "text-rose-400" : "text-slate-400"}`}>
                        {results.projections.nitrogen_deficit.delta_day7 > 0 ? "+" : ""}{results.projections.nitrogen_deficit.delta_day7} kg/ha
                      </span>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {results.projections.nitrogen_deficit.simulated[6]} kg/ha simulated
                      </span>
                    </div>
                  </div>
                  {/* Fungal Risk Delta */}
                  <div className="p-4 rounded-xl bg-slate-900/60 border border-white/5 flex flex-col gap-1">
                    <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Fungal Threat Delta (Day 7)</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className={`text-xl font-mono font-bold ${results.projections.fungal_risk.delta_day7 < 0 ? "text-emerald-400" : results.projections.fungal_risk.delta_day7 > 0 ? "text-rose-400" : "text-slate-400"}`}>
                        {results.projections.fungal_risk.delta_day7 > 0 ? "+" : ""}{results.projections.fungal_risk.delta_day7}%
                      </span>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {results.projections.fungal_risk.simulated[6]}% simulated
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Dynamic Graphic Display (Charts Panel) */}
              <div className="flex flex-col rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-lg">
                {/* Tabs */}
                <div className="flex items-center gap-2 mb-6 border-b border-white/5 pb-3">
                  {[
                    { id: "moisture", label: "Soil Moisture %", icon: <Droplets className="w-3.5 h-3.5" /> },
                    { id: "nitrogen", label: "Nitrogen Deficit kg/ha", icon: <Sprout className="w-3.5 h-3.5" /> },
                    { id: "risk", label: "Fungal Risk %", icon: <Info className="w-3.5 h-3.5" /> },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveChartTab(tab.id as any)}
                      className={`flex items-center gap-1.5 py-2 px-4 text-xs font-semibold rounded-lg border transition-all ${
                        activeChartTab === tab.id
                          ? "bg-indigo-600/10 border-indigo-500/40 text-indigo-300"
                          : "bg-slate-900/30 hover:bg-slate-900/70 border-white/5 text-slate-450 hover:text-slate-200"
                      }`}
                    >
                      {tab.icon}
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Recharts Wrapper */}
                <div className="h-[280px] w-full mt-2 font-mono text-[11px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                      <XAxis dataKey="name" stroke="#64748b" />
                      <YAxis stroke="#64748b" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#0F172A",
                          borderColor: "rgba(255,255,255,0.1)",
                          borderRadius: "12px",
                          color: "#F8FAFC",
                          fontFamily: "monospace",
                        }}
                      />
                      <Legend wrapperStyle={{ paddingTop: "10px" }} />
                      
                      {activeChartTab === "moisture" && (
                        <>
                          <Line type="monotone" dataKey="Soil Moisture (Base)" stroke="#64748b" strokeWidth={2.5} strokeDasharray="5 5" />
                          <Line type="monotone" dataKey="Soil Moisture (Sim)" stroke="#60a5fa" strokeWidth={3} activeDot={{ r: 6 }} />
                        </>
                      )}

                      {activeChartTab === "nitrogen" && (
                        <>
                          <Line type="monotone" dataKey="Nitrogen Deficit (Base)" stroke="#64748b" strokeWidth={2.5} strokeDasharray="5 5" />
                          <Line type="monotone" dataKey="Nitrogen Deficit (Sim)" stroke="#10b981" strokeWidth={3} activeDot={{ r: 6 }} />
                        </>
                      )}

                      {activeChartTab === "risk" && (
                        <>
                          <Line type="monotone" dataKey="Fungal Risk (Base)" stroke="#64748b" strokeWidth={2.5} strokeDasharray="5 5" />
                          <Line type="monotone" dataKey="Fungal Risk (Sim)" stroke="#f59e0b" strokeWidth={3} activeDot={{ r: 6 }} />
                        </>
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Mechanistic Formulas (LaTeX) container */}
              <div className="flex flex-col p-5 bg-[#0B1015]/95 border border-white/5 rounded-2xl">
                <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase tracking-wider mb-3">
                  <Brain className="w-3.5 h-3.5 text-indigo-400" /> Underlying Physical Modeling Equations
                </div>
                <div className="flex flex-col gap-4 text-slate-300 text-xs leading-relaxed font-sans">
                  {/* Formula 1 */}
                  <div className="p-3 bg-black/40 rounded-xl border border-white/5 flex flex-col gap-2">
                    <div className="font-semibold text-slate-400">1. Penman-Monteith Evapotranspiration scaling:</div>
                    <code className="text-indigo-300 font-mono block p-2 bg-[#090D11] rounded border border-white/5 select-all overflow-x-auto whitespace-nowrap">
                      {results.equations_used.et0_scaling}
                    </code>
                    <p className="text-[11px] text-slate-500 m-0 leading-normal">
                      Adjusts transpiration rates by 5% per °C temperature shift from reference baseline averages (22°C).
                    </p>
                  </div>
                  {/* Formula 2 */}
                  <div className="p-3 bg-black/40 rounded-xl border border-white/5 flex flex-col gap-2">
                    <div className="font-semibold text-slate-400">2. Soil Liebig Water Bucket dynamics:</div>
                    <code className="text-blue-300 font-mono block p-2 bg-[#090D11] rounded border border-white/5 select-all overflow-x-auto whitespace-nowrap">
                      {results.equations_used.water_balance}
                    </code>
                    <p className="text-[11px] text-slate-500 m-0 leading-normal">
                      Determines daily water saturation/depletion %clutched by decadal Plot DNA traits (retention $\theta$ and capacity).
                    </p>
                  </div>
                  {/* Formula 3 */}
                  <div className="p-3 bg-black/40 rounded-xl border border-white/5 flex flex-col gap-2">
                    <div className="font-semibold text-slate-400">3. Gaussian Spore Outbreak Outcrop:</div>
                    <code className="text-orange-300 font-mono block p-2 bg-[#090D11] rounded border border-white/5 select-all overflow-x-auto whitespace-nowrap">
                      {results.equations_used.biotic_outbreak}
                    </code>
                    <p className="text-[11px] text-slate-500 m-0 leading-normal">
                      Models fungal germination probability shifts driven by leaf wetness durations clutched by heat stresses.
                    </p>
                  </div>
                </div>
              </div>

              {/* Dynamic Narrative Summary */}
              <div className="p-5 bg-indigo-500/5 border border-indigo-500/10 rounded-2xl flex items-start gap-3">
                <Info className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                <div className="text-sm leading-relaxed text-slate-350 font-sans">
                  <span className="font-bold text-slate-200 block mb-1">Agronomist Sandbox Summary</span>
                  {results.projections.soil_moisture.delta_day7 > 0 ? (
                    <span>
                      Applying moisture factors yields a **positive {results.projections.soil_moisture.delta_day7}% gain** in soil moisture at Day 7. 
                    </span>
                  ) : (
                    <span>
                      Elevated weather stress triggers a **depletion of {Math.abs(results.projections.soil_moisture.delta_day7)}%** in water reserves by Day 7.
                    </span>
                  )}
                  {results.environmental_assumptions.nitrogen_applied_kg_ha > 0 ? (
                    <span>
                      {" "}Nitrogen application successfully suppresses the crop deficit boundary by **{Math.abs(results.projections.nitrogen_deficit.delta_day7)} kg/ha** compared to the unfertilized baseline, maximizing Mitscherlich-Baule demand uptake.
                    </span>
                  ) : (
                    <span>
                      {" "}Accumulated transpiration uptake triggers a continuous deficit boundary rise of **{results.projections.nitrogen_deficit.simulated[6]} kg/ha** at Day 7.
                    </span>
                  )}
                  {results.projections.fungal_risk.delta_day7 > 0 ? (
                    <span>
                      {" "}**Warning:** Altered leaf wetness dynamics elevate biotic spore risk thresholds by **{results.projections.fungal_risk.delta_day7}%**. Monitor for Bacterial Blight spots.
                    </span>
                  ) : (
                    <span>
                      {" "}Dry canopy conditions safely hold fungal spore spreads to a low **{results.projections.fungal_risk.simulated[6]}%** risk index.
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

    </div>
  );
}
