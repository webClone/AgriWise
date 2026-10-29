"use client";

/**
 * PlotDashboard V4 — Full Intelligence Operating Surface
 *
 * Uses TWO hooks:
 *   - useLayer10 → map surfaces, zones, histograms (proven, working)
 *   - usePlotIntelligence → engines, timeline, raw data (new overlay)
 *
 * Layout:
 *   ┌────────────────────────────────────────────────────────┐
 *   │  PlotContextBand (rendered by layout)                  │
 *   ├──────┬────────────────────────────────┬────────────────┤
 *   │Engine│      Satellite Map             │  Analysis      │
 *   │Panel │   (surfaces + zones)           │  Sidebar       │
 *   │      │  [HUD]             [Histogram] │                │
 *   ├──────┴────────────────────────────────┴────────────────┤
 *   │  TimelineStrip (7 past ← TODAY → 7 future)            │
 *   ├────────────────────────────────────────────────────────┤
 *   │  FieldInsightBar                                       │
 *   └────────────────────────────────────────────────────────┘
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { useLayer10, MODE_CONFIG } from "@/hooks/useLayer10";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import FieldInsightBar from "@/components/farm/intelligence/FieldInsightBar";
import FieldSnapshotHUD from "@/components/farm/intelligence/FieldSnapshotHUD";
import HistogramDrawer from "@/components/farm/intelligence/HistogramDrawer";
import ZoneDetailStrip from "@/components/farm/intelligence/ZoneDetailStrip";
import MethodologyDrawer from "@/components/farm/intelligence/MethodologyDrawer";
import EnginePipelinePanel from "@/components/farm/intelligence/EnginePipelinePanel";
import TimelineStrip from "@/components/farm/intelligence/TimelineStrip";
import CropIdentityBanner from "@/components/farm/intelligence/CropIdentityBanner";
import PlotLoadingSequence from "@/components/farm/intelligence/PlotLoadingSequence";
import ResolutionCoverageHUD from "@/components/farm/intelligence/ResolutionCoverageHUD";

// ── Lazy-loaded panels (only imported when opened) ──────────────────────
const AgriBrainWorkspace = dynamic(
  () => import("@/components/farm/intelligence/AgriBrainWorkspace"),
  { ssr: false }
);
const DroneMissionPanel = dynamic(
  () => import("@/components/farm/drone/DroneMissionPanel"),
  { ssr: false }
);
const SensorNetworkWorkspace = dynamic(
  () => import("@/components/farm/intelligence/SensorNetworkWorkspace"),
  { ssr: false }
);
const IrrigationDashboard = dynamic(
  () => import("@/components/irrigation/IrrigationDashboard"),
  { ssr: false }
);
const AddEvidenceModal = dynamic(
  () => import("@/components/farm/intelligence/AddEvidenceModal"),
  { ssr: false }
);
const RawDataSidebar = dynamic(
  () => import("@/components/farm/intelligence/RawDataSidebar"),
  { ssr: false }
);
const MesiaObservatoryWorkspace = dynamic(
  () => import("@/components/farm/intelligence/MesiaObservatoryWorkspace"),
  { ssr: false }
);

const PlotMapShell = dynamic(() => import("@/components/farm/map/PlotMapShell"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full bg-slate-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
        <span className="text-slate-500 text-sm tracking-wide">Loading field view…</span>
      </div>
    </div>
  ),
});

interface PlotDashboardProps {
  farm: Record<string, unknown> | null;
  plot: Record<string, unknown> | null;
  cropName?: string;
  context: Record<string, unknown> | null;
  plotId?: string;
  farmId?: string;
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.1 }
  }
};
const slideLeft = { hidden: { x: -40, opacity: 0 }, visible: { x: 0, opacity: 1, transition: { type: "spring" as const, stiffness: 300, damping: 30 } } };
const slideRight = { hidden: { x: 40, opacity: 0 }, visible: { x: 0, opacity: 1, transition: { type: "spring" as const, stiffness: 300, damping: 30 } } };
const slideUp = { hidden: { y: 40, opacity: 0 }, visible: { y: 0, opacity: 1, transition: { type: "spring" as const, stiffness: 300, damping: 30 } } };
const slideDown = { hidden: { y: -40, opacity: 0 }, visible: { y: 0, opacity: 1, transition: { type: "spring" as const, stiffness: 300, damping: 30 } } };
const popIn = { hidden: { scale: 0.5, opacity: 0 }, visible: { scale: 1, opacity: 1, transition: { type: "spring" as const, stiffness: 400, damping: 25 } } };

export default function PlotDashboard({ farm, plot, cropName, context, plotId: _plotId, farmId: _farmId }: PlotDashboardProps) {
  const plotId = _plotId || String(plot?.id || "");
  const farmId = _farmId || String(farm?.id || "");
  const [mounted, setMounted] = useState(false);
  const [methodologyMetric, setMethodologyMetric] = useState<string | null>(null);
  const [showDronePanel, setShowDronePanel] = useState(false);
  const [showSensorsPanel, setShowSensorsPanel] = useState(false);
  const [showMesiaPanel, setShowMesiaPanel] = useState(false);
  const [showIrrigationPanel, setShowIrrigationPanel] = useState(false);
  const [isEvidenceModalOpen, setIsEvidenceModalOpen] = useState(false);
  const [isRefreshingVision, setIsRefreshingVision] = useState(false);
  const [visionRefreshStatus, setVisionRefreshStatus] = useState<string | null>(null);
  const [mapVisualLens, setMapVisualLens] = useState<"standard" | "thermal" | "chlorophyll" | "chroma">("standard");

  // ── AUTHORITATIVE PUBLICATION OWNER: useParcelAssessment ────────────────
  const parcelAssessment = useParcelAssessment();

  // ── PRESENTATION VIEW ADAPTERS ──────────────────────────────────────────
  const l10 = useLayer10();
  const pi = usePlotIntelligence();

  useEffect(() => { setMounted(true); }, []);

  // Fetch authoritative canonical parcel assessment on mount / plot change
  useEffect(() => {
    if (plot?.id && farm?.id) {
      parcelAssessment.fetchAssessment(String(plot.id), String(farm.id), {
        geometry: plot.geoJson,
        cropCycleId: (plot as any)?.cropCycleId || undefined,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plot?.id, farm?.id]);

  // P2-B: Retire independent intelligence fetch — derive presentation state strictly from canonical assessment
  const injectData = pi.injectData;
  useEffect(() => {
    if (l10.data) {
      injectData(l10.data, (plot as any)?.id, l10.isApplicable);
    }
  }, [l10.data, l10.isApplicable, injectData, (plot as any)?.id]);

  // ── Screen state (from L10 — the working hook) ─────────────────────────
  // Simplified: no more "diagnose" state that hides everything
  const screenState = useMemo<"observe" | "decide">(() => {
    if (l10.isDecideMode) return "decide";
    return "observe";
  }, [l10.isDecideMode]);

  const selectedZoneData = useMemo(() => {
    if (!l10.selectedZone || !l10.data) return null;
    return l10.data.zones.find((z) => z.zone_id === l10.selectedZone) ?? null;
  }, [l10.selectedZone, l10.data]);

  const handleHistogramToggle = useCallback(() => {
    l10.setHistogramExpanded(!l10.histogramExpanded);
  }, [l10]);

  // ── Manual Satellite Vision Refresh ────────────────────────────────────
  const refreshSatelliteVision = useCallback(async () => {
    if (isRefreshingVision || !plot?.id) return;

    setIsRefreshingVision(true);
    setVisionRefreshStatus("Fetching satellite tile…");

    const lat = typeof plot.lat === "number" ? plot.lat : parseFloat(String(plot.lat || "0"));
    const lng = typeof plot.lng === "number" ? plot.lng : parseFloat(String(plot.lng || "0"));
    const plotIdStr = String(plot.id);

    try {
      // Step 1: Fetch tile
      const tileRes = await fetch("/api/agribrain/satellite-tile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plot_id: plotIdStr,
          lat, lng,
          polygon: plot.polygon || plot.coordinates || null,
        }),
      });
      const tileData = await tileRes.json();
      if (tileData.status !== "fetched" && tileData.status !== "cached") {
        setVisionRefreshStatus("No satellite tile available");
        setTimeout(() => setVisionRefreshStatus(null), 3000);
        return;
      }

      // Step 2: Vision analysis
      setVisionRefreshStatus("Running visual analysis…");
      let vision = null;
      try {
        const visionRes = await fetch("/api/agribrain/satellite-vision", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plot_id: plotIdStr, lat, lng }),
        });
        const visionData = await visionRes.json();
        if (visionData.status === "analyzed") {
          vision = visionData.vision;
        }
      } catch { /* Vision is best-effort */ }

      // Step 3: Save
      setVisionRefreshStatus("Saving observations…");
      try {
        await fetch(`/api/agribrain/satellite-tile-save/${plotIdStr}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            fetched_date: tileData.metadata?.fetched_date || new Date().toISOString(),
            vision,
          }),
        });
      } catch { /* Save is best-effort */ }

      setVisionRefreshStatus("✓ Visual evidence updated");
      setTimeout(() => setVisionRefreshStatus(null), 3000);
    } catch {
      setVisionRefreshStatus("Failed — try again later");
      setTimeout(() => setVisionRefreshStatus(null), 3000);
    } finally {
      setIsRefreshingVision(false);
    }
  }, [isRefreshingVision, plot]);

  const groundingClass = l10.activeSurface?.grounding_class ?? "UNIFORM";

  const coverageRatio = useMemo(() => {
    if (!l10.activeSurface || !l10.data) return null;
    const totalCells = l10.data.grid.height * l10.data.grid.width;
    if (totalCells === 0) return null;
    let validCount = 0;
    for (const row of l10.activeSurface.values) {
      for (const v of row) {
        if (v !== null && v !== undefined) validCount++;
      }
    }
    return validCount / totalCells;
  }, [l10.activeSurface, l10.data]);

  const isMapVisible = !l10.isDecideMode;
  const modeLabel = MODE_CONFIG[l10.activeMode]?.label ?? "Surface";
  const asmaeWorkerState = l10.data?.source_policy_display_state?.asmaePlotState ?? null;
  const asmaeWorkerStatus = String(
    asmaeWorkerState?.activeSpatialJobStatus || "",
  ).toLowerCase();
  const asmaePublicationRelation = String(
    asmaeWorkerState?.publicationRelation || "",
  ).toLowerCase();
  // A request-local Layer 10 failure is not necessarily an ASMAE worker
  // failure, but it still has to remain visible when a last-known-good map is
  // retained. PlotLoadingSequence distinguishes the two cases from the
  // durable job receipt; this gate must not suppress generic publication
  // errors such as a masking or serialization exception.
  const surfacePublicationRequestError = Boolean(l10.error);
  const showAsmaeWorkerProgress = Boolean(
    !l10.data
    || l10.loading
    || surfacePublicationRequestError
    || [
      "queued",
      "running",
      "stalled",
      "completed_reintegration_pending",
      "failed",
      "error",
      "cancelled",
    ].includes(asmaeWorkerStatus)
    || (asmaeWorkerStatus === "completed" && asmaePublicationRelation !== "published"),
  );
  const handleAsmaeWorkerRetry = useCallback(() => {
    if (!plotId || l10.loading) return;
    l10.setCanopySource("asmae_diagnostic");
    void l10.fetchLayer10(
      plotId,
      farmId,
      undefined,
      undefined,
      cropName,
      { forceRefresh: true, sourcePolicy: "asmae_diagnostic" },
    );
  }, [cropName, farmId, l10, plotId]);

  return (
    <div className="aw-dashboard" id="plot-dashboard" style={{ direction: "ltr" }} suppressHydrationWarning={true}>

      {/* ── Map Canvas ──────────────────────────────────────────────── */}
      <div
        className="aw-dashboard__map"
        style={{
          visibility: isMapVisible ? "visible" : "hidden",
          height: isMapVisible ? undefined : 0,
          overflow: isMapVisible ? undefined : "hidden",
          position: isMapVisible ? undefined : "absolute",
        }}
        suppressHydrationWarning={true}
      >
        {farm && (
          <PlotMapShell
            farms={farm ? [farm] : []}
            plots={plot ? [plot] : []}
            activeMode={l10.activeMode}
            cropName={cropName}
            surfaceData={l10.activeSurface}
            surfaceColors={l10.activeColors}
            confidenceSurface={l10.activeConfidenceSurface}
            reliabilitySurface={l10.activeReliabilitySurface}
            deviationSurface={
              l10.activeMode === "veg_attention"
                ? (l10.data?.surfaces.find(s => s.type === "NDVI_DEVIATION") ?? null)
                : null
            }
            gridHeight={l10.data?.grid.height}
            gridWidth={l10.data?.grid.width}
            l10Zones={l10.data?.zones ?? null}
            selectedZone={l10.selectedZone}
            detailMode={l10.detailMode}
            onZoneClick={(zoneId: string) => l10.setSelectedZone(zoneId)}
            visualSource={l10.data?.visual_source}
            showExperimental1m={l10.showExperimental1m}
            showCandidateMask={l10.showCandidateMask}
            experimental1mSurface={l10.activeExperimentalSurface}
            candidateMaskSurface={l10.candidateMaskSurface}
            paletteId={mapVisualLens}
            onPaletteChange={setMapVisualLens}
          />
        )}
      </div>



      {/* ── OBSERVE: Intelligence Surfaces ─────────────────────────── */}
      <AnimatePresence>
        {screenState === "observe" && l10.data && (
          <motion.div
            key="observe-ui"
            initial="hidden"
            animate="visible"
            exit="hidden"
            variants={containerVariants}
            style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
          >
            {/* Engine Pipeline Panel — left sidebar (from usePlotIntelligence) */}
            <motion.div variants={slideLeft} style={{ pointerEvents: "auto" }}>
              <EnginePipelinePanel visualLens={mapVisualLens} />
            </motion.div>



            {/* Analysis Sidebar — right (from usePlotIntelligence) */}
            <motion.div variants={slideRight} style={{ pointerEvents: "auto" }}>
              <RawDataSidebar />
            </motion.div>

            {/* V61C: Resolution Coverage / Experimental 1m Advisory HUD — top-right, below sidebar */}
            {(() => {
              // V61C: Merge ladder-evaluated percentages from the RESOLUTION_COVERAGE
              // surface provenance into the registry's ground_truth_summary. The registry
              // only knows about 3cm/10m; the actual 1m/2m/3m/5m breakdown comes from
              // the resolution ladder selector embedded in the surface provenance.
              const gts = l10.data?.ground_truth_summary;
              const resSurface = (l10.data?.surfaces ?? []).find(
                (s: any) => s.type === "RESOLUTION_COVERAGE"
              );
              const ladderPcts = resSurface?.provenance?.resolution_percentages;

              // Build a merged summary: start with registry, override percentages with ladder
              const mergedSummary = gts
                ? {
                  ...gts,
                  resolution_percentages: ladderPcts ?? gts.resolution_percentages ?? {},
                }
                : ladderPcts
                  ? {
                    resolution_percentages: ladderPcts,
                    certification_decision: {},
                    evidence_sources: [],
                  }
                  : null;

              if (!mergedSummary) return null;
              return (
                <motion.div
                  variants={slideRight}
                  style={{
                    pointerEvents: "auto",
                    position: "absolute",
                    top: 180,
                    right: 344,
                    zIndex: 40,
                  }}
                >
                  <ResolutionCoverageHUD summary={mergedSummary as any} />
                </motion.div>
              );
            })()}


            {/* Zone Detail Strip — appears above timeline when a zone is selected */}
            {l10.selectedZone && selectedZoneData && (
              <motion.div variants={slideUp} style={{ pointerEvents: "auto" }}>
                <ZoneDetailStrip
                  zone={selectedZoneData}
                  allZones={l10.data?.zones ?? []}
                  onClose={() => l10.setSelectedZone(null)}
                  onAskAgriBrain={(query) => l10.openDecideMode(query)}
                />
              </motion.div>
            )}

            {/* ── Left side Timeline Buttons ──────────────────────────────── */}
            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              <div style={{
                position: "absolute",
                bottom: "116px",
                right: "calc(50% + 440px)",
                zIndex: 35,
                width: "56px",
                height: "56px",
              }}>
                {/* Attention Animation Ring */}
                <span className="absolute inline-flex h-full w-full rounded-[10px] bg-blue-500 opacity-40 animate-ping pointer-events-none" style={{ animationDuration: '2s' }} />

                <button
                  onClick={() => l10.setIsDecideMode(true)}
                  id="agribrain-chat-toggle"
                  className="relative w-full h-full flex items-center justify-center rounded-[10px] cursor-pointer transition-all duration-150"
                  style={{
                    border: "1px solid #2563eb", /* blue-600 */
                    background: "#3b82f6", /* blue-500 (solid, opaque) */
                    color: "#ffffff",
                    boxShadow: "0 4px 12px rgba(59,130,246,0.5), 0 0 0 1px rgba(255,255,255,0.15) inset",
                  }}
                  title="AgriBrain Chat"
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "#ffffff" }}>
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    <path d="M12 7v0" />
                    <path d="M8 7v0" />
                    <path d="M16 7v0" />
                  </svg>
                </button>
              </div>
            </motion.div>

            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              <button
                onClick={() => setIsEvidenceModalOpen(true)}
                id="add-evidence-toggle"
                style={{
                  position: "absolute",
                  bottom: "52px",
                  right: "calc(50% + 440px)",
                  zIndex: 35,
                  width: "56px",
                  height: "56px",
                  borderRadius: "10px",
                  border: isEvidenceModalOpen ? "1px solid rgba(148,163,184,0.4)" : "1px solid rgba(71,85,105,0.25)",
                  background: isEvidenceModalOpen ? "rgba(148,163,184,0.1)" : "rgba(8,12,25,0.92)",
                  backdropFilter: "blur(24px)",
                  color: isEvidenceModalOpen ? "#f8fafc" : "#cbd5e1",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
                  transition: "all 0.15s ease",
                }}
                title="Add Evidence"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ color: isEvidenceModalOpen ? "#e2e8f0" : "#cbd5e1", opacity: isEvidenceModalOpen ? 1 : 0.9 }}>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="12" y1="18" x2="12" y2="12" />
                  <line x1="9" y1="15" x2="15" y2="15" />
                </svg>
              </button>
            </motion.div>

            {/* ── Crop Detection Button (FAB) — above Chat ─────────────── */}
            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              <div style={{
                position: "absolute",
                bottom: "180px",
                right: "calc(50% + 440px)",
                zIndex: 35,
              }}>
                <CropIdentityBanner
                  plotId={plotId}
                  farmId={farmId}
                  currentCropCode={cropName}
                  currentCropName={cropName}
                />
              </div>
            </motion.div>

            {/* ── Timeline Strip — bottom bar (from usePlotIntelligence) ── */}
            <motion.div variants={slideUp} style={{ pointerEvents: "auto" }}>
              <TimelineStrip />
            </motion.div>

            {/* ── Sensors Button ──────────────────────────────────────────── */}
            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              <button
                onClick={() => setShowSensorsPanel(!showSensorsPanel)}
                id="sensors-panel-toggle"
                style={{
                  position: "absolute",
                  bottom: "116px",
                  left: "calc(50% + 440px)",
                  zIndex: 35,
                  width: "56px",
                  height: "56px",
                  borderRadius: "10px",
                  border: showSensorsPanel ? "1px solid rgba(34,197,94,0.4)" : "1px solid rgba(71,85,105,0.25)",
                  background: showSensorsPanel ? "rgba(34,197,94,0.1)" : "rgba(8,12,25,0.92)",
                  backdropFilter: "blur(24px)",
                  color: showSensorsPanel ? "#22c55e" : "#cbd5e1",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
                  transition: "all 0.15s ease",
                }}
                title="Sensor Network"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ color: showSensorsPanel ? "#22c55e" : "#22c55e", opacity: showSensorsPanel ? 1 : 0.9 }}>
                  {/* Ground line */}
                  <path d="M3 16h18" />
                  {/* Soil Sensor body */}
                  <rect x="10" y="6" width="4" height="7" rx="1" />
                  {/* Probe into ground */}
                  <path d="M12 13v8" />
                  <path d="M11 15h2" />
                  <path d="M11 18h2" />
                  {/* Radio waves transmitting up */}
                  <path d="M8 5a6 6 0 0 1 8 0" />
                  <path d="M5 2a10 10 0 0 1 14 0" />
                </svg>
              </button>
            </motion.div>

            {/* ── MESIA Ambient Radio Observatory Button ────────────── */}
            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              <button
                onClick={() => setShowMesiaPanel(!showMesiaPanel)}
                id="mesia-observatory-toggle"
                style={{
                  position: "absolute",
                  bottom: "180px",
                  left: "calc(50% + 440px)",
                  zIndex: 35,
                  width: "56px",
                  height: "56px",
                  borderRadius: "10px",
                  border: showMesiaPanel ? "1px solid rgba(56,189,248,0.6)" : "1px solid rgba(71,85,105,0.25)",
                  background: showMesiaPanel ? "rgba(56,189,248,0.15)" : "rgba(8,12,25,0.92)",
                  backdropFilter: "blur(24px)",
                  color: showMesiaPanel ? "#38bdf8" : "#cbd5e1",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
                  transition: "all 0.15s ease",
                }}
                title="MESIA Radio Spectrum Observatory (Signals of Opportunity)"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 11a9 9 0 0 1 9 9" />
                  <path d="M4 4a16 16 0 0 1 16 16" />
                  <circle cx="5" cy="19" r="1" />
                </svg>
              </button>
            </motion.div>

            {/* ── Drone Mission Button + Panel ──────────────────────── */}
            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              <button
                onClick={() => setShowDronePanel(!showDronePanel)}
                id="drone-mission-toggle"
                style={{
                  position: "absolute",
                  bottom: "52px",
                  left: "calc(50% + 440px)",
                  zIndex: 35,
                  width: "56px",
                  height: "56px",
                  borderRadius: "10px",
                  border: showDronePanel ? "1px solid rgba(249,115,22,0.4)" : "1px solid rgba(71,85,105,0.25)",
                  background: showDronePanel ? "rgba(249,115,22,0.1)" : "rgba(8,12,25,0.92)",
                  backdropFilter: "blur(24px)",
                  color: showDronePanel ? "#f97316" : "#cbd5e1",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
                  transition: "all 0.15s ease",
                }}
                title="Drone Mission Control"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ color: showDronePanel ? "#f97316" : "#f97316", opacity: showDronePanel ? 1 : 0.9 }}>
                  <line x1="5.4" y1="5.4" x2="10" y2="10" />
                  <line x1="18.6" y1="5.4" x2="14" y2="10" />
                  <line x1="5.4" y1="18.6" x2="10" y2="14" />
                  <line x1="18.6" y1="18.6" x2="14" y2="14" />
                  <circle cx="4" cy="4" r="2" />
                  <circle cx="20" cy="4" r="2" />
                  <circle cx="4" cy="20" r="2" />
                  <circle cx="20" cy="20" r="2" />
                  <rect x="9" y="9" width="6" height="6" rx="1.5" />
                </svg>
              </button>
            </motion.div>

            {/* ── Irrigation Button ────────────────────────────────── */}
            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              <button
                onClick={() => setShowIrrigationPanel(!showIrrigationPanel)}
                id="irrigation-panel-toggle"
                style={{
                  position: "absolute",
                  bottom: "244px",
                  left: "calc(50% + 440px)",
                  zIndex: 35,
                  width: "56px",
                  height: "56px",
                  borderRadius: "10px",
                  border: showIrrigationPanel ? "1px solid rgba(6,182,212,0.4)" : "1px solid rgba(71,85,105,0.25)",
                  background: showIrrigationPanel ? "rgba(6,182,212,0.1)" : "rgba(8,12,25,0.92)",
                  backdropFilter: "blur(24px)",
                  color: showIrrigationPanel ? "#06b6d4" : "#cbd5e1",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
                  transition: "all 0.15s ease",
                }}
                title="Irrigation Control"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ color: showIrrigationPanel ? "#06b6d4" : "#06b6d4", opacity: showIrrigationPanel ? 1 : 0.9 }}>
                  <path d="M12 2v6" />
                  <path d="M12 8c-3 4-6 5.5-6 9a6 6 0 0 0 12 0c0-3.5-3-5-6-9z" />
                </svg>
              </button>
            </motion.div>

            {/* ── Refresh Visual Evidence Button ─────────────────────── */}
            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              <button
                onClick={refreshSatelliteVision}
                disabled={isRefreshingVision}
                id="satellite-vision-refresh"
                style={{
                  position: "absolute",
                  bottom: "308px",
                  left: "calc(50% + 440px)",
                  zIndex: 35,
                  width: "56px",
                  height: "56px",
                  borderRadius: "10px",
                  border: isRefreshingVision ? "1px solid rgba(168,85,247,0.4)" : "1px solid rgba(71,85,105,0.25)",
                  background: isRefreshingVision ? "rgba(168,85,247,0.1)" : "rgba(8,12,25,0.92)",
                  backdropFilter: "blur(24px)",
                  color: isRefreshingVision ? "#a855f7" : "#cbd5e1",
                  cursor: isRefreshingVision ? "wait" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
                  transition: "all 0.15s ease",
                  opacity: isRefreshingVision ? 0.7 : 1,
                }}
                title="Refresh Visual Evidence — Runs satellite image analysis in the background"
              >
                {isRefreshingVision ? (
                  <div className="w-5 h-5 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin" />
                ) : (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ color: "#a855f7", opacity: 0.9 }}>
                    <circle cx="12" cy="12" r="10" />
                    <circle cx="12" cy="12" r="4" />
                    <path d="M12 2v4" />
                    <path d="M12 18v4" />
                    <path d="M2 12h4" />
                    <path d="M18 12h4" />
                  </svg>
                )}
              </button>
              {visionRefreshStatus && (
                <div style={{
                  position: "absolute",
                  bottom: "320px",
                  left: "calc(50% + 360px)",
                  zIndex: 40,
                  background: "rgba(8,12,25,0.95)",
                  backdropFilter: "blur(16px)",
                  border: "1px solid rgba(168,85,247,0.3)",
                  borderRadius: "8px",
                  padding: "6px 12px",
                  color: visionRefreshStatus.startsWith("✓") ? "#a3e635" : "#c4b5fd",
                  fontSize: "0.75rem",
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                  boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
                }}>
                  {visionRefreshStatus}
                </div>
              )}
            </motion.div>

            <motion.div variants={popIn} style={{ pointerEvents: "auto" }}>
              {showDronePanel && (() => {
                // Extract polygon geometry from plot.geoJson (stored as GeoJSON Feature)
                let dronePolygon: any = undefined;
                if (plot?.geoJson) {
                  try {
                    const parsed = typeof plot.geoJson === "string"
                      ? JSON.parse(plot.geoJson as string)
                      : plot.geoJson;
                    // Could be a Feature or a raw Geometry
                    if (parsed?.geometry?.coordinates) {
                      dronePolygon = parsed.geometry;
                    } else if (parsed?.coordinates) {
                      dronePolygon = parsed;
                    }
                  } catch { /* parse error — leave undefined */ }
                }
                return (
                  <DroneMissionPanel
                    plotId={String(plot?.id || "")}
                    polygonGeoJson={dronePolygon}
                    onClose={() => setShowDronePanel(false)}
                  />
                );
              })()}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Loading / Error state ─────────────────────────────────── */}
      <AnimatePresence>
        {mounted && showAsmaeWorkerProgress && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="absolute left-0 right-0 top-[270px] z-50 flex justify-center px-4 pointer-events-none"
          >
            <div className="pointer-events-auto w-full max-w-lg px-4 flex justify-center">
              <PlotLoadingSequence
                key={plot?.id ? String(plot.id) : "plot-missing"}
                plotId={plot?.id ? String(plot.id) : undefined}
                compact={Boolean(l10.data)}
                hasCanonicalFallback={Boolean(l10.data?.surfaces?.length)}
                initialWorkerState={asmaeWorkerState}
                loading={l10.loading}
                onRetry={handleAsmaeWorkerRetry}
                requestError={l10.error}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── SENSORS: SensorNetworkWorkspace ──────────────────────────── */}
      {showSensorsPanel && (
        <SensorNetworkWorkspace
          plotId={String(plot?.id || "")}
          onClose={() => setShowSensorsPanel(false)}
        />
      )}

      {/* ── MESIA: MesiaObservatoryWorkspace ──────────────────────────── */}
      {showMesiaPanel && (
        <MesiaObservatoryWorkspace
          plotId={String(plot?.id || "")}
          onClose={() => setShowMesiaPanel(false)}
        />
      )}

      {/* ── IRRIGATION: IrrigationDashboard Workspace ──────────────── */}
      {showIrrigationPanel && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 60,
          background: "rgba(2,6,23,0.95)",
          backdropFilter: "blur(20px)",
          overflowY: "auto",
        }}>
          <div style={{
            position: "sticky", top: 0, zIndex: 10,
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "12px 24px",
            background: "rgba(2,6,23,0.9)",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: "#94A3B8" }}>Irrigation Control Center</span>
            <button
              onClick={() => setShowIrrigationPanel(false)}
              style={{
                padding: "6px 16px", borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.1)",
                background: "rgba(255,255,255,0.04)",
                color: "#94A3B8", fontSize: 13, cursor: "pointer",
              }}
            >
              ✕ Close
            </button>
          </div>
          <IrrigationDashboard />
        </div>
      )}

      <MethodologyDrawer
        metricKey={methodologyMetric}
        data={l10.data}
        onClose={() => setMethodologyMetric(null)}
      />

      {isEvidenceModalOpen && l10.data && (
        <AddEvidenceModal
          plotId={l10.data.plot_id}
          onClose={() => setIsEvidenceModalOpen(false)}
          onSuccess={() => {
            setIsEvidenceModalOpen(false);
            if (l10.fetchLayer10) {
              l10.fetchLayer10(l10.data!.plot_id, "", undefined, undefined, undefined);
            }
          }}
        />
      )}
    </div>
  );
}
