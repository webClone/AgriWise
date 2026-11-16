"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PanelRightOpen, PanelRightClose } from "lucide-react";
import WorkspaceSpatialCanvas from "./WorkspaceSpatialCanvas";
import WorkspaceSceneControlsP06 from "./WorkspaceSceneControlsP06";
import {buildSceneManifest,filterCurrentSceneEntities} from "./p06-scene-registry.mjs";
import "./p06-scene-controls.css";
import WorkspaceSpecializedToolsP04 from "./WorkspaceSpecializedToolsP04";
import { useWorkspaceScientificAdapter } from "./useWorkspaceScientificAdapter";
import WorkspaceToolDock, { type WorkspaceQuickAction } from "./WorkspaceToolDock";
import WorkspaceContextInspector from "./WorkspaceContextInspector";
import WorkspaceScientificStatus from "./WorkspaceScientificStatus";
import WorkspaceTimelineContainer from "./WorkspaceTimelineContainer";
import WorkspaceContextActionsP04, { type P04InvestigationKind } from "./WorkspaceContextActionsP04";
import WorkspaceInvestigationHostP04, { type P04HostMode } from "./WorkspaceInvestigationHostP04";
import WorkspaceGeometryAuthoringHUD from "./WorkspaceGeometryAuthoringHUD";
import WorkspaceGeometryLifecycleModal from "./WorkspaceGeometryLifecycleModal";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";
import type { GeometryEditingSession } from "@/lib/agribrain/geometry-authoring";
import "./p04-investigation.css";
import {
  PlotWorkspaceProvider,
  usePlotWorkspace,
} from "./PlotWorkspaceProvider";
import { useWorkspaceStateBridging } from "./useWorkspaceStateBridging";
import { useWorkspaceEntities } from "./useWorkspaceEntities";
import type { PlotWorkspaceProps } from "./PlotWorkspaceFeatureGate";
import type { PlotScope } from "./workspace-types";
import "./plot-workspace-v2.css";
import {
  ASMAE_13_STATE_ORDER,
  resolveAsmaeStateAvailability,
  sampleSirePixel,
  type AsmaeStateKey,
} from "@/lib/agribrain/asmae-13-states";
import { classifyCanonicalHeadValidation } from "@/lib/agribrain/layer10-request-state.mjs";
import { geometryBounds } from "@/lib/agribrain/workspace-geometry.mjs";

function WorkspaceStateBridge() {
  useWorkspaceStateBridging();
  return null;
}

