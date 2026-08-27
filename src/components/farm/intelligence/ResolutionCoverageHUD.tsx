"use client";

import { useMemo, useEffect, useCallback, useRef } from "react";
import type { GroundTruthSummary } from "@/hooks/useLayer10";
import { useLayer10 } from "@/hooks/useLayer10";
import {
  isRenderedMaterialization,
  RENDER_AUTHORIZATION_VERSION,
} from "@/lib/agribrain/render-materialization";
import {
  isAsmaeSurfaceType,
  isCompositeAdvisorySurface,
  normalizeMode,
} from "@/lib/agribrain/source-policy-display-resolver";

interface ResolutionCoverageHUDProps {
  summary: GroundTruthSummary;
}

/** Source badge config */
const SOURCE_CONFIG: Record<string, { icon: string; label: string }> = {
  drone:        { icon: "🛩️", label: "Drone" },
  ip_camera:    { icon: "📷", label: "Camera" },
  farmer_photo: { icon: "📸", label: "Photo" },
  iot_sensor:   { icon: "📡", label: "IoT" },
  farmer_input: { icon: "🧑‍🌾", label: "Farmer" },
};

/** V61C: Full six-tier resolution bar segments */
const RESOLUTION_TIERS = [
  { key: "three_cm",    altKey: "three_cm_external_ground_truth_pct", label: "3cm",  color: "#06b6d4" },
  { key: "one_meter",   altKey: "one_meter_advisory_pct",             label: "1m advisory",   color: "#3b82f6" },
  { key: "two_meter",   altKey: "two_meter_model_assisted_pct",       label: "2m model-assisted", color: "#14b8a6" },
  { key: "three_meter", altKey: "three_meter_model_assisted_pct",     label: "3m model-assisted", color: "#22c55e" },
  { key: "five_meter",  altKey: "five_meter_model_assisted_pct",      label: "5m model-assisted", color: "#f59e0b" },
  { key: "ten_meter",   altKey: "ten_meter_fallback_pct",             label: "10m",  color: "rgba(100,116,139,0.5)" },
] as const;

function getStatusColor(status: string): string {
  switch (status) {
    case "available": return "#22c55e";
    case "absent":    return "#64748b";
    case "blocked":   return "#ef4444";
    default:          return "#64748b";
  }
}

function getVerdictConfig(summary: GroundTruthSummary): { label: string; color: string; glow: string } {
  const cert = summary?.certification_decision;
  if (!cert) {
    return { label: "Standard Fallback", color: "#64748b", glow: "none" };
  }
  if (cert.three_cm_allowed) {
    return { label: "3cm Validated ✓", color: "#06b6d4", glow: "0 0 12px rgba(6,182,212,0.3)" };
  }
  if (cert.one_meter_certified) {
    return { label: "Advisory Detail Tier", color: "#f59e0b", glow: "0 0 12px rgba(245,158,11,0.2)" };
  }
  return { label: "Standard Fallback", color: "#64748b", glow: "none" };
}

/**
 * ResolutionCoverageHUD — V61C
 * 
 * Compact glass-morphic widget that displays:
 * 1. Stacked resolution bar with all six tiers (3cm/1m/2m/3m/5m/10m)
 * 2. Evidence source badges with status colors
 * 3. Certification verdict text
 * 
 * Renders only when ground_truth_summary is provided.
 */
