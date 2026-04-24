"use client";

import { useState, useEffect } from "react";
import AgriBrainChat from "@/components/farm/AgriBrainChat";
import { type Layer10Result, MODE_SURFACE_MAP, type MapMode } from "@/hooks/useLayer10";

interface AgriBrainWorkspaceProps {
  isOpen: boolean;
  onClose: () => void;
  context: Record<string, unknown> | null;
  activeMode: string;
  data: Layer10Result | null;
  plotName?: string;
}

export default function AgriBrainWorkspace({
  isOpen,
  onClose,
  context,
  activeMode,
  data,
  plotName,
}: AgriBrainWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<"chat" | "explain" | "simulate" | "trust" | "history">("chat");
  const [prevIsOpen, setPrevIsOpen] = useState(isOpen);

  if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
    if (isOpen) {
      setActiveTab("chat"); // Reset
    }
  }

  useEffect(() => {
    if (!isOpen) return;

    document.body.style.overflow = "hidden"; // Lock scroll

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const activeSurfaceType = MODE_SURFACE_MAP[activeMode as MapMode];
  const activePack = data?.explainability_pack?.[activeSurfaceType];

  return (
    <div 
      className="fixed inset-0 w-full h-full bg-[#0B1015] z-50 flex flex-col animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="workspace-title"
    >
      
      {/* Header Ribbon */}
      <div className="px-6 py-4 flex items-center justify-between border-b border-white/10 shrink-0 bg-linear-to-r from-slate-900 to-indigo-950/20">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center text-indigo-400">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 id="workspace-title" className="text-xl font-light text-white tracking-wide">{plotName ? `${plotName} Intelligence` : "AgriBrain Workspace"}</h1>
              <div className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase tracking-widest border border-emerald-500/20">
                Inference Active
              </div>
            </div>
            <p className="text-[13px] text-slate-400 font-medium tracking-wide mt-1">
              {activeMode.charAt(0).toUpperCase() + activeMode.slice(1).replace("_", " ")} intelligence &middot; {(data?.quality?.reliability_score ? (data.quality.reliability_score * 100).toFixed(0) : "N/A")}% confidence
            </p>
          </div>
        </div>

        <button 
            onClick={onClose} 
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-slate-300 hover:text-white hover:bg-white/10 rounded-lg transition-colors border border-white/10"
        >
          Close Workspace
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>

      {/* Main Workspace Body (2-Column) */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Column (70%) - Chat & Scenarios */}
        <div className="w-[70%] flex flex-col border-r border-white/10 relative">
           
           {/* In this version, we combine Chat and Scenarios via local tabs for clarity, but giving them full width */}
           <div className="flex items-center px-6 border-b border-white/5 shrink-0 bg-[#0B1015]/80">
            {[{id: "chat", label: "Chat"}, {id: "simulate", label: "Agronomic Projections"}].map((tab) => {
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as "chat" | "simulate")}
                  className={`min-w-[120px] py-4 text-sm font-medium border-b-2 transition-colors relative top-px capitalize whitespace-nowrap ${
                    activeTab === tab.id 
                      ? "border-indigo-500 text-indigo-300" 
                      : "border-transparent text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="flex-1 overflow-hidden relative">
              {activeTab !== "simulate" && (
                <div className="absolute inset-0 animate-fade-in">
                  <AgriBrainChat context={context} />
                </div>
              )}

              {activeTab === "simulate" && (
                <div className="absolute inset-0 p-8 overflow-y-auto animate-fade-in selection:bg-indigo-500/30">
                   <div className="max-w-4xl mx-auto">
                      <h2 className="text-2xl font-light text-white mb-6">Agronomic Projections</h2>
                      <div className="grid grid-cols-2 gap-6">
                        {data?.scenario_pack?.map((scn, idx) => (
                          <div key={idx} className={`p-6 bg-slate-800/20 rounded-2xl border border-white/10 hover:border-white/20 transition-colors ${idx > 1 ? 'opacity-70' : ''}`}>
                            <div className="flex justify-between items-start mb-4">
                              <h4 className={`text-sm font-bold uppercase tracking-widest ${idx === 0 ? 'text-emerald-400' : idx === 1 ? 'text-indigo-400' : 'text-rose-400'}`}>{scn.title}</h4>
                              <span className="text-xs bg-slate-800 text-slate-300 px-3 py-1 rounded-full border border-white/5 font-mono">
                                {idx === 0 ? 'Next 24h' : idx === 1 ? 'Within 3d' : 'Coming week'}
                              </span>
                            </div>
                            <p className="text-sm text-slate-400 mb-6 leading-relaxed">{scn.description}</p>
                            <div className="flex flex-col gap-2 text-sm font-mono">
                              {scn.outcomes?.map((out, oidx) => (
                                <div key={oidx} className={`flex items-center justify-between p-3 rounded-lg bg-black/20 ${out.sentiment === 'positive' ? 'text-emerald-400' : out.sentiment === 'negative' ? 'text-rose-400' : 'text-slate-400'}`}>
                                  <span className="font-sans text-slate-300">{out.label}</span>
                                  <span className="font-bold">{out.value}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                        {!data?.scenario_pack?.length && (
                          <div className="col-span-2 text-center py-20 text-slate-500 bg-white/5 rounded-2xl border border-white/5 border-dashed">
                            No active scenarios loaded for this context.
                          </div>
                        )}
                      </div>
                   </div>
                </div>
              )}
          </div>
        </div>

        {/* Right Column (30%) - Evidence, Trust & Methodology */}
        <div className="w-[30%] flex flex-col bg-[#0B1015]">
          <div className="flex items-center px-4 border-b border-white/5 shrink-0 bg-[#0B1015]/80">
            {[
              {id: "explain", label: "Evidence Trace"}, 
              {id: "trust", label: "Confidence & Reliability"}, 
              {id: "history", label: "Field History"}
            ].map((tab) => {
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as "explain" | "trust" | "history")}
                  className={`min-w-[90px] py-4 px-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors relative top-px whitespace-nowrap ${
                    activeTab === tab.id || (activeTab === "chat" && tab.id === "explain") || (activeTab === "simulate" && tab.id === "explain")
                      ? "border-slate-400 text-slate-200" 
                      : "border-transparent text-slate-600 hover:text-slate-400"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="flex-1 overflow-y-auto p-6 relative">
             {/* By default we map 'chat' and 'simulate' activeTabs to show 'explain' side-panel. Otherwise respect activeTab for trust/history */}
             {(activeTab === "chat" || activeTab === "simulate" || activeTab === "explain") && (
                <div className="animate-fade-in flex flex-col">
                  {data && activePack ? (
                    <div className="space-y-8">
                      {/* Summary */}
                      <div className="p-5 bg-indigo-900/10 border border-indigo-500/20 rounded-2xl">
                        <h4 className="text-[10px] text-indigo-400 font-bold uppercase tracking-widest mb-3">Synthesized Intelligence</h4>
                        <p className="text-[15px] text-slate-300 leading-relaxed font-light">{activePack.summary}</p>
                      </div>

                      {/* Top Drivers */}
                      <div>
                        <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-4">Key Evidence</h4>
                        <div className="space-y-3">
                          {activePack.top_drivers.map((d, i) => (
                            <div key={i} className="flex flex-col bg-white/5 rounded-xl p-4 border border-white/5">
                              <div className="flex justify-between items-center mb-1.5">
                                <span className="text-sm font-medium text-slate-200">{d.name}</span>
                                <span className={`text-sm font-bold font-mono ${d.role === 'positive' ? 'text-emerald-400' : d.role === 'negative' ? 'text-rose-400' : 'text-amber-400'}`}>
                                  {d.value > 0 ? "+" : ""}{d.value.toFixed(2)}
                                </span>
                              </div>
                              <span className="text-[10px] text-slate-500 uppercase tracking-wider">{d.role} Impact</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      {/* Methodology Highlight */}
                      <div className="p-5 bg-white/5 rounded-2xl border border-white/5">
                        <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-3">Model Engine Provenance</h4>
                        <div className="text-xs text-slate-400 font-mono mb-3 bg-black/30 p-3 rounded-lg">
                          {activePack.equations[0]?.expression || "Ensemble interpolation running."}
                        </div>
                        <p className="text-[10px] text-slate-500 uppercase tracking-wider">Version: {activePack.provenance.model_version}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-center mt-32">
                      <svg className="text-slate-700 mb-4" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                      <p className="text-sm text-slate-600">Contextual evidence not loaded.</p>
                    </div>
                  )}
                </div>
             )}

             {activeTab === "trust" && (
                <div className="animate-fade-in flex flex-col">
                  {data ? (
                    <div className="space-y-6">
                      <div className={`p-5 rounded-2xl border ${data.quality.reliability_score >= 0.8 ? 'bg-emerald-900/10 border-emerald-500/20' : data.quality.reliability_score >= 0.5 ? 'bg-amber-900/10 border-amber-500/20' : 'bg-rose-900/10 border-rose-500/20'} flex items-center justify-between`}>
                        <div>
                          <span className="block text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1.5">Overall Trust</span>
                          <span className={`text-2xl font-bold font-mono ${data.quality.reliability_score >= 0.8 ? 'text-emerald-400' : data.quality.reliability_score >= 0.5 ? 'text-amber-400' : 'text-rose-400'}`}>
                            {(data.quality.reliability_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="text-right">
                           <span className="block text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1.5">Fall-back State</span>
                           <span className="text-sm font-bold text-slate-300 uppercase tracking-wider">{data.quality.degradation_mode.replace(/_/g, " ")}</span>
                        </div>
                      </div>

                      <div className="p-5 rounded-2xl bg-white/5 border border-white/5">
                         <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-4">Pipeline Integration Checks</h4>
                         <ul className="space-y-3 text-sm">
                            <li className="flex items-center justify-between pb-3 border-b border-white/5">
                              <span className="text-slate-400">Grid Alignment</span>
                              <span className={data.quality.grid_alignment_ok ? "text-emerald-400 font-medium" : "text-rose-400 font-medium"}>{data.quality.grid_alignment_ok ? 'Perfect Synced' : 'Interpolation Required'}</span>
                            </li>
                            <li className="flex items-center justify-between pb-3 border-b border-white/5">
                              <span className="text-slate-400">Detail Conservation</span>
                              <span className={data.quality.detail_conservation_ok ? "text-emerald-400 font-medium" : "text-amber-400 font-medium"}>{data.quality.detail_conservation_ok ? 'Strictly Conserved' : 'Edge Smoothing'}</span>
                            </li>
                            <li className="flex items-center justify-between">
                              <span className="text-slate-400">Rendered Surfaces</span>
                              <span className="text-slate-200 font-mono text-xs">{data.quality.surfaces_generated}</span>
                            </li>
                         </ul>
                      </div>

                      {data.quality.warnings.length > 0 && (
                         <div className="p-5 rounded-2xl bg-amber-900/10 border border-amber-500/30">
                            <h4 className="text-[10px] font-bold text-amber-500 uppercase tracking-wider mb-3">Active Penalties</h4>
                            <ul className="list-disc pl-5 text-sm text-amber-200/80 space-y-2 leading-relaxed">
                              {data.quality.warnings.map((w, i) => <li key={i}>{w}</li>)}
                            </ul>
                         </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-center mt-32">
                      <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
                      <p className="text-sm text-slate-500">Connecting to telemetry stream...</p>
                    </div>
                  )}
                </div>
             )}

             {activeTab === "history" && (
                <div className="animate-fade-in flex flex-col">
                  <div className="relative border-l border-white/10 ml-4 space-y-8 pb-8 mt-2 cursor-default">
                    {data?.history_pack?.map((hist, idx) => {
                      const isAction = hist.type === 'USER_ACTION';
                      const isSuccess = hist.title.toLowerCase().includes('validate') || hist.title.toLowerCase().includes('recover');
                      const bgContainer = isSuccess ? 'bg-emerald-900/10 border-emerald-500/20' : 'bg-white/5 border-white/5';
                      const dotColor = isAction ? 'bg-indigo-500' : isSuccess ? 'bg-emerald-500' : 'bg-slate-600';
                      
                      return (
                        <div key={idx} className="relative pl-8">
                          <div className={`absolute -left-[7px] top-1.5 w-3.5 h-3.5 ${dotColor} rounded-full border-[3px] border-[#0B1015]`}></div>
                          <div className="text-xs text-slate-500 font-mono mb-2">{hist.timestamp}</div>
                          <div className={`p-4 rounded-xl border ${bgContainer}`}>
                            <p className={`text-sm font-bold mb-1.5 ${isSuccess ? 'text-emerald-400' : 'text-slate-200'}`}>{hist.title}</p>
                            <p className={`text-sm leading-relaxed ${isSuccess ? 'text-emerald-200/70' : 'text-slate-400'}`}>{hist.description}</p>
                          </div>
                        </div>
                      );
                    })}
                    {!data?.history_pack?.length && (
                      <div className="text-center text-sm text-slate-600 mt-20">No history available for context.</div>
                    )}
                  </div>
                </div>
             )}
          </div>
        </div>

      </div>
    </div>
  );
}
