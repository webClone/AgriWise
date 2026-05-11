"use client";

import { useState, useEffect } from "react";
import { Brain, X } from "lucide-react";
import AgriBrainChat from "@/components/farm/AgriBrainChat";
import { type Layer10Result, MODE_SURFACE_MAP, type MapMode } from "@/hooks/useLayer10";
import WorkspaceIntelPanel from "./WorkspaceIntelPanel";

interface AgriBrainWorkspaceProps {
  isOpen: boolean;
  onClose: () => void;
  context: Record<string, unknown> | null;
  activeMode: string;
  data: Layer10Result | null;
  plotName?: string;
  initialQuery?: string | null;
}

export default function AgriBrainWorkspace({
  isOpen,
  onClose,
  context,
  activeMode,
  data,
  plotName,
  initialQuery,
}: AgriBrainWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<"chat" | "simulate">("chat");
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
      dir="ltr"
    >
      
      {/* Header Ribbon */}
      <div className="px-6 py-4 flex items-center justify-between border-b border-white/5 shrink-0 bg-[#0B1015]/95 backdrop-blur-xl shadow-lg">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.15)]">
            <Brain size={24} strokeWidth={1.5} />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 id="workspace-title" className="text-[22px] font-light text-white tracking-wide">AgriBrain <span className="font-semibold text-indigo-400">Assistant</span></h1>
              <div className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase tracking-widest border border-emerald-500/20 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live Inference
              </div>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-[13px] text-slate-400 font-medium tracking-wide">
                {plotName ? `Analyzing ${plotName}` : "Plot Analysis"} &middot; {activeMode.charAt(0).toUpperCase() + activeMode.slice(1).replace("_", " ")} Model
              </p>
              <span className="text-[13px] text-slate-600">&middot;</span>
              <p className="text-[13px] text-slate-500 font-medium tracking-wide">
                {(data?.quality?.reliability_score ? (data.quality.reliability_score * 100).toFixed(0) : "N/A")}% System Confidence
              </p>
            </div>
          </div>
        </div>

        <button 
            onClick={onClose} 
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-slate-400 hover:text-white hover:bg-white/10 rounded-xl transition-colors border border-white/5 hover:border-white/10 bg-white/5"
        >
          Close Workspace
          <X size={16} strokeWidth={2.5} />
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
                  <AgriBrainChat 
                    context={context} 
                    initialQuery={initialQuery}
                    suggestedQuery={
                      activeTab === "chat" && !initialQuery
                        ? { label: "Ask about this evidence", query: "Can you explain the current evidence trace and its top drivers in detail?" } 
                        : null
                    }
                  />
                </div>
              )}

              {activeTab === "simulate" && (
                <div className="absolute inset-0 p-8 overflow-y-auto animate-fade-in selection:bg-indigo-500/30">
                   <div className="max-w-4xl mx-auto">
                      <h2 className="text-2xl font-light text-white mb-6">Agronomic Projections</h2>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-20">
                        {data?.scenario_pack?.map((scn, idx) => (
                          <div key={idx} className={`flex flex-col p-6 bg-[#0B1015]/60 rounded-2xl border border-white/10 hover:border-white/20 transition-colors shadow-lg ${idx > 1 ? '' : ''}`}>
                            <div className="flex justify-between items-start mb-4">
                              <h4 className={`text-sm font-bold uppercase tracking-widest ${idx === 0 ? 'text-slate-400' : idx === 1 ? 'text-indigo-400' : 'text-emerald-400'}`}>{scn.title}</h4>
                              <span className="text-[10px] uppercase font-bold tracking-widest bg-slate-800/80 text-slate-300 px-2.5 py-1 rounded-md border border-white/5">
                                {idx === 0 ? 'Baseline' : idx === 1 ? 'Primary Action' : 'Alternative'}
                              </span>
                            </div>
                            <p className="text-sm text-slate-400 mb-6 leading-relaxed flex-1">{scn.description}</p>
                            
                            {/* Key Metrics Row */}
                            <div className="grid grid-cols-3 gap-2 mb-6">
                              <div className="flex flex-col gap-1 p-3 rounded-xl bg-slate-900/50 border border-white/5">
                                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Yield Impact</span>
                                <span className={`text-sm font-mono font-bold ${scn.yield_impact_pct && scn.yield_impact_pct > 0 ? 'text-emerald-400' : scn.yield_impact_pct && scn.yield_impact_pct < 0 ? 'text-rose-400' : 'text-slate-300'}`}>
                                  {scn.yield_impact_pct != null ? `${scn.yield_impact_pct > 0 ? '+' : ''}${scn.yield_impact_pct}%` : '—'}
                                </span>
                              </div>
                              <div className="flex flex-col gap-1 p-3 rounded-xl bg-slate-900/50 border border-white/5">
                                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Action Cost</span>
                                <span className="text-sm font-mono font-bold text-slate-300">
                                  {scn.cost_of_action ? `$${scn.cost_of_action}/ha` : '—'}
                                </span>
                              </div>
                              <div className="flex flex-col gap-1 p-3 rounded-xl bg-slate-900/50 border border-white/5">
                                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Val at Risk</span>
                                <span className="text-sm font-mono font-bold text-amber-400">
                                  {scn.val_at_risk ? `$${scn.val_at_risk}/ha` : '—'}
                                </span>
                              </div>
                            </div>

                            <div className="flex flex-col gap-2 text-sm font-mono">
                              {scn.outcomes?.map((out, oidx) => (
                                <div key={oidx} className={`flex items-center justify-between px-4 py-3 rounded-xl bg-black/30 border border-white/5 ${out.sentiment === 'positive' ? 'text-emerald-400' : out.sentiment === 'negative' ? 'text-rose-400' : 'text-slate-400'}`}>
                                  <span className="font-sans text-[13px] text-slate-300 font-medium">{out.label}</span>
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

        {/* Right Column (30%) — Intelligence Stream */}
        <div className="w-[30%] flex flex-col bg-[#0B1015] border-l border-white/5 overflow-hidden min-h-0">
          <WorkspaceIntelPanel
            data={data}
            activeMode={activeMode}
            activeSurfaceType={activeSurfaceType}
            activePack={activePack}
          />
        </div>

      </div>
    </div>
  );
}