export default function ResolutionCoverageHUD({ summary }: ResolutionCoverageHUDProps) {
  const res = summary?.resolution_percentages ?? {};
  const verdict = useMemo(() => getVerdictConfig(summary), [summary]);
  const l10 = useLayer10();
  const {
    showExperimental1m,
    setShowExperimental1m,
    showCandidateMask,
    setShowCandidateMask,
    detailMode,
    data,
    visualIntensity,
    setVisualIntensity,
    experimentalDisplayState,
    experimentalVisualLadder,
    asmaeApprovalLadder,
    asmae_evidence_state,
    canopySource,
    bannerState,
    canShowExperimentalDetail,
    surfaceByType,
    activeExperimentalSurface,
    activeExperimentalSurfaceType,
    renderPlan,
    browserRenderReceipt,
    fetchLayer10,
  } = l10;
  const experimentalRenderMaterialization =
    browserRenderReceipt?.viewIdentity === renderPlan.viewIdentity
      ? browserRenderReceipt.overlayMaterialization
      : null;
  const lastCommittedIntensityRef = useRef(visualIntensity);

  const commitVisualIntensity = useCallback((value: number) => {
    const nextValue = Math.max(0.15, Math.min(0.75, value));
    if (Math.abs(lastCommittedIntensityRef.current - nextValue) < 0.001) {
      return;
    }
    lastCommittedIntensityRef.current = nextValue;
    if (!data?.plot_id) return;
    const farmId = (data.provenance?.farm_id as string) || "UNKNOWN";
    void fetchLayer10(data.plot_id, farmId, undefined, undefined, undefined, {
      forceRefresh: true,
      experimental1m: true,
      visualIntensity: nextValue,
      sourcePolicy: canopySource,
    });
  }, [canopySource, data, fetchLayer10]);

  // Force candidate mask off when low confidence
  const isLowConfidence = useMemo(() => {
    return data?.quality?.degradation_mode === "DEGRADED" ||
           (data?.quality?.reliability_score !== undefined && Number(data.quality.reliability_score) < 0.40);
  }, [data]);

  // ── BC.10.19 P0.7 — Experimental Detail Authorization Gate ─────────────
  // The experimental visual detail toggle may only be activated when a valid
  // The current render authority proof exists in the payload.
  // The frontend MUST NOT promote backend authority — it may only demote.
  const isExperimentalAuthorized = useMemo(() => {
    const authVersion = data?.render_authorization_version;
    const authMap = data?.render_authorizations;
    const surfaceType = activeExperimentalSurface?.semantic_type
      || activeExperimentalSurface?.type
      || activeExperimentalSurfaceType;
    if (authVersion !== RENDER_AUTHORIZATION_VERSION || !surfaceType) return false;
    const auth = authMap?.experimental?.[normalizeMode(l10.activeMode)]?.overlay?.[surfaceType];
    return auth?.authorized === true
      && auth?.renderKind === "proxy_overlay"
      && auth?.surfaceType === surfaceType
      && auth?.policy === "experimental"
      && auth?.role === "overlay";
  }, [
    data?.render_authorization_version,
    data?.render_authorizations,
    activeExperimentalSurface,
    activeExperimentalSurfaceType,
    l10.activeMode,
  ]);

  const canClaimExperimentalCoverage = isExperimentalAuthorized
    && isRenderedMaterialization(
      experimentalRenderMaterialization,
      activeExperimentalSurface?.semantic_type || activeExperimentalSurface?.type || activeExperimentalSurfaceType,
    );
  const baseRenderMaterialization =
    browserRenderReceipt?.viewIdentity === renderPlan.viewIdentity
      ? browserRenderReceipt.baseMaterialization
      : null;
  const renderedBaseType = baseRenderMaterialization?.surfaceType || "";
  const baseRasterMaterialized = isRenderedMaterialization(
    baseRenderMaterialization,
    renderedBaseType || undefined,
  );
  const asmaeRasterMaterialized = baseRasterMaterialized
    && isAsmaeSurfaceType(renderedBaseType);
  const providerFallbackMaterialized = baseRasterMaterialized
    && renderedBaseType === "NDVI_CLEAN";
  const compositeRasterMaterialized = baseRasterMaterialized
    && isCompositeAdvisorySurface(renderedBaseType);
  const committedHybridOverlayCount = browserRenderReceipt?.viewIdentity === renderPlan.viewIdentity
    ? (browserRenderReceipt.hybridOverlayMaterializations || []).filter(
        (item) => item.status === "rendered"
          && item.receipt?.publicationId === data?.publication_id,
      ).length + (canClaimExperimentalCoverage ? 1 : 0)
    : 0;
  const compositeStatusLabel = committedHybridOverlayCount > 0
    ? `Composite + ${committedHybridOverlayCount} committed hybrid overlay${committedHybridOverlayCount === 1 ? "" : "s"}`
    : "Composite Advisory Active";
  const spatialJobStatus = String(
    l10.data?.source_policy_display_state?.asmaePlotState?.activeSpatialJobStatus
      || l10.data?.asmae_evidence_state?.active_spatial_job_status
      || ""
  ).toLowerCase();
  const spatialMaterializationPending = ["queued", "running"].includes(spatialJobStatus);
  const spatialMaterializationNotEligible = spatialJobStatus === "not_eligible"
    || l10.data?.asmae_evidence_state?.reason === "NOT_ELIGIBLE_NO_EXECUTABLE_SPATIAL_SCENE";

  useEffect(() => {
    if (showExperimental1m && isLowConfidence && showCandidateMask) {
      setShowCandidateMask(false);
    }
  }, [showExperimental1m, isLowConfidence, showCandidateMask, setShowCandidateMask]);

  // BC.10.19 P0.7: If experimental detail was previously enabled but authority
  // is now missing (stale payload reloaded), auto-disable it.
  useEffect(() => {
    if (showExperimental1m && !isExperimentalAuthorized) {
      setShowExperimental1m(false);
    }
  }, [isExperimentalAuthorized, showExperimental1m, setShowExperimental1m]);

  if (!summary) return null;

  // V61C: Extract all six resolution percentages
  const tierPcts = RESOLUTION_TIERS.map((tier) => {
    const val = res[tier.altKey as keyof typeof res] ?? 0;
    return { ...tier, pct: typeof val === "number" ? val : 0 };
  });

  // Filter to tiers with > 0%
  const visibleTiers = tierPcts.filter((t) => t.pct > 0);

  const isResolutionMode = l10.activeMode === "resolution_coverage";

  const renderExperimental1mSection = () => {
    // V92.4-BC.10.10 Visual & Strict registries
    const visualSurface =
      (surfaceByType && (
        surfaceByType["EXPERIMENTAL_VISUAL_CANOPY_HIGHRES"] ||
        surfaceByType["NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL"] ||
        surfaceByType["EXPERIMENTAL_VISUAL_CANOPY"] ||
        surfaceByType["EXPERIMENTAL_TEXTURE_SUPPORT_MASK"]
      )) || null;

    const strictCandidateSurface =
      (surfaceByType && (
        surfaceByType["EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK"] ||
        surfaceByType["EXPERIMENTAL_FINE_DETAIL_CANDIDATE"]
      )) || null;

    const expSurf = visualSurface || strictCandidateSurface || null;
    const hasSurf = !!expSurf;
    const prov = (expSurf?.provenance ?? {}) as Record<string, unknown>;

    const visualCoveragePct = canClaimExperimentalCoverage
      ? experimentalVisualLadder?.textureAppliedPct ?? null
      : null;

    const strictCandidatePct = canClaimExperimentalCoverage
      ? experimentalVisualLadder?.unvalidatedCandidatePct ?? null
      : null;
    
    // Check generating state
    const generating = l10.experimental1mGenerating;

    if (generating) {
      return (
        <div style={{
          marginTop: 10,
          background: "rgba(168,85,247,0.12)",
          border: "1px solid rgba(168,85,247,0.3)",
          borderRadius: 8,
          padding: "10px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          color: "#d8b4fe",
          fontSize: 10,
          fontWeight: 500,
        }}>
          <span style={{
            display: "inline-block",
            width: 12,
            height: 12,
            border: "2px solid rgba(168,85,247,0.3)",
            borderTopColor: "#d8b4fe",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }} />
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
          <span>Generating experimental visual detail…</span>
        </div>
      );
    }

    const triggerGeneration = () => {
      if (!data?.plot_id) return;
      const plotId = data.plot_id;
      const farmId = (data.provenance?.farm_id as string) || "UNKNOWN";
      lastCommittedIntensityRef.current = visualIntensity;
      void fetchLayer10(plotId, farmId, undefined, undefined, undefined, {
        forceRefresh: true,
        experimental1m: true,
        visualIntensity,
        sourcePolicy: canopySource,
      });
    };

    const isReady = canShowExperimentalDetail || hasSurf;

    if (!isReady) {
      // State 1: Missing
      if (!hasSurf) {
        return (
          <div style={{
            marginTop: 10,
            borderTop: "1px solid rgba(255,255,255,0.06)",
            paddingTop: 8,
          }}>
            <p style={{ margin: "0 0 6px 0", fontSize: 9.5, color: "#94a3b8" }}>
              {canopySource === "asmae_diagnostic"
                ? "Optional experimental enhancement unavailable"
                : "Experimental visual detail is missing or stale."}
            </p>
            <button
              id="generate-1m-btn"
              onClick={triggerGeneration}
              style={{
                width: "100%",
                background: "linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)",
                border: "none",
                borderRadius: 6,
                color: "#ffffff",
                padding: "6px 12px",
                fontSize: 10,
                fontWeight: 600,
                cursor: "pointer",
                boxShadow: "0 2px 8px rgba(124,58,237,0.3)",
                transition: "transform 0.15s ease, opacity 0.15s ease",
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.transform = "translateY(-1px)";
                e.currentTarget.style.opacity = "0.95";
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.opacity = "1";
              }}
            >
              Generate Experimental Visual Detail
            </button>
          </div>
        );
      }

      // State 2: Empty (only if not ready)
      if (!canShowExperimentalDetail && !hasSurf) { // !l10.canShowExperimentalDetail
        const isExpBase = canopySource === "experimental";
        return (
          <div style={{
            marginTop: 10,
            borderTop: "1px solid rgba(255,255,255,0.06)",
            paddingTop: 8,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, opacity: 0.5 }}>
              <input type="checkbox" id="experimental-1m-toggle-empty" checked={false} disabled style={{ cursor: "not-allowed" }} />
              <label htmlFor="experimental-1m-toggle-empty" style={{ fontSize: 10, fontWeight: 600, color: "#94a3b8", cursor: "not-allowed" }}>
                {isExpBase ? "Show extra detail / candidate overlay" : "Experimental Visual Detail"}
              </label>
            </div>
            <div style={{
              marginTop: 6,
              background: isExpBase ? "rgba(168,85,247,0.08)" : "rgba(239,68,68,0.08)",
              border: isExpBase ? "1px solid rgba(168,85,247,0.2)" : "1px solid rgba(239,68,68,0.2)",
              borderRadius: 8,
              padding: "8px",
              fontSize: 9.5,
              color: isExpBase ? "#d8b4fe" : "#fca5a5",
            }}>
              <p style={{ margin: "0 0 6px 0", fontWeight: 600 }}>
                {isExpBase ? "Experimental visual base active" : "No visual detail candidates available for this run."}
              </p>
              {!isExpBase && (
                <button
                  onClick={triggerGeneration}
                  style={{
                    width: "100%",
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(239,68,68,0.3)",
                    borderRadius: 6,
                    color: "#fca5a5",
                    padding: "4px 8px",
                    fontSize: 9,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.background = "rgba(239,68,68,0.12)";
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                  }}
                >
                  Generate deeper visual analysis?
                </button>
              )}
            </div>
          </div>
        );
      }
    }

    const isExpBase = canopySource === "experimental";
    const rawConfidence = prov.fine_detail_confidence;
    const rawUncertainty = prov.fine_detail_uncertainty;
    const confidenceText = rawConfidence !== null && rawConfidence !== undefined ? `${Math.round(Number(rawConfidence) * 100)}%` : "N/A";
    const uncertaintyText = rawUncertainty !== null && rawUncertainty !== undefined ? `${Math.round(Number(rawUncertainty) * 100)}%` : "N/A";
    const reason = prov.fine_detail_reason ?? "deconvolution candidate, not certified";
    const certificationStatus = prov.certification_status ?? "experimental_learning";
    const candidateSource = prov.candidate_source ?? "quality_gated_candidate";

    const isAsmaeOrHybrid = canopySource === "asmae_diagnostic" || canopySource === "hybrid";
    const showLens = showExperimental1m || isAsmaeOrHybrid;

    return (
      <div style={{
        marginTop: 10,
        borderTop: "1px solid rgba(255,255,255,0.06)",
        paddingTop: 8,
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: showLens ? 8 : 0,
        }}>
          {!isAsmaeOrHybrid ? (
            <>
              {/* BC.10.19 P0.7: authority-gated experimental detail toggle */}
              {!isExperimentalAuthorized ? (
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  opacity: 0.45,
                  cursor: "not-allowed",
                  userSelect: "none",
                }} title={`Experimental detail requires a valid authority proof (${RENDER_AUTHORIZATION_VERSION}). Authority is calibrating.`}>
                  <input
                    type="checkbox"
                    id="experimental-1m-toggle-ready"
                    checked={false}
                    disabled
                    style={{ cursor: "not-allowed" }}
                  />
                  <label
                    htmlFor="experimental-1m-toggle-ready"
                    style={{ fontSize: 10, fontWeight: 600, color: "#64748b", cursor: "not-allowed" }}
                  >
                    {isExpBase ? "Show extra detail / candidate overlay" : "Experimental Visual Detail"}
                    <span style={{ marginLeft: 4, fontSize: 9, color: "#f59e0b" }}>🔒 Auth pending</span>
                  </label>
                </div>
              ) : (
                <>
                  <input
                    type="checkbox"
                    id="experimental-1m-toggle-ready"
                    checked={l10.experimentalOverlayEnabled}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      if (checked) {
                        if (detailMode === "farmer") {
                          const ok = typeof window !== "undefined" && window.confirm("Advanced experimental layer — show anyway?");
                          if (ok) {
                            setShowExperimental1m(true);
                          }
                        } else {
                          setShowExperimental1m(true);
                        }
                      } else {
                        setShowExperimental1m(false);
                      }
                    }}
                    style={{ cursor: "pointer" }}
                  />
                  <label
                    htmlFor="experimental-1m-toggle-ready"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: "#e2e8f0",
                      cursor: "pointer",
                      userSelect: "none"
                    }}
                  >
                    {isExpBase ? "Show extra detail / candidate overlay" : "Experimental Visual Detail"}
                  </label>
                </>
              )}
            </>
          ) : (
            compositeRasterMaterialized ? (
              <div style={{
                fontSize: 10,
                fontWeight: 700,
                color: "#34d399",
                display: "flex",
                alignItems: "center",
                gap: 4
              }}>
                <span>⚙️</span>
                <span>{compositeStatusLabel}</span>
              </div>
            ) : (
              <div style={{
                fontSize: 10,
                fontWeight: 700,
                color: asmaeRasterMaterialized ? "#34d399" : "#fbbf24",
                display: "flex",
                alignItems: "center",
                gap: 4
              }}>
                <span>⚙️</span>
                <span>
                  {asmaeRasterMaterialized
                    ? "ASMAE 10m Diagnostic Active (1m approval unavailable)"
                    : spatialMaterializationPending
                      ? "ASMAE Requested — Spatial Raster Materialization Pending"
                      : spatialMaterializationNotEligible
                        ? "ASMAE Spatial Unavailable - No Executable Scene"
                      : providerFallbackMaterialized
                        ? "NDVI Provider Fallback Active"
                        : "ASMAE Unavailable — No Fallback Layer Committed"}
                </span>
              </div>
            )
          )}
        </div>

        {/* Expert mode candidate mask toggle */}
        {l10.experimentalOverlayEnabled && detailMode === "expert" && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginTop: 6,
            marginBottom: 8,
            paddingLeft: 16,
          }}>
            <input
              type="checkbox"
              id="experimental-candidate-mask-toggle"
              checked={showCandidateMask}
              onChange={(e) => {
                setShowCandidateMask(e.target.checked);
              }}
              style={{ cursor: "pointer" }}
            />
            <label
              htmlFor="experimental-candidate-mask-toggle"
              style={{
                fontSize: 9.5,
                fontWeight: 600,
                color: "#cbd5e1",
                cursor: "pointer",
                userSelect: "none"
              }}
            >
              Show Candidate Mask
            </label>
          </div>
        )}

        {showLens && (
          <div style={{
            background: isAsmaeOrHybrid ? "rgba(52,211,153,0.06)" : "rgba(168,85,247,0.1)",
            border: isAsmaeOrHybrid ? "1px solid rgba(52,211,153,0.2)" : "1px solid rgba(168,85,247,0.25)",
            borderRadius: 8,
            padding: "8px 10px",
            fontSize: 9,
            color: isAsmaeOrHybrid ? "#cbd5e1" : "#d8b4fe",
            lineHeight: "1.3em",
          }}>
            {isAsmaeOrHybrid ? (
              // ASMAE Approval Ladder OR ASMAE Diagnostic Unavailable
              compositeRasterMaterialized ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div style={{ fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 3, color: "#34d399" }}>
                    <span>✓</span>
                    <span>{compositeStatusLabel}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>Mode:</span>
                    <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>Composite Advisory</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>Source basis:</span>
                    <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>Multi-Sensor Composite</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>Detail ladder:</span>
                    <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>10m Advisory (No 1m Approval)</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 3, marginTop: 2 }}>
                    <span style={{ color: "#34d399" }}>Authority:</span>
                    <span style={{ fontWeight: "bold", color: "#34d399" }}>advisory only</span>
                  </div>
                </div>
              ) : (asmaeApprovalLadder?.oneMeterAsmaeApprovalPct !== null && asmaeApprovalLadder?.oneMeterAsmaeApprovalPct !== undefined) ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div style={{ fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 3, color: "#34d399" }}>
                    <span>✓</span>
                    <span>ASMAE 1m Approval Ladder</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>ASMAE 1m approval:</span>
                    <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>{asmaeApprovalLadder?.oneMeterAsmaeApprovalPct}%</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>2.5m model-assisted:</span>
                    <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>{asmaeApprovalLadder?.modelAssisted2_5mPct}%</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>5m generalized:</span>
                    <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>{asmaeApprovalLadder?.generalized5mPct}%</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 3, marginTop: 2 }}>
                    <span style={{ color: "#34d399" }}>Authority:</span>
                    <span style={{ fontWeight: "bold", color: "#34d399" }}>{String(prov.certification_status ?? "verified")}</span>
                  </div>
                </div>
              ) : (asmaeRasterMaterialized && (bannerState === "asmae_diagnostic_active" || bannerState === "hybrid_active")) ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div style={{ fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 3, color: "#38bdf8" }}>
                    <span>🔬</span>
                    <span>ASMAE 10m Diagnostic Active</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>Scientific basis:</span>
                    <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>10m ASMAE Diagnostic</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>1m approval:</span>
                    <span style={{ fontWeight: "bold", color: "#94a3b8" }}>unavailable</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 3, marginTop: 2 }}>
                    <span style={{ color: "#38bdf8" }}>Authority:</span>
                    <span style={{ fontWeight: "bold", color: "#38bdf8" }}>advisory only</span>
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div style={{ fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 3, color: "#f87171" }}>
                    <span>⚠️</span>
                    <span>ASMAE diagnostic unavailable</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>Reason:</span>
                    <span style={{ fontWeight: "bold", color: "#fca5a5" }}>{(asmaeApprovalLadder?.unavailableReason || asmae_evidence_state?.reason || "no full scene stack").replace(/_/g, " ")}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>Displayed raster:</span>
                    <span style={{ fontWeight: "bold", color: providerFallbackMaterialized ? "#fca5a5" : "#94a3b8" }}>
                      {providerFallbackMaterialized
                        ? "NDVI_CLEAN provider fallback"
                        : baseRasterMaterialized
                          ? renderedBaseType
                          : "none"}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                    <span style={{ color: "#94a3b8" }}>ASMAE 1m approval:</span>
                    <span style={{ fontWeight: "bold", color: "#fca5a5" }}>unavailable</span>
                  </div>
                </div>
              )
            ) : (
              // Experimental Visual Ladder
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <div style={{ fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 3, color: "#e9d5ff" }}>
                  <span>🔬</span>
                  <span>Experimental Visual Detail</span>
                </div>
                {!canClaimExperimentalCoverage ? (
                  <div style={{ paddingLeft: 6, margin: "4px 0", color: "#fca5a5", lineHeight: 1.4 }}>
                    Spatial coverage unavailable — the authorized experimental overlay did not materialize
                    {experimentalRenderMaterialization?.reason
                      ? ` (${experimentalRenderMaterialization.reason.replace(/_/g, " ")})`
                      : ""}.
                  </div>
                ) : experimentalVisualLadder?.textureAppliedPct === null || experimentalVisualLadder?.status === "ladder_pending_or_cache_stale" ? (
                  <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6, margin: "4px 0" }}>
                    <span style={{ color: "#fbbf24", fontWeight: "bold" }}>Experimental ladder pending/cache stale</span>
                  </div>
                ) : (
                  <>
                    <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                      <span style={{ color: "#a5b4fc" }}>Texture applied to candidates:</span>
                      <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>{visualCoveragePct !== null ? `${Math.round(visualCoveragePct)}%` : "N/A"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                      <span style={{ color: "#a5b4fc" }}>Unvalidated candidate cells:</span>
                      <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>{strictCandidatePct !== null ? `${strictCandidatePct}%` : "N/A"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                      <span style={{ color: "#a5b4fc" }}>Validated fine detail:</span>
                      <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>{typeof experimentalVisualLadder?.validatedFineDetailPct === "number" ? `${experimentalVisualLadder.validatedFineDetailPct}%` : "N/A"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                      <span style={{ color: "#a5b4fc" }}>Evidence / display grid:</span>
                      <span style={{ fontWeight: "bold", color: "#f1f5f9" }}>{experimentalVisualLadder ? `${experimentalVisualLadder.sourceEvidenceResolutionM}m / ${experimentalVisualLadder.displayGridResolutionM}m` : "N/A"}</span>
                    </div>
                  </>
                )}
                <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                  <span style={{ color: "#94a3b8" }}>ASMAE 1m approval:</span>
                  <span style={{ color: "#fb7185", fontWeight: "bold" }}>
                    {asmaeApprovalLadder?.oneMeterAsmaeApprovalPct !== null
                      ? "available"
                      : `unavailable — ${(asmaeApprovalLadder?.unavailableReason || asmae_evidence_state?.reason || "no full scene stack").replace(/_/g, " ")}`}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6 }}>
                  <span style={{ color: "#94a3b8" }}>10m diagnostic support:</span>
                  <span style={{ color: data?.source_policy_display_state?.asmaePlotState?.spatialAvailable ? "#34d399" : "#fbbf24", fontWeight: "bold" }}>
                    {data?.source_policy_display_state?.asmaePlotState?.spatialAvailable
                      ? "available · scouting authority"
                      : "not spatially available"}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 6, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 3, marginTop: 2 }}>
                  <span style={{ color: "#fca5a5" }}>Authority:</span>
                  <span style={{ fontWeight: "bold", color: "#fca5a5" }}>scouting only</span>
                </div>
              </div>
            )}

            {showExperimental1m && isLowConfidence && (
              <div style={{
                background: "rgba(239, 68, 68, 0.2)",
                border: "1px solid rgba(239, 68, 68, 0.5)",
                borderRadius: 6,
                padding: "6px 8px",
                marginTop: 6,
                fontSize: 9.5,
                color: "#fca5a5",
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}>
                <span>⚠️</span>
                <span>Low Spatial Confidence — Scouting Only</span>
              </div>
            )}

            {showExperimental1m && experimentalDisplayState === "base_fallback_experimental_missing" && (
              <div style={{
                background: "rgba(245, 158, 11, 0.12)",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                borderRadius: 6,
                padding: "6px 8px",
                marginTop: 6,
                fontSize: 9,
                color: "#fef08a",
                fontWeight: 600,
                lineHeight: "1.25em",
              }}>
                ⚠️ Experimental unavailable for this mode. Showing committed composite advisory raster.
              </div>
            )}
            
            {certificationStatus === "experimental_learning_unvalidated" ? (
              <div style={{
                background: "rgba(245,158,11,0.08)",
                border: "1px solid rgba(245,158,11,0.2)",
                borderRadius: 6,
                padding: "6px",
                marginBottom: 6,
                fontSize: 8.5,
                color: "#fef08a",
              }}>
                <div style={{ fontWeight: 700, marginBottom: 2 }}>Unvalidated texture-learning candidate</div>
                <div>Confidence: N/A</div>
                <div>Use for scouting only</div>
              </div>
            ) : (
              <p style={{ margin: "0 0 6px 0", color: "#e9d5ff" }}>
                This overlay shows where AgriBrain’s sub-pixel model detects possible fine-scale structure. It is experimental and improves over time through validation from field observations, photos, sensors, and drone evidence. Use it for scouting guidance only. It does not change certified agronomic recommendations.
              </p>
            )}

            {/* Expert mode details */}
            {detailMode === "expert" && (
              <div style={{
                marginTop: 6,
                borderTop: "1px solid rgba(168,85,247,0.15)",
                paddingTop: 6,
                display: "flex",
                flexDirection: "column",
                gap: 3,
                fontSize: 8.5,
                color: "#c084fc",
                fontFamily: "monospace",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Candidate source:</span>
                  <span style={{ color: "#38bdf8" }}>{String(candidateSource)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Confidence:</span>
                  <span style={{ color: "#38bdf8" }}>{confidenceText}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Uncertainty:</span>
                  <span style={{ color: "#fb7185" }}>{uncertaintyText}</span>
                </div>
                <div style={{ wordBreak: "break-all" }}>
                  <span>Reason:</span> <span style={{ color: "#e9d5ff" }}>{String(reason)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>state_update_allowed:</span>
                  <span style={{ color: "#f43f5e" }}>false</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>production_selectable:</span>
                  <span style={{ color: "#f43f5e" }}>false</span>
                </div>
                <div style={{
                  marginTop: 6,
                  borderTop: "1px dashed rgba(168,85,247,0.15)",
                  paddingTop: 6,
                }}>
                  {/* V65G Fix 1: Dynamic resolution metadata — not hardcoded */}
                  {(() => {
                    const certBasis = Number(prov.certified_data_basis_m ?? prov.effective_data_basis_m ?? 10);
                    const vScale = Number(prov.visual_scale ?? 4);
                    const displayRes = (certBasis / vScale).toFixed(1);
                    const nativeBasis = prov.native_sensor_basis_m ?? "10–20";
                    return (
                      <div style={{
                        marginBottom: 6,
                        padding: "4px 6px",
                        background: "rgba(168,85,247,0.06)",
                        borderRadius: 4,
                        fontSize: 8,
                        color: "#c084fc",
                        lineHeight: "1.4em",
                      }}>
                        <div>Display grid: ~{displayRes} m interpolated visual surface</div>
                        <div>Certified grid basis: {certBasis} m working grid</div>
                        <div>Native evidence basis: Sentinel-2 {String(nativeBasis)} m, depending on surface</div>
                        <div style={{ color: "#f87171", fontWeight: 600, marginTop: 2 }}>Not a direct 1 m observation</div>
                      </div>
                    );
                  })()}
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span>Visual Intensity:</span>
                    <span style={{ color: "#38bdf8" }}>{visualIntensity.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0.15"
                    max="0.75"
                    step="0.05"
                    value={visualIntensity}
                    onChange={(e) => {
                      setVisualIntensity(parseFloat(e.target.value));
                    }}
                    onPointerUp={(e) => commitVisualIntensity(parseFloat(e.currentTarget.value))}
                    onBlur={(e) => commitVisualIntensity(parseFloat(e.currentTarget.value))}
                    onKeyUp={(e) => {
                      if (e.key === "Enter") {
                        commitVisualIntensity(parseFloat(e.currentTarget.value));
                      }
                    }}
                    style={{
                      width: "100%",
                      accentColor: "#a855f7",
                      cursor: "pointer",
                      height: 4,
                      background: "rgba(255,255,255,0.15)",
                      borderRadius: 2,
                      outline: "none",
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  if (!isResolutionMode) {
    return (
      <div
        id="resolution-coverage-hud"
        style={{
          background: "rgba(8,12,25,0.88)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 12,
          padding: "10px 14px",
          width: 260,
          boxShadow: "0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)",
        }}
      >
        {canClaimExperimentalCoverage && (
          <div style={{
            background: "linear-gradient(135deg, rgba(168,85,247,0.2) 0%, rgba(124,58,237,0.2) 100%)",
            border: "1px solid rgba(168,85,247,0.4)",
            borderRadius: 8,
            padding: "6px 10px",
            marginBottom: 8,
            display: "flex",
            alignItems: "center",
            gap: 6,
            color: "#d8b4fe",
            fontSize: 9.5,
            fontWeight: 600,
            boxShadow: "0 2px 8px rgba(168,85,247,0.15)",
          }}>
            <span>🔬</span>
            <span>Experimental Visual Detail — scouting only</span>
          </div>
        )}
        {/* ── Experimental Toggle ────────────────────────────── */}
        {renderExperimental1mSection()}
      </div>
    );
  }

  return (
    <div
      id="resolution-coverage-hud"
      style={{
        background: "rgba(8,12,25,0.88)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 12,
        padding: "10px 14px",
        width: 260,
        boxShadow: "0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)",
      }}
    >
      {canClaimExperimentalCoverage && (
        <div style={{
          background: "linear-gradient(135deg, rgba(168,85,247,0.2) 0%, rgba(124,58,237,0.2) 100%)",
          border: "1px solid rgba(168,85,247,0.4)",
          borderRadius: 8,
          padding: "6px 10px",
          marginBottom: 8,
          display: "flex",
          alignItems: "center",
          gap: 6,
          color: "#d8b4fe",
          fontSize: 9.5,
          fontWeight: 600,
          boxShadow: "0 2px 8px rgba(168,85,247,0.15)",
        }}>
          <span>🔬</span>
          <span>Experimental Visual Detail — scouting only</span>
        </div>
      )}
      {/* ── Verdict ──────────────────────────────────────────── */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 8,
      }}>
        <span style={{
          fontSize: 10,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "#94a3b8",
        }}>
          Resolution Coverage
        </span>
        <span style={{
          fontSize: 10,
          fontWeight: 700,
          color: verdict.color,
          textShadow: verdict.glow,
          letterSpacing: "0.02em",
        }}>
          {verdict.label}
        </span>
      </div>

      {/* ── Stacked Bar (V61C: six tiers) ────────────────────── */}
      <div style={{
        display: "flex",
        height: 8,
        borderRadius: 4,
        overflow: "hidden",
        marginBottom: 6,
        background: "rgba(255,255,255,0.04)",
      }}>
        {visibleTiers.map((tier) => (
          <div
            key={tier.key}
            style={{
              width: `${tier.pct}%`,
              background: tier.color,
              transition: "width 0.5s ease",
            }}
            title={`${tier.label}: ${tier.pct.toFixed(1)}%`}
          />
        ))}
      </div>

      {/* ── Legend Labels (V61C: all tiers) ────────────────────── */}
      <div style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "2px 8px",
        marginBottom: 10,
        fontSize: 9,
        color: "#94a3b8",
      }}>
        {tierPcts.map((tier) => (
          <span key={tier.key} style={{ opacity: tier.pct > 0 ? 1 : 0.4 }}>
            <span style={{
              display: "inline-block",
              width: 6,
              height: 6,
              borderRadius: 2,
              background: tier.color,
              marginRight: 3,
              verticalAlign: "middle",
            }} />
            {tier.label} {tier.pct.toFixed(0)}%
          </span>
        ))}
      </div>

      {/* ── Evidence Source Badges ────────────────────────────── */}
      <div style={{
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        paddingTop: 8,
      }}>
        {(summary.evidence_sources ?? []).map((src) => {
          const cfg = SOURCE_CONFIG[src.type] ?? { icon: "📌", label: src.type };
          const statusColor = getStatusColor(src.status);
          return (
            <div
              key={src.type}
              title={`${cfg.label}: ${src.status} (${src.scope})`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
                padding: "2px 6px",
                borderRadius: 6,
                background: "rgba(255,255,255,0.04)",
                border: `1px solid ${statusColor}33`,
                fontSize: 9,
                color: statusColor,
                fontWeight: 500,
                cursor: "default",
                transition: "all 0.15s ease",
              }}
            >
              <span style={{ fontSize: 11 }}>{cfg.icon}</span>
              <span>{cfg.label}</span>
              <span style={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: statusColor,
                boxShadow: `0 0 4px ${statusColor}66`,
              }} />
            </div>
          );
        })}
      </div>

      {/* ── State Update Lock ────────────────────────────────── */}
      {summary.certification_decision?.state_updates_blocked && (
        <div style={{
          marginTop: 6,
          fontSize: 9,
          color: "#94a3b8",
          display: "flex",
          alignItems: "center",
          gap: 4,
        }}>
          <span style={{ fontSize: 10 }}>🔒</span>
          <span>State updates blocked (1m + 3cm)</span>
        </div>
      )}

      {/* ── Experimental Toggle ────────────────────────────── */}
      {renderExperimental1mSection()}
    </div>
  );
}

// activeSurface?.type?.startsWith("COMPOSITE_")
