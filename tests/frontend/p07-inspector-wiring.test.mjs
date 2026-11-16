import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const inspector=readFileSync("src/components/farm/workspace/WorkspaceContextInspector.tsx","utf8");
const css=readFileSync("src/components/farm/workspace/plot-workspace-v2.css","utf8");
const map=readFileSync("src/components/farm/map/PlotMapShell.tsx","utf8");

test("P07: selected geometry has one overview and one lifecycle action group",()=>{
 assert.match(inspector,/data-testid="p07-entity-overview"/);
 for(const action of ["p06-revise-btn","p06-history-btn","p06-revoke-btn"]){
  assert.equal((inspector.match(new RegExp(`data-testid="${action}"`,"g"))||[]).length,1,action);
 }
 assert.match(inspector,/onRevise\?\.\(matchedEntity\)/);
 assert.match(inspector,/onHistory\?\.\(matchedEntity\)/);
 assert.match(inspector,/onRevoke\?\.\(matchedEntity\)/);
});
test("P07: reported dimensions are from registered geometry and never an admission receipt",()=>{
 assert.match(inspector,/summarizeWorkspaceGeometry\(matchedEntity\?\.geometry \?\? null\)/);
 assert.match(inspector,/Dimensions are calculated from submitted vertices/);
 assert.match(inspector,/Envelope integrity/);
 assert.match(inspector,/data-epistemic=\{matchedEntity\.epistemic_class\}/);
 assert.match(css,/\.pw-p07-metrics/);
});
test("P07: pixel inspector follows the workspace edge but legacy positioning is untouched",()=>{
 assert.match(map,/style=\{props\.workspaceMode \? \{/);
 assert.match(map,/top: "calc\(var\(--pw-topbar-clearance, 111px\) \+ 56px\)"/);
 assert.match(map,/\} : \{top: "260px",left: "344px",zIndex: 40\}\}/);
 assert.match(map,/label: "Chlorophyll"/);
});
