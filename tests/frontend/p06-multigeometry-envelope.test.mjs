import test from "node:test";
import assert from "node:assert/strict";
import {createWorkspaceFeatureEnvelope,validateWorkspaceFeatureEnvelope} from "../../src/lib/agribrain/workspace-feature-envelope.mjs";
import {geometryBounds,isRenderableWorkspaceEntity,isSupportedWorkspaceGeometry} from "../../src/lib/agribrain/workspace-geometry.mjs";
const scope={tenant_id:"t",farm_id:"f",plot_id:"p"};
const poly={type:"Polygon",coordinates:[[[2,36],[2.001,36],[2.001,36.001],[2,36.001],[2,36]]]};
const multi={type:"MultiPolygon",coordinates:[poly.coordinates,[[[2.01,36],[2.02,36],[2.02,36.01],[2.01,36.01],[2.01,36]]]]};
const line={type:"LineString",coordinates:[[2,36],[2.001,36.001]]};
const make=(geometry,extra={})=>createWorkspaceFeatureEnvelope({entity_kind:"DRONE_MISSION",entity_id:"mission-a",owner_scope:scope,geometry,location_source:"SURVEYED",epistemic_class:"PLANNED",properties:{is_benchmark_fixture:true},...extra});
test("P06.03: registered lines have separate geometry eligibility, not fake point pins",()=>{
 const x=make(line);
 assert.equal(x.geometry.type,"LineString");assert.equal(x.display_eligibility.eligible_for_map_pin,false);
 assert.equal(x.display_eligibility.eligible_for_map_geometry,true);
 assert.equal(x.spatial_support.has_location,true);assert.equal(isRenderableWorkspaceEntity(x),true);
 assert.equal(validateWorkspaceFeatureEnvelope(x,scope).valid,true);
});
test("P06.03: closed polygon and multipolygon survive construction and validation",()=>{
 for(const g of [poly,multi]){
  const e=make(g);
  assert.equal(e.geometry.type,g.type);
  assert.equal(validateWorkspaceFeatureEnvelope(e,scope).valid,true);
  assert.equal(isRenderableWorkspaceEntity(e),true);
 }
 assert.deepEqual(geometryBounds(multi),[2,36,2.02,36.01]);
});
test("P06.03: invalid geometry is rejected before hashing",()=>{
 const bad=[
  {type:"LineString",coordinates:[[2,36]]},
  {type:"LineString",coordinates:[[NaN,36],[2,36]]},
  {type:"Polygon",coordinates:[[[2,36],[2,36.01],[2.01,36.01]]]},
  {type:"Polygon",coordinates:[[[2,36],[2,36],[2,36],[2,36]]]},
  {type:"MultiPolygon",coordinates:[]},
  {type:"Polygon",coordinates:[[[181,36],[2,36],[2,37],[181,36]]]},
  {type:"GeometryCollection",geometries:[]},
 ];
 for(const g of bad){assert.equal(isSupportedWorkspaceGeometry(g),false);assert.throws(()=>make(g),/Invalid WGS84/);}
});
test("P06.03: centroid substitution and untrusted source never render a polygon",()=>{
 const c=make(poly,{is_centroid_substitute:true});
 assert.equal(c.geometry,null);assert.equal(c.display_eligibility.eligible_for_map_geometry,false);
 const u=make(poly,{location_source:"UNSPECIFIED"});
 assert.equal(u.display_eligibility.eligible_for_map_geometry,false);assert.equal(isRenderableWorkspaceEntity(u),false);
});
test("P06.03: constructor detaches and freezes nested geometry coordinates",()=>{
 const g=JSON.parse(JSON.stringify(multi)),e=make(g),digest=e.provenance.record_digest;
 g.coordinates[0][0][0][0]=19;
 assert.deepEqual(e.geometry.coordinates,multi.coordinates);assert.equal(e.provenance.record_digest,digest);
 assert.equal(Object.isFrozen(e.geometry.coordinates[0][0][0]),true);
});
test("P06.03: point-only envelopes remain backwards compatible",()=>{
 const x=createWorkspaceFeatureEnvelope({entity_kind:"SENSOR",entity_id:"s",owner_scope:scope,latitude:36,longitude:2,location_source:"REGISTERED_HARDWARE"});
 assert.equal(x.display_eligibility.eligible_for_map_pin,true);
 assert.equal(x.display_eligibility.eligible_for_map_geometry,false);
 assert.equal(validateWorkspaceFeatureEnvelope(x,scope).valid,true);
});
test("P06.03: foreign plot envelope fails validation",()=>{
 const x=make(line);
 assert.equal(validateWorkspaceFeatureEnvelope(x,{tenant_id:"t",plot_id:"other"}).valid,false);
});
test("P06.03: digest includes full geometry not only its bbox",()=>{
 const a=make(line);
 const b=make({type:"LineString",coordinates:[[2,36],[2.0005,36.0005],[2.001,36.001]]});
 assert.notEqual(a.provenance.record_digest,b.provenance.record_digest);
});
