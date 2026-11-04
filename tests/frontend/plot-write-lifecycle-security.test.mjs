/** B2B-05 complete owned plot route regression, exact native PUT/POST handlers.
 * Session, Prisma and internal HTTP are fixtures. Run the signed live Mongo
 * create -> edit -> scoped assessment smoke separately before freezing.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import * as nodeModule from "node:module";

let strip = nodeModule.stripTypeScriptTypes;
if (!strip) {
  const ts = (await import("typescript")).default;
  strip = (source) => ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ESNext },
  }).outputText;
}
const root = process.cwd();
function stripImports(src) {
  return src.replace(/^import[^\n]*\n/gm, "").replace(/^export /gm, "");
}
const helperSource = fs.readFileSync(
  path.join(root, "src/lib/plot/owned-plot-mutation.ts"), "utf8",
);
const helperJs = strip(stripImports(helperSource), { mode: "strip" });
const { parseOwnedPlotMutation, PlotMutationValidationError } = new Function(
  helperJs + "\nreturn {parseOwnedPlotMutation, PlotMutationValidationError};",
)();
const rootRoute = fs.readFileSync(
  path.join(root, "src/app/api/plots/route.ts"), "utf8",
).replace(
  'await import("@/lib/agribrain/internal-service-auth")',
  "Promise.resolve({buildSignedInternalHeaders: () => ({})})",
);
const detailRoute = fs.readFileSync(
  path.join(root, "src/app/api/plots/[id]/route.ts"), "utf8",
);
const owner = "444444444444444444444444";
const ownedId = "111111111111111111111111";
const farmId = "222222222222222222222222";
const foreignId = "333333333333333333333333";
const committedHash = "b".repeat(64);
const geometry = {
  type: "Feature", properties: {},
  geometry: {type: "Polygon", coordinates: [[[3,36],[3.001,36],[3.001,36.001],[3,36.001],[3,36]]]},
};
const statusJson = (body, opts = {}) => ({ body, status: opts.status ?? 200 });

function harness(routeSource, { signedIn = true, owns = true,
  epochSucceeds = true, matchingEpoch = true } = {}) {
  const calls = { updates: [], create: [], epochs: [], reads: [], external: [] };
  let persistent = {
    id: ownedId, farmId, name: "original",
    geoJson: geometry, geometryVersion: 1, geometryHash: committedHash,
  };
  const detached = {
    ...persistent, geometryVersion: null, geometryHash: null,
  };
  const prisma = {
    plot: {
      findFirst: async ({ where, select }) => {
        calls.reads.push({ where, select });
        assert.equal(where.farm.userId, owner);
        if (!owns) return null;
        if (where.id && where.id !== ownedId) return null;
        return persistent;
      },
      findUniqueOrThrow: async () => persistent,
      findMany: async () => [persistent],
      create: async ({ data }) => {
        calls.create.push(data);
        persistent = { ...detached, ...data };
        return { ...persistent };
      },
      update: async ({ where, data }) => {
        calls.updates.push({ where, data });
        assert.equal(where.id, ownedId);
        persistent = { ...persistent, ...data };
        return persistent;
      },
      delete: async () => { throw Error("unexpected delete"); },
    },
    farm: { findFirst: async ({ where }) => (
      owns && where.id === farmId && where.userId === owner ? { id: farmId } : null
    ) },
  };
  const init = async (id, farm, user, geo) => {
    calls.epochs.push({ op: "initialize", id, farm, user, geo });
    if (!epochSucceeds) throw Error("epoch unavailable");
    persistent = { ...persistent, geometryVersion: 1, geometryHash: committedHash };
    if (!matchingEpoch) persistent.geometryHash = "a".repeat(64);
    return { plot_id: id, tenant_id: user, geometry_version: 1, geometry_hash: committedHash };
  };
  const update = async (plot, user, geo) => {
    calls.epochs.push({ op: "update", plot, user, geo });
    if (!epochSucceeds) throw Error("epoch unavailable");
    persistent = { ...persistent, geoJson: geo, geometryVersion: 2, geometryHash: "c".repeat(64) };
    return { geometry_version: 2, geometry_hash: "c".repeat(64) };
  };
  const compiled = strip(stripImports(routeSource), { mode: "strip" });
  const routes = new Function(
    "ObjectId", "NextResponse", "prisma", "getSession",
    "initializePlotGeometry", "updatePlotGeometry",
    "parseOwnedPlotMutation", "PlotMutationValidationError",
    "fetch",
    compiled + "\nreturn {POST: typeof POST === 'undefined' ? null : POST, PUT};",
  )(
    { isValid: id => typeof id === "string" && /^[0-9a-f]{24}$/.test(id) },
    { json: statusJson }, prisma, async () => signedIn ? {userId: owner} : null,
    init, update, parseOwnedPlotMutation, PlotMutationValidationError,
    async (...args) => {calls.external.push(args);return {ok: true, status: 200};},
  );
  return { ...routes, calls, persisted: () => persistent };
}
const detailParams = { params: Promise.resolve({id: ownedId}) };
const bulkPut = (h, body) => h.PUT({json: async () => ({id: ownedId, ...body})});
const detailPut = (h, body) => h.PUT({json: async () => body}, detailParams);

test("both PUT routes reject foreign farm.connect before Prisma mutation", async () => {
  for (const [src, call] of [[rootRoute, bulkPut],[detailRoute, detailPut]]) {
    const h = harness(src);
    const response = await call(h, {name: "new", farm: {connect:{id:foreignId}}});
    assert.equal(response.status, 403);
    assert.equal(h.calls.updates.length, 0);
    assert.equal(h.calls.epochs.length, 0);
  }
});

test("unlisted nested writes and metadata authority are rejected in both routes", async () => {
  for (const [src, call] of [[rootRoute, bulkPut],[detailRoute, detailPut]]) {
    for (const payload of [
      {photos:{create:[{url:"forged"}]}}, {sensors:{set:[]}},
      {farmId: foreignId}, {geometryVersion: 999}, {physicalConstraints:{set:[]}},
      {unexpectedField: "value"},
    ]) {
      const h = harness(src);
      const response = await call(h, payload);
      assert.equal(response.status, 403);
      assert.equal(h.calls.updates.length, 0);
    }
  }
});

test("both routes permit owned scalar updates without relationship propagation", async () => {
  for (const [src, call] of [[rootRoute, bulkPut],[detailRoute, detailPut]]) {
    const h = harness(src);
    const response = await call(h, {
      name: " updated ", nameAr: "قطعة", area: "3.2",
      soilType: "LOAM", irrigation: "DRIP",
      physicalConstraints: ["slope"],
    });
    assert.equal(response.status, 200);
    assert.equal(h.calls.updates.length, 1);
    assert.deepEqual(h.calls.updates[0].data, {
      name:"updated",nameAr:"قطعة",area:3.2,
      soilType:"LOAM",irrigation:"DRIP",
      physicalConstraints:{set:["slope"]},
    });
    assert.equal(h.persisted().farmId, farmId);
  }
});

test("both PUT routes retain 401 unauthenticated and 404 foreign plot controls", async () => {
  for (const [src, call] of [[rootRoute, bulkPut],[detailRoute, detailPut]]) {
    const unauthorized = harness(src,{signedIn:false});
    assert.equal((await call(unauthorized,{name:"new"})).status,401);
    assert.equal(unauthorized.calls.updates.length,0);
    const foreign = harness(src,{owns:false});
    assert.equal((await call(foreign,{name:"new"})).status,404);
    assert.equal(foreign.calls.updates.length,0);
  }
});

test("POST returns the owned *committed* geometry epoch rather than detached create", async () => {
  const h = harness(rootRoute);
  const response = await h.POST({json:async()=>({
    farmId,name:"new",nameAr:"جديد",area:1.2,geoJson:geometry,
  })});
  assert.equal(response.status,201);
  assert.equal(response.body.data.geometryVersion,1);
  assert.equal(response.body.data.geometryHash,committedHash);
  assert.equal(response.body.data.geometryHash,h.persisted().geometryHash);
  assert.equal(h.calls.create.length,1);
  assert.equal(h.calls.epochs.length,1);
  assert.ok(h.calls.reads.some(r=>r.where?.id===ownedId && r.where?.farm?.userId===owner));
});

test("POST refuses successful readiness response when epoch commit fails", async () => {
  for(const options of [{epochSucceeds:false},{matchingEpoch:false}]) {
    const h = harness(rootRoute,options);
    const response = await h.POST({json:async()=>({
      farmId,name:"new",area:1,geoJson:geometry,
    })});
    assert.equal(response.status,503);
    assert.equal(response.body.spatialAuthorityReady,false);
  }
});

test("owned geometry edit is signed through epoch service, not Prisma geoJson update",async()=>{
  for (const [src, call] of [[rootRoute, bulkPut],[detailRoute, detailPut]]) {
    const h=harness(src);
    const result=await call(h,{geoJson:geometry,name:"new"});
    assert.equal(result.status,200);
    assert.equal(h.calls.epochs.length,1);
    assert.deepEqual(h.calls.updates[0].data,{name:"new"});
  }
});

test("parser rejects non-scalar nested payloads without invoking ORM",()=>{
  assert.throws(()=>parseOwnedPlotMutation({farm:{connect:{id:foreignId}}}),
    e=>e instanceof PlotMutationValidationError && e.status===403);
  assert.deepEqual(parseOwnedPlotMutation({area:"2.5"}).metadata,{area:2.5});
});
