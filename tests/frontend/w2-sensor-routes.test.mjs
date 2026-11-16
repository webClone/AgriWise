import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import * as nodeModule from "node:module";

let stripTypeScriptTypes = nodeModule.stripTypeScriptTypes;
if (!stripTypeScriptTypes) {
  const ts = (await import("typescript")).default;
  stripTypeScriptTypes = (code) =>
    ts.transpileModule(code, {
      compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ESNext },
    }).outputText;
}

import { physicalObservationStore } from "../../src/lib/agribrain/physical-observation-store.mjs";

test("W2-02 & W2-03: Route Boundaries, Auth, and Contract Enforcement", async (t) => {
  t.beforeEach(() => {
    physicalObservationStore.reset();
  });

  await t.test("Depth-profile route enforces authentication and owner-scoped tenant isolation", async () => {
    // Read route source, slicing from export async function GET
    const routePath = path.join(process.cwd(), "src/app/api/plots/[id]/sensors/depth-profile/route.ts");
    const routeCode = fs.readFileSync(routePath, "utf8");
    const getCode = routeCode.slice(routeCode.indexOf("export async function GET")).replace("export async function GET", "async function GET");
    const transpiled = stripTypeScriptTypes(getCode, { mode: "strip" });

    // Mock NextRequest and NextResponse
    const makeReq = (url) => ({
      url,
      headers: new Map(),
    });

    const statusObj = (body, opts = {}) => ({
      body,
      status: opts.status ?? 200,
      headers: opts.headers ?? {},
    });

    const plotId = "6a09d9e91dd0c7ed6fce7d50";
    const validOwner = "user-owner-123";

    // 1. Unauthenticated test
    {
      let authCalled = false;
      const harness = new Function(
        "NextResponse", "prisma", "authenticatedUserId", "userOwnsPlot",
        "physicalObservationStore", "normalizeRawReading", "buildSoilDepthProfile",
        transpiled + "\nreturn GET;"
      )(
        { json: statusObj },
        {},
        async () => null, // Unauthenticated
        async () => true,
        physicalObservationStore,
        () => ({}),
        () => ({})
      );

      const res = await harness(makeReq(`http://localhost:3000/api/plots/${plotId}/sensors/depth-profile`), {
        params: Promise.resolve({ id: plotId }),
      });
      assert.equal(res.status, 401);
      assert.equal(res.body.error, "Authentication required");
    }

    // 2. Cross-tenant test (user does not own plot)
    {
      const harness = new Function(
        "NextResponse", "prisma", "authenticatedUserId", "userOwnsPlot",
        "physicalObservationStore", "normalizeRawReading", "buildSoilDepthProfile",
        transpiled + "\nreturn GET;"
      )(
        { json: statusObj },
        {},
        async () => "attacker-user",
        async () => false, // Does not own plot
        physicalObservationStore,
        () => ({}),
        () => ({})
      );

      const res = await harness(makeReq(`http://localhost:3000/api/plots/${plotId}/sensors/depth-profile`), {
        params: Promise.resolve({ id: plotId }),
      });
      assert.equal(res.status, 404);
      assert.equal(res.body.error, "Plot not found");
    }

    // 3. Authorized owner test with simulated sensor
    {
      const mockPrisma = {
        sensor: {
          findMany: async () => [
            {
              id: "sensor-1",
              deviceId: "DEV-PLOT-A",
              type: "MOISTURE",
              vendor: "Sentek Drill & Drop",
              status: "ACTIVE",
              battery: 90,
              rssi: -65,
              lastSync: new Date(),
            },
          ],
        },
        sensorReading: {
          findFirst: async () => ({
            id: "reading-1",
            soilMoisture: 34.2,
            timestamp: new Date("2026-09-08T12:00:00Z"),
          }),
        },
      };

      const harness = new Function(
        "NextResponse", "prisma", "authenticatedUserId", "userOwnsPlot",
        "physicalObservationStore", "normalizeRawReading", "buildSoilDepthProfile",
        transpiled + "\nreturn GET;"
      )(
        { json: statusObj },
        mockPrisma,
        async () => validOwner,
        async () => true, // Owner confirmed
        physicalObservationStore,
        (opts) => ({
          ...opts,
          depthInterval: { nominalCm: opts.nominalDepthCm ?? 15 },
          normalizedValue: (opts.rawValue ?? 0) / 100,
          normalizedUnit: "fraction",
          qaState: "VALID",
        }),
        (records, ctx) => ({
          plotId: ctx.plotId,
          deviceId: ctx.deviceId,
          timestamp: ctx.timestamp,
          standardDepthsCm: [10, 15, 30, 45, 60, 90],
          layers: [
            { nominalCm: 10, measured: false, vwcFraction: null, label: "Not measured —" },
            { nominalCm: 15, measured: true, vwcFraction: 0.342, label: "34.2%" },
            { nominalCm: 30, measured: false, vwcFraction: null, label: "Not measured —" },
            { nominalCm: 45, measured: false, vwcFraction: null, label: "Not measured —" },
            { nominalCm: 60, measured: false, vwcFraction: null, label: "Not measured —" },
            { nominalCm: 90, measured: false, vwcFraction: null, label: "Not measured —" },
          ],
          measuredCount: 1,
          rootZoneAggregateAllowed: false,
          supportDifferenceDisclaimer: "A point measurement at 15 cm and a modeled root-zone estimate represent different spatial and vertical supports.",
        })
      );

      const res = await harness(makeReq(`http://localhost:3000/api/plots/${plotId}/sensors/depth-profile`), {
        params: Promise.resolve({ id: plotId }),
      });

      assert.equal(res.status, 200);
      assert.equal(res.body.plotId, plotId);
      assert.equal(res.body.deviceId, "DEV-PLOT-A");
      assert.equal(res.body.profile.measuredCount, 1);
      assert.equal(res.body.rootZoneAggregateAllowed, false);
      assert.ok(res.body.supportDifferenceDisclaimer.includes("spatial and vertical supports"));
      assert.equal(res.body.channels.length, 1);
      assert.equal(res.body.channels[0].depthCm, 15);
      assert.equal(res.headers["Cache-Control"], "private, no-store, max-age=0");
    }
  });

  await t.test("Ingest route enforces device authentication and clock drift boundaries", async () => {
    const routePath = path.join(process.cwd(), "src/app/api/sensors/ingest/route.ts");
    const routeCode = fs.readFileSync(routePath, "utf8");
    const postCode = routeCode.slice(routeCode.indexOf("export async function POST")).replace("export async function POST", "async function POST");
    const transpiled = stripTypeScriptTypes(postCode, { mode: "strip" });

    const statusObj = (body, opts = {}) => ({
      body,
      status: opts.status ?? 200,
    });

    const makeReq = (body) => ({
      json: async () => body,
    });

    // 1. Missing deviceId
    {
      const harness = new Function(
        "NextResponse", "prisma", "crypto", "physicalObservationStore",
        transpiled + "\nreturn POST;"
      )(
        { json: statusObj },
        {},
        (await import("node:crypto")).default,
        physicalObservationStore
      );

      const res = await harness(makeReq({}));
      assert.equal(res.status, 400);
      assert.match(res.body.error, /deviceId is required/);
    }

    // 2. Unregistered device
    {
      const mockPrisma = {
        sensor: { findUnique: async () => null },
      };
      const harness = new Function(
        "NextResponse", "prisma", "crypto", "physicalObservationStore",
        transpiled + "\nreturn POST;"
      )(
        { json: statusObj },
        mockPrisma,
        (await import("node:crypto")).default,
        physicalObservationStore
      );

      const res = await harness(makeReq({ deviceId: "DEV-UNKNOWN" }));
      assert.equal(res.status, 404);
      assert.match(res.body.error, /No sensor registered/);
    }

    // 3. Bad API key
    {
      const mockPrisma = {
        sensor: {
          findUnique: async () => ({
            id: "s1",
            deviceId: "DEV-AUTH",
            apiKey: "secret-key-123",
          }),
        },
      };
      const harness = new Function(
        "NextResponse", "prisma", "crypto", "physicalObservationStore",
        transpiled + "\nreturn POST;"
      )(
        { json: statusObj },
        mockPrisma,
        (await import("node:crypto")).default,
        physicalObservationStore
      );

      const res = await harness(makeReq({ deviceId: "DEV-AUTH", apiKey: "wrong-key" }));
      assert.equal(res.status, 403);
      assert.equal(res.body.error, "Invalid API key");
    }

    // 4. Future clock drift
    {
      const mockPrisma = {
        sensor: {
          findUnique: async () => ({
            id: "s1",
            deviceId: "DEV-AUTH",
            apiKey: "secret-key-123",
            plotId: "plot-1",
          }),
        },
      };
      const harness = new Function(
        "NextResponse", "prisma", "crypto", "physicalObservationStore",
        transpiled + "\nreturn POST;"
      )(
        { json: statusObj },
        mockPrisma,
        (await import("node:crypto")).default,
        physicalObservationStore
      );

      const futureDate = new Date(Date.now() + 10 * 60 * 1000).toISOString();
      const res = await harness(
        makeReq({
          deviceId: "DEV-AUTH",
          apiKey: "secret-key-123",
          deviceAcquiredAt: futureDate,
        })
      );
      assert.equal(res.status, 400);
      assert.match(res.body.error, /clock drift violation/);
    }
  });
});
