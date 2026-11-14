"use client";

/**
 * Bounded adapters for already-existing specialized tools. This host does not
 * grant permissions or import the old dashboard. Scientific/physical actions
 * remain subject to their existing server enforcement.
 */
import { useCallback, useEffect, useMemo, useRef } from "react";
import dynamic from "next/dynamic";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotWorkspace } from "./PlotWorkspaceProvider";
import type { PlotWorkspaceProps } from "./PlotWorkspaceFeatureGate";

const SensorNetworkWorkspace = dynamic(() => import("@/components/farm/intelligence/SensorNetworkWorkspace"), { ssr: false });
const MesiaObservatoryWorkspace = dynamic(() => import("@/components/farm/intelligence/MesiaObservatoryWorkspace"), { ssr: false });
const DroneMissionPanel = dynamic(() => import("@/components/farm/drone/DroneMissionPanel"), { ssr: false });
const IrrigationDashboard = dynamic(() => import("@/components/irrigation/IrrigationDashboard"), { ssr: false });
const AddEvidenceModal = dynamic(() => import("@/components/farm/intelligence/AddEvidenceModal"), { ssr: false });
const AgriBrainWorkspace = dynamic(() => import("@/components/farm/intelligence/AgriBrainWorkspace"), { ssr: false });

const KNOWN_TOOLS = new Set(["sensors", "drone", "mesia", "irrigation", "evidence", "assistant"]);

export default function WorkspaceExistingToolHost(props: PlotWorkspaceProps) {
  const { state, setActiveTool } = usePlotWorkspace();
  const layer10 = useLayer10();
  const plotId = state.plotScope.plotId;
  const farmId = state.plotScope.farmId;
  const tool = KNOWN_TOOLS.has(state.activeTool) ? state.activeTool : null;
  const launchFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (tool && !launchFocusRef.current && document.activeElement instanceof HTMLElement) {
      launchFocusRef.current = document.activeElement;
    }
  }, [tool]);

  // Scope changes cannot carry forward a specialized tool selection.
  useEffect(() => {
    setActiveTool("map");
  }, [state.generationId, plotId, state.plotScope.cropCycleId, state.plotScope.geometryHash, setActiveTool]);

  const closeTool = useCallback(() => {
    setActiveTool("map");
    const previous = launchFocusRef.current;
    launchFocusRef.current = null;
    requestAnimationFrame(() => {
      if (previous?.isConnected) previous.focus();
    });
  }, [setActiveTool]);

  const dronePolygon = useMemo(() => {
    const raw = props.plot?.geoJson;
    if (!raw) return undefined;
    try {
      const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
      if (!parsed || typeof parsed !== "object") return undefined;
      const data = parsed as Record<string, unknown>;
      const geometry = data.geometry && typeof data.geometry === "object" ? data.geometry : data;
      return (geometry as Record<string, unknown>).coordinates ? geometry : undefined;
    } catch { return undefined; }
  }, [props.plot?.geoJson]);

  if (!tool) return null;

  return (
    <>
      {tool === "sensors" && <SensorNetworkWorkspace plotId={plotId} onClose={closeTool} />}
      {tool === "mesia" && <MesiaObservatoryWorkspace plotId={plotId} onClose={closeTool} />}
      {tool === "drone" && <DroneMissionPanel plotId={plotId} polygonGeoJson={dronePolygon} onClose={closeTool} />}
      {tool === "irrigation" && (
        <div className="pw-native-tool-modal" role="dialog" aria-label="Irrigation workspace">
          <header className="pw-native-tool-header">
            <div><strong>Irrigation workspace</strong><small>Any operational authorization is enforced by server policy, not the client tool dock.</small></div>
            <button type="button" onClick={closeTool} aria-label="Close irrigation workspace">Close</button>
          </header>
          <IrrigationDashboard />
        </div>
      )}
      {tool === "evidence" && (
        layer10.data?.plot_id === plotId
          ? <AddEvidenceModal plotId={plotId} onClose={closeTool} onSuccess={() => {
              closeTool();
              void layer10.fetchLayer10(plotId, farmId, undefined, undefined, props.cropName);
            }} />
          : <div className="pw-native-tool-modal" role="dialog" aria-label="Field evidence unavailable">
              <header className="pw-native-tool-header"><strong>Scientific plot context not loaded</strong>
                <button type="button" onClick={closeTool}>Close</button></header>
              <p>Field evidence can be added when the current authorized plot context has loaded.</p>
            </div>
      )}
      {tool === "assistant" && (
        layer10.data?.plot_id === plotId && layer10.isApplicable
          ? <AgriBrainWorkspace isOpen onClose={closeTool} context={props.context}
              activeMode={layer10.activeMode} data={layer10.data}
              plotName={props.cropName} />
          : <div className="pw-native-tool-modal" role="dialog" aria-label="Scientific assistant unavailable">
              <header className="pw-native-tool-header"><strong>Scientific assessment unavailable</strong>
                <button type="button" onClick={closeTool}>Close</button></header>
              <p>No qualified current-plot assessment is available for the assistant.</p>
            </div>
      )}
    </>
  );
}
