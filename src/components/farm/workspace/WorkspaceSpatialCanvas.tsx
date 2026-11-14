"use client";

import dynamic from "next/dynamic";
import type { useLayer10 } from "@/hooks/useLayer10";
import type { MapVisualLens } from "./useWorkspaceScientificAdapter";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";

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

interface WorkspaceSpatialCanvasProps {
  farm?: Record<string, unknown> | null;
  plot?: Record<string, unknown> | null;
  cropName?: string;
  l10: ReturnType<typeof useLayer10>;
  mapVisualLens: MapVisualLens;
  onPaletteChange: (lens: MapVisualLens) => void;
  onZoneClick: (zoneId: string) => void;
  workspaceEntities?: WorkspaceFeatureEnvelope[];
  selectedEntityId?: string | null;
  onEntityClick?: (entity: WorkspaceFeatureEnvelope) => void;
}

/**
 * P04 Native Spatial Canvas:
 * Owns the field viewport, DeckGL/MapLibre layers, raster surfaces,
 * contour polygons, and spatial entity selection directly.
 */
export default function WorkspaceSpatialCanvas({
  farm,
  plot,
  cropName,
  l10,
  mapVisualLens,
  onPaletteChange,
  onZoneClick,
  workspaceEntities,
  selectedEntityId,
  onEntityClick,
}: WorkspaceSpatialCanvasProps) {
  const deviationSurface =
    l10.activeMode === "veg_attention"
      ? (l10.data?.surfaces.find((s) => s.type === "NDVI_DEVIATION") ?? null)
      : null;

  return (
    <div className="pw-spatial-canvas" data-testid="pw-spatial-canvas" style={{ position: "absolute", inset: 0 }}>
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
          deviationSurface={deviationSurface}
          gridHeight={l10.data?.grid.height}
          gridWidth={l10.data?.grid.width}
          l10Zones={l10.data?.zones ?? null}
          selectedZone={l10.selectedZone}
          detailMode={l10.detailMode}
          onZoneClick={onZoneClick}
          visualSource={l10.data?.visual_source}
          showExperimental1m={l10.showExperimental1m}
          showCandidateMask={l10.showCandidateMask}
          experimental1mSurface={l10.activeExperimentalSurface}
          candidateMaskSurface={l10.candidateMaskSurface}
          paletteId={mapVisualLens}
          onPaletteChange={onPaletteChange}
          workspaceEntities={workspaceEntities}
          selectedEntityId={selectedEntityId}
          onEntityClick={onEntityClick}
        />
      )}
    </div>
  );
}
