"use client";

import { useState } from "react";
import type { Layer10Result } from "@/hooks/useLayer10";

// Standard UI Icons for the progressive disclosure tabs
const TabIcon = ({ type, active }: { type: string, active: boolean }) => {
  const color = active ? "text-indigo-400" : "text-slate-500";
  switch (type) {
    case "summary": return <svg className={color} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6h16M4 12h16M4 18h7"/></svg>;
    case "drivers": return <svg className={color} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>;
    case "charts": return <svg className={color} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>;
    case "equations": return <svg className={color} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>;
    case "provenance": return <svg className={color} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>;
    default: return null;
  }
};

interface MethodologyDrawerProps {
  metricKey: string | null;
  data: Layer10Result | null;
  onClose: () => void;
}

export default function MethodologyDrawer({ metricKey, data, onClose }: MethodologyDrawerProps) {
  const [activeTab, setActiveTab] = useState<"summary" | "drivers" | "charts" | "equations" | "provenance">("summary");

  if (!metricKey || !data) return null;

  const pack = data.explainability_pack?.[metricKey];
  
  if (!pack) {
    return (
      <>
        <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px] z-40 animate-fade-in transition-all" onClick={onClose} />
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full max-w-2xl bg-slate-900 border border-slate-700/60 rounded-t-2xl shadow-2xl z-50 p-6 flex flex-col items-center justify-center min-h-[300px]">
           <div className="text-slate-400 font-mono text-xs">Awaiting Layer 10 Explainability Pack for {metricKey}...</div>
           <button onClick={onClose} className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs rounded transition-colors">Close</button>
        </div>
      </>
    );
  }

  const renderSummary = () => (
    <div className="space-y-4 animate-fade-in-up">
      <div className="p-4 bg-slate-800/30 rounded-lg border border-slate-700/50">
        <p className="text-sm text-slate-300 leading-relaxed">
           <strong className="text-white font-semibold">{(metricKey.replace(/_/g, " ").toUpperCase())}</strong>: {pack.summary}
        </p>
      </div>
      <div className="flex gap-4">
        {pack.top_drivers.slice(0, 1).map((driver, idx) => (
          <div key={idx} className="flex-1 p-3 bg-emerald-900/10 border border-emerald-800/30 rounded-lg">
            <span className="text-[10px] text-emerald-500 font-bold tracking-wider uppercase">Deepest Driver</span>
            <p className="text-xs text-slate-300 mt-1">{driver.name}</p>
          </div>
        ))}
         {pack.confidence.penalties.slice(0, 1).map((penalty, idx) => (
          <div key={idx} className="flex-1 p-3 bg-amber-900/10 border border-amber-800/30 rounded-lg">
            <span className="text-[10px] text-amber-500 font-bold tracking-wider uppercase">Confidence Penalty</span>
            <p className="text-xs text-slate-300 mt-1">{penalty.reason}</p>
          </div>
        ))}
        {pack.confidence.penalties.length === 0 && (
           <div className="flex-1 p-3 bg-indigo-900/10 border border-indigo-800/30 rounded-lg">
            <span className="text-[10px] text-indigo-400 font-bold tracking-wider uppercase">Confidence Score</span>
            <p className="text-xs text-slate-300 mt-1">{(pack.confidence.score * 100).toFixed(0)}% (Nominal)</p>
          </div>
        )}
      </div>
    </div>
  );

  const renderDrivers = () => (
    <div className="animate-fade-in-up">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="text-[10px] text-slate-500 uppercase bg-slate-800/30">
          <tr>
            <th className="px-3 py-2 rounded-tl-lg">Driver Input</th>
            <th className="px-3 py-2">Role</th>
            <th className="px-3 py-2 text-right rounded-tr-lg">Weight</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/50">
          {pack.top_drivers.map((driver, idx) => (
            <tr key={idx} className="hover:bg-slate-800/20">
              <td className="px-3 py-2.5 font-medium text-indigo-300">{driver.name}</td>
              <td className="px-3 py-2.5 text-slate-400 capitalize">{driver.role}</td>
              <td className={`px-3 py-2.5 text-right ${driver.role === 'positive' ? 'text-emerald-400' : driver.role === 'negative' ? 'text-rose-400' : 'text-amber-400'}`}>
                {(driver.value > 0 ? '+' : '')}{driver.value.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderEquations = () => (
    <div className="space-y-4 animate-fade-in-up">
      {pack.equations.map((eq, idx) => (
        <div key={idx} className="p-4 bg-[#0d1117] rounded-lg font-mono text-xs overflow-x-auto border border-slate-700/50">
          <div className="text-slate-500 mb-2">{"// " + eq.label}</div>
          <div className="text-indigo-400">{eq.expression}</div>
          <div className="mt-3 text-emerald-400">Where:</div>
          <div className="text-slate-400 ml-4 whitespace-pre-line">{eq.plain_language}</div>
        </div>
      ))}
    </div>
  );

  const renderProvenance = () => (
    <div className="space-y-3 animate-fade-in-up text-xs">
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-slate-800/20 p-2.5 rounded border border-slate-700/30">
          <span className="block text-[9px] text-slate-500 uppercase mb-1">Source Imagery</span>
          <span className="text-slate-300 font-mono">{pack.provenance.sources.join(", ")}</span>
        </div>
        <div className="bg-slate-800/20 p-2.5 rounded border border-slate-700/30">
          <span className="block text-[9px] text-slate-500 uppercase mb-1">Acquisition Window</span>
          <span className="text-slate-300 font-mono text-[10px]">{pack.provenance.timestamps.join(" → ")}</span>
        </div>
        <div className="bg-slate-800/20 p-2.5 rounded border border-slate-700/30">
          <span className="block text-[9px] text-slate-500 uppercase mb-1">Pipeline Build</span>
          <span className="text-slate-300 font-mono">SIRE {pack.provenance.model_version}</span>
        </div>
        <div className="bg-slate-800/20 p-2.5 rounded border border-slate-700/30">
          <span className="block text-[9px] text-slate-500 uppercase mb-1">Run Hash</span>
          <span className="text-slate-300 font-mono">{pack.provenance.run_id.substring(0, 8)}</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px] z-40 animate-fade-in transition-all" onClick={onClose} />
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full max-w-2xl bg-slate-900 border border-slate-700/60 rounded-t-2xl shadow-2xl z-50 flex flex-col pointer-events-auto transform transition-transform duration-300 ease-out">
        
        {/* Header Ribbon */}
        <div className="px-6 py-4 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-wide">Methodology Inspector</h2>
              <p className="text-[10px] text-slate-400 font-mono mt-0.5">METRIC / {metricKey?.toUpperCase()}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-md transition-colors">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center px-6 gap-6 border-b border-slate-800 bg-slate-900/50">
          {(["summary", "drivers", "charts", "equations", "provenance"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex items-center gap-2 py-3 text-xs font-medium border-b-2 transition-colors relative top-px ${
                activeTab === tab 
                  ? "border-indigo-500 text-indigo-400" 
                  : "border-transparent text-slate-400 hover:text-slate-300"
              }`}
            >
              <TabIcon type={tab} active={activeTab === tab} />
              <span className="capitalize">{tab}</span>
            </button>
          ))}
        </div>

        {/* Dynamic Body */}
        <div className="p-6 min-h-[200px] bg-slate-950/20">
          {activeTab === "summary" && renderSummary()}
          {activeTab === "drivers" && renderDrivers()}
          {activeTab === "charts" && (
            <div className="space-y-4 animate-fade-in-up">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3">Model Driver Influence</h3>
              <div className="space-y-3">
                {pack.top_drivers.map((driver, idx) => {
                  const widthPct = Math.min(100, Math.max(5, Math.abs(driver.value) * 100));
                  const bgClass = driver.role === 'positive' ? 'bg-emerald-500' : driver.role === 'negative' ? 'bg-rose-500' : 'bg-amber-500';
                  return (
                    <div key={idx} className="flex flex-col gap-1">
                      <div className="flex justify-between text-[10px] text-slate-400">
                        <span>{driver.name}</span>
                        <span className="font-mono">{driver.value > 0 ? '+' : ''}{driver.value.toFixed(2)}</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden flex">
                        <div 
                          className={`h-full ${bgClass} rounded-full transition-all duration-1000 ease-out`} 
                          style={{ width: `${widthPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {activeTab === "equations" && renderEquations()}
          {activeTab === "provenance" && renderProvenance()}
        </div>
      </div>
    </>
  );
}
