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
import { useLayer10, MODE_CONFIG } from "@/hooks/useLayer10";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import FieldInsightBar from "@/components/farm/intelligence/FieldInsightBar";
import FieldSnapshotHUD from "@/components/farm/intelligence/FieldSnapshotHUD";
import HistogramDrawer from "@/components/farm/intelligence/HistogramDrawer";
import ZoneDetailStrip from "@/components/farm/intelligence/ZoneDetailStrip";
import MethodologyDrawer from "@/components/farm/intelligence/MethodologyDrawer";
import AgriBrainWorkspace from "@/components/farm/intelligence/AgriBrainWorkspace";
import EnginePipelinePanel from "@/components/farm/intelligence/EnginePipelinePanel";
import TimelineStrip from "@/components/farm/intelligence/TimelineStrip";
import RawDataSidebar from "@/components/farm/intelligence/RawDataSidebar";

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
}

export default function PlotDashboard({ farm, plot, cropName, context }: PlotDashboardProps) {
  const [mounted, setMounted] = useState(false);
  const [methodologyMetric, setMethodologyMetric] = useState<string | null>(null);

  // ── PRIMARY: useLayer10 for map surfaces (proven, working) ──────────────
  const l10 = useLayer10();
  
  // ── SECONDARY: usePlotIntelligence for engines, timeline, raw data ──────
  const pi = usePlotIntelligence();

  useEffect(() => { setMounted(true); }, []);

  // Fetch L10 data (map surfaces) on mount — this is the working pipeline
  useEffect(() => {
    if (plot?.id && farm?.id) {
      l10.fetchLayer10(String(plot.id), String(farm.id), undefined, undefined, cropName);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plot?.id, farm?.id, cropName]);

  // Fetch intelligence data (engines, timeline) — independent of L10 surfaces
  useEffect(() => {
    if (plot?.id && farm?.id) {
      pi.fetchIntelligence(String(plot.id), String(farm.id));

      // Fire-and-forget: trigger full satellite vision pipeline (tile → vision → save)
      // This ensures the LLM vision cache is populated for the orchestrator
      const lat = typeof plot.lat === "number" ? plot.lat : parseFloat(String(plot.lat || "0"));
      const lng = typeof plot.lng === "number" ? plot.lng : parseFloat(String(plot.lng || "0"));
      if (lat && lng) {
        const plotIdStr = String(plot.id);
        (async () => {
          try {
            // Step 1: Fetch the tile (cached for 7 days server-side)
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
            if (tileData.status !== "fetched" && tileData.status !== "cached") return;

            // Step 2: Run LLM vision analysis
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

            // Step 3: Save tile + LLM observation to DB
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
          } catch { /* Entire pipeline is best-effort */ }
        })();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plot?.id, farm?.id]);

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

  return (
    <div className="aw-dashboard" id="plot-dashboard" style={{ direction: "ltr" }}>

      {/* ── Map Canvas ──────────────────────────────────────────────── */}
      <div
        className="aw-dashboard__map"
        style={{
          visibility: isMapVisible ? "visible" : "hidden",
          height: isMapVisible ? undefined : 0,
          overflow: isMapVisible ? undefined : "hidden",
          position: isMapVisible ? undefined : "absolute",
        }}
      >
        {farm && (
          <PlotMapShell
            farms={farm ? [farm] : []}
            plots={plot ? [plot] : []}
            activeMode={l10.activeMode}
            cropName={cropName}
            surfaceData={l10.spatialSurfaceAvailable ? l10.activeSurface : null}
            surfaceColors={l10.activeColors}
            confidenceSurface={l10.spatialSurfaceAvailable ? l10.activeConfidenceSurface : null}
            reliabilitySurface={l10.spatialSurfaceAvailable ? l10.activeReliabilitySurface : null}
            deviationSurface={
              (l10.activeMode === "veg_attention" && l10.spatialSurfaceAvailable)
                ? (l10.data?.surfaces.find(s => s.type === "NDVI_DEVIATION") ?? null)
                : null
            }
            gridHeight={l10.data?.grid.height}
            gridWidth={l10.data?.grid.width}
            l10Zones={l10.localizedZoneAvailable ? l10.data?.zones : null}
            selectedZone={l10.selectedZone}
            detailMode={l10.detailMode}
            onZoneClick={(zoneId: string) => l10.setSelectedZone(zoneId)}
          />
        )}
      </div>

      {/* ── OBSERVE: Intelligence Surfaces ─────────────────────────── */}
      {screenState === "observe" && (
        <>
          {/* Engine Pipeline Panel — left sidebar (from usePlotIntelligence) */}
          <EnginePipelinePanel />

          {/* Field Snapshot HUD — offset from engine panel */}
          {l10.data && (
            <div style={{
              position: "absolute", top: "104px",
              left: pi.showEnginePanel ? "304px" : "60px",
              zIndex: 15, transition: "all 0.25s ease",
            }}>
              <FieldSnapshotHUD
                data={l10.data}
                activeMode={l10.activeMode}
                activeSurfaceType={l10.activeSurfaceType}
              />
            </div>
          )}

          {/* Analysis Sidebar — right (from usePlotIntelligence) */}
          <RawDataSidebar />


          {/* Zone Detail Strip — appears above timeline when a zone is selected */}
          {l10.selectedZone && selectedZoneData && (
            <ZoneDetailStrip
              zone={selectedZoneData}
              allZones={l10.data?.zones ?? []}
              onClose={() => l10.setSelectedZone(null)}
              onAskAgriBrain={(query) => l10.openDecideMode(query)}
            />
          )}

          {/* Timeline Strip — bottom bar (from usePlotIntelligence) */}
          <TimelineStrip />
        </>
      )}

      {/* ── Loading / Error state ─────────────────────────────────── */}
      {mounted && !l10.data && (
        <div className="aw-dashboard__status">
          {l10.error ? (
            <div className="aw-dashboard__error">
              <span className="aw-dashboard__error-icon">⚠</span>
              <span>{l10.error}</span>
            </div>
          ) : (
            <div className="aw-dashboard__loading">
              <div className="aw-dashboard__loading-dot" />
              <span>{l10.loading ? "Analyzing your field…" : "Connecting…"}</span>
            </div>
          )}
        </div>
      )}

      {/* ── FieldInsightBar ─────────────────────────── */}
      {screenState === "observe" && l10.data && (
        <div style={{
          position: "absolute", top: "106px", left: "50%", transform: "translateX(-50%)",
          zIndex: 15, width: "100%", display: "flex", justifyContent: "center", pointerEvents: "none"
        }}>
          <FieldInsightBar
            data={l10.data}
            activeMode={l10.activeMode}
            loading={l10.loading}
            onInspect={(zoneId) => l10.setSelectedZone(zoneId)}
          />
        </div>
      )}

      {/* Zone detail is now inline above the timeline — no separate diagnose screen */}

      {/* ── DECIDE: AgriBrainWorkspace ─────────────────────────────── */}
      <AgriBrainWorkspace
        isOpen={l10.isDecideMode}
        onClose={() => l10.setIsDecideMode(false)}
        context={context}
        activeMode={l10.activeMode}
        data={l10.data}
        plotName={plot?.name ? String(plot.name) : undefined}
        initialQuery={l10.decideModeQuery}
      />

      <MethodologyDrawer
        metricKey={methodologyMetric}
        data={l10.data}
        onClose={() => setMethodologyMetric(null)}
      />
    </div>
  );
}
