import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import {
  serializeOperationalTelemetry, validateOperationalTelemetryResponse,
} from "../../src/lib/agribrain/operational-telemetry-transport.mjs";
import {
  TELEMETRY_STATUS as S, TELEMETRY_CONTRACT_VERSION,
  classifyTelemetryObservation, createLiveTelemetryStream, appendOperationalTelemetry,
} from "../../src/lib/agribrain/telemetry-contract.mjs";

/**
 * Joined regression: native Python OpenWeather acquisition adapter ->
 * native Python EO promoter Mongo write shape -> actual JS transport ->
 * actual JS classifier/buffer. HTTP and Mongo are intentionally stubbed.
 */
test("qualified provider clock survives acquisition, promotion, serialization, classification", () => {
  const script = resolve(process.cwd(), "tests/fixtures/operational_weather_clock_probe.py");
  const commands = [
    ["python3", [script]], ["python", [script]], ["py", ["-3", script]],
  ];
  let result;
  for (const [bin, args] of commands) {
    const probe = spawnSync(bin, args, {
      cwd: process.cwd(), encoding: "utf8", timeout: 20000,
    });
    if (probe.error?.code === "ENOENT") continue;
    if (probe.status === 0) { result = probe; break; }
    // Windows Store Python stubs may be present but nonfunctional.
    if (/not found|not recognized|not installed/i.test(probe.stderr + probe.stdout)) continue;
    throw new Error("native Python clock probe failed: " + probe.stderr + probe.stdout);
  }
  assert.ok(result, "Python 3 is required to execute the joined EO provenance test");
  const marker = result.stdout.split(/\r?\n/).find(line => line.startsWith("__CLOCK_JSON__"));
  assert.ok(marker, "native fixture must emit clock receipt");
  const receipt = JSON.parse(marker.slice("__CLOCK_JSON__".length));
  const scope = { tenantId: "owner-A", farmId: "farm-A", plotId: "507f1f77bcf86cd799439011" };
  const all = serializeOperationalTelemetry({
    scope, plotObservations: Object.values(receipt.rows),
  });
  assert.equal(all.length, 6, "temperature zero and humidity 70 survive for each acquisition");
  const pick = name => all.find(item => item.id === "plot-observation:weather-" + name + ":temp");
  const live = pick("live"), late = pick("late"), legacy = pick("legacy");
  assert.equal(live.value, 0);
  assert.equal(live.observedAt, "2026-10-31T14:00:00.000Z");
  assert.equal(live.ingestedAt, "2026-10-31T14:01:00.000Z");
  assert.equal(live.timeBasis, "source_observation_at");
  assert.equal(live.dayBucketDate, "2026-10-31");
  assert.equal(classifyTelemetryObservation(live, receipt.cutoff, receipt.now), S.LIVE_UNCERTIFIED);
  assert.equal(late.observedAt, "2026-10-31T09:00:00.000Z");
  assert.equal(late.timeBasis, "source_observation_at");
  assert.equal(classifyTelemetryObservation(late, receipt.cutoff, receipt.now), S.LATE_ARRIVING_UNADMITTED);
  assert.equal(legacy.observedAt, "2026-10-31T00:00:00.000Z");
  assert.equal(legacy.timeBasis, "day_bucket_unverified");
  assert.equal(classifyTelemetryObservation(legacy, receipt.cutoff, receipt.now), S.UNVERIFIED);
  assert.equal(receipt.openMeteoAcquired, "2026-10-31T14:00:00+00:00");
  for (const item of all) {
    assert.notEqual(classifyTelemetryObservation(item, receipt.cutoff, receipt.now), S.CERTIFIED_MANIFEST);
    assert.equal(item.scope.plotId, scope.plotId);
    assert.equal(item.obsType, "current_weather");
  }
  validateOperationalTelemetryResponse(
    { contractVersion: TELEMETRY_CONTRACT_VERSION, scope, observations: all },
    scope, TELEMETRY_CONTRACT_VERSION,
  );
  const prior = createLiveTelemetryStream(scope);
  const current = all.reduce((stream, item) => appendOperationalTelemetry(stream, item), prior);
  assert.equal(prior.observations.length, 0);
  assert.equal(current.observations.length, all.length);
});
