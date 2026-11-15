import test from "node:test";
import assert from "node:assert/strict";
import {buildSceneManifest,visibleSceneEntities,filterCurrentSceneEntities,coincidentSceneEntities} from "../../src/components/farm/workspace/p06-scene-registry.mjs";
import {createInitialWorkspaceState,workspaceReducer} from "../../src/components/farm/workspace/workspace-reducer.mjs";
const scope={tenantId:"t",farmId:"f",plotId:"p"};
const entity=(id,kind,overrides={})=>({entity_kind:kind,entity_id:id,envelope_id:kind+":"+id,owner_scope:{tenant_id:"t",farm_id:"f",plot_id:"p"},geometry:{type:"Point",coordinates:[2.95,36.58]},display_eligibility:{eligible_for_map_pin:true,eligible_for_catalog:true},...overrides});
test("P06-G07 counts are tenant and plot scoped",()=>{
 const xs=[entity("s","SENSOR"),entity("c","CAMERA"),entity("bad","SENSOR",{owner_scope:{tenant_id:"x",farm_id:"f",plot_id:"p"}})];
 const m=buildSceneManifest({scope,entities:xs,zones:[{zone_id:"z1"}],rasterAvailable:true});
 assert.equal(m.find(x=>x.id==="sensors").count,1);assert.equal(m.find(x=>x.id==="cameras").count,1);assert.equal(m.find(x=>x.id==="zones").count,1);assert.equal(m.find(x=>x.id==="raster").count,1);
});
test("P06-G02 raster toggle does not hide vector pins",()=>{
 let s=createInitialWorkspaceState(scope);s=workspaceReducer(s,{type:"TOGGLE_SCENE_LAYER",payload:{layerId:"raster",visible:false}});
 assert.equal(s.renderIntent.visibleVectors.raster,false);
 assert.equal(visibleSceneEntities([entity("s","SENSOR")],scope,s.renderIntent.visibleVectors).length,1);
});
test("P06-G03 scientific mode does not change vector visibility",()=>{
 let s=createInitialWorkspaceState(scope);s=workspaceReducer(s,{type:"TOGGLE_SCENE_LAYER",payload:{layerId:"cameras",visible:false}});
 s=workspaceReducer(s,{type:"RENDER_INTENT_SET",payload:{activeLens:"water"}});
 assert.equal(s.renderIntent.visibleVectors.cameras,false);
});
test("P06 opacity clamped, invalid rejected, publication stays isolated",()=>{
 let s=createInitialWorkspaceState(scope);const p=s.publication;
 s=workspaceReducer(s,{type:"SET_LAYER_OPACITY",payload:{layerId:"raster",opacity:0.45}});
 assert.equal(s.renderIntent.sceneLayerOpacity.raster,0.45);
 assert.strictEqual(workspaceReducer(s,{type:"SET_LAYER_OPACITY",payload:{layerId:"raster",opacity:NaN}}),s);
 assert.strictEqual(s.publication,p);
});
test("P06 show-all and hide-all only affect scene preferences",()=>{
 let s=createInitialWorkspaceState(scope);s=workspaceReducer(s,{type:"SET_ALL_LAYERS_VISIBILITY",payload:{visible:false}});
 assert.ok(["raster","zones","sensors","cameras","drones","observations"].every(k=>s.renderIntent.visibleVectors[k]===false));
 assert.equal(s.publication.snapshotId,null);
});
test("P06-G07 plot transition filters stale entities and clears selection",()=>{
 let s=createInitialWorkspaceState(scope);s=workspaceReducer(s,{type:"ENTITY_SELECTED",payload:{kind:"SENSOR",id:"s"}});
 s=workspaceReducer(s,{type:"PLOT_CHANGED",payload:{scope:{...scope,plotId:"q"}}});
 assert.equal(s.selectedEntity.id,null);assert.deepEqual(filterCurrentSceneEntities([entity("s","SENSOR")],{...scope,plotId:"q"}),[]);
});
test("P06-G05 coincident pin candidates are disambiguated",()=>{
 const a=entity("a","SENSOR"),b=entity("b","CAMERA"),c=entity("c","SENSOR",{geometry:{type:"Point",coordinates:[4,38]}});
 assert.deepEqual(coincidentSceneEntities([a,b,c],a,([x,y])=>[x*100,y*100]).map(x=>x.entity_id),["a","b"]);
});
test("P06 no fabricated coordinates for unlocated items",()=>{
 const e=entity("u","SENSOR",{geometry:null,display_eligibility:{eligible_for_catalog:true,eligible_for_map_pin:false}});
 assert.equal(filterCurrentSceneEntities([e],scope).length,1);assert.equal(visibleSceneEntities([e],scope,{}).length,0);
});

test("P06.03: polyline selection cannot be passed to point projection for overlap tests",()=>{
 const line={...entity("line","DRONE_MISSION"),geometry:{type:"LineString",coordinates:[[2.95,36.58],[2.96,36.59]]},display_eligibility:{eligible_for_catalog:true,eligible_for_map_pin:false,eligible_for_map_geometry:true}};
 let projections=0;
 const hits=coincidentSceneEntities([line,entity("point","SENSOR")],line,()=>{projections++;throw Error("polygon coords are not positions")});
 assert.equal(projections,0);assert.deepEqual(hits.map(x=>x.entity_id),["line"]);
});
test("P06.03: a polygon overlapping a point is excluded from point-only collision projection",()=>{
 const point=entity("s","SENSOR");
 const polygon=entity("a","FIELD_OBSERVATION",{geometry:{type:"Polygon",coordinates:[[[2.95,36.58],[2.96,36.58],[2.96,36.59],[2.95,36.58]]]},display_eligibility:{eligible_for_catalog:true,eligible_for_map_pin:false,eligible_for_map_geometry:true}});
 const hits=coincidentSceneEntities([point,polygon],point,xy=>[xy[0]*100,xy[1]*100]);
 assert.deepEqual(hits.map(x=>x.entity_id),["s"]);
});
