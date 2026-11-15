"use client";

import { useEffect, useRef, useState } from "react";
import { X, Droplets, History, FlaskConical, ShieldAlert, Expand, Layers2 } from "lucide-react";
import { useLayer10 } from "@/hooks/useLayer10";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { usePlotWorkspace } from "./PlotWorkspaceProvider";
import { evaluateZoneInvestigationContext } from "./p04-context-runtime.mjs";
import type { P04InvestigationKind } from "./WorkspaceContextActionsP04";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";
import { buildEntityTemporalComparison } from "./p06-time-comparison.mjs";

export type P04HostMode = "context" | "split" | "workbench";

const kindTitle: Record<P04InvestigationKind, string> = {
  water: "Water stress investigation",
  compare: "Compare scientific time",
  simulate: "Irrigation what-if preparation",
};
const kindIcon = { water: Droplets, compare: History, simulate: FlaskConical };

export default function WorkspaceInvestigationHostP04({
  kind, mode, onClose, onMode, workspaceEntities = [],
}: {
  kind: P04InvestigationKind;
  mode: P04HostMode;
  workspaceEntities?: WorkspaceFeatureEnvelope[];
  onClose: () => void;
  onMode: (mode: P04HostMode) => void;
}) {
  const { state, setTimeCursor } = usePlotWorkspace();
  const layer10 = useLayer10();
  const parcel = useParcelAssessment();
  const [hypotheticalMm, setHypotheticalMm] = useState(0);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    titleRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const context = evaluateZoneInvestigationContext({
    workspace: state,
    layer10PlotId: layer10.data?.plot_id,
    layer10SelectedZoneId: layer10.selectedZone,
    layer10PublicationId: layer10.data?.publication_id,
    assessmentPublicationId: parcel.assessment?.identity?.publicationId,
    assessmentSnapshotId: parcel.assessment?.identity?.snapshotId,
    assessmentReady: parcel.status === "ready",
    assessmentApplicable: parcel.isApplicable,
  });
  const zone = context.zoneId && context.canShowZoneNumbers
    ? (layer10.data?.zones?.find(z => z.zone_id === context.zoneId) ?? null)
    : null;
  const selectedEnvelope = workspaceEntities.find(e =>
    e.entity_kind === state.selectedEntity.kind &&
    (e.entity_id === state.selectedEntity.id || e.envelope_id === state.selectedEntity.id)
  ) ?? null;
  const entityTime = buildEntityTemporalComparison({ workspace: state, entity: selectedEnvelope });
  const Icon = kindIcon[kind];
  const fmt = (value: unknown) => typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(3) : "Unavailable";

  return (
    <section className={`p04-investigation p04-mode-${mode}`}
      aria-label={kindTitle[kind]} data-testid="p04-investigation-host"
      data-investigation-kind={kind} data-host-mode={mode}>
      <header className="p04-investigation-header">
        <div className="p04-investigation-title"><Icon size={19} aria-hidden="true"/>
          <div><span>PLOT INVESTIGATION</span><h2 ref={titleRef} tabIndex={-1}>{kindTitle[kind]}</h2></div>
        </div>
        <button aria-label="Close investigation and return to map" type="button"
          onClick={onClose} className="p04-investigation-close"><X size={19}/></button>
      </header>
      <div className="p04-investigation-modes" aria-label="Workbench layout">
        {(["context", "split", "workbench"] as const).map(m => (
          <button type="button" key={m} aria-pressed={mode === m}
            onClick={() => onMode(m)}>
            {m === "context" ? <Layers2 size={14}/> : m === "split" ? <Expand size={14}/> : <FlaskConical size={14}/>}
            {m === "context" ? "Context" : m === "split" ? "Split" : "Workbench"}
          </button>
        ))}
      </div>
      <div className="p04-investigation-scroll">
        <div className="p04-investigation-scope">
          <span>ACTIVE CONTEXT</span>
          <strong>Plot {state.plotScope.plotId}</strong>
          <small>Zone: {context.zoneId ?? "No current zone"} · {state.clocks.activeTimeMode} · Generation {state.generationId}</small>
          <small>Snapshot: {state.publication.snapshotId ?? "Unavailable"}</small>
        </div>
        <p className={context.qualified ? "p04-source-qualified" : "p04-source-warning"}>
          <ShieldAlert size={16} aria-hidden="true"/> {context.explanation}
        </p>
        {kind === "water" && (
          <div className="p04-investigation-section">
            <h3>Investigate current zone</h3>
            <p>View the map's water-stress mode and review the current zone record only when its scientific publication matches this workspace.</p>
            <button className="p04-investigation-primary" type="button"
              onClick={() => layer10.setActiveMode("water_stress")}>
              <Droplets size={15}/> Show water-stress map mode
            </button>
            {zone ? (
              <div className="p04-zone-readout">
                <div><span>Reported zone severity</span><strong>{fmt(zone.severity)}</strong></div>
                <div><span>Reported confidence</span><strong>{fmt(zone.confidence)}</strong></div>
                <p>Data from the current matching Layer 10 zone. Confidence and severity are source values, not newly computed results.</p>
                {zone.top_drivers?.length > 0 && <p>Reported drivers: {zone.top_drivers.join(", ")}</p>}
              </div>
            ) : (
              <p className="p04-evidence-empty">No matching qualified water-stress zone data to display. The map remains available for exploratory inspection.</p>
            )}
          </div>
        )}
        {kind === "compare" && (
          <div className="p04-investigation-section">
            <h3>Choose a temporal basis</h3>
            <div className="p04-temporal-readout">
              <div><span>Scientific cutoff</span><strong>{state.clocks.scientificAsOf ?? "Not available"}</strong></div>
              <div><span>Scientific authority</span><strong>{state.publication.authorityStatus}{state.publication.isStale ? " · stale" : ""}</strong></div>
              <div><span>Operational clock</span><strong>{state.clocks.operationalObserved ?? "Not available"}</strong></div>
              <div><span>Selected UI cursor</span><strong>{state.clocks.cursorTimestamp ?? "Not selected"}</strong></div>
            </div>
            {state.selectedEntity.kind !== null && state.selectedEntity.kind !== "ZONE" && (
              <div className="p06-temporal-entity" data-testid="p06-entity-time-context" data-context-status={entityTime.status}>
                <h4>Selected entity · temporal evidence</h4>
                {entityTime.status === "matched" ? (
                  <>
                    <div className="p04-temporal-readout">
                      <div><span>Entity</span><strong>{entityTime.entityKind} · {entityTime.entityId}</strong></div>
                      <div><span>Epistemic class</span><strong>{entityTime.epistemicClass}</strong></div>
                      <div><span>Observed at</span><strong>{entityTime.observedAt ?? "Not registered"}</strong></div>
                      <div><span>First available at</span><strong>{entityTime.firstAvailableAt ?? "Not established"}</strong></div>
                      <div><span>Publication / upload time</span><strong>{entityTime.publishedAt ?? "Not registered"}</strong></div>
                      <div><span>Observation vs scientific cutoff</span><strong>{entityTime.observationRelation}</strong></div>
                      <div><span>Availability vs scientific cutoff</span><strong>{entityTime.availabilityRelation}</strong></div>
                    </div>
                    <p className="p06-time-guidance">{entityTime.guidance}</p>
                    <small className="p06-time-digest">Envelope checksum: {entityTime.envelopeDigest ?? "Not available"} · A checksum is not a device signature or evidence-admission receipt.</small>
                  </>
                ) : (
                  <p className="p04-evidence-empty">{entityTime.guidance} The workspace will not display stale or unscoped evidence.</p>
                )}
              </div>
            )}
            {state.clocks.scientificAsOf && (
              <button type="button" className="p04-investigation-primary"
                onClick={() => setTimeCursor(state.clocks.scientificAsOf!, "LATEST")}>
                Select scientific cutoff time
              </button>
            )}
            <p className="p04-evidence-empty">Chronological alignment only. No point-to-raster numerical comparison or second historical snapshot is computed. Publication cutoff, sensor observation, receipt availability, and operational clock remain independent; historical scientific admission is not inferred.</p>
          </div>
        )}
        {kind === "simulate" && (
          <div className="p04-investigation-section">
            <h3>Prepare a hypothetical irrigation input</h3>
            <label className="p04-whatif-label" htmlFor="p04-mm">Additional water: <strong>{hypotheticalMm} mm</strong></label>
            <input id="p04-mm" type="range" min={0} max={30} step={1}
              value={hypotheticalMm} onChange={e => setHypotheticalMm(Number(e.target.value))}/>
            <button className="p04-investigation-secondary" type="button" onClick={() => setHypotheticalMm(0)}>Reset input</button>
            <p className="p04-evidence-empty">Input preparation only. No scenario model has executed, no predicted outcome is shown, and no irrigation hardware command is available.</p>
          </div>
        )}
      </div>
      <footer className="p04-investigation-footer">Spatial context stays on the map · Scientific, operational and hypothetical values remain separate</footer>
    </section>
  );
}
