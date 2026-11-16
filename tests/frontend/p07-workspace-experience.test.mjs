import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createInitialWorkspaceState, workspaceReducer} from "../../src/components/farm/workspace/workspace-reducer.mjs";

const read=path=>readFileSync(path,"utf8");
const map=read("src/components/farm/map/PlotMapShell.tsx");
const canvas=read("src/components/farm/workspace/WorkspaceSpatialCanvas.tsx");
const shell=read("src/components/farm/workspace/PlotWorkspaceShell.tsx");
const sceneControls=read("src/components/farm/workspace/WorkspaceSceneControlsP06.tsx");
const legend=read("src/components/farm/map/PlotScientificLegend.tsx");
const legendCss=read("src/components/farm/map/plot-scientific-legend.css");
const status=read("src/components/farm/workspace/WorkspaceScientificStatus.tsx");
const hud=read("src/components/farm/workspace/WorkspaceGeometryAuthoringHUD.tsx");
const css=read("src/components/farm/workspace/plot-workspace-v2.css");
const gate=read("src/components/farm/workspace/PlotWorkspaceFeatureGate.tsx");

test("P07-G01: exactly one unified View control integrated into scene controls header",()=>{
  // Scene header contains the single unified View control
  assert.match(sceneControls,/data-testid="p07-map-view-toggle"/);
  assert.match(sceneControls,/id="p07-map-view-panel"/);
  assert.match(sceneControls,/Color Lens/);
  assert.match(sceneControls,/Spatial Analysis/);
  // PlotMapShell does not render competing view triggers when workspaceMode is active
  assert.doesNotMatch(map,/className="pw-p07-map-tools-trigger"/);
  // Shell passes palette and analysis props to unified scene controls
  assert.match(shell,/mapVisualLens=\{scientific\.mapVisualLens\}/);
  assert.match(shell,/onPaletteChange=\{scientific\.setMapVisualLens\}/);
  assert.match(shell,/canTransect=\{analysisState\?\.canTransect \?\? false\}/);
});

test("P07-G02: appearance colors and cross-section continue through existing qualified map code",()=>{
  assert.match(map,/inspectorDiagnosisAllowed/);
  assert.match(map,/onAnalysisStateChange\?\.\(/);
  assert.match(map,/canTransect:\s*inspectorDiagnosisAllowed/);
  assert.match(canvas,/onAnalysisStateChange=\{onAnalysisStateChange\}/);
  assert.match(sceneControls,/title=\{!canTransect \? "Cross-section requires inspector-authorized observed raster data"/);
  assert.match(sceneControls,/disabled=\{!canTransect\}/);
});

test("P07-G03: map evidence disclosure is interactive, keyboard-accessible, and collapsible",()=>{
  assert.match(legend,/data-testid="p07-map-evidence-toggle"/);
  assert.match(legend,/aria-expanded=\{expanded\}/);
  assert.match(legend,/aria-controls="akaloris-legend-detail"/);
  assert.match(legend,/id="akaloris-legend-detail"/);
  assert.match(legendCss,/pointer-events: auto/);
  assert.match(legendCss,/\.akaloris-legend-toggle:focus-visible/);
});

test("P07-G04 & P07-G05 & P07-G06: coordinated inspector collapse and expansion states in reducer",()=>{
  const initialState = createInitialWorkspaceState({ farmId: "f1", plotId: "p1", tenantId: "t1" });
  // P07-G04: Starts collapsed by default
  assert.equal(initialState.isInspectorCollapsed, true, "initial empty inspector starts collapsed");

  // P07-G05: Selecting an entity reveals the inspector
  const entitySelectedState = workspaceReducer(initialState, {
    type: "ENTITY_SELECTED",
    payload: {
      kind: "SENSOR",
      id: "sensor-node-01",
      metadata: { name: "Soil Sensor 1" },
    },
  });
  assert.equal(entitySelectedState.isInspectorCollapsed, false, "selecting entity expands inspector");
  assert.equal(entitySelectedState.selectedEntity.id, "sensor-node-01");

  // Clearing selection collapses the inspector
  const clearedSelectionState = workspaceReducer(entitySelectedState, {
    type: "ENTITY_SELECTED",
    payload: {
      kind: null,
      id: null,
    },
  });
  assert.equal(clearedSelectionState.isInspectorCollapsed, true, "clearing selection collapses inspector");

  // P07-G06: Plot scope change resets inspector and selection
  const plotChangedState = workspaceReducer(entitySelectedState, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "t1",
        farmId: "f1",
        plotId: "p2", // new plot
      },
    },
  });
  assert.equal(plotChangedState.isInspectorCollapsed, true, "plot transition resets inspector to collapsed");
  assert.equal(plotChangedState.selectedEntity.id, null, "plot transition clears selected entity");
});

test("P07-G07: mobile layout positions legend away from timeline collision",()=>{
  assert.match(legendCss,/@media \(max-width: 850px\)/);
  assert.match(legendCss,/top: 60px/);
  assert.match(legendCss,/bottom: auto/);
});

test("P07-G08: workspace mode scoped exclusively to native V2; fallback legacy dashboard intact",()=>{
  assert.match(canvas,/workspaceMode=\{workspaceMode\}/);
  assert.match(shell,/\sworkspaceMode\s/);
  assert.match(gate,/if \(!isPlotWorkspaceV2Enabled\(\)\) return <PlotDashboard \{\.\.\.props\} \/>/);
  assert.match(map,/style=\{\{ top: "340px", right: "344px" \}\}/);
});

test("P07: compact disclosure retains separate scientific and operational epistemic status",()=>{
  assert.match(status,/aria-expanded=\{expanded\}/);
  assert.match(status,/data-testid="p07-scientific-status"/);
  assert.match(status,/useParcelAssessment\(\)/);
  assert.match(status,/usePlotTelemetry\(\)/);
  assert.match(status,/Operational IoT · not scientific evidence/);
  assert.match(status,/A loaded publication does not prove that a scientific raster is rendered/);
});

test("P07: drawing and revision modes have visible, accessible state without changing publication",()=>{
  assert.match(shell,/data-spatial-mode=\{drawingKind \?/);
  assert.match(hud,/data-authoring-mode=\{isRevise \? "revising" : "drawing"\}/);
  assert.match(hud,/aria-live="polite"/);
  assert.match(css,/\.pw-shell\[data-spatial-mode="drawing"\]/);
  assert.match(css,/pointer-events:none;z-index:8/);
  assert.match(map,/const safeOnZoneClick = props\.draftGeometry \? undefined : onZoneClick/);
});
