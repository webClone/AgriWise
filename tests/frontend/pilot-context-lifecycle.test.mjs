/**
 * Pilot current-context integration regression.
 * Executes the real ParcelAssessmentProvider and immutable contract through
 * deterministic hook/fetch adapters. NOT a mounted React or browser test.
 * Validation is stubbed as valid: this checks lifecycle, not backend signatures.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import * as nodeModule from "node:module";

let stripTypeScriptTypes = nodeModule.stripTypeScriptTypes;
if (!stripTypeScriptTypes) {
  const ts = (await import("typescript")).default;
  stripTypeScriptTypes = (code) => ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ESNext } }).outputText;
}
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const root = resolve(process.cwd());
const contract = await import(pathToFileURL(resolve(root, "src/lib/agribrain/parcel-assessment-contract.mjs")));
let text = fs.readFileSync(resolve(root, "src/hooks/useParcelAssessment.tsx"), "utf8");
text = text.replace(/^import[\s\S]*?from\s+["'][^"']+["'];\s*/gm, "")
  .replace(/^export\s*\{[\s\S]*?\};\s*/gm, "");
text = stripTypeScriptTypes(text, { mode: "transform" }).replace(/export /g, "");

const G1 = { type: "Polygon", coordinates: [[[0,0],[1,0],[1,1],[0,0]]] };
const G2 = { type: "Polygon", coordinates: [[[0,0],[2,0],[2,2],[0,0]]] };

function publication(geom, cycle, sid) {
  return {
    status: "fresh", available: true, validation: {},
    tenant_id: "T", farm_id: "F", plot_id: "P",
    crop_cycle_id: cycle,
    publication_id: "PUB-" + sid, publication_run_id: "RUN-" + sid,
    intelligence_snapshot_id: sid,
    geometry_hash: contract.computeGeometryHash(geom),
    evidence_cutoff_at: "2026-10-29T12:00:00Z",
    published_at: "2026-10-29T13:00:00Z",
    observation_window: { start: "2026-10-28T00:00:00Z", end: "2026-10-29T00:00:00Z" },
    canonical_publication_receipt_hash: "receipt-" + sid,
  };
}
function makeHarness(currentGeometry = G1, currentCrop = "C1", initialHead = publication(G1,"C1","snap-A")) {
  let states = [], refs = [], stateIndex = 0, refIndex = 0;
  let geometry = currentGeometry, crop = currentCrop, head = initialHead;
  const calls = [];
  let onRun = null;
  const mock = {
    ...contract,
    createContext: () => ({ Provider: "Provider" }),
    useContext: () => null,
    useState: value => {
      const index = stateIndex++;
      if (!(index in states)) states[index] = value;
      return [states[index], next => { states[index] = typeof next === "function" ? next(states[index]) : next; }];
    },
    useRef: value => {
      const index = refIndex++;
      return refs[index] ??= { current: value };
    },
    useEffect: () => {},
    useCallback: fn => fn,
    createElement: (type, props) => ({ type, props }),
    classifyCanonicalHeadValidation: () => "valid",
  };
  const component = new Function(...Object.keys(mock), text + "\nreturn ParcelAssessmentProvider;")(...Object.values(mock));
  const render = () => {
    stateIndex = 0; refIndex = 0;
    return component({ children: null, plotGeoJson: geometry, cropCycleId: crop }).props.value;
  };
  const fetchMock = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    if (url.endsWith("/run")) {
      if (onRun) head = onRun();
      return { ok: true, status: 200, json: async () => ({ success: true }) };
    }
    return { ok: true, status: 200, json: async () => head };
  };
  return {
    calls, render, fetchMock,
    changeContext: (g,c) => { geometry = g; crop = c; },
    setHead: h => { head = h; },
    whenRun: fn => { onRun = fn; },
  };
}

test("same-provider geometry/cycle change invalidates current-use permission before refetch", async () => {
  const h = makeHarness();
  globalThis.fetch = h.fetchMock;
  await h.render().fetchAssessment("P","F");
  assert.equal(h.render().isApplicable, true);
  h.changeContext(G2,"C2");
  const stale = h.render();
  assert.equal(stale.status, "stale");
  assert.equal(stale.isApplicable, false);
  assert.equal(stale.state.status, "stale");
  assert.equal(stale.assessment.identity.cropCycleId, "C1");
});

test("explicit force refresh runs and adopts a distinct validated publication", async () => {
  const h = makeHarness();
  h.whenRun(() => publication(G1,"C1","snap-B"));
  globalThis.fetch = h.fetchMock;
  await h.render().fetchAssessment("P","F",{forceRefresh:true});
  assert.equal(h.calls.filter(c => c.url.endsWith("/run")).length, 1);
  assert.equal(h.render().assessment.identity.snapshotId, "snap-B");
  assert.equal(h.render().isApplicable, true);
});

test("stale cache head triggers run; new geometry/cycle head survives a simulated reload", async () => {
  const h = makeHarness();
  h.changeContext(G2,"C2");
  h.whenRun(() => publication(G2,"C2","snap-new-cycle"));
  globalThis.fetch = h.fetchMock;
  await h.render().fetchAssessment("P","F");
  assert.equal(h.calls.filter(c => c.url.endsWith("/run")).length, 1);
  assert.equal(h.render().assessment.identity.cropCycleId, "C2");
  assert.equal(h.render().isApplicable, true);

  const reload = makeHarness(G2,"C2",publication(G2,"C2","snap-new-cycle"));
  globalThis.fetch = reload.fetchMock;
  await reload.render().fetchAssessment("P","F");
  assert.equal(reload.calls.filter(c => c.url.endsWith("/run")).length, 0);
  assert.equal(reload.render().assessment.identity.snapshotId, "snap-new-cycle");
});

test("exact immutable snapshot remains historical and never invokes run", async () => {
  const h = makeHarness();
  globalThis.fetch = h.fetchMock;
  await h.render().fetchAssessment("P","F",{snapshotId:"snap-A",geometry:G2,cropCycleId:"C2"});
  assert.equal(h.render().isApplicable,false);
  assert.equal(h.render().status,"stale");
  assert.equal(h.calls.filter(c => c.url.endsWith("/run")).length,0);
});
