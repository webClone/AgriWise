"use client";

import { useMemo } from "react";
import { Brain } from "lucide-react";
import type { ZoneData } from "@/hooks/useLayer10";
import {
  generateZoneCondition,
  humanizeZoneName,
  humanizeConfidence,
  humanizeAction,
  humanizeDriver,
} from "./fieldInsightAdapter";

interface ZoneSheetProps {
  zone: ZoneData | null;
  allZones: ZoneData[];
  onClose: () => void;
  onAskAgriBrain?: () => void;
}

export default function ZoneSheet({
  zone,
  allZones,
  onClose,
  onAskAgriBrain,
}: ZoneSheetProps) {

  // Rank all zones for the zone list
  const rankedZones = useMemo(() => {
    return [...allZones]
      .sort((a, b) => (b.severity ?? 0) * (b.area_fraction ?? 0) - (a.severity ?? 0) * (a.area_fraction ?? 0))
      .slice(0, 6);
  }, [allZones]);

  if (!zone) return null;

  const severityPct = Math.round((zone.severity ?? 0) * 100);
  const conditionSentence = generateZoneCondition(zone);
  const zoneName = humanizeZoneName(zone, rankedZones.findIndex(z => z.zone_id === zone.zone_id));
  const confidenceLabel = humanizeConfidence(zone.confidence);

  const severityWord = severityPct > 70 ? "High" : severityPct > 40 ? "Moderate" : "Low";
  const severityColor =
    severityPct > 70 ? "var(--aw-severity-high)" :
    severityPct > 40 ? "var(--aw-severity-mid)" :
    "var(--aw-severity-low)";

  return (
    <div className="fixed right-6 top-[100px] bottom-6 w-[380px] bg-[#0B1015]/85 backdrop-blur-2xl border border-white/10 rounded-[28px] p-8 flex flex-col z-50 shadow-2xl overflow-y-auto" id="zone-sheet">
        {/* Title row */}
        <div className="flex justify-between items-start mb-6">
            <h2 className="text-3xl font-light text-white leading-tight pr-4">{zoneName}</h2>
            <button 
                className="p-2 bg-white/5 hover:bg-white/10 rounded-full text-slate-400 hover:text-white transition shrink-0" 
                onClick={onClose}
                aria-label="Close"
            >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
            </button>
        </div>

        {/* Confidence/meta */}
        <div className="flex items-center gap-3 mb-8">
            <span className="text-xs font-bold tracking-[0.15em] uppercase" style={{ color: severityColor }}>
               {severityWord}
            </span>
            <span className="w-1 h-1 rounded-full bg-slate-700" />
            <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
               {confidenceLabel}
            </span>
        </div>

        {/* Advisory Statement */}
        <div className="flex flex-col gap-6 mt-2">
            <p className="text-[17px] text-slate-300 font-light leading-relaxed">
                {conditionSentence}
                <span className="text-slate-500 ml-2">
                    {zone.is_inferred ? "Pattern inferred from" : "Observed via"} latest satellite imagery over {Math.round(zone.area_fraction * 100)}% of the field.
                </span>
            </p>

            {/* Lightweight why-trace — universal scaffolding */}
            <div className="flex flex-col gap-2 py-4 px-5 bg-[#0B1015]/40 rounded-2xl border border-white/5 mt-4">
                <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Evidence Trace</span>
                {(zone.top_drivers && zone.top_drivers.length > 0) ? (
                    <ul className="flex flex-col gap-1.5">
                        {zone.top_drivers.slice(0, 3).map((d, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-slate-400">
                                <span className="w-1 h-1 rounded-full bg-slate-600 shrink-0 mt-2" />
                                <span className="leading-relaxed">{humanizeDriver(d)}</span>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-sm text-slate-400 italic">Assessment relies primarily on modeled satellite signatures due to limited local high-weight telemetry.</p>
                )}
                {zone.trust_note && (
                    <p className="text-xs text-slate-500 italic mt-2 border-t border-white/5 pt-2">&ldquo;{zone.trust_note}&rdquo;</p>
                )}
            </div>
            
            {/* Recommendation */}
            <p className="text-indigo-300 font-medium text-[16px] leading-relaxed p-5 bg-indigo-500/5 rounded-2xl border border-indigo-500/10">
                 {zone.linked_actions && zone.linked_actions.length > 0 
                    ? humanizeAction(zone.linked_actions[0]) 
                    : "Observation aligns with expected crop progression. No immediate intervention required."}
            </p>
        </div>

        {/* Decide state entry — Ask AgriBrain */}
        {onAskAgriBrain && (
            <button
                className="mt-auto flex items-center justify-center gap-2.5 w-full py-4 rounded-2xl bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 text-indigo-300 hover:text-indigo-200 text-[15px] font-semibold transition-all shadow-lg group"
                onClick={onAskAgriBrain}
                id="zone-sheet-ask-agribrain"
            >
                <Brain size={18} strokeWidth={1.5} className="group-hover:scale-110 transition-transform" />
                Ask AgriBrain to Decide
            </button>
        )}
    </div>
  );
}
