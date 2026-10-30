"use client";

import { useMemo } from "react";
import { useLayer10, type Layer10Result, type ZoneData, type ExplainabilityPack } from "@/hooks/useLayer10";
import {
  getRenderableZonesForMode,
  MODE_ZONE_SURFACE_MAP,
  type MapMode,
  sanitizeRecommendedAction,
  resolveRiskNarrative,
  type RiskNarrative
} from "@/lib/agribrain/plot-map-evidence-state";
import { getRenderAuthorization, normalizeMode } from "@/lib/agribrain/source-policy-display-resolver";
import {
  isRenderedMaterialization,
  RENDER_AUTHORIZATION_VERSION,
} from "@/lib/agribrain/render-materialization";
import type { EngineStatus } from "@/hooks/usePlotIntelligence";

import type { Finding } from "@/lib/agribrain/parcel-assessment-contract";

interface FarmerViewProps {
  data: Layer10Result;
  activeMode: string;
  surfaceType: string;
  explainPack: ExplainabilityPack | undefined;
  engines: EngineStatus[];
  topFindings?: Finding[];
  assimilation: any;
  onAskBrain: (query: string) => void;
}

interface GatewayEvidenceState {
  status?: string;
  last_successful_observation_at?: string;
  source_snapshot_id?: string;
  data_age_days?: number;
  refresh_attempted_at?: string;
  refresh_status?: string;
}

function findStaleGatewayState(rawData: Record<string, unknown> | undefined): GatewayEvidenceState | undefined {
  for (const value of Object.values(rawData || {})) {
    if (!value || typeof value !== "object") continue;
    const state = (value as Record<string, unknown>).gateway_evidence_state;
    if (!state || typeof state !== "object") continue;
    const typed = state as GatewayEvidenceState;
    if (typed.status === "stale_available") return typed;
  }
  return undefined;
}

// ── Helpers (derive from real data, no hardcoded thresholds fabrication) ─────

function vigorLabel(ndvi: number | null): { text: string; color: string } {
  if (ndvi == null) return { text: "No vigor data", color: "#64748b" };
  if (ndvi >= 0.6) return { text: "Strong growth", color: "#4ade80" };
  if (ndvi >= 0.35) return { text: "Moderate growth", color: "#fbbf24" };
  return { text: "Weak growth", color: "#f87171" };
}

function waterLabel(deficit: number | null): { text: string; color: string } {
  if (deficit == null) return { text: "No water data", color: "#64748b" };
  const abs = Math.abs(deficit);
  if (abs < 5) return { text: "Low modelled deficit", color: "#4ade80" };
  if (abs < 15) return { text: "Getting dry", color: "#fbbf24" };
  return { text: "Water deficit indicated — verify", color: "#f87171" };
}

function consistencyLabel(std: number | null): { text: string; color: string } {
  if (std == null) return { text: "No consistency data", color: "#64748b" };
  if (std < 0.05) return { text: "Very even growth", color: "#4ade80" };
  if (std < 0.1) return { text: "Mostly even", color: "#fbbf24" };
  return { text: "Patchy — check zones", color: "#f87171" };
}

// ── Inline SVG Spark Line (7-day NDVI trend) ────────────────────────────
function SparkLine({ values, color, label }: { values: number[]; color: string; label: string }) {
  if (!values || values.length < 2) return null;
  const mn = Math.min(...values), mx = Math.max(...values);
  const rng = mx - mn || 0.01;
  const w = 120, h = 28, pad = 2;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - mn) / rng) * (h - pad * 2);
    return `${x},${y}`;
  }).join(" ");
  const last = values[values.length - 1];
  const delta = last - values[0];
  const arrow = delta > 0.005 ? "↑" : delta < -0.005 ? "↓" : "→";
  return (
    <div className="sfv-sparkline" style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 10px", borderRadius: "8px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.12)" }}>
      <svg width={w} height={h} style={{ flexShrink: 0 }}>
        <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
        <circle cx={parseFloat(pts.split(" ").pop()!.split(",")[0])} cy={parseFloat(pts.split(" ").pop()!.split(",")[1])} r="2.5" fill={color} />
      </svg>
      <div style={{ fontSize: "12px", color: "#94a3b8", lineHeight: 1.3 }}>
        <div style={{ fontWeight: 700 }}>{label}</div>
        <span style={{ color, fontWeight: 600 }}>{arrow} {last.toFixed(3)}</span>
      </div>
    </div>
  );
}

// ── Stacked Risk Decomposition Bar ──────────────────────────────────────
function RiskDecomposition({ data, narrative }: { data: Layer10Result; narrative: RiskNarrative }) {
  const waterSurf = data.surfaces.find(s => s.type === "WATER_STRESS_PROB");
  const nutSurf = data.surfaces.find(s => s.type === "NUTRIENT_STRESS_PROB");
  const disSurf = data.surfaces.find(s => s.type === "BIOTIC_PRESSURE");
  const salSurf = data.surfaces.find(s => s.type === "SALINITY_STRESS");
  const mean = (s: any) => {
    if (!s?.values) return 0;
    const v = s.values.flat().filter((x: any) => x != null);
    return v.length ? v.reduce((a: number, b: number) => a + b, 0) / v.length : 0;
  };
  const w = mean(waterSurf), n = mean(nutSurf), d = mean(disSurf), sal = mean(salSurf);
  const total = w + n + d + sal || 1;
  const items = [
    { label: "Water", frac: w / total, abs: w, color: "#38bdf8" },
    { label: "Nutrient", frac: n / total, abs: n, color: "#facc15" },
    { label: "Disease", frac: d / total, abs: d, color: "#f97316" },
    ...(sal > 0.05 ? [{ label: "Salinity", frac: sal / total, abs: sal, color: "#14b8a6" }] : []),
  ];
  
  // Find dominant risk factor
  const maxVal = Math.max(w, n, d, sal);
  let dominantMsg = "";
  if (sal > 0.3 && sal === maxVal) {
    dominantMsg = "🧂 Soil salinity is the dominant risk — salt accumulation is limiting root water uptake and reducing yield.";
  } else if (w > n && w > d) {
    dominantMsg = "💧 Water stress is the dominant risk factor — check irrigation schedule.";
  } else if (n > w && n > d) {
    dominantMsg = "🧪 Nutrient deficiency leads risk — consider fertilizer application.";
  } else if (d > 0.2) {
    dominantMsg = "🦠 Disease pressure is elevated — scout for symptoms.";
  } else {
    if (narrative.balancedAllowed) {
      dominantMsg = "✅ No dominant risk factor — field is balanced.";
    } else {
      dominantMsg = `⚠️ ${narrative.message}`;
    }
  }

  return (
    <div className="sfv-card" style={{ padding: "10px 12px", borderRadius: "8px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.12)" }}>
      <div style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", marginBottom: "6px" }}>Risk Breakdown</div>
      <div style={{ display: "flex", height: "6px", borderRadius: "3px", overflow: "hidden", marginBottom: "6px" }}>
        {items.map(it => <div key={it.label} style={{ width: `${Math.max(it.frac * 100, 2)}%`, background: it.color, transition: "width 0.4s" }} />)}
      </div>
      <div style={{ display: "flex", gap: "8px", fontSize: "12px", flexWrap: "wrap" }}>
        {items.map(it => <span key={it.label} style={{ color: it.color, fontWeight: 600 }}>● {it.label} {(it.abs * 100).toFixed(0)}%</span>)}
      </div>
      <div style={{ fontSize: "12px", color: "#64748b", marginTop: "6px", lineHeight: 1.5 }}>
        {dominantMsg}
      </div>
    </div>
  );
}

