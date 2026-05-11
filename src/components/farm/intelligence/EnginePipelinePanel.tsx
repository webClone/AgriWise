"use client";

/**
 * EnginePipelinePanel — Left sidebar showing all 10 AgriBrain engine layers.
 * 
 * Farmer mode: Simplified cards with emoji + status + 1-line finding
 * Expert mode: Full detail with raw values, model versions, source timestamps
 */

import { usePlotIntelligence, type EngineStatus } from "@/hooks/usePlotIntelligence";
import { useLayer10 } from "@/hooks/useLayer10";
import SurfaceLegendBar from "@/components/farm/map/SurfaceLegendBar";

const STATUS_COLORS: Record<string, { bg: string; border: string; dot: string; text: string }> = {
  OK: { bg: "rgba(34, 197, 94, 0.08)", border: "rgba(34, 197, 94, 0.2)", dot: "#4ade80", text: "Good" },
  DEGRADED: { bg: "rgba(251, 191, 36, 0.08)", border: "rgba(251, 191, 36, 0.2)", dot: "#fbbf24", text: "Watch" },
  OFFLINE: { bg: "rgba(239, 68, 68, 0.08)", border: "rgba(239, 68, 68, 0.2)", dot: "#f87171", text: "Action Needed" },
  LOADING: { bg: "rgba(99, 102, 241, 0.08)", border: "rgba(99, 102, 241, 0.2)", dot: "#818cf8", text: "Loading" },
};

