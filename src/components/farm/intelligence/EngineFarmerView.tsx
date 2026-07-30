"use client";

/**
 * EngineFarmerView — Farmer-friendly grouped engine status.
 * Groups L0-L10 engines into meaningful categories farmers understand.
 * Shows plain-language summaries, field health impact, and actionable insights.
 * All data from real engine statuses. Zero synthetic data.
 */

import type { EngineStatus } from "@/hooks/usePlotIntelligence";
import type { Layer10Result } from "@/hooks/useLayer10";

interface FarmerViewProps {
  engines: EngineStatus[];
  data: Layer10Result | null;
  onAskBrain: (query: string) => void;
}

// ── Engine groupings by farmer concern ──────────────────────────────────
const GROUPS = [
  {
    key: "conditions",
    label: "Field Conditions",
    icon: "🌤️",
    engineIds: ["L0", "L1"],
    description: "Weather, soil and data fusion",
  },
  {
    key: "crop",
    label: "Crop Health Systems",
    icon: "🌿",
    engineIds: ["L2", "L3", "L4", "L5"],
    description: "Vegetation, water, nutrients, disease pipelines",
  },
  {
    key: "planning",
    label: "Yield & Planning",
    icon: "📋",
    engineIds: ["L6", "L7", "L8"],
    description: "Yield estimation, calendar, actions",
  },
  {
    key: "intelligence",
    label: "Intelligence",
    icon: "🧠",
    engineIds: ["L9", "L10"],
    description: "Advisory and synthesis",
  },
] as const;

const STATUS_DOT: Record<string, { color: string; label: string }> = {
  OK: { color: "#4ade80", label: "OK" },
  DEGRADED: { color: "#fbbf24", label: "Needs attention" },
  SKIPPED: { color: "#64748b", label: "Skipped" },
  UNAVAILABLE: { color: "#94a3b8", label: "Unavailable" },
  FAILED: { color: "#f87171", label: "Failed" },
  OFFLINE: { color: "#f87171", label: "Issue detected" },
  LOADING: { color: "#818cf8", label: "Loading..." },
};

// ── Farmer-friendly engine name translations ────────────────────────────
const FARMER_NAMES: Record<string, string> = {
  L0: "Weather & Environment",
  L1: "Data Sources",
  L2: "Crop Greenness",
  L3: "Water & Irrigation",
  L4: "Soil Nutrients",
  L5: "Disease & Pests",
  L6: "Expected Yield",
  L7: "Farm Calendar",
  L8: "Recommended Actions",
  L9: "Expert Advice",
  L10: "Overall Analysis",
};