// ── Phenology Phase Badge ───────────────────────────────────────────────
function PhenologyBadge() {
  const l10 = useLayer10();
  const resolved = l10.evidenceState?.resolvedPhenology;
  if (!resolved) return null;

  const stage = resolved.stage || "UNKNOWN";
  const stageMap: Record<string, { icon: string; label: string; tip: string }> = {
    BARE_SOIL: { icon: "🟤", label: "Bare Soil", tip: "Pre-planting. Focus on soil preparation and moisture conservation." },
    EMERGENCE: { icon: "🌱", label: "Emergence", tip: "Seedlings are vulnerable. Protect from pests and ensure even moisture." },
    VEGETATIVE: { icon: "🌿", label: "Vegetative", tip: "Rapid growth phase. Peak nutrient demand — ensure adequate nitrogen." },
    REPRODUCTIVE: { icon: "🌾", label: "Reproductive", tip: "Critical window! Water stress now directly reduces grain count." },
    SENESCENCE: { icon: "🍂", label: "Senescence", tip: "Natural decline. Reduce inputs and plan harvest timing." },
    HARVESTED: { icon: "✅", label: "Harvested", tip: "Post-harvest. Consider cover cropping for soil health." },
    UNKNOWN: { icon: "❓", label: "Unknown", tip: resolved.userLabel },
  };
  const info = stageMap[stage] || stageMap.UNKNOWN;

  if (resolved.conflict) {
    return (
      <div className="sfv-card animate-pulse" style={{ display: "flex", alignItems: "center", gap: "8px", padding: "10px 12px", borderRadius: "8px", background: "rgba(239, 68, 68, 0.05)", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
        <span style={{ fontSize: "1.4rem" }}>⚠️</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: "11px", color: "#f87171", fontWeight: 700, textTransform: "uppercase" }}>Growth Stage Conflict</div>
          <div style={{ fontSize: "12px", color: "#fca5a5", marginTop: "2px", lineHeight: 1.4 }}>{resolved.userLabel}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="sfv-card" style={{ display: "flex", alignItems: "center", gap: "8px", padding: "10px 12px", borderRadius: "8px", background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.12)" }}>
      <span style={{ fontSize: "1.4rem" }}>{info.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>Growth Stage</div>
        <div style={{ fontSize: "14px", color: "#e2e8f0", fontWeight: 700 }}>{info.label}</div>
        <div style={{ fontSize: "12px", color: "#a5b4fc", marginTop: "2px", lineHeight: 1.4 }}>{info.tip}</div>
        {resolved.receiptValid && resolved.posteriorHash && (
          <div style={{ fontSize: "9px", color: "#64748b", marginTop: "3px", fontFamily: "monospace" }}>
            Layer 2 {resolved.authority} · {resolved.posteriorHash.slice(0, 12)}
          </div>
        )}
      </div>
    </div>
  );
}

// ── VPD Heat Alert Badge ────────────────────────────────────────────────
function VPDAlert({ data }: { data: Layer10Result }) {
  const vpd = data.surfaces.find(s => s.type === "VPD_STRESS");
  if (!vpd) return null;
  const prov = (vpd.provenance as any) || {};
  const vpdKpa = prov.vpd_kpa;
  if (vpdKpa == null || vpdKpa < 1.5) return null;

  const physiologicalClaimAllowed = prov.physiological_claim_allowed === true;
  const humiditySource = prov.humidity_source || "unknown";
  const cropApplicability = prov.crop_applicability || "applicable";

  const severity = vpdKpa > 3.0 ? "Severe" : vpdKpa > 2.0 ? "Moderate" : "Mild";
  const color = vpdKpa > 3.0 ? "#ef4444" : vpdKpa > 2.0 ? "#f97316" : "#facc15";

  const titleText = physiologicalClaimAllowed
    ? `${severity} Heat Stress — VPD ${vpdKpa.toFixed(1)} kPa`
    : `${severity} Atmospheric Demand — VPD ${vpdKpa.toFixed(1)} kPa`;

  let bodyText = "";
  if (physiologicalClaimAllowed) {
    bodyText = vpdKpa > 3.0
      ? "Stomata are closing even with adequate irrigation. Crops cannot cool themselves. Consider shade netting or misting if possible."
      : vpdKpa > 2.0
      ? "Transpiration is elevated — plants are losing water faster than roots can supply. Monitor wilting and increase irrigation frequency."
      : "Atmospheric drying is slightly above normal. Keep irrigation on schedule.";
  } else {
    bodyText = vpdKpa > 3.0
      ? "Atmospheric drying demand is very high. Crop-specific physiological impact depends on growth stage and crop type."
      : vpdKpa > 2.0
      ? "Atmospheric drying demand is elevated. Monitor crop condition and soil moisture levels."
      : "Atmospheric drying is slightly above normal.";
  }

  const footerExtra = humiditySource === "imputed_default" ? " (humidity estimated)" : "";

  return (
    <div style={{ padding: "8px 10px", borderRadius: "8px", background: `${color}08`, border: `1px solid ${color}20` }}>
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
        <span style={{ fontSize: "1.1rem" }}>🌡️</span>
        <span style={{ fontSize: "12px", color, fontWeight: 700 }}>{titleText}</span>
      </div>
      <div style={{ fontSize: "10px", color: "#94a3b8", lineHeight: 1.4 }}>
        {bodyText}
      </div>
      <div style={{ fontSize: "9px", color: "#475569", marginTop: "4px" }}>
        VPD = atmospheric drying power (Tetens eq., FAO-56){footerExtra}
      </div>
    </div>
  );
}

// ── Why This Matters Card ───────────────────────────────────────────────
function WhyCard({ icon, title, why }: { icon: string; title: string; why: string }) {
  return (
    <div className="sfv-why-card" style={{ display: "flex", gap: "6px", padding: "8px 10px", borderRadius: "6px", background: "rgba(250,204,21,0.04)", border: "1px solid rgba(250,204,21,0.08)" }}>
      <span style={{ fontSize: "0.9rem", flexShrink: 0 }}>{icon}</span>
      <div>
        <div style={{ fontSize: "11px", color: "#facc15", fontWeight: 700 }}>{title}</div>
        <div style={{ fontSize: "12px", color: "#94a3b8", lineHeight: 1.5 }}>{why}</div>
      </div>
    </div>
  );
}

// ── Condition Card ──────────────────────────────────────────────────────
function ConditionCard({ icon, title, label, color, value, detail }: { icon: string; title: string; label: string; color: string; value?: string; detail?: string }) {
  return (
    <div className="sfv-condition-card" style={{ background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.15)", borderRadius: "10px", padding: "10px 12px", display: "flex", alignItems: "center", gap: "10px" }}>
      <span style={{ fontSize: "1.3rem" }}>{icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>{title}</div>
        <div style={{ fontSize: "14px", color, fontWeight: 700 }}>{label}</div>
        {detail && <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px", lineHeight: 1.35 }}>{detail}</div>}
      </div>
      {value && <div style={{ fontSize: "13px", color: "#e2e8f0", fontFamily: "monospace", fontWeight: 600 }}>{value}</div>}
    </div>
  );
}

// ── Farmer-Friendly Zone Explanations ───────────────────────────────────
const FARMER_ZONE_EXPLAINER: Record<string, { icon: string; why: string; todo: string }> = {
  LOW_VIGOR: {
    icon: "🟤",
    why: "This area has a lower vegetation indicator than nearby areas. Water, nutrient, pest and soil explanations are possibilities, not confirmed causes.",
    todo: "Walk this area and check: Are leaves yellowing? (nutrient issue). Are they wilting? (water issue). Are there spots or holes? (pest issue). Then talk to AgriBrain for a targeted solution.",
  },
  WATER_STRESS: {
    icon: "💧",
    why: "This zone shows an indicator associated with water stress. The map alone does not confirm root-zone moisture or the cause.",
    todo: "Inspect soil moisture and irrigation distribution in this zone. Confirm the cause before choosing an irrigation amount or schedule.",
  },
  NUTRIENT_RISK: {
    icon: "🧪",
    why: "A nutrient-risk indicator is elevated in this zone. The cause and affected nutrient have not been established by the map alone.",
    todo: "Take a representative soil or leaf tissue sample and review the result with an agronomist. A fertilizer dose requires a qualified canonical prescription.",
  },
  DISEASE_RISK: {
    icon: "🦠",
    why: "This area has a disease-risk signal. A risk map does not identify a pathogen or establish that disease is present.",
    todo: "Inspect leaves for lesions or unusual discoloration and obtain a diagnosis before selecting any treatment.",
  },
  SALINITY_RISK: {
    icon: "🧂",
    why: "This area has a salinity-risk signal. Salt concentration and its cause require field measurements before being treated as established.",
    todo: "Check for visible salt deposits and confirm soil or irrigation-water salinity with appropriate tests. Any leaching plan requires measured drainage and a qualified water-management prescription.",
  },
  BLOCKED_ZONE: {
    icon: "🚫",
    why: "This zone has been flagged as blocked — a mild-severity area where the existing conditions are being monitored rather than requiring immediate intervention.",
    todo: "Keep monitoring. If conditions change or worsen, this zone will be escalated. No immediate action required.",
  },
};

function _getFarmerExplain(zone: ZoneData) {
  const exact = FARMER_ZONE_EXPLAINER[zone.zone_type];
  if (exact) return exact;
  for (const driver of zone.top_drivers) {
    const u = driver.toUpperCase();
    if (u.includes("WATER") || u.includes("DROUGHT")) return FARMER_ZONE_EXPLAINER.WATER_STRESS;
    if (u.includes("NUTRI") || u.includes("NITROGEN")) return FARMER_ZONE_EXPLAINER.NUTRIENT_RISK;
    if (u.includes("DISEASE") || u.includes("BIOTIC")) return FARMER_ZONE_EXPLAINER.DISEASE_RISK;
    if (u.includes("NDVI") || u.includes("VIGOR") || u.includes("VEGETATION")) return FARMER_ZONE_EXPLAINER.LOW_VIGOR;
  }
  return { icon: "📍", why: "This area differs in the available indicator. The underlying cause is not yet established.", todo: "Walk this zone and compare with a healthy area nearby. Note any differences in soil, moisture, or plant appearance." };
}

// ── Zone Alert Card (Farmer — rich intelligence) ────────────────────────
function ZoneAlertCard({ zone, onAsk }: { zone: ZoneData; onAsk: (q: string) => void }) {
  const sevColor = zone.severity > 0.6 ? "#f87171" : zone.severity > 0.3 ? "#fbbf24" : "#4ade80";
  const explain = _getFarmerExplain(zone);
  return (
    <div className="sfv-zone-card" style={{ background: "rgba(15,23,42,0.5)", border: `1px solid ${sevColor}25`, borderRadius: "10px", padding: "12px", borderLeft: `3px solid ${sevColor}` }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
        <span style={{ fontSize: "1.2rem" }}>{explain.icon}</span>
        <span style={{ fontSize: "14px", color: "#e2e8f0", fontWeight: 700, flex: 1 }}>{zone.label || zone.zone_id}</span>
        <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "6px", background: `${sevColor}15`, color: sevColor, fontWeight: 700 }}>
          {zone.severity > 0.6 ? "Urgent" : zone.severity > 0.3 ? "Watch" : "Low"}
        </span>
      </div>

      {/* Why this is happening */}
      <div className="sfv-zone-why" style={{ padding: "8px 10px", borderRadius: "8px", background: "rgba(99,102,241,0.04)", border: "1px solid rgba(99,102,241,0.08)", marginBottom: "8px" }}>
        <div style={{ fontSize: "11px", color: "#a5b4fc", fontWeight: 700, marginBottom: "4px" }}>🔍 Why this is happening</div>
        <div style={{ fontSize: "12px", color: "#cbd5e1", lineHeight: 1.6 }}>{explain.why}</div>
      </div>

      {/* What to do */}
      <div className="sfv-zone-todo" style={{ padding: "8px 10px", borderRadius: "8px", background: "rgba(34,197,94,0.04)", border: "1px solid rgba(34,197,94,0.1)", marginBottom: "8px" }}>
        <div style={{ fontSize: "11px", color: "#4ade80", fontWeight: 700, marginBottom: "4px" }}>✅ What to do</div>
        <div style={{ fontSize: "12px", color: "#cbd5e1", lineHeight: 1.6 }}>{explain.todo}</div>
      </div>

      {/* Quick facts */}
      <div style={{ display: "flex", gap: "8px", fontSize: "11px", color: "#64748b", marginBottom: "8px", flexWrap: "wrap" }}>
        <span>📐 {(zone.area_fraction * 100).toFixed(0)}% of your field</span>
        {zone.confidence > 0 && <span>· 🎯 {(zone.confidence * 100).toFixed(0)}% sure</span>}
        {zone.evidence_age_days != null && <span>· 📅 {zone.evidence_age_days}d since last check</span>}
      </div>

      {/* Unqualified free-text linked actions are intentionally withheld. */}

      {/* Solution buttons */}
      <div style={{ display: "flex", gap: "6px" }}>
        <button onClick={() => onAsk(`My ${zone.label || zone.zone_id} zone shows ${zone.zone_type.replace(/_/g, ' ').toLowerCase()} with ${(zone.severity*100).toFixed(0)}% severity. Drivers are: ${zone.top_drivers.join(', ')}. What field checks would help verify this signal? Do not suggest a numerical treatment without an applicable canonical prescription.`)}
          style={{ flex: 1, padding: "8px 12px", borderRadius: "6px", border: "none", background: "rgba(99,102,241,0.12)", color: "#a5b4fc", fontSize: "12px", fontWeight: 700, cursor: "pointer" }}>
          🧠 Verify This Zone
        </button>
        <button onClick={() => onAsk(`Is the ${zone.zone_type.replace(/_/g, ' ').toLowerCase()} in zone ${zone.label || zone.zone_id} really a problem? What if it's a false alarm? What should I check in the field to confirm?`)}
          style={{ padding: "8px 10px", borderRadius: "6px", border: "1px solid rgba(251,191,36,0.2)", background: "rgba(251,191,36,0.04)", color: "#fbbf24", fontSize: "12px", fontWeight: 700, cursor: "pointer" }}>
          🤔 Verify
        </button>
      </div>
    </div>
  );
}

// ── Main Farmer View ────────────────────────────────────────────────────
export default function SidebarFarmerView({
  data,
  activeMode,
  surfaceType,
  explainPack,
  engines,
  topFindings = [],
  assimilation,
  onAskBrain,
}: FarmerViewProps) {
  // Extract real values from engine data
  const l0 = engines.find(e => e.id === "L0");
  const l2 = engines.find(e => e.id === "L2");
  const l3 = engines.find(e => e.id === "L3");

  // Whole-field vigor must come from the field-supported NDVI raster only.
  // A Layer 2 Sentinel index is a point sample at the request coordinate and
  // must never be substituted for a missing field histogram.
  const ndviCandidates = data.histograms.field.filter(h => h.surface_type === "NDVI_CLEAN");
  const ndviHist = ndviCandidates.find(h => h.region_id === "field_combined_display")
    ?? ndviCandidates.find(h => h.region_id === "field")
    ?? null;
  const ndviMean = ndviHist?.mean ?? null;
  const ndviStd = ndviHist?.std ?? null;
  const pointNdvi = l2?.data?.ndvi_source === "sentinel2" && l2.data.ndvi_mean != null
    ? Number(l2.data.ndvi_mean)
    : null;
  const pointObservationTime = String(l2?.data?.observation_time || l2?.lastUpdate || "unknown date");
  const pointCoordinate = l2?.data?.support_coordinate && typeof l2.data.support_coordinate === "object"
    ? l2.data.support_coordinate as Record<string, unknown>
    : null;
  const pointSupportLabel = pointCoordinate?.lat != null && pointCoordinate?.lng != null
    ? `${Number(pointCoordinate.lat).toFixed(4)}, ${Number(pointCoordinate.lng).toFixed(4)}`
    : "query coordinate unavailable";
  const fieldWindow = Array.isArray(data.source_window) && data.source_window.length === 2
    ? `${data.source_window[0]} to ${data.source_window[1]}`
    : "source window unavailable";
  const deficitMm = l3?.data?.deficit_mm != null ? Number(l3.data.deficit_mm) : null;
  const staleSourceState = findStaleGatewayState(data.rawData);

  // A composite score requires a qualified canonical health metric. Do not
  // invent water or vegetation defaults, whole-field scores, or confidence bands.
  const missingHealthEvidence = [
    ndviMean == null ? "field NDVI" : null,
    ndviStd == null ? "NDVI variability" : null,
    deficitMm == null ? "water balance" : null,
  ].filter((name): name is string => !!name);

  // Zones relevant to current mode — filter by active surface type
  const l10Context = useLayer10();
  const activeZoneSurfaceType = MODE_ZONE_SURFACE_MAP[activeMode as MapMode] || "";
  const renderableZones = getRenderableZonesForMode({
    zones: data.zones || [],
    activeMode: activeMode as MapMode,
    activeZoneSurfaceType,
    detailMode: "farmer",
    materialization: l10Context.renderPlan.baseMaterialization,
    gridHeight: l10Context.renderPlan.baseMaterialization.gridHeight ?? undefined,
    gridWidth: l10Context.renderPlan.baseMaterialization.gridWidth ?? undefined,
  });
  const relevantZones = renderableZones.filter((z) => z.severity > 0.2);

  // Vigor / Water helpers
  const vigor = vigorLabel(ndviMean);
  const water = waterLabel(deficitMm);
  const consistency = consistencyLabel(ndviStd);

  const evidenceState = l10Context.evidenceState;
  const vigorTxt = vigor.text;
  const riskNarrative = useMemo(() => {
    return resolveRiskNarrative({
      evidenceState,
      ndviMean,
      vigorText: vigorTxt,
    });
  }, [evidenceState, ndviMean, vigorTxt]);

  const sanitizedAction = useMemo(() => {
    const message = sanitizeRecommendedAction(explainPack?.recommended_action || null, evidenceState);
    // Free-text explainability is not a signed, unit-qualified prescription.
    if (!message.text) return message;
    return {
      ...message,
      text: "Review map evidence and verify field conditions. Treatment quantities require a qualified canonical prescription.",
      actionLevel: "scout" as const,
      suppressed: true,
      reason: "Unqualified free-text treatment advice withheld",
    };
  }, [explainPack?.recommended_action, evidenceState]);

  // ── BC.10.19 P0.6 — Render Authorization Gate ────────────────────────────
  // Diagnosis blocks (health gauge, mode insight, advisory card, zone alerts,
  // risk decomposition, scenario pack) are gated behind a valid authority proof.
  // The frontend MUST NOT promote backend authority — it may only demote.
  // If the payload lacks the current canonical render-authorization version OR
  // render_authorizations is empty/missing, we suppress diagnosis and show a
  // calibration notice so the user knows data is pending re-authorisation.
  const isRasterCommitted = useMemo(() => {
    return isRenderedMaterialization(l10Context.renderPlan.baseMaterialization, surfaceType);
  }, [l10Context.renderPlan, surfaceType]);

  const hasCurrentAuthorizationContract = useMemo(() => {
    const authVersion = l10Context.data?.render_authorization_version;
    const authMap = l10Context.data?.render_authorizations;
    if (authVersion !== RENDER_AUTHORIZATION_VERSION) return false;
    if (!authMap || typeof authMap !== "object") return false;
    if (Object.keys(authMap).length === 0) return false;
    return true;
  }, [
    l10Context.data?.render_authorization_version,
    l10Context.data?.render_authorizations,
  ]);

  // ── Mode-Specific Authorization Check ────────────────────────────────────
  // Verify that the active mode is authorized for diagnosis by checking the
  // render authorization map. Returns false if mode is not in the map (deny-by-default).
  const isModeAuthorizedForDiagnosis = useMemo(() => {
    if (!isRasterCommitted || !hasCurrentAuthorizationContract) return false;
    const renderAuths = l10Context.data?.render_authorizations;
    if (!renderAuths || typeof renderAuths !== "object") return false;
    const policy = l10Context.canopySource || "satellite";
    const role = "inspector";
    const auth = getRenderAuthorization(surfaceType, policy, normalizeMode(activeMode), role, renderAuths);
    return l10Context.canInterpretDiagnostically === true
      && !!auth?.authorized
      && auth.inspectorAllowed === true;
  }, [isRasterCommitted, hasCurrentAuthorizationContract, activeMode, surfaceType, l10Context.data?.render_authorizations, l10Context.canopySource, l10Context.canInterpretDiagnostically]);

  // Delta / trend from actual delta histogram
  const delta = data.histograms.delta.find(d => d.surface_type === surfaceType);
  const trendDir = delta?.shift_direction || null;

  // ── Agronomic velocity guard (Fix 4) ─────────────────────────────────────
  // NDVI change rates are physically bounded by plant biology:
  //   Maximum credible NDVI growth rate ≈ 0.025–0.030/day (rapid vegetative phase)
  //   Any value above 0.05/day is definitively an artifact.
  //
  // A large Kalman bridge correction produces an apparent "trend" because the
  // baseline (pre-correction surface) had corrupted/zeroed values. The delta
  // histogram then shows the gap between corrected and historical data as if
  // it were a real crop change. We must detect and suppress this.
  //
  // Detection: if mean_change / days_elapsed > 0.035/day → flag as artifact.
  const NDVI_MAX_DAILY_VELOCITY = 0.035; // biological maximum, any crop, any climate
  const isTrendArtifact = (() => {
    if (!delta || !delta.mean_change || !delta.date_from) return false;
    const msPerDay = 86_400_000;
    const msElapsed = Date.now() - new Date(delta.date_from).getTime();
    const daysElapsed = Math.max(1, msElapsed / msPerDay);
    const dailyVelocity = Math.abs(delta.mean_change) / daysElapsed;
    // Also check provenance for explicit Kalman bridge correction flag
    const provenance = data.provenance as any;
    const bridgeGap = provenance?.kalman_bridge?.correction_gap ?? 0;
    const isBridgeCorrected = bridgeGap > 0.15;
    return dailyVelocity > NDVI_MAX_DAILY_VELOCITY || isBridgeCorrected;
  })();

  const trendLabel = !isTrendArtifact
    ? (trendDir === "IMPROVING" ? "↑ Improving"
       : trendDir === "DECLINING" ? "↓ Declining"
       : trendDir === "STABLE" ? "→ Stable"
       : null)
    : null; // suppress artifact trends entirely
  const trendColor = trendDir === "IMPROVING" ? "#4ade80" : trendDir === "DECLINING" ? "#f87171" : "#fbbf24";

  // Expose artifact flag for UI — show recalibration notice instead of misleading trend
  const showRecalibrationNotice = isTrendArtifact && delta != null && delta.mean_change !== 0;

  // Extract L2 curve data for spark line
  const ndvi7dBack: number[] = (l2?.data as any)?.ndvi_7d_back || [];

  // ── Mode-specific surface stats ──────────────────────────────────────────
  // Extract the active surface's histogram so each mode shows its own primary metric
  const activeSurfHist = data.histograms.field.find(h => h.surface_type === surfaceType);
  const activeSurfMean = activeSurfHist?.mean ?? null;
  const activeSurfStd = activeSurfHist?.std ?? null;
  const activeSurf = data.surfaces.find(s => s.type === surfaceType);

  // Mode-specific labels and interpretations
  const modeInsight = isModeAuthorizedForDiagnosis ? (() => {
    switch (activeMode) {
      case "water_stress": {
        const prob = activeSurfMean;
        if (prob == null) return { icon: "💧", title: "Water Stress Probability", label: "No data", color: "#64748b", value: undefined, why: null };
        const pct = (prob * 100).toFixed(0);
        const label = prob > 0.6 ? "High stress risk" : prob > 0.3 ? "Moderate stress" : "Low stress";
        const color = prob > 0.6 ? "#f87171" : prob > 0.3 ? "#fbbf24" : "#4ade80";
        return { icon: "💧", title: "Water Stress Probability", label, color, value: `${pct}%`,
          why: prob > 0.3 ? `${pct}% probability of water stress across your field. The soil moisture balance indicates ${prob > 0.6 ? "critical" : "developing"} deficit conditions. Check irrigation systems and soil moisture sensors.` : null };
      }
      case "nutrient_risk": {
        const prob = activeSurfMean;
        if (prob == null) return { icon: "🧪", title: "Nutrient Stress Probability", label: "No data", color: "#64748b", value: undefined, why: null };
        const pct = (prob * 100).toFixed(0);
        const label = prob > 0.5 ? "High deficiency risk" : prob > 0.25 ? "Moderate risk" : "Low modelled nutrient risk";
        const color = prob > 0.5 ? "#f87171" : prob > 0.25 ? "#fbbf24" : "#4ade80";
        return { icon: "🧪", title: "Nutrient Stress Probability", label, color, value: `${pct}%`,
          why: prob > 0.25 ? `${pct}% probability of nutrient limitation. The indicator warrants nutrient status verification before any diagnosis or treatment. Consider tissue sampling in flagged zones.` : null };
      }
      case "salinity": {
        const prob = activeSurfMean;
        if (prob == null) return { icon: "🧂", title: "Soil Salinity Stress", label: "No data", color: "#64748b", value: undefined, why: null };
        const pct = (prob * 100).toFixed(0);
        const label = prob > 0.6 ? "High salinity risk" : prob > 0.3 ? "Moderate salinity risk" : prob > 0.15 ? "Mild salinity risk" : "Low salinity risk";
        const color = prob > 0.6 ? "#ef4444" : prob > 0.3 ? "#f59e0b" : prob > 0.15 ? "#22d3ee" : "#14b8a6";
        return { icon: "🧂", title: "Soil Salinity Stress", label, color, value: `${pct}%`,
          why: prob > 0.15
            ? `${pct}% salinity stress probability. ${prob > 0.6
                ? "Elevated salinity risk should prompt soil and irrigation-water testing; leaching requires measured drainage and qualified guidance."
                : prob > 0.3
                ? "A salinity indicator warrants soil and irrigation-water testing. Do not select a leaching amount without drainage evidence and qualified guidance."
                : "A mild salinity-risk signal should be checked against measured soil and irrigation-water salinity."}`
            : null };
      }
      case "veg_attention": {
        const dev = activeSurfMean;
        if (dev == null) return { icon: "🎯", title: "Vegetation Deviation", label: "No data", color: "#64748b", value: undefined, why: null };
        const label = dev < -0.05 ? "Below expected" : dev > 0.05 ? "Above expected" : "On track";
        const color = dev < -0.05 ? "#f87171" : dev > 0.05 ? "#4ade80" : "#fbbf24";
        return { icon: "🎯", title: "Vegetation Deviation", label, color, value: dev.toFixed(3),
          why: Math.abs(dev) > 0.05 ? `Vegetation is ${dev < 0 ? "underperforming" : "outperforming"} the baseline by ${Math.abs(dev).toFixed(3)}. ${dev < 0 ? "This may indicate emerging stress or damage." : "Growth conditions are favorable."}` : null };
      }
      case "composite_risk": {
        const risk = activeSurfMean;
        if (risk == null) return { icon: "⚠️", title: "Composite Risk Index", label: "No data", color: "#64748b", value: undefined, why: null };
        const pct = (risk * 100).toFixed(0);
        const label = risk > 0.6 ? "High overall risk" : risk > 0.3 ? "Moderate risk" : "Low risk";
        const color = risk > 0.6 ? "#f87171" : risk > 0.3 ? "#fbbf24" : "#4ade80";
        return { icon: "⚠️", title: "Composite Risk", label, color, value: `${pct}%`,
          why: risk > 0.3 ? `Combined risk from water, nutrient, disease, and salinity factors is at ${pct}%. Multiple stressors may be interacting.` : null };
      }
      case "uncertainty": {
        const unc = activeSurfMean;
        if (unc == null) return { icon: "🔍", title: "Data Uncertainty", label: "No data", color: "#64748b", value: undefined, why: null };
        const label = unc > 0.3 ? "High uncertainty" : unc > 0.15 ? "Moderate uncertainty" : "Good confidence";
        const color = unc > 0.3 ? "#f87171" : unc > 0.15 ? "#fbbf24" : "#4ade80";
        return { icon: "🔍", title: "Data Uncertainty", label, color, value: `σ ${unc.toFixed(3)}`,
          why: unc > 0.15 ? `Uncertainty is ${unc > 0.3 ? "high" : "moderate"} — predictions in flagged areas should be field-verified before acting.` : null };
      }
      default: return null; // canopy/vegetation use the standard layout
    }
  })() : null;

  // Highlight which condition card matches the active mode
  const highlightMode = activeMode;

  // ── BC.10.19 P0.6 — Authorization Pending Notice ───────────────────────
  // No browser render receipt means there is no committed spatial evidence.
  if (!isRasterCommitted) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {/* Phenology Badge is always safe to show (source-agnostic) */}
        <PhenologyBadge />
        {/* Authority calibration notice */}
        <div style={{
          padding: "16px",
          borderRadius: "10px",
          background: "rgba(71,85,105,0.08)",
          border: "1px solid rgba(71,85,105,0.20)",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          alignItems: "center",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "22px", lineHeight: 1 }}>🔄</div>
          <div style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8" }}>Spatial evidence unavailable</div>
          <div style={{ fontSize: "11px", color: "#64748b", lineHeight: 1.5 }}>
            The active surface was not placed on the map, so its zones, pixel statistics,
            and diagnosis cards are hidden. Reason: {(l10Context.renderPlan.baseMaterialization.reason || "missing render authorization").replace(/_/g, " ")}.
          </div>
        </div>
        {/* Ask button is always available */}
        <button onClick={() => onAskBrain("The current map evidence is not render-authorized. Do not diagnose or recommend actions. Explain which evidence/proof is missing and what field verification steps are needed.")}
          style={{ width: "100%", padding: "10px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.15))", color: "#a5b4fc", fontSize: "12px", fontWeight: 700, cursor: "pointer", transition: "all 0.15s" }}>
          🧠 Ask AgriBrain for full report
        </button>
      </div>
    );
  }

  // A committed raster remains valid for display and pixel sampling even when
  // the backend denies certified interpretation for the inspector role.
  if (!isModeAuthorizedForDiagnosis) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <PhenologyBadge />
        <div style={{
          padding: "16px",
          borderRadius: "10px",
          background: "rgba(245,158,11,0.08)",
          border: "1px solid rgba(245,158,11,0.22)",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          alignItems: "center",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "22px", lineHeight: 1 }}>🔎</div>
          <div style={{ fontSize: "12px", fontWeight: 700, color: "#fbbf24" }}>Certified diagnostic interpretation unavailable</div>
          <div style={{ fontSize: "11px", color: "#94a3b8", lineHeight: 1.5 }}>
            The scouting raster is committed and remains visible. Pixel values may be sampled as scouting hints,
            but diagnostic classes, management cards, localized prescriptions, and certified interpretation are withheld.
            Reason: {hasCurrentAuthorizationContract ? "inspector authorization missing" : "authorization contract unavailable"}.
          </div>
        </div>
        <button onClick={() => onAskBrain("The committed raster is available for scouting, but certified inspector interpretation is not authorized. Explain the visible evidence as a scouting signal only, without diagnosis, localized prescription, or management claims.")}
          style={{ width: "100%", padding: "10px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.15))", color: "#a5b4fc", fontSize: "12px", fontWeight: 700, cursor: "pointer", transition: "all 0.15s" }}>
          🧠 Ask AgriBrain for scouting context
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {/* Health Gauge with Confidence Interval */}
      <div data-testid="field-health-unavailable" style={{ padding: "12px", borderRadius: "10px", border: "1px solid rgba(148,163,184,0.25)", background: "rgba(15,23,42,0.4)", color: "#cbd5e1" }}>
          <div style={{ fontWeight: 700, fontSize: "13px" }}>Whole-field health score unavailable</div>
          <div style={{ fontSize: "11px", marginTop: "4px" }}>No qualified canonical whole-field health metric or calibrated interval was published. Component measurements are shown below without inferring a percentage.</div>
          {missingHealthEvidence.length > 0 && <div style={{ fontSize: "11px", color: "#fbbf24", marginTop: "4px" }}>Missing evidence: {missingHealthEvidence.join(", ")}</div>}
        </div>

      {/* Phenology Phase Badge */}
      <PhenologyBadge />

      {/* VPD Heat Alert (shows only when VPD > 1.5 kPa) */}
      <VPDAlert data={data} />

      {/* ── Mode-Specific Primary Metric ──────────────────────────── */}
      {modeInsight && (
        <div style={{ background: `${modeInsight.color}08`, border: `1px solid ${modeInsight.color}20`, borderRadius: "10px", padding: "12px" }}>
          <ConditionCard icon={modeInsight.icon} title={modeInsight.title} label={modeInsight.label} color={modeInsight.color} value={modeInsight.value} />
          {activeSurfStd != null && (
            <div style={{ fontSize: "11px", color: "#64748b", marginTop: "6px", display: "flex", gap: "12px" }}>
              <span>μ={activeSurfMean?.toFixed(3)}</span>
              <span>σ={activeSurfStd.toFixed(3)}</span>
              {activeSurfHist?.p10 != null && <span>P10={activeSurfHist.p10.toFixed(3)}</span>}
              {activeSurfHist?.p90 != null && <span>P90={activeSurfHist.p90.toFixed(3)}</span>}
            </div>
          )}
          {modeInsight.why && (
            <WhyCard icon="💡" title="Why it matters" why={modeInsight.why} />
          )}
        </div>
      )}

      {/* Farmer Advisory Card (V63F) */}
      {sanitizedAction.text && (
        <div className="sfv-action-card animate-fadeInUp" data-testid="driver-action-card" style={{
          padding: "12px 14px",
          borderRadius: "10px",
          background: "rgba(99, 102, 241, 0.08)",
          border: "1px solid rgba(99, 102, 241, 0.2)",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.1)",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          marginTop: "4px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.6rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", color: "#818cf8" }}>Recommended Action</span>
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
          <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "#f1f5f9" }}>{sanitizedAction.text}</div>
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
          {explainPack?.dominant_driver && (
            <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>
              Dominant Driver: <span style={{ fontWeight: 600, color: "#cbd5e1" }}>{explainPack.dominant_driver}</span>
              {explainPack.driver_confidence !== undefined && (
                <span> ({(explainPack.driver_confidence * 100).toFixed(0)}% confidence)</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* 7-Day NDVI Spark Trend — only in canopy/veg modes */}
      {(activeMode === "canopy" || activeMode === "vegetation") && ndvi7dBack.length >= 3 && (
        <SparkLine values={ndvi7dBack} color="#4ade80" label="NDVI 7-day trend" />
      )}

      {/* Trend indicator — only when not an artifact */}
      {trendLabel && delta && (
        <div style={{ textAlign: "center", padding: "6px 12px", borderRadius: "8px", background: `${trendColor}10`, border: `1px solid ${trendColor}20` }}>
          <span style={{ fontSize: "13px", color: trendColor, fontWeight: 700 }}>{trendLabel}</span>
          {delta.mean_change !== 0 && (
            <span style={{ fontSize: "11px", color: "#94a3b8", marginLeft: "8px" }}>
              ({delta.mean_change > 0 ? "+" : ""}{delta.mean_change.toFixed(3)} since {delta.date_from})
            </span>
          )}
        </div>
      )}

      {/* Recalibration notice — replaces trend when large data correction detected */}
      {showRecalibrationNotice && (
        <div style={{ textAlign: "center", padding: "6px 12px", borderRadius: "8px", background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}>
          <span style={{ fontSize: "12px", color: "#a5b4fc", fontWeight: 600 }}>🔄 Baseline recalibrated</span>
          <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px" }}>
            Historical trend suppressed — data quality correction applied. Next satellite pass will establish a clean baseline.
          </div>
        </div>
      )}

      {/* Risk Decomposition (stacked bar) — gated behind mode authorization */}
      {isModeAuthorizedForDiagnosis && (
        <RiskDecomposition data={data} narrative={riskNarrative} />
      )}

      {/* What's Happening — condition cards with active-mode highlighting */}
      <div>
        <div style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "8px" }}>What's Happening</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <div style={{ borderLeft: (highlightMode === "canopy" || highlightMode === "vegetation") ? "3px solid #4ade80" : "3px solid transparent", paddingLeft: "4px", borderRadius: "2px" }}>
            <ConditionCard icon="🌿" title="Field raster composite" label={vigor.text} color={vigor.color} value={ndviMean != null ? ndviMean.toFixed(2) : undefined} detail={`Plot-supported NDVI raster · ${fieldWindow}`} />
          </div>
          {pointNdvi != null && Number.isFinite(pointNdvi) && (
            <ConditionCard
              icon="📍"
              title="Point Sentinel index"
              label={`NDVI ${pointNdvi.toFixed(3)}`}
              color="#93c5fd"
              detail={`${pointObservationTime} · ${pointSupportLabel} · point support only; not a field mean`}
            />
          )}
          {ndviMean != null && ndviMean < 0.5 && (highlightMode === "canopy" || highlightMode === "vegetation") && (
            <WhyCard icon="💡" title="Why it matters" why="Low vigor means less photosynthesis → less biomass → lower yield. Check for nutrient deficiency, water stress, or pest damage." />
          )}
          <div style={{ borderLeft: highlightMode === "water_stress" ? "3px solid #38bdf8" : "3px solid transparent", paddingLeft: "4px", borderRadius: "2px" }}>
            <ConditionCard icon="💧" title="Water Status" label={water.text} color={water.color} value={deficitMm != null ? `${Math.abs(deficitMm).toFixed(1)}mm` : undefined} />
          </div>
          {l10Context.evidenceState?.riskWaterConflict?.hasConflict && (
            <div style={{ padding: "8px 10px", borderRadius: "8px", background: "rgba(239, 68, 68, 0.05)", border: "1px solid rgba(239, 68, 68, 0.2)", fontSize: "12px", color: "#fca5a5", marginTop: "4px", lineHeight: 1.4 }}>
              ⚠️ {l10Context.evidenceState.riskWaterConflict.message}
            </div>
          )}
          {deficitMm != null && Math.abs(deficitMm) > 30 && highlightMode === "water_stress" && !l10Context.evidenceState?.riskWaterConflict?.hasConflict && (
            <WhyCard icon="💡" title="Why it matters" why={`A ${Math.abs(deficitMm).toFixed(0)}mm deficit means the soil can't supply what the crop demands. Each day of deficit during active growth costs yield.`} />
          )}
          <div style={{ borderLeft: highlightMode === "nutrient_risk" ? "3px solid #facc15" : "3px solid transparent", paddingLeft: "4px", borderRadius: "2px" }}>
            <ConditionCard icon="📊" title="Field Consistency" label={consistency.text} color={consistency.color} value={ndviStd != null ? `σ ${ndviStd.toFixed(3)}` : undefined} />
          </div>
          {l0?.data?.temp_current != null && (
            <ConditionCard icon="🌡️" title="Temperature" label={`${Number(l0.data.temp_current).toFixed(1)}°C`} color="#e2e8f0" value={l0.data.rain_prob ? `${l0.data.rain_prob}% rain` : undefined} />
          )}
        </div>
      </div>

      {/* AI Summary */}
      {explainPack?.summary && (
        <div style={{ padding: "10px 12px", borderRadius: "10px", background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.12)" }}>
          <div style={{ fontSize: "11px", fontWeight: 700, color: "#a5b4fc", textTransform: "uppercase", marginBottom: "6px" }}>AI Insight</div>
          <p style={{ fontSize: "12px", color: "#e2e8f0", lineHeight: 1.6, margin: 0 }}>{explainPack.summary}</p>
        </div>
      )}

      {/* ── Headline Findings from Canonical Assessment ─────────── */}
      <div>
        <div style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "8px" }}>
          Key Assessment Findings
        </div>
        {topFindings && topFindings.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {topFindings.map((finding, idx) => (
              <div
                key={finding.id || idx}
                style={{
                  padding: "8px 10px",
                  borderRadius: "8px",
                  background: finding.severity === "critical"
                    ? "rgba(239, 68, 68, 0.08)"
                    : finding.severity === "medium"
                    ? "rgba(245, 158, 11, 0.08)"
                    : "rgba(99, 102, 241, 0.08)",
                  border: `1px solid ${
                    finding.severity === "critical"
                      ? "rgba(239, 68, 68, 0.2)"
                      : finding.severity === "medium"
                      ? "rgba(245, 158, 11, 0.2)"
                      : "rgba(99, 102, 241, 0.15)"
                  }`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "4px" }}>
                  <span style={{ fontSize: "12px", fontWeight: 700, color: "#f1f5f9" }}>
                    {finding.title}
                  </span>
                  <span
                    style={{
                      fontSize: "9px",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      padding: "1px 5px",
                      borderRadius: "3px",
                      background: finding.severity === "critical" ? "rgba(239,68,68,0.2)" : "rgba(148,163,184,0.15)",
                      color: finding.severity === "critical" ? "#f87171" : "#94a3b8",
                    }}
                  >
                    {finding.severity}
                  </span>
                </div>
                {finding.description && finding.description !== finding.title && (
                  <div style={{ fontSize: "11px", color: "#94a3b8", lineHeight: 1.4 }}>
                    {finding.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: "8px",
              background: "rgba(148, 163, 184, 0.05)",
              border: "1px solid rgba(148, 163, 184, 0.1)",
              fontSize: "11px",
              color: "#94a3b8",
              fontStyle: "italic",
            }}
          >
            No headline findings reported for this parcel publication.
          </div>
        )}
      </div>

      {/* Zone Alerts — gated behind mode authorization */}
      {isModeAuthorizedForDiagnosis && relevantZones.length > 0 && (
        <div>
          <div style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "8px" }}>
            Zone Alerts ({relevantZones.length})
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {relevantZones.slice(0, 4).map(z => (
              <ZoneAlertCard key={z.zone_id} zone={z} onAsk={onAskBrain} />
            ))}
          </div>
        </div>
      )}

      {/* Scenarios / What To Do — gated behind mode authorization */}
      {isModeAuthorizedForDiagnosis && data.scenario_pack && data.scenario_pack.length > 0 && (
        <div>
          <div style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "8px" }}>What To Do Next</div>
          {data.scenario_pack.slice(0, 2).map((s, i) => (
            <div key={i} className="sfv-scenario-card" style={{ background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.15)", borderRadius: "10px", padding: "10px 12px", marginBottom: "6px" }}>
              <div style={{ fontSize: "13px", color: "#e2e8f0", fontWeight: 700, marginBottom: "4px" }}>{s.title}</div>
              <div style={{ fontSize: "12px", color: "#94a3b8", lineHeight: 1.5 }}>{s.description}</div>
              {s.yield_impact_pct != null && (
                <div style={{ fontSize: "11px", color: s.yield_impact_pct > 0 ? "#4ade80" : "#f87171", fontWeight: 600, marginTop: "4px" }}>
                  Yield impact: {s.yield_impact_pct > 0 ? "+" : ""}{s.yield_impact_pct}%
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Data Sources */}
      {(assimilation || staleSourceState) && (
        <div style={{ padding: "8px 10px", borderRadius: "8px", background: "rgba(34,197,94,0.04)", border: "1px solid rgba(34,197,94,0.1)" }}>
          <div style={{ fontSize: "10px", color: "#64748b", fontWeight: 700, textTransform: "uppercase", marginBottom: "4px" }}>Data Sources</div>
          {assimilation && <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
            {assimilation.sources_used?.map((s: string) => (
              <span key={s} style={{ padding: "2px 6px", borderRadius: "4px", fontSize: "10px", background: "rgba(34,197,94,0.08)", color: "#4ade80", fontWeight: 600 }}>{s}</span>
            ))}
          </div>}
          {staleSourceState && (
            <div style={{ marginTop: "6px", padding: "6px 7px", borderRadius: "6px", background: "rgba(251,191,36,0.07)", border: "1px solid rgba(251,191,36,0.16)", color: "#fbbf24", fontSize: "10px", lineHeight: 1.45 }}>
              <div style={{ fontWeight: 700 }}>Last successful satellite composite available</div>
              <div>Current refresh unavailable · last observation {staleSourceState.last_successful_observation_at || "unknown"}</div>
              <div style={{ color: "#94a3b8" }}>Source snapshot {staleSourceState.source_snapshot_id || "unknown"} · age {staleSourceState.data_age_days != null ? `${Number(staleSourceState.data_age_days).toFixed(1)}d` : "unknown"}</div>
              <div style={{ color: "#94a3b8" }}>Intelligence snapshot {data.intelligence_snapshot_id || "unknown"} · generated {data.generated_at || data.timestamp || "unknown"}</div>
              <div style={{ color: "#94a3b8" }}>Refresh attempted {staleSourceState.refresh_attempted_at || "unknown"} · status {staleSourceState.refresh_status || "failed"}</div>
            </div>
          )}
        </div>
      )}

      {/* Ask button */}
      <button onClick={() => onAskBrain("Give me a complete field health summary with recommendations.")}
        style={{ width: "100%", padding: "10px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.15))", color: "#a5b4fc", fontSize: "12px", fontWeight: 700, cursor: "pointer", transition: "all 0.15s" }}>
        🧠 Ask AgriBrain for full report
      </button>
    </div>
  );
}
