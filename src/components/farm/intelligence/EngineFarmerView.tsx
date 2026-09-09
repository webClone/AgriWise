"use client";

/**
 * EngineFarmerView — Farmer-friendly grouped engine status.
 * Groups L0-L10 engines into meaningful categories farmers understand.
 * Shows plain-language summaries, field health impact, and actionable insights.
 * All data from real engine statuses. Zero synthetic data.
 */

import { type EngineStatus, SUBSYSTEM_METADATA } from "@/hooks/usePlotIntelligence";
import type { Layer10Result } from "@/hooks/useLayer10";

interface FarmerViewProps {
  engines: EngineStatus[];
  data: Layer10Result | null;
  onAskBrain: (query: string) => void;
  onOpenLayerDashboard?: (layerId: string) => void;
}

// ── Engine groupings by farmer concern ──────────────────────────────────
const GROUPS = [
  {
    key: "conditions",
    label: "Field Conditions",
    icon: "🌤️",
    engineIds: ["L0", "L1"],
    description: "Microclimate, atmospheric forecast & sensor assimilation",
  },
  {
    key: "crop",
    label: "Canopy & Root Zone",
    icon: "🌿",
    engineIds: ["L2", "L3", "L4", "L5"],
    description: "ASMAE biophysical vigor, root moisture, soil nutrients, pest pathology",
  },
  {
    key: "planning",
    label: "Yield & Operations",
    icon: "📋",
    engineIds: ["L6", "L7", "L8"],
    description: "Yield calibration, agronomic calendar, precision prescriptions",
  },
  {
    key: "intelligence",
    label: "Field Intelligence",
    icon: "🧠",
    engineIds: ["L9", "L10"],
    description: "MESIA World Model synthesis & AI advisory",
  },
] as const;

// ── Status dot & color helpers ──────────────────────────────────────────
const STATUS_DOT: Record<string, { color: string; label: string }> = {
  OK: { color: "#4ade80", label: "Good" },
  DEGRADED: { color: "#fbbf24", label: "Warning" },
  OFFLINE: { color: "#f87171", label: "Issue" },
  LOADING: { color: "#818cf8", label: "Updating" },
};

function getGroupStatus(engines: EngineStatus[]) {
  if (engines.some(e => e.status === "OFFLINE")) return { color: "#f87171", label: "Needs Attention", dot: "🔴" };
  if (engines.some(e => e.status === "DEGRADED")) return { color: "#fbbf24", label: "Warning", dot: "🟡" };
  if (engines.every(e => e.status === "OK")) return { color: "#4ade80", label: "All Systems OK", dot: "🟢" };
  return { color: "#94a3b8", label: "Active", dot: "⚪" };
}

// ── Helper to resolve canonical agronomic name ──────────────────────────
const getSubsystemName = (e: EngineStatus) => {
  if (SUBSYSTEM_METADATA[e.id]) {
    return SUBSYSTEM_METADATA[e.id].name;
  }
  if (e.name && !/^L\d+$/i.test(e.name)) {
    return e.name;
  }
  return "Agronomic Subsystem";
};

// ── Sanitize text from SoilGrids & layer codes ───────────────────────────
const sanitizeSummary = (txt: any) => {
  if (!txt) return "";
  return String(txt)
    .replace(/SoilGrids-ISRIC/gi, "Regional Soil Survey")
    .replace(/SoilGrids Proxy/gi, "Regional Soil Survey Baseline")
    .replace(/SoilGrids/gi, "Regional Soil Survey")
    .replace(/\bL([0-9]{1,2})\b/g, (m) => SUBSYSTEM_METADATA[m]?.name || m);
};

