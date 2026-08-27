"use client";

import React, { useMemo } from "react";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import { OverlayKind } from "@/lib/agribrain/plot-map-evidence-state";
import type { SourcePolicy } from "@/lib/agribrain/layer10-request-state.mjs";
import { resolveAsmaeGenerationState } from "@/lib/agribrain/asmae-job-state.mjs";

export default function MapLayerDock() {
  const l10 = useLayer10();
  const pi = usePlotIntelligence();
  const { data: l10Data, baseSurfaceMode, setBaseSurfaceMode, overlayToggles, setOverlayToggle, overlayAvailability, surfaceAvailabilityByMode } = l10;

  const activeMode = l10.activeMode;
  const modeDisplay = l10Data?.mode_display_state?.[activeMode];
  const asmaeUtil = modeDisplay?.asmae_utilization;
  const asmaeRan = !!l10.surfaceByType?.["CANOPY_ASMAE_VIGOR"];
  const policyState = l10Data?.source_policy_display_state;
  const plotState = policyState?.asmaePlotState;
  const asmaeGeneration = resolveAsmaeGenerationState(plotState, asmaeRan, l10.loading);
  const committedBase = l10.browserRenderReceipt?.viewIdentity === l10.renderPlan.viewIdentity
    ? l10.browserRenderReceipt.baseMaterialization
    : null;
  const committedOverlay = l10.browserRenderReceipt?.viewIdentity === l10.renderPlan.viewIdentity
    ? l10.browserRenderReceipt.overlayMaterialization
    : null;
  const committedHybridCandidates = l10.browserRenderReceipt?.viewIdentity === l10.renderPlan.viewIdentity
    ? (l10.browserRenderReceipt.hybridOverlayMaterializations || [])
    : [];
  const publicationMatches = (materialization: typeof committedBase) =>
    materialization?.status === "rendered"
    && !!l10Data?.publication_id
    && materialization.receipt?.publicationId === l10Data.publication_id;
  const activeBaseCommitted = publicationMatches(committedBase)
    && committedBase?.surfaceType === l10.activeSurfaceType;
  const activeOverlayCommitted = publicationMatches(committedOverlay);
  const committedHybridOverlays = committedHybridCandidates.filter((item) => publicationMatches(item));
  const committedHybridLabels = [
    ...(activeOverlayCommitted ? ["experimental detail"] : []),
    ...committedHybridOverlays.map((item) => ({
      CANOPY_ASMAE_VIGOR: "ASMAE vigor",
      ASMAE_POSTERIOR_CONCENTRATION: "posterior concentration",
      ASMAE_BMA_DISAGREEMENT: "BMA disagreement",
      VEG_ATTENTION_ASMAE_DISAGREEMENT: "vegetation disagreement",
    }[item.surfaceType] || item.surfaceType.replace(/_/g, " ").toLowerCase())),
  ];
  const providerFallbackCommitted = committedBase?.status === "rendered"
    && committedBase.surfaceType === "NDVI_CLEAN"
    && publicationMatches(committedBase);

  const requestAsmaeDiagnostic = () => {
    l10.setCanopySource("asmae_diagnostic");
    if (!l10Data?.plot_id) return;
    void l10.fetchLayer10(
      l10Data.plot_id,
      String(l10Data.provenance?.farm_id || ""),
      undefined,
      undefined,
      undefined,
      { forceRefresh: true, sourcePolicy: "asmae_diagnostic" },
    );
  };

  // Base Surface modes mapping
  const baseModes = [
    { key: "canopy", label: "Canopy" },
    { key: "veg_attention", label: "Vegetation Attention" },
    { key: "water_stress", label: "Water" },
    { key: "nutrient_risk", label: "Nutrients" },
    { key: "salinity", label: "Salinity" },
    { key: "composite_risk", label: "Risk" }
  ] as const;

  // Overlays list
  const overlaysList = [
    { key: "zones", label: "Zones" },
    { key: "water", label: "Water" },
    { key: "nutrients", label: "Nutrients" },
    { key: "risk", label: "Risk" },
    { key: "salinity", label: "Salinity" },
    { key: "confidence", label: "Confidence" },
    { key: "resolution", label: "Resolution" },
    { key: "experimentalDetail", label: "Experimental Detail" },
    { key: "gapFill", label: "Gap-fill Mask" }
  ] as const;

  // Helper for display level label
  const getDisplayLevelLabel = (level: string, mode: string) => {
    if (!level) return "Plot-level estimate";
    const lvl = level.toLowerCase();
    if (lvl === "raster") return "raster";
    if (lvl === "asmae_diagnostic") return mode === "composite_risk" ? "summary" : "ASMAE diagnostic";
    if (lvl === "proxy") return "proxy";
    if (lvl === "plot_level") return "Plot-level estimate";
    if (lvl === "visual_only") return "Visual-only";
    if (lvl === "unavailable") return "Experimental unavailable";
    return lvl;
  };

  const currentSourceInfo = useMemo(() => {
    const activeSurfaceType = l10.activeSurfaceType;
    const activeAuthorityLabel = l10.activeAuthorityLabel;
    if (!activeSurfaceType) return null;
    const evidence = l10.evidenceState?.evidenceLevel || "unavailable";
    const resolution = activeSurfaceType.includes("EXPERIMENTAL_FINE_DETAIL") ? "visual 2.5m / evidence basis 10m" : "evidence basis 10m";

    return {
      surface: activeSurfaceType,
      evidence: evidence.replace(/_/g, " "),
      authority: activeAuthorityLabel,
      resolution: resolution,
      reason: policyState?.fallback_reason || ""
    };
  }, [l10.activeSurfaceType, l10.activeAuthorityLabel, l10.evidenceState, policyState]);

  if (l10.loading || pi.loading) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "#94a3b8" }}>
        Loading layers...
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "18px", color: "#e2e8f0" }}>
      
      {/* 1. BASE SURFACE SECTION */}
      <div>
        <div style={sectionTitleStyle}>Base Surface</div>
        <div style={listContainerStyle}>
          {baseModes.map(({ key, label }) => {
            const availability = surfaceAvailabilityByMode?.[key];
            const activeSurfForMode = availability?.surfaceType || null;
            const levelLabel = availability?.levelLabel || "Plot-level estimate";
            const isUnavailable = availability?.status === "unavailable_missing_proof" || availability?.status === "unavailable_missing_feature_family";
            const hasComposite = activeSurfForMode && String(activeSurfForMode).startsWith("COMPOSITE_");

            const isSelected = baseSurfaceMode === key;

            return (
              <React.Fragment key={key}>
                <label
                  style={{
                    ...itemRowStyle,
                    background: isSelected ? "rgba(99, 102, 241, 0.08)" : "transparent",
                    borderColor: isSelected ? "rgba(99, 102, 241, 0.3)" : "rgba(71, 85, 105, 0.12)",
                    opacity: isUnavailable ? 0.45 : 1,
                    cursor: isUnavailable ? "not-allowed" : "pointer"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <input
                      type="radio"
                      name="baseSurface"
                      checked={isSelected}
                      disabled={isUnavailable}
                      onChange={() => !isUnavailable && setBaseSurfaceMode(key)}
                      style={{
                        ...radioStyle,
                        cursor: isUnavailable ? "not-allowed" : "pointer"
                      }}
                    />
                    <span style={{ fontSize: "0.82rem", fontWeight: isSelected ? 600 : 500 }}>{label}</span>
                  </div>
                  <span
                    style={{
                      fontSize: "0.72rem",
                      color: isUnavailable ? "#ef4444" : (isSelected ? "#a5b4fc" : "#64748b"),
                      textTransform: isSelected && hasComposite ? "none" : "none",
                    }}
                  >
                    {levelLabel}
                  </span>
                </label>

                {isSelected && key === "canopy" && (
                  <div style={{
                    padding: "10px 12px 12px 28px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    background: "rgba(15, 23, 42, 0.3)",
                    borderLeft: "2px solid rgba(99, 102, 241, 0.4)",
                    marginTop: "-4px",
                    marginBottom: "4px",
                    borderRadius: "0 0 4px 0"
                  }}>
                    <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase" }}>Source Policy</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {([
                        { val: "satellite", label: "Satellite" },
                        { val: "experimental", label: "Experimental" },
                        { val: "asmae_diagnostic", label: "ASMAE diagnostic" },
                        { val: "hybrid", label: "Hybrid" }
                      ] satisfies ReadonlyArray<{ val: SourcePolicy; label: string }>).map((item) => (
                        <label key={item.val} style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                          <input
                            type="radio"
                            name="canopySource"
                            checked={l10.canopySource === item.val}
                            onChange={() => l10.setCanopySource(item.val)}
                            style={radioStyle}
                          />
                          <span style={{ fontSize: "0.78rem", color: l10.canopySource === item.val ? "#e2e8f0" : "#94a3b8" }}>{item.label}</span>
                        </label>
                      ))}
                    </div>
                    {l10.canopySource === "asmae_diagnostic" && asmaeGeneration.visible && (
                      <button
                        type="button"
                        onClick={requestAsmaeDiagnostic}
                        disabled={asmaeGeneration.disabled}
                        style={{
                          border: "1px solid rgba(99,102,241,0.45)",
                          borderRadius: "6px",
                          padding: "7px 9px",
                          color: "#c7d2fe",
                          background: "rgba(99,102,241,0.12)",
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          cursor: asmaeGeneration.disabled ? "not-allowed" : "pointer",
                          opacity: asmaeGeneration.disabled ? 0.7 : 1,
                        }}
                      >
                        {asmaeGeneration.label}
                      </button>
                    )}
                    {l10.canopySource === "hybrid" && (
                      <div style={{
                        marginTop: "4px",
                        fontSize: "0.72rem",
                        color: committedHybridLabels.length > 0 ? "#34d399" : "#fbbf24",
                        background: committedHybridLabels.length > 0
                          ? "rgba(52, 211, 153, 0.08)"
                          : "rgba(251, 191, 36, 0.08)",
                        padding: "6px 8px",
                        borderRadius: "4px",
                        border: committedHybridLabels.length > 0
                          ? "1px solid rgba(52, 211, 153, 0.2)"
                          : "1px solid rgba(251, 191, 36, 0.2)",
                        lineHeight: "1.2"
                      }}>
                        {committedHybridLabels.length > 0 ? "✅" : "⚠️"}{" "}
                        <strong>{committedHybridLabels.length > 0 ? "Hybrid overlays committed:" : "Hybrid requested:"}</strong>{" "}
                        {committedHybridLabels.length > 0
                          ? `${committedHybridLabels.join(", ")}. Visual representation only.`
                          : `No hybrid overlay has been committed; showing ${committedBase?.surfaceType?.replace(/_/g, " ").toLowerCase() || "the committed base"} only.`}
                      </div>
                    )}
                    {((l10.canopySource === "asmae_diagnostic" || l10.canopySource === "hybrid") && l10.bannerState === null) && (
                      <div style={{
                        marginTop: "4px",
                        fontSize: "0.72rem",
                        color: "#f87171",
                        background: "rgba(248, 113, 113, 0.08)",
                        padding: "6px 8px",
                        borderRadius: "4px",
                        border: "1px solid rgba(248, 113, 113, 0.2)",
                        lineHeight: "1.2"
                      }}>
                        ⚠️ <strong>{providerFallbackCommitted ? "Map Fallback Active:" : "ASMAE spatial view unavailable:"}</strong>{" "}
                        {providerFallbackCommitted
                          ? <>The browser committed the <strong>Satellite</strong> NDVI raster. </>
                          : <>No fallback raster has been confirmed by the browser. </>}
                        {plotState?.available
                          ? `ASMAE temporal state (belief valid ${plotState.effectiveDate || "time unavailable"}) is still available. `
                          : ""}
                        Reason:{" "}
                        {policyState?.fallback_reason === "asmae_quick_visual_timeout"
                          ? "ASMAE execution timed out (>150ms)."
                          : policyState?.fallback_reason === "asmae_low_coverage"
                          ? `ASMAE 1m advisory coverage (${policyState.one_meter_advisory_coverage_pct?.toFixed(1)}%) fell below 60% threshold.`
                          : policyState?.fallback_reason?.replace(/_/g, " ") || "ASMAE not available."}
                      </div>
                    )}
                    {l10.bannerState === "composite_advisory_active" && activeBaseCommitted && (
                      <div style={{
                        marginTop: "4px",
                        fontSize: "0.72rem",
                        color: "#34d399",
                        background: "rgba(52, 211, 153, 0.08)",
                        padding: "6px 8px",
                        borderRadius: "4px",
                        border: "1px solid rgba(52, 211, 153, 0.2)",
                        lineHeight: "1.2"
                      }}>
                        ✅ <strong>Composite Advisory Active</strong>
                      </div>
                    )}
                    {(l10.bannerState === "asmae_diagnostic_active" && activeBaseCommitted) && (
                      <div style={{
                        marginTop: "4px",
                        fontSize: "0.72rem",
                        color: "#34d399",
                        background: "rgba(52, 211, 153, 0.08)",
                        padding: "6px 8px",
                        borderRadius: "4px",
                        border: "1px solid rgba(52, 211, 153, 0.2)",
                        lineHeight: "1.2"
                      }}>
                        ✅ <strong>ASMAE Diagnostic Active</strong>{" "}
                        {(() => {
                          const oneMeterPct = policyState?.one_meter_advisory_coverage_pct;
                          return typeof oneMeterPct === "number"
                            ? `${oneMeterPct.toFixed(1)}% ML-supported`
                            : "advisory only";
                        })()}
                        {policyState?.one_meter_physics_coverage_pct !== null && policyState?.one_meter_physics_coverage_pct !== undefined
                          ? ` (Physics-only: ${policyState.one_meter_physics_coverage_pct.toFixed(1)}%)`
                          : ""}
                      </div>
                    )}
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* 2. OVERLAYS SECTION */}
      <div>
        <div style={sectionTitleStyle}>Overlays</div>
        <div style={listContainerStyle}>
          {overlaysList.map(({ key, label }) => {
            const isToggled = !!overlayToggles[key];
            const isAvailable = overlayAvailability?.[key]?.available ?? true;
            const grounding = overlayAvailability?.[key]?.groundingClass;
            const isSpatial = overlayAvailability?.[key]?.isSpatial ?? false;

            return (
              <label
                key={key}
                style={{
                  ...itemRowStyle,
                  opacity: isAvailable ? 1 : 0.45,
                  cursor: isAvailable ? "pointer" : "not-allowed",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <input
                    type="checkbox"
                    checked={isToggled}
                    disabled={!isAvailable}
                    onChange={(e) => setOverlayToggle(key as OverlayKind, e.target.checked)}
                    style={checkboxStyle}
                  />
                  <span style={{ fontSize: "0.82rem" }}>{label}</span>
                </div>
                {!isAvailable ? (
                  <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Experimental unavailable</span>
                ) : (
                  <span style={{ fontSize: "0.7rem", color: "#64748b" }}>
                    {isSpatial ? "spatial" : grounding ? "uniform" : ""}
                  </span>
                )}
              </label>
            );
          })}
        </div>
      </div>

      {/* 3. CURRENT SOURCE INFO */}
      {currentSourceInfo && (
        <div style={sourceCardStyle}>
          <div style={cardTitleStyle}>Current Source</div>
          <div style={cardRowStyle}>
            <span style={cardLabelStyle}>Surface:</span>
            <span style={cardValueStyle}>{currentSourceInfo.surface}</span>
          </div>
          <div style={cardRowStyle}>
            <span style={cardLabelStyle}>Evidence:</span>
            <span style={{ ...cardValueStyle, textTransform: "lowercase" }}>{currentSourceInfo.evidence}</span>
          </div>
          <div style={cardRowStyle}>
            <span style={cardLabelStyle}>Authority:</span>
            <span style={cardValueStyle}>{currentSourceInfo.authority}</span>
          </div>
          <div style={cardRowStyle}>
            <span style={cardLabelStyle}>Resolution:</span>
            <span style={cardValueStyle}>{currentSourceInfo.resolution}</span>
          </div>
          
          {/* ASMAE Utilization sub-card */}
          <div style={asmaeHeaderStyle}>ASMAE Details</div>
          {!asmaeUtil || asmaeUtil.status === "not_used" || asmaeUtil.status === "skipped" || asmaeUtil.status === "unavailable" ? (
            <div style={asmaeNotActiveStyle}>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>ASMAE:</span>
                <span style={{ ...cardValueStyle, color: "#64748b" }}>
                  {asmaeRan && activeMode === "canopy" && l10.canopySource !== "asmae_diagnostic" && l10.canopySource !== "hybrid" ? (
                    "ASMAE completed, not selected for this source mode."
                  ) : (
                    "ASMAE not active"
                  )}
                </span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>Reason:</span>
                <span style={{ ...cardValueStyle, color: "#ef4444", textTransform: "none" }}>
                  {asmaeUtil?.reason === "no_l1_asmae_output" ? "no Layer 1 ASMAE raster refs" :
                   (asmaeUtil?.reason || "no Layer 1 ASMAE raster refs").replace(/_/g, " ")}
                </span>
              </div>
            </div>
          ) : (
            <div style={asmaeActiveContainerStyle}>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>ASMAE:</span>
                <span style={{ ...cardValueStyle, color: asmaeUtil.status === "active" ? "#4ade80" : "#fbbf24", fontWeight: "bold" }}>
                  {asmaeUtil.status === "active" ? "active" : "diagnostic only"}
                </span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>Selected:</span>
                <span style={cardValueStyle}>{asmaeUtil.selected_surface || "not provided"}</span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>EnKF:</span>
                <span style={cardValueStyle}>{asmaeUtil.enkf_used ? (asmaeUtil.enkf_mode || "used") : "not used"}</span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>Radiometric:</span>
                <span style={cardValueStyle}>{asmaeUtil.radiometric_used ? (asmaeUtil.radiometric_mode || "used") : "not used"}</span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>Retrovalidation:</span>
                <span style={cardValueStyle}>
                  {asmaeUtil.retrovalidation_score !== null && asmaeUtil.retrovalidation_score !== undefined
                    ? asmaeUtil.retrovalidation_score
                    : "not provided"}
                </span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>BMA:</span>
                <span style={cardValueStyle}>{asmaeUtil.bma_used ? "used" : "not used"}</span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>Archive:</span>
                <span style={cardValueStyle}>
                  {asmaeUtil.sentinel_archive_used && asmaeUtil.archive_scene_count
                    ? `${asmaeUtil.archive_scene_count} scenes${asmaeUtil.archive_date_range ? ` (${asmaeUtil.archive_date_range})` : ""}`
                    : "not provided"}
                </span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>Effective resolution:</span>
                <span style={cardValueStyle}>{asmaeUtil.effective_resolution_m ? `${asmaeUtil.effective_resolution_m}m` : "not provided"}</span>
              </div>
              <div style={cardRowStyle}>
                <span style={cardLabelStyle}>Authority:</span>
                <span style={cardValueStyle}>
                  {asmaeUtil.authority_allowed ? "allowed" : (asmaeUtil.authority_block_reason || "diagnostic only").replace(/_/g, " ")}
                </span>
              </div>
            </div>
          )}

          {currentSourceInfo.reason && (
            <div style={warningStyle}>
              {currentSourceInfo.reason}
            </div>
          )}
        </div>
      )}

      {/* 4. COMPACT DEBUG/TRUTH ROW */}
      <div style={debugRowStyle}>
        <span style={debugLabelStyle}>Debug / Truth</span>
        <span style={debugValueStyle}>
          {l10Data?.ground_truth_summary ? "Active" : "None"}
        </span>
      </div>
    </div>
  );
}

// Helper to pull a variable from the surface's provenance if available
function provValue(l10Data: any, surfaceType: string | null, key: string): any {
  if (!l10Data || !surfaceType) return null;
  const s = l10Data.surfaces?.find((x: any) => x.type === surfaceType);
  return s?.provenance?.[key];
}

// Inline Styles to match AgriWise Dark Theme
const sectionTitleStyle: React.CSSProperties = {
  fontSize: "0.75rem",
  fontWeight: 700,
  color: "#94a3b8",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: "8px",
};

const listContainerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "6px",
};

const itemRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "8px 12px",
  borderRadius: "8px",
  border: "1px solid rgba(71, 85, 105, 0.15)",
  cursor: "pointer",
  transition: "all 0.2s ease-in-out",
};

const radioStyle: React.CSSProperties = {
  cursor: "pointer",
  accentColor: "#6366f1",
};

const checkboxStyle: React.CSSProperties = {
  cursor: "pointer",
  accentColor: "#6366f1",
};

const sourceCardStyle: React.CSSProperties = {
  marginTop: "10px",
  padding: "12px",
  borderRadius: "10px",
  background: "rgba(15, 23, 42, 0.4)",
  border: "1px solid rgba(71, 85, 105, 0.2)",
};

const cardTitleStyle: React.CSSProperties = {
  fontSize: "0.75rem",
  fontWeight: 700,
  color: "#e2e8f0",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  borderBottom: "1px solid rgba(71, 85, 105, 0.2)",
  paddingBottom: "6px",
  marginBottom: "8px",
};

const cardRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  fontSize: "0.74rem",
  padding: "3px 0",
};

const cardLabelStyle: React.CSSProperties = {
  color: "#94a3b8",
};

const cardValueStyle: React.CSSProperties = {
  color: "#f1f5f9",
  fontFamily: "monospace",
  fontWeight: 500,
};

const asmaeHeaderStyle: React.CSSProperties = {
  fontSize: "0.72rem",
  fontWeight: 700,
  color: "#a5b4fc",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  marginTop: "10px",
  marginBottom: "6px",
  paddingTop: "6px",
  borderTop: "1px solid rgba(71, 85, 105, 0.15)",
};

const asmaeNotActiveStyle: React.CSSProperties = {
  fontSize: "0.7rem",
  color: "#64748b",
  fontStyle: "italic",
  background: "rgba(100, 116, 139, 0.05)",
  padding: "6px 8px",
  borderRadius: "6px",
};

const asmaeActiveContainerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "2px",
  background: "rgba(16, 185, 129, 0.03)",
  padding: "6px 8px",
  borderRadius: "6px",
  border: "1px solid rgba(16, 185, 129, 0.1)",
};

const warningStyle: React.CSSProperties = {
  fontSize: "0.68rem",
  color: "#f59e0b",
  marginTop: "8px",
  padding: "6px 8px",
  background: "rgba(245, 158, 11, 0.05)",
  borderRadius: "6px",
  border: "1px solid rgba(245, 158, 11, 0.15)",
};

const debugRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  fontSize: "0.74rem",
  padding: "6px 12px",
  borderRadius: "8px",
  background: "rgba(15, 23, 42, 0.4)",
  border: "1px solid rgba(71, 85, 105, 0.2)",
  marginTop: "10px",
};

const debugLabelStyle: React.CSSProperties = {
  color: "#94a3b8",
};

const debugValueStyle: React.CSSProperties = {
  color: "#f1f5f9",
  fontFamily: "monospace",
  fontWeight: 500,
};
