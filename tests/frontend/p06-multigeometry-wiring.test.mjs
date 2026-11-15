import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
const read=p=>fs.readFileSync(path.join(process.cwd(),p),"utf8");
const map=read("src/components/farm/map/PlotMapShell.tsx");
const layer=read("src/components/farm/map/layers/WorkspaceEntityGeometryLayer.ts");
const pins=read("src/components/farm/map/layers/WorkspaceEntityPinsLayer.ts");
const directory=read("src/components/farm/workspace/WorkspaceSceneControlsP06.tsx");
const actions=read("src/components/farm/workspace/WorkspaceContextActionsP04.tsx");
const inspector=read("src/components/farm/workspace/WorkspaceContextInspector.tsx");
const api=read("src/app/api/plots/[id]/workspace/entities/route.ts");

test("P06.03: eligible paths and polygons mount independently of scientific raster",()=>{
 assert.match(map,/getWorkspaceEntityGeometryLayers/);
 assert.match(map,/visibleEntities\.length\?\[/);
 assert.match(map,/getWorkspaceEntityPinsLayers/);
 assert.match(map,/const surfaceLayers=showRaster/);
 assert.match(layer,/new PathLayer/);
 assert.match(layer,/new GeoJsonLayer/);
});
test("P06.03: no line or polygon is positioned as a point pin",()=>{
 assert.match(pins,/e\.geometry\?\.type === "Point"/);
 assert.match(layer,/geometry\?\.type==="LineString"/);
 assert.match(layer,/geometry\?\.type==="Polygon"/);
 assert.match(layer,/geometry\?\.type==="MultiPolygon"/);
 assert.match(layer,/isRenderableWorkspaceEntity/);
});
test("P06.03: selected geometries use same entity selection and highlighting",()=>{
 assert.match(layer,/onEntityClick\?\.\(e,info\)/);
 assert.match(layer,/onEntityClick\?\.\(info\.object,info\)/);
 assert.match(layer,/chosen\(e,selectedEntityId\)/);
 assert.match(map,/pickEntity/);
 assert.match(map,/sceneVisibility/);
});
test("P06.03: directory and inspector accommodate multi-geometry without fake pin",()=>{
 assert.match(directory,/eligible_for_map_geometry/);
 assert.match(map,/geometryBounds\(e\?\.geometry\)/);
 assert.match(inspector,/footprintBounds/);
 assert.match(actions,/geometry\?\.type === "Point"/);
 assert.doesNotMatch(actions,/selection\.metadata/);
 assert.doesNotMatch(inspector,/selectedEntity\.metadata/);
});
test("P06.03: versioned API retains tenant check and does not invent corridors",()=>{
 assert.match(api,/WORKSPACE_FEATURE_CONTRACT_VERSION/);
 assert.match(api,/const userId = await authenticatedUserId\(\)/);
 assert.match(api,/farm: \{ userId \}/);
 assert.doesNotMatch(api,/NODE_ENV\s*===\s*"development"/);
 assert.doesNotMatch(api,/createSyntheticFlightPath|generateCameraCone/);
});
