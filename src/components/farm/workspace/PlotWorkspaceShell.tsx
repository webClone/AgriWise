"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { PanelRightOpen, PanelRightClose } from "lucide-react";
import WorkspaceNativeSpatialCanvas from "./WorkspaceNativeSpatialCanvas";
import WorkspaceExistingToolHost from "./WorkspaceExistingToolHost";
import WorkspaceToolDock, { type WorkspaceQuickAction } from "./WorkspaceToolDock";
import WorkspaceContextInspector from "./WorkspaceContextInspector";
import WorkspaceScientificStatus from "./WorkspaceScientificStatus";
import WorkspaceTimelineContainer from "./WorkspaceTimelineContainer";
import WorkspaceLegacyTimelineBridge from "./WorkspaceLegacyTimelineBridge";
import WorkspaceContextActionsP04, { type P04InvestigationKind } from "./WorkspaceContextActionsP04";
import WorkspaceInvestigationHostP04, { type P04HostMode } from "./WorkspaceInvestigationHostP04";
import "./p04-investigation.css";
import {
  PlotWorkspaceProvider,
  usePlotWorkspace,
} from "./PlotWorkspaceProvider";
import { useWorkspaceStateBridging } from "./useWorkspaceStateBridging";
import type { PlotWorkspaceProps } from "./PlotWorkspaceFeatureGate";
import type { PlotScope } from "./workspace-types";
import "./plot-workspace-v2.css";

function WorkspaceStateBridge() {
  useWorkspaceStateBridging();
  return null;
}

function PlotWorkspaceShellContent(props: PlotWorkspaceProps) {
  const farmId = props.farmId || String(props.farm?.id || "");
  const plotId = props.plotId || String(props.plot?.id || "");
  const { state, setActiveTool, toggleInspector, selectEntity } = usePlotWorkspace();
  const [mobileInspectorOpen, setMobileInspectorOpen] = useState(false);
  const [investigation, setInvestigation] = useState<P04InvestigationKind | null>(null);
  const [hostMode, setHostMode] = useState<P04HostMode>("context");
  const launchControlRef = useRef<HTMLElement | null>(null);

  const launchInvestigation = useCallback((kind: P04InvestigationKind) => {
    launchControlRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setInvestigation(kind);
    setHostMode("context");
    setActiveTool(`p04:${kind}`);
  }, [setActiveTool]);

  const closeInvestigation = useCallback(() => {
    setInvestigation(null);
    setActiveTool("map");
    const control = launchControlRef.current;
    requestAnimationFrame(() => {
      if (control?.isConnected) control.focus();
    });
  }, [setActiveTool]);

  // Development & testing affordance for direct zone investigation
  useEffect(() => {
    if (process.env.NODE_ENV !== "development") return;
    if (typeof window !== "undefined") {
      const onTestSelectZone = (e: Event) => {
        const detail = (e as CustomEvent<{ zoneId: string }>).detail;
        if (detail?.zoneId) {
          selectEntity({
            kind: "ZONE",
            id: detail.zoneId,
            sourceSnapshotId: state.publication.snapshotId,
          });
        }
      };
      const onTestLaunch = (e: Event) => {
        const detail = (e as CustomEvent<{ kind: P04InvestigationKind; mode?: P04HostMode }>).detail;
        if (detail?.kind) {
          setInvestigation(detail.kind);
          if (detail.mode) setHostMode(detail.mode);
          setActiveTool(`p04:${detail.kind}`);
        }
      };
      window.addEventListener("akaloris:test:select-zone", onTestSelectZone);
      window.addEventListener("akaloris:test:launch-investigation", onTestLaunch);
      return () => {
        window.removeEventListener("akaloris:test:select-zone", onTestSelectZone);
        window.removeEventListener("akaloris:test:launch-investigation", onTestLaunch);
      };
    }
  }, [selectEntity, setActiveTool, state.publication.snapshotId]);

  // An open investigation must never retain context across tenant, plot,
  // crop-cycle, geometry or request-generation changes.
  useEffect(() => {
    setInvestigation(null);
  }, [state.generationId, state.plotScope.plotId, state.plotScope.cropCycleId,
      state.plotScope.geometryHash, state.plotScope.geometryVersion]);


  const desktopInspectorOpen = !state.isInspectorCollapsed;

  const openTool = useCallback((tool: WorkspaceQuickAction) => {
    setActiveTool(tool);
    setMobileInspectorOpen(false);
  }, [setActiveTool]);

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
        <WorkspaceNativeSpatialCanvas {...props} />
        <WorkspaceExistingToolHost {...props} />
        <WorkspaceContextActionsP04 onLaunch={launchInvestigation} />
        {investigation && (
          <WorkspaceInvestigationHostP04
            kind={investigation} mode={hostMode}
            onMode={setHostMode} onClose={closeInvestigation}
          />
        )}
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
  const tenantId =
    props.verifiedScope?.tenantId ||
    String((props.farm as any)?.userId || (props.farm as any)?.ownerId || "");
  const cropCycleId =
    props.verifiedScope?.cropCycleId ??
    ((props.context?.crop as any)?.id || null);
  const geometryHash =
    props.verifiedScope?.geometryHash ??
    ((props.plot as any)?.geometryHash || (props.plot as any)?.geometry_hash || null);
  const geometryVersion =
    props.verifiedScope?.geometryVersion ??
    ((props.plot as any)?.geometryVersion ?? null);

  const scope: PlotScope = props.verifiedScope || {
    tenantId,
    farmId,
    plotId,
    cropCycleId,
    geometryHash,
    geometryVersion,
  };

  return (
    <PlotWorkspaceProvider scope={scope}>
      <WorkspaceStateBridge />
      <WorkspaceLegacyTimelineBridge />
      <PlotWorkspaceShellContent {...props} />
    </PlotWorkspaceProvider>
  );
}
