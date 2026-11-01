import test from "node:test";
import assert from "node:assert/strict";
import {
  serializeOperationalTelemetry,
  validateOperationalTelemetryResponse,
} from "../../src/lib/agribrain/operational-telemetry-transport.mjs";
import {
  TELEMETRY_CONTRACT_VERSION as VERSION,
  createLiveTelemetryStream,
  appendOperationalTelemetry,
} from "../../src/lib/agribrain/telemetry-contract.mjs";

const scope = Object.freeze({ tenantId: "owner-A", farmId: "farm-A", plotId: "plot-A" });
const received = new Date("2026-10-30T14:00:00Z");
const acquisition = new Date("2026-10-30T13:30:00Z");
const persisted = new Date("2026-10-30T13:35:00Z");

test("real sensor reads preserve server-time basis; do not invent device acquisition", () => {
  const rows = serializeOperationalTelemetry({
    scope,
    sensorReadings: [{
      id: "reading-1", timestamp: received,
      sensor: { deviceId: "device-1" },
      temperature: 22, rainfall: 0, humidity: null,
    }],
  });
  assert.equal(rows.length, 2);
  assert.equal(rows.find(r => r.metric === "rain").value, 0);
  assert.equal(rows[0].timeBasis, "server_received_at");
  assert.equal(rows[0].observedAt, received.toISOString());
  assert.equal(rows[0].ingestedAt, received.toISOString());
  assert.equal(rows[0].source, "sensor:device-1");
  assert.ok(rows.every(r => !("certified" in r) && !("manifestMembership" in r)));
});

test("plot observations preserve separate acquisition/fetch timestamps", () => {
  const rows = serializeOperationalTelemetry({
    scope,
    plotObservations: [{
      id: "plot-reading-1", source: "weather", obsType: "current_weather",
      obsDate: acquisition, data: { observed_at: acquisition.toISOString() },
      fetchedAt: persisted, tempC: 19, precipMm: 0, et0: 3.5, humidity: null,
    }],
  });
  assert.equal(rows.length, 3);
  assert.equal(rows[0].observedAt, acquisition.toISOString());
  assert.equal(rows[0].ingestedAt, persisted.toISOString());
  assert.equal(rows[0].timeBasis, "source_observation_at");
  assert.equal(rows[0].source, "plot-source:weather");
});

test("legacy daily weather bucket never gains acquisition authority", () => {
  const records = serializeOperationalTelemetry({
    scope, plotObservations: [{
      id: "legacy-weather", source: "weather", obsType: "current_weather",
      obsDate: new Date("2026-10-30T00:00:00Z"),
      fetchedAt: received, data: {}, tempC: 20, precipMm: 0,
    }],
  });
  assert.equal(records.length, 2);
  assert.equal(records[0].timeBasis, "day_bucket_unverified");
  assert.equal(records[0].dayBucketDate, "2026-10-30");
  assert.equal(records[0].value, 20);
  assert.equal(records[1].value, 0);
});

test("response scope and contract validated atomically before buffer writes", () => {
  const items = serializeOperationalTelemetry({
    scope, sensorReadings: [{
      id: "A", timestamp: received, temperature: 23,
      sensor: { deviceId: "d1" },
    }],
  });
  const body = { contractVersion: VERSION, scope, observations: items };
  assert.deepEqual(validateOperationalTelemetryResponse(body, scope, VERSION), items);
  assert.throws(() => validateOperationalTelemetryResponse(
    { ...body, scope: { ...scope, plotId: "plot-B" } }, scope, VERSION,
  ), /scope_or_contract_invalid/);
  assert.throws(() => validateOperationalTelemetryResponse(
    { ...body, observations: [{ ...items[0], scope: { ...scope, tenantId: "owner-B" } }] },
    scope, VERSION,
  ), /observation_invalid/);
  assert.throws(() => validateOperationalTelemetryResponse(
    { ...body, observations: [{ ...items[0], certified: true }] }, scope, VERSION,
  ), /observation_invalid/);
  assert.throws(() => validateOperationalTelemetryResponse(
    { ...body, contractVersion: "wrong" }, scope, VERSION,
  ), /scope_or_contract_invalid/);
});

test("repeated GET projection appends idempotently and keeps old stream immutable", () => {
  const records = serializeOperationalTelemetry({
    scope, sensorReadings: [{
      id: "same-reading", timestamp: received, rainfall: 0,
      sensor: { deviceId: "d1" },
    }],
  });
  const a = createLiveTelemetryStream(scope);
  const b = appendOperationalTelemetry(a, records[0]);
  const c = appendOperationalTelemetry(b, serializeOperationalTelemetry({
    scope, sensorReadings: [{
      id: "same-reading", timestamp: received, rainfall: 0,
      sensor: { deviceId: "d1" },
    }],
  })[0]);
  assert.equal(a.observations.length, 0);
  assert.strictEqual(c, b);
  assert.equal(b.observations[0].value, 0);
});
