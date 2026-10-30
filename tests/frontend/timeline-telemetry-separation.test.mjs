import test from "node:test";
import assert from "node:assert/strict";
import {
  TELEMETRY_STATUS as S,
  classifyManifestEvidence,
  classifyTelemetryObservation,
  createLiveTelemetryStream,
  appendOperationalTelemetry,
} from "../../src/lib/agribrain/telemetry-contract.mjs";

const now = "2026-10-30T16:00:00Z";
const cutoff = "2026-10-30T10:00:00Z";
const observation = (id, observedAt, source = "weather_station") => ({
  id, source, kind: "observation", observedAt, value: 12, unit: "°C",
});
const manifestEvent = Object.freeze({
  id: "manifest-001",
  source: "sentinel2",
  type: "observation",
  observedAt: "2026-10-29T10:00:00Z",
  capturedAt: "2026-10-29T10:00:00Z",
  ingestedAt: "2026-10-29T11:00:00Z",
  acceptedAt: "2026-10-29T12:00:00Z",
  verified: true,
  manifestMembership: true,
  summary: "Recorded acquisition",
});
const assessment = Object.freeze({
  identity: Object.freeze({
    tenantId: "T", farmId: "F", plotId: "P",
    snapshotId: "snap-A", publicationReceiptHash: "receipt-A",
    evidenceCutoffAt: cutoff,
  }),
  evidenceTimeline: Object.freeze([manifestEvent]),
});

test("only the actual immutable manifest event is certified", () => {
  assert.equal(classifyManifestEvidence(assessment, manifestEvent), S.CERTIFIED_MANIFEST);
  assert.equal(classifyManifestEvidence(assessment, { ...manifestEvent }), S.UNVERIFIED);
  assert.equal(classifyManifestEvidence(assessment, { ...manifestEvent, observedAt: "2026-10-30T11:00:00Z" }), S.UNVERIFIED);
  assert.equal(classifyManifestEvidence(null, manifestEvent), S.UNVERIFIED);
});

test("historical observations cannot be certified by timestamp or sender flag", () => {
  const old = { ...observation("late", "2026-10-29T09:00:00Z"), ingestedAt: "2026-10-30T12:00:00Z" };
  assert.equal(classifyTelemetryObservation(old, cutoff, now), S.LATE_ARRIVING_UNADMITTED);
  assert.equal(classifyTelemetryObservation({ ...old, manifestMembership: true }, cutoff, now), S.LATE_ARRIVING_UNADMITTED);
});

test("live, forecast and missing evidence stay distinct", () => {
  assert.equal(classifyTelemetryObservation(observation("live", "2026-10-30T11:00:00Z"), cutoff, now), S.LIVE_UNCERTIFIED);
  assert.equal(classifyTelemetryObservation(observation("future-raw", "2026-10-31T11:00:00Z"), cutoff, now), S.UNVERIFIED);
  assert.equal(classifyTelemetryObservation({ id: "f", kind: "forecast", source: "weather-model", modelId: "wx-v1", validAt: "2026-11-01T00:00:00Z" }, cutoff, now), S.MODEL_FORECAST);
  assert.equal(classifyTelemetryObservation({ id: "f", kind: "forecast", source: "weather-model", validAt: "2026-11-01T00:00:00Z" }, cutoff, now), S.UNVERIFIED);
  assert.equal(classifyTelemetryObservation(observation("no-cutoff", "2026-10-30T11:00:00Z"), null, now), S.UNVERIFIED);
  assert.equal(classifyTelemetryObservation(observation("date-only", "2026-10-29"), cutoff, now), S.UNVERIFIED);
});

test("operational append is immutable and cannot assert manifest authority", () => {
  const base = createLiveTelemetryStream({ tenantId: "T", farmId: "F", plotId: "P" });
  const before = JSON.stringify(assessment);
  const sample = observation("o-1", "2026-10-30T11:00:00Z");
  const next = appendOperationalTelemetry(base, sample);
  assert.equal(base.observations.length, 0);
  assert.equal(next.observations.length, 1);
  assert.equal(Object.isFrozen(next.observations), true);
  assert.equal(JSON.stringify(assessment), before);
  assert.strictEqual(appendOperationalTelemetry(next, sample), next);
  assert.throws(() => appendOperationalTelemetry(next, { ...sample, value: 19 }), /collision/);
  assert.throws(() => appendOperationalTelemetry(next, { ...sample, manifestMembership: true }), /cannot_assert/);
  assert.throws(() => appendOperationalTelemetry(next, { ...sample, certified: true }), /cannot_assert/);
  assert.throws(() => appendOperationalTelemetry(next, { ...sample, certificationStatus: S.CERTIFIED_MANIFEST }), /cannot_assert/);
});

test("stream is bounded without editing older immutable buffers", () => {
  let stream = createLiveTelemetryStream({ tenantId: "T", farmId: "F", plotId: "P" });
  const initial = stream;
  for (let i = 0; i < 4; i++) {
    stream = appendOperationalTelemetry(stream, observation("obs-" + i, "2026-10-30T11:00:00Z"), 2);
  }
  assert.equal(initial.observations.length, 0);
  assert.deepEqual(stream.observations.map(x => x.id), ["obs-2", "obs-3"]);
});
