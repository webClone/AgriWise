"use client";

/**
 * EngineExpertView — Scientific engine pipeline analysis console.
 * Shows per-engine detailed metrics, confidence breakdown, data flow,
 * inter-engine dependencies, and zone-level relevance.
 * All data from real engine statuses + L10 quality. Zero synthetic data.
 */

import type { EngineStatus } from "@/hooks/usePlotIntelligence";
import type { Layer10Result } from "@/hooks/useLayer10";

interface ExpertViewProps {
  engines: EngineStatus[];
  data: Layer10Result | null;
  expandedEngine: string | null;
  onToggleEngine: (id: string | null) => void;
  onAskBrain: (query: string) => void;
}

const STATUS_COLORS: Record<string, { bg: string; border: string; dot: string; text: string }> = {
  OK: { bg: "rgba(34, 197, 94, 0.08)", border: "rgba(34, 197, 94, 0.2)", dot: "#4ade80", text: "OK" },
  DEGRADED: { bg: "rgba(251, 191, 36, 0.08)", border: "rgba(251, 191, 36, 0.2)", dot: "#fbbf24", text: "DEGRADED" },
  OFFLINE: { bg: "rgba(239, 68, 68, 0.08)", border: "rgba(239, 68, 68, 0.2)", dot: "#f87171", text: "OFFLINE" },
  LOADING: { bg: "rgba(99, 102, 241, 0.08)", border: "rgba(99, 102, 241, 0.2)", dot: "#818cf8", text: "LOADING" },
};