function PlotWorkspaceShellContent(props: PlotWorkspaceProps) {
  const farmId = props.farmId || String(props.farm?.id || "");
  const plotId = props.plotId || String(props.plot?.id || "");
  const { state, setActiveTool, toggleInspector, selectEntity, toggleSceneLayer, setSceneLayerOpacity, setAllSceneLayersVisibility, clearSelection } = usePlotWorkspace();
  const [mobileInspectorOpen, setMobileInspectorOpen] = useState(false);
  const prevSelectedEntityIdRef = useRef<string | null>(null);

  // P07.02 / P07-G05 Mobile: Selecting an entity automatically reveals the mobile inspector drawer
  useEffect(() => {
    if (state.selectedEntity.id && state.selectedEntity.id !== prevSelectedEntityIdRef.current) {
      setMobileInspectorOpen(true);
    } else if (!state.selectedEntity.id && prevSelectedEntityIdRef.current) {
      setMobileInspectorOpen(false);
    }
    prevSelectedEntityIdRef.current = state.selectedEntity.id;
  }, [state.selectedEntity.id]);

  useEffect(() => {
    setMobileInspectorOpen(false);
  }, [plotId]);
  const [investigation, setInvestigation] = useState<P04InvestigationKind | null>(null);
  const [hostMode, setHostMode] = useState<P04HostMode>("context");
  const [activeSpecializedTool, setActiveSpecializedTool] = useState<WorkspaceQuickAction | null>(null);
  const [activeInitialSensorId, setActiveInitialSensorId] = useState<string | null>(null);
  const { entities, refetch: refetchEntities } = useWorkspaceEntities(plotId, 30000, state.generationId);
  const launchControlRef = useRef<HTMLElement | null>(null);

  const scopedScene = useMemo(() => ({tenantId:state.ownerScope.tenantId,farmId:state.plotScope.farmId,plotId:state.plotScope.plotId}),
    [state.ownerScope.tenantId,state.plotScope.farmId,state.plotScope.plotId]);
  const scopedEntities = useMemo(() => filterCurrentSceneEntities(entities,scopedScene),[entities,scopedScene]);
  const selectSceneEntity = useCallback((entity:typeof entities[number]) => {
    selectEntity({kind:entity.entity_kind,id:entity.entity_id,sourceSnapshotId:entity.source_version,
      metadata:entity as unknown as Record<string,unknown>});
  },[selectEntity]);

  // P06.05 Authoring & Controlled Lifecycle State
  const [drawingKind, setDrawingKind] = useState<"DRONE_MISSION" | "FIELD_OBSERVATION" | null>(null);
  const [draftCoordinates, setDraftCoordinates] = useState<[number, number][]>([]);
  const [editingSession, setEditingSession] = useState<GeometryEditingSession | null>(null);
  const [lifecycleModal, setLifecycleModal] = useState<{
    mode: "revise" | "revoke" | "history" | null;
    entity: WorkspaceFeatureEnvelope | null;
  }>({ mode: null, entity: null });

  const handleStartDrawing = useCallback((kind: "DRONE_MISSION" | "FIELD_OBSERVATION") => {
    setDrawingKind(kind);
    setDraftCoordinates([]);
    setEditingSession({ mode: "create" });
    clearSelection();
  }, [clearSelection]);

  const handleUndoVertex = useCallback(() => {
    setDraftCoordinates((prev) => prev.slice(0, -1));
  }, []);

  const handleClearVertices = useCallback(() => {
    setDraftCoordinates([]);
  }, []);

  const handleCancelDrawing = useCallback(() => {
    setDrawingKind(null);
    setDraftCoordinates([]);
    setEditingSession(null);
  }, []);

  const handleAuthoringComplete = useCallback(async (newEntity: WorkspaceFeatureEnvelope) => {
    setDrawingKind(null);
    setDraftCoordinates([]);
    setEditingSession(null);
    await refetchEntities();
    selectSceneEntity(newEntity);
  }, [refetchEntities, selectSceneEntity]);

  const handleRevise = useCallback((entity: WorkspaceFeatureEnvelope) => {
    setLifecycleModal({ mode: "revise", entity });
  }, []);

  const handleRevoke = useCallback((entity: WorkspaceFeatureEnvelope) => {
    setLifecycleModal({ mode: "revoke", entity });
  }, []);

  const handleHistory = useCallback((entity: WorkspaceFeatureEnvelope) => {
    setLifecycleModal({ mode: "history", entity });
  }, []);

  const handleLifecycleClose = useCallback(() => {
    setLifecycleModal({ mode: null, entity: null });
  }, []);

  const handleEditOnMap = useCallback((entity: WorkspaceFeatureEnvelope) => {
    let coords: [number, number][] = [];
    if (entity.geometry) {
      if (entity.geometry.type === "LineString") {
        coords = (entity.geometry.coordinates as [number, number][]).map((c: any) => [Number(c[0]), Number(c[1])]);
      } else if (entity.geometry.type === "Polygon") {
        const ring = (entity.geometry.coordinates as [number, number][][])[0] || [];
        const rawCoords = ring.map((c: any) => [Number(c[0]), Number(c[1])] as [number, number]);
        if (
          rawCoords.length > 1 &&
          rawCoords[0][0] === rawCoords[rawCoords.length - 1][0] &&
          rawCoords[0][1] === rawCoords[rawCoords.length - 1][1]
        ) {
          coords = rawCoords.slice(0, -1);
        } else {
          coords = rawCoords;
        }
      }
    }
    const kind = entity.entity_kind === "DRONE_MISSION" ? "DRONE_MISSION" : "FIELD_OBSERVATION";
    const regId = (entity.provenance as any)?.registration_id || entity.entity_id;
    const currentRevision = Number((entity.properties as any)?.revision) || 1;
    const initialLabel = String((entity.properties as any)?.name || entity.entity_id);
    const initialNotes = String((entity.properties as any)?.notes || "");

    setEditingSession({
      mode: "revise",
      registrationId: regId,
      expectedRevision: currentRevision,
      originalEntity: entity,
      initialLabel,
      initialNotes,
    });
    setDrawingKind(kind);
    setDraftCoordinates(coords);
    setLifecycleModal({ mode: null, entity: null });
  }, []);

  const handleEntityRevised = useCallback(async (updatedEntity: WorkspaceFeatureEnvelope) => {
    setLifecycleModal({ mode: null, entity: null });
    await refetchEntities();
    selectSceneEntity(updatedEntity);
  }, [refetchEntities, selectSceneEntity]);

  const handleEntityRevoked = useCallback(async (_revokedId: string) => {
    setLifecycleModal({ mode: null, entity: null });
    clearSelection();
    await refetchEntities();
  }, [clearSelection, refetchEntities]);

  const scientific = useWorkspaceScientificAdapter({
    farm: props.farm,
    plot: props.plot,
    cropName: props.cropName,
  });

  const [activeAsmaeKey, setActiveAsmaeKey] = useState<AsmaeStateKey>("vigor");
  const [sirePixelHover, setSirePixelHover] = useState<{
    value: number | null;
    row: number;
    col: number;
    coordinate: [number, number];
  } | null>(null);

  // Authoritative ASMAE 13-state availability & statistics derivation
  const rawPub = scientific.parcelAssessment?.rawPublication;
  const posteriorRecord = rawPub?.asmae_posterior_numerical_record || null;
  const pubSurfaces = rawPub?.surfaces || scientific.l10.data?.surfaces || [];
  const pubInventory = rawPub?.surface_inventory || null;
  const validationState = classifyCanonicalHeadValidation(rawPub?.validation);

  const asmaeStatesSummary = useMemo(() => {
    return ASMAE_13_STATE_ORDER.map((sKey) =>
      resolveAsmaeStateAvailability(sKey, pubSurfaces, posteriorRecord, pubInventory, {
        validationState: scientific.parcelAssessment.status === "invalid" ? "corrupt" : scientific.parcelAssessment.status === "stale" ? "stale" : validationState,
        isBlocked: scientific.parcelAssessment.status === "invalid",
        blockReason: scientific.parcelAssessment.status === "invalid" ? "Publication failed cryptographic integrity validation." : undefined,
      })
    );
  }, [pubSurfaces, posteriorRecord, pubInventory, validationState, scientific.parcelAssessment.status]);

  const activeAsmaeAvailability = useMemo(() => {
    return (
      asmaeStatesSummary.find((s) => s.state.key === activeAsmaeKey) ||
      resolveAsmaeStateAvailability(activeAsmaeKey, pubSurfaces, posteriorRecord, pubInventory, {
        validationState,
      })
    );
  }, [asmaeStatesSummary, activeAsmaeKey, pubSurfaces, posteriorRecord, pubInventory, validationState]);

  const plotBounds = useMemo(() => {
    const geo = (props.plot as any)?.geoJson?.geometry || (props.plot as any)?.geoJson;
    return geo ? geometryBounds(geo) : null;
  }, [props.plot]);

  const handleCanvasMapClick = useCallback((coord: [number, number]) => {
    if (drawingKind) {
      setDraftCoordinates((prev) => [...prev, coord]);
      return;
    }
    if (activeAsmaeAvailability?.canRenderPixels && activeAsmaeAvailability?.rasterSurface) {
      const sample = sampleSirePixel(activeAsmaeAvailability.rasterSurface as any, coord, plotBounds);
      setSirePixelHover(sample.valid ? sample : null);
    }
  }, [drawingKind, activeAsmaeAvailability, plotBounds]);

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
    if (typeof window !== "undefined") {
      const onTestSelectZone = (e: Event) => {
        const detail = (e as CustomEvent<{ zoneId: string }>).detail;
        if (detail?.zoneId) {
          scientific.l10.setSelectedZone(detail.zoneId);
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
      const onTestSelectEntity = (e: Event) => {
        const detail = (e as CustomEvent).detail;
        if (detail?.kind && detail?.id) {
          selectEntity({
            kind: detail.kind,
            id: detail.id,
            sourceSnapshotId: state.publication.snapshotId,
            metadata: detail.metadata || detail.properties,
          });
        }
      };
      const onTestStartDrawing = (e: Event) => {
        const detail = (e as CustomEvent<{ kind: "DRONE_MISSION" | "FIELD_OBSERVATION" }>).detail;
        if (detail?.kind) {
          handleStartDrawing(detail.kind);
        }
      };
      const onTestAddDraftPoint = (e: Event) => {
        const detail = (e as CustomEvent<{ coord: [number, number] }>).detail;
        if (detail?.coord) {
          handleCanvasMapClick(detail.coord);
        }
      };
      window.addEventListener("akaloris:test:select-zone", onTestSelectZone);
      window.addEventListener("akaloris:test:select-entity", onTestSelectEntity);
      window.addEventListener("akaloris:test:launch-investigation", onTestLaunch);
      window.addEventListener("akaloris:test:start-drawing", onTestStartDrawing);
      window.addEventListener("akaloris:test:add-draft-point", onTestAddDraftPoint);
      return () => {
        window.removeEventListener("akaloris:test:select-zone", onTestSelectZone);
        window.removeEventListener("akaloris:test:select-entity", onTestSelectEntity);
        window.removeEventListener("akaloris:test:launch-investigation", onTestLaunch);
        window.removeEventListener("akaloris:test:start-drawing", onTestStartDrawing);
        window.removeEventListener("akaloris:test:add-draft-point", onTestAddDraftPoint);
      };
    }
  }, [scientific.l10, selectEntity, setActiveTool, state.publication.snapshotId, handleStartDrawing, handleCanvasMapClick]);

  // An open investigation, specialized tool, authoring draft, editing session or lifecycle modal
  // must never retain context across tenant, plot, crop-cycle, geometry or request-generation changes.
  useEffect(() => {
    setInvestigation(null);
    setActiveSpecializedTool(null);
    setActiveInitialSensorId(null);
    setDrawingKind(null);
    setDraftCoordinates([]);
    setEditingSession(null);
    setLifecycleModal({ mode: null, entity: null });
  }, [state.generationId, state.plotScope.plotId, state.plotScope.cropCycleId,
      state.plotScope.geometryHash, state.plotScope.geometryVersion]);


  const sceneZones = scientific.l10.data?.plot_id === plotId ? (scientific.l10.data?.zones ?? []) : [];
  const sceneManifest = buildSceneManifest({
    scope:scopedScene,entities:scopedEntities,zones:sceneZones,
    rasterAvailable:!!scientific.l10.activeSurface&&scientific.l10.data?.plot_id===plotId,
    visibleVectors:state.renderIntent.visibleVectors,sceneOpacity:state.renderIntent.sceneLayerOpacity
  });
  const desktopInspectorOpen = !state.isInspectorCollapsed;

  const [analysisState, setAnalysisState] = useState<{
    canTransect: boolean;
    transectActive: boolean;
    transectPointsCount: number;
    toggleTransect: () => void;
  } | null>(null);

  const openTool = useCallback((tool: WorkspaceQuickAction) => {
    setActiveTool(tool);
    setActiveSpecializedTool(tool);
    // UI bridge to legacy/external listeners.
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("akaloris:p02:open-tool", {
        detail: { plotId, tool },
      }));
    }
    setMobileInspectorOpen(false);
  }, [plotId, setActiveTool]);

  const handleOpenSensor = useCallback((sensorDeviceId: string) => {
    setActiveInitialSensorId(sensorDeviceId);
    openTool("sensors");
  }, [openTool]);

  return (
    <div
      className={`pw-shell ${desktopInspectorOpen ? "pw-inspector-expanded" : "pw-inspector-collapsed"} ${mobileInspectorOpen ? "pw-mobile-inspector-open" : ""}`}
      data-testid="plot-workspace-v2"
      data-workspace-version="p07.02-consolidated"
      data-spatial-mode={drawingKind ? editingSession?.mode === "revise" ? "revising" : "drawing" : state.selectedEntity.id ? "selected" : "idle"}
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
        <div className="pw-spatial-canvas-host">
          <WorkspaceSpatialCanvas
            farm={props.farm}
            plot={props.plot}
            cropName={props.cropName}
            l10={scientific.l10}
            mapVisualLens={scientific.mapVisualLens}
            onPaletteChange={scientific.setMapVisualLens}
            workspaceEntities={scopedEntities}
            sceneVisibility={state.renderIntent.visibleVectors}
            sceneOpacity={state.renderIntent.sceneLayerOpacity}
            sceneGeneration={state.generationId}
            selectedEntityId={state.selectedEntity.id}
            onEntityClick={selectSceneEntity}
            draftGeometry={drawingKind ? {
              type: drawingKind === "DRONE_MISSION" ? "LineString" : "Polygon",
              coordinates: draftCoordinates,
            } : null}
            onCanvasMapClick={handleCanvasMapClick}
            workspaceMode
            onAnalysisStateChange={setAnalysisState}
            activeAsmaeAvailability={activeAsmaeAvailability}
            onZoneClick={(zoneId) => {
              if (drawingKind) return;
              scientific.l10.setSelectedZone(zoneId);
              selectEntity({
                kind: "ZONE",
                id: zoneId,
                sourceSnapshotId: state.publication.snapshotId,
              });
            }}
          />
        </div>
        <WorkspaceSceneControlsP06
          manifest={sceneManifest}
          entities={scopedEntities}
          zones={sceneZones}
          selectedId={state.selectedEntity.id}
          onStartDrawing={handleStartDrawing}
          activeAsmaeKey={activeAsmaeKey}
          onSelectAsmaeState={setActiveAsmaeKey}
          asmaeStatesSummary={asmaeStatesSummary}
          mapVisualLens={scientific.mapVisualLens}
          onPaletteChange={scientific.setMapVisualLens}
          canTransect={analysisState?.canTransect ?? false}
          transectActive={analysisState?.transectActive ?? false}
          transectPointsCount={analysisState?.transectPointsCount ?? 0}
          onToggleTransect={analysisState?.toggleTransect}
          onToggle={(id, visible) => {
            toggleSceneLayer(id, visible);
            if (!visible && id === "zones" && state.selectedEntity.kind === "ZONE") {
              clearSelection();
            }
            if (
              !visible &&
              scopedEntities.some(
                (e) =>
                  e.entity_id === state.selectedEntity.id &&
                  ((id === "sensors" && e.entity_kind === "SENSOR") ||
                    (id === "cameras" && e.entity_kind === "CAMERA") ||
                    (id === "drones" && e.entity_kind === "DRONE_MISSION") ||
                    (id === "observations" &&
                      (e.entity_kind === "FIELD_OBSERVATION" || e.entity_kind === "FIELD_EVENT")))
              )
            ) {
              clearSelection();
            }
          }}
          onOpacity={setSceneLayerOpacity}
          onAll={visible=>{setAllSceneLayersVisibility(visible);if(!visible)clearSelection();}}
          onSelectEntity={selectSceneEntity}
          onSelectZone={zoneId=>{
            scientific.l10.setSelectedZone(zoneId);
            selectEntity({kind:"ZONE",id:zoneId,sourceSnapshotId:state.publication.snapshotId});
          }}
        />
        {drawingKind && (
          <WorkspaceGeometryAuthoringHUD
            plotId={plotId}
            drawingKind={drawingKind}
            draftCoordinates={draftCoordinates}
            editingSession={editingSession}
            onAddVertex={handleCanvasMapClick}
            onUndoVertex={handleUndoVertex}
            onClearVertices={handleClearVertices}
            onCancel={handleCancelDrawing}
            onComplete={handleAuthoringComplete}
          />
        )}
        {lifecycleModal.mode && lifecycleModal.entity && (
          <WorkspaceGeometryLifecycleModal
            plotId={plotId}
            entity={lifecycleModal.entity}
            mode={lifecycleModal.mode}
            onClose={handleLifecycleClose}
            onRevised={handleEntityRevised}
            onRevoked={handleEntityRevoked}
            onEditOnMap={handleEditOnMap}
          />
        )}
        <WorkspaceSpecializedToolsP04
          plotId={plotId}
          plot={props.plot}
          activeSpecializedTool={activeSpecializedTool}
          initialSensorId={activeInitialSensorId}
          onClose={() => {
            setActiveSpecializedTool(null);
            setActiveInitialSensorId(null);
          }}
          onEvidenceAdded={() => {
            if (scientific.l10.fetchLayer10) {
              void scientific.l10.fetchLayer10(plotId, farmId, undefined, undefined, props.cropName);
            }
          }}
        />
        <WorkspaceContextActionsP04
          onLaunch={launchInvestigation}
          onOpenSensor={handleOpenSensor}
          onOpenTool={openTool}
          workspaceEntities={scopedEntities}
        />
        {investigation && (
          <WorkspaceInvestigationHostP04
            kind={investigation} mode={hostMode} workspaceEntities={scopedEntities}
            onMode={setHostMode} onClose={closeInvestigation}
          />
        )}
      </section>

      <aside className="pw-context-slot" id="pw-context-inspector">
        <WorkspaceContextInspector
          farmId={farmId}
          plotId={plotId}
          onOpenSensor={handleOpenSensor}
          onOpenTool={openTool}
          workspaceEntities={scopedEntities}
          onRevise={handleRevise}
          onRevoke={handleRevoke}
          onHistory={handleHistory}
          activeAsmaeKey={activeAsmaeKey}
          onSelectAsmaeState={setActiveAsmaeKey}
          activeAsmaeAvailability={activeAsmaeAvailability}
          sirePixelHover={sirePixelHover}
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
      <PlotWorkspaceShellContent {...props} />
    </PlotWorkspaceProvider>
  );
}