// ── Group Status Summary ────────────────────────────────────────────────
function GroupCard({ group, engines, onAskBrain }: {
  group: typeof GROUPS[number];
  engines: EngineStatus[];
  onAskBrain: (q: string) => void;
}) {
  const groupEngines = engines.filter(e => (group.engineIds as readonly string[]).includes(e.id));
  if (groupEngines.length === 0) return null;

  const worstStatus = groupEngines.reduce((worst, e) => {
    const priority = { FAILED: 5, OFFLINE: 5, UNAVAILABLE: 4, DEGRADED: 3, SKIPPED: 2, LOADING: 1, OK: 0 };
    const ep = priority[e.status as keyof typeof priority] ?? 0;
    const wp = priority[worst as keyof typeof priority] ?? 0;
    return ep > wp ? e.status : worst;
  }, "OK" as string);

  const statusInfo = STATUS_DOT[worstStatus] || STATUS_DOT.OK;
  const okCount = groupEngines.filter(e => e.status === "OK").length;
  const degradedEngines = groupEngines.filter(e => e.status !== "OK");

  // Get first non-empty farmer summary from any engine in group
  const primarySummary = groupEngines
    .map(e => String(e.data?.farmer_summary || e.summary || ""))
    .find(s => s.length > 10) || null;

  return (
    <div className="efv-group-card" style={{
      background: "rgba(15,23,42,0.4)",
      border: `1px solid ${statusInfo.color}15`,
      borderRadius: "12px",
      padding: "12px",
      transition: "all 0.2s",
    }}>
      {/* Group header */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
        <span style={{ fontSize: "1.3rem" }}>{group.icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: "14px", fontWeight: 700, color: "#f1f5f9" }}>{group.label}</div>
          <div style={{ fontSize: "12px", color: "#64748b" }}>{group.description}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <div style={{
            width: "8px", height: "8px", borderRadius: "50%",
            background: statusInfo.color,
            boxShadow: `0 0 6px ${statusInfo.color}40`,
          }} />
          <span style={{ fontSize: "12px", color: statusInfo.color, fontWeight: 700 }}>{statusInfo.label}</span>
        </div>
      </div>

      {/* Engine status chips */}
      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginBottom: "8px" }}>
        {groupEngines.map(e => {
          const eStatus = STATUS_DOT[e.status] || STATUS_DOT.OK;
          return (
            <div key={e.id} style={{
              display: "flex", alignItems: "center", gap: "4px",
              padding: "3px 8px", borderRadius: "6px",
              background: `${eStatus.color}08`,
              border: `1px solid ${eStatus.color}15`,
            }}>
              <div style={{ width: "5px", height: "5px", borderRadius: "50%", background: eStatus.color }} />
              <span style={{ fontSize: "11px", color: "#cbd5e1", fontWeight: 600 }}>
                {FARMER_NAMES[e.id] || e.name}
              </span>
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
          {primarySummary}
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
          <span style={{ color: "#e2e8f0", fontWeight: 600 }}>{FARMER_NAMES[e.id] || e.name}: </span>
          {String(e.data.why_it_matters)}
        </div>
      ) : null)}

      {/* Degraded alerts */}
      {degradedEngines.length > 0 && (
        <div style={{ marginTop: "4px" }}>
          {degradedEngines.map(e => (
            <div key={e.id} style={{
              display: "flex", alignItems: "center", gap: "6px",
              padding: "5px 10px", borderRadius: "6px",
              background: e.status === "OFFLINE" ? "rgba(248,113,113,0.06)" : "rgba(251,191,36,0.06)",
              border: `1px solid ${e.status === "OFFLINE" ? "rgba(248,113,113,0.1)" : "rgba(251,191,36,0.1)"}`,
              marginBottom: "4px", fontSize: "12px",
            }}>
              <span style={{ color: STATUS_DOT[e.status]?.color || "#fbbf24" }}>⚠</span>
              <span style={{ color: "#cbd5e1", flex: 1 }}>
                {FARMER_NAMES[e.id] || e.name}: {String(e.data?.farmer_summary || e.summary || "Check needed")}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Quick metrics from key engines */}
      <EngineQuickMetrics engines={groupEngines} />

      {/* Ask button */}
      <button
        onClick={() => onAskBrain(`Tell me about my field's ${group.label.toLowerCase()}. What should I know and what should I do?`)}
        style={{
          marginTop: "8px", width: "100%", padding: "8px",
          borderRadius: "6px", border: "none",
          background: "rgba(99,102,241,0.08)", color: "#a5b4fc",
          fontSize: "12px", fontWeight: 700, cursor: "pointer",
        }}
      >
        🧠 Ask about {group.label.toLowerCase()}
      </button>
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
      const support = e.data.ndvi_support_type === "point" ? "Point Sentinel index" : "Temporal NDVI estimate";
      metrics.push({ label: support, value: ndvi.toFixed(2), color: ndvi > 0.5 ? "#4ade80" : ndvi > 0.3 ? "#fbbf24" : "#f87171" });
    }
    if (e.id === "L3" && e.data.deficit_mm != null) {
      const d = Math.abs(Number(e.data.deficit_mm));
      metrics.push({ label: "Water deficit", value: `${d.toFixed(1)}mm`, color: d < 5 ? "#4ade80" : d < 15 ? "#fbbf24" : "#f87171" });
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
          <div style={{ fontSize: "14px", color: m.color, fontFamily: "monospace", fontWeight: 700 }}>{m.value}</div>
        </div>
      ))}
    </div>
  );
}

// ── Main Farmer View ────────────────────────────────────────────────────
export default function EngineFarmerView({ engines, data, onAskBrain }: FarmerViewProps) {
  // Zone alerts summary for farmer
  const alertZones = data?.zones?.filter(z => z.severity > 0.4) || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {/* Engine groups */}
      {GROUPS.map(group => (
        <GroupCard key={group.key} group={group} engines={engines} onAskBrain={onAskBrain} />
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
