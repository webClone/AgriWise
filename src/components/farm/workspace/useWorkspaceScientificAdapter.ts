"use client";

import { useEffect, useState } from "react";
import { computeGeometryHash, useParcelAssessment } from "@/hooks/useParcelAssessment";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";

export type MapVisualLens = "standard" | "thermal" | "chlorophyll" | "chroma";

interface ScientificAdapterProps {
  farm?: Record<string, unknown> | null;
  plot?: Record<string, unknown> | null;
  cropName?: string;
}

/**
 * P04 Native Scientific Adapter:
 * Directly owns parcel assessment fetching, geometry change detection,
 * Layer 10 presentation binding, and visual lens management without
 * relying on the legacy PlotDashboard.
 */
export function useWorkspaceScientificAdapter({ farm, plot }: ScientificAdapterProps) {
  const [mapVisualLens, setMapVisualLens] = useState<MapVisualLens>("standard");

  // 1. Authoritative publication owner
  const parcelAssessment = useParcelAssessment();

  // 2. Presentation view adapters
  const l10 = useLayer10();
  const pi = usePlotIntelligence();

  // 3. Rebind after a geometry or active crop-cycle edit on the same plot
  const geometrySignature = plot?.geoJson ? computeGeometryHash(plot.geoJson) : "";
  const activeCropCycleId = parcelAssessment.activeCropCycleId;
  const fetchAssessment = parcelAssessment.fetchAssessment;

  useEffect(() => {
    if (!plot?.id || !farm?.id) return;
    void fetchAssessment(String(plot.id), String(farm.id), {
      geometry: plot.geoJson,
      cropCycleId: activeCropCycleId,
    });
  }, [plot?.id, farm?.id, geometrySignature, activeCropCycleId, fetchAssessment]);

  // 4. Derive presentation state strictly from canonical assessment
  const injectData = pi.injectData;
  useEffect(() => {
    if (l10.data) {
      injectData(l10.data, (plot as any)?.id, l10.isApplicable);
    }
  }, [l10.data, l10.isApplicable, injectData, (plot as any)?.id]);

  return {
    parcelAssessment,
    l10,
    pi,
    mapVisualLens,
    setMapVisualLens,
  };
}
