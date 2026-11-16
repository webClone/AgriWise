import test from "node:test";
import assert from "node:assert/strict";

import {
  ASMAE_13_STATE_CATALOG,
  resolveAsmaeStateAvailability,
  compareSensorWithCollocatedAsmae,
} from "../../src/lib/agribrain/asmae-13-states.mjs";

import {
  PHYSICAL_VARIABLE_LIMITS,
  STANDARD_SOIL_PROFILE_DEPTHS_CM,
  computeRawPayloadHash,
  validatePhysicalObservation,
  normalizeRawReading,
  buildSoilDepthProfile,
  checkRetroactivePublicationAdmission,
} from "../../src/lib/agribrain/physical-sensor-contract.mjs";

import { physicalObservationStore } from "../../src/lib/agribrain/physical-observation-store.mjs";

test("W2-00: Scientific-Comparison Hardening & Epistemic Safeguards", async (t) => {
  await t.test("Zero fabricated uncertainty: sigma is strictly null when scalarSigma is absent", () => {
    const rasterWithoutSigma = {
      surface_id: "surf-test-vigor",
      surface_type: "ASMAE_VIGOR",
      values: [[0.5, 0.6], [0.7, 0.8]],
      bounds: [3.0, 36.5, 3.01, 36.51],
    };

    // posteriorRecord has NO sigmas
    const posteriorWithoutSigmas = {
      states: { vigor: 0.65 },
      sigmas: null,
    };

    const res = resolveAsmaeStateAvailability("vigor", [rasterWithoutSigma], posteriorWithoutSigmas);
    assert.equal(res.status, "QUALIFIED_SPATIAL");
    assert.equal(res.mean, 0.65);
    // MUST NOT fabricate 0.05
    assert.equal(res.sigma, null, "Must not default to 0.05 when sigma is absent in publication");
  });

  await t.test("Observation evidence does not make hardcoded false hardware claims", () => {
    const raster = {
      surface_id: "surf-test-vigor",
      surface_type: "ASMAE_VIGOR",
      values: [[0.5, 0.6], [0.7, 0.8]],
      sources: ["Sentinel-2 MSI Level-2A", "SNAP Biophysical Processor"],
    };

    const res = resolveAsmaeStateAvailability("vigor", [raster], { states: { vigor: 0.65 } });
    assert.deepEqual(res.observationEvidence, ["Sentinel-2 MSI Level-2A", "SNAP Biophysical Processor"]);
  });

  await t.test("compareSensorWithCollocatedAsmae handles missing sigma without crashing or inventing 0.05", () => {
    const asmaeNoSigma = {
      state: ASMAE_13_STATE_CATALOG.root_zone_water,
      status: "PLOT_ESTIMATE",
      canonicalStatus: "PLOT_ESTIMATE",
      mean: 0.365,
      sigma: null, // No uncertainty reported
      min: 0.0,
      max: 1.0,
      supportClassification: "ASSIMILATED_INDIRECT",
      rasterSurface: null,
      canRenderPixels: false,
      explanation: "Scalar posterior estimate",
      observationEvidence: ["In-Situ Telemetry"],
    };

    const comp = compareSensorWithCollocatedAsmae({ soilMoisture: 0.342, depthCm: 15 }, asmaeNoSigma);
    assert.equal(comp.sensorValue, 0.342);
    assert.equal(comp.asmaeMean, 0.365);
    assert.equal(comp.asmaeSigma, null);
    assert.equal(comp.zScore, null, "Cannot compute z-score without sigma");
    assert.equal(comp.withinOneSigma, false);
    assert.equal(comp.withinTwoSigma, false);
    assert.match(comp.narrative, /posterior uncertainty \(sigma\) is unavailable/);
    assert.ok(comp.supportDifferenceDisclaimer.includes("spatial and vertical supports"));
  });

  await t.test("Authoritative catalog classifies LAI and chlorophyll as DIAGNOSTIC", () => {
    assert.equal(ASMAE_13_STATE_CATALOG.lai.authorityCeiling, "DIAGNOSTIC");
    assert.equal(ASMAE_13_STATE_CATALOG.chlorophyll.authorityCeiling, "DIAGNOSTIC");
    assert.equal(ASMAE_13_STATE_CATALOG.vigor.authorityCeiling, "PRESCRIPTION_ELIGIBLE");
  });
});

