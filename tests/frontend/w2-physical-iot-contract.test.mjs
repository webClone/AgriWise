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
