"use client";

/**
 * SidebarExpertView — Agronomic analysis console.
 * Dense scientific view: stats, zone decomposition, evidence chain, charts.
 * All data from real L10/engine data. Zero synthetic data.
 */

import React from "react";
import { useLayer10, type Layer10Result, type ZoneData, type ExplainabilityPack, type DriverWeight } from "@/hooks/useLayer10";
import {
  getRenderableZonesForMode,
  MODE_ZONE_SURFACE_MAP,
  type MapMode,
  sanitizeRecommendedAction
} from "@/lib/agribrain/plot-map-evidence-state";
import type { EngineStatus } from "@/hooks/usePlotIntelligence";
import { isRenderedMaterialization } from "@/lib/agribrain/render-materialization";

interface ExpertViewProps {
  data: Layer10Result;
  activeMode: string;
  surfaceType: string;
  explainPack: ExplainabilityPack | undefined;
  engines: EngineStatus[];
  assimilation: any;
  onAskBrain: (query: string) => void;
}

const S = {
  card: { background: "rgba(0,0,0,0.25)", border: "1px solid rgba(71,85,105,0.12)", borderRadius: "8px", padding: "10px" } as React.CSSProperties,
  sectionLabel: { fontSize: "11px", color: "#64748b", fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.08em", marginBottom: "8px" },
  mono: { fontFamily: "monospace", fontWeight: 700 } as React.CSSProperties,
};

// Helper: merge S.card with a className
const card = (extra?: React.CSSProperties) => ({ className: "sev-card", style: { ...S.card, ...extra } });

// ── Inline SVG Bar Chart (horizontal) ───────────────────────────────────
function HBarChart({ items, maxVal }: { items: { label: string; value: number; color: string }[]; maxVal: number }) {
  if (items.length === 0) return null;
  const w = 200, barH = 14, gap = 4;
  const h = items.length * (barH + gap);
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block" }}>
      {items.map((item, i) => {
        const y = i * (barH + gap);
        const bw = maxVal > 0 ? (item.value / maxVal) * (w - 60) : 0;
        return (
          <g key={i}>
            <rect x={0} y={y} width={Math.max(bw, 2)} height={barH} rx={3} fill={item.color} opacity={0.8} />
            <text x={Math.max(bw, 2) + 4} y={y + barH - 3} fontSize="9" fill="#94a3b8" fontFamily="monospace">{item.value.toFixed(3)}</text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Driver Weight Bar ───────────────────────────────────────────────────
function DriverBar({ driver, maxWeight }: { driver: DriverWeight; maxWeight: number }) {
  const pct = maxWeight > 0 ? (Math.abs(driver.value) / maxWeight) * 100 : 0;
  const color = driver.role === "positive" ? "#4ade80" : driver.role === "negative" ? "#f87171" : "#fbbf24";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "5px" }}>
      <div style={{ width: "70px", fontSize: "12px", color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{driver.name}</div>
      <div style={{ flex: 1, height: "6px", background: "rgba(71,85,105,0.2)", borderRadius: "3px", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: "3px", transition: "width 0.3s" }} />
      </div>
      <div style={{ fontSize: "12px", color, fontFamily: "monospace", fontWeight: 700, minWidth: "30px", textAlign: "right" }}>{driver.value.toFixed(2)}</div>
    </div>
  );
}

// ── Root Cause + Directive Lookup ───────────────────────────────────────
const ZONE_INTELLIGENCE: Record<string, { icon: string; cause: string; directive: string; expertHypothesis: string }> = {
  LOW_VIGOR: {
    icon: "🟤",
    cause: "Plants in this area show significantly less chlorophyll activity. This typically indicates one of: (a) water deficit limiting photosynthesis, (b) nitrogen deficiency reducing leaf greenness, (c) pest/disease damage to leaf tissue, or (d) compacted soil restricting root growth.",
    directive: "Scout this zone within 48h. Check leaf color (yellowing = N deficiency, wilting = water), dig 15cm to check soil moisture, inspect for pest damage on leaf undersides.",
    expertHypothesis: "Consider whether this zone coincides with soil texture boundaries (clay→sand transition). Low vigor in consistent spatial positions across seasons suggests a structural soil limitation rather than management-induced stress.",
  },
  WATER_STRESS: {
    icon: "💧",
    cause: "Soil moisture deficit is exceeding the crop's extraction capacity. The root zone cannot supply water fast enough to meet transpiration demand. This may be caused by: insufficient irrigation scheduling, blocked drip lines, high VPD forcing excess transpiration, or shallow root development.",
    directive: "Check irrigation system function in this zone. Verify drip line flow rates. If rain-fed, consider supplemental irrigation for the next 7 days. Prioritize this zone if crop is in reproductive stage.",
    expertHypothesis: "Evaluate whether apparent water stress is actually a nutrient deficiency reducing stomatal conductance (N-deficient crops show similar spectral signatures). Cross-reference with nutrient surface for confirmation.",
  },
  NUTRIENT_RISK: {
    icon: "🧪",
    cause: "Spectral analysis suggests sub-optimal nutrient availability. The most common cause is nitrogen depletion during rapid vegetative growth. Could also indicate phosphorus limitation (purple tinting), potassium deficiency (edge scorch), or micronutrient lock-out from extreme soil pH.",
    directive: "Conduct tissue analysis (petiole NO₃⁻ test). If confirmed, apply variable-rate N at 20-30 kg/ha in deficit zones. Avoid blanket application — healthy zones don't need it.",
    expertHypothesis: "Nutrient stress can be confounded with waterlogging (anaerobic root conditions inhibit N uptake even when soil N is adequate). Check topographic position — is this a low-lying area?",
  },
  DISEASE_RISK: {
    icon: "🦠",
    cause: "Environmental conditions (high humidity, dense canopy, leaf wetness >6h) have created favorable conditions for fungal/bacterial development. The spectral signal shows localized reflectance changes consistent with biotic damage.",
    directive: "Scout immediately: look for lesions, spots, or discoloration patterns. If confirmed, apply targeted fungicide to this zone only (not field-wide). Monitor spread direction — disease moves downwind.",
    expertHypothesis: "Spectral anomalies from disease can be confused with early senescence or herbicide drift damage. Check if the affected zone is downwind of spray applications or adjacent to treated fields.",
  },
  YIELD_GAP: {
    icon: "📉",
    cause: "This zone is producing significantly below the field's potential. The gap represents lost production from cumulative stress over the season — water, nutrient, and disease effects compound over time.",
    directive: "This zone needs a recovery plan for next season: soil test, check drainage, review irrigation coverage. Current-season intervention has limited yield recovery potential.",
    expertHypothesis: "Persistent yield gaps in the same spatial position across seasons point to soil structural issues (compaction, poor drainage, pH) rather than seasonal management. Review historical imagery for spatial consistency.",
  },
  HIGH_VIGOR: {
    icon: "🌿",
    cause: "This area shows above-average vegetation vigor. While generally positive, excessive vigor can indicate: over-fertilization (N leaching risk), poor lodging resistance, or increased disease susceptibility from dense canopy.",
    directive: "No immediate action needed. Monitor for lodging risk if grain crop. Consider reducing N input in this zone next season to optimize cost efficiency.",
    expertHypothesis: "Over-vigorous zones near field edges may indicate nutrient runoff accumulation from adjacent areas. Assess whether the vigor is productive (grain fill) or vegetative excess (tall stems, small heads).",
  },
  BLOCKED_ZONE: {
    icon: "🚫",
    cause: "This zone has been flagged as blocked for intervention — typically due to restricted access, ongoing treatment, or regulatory constraints.",
    directive: "Verify the block reason. If access is restored, reassess priority. Otherwise, monitor remotely.",
    expertHypothesis: "Blocked zones that persist may be accumulating stress that will require higher-intensity intervention once access is restored.",
  },
  SCOUT_ZONE: {
    icon: "🔍",
    cause: "The system has identified uncertainty in this zone that requires ground-truth verification. Remote sensing confidence is below threshold — human eyes needed.",
    directive: "Schedule field scouting within 3 days. Photograph representative plants, measure soil moisture at 10cm and 30cm depth, collect tissue samples if nutrient stress is suspected.",
    expertHypothesis: "Low-confidence zones may reflect spectral confusion from mixed pixels (crop/soil boundary), shadow effects, or cloud contamination in the source imagery.",
  },
  SALINITY_RISK: {
    icon: "🧂",
    cause: "Elevated soil electrical conductivity (EC) or sodicity indicators suggest salt accumulation in the root zone. Salinity reduces osmotic potential, making water extraction progressively harder for roots even in wet soil. Sources: L1 EC/pH rasters, L3 diagnostic probability, or FAO soil classification metadata.",
    directive: "Measure soil EC at 0-30cm and 30-60cm with a portable EC meter. If EC > 4 dS/m: apply leaching irrigation (50-75mm) and monitor drainage. Avoid ammonium-based fertilizers (use calcium nitrate instead). For sodic soils (pH > 8.5), consider gypsum application at 2-5 t/ha.",
    expertHypothesis: "Apparent salinity stress can be confounded with drought stress (both cause leaf tip burn and stunted growth). Differentiate by checking soil moisture: if soil is moist but crop is wilted, salinity is the likely cause (osmotic stress). Also check if the pattern follows topography — salt tends to accumulate in low-lying areas with poor drainage or in areas receiving lateral seepage from higher ground.",
  },
};

function _getZoneIntel(zone: ZoneData) {
  // Try exact zone_type match first
  const exact = ZONE_INTELLIGENCE[zone.zone_type];
  if (exact) return exact;
  // Fuzzy match from drivers
  for (const driver of zone.top_drivers) {
    const upper = driver.toUpperCase();
    if (upper.includes("WATER") || upper.includes("DROUGHT") || upper.includes("MOISTURE")) return ZONE_INTELLIGENCE.WATER_STRESS;
    if (upper.includes("NUTRI") || upper.includes("NITROGEN") || upper.includes("FERTIL")) return ZONE_INTELLIGENCE.NUTRIENT_RISK;
    if (upper.includes("DISEASE") || upper.includes("BIOTIC") || upper.includes("FUNGAL")) return ZONE_INTELLIGENCE.DISEASE_RISK;
    if (upper.includes("NDVI") || upper.includes("VIGOR") || upper.includes("VEGETATION")) return ZONE_INTELLIGENCE.LOW_VIGOR;
  }
  return { icon: "📍", cause: "Zone flagged by multi-surface analysis. Review drivers and surface stats for detailed assessment.", directive: "Scout this zone and compare with adjacent healthy areas.", expertHypothesis: "Consider whether this zone was created from uniform data with low spatial confidence." };
}

// ── Zone Intelligence Card (Expert) ─────────────────────────────────────
function ZoneRow({ zone, onAsk }: { zone: ZoneData; onAsk: (q: string) => void }) {
  const sevColor = zone.severity > 0.6 ? "#f87171" : zone.severity > 0.3 ? "#fbbf24" : "#4ade80";
  const confColor = zone.confidence > 0.7 ? "#4ade80" : zone.confidence > 0.4 ? "#fbbf24" : "#f87171";
  const intel = _getZoneIntel(zone);
  const statsEntries = Object.entries(zone.surface_stats || {});

  return (
    <div className="sev-card" style={{ ...S.card, marginBottom: "8px", borderLeft: `3px solid ${sevColor}` }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "1.1rem" }}>{intel.icon}</span>
          <span style={{ fontSize: "14px", color: "#e2e8f0", fontWeight: 700 }}>{zone.label || zone.zone_id}</span>
        </div>
        <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
          <span style={{ fontSize: "9px", padding: "2px 6px", borderRadius: "4px", background: `${sevColor}15`, color: sevColor, fontWeight: 700 }}>
            {zone.severity > 0.6 ? "CRITICAL" : zone.severity > 0.3 ? "WATCH" : "LOW"}
          </span>
          <span style={{ fontSize: "9px", padding: "2px 6px", borderRadius: "4px", background: `${confColor}15`, color: confColor, fontWeight: 700 }}>
            {(zone.confidence * 100).toFixed(0)}% conf
          </span>
        </div>
      </div>

      {/* Metadata row */}
      <div style={{ display: "flex", gap: "8px", fontSize: "11px", color: "#64748b", marginBottom: "8px", flexWrap: "wrap" }}>
        <span>📐 {(zone.area_fraction * 100).toFixed(1)}% of field</span>
        <span>🏷️ {zone.zone_type.replace(/_/g, " ")}</span>
        {zone.evidence_age_days != null && <span>📅 {zone.evidence_age_days}d old</span>}
        {zone.is_inferred && <span style={{ color: "#fbbf24" }}>⚡ inferred</span>}
      </div>

      {/* ── Root Cause Analysis ── */}
      <div className="sev-cause" style={{ padding: "8px 10px", borderRadius: "6px", background: "rgba(99,102,241,0.04)", border: "1px solid rgba(99,102,241,0.08)", marginBottom: "6px" }}>
        <div style={{ fontSize: "11px", color: "#a5b4fc", fontWeight: 700, textTransform: "uppercase", marginBottom: "4px" }}>🔍 Root Cause Analysis</div>
        <div style={{ fontSize: "12px", color: "#cbd5e1", lineHeight: 1.5 }}>{intel.cause}</div>
        {zone.top_drivers.length > 0 && (
          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginTop: "6px" }}>
            {zone.top_drivers.map((d, i) => (
              <span key={i} style={{ fontSize: "9px", padding: "2px 6px", borderRadius: "4px", background: "rgba(0,0,0,0.3)", color: "#e2e8f0", border: "1px solid rgba(71,85,105,0.15)" }}>
                {d}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Action Directive ── */}
      <div className="sev-directive" style={{ padding: "8px 10px", borderRadius: "6px", background: "rgba(34,197,94,0.04)", border: "1px solid rgba(34,197,94,0.1)", marginBottom: "6px" }}>
        <div style={{ fontSize: "11px", color: "#4ade80", fontWeight: 700, textTransform: "uppercase", marginBottom: "4px" }}>✅ Recommended Action</div>
        <div style={{ fontSize: "12px", color: "#cbd5e1", lineHeight: 1.5 }}>{intel.directive}</div>
        {zone.linked_actions.length > 0 && (
          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginTop: "6px" }}>
            {zone.linked_actions.map((a, i) => (
              <span key={i} style={{ fontSize: "9px", padding: "2px 6px", borderRadius: "4px", background: "rgba(99,102,241,0.08)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.1)", fontWeight: 600 }}>
                💡 {a}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Surface Stats ── */}
      {statsEntries.length > 0 && (
        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginBottom: "6px" }}>
          {statsEntries.map(([surfKey, stats]) => (
            <div key={surfKey} style={{ fontSize: "9px", color: "#94a3b8", padding: "2px 6px", borderRadius: "4px", background: "rgba(0,0,0,0.3)", border: "1px solid rgba(71,85,105,0.1)" }}>
              <span style={{ color: "#64748b" }}>{surfKey}: </span>
              {(stats as any).mean != null && <span style={{ color: "#e2e8f0" }}>μ={((stats as any).mean).toFixed(3)} </span>}
              {(stats as any).std != null && <span style={{ color: "#a78bfa" }}>σ={((stats as any).std).toFixed(3)}</span>}
            </div>
          ))}
        </div>
      )}

      {/* ── Confidence Reasons ── */}
      {zone.confidence_reasons.length > 0 && (
        <div style={{ fontSize: "9px", color: "#94a3b8", marginBottom: "6px" }}>
          {zone.confidence_reasons.map((r, i) => (
            <div key={i} style={{ marginBottom: "2px" }}>
              <span style={{ color: zone.confidence > 0.7 ? "#4ade80" : "#fbbf24" }}>•</span> {r}
            </div>
          ))}
        </div>
      )}

      {/* ── Expert Hypothesis ── */}
      <div className="sev-hypothesis" style={{ padding: "8px 10px", borderRadius: "6px", background: "rgba(251,191,36,0.04)", border: "1px solid rgba(251,191,36,0.08)", marginBottom: "6px" }}>
        <div style={{ fontSize: "11px", color: "#fbbf24", fontWeight: 700, textTransform: "uppercase", marginBottom: "3px" }}>⚖️ Alternative Hypothesis</div>
        <div style={{ fontSize: "12px", color: "#94a3b8", lineHeight: 1.4, fontStyle: "italic" }}>{intel.expertHypothesis}</div>
      </div>

      {/* Trust note */}
      {zone.trust_note && (
        <div style={{ fontSize: "9px", color: "#fbbf24", marginBottom: "6px", fontStyle: "italic" }}>⚠ {zone.trust_note}</div>
      )}

      {/* ── Debate Buttons ── */}
      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
        <button onClick={() => onAsk(`Zone ${zone.label || zone.zone_id} is classified as ${zone.zone_type} with severity ${(zone.severity*100).toFixed(0)}%. Drivers: ${zone.top_drivers.join(', ')}. What is the most likely root cause? Could this be a false positive?`)}
          style={{ fontSize: "12px", padding: "6px 10px", borderRadius: "5px", border: "1px solid rgba(99,102,241,0.2)", background: "rgba(99,102,241,0.06)", color: "#a5b4fc", fontWeight: 700, cursor: "pointer" }}>
          🧪 Diagnose
        </button>
        <button onClick={() => onAsk(`What specific interventions would address the ${zone.zone_type.replace(/_/g, ' ').toLowerCase()} in zone ${zone.label || zone.zone_id}? Compare cost vs. expected yield recovery.`)}
          style={{ fontSize: "12px", padding: "6px 10px", borderRadius: "5px", border: "1px solid rgba(34,197,94,0.2)", background: "rgba(34,197,94,0.06)", color: "#34d399", fontWeight: 700, cursor: "pointer" }}>
          💊 Prescribe
        </button>
        <button onClick={() => onAsk(`Challenge the ${zone.zone_type} classification in zone ${zone.label || zone.zone_id}. Confidence is ${(zone.confidence*100).toFixed(0)}%. What alternative explanations exist? What additional data would resolve the ambiguity?`)}
          style={{ fontSize: "12px", padding: "6px 10px", borderRadius: "5px", border: "1px solid rgba(251,191,36,0.2)", background: "rgba(251,191,36,0.06)", color: "#fbbf24", fontWeight: 700, cursor: "pointer" }}>
          ⚖️ Challenge
        </button>
      </div>
    </div>
  );
}

// ── Main Expert View ────────────────────────────────────────────────────
export default function SidebarExpertView({ data, activeMode, surfaceType, explainPack, engines, assimilation, onAskBrain }: ExpertViewProps) {
  const l10Context = useLayer10();
  const spatiallyMaterialized = isRenderedMaterialization(l10Context.renderPlan.baseMaterialization, surfaceType);
  const fieldHist = spatiallyMaterialized
    ? data.histograms.field.find(h => h.surface_type === surfaceType)
    : undefined;
  const zoneHists = data.histograms.zone.filter(h => h.surface_type === surfaceType);
  const delta = data.histograms.delta.find(d => d.surface_type === surfaceType);
  // Mode-aware zone filtering — only show zones relevant to the active surface
  const activeZoneSurfaceType = MODE_ZONE_SURFACE_MAP[activeMode as MapMode] || "";
  const renderableZones = getRenderableZonesForMode({
    zones: data.zones || [],
    activeMode: activeMode as MapMode,
    activeZoneSurfaceType,
    detailMode: "expert",
    materialization: l10Context.renderPlan.baseMaterialization,
    gridHeight: l10Context.renderPlan.baseMaterialization.gridHeight ?? undefined,
    gridWidth: l10Context.renderPlan.baseMaterialization.gridWidth ?? undefined,
  });
  const relevantZones = renderableZones.filter((z) => z.severity > 0);
  const quality = data.quality;

  // CV calculation from real histogram
  const cv = fieldHist && fieldHist.mean !== 0 ? (fieldHist.std / Math.abs(fieldHist.mean)) * 100 : null;

  // Max driver weight for scaling
  const drivers = explainPack?.top_drivers || [];
  const maxDriverWeight = drivers.length > 0 ? Math.max(...drivers.map(d => Math.abs(d.value))) : 1;

  const activeSurfaceObj = data.surfaces.find(s => s.type === surfaceType || s.semantic_type === surfaceType);
  let minVal = 0, maxVal = 0, meanVal = 0, stdVal = 0;
  let forceUniform = false;
  if (activeSurfaceObj) {
    const flatVals = activeSurfaceObj.values.flat().filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    if (flatVals.length > 0) {
      minVal = Math.min(...flatVals);
      maxVal = Math.max(...flatVals);
      meanVal = flatVals.reduce((a, b) => a + b, 0) / flatVals.length;
      const variance = flatVals.reduce((a, b) => a + Math.pow(b - meanVal, 2), 0) / flatVals.length;
      stdVal = Math.sqrt(variance);
    }
    const gc = activeSurfaceObj.grounding_class || "";
    const isRealRaster = ["RASTER_GROUNDED", "PARTIAL_RASTER_GROUNDED"].includes(gc);
    const modeAvail = l10Context.modeAvailability?.[activeMode];
    const displayLevel = modeAvail?.displayLevel;
    const renderKind = modeAvail?.renderKind;
    const renderMode = l10Context.evidenceState?.renderMode;
    forceUniform =
      renderKind === "uniform_tint" ||
      displayLevel === "plot_level" ||
      displayLevel === "visual_only" ||
      (renderMode === "soft_proxy_tint" && !isRealRaster);
  }

  const evidenceState = l10Context.evidenceState;
  const sanitizedAction = React.useMemo(() => {
    return sanitizeRecommendedAction(explainPack?.recommended_action || null, evidenceState);
  }, [explainPack?.recommended_action, evidenceState]);

  if (!spatiallyMaterialized) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div className="sev-card" style={{ ...S.card, border: "1px solid rgba(248,113,113,0.3)", padding: "12px" }}>
          <div style={{ ...S.sectionLabel, color: "#fca5a5", marginBottom: "8px" }}>Spatial materialization blocked</div>
          <div style={{ fontSize: "11px", color: "#94a3b8", lineHeight: 1.5 }}>
            Surface {surfaceType || "unknown"} did not create a map layer. Pixel histograms,
            geographic zones, and derived diagnostics are suppressed.
          </div>
          <div style={{ marginTop: "8px", fontSize: "10px", color: "#f87171", fontFamily: "monospace" }}>
            {l10Context.renderPlan.baseMaterialization.status}: {l10Context.renderPlan.baseMaterialization.reason || "missing surface"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {/* ── Surface Debug Card ─────────────────────────────────── */}
      {activeSurfaceObj && (
        <div className="sev-card" style={{ ...S.card, border: "1px solid rgba(167, 139, 250, 0.3)", background: "rgba(15, 23, 42, 0.6)", padding: "12px" }}>
          <div style={{ ...S.sectionLabel, color: "#a78bfa", marginBottom: "6px" }}>Surface Debug</div>
          <div style={{ fontSize: "11px", color: "#cbd5e1", display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "6px", fontFamily: "monospace" }}>
            <div>Surface: <span style={{ color: "#f1f5f9" }}>{surfaceType}</span></div>
            <div>Display level: <span style={{ color: "#f1f5f9" }}>{l10Context.modeAvailability?.[activeMode]?.displayLevel || "raster"}</span></div>
            <div>Render mode: <span style={{ color: "#f1f5f9" }}>{l10Context.evidenceState?.renderMode || "standard"}</span></div>
            <div>Grid: <span style={{ color: "#f1f5f9" }}>{activeSurfaceObj.values.length} × {activeSurfaceObj.values[0]?.length || 0}</span></div>
            <div>Native res: <span style={{ color: "#f1f5f9" }}>{(activeSurfaceObj as any).native_resolution_m ?? "10"}m</span></div>
            <div>Observed ratio: <span style={{ color: "#f1f5f9" }}>{activeSurfaceObj.observed_ratio ?? (activeSurfaceObj as any).observed_ratio ?? "1.00"}</span></div>
            <div>Gap-filled ratio: <span style={{ color: "#f1f5f9" }}>{((activeSurfaceObj.provenance as any)?.gap_fill_ratio ?? 0.00).toFixed(2)}</span></div>
            <div style={{ gridColumn: "span 2" }}>Value min/mean/max/std:
              <span style={{ color: "#f1f5f9" }}> {minVal.toFixed(3)}/{meanVal.toFixed(3)}/{maxVal.toFixed(3)}/{stdVal.toFixed(3)}</span>
            </div>
            <div style={{ gridColumn: "span 2" }}>Color range: <span style={{ color: "#f1f5f9" }}>{(activeSurfaceObj.render_range?.[0] ?? -0.1).toFixed(2)} → {(activeSurfaceObj.render_range?.[1] ?? 1.0).toFixed(2)}</span></div>
            <div>Visual stretch: <span style={{ color: "#f1f5f9" }}>{activeMode === "canopy" && stdVal < 0.12 ? "hybrid" : "absolute"}</span></div>
            <div>Force uniform: <span style={{ color: forceUniform ? "#fbbf24" : "#4ade80" }}>{forceUniform ? "true" : "false"}</span></div>
            <div>Exp. active: <span style={{ color: l10Context.showExperimental1m ? "#4ade80" : "#94a3b8" }}>{l10Context.showExperimental1m ? "true" : "false"}</span></div>
            <div>ASMAE active: <span style={{ color: (l10Context.modeAvailability?.[activeMode] as any)?.asmae_status === "active" ? "#4ade80" : "#f87171" }}>{(l10Context.modeAvailability?.[activeMode] as any)?.asmae_status === "active" ? "true" : "false"}</span></div>
            <div>ASMAE core: <span style={{ color: "#f1f5f9" }}>{(l10Context.modeAvailability?.[activeMode] as any)?.asmae_core_status || "not requested"}</span></div>
            <div style={{ gridColumn: "span 2", overflow: "hidden", textOverflow: "ellipsis" }}>ASMAE status: <span style={{ color: "#f1f5f9" }}>{(l10Context.modeAvailability?.[activeMode] as any)?.asmae_status || "not_run"}</span></div>
            <div style={{ gridColumn: "span 2", overflow: "hidden", textOverflow: "ellipsis" }}>ASMAE reason: <span style={{ color: "#f1f5f9" }}>{(l10Context.modeAvailability?.[activeMode] as any)?.asmae_rejection_reason || "None"}</span></div>
          </div>
        </div>
      )}

      {/* ── V92.4-BC.2: ASMAE Mode Status Card ────────────────── */}
      {(() => {
        const mds = (data as any)?.mode_display_state;
        if (!mds || typeof mds !== "object") return null;
        const ASMAE_MODES = [
          { key: "canopy", label: "Canopy" },
          { key: "veg_attention", label: "Veg Attention" },
          { key: "water_stress", label: "Water" },
          { key: "nutrient_risk", label: "Nutrients" },
          { key: "salinity", label: "Salinity" },
          { key: "composite_risk", label: "Risk" },
          { key: "uncertainty", label: "Confidence" },
          { key: "resolution_coverage", label: "Resolution" },
        ];
        const STATUS_COLORS: Record<string, string> = {
          active: "#4ade80",
          authority_eligible: "#22d3ee",
          visual_eligible: "#a78bfa",
          eligible: "#60a5fa",
          visual_ineligible: "#fbbf24",
          ineligible: "#f87171",
          no_l1_asmae: "#94a3b8",
          not_run: "#475569",
        };
        const STATUS_LABELS: Record<string, string> = {
          active: "ACTIVE",
          authority_eligible: "AUTH ✓",
          visual_eligible: "VISUAL ✓",
          eligible: "ELIGIBLE",
          visual_ineligible: "VIS INELIG",
          ineligible: "INELIGIBLE",
          no_l1_asmae: "NO L1",
          not_run: "NOT RUN",
        };
        return (
          <div className="sev-card" style={{ ...S.card, border: "1px solid rgba(96, 165, 250, 0.25)", background: "rgba(15, 23, 42, 0.6)", padding: "12px" }}>
            <div style={{ ...S.sectionLabel, color: "#60a5fa", marginBottom: "8px" }}>ASMAE Mode Status</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px" }}>
              {ASMAE_MODES.map(({ key, label }) => {
                const state = mds[key];
                if (!state) return null;
                const status = state.asmae_status || "not_run";
                const color = STATUS_COLORS[status] || "#475569";
                const statusLabel = STATUS_LABELS[status] || status.toUpperCase();
                return (
                  <div key={key} style={{ display: "flex", flexDirection: "column", gap: "2px", padding: "4px 6px", borderRadius: "4px", background: `${color}08`, border: `1px solid ${color}15` }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "6px" }}>
                      <span style={{ fontSize: "10px", color: "#94a3b8", width: "58px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
                      <span style={{ fontSize: "9px", fontWeight: 700, color, fontFamily: "monospace", padding: "1px 4px", borderRadius: "3px", background: `${color}15` }}>{statusLabel}</span>
                    </div>
                    <div style={{ fontSize: "8px", color: "#94a3b8", fontFamily: "monospace" }}>Core: {state.asmae_core_status || "not requested"}</div>
                  </div>
                );
              })}
            </div>
            {/* Expanded detail for active mode */}
            {(() => {
              const activeMds = mds[activeMode];
              if (!activeMds || activeMds.asmae_status === "not_run") return null;
              return (
                <div style={{ marginTop: "8px", padding: "6px 8px", borderRadius: "6px", background: "rgba(0,0,0,0.3)", fontSize: "10px", color: "#cbd5e1", fontFamily: "monospace", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "3px" }}>
                  <div>Status: <span style={{ color: STATUS_COLORS[activeMds.asmae_status] || "#94a3b8" }}>{activeMds.asmae_status}</span></div>
                  <div>Core: <span style={{ color: "#f1f5f9" }}>{activeMds.asmae_core_status || "not requested"}</span></div>
                  <div>Surface: <span style={{ color: "#f1f5f9" }}>{activeMds.selected_asmae_surface || "none"}</span></div>
                  <div style={{ gridColumn: "span 2" }}>Rejection: <span style={{ color: activeMds.asmae_rejection_reason ? "#fbbf24" : "#4ade80" }}>{activeMds.asmae_rejection_reason || "none"}</span></div>
                  {activeMds.authority_block_reason && (
                    <div style={{ gridColumn: "span 2" }}>Auth block: <span style={{ color: "#f87171" }}>{activeMds.authority_block_reason}</span></div>
                  )}
                  <div>Display: <span style={{ color: "#f1f5f9" }}>{activeMds.displayLevel || "?"}</span></div>
                  <div>Authority: <span style={{ color: "#f1f5f9" }}>{activeMds.authorityLevel || "?"}</span></div>
                </div>
              );
            })()}
          </div>
        );
      })()}

      {/* ── Surface Statistics ─────────────────────────────────── */}
      {fieldHist && (
        <div>
          <div style={S.sectionLabel}>Surface Statistics — {surfaceType.replace(/_/g, " ")}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px" }}>
            <StatCell label="μ mean" value={fieldHist.mean.toFixed(4)} color="#e2e8f0" />
            <StatCell label="σ std" value={fieldHist.std.toFixed(4)} color="#a78bfa" />
            {cv != null && <StatCell label="CV%" value={cv.toFixed(1) + "%"} color={cv < 15 ? "#4ade80" : cv < 30 ? "#fbbf24" : "#f87171"} />}
            {fieldHist.p10 != null && <StatCell label="P10" value={fieldHist.p10.toFixed(4)} color="#94a3b8" />}
            {fieldHist.p90 != null && <StatCell label="P90" value={fieldHist.p90.toFixed(4)} color="#94a3b8" />}
            {fieldHist.valid_pixels != null && <StatCell label="Pixels" value={`${fieldHist.valid_pixels}/${fieldHist.total_pixels || "?"}`} color="#64748b" />}
          </div>
        </div>
      )}

      {/* ── Delta / Temporal Shift ─────────────────────────────── */}
      {delta && (
        <div className="sev-card" style={S.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
            <span style={{ fontSize: "10px", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>Temporal Shift</span>
            <span style={{ fontSize: "10px", color: delta.shift_direction === "IMPROVING" ? "#4ade80" : delta.shift_direction === "DECLINING" ? "#f87171" : "#fbbf24", fontWeight: 700 }}>
              {delta.shift_direction}
            </span>
          </div>
          <div style={{ fontSize: "11px", color: "#e2e8f0", fontFamily: "monospace" }}>
            Δμ = {delta.mean_change > 0 ? "+" : ""}{delta.mean_change.toFixed(4)}
          </div>
          <div style={{ fontSize: "9px", color: "#64748b", marginTop: "2px" }}>
            {delta.date_from} → {delta.date_to}
          </div>
        </div>
      )}

      {/* ── Driver Weights ─────────────────────────────────────── */}
      {drivers.length > 0 && (
        <div>
          <div style={S.sectionLabel}>Driver Weights</div>
          {drivers.map((d, i) => <DriverBar key={i} driver={d} maxWeight={maxDriverWeight} />)}
        </div>
      )}

      {/* ── AI Interpretation ─────────────────────────────────── */}
      {explainPack?.summary && (
        <div style={{ padding: "8px 10px", borderRadius: "8px", background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.1)" }}>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "#a5b4fc", textTransform: "uppercase", marginBottom: "4px" }}>Model Interpretation</div>
          <p style={{ fontSize: "11px", color: "#cbd5e1", lineHeight: 1.5, margin: 0 }}>{explainPack.summary}</p>
        </div>
      )}

      {/* Expert Evidence & Action Card (V63F) */}
      {sanitizedAction.text && (
        <div className="sev-evidence-action-card animate-fadeInUp" data-testid="driver-action-card" style={{
          ...S.card,
          padding: "12px 14px",
          background: "rgba(99, 102, 241, 0.08)",
          border: "1px solid rgba(99, 102, 241, 0.2)",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.1)",
          display: "flex",
          flexDirection: "column",
          gap: "8px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.6rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", color: "#818cf8" }}>Evidence & Advisory Action</span>
            {sanitizedAction.actionLevel && (
              <span style={{
                fontSize: "0.55rem",
                fontWeight: 800,
                textTransform: "uppercase",
                padding: "2px 6px",
                borderRadius: "4px",
                background: sanitizedAction.actionLevel === "act_blocked" ? "rgba(239, 68, 68, 0.15)" : sanitizedAction.actionLevel === "scout" ? "rgba(249, 115, 22, 0.15)" : sanitizedAction.actionLevel === "verify" ? "rgba(251, 191, 36, 0.15)" : "rgba(99, 102, 241, 0.15)",
                color: sanitizedAction.actionLevel === "act_blocked" ? "#f87171" : sanitizedAction.actionLevel === "scout" ? "#fb923c" : sanitizedAction.actionLevel === "verify" ? "#fbbf24" : "#818cf8",
                border: `1px solid ${sanitizedAction.actionLevel === "act_blocked" ? "rgba(239, 68, 68, 0.25)" : sanitizedAction.actionLevel === "scout" ? "rgba(249, 115, 22, 0.25)" : sanitizedAction.actionLevel === "verify" ? "rgba(251, 191, 36, 0.25)" : "rgba(99, 102, 241, 0.25)"}`
              }}>{sanitizedAction.actionLevel}</span>
            )}
          </div>
          {explainPack?.dominant_driver && (
            <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "#f1f5f9" }}>
              Dominant Driver: {explainPack.dominant_driver}
              {explainPack.driver_confidence !== undefined && (
                <span style={{ fontSize: "0.7rem", fontWeight: 500, color: "#94a3b8", marginLeft: "6px" }}>
                  ({(explainPack.driver_confidence * 100).toFixed(0)}% confidence)
                </span>
              )}
            </div>
          )}
          {explainPack?.evidence && explainPack.evidence.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontSize: "0.6rem", fontWeight: 700, textTransform: "uppercase", color: "#94a3b8" }}>Supporting Evidence:</span>
              <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "0.72rem", color: "#cbd5e1" }}>
                {explainPack.evidence.map((ev, i) => (
                  <li key={i} style={{ marginBottom: "2px" }}>{ev}</li>
                ))}
              </ul>
            </div>
          )}
          <div style={{ fontSize: "0.75rem", color: "#e2e8f0", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "8px", marginTop: "4px" }}>
            <span style={{ fontWeight: 700, color: "#818cf8" }}>Recommended Action:</span> {sanitizedAction.text}
          </div>
          {sanitizedAction.suppressed && (
            <div style={{
              fontSize: "0.7rem",
              background: "rgba(249, 115, 22, 0.15)",
              color: "#fb923c",
              padding: "4px 8px",
              borderRadius: "4px",
              marginTop: "2px",
              border: "1px solid rgba(249, 115, 22, 0.25)",
              display: "inline-block",
              alignSelf: "flex-start"
            }}>
              ⚠️ Action adjusted to current map evidence
            </div>
          )}
        </div>
      )}

      {/* ── Confidence Breakdown ───────────────────────────────── */}
      {explainPack?.confidence && (
        <div>
          <div style={S.sectionLabel}>Confidence Audit</div>
          <div className="sev-card" style={S.card}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
              <span style={{ fontSize: "11px", color: "#94a3b8" }}>Composite Score</span>
              <span style={{ fontSize: "12px", fontFamily: "monospace", fontWeight: 700, color: explainPack.confidence.score > 0.7 ? "#4ade80" : "#fbbf24" }}>
                {(explainPack.confidence.score * 100).toFixed(0)}%
              </span>
            </div>
            {explainPack.confidence.penalties.length > 0 && (
              <div style={{ marginTop: "4px" }}>
                {explainPack.confidence.penalties.map((p, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", padding: "2px 0" }}>
                    <span style={{ color: "#94a3b8" }}>⚠ {p.reason}</span>
                    <span style={{ color: "#f87171", fontFamily: "monospace" }}>-{(p.impact * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Zone Decomposition ─────────────────────────────────── */}
      {relevantZones.length > 0 && (
        <div>
          <div style={S.sectionLabel}>Zone Decomposition ({relevantZones.length} zones)</div>

          {/* Zone comparison bar chart */}
          {zoneHists.length > 1 && (
            <div style={{ ...S.card, marginBottom: "8px" }}>
              <div style={{ fontSize: "9px", color: "#64748b", marginBottom: "6px", textTransform: "uppercase" }}>Zone Mean Comparison</div>
              <HBarChart
                items={zoneHists.map((zh, i) => ({
                  label: zh.region_id || `Z${i}`,
                  value: zh.mean,
                  color: ["#60a5fa", "#4ade80", "#f59e0b", "#f87171", "#a78bfa"][i % 5],
                }))}
                maxVal={Math.max(...zoneHists.map(z => z.mean), 0.01)}
              />
              <div style={{ display: "flex", gap: "6px", marginTop: "4px", flexWrap: "wrap" }}>
                {zoneHists.map((zh, i) => (
                  <span key={i} style={{ fontSize: "8px", color: ["#60a5fa", "#4ade80", "#f59e0b", "#f87171", "#a78bfa"][i % 5] }}>
                    {zh.region_id || `Z${i}`}: μ={zh.mean.toFixed(3)} σ={zh.std.toFixed(3)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {relevantZones.map(z => <ZoneRow key={z.zone_id} zone={z} onAsk={onAskBrain} />)}
        </div>
      )}

      {/* ── Evidence Provenance ─────────────────────────────────── */}
      {explainPack?.provenance && (
        <div>
          <div style={S.sectionLabel}>Evidence Provenance</div>
          <div className="sev-card" style={S.card}>
            <div style={{ fontSize: "10px", color: "#94a3b8", display: "flex", flexDirection: "column", gap: "3px" }}>
              <div>Model: <span style={{ color: "#e2e8f0", fontFamily: "monospace" }}>{explainPack.provenance.model_version}</span></div>
              <div>Run: <span style={{ color: "#e2e8f0", fontFamily: "monospace" }}>{explainPack.provenance.run_id?.slice(0, 20)}</span></div>
              {explainPack.provenance.sources.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "3px", marginTop: "4px" }}>
                  {explainPack.provenance.sources.map(s => (
                    <span key={s} style={{ fontSize: "9px", padding: "1px 5px", borderRadius: "4px", background: "rgba(34,197,94,0.08)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.1)" }}>{s}</span>
                  ))}
                </div>
              )}
              {explainPack.provenance.degraded_reasons.length > 0 && (
                <div style={{ marginTop: "4px" }}>
                  {explainPack.provenance.degraded_reasons.map((r, i) => (
                    <div key={i} style={{ fontSize: "9px", color: "#fbbf24" }}>⚠ {r}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Quality Flags ──────────────────────────────────────── */}
      <div>
        <div style={S.sectionLabel}>Quality Flags</div>
        <div className="sev-card" style={S.card}>
          <div style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "10px" }}>
            <QualityRow label="Reliability" value={`${(quality.reliability_score * 100).toFixed(0)}%`} ok={quality.reliability_score > 0.6} />
            <QualityRow label="Surfaces" value={`${quality.surfaces_generated}`} ok={quality.surfaces_generated > 0} />
            <QualityRow label="Zones" value={`${quality.zones_generated}`} ok={true} />
            <QualityRow label="Grid Aligned" value={quality.grid_alignment_ok === true ? "Yes" : quality.grid_alignment_ok === false ? "No" : "Not reported"} ok={quality.grid_alignment_ok === true} />
            <QualityRow label="Detail OK" value={quality.detail_conservation_ok === true ? "Yes" : quality.detail_conservation_ok === false ? "No" : "Not reported"} ok={quality.detail_conservation_ok === true} />
            <QualityRow label="Degradation" value={quality.degradation_mode} ok={quality.degradation_mode === "NORMAL"} />
          </div>
          {quality.warnings.length > 0 && (
            <div style={{ marginTop: "6px", borderTop: "1px solid rgba(71,85,105,0.1)", paddingTop: "6px" }}>
              {quality.warnings.map((w, i) => (
                <div key={i} style={{ fontSize: "9px", color: "#fbbf24", marginBottom: "2px" }}>⚠ {w}</div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Model Equations ─────────────────────────────────────── */}
      {explainPack?.equations && explainPack.equations.length > 0 && (
        <div>
          <div style={S.sectionLabel}>Model Equations</div>
          {explainPack.equations.map((eq, i) => (
            <div key={i} className="sev-card" style={{ ...S.card, marginBottom: "4px" }}>
              <div style={{ fontSize: "12px", color: "#a5b4fc", fontWeight: 600, marginBottom: "2px" }}>{eq.label}</div>
              <div className="sev-code" style={{ fontSize: "12px", color: "#e2e8f0", fontFamily: "monospace", background: "rgba(0,0,0,0.3)", padding: "4px 6px", borderRadius: "4px", marginBottom: "4px", overflowX: "auto" }}>{eq.expression}</div>
              <div style={{ fontSize: "11px", color: "#94a3b8", lineHeight: 1.4 }}>{eq.plain_language}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Evidence Chain — source contribution + freshness ────── */}
      {assimilation && (
        <div>
          <div style={S.sectionLabel}>Evidence Chain</div>
          <div className="sev-card" style={S.card}>
            <div style={{ fontSize: "9px", color: "#64748b", marginBottom: "6px" }}>
              Per-source contribution to this surface's spatial pattern. Width ∝ weight.
            </div>
            {(() => {
              const srcWeights: Record<string, number> = (assimilation as any)?.source_weights || {};
              const entries = Object.entries(srcWeights).sort((a, b) => b[1] - a[1]);
              const maxW = entries.length > 0 ? Math.max(...entries.map(e => e[1])) : 1;
              const srcColors: Record<string, string> = {
                s2: "#60a5fa", s1: "#a78bfa", weather: "#fbbf24", soil: "#f97316",
                sensor: "#4ade80", user: "#f472b6", IoT: "#34d399", NDMI: "#38bdf8",
                "SAR-VV": "#8b5cf6", "SWB-Ks": "#fb923c", optical: "#60a5fa", sar: "#a78bfa",
              };
              return entries.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                  {entries.map(([src, w]) => (
                    <div key={src} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <div style={{ width: "60px", fontSize: "9px", color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis" }}>{src}</div>
                      <div style={{ flex: 1, height: "5px", background: "rgba(71,85,105,0.2)", borderRadius: "3px", overflow: "hidden" }}>
                        <div style={{ width: `${(w / maxW) * 100}%`, height: "100%", background: srcColors[src] || "#94a3b8", borderRadius: "3px" }} />
                      </div>
                      <div style={{ fontSize: "9px", color: "#e2e8f0", fontFamily: "monospace", minWidth: "28px", textAlign: "right" }}>{(w * 100).toFixed(0)}%</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: "10px", color: "#475569" }}>No source weight data available for this surface.</div>
              );
            })()}
            {assimilation?.data_freshness_days != null && (
              <div style={{ marginTop: "6px", fontSize: "9px", color: "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                📅 Last observation: <span style={{ color: assimilation.data_freshness_days < 3 ? "#4ade80" : assimilation.data_freshness_days < 7 ? "#fbbf24" : "#f87171", fontFamily: "monospace", fontWeight: 700 }}>{assimilation.data_freshness_days}d ago</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Methodology & Scientific References ─────────────────── */}
      <div>
        <div style={S.sectionLabel}>Methodology</div>
        <div className="sev-card" style={{ ...S.card, fontSize: "12px", color: "#94a3b8", lineHeight: 1.6 }}>
          <div style={{ marginBottom: "6px" }}>
            <span style={{ color: "#a5b4fc", fontWeight: 700 }}>Water Stress:</span> FAO-56 Penman-Monteith ET₀ × crop Kc → deficit / ETc demand.
            Thresholds are phenology-aware (Allen et al. 1998).
          </div>
          <div style={{ marginBottom: "6px" }}>
            <span style={{ color: "#a5b4fc", fontWeight: 700 }}>VPD Stress:</span> Tetens equation es(T) = 0.6108·exp(17.27T/(T+237.3)).
            Stomatal closure thresholds from Grossiord et al. (2020).
          </div>
          <div style={{ marginBottom: "6px" }}>
            <span style={{ color: "#a5b4fc", fontWeight: 700 }}>Salinity Stress:</span> EC → stress mapping per FAO Irrigation & Drainage Paper 29
            (Ayers & Westcot, 1985). EC {"<"} 2 dS/m = no stress; 2–4 = mild; 4–8 = moderate; {">"}8 = severe.
            pH {">"}8.5 used as sodicity proxy. Multi-source cascade: L1 EC → L1 pH → FAO category → L3 diagnostic.
          </div>
          <div style={{ marginBottom: "6px" }}>
            <span style={{ color: "#a5b4fc", fontWeight: 700 }}>Yield Penalty:</span> Stewart model Ya/Ym = 1 − Ky·(1 − ETa/ETm).
            Ky factors from Doorenbos & Kassam (1979), FAO-33.
          </div>
          <div>
            <span style={{ color: "#a5b4fc", fontWeight: 700 }}>Risk Composite:</span> Stage-weighted multi-source: water(Kw) + nutrient(Kn) + disease(Kd) + salinity(Ks) + NDVI deviation.
            Weights shift with phenology (e.g., water 35% at REPRODUCTIVE vs 15% at BARE_SOIL).
          </div>
        </div>
      </div>

      {/* Debate & Challenge buttons */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        <div style={{ display: "flex", gap: "6px" }}>
          <button onClick={() => onAskBrain(`Provide a deep agronomic analysis of the ${surfaceType} surface. Include zone-level interpretation, confidence discussion, and alternative hypotheses.`)}
            style={{ flex: 1, padding: "8px", borderRadius: "8px", border: "1px solid rgba(99,102,241,0.2)", background: "rgba(99,102,241,0.08)", color: "#a5b4fc", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}>
            🧪 Deep Analysis
          </button>
          <button onClick={() => onAskBrain(`What are the limitations and edge cases of the current ${surfaceType} model output? What alternative interpretations should I consider?`)}
            style={{ flex: 1, padding: "8px", borderRadius: "8px", border: "1px solid rgba(251,191,36,0.2)", background: "rgba(251,191,36,0.08)", color: "#fbbf24", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}>
            ⚖️ Challenge
          </button>
        </div>
        <button onClick={() => onAskBrain(`Compare the water stress, nutrient stress, salinity stress, and disease pressure surfaces. Are there correlations that suggest a common root cause? Could the salinity be amplifying the water stress (osmotic effect)?`)}
          style={{ padding: "8px", borderRadius: "8px", border: "1px solid rgba(248,113,113,0.2)", background: "rgba(248,113,113,0.06)", color: "#f87171", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}>
          🔬 Cross-Surface Correlation Analysis
        </button>
        <button onClick={() => onAskBrain(`Using the yield penalty and value-at-risk surfaces, estimate the total field-level economic impact of current stress conditions. What interventions have the highest ROI?`)}
          style={{ padding: "8px", borderRadius: "8px", border: "1px solid rgba(52,211,153,0.2)", background: "rgba(52,211,153,0.06)", color: "#34d399", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}>
          💰 Economic Impact Analysis
        </button>
      </div>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────
function StatCell({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="sev-stat-cell" style={{ background: "rgba(0,0,0,0.3)", borderRadius: "6px", padding: "8px", textAlign: "center", border: "1px solid rgba(71,85,105,0.08)" }}>
      <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
      <div style={{ fontSize: "13px", color, fontFamily: "monospace", fontWeight: 700, marginTop: "2px" }}>{value}</div>
    </div>
  );
}

function QualityRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}>
      <span style={{ fontSize: "12px", color: "#94a3b8" }}>{label}</span>
      <span style={{ fontSize: "12px", color: ok ? "#4ade80" : "#fbbf24", fontFamily: "monospace", fontWeight: 600 }}>{value}</span>
    </div>
  );
}
