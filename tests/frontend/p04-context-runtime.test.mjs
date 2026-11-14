import test from "node:test";
import assert from "node:assert/strict";
import { evaluateZoneInvestigationContext as evaluate, P04_INVESTIGATION_KINDS, P04_HOST_MODES } from "../../src/components/farm/workspace/p04-context-runtime.mjs";

const state = () => ({
  plotScope: { plotId: "plot-A", cropCycleId: "cycle-A", geometryHash: "g1" },
  publication: { snapshotId: "snap-1", authorityStatus: "CERTIFIED", isStale: false },
  selectedEntity: { kind: "ZONE", id: "zone-1", sourceSnapshotId: "snap-1" },
});
const ctx = (workspace = state()) => ({
  workspace, layer10PlotId: "plot-A", layer10SelectedZoneId: "zone-1",
  layer10PublicationId: "publication-1", assessmentPublicationId: "publication-1",
  assessmentSnapshotId: "snap-1", assessmentReady: true, assessmentApplicable: true,
});

test("P04-C02 maps only supported investigations and host modes", () => {
  assert.deepEqual(P04_INVESTIGATION_KINDS, ["water", "compare", "simulate"]);
  assert.deepEqual(P04_HOST_MODES, ["context", "split", "workbench"]);
});
test("P04-C02 current zone and source-verified publication allow read-only diagnostics", () => {
  const result = evaluate(ctx());
  assert.deepEqual([result.zoneId, result.currentSnapshot, result.qualified], ["zone-1", true, true]);
});
test("P04-C02 old selected zone never inherits a newer snapshot", () => {
  const w = state(); w.publication.snapshotId = "snap-2";
  assert.equal(evaluate(ctx(w)).canShowZoneNumbers, false);
});
test("P04-C02 wrong tenant plot or map selection never presents zone diagnostics", () => {
  assert.equal(evaluate({ ...ctx(), layer10PlotId: "plot-B" }).zoneId, null);
  assert.equal(evaluate({ ...ctx(), layer10SelectedZoneId: "zone-2" }).zoneId, null);
});
test("P04-C02 publication mismatch and stale authority cannot be presented as qualified", () => {
  assert.equal(evaluate({ ...ctx(), layer10PublicationId: "publication-2" }).qualified, false);
  const w = state(); w.publication.isStale = true;
  assert.equal(evaluate(ctx(w)).qualified, false);
});
test("P04-C02 diagnostic selection works without silently promoting operational data", () => {
  const w = state(); w.publication.authorityStatus = "UNAVAILABLE";
  const result = evaluate(ctx(w));
  assert.equal(result.zoneId, "zone-1");
  assert.equal(result.canShowZoneNumbers, false);
  assert.match(result.explanation, /not qualified/);
});