// ── Group Card ──────────────────────────────────────────────────────────
function GroupCard({ group, engines, onAskBrain, onOpenLayerDashboard }: {
  group: typeof GROUPS[number];
  engines: EngineStatus[];
  onAskBrain: (q: string) => void;
  onOpenLayerDashboard?: (layerId: string) => void;
}) {
  const groupEngines = engines.filter(e => (group.engineIds as readonly string[]).includes(e.id));
  if (groupEngines.length === 0) return null;

  const statusInfo = getGroupStatus(groupEngines);
  const degradedEngines = groupEngines.filter(e => e.status === "DEGRADED" || e.status === "OFFLINE");

  // Primary summary: best available summary from the group
  const primarySummary = groupEngines.find(e => e.data?.farmer_summary)?.data?.farmer_summary as string
    || groupEngines.find(e => e.summary)?.summary
    || "";

  return (
    <div
      className="efv-group-card"
      style={{
        background: "rgba(0,0,0,0.3)",
        border: `1px solid ${degradedEngines.length > 0 ? "rgba(251,191,36,0.2)" : "rgba(71,85,105,0.12)"}`,
        borderRadius: "10px",
        padding: "10px 12px",
        transition: "border-color 0.2s",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "1rem" }}>{group.icon}</span>
          <div>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "#f1f5f9" }}>{group.label}</span>
            <div style={{ fontSize: "10px", color: "#64748b", lineHeight: 1.2 }}>{group.description}</div>
          </div>
        </div>
        <span style={{
          fontSize: "10px", fontWeight: 700, color: statusInfo.color,
          display: "flex", alignItems: "center", gap: "3px",
        }}>
          {statusInfo.dot} {statusInfo.label}
        </span>
      </div>

      {/* Engine status chips */}
      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginBottom: "8px" }}>
        {groupEngines.map(e => {
          const eStatus = STATUS_DOT[e.status] || STATUS_DOT.OK;
          return (
            <div
              key={e.id}
              onClick={() => onOpenLayerDashboard?.(e.id)}
              title={`Click to open ${getSubsystemName(e)} dashboard & parameters`}
              style={{
                display: "flex", alignItems: "center", gap: "4px",
                padding: "3px 8px", borderRadius: "6px",
                background: `${eStatus.color}08`,
                border: `1px solid ${eStatus.color}15`,
                cursor: "pointer",
                transition: "all 0.15s",
              }}
              onMouseOver={(ev) => (ev.currentTarget.style.borderColor = "#6366f1")}
              onMouseOut={(ev) => (ev.currentTarget.style.borderColor = `${eStatus.color}15`)}
            >
              <div style={{ width: "5px", height: "5px", borderRadius: "50%", background: eStatus.color }} />
              <span style={{ fontSize: "11px", color: "#cbd5e1", fontWeight: 600 }}>
                {getSubsystemName(e)}
              </span>
              <span style={{ fontSize: "10px", opacity: 0.6 }}>⚙️</span>
            </div>
          );
        })}
      </div>

      {/* Primary summary */}
      {primarySummary && (
        <div className="efv-summary-box" style={{
          fontSize: "12px", color: "#94a3b8", lineHeight: 1.6,
          padding: "8px 10px", borderRadius: "6px",
          background: "rgba(0,0,0,0.2)",
          marginBottom: "6px",
        }}>
          {sanitizeSummary(primarySummary)}
        </div>
      )}

      {/* "Why it matters" from engines */}
      {groupEngines.map(e => e.data?.why_it_matters ? (
        <div key={e.id + "_why"} className="efv-why-box" style={{
          fontSize: "12px", color: "#94a3b8", lineHeight: 1.5,
          padding: "6px 10px", borderRadius: "4px",
          background: "rgba(0,0,0,0.15)", marginBottom: "4px",
          borderLeft: `2px solid ${statusInfo.color}40`,
        }}>
          <span style={{ color: "#e2e8f0", fontWeight: 600 }}>{getSubsystemName(e)}: </span>
          {sanitizeSummary(e.data.why_it_matters)}
        </div>
      ) : null)}

      {/* Degraded alerts with direct resolution action buttons */}
      {degradedEngines.length > 0 && (
        <div style={{ marginTop: "4px" }}>
          {degradedEngines.map(e => (
            <div key={e.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between", gap: "6px",
              padding: "6px 10px", borderRadius: "6px",
              background: e.status === "OFFLINE" ? "rgba(248,113,113,0.06)" : "rgba(251,191,36,0.06)",
              border: `1px solid ${e.status === "OFFLINE" ? "rgba(248,113,113,0.15)" : "rgba(251,191,36,0.15)"}`,
              marginBottom: "4px", fontSize: "12px",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", flex: 1 }}>
                <span style={{ color: STATUS_DOT[e.status]?.color || "#fbbf24" }}>⚠</span>
                <span style={{ color: "#cbd5e1" }}>
                  {getSubsystemName(e)}: {sanitizeSummary(e.data?.farmer_summary || e.summary || "Check needed")}
                </span>
              </div>
              <button
                onClick={() => onOpenLayerDashboard?.(e.id)}
                style={{
                  padding: "2px 8px", borderRadius: "4px",
                  background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)",
                  color: "#a5b4fc", fontSize: "10px", fontWeight: 700, cursor: "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                {e.id === "L4" ? "🧪 Soil Test" : e.id === "L6" ? "🎯 Calibrate" : "⚙️ Fix"}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Quick metrics from key engines */}
      <EngineQuickMetrics engines={groupEngines} />

      {/* Action buttons */}
      <div style={{ display: "flex", gap: "6px", marginTop: "8px" }}>
        <button
          onClick={() => onAskBrain(`Tell me about my field's ${group.label.toLowerCase()}. What should I know and what should I do?`)}
          style={{
            flex: 1, padding: "8px",
            borderRadius: "6px", border: "none",
            background: "rgba(99,102,241,0.08)", color: "#a5b4fc",
            fontSize: "12px", fontWeight: 700, cursor: "pointer",
          }}
        >
          💬 Ask about {group.label.toLowerCase()}
        </button>
        <button
          onClick={() => onOpenLayerDashboard?.(group.engineIds[0])}
          title="Open parameter tuning dashboard for this group"
          style={{
            padding: "8px 12px",
            borderRadius: "6px", border: "1px solid rgba(71,85,105,0.25)",
            background: "rgba(255,255,255,0.03)", color: "#cbd5e1",
            fontSize: "12px", fontWeight: 700, cursor: "pointer",
            display: "flex", alignItems: "center", gap: "4px",
          }}
        >
          ⚙️ Tune
        </button>
      </div>
    </div>
  );
}

// ── Quick inline metrics from engine data ────────────────────────────────
function EngineQuickMetrics({ engines }: { engines: EngineStatus[] }) {
  const metrics: { label: string; value: string; color: string }[] = [];

  for (const e of engines) {
    if (!e.data) continue;
    if (e.id === "L0" && e.data.temp_current != null) {
      metrics.push({ label: "Temperature", value: `${Number(e.data.temp_current).toFixed(1)}°C`, color: "#e2e8f0" });
      if (e.data.rain_prob) metrics.push({ label: "Rain chance", value: `${e.data.rain_prob}%`, color: "#60a5fa" });
    }
    if (e.id === "L2" && e.data.ndvi_mean != null) {
      const ndvi = Number(e.data.ndvi_mean);
      const support = e.data.ndvi_support_type === "point" ? "Point Vigor" : "Canopy Vigor";
      metrics.push({ label: support, value: ndvi.toFixed(2), color: ndvi > 0.5 ? "#4ade80" : ndvi > 0.3 ? "#fbbf24" : "#f87171" });
    }
    if (e.id === "L3" && e.data.deficit_mm != null) {
      const d = Math.abs(Number(e.data.deficit_mm));
      metrics.push({ label: "Water deficit", value: `${d.toFixed(1)}mm`, color: d < 5 ? "#4ade80" : d < 15 ? "#fbbf24" : "#f87171" });
    }
    if (e.id === "L4" && (e.data.texture || e.data.clay_pct != null || e.data.soil_type)) {
      const texture = String(e.data.texture || e.data.soil_type || (e.data.clay_pct != null ? `${e.data.clay_pct}% clay` : "Loam"));
      metrics.push({ label: "Soil Texture", value: texture.slice(0, 10), color: "#cbd5e1" });
    }
    if (e.id === "L5" && (e.data.threat_level || e.data.disease_risk || e.data.pest_risk)) {
      const threat = String(e.data.dominant_threat || e.data.threat_level || e.data.disease_risk || "Low");
      const isHigh = /high|critical|severe/i.test(threat);
      const isMed = /moderate|medium|watch/i.test(threat);
      metrics.push({ label: "Pest / Disease", value: threat.slice(0, 10), color: isHigh ? "#f87171" : isMed ? "#fbbf24" : "#4ade80" });
    }
    if (e.id === "L6" && (e.data.expected_yield_t_ha != null || e.data.yield_potential_pct != null)) {
      const yVal = e.data.expected_yield_t_ha != null ? `${Number(e.data.expected_yield_t_ha).toFixed(1)} t/ha` : `${e.data.yield_potential_pct}%`;
      metrics.push({ label: "Yield Target", value: yVal, color: "#60a5fa" });
    }
  }

  if (metrics.length === 0) return null;

  return (
    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginTop: "6px" }}>
      {metrics.map((m, i) => (
        <div key={i} className="efv-metric-chip" style={{
          padding: "5px 10px", borderRadius: "6px",
          background: "rgba(0,0,0,0.3)", border: "1px solid rgba(71,85,105,0.08)",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>{m.label}</div>
          <div style={{ fontSize: "13px", color: m.color, fontFamily: "monospace", fontWeight: 700 }}>{m.value}</div>
        </div>
      ))}
    </div>
  );
}

// ── Main Farmer View ────────────────────────────────────────────────────
export default function EngineFarmerView({ engines, data, onAskBrain, onOpenLayerDashboard }: FarmerViewProps) {
  // Zone alerts summary for farmer
  const alertZones = data?.zones?.filter(z => z.severity > 0.4) || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {/* Engine groups */}
      {GROUPS.map(group => (
        <GroupCard
          key={group.key}
          group={group}
          engines={engines}
          onAskBrain={onAskBrain}
          onOpenLayerDashboard={onOpenLayerDashboard}
        />
      ))}

      {/* Zone awareness */}
      {alertZones.length > 0 && (
        <div style={{
          padding: "10px 12px", borderRadius: "10px",
          background: "rgba(248,113,113,0.04)", border: "1px solid rgba(248,113,113,0.1)",
        }}>
          <div style={{ fontSize: "10px", color: "#f87171", fontWeight: 700, textTransform: "uppercase", marginBottom: "6px" }}>
            ⚠️ {alertZones.length} Zone{alertZones.length > 1 ? "s" : ""} Need Attention
          </div>
          {alertZones.slice(0, 3).map(z => (
            <div key={z.zone_id} style={{
              display: "flex", alignItems: "center", gap: "6px",
              padding: "4px 0", fontSize: "11px",
            }}>
              <div style={{
                width: "6px", height: "6px", borderRadius: "50%",
                background: z.severity > 0.6 ? "#f87171" : "#fbbf24",
              }} />
              <span style={{ color: "#e2e8f0", flex: 1 }}>{z.label || z.zone_id}</span>
              <span style={{ fontSize: "9px", color: "#94a3b8" }}>{(z.area_fraction * 100).toFixed(0)}% area</span>
            </div>
          ))}
          <button
            onClick={() => onAskBrain("Which zones in my field need attention and what should I do about them?")}
            style={{
              marginTop: "6px", padding: "4px 10px", borderRadius: "6px",
              border: "none", background: "rgba(248,113,113,0.08)",
              color: "#f87171", fontSize: "10px", fontWeight: 700, cursor: "pointer",
            }}
          >
            🔍 Explain zones
          </button>
        </div>
      )}

      {/* Overall ask */}
      <button
        onClick={() => onAskBrain("Give me a simple overview of my field's current status and what I should prioritize today.")}
        style={{
          width: "100%", padding: "10px", borderRadius: "10px", border: "none",
          background: "linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.12))",
          color: "#a5b4fc", fontSize: "12px", fontWeight: 700, cursor: "pointer",
        }}
      >
        🧠 What should I do today?
      </button>
    </div>
  );
}