// Custom widgets for Expert Mode
function ExpertWidget({ engine }: { engine: EngineStatus }) {
  const { id, data } = engine;
  
  if (data?.expert_metrics && Array.isArray(data.expert_metrics)) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "10px" }}>
        {data.expert_metrics.map((metric: any, idx: number) => {
          const conf = metric.confidence ?? 0;
          const color = conf >= 0.85 ? "#4ade80" : conf >= 0.6 ? "#fbbf24" : "#f87171";
          return (
            <div key={idx} style={{ background: "rgba(0,0,0,0.35)", borderRadius: "8px", padding: "8px", border: "1px solid rgba(71, 85, 105, 0.15)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontSize: "0.75rem", color: "#e2e8f0", fontWeight: 500 }}>{metric.name}</div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ fontSize: "0.85rem", color: "#f1f5f9", fontWeight: 600 }}>{metric.value}</div>
                  <div style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: "10px", background: `${color}20`, color: color, border: `1px solid ${color}40` }}>
                    {(Number(conf) * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              {metric.reason && (
                <div style={{ fontSize: "0.65rem", color: "#94a3b8", marginTop: "4px", lineHeight: 1.3 }}>
                  {metric.reason}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  switch (id) {
    case "L0":
      if (id === "L0") {
        return (
          <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
            <div style={{ background: "rgba(0,0,0,0.35)", borderRadius: "8px", padding: "8px", flex: 1, border: "1px solid rgba(71, 85, 105, 0.15)" }}>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>Current Temp</div>
              <div style={{ fontSize: "1.1rem", color: "#f1f5f9", fontWeight: 600 }}>{String(data?.temp_current ?? "--")}°C</div>
            </div>
            <div style={{ background: "rgba(0,0,0,0.35)", borderRadius: "8px", padding: "8px", flex: 1, border: "1px solid rgba(71, 85, 105, 0.15)" }}>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>Rain Prob</div>
              <div style={{ fontSize: "1.1rem", color: "#60a5fa", fontWeight: 600 }}>{String(data?.rain_prob ?? "0")}%</div>
            </div>
          </div>
        );
      }
      return (
        <div style={{ background: "rgba(0,0,0,0.35)", borderRadius: "8px", padding: "10px", marginTop: "10px", border: "1px solid rgba(71, 85, 105, 0.15)" }}>
          <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Awaiting detailed metrics...</div>
        </div>
      );
    case "L2":
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "10px" }}>
          <div style={{ background: "rgba(0,0,0,0.35)", borderRadius: "8px", padding: "8px", border: "1px solid rgba(71, 85, 105, 0.15)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>Mean NDVI</span>
              <span style={{ fontSize: "0.75rem", color: "#4ade80", fontWeight: 600 }}>{data?.ndvi_mean ? Number(data.ndvi_mean).toFixed(2) : "--"}</span>
            </div>
            <div style={{ width: "100%", background: "rgba(255,255,255,0.1)", borderRadius: "4px", height: "6px" }}>
              <div style={{ width: `${(Number(data?.ndvi_mean) || 0) * 100}%`, background: "#4ade80", height: "100%", borderRadius: "4px" }} />
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem" }}>
            <span style={{ color: "#94a3b8" }}>Canopy Cover: <span style={{ color: "#e2e8f0" }}>{String(data?.canopy_cover_pct ?? "--")}%</span></span>
            <span style={{ color: "#94a3b8" }}>Variability: <span style={{ color: "#fbbf24" }}>{String(data?.spatial_variability ?? "--")}</span></span>
          </div>
        </div>
      );
    case "L3":
      return (
        <div style={{ display: "flex", gap: "8px", marginTop: "10px" }}>
          <div style={{ background: "rgba(0,0,0,0.35)", borderRadius: "8px", padding: "8px", flex: 1, border: "1px solid rgba(71, 85, 105, 0.15)" }}>
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>Deficit</div>
            <div style={{ fontSize: "1.1rem", color: "#f87171", fontWeight: 600 }}>{Math.abs(Number(data?.deficit_mm) || 0).toFixed(1)}mm</div>
          </div>
          <div style={{ background: "rgba(0,0,0,0.35)", borderRadius: "8px", padding: "8px", flex: 1, border: "1px solid rgba(71, 85, 105, 0.15)" }}>
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>ET0 Today</div>
            <div style={{ fontSize: "1.1rem", color: "#f1f5f9", fontWeight: 600 }}>{Number(data?.et0_mm || 0).toFixed(1)}mm</div>
          </div>
        </div>
      );
    case "L10":
      return (
        <div style={{ background: "rgba(0,0,0,0.35)", borderRadius: "8px", padding: "10px", marginTop: "10px", border: "1px solid rgba(71, 85, 105, 0.15)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
            <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Overall Quality Score</span>
            <span style={{ fontSize: "0.75rem", color: "#4ade80", fontWeight: 600 }}>{(Number(data?.overall_quality_score || 0) * 100).toFixed(0)}%</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
            <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Hard Gates Passed</span>
            <span style={{ fontSize: "0.75rem", color: "#e2e8f0" }}>{String(data?.hard_gates_passed ?? "--")}/12</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Spatial Anomaly</span>
            <span style={{ fontSize: "0.7rem", color: data?.spatial_anomaly_trustworthy ? "#4ade80" : "#fbbf24" }}>
              {data?.spatial_anomaly_trustworthy ? "Trustworthy" : "Watch"}
            </span>
          </div>
        </div>
      );
    default:
      return (
        <div style={{
          background: "rgba(0,0,0,0.35)", borderRadius: "8px",
          padding: "8px 10px", marginTop: "10px",
          fontFamily: "monospace", fontSize: "0.7rem",
          color: "#94a3b8", maxHeight: "120px", overflow: "auto",
          border: "1px solid rgba(71, 85, 105, 0.15)",
        }}>
          {Object.entries(data || {}).slice(0, 6).map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
              <span style={{ color: "#94a3b8" }}>{k}</span>
              <span style={{ color: "#e2e8f0" }}>
                {typeof v === "object" ? (v === null ? "null" : "{ … }") : String(v)}
              </span>
            </div>
          ))}
        </div>
      );
  }
}

function EngineCard({ engine, isExpanded, onToggle }: {
  engine: EngineStatus;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const { detailMode, dataView } = usePlotIntelligence();
  const { openDecideMode } = useLayer10();
  const colors = STATUS_COLORS[engine.status] || STATUS_COLORS.OFFLINE;

  return (
    <div
      style={{
        background: isExpanded ? colors.bg : "transparent",
        border: `1px solid ${isExpanded ? colors.border : "transparent"}`,
        borderRadius: "12px",
        transition: "all 0.2s ease",
        cursor: "pointer",
        marginBottom: "2px",
      }}
      onClick={onToggle}
      onMouseOver={e => {
        if (!isExpanded) e.currentTarget.style.background = "rgba(255,255,255,0.04)";
      }}
      onMouseOut={e => {
        if (!isExpanded) e.currentTarget.style.background = "transparent";
      }}
    >
      {/* Compact row */}
      <div style={{
        display: "flex", alignItems: "center", gap: "10px",
        padding: "10px 12px",
      }}>
        {/* Status dot */}
        <div style={{
          width: "8px", height: "8px", borderRadius: "50%",
          background: colors.dot, flexShrink: 0,
          boxShadow: `0 0 8px ${colors.dot}50`,
        }} />

        {/* Icon */}
        <span style={{ fontSize: "1.1rem", lineHeight: 1 }}>{engine.icon}</span>

        {/* Name + Status */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: "0.82rem", fontWeight: 600, color: "#f1f5f9",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {detailMode === "expert" ? `${engine.id} ${engine.name}` : engine.name}
          </div>
          <div style={{
            fontSize: "0.72rem", color: "#94a3b8",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {engine.statusLabel}
          </div>
        </div>

        {/* Expand arrow */}
        <span style={{
          fontSize: "0.7rem", color: "#64748b",
          transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
          transition: "transform 0.2s",
        }}>
          ▶
        </span>
      </div>

      {/* Expanded detail */}
      {isExpanded && (
        <div style={{
          padding: "0 12px 12px 40px",
          fontSize: "0.78rem", color: "#cbd5e1",
          lineHeight: 1.7,
          borderTop: `1px solid ${colors.border}`,
          marginTop: "-2px", paddingTop: "10px",
        }}>
          {detailMode === "farmer" ? (
            <>
              <p style={{ margin: "0 0 8px 0", color: "#e2e8f0", fontSize: "0.85rem", lineHeight: 1.5 }}>
                {String(engine.data?.farmer_summary || engine.summary)}
              </p>
              
              {engine.data?.why_it_matters && (
                <div style={{ 
                  margin: "8px 0", padding: "8px", borderRadius: "8px", 
                  background: "rgba(255,255,255,0.03)", border: "1px dashed rgba(255,255,255,0.1)",
                  fontSize: "0.75rem", color: "#94a3b8"
                }}>
                  <strong style={{ color: "#e2e8f0", display: "block", marginBottom: "2px" }}>Why it matters:</strong>
                  {String(engine.data.why_it_matters)}
                </div>
              )}
              
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "10px" }}>
                <div style={{
                  display: "inline-flex", alignItems: "center", gap: "6px",
                  padding: "4px 10px", borderRadius: "6px",
                  background: colors.bg, border: `1px solid ${colors.border}`,
                  fontSize: "0.72rem", fontWeight: 600, color: colors.dot,
                }}>
                  <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: colors.dot }} />
                  {colors.text}
                </div>
                <button
                  onClick={(e) => { 
                    e.stopPropagation(); 
                    openDecideMode(`Can you explain the current status and findings of the ${engine.name} layer?`); 
                  }}
                  style={{
                    background: "rgba(99, 102, 241, 0.15)", border: "1px solid rgba(99, 102, 241, 0.3)",
                    color: "#a5b4fc", padding: "4px 10px", borderRadius: "6px",
                    fontSize: "0.7rem", fontWeight: 600, cursor: "pointer",
                    transition: "all 0.2s"
                  }}
                  onMouseOver={e => e.currentTarget.style.background = "rgba(99, 102, 241, 0.25)"}
                  onMouseOut={e => e.currentTarget.style.background = "rgba(99, 102, 241, 0.15)"}
                >
                  Ask AgriBrain why
                </button>
              </div>
            </>
          ) : (
            <>
              <p style={{ margin: "0 0 8px 0", fontSize: "0.75rem", color: "#cbd5e1" }}>
                {String(engine.data?.expert_summary || engine.summary)}
              </p>
              
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                {engine.data?.confidence_level !== undefined ? (
                  <div 
                    title={String(engine.data.confidence_reason || "Confidence based on model agreement")}
                    style={{ 
                      fontSize: "0.7rem", color: "#94a3b8", display: "flex", alignItems: "center", gap: "4px",
                      cursor: "help", padding: "2px 6px", borderRadius: "4px", background: "rgba(0,0,0,0.2)",
                      border: "1px solid rgba(255,255,255,0.05)"
                    }}
                  >
                    <span style={{ color: Number(engine.data.confidence_level) > 0.8 ? "#4ade80" : Number(engine.data.confidence_level) > 0.6 ? "#fbbf24" : "#f87171" }}>
                      ●
                    </span>
                    Confidence: {(Number(engine.data.confidence_level || 0) * 100).toFixed(0)}%
                  </div>
                ) : (
                  <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>
                    {String(engine.data?.data_freshness || "Updated just now")}
                  </div>
                )}
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    style={{
                      background: "none", border: "none", color: "#818cf8",
                      fontSize: "0.65rem", cursor: "pointer", textTransform: "uppercase",
                      fontWeight: 600, letterSpacing: "0.05em", padding: 0
                    }}
                    onClick={(e) => { 
                      e.stopPropagation(); 
                      openDecideMode(`Can you explain the current status and findings of the ${engine.name} layer?`); 
                    }}
                  >
                    Ask Why
                  </button>
                  <button
                    style={{
                      background: "none", border: "none", color: "#94a3b8",
                      fontSize: "0.65rem", cursor: "pointer", textTransform: "uppercase",
                      fontWeight: 600, letterSpacing: "0.05em", padding: 0
                    }}
                    onClick={(e) => { 
                      e.stopPropagation(); 
                      openDecideMode(`What are the alternative interpretations or edge cases for the ${engine.name} layer?`); 
                    }}
                  >
                    Alternatives
                  </button>
                </div>
              </div>

              {engine.data && Object.keys(engine.data).length > 0 && (
                <ExpertWidget engine={engine} />
              )}
              
              {engine.data?.why_it_matters && (
                <details style={{ marginTop: "10px", fontSize: "0.7rem", color: "#94a3b8" }}>
                  <summary style={{ cursor: "pointer", outline: "none", fontWeight: 600 }}>Why this matters</summary>
                  <div style={{ padding: "6px 8px", background: "rgba(0,0,0,0.2)", borderRadius: "4px", marginTop: "4px" }}>
                    {String(engine.data.why_it_matters)}
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function EnginePipelinePanel() {
  const { engines, expandedEngine, setExpandedEngine, showEnginePanel, setShowEnginePanel, detailMode } = usePlotIntelligence();
  const l10 = useLayer10();

  if (!showEnginePanel) {
    return (
      <button
        onClick={() => setShowEnginePanel(true)}
        style={{
          position: "absolute", top: "100px", left: "12px", zIndex: 20,
          width: "40px", height: "40px", borderRadius: "12px",
          background: "rgba(8, 12, 25, 0.92)", backdropFilter: "blur(20px)",
          border: "1px solid rgba(71, 85, 105, 0.25)",
          color: "#e2e8f0", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1.1rem",
          transition: "all 0.2s",
        }}
        onMouseOver={e => e.currentTarget.style.background = "rgba(8, 12, 25, 1)"}
        onMouseOut={e => e.currentTarget.style.background = "rgba(8, 12, 25, 0.9)"}
        title="Show Engine Panel"
      >
        🧠
      </button>
    );
  }

  // Compute system confidence from per-metric confidence scores
  // Engines without expert_metrics get 0.5 (honest "unknown") not inflated 0.8
  const { confidencePercent, okCount, total } = (() => {
    let totalConf = 0;
    let metricCount = 0;
    for (const e of engines) {
      const metrics = (e.data?.expert_metrics as any[]) || [];
      if (metrics.length > 0) {
        for (const m of metrics) {
          const c = Number(m.confidence ?? 0);
          totalConf += c;
          metricCount++;
        }
      } else {
        // No metrics = unknown confidence, not assumed good
        totalConf += 0.5;
        metricCount++;
      }
    }
    const meanConf = metricCount > 0 ? totalConf / metricCount : 0;
    return {
      confidencePercent: Math.round(meanConf * 100),
      // Only count truly OK engines, not DEGRADED
      okCount: engines.filter(e => e.status === "OK").length,
      total: engines.length,
    };
  })();
  
  // Progress Ring logic
  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (confidencePercent / 100) * circumference;

  return (
    <div
      style={{
        position: "absolute", top: "100px", left: "12px", bottom: "170px",
        width: "280px", zIndex: 20,
        background: "rgba(8, 12, 25, 0.92)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(71, 85, 105, 0.2)",
        borderRadius: "16px",
        display: "flex", flexDirection: "column",
        overflowY: "hidden",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
      }}
    >
      {/* Header */}
      <div style={{
        padding: "16px",
        borderBottom: "1px solid rgba(71, 85, 105, 0.15)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Progress Ring */}
          <div style={{ position: "relative", width: "40px", height: "40px" }}>
            <svg width="40" height="40" style={{ transform: "rotate(-90deg)" }}>
              <circle
                cx="20" cy="20" r={radius}
                fill="transparent"
                stroke="rgba(71, 85, 105, 0.3)"
                strokeWidth="4"
              />
              <circle
                cx="20" cy="20" r={radius}
                fill="transparent"
                stroke={confidencePercent >= 75 ? "#4ade80" : confidencePercent >= 50 ? "#fbbf24" : "#f87171"}
                strokeWidth="4"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{ transition: "stroke-dashoffset 0.5s ease" }}
              />
            </svg>
            <div style={{
              position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "0.65rem", fontWeight: 700, color: "#f1f5f9"
            }}>
              {confidencePercent}%
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f1f5f9", letterSpacing: "0.01em" }}>
              System Confidence
            </div>
            <div style={{ fontSize: "0.7rem", color: "#94a3b8", marginTop: "2px" }}>
              {okCount}/{total} engines OK{okCount < total ? ` (${total - okCount} degraded)` : ""}
            </div>
          </div>
        </div>
        <button
          onClick={() => setShowEnginePanel(false)}
          style={{
            width: "28px", height: "28px", borderRadius: "8px",
            background: "rgba(71, 85, 105, 0.2)", border: "none",
            color: "#94a3b8", cursor: "pointer", fontSize: "0.8rem",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s",
          }}
          onMouseOver={e => e.currentTarget.style.background = "rgba(71, 85, 105, 0.35)"}
          onMouseOut={e => e.currentTarget.style.background = "rgba(71, 85, 105, 0.2)"}
        >
          ✕
        </button>
      </div>

      {/* Engine list */}
      <div style={{
        flex: 1, overflowY: "auto", padding: "6px 8px",
      }} className="custom-scrollbar">
        {engines.map((engine) => (
          <EngineCard
            key={engine.id}
            engine={engine}
            isExpanded={expandedEngine === engine.id}
            onToggle={() => setExpandedEngine(expandedEngine === engine.id ? null : engine.id)}
          />
        ))}
      </div>

      {/* Embedded Legend */}
      <div style={{
        borderTop: "1px solid rgba(71, 85, 105, 0.15)",
        padding: "10px 8px 6px",
        flexShrink: 0,
      }}>
        <SurfaceLegendBar
          activeMode={l10.activeMode}
          detailMode={detailMode}
          groundingClass={l10.data?.quality?.grounding_class}
          coverageRatio={l10.data?.quality?.coverage_ratio ?? null}
        />
      </div>

      {/* Footer */}
      <div style={{
        padding: "10px 16px",
        borderTop: "1px solid rgba(71, 85, 105, 0.15)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        fontSize: "0.7rem", color: "#64748b", fontWeight: 600,
        textTransform: "uppercase", letterSpacing: "0.05em",
      }}>
        <span>SIRE v11</span>
        <span style={{ color: "#4ade80" }}>● LIVE</span>
      </div>
    </div>
  );
}
