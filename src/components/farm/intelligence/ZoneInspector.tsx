"use client";

import { useMemo, useState } from "react";
import type { ZoneData } from "@/hooks/useLayer10";

interface ZoneInspectorProps {
  zone: ZoneData | null;
  groundingClass?: string;
  onClose: () => void;
}

function getConfidenceLevel(confidence: number): { level: "high" | "medium" | "low", label: string } {
  if (confidence >= 0.7) return { level: "high", label: "High Confidence" };
  if (confidence >= 0.4) return { level: "medium", label: "Medium Confidence" };
  return { level: "low", label: "Low Confidence / Verify" };
}

/** Generate dynamic cause list from zone data */
function generateCauseReasons(zone: ZoneData): string[] {
  const reasons: string[] = [];
  if (zone.top_drivers && zone.top_drivers.length > 0) {
    const primaryDriver = zone.top_drivers[0].replace(/_/g, " ").toLowerCase();
    reasons.push(`Primary driver: ${primaryDriver} signal detected`);
  }
  if (zone.severity > 0.6) {
    reasons.push("Severity exceeds 60% — significantly diverges from field median");
  } else if (zone.severity > 0.3) {
    reasons.push("Moderate departure from field baseline");
  }
  if (zone.evidence_age_days != null) {
    if (zone.evidence_age_days <= 3) {
      reasons.push("Recent observation (within 3 days) — high temporal relevance");
    } else if (zone.evidence_age_days > 14) {
      reasons.push(`Evidence is ${zone.evidence_age_days} days old — verify current state`);
    }
  }
  if (zone.confidence < 0.4) {
    reasons.push("Low confidence — boundary may be approximate");
  } else if (zone.confidence < 0.7) {
    reasons.push("Moderate confidence — could refine with additional sources");
  }
  if (zone.area_fraction > 0.3) {
    reasons.push(`Covers ${Math.round(zone.area_fraction * 100)}% of field — large-scale pattern`);
  } else if (zone.area_fraction < 0.05) {
    reasons.push("Small localized anomaly — may indicate point-source issue");
  }
  if (zone.is_inferred) {
    reasons.push("Zone is model-inferred, not directly observed by sensor");
  }
  if (zone.source_dominance && zone.source_dominance !== "Mixed") {
    reasons.push(`Dominated by ${zone.source_dominance.replace(/_/g, " ")} source`);
  }
  return reasons.length > 0 ? reasons : ["Zone identified by multi-factor spatial analysis"];
}

