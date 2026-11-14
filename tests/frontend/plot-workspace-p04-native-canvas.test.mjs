import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
const read = p => fs.readFileSync(path.join(process.cwd(), p), "utf8");
const gate=read("src/components/farm/workspace/PlotWorkspaceFeatureGate.tsx");
const shell=read("src/components/farm/workspace/PlotWorkspaceShell.tsx");
const canvas=read("src/components/farm/workspace/WorkspaceNativeSpatialCanvas.tsx");
const host=read("src/components/farm/workspace/WorkspaceExistingToolHost.tsx");
const actions=read("src/components/farm/workspace/WorkspaceContextActionsP04.tsx");

test("P04-C03 native V2 canvas never mounts legacy PlotDashboard",()=>{
 assert.match(shell, /<WorkspaceNativeSpatialCanvas/);
 assert.doesNotMatch(shell, /import PlotDashboard|<PlotDashboard|embeddedInWorkspace|akaloris:p02:open-tool/);
 assert.match(gate, /if \(!isPlotWorkspaceV2Enabled\(\)\) return <PlotDashboard/);
});
test("P04-C03 exactly one canonical parcel acquisition path, no independent Layer10 fetch on render",()=>{
 assert.match(canvas, /useParcelAssessment\(\)/);
 assert.match(canvas, /fetchAssessment\(plotId, farmId/);
 assert.match(canvas, /computeGeometryHash\(geometry\)/);
 assert.match(canvas, /cropCycleId: cycleId/);
 assert.match(canvas, /dynamic\(\(\) => import\("@\/components\/farm\/map\/PlotMapShell"\)/);
 assert.match(canvas, /onZoneClick=\{l10.setSelectedZone\}/);
 assert.doesNotMatch(canvas, /fetchLayer10\(/);
 assert.doesNotMatch(canvas, /ParcelAssessmentProvider|Layer10Provider/);
});
test("P04-C03 old specialized tools no longer depend on hidden dashboard event bridge",()=>{
 for (const name of ["sensors","drone","mesia","irrigation","evidence","assistant"]) {
  assert.match(host,new RegExp('tool === "'+name+'"'));
 }
 assert.match(host,/usePlotWorkspace\(\)/);
 assert.match(host,/setActiveTool\("map"\)/);
 assert.doesNotMatch(host,/akaloris:p02:open-tool|<PlotDashboard/);
});
test("P04-C03 contextual action pill requires actual current Layer10 selection and plot",()=>{
 assert.match(actions,/layer10\.data\?\.plot_id === state\.plotScope\.plotId/);
 assert.match(actions,/layer10\.selectedZone === selection\.id/);
 assert.doesNotMatch(actions,/!layer10\.data \|\|/);
});
