/** W1-B RED contracts — run-result route auth and non-authoritative map action cap.
 * Exact production function bodies are executed using fixture adapters.
 * These are NOT live Next.js, database, or internal API integration tests.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import ts from "typescript";

const read = p => readFileSync(path.join(process.cwd(), p), "utf8");
const route = read("src/app/api/agribrain/runs/[runId]/result/route.ts");
const routeStart = route.indexOf("export async function GET(");
assert.ok(routeStart >= 0, "missing run-result GET handler");
const routeJs = ts.transpileModule(
  route.slice(routeStart).replace("export async function GET(", "async function GET("),
  { compilerOptions: { module: ts.ModuleKind.None, target: ts.ScriptTarget.ES2022 } }
).outputText;
const json = (body, opts = {}) => ({
  body, status: opts.status ?? 200, headers: opts.headers ?? {},
});

function handler({ signedIn = false, ownsRun = false, upstreamPlotId = "plot-1", upstreamRunId = "run-1" } = {}) {
  const calls = { sessions: 0, fetches: 0, plotAuthorization: 0, runLookups: 0 };
  const prisma = {
    agriBrainRun: { findFirst: async () => {
      calls.runLookups++;
      return ownsRun ? { runId: "run-1", plotId: "plot-1", farmId: "farm-1", tenantId: "tenant-owner" } : null;
    } },
  };
  const GET = new Function(
    "NextResponse", "prisma", "getSession", "authorizePlot", "fetch", "buildSignedInternalHeaders",
    routeJs + "\nreturn GET;"
  )(
    { json },
    prisma,
    async () => { calls.sessions++; return signedIn ? { userId: "tenant-owner" } : null; },
    async () => { calls.plotAuthorization++; return ownsRun
      ? { status: 200, plot: { id: "plot-1", farmId: "farm-1" }, userId: "tenant-owner" }
      : { status: 404, plot: null };
    },
    async () => { calls.fetches++; return {
      ok: true, status: 200, json: async () => ({ run_id: upstreamRunId, plot_id: upstreamPlotId }),
    }; },
    () => ({ Authorization: "test-signed-internal-scope" }),
  );
  return { GET, calls };
}

const context = { params: Promise.resolve({ runId: "run-1" }) };

test("W1B unauthorized run-result cannot reach upstream even with fabricated run ID", async () => {
  const h = handler({ signedIn: false, ownsRun: false });
  const response = await h.GET({}, context);
  assert.ok(response.status === 401 || response.status === 404);
  assert.equal(h.calls.fetches, 0, "authentication MUST precede all upstream data access");
});

test("W1B foreign-tenant run cannot trigger upstream data access", async () => {
  const h = handler({ signedIn: true, ownsRun: false });
  const response = await h.GET({}, context);
  assert.equal(response.status, 404);
  assert.equal(h.calls.fetches, 0, "tenant-owned run context must be established first");
});

test("W1B run-result handler uses session before HTTP and trusted run ownership", () => {
  const getBody = route.slice(routeStart);
  const firstFetch = getBody.indexOf("await fetch(");
  assert.ok(firstFetch >= 0);
  assert.ok(getBody.includes("getSession("), "session must be checked, not merely imported");
  assert.ok(getBody.indexOf("getSession(") < firstFetch,
    "session check must precede upstream fetch");
  // An upstream envelope's plot_id is not an authorization source.
  assert.ok(!/await upstream\.json\(\)[\s\S]*?const plotId[\s\S]*?authorizePlot/.test(getBody),
    "first authorizing by trusting upstream plot_id is unacceptable");
});

const map = read("src/lib/agribrain/plot-map-evidence-state.ts");
const capStart = map.indexOf('  let actionCap: ActionCap = "monitor";');
const capEnd = map.indexOf("  // 5. Warnings & Recalibration", capStart);
assert.ok(capStart >= 0 && capEnd > capStart, "missing exact production action-cap block");
const actionCapBlock = map.slice(capStart, capEnd).replace(
  "let actionCap: ActionCap", "let actionCap"
);
const cap = new Function(
  "visibleZoneCount", "mapSemantics", "evidenceLevel", "activeSurface",
  actionCapBlock + "\nreturn actionCap;"
);

test("W1B bare real raster never grants prescription without scientific authority", () => {
  const surface = { grounding_class: "RASTER_GROUNDED",
    provenance: { prescription_driver_allowed: false, diagnostic_only: true } };
  assert.notEqual(cap(0, "field_wide_surface", "real_raster", surface),
    "prescription_allowed");
});

test("W1B no signed prescription driver proof means even partial raster is not an action permit", () => {
  assert.notEqual(cap(0, "field_wide_surface", "partial_raster", {
    provenance: { prescription_driver_allowed: false, state_update_allowed: false }
  }), "prescription_allowed");
});



test("W1B authorized run uses exactly one upstream call with matching identity", async () => {
  const h = handler({ signedIn: true, ownsRun: true });
  const response = await h.GET({}, context);
  assert.equal(response.status, 200);
  assert.equal(h.calls.fetches, 1);
  assert.equal(response.body.plot_id, "plot-1");
  assert.equal(response.body.run_id, "run-1");
});

test("W1B upstream spoofed plot cannot become run authorization", async () => {
  const h = handler({ signedIn: true, ownsRun: true, upstreamPlotId: "foreign-plot" });
  const response = await h.GET({}, context);
  assert.equal(response.status, 404);
  assert.equal(h.calls.fetches, 1);
});

test("W1B upstream wrong run ID cannot be substituted for authorized result", async () => {
  const h = handler({ signedIn: true, ownsRun: true, upstreamRunId: "foreign-run" });
  const response = await h.GET({}, context);
  assert.equal(response.status, 404);
});
