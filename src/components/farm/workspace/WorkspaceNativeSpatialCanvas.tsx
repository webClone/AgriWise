"use client";

/**
 * P04-C03 native spatial host: the map is a first-class member of the new
 * workspace. We reuse PlotMapShell's established scientific pixel and polygon
 * authority; the legacy PlotDashboard is NOT mounted anywhere in the V2 tree.
 * No second Layer10 or ParcelAssessment provider is constructed here.
 */
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { computeGeometryHash, useParcelAssessment } from "@/hooks/useParcelAssessment";
import { useLayer10 } from "@/hooks/useLayer10";
import type { PlotWorkspaceProps } from "./PlotWorkspaceFeatureGate";

const PlotMapShell = dynamic(() => import("@/components/farm/map/PlotMapShell"), {
  ssr: false,
  loading: () => <div role="status" className="pw-native-map-loading">Loading field map…</div>,
});

export default function WorkspaceNativeSpatialCanvas(props: PlotWorkspaceProps) {
  const parcelAssessment = useParcelAssessment();
  const l10 = useLayer10();
  const [visualLens, setVisualLens] = useState<"standard" | "thermal" | "chlorophyll" | "chroma">("standard");

  const plotId = props.verifiedScope?.plotId || props.plotId || String(props.plot?.id || "");
  const farmId = props.verifiedScope?.farmId || props.farmId || String(props.farm?.id || "");
  const geometry = props.plot?.geoJson ?? null;
  const geometrySignature = geometry ? computeGeometryHash(geometry) : "";
  const cycleId = props.verifiedScope?.cropCycleId ?? parcelAssessment.activeCropCycleId;

  // This was previously triggered by PlotDashboard. The canonical
  // ParcelAssessmentProvider still owns requests, aborts and publication checks.
  // Layer10Provider projects the same assessment; do not independently fetch L10.
  useEffect(() => {
    if (!plotId || !farmId || !props.plot) return;
    void parcelAssessment.fetchAssessment(plotId, farmId, {
      geometry,
      cropCycleId: cycleId,
    });
  }, [plotId, farmId, geometrySignature, cycleId, parcelAssessment.fetchAssessment]);

  if (!props.farm || !props.plot || !plotId || !farmId) {
    return <div className="pw-native-map-host" role="status">An authorized field is required to display the spatial canvas.</div>;
  }

  return (
    <div className="pw-native-map-host" data-testid="p04-native-spatial-canvas" data-plot-id={plotId}>
      <PlotMapShell
        farms={[props.farm]}
        plots={[props.plot]}
        activeMode={l10.activeMode}
        cropName={props.cropName}
        surfaceData={l10.activeSurface}
        surfaceColors={l10.activeColors}
        confidenceSurface={l10.activeConfidenceSurface}
        reliabilitySurface={l10.activeReliabilitySurface}
        deviationSurface={l10.activeMode === "veg_attention"
          ? (l10.data?.surfaces.find(s => s.type === "NDVI_DEVIATION") ?? null) : null}
        gridHeight={l10.data?.grid.height}
        gridWidth={l10.data?.grid.width}
        l10Zones={l10.data?.zones ?? null}
        selectedZone={l10.selectedZone}
        detailMode={l10.detailMode}
        onZoneClick={l10.setSelectedZone}
        visualSource={l10.data?.visual_source}
        showExperimental1m={l10.showExperimental1m}
        showCandidateMask={l10.showCandidateMask}
        experimental1mSurface={l10.activeExperimentalSurface}
        candidateMaskSurface={l10.candidateMaskSurface}
        paletteId={visualLens}
        onPaletteChange={setVisualLens}
      />
    </div>
  );
}
