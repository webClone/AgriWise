"use client";

import type { SurfaceData } from "@/hooks/useLayer10";
import "./plot-scientific-legend.css";

type SceneEvidence = {
  provider?: string | null;
  scene_date?: string | null;
  native_resolution_m?: number | null;
  is_mock?: boolean | null;
  status?: string | null;
};
interface PlotScientificLegendProps {
  layerName: string;
  surface: SurfaceData | null | undefined;
  scene: SceneEvidence | null | undefined;
  degraded?: boolean;
  canInterpret?: boolean;
}

const show = (value: unknown): string =>
  typeof value === "string" && value.trim() ? value.trim() : "Not reported";

export default function PlotScientificLegend({
  layerName, surface, scene, degraded = false, canInterpret = false,
}: PlotScientificLegendProps) {
  const provenance = (surface?.provenance || {}) as Record<string, unknown>;
  const source = show(provenance.provider || provenance.source || scene?.provider);
  const observationDate = show(
    provenance.observation_date || provenance.acquired_at || provenance.scene_date || scene?.scene_date,
  );
  const units = show((surface as unknown as Record<string, unknown> | null)?.units || provenance.units);
  const nativeResolution = provenance.native_resolution_m ?? scene?.native_resolution_m;
  const resolution = typeof nativeResolution === "number" && Number.isFinite(nativeResolution) && nativeResolution > 0
    ? `${nativeResolution} m (source)`
    : "Not reported";
  const evidenceClass = show(
    provenance.evidence_class || provenance.support_class || (surface as unknown as Record<string, unknown> | null)?.source_reality,
  );
  const state = scene?.is_mock ? "Simulated visual context"
    : !surface ? "No scientific surface"
    : degraded ? "Degraded evidence"
    : canInterpret ? "Qualified interpretation available"
    : "Diagnostic / contextual only";

  return <aside className="akaloris-scientific-legend" aria-label="Scientific map evidence">
    <div className="akaloris-scientific-legend-head"><span>MAP EVIDENCE</span><strong>{layerName}</strong></div>
    <dl>
      <div><dt>01 / Source and date</dt><dd>{source} · {observationDate}</dd></div>
      <div><dt>02 / Units and resolution</dt><dd>{units} · {resolution}</dd></div>
      <div><dt>03 / Provenance / support</dt><dd>{evidenceClass}</dd></div>
      <div><dt>04 / Interpretation status</dt><dd>{state}</dd></div>
    </dl>
    <p>Boundary: user-registered geometry; not a surveyed cadastral outline.</p>
  </aside>;
}