function WhyThisZone({ zone }: { zone: ZoneData }) {
  const [expanded, setExpanded] = useState(false);
  const reasons = useMemo(() => generateCauseReasons(zone), [zone]);
  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors font-medium group"
        id="why-this-zone-toggle"
      >
        <svg className={`w-3 h-3 transition-transform duration-150 ${expanded ? "rotate-90" : ""}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" /></svg>
        <span>Why this zone?</span>
      </button>
      {expanded && (
        <div className="mt-2 bg-indigo-950/20 border border-indigo-500/15 rounded-lg p-3 zone-why-enter">
          <ul className="space-y-1.5">
            {reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[11px] text-slate-300">
                <span className="text-indigo-400 mt-0.5 text-[10px] flex-shrink-0">●</span>
                <span className="leading-snug">{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ZoneInspector({
  zone,
  onClose,
}: ZoneInspectorProps) {
  if (!zone) return null;

  const confidenceLevel = getConfidenceLevel(zone.confidence);
  const severityPct = Math.round((zone.severity || 0) * 100);
  
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const summarySentence = useMemo(() => {
    const typeLabel = zone.zone_type?.replace(/_/g, " ").toLowerCase() || "anomalous";
    const driverList = zone.top_drivers?.slice(0, 2).map(d => d.replace(/_/g, " ").toLowerCase()).join(" and ");
    const driverStr = driverList ? `likely driven by ${driverList}` : "with complex causal factors";
    const confLabel = confidenceLevel.label.toLowerCase();
    
    // Attempt to synthesize the sentence the user asked for
    return `This zone is a ${severityPct > 60 ? 'severe' : 'moderate'} ${typeLabel} area, ${driverStr}, with ${confLabel}.`;
  }, [zone, confidenceLevel, severityPct]);

  return (
    <div className={`zone-inspector open intelligence-panel p-4 flex flex-col gap-4 overflow-y-auto max-h-[85vh]`} id="zone-inspector">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-700/50">
        <div>
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            {zone.label || zone.zone_id}
            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-sm uppercase tracking-wider ${zone.is_inferred ? 'bg-indigo-500/20 text-indigo-300' : 'bg-emerald-500/20 text-emerald-300'}`}>
              {zone.is_inferred ? 'Inferred' : 'Observed'}
            </span>
          </h3>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors"
          id="zone-inspector-close"
        >
          ✕
        </button>
      </div>

      {/* SECTION 1: Summary */}
      <div className="flex flex-col gap-2">
        <h4 className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">1. Summary</h4>
        <div className="text-sm text-slate-300 italic px-2 border-l-2 border-indigo-500/50 leading-snug mb-2">
          &quot;{summarySentence}&quot;
        </div>
        
        <div className="grid grid-cols-2 gap-2 mt-1">
          <div className="bg-slate-800/30 rounded-lg p-2.5">
            <span className="text-[10px] text-slate-400 block mb-0.5">Classification</span>
            <span className="text-xs font-bold text-indigo-400 leading-tight block">{zone.zone_type?.replace(/_/g, " ")}</span>
          </div>
          <div className="bg-slate-800/30 rounded-lg p-2.5">
            <span className="text-[10px] text-slate-400 block mb-0.5">Field Share</span>
            <span className="text-xs font-bold text-slate-200 leading-tight block">{Math.round(zone.area_fraction * 100)}%</span>
          </div>
        </div>

        <div className="bg-slate-800/30 rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-400">Severity</span>
            <span className="text-xs font-bold text-slate-300">{severityPct}%</span>
          </div>
          <div className="severity-bar">
            <div
              className="severity-marker"
              style={{
                left: `${severityPct}%`,
                backgroundColor: severityPct > 70 ? "#ef4444" : severityPct > 40 ? "#eab308" : "#22c55e",
              }}
            />
          </div>
        </div>
      </div>

      {/* SECTION 2: How AgriBrain calculated this */}
      <div className="flex flex-col gap-2 mt-2">
        <h4 className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">2. How AgriBrain calculated this</h4>
        <div className="bg-slate-800/30 rounded-lg p-3 border border-slate-700/50 text-xs text-slate-300">
          <ul className="space-y-1.5">
            <li><strong className="text-slate-400 font-semibold">Primary surface:</strong> {String(zone.calculation_trace?.surface ?? "Vegetation surface").replace(/_/g, " ")}</li>
            <li><strong className="text-slate-400 font-semibold">Sources used:</strong> {Array.isArray(zone.calculation_trace?.sources) ? zone.calculation_trace?.sources.join(", ") : "Multi-spectral imaging"}</li>
            <li><strong className="text-slate-400 font-semibold">Time window:</strong> {String(zone.calculation_trace?.time_window_days ?? 14)} days</li>
            <li><strong className="text-slate-400 font-semibold">Normalization:</strong> {String(zone.calculation_trace?.normalization ?? "P02-P98 per-field stretch").replace(/_/g, " ")}</li>
            <li><strong className="text-slate-400 font-semibold">Confidence basis:</strong> {String(zone.calculation_trace?.confidence_basis ?? "Layer 0 Reliability Surface Tracker").replace(/_/g, " ")}</li>
            <li><strong className="text-slate-400 font-semibold">Zoning method:</strong> {String(zone.calculation_trace?.zone_method ?? "Severity-area ranked sorting").replace(/_/g, " ")}</li>
          </ul>
        </div>
      </div>

      {/* SECTION 3: Evidence and trust */}
      <div className="flex flex-col gap-2 mt-2">
        <h4 className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">3. Evidence and trust</h4>
        <div className="bg-slate-800/40 rounded-lg p-3 text-xs text-slate-300 space-y-2">
          <p><strong className="text-slate-400 font-semibold">Type:</strong> {zone.is_inferred ? "Inferred (Modeled)" : "Observed (Sensor)"}</p>
          <p><strong className="text-slate-400 font-semibold">Dominant source:</strong> {zone.source_dominance ?? "Multi-source fusion"}</p>
          <p><strong className="text-slate-400 font-semibold">Evidence age:</strong> {zone.evidence_age_days != null ? (zone.evidence_age_days === 0 ? "Latest cycle (Today)" : `${zone.evidence_age_days} days`) : "Latest cycle"}</p>
          <p><strong className="text-slate-400 font-semibold">Trust note:</strong> <span className="italic text-slate-400">&quot;{zone.trust_note ?? "Strong spatio-temporal coherence"}&quot;</span></p>
          
          {zone.top_drivers && zone.top_drivers.length > 0 && (
            <div className="mt-3 pt-2 border-t border-slate-700/50">
              <strong className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">Ranked Drivers</strong>
              <ol className="list-decimal pl-4 space-y-1">
                {zone.top_drivers.map((driver, idx) => (
                  <li key={idx} className="text-amber-400/90 font-medium">
                    {driver.replace(/_/g, " ")}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </div>

      {/* Why this zone? — expandable cause list */}
      <WhyThisZone zone={zone} />

      {/* SECTION 4: What this means */}
      <div className="flex flex-col gap-2 mt-2">
        <h4 className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">4. What this means</h4>
        <div className="bg-slate-800/30 rounded-lg p-3 border border-slate-700/30 text-xs text-slate-300 space-y-2">
          <p>This zone is underperforming compared to the rest of the field and may reduce relative productivity if the trend continues.</p>
          <p><strong className="text-amber-500/80 font-semibold">Inspect now:</strong> Look for localized stress signs, irrigation uniformity issues, or historical compaction near these coordinates.</p>
        </div>
      </div>

      {/* SECTION 5: Recommended action */}
      <div className="flex flex-col gap-2 mt-2 mb-2">
        <h4 className="text-[10px] font-semibold text-emerald-600 uppercase tracking-widest">5. Recommended action</h4>
        <div className="bg-emerald-900/10 rounded-lg p-3 border border-emerald-800/30 text-xs text-emerald-400/90">
          {zone.linked_actions && zone.linked_actions.length > 0 ? (
            <ul className="space-y-2">
               {zone.linked_actions.map((action, idx) => (
                 <li key={idx} className="flex items-start gap-2 font-bold">
                   <span className="text-emerald-500 mt-0.5">↳</span>
                   <span className="leading-tight">{action.replace(/_/g, " ")}</span>
                 </li>
               ))}
            </ul>
          ) : (
            <p className="font-medium text-emerald-500/80 italic">No direct intervention recommended yet. Continue monitoring for worsening trends during the next satellite pass.</p>
          )}
        </div>
      </div>
      {/* Back link — clear escape from inspection mode */}
      <div className="pt-3 mt-2 border-t border-slate-700/30">
        <button
          onClick={onClose}
          className="flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-200 transition-colors font-medium group w-full justify-center"
          id="zone-inspector-back"
        >
          <svg className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7" /></svg>
          <span>Back to field view</span>
        </button>
      </div>

    </div>
  );
}
