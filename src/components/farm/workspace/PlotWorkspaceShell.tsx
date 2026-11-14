"use client";

import { useCallback, useState } from "react";
import { PanelRightOpen, PanelRightClose } from "lucide-react";
import PlotDashboard from "@/components/farm/PlotDashboard";
import WorkspaceToolDock, { type WorkspaceQuickAction } from "./WorkspaceToolDock";
import WorkspaceContextInspector from "./WorkspaceContextInspector";
import WorkspaceScientificStatus from "./WorkspaceScientificStatus";
import WorkspaceTimelineContainer from "./WorkspaceTimelineContainer";
import {
  PlotWorkspaceProvider,
  usePlotWorkspace,
} from "./PlotWorkspaceProvider";
import { useWorkspaceStateBridging } from "./useWorkspaceStateBridging";
import type { PlotWorkspaceProps } from "./PlotWorkspaceFeatureGate";
import "./plot-workspace-v2.css";

function WorkspaceStateBridge() {
  useWorkspaceStateBridging();
  return null;
}

function PlotWorkspaceShellContent(props: PlotWorkspaceProps) {
  const farmId = props.farmId || String(props.farm?.id || "");
  const plotId = props.plotId || String(props.plot?.id || "");
  const { state, setActiveTool, toggleInspector } = usePlotWorkspace();
  const [mobileInspectorOpen, setMobileInspectorOpen] = useState(false);

  const desktopInspectorOpen = !state.isInspectorCollapsed;

  const openTool = useCallback((tool: WorkspaceQuickAction) => {
    setActiveTool(tool);
    // UI bridge to legacy PlotDashboard tool implementations.
    window.dispatchEvent(new CustomEvent("akaloris:p02:open-tool", {
      detail: { plotId, tool },
    }));
    setMobileInspectorOpen(false);
  }, [plotId, setActiveTool]);

  return (
    <div
      className={`pw-shell ${desktopInspectorOpen ? "pw-inspector-expanded" : "pw-inspector-collapsed"} ${mobileInspectorOpen ? "pw-mobile-inspector-open" : ""}`}
      data-testid="plot-workspace-v2"
      data-workspace-version="p03"
      data-workspace-generation={state.generationId}
      aria-label="Akaloris Plot Workspace"
    >
      <WorkspaceToolDock farmId={farmId} plotId={plotId} onOpenTool={openTool} />

      <section className="pw-map-slot" aria-label="Shared plot map and visualization">
        <div className="pw-scientific-status">
          <WorkspaceScientificStatus />
        </div>
        {!desktopInspectorOpen && (
          <button
            type="button"
            className="pw-desktop-inspector-reopen"
            aria-label="Expand Context Inspector"
            onClick={() => toggleInspector(false)}
          >
            <PanelRightOpen size={17} aria-hidden="true" /> Inspector
          </button>
        )}
        <button
          type="button"
          className="pw-mobile-inspector-button"
          aria-expanded={mobileInspectorOpen}
          aria-controls="pw-context-inspector"
          onClick={() => setMobileInspectorOpen((open) => !open)}
        >
          {mobileInspectorOpen
            ? <PanelRightClose size={18} aria-hidden="true" />
            : <PanelRightOpen size={18} aria-hidden="true" />}
          {mobileInspectorOpen ? "Close inspector" : "Inspector"}
        </button>
        <div className="pw-legacy-map-host">
          <PlotDashboard {...props} embeddedInWorkspace />
        </div>
      </section>

      <aside className="pw-context-slot" id="pw-context-inspector">
        <WorkspaceContextInspector
          farmId={farmId}
          plotId={plotId}
          onCollapse={() => {
            if (window.matchMedia("(max-width: 820px)").matches) {
              setMobileInspectorOpen(false);
            } else {
              toggleInspector(true);
            }
          }}
        />
      </aside>
      <WorkspaceTimelineContainer />
      <span className="sr-only">
        P03 scoped workspace state controller: pure reducer, request generations,
        separated temporal clocks, and unified entity selection.
      </span>
    </div>
  );
}

export default function PlotWorkspaceShell(props: PlotWorkspaceProps) {
  const farmId = props.farmId || String(props.farm?.id || "");
  const plotId = props.plotId || String(props.plot?.id || "");
  const tenantId = String((props.farm as any)?.userId || (props.farm as any)?.ownerId || "");
  const cropCycleId = (props.context?.crop as any)?.id || null;
  const geometryHash = (props.plot as any)?.geometryHash || (props.plot as any)?.geometry_hash || null;
  const geometryVersion = (props.plot as any)?.geometryVersion || null;

  return (
    <PlotWorkspaceProvider
      scope={{
        tenantId,
        farmId,
        plotId,
        cropCycleId,
        geometryHash,
        geometryVersion,
      }}
    >
      <WorkspaceStateBridge />
      <PlotWorkspaceShellContent {...props} />
    </PlotWorkspaceProvider>
  );
}
