import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=p=>readFileSync(p,"utf8");
const route=read("src/app/api/plots/[id]/workspace/geometries/route.ts");
const entities=read("src/app/api/plots/[id]/workspace/entities/route.ts");
const reader=read("src/lib/agribrain/read-scoped-workspace-geometry.ts");
const schema=read("prisma/schema.prisma");
const inspector=read("src/components/farm/workspace/WorkspaceContextInspector.tsx");
test("P06.04: POST requires auth, plot ownership and source ownership",()=>{
 assert.match(route,/await authenticatedUserId\(\)/);
 assert.match(route,/farm:\s*\{\s*userId\s*\}/);
 assert.match(route,/where:\s*\{\s*id:\s*input\.source_id!,\s*plotId:\s*scope\.plotId\s*\}/);
 assert.match(route,/cropCycle:\s*\{\s*plotId:\s*scope\.plotId\s*\}/);
 assert.match(route,/validateGeometryRegistrationInput\(raw\)/);
});
test("P06.04: GET rechecks camera/scouting source ownership before projection",()=>{
 assert.match(reader,/id:\s*\{\s*in:\s*cameraIds\s*\},\s*plotId:\s*scope\.plotId/);
 assert.match(reader,/id:\s*\{\s*in:\s*scoutingIds\s*\},\s*cropCycle:\s*\{\s*plotId:\s*scope\.plotId\s*\}/);
 assert.match(reader,/!cameraSet.has/);
 assert.match(reader,/!scoutSet.has/);
 assert.match(entities,/readScopedWorkspaceGeometry/);
 assert.match(route,/readScopedWorkspaceGeometry/);
});
test("P06.04: persistence uniqueness and immutable revision 1",()=>{
 assert.match(schema,/model WorkspaceGeometryRegistration \{/);
 assert.match(schema,/@@unique\(\[plotId, registrationKey\]\)/);
 assert.match(route,/revision:\s*1/);
 assert.match(route,/status:\s*"OWNER_DECLARED"/);
 assert.doesNotMatch(route,/export async function PUT|export async function PATCH|export async function DELETE/);
});
test("P06.04: owner-declared geometry is visibly provisional and separate from hardware science",()=>{
 assert.match(inspector,/Owner-declared geometry/);
 assert.match(route,/OWNER_DECLARED_NOT_SCIENTIFICALLY_ADMITTED/);
 assert.match(entities,/mapped_geometry_count/);
});
