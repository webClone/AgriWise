"use client";

/**
 * ZoneDetailStrip V2 — Expanded diagnostic intelligence panel.
 * 
 * Shows: WHY (root cause) → EVIDENCE (data sources + stats) → ACTION (multi-step protocol)
 * Real zone data integration: surface_stats, confidence_reasons, calculation_trace, linked_actions.
 */

import { useMemo, useState } from "react";
import { Brain, X, MapPin, Shield, TrendingDown, Zap, ChevronDown, ChevronUp, Layers, Clock, AlertTriangle, CheckCircle } from "lucide-react";
import type { ZoneData } from "@/hooks/useLayer10";
import { humanizeZoneName, humanizeConfidence, humanizeDriver } from "./fieldInsightAdapter";

// ── Rich intelligence lookup ──────────────────────────────────────────────
interface StripIntel {
  why: string;
  mechanism: string;
  steps: string[];
  urgency: "immediate" | "48h" | "weekly" | "monitor";
  expertNote: string;
}

const STRIP_INTEL: Record<string, StripIntel> = {
  LOW_VIGOR: {
    why: "Photosynthetic capacity reduced — canopy reflectance shows chlorophyll stress below field baseline.",
    mechanism: "NDVI deviation from field mean exceeds 1σ. Common causes: water deficit limiting stomatal conductance, N depletion during rapid growth, or root-zone compaction restricting uptake.",
    steps: [
      "Scout within 48h — check leaf color (pale yellow = N deficit, curling = water)",
      "Dig 15cm to assess soil moisture and root health",
      "Compare with adjacent healthy zone for reference",
      "If N deficit confirmed by petiole test: consult agronomist for certified variable-rate prescription",
    ],
    urgency: "48h",
    expertNote: "Cross-reference with SAR backscatter for soil moisture confirmation. If NDVI deviation > 0.15 and VPD > 2.5 kPa, prioritize irrigation over fertilization.",
  },
  WATER_STRESS: {
    why: "Soil moisture deficit exceeds crop extraction capacity. Evapotranspiration demand outpaces root water supply.",
    mechanism: "SAR backscatter + NDVI temporal decline indicate progressive soil drying. Water balance model shows cumulative deficit over past 7 days.",
    steps: [
      "Verify irrigation delivery — check drip lines, emitter flow rates, pressure",
      "Measure soil moisture at 15cm and 30cm depth if probe available",
      "Prioritize irrigation if crop is at reproductive stage (flowering/grain fill)",
      "If deficit confirmed by soil probe: review water budget and schedule verified irrigation cycle",
    ],
    urgency: "immediate",
    expertNote: "VPD-driven demand vs. SAR-derived supply mismatch. If ET₀ > 6mm/day and SAR VV declining > 0.5dB/week, stomatal closure is likely. Nighttime irrigation preferred to minimize evaporative loss.",
  },
  NUTRIENT_RISK: {
    why: "Spectral signatures indicate sub-optimal nutrient availability — growth rate decoupled from expected phenological trajectory.",
    mechanism: "NDVI growth velocity < expected for current GDD accumulation. Red-edge position shift suggests chlorophyll-a reduction consistent with N or Fe limitation.",
    steps: [
      "Collect tissue samples — petiole NO₃⁻ test for nitrogen status",
      "Soil sample at 0-30cm for available N, P, K, and pH",
      "If nutrient limitation confirmed by lab analysis: obtain certified nutrient prescription",
      "Re-assess in 10 days via satellite — expect NDVI recovery within 2 weeks",
    ],
    urgency: "48h",
    expertNote: "Differentiate N from Fe deficiency: N shows older-leaf yellowing first (basipetal), Fe shows interveinal chlorosis on youngest leaves. pH > 7.5 increases Fe lock-up risk.",
  },
  DISEASE_RISK: {
    why: "Environmental conditions favor pathogen development. Spectral anomaly pattern consistent with early biotic damage.",
    mechanism: "Leaf wetness hours > threshold + temperature in pathogen growth range. NDVI micro-texture shows patchy decline inconsistent with abiotic stress.",
    steps: [
      "Scout immediately — look for lesions, spots, or mycelium on leaf surfaces",
      "Photograph affected leaves for pathologist consultation",
      "If pathogen confirmed: consult crop protection advisor for approved treatment plan",
      "Increase monitoring frequency to every 3 days during high-risk window",
    ],
    urgency: "immediate",
    expertNote: "Patchy NDVI decline with high leaf-wetness hours suggests foliar fungal pathogen. If spread pattern is wind-aligned, suspect airborne spores. Prophylactic treatment of adjacent zones may be warranted.",
  },
  HIGH_VIGOR: {
    why: "Vegetation performance exceeds field average — indicates favorable micro-conditions or over-fertilization.",
    mechanism: "NDVI consistently > field P90. High vigor may indicate optimal soil/water conditions, or excess N leading to vegetative over-growth at expense of reproductive yield.",
    steps: [
      "Monitor for lodging risk if grain crop (excess stem elongation)",
      "Check for pest attraction — lush canopy attracts insects",
      "Consider reducing N input in this zone next application cycle",
      "Use as benchmark — replicate conditions in underperforming zones",
    ],
    urgency: "monitor",
    expertNote: "High vigor ≠ high yield. Excessive vegetative growth can reduce harvest index. For cereals, check stem diameter and internode length. For tree crops, excessive vigor increases alternate bearing risk.",
  },
  YIELD_GAP: {
    why: "Cumulative season performance significantly below field potential. Multiple stress episodes have compounded yield loss.",
    mechanism: "Integrated NDVI-days (biomass proxy) < field P25 for current growth stage. Historical comparison shows persistent underperformance in this zone.",
    steps: [
      "This season: focus on preventing further degradation — maintain irrigation",
      "Post-harvest: comprehensive soil test (compaction, drainage, nutrients)",
      "Check for drainage issues — waterlogging early-season can cause lasting root damage",
      "Plan remediation: deep tillage, cover crop, or amendment based on soil analysis",
    ],
    urgency: "weekly",
    expertNote: "Persistent yield gaps often indicate structural soil issues (compaction, poor drainage, salinity) rather than seasonal management failures. Multi-year NDVI overlay can distinguish chronic from acute zones.",
  },
  BLOCKED_ZONE: {
    why: "Zone access or intervention currently restricted — monitoring status only.",
    mechanism: "Zone flagged as operationally constrained. May be due to equipment access limitations, regulatory buffer, or pending assessment.",
    steps: [
      "Verify block reason — access, regulation, or assessment pending",
      "Continue remote monitoring via satellite at standard frequency",
      "If access restored, schedule priority scouting within 48h",
      "Document any visible changes for comparison when access available",
    ],
    urgency: "monitor",
    expertNote: "Blocked zones near water bodies may have regulatory buffer requirements. Check local agricultural regulations before planning any intervention.",
  },
};

