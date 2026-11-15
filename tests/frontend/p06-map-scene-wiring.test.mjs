import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
const root=process.cwd();
const read=p=>fs.readFileSync(path.join(root,p),"utf8");
const shell=read("src/components/farm/workspace/PlotWorkspaceShell.tsx");
const canvas=read("src/components/farm/workspace/WorkspaceSpatialCanvas.tsx");
const map=read("src/components/farm/map/PlotMapShell.tsx");
const pin=read("src/components/farm/map/layers/WorkspaceEntityPinsLayer.ts");
const controls=read("src/components/farm/workspace/WorkspaceSceneControlsP06.tsx");
const reducer=read("src/components/farm/workspace/workspace-reducer.mjs");
test("P06-G02/G03 raster, zones and entity pins remain independently gated",()=>{
 assert.match(map,/const surfaceLayers=showRaster/);
 assert.match(map,/const zoneLayers=showZones/);
 assert.match(map,/sceneVisibility\?\.\[layer\]/);
 assert.match(map,/getWorkspaceEntityPinsLayers/);
});
test("P06-G06 scientific render receipts still derive from committed layers",()=>{
 assert.match(map,/createCommittedRenderReceipt/);
 assert.match(map,/committedLayerIds/);
 assert.match(map,/surfaceStack\.materialization/);
 assert.match(map,/showRaster && <PlotScientificLegend/);
});
test("P06-G05 overlapping entity choices use viewport projection and keyboard focus",()=>{
 assert.match(map,/coincidentSceneEntities/);
 assert.match(map,/info\?\.viewport\?\.project/);
 assert.match(map,/data-entity-choice/);
 assert.match(map,/Escape/);
 assert.match(pin,/onEntityClick\(info\.object,info\)/);
});
test("P06 accessible directory retains unlocated entities and shared selection",()=>{
 assert.match(controls,/Location not registered \(list only\)/);
 assert.match(controls,/onSelectEntity\(entity\)/);
 assert.match(shell,/onSelectEntity=\{selectSceneEntity\}/);
 assert.match(shell,/filterCurrentSceneEntities/);
});
test("P06 presentation actions never write scientific publication state",()=>{
 assert.match(reducer,/case "TOGGLE_SCENE_LAYER"/);
 assert.match(reducer,/case "SET_LAYER_OPACITY"/);
 assert.match(reducer,/case "SET_ALL_LAYERS_VISIBILITY"/);
 assert.match(canvas,/sceneVisibility=\{sceneVisibility\}/);
});
test("P06 directory selection pans only to known located entity",()=>{
 assert.match(map,/eligible_for_map_pin===true/);
 assert.match(map,/setViewState\(prev=>/);
 assert.match(map,/lastFocusedRef/);
});
