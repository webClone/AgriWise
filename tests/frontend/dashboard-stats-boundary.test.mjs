import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import vm from "node:vm";

// Execute the production route with service-boundary mocks. No database,
// Next.js server or fabricated production records are needed for this check.
async function routeWith({ userId = "tenant-a", fail = false, farmCount = 0 } = {}) {
  const calls = [];
  const query = (name, result) => async (args) => {
    calls.push({ name, args });
    if (fail) throw new Error("Database unavailable");
    return result;
  };
  const prisma = {
    farm: { count: query("farm.count", farmCount), findMany: query("farm.findMany", []) },
    plot: { count: query("plot.count", 0) },
    cropCycle: { count: query("cropCycle.count", 0) },
    cropTask: { count: query("cropTask.count", 0) },
  };
  const context = vm.createContext({ console: { error() {} } });
  const modules = {
    "next/server": { NextResponse: { json: (body, init = {}) => ({ body, status: init.status ?? 200 }) } },
    "@/lib/prisma": { prisma },
    "@/lib/tenant-authorization": { authenticatedUserId: async () => userId },
  };
  const source = await readFile(new URL("../../src/app/api/dashboard/stats/route.ts", import.meta.url), "utf8");
  const route = new vm.SourceTextModule(source, { context });
  await route.link((specifier) => {
    const exports = modules[specifier];
    assert.ok(exports, `Unexpected dependency: ${specifier}`);
    return new vm.SyntheticModule(Object.keys(exports), function () {
      for (const [key, value] of Object.entries(exports)) this.setExport(key, value);
    }, { context });
  });
  await route.evaluate();
  return { response: await route.namespace.GET(), calls };
}

test("unauthenticated requests return 401 without querying data", async () => {
  const { response, calls } = await routeWith({ userId: null });
  assert.equal(response.status, 401);
  assert.equal(calls.length, 0);
});

test("database failure returns unavailable rather than successful zero counts", async () => {
  const { response } = await routeWith({ fail: true });
  assert.equal(response.status, 503);
  assert.equal(response.body.success, false);
  assert.equal(response.body.stats, null);
  assert.ok(response.body.error);
});

test("a real empty account preserves legitimate zero counts", async () => {
  const { response } = await routeWith();
  assert.equal(response.status, 200);
  assert.equal(response.body.success, true);
  assert.equal(response.body.stats.farmCount, 0);
  assert.equal(response.body.stats.totalArea, "0.0");
});

test("every statistics query remains scoped to the authenticated tenant", async () => {
  const { response, calls } = await routeWith({ farmCount: 3 });
  assert.equal(response.body.stats.farmCount, 3);
  assert.equal(calls.length, 5);
  for (const { args } of calls) assert.ok(JSON.stringify(args.where).includes("tenant-a"));
});