const URGENCY_META: Record<string, { label: string; color: string; icon: typeof AlertTriangle }> = {
  immediate: { label: "Act Now", color: "#f87171", icon: AlertTriangle },
  "48h": { label: "Within 48h", color: "#fbbf24", icon: Clock },
  weekly: { label: "This Week", color: "#60a5fa", icon: Clock },
  monitor: { label: "Monitor", color: "#4ade80", icon: CheckCircle },
};

function _getStripIntel(zone: ZoneData): StripIntel {
  const exact = STRIP_INTEL[zone.zone_type];
  if (exact) return exact;
  for (const d of zone.top_drivers) {
    const u = d.toUpperCase();
    if (u.includes("WATER") || u.includes("DROUGHT")) return STRIP_INTEL.WATER_STRESS;
    if (u.includes("NUTRI") || u.includes("NITROGEN")) return STRIP_INTEL.NUTRIENT_RISK;
    if (u.includes("DISEASE") || u.includes("BIOTIC")) return STRIP_INTEL.DISEASE_RISK;
    if (u.includes("NDVI") || u.includes("VIGOR")) return STRIP_INTEL.LOW_VIGOR;
  }
  return STRIP_INTEL.LOW_VIGOR;
}

// Format surface stat values
function fmtStat(key: string, val: number): string {
  if (key.includes("NDVI")) return val.toFixed(3);
  if (key.includes("PROB") || key.includes("RISK")) return `${(val * 100).toFixed(0)}%`;
  return val.toFixed(2);
}

interface ZoneDetailStripProps {
  zone: ZoneData | null;
  allZones: ZoneData[];
  onClose: () => void;
  onAskAgriBrain?: (query?: string) => void;
}

