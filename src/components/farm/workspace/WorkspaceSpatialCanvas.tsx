"use client";

import dynamic from "next/dynamic";
import type { useLayer10 } from "@/hooks/useLayer10";
import type { MapVisualLens } from "./useWorkspaceScientificAdapter";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";
import type { WorkspaceDraftGeometryProps } from "@/components/farm/map/layers/WorkspaceEntityGeometryLayer";
import type { AsmaeStateAvailabilityResult } from "@/lib/agribrain/asmae-13-states";

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
  sceneVisibility?: Record<string,boolean>;
  sceneOpacity?: Record<string,number>;
  sceneGeneration?: number;
  selectedEntityId?: string | null;
  onEntityClick?: (entity: WorkspaceFeatureEnvelope) => void;
  draftGeometry?: WorkspaceDraftGeometryProps | null;
  onCanvasMapClick?: (coordinate: [number, number]) => void;
  workspaceMode?: boolean;
  onAnalysisStateChange?: (state: {
    canTransect: boolean;
    transectActive: boolean;
    transectPointsCount: number;
    toggleTransect: () => void;
  }) => void;
  activeAsmaeAvailability?: AsmaeStateAvailabilityResult;
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
  sceneVisibility,
  sceneOpacity,
  sceneGeneration,
  selectedEntityId,
  onEntityClick,
  draftGeometry,
  onCanvasMapClick,
  workspaceMode,
  onAnalysisStateChange,
  activeAsmaeAvailability,
}: WorkspaceSpatialCanvasProps) {
  const deviationSurface =
    l10.activeMode === "veg_attention"
      ? (l10.data?.surfaces.find((s) => s.type === "NDVI_DEVIATION") ?? null)
      : null;

  const isScalarOrUnavailable =
    activeAsmaeAvailability && !activeAsmaeAvailability.canRenderPixels;

  const effectiveSurface = isScalarOrUnavailable
    ? null
    : (activeAsmaeAvailability?.rasterSurface as any) || l10.activeSurface;

  return (
    <div className="pw-spatial-canvas" data-testid="pw-spatial-canvas" style={{ position: "absolute", inset: 0 }}>
      {farm && (
        <PlotMapShell
          farms={farm ? [farm] : []}
          plots={plot ? [plot] : []}
          activeMode={l10.activeMode}
          cropName={cropName}
          surfaceData={effectiveSurface}
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
          sceneVisibility={sceneVisibility}
          sceneOpacity={sceneOpacity}
          sceneGeneration={sceneGeneration}
          selectedEntityId={selectedEntityId}
          onEntityClick={onEntityClick}
          draftGeometry={draftGeometry}
          onCanvasMapClick={onCanvasMapClick}
          workspaceMode={workspaceMode}
          onAnalysisStateChange={onAnalysisStateChange}
        />
      )}

      {/* Truthfulness Gate HUD: Appears when a state has scalar values but no certified spatial raster */}
      {isScalarOrUnavailable && activeAsmaeAvailability && (
        <div
          className="pw-truthfulness-hud"
          data-testid="pw-truthfulness-hud"
          style={{
            position: "absolute",
            bottom: "80px",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 35,
            background: "rgba(15, 23, 42, 0.88)",
            backdropFilter: "blur(8px)",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            borderRadius: "8px",
            padding: "8px 16px",
            color: "#f8fafc",
            fontSize: "12px",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5)",
            pointerEvents: "none",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span style={{ color: "#38bdf8", fontWeight: 800 }}>[TRUTHFULNESS GATE]</span>
          <span>
            ASMAE State <strong>{activeAsmaeAvailability.state.name}</strong> is a scalar-only estimate
            {activeAsmaeAvailability.mean !== null ? ` (${activeAsmaeAvailability.mean} ± ${activeAsmaeAvailability.sigma} ${activeAsmaeAvailability.state.unit})` : ""}.
            Full-field spatial raster withheld.
          </span>
        </div>
      )}
    </div>
  );
}
