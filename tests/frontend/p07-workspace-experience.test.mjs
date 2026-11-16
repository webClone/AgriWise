import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=path=>readFileSync(path,"utf8");
const map=read("src/components/farm/map/PlotMapShell.tsx");
const canvas=read("src/components/farm/workspace/WorkspaceSpatialCanvas.tsx");
const shell=read("src/components/farm/workspace/PlotWorkspaceShell.tsx");
const status=read("src/components/farm/workspace/WorkspaceScientificStatus.tsx");
const hud=read("src/components/farm/workspace/WorkspaceGeometryAuthoringHUD.tsx");
const css=read("src/components/farm/workspace/plot-workspace-v2.css");
const gate=read("src/components/farm/workspace/PlotWorkspaceFeatureGate.tsx");

test("P07: map appearance panel stays available but is no longer permanently mounted over the V2 canopy",()=>{
  assert.match(map,/props\.workspaceMode && \(/);
  assert.match(map,/showWorkspaceViewTools/);
  assert.match(map,/data-testid="p07-map-view-toggle"/);
  assert.match(map,/\(!props\.workspaceMode \|\| showWorkspaceViewTools\)/);
  assert.match(css,/\.pw-p07-map-tools-panel/);
  assert.match(css,/inset-inline-end:14px/);
});
test("P07: appearance colors and cross-section continue through existing qualified map code",()=>{
  assert.match(map,/onPaletteChange\?\.\(pal\.id/);
  assert.match(map,/inspectorDiagnosisAllowed/);
  assert.match(map,/Cross-section requires inspector-authorized observed raster data/);
  assert.match(map,/setTransectMode\(prev => !prev\)/);
});
test("P07: workspace mode is scoped exclusively to native V2; standalone fallback unchanged",()=>{
  assert.match(canvas,/workspaceMode=\{workspaceMode\}/);
  assert.match(shell,/\sworkspaceMode\s*\/>/);
  assert.match(gate,/if \(!isPlotWorkspaceV2Enabled\(\)\) return <PlotDashboard \{\.\.\.props\} \/>/);
  assert.match(map,/style=\{props\.workspaceMode \? undefined : \{top:"340px",right:"344px"\}\}/);
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
test("P07: P03 scoped entity selection and scientific controls remain connected",()=>{
  assert.match(shell,/onEntityClick=\{selectSceneEntity\}/);
  assert.match(shell,/onCanvasMapClick=\{handleCanvasMapClick\}/);
  assert.match(shell,/onSelectEntity=\{selectSceneEntity\}/);
  assert.match(shell,/<WorkspaceTimelineContainer\s*\/>/);
  assert.match(shell,/<WorkspaceContextInspector\s/);
});
