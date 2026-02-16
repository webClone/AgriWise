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
    // New: for visual ground truth recency check
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
  
  if (!checks.activeSensors) {
      nextBestActions.push({ 
          action: "Activate soil moisture sensor", 
          impact: "+12% irrigation precision" 
      });
  }
  
  if (!checks.soil) {
      nextBestActions.push({ 
          action: "Import recent soil analysis", 
          impact: "+15% nutrient model accuracy" 
      });
  }
  
  if (!checks.crop) {
      nextBestActions.push({ 
          action: "Log current crop variety", 
          impact: "Enables phenology tracking" 
      });
  }
  
  if (!checks.geometry) {
      nextBestActions.push({ 
          action: "Define plot geometry", 
          impact: "Required for satellite data" 
      });
  }

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm min-w-[320px] flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-2">
          <div>
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                Field Intelligence Readiness
                <div title="Higher readiness improves AgriBrain prediction accuracy.">
                    <Info size={10} className="text-slate-300 cursor-help" />
                </div>
              </h4>
          </div>
          <div className="flex flex-col items-end gap-0.5">
            <div className="flex items-center gap-1.5">
                <span className="text-[9px] font-medium text-slate-400 uppercase tracking-wider">Model Trust</span>
                <span className={`text-[9px] font-bold ${score >= 80 ? 'text-emerald-500' : score >= 50 ? 'text-amber-500' : 'text-slate-400'}`}>
                    {score >= 80 ? 'High' : score >= 50 ? 'Moderate' : 'Low'}
                </span>
            </div>
            <div className="flex items-center gap-1.5">
                <span className="text-[9px] font-medium text-slate-400 uppercase tracking-wider">Data Coverage</span>
                <span className="text-[9px] font-bold text-indigo-500">
                    {checks.activeSensors ? 'Live Monitoring' : checks.sensors ? 'Partial Live' : 'Satellite Only'}
                </span>
            </div>
          </div>
        </div>
        
        <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full mb-1 overflow-hidden relative group">
          <div 
              className={`h-full transition-all duration-1000 ${score >= 80 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : 'bg-slate-400'}`} 
              style={{ width: `${score}%` }} 
          />
        </div>
        
        <div className="flex justify-between items-start mb-4">
            <p className="text-[9px] text-slate-400 h-3">
                {score >= 80 ? "Data supports high-confidence satellite analysis." : "Add more data to enable advanced models."}
            </p>
            <button 
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-[9px] text-indigo-500 font-medium hover:text-indigo-600 flex items-center gap-0.5"
            >
                {isExpanded ? "Hide breakdown" : "View breakdown"}
                {isExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </button>
        </div>

        {isExpanded && (
            <div className="mb-4 bg-slate-50 dark:bg-slate-950 rounded-lg p-3 space-y-2 border border-slate-100 dark:border-slate-800 animate-in slide-in-from-top-2 fade-in duration-300">
                <ScoreRow label="Geometry" percent={30} isComplete={checks.geometry} />
                <ScoreRow label="Crop & Mgmt" percent={30} isComplete={checks.crop} />
                <ScoreRow label="Soil Data" percent={20} isComplete={checks.soil} />
                <ScoreRow 
                    label="Live Monitoring" 
                    percent={20} 
                    isComplete={checks.activeSensors} 
                    isPartial={checks.sensors && !checks.activeSensors}
                    warning={!checks.activeSensors ? "Satellite + Weather Only" : undefined}
                />
            </div>
        )}

        {/* Unlock Indicators */}
        <div className="grid grid-cols-3 gap-2 mb-4 border-t border-slate-100 dark:border-slate-800 pt-4">
           <UnlockBadge 
                label="Yield Prediction" 
                unlocked={unlocks.yield} 
                confidence="High Confidence" 
                color="emerald" 
            />
           <UnlockBadge 
                label="Nutrient Engine" 
                unlocked={checks.soil} 
                confidence="Medium Confidence" 
                color="indigo" 
            />
           <UnlockBadge 
                label="Real-Time Alerts" 
                unlocked={unlocks.alerts} 
                confidence="Partial Coverage" 
                color="amber" 
            />
        </div>
      </div>

      {score < 100 && nextBestActions.length > 0 && (
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800">
            <p className="text-[9px] font-bold text-slate-400 uppercase tracking-tight mb-2">Next Best Action:</p>
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">To reach 100%:</p>
            <ul className="space-y-1.5">
              {nextBestActions.slice(0, 2).map((item, idx) => (
                <li key={idx} className="flex flex-col gap-0.5">
                    <div className="flex items-start gap-1.5 text-[10px] text-slate-600 dark:text-slate-400">
                        <span className="text-indigo-500 mt-0.5">•</span>
                        {item.action}
                    </div>
                    <span className="text-[9px] font-bold text-emerald-600 dark:text-emerald-400 ml-3 bg-emerald-50 dark:bg-emerald-900/30 px-1.5 py-0.5 rounded self-start">
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

interface ScoreRowProps {
    label: string;
    percent: number;
    isComplete: boolean;
    isPartial?: boolean;
    warning?: string;
}

function ScoreRow({ label, percent, isComplete, isPartial, warning }: ScoreRowProps) {
    return (
        <div className="flex items-center justify-between text-[10px]">
            <span className="text-slate-600 dark:text-slate-400">{label}</span>
            <div className="flex items-center gap-2">
                <span className="text-slate-400 font-mono text-[9px]">{percent}%</span>
                {isComplete ? (
                    <span className="text-emerald-500 font-bold">✓</span>
                ) : isPartial ? (
                    <div className="flex items-center gap-1">
                        <span className="text-amber-500 font-bold">⚠ Partial</span>
                        {warning && (
                             <div title={warning} className="cursor-help">
                                <Info size={10} className="text-amber-400" />
                            </div>
                        )}
                    </div>
                ) : (
                    <span className="text-slate-300">○</span>
                )}
            </div>
        </div>
    )
}

interface UnlockBadgeProps {
    label: string;
    unlocked: boolean;
    confidence: string;
    color: 'emerald' | 'indigo' | 'amber' | 'slate';
}

function UnlockBadge({ label, unlocked, confidence, color }: UnlockBadgeProps) {
    const colors: Record<string, string> = {
        emerald: "bg-emerald-100 text-emerald-600",
        indigo: "bg-indigo-100 text-indigo-600",
        amber: "bg-amber-100 text-amber-600",
        slate: "bg-slate-100 text-slate-300"
    };
    
    return (
        <div className="text-center group relative cursor-help">
            <div className={`mx-auto w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold mb-1 ${unlocked ? colors[color] : colors.slate}`}>
                {unlocked ? '✓' : '🔒'}
            </div>
            <p className="text-[9px] text-slate-500 font-medium leading-tight">{label}</p> 
            {unlocked && (
                <p className="text-[8px] text-slate-400 mt-0.5 font-medium">{confidence}</p>
            )}
       </div>
    )
}
