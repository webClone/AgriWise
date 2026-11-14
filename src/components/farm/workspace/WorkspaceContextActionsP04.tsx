"use client";

import { Droplets, History, FlaskConical, MapPin } from "lucide-react";
import { usePlotWorkspace } from "./PlotWorkspaceProvider";
import { useLayer10 } from "@/hooks/useLayer10";

export type P04InvestigationKind = "water" | "compare" | "simulate";

export default function WorkspaceContextActionsP04({
  onLaunch,
}: {
  onLaunch: (kind: P04InvestigationKind) => void;
}) {
  const { state } = usePlotWorkspace();
  const layer10 = useLayer10();
  const selection = state.selectedEntity;
  const plotMatches = layer10.data?.plot_id === state.plotScope.plotId;
  const zoneId = selection.kind === "ZONE" && plotMatches &&
    layer10.selectedZone === selection.id ? selection.id : null;
  if (!zoneId) return null;
  return (
    <section className="p04-map-context" aria-label="Zone investigation actions" data-testid="p04-map-context">
      <div className="p04-context-title"><MapPin size={16} aria-hidden="true"/>
        <span>Investigate zone <strong>{zoneId}</strong></span></div>
      <div className="p04-context-actions">
        <button type="button" onClick={() => onLaunch("water")}><Droplets size={15}/> Water stress</button>
        <button type="button" onClick={() => onLaunch("compare")}><History size={15}/> Compare time</button>
        <button type="button" onClick={() => onLaunch("simulate")}><FlaskConical size={15}/> Prepare what-if</button>
      </div>
    </section>
  );
}
