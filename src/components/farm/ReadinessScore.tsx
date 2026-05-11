"use client";

import { Info, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

interface ReadinessScoreProps {
  score: number;
  checks: {
    geometry: boolean;
    crop: boolean;
    soil: boolean;
    activeSensors: boolean;
    sensors: boolean;
    photos: boolean;
  };
  unlocks: {
    irrigation: boolean;
    yield: boolean;
    alerts: boolean;
  };
}

export default function ReadinessScore({ score, checks, unlocks }: ReadinessScoreProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const nextBestActions = [];
  if (!checks.activeSensors) nextBestActions.push({ action: "Activate soil moisture sensor", impact: "+12% irrigation precision" });
  if (!checks.soil) nextBestActions.push({ action: "Import recent soil analysis", impact: "+15% nutrient model accuracy" });
  if (!checks.crop) nextBestActions.push({ action: "Log current crop variety", impact: "Enables phenology tracking" });
  if (!checks.geometry) nextBestActions.push({ action: "Define plot geometry", impact: "Required for satellite data" });

  return (
    <div className="rounded-2xl border border-white/[0.06] p-5 min-w-[320px] flex flex-col justify-between" style={{ background: "linear-gradient(180deg, rgba(11,16,21,0.9) 0%, rgba(8,12,25,0.95) 100%)" }}>
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
              Field Intelligence Readiness
              <div title="Higher readiness improves AgriBrain prediction accuracy.">
                <Info size={10} className="text-slate-600 cursor-help" />
              </div>
            </h4>
          </div>
          <div className="flex flex-col items-end gap-0.5">
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] font-medium text-slate-600 uppercase tracking-wider">Model Trust</span>
              <span className={`text-[9px] font-bold ${score >= 80 ? 'text-emerald-400' : score >= 50 ? 'text-amber-400' : 'text-slate-500'}`}>
                {score >= 80 ? 'High' : score >= 50 ? 'Moderate' : 'Low'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] font-medium text-slate-600 uppercase tracking-wider">Data Coverage</span>
              <span className="text-[9px] font-bold text-indigo-400">
                {checks.activeSensors ? 'Live Monitoring' : checks.sensors ? 'Partial Live' : 'Satellite Only'}
              </span>
            </div>
          </div>
        </div>

        {/* Score + Big Number */}
        <div className="flex items-end gap-3 mb-2">
          <span className={`text-4xl font-mono font-black tracking-tighter ${score >= 80 ? 'text-emerald-400' : score >= 50 ? 'text-amber-400' : 'text-slate-500'}`}>
            {score}%
          </span>
          <div className="flex-1 pb-2">
            <div className="h-2 bg-slate-800/80 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-1000 ${score >= 80 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : 'bg-slate-500'}`}
                style={{ width: `${score}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex justify-between items-start mb-4">
          <p className="text-[9px] text-slate-600">{score >= 80 ? "Data supports high-confidence satellite analysis." : "Add more data to enable advanced models."}</p>
          <button onClick={() => setIsExpanded(!isExpanded)} className="text-[9px] text-indigo-400 font-medium hover:text-indigo-300 flex items-center gap-0.5 shrink-0">
            {isExpanded ? "Hide" : "Breakdown"}
            {isExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
          </button>
        </div>

        {isExpanded && (
          <div className="mb-4 bg-black/30 rounded-xl p-3 space-y-2.5 border border-white/[0.04] animate-in slide-in-from-top-2 fade-in duration-300">
            <ScoreRow label="Geometry" percent={30} isComplete={checks.geometry} />
            <ScoreRow label="Crop & Mgmt" percent={30} isComplete={checks.crop} />
            <ScoreRow label="Soil Data" percent={20} isComplete={checks.soil} />
            <ScoreRow label="Live Monitoring" percent={20} isComplete={checks.activeSensors} isPartial={checks.sensors && !checks.activeSensors} warning={!checks.activeSensors ? "Satellite + Weather Only" : undefined} />
          </div>
        )}

        {/* Unlock Indicators */}
        <div className="grid grid-cols-3 gap-2 mb-4 border-t border-white/[0.04] pt-4">
          <UnlockBadge label="Yield Prediction" unlocked={unlocks.yield} confidence="High" />
          <UnlockBadge label="Nutrient Engine" unlocked={checks.soil} confidence="Medium" />
          <UnlockBadge label="Real-Time Alerts" unlocked={unlocks.alerts} confidence="Partial" />
        </div>
      </div>

      {score < 100 && nextBestActions.length > 0 && (
        <div className="pt-3 border-t border-white/[0.04]">
          <p className="text-[9px] font-bold text-slate-600 uppercase tracking-widest mb-2">Next Best Action</p>
          <ul className="space-y-2">
            {nextBestActions.slice(0, 2).map((item, idx) => (
              <li key={idx} className="flex flex-col gap-1">
                <div className="flex items-start gap-1.5 text-[10px] text-slate-400">
                  <span className="text-indigo-400 mt-0.5">•</span>
                  {item.action}
                </div>
                <span className="text-[9px] font-bold text-emerald-400 ml-3 bg-emerald-500/10 px-1.5 py-0.5 rounded-lg self-start border border-emerald-500/10">
                  {item.impact}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ScoreRow({ label, percent, isComplete, isPartial, warning }: { label: string; percent: number; isComplete: boolean; isPartial?: boolean; warning?: string }) {
  return (
    <div className="flex items-center justify-between text-[10px]">
      <span className="text-slate-400">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-slate-600 font-mono text-[9px]">{percent}%</span>
        {isComplete ? (
          <span className="text-emerald-400 font-bold">✓</span>
        ) : isPartial ? (
          <div className="flex items-center gap-1">
            <span className="text-amber-400 font-bold text-[9px]">⚠ Partial</span>
            {warning && <div title={warning} className="cursor-help"><Info size={10} className="text-amber-400/60" /></div>}
          </div>
        ) : (
          <span className="text-slate-700">○</span>
        )}
      </div>
    </div>
  );
}

function UnlockBadge({ label, unlocked, confidence }: { label: string; unlocked: boolean; confidence: string }) {
  return (
    <div className="text-center cursor-default">
      <div className={`mx-auto w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold mb-1 border ${
        unlocked ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' : 'bg-white/[0.02] text-slate-700 border-white/[0.04]'
      }`}>
        {unlocked ? '✓' : '🔒'}
      </div>
      <p className="text-[9px] text-slate-500 font-medium leading-tight">{label}</p>
      {unlocked && <p className="text-[7px] text-slate-600 mt-0.5">{confidence}</p>}
    </div>
  );
}
