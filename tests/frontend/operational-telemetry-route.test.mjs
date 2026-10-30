import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { stripTypeScriptTypes } from "node:module";
import { serializeOperationalTelemetry } from "../../src/lib/agribrain/operational-telemetry-transport.mjs";
import { TELEMETRY_CONTRACT_VERSION } from "../../src/lib/agribrain/telemetry-contract.mjs";

// Exact GET function, injected auth + database adapters. No live DB, HTTP or
// session used; integration of actual route logic with authored boundaries.
const file = fs.readFileSync(path.join(process.cwd(), "src/app/api/plots/[id]/telemetry/route.ts"), "utf8");
const functionCode = stripTypeScriptTypes(
  file.slice(file.indexOf("export async function GET")).replace("export async function GET", "async function GET"),
  { mode: "strip" }
);
const plotId = "507f1f77bcf86cd799439011";
const owner = "authenticated-owner";
const status = (body, opts = {}) => ({ body, status: opts.status ?? 200, headers: opts.headers ?? {} });

function routeHarness({ authenticated = owner, owns = true, plotFarmId = "farm-one" } = {}) {
  const calls = { owns: 0, plot: 0, sensor: 0, observation: 0 };
  const prisma = {
    plot: { findFirst: async ({ where }) => {
      calls.plot += 1;
      assert.equal(where.farm.userId, owner);
      assert.equal(where.id, plotId);
      return plotFarmId ? { farmId: plotFarmId } : null;
    }},
    sensorReading: { findMany: async ({ where, take }) => {
      calls.sensor += 1;
      assert.equal(where.sensor.is.plotId, plotId);
      assert.ok(take <= 50);
      return [{
        id: "reading-1", timestamp: new Date("2026-10-30T16:00:00Z"),
        sensor: { deviceId: "station-a" },
        temperature: 20, rainfall: 0, humidity: null,
      }];
    }},
    plotObservation: { findMany: async ({ where, take }) => {
      calls.observation += 1;
      assert.equal(where.plotId, plotId);
      assert.ok(take <= 50);
      return [{
        id: "record-1", source: "weather",
        obsDate: new Date("2026-10-30T15:00:00Z"),
        fetchedAt: new Date("2026-10-30T16:01:00Z"),
        tempC: 19, precipMm: 1, et0: 3.2,
      }];
    }},
  };
  const GET = new Function(
    "NextResponse", "prisma", "authenticatedUserId", "userOwnsPlot",
    "TELEMETRY_CONTRACT_VERSION", "serializeOperationalTelemetry",
    functionCode + ";return GET;",
  )(
    { json: status }, prisma,
    async () => authenticated,
    async (u, id) => { calls.owns += 1; assert.equal(u, owner); assert.equal(id, plotId); return owns; },
    TELEMETRY_CONTRACT_VERSION, serializeOperationalTelemetry,
  );
  return { GET, calls };
}
const args = { params: Promise.resolve({ id: plotId }) };

test("unauthenticated GET rejects 401 before ownership/database lookup", async () => {
  const h = routeHarness({ authenticated: null });
  const out = await h.GET({}, args);
  assert.equal(out.status, 401);
  assert.deepEqual(h.calls, { owns: 0, plot: 0, sensor: 0, observation: 0 });
});

test("foreign plot rejects 404 before querying any telemetry", async () => {
  const h = routeHarness({ owns: false });
  const out = await h.GET({}, args);
  assert.equal(out.status, 404);
  assert.deepEqual(h.calls, { owns: 1, plot: 0, sensor: 0, observation: 0 });
});

test("authorized GET derives tenant+farm from trusted sources and returns real persisted timestamps", async () => {
  const h = routeHarness();
  const first = await h.GET({}, args);
  const second = await h.GET({}, args);
  assert.equal(first.status, 200);
  assert.equal(first.headers["Cache-Control"], "private, no-store, max-age=0");
  assert.deepEqual(first.body, second.body, "identical persisted rows produce identical observation identities");
  assert.deepEqual(first.body.scope, { tenantId: owner, farmId: "farm-one", plotId });
  assert.equal(first.body.contractVersion, TELEMETRY_CONTRACT_VERSION);
  const rain = first.body.observations.find(x => x.id === "sensor-reading:reading-1:rain");
  assert.equal(rain.value, 0);
  assert.equal(rain.observedAt, "2026-10-30T16:00:00.000Z");
  assert.equal(rain.ingestedAt, rain.observedAt);
  assert.equal(rain.timeBasis, "server_received_at");
  const weather = first.body.observations.find(x => x.id === "plot-observation:record-1:temp");
  assert.equal(weather.observedAt, "2026-10-30T15:00:00.000Z");
  assert.equal(weather.ingestedAt, "2026-10-30T16:01:00.000Z");
  assert.ok(first.body.observations.every(x => x.scope.tenantId === owner
    && !Object.hasOwn(x, "certified") && !Object.hasOwn(x, "manifestMembership")));
});

test("deleted/foreign-farm plot fails closed after preliminary authorization", async () => {
  const h = routeHarness({ plotFarmId: null });
  const out = await h.GET({}, args);
  assert.equal(out.status, 404);
  assert.equal(h.calls.sensor, 0);
  assert.equal(h.calls.observation, 0);
});