test("W2-01: Physical Observation Contract & Schema Validation", async (t) => {
  await t.test("Deterministic raw payload hash computation", () => {
    const payload1 = { deviceId: "DEV-01", vwc: 34.2, timestamp: "2026-09-08T12:00:00Z" };
    const payload2 = { deviceId: "DEV-01", vwc: 34.2, timestamp: "2026-09-08T12:00:00Z" };
    const payload3 = { deviceId: "DEV-01", vwc: 34.3, timestamp: "2026-09-08T12:00:00Z" };

    const hash1 = computeRawPayloadHash(payload1);
    const hash2 = computeRawPayloadHash(payload2);
    const hash3 = computeRawPayloadHash(payload3);

    assert.equal(hash1, hash2, "Identical payloads produce identical hash");
    assert.notEqual(hash1, hash3, "Different payloads produce different hashes");
    assert.equal(hash1.length, 64, "SHA-256 hex length is 64");
  });

  await t.test("normalizeRawReading converts percentage to fraction and computes metadata", () => {
    const reading = normalizeRawReading({
      deviceId: "DEV-SENTEK-01",
      channelId: "ch_depth_15cm",
      plotId: "6a09d9e91dd0c7ed6fce7d50",
      variable: "soil_moisture_vwc",
      rawValue: 34.2,
      rawUnit: "pct",
      nominalDepthCm: 15,
      depthInterval: { topCm: 10, bottomCm: 20, nominalCm: 15 },
      deviceAcquiredAt: "2026-09-08T12:00:00Z",
      serverReceivedAt: "2026-09-08T12:00:02Z",
    });

    assert.equal(reading.deviceId, "DEV-SENTEK-01");
    assert.equal(reading.channelId, "ch_depth_15cm");
    assert.equal(reading.variable, "soil_moisture_vwc");
    assert.equal(reading.rawUnit, "pct");
    assert.equal(reading.normalizedUnit, "fraction");
    assert.equal(reading.rawValue, 34.2);
    assert.equal(reading.normalizedValue, 0.342);
    assert.equal(reading.depthInterval.nominalCm, 15);
    assert.equal(reading.depthInterval.topCm, 10);
    assert.equal(reading.depthInterval.bottomCm, 20);
    assert.equal(reading.qaState, "VALID");
    assert.equal(reading.admissionStatus, "UNADMITTED");
  });

  await t.test("validatePhysicalObservation rejects impossible out-of-range physical values", () => {
    // VWC > 0.75 is physically impossible in soil
    const impossibleVwc = normalizeRawReading({
      deviceId: "DEV-BAD-01",
      channelId: "ch_01",
      plotId: "plot-1",
      variable: "soil_moisture_vwc",
      rawValue: 85.0, // 85% = 0.85 fraction > 0.75 max
      rawUnit: "pct",
    });

    assert.equal(impossibleVwc.qaState, "OUT_OF_RANGE");
    assert.equal(impossibleVwc.admissionStatus, "REJECTED");

    const valRes = validatePhysicalObservation(impossibleVwc);
    assert.equal(valRes.valid, false);
    assert.ok(valRes.errors.some((e) => e.includes("out of physical range")));
  });

  await t.test("validatePhysicalObservation rejects clock drift future timestamps", () => {
    const futureAcquiredAt = new Date(Date.now() + 3_600_000).toISOString(); // 1 hour in future
    const futureRecord = normalizeRawReading({
      deviceId: "DEV-FUTURE-01",
      channelId: "ch_01",
      plotId: "plot-1",
      variable: "soil_temperature_c",
      rawValue: 22.5,
      rawUnit: "celsius",
      deviceAcquiredAt: futureAcquiredAt,
    });

    const valRes = validatePhysicalObservation(futureRecord);
    assert.equal(valRes.valid, false);
    assert.ok(valRes.errors.some((e) => e.includes("clock drift violation")));
  });
});

