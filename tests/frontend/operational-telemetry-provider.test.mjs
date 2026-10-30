import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { stripTypeScriptTypes } from "node:module";
import {
  appendOperationalTelemetry, createLiveTelemetryStream, TELEMETRY_CONTRACT_VERSION,
} from "../../src/lib/agribrain/telemetry-contract.mjs";
import { validateOperationalTelemetryResponse } from "../../src/lib/agribrain/operational-telemetry-transport.mjs";

// Exact PlotTelemetryProvider with authored hook/fetch adapters.
// No React DOM, browser, authenticated HTTP service, or database is mounted.
const source = fs.readFileSync(path.join(process.cwd(), "src/hooks/usePlotTelemetry.ts"), "utf8");
const body = source.slice(source.indexOf("const PlotTelemetryContext ="), source.indexOf("export function usePlotTelemetry"));
const transpiled = stripTypeScriptTypes(
  body.replace("export function PlotTelemetryProvider", "function PlotTelemetryProvider"),
  { mode: "strip" }
);
const A = { tenantId: "T", farmId: "F", plotId: "A" };
const B = { tenantId: "T", farmId: "F", plotId: "B" };
const record = (scope, id) => ({
  id, scope, source: "sensor:one", kind: "observation",
  observedAt: "2026-10-30T17:00:00Z", ingestedAt: "2026-10-30T17:00:00Z",
  metric: "temp", value: 20, unit: "°C",
});

function makeHarness() {
  let hooks = [], cursor = 0, queued = [];
  const requests = [], intervals = new Map();
  let nextIntervalId = 0;
  const dependenciesChanged = (a, b) => !a || a.length !== b.length
    || a.some((value, index) => !Object.is(value, b[index]));
  const useSlot = init => {
    const i = cursor++;
    if (!(i in hooks)) hooks[i] = init();
    return [hooks[i], value => { hooks[i] = typeof value === "function" ? value(hooks[i]) : value; }];
  };
  const adapter = {
    createContext: () => ({ Provider: "provider" }),
    createElement: (_component, props) => props.value,
    useState: initial => useSlot(() => typeof initial === "function" ? initial() : initial),
    useRef: initial => {
      const [value] = useSlot(() => ({ current: initial }));
      return value;
    },
    useCallback: fn => fn,
    useEffect: (fn, deps) => {
      const i = cursor++;
      const previous = hooks[i];
      if (!previous || dependenciesChanged(previous.deps, deps)) {
        queued.push(() => {
          if (previous?.cleanup) previous.cleanup();
          const cleanup = fn();
          hooks[i] = { deps, cleanup };
        });
      }
    },
    setInterval: fn => { const id = ++nextIntervalId; intervals.set(id, fn); return id; },
    clearInterval: id => { intervals.delete(id); },
    fetch: (url, opts) => new Promise((resolve, reject) => requests.push({ url, opts, resolve, reject })),
    AbortController,
    appendOperationalTelemetry, createLiveTelemetryStream, validateOperationalTelemetryResponse,
    TELEMETRY_CONTRACT_VERSION,
  };
  const component = new Function(...Object.keys(adapter), transpiled + ";return PlotTelemetryProvider;")(
    ...Object.values(adapter)
  );
  const render = scope => { cursor = 0; return component({ scope, children: null }); };
  const flush = () => { const pending = queued; queued = []; pending.forEach(fn => fn()); };
  const complete = async (requestIndex, scope, observations) => {
    requests[requestIndex].resolve({
      ok: true, json: async () => ({
        contractVersion: TELEMETRY_CONTRACT_VERSION, scope, observations,
      }),
    });
    await new Promise(resolve => setImmediate(resolve));
  };
  const unmount = () => {
    for (const slot of hooks) if (slot && typeof slot.cleanup === "function") slot.cleanup();
  };
  return { requests, intervals, render, flush, complete, unmount };
}

test("polls owner endpoint, ignores old response and old A callback across A→B→A", async () => {
  const h = makeHarness();
  let a = h.render(A);
  h.flush();
  assert.equal(h.requests.length, 1);
  assert.match(h.requests[0].url, /\/api\/plots\/A\/telemetry$/);
  assert.equal(h.requests[0].opts.credentials, "same-origin");
  assert.equal(h.requests[0].opts.cache, "no-store");
  assert.equal(a.stream.observations.length, 0);

  const staleAIngest = a.ingestObservation;
  let b = h.render(B);
  assert.equal(b.stream.observations.length, 0);
  staleAIngest(record(A, "old-action"));
  h.flush();
  assert.equal(h.requests.length, 2);
  await h.complete(0, A, [record(A, "late-A")]);
  b = h.render(B);
  assert.equal(b.stream.observations.length, 0);
  await h.complete(1, B, [record(B, "new-B")]);
  b = h.render(B);
  assert.deepEqual(b.stream.observations.map(o => o.id), ["new-B"]);
  const heldB = b.stream;

  // A new A generation must not accept the old A callback.
  a = h.render(A);
  assert.equal(a.stream.observations.length, 0);
  staleAIngest(record(A, "ghost-A"));
  h.flush();
  await h.complete(2, A, [record(A, "new-A")]);
  a = h.render(A);
  assert.deepEqual(a.stream.observations.map(o => o.id), ["new-A"]);
  assert.deepEqual(heldB.observations.map(o => o.id), ["new-B"]);
  h.unmount();
  assert.equal(h.intervals.size, 0);
});

test("unmount aborts pending fetch and rejects foreign response", async () => {
  const h = makeHarness();
  let a = h.render(A); h.flush();
  assert.equal(h.requests.length, 1);
  h.unmount();
  assert.equal(h.requests[0].opts.signal.aborted, true);
  await h.complete(0, A, [record(A, "late")]);
  a = h.render(A);
  assert.equal(a.stream.observations.length, 0);
});

test("authenticated response with foreign record fails entire batch", async () => {
  const h = makeHarness();
  let a = h.render(A); h.flush();
  await h.complete(0, A, [record(A, "okay"), record(B, "foreign")]);
  a = h.render(A);
  assert.equal(a.stream.observations.length, 0);
  assert.equal(a.transportStatus, "unavailable");
  h.unmount();
});
