/** P01 targeted owner-scope regression. Executes the exact production route-context
 * function body with independent Prisma/session fixtures. This is NOT a real Next.js
 * HTTP/browser or database test; run those in the P01 integration gate.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const service = fs.readFileSync(path.join(root, "src/lib/farm-services.ts"), "utf8");
const start = service.indexOf("export const getAuthorizedPlotRouteContext = cache(");
const end = service.indexOf("// Wrap with React cache()", start);
assert.ok(start >= 0 && end > start, "missing expected owner-scoped production function");
const code = service.slice(start, end)
  .replace("export const getAuthorizedPlotRouteContext", "const getAuthorizedPlotRouteContext")
  .replace("async (plotId: string, farmId: string)", "async (plotId, farmId)");
const compile = new Function(
  "cache", "ObjectId", "currentOwnerId", "prisma", "ownerScope",
  "activeCropCyclePrismaFilter", "mapPlot", "mapFarm", "mapCropCycle",
  code + "\nreturn getAuthorizedPlotRouteContext;"
);

function harness(owner, ownerInDB = owner) {
  const reads = [];
  const plotId = "a".repeat(24);
  const farmId = "b".repeat(24);
  const prisma = {
    plot: {
      findFirst: async query => {
        reads.push(query);
        if (query.where.farm?.userId !== ownerInDB) return null;
        return { id: plotId, farmId, farm: { id: farmId }, cropCycles: [] };
      },
    },
  };
  const get = compile(
    cb => cb,
    { isValid: value => /^[a-f0-9]{24}$/.test(value) },
    async () => owner,
    prisma,
    userId => ({ farm: { userId } }),
    () => ({ in: ["ACTIVE"] }),
    plot => plot, farm => farm, cycle => cycle,
  );
  return { get, reads, plotId, farmId };
}

test("local development signed owner cannot query another owner's plot", async () => {
  const previous = process.env.NODE_ENV;
  process.env.NODE_ENV = "development";
  try {
    const h = harness("owner-A", "owner-B");
    assert.equal(await h.get(h.plotId, h.farmId), null);
    assert.equal(h.reads.length, 1);
    assert.equal(h.reads[0].where.farm.userId, "owner-A");
    assert.equal(h.reads[0].where.farmId, h.farmId);
  } finally {
    if (previous === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previous;
  }
});

test("missing session performs no plot database query even in local development", async () => {
  const h = harness(null);
  assert.equal(await h.get(h.plotId, h.farmId), null);
  assert.equal(h.reads.length, 0);
});

test("valid owner session retrieves only its own plot", async () => {
  const h = harness("owner-A");
  const result = await h.get(h.plotId, h.farmId);
  assert.equal(result.plot.id, h.plotId);
  assert.equal(result.farm.id, h.farmId);
  assert.deepEqual(h.reads[0].where.farm, { userId: "owner-A" });
});

test("invalid plot or farm identifier never queries database", async () => {
  const h = harness("owner-A");
  assert.equal(await h.get("not-a-plot", h.farmId), null);
  assert.equal(await h.get(h.plotId, "not-a-farm"), null);
  assert.equal(h.reads.length, 0);
});

test("layout boots local session before providers, without fallback tenant identity", () => {
  const layout = fs.readFileSync(path.join(root, "src/app/farm/[id]/plot/[plotId]/layout.tsx"), "utf8");
  assert.match(layout, /if \(!session\?\.userId\) \{/);
  assert.match(layout, /return <DevelopmentSessionBootstrap plotId=\{plotId\} farmId=\{farmId\}/);
  assert.match(layout, /if \(!routeContext\) notFound\(\)/);
  assert.match(layout, /tenantId: session\.userId/);
  assert.doesNotMatch(layout, /tenantId: String\(session\?\.userId \|\|/);
});

test("other-owner session never triggers dev-session replacement", () => {
  const page = fs.readFileSync(path.join(root, "src/app/farm/[id]/plot/[plotId]/page.tsx"), "utf8");
  assert.match(page, /if \(!session\?\.userId\) \{/);
  assert.match(page, /if \(!routeContext\) notFound\(\)/);
  const irrigation = fs.readFileSync(
    path.join(root, "src/app/farm/[id]/plot/[plotId]/irrigation/page.tsx"),
    "utf8"
  );
  assert.match(irrigation, /getAuthorizedPlotRouteContext\(plotId, farmId\)/);
});