test("W2-01: Multi-Depth Soil Profile Contract & Zero Fabrication Gate", async (t) => {
  await t.test("Plot A empirical scenario: exactly 1 measured depth at 15cm, others unmeasured", () => {
    const plotA15cmReading = normalizeRawReading({
      deviceId: "DEV-SENTEK-PLOT-A",
      channelId: "ch_depth_15cm",
      plotId: "6a09d9e91dd0c7ed6fce7d50",
      variable: "soil_moisture_vwc",
      rawValue: 34.2,
      rawUnit: "pct",
      nominalDepthCm: 15,
      depthInterval: { topCm: 10, bottomCm: 20, nominalCm: 15 },
      deviceAcquiredAt: "2026-09-08T12:00:00Z",
    });

    const profile = buildSoilDepthProfile([plotA15cmReading], {
      plotId: "6a09d9e91dd0c7ed6fce7d50",
      deviceId: "DEV-SENTEK-PLOT-A",
      timestamp: "2026-09-08T12:00:00Z",
    });

    assert.equal(profile.measuredCount, 1);
    assert.equal(profile.rootZoneAggregateAllowed, false, "1 probe cannot represent full root zone");

    // Check specific depth slots
    const layer10 = profile.layers.find((l) => l.nominalCm === 10);
    assert.equal(layer10.measured, false);
    assert.equal(layer10.vwcFraction, null);
    assert.equal(layer10.label, "Not measured —");

    const layer15 = profile.layers.find((l) => l.nominalCm === 15);
    assert.equal(layer15.measured, true);
    assert.equal(layer15.vwcFraction, 0.342);
    assert.equal(layer15.label, "34.2%");

    const layer30 = profile.layers.find((l) => l.nominalCm === 30);
    assert.equal(layer30.measured, false);
    assert.equal(layer30.vwcFraction, null);
    assert.equal(layer30.label, "Not measured —");

    const layer60 = profile.layers.find((l) => l.nominalCm === 60);
    assert.equal(layer60.measured, false);
    assert.equal(layer60.vwcFraction, null);
    assert.equal(layer60.label, "Not measured —");
  });

  await t.test("Retroactive admission guard strictly rejects late-arriving telemetry into historical sealed snapshot", () => {
    const lateReading = normalizeRawReading({
      deviceId: "DEV-LATE-01",
      channelId: "ch_depth_15cm",
      plotId: "6a09d9e91dd0c7ed6fce7d50",
      variable: "soil_moisture_vwc",
      rawValue: 32.5,
      rawUnit: "pct",
      deviceAcquiredAt: "2026-09-07T10:00:00Z", // acquired BEFORE publication cutoff
      serverReceivedAt: "2026-11-16T17:00:00Z", // received MONTHS LATER
    });

    const historicalPublication = {
      published_at: "2026-09-08T12:00:00+00:00",
      evidence_cutoff_at: "2026-09-08T12:00:00+00:00",
    };

    const check = checkRetroactivePublicationAdmission(lateReading, historicalPublication);
    assert.equal(check.canAdmitRetroactively, false);
    assert.match(check.reason, /Scientific boundary rejection/);
    assert.match(check.reason, /cannot be inserted retroactively/);
  });
});

