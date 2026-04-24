"use client";

import React, { useEffect } from "react";
import { useLayer10 } from "@/hooks/useLayer10";

interface Props {
  plot: { id: string; name: string; [key: string]: unknown };
  farm: { id: string; name: string; [key: string]: unknown };
  currentCrop: { cropCode: string; cropNameAr?: string; [key: string]: unknown } | null;
}

export default function AgriBrainCommandCenterClient({ plot, farm, currentCrop }: Props) {
  const { data, loading, fetchLayer10 } = useLayer10();

  useEffect(() => {
    fetchLayer10(plot.id, farm.id);
  }, [plot.id, farm.id, fetchLayer10]);

  // Fallbacks if data is not loaded yet
  const isLoading = loading || !data;
  
  // Extract canonical RunArtifact fields
  const activeWarning = data?.quality?.warnings?.[0] || "No critical alerts";
  const explanationSummary = data?.explainability_pack?.["NDVI_CLEAN"]?.summary || "Analyzing latest telemetry...";
  
  // Scenarios
  const scenario = data?.scenario_pack?.[0];
  const scenarioYieldValue = scenario?.yield_impact_pct ?? 0;
  
  // Economic Impact (Live from SIRE Layer 10/Layer 3 Risk Models)
  const valAtRisk = scenario?.val_at_risk;
  const costOfAction = scenario?.cost_of_action;
  const roi = (costOfAction && valAtRisk && costOfAction > 0) ? (valAtRisk / costOfAction).toFixed(1) : null;

  // History Pack action
  const latestAction = data?.history_pack?.find((h) => h.type === 'USER_ACTION') || data?.history_pack?.[0] || { title: "System Ready", description: "Awaiting telemetry" };

  return (
    <>
      {/* Sticky Intelligence Bar */}
      <div className="sticky top-0 z-40 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <span className="bg-linear-to-br from-indigo-500 to-purple-600 rounded-lg p-1.5 shadow-lg shadow-indigo-500/20 text-white">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            </span>
            AgriBrain Command Center
          </h1>
          <div className="text-sm text-slate-500 flex items-center gap-2 mt-1">
            <span>{farm.name}</span>
            <span className="text-slate-300 dark:text-slate-700">/</span>
            <span className="font-semibold text-slate-700 dark:text-slate-300">{plot.name}</span>
            {currentCrop && (
              <>
                <span className="text-slate-300 dark:text-slate-700">/</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{currentCrop.cropNameAr || currentCrop.cropCode}</span>
              </>
            )}
          </div>
        </div>
        
        <div className="hidden sm:flex items-center gap-4">
          <div className={`${data?.quality?.warnings?.length ? 'bg-rose-50 dark:bg-rose-900/20 border-rose-200 dark:border-rose-800' : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'} border px-4 py-2 rounded-xl flex items-center gap-3 shadow-sm transition-colors`}>
            <div className={`w-2 h-2 rounded-full ${data?.quality?.warnings?.length ? 'bg-rose-500 animate-pulse' : 'bg-amber-500'}`}></div>
            <div className="flex flex-col">
              <span className={`text-[10px] font-bold ${data?.quality?.warnings?.length ? 'text-rose-600 dark:text-rose-400' : 'text-amber-600 dark:text-amber-400'} uppercase tracking-widest`}>Act Now Priority</span>
              <span className={`text-sm font-bold ${data?.quality?.warnings?.length ? 'text-rose-700 dark:text-rose-300' : 'text-amber-700 dark:text-amber-300'}`}>
                {isLoading ? "Analyzing..." : activeWarning.split(".")[0]}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className={`p-6 max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6 mt-4 transition-opacity duration-500 ${isLoading ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
        
        {/* Left Col: Act-Now & Economics */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Executive Summary */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
            <div className="border-b border-slate-100 dark:border-slate-800 px-6 py-4 flex items-center gap-2 bg-slate-50/50 dark:bg-slate-800/20">
              <svg className="text-indigo-500" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
              <h2 className="font-bold text-slate-800 dark:text-slate-100">AI Diagnostic Summary</h2>
            </div>
            <div className="p-6">
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed text-[15px]">
                 {isLoading ? "Fetching SIRE Layer 10 synthesis..." : explanationSummary}
              </p>
            </div>
            <div className="bg-slate-50 dark:bg-slate-800/50 px-6 py-4 flex items-center gap-4">
               <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all hover:scale-105 active:scale-95 shadow-lg shadow-indigo-500/20">
                 Approve Action Plan
               </button>
               <button className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-sm">
                 Simulate Alternatives
               </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Yield Modeling */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <svg className="text-emerald-500" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                  <h2 className="font-bold text-slate-800 dark:text-slate-100">Yield Trajectory</h2>
                </div>
                <div className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 px-2 py-1 rounded font-mono uppercase tracking-widest">
                  Live Model
                </div>
              </div>
              <div className="flex items-end gap-3 mb-2">
                <span className={`text-4xl font-bold bg-clip-text text-transparent ${valAtRisk === undefined ? 'from-slate-400 to-slate-200 text-lg uppercase tracking-widest' : 'bg-linear-to-r from-slate-900 to-slate-600 dark:from-white dark:to-slate-400'}`}>
                  {valAtRisk === undefined ? "Requires Baseline" : "Calibrated"}
                </span>
                {valAtRisk !== undefined && <span className="text-slate-500 font-semibold mb-1.5 text-lg">Model Active</span>}
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className={`${scenarioYieldValue >= 0 ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20' : 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-900/20'} px-2.5 py-0.5 rounded-full font-bold`}>
                  {scenarioYieldValue > 0 ? '+' : ''}{scenarioYieldValue ? scenarioYieldValue.toFixed(1) : "0.0"}% expected impact
                </span>
                <span className="text-slate-500 block font-medium">vs trajectory</span>
              </div>
              <div className="mt-8 pt-6 border-t border-slate-100 dark:border-slate-800">
                <div className="flex justify-between text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
                  <span>Downside Risk</span>
                  <span>Optimal Potential</span>
                </div>
                <div className="w-full bg-slate-100 dark:bg-slate-800 h-2.5 rounded-full overflow-hidden flex shadow-inner">
                   <div className="bg-rose-400 w-[20%] border-r border-white/20"></div>
                   <div className="bg-slate-300 dark:bg-slate-600 w-[20%] border-r border-white/20"></div>
                   <div className="bg-emerald-500 transition-all duration-1000 border-r border-white/20" style={{width: `${Math.max(10, 40 + (scenarioYieldValue || 0) * 2)}%`}}></div>
                   <div className="bg-indigo-400 flex-1"></div>
                </div>
                <div className="flex justify-between text-sm font-mono font-bold text-slate-700 dark:text-slate-300 mt-2">
                  <span>{valAtRisk !== undefined ? "Low" : "N/A"}</span>
                  <span>{valAtRisk !== undefined ? "High" : "N/A"}</span>
                </div>
              </div>
            </div>

            {/* Economics & ROI */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center gap-2 mb-6">
                <svg className="text-amber-500" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                <h2 className="font-bold text-slate-800 dark:text-slate-100">Economic Impact</h2>
              </div>
              
              <div className="space-y-4 relative">
                <div className="absolute left-4 top-8 bottom-8 w-px bg-slate-200 dark:bg-slate-800 z-0"></div>
                <div className="flex justify-between items-center p-4 rounded-xl bg-white dark:bg-slate-900 border-2 border-amber-100 dark:border-amber-900/30 relative z-10 shadow-sm transition-transform hover:-translate-y-1">
                  <div className="flex flex-col">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-amber-600 dark:text-amber-500 mb-1">Value at Risk</span>
                    <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Yield Penalty</span>
                  </div>
                  <span className={`text-xl font-bold ${valAtRisk === undefined ? 'text-slate-400 text-sm uppercase' : 'text-amber-600 dark:text-amber-400'}`}>
                    {valAtRisk === undefined ? "N/A" : `-$${valAtRisk}`}
                  </span>
                </div>

                <div className="flex justify-between items-center p-4 rounded-xl bg-white dark:bg-slate-900 border-2 border-emerald-100 dark:border-emerald-900/30 relative z-10 shadow-sm transition-transform hover:-translate-y-1">
                  <div className="flex flex-col">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-600 dark:text-emerald-500 mb-1">Cost of Action</span>
                    <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Est. Resources</span>
                  </div>
                  <span className={`text-xl font-bold ${costOfAction === undefined ? 'text-slate-400 text-sm uppercase' : 'text-slate-900 dark:text-white'}`}>
                    {costOfAction === undefined ? "N/A" : `$${costOfAction}`}
                  </span>
                </div>

                <div className="flex justify-between items-center pl-6 pr-4 pt-3 border-t border-slate-100 dark:border-slate-800">
                  <span className="text-sm font-bold text-slate-600 dark:text-slate-300">Net ROI of Action</span>
                  <span className={`text-2xl font-black ${roi ? 'text-transparent bg-clip-text bg-linear-to-r from-emerald-500 to-emerald-400' : 'text-slate-400 text-lg'}`}>
                    {roi ? `${roi}x` : "Unavailable"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Col: Priority Actions & Trace */}
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm hover:shadow-md transition-shadow">
            <h2 className="font-bold text-slate-800 dark:text-slate-100 mb-6 flex items-center gap-2">
              <span className="bg-indigo-100 dark:bg-indigo-900/40 p-1.5 rounded-lg text-indigo-500">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
              </span>
              Critical Interventions
            </h2>
            
            <div className="space-y-5">
              {data?.quality?.warnings?.slice(0, 2).map((warning, idx) => (
                <div key={idx} className={`relative pl-5 before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-1.5 ${idx === 0 ? 'before:bg-rose-500' : 'before:bg-amber-400'} before:rounded-full`}>
                  <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100">{warning.split(":")[0] || "Alert"}</h4>
                  <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{warning}</p>
                  <div className={`mt-2.5 text-[10px] font-mono font-bold ${idx === 0 ? 'text-rose-600 bg-rose-50 dark:bg-rose-900/30 border-rose-100 dark:border-rose-800/50' : 'text-amber-700 dark:text-amber-500 bg-amber-50 dark:bg-amber-900/30 border-amber-100 dark:border-amber-800/50'} inline-block px-2.5 py-1 rounded-md border`}>
                    Confidence: {(data?.quality?.reliability_score * 100).toFixed(0)}%
                  </div>
                </div>
              )) || (
                <div className="text-sm text-slate-500 text-center py-4">No critical interventions required at this time.</div>
              )}
            </div>
          </div>
          
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm hover:shadow-md transition-shadow">
            <h2 className="font-bold text-slate-800 dark:text-slate-100 mb-6 flex items-center gap-2">
              <span className="bg-slate-100 dark:bg-slate-800 p-1.5 rounded-lg text-slate-500">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
              </span>
              Recent Activity Trace
            </h2>
            
            <div className="space-y-4">
               <div className="relative pl-5 before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-1.5 before:bg-indigo-500 before:rounded-full">
                  <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100">{latestAction.title}</h4>
                  <p className="text-xs text-slate-500 mt-1.5">{latestAction.description}</p>
               </div>
               
               <button className="w-full text-center mt-4 text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 transition-colors uppercase tracking-widest pt-4 border-t border-slate-100 dark:border-slate-800">
                 View Full Trace
               </button>
            </div>
          </div>
        </div>

      </div>
    </>
  );
}