export default function ZoneDetailStrip({ zone, allZones, onClose, onAskAgriBrain }: ZoneDetailStripProps) {
  const [expanded, setExpanded] = useState(false);

  const rankedZones = useMemo(() => {
    return [...allZones]
      .sort((a, b) => (b.severity ?? 0) * (b.area_fraction ?? 0) - (a.severity ?? 0) * (a.area_fraction ?? 0))
      .slice(0, 6);
  }, [allZones]);

  if (!zone) return null;

  const intel = _getStripIntel(zone);
  const urgMeta = URGENCY_META[intel.urgency] || URGENCY_META.monitor;
  const zoneName = humanizeZoneName(zone, rankedZones.findIndex(z => z.zone_id === zone.zone_id));
  const confidenceLabel = humanizeConfidence(zone.confidence);
  const severityPct = Math.round((zone.severity ?? 0) * 100);
  const severityColor = severityPct > 70 ? "#f87171" : severityPct > 40 ? "#fbbf24" : "#4ade80";
  const areaPct = Math.round((zone.area_fraction ?? 0) * 100);
  const drivers = (zone.top_drivers || []).slice(0, 4);

  // Extract real surface stats if available
  const surfaceStats = zone.surface_stats || {};
  const hasStats = Object.keys(surfaceStats).length > 0;

  // Confidence reasons from backend
  const confReasons = (zone.confidence_reasons || []).slice(0, 3);

  // Calculation trace (provenance)
  const trace = (zone as any).calculation_trace || {};
  const traceSources = trace.sources || [];

  const S = {
    statCard: { padding: "6px 12px", borderRadius: "8px", background: "rgba(0,0,0,0.25)", border: "1px solid rgba(71,85,105,0.1)", display: "flex" as const, flexDirection: "column" as const, alignItems: "center" as const, gap: "2px", minWidth: "52px" },
    label: { fontSize: "0.55rem", color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.05em" },
    val: { fontSize: "0.82rem", fontWeight: 700, color: "#f1f5f9" },
    tag: { fontSize: "0.6rem", fontWeight: 600, color: "#94a3b8", padding: "1px 6px", borderRadius: "4px", background: "rgba(71,85,105,0.15)", border: "1px solid rgba(71,85,105,0.1)" },
  };

  return (
    <div style={{ position: "absolute", bottom: "170px", left: "50%", transform: "translateX(-50%)", zIndex: 25, width: "100%", maxWidth: "920px", padding: "0 12px", boxSizing: "border-box", pointerEvents: "auto" }}>
      <div style={{ background: "rgba(15, 23, 42, 0.5)", backdropFilter: "blur(32px)", WebkitBackdropFilter: "blur(32px)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: "14px", overflow: "hidden", boxShadow: "0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)" }} id="zone-detail-strip">

        {/* ── Row 1: Header ────────────────────────────────────────── */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "10px 16px 8px", borderBottom: "1px solid rgba(71,85,105,0.12)" }}>
          {/* Severity badge */}
          <div style={{ display: "flex", alignItems: "center", gap: "5px", padding: "3px 10px", borderRadius: "20px", background: `${severityColor}12`, border: `1px solid ${severityColor}30` }}>
            <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: severityColor, boxShadow: `0 0 6px ${severityColor}60` }} />
            <span style={{ fontSize: "0.66rem", fontWeight: 700, color: severityColor, letterSpacing: "0.06em", textTransform: "uppercase" }}>{severityPct > 70 ? "Critical" : severityPct > 40 ? "Moderate" : "Low"}</span>
          </div>
          <span style={{ fontSize: "0.88rem", fontWeight: 700, color: "#f1f5f9" }}>{zoneName}</span>
          <span style={{ fontSize: "0.6rem", fontWeight: 600, color: "#94a3b8", padding: "2px 8px", borderRadius: "10px", background: "rgba(71,85,105,0.2)", border: "1px solid rgba(71,85,105,0.15)", textTransform: "uppercase", letterSpacing: "0.08em" }}>{confidenceLabel}</span>

          {/* Urgency badge */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px", padding: "2px 8px", borderRadius: "6px", background: `${urgMeta.color}15`, border: `1px solid ${urgMeta.color}30` }}>
            <urgMeta.icon size={10} color={urgMeta.color} />
            <span style={{ fontSize: "0.6rem", fontWeight: 700, color: urgMeta.color, textTransform: "uppercase", letterSpacing: "0.05em" }}>{urgMeta.label}</span>
          </div>

          <div style={{ flex: 1 }} />

          {/* Expand toggle */}
          <button onClick={() => setExpanded(!expanded)} style={{ width: "26px", height: "26px", borderRadius: "8px", background: "rgba(71,85,105,0.15)", border: "none", color: "#94a3b8", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }} title={expanded ? "Collapse" : "Expand"}>
            {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>

          {onAskAgriBrain && (
            <button
              onClick={() => onAskAgriBrain(`Zone "${zoneName}" is ${zone.zone_type.replace(/_/g,' ')} with ${severityPct}% severity affecting ${areaPct}% of field. Drivers: ${zone.top_drivers.join(', ')}. Surface stats: ${JSON.stringify(surfaceStats)}. Give me a detailed root-cause analysis and week-by-week action plan.`)}
              style={{ display: "flex", alignItems: "center", gap: "6px", padding: "5px 14px", borderRadius: "8px", background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)", color: "#a5b4fc", fontSize: "0.72rem", fontWeight: 600, cursor: "pointer" }}
              id="zone-strip-ask-agribrain"
            >
              <Brain size={13} />
              Deep Analysis
            </button>
          )}
          <button onClick={onClose} style={{ width: "26px", height: "26px", borderRadius: "8px", background: "rgba(71,85,105,0.15)", border: "none", color: "#94a3b8", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }} aria-label="Close"><X size={14} /></button>
        </div>

        {/* ── Row 2: Why + Stats + Action Steps ──────────────────── */}
        <div style={{ display: "flex", alignItems: "stretch", gap: "1px" }}>
          {/* Root Cause */}
          <div style={{ flex: "1 1 auto", padding: "10px 16px", display: "flex", flexDirection: "column", justifyContent: "center", minWidth: 0, gap: "4px" }}>
            <div style={{ fontSize: "0.6rem", color: "#a5b4fc", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>🔍 Root Cause</div>
            <p style={{ fontSize: "0.76rem", color: "#cbd5e1", lineHeight: 1.45, margin: 0 }}>{intel.why}</p>
          </div>

          {/* Stat cards */}
          <div style={{ display: "flex", gap: "2px", padding: "8px 4px", flexShrink: 0 }}>
            <div style={S.statCard}>
              <MapPin size={11} color="#94a3b8" />
              <span style={S.val}>{areaPct}%</span>
              <span style={S.label}>Area</span>
            </div>
            <div style={S.statCard}>
              <TrendingDown size={11} color={severityColor} />
              <span style={{ ...S.val, color: severityColor }}>{severityPct}</span>
              <span style={S.label}>Severity</span>
            </div>
            <div style={S.statCard}>
              <Shield size={11} color="#60a5fa" />
              <span style={S.val}>{Math.round((zone.confidence ?? 0) * 100)}%</span>
              <span style={S.label}>Conf</span>
            </div>
          </div>

          {/* Drivers + Primary action */}
          <div style={{ padding: "8px 16px 8px 12px", display: "flex", flexDirection: "column", justifyContent: "center", gap: "5px", borderLeft: "1px solid rgba(71,85,105,0.1)", minWidth: "220px", maxWidth: "300px", flexShrink: 0 }}>
            {drivers.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "3px" }}>
                {drivers.map((d, i) => (
                  <span key={i} style={S.tag}>{humanizeDriver(d)}</span>
                ))}
              </div>
            )}
            <div style={{ display: "flex", alignItems: "flex-start", gap: "5px", fontSize: "0.72rem", color: "#4ade80", fontWeight: 600, lineHeight: 1.35 }}>
              <Zap size={10} color="#4ade80" style={{ flexShrink: 0, marginTop: "2px" }} />
              <span>{intel.steps[0]}</span>
            </div>
          </div>
        </div>

        {/* ── Row 3: Expanded Panel ──────────────────────────────── */}
        {expanded && (
          <div style={{ borderTop: "1px solid rgba(71,85,105,0.12)", padding: "12px 16px", display: "flex", gap: "16px" }}>
            {/* Col 1: Mechanism + Evidence */}
            <div style={{ flex: "1 1 50%", display: "flex", flexDirection: "column", gap: "10px" }}>
              {/* Mechanism */}
              <div>
                <div style={{ fontSize: "0.58rem", color: "#818cf8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>⚙️ Mechanism</div>
                <p style={{ fontSize: "0.72rem", color: "#94a3b8", lineHeight: 1.5, margin: 0 }}>{intel.mechanism}</p>
              </div>

              {/* Surface Stats */}
              {hasStats && (
                <div>
                  <div style={{ fontSize: "0.58rem", color: "#818cf8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>📊 Zone Measurements</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                    {Object.entries(surfaceStats).map(([surfType, stats]) => (
                      Object.entries(stats as Record<string, number>).map(([k, v]) => (
                        <span key={`${surfType}-${k}`} style={{ fontSize: "0.62rem", padding: "2px 8px", borderRadius: "5px", background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)", color: "#c7d2fe", fontFamily: "monospace" }}>
                          {surfType.replace(/_/g,' ')}: {fmtStat(surfType, v)}
                        </span>
                      ))
                    ))}
                  </div>
                </div>
              )}

              {/* Data Sources */}
              {traceSources.length > 0 && (
                <div>
                  <div style={{ fontSize: "0.58rem", color: "#818cf8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>
                    <Layers size={9} style={{ display: "inline", marginRight: "4px" }} />Evidence Sources
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "3px" }}>
                    {traceSources.map((src: string, i: number) => (
                      <span key={i} style={{ fontSize: "0.6rem", padding: "2px 7px", borderRadius: "4px", background: "rgba(52,211,153,0.08)", border: "1px solid rgba(52,211,153,0.15)", color: "#6ee7b7" }}>{src}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Confidence Reasons */}
              {confReasons.length > 0 && (
                <div>
                  <div style={{ fontSize: "0.58rem", color: "#818cf8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>🛡️ Confidence Basis</div>
                  {confReasons.map((r, i) => (
                    <div key={i} style={{ fontSize: "0.66rem", color: "#94a3b8", lineHeight: 1.4, paddingLeft: "8px", borderLeft: "2px solid rgba(99,102,241,0.2)", marginBottom: "3px" }}>{r}</div>
                  ))}
                </div>
              )}
            </div>

            {/* Col 2: Action Protocol + Expert Note */}
            <div style={{ flex: "1 1 50%", display: "flex", flexDirection: "column", gap: "10px", borderLeft: "1px solid rgba(71,85,105,0.1)", paddingLeft: "16px" }}>
              {/* Step-by-step protocol */}
              <div>
                <div style={{ fontSize: "0.58rem", color: "#4ade80", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "6px" }}>⚡ Action Protocol</div>
                {intel.steps.map((step, i) => (
                  <div key={i} style={{ display: "flex", gap: "8px", marginBottom: "6px", alignItems: "flex-start" }}>
                    <div style={{ width: "18px", height: "18px", borderRadius: "50%", background: i === 0 ? "rgba(74,222,128,0.15)" : "rgba(71,85,105,0.15)", border: i === 0 ? "1px solid rgba(74,222,128,0.3)" : "1px solid rgba(71,85,105,0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.58rem", fontWeight: 700, color: i === 0 ? "#4ade80" : "#94a3b8", flexShrink: 0 }}>{i + 1}</div>
                    <span style={{ fontSize: "0.7rem", color: i === 0 ? "#e2e8f0" : "#94a3b8", lineHeight: 1.4, fontWeight: i === 0 ? 600 : 400 }}>{step}</span>
                  </div>
                ))}
              </div>

              {/* Expert Note */}
              <div style={{ padding: "8px 10px", borderRadius: "8px", background: "rgba(139,92,246,0.06)", border: "1px solid rgba(139,92,246,0.12)" }}>
                <div style={{ fontSize: "0.58rem", color: "#a78bfa", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>🧬 Expert Analysis</div>
                <p style={{ fontSize: "0.68rem", color: "#a78bfa", lineHeight: 1.5, margin: 0, opacity: 0.85 }}>{intel.expertNote}</p>
              </div>

              {/* Linked Actions from L8 */}
              {zone.linked_actions && zone.linked_actions.length > 0 && (
                <div>
                  <div style={{ fontSize: "0.58rem", color: "#fbbf24", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>🔗 Linked Prescriptions</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                    {zone.linked_actions.map((a, i) => (
                      <span key={i} style={{ fontSize: "0.6rem", padding: "2px 8px", borderRadius: "4px", background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.15)", color: "#fcd34d" }}>{a.replace(/_/g, ' ')}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