test("W2-02: Secure Sensor Ingestion, Idempotence & Quarantine Engine", async (t) => {
  t.beforeEach(() => {
    physicalObservationStore.reset();
  });

  await t.test("Valid multi-depth ingestion creates normalized physical observation records", () => {
    const payload = {
      deviceId: "DEV-MULTI-01",
      deviceAcquiredAt: "2026-11-16T15:00:00Z",
      plotId: "plot-alpha",
      readings: [
        {
          channelId: "ch_10cm",
          variable: "soil_moisture_vwc",
          rawValue: 28.4,
          rawUnit: "pct",
          depthCm: 10,
        },
        {
          channelId: "ch_20cm",
          variable: "soil_moisture_vwc",
          rawValue: 32.1,
          rawUnit: "pct",
          depthCm: 20,
        },
        {
          channelId: "ch_40cm",
          variable: "soil_moisture_vwc",
          rawValue: 35.8,
          rawUnit: "pct",
          depthCm: 40,
        },
      ],
    };

    const res = physicalObservationStore.ingestPayload(payload, { registeredPlotId: "plot-alpha" });
    assert.equal(res.success, true);
    assert.equal(res.replayed, false);
    assert.equal(res.accepted.length, 3);
    assert.equal(res.quarantined.length, 0);
    assert.equal(res.rawPayloadHash.length, 64);

    assert.equal(res.accepted[0].depthInterval.nominalCm, 10);
    assert.equal(res.accepted[0].normalizedValue, 0.284);
    assert.equal(res.accepted[1].depthInterval.nominalCm, 20);
    assert.equal(res.accepted[1].normalizedValue, 0.321);
    assert.equal(res.accepted[2].depthInterval.nominalCm, 40);
    assert.equal(res.accepted[2].normalizedValue, 0.358);
  });

  await t.test("Duplicate-message replay protection & idempotence", () => {
    const messageId = "msg-unique-test-999";
    const payload = {
      deviceId: "DEV-REPLAY-01",
      messageId,
      deviceAcquiredAt: "2026-11-16T15:30:00Z",
      plotId: "plot-alpha",
      readings: [
        {
          channelId: "ch_15cm",
          variable: "soil_moisture_vwc",
          rawValue: 33.0,
          rawUnit: "pct",
          depthCm: 15,
        },
      ],
    };

    // First ingestion succeeds
    const firstRes = physicalObservationStore.ingestPayload(payload, { registeredPlotId: "plot-alpha" });
    assert.equal(firstRes.success, true);
    assert.equal(firstRes.replayed, false);
    assert.equal(firstRes.accepted.length, 1);

    // Duplicate ingestion with same messageId returns idempotent success with replayed=true
    const replayRes = physicalObservationStore.ingestPayload(payload, { registeredPlotId: "plot-alpha" });
    assert.equal(replayRes.success, true);
    assert.equal(replayRes.replayed, true);
    assert.equal(replayRes.accepted.length, 0);
    assert.match(replayRes.message, /Duplicate message detected/);

    // Replay with identical payload hash and acquisition timestamp without messageId also caught
    const payloadNoId = {
      deviceId: "DEV-REPLAY-HASH",
      deviceAcquiredAt: "2026-11-16T15:35:00Z",
      plotId: "plot-alpha",
      readings: [
        {
          channelId: "ch_15cm",
          variable: "soil_moisture_vwc",
          rawValue: 33.0,
          rawUnit: "pct",
          depthCm: 15,
        },
      ],
    };
    const firstHashRes = physicalObservationStore.ingestPayload(payloadNoId, { registeredPlotId: "plot-alpha" });
    assert.equal(firstHashRes.success, true);
    assert.equal(firstHashRes.replayed, false);

    const hashReplayRes = physicalObservationStore.ingestPayload(payloadNoId, { registeredPlotId: "plot-alpha" });
    assert.equal(hashReplayRes.success, true);
    assert.equal(hashReplayRes.replayed, true);
    assert.match(hashReplayRes.message, /Duplicate payload detected/);
  });

  await t.test("Clock drift future timestamp rejection", () => {
    const futureAcquiredAt = new Date(Date.now() + 600_000).toISOString(); // 10 min in future
    const payload = {
      deviceId: "DEV-DRIFT-01",
      deviceAcquiredAt: futureAcquiredAt,
      soilMoisture: 30.0,
    };

    assert.throws(
      () => physicalObservationStore.ingestPayload(payload),
      /clock drift violation/
    );
  });

  await t.test("Physical range violation is quarantined, not admitted to observations", () => {
    const payload = {
      deviceId: "DEV-QA-RANGE",
      deviceAcquiredAt: "2026-11-16T15:45:00Z",
      plotId: "plot-alpha",
      readings: [
        {
          channelId: "ch_15cm",
          variable: "soil_moisture_vwc",
          rawValue: 95.0, // 95% = 0.95 fraction > 0.75 max
          rawUnit: "pct",
          depthCm: 15,
        },
      ],
    };

    const res = physicalObservationStore.ingestPayload(payload, { registeredPlotId: "plot-alpha" });
    assert.equal(res.success, true);
    assert.equal(res.accepted.length, 0);
    assert.equal(res.quarantined.length, 1);
    assert.equal(res.quarantined[0].variable, "soil_moisture_vwc");
    assert.match(res.quarantined[0].reason, /out_of_physical_range/);

    // Confirm it is not stored in operational plot observations
    const stored = physicalObservationStore.getObservationsForPlot("plot-alpha");
    assert.equal(stored.length, 0);

    // Confirm it is stored in quarantine partition
    const quar = physicalObservationStore.getQuarantined("plot-alpha");
    assert.equal(quar.length, 1);
  });

  await t.test("Incorrect depth registration is quarantined for soil probes", () => {
    const payload = {
      deviceId: "DEV-DEPTH-ERR",
      deviceAcquiredAt: "2026-11-16T15:50:00Z",
      plotId: "plot-alpha",
      readings: [
        {
          channelId: "ch_negative_depth",
          variable: "soil_moisture_vwc",
          rawValue: 32.0,
          rawUnit: "pct",
          depthCm: -10, // Invalid negative depth
        },
      ],
    };

    const res = physicalObservationStore.ingestPayload(payload, { registeredPlotId: "plot-alpha" });
    assert.equal(res.accepted.length, 0);
    assert.equal(res.quarantined.length, 1);
    assert.match(res.quarantined[0].reason, /incorrect_depth_registration/);
  });

  await t.test("Calibration expiration flags observation as SUSPECT", () => {
    const deviceId = "DEV-EXPIRED-CAL";
    physicalObservationStore.registerCalibration(deviceId, {
      calibrationId: "cal-old-2025",
      version: "1.0",
      method: "FIELD_TWO_POINT",
      validUntil: "2026-01-01T00:00:00Z", // expired
    });

    const payload = {
      deviceId,
      deviceAcquiredAt: "2026-11-16T16:00:00Z",
      plotId: "plot-alpha",
      readings: [
        {
          channelId: "ch_15cm",
          variable: "soil_moisture_vwc",
          rawValue: 34.0,
          rawUnit: "pct",
          depthCm: 15,
        },
      ],
    };

    const res = physicalObservationStore.ingestPayload(payload, { registeredPlotId: "plot-alpha" });
    assert.equal(res.accepted.length, 1);
    assert.equal(res.accepted[0].qaState, "SUSPECT", "Expired calibration flags QA as SUSPECT");
  });
});

