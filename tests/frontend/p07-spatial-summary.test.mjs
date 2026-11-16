import test from "node:test";
import assert from "node:assert/strict";
import {summarizeWorkspaceGeometry} from "../../src/components/farm/workspace/p07-spatial-summary.mjs";

test("P07: a point carries no fabricated area or linear measurement",()=>{
 const m=summarizeWorkspaceGeometry({type:"Point",coordinates:[2.659,36.508]});
 assert.ok(m);
 assert.equal(m.kind,"Point");
 assert.equal(m.areaM2,null);
 assert.equal(m.lengthM,null);
 assert.equal(m.vertexCount,1);
});
test("P07: a planned line reports positive geodesic length and vertex count",()=>{
 const m=summarizeWorkspaceGeometry({type:"LineString",coordinates:[[2.659,36.508],[2.660,36.509]]});
 assert.ok(m);assert.equal(m.kind,"LineString");
 assert.equal(m.vertexCount,2);
 assert.ok(m.lengthM>100 && m.lengthM<220);
 assert.equal(m.areaM2,null);
});
test("P07: owner-drawn polygon reports area and full-ring perimeter without certification",()=>{
 const ring=[[2.659,36.508],[2.660,36.508],[2.660,36.509],[2.659,36.509],[2.659,36.508]];
 const m=summarizeWorkspaceGeometry({type:"Polygon",coordinates:[ring]});
 assert.ok(m);assert.equal(m.vertexCount,4);
 assert.ok(m.areaM2>8500 && m.areaM2<14000);
 assert.ok(m.perimeterM>300 && m.perimeterM<500);
});
test("P07: multipolygon metrics include every footprint, not just first island",()=>{
 const box=(x,y)=>[[x,y],[x+.001,y],[x+.001,y+.001],[x,y+.001],[x,y]];
 const a=summarizeWorkspaceGeometry({type:"Polygon",coordinates:[box(2.659,36.508)]});
 const b=summarizeWorkspaceGeometry({type:"MultiPolygon",coordinates:[[box(2.659,36.508)],[box(2.661,36.508)]]});
 assert.ok(a);assert.ok(b);
 assert.equal(b.vertexCount,8);
 assert.ok(b.areaM2>a.areaM2*1.9 && b.areaM2<a.areaM2*2.1);
});
test("P07: no geometry or malformed geometry supplies no numerical authority",()=>{
 assert.equal(summarizeWorkspaceGeometry(null),null);
 assert.equal(summarizeWorkspaceGeometry({type:"LineString",coordinates:[]}),null);
 assert.equal(summarizeWorkspaceGeometry({type:"Unsupported",coordinates:[]}),null);
});
