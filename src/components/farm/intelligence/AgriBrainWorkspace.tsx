"use client";

import { useState, useEffect } from "react";
import { Brain, X } from "lucide-react";
import AgriBrainChat from "@/components/farm/AgriBrainChat";
import WhatIfSandboxUI from "@/components/farm/intelligence/WhatIfSandboxUI";
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
                   <div className="max-w-6xl mx-auto">
                      <WhatIfSandboxUI
                        plotId={String((context as any)?.plotId || (context as any)?.plot?.id || (context as any)?.plot_id || "")}
                        context={context}
                      />
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
