"use client";

/**
 * EnginePipelinePanel — Left sidebar showing AgriBrain engine pipeline.
 *
 * Dual-mode:
 *   Farmer: Grouped categories with plain-language summaries
 *   Expert: Per-engine expandable cards with detailed metrics
 *
 * Rich system status dashboard showing data pipeline health, assimilation,
 * sensor context, crop phenology, and quality indicators.
 *
 * All data from real engine statuses + L10 quality + PI context. Zero synthetic data.
 */

import { useMemo, useState } from "react";
import { usePlotIntelligence, type EngineStatus } from "@/hooks/usePlotIntelligence";
import { useLayer10 } from "@/hooks/useLayer10";
import SurfaceLegendBar from "@/components/farm/map/SurfaceLegendBar";
import EngineFarmerView from "./EngineFarmerView";
import EngineExpertView from "./EngineExpertView";

// ── System Status Dashboard ─────────────────────────────────────────────
function SystemStatusDashboard({
  detailMode,
  engines,
  assimilation,
  cacheStatus,
  refreshing,
  lastCaptured,
  cropPhenology,
  sensorContext,
  userInputs,
  l10Quality,
  l10Provenance,
  l10Timestamp,
  mapSemantics,
  l10Grid,
}: {
  detailMode: "farmer" | "expert";
  engines: any[];
  assimilation: any;
  cacheStatus: string | null;
  refreshing: boolean;
  lastCaptured: string | null;
  cropPhenology: any;
  sensorContext: any;
  userInputs: any;
  l10Quality: any;
  l10Provenance: any;
  l10Timestamp: string | null;
  mapSemantics: string;
  l10Grid: { height: number; width: number } | null;
}) {
  // Engine status breakdown
  const statusCounts: Record<string, number> = { OK: 0, DEGRADED: 0, SKIPPED: 0, UNAVAILABLE: 0, FAILED: 0, OFFLINE: 0, LOADING: 0 };
  for (const e of engines) {
    statusCounts[e.status as keyof typeof statusCounts] = (statusCounts[e.status as keyof typeof statusCounts] || 0) + 1;
  }

  // Freshness color
  const freshnessColor = assimilation?.freshness_score > 0.8 ? "#4ade80" :
    assimilation?.freshness_score > 0.5 ? "#fbbf24" : "#f87171";

  // Cache color
  const cacheColor = cacheStatus === "HIT" ? "#4ade80" : cacheStatus === "REFRESHED" ? "#60a5fa" :
    cacheStatus === "STALE" ? "#fbbf24" : "#94a3b8";

  // Degradation
  const degradationMode = l10Quality?.degradation_mode || "UNKNOWN";
  const isNormal = degradationMode === "NORMAL";

  // Relative time
  const timeAgo = (iso: string | null | undefined) => {
    if (!iso) return null;
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  const capturedAgo = timeAgo(lastCaptured);
  const l10Ago = timeAgo(l10Timestamp);

  return (
    <div style={{
      padding: "8px 10px",
      borderBottom: "1px solid rgba(71,85,105,0.12)",
      display: "flex", flexDirection: "column", gap: "6px",
      flexShrink: 0,
    }}>

      {/* ── Row 1: Engine Pipeline Status Bar ────────────────────── */}
      <div style={{ display: "flex", gap: "2px", height: "4px", borderRadius: "2px", overflow: "hidden" }}>
        {engines.map((e, i) => {
          const c = e.status === "OK" ? "#4ade80" : e.status === "DEGRADED" ? "#fbbf24" : e.status === "SKIPPED" ? "#64748b" : e.status === "LOADING" ? "#818cf8" : "#f87171";
          return <div key={i} style={{ flex: 1, background: c, transition: "background 0.3s" }} title={`${e.id}: ${e.status}`} />;
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "8px", color: "#64748b" }}>
        <span>{statusCounts.OK} OK · {statusCounts.DEGRADED} degraded · {statusCounts.SKIPPED} skipped · {statusCounts.FAILED + statusCounts.OFFLINE} failed</span>
        {refreshing && <span style={{ color: "#818cf8" }}>⟳ refreshing</span>}
      </div>

      {/* ── Row 2: Data Pipeline ──────────────────────────────────── */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
        gap: "4px",
      }}>
        {/* Assimilation / Data freshness */}
        <StatusChip
          icon="📡"
          label="Data"
          value={assimilation ? `${(assimilation.freshness_score * 100).toFixed(0)}%` : "—"}
          color={freshnessColor}
          subtitle={assimilation ? `${assimilation.sources_count} src` : undefined}
        />
        {/* Cache */}
        <StatusChip
          icon="💾"
          label="Cache"
          value={cacheStatus || "—"}
          color={cacheColor}
          subtitle={capturedAgo || undefined}
        />
        {/* L10 Pipeline */}
        <StatusChip
          icon="🧠"
          label="L10"
          value={isNormal ? "OK" : degradationMode.slice(0, 6)}
          color={isNormal ? "#4ade80" : "#fbbf24"}
          subtitle={l10Ago || undefined}
        />
      </div>

      {/* ── Row 3: Context Strip (Crop + Sensors + Area) ──────────── */}
      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
        {/* Crop stage */}
        {cropPhenology?.stage && (
          <ContextPill icon="🌱" label={cropPhenology.stage} detail={cropPhenology.dap != null ? `DAP ${cropPhenology.dap}` : cropPhenology.basis} />
        )}
        {/* Sensor network */}
        {sensorContext && sensorContext.count > 0 && (
          <ContextPill icon="📶" label={`${sensorContext.active}/${sensorContext.count} sensors`} detail={sensorContext.types?.join(", ")} />
        )}
        {/* Area */}
        {userInputs?.area_ha != null && (
          <ContextPill icon="📐" label={`${userInputs.area_ha} ha`} />
        )}
        {/* Soil */}
        {userInputs?.soil_type && (
          <ContextPill icon="🪨" label={userInputs.soil_type} detail={userInputs.soil_source} />
        )}
        {/* Irrigation */}
        {userInputs?.irrigation_type && (
          <ContextPill icon="💧" label={userInputs.irrigation_type} />
        )}
      </div>

      {/* ── Row 4: L10 Quality Grid (Expert only) ────────────────── */}
      {detailMode === "expert" && l10Quality && (
        <div style={{
          display: "flex", gap: "3px", flexWrap: "wrap",
        }}>
          <QualityTag label="Reliability" value={`${(l10Quality.reliability_score * 100).toFixed(0)}%`} ok={l10Quality.reliability_score > 0.6} />
          <QualityTag label="Surfaces" value={`${l10Quality.surfaces_generated}`} ok={l10Quality.surfaces_generated > 0} />
          <QualityTag label="Zones" value={`${l10Quality.zones_generated}`} ok={l10Quality.zones_generated > 0} />
          <QualityTag label="Grid" value={l10Grid ? `${l10Grid.height}×${l10Grid.width}` : "—"} ok={l10Quality.grid_alignment_ok} />
          <QualityTag label="Semantics" value={mapSemantics.replace(/_/g, " ").slice(0, 12)} ok={mapSemantics !== "no_data"} />
          {!isNormal && <QualityTag label="Degrade" value={degradationMode} ok={false} />}
        </div>
      )}

      {/* ── Data sources strip ────────────────────────────────────── */}
      {assimilation && assimilation.sources_used?.length > 0 && (
        <div style={{ display: "flex", gap: "3px", flexWrap: "wrap" }}>
          {assimilation.sources_used.map((s: string) => (
            <span key={s} style={{
              fontSize: "8px", padding: "1px 5px", borderRadius: "3px",
              background: "rgba(34,197,94,0.06)", color: "#4ade80",
              border: "1px solid rgba(34,197,94,0.08)", fontWeight: 600,
            }}>{s}</span>
          ))}
          {assimilation.dataAge_days > 0 && (
            <span style={{
              fontSize: "8px", padding: "1px 5px", borderRadius: "3px",
              background: assimilation.dataAge_days > 3 ? "rgba(248,113,113,0.06)" : "rgba(71,85,105,0.1)",
              color: assimilation.dataAge_days > 3 ? "#f87171" : "#94a3b8",
              fontWeight: 600,
            }}>
              {assimilation.dataAge_days.toFixed(1)}d old
            </span>
          )}
        </div>
      )}

      {/* ── Sensor live readings (if available) ──────────────────── */}
      {sensorContext && (sensorContext.soil_moisture_pct != null || sensorContext.field_temperature_c != null) && (
        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
          {sensorContext.field_temperature_c != null && (
            <SensorPill label="Temp" value={`${sensorContext.field_temperature_c.toFixed(1)}°C`} />
          )}
          {sensorContext.field_humidity_pct != null && (
            <SensorPill label="Humidity" value={`${sensorContext.field_humidity_pct.toFixed(0)}%`} />
          )}
          {sensorContext.soil_moisture_pct != null && (
            <SensorPill label="Soil" value={`${sensorContext.soil_moisture_pct.toFixed(1)}%`} />
          )}
          {sensorContext.soil_ec_ds_m != null && (
            <SensorPill label="EC" value={`${sensorContext.soil_ec_ds_m.toFixed(2)}`} />
          )}
          {sensorContext.field_wind_speed_ms != null && (
            <SensorPill label="Wind" value={`${sensorContext.field_wind_speed_ms.toFixed(1)}m/s`} />
          )}
          {sensorContext.field_rainfall_mm != null && sensorContext.field_rainfall_mm > 0 && (
            <SensorPill label="Rain" value={`${sensorContext.field_rainfall_mm.toFixed(1)}mm`} />
          )}
        </div>
      )}

      {/* ── Quality warnings ─────────────────────────────────────── */}
      {l10Quality?.warnings?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
          {l10Quality.warnings.slice(0, 3).map((w: string, i: number) => (
            <div key={i} style={{
              fontSize: "8px", color: "#fbbf24", padding: "2px 6px", borderRadius: "3px",
              background: "rgba(251,191,36,0.04)", border: "1px solid rgba(251,191,36,0.06)",
            }}>⚠ {w}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────
function StatusChip({ icon, label, value, color, subtitle }: {
  icon: string; label: string; value: string; color: string; subtitle?: string;
}) {
  return (
    <div className="epp-status-chip" style={{
      background: "rgba(0,0,0,0.25)", borderRadius: "6px", padding: "5px 6px",
      border: "1px solid rgba(71,85,105,0.08)", textAlign: "center",
    }}>
      <div style={{ fontSize: "9px", color: "#64748b", display: "flex", alignItems: "center", justifyContent: "center", gap: "3px" }}>
        <span style={{ fontSize: "10px" }}>{icon}</span> {label}
      </div>
      <div style={{ fontSize: "11px", color, fontFamily: "monospace", fontWeight: 700 }}>{value}</div>
      {subtitle && <div style={{ fontSize: "7px", color: "#475569", marginTop: "1px" }}>{subtitle}</div>}
    </div>
  );
}

function ContextPill({ icon, label, detail }: { icon: string; label: string; detail?: string }) {
  return (
    <div className="epp-context-pill" style={{
      display: "flex", alignItems: "center", gap: "3px",
      padding: "2px 6px", borderRadius: "4px",
      background: "rgba(0,0,0,0.2)", border: "1px solid rgba(71,85,105,0.06)",
      fontSize: "9px", color: "#cbd5e1",
    }}>
      <span style={{ fontSize: "10px" }}>{icon}</span>
      <span style={{ fontWeight: 600 }}>{label}</span>
      {detail && <span style={{ color: "#64748b", fontSize: "8px" }}>· {detail}</span>}
    </div>
  );
}

function QualityTag({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <span style={{
      fontSize: "8px", padding: "1px 5px", borderRadius: "3px",
      background: ok ? "rgba(34,197,94,0.05)" : "rgba(251,191,36,0.05)",
      color: ok ? "#4ade80" : "#fbbf24",
      border: `1px solid ${ok ? "rgba(34,197,94,0.08)" : "rgba(251,191,36,0.08)"}`,
      fontWeight: 600,
    }}>
      {label}: {value}
    </span>
  );
}

function SensorPill({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      padding: "2px 6px", borderRadius: "4px",
      background: "rgba(96,165,250,0.06)", border: "1px solid rgba(96,165,250,0.08)",
      textAlign: "center",
    }}>
      <div style={{ fontSize: "7px", color: "#64748b", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: "10px", color: "#60a5fa", fontFamily: "monospace", fontWeight: 700 }}>{value}</div>
    </div>
  );
}


// ── Main Panel ──────────────────────────────────────────────────────────
export default function EnginePipelinePanel() {
  const pi = usePlotIntelligence();
  const {
    engines, expandedEngine, setExpandedEngine,
    showEnginePanel, setShowEnginePanel,
    detailMode, loading: piLoading,
    assimilation, cacheStatus, refreshing, lastCaptured,
    cropPhenology,
  } = pi;
  const l10 = useLayer10();
  const [statusExpanded, setStatusExpanded] = useState(false);

  const canonicalEngines = useMemo<EngineStatus[]>(() => {
    const layerResults = l10.data?.layer_results;
    if (!layerResults || Object.keys(layerResults).length === 0) return engines;
    return Object.entries(layerResults)
      .sort(([a], [b]) => Number(a.replace(/\D/g, "")) - Number(b.replace(/\D/g, "")))
      .map(([key, layer]) => {
        const id = `L${Number(key.replace(/\D/g, ""))}`;
        const supplementary = engines.find(engine => engine.id === id);
        const rawStatus = String(layer?.status || "SKIPPED").toUpperCase();
        const status: EngineStatus["status"] = rawStatus === "COMPLETED" || rawStatus === "OK"
          ? "OK"
          : rawStatus === "DEGRADED"
            ? "DEGRADED"
            : rawStatus === "FAILED"
              ? "FAILED"
              : rawStatus === "UNAVAILABLE"
                ? "UNAVAILABLE"
                : "SKIPPED";
        return {
          ...(supplementary || {
            id,
            name: id,
            nameAr: id,
            icon: "🔬",
            summary: "",
            summaryAr: "",
            lastUpdate: null,
            data: {},
          }),
          id,
          status,
          statusLabel: status === "OK" ? "Good" : status === "DEGRADED" ? "Degraded" : status === "FAILED" ? "Failed" : status === "UNAVAILABLE" ? "Unavailable" : "Skipped",
          data: {
            ...(supplementary?.data || {}),
            canonical_confidence: layer?.confidence,
            canonical_errors: layer?.errors || [],
            canonical_degradation_flags: layer?.degradation_flags || [],
            canonical_sources: layer?.sources || [],
          },
        };
      });
  }, [engines, l10.data?.layer_results]);

  const isLoading = piLoading || l10.loading;
  const isVisible = !isLoading && showEnginePanel;

  // Sensor context + user inputs from PI data
  const sensorContext = pi.data?.sensorContext || null;
  const userInputs = pi.data?.userInputs || null;

  // Compute system confidence
  const { confidencePercent, okCount, total } = (() => {
    let totalConf = 0;
    let metricCount = 0;
    const scientificReliability = Number(l10.data?.scientific_pipeline_quality?.reliability ?? l10.data?.global_quality?.reliability);
    for (const e of canonicalEngines) {
      const metrics = ((e.data as Record<string, unknown> | undefined)?.expert_metrics as any[]) || [];
      if (metrics.length > 0) {
        for (const m of metrics) {
          totalConf += Number(m.confidence ?? 0);
          metricCount++;
        }
      } else {
        totalConf += 0.5;
        metricCount++;
      }
    }
    return {
      confidencePercent: Math.round(Number.isFinite(scientificReliability) ? scientificReliability * 100 : metricCount > 0 ? (totalConf / metricCount) * 100 : 0),
      okCount: canonicalEngines.filter(e => e.status === "OK").length,
      total: canonicalEngines.length,
    };
  })();

  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (confidencePercent / 100) * circumference;
  const ringColor = confidencePercent >= 75 ? "#4ade80" : confidencePercent >= 50 ? "#fbbf24" : "#f87171";
  const degradedCount = total - okCount;

  return (
    <>
      {/* Toggle Button */}
      <button
        className="epp-toggle"
        onClick={() => setShowEnginePanel(true)}
        style={{
          position: "absolute", top: "100px", left: "12px", zIndex: 19,
          width: "40px", height: "40px", borderRadius: "12px",
          background: "rgba(8, 12, 25, 0.92)", backdropFilter: "blur(20px)",
          border: "1px solid rgba(71, 85, 105, 0.25)",
          color: "#e2e8f0", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1.1rem",
          transition: "all 0.5s cubic-bezier(0.16, 1, 0.3, 1)",
          opacity: (!isLoading && !showEnginePanel) ? 1 : 0,
          pointerEvents: (!isLoading && !showEnginePanel) ? "auto" : "none",
          transform: (!isLoading && !showEnginePanel) ? "translateX(0)" : "translateX(-20px)",
        }}
        onMouseOver={e => e.currentTarget.style.background = "rgba(8, 12, 25, 1)"}
        onMouseOut={e => e.currentTarget.style.background = "rgba(8, 12, 25, 0.9)"}
        title="Show Engine Panel"
        suppressHydrationWarning={true}
      >
        🧠
      </button>

      {/* Main Panel */}
      <div
        className="epp-panel"
        style={{
          position: "absolute", top: "100px", left: "12px", bottom: "170px",
          width: "320px", zIndex: 20,
          background: "rgba(8, 12, 25, 0.92)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(71, 85, 105, 0.2)",
          borderRadius: "16px",
          display: "flex", flexDirection: "column",
          overflowY: "hidden",
          boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
          transition: "transform 0.5s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.5s cubic-bezier(0.16, 1, 0.3, 1)",
          transform: isVisible ? "translateX(0)" : "translateX(-360px)",
          opacity: isVisible ? 1 : 0,
          pointerEvents: isVisible ? "auto" : "none",
        }}
        suppressHydrationWarning={true}
      >
         {/* Header — clickable to toggle status dashboard */}
        <div
          onClick={() => setStatusExpanded(!statusExpanded)}
          style={{
            padding: "12px 14px",
            borderBottom: "1px solid rgba(71, 85, 105, 0.15)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
            flexShrink: 0,
            cursor: "pointer",
            userSelect: "none",
          }}
          suppressHydrationWarning={true}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }} suppressHydrationWarning={true}>
            {/* Progress Ring */}
            <div style={{ position: "relative", width: "38px", height: "38px" }} suppressHydrationWarning={true}>
              <svg width="38" height="38" style={{ transform: "rotate(-90deg)" }}>
                <circle cx="19" cy="19" r={radius} fill="transparent" stroke="rgba(71, 85, 105, 0.3)" strokeWidth="3.5" />
                <circle cx="19" cy="19" r={radius} fill="transparent" stroke={ringColor} strokeWidth="3.5"
                  strokeDasharray={circumference} strokeDashoffset={strokeDashoffset} strokeLinecap="round"
                  style={{ transition: "stroke-dashoffset 0.5s ease" }} />
              </svg>
              <div style={{
                position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "0.6rem", fontWeight: 700, color: "#f1f5f9",
              }} suppressHydrationWarning={true}>
                {confidencePercent}%
              </div>
            </div>
            <div suppressHydrationWarning={true}>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f1f5f9" }} suppressHydrationWarning={true}>
                {detailMode === "farmer" ? "System Status" : "Pipeline Confidence"}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }} suppressHydrationWarning={true}>
                <span style={{ fontSize: "0.65rem", color: "#94a3b8" }}>
                  {okCount}/{total} {detailMode === "farmer" ? "systems" : "engines"} OK
                </span>
                {degradedCount > 0 && (
                  <span style={{
                    fontSize: "7px", padding: "1px 4px", borderRadius: "3px",
                    background: "rgba(251,191,36,0.1)", color: "#fbbf24", fontWeight: 700,
                  }}>
                    {degradedCount} ⚠
                  </span>
                )}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "4px" }} suppressHydrationWarning={true}>
            {/* Expand/collapse chevron */}
            <span style={{
              fontSize: "0.7rem", color: "#64748b",
              transition: "transform 0.25s ease",
              transform: statusExpanded ? "rotate(180deg)" : "rotate(0deg)",
              display: "inline-flex",
            }} suppressHydrationWarning={true}>▼</span>
            <span style={{
              fontSize: "7px", padding: "2px 5px", borderRadius: "3px",
              background: detailMode === "farmer" ? "rgba(34,197,94,0.1)" : "rgba(99,102,241,0.1)",
              color: detailMode === "farmer" ? "#4ade80" : "#a5b4fc",
              fontWeight: 700, textTransform: "uppercase",
            }}>
              {detailMode}
            </span>
            <button
              className="epp-close-btn"
              onClick={(e) => { e.stopPropagation(); setShowEnginePanel(false); }}
              style={{
                width: "26px", height: "26px", borderRadius: "6px",
                background: "rgba(71, 85, 105, 0.2)", border: "none",
                color: "#94a3b8", cursor: "pointer", fontSize: "0.75rem",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
              onMouseOver={e => e.currentTarget.style.background = "rgba(71, 85, 105, 0.35)"}
              onMouseOut={e => e.currentTarget.style.background = "rgba(71, 85, 105, 0.2)"}
            >
              ✕
            </button>
          </div>
        </div>

        {/* System Status Dashboard — collapsible */}
        <div style={{
          maxHeight: statusExpanded ? "600px" : "0px",
          overflow: "hidden",
          transition: "max-height 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
        }} suppressHydrationWarning={true}>
        <SystemStatusDashboard
          detailMode={detailMode}
          engines={canonicalEngines}
          assimilation={assimilation}
          cacheStatus={cacheStatus}
          refreshing={refreshing}
          lastCaptured={lastCaptured}
          cropPhenology={cropPhenology}
          sensorContext={sensorContext}
          userInputs={userInputs}
          l10Quality={l10.data?.quality || null}
          l10Provenance={l10.data?.provenance || null}
          l10Timestamp={l10.data?.timestamp || null}
          mapSemantics={l10.mapSemantics}
          l10Grid={l10.data?.grid || null}
        />
        </div>

        {/* Engine Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "6px 10px" }} className="custom-scrollbar" suppressHydrationWarning={true}>
          {detailMode === "farmer" ? (
            <EngineFarmerView
              engines={canonicalEngines}
              data={l10.data}
              onAskBrain={(q) => l10.openDecideMode(q)}
            />
          ) : (
            <EngineExpertView
              engines={canonicalEngines}
              data={l10.data}
              expandedEngine={expandedEngine}
              onToggleEngine={setExpandedEngine}
              onAskBrain={(q) => l10.openDecideMode(q)}
            />
          )}
        </div>

        {/* Embedded Legend */}
        <div style={{
          borderTop: "1px solid rgba(71, 85, 105, 0.15)",
          padding: "10px 8px 6px",
          flexShrink: 0,
        }} suppressHydrationWarning={true}>
          <SurfaceLegendBar
            activeMode={l10.activeMode}
            detailMode={detailMode}
            groundingClass={l10.activeSurface?.grounding_class ?? "UNIFORM"}
            evidenceLevel={l10.evidenceState?.evidenceLevel}
            coverageRatio={l10.data?.quality?.coverage_ratio ?? null}
          />
        </div>

        {/* Footer */}
        <div style={{
          padding: "8px 14px",
          borderTop: "1px solid rgba(71, 85, 105, 0.15)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          fontSize: "0.65rem", color: "#64748b", fontWeight: 600,
          textTransform: "uppercase", letterSpacing: "0.05em",
          flexShrink: 0,
        }} suppressHydrationWarning={true}>
          <span>SIRE v11</span>
          <span style={{ color: refreshing ? "#818cf8" : "#4ade80" }}>
            {refreshing ? "⟳ SYNCING" : "● LIVE"}
          </span>
        </div>
      </div>
    </>
  );
}
