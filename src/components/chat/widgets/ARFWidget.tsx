import React from 'react';
import { ShieldAlert, ShieldCheck, Shield, CheckCircle2, AlertTriangle, Info, BookOpen, Activity } from 'lucide-react';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function ARFWidget({ arf }: { arf: any }) {
  if (arf.error) {
    return <div className="text-red-500 text-sm">Error: {arf.error}</div>;
  }

  const badgeConfig = {
    HIGH: { color: 'text-emerald-700 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30', border: 'border-emerald-200 dark:border-emerald-800', icon: <ShieldCheck className="w-4 h-4" /> },
    MED: { color: 'text-amber-700 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/30', border: 'border-amber-200 dark:border-amber-800', icon: <Shield className="w-4 h-4" /> },
    LOW: { color: 'text-rose-700 dark:text-rose-400', bg: 'bg-rose-50 dark:bg-rose-900/30', border: 'border-rose-200 dark:border-rose-800', icon: <ShieldAlert className="w-4 h-4" /> }
  };

  const badge = badgeConfig[arf.confidence_badge as keyof typeof badgeConfig] || badgeConfig['LOW'];

  return (
    <div className="flex flex-col gap-4 text-sm w-[450px] max-w-full">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h4 className="text-lg font-bold text-slate-900 dark:text-white leading-tight mt-1">
          {arf.headline || "Analysis Report"}
        </h4>
        <div className="flex flex-col sm:flex-row gap-2 mt-1">
          {arf.suitability_score && (
            <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border w-fit bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800`}>
              <CheckCircle2 className="w-4 h-4" />
              <span>Suitability: {arf.suitability_score}</span>
            </div>
          )}
          {arf.confidence_badge && (
            <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border w-fit ${badge.bg} ${badge.color} ${badge.border}`}>
              {badge.icon}
              <span>Confidence: {arf.confidence_badge}</span>
              {arf.confidence_reason && <span className="opacity-75 font-normal ml-1 hidden sm:inline">({arf.confidence_reason})</span>}
            </div>
          )}
        </div>
        {arf.confidence_reason && (
          <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 sm:hidden">
            Reason: {arf.confidence_reason}
          </div>
        )}
      </div>

      {/* Answer Block */}
      {(arf.direct_answer || arf.what_it_means) && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 shadow-sm">
          {arf.direct_answer && <p className="font-semibold text-slate-800 dark:text-slate-200 m-0 mb-2">{arf.direct_answer}</p>}
          {arf.what_it_means && <p className="text-slate-600 dark:text-slate-400 m-0 text-[13px] leading-relaxed">{arf.what_it_means}</p>}
        </div>
      )}

      {/* Evidence Cards */}
      {arf.reasoning_cards && arf.reasoning_cards.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5" /> Evidence & Findings
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {arf.reasoning_cards.map((card: any, i: number) => (
              <div key={i} className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 rounded-lg p-2.5 text-[13px]">
                <div className="font-medium text-slate-800 dark:text-slate-200 mb-1">{card.claim}</div>
                <div className="text-slate-600 dark:text-slate-400 text-xs leading-relaxed">{card.evidence}</div>
                {card.uncertainty && card.uncertainty !== "LOW" && card.uncertainty !== "NONE" && (
                  <div className="mt-1.5 text-[10px] text-amber-600 dark:text-amber-500 bg-amber-50 dark:bg-amber-900/20 px-1.5 py-0.5 rounded w-fit">
                    Uncertainty: {card.uncertainty}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {arf.recommendations && arf.recommendations.length > 0 && (
        <div className="flex flex-col gap-2 mt-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            <CheckCircle2 className="w-3.5 h-3.5" /> Recommended Actions
          </div>
          <div className="flex flex-col gap-2">
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {arf.recommendations.map((rec: any, i: number) => (
              <div key={i} className={`border rounded-lg p-3 ${rec.is_allowed ? 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800' : 'bg-rose-50 dark:bg-rose-900/10 border-rose-200 dark:border-rose-900/30'}`}>
                <div className="flex items-start gap-2">
                  <div className="mt-0.5">
                    {rec.is_allowed ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <AlertTriangle className="w-4 h-4 text-rose-500" />}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-slate-900 dark:text-slate-100">{rec.type}: {rec.title}</div>
                    {!rec.is_allowed && rec.blocked_reasons && (
                        <div className="text-rose-600 dark:text-rose-400 text-xs mt-1 font-medium">Blocked: {rec.blocked_reasons.join(", ")}</div>
                    )}
                    {rec.why_it_matters && (
                      <div className="text-slate-600 dark:text-slate-400 text-xs mt-1.5 leading-relaxed">{rec.why_it_matters}</div>
                    )}
                    {rec.how_to_do_it_steps && rec.how_to_do_it_steps.length > 0 && (
                      <ul className="mt-2 pl-4 list-disc text-xs text-slate-600 dark:text-slate-400 space-y-1">
                        {rec.how_to_do_it_steps.map((step: string, j: number) => (
                          <li key={j}>{step}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Learning & Limitations */}
      {(arf.learning || (arf.limitations && arf.limitations.length > 0)) && (
        <div className="mt-2 border-t border-slate-200 dark:border-slate-800 pt-3 flex flex-col gap-3">
            {arf.learning && (
                <div className="flex items-start gap-2.5 bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 p-2.5 rounded-lg text-xs">
                    <BookOpen className="w-4 h-4 mt-0.5 shrink-0" />
                    <div>
                        <span className="font-semibold block mb-0.5">AgriBrain Lesson ({arf.learning.level})</span>
                        {arf.learning.micro_lesson}
                    </div>
                </div>
            )}
            {arf.limitations && arf.limitations.length > 0 && (
                <div className="flex items-start gap-2.5 text-slate-500 dark:text-slate-400 text-xs px-1">
                    <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    <div>
                        <span className="font-semibold text-slate-600 dark:text-slate-300">System Limitations:</span> {arf.limitations.join("; ")}
                    </div>
                </div>
            )}
        </div>
      )}
    </div>
  );
}