// ── Confidence mini-bar ─────────────────────────────────────────────────
function ConfBar({ value, label }: { value: number; label: string }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "#4ade80" : pct >= 60 ? "#fbbf24" : "#f87171";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
      <div style={{ width: "60px", fontSize: "11px", color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</div>
      <div style={{ flex: 1, height: "5px", background: "rgba(71,85,105,0.2)", borderRadius: "2px", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: "2px", transition: "width 0.3s" }} />
      </div>
      <div style={{ fontSize: "11px", color, fontFamily: "monospace", fontWeight: 700, minWidth: "28px", textAlign: "right" }}>{pct}%</div>
    </div>
  );
}

// ── Expert Metric Row ───────────────────────────────────────────────────
function MetricRow({ metric }: { metric: any }) {
  const conf = Number(metric.confidence ?? 0);
  const color = conf >= 0.85 ? "#4ade80" : conf >= 0.6 ? "#fbbf24" : "#f87171";
  return (
    <div className="eev-metric-row" style={{
      background: "rgba(0,0,0,0.25)", borderRadius: "6px",
      padding: "8px 10px", border: "1px solid rgba(71,85,105,0.08)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "12px", color: "#cbd5e1", fontWeight: 600 }}>{metric.name}</span>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "13px", color: "#f1f5f9", fontFamily: "monospace", fontWeight: 700 }}>{metric.value}</span>
          <span style={{
            fontSize: "11px", padding: "1px 5px", borderRadius: "8px",
            background: `${color}15`, color, border: `1px solid ${color}30`, fontWeight: 700,
          }}>
            {(conf * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      {metric.reason && (
        <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px", lineHeight: 1.4 }}>{metric.reason}</div>
      )}
    </div>
  );
}

// ── Engine Card (Expert) ────────────────────────────────────────────────
function EngineCardExpert({ engine, isExpanded, onToggle, onAskBrain, zoneRelevance }: {
  engine: EngineStatus;
  isExpanded: boolean;
  onToggle: () => void;
  onAskBrain: (q: string) => void;
  zoneRelevance: string[];
}) {
  const colors = STATUS_COLORS[engine.status] || STATUS_COLORS.OFFLINE;
  const expertMetrics = (engine.data?.expert_metrics as any[]) || [];

  // Compute per-engine confidence from its metrics
  const engineConf = expertMetrics.length > 0
    ? expertMetrics.reduce((sum, m) => sum + Number(m.confidence ?? 0), 0) / expertMetrics.length
    : null;

  return (
    <div
      style={{
        background: isExpanded ? colors.bg : "transparent",
        border: `1px solid ${isExpanded ? colors.border : "transparent"}`,
        borderRadius: "10px",
        transition: "all 0.2s ease",
        marginBottom: "2px",
      }}
    >
      {/* Compact row */}
      <div
        onClick={onToggle}
        style={{
          display: "flex", alignItems: "center", gap: "8px",
          padding: "8px 10px", cursor: "pointer",
        }}
      >
        {/* Status dot */}
        <div style={{
          width: "7px", height: "7px", borderRadius: "50%",
          background: colors.dot, flexShrink: 0,
          boxShadow: `0 0 6px ${colors.dot}40`,
        }} />

        {/* Icon */}
        <span style={{ fontSize: "1rem", lineHeight: 1 }}>{engine.icon}</span>

        {/* ID + Name */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ fontSize: "12px", color: "#64748b", fontFamily: "monospace", fontWeight: 700 }}>{engine.id}</span>
            <span style={{
              fontSize: "13px", fontWeight: 600, color: "#e2e8f0",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}>
              {engine.name}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "11px", color: colors.dot, fontWeight: 600 }}>{colors.text}</span>
            {engineConf !== null && (
              <span style={{
                fontSize: "11px", color: engineConf > 0.7 ? "#4ade80" : "#fbbf24",
                fontFamily: "monospace",
              }}>
                conf:{(engineConf * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>

        {/* Expand arrow */}
        <span style={{
          fontSize: "0.75rem", color: "#64748b",
          transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
          transition: "transform 0.2s",
        }}>
          ▶
        </span>
      </div>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="eev-expanded" style={{
          padding: "0 10px 10px 35px",
          borderTop: `1px solid ${colors.border}`,
          marginTop: "-2px", paddingTop: "8px",
        }}>
          {/* Expert summary */}
          <p style={{ fontSize: "13px", color: "#cbd5e1", lineHeight: 1.6, margin: "0 0 10px 0" }}>
            {String(engine.data?.expert_summary || engine.summary)}
          </p>

          {/* Confidence + freshness row */}
          <div style={{ display: "flex", gap: "6px", marginBottom: "10px", flexWrap: "wrap" }}>
            {engine.data?.confidence_level !== undefined ? (
              <div className="eev-meta-chip" style={{
                fontSize: "12px", padding: "3px 8px", borderRadius: "4px",
                background: "rgba(0,0,0,0.2)", border: "1px solid rgba(71,85,105,0.08)",
                color: "#94a3b8", display: "flex", alignItems: "center", gap: "3px",
              }}>
                <span style={{ color: Number(engine.data.confidence_level) > 0.7 ? "#4ade80" : "#fbbf24" }}>●</span>
                Conf: {(Number(engine.data.confidence_level) * 100).toFixed(0)}%
              </div>
            ) : null}
            {!!engine.data?.data_freshness ? (
              <div className="eev-meta-chip" style={{
                fontSize: "12px", padding: "3px 8px", borderRadius: "4px",
                background: "rgba(0,0,0,0.2)", color: "#64748b",
              }}>
                📅 {String(engine.data.data_freshness)}
              </div>
            ) : null}
            {!!engine.data?.model_version ? (
              <div className="eev-meta-chip" style={{
                fontSize: "12px", padding: "3px 8px", borderRadius: "4px",
                background: "rgba(0,0,0,0.2)", color: "#64748b", fontFamily: "monospace",
              }}>
                v{String(engine.data.model_version)}
              </div>
            ) : null}
          </div>

          {/* Expert metrics */}
          {expertMetrics.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "8px" }}>
              {expertMetrics.map((m: any, i: number) => (
                <MetricRow key={i} metric={m} />
              ))}
            </div>
          ) : null}

          {/* Raw data preview (top 6 fields) */}
          {engine.data && Object.keys(engine.data).filter(k => !["expert_metrics", "expert_summary", "farmer_summary", "why_it_matters", "confidence_level", "confidence_reason", "data_freshness", "model_version"].includes(k)).length > 0 ? (
            <details style={{ marginBottom: "6px" }}>
              <summary style={{ fontSize: "12px", color: "#64748b", cursor: "pointer", fontWeight: 700, textTransform: "uppercase" }}>
                Raw Fields ({Object.keys(engine.data).length})
              </summary>
              <div className="eev-raw-box" style={{
                marginTop: "4px", padding: "8px 10px", borderRadius: "6px",
                background: "rgba(0,0,0,0.3)", border: "1px solid rgba(71,85,105,0.06)",
                fontFamily: "monospace", fontSize: "11px", maxHeight: "140px", overflowY: "auto",
              }}>
                {Object.entries(engine.data)
                  .filter(([k]) => !["expert_metrics", "expert_summary", "farmer_summary", "why_it_matters"].includes(k))
                  .slice(0, 8)
                  .map(([k, v]) => (
                    <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "1px 0" }}>
                      <span style={{ color: "#64748b" }}>{k}</span>
                      <span style={{ color: "#cbd5e1" }}>
                        {typeof v === "object" ? (v === null ? "null" : Array.isArray(v) ? `[${(v as any[]).length}]` : "{…}") : String(v)}
                      </span>
                    </div>
                  ))}
              </div>
            </details>
          ) : null}

          {/* Zone relevance */}
          {zoneRelevance.length > 0 ? (
            <div style={{ display: "flex", gap: "3px", flexWrap: "wrap", marginBottom: "6px" }}>
              <span style={{ fontSize: "8px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Zones: </span>
              {zoneRelevance.map(z => (
                <span key={z} style={{
                  fontSize: "8px", padding: "1px 5px", borderRadius: "3px",
                  background: "rgba(99,102,241,0.08)", color: "#a5b4fc",
                  border: "1px solid rgba(99,102,241,0.1)",
                }}>{z}</span>
              ))}
            </div>
          ) : null}

          {/* Why it matters */}
          {!!engine.data?.why_it_matters ? (
            <details style={{ marginBottom: "8px" }}>
              <summary style={{ fontSize: "12px", color: "#94a3b8", cursor: "pointer", fontWeight: 600 }}>Why this matters</summary>
              <div className="eev-why-box" style={{
                padding: "6px 10px", background: "rgba(0,0,0,0.2)", borderRadius: "4px",
                marginTop: "4px", fontSize: "12px", color: "#94a3b8", lineHeight: 1.5,
              }}>
                {String(engine.data.why_it_matters)}
              </div>
            </details>
          ) : null}

          {/* Action buttons */}
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={(e) => { e.stopPropagation(); onAskBrain(`Deep analysis of ${engine.id} ${engine.name}: current findings, confidence reasoning, and what alternative interpretations exist.`); }}
              style={{
                fontSize: "12px", color: "#818cf8", background: "none", border: "none",
                cursor: "pointer", fontWeight: 700, textTransform: "uppercase", padding: "2px 0",
              }}
            >
              Analyze →
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onAskBrain(`What are the limitations of ${engine.id} ${engine.name} right now? What could invalidate its current assessment?`); }}
              style={{
                fontSize: "12px", color: "#fbbf24", background: "none", border: "none",
                cursor: "pointer", fontWeight: 700, textTransform: "uppercase", padding: "2px 0",
              }}
            >
              Challenge →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Expert View ────────────────────────────────────────────────────
export default function EngineExpertView({ engines, data, expandedEngine, onToggleEngine, onAskBrain }: ExpertViewProps) {
  // Build zone relevance map from real zone data
  const zoneRelevanceMap: Record<string, string[]> = {};
  if (data?.zones) {
    for (const zone of data.zones) {
      for (const driver of zone.top_drivers) {
        // Map driver names to engine IDs
        const driverLower = driver.toLowerCase();
        if (driverLower.includes("weather") || driverLower.includes("temp") || driverLower.includes("rain")) {
          (zoneRelevanceMap["L0"] = zoneRelevanceMap["L0"] || []).push(zone.zone_id);
        }
        if (driverLower.includes("ndvi") || driverLower.includes("vegetation") || driverLower.includes("canopy")) {
          (zoneRelevanceMap["L2"] = zoneRelevanceMap["L2"] || []).push(zone.zone_id);
        }
        if (driverLower.includes("water") || driverLower.includes("moisture") || driverLower.includes("deficit")) {
          (zoneRelevanceMap["L3"] = zoneRelevanceMap["L3"] || []).push(zone.zone_id);
        }
        if (driverLower.includes("nutrient") || driverLower.includes("nitrogen") || driverLower.includes("phosph")) {
          (zoneRelevanceMap["L4"] = zoneRelevanceMap["L4"] || []).push(zone.zone_id);
        }
        if (driverLower.includes("disease") || driverLower.includes("pest") || driverLower.includes("biotic")) {
          (zoneRelevanceMap["L5"] = zoneRelevanceMap["L5"] || []).push(zone.zone_id);
        }
      }
    }
    // Deduplicate
    for (const key of Object.keys(zoneRelevanceMap)) {
      zoneRelevanceMap[key] = [...new Set(zoneRelevanceMap[key])];
    }
  }

  // Quality summary from L10
  const quality = data?.quality;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      {/* Pipeline health strip */}
      {quality && (
        <div className="eev-quality-strip" style={{
          display: "flex", gap: "4px", padding: "8px", marginBottom: "6px",
          borderRadius: "8px", background: "rgba(0,0,0,0.2)",
          border: "1px solid rgba(71,85,105,0.08)",
        }}>
          <QualityChip label="Surfaces" value={`${quality.surfaces_generated}`} ok={quality.surfaces_generated > 0} />
          <QualityChip label="Zones" value={`${quality.zones_generated}`} ok={quality.zones_generated > 0} />
          <QualityChip label="Reliability" value={`${(quality.reliability_score * 100).toFixed(0)}%`} ok={quality.reliability_score > 0.6} />
          <QualityChip label="Mode" value={quality.degradation_mode === "NORMAL" ? "OK" : quality.degradation_mode} ok={quality.degradation_mode === "NORMAL"} />
        </div>
      )}

      {/* Engine list */}
      {engines.map(engine => (
        <EngineCardExpert
          key={engine.id}
          engine={engine}
          isExpanded={expandedEngine === engine.id}
          onToggle={() => onToggleEngine(expandedEngine === engine.id ? null : engine.id)}
          onAskBrain={onAskBrain}
          zoneRelevance={zoneRelevanceMap[engine.id] || []}
        />
      ))}

      {/* Quality warnings */}
      {quality && quality.warnings.length > 0 && (
        <div className="eev-warnings" style={{
          marginTop: "6px", padding: "8px 10px", borderRadius: "8px",
          background: "rgba(251,191,36,0.04)", border: "1px solid rgba(251,191,36,0.1)",
        }}>
          <div style={{ fontSize: "12px", color: "#fbbf24", fontWeight: 700, textTransform: "uppercase", marginBottom: "6px" }}>
            Pipeline Warnings ({quality.warnings.length})
          </div>
          {quality.warnings.map((w, i) => (
            <div key={i} style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "3px" }}>⚠ {w}</div>
          ))}
        </div>
      )}

      {/* Full pipeline debate */}
      <div style={{ display: "flex", gap: "6px", marginTop: "6px" }}>
        <button
          onClick={() => onAskBrain("Provide a complete pipeline diagnostic: which engines are underperforming, why, and how does this affect the overall field assessment confidence?")}
          style={{
            flex: 1, padding: "8px", borderRadius: "6px",
            border: "1px solid rgba(99,102,241,0.15)", background: "rgba(99,102,241,0.06)",
            color: "#a5b4fc", fontSize: "12px", fontWeight: 700, cursor: "pointer",
          }}
        >
          🔬 Pipeline Diagnostic
        </button>
        <button
          onClick={() => onAskBrain("What data sources are missing or degraded? How would additional ground truth change the confidence levels?")}
          style={{
            flex: 1, padding: "8px", borderRadius: "6px",
            border: "1px solid rgba(251,191,36,0.15)", background: "rgba(251,191,36,0.06)",
            color: "#fbbf24", fontSize: "12px", fontWeight: 700, cursor: "pointer",
          }}
        >
          📡 Data Gaps
        </button>
      </div>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────
function QualityChip({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div style={{ flex: 1, textAlign: "center" }}>
      <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
      <div style={{ fontSize: "13px", color: ok ? "#4ade80" : "#fbbf24", fontFamily: "monospace", fontWeight: 700 }}>{value}</div>
    </div>
  );
}
