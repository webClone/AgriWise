"use client";

import { useCallback, useState } from "react";
import { PanelRightOpen, PanelRightClose } from "lucide-react";
import PlotDashboard from "@/components/farm/PlotDashboard";
import WorkspaceToolDock, { type WorkspaceQuickAction } from "./WorkspaceToolDock";
import WorkspaceContextInspector from "./WorkspaceContextInspector";
import WorkspaceScientificStatus from "./WorkspaceScientificStatus";
import WorkspaceTimelineContainer from "./WorkspaceTimelineContainer";
import type { PlotWorkspaceProps } from "./PlotWorkspaceFeatureGate";
import "./plot-workspace-v2.css";

/**
 * P02 is deliberately a compositional shell over the existing map and
 * scientific providers. The canonical publication controller remains
 * ParcelAssessmentProvider, and PlotMapShell remains the pixel authority.
 * Tool Registry, time/selection state and new data adapters belong to P03+.
 */
export default function PlotWorkspaceShell(props: PlotWorkspaceProps) {
  const farmId = props.farmId || String(props.farm?.id || "");
  const plotId = props.plotId || String(props.plot?.id || "");
  const [desktopInspectorOpen, setDesktopInspectorOpen] = useState(true);
  const [mobileInspectorOpen, setMobileInspectorOpen] = useState(false);

  const openTool = useCallback((tool: WorkspaceQuickAction) => {
    // UI-only bridge to the existing PlotDashboard tool implementations.
    // It does not invoke device, experiment or scientific API actions.
    window.dispatchEvent(new CustomEvent("akaloris:p02:open-tool", {
      detail: { plotId, tool },
    }));
    setMobileInspectorOpen(false);
  }, [plotId]);

  return (
    <div className={`pw-shell ${desktopInspectorOpen ? "pw-inspector-expanded" : "pw-inspector-collapsed"} ${mobileInspectorOpen ? "pw-mobile-inspector-open" : ""}`}
      data-testid="plot-workspace-v2" data-workspace-version="p02"
      aria-label="Akaloris Plot Workspace">
      <WorkspaceToolDock farmId={farmId} plotId={plotId} onOpenTool={openTool} />

      <main className="pw-map-slot" aria-label="Shared plot map and visualization">
        <div className="pw-scientific-status">
          <WorkspaceScientificStatus />
        </div>
        {!desktopInspectorOpen && (
          <button type="button" className="pw-desktop-inspector-reopen"
            aria-label="Expand Context Inspector"
            onClick={() => setDesktopInspectorOpen(true)}>
            <PanelRightOpen size={17} aria-hidden="true" /> Inspector
          </button>
        )}
        <button type="button" className="pw-mobile-inspector-button"
          aria-expanded={mobileInspectorOpen} aria-controls="pw-context-inspector"
          onClick={() => setMobileInspectorOpen(open => !open)}>
          {mobileInspectorOpen
            ? <PanelRightClose size={18} aria-hidden="true" />
            : <PanelRightOpen size={18} aria-hidden="true" />}
          {mobileInspectorOpen ? "Close inspector" : "Inspector"}
        </button>
        <div className="pw-legacy-map-host">
          <PlotDashboard {...props} embeddedInWorkspace />
        </div>
      </main>

      {desktopInspectorOpen && (
        <aside className="pw-context-slot" id="pw-context-inspector">
          <WorkspaceContextInspector farmId={farmId} plotId={plotId}
            onCollapse={() => {
              setDesktopInspectorOpen(false);
              setMobileInspectorOpen(false);
            }}
          />
        </aside>
      )}
      <WorkspaceTimelineContainer />
      <span className="sr-only">
        V2 shell preview: the full Tool Registry, cross-panel selection and
        13-state laboratory are implemented in later passes.
      </span>
    </div>
  );
}
