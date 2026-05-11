"use client";

/**
 * RawDataSidebar — Right collapsible sidebar.
 *
 * Uses useLayer10 for surface stats + useePlotIntelligence for assimilation/raw data.
 */

import { useState, useMemo } from "react";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import { useLayer10, MODE_SURFACE_MAP, MODE_CONFIG } from "@/hooks/useLayer10";
import HistogramDrawer from "./HistogramDrawer";

type SidebarTab = "analysis" | "raw";

function SourceComparisonTable({ data }: { data: Record<string, unknown> | null }) {
  if (!data) return <div style={styles.emptyState}>No raw data available</div>;

  const sources = Object.entries(data).filter(([, v]) => v && typeof v === "object" && !Array.isArray(v));
  if (sources.length === 0) return <div style={styles.emptyState}>No sources loaded</div>;

  return (
    <div style={{ overflowX: "auto" }}>
      {sources.map(([key, val]) => (
        <div key={key} style={{
          marginBottom: "10px", borderRadius: "10px",
          border: "1px solid rgba(71, 85, 105, 0.15)",
          overflow: "hidden",
        }}>
          <div style={{
            padding: "8px 12px",
            background: "rgba(71, 85, 105, 0.1)",
            fontSize: "0.78rem", fontWeight: 700,
            color: "#e2e8f0", textTransform: "uppercase",
            letterSpacing: "0.04em",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span>{key.replace(/_/g, " ")}</span>
            <span style={{ fontSize: "0.7rem", color: "#64748b", fontWeight: 400 }}>
              {typeof val === "object" && val !== null ? `${Object.keys(val).length} fields` : "—"}
            </span>
          </div>
          <div style={{ padding: "6px 12px" }}>
            {typeof val === "object" && val !== null &&
              Object.entries(val as Record<string, unknown>)
                .filter(([, v]) => typeof v !== "object" || v === null)
                .slice(0, 12)
                .map(([field, fieldVal]) => (
                  <div key={field} style={{
                    display: "flex", justifyContent: "space-between",
                    padding: "4px 0",
                    borderBottom: "1px solid rgba(71, 85, 105, 0.06)",
                    fontSize: "0.78rem",
                  }}>
                    <span style={{ color: "#94a3b8" }}>{field}</span>
                    <span style={{ color: "#f1f5f9", fontFamily: "monospace", fontWeight: 500 }}>
                      {fieldVal === null ? "null" : typeof fieldVal === "number" ? fieldVal.toFixed(3) : String(fieldVal)}
                    </span>
                  </div>
                ))
            }
          </div>
        </div>
      ))}
    </div>
  );
}

export default function RawDataSidebar() {
  const l10 = useLayer10();
  const pi = usePlotIntelligence();
  const { detailMode, dataView, setDataView, rawData, showAnalysisSidebar, setShowAnalysisSidebar, assimilation, engines } = pi;

  const [activeTab, setActiveTab] = useState<SidebarTab>("analysis");

  // ── These MUST be above any early return (Rules of Hooks) ────────────────
  const activeMode = l10.activeMode;
  const modeConfig = MODE_CONFIG[activeMode];
  const surfaceType = MODE_SURFACE_MAP[activeMode];
  const activeSurface = l10.activeSurface;

  const surfaceStats = useMemo(() => {
    if (!activeSurface?.values) return null;
    const vals: number[] = [];
    for (const row of activeSurface.values)
      for (const v of row)
        if (v !== null && v !== undefined && !isNaN(v)) vals.push(v);
    if (vals.length === 0) return null;
    const sum = vals.reduce((a, b) => a + b, 0);
    const mean = sum / vals.length;
    const sorted = [...vals].sort((a, b) => a - b);
    const p10 = sorted[Math.floor(vals.length * 0.1)];
    const p90 = sorted[Math.floor(vals.length * 0.9)];
    const std = Math.sqrt(vals.reduce((a, v) => a + (v - mean) ** 2, 0) / vals.length);
    return { mean, std, p10, p90, count: vals.length };
  }, [activeSurface]);

  const explainPack = l10.data?.explainability_pack?.[surfaceType];
  // ─────────────────────────────────────────────────────────────────────────
  // All hooks are now above — safe to early return below.

  if (!showAnalysisSidebar) {
    return (
      <button
        onClick={() => setShowAnalysisSidebar(true)}
        style={{
          position: "absolute", top: "100px", right: "12px", zIndex: 20,
          width: "40px", height: "40px", borderRadius: "12px",
          background: "rgba(8, 12, 25, 0.92)", backdropFilter: "blur(20px)",
          border: "1px solid rgba(71, 85, 105, 0.25)",
          color: "#e2e8f0", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1.1rem", transition: "all 0.2s",
        }}
        onMouseOver={e => e.currentTarget.style.background = "rgba(8, 12, 25, 1)"}
        onMouseOut={e => e.currentTarget.style.background = "rgba(8, 12, 25, 0.9)"}
        title="Show Analysis"
      >
        📊
      </button>
    );
  }


  return (
    <div style={{
      position: "absolute", top: "100px", right: "12px", bottom: "170px",
      width: "280px", zIndex: 20,
      background: "rgba(8, 12, 25, 0.92)",
      backdropFilter: "blur(20px)",
      border: "1px solid rgba(71, 85, 105, 0.2)",
      borderRadius: "16px",
      display: "flex", flexDirection: "column",
      overflow: "hidden",
      boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
    }}>
      {/* Header */}
      <div style={{
        padding: "14px 16px 8px",
        borderBottom: "1px solid rgba(71, 85, 105, 0.15)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f1f5f9" }}>
            {detailMode === "expert" ? `${activeMode.replace(/_/g, " ").toUpperCase()} — Analysis` : modeConfig.label}
          </div>
          <button
            onClick={() => setShowAnalysisSidebar(false)}
            style={{
              width: "28px", height: "28px", borderRadius: "8px",
              background: "rgba(71, 85, 105, 0.2)", border: "none",
              color: "#94a3b8", cursor: "pointer", fontSize: "0.8rem",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >✕</button>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: "4px" }}>
          {(["analysis", ...(detailMode === "expert" ? ["raw"] : [])] as SidebarTab[]).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: "6px 14px", borderRadius: "8px",
                fontSize: "0.8rem", fontWeight: 600, cursor: "pointer", border: "none",
                background: activeTab === tab ? "rgba(99, 102, 241, 0.15)" : "transparent",
                color: activeTab === tab ? "#a5b4fc" : "#94a3b8",
              }}
            >
              {tab === "analysis" ? "Analysis" : "Raw Data"}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }} className="custom-scrollbar">

        {activeTab === "analysis" && (
          <>
            {surfaceStats ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", marginBottom: "12px" }}>
                {[
                  { label: "Mean", value: surfaceStats.mean.toFixed(3), color: modeConfig.colors[1] },
                  { label: "σ", value: `±${surfaceStats.std.toFixed(3)}`, color: "#cbd5e1" },
                  { label: "P10", value: surfaceStats.p10.toFixed(3), color: modeConfig.colors[0] },
                  { label: "P90", value: surfaceStats.p90.toFixed(3), color: modeConfig.colors[2] },
                ].map(stat => (
                  <div key={stat.label} style={{
                    padding: "10px 12px", borderRadius: "10px",
                    background: "rgba(71, 85, 105, 0.1)", border: "1px solid rgba(71, 85, 105, 0.1)",
                  }}>
                    <div style={{ fontSize: "0.95rem", fontWeight: 700, color: stat.color, fontFamily: "monospace" }}>{stat.value}</div>
                    <div style={{ fontSize: "0.7rem", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase" }}>{stat.label}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={styles.emptyState}>No surface data — waiting for L10</div>
            )}

            {explainPack?.summary && (
              <div style={{
                padding: "10px 12px", borderRadius: "10px",
                background: "rgba(99, 102, 241, 0.08)", border: "1px solid rgba(99, 102, 241, 0.15)", marginBottom: "10px",
              }}>
                <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#a5b4fc", textTransform: "uppercase", marginBottom: "6px" }}>AI Summary</div>
                <p style={{ fontSize: "0.82rem", color: "#e2e8f0", lineHeight: 1.6, margin: 0 }}>{explainPack.summary}</p>
              </div>
            )}

            {assimilation && (
              <div style={{
                padding: "10px 12px", borderRadius: "10px",
                background: assimilation.assimilated ? "rgba(34, 197, 94, 0.06)" : "rgba(251, 191, 36, 0.06)",
                border: `1px solid ${assimilation.assimilated ? "rgba(34, 197, 94, 0.15)" : "rgba(251, 191, 36, 0.15)"}`,
              }}>
                <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: "6px" }}>Data Assimilation</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {assimilation.sources_used.map(src => (
                    <span key={src} style={{ padding: "3px 8px", borderRadius: "6px", fontSize: "0.72rem", fontWeight: 600, background: "rgba(34, 197, 94, 0.1)", color: "#4ade80" }}>{src}</span>
                  ))}
                </div>
                <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: "6px" }}>
                  Freshness: {(assimilation.freshness_score * 100).toFixed(0)}% · {assimilation.sources_count} sources
                </div>
              </div>
            )}

            {detailMode === "expert" && (
              <div style={{ marginTop: "10px" }}>
                <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: "6px" }}>Contributing Engines</div>
                {engines.filter(e => ["L0", "L1", "L2", "L3", "L10"].includes(e.id)).map(e => (
                  <div key={e.id} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "5px 0", fontSize: "0.78rem" }}>
                    <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: e.status === "OK" ? "#4ade80" : e.status === "DEGRADED" ? "#fbbf24" : "#f87171" }} />
                    <span style={{ color: "#e2e8f0", fontWeight: 600 }}>{e.id}</span>
                    <span style={{ color: "#94a3b8" }}>{e.name}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {activeTab === "raw" && detailMode === "expert" && (
          <>
            <div style={{ display: "flex", gap: "4px", marginBottom: "12px", background: "rgba(71, 85, 105, 0.1)", borderRadius: "10px", padding: "4px" }}>
              {(["assimilated", "raw"] as const).map(view => (
                <button key={view} onClick={() => setDataView(view)} style={{
                  flex: 1, padding: "8px 10px", borderRadius: "8px", fontSize: "0.8rem", fontWeight: 700,
                  cursor: "pointer", border: "none", textTransform: "uppercase",
                  background: dataView === view ? (view === "assimilated" ? "rgba(34, 197, 94, 0.15)" : "rgba(99, 102, 241, 0.15)") : "transparent",
                  color: dataView === view ? (view === "assimilated" ? "#4ade80" : "#a5b4fc") : "#64748b",
                }}>{view === "assimilated" ? "Assimilated" : "Raw"}</button>
              ))}
            </div>
            {dataView === "raw" ? (
              <SourceComparisonTable data={rawData as Record<string, unknown> | null} />
            ) : (
              <div style={styles.emptyState}>Assimilated view shows fused data. Switch to Raw to see individual source responses.</div>
            )}
          </>
        )}
      </div>

      {/* Embedded Histogram */}
      <div style={{
        borderTop: "1px solid rgba(71, 85, 105, 0.15)",
        flexShrink: 0,
      }}>
        <HistogramDrawer
          histogram={l10.activeHistogram}
          delta={l10.activeDelta}
          colors={l10.activeColors}
          expanded={l10.histogramExpanded}
          onToggle={() => l10.setHistogramExpanded(!l10.histogramExpanded)}
          surfaceLabel={modeConfig?.label || activeMode}
        />
      </div>

      {/* Footer */}
      <div style={{
        padding: "10px 16px", borderTop: "1px solid rgba(71, 85, 105, 0.15)",
        display: "flex", justifyContent: "space-between",
        fontSize: "0.72rem", color: "#64748b", fontWeight: 600, textTransform: "uppercase",
        flexShrink: 0,
      }}>
        <span>{surfaceType?.replace(/_/g, " ") || "—"}</span>
        <span style={{ color: "#a5b4fc" }}>L10</span>
      </div>
    </div>
  );
}

const styles = {
  emptyState: {
    padding: "20px", textAlign: "center" as const, fontSize: "0.82rem", color: "#94a3b8",
    background: "rgba(71, 85, 105, 0.06)", borderRadius: "10px",
    border: "1px dashed rgba(71, 85, 105, 0.2)", lineHeight: 1.6,
  },
};