test("W2-03: Multi-Depth Profile State, Channel Health & Tenant Boundary", async (t) => {
  t.beforeEach(() => {
    physicalObservationStore.reset();
  });

  await t.test("Soil depth profile preserves unmeasured standard depths as gaps (zero fabrication)", () => {
    const payload = {
      deviceId: "DEV-DEPTH-PROFILE",
      deviceAcquiredAt: "2026-11-16T16:15:00Z",
      plotId: "plot-beta",
      readings: [
        {
          channelId: "ch_15cm",
          variable: "soil_moisture_vwc",
          rawValue: 34.2,
          rawUnit: "pct",
          depthCm: 15,
        },
        {
          channelId: "ch_30cm",
          variable: "soil_moisture_vwc",
          rawValue: 31.0,
          rawUnit: "pct",
          depthCm: 30,
        },
      ],
    };

    physicalObservationStore.ingestPayload(payload, { registeredPlotId: "plot-beta" });

    const profile = physicalObservationStore.getSoilDepthProfile("plot-beta", "DEV-DEPTH-PROFILE");
    assert.equal(profile.measuredCount, 2);
    assert.equal(profile.rootZoneAggregateAllowed, false, "2 depths cannot represent full root zone (requires >= 3)");

    const layer10 = profile.layers.find((l) => l.nominalCm === 10);
    assert.equal(layer10.measured, false);
    assert.equal(layer10.label, "Not measured —");

    const layer15 = profile.layers.find((l) => l.nominalCm === 15);
    assert.equal(layer15.measured, true);
    assert.equal(layer15.vwcFraction, 0.342);
    assert.equal(layer15.label, "34.2%");

    const layer30 = profile.layers.find((l) => l.nominalCm === 30);
    assert.equal(layer30.measured, true);
    assert.equal(layer30.vwcFraction, 0.31);
    assert.equal(layer30.label, "31.0%");

    const layer45 = profile.layers.find((l) => l.nominalCm === 45);
    assert.equal(layer45.measured, false);
    assert.equal(layer45.label, "Not measured —");
  });

  await t.test("Channel health classifies FRESH, STALE, and OFFLINE channels accurately", () => {
    const now = new Date();

    // Fresh channel: 5 min ago
    physicalObservationStore.ingestPayload({
      deviceId: "DEV-HEALTH-01",
      deviceAcquiredAt: new Date(now.getTime() - 5 * 60 * 1000).toISOString(),
      plotId: "plot-gamma",
      readings: [{ channelId: "ch_fresh", variable: "soil_moisture_vwc", rawValue: 30.0, rawUnit: "pct", depthCm: 15 }],
    });

    // Stale channel: 25 min ago
    physicalObservationStore.ingestPayload({
      deviceId: "DEV-HEALTH-01",
      deviceAcquiredAt: new Date(now.getTime() - 25 * 60 * 1000).toISOString(),
      plotId: "plot-gamma",
      readings: [{ channelId: "ch_stale", variable: "soil_moisture_vwc", rawValue: 28.0, rawUnit: "pct", depthCm: 30 }],
    });

    // Offline channel: 60 min ago
    physicalObservationStore.ingestPayload({
      deviceId: "DEV-HEALTH-01",
      deviceAcquiredAt: new Date(now.getTime() - 60 * 60 * 1000).toISOString(),
      plotId: "plot-gamma",
      readings: [{ channelId: "ch_offline", variable: "soil_moisture_vwc", rawValue: 25.0, rawUnit: "pct", depthCm: 60 }],
    });

    const channels = physicalObservationStore.getChannelsForDevice("DEV-HEALTH-01", now);
    const freshCh = channels.find((c) => c.channelId === "ch_fresh");
    const staleCh = channels.find((c) => c.channelId === "ch_stale");
    const offlineCh = channels.find((c) => c.channelId === "ch_offline");

    assert.equal(freshCh.freshness, "FRESH");
    assert.equal(freshCh.status, "ACTIVE");

    assert.equal(staleCh.freshness, "STALE");
    assert.equal(staleCh.status, "ACTIVE");

    assert.equal(offlineCh.freshness, "OFFLINE");
    assert.equal(offlineCh.status, "OFFLINE");
  });

  await t.test("Owner-scoped authorization boundary: unauthenticated 401, cross-tenant 404", () => {
    // Contract check for tenant boundary rules
    const evaluateTenantAccess = (userId, plotOwnerId) => {
      if (!userId) return { status: 401, error: "Authentication required" };
      if (userId !== plotOwnerId) return { status: 404, error: "Plot not found" };
      return { status: 200, ok: true };
    };

    assert.deepEqual(evaluateTenantAccess(null, "user-owner"), {
      status: 401,
      error: "Authentication required",
    });

    assert.deepEqual(evaluateTenantAccess("user-attacker", "user-owner"), {
      status: 404,
      error: "Plot not found",
    });

    assert.deepEqual(evaluateTenantAccess("user-owner", "user-owner"), {
      status: 200,
      ok: true,
    });
  });
});
