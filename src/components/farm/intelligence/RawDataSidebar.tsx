"use client";

/**
 * RawDataSidebar — Right collapsible sidebar.
 *
 * Dual-mode: Farmer (plain-language health report) vs Expert (agronomic analysis console).
 * Uses useLayer10 for surface stats/zones + usePlotIntelligence for assimilation/engines.
 */

import { useState } from "react";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import { useLayer10, MODE_CONFIG } from "@/hooks/useLayer10";
import HistogramDrawer from "./HistogramDrawer";
import SidebarFarmerView from "./SidebarFarmerView";
import SidebarExpertView from "./SidebarExpertView";
import MapLayerDock from "./MapLayerDock";

type SidebarTab = "analysis" | "layers" | "raw";

function SourceComparisonTable({ data }: { data: Record<string, unknown> | null }) {
  if (!data) return <div style={emptyStyle}>No raw data available</div>;

  const sources = Object.entries(data).filter(([, v]) => v && typeof v === "object" && !Array.isArray(v));
  if (sources.length === 0) return <div style={emptyStyle}>No sources loaded</div>;

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
  const { detailMode, dataView, setDataView, rawData, showAnalysisSidebar, setShowAnalysisSidebar, assimilation, engines, activeSidebarTab, setActiveSidebarTab } = pi;

  const activeTab = activeSidebarTab;
  const setActiveTab = setActiveSidebarTab;

  // ── These MUST be above any early return (Rules of Hooks) ────────────────
  const activeMode = l10.activeMode;
  const modeConfig = MODE_CONFIG[activeMode];
  // Use hook's resolved surface type (handles veg_attention → NDVI_DEVIATION | BASELINE_ANOMALY)
  const surfaceType = l10.activeSurfaceType;
  const committedBase = l10.browserRenderReceipt?.viewIdentity === l10.renderPlan.viewIdentity
    ? l10.browserRenderReceipt.baseMaterialization
    : null;
  const committedOverlay = l10.browserRenderReceipt?.viewIdentity === l10.renderPlan.viewIdentity
    ? l10.browserRenderReceipt.overlayMaterialization
    : null;
  const activeBaseCommitted = committedBase?.status === "rendered"
    && committedBase.surfaceType === surfaceType
    && !!l10.data?.publication_id
    && committedBase.receipt?.publicationId === l10.data.publication_id;
  const activeOverlayCommitted = committedOverlay?.status === "rendered"
    && !!l10.data?.publication_id
    && committedOverlay.receipt?.publicationId === l10.data.publication_id;
  const committedHybridOverlays = (
    l10.browserRenderReceipt?.viewIdentity === l10.renderPlan.viewIdentity
      ? (l10.browserRenderReceipt.hybridOverlayMaterializations || [])
      : []
  ).filter((item) => item.status === "rendered"
    && !!l10.data?.publication_id
    && item.receipt?.publicationId === l10.data.publication_id);
  const committedHybridLabels = [
    ...(activeOverlayCommitted ? ["experimental detail"] : []),
    ...committedHybridOverlays.map((item) => item.surfaceType.replace(/_/g, " ").toLowerCase()),
  ];

  const explainPack = l10.data?.explainability_pack?.[surfaceType];
  // ─────────────────────────────────────────────────────────────────────────
  const isLoading = l10.loading || pi.loading;
  const isVisible = !isLoading && showAnalysisSidebar;

  return (
    <>
      {/* Toggle Button */}
      <button
        className="epp-toggle"
        onClick={() => setShowAnalysisSidebar(true)}
        style={{
          position: "absolute", top: "100px", right: "12px", zIndex: 19,
          width: "40px", height: "40px", borderRadius: "12px",
          background: "rgba(8, 12, 25, 0.92)", backdropFilter: "blur(20px)",
          border: "1px solid rgba(71, 85, 105, 0.25)",
          color: "#e2e8f0", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1.1rem",
          transition: "all 0.5s cubic-bezier(0.16, 1, 0.3, 1)",
          opacity: (!isLoading && !showAnalysisSidebar) ? 1 : 0,
          pointerEvents: (!isLoading && !showAnalysisSidebar) ? "auto" : "none",
          transform: (!isLoading && !showAnalysisSidebar) ? "translateX(0)" : "translateX(20px)",
        }}
        onMouseOver={e => e.currentTarget.style.background = "rgba(8, 12, 25, 1)"}
        onMouseOut={e => e.currentTarget.style.background = "rgba(8, 12, 25, 0.9)"}
        title="Show Analysis"
        suppressHydrationWarning={true}
      >
        📊
      </button>

      {/* Main Panel */}
      <div className="epp-panel" style={{
        position: "absolute", top: "100px", right: "12px", bottom: "170px",
        width: "320px", zIndex: 20,
        background: "rgba(8, 12, 25, 0.92)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(71, 85, 105, 0.2)",
        borderRadius: "16px",
        display: "flex", flexDirection: "column",
        overflow: "hidden",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
        transition: "transform 0.5s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.5s cubic-bezier(0.16, 1, 0.3, 1)",
        transform: isVisible ? "translateX(0)" : "translateX(360px)",
        opacity: isVisible ? 1 : 0,
        pointerEvents: isVisible ? "auto" : "none",
      }} suppressHydrationWarning={true}>
      {/* Header */}
      <div style={{
        padding: "14px 16px 8px",
        borderBottom: "1px solid rgba(71, 85, 105, 0.15)",
      }} suppressHydrationWarning={true}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }} suppressHydrationWarning={true}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }} suppressHydrationWarning={true}>
            <div style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f1f5f9" }} suppressHydrationWarning={true}>
              {modeConfig.icon} {modeConfig.label}
            </div>
            <span style={{
              fontSize: "9px", padding: "2px 6px", borderRadius: "4px",
              background: detailMode === "farmer" ? "rgba(34,197,94,0.1)" : "rgba(99,102,241,0.1)",
              color: detailMode === "farmer" ? "#4ade80" : "#a5b4fc",
              fontWeight: 700, textTransform: "uppercase",
            }} suppressHydrationWarning={true}>
              {detailMode}
            </span>
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
        <div style={{ display: "flex", gap: "4px" }} suppressHydrationWarning={true}>
          {(["analysis", "layers", ...(detailMode === "expert" ? ["raw"] : [])] as SidebarTab[]).map(tab => (
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
              {tab === "analysis" ? "Analysis" : tab === "layers" ? "Layers" : "Raw Data"}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }} className="custom-scrollbar" suppressHydrationWarning={true}>
        {/* ASMAE plot state is a card-only product, independent of maps. */}
        {l10.data?.source_policy_display_state?.asmaePlotState?.available && (() => {
          const plotState = l10.data.source_policy_display_state.asmaePlotState;
          const directlyAssimilated = Array.isArray(plotState.directlyAssimilatedStates)
            ? plotState.directlyAssimilatedStates
            : [];
          const proxyAssimilated = Array.isArray(plotState.proxyAssimilatedStates)
            ? plotState.proxyAssimilatedStates
            : [];
          const assimilated = Array.isArray(plotState.assimilatedStates)
            ? plotState.assimilatedStates
            : [];
          const indirect = Array.isArray(plotState.indirectlyConstrainedStates)
            ? plotState.indirectlyConstrainedStates
            : [];
          const priorOnly = Array.isArray(plotState.priorConstrainedStates)
            ? plotState.priorConstrainedStates
            : [];
          return (
            <div style={{
              marginBottom: "12px",
              padding: "10px 12px",
              borderRadius: "10px",
              background: "rgba(20, 184, 166, 0.08)",
              border: "1px solid rgba(45, 212, 191, 0.24)",
              fontSize: "0.76rem",
              color: "#99f6e4",
              lineHeight: "1.35",
            }}>
              <div style={{ fontWeight: 700, marginBottom: "5px" }}>
                ASMAE plot state available
              </div>
              <div>
                {String(plotState.stateAvailability || "UNAVAILABLE").replace(/_/g, " ")}
                {" · "}
                {String(plotState.authorityLevel || "DIAGNOSTIC").replace(/_/g, " ")}
              </div>
              <div style={{ color: "#5eead4", marginTop: "3px" }}>
                ASMAE temporal state · belief valid time: {plotState.effectiveDate || "unavailable"}
              </div>
              {plotState.activeSpatialJobStatus && (
                <div style={{
                  color: plotState.activeSpatialJobStatus === "stalled" || plotState.activeSpatialJobStatus === "failed"
                    ? "#fca5a5"
                    : "#94a3b8",
                  marginTop: "3px",
                }}>
                  Spatial refresh: {String(plotState.activeSpatialJobStatus).replace(/_/g, " ")}
                  {plotState.activeSpatialJobId ? ` · job ${plotState.activeSpatialJobId}` : ""}
                </div>
              )}
              <div style={{ color: "#94a3b8", marginTop: "3px" }}>
                {plotState.spatialAvailable && activeBaseCommitted
                  ? (l10.activeSurfaceType && (l10.activeSurfaceType.startsWith("CANOPY_ASMAE") || l10.activeSurfaceType.includes("ASMAE") || l10.activeSurfaceType.startsWith("COMPOSITE_"))
                      ? "ASMAE diagnostic state active. Raster visualization active (10m diagnostic basis)."
                      : "ASMAE diagnostic state available. Raster visualization active.")
                  : "ASMAE diagnostic state available. Raster visualization unavailable (materialization pending)."}
                {directlyAssimilated.length > 0
                  ? " Directly assimilated: " + directlyAssimilated.slice(0, 5).join(", ") + "."
                  : (assimilated.length > 0 ? " Assimilated: " + assimilated.slice(0, 5).join(", ") + "." : "")}
                {proxyAssimilated.length > 0
                  ? " Proxy-assimilated: " + proxyAssimilated.slice(0, 5).join(", ") + (proxyAssimilated.length > 5 ? ` +${proxyAssimilated.length - 5}` : "") + "."
                  : ""}
                {indirect.length > 0
                  ? " Indirect: " + indirect.slice(0, 5).join(", ") + "."
                  : ""}
                {priorOnly.length > 0
                  ? " Prior only: " + priorOnly.slice(0, 5).join(", ") + (priorOnly.length > 5 ? ` +${priorOnly.length - 5}` : "") + "."
                  : ""}
              </div>
            </div>
          );
        })()}

        {/* Source Policy Banner */}
        {l10.data?.source_policy_display_state &&
         (l10.canopySource === "asmae_diagnostic" || l10.canopySource === "hybrid") &&
         l10.activeSurface?.semantic_type === "NDVI_CLEAN" &&
         l10.data.source_policy_display_state.fallback_reason && (
          <div style={{
            marginBottom: "12px",
            padding: "10px 12px",
            borderRadius: "10px",
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.2)",
            fontSize: "0.76rem",
            color: "#f87171",
            lineHeight: "1.3",
            boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
          }}>
            <div style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
              <span>⚠️</span> Source Policy Fallback
            </div>
            The map fell back to satellite.{" "}
            {l10.data.source_policy_display_state.asmaePlotState?.available
              ? "The ASMAE plot state remains available. "
              : ""}
            Reason:{" "}
            <span style={{ fontWeight: 600, color: "#fca5a5" }}>
              {l10.data.source_policy_display_state.fallback_reason === "asmae_quick_visual_timeout"
                ? "ASMAE execution timed out (>150ms)."
                : l10.data.source_policy_display_state.fallback_reason === "asmae_low_coverage"
                ? `ASMAE 1m advisory coverage (${l10.data.source_policy_display_state.one_meter_advisory_coverage_pct?.toFixed(1)}%) fell below 60% threshold.`
                : l10.data.source_policy_display_state.fallback_reason?.replace(/_/g, " ") || "ASMAE not available."}
            </span>
          </div>
        )}

        {l10.bannerState === "composite_advisory_active" && activeBaseCommitted && (
          <div style={{
            marginBottom: "12px",
            padding: "10px 12px",
            borderRadius: "10px",
            background: "rgba(52, 211, 153, 0.08)",
            border: "1px solid rgba(52, 211, 153, 0.2)",
            fontSize: "0.76rem",
            color: "#34d399",
            lineHeight: "1.3",
            boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
          }}>
            <div style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
              <span>✅</span> Composite Advisory Active
            </div>
            Composite Advisory Active (No 1m physical data).
          </div>
        )}

        {((l10.bannerState === "hybrid_active" && committedHybridLabels.length > 0)
          || (l10.bannerState === "asmae_diagnostic_active" && activeBaseCommitted)) && (
          <div style={{
            marginBottom: "12px",
            padding: "10px 12px",
            borderRadius: "10px",
            background: "rgba(52, 211, 153, 0.08)",
            border: "1px solid rgba(52, 211, 153, 0.2)",
            fontSize: "0.76rem",
            color: "#34d399",
            lineHeight: "1.3",
            boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
          }}>
            <div style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
              <span>✅</span> {l10.bannerState === "hybrid_active" ? "Hybrid Overlays Committed" : "ASMAE Diagnostic Active"}
            </div>
            {l10.bannerState === "hybrid_active" && (
              <div style={{ marginBottom: "4px" }}>{committedHybridLabels.join(", ")}</div>
            )}
            {(() => {
              const oneMeterPct = l10.data?.source_policy_display_state?.one_meter_advisory_coverage_pct;
              if (typeof oneMeterPct === "number") {
                return (
                  <span>
                    1m Coverage: <span style={{ fontWeight: 600, color: "#6ee7b7" }}>{oneMeterPct.toFixed(1)}% ML-supported</span>
                  </span>
                );
              }
              return (
                <span>
                  Scientific basis: <span style={{ fontWeight: 600, color: "#6ee7b7" }}>10m</span> · Authority: <span style={{ fontWeight: 600, color: "#6ee7b7" }}>advisory only</span> · 1m approval: <span style={{ fontWeight: 600, color: "#94a3b8" }}>unavailable</span>
                </span>
              );
            })()}
          </div>
        )}

        {activeTab === "analysis" && (
          <>
            {l10.data ? (
              detailMode === "farmer" ? (
                <SidebarFarmerView
                  data={l10.data}
                  activeMode={activeMode}
                  surfaceType={surfaceType}
                  explainPack={explainPack}
                  engines={engines}
                  assimilation={assimilation}
                  onAskBrain={(q) => l10.openDecideMode(q)}
                />
              ) : (
                <SidebarExpertView
                  data={l10.data}
                  activeMode={activeMode}
                  surfaceType={surfaceType}
                  explainPack={explainPack}
                  engines={engines}
                  assimilation={assimilation}
                  onAskBrain={(q) => l10.openDecideMode(q)}
                />
              )
            ) : (
              <div style={emptyStyle}>No surface data — waiting for L10</div>
            )}
          </>
        )}

        {activeTab === "layers" && (
          <MapLayerDock />
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
              <div style={emptyStyle}>Assimilated view shows fused data. Switch to Raw to see individual source responses.</div>
            )}
          </>
        )}
      </div>

      {/* Embedded Histogram */}
      <div style={{
        borderTop: "1px solid rgba(71, 85, 105, 0.15)",
        flexShrink: 0,
      }} suppressHydrationWarning={true}>
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
      }} suppressHydrationWarning={true}>
        <span>
          {l10.activeAuthorityLabel}
          {l10.activeDisplay?.groundingDetail ? " " + l10.activeDisplay.groundingDetail : ""}
        </span>
        <span style={{
          color: l10.activeSourceLabel.includes("EXPERIMENTAL")
            ? "#f59e0b"
            : l10.activeSourceLabel === "ASMAE ADVISORY"
            ? "#22c55e"
            : l10.activeSourceLabel === "ASMAE FUSION"
            ? "#10b981"
            : "#3b82f6",
          fontWeight: 700,
        }}>
          {l10.activeSourceLabel}
        </span>
      </div>
      </div>
    </>
  );
}

const emptyStyle = {
  padding: "20px", textAlign: "center" as const, fontSize: "0.82rem", color: "#94a3b8",
  background: "rgba(71, 85, 105, 0.06)", borderRadius: "10px",
  border: "1px dashed rgba(71, 85, 105, 0.2)", lineHeight: 1.6,
};

// getGroundingDetailLabel shouldShowPlotLevel
// ASMAE ADVISORY
// Composite Advisory Active
// !l10.activeSurface?.type?.startsWith("COMPOSITE_")
