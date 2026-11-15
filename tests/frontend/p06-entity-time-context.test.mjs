import test from "node:test";
import assert from "node:assert/strict";
import { buildEntityTemporalComparison } from "../../src/components/farm/workspace/p06-time-comparison.mjs";
const workspace = {
  selectedEntity: {kind: "SENSOR", id: "sensor-db-1", sourceSnapshotId: "v1"},
  ownerScope: {tenantId: "tenant-a", farmId: "farm-a"},
  plotScope: {tenantId: "tenant-a", farmId: "farm-a", plotId: "plot-a"},
  publication: {authorityStatus: "CERTIFIED", isStale: false, snapshotId: "snapshot-real"},
  clocks: {scientificAsOf: "2026-09-08T12:00:00Z"}
};
const envelope = {
  entity_kind: "SENSOR", entity_id: "sensor-db-1", envelope_id: "SENSOR:sensor-db-1:v1",
  source_version: "v1", owner_scope: {tenant_id: "tenant-a", farm_id: "farm-a", plot_id: "plot-a"},
  temporal_extent: {observed_at: "2026-09-08T11:45:00Z", first_available_at: null, published_at: null},
  epistemic_class: "OBSERVED_TELEMETRY", properties: {is_benchmark_fixture: false},
  provenance: {record_digest: "sha256-example-not-attestation"}
};
const evaluate = (w = workspace, e = envelope) => buildEntityTemporalComparison({workspace:w, entity:e});
test("P06: matching scoped sensor shows chronology but not historical admission", () => {
  const result = evaluate();
  assert.equal(result.status, "matched");
  assert.equal(result.observationRelation, "Before cutoff");
  assert.match(result.guidance, /signed first-availability proof is not established/);
  assert.equal(result.scientificReferenceQualified, true);
});
test("P06: missing authenticated entity never falls back to stale metadata", () => {
  const result = evaluate(workspace, null);
  assert.equal(result.status, "unavailable");
  assert.equal(result.observedAt, null);
});
test("P06: cross-tenant, cross-farm, cross-plot envelopes fail closed", () => {
  for (const owner of [{tenant_id:"tenant-b"}, {farm_id:"farm-b"}, {plot_id:"plot-b"}]) {
    assert.equal(evaluate(workspace, {...envelope, owner_scope:{...envelope.owner_scope,...owner}}).status, "scope_mismatch");
  }
});
test("P06: source-version and selected identity mismatches are rejected", () => {
  assert.equal(evaluate(workspace,{...envelope,source_version:"v2"}).status,"scope_mismatch");
  assert.equal(evaluate(workspace,{...envelope,entity_id:"other"}).status,"scope_mismatch");
});
test("P06: synthetic fixture does not imply historical or live proof", () => {
  assert.match(evaluate(workspace,{...envelope,epistemic_class:"SIMULATED",properties:{is_benchmark_fixture:true}}).guidance,/DEMO FIXTURE/);
});
test("P06: planned mission cannot masquerade as an observation", () => {
  const w={...workspace,selectedEntity:{kind:"DRONE_MISSION",id:"drone-a",sourceSnapshotId:"v1"}};
  const e={...envelope,entity_kind:"DRONE_MISSION",entity_id:"drone-a",epistemic_class:"PLANNED"};
  assert.match(evaluate(w,e).guidance,/PLANNED/);
});
test("P06: post-cutoff observation and availability are never backdated", () => {
  const later={...envelope,temporal_extent:{observed_at:"2026-09-08T12:05:00Z",first_available_at:"2026-09-08T12:07:00Z"}};
  const result=evaluate(workspace,later);
  assert.equal(result.observationRelation,"After cutoff");
  assert.equal(result.availabilityRelation,"After cutoff");
  assert.match(result.guidance,/do not backdate/);
});
test("P06: uncertified publication and invalid timestamps remain explicit", () => {
  const w={...workspace,publication:{authorityStatus:"STALE",isStale:true,snapshotId:"old"}};
  assert.equal(evaluate(w).scientificReferenceQualified,false);
  assert.match(evaluate(w).guidance,/not attached to a current certified publication/);
  const e={...envelope,temporal_extent:{observed_at:"yesterday",first_available_at:null}};
  assert.equal(evaluate(workspace,e).observedAt,null);
});
test("P06: availability string is not mistaken for a verified receipt", () => {
  const e={...envelope,temporal_extent:{observed_at:"2026-09-08T11:45:00Z",first_available_at:"2026-09-08T11:50:00Z"}};
  const result=evaluate(workspace,e);
  assert.match(result.guidance,/has not verified the sensor receipt/);
  assert.equal(result.availabilityRelation,"Before cutoff");
});
