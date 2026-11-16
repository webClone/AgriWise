"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
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
  workspaceMode?: boolean;
}

const show = (value: unknown): string =>
  typeof value === "string" && value.trim() ? value.trim() : "Not reported";

export default function PlotScientificLegend({
  layerName, surface, scene, degraded = false, canInterpret = false, workspaceMode = false,
}: PlotScientificLegendProps) {
  const [expanded, setExpanded] = useState(false);

  // Scientific metadata MUST originate from the published scientific surface.
  // A visual basemap has separate acquisition and provenance authority.
  const provenance = (surface?.provenance || {}) as Record<string, unknown>;
  const source = show(provenance.provider || provenance.source);
  const observationDate = show(
    provenance.observation_date || provenance.acquired_at || provenance.scene_date,
  );
  const units = show(surface?.units || provenance.units);
  const nativeResolution = provenance.native_resolution_m;
  const resolution = typeof nativeResolution === "number"
    && Number.isFinite(nativeResolution) && nativeResolution > 0
    ? `${nativeResolution} m (source)` : "Not reported";
  const evidenceClass = show(
    provenance.evidence_class || provenance.support_class || surface?.source_reality,
  );
  const state = !surface ? "No scientific surface"
    : degraded ? "Degraded evidence"
    : canInterpret ? "Qualified interpretation available"
    : "Diagnostic / contextual only";

  const basemapProvider = show(scene?.provider);
  const basemapDate = show(scene?.scene_date);
  const basemapLabel = scene?.is_mock ? "Simulated visual basemap" : "Visual basemap";

  // P07.02 / P07-G08: Strict legacy fallback. Non-V2 dashboard keeps the exact static aside.
  if (!workspaceMode) {
    return (
      <aside className="akaloris-scientific-legend akaloris-scientific-legend-legacy" aria-label="Scientific map evidence">
        <div className="akaloris-scientific-legend-head"><span>MAP EVIDENCE</span><strong>{layerName}</strong></div>
        <dl>
          <div><dt>01 / Scientific source and date</dt><dd>{source} · {observationDate}</dd></div>
          <div><dt>02 / Units and source resolution</dt><dd>{units} · {resolution}</dd></div>
          <div><dt>03 / Provenance / support</dt><dd>{evidenceClass}</dd></div>
          <div><dt>04 / Interpretation status</dt><dd>{state}</dd></div>
        </dl>
        <p>Boundary: user-registered geometry; not a surveyed cadastral outline.</p>
        <p>{basemapLabel}: {basemapProvider} · {basemapDate}. Not scientific evidence.</p>
      </aside>
    );
  }

  return (
    <aside
      className={`akaloris-scientific-legend akaloris-scientific-legend-v2 ${expanded ? "is-expanded" : "is-collapsed"}`}
      aria-label="Scientific map evidence"
    >
      <button
        type="button"
        className="akaloris-legend-toggle"
        data-testid="p07-map-evidence-toggle"
        aria-expanded={expanded}
        aria-controls="akaloris-legend-detail"
        onClick={() => setExpanded(prev => !prev)}
      >
        <span className="akaloris-legend-head-tag">MAP EVIDENCE</span>
        <strong className="akaloris-legend-head-layer">{layerName}</strong>
        <span className="akaloris-legend-head-state">{state}</span>
        {expanded ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
      </button>

      {expanded && (
        <div id="akaloris-legend-detail" className="akaloris-legend-detail">
          <dl>
            <div><dt>01 / Scientific source and date</dt><dd>{source} · {observationDate}</dd></div>
            <div><dt>02 / Units and source resolution</dt><dd>{units} · {resolution}</dd></div>
            <div><dt>03 / Provenance / support</dt><dd>{evidenceClass}</dd></div>
            <div><dt>04 / Interpretation status</dt><dd>{state}</dd></div>
          </dl>
          <p>Boundary: user-registered geometry; not a surveyed cadastral outline.</p>
          <p>{basemapLabel}: {basemapProvider} · {basemapDate}. Not scientific evidence.</p>
        </div>
      )}
    </aside>
  );
}
