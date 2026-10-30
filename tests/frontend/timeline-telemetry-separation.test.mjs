import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import * as nodeModule from "node:module";
import {
  TELEMETRY_STATUS as S,
  classifyManifestEvidence,
  classifyTelemetryObservation,
  createLiveTelemetryStream,
  appendOperationalTelemetry,
} from "../../src/lib/agribrain/telemetry-contract.mjs";

let stripTypeScriptTypes = nodeModule.stripTypeScriptTypes;
if (!stripTypeScriptTypes) {
  const ts = (await import("typescript")).default;
  stripTypeScriptTypes = (code) => ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ESNext } }).outputText;
}

const now = "2026-10-30T16:00:00Z";
const cutoff = "2026-10-30T10:00:00Z";
const observation = (id, observedAt, source = "weather_station") => ({
  scope: { tenantId: "T", farmId: "F", plotId: "P" },
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
  assert.throws(() => appendOperationalTelemetry(next, { ...sample, scope: { tenantId: "T", farmId: "F", plotId: "other" } }), /scope_mismatch/);
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

test("timeline mixed-row selects metric value and supplier together without mislabeling forecast", () => {
  const root = process.cwd();
  const timelineSource = fs.readFileSync(path.join(root, "src/components/farm/intelligence/TimelineStrip.tsx"), "utf8");

  const helperStart = timelineSource.indexOf("function classifyTimelineDatum(");
  const helperEnd = timelineSource.indexOf("/* ─── Sparkline", helperStart);
  const helper = stripTypeScriptTypes(timelineSource.slice(helperStart, helperEnd), { mode: "strip" });

  const memoStart = timelineSource.indexOf("const days: DayCell[] = useMemo(() => {") + "const days: DayCell[] = useMemo(() => {".length;
  const memoEnd = timelineSource.indexOf("}, [timeline, assessment, evidenceCutoffAt]);", memoStart);
  const build = stripTypeScriptTypes("function build(timeline:any,assessment:any,evidenceCutoffAt:any){" + timelineSource.slice(memoStart, memoEnd) + "}", { mode: "strip" });

  const buildDays = new Function("classifyTelemetryObservation", "classifyManifestEvidence", "TELEMETRY_STATUS", helper + build + ";return build;")(classifyTelemetryObservation, classifyManifestEvidence, S);

  const today = new Date().toISOString().slice(0, 10);
  const testCutoff = new Date(Date.now() - 86400000).toISOString();
  const weather = { date: today, timestamp: today + "T00:00:00Z", source: "weather_station", temp: 22 };
  const forecast = { date: today + "T12:00:00Z", source: "weather_model", modelId: "forecast-v1", temp: 19, rain_mm: 6, humidity: 75 };

  const select = t => buildDays(t, null, testCutoff).find(x => x.date === today);

  // Mixed row: observed temp (22), forecast rain (6) and humidity (75)
  const mixed = select({ weather: [weather], forecast: [forecast] });
  assert.equal(mixed.values.temp, 22);
  assert.equal(mixed.metricStatuses.temp, S.LIVE_UNCERTIFIED);
  assert.equal(mixed.values.rain, 6);
  assert.equal(mixed.metricStatuses.rain, S.MODEL_FORECAST);
  assert.equal(mixed.values.humidity, 75);
  assert.equal(mixed.metricStatuses.humidity, S.MODEL_FORECAST);

  // C3 visual provenance indicator matches active metric status rather than generic day source
  assert.equal(mixed.metricDotColors.temp, "#4ade80"); // green, observed
  assert.equal(mixed.metricDotColors.rain, "#60a5fa"); // blue, forecast
  assert.equal(mixed.metricDotColors.humidity, "#60a5fa"); // blue, forecast

  // Forecast-only row
  const forecastOnly = select({ forecast: [forecast] });
  assert.equal(forecastOnly.values.rain, 6);
  assert.equal(forecastOnly.metricStatuses.rain, S.MODEL_FORECAST);
  assert.equal(forecastOnly.metricDotColors.rain, "#60a5fa");

  // Complete observation row with valid zero rainfall
  const observedComplete = select({ weather: [{ ...weather, rain: 0, humidity: 60 }], forecast: [forecast] });
  assert.equal(observedComplete.values.rain, 0);
  assert.equal(observedComplete.metricStatuses.rain, S.LIVE_UNCERTIFIED);
  assert.equal(observedComplete.values.humidity, 60);
  assert.equal(observedComplete.metricStatuses.humidity, S.LIVE_UNCERTIFIED);
  assert.equal(observedComplete.metricDotColors.rain, "#4ade80");

  // Missing values yield null and UNVERIFIED with slate indicator
  const missing = select({ weather: [{ date: today, timestamp: today + "T00:00:00Z", source: "weather_station" }] });
  assert.equal(missing.values.rain, null);
  assert.equal(missing.metricStatuses.rain, S.UNVERIFIED);
  assert.equal(missing.values.temp, null);
  assert.equal(missing.metricStatuses.temp, S.UNVERIFIED);
  assert.equal(missing.metricDotColors.rain, "#64748b");
});
