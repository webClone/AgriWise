"use client";

/**
 * PlotDashboard V3 — Restored Intelligence Surfaces
 *
 * Three screen states:
 *   observe  → cinematic map + HUD + Legend + FieldInsightBar + Histogram toggle
 *   diagnose → focused map + ZoneSheet
 *   decide   → AgriBrainWorkspace fullscreen
 *
 * Fix: map container uses visibility/overflow instead of display:none
 * to prevent canvas resize regression.
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import { useLayer10, MODE_CONFIG } from "@/hooks/useLayer10";
import FieldInsightBar from "@/components/farm/intelligence/FieldInsightBar";
import FieldSnapshotHUD from "@/components/farm/intelligence/FieldSnapshotHUD";
import SurfaceLegendBar from "@/components/farm/map/SurfaceLegendBar";
import HistogramDrawer from "@/components/farm/intelligence/HistogramDrawer";
import ZoneSheet from "@/components/farm/intelligence/ZoneSheet";
import MethodologyDrawer from "@/components/farm/intelligence/MethodologyDrawer";
import AgriBrainWorkspace from "@/components/farm/intelligence/AgriBrainWorkspace";

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

  const l10 = useLayer10();

  useEffect(() => { setMounted(true); }, []);

  // Fetch L10 data on mount
  useEffect(() => {
    if (plot?.id && farm?.id) {
      l10.fetchLayer10(String(plot.id), String(farm.id), undefined, undefined, cropName);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plot?.id, farm?.id, cropName]);

  // ── Derive screen state from existing app state ──────────────────────────
  const screenState = useMemo<"observe" | "diagnose" | "decide">(() => {
    if (l10.isDecideMode) return "decide";
    if (l10.selectedZone) return "diagnose";
    return "observe";
  }, [l10.isDecideMode, l10.selectedZone]);

  // Selected zone data
  const selectedZoneData = useMemo(() => {
    if (!l10.selectedZone || !l10.data) return null;
    return l10.data.zones.find((z) => z.zone_id === l10.selectedZone) ?? null;
  }, [l10.selectedZone, l10.data]);

  // Histogram toggle
  const handleHistogramToggle = useCallback(() => {
    l10.setHistogramExpanded(!l10.histogramExpanded);
  }, [l10]);

  // Surface grounding class from active surface
  const groundingClass = l10.activeSurface?.grounding_class ?? "UNIFORM";

  // Coverage ratio from surface
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
    <div className="aw-dashboard" id="plot-dashboard">

      {/* ── Map Canvas ────────────────────────────────────────────────────
           Uses visibility + overflow instead of display:none to prevent
           Mapbox/canvas resize regression when returning from Decide mode.
      */}
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

      {/* ── OBSERVE: Intelligence Surfaces ─────────────────────────────── */}
      {screenState === "observe" && l10.data && (
        <>
          {/* Field Snapshot HUD — top-left floating card */}
          <FieldSnapshotHUD data={l10.data} activeMode={l10.activeMode} activeSurfaceType={l10.activeSurfaceType} />

          {/* Surface Legend Bar — bottom-left */}
          <SurfaceLegendBar
            activeMode={l10.activeMode}
            detailMode={l10.detailMode}
            groundingClass={groundingClass}
            coverageRatio={coverageRatio}
          />

          {/* Histogram Drawer — bottom-right floating */}
          <div className="absolute bottom-24 right-4 z-10 w-72">
            <HistogramDrawer
              histogram={l10.activeHistogram}
              delta={l10.activeDelta}
              colors={l10.activeColors}
              expanded={l10.histogramExpanded}
              onToggle={handleHistogramToggle}
              surfaceLabel={modeLabel}
            />
          </div>
        </>
      )}

      {/* ModeLens moved to PlotContextBand */}

      {/* ── Loading / Error state ─────────────────────────────────────── */}
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

      {/* ── OBSERVE: FieldInsightBar (bottom edge) ────────────────────── */}
      {screenState === "observe" && l10.data && (
        <div className="aw-dashboard__insight-bar">
          <FieldInsightBar
            data={l10.data}
            activeMode={l10.activeMode}
            loading={l10.loading}
            onInspect={(zoneId) => l10.setSelectedZone(zoneId)}
          />
        </div>
      )}

      {/* ── DIAGNOSE: ZoneSheet (right panel) ─────────────────────────── */}
      {screenState === "diagnose" && (
        <div className="aw-dashboard__zone-sheet">
          <ZoneSheet
            zone={selectedZoneData}
            allZones={l10.data?.zones ?? []}
            onClose={() => l10.setSelectedZone(null)}
            onAskAgriBrain={() => l10.setIsDecideMode(true)}
          />
        </div>
      )}

      {/* AgriBrain FAB removed to reduce floating button clutter */}

      {/* ── DECIDE: AgriBrainWorkspace ─────────────────────────────────── */}
      <AgriBrainWorkspace
        isOpen={l10.isDecideMode}
        onClose={() => l10.setIsDecideMode(false)}
        context={context}
        activeMode={l10.activeMode}
        data={l10.data}
        plotName={plot?.name ? String(plot.name) : undefined}
      />

      <MethodologyDrawer
        metricKey={methodologyMetric}
        data={l10.data}
        onClose={() => setMethodologyMetric(null)}
      />
    </div>
  );
}

