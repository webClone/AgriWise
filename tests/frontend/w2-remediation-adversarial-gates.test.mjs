import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

import {
  PHYSICAL_VARIABLE_LIMITS,
  STANDARD_SOIL_PROFILE_DEPTHS_CM,
  computeRawPayloadHash,
  validatePhysicalObservation,
  normalizeRawReading,
  buildSoilDepthProfile,
  checkRetroactivePublicationAdmission,
} from "../../src/lib/agribrain/physical-sensor-contract.mjs";

import {
  PhysicalObservationStore,
} from "../../src/lib/agribrain/physical-observation-store.mjs";

import {
  compareSensorWithCollocatedAsmae,
} from "../../src/lib/agribrain/asmae-13-states.mjs";

// Helper to create clean temporary storage directories for adversarial tests
function makeTestStore() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "w2-sensor-store-test-"));
  const store = new PhysicalObservationStore({ storageDir: tmpDir, autoRehydrate: false });
  return { store, tmpDir };
}

test("Gate A: Durable Observation Truth & Ingestion Correctness", async (t) => {
  await t.test("Multi-worker concurrent submission of identical message achieves exact idempotent persistence", async () => {
    const { store, tmpDir } = makeTestStore();
    try {
      const messageId = "MSG-CONCUR-001";
      const payload = {
        deviceId: "DEV-CONCUR-01",
        messageId,
        plotId: "plot-concur-test",
        deviceAcquiredAt: "2026-11-16T12:00:00Z",
        readings: [
          { channelId: "ch_15", variable: "soil_moisture_vwc", rawValue: 32.5, rawUnit: "pct", depthCm: 15 },
          { channelId: "ch_30", variable: "soil_moisture_vwc", rawValue: 28.0, rawUnit: "pct", depthCm: 30 },
        ],
      };

      // Simulate 5 concurrent workers attempting ingestion of identical message
      const results = await Promise.all([
        Promise.resolve().then(() => store.ingestPayload(payload)),
        Promise.resolve().then(() => store.ingestPayload(payload)),
        Promise.resolve().then(() => store.ingestPayload(payload)),
        Promise.resolve().then(() => store.ingestPayload(payload)),
        Promise.resolve().then(() => store.ingestPayload(payload)),
      ]);

      // Exactly 1 must have performed initial ingestion, remaining 4 must be replayed: true
      const freshIngests = results.filter((r) => r.success && !r.replayed);
      const replayedIngests = results.filter((r) => r.success && r.replayed);

      assert.equal(freshIngests.length, 1, "Exactly one worker committed fresh message");
      assert.equal(replayedIngests.length, 4, "Four workers received idempotent replay acknowledgement");
      assert.equal(freshIngests[0].accepted.length, 2);

      // Verify durable deduplication file exists
      const dedupFile = path.join(tmpDir, "dedup", "message_registry.json");
      assert.ok(fs.existsSync(dedupFile), "Deduplication registry file created on disk");
      const registryData = JSON.parse(fs.readFileSync(dedupFile, "utf8"));
      assert.ok(registryData.messages[messageId]);
      assert.equal(registryData.messages[messageId].acceptedCount, 2);
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  await t.test("Crash recovery & rehydration: zero state loss across server restarts", async () => {
    const { store: store1, tmpDir } = makeTestStore();
    try {
      const messageId = "MSG-RESTART-001";
      const payload = {
        deviceId: "DEV-RESTART-01",
        messageId,
        plotId: "plot-restart-test",
        deviceAcquiredAt: "2026-11-16T14:00:00Z",
        readings: [
          { channelId: "ch_15cm", variable: "soil_moisture_vwc", rawValue: 33.1, rawUnit: "pct", depthCm: 15 },
          { channelId: "ch_45cm", variable: "soil_moisture_vwc", rawValue: 27.4, rawUnit: "pct", depthCm: 45 },
          { channelId: "ch_bad", variable: "soil_moisture_vwc", rawValue: 99.0, rawUnit: "pct", depthCm: 60 }, // Out of range -> quarantined
        ],
      };

      const res1 = store1.ingestPayload(payload);
      assert.equal(res1.success, true);
      assert.equal(res1.accepted.length, 2);
      assert.equal(res1.quarantined.length, 1);

      // Simulate complete process crash and new server startup pointing to same disk
      const store2 = new PhysicalObservationStore({ storageDir: tmpDir, autoRehydrate: true });

      // 1. Replay check must recognize messageId from disk registry
      const retryRes = store2.ingestPayload(payload);
      assert.equal(retryRes.replayed, true, "New process recognized already-persisted messageId");
      assert.equal(retryRes.success, true);

      // 2. Observations must be rehydrated from disk
      const obs = store2.getObservationsForPlot("plot-restart-test");
      assert.equal(obs.length, 2, "Normalized observations rehydrated from disk");
      assert.equal(obs[0].normalizedValue, 0.331);
      assert.equal(obs[1].normalizedValue, 0.274);

      // 3. Quarantine log must be rehydrated
      const quar = store2.getQuarantined("plot-restart-test");
      assert.equal(quar.length, 1, "Quarantine log rehydrated from disk");
      assert.ok(quar[0].reason.includes("out_of_physical_range"));

      // 4. Channel health must reflect persisted channels
      const channels = store2.getChannelsForDevice("DEV-RESTART-01");
      assert.equal(channels.length, 2);
      const ch15 = channels.find((c) => c.channelId === "ch_15cm");
      assert.ok(ch15);
      assert.equal(ch15.depthCm, 15);
      assert.equal(ch15.latestNormalizedValue, 0.331);
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  await t.test("Atomic transaction failure: DB write abort prevents false replay acknowledgement (W2-R02)", async () => {
    const { store, tmpDir } = makeTestStore();
    try {
      const messageId = "MSG-DBFAIL-001";
      const payload = {
        deviceId: "DEV-DBFAIL-01",
        messageId,
        plotId: "plot-dbfail",
        deviceAcquiredAt: "2026-11-16T15:00:00Z",
        readings: [
          { channelId: "ch_15", variable: "soil_moisture_vwc", rawValue: 31.0, rawUnit: "pct", depthCm: 15 },
        ],
      };

      // Prepare ingest without committing
      const prepared = store.prepareIngest(payload);
      assert.equal(prepared.accepted.length, 1);
      assert.equal(prepared.isCommitted, false);

      // Simulate DB write failure -> commit is NEVER called
      // Then client retries the same message:
      const preparedRetry = store.prepareIngest(payload);
      assert.equal(preparedRetry.replayed, false, "Retry does NOT return false replay when previous DB failed");
      assert.equal(preparedRetry.accepted.length, 1);

      // Now DB succeeds, so commit is executed:
      const commitRes = store.commitIngest(preparedRetry);
      assert.equal(commitRes.success, true);
      assert.equal(commitRes.replayed, false);

      // Subsequent attempt now succeeds as idempotent replay
      const thirdAttempt = store.ingestPayload(payload);
      assert.equal(thirdAttempt.replayed, true, "Only truly committed message returns replayed: true");
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  await t.test("MessageId reuse with conflicting payload bytes triggers 409 Conflict & quarantine (W2-R03)", async () => {
    const { store, tmpDir } = makeTestStore();
    try {
      const messageId = "MSG-COLLISION-001";
      const payloadOriginal = {
        deviceId: "DEV-COLLISION-01",
        messageId,
        plotId: "plot-collision",
        deviceAcquiredAt: "2026-11-16T16:00:00Z",
        readings: [
          { channelId: "ch_15", variable: "soil_moisture_vwc", rawValue: 32.0, rawUnit: "pct", depthCm: 15 },
        ],
      };

      const res1 = store.ingestPayload(payloadOriginal);
      assert.equal(res1.success, true);
      assert.equal(res1.replayed, false);

      // Same messageId with DIFFERENT payload bytes (conflicting values)
      const payloadConflicting = {
        deviceId: "DEV-COLLISION-01",
        messageId,
        plotId: "plot-collision",
        deviceAcquiredAt: "2026-11-16T16:00:00Z",
        readings: [
          { channelId: "ch_15", variable: "soil_moisture_vwc", rawValue: 48.5, rawUnit: "pct", depthCm: 15 }, // Different value!
        ],
      };

      const res2 = store.ingestPayload(payloadConflicting);
      assert.equal(res2.success, false, "Conflicting payload digest must NOT succeed");
      assert.equal(res2.conflict, true, "Conflicting messageId flagged with conflict: true");
      assert.ok(res2.error.includes("409 Conflict"), "Returns 409 Conflict status error");

      // Verify conflict recorded in quarantine
      const quar = store.getQuarantined("plot-collision");
      assert.ok(quar.length >= 1);
      const conflictQuar = quar.find((q) => q.reason.includes("conflicting_message_payload_digest"));
      assert.ok(conflictQuar, "Conflicting messageId event recorded in quarantine log");
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  await t.test("Strict unit normalization: magnitude is never guessed (W2-R08)", () => {
    // 0.5 with pct unit must be 0.005 (0.5%), NOT 50%
    const p1 = normalizeRawReading({
      deviceId: "DEV-UNIT-01",
      channelId: "ch_1",
      plotId: "plot-1",
      variable: "soil_moisture_vwc",
      rawValue: 0.5,
      rawUnit: "pct",
      nominalDepthCm: 15,
      deviceAcquiredAt: "2026-11-16T12:00:00Z",
    });
    assert.equal(p1.normalizedValue, 0.005, "0.5% normalized to 0.005 fraction");
    assert.equal(p1.qaState, "VALID");

    // 34.2 with pct unit must be 0.342
    const p2 = normalizeRawReading({
      deviceId: "DEV-UNIT-01",
      channelId: "ch_1",
      plotId: "plot-1",
      variable: "soil_moisture_vwc",
      rawValue: 34.2,
      rawUnit: "pct",
      nominalDepthCm: 15,
      deviceAcquiredAt: "2026-11-16T12:00:00Z",
    });
    assert.equal(p2.normalizedValue, 0.342, "34.2% normalized to 0.342 fraction");

    // 0.342 with fraction unit must be 0.342
    const p3 = normalizeRawReading({
      deviceId: "DEV-UNIT-01",
      channelId: "ch_1",
      plotId: "plot-1",
      variable: "soil_moisture_vwc",
      rawValue: 0.342,
      rawUnit: "fraction",
      nominalDepthCm: 15,
      deviceAcquiredAt: "2026-11-16T12:00:00Z",
    });
    assert.equal(p3.normalizedValue, 0.342, "0.342 fraction preserved as 0.342");

    // Unrecognized unit must be flagged SUSPECT / quarantined
    const p4 = normalizeRawReading({
      deviceId: "DEV-UNIT-01",
      channelId: "ch_1",
      plotId: "plot-1",
      variable: "soil_moisture_vwc",
      rawValue: 25.0,
      rawUnit: "invalid_unregistered_unit",
      nominalDepthCm: 15,
      deviceAcquiredAt: "2026-11-16T12:00:00Z",
    });
    assert.equal(p4.qaState, "SUSPECT", "Unrecognized unit flagged as SUSPECT");
    assert.ok(p4.qaDetails.reason.includes("Unrecognized unit"));
  });

  await t.test("All-quarantined payload suppresses active observation state (W2-R04)", () => {
    const { store, tmpDir } = makeTestStore();
    try {
      const payload = {
        deviceId: "DEV-ALLQUAR-01",
        messageId: "MSG-ALLQUAR-01",
        plotId: "plot-allquar",
        deviceAcquiredAt: "2026-11-16T12:00:00Z",
        readings: [
          { channelId: "ch_1", variable: "soil_moisture_vwc", rawValue: 98.0, rawUnit: "pct", depthCm: 15 }, // Out of range
          { channelId: "ch_2", variable: "soil_moisture_vwc", rawValue: -5.0, rawUnit: "pct", depthCm: 30 }, // Out of range
        ],
      };

      const res = store.ingestPayload(payload);
      assert.equal(res.success, true);
      assert.equal(res.allQuarantined, true, "allQuarantined flag is true");
      assert.equal(res.accepted.length, 0, "Zero accepted readings");
      assert.equal(res.quarantined.length, 2, "Two quarantined readings");

      const obs = store.getObservationsForPlot("plot-allquar");
      assert.equal(obs.length, 0, "No observations added to plot ledger");

      const profile = store.getSoilDepthProfile("plot-allquar", "DEV-ALLQUAR-01");
      assert.equal(profile.measuredCount, 0, "Profile has 0 measured depths");
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  await t.test("Acquisition-time ordering: delayed older arrivals do not overwrite latest seen (W2-R11)", () => {
    const { store, tmpDir } = makeTestStore();
    try {
      // 1. Ingest reading acquired at 14:00:00Z
      store.ingestPayload({
        deviceId: "DEV-ORDER-01",
        messageId: "MSG-ORDER-01",
        plotId: "plot-order",
        deviceAcquiredAt: "2026-11-16T14:00:00Z",
        readings: [
          { channelId: "ch_15", variable: "soil_moisture_vwc", rawValue: 30.0, rawUnit: "pct", depthCm: 15 },
        ],
      });

      let channels = store.getChannelsForDevice("DEV-ORDER-01");
      assert.equal(channels[0].lastSeen, "2026-11-16T14:00:00.000Z");
      assert.equal(channels[0].latestNormalizedValue, 0.3);

      // 2. Delayed older message acquired at 13:00:00Z arrives later
      store.ingestPayload({
        deviceId: "DEV-ORDER-01",
        messageId: "MSG-ORDER-02",
        plotId: "plot-order",
        deviceAcquiredAt: "2026-11-16T13:00:00Z", // 1 hour OLDER!
        readings: [
          { channelId: "ch_15", variable: "soil_moisture_vwc", rawValue: 22.0, rawUnit: "pct", depthCm: 15 },
        ],
      });

      channels = store.getChannelsForDevice("DEV-ORDER-01");
      // Channel lastSeen must STILL be 14:00:00Z (NOT 13:00:00Z!)
      assert.equal(channels[0].lastSeen, "2026-11-16T14:00:00.000Z", "Delayed older reading did not overwrite lastSeen");
      assert.equal(channels[0].latestNormalizedValue, 0.3, "Delayed older reading did not overwrite latest value");
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  await t.test("Depth interval preservation without synthetic ±5cm assumption (W2-R09)", () => {
    const reading = normalizeRawReading({
      deviceId: "DEV-INT-01",
      channelId: "ch_int",
      plotId: "plot-int",
      variable: "soil_moisture_vwc",
      rawValue: 32.0,
      rawUnit: "pct",
      depthInterval: { topCm: 25, bottomCm: 35, nominalCm: 30 },
      deviceAcquiredAt: "2026-11-16T12:00:00Z",
    });

    assert.equal(reading.depthInterval.nominalCm, 30);
    assert.equal(reading.depthInterval.topCm, 25);
    assert.equal(reading.depthInterval.bottomCm, 35);

    // When only nominalDepth is provided without interval, topCm = bottomCm = nominalCm (no synthetic ±5cm)
    const reading2 = normalizeRawReading({
      deviceId: "DEV-INT-02",
      channelId: "ch_nominal",
      plotId: "plot-int",
      variable: "soil_moisture_vwc",
      rawValue: 32.0,
      rawUnit: "pct",
      nominalDepthCm: 45,
      deviceAcquiredAt: "2026-11-16T12:00:00Z",
    });

    assert.equal(reading2.depthInterval.nominalCm, 45);
    assert.equal(reading2.depthInterval.topCm, 45, "Exact nominal depth preserved, not ±5cm");
    assert.equal(reading2.depthInterval.bottomCm, 45, "Exact nominal depth preserved, not ±5cm");
  });

  await t.test("Root-Zone Aggregation Gate enforces Layer 0 representativeness (W2-R10)", () => {
    const makeReading = (depthCm, expired = false) =>
      normalizeRawReading({
        deviceId: "DEV-RZ-01",
        channelId: `ch_${depthCm}`,
        plotId: "plot-rz",
        variable: "soil_moisture_vwc",
        rawValue: 30.0,
        rawUnit: "pct",
        nominalDepthCm: depthCm,
        calibration: {
          calibrationId: "CAL-01",
          version: "1.0",
          method: "SOIL_SPECIFIC",
          isExpired: expired,
        },
        deviceAcquiredAt: "2026-11-16T12:00:00Z",
      });

    // Case 1: Only 1 depth (15cm) -> FALSE
    const p1 = buildSoilDepthProfile([makeReading(15)]);
    assert.equal(p1.measuredCount, 1);
    assert.equal(p1.rootZoneAggregateAllowed, false, "1 depth cannot aggregate root zone");

    // Case 2: 3 depths with shallow span (10, 15, 30 -> vertical span = 20cm < 45cm) -> FALSE
    const p2 = buildSoilDepthProfile([makeReading(10), makeReading(15), makeReading(30)]);
    assert.equal(p2.measuredCount, 3);
    assert.equal(p2.rootZoneAggregateAllowed, false, "Span 20cm < 45cm cannot aggregate root zone");

    // Case 3: 3 depths with expired calibration -> FALSE
    const p3 = buildSoilDepthProfile([makeReading(10), makeReading(30), makeReading(60, true)]);
    assert.equal(p3.measuredCount, 3);
    assert.equal(p3.rootZoneAggregateAllowed, false, "Expired calibration prohibits root-zone aggregation");

    // Case 4: 4 depths (10, 30, 45, 60 -> span = 50cm >= 45cm, shallowest = 10 <= 20cm, all valid) -> TRUE
    const p4 = buildSoilDepthProfile([makeReading(10), makeReading(30), makeReading(45), makeReading(60)]);
    assert.equal(p4.measuredCount, 4);
    assert.equal(p4.rootZoneAggregateAllowed, true, "Representative calibrated multi-depth profile allowed to aggregate");
  });
});

test("Gate B: Factual Profile UI & Historical Scientific Identity", async (t) => {
  await t.test("Two fresh depths and four missing depths truly persisted across simulated restart", () => {
    const { store: store1, tmpDir } = makeTestStore();
    try {
      store1.ingestPayload({
        deviceId: "DEV-BENCH-A",
        messageId: "MSG-BENCH-01",
        plotId: "6a09d9e91dd0c7ed6fce7d50",
        deviceAcquiredAt: "2026-11-16T12:00:00Z",
        readings: [
          { channelId: "ch_15", variable: "soil_moisture_vwc", rawValue: 34.2, rawUnit: "pct", depthCm: 15 },
          { channelId: "ch_45", variable: "soil_moisture_vwc", rawValue: 26.8, rawUnit: "pct", depthCm: 45 },
        ],
      });

      // Restart
      const store2 = new PhysicalObservationStore({ storageDir: tmpDir, autoRehydrate: true });
      const profile = store2.getSoilDepthProfile("6a09d9e91dd0c7ed6fce7d50", "DEV-BENCH-A");

      assert.equal(profile.measuredCount, 2);
      assert.equal(profile.layers.find((l) => l.nominalCm === 15).measured, true);
      assert.equal(profile.layers.find((l) => l.nominalCm === 15).vwcFraction, 0.342);
      assert.equal(profile.layers.find((l) => l.nominalCm === 45).measured, true);
      assert.equal(profile.layers.find((l) => l.nominalCm === 45).vwcFraction, 0.268);

      // Exactly four missing depths
      const missingDepths = profile.layers.filter((l) => !l.measured);
      assert.equal(missingDepths.length, 4);
      for (const m of missingDepths) {
        assert.equal(m.vwcFraction, null);
        assert.equal(m.label, "Not measured —");
      }
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  await t.test("15-cm legacy without depth stays unknown (W2-R05)", () => {
    // When a legacy reading has no registered depth interval, depth-profile must NOT invent 15cm
    const emptyStore = new PhysicalObservationStore({ autoRehydrate: false });
    const profile = emptyStore.getSoilDepthProfile("plot-legacy", "DEV-LEGACY-01");
    assert.equal(profile.measuredCount, 0, "No depths invented for empty observation store");
    assert.equal(profile.rootZoneAggregateAllowed, false);
    for (const l of profile.layers) {
      assert.equal(l.measured, false);
      assert.equal(l.vwcFraction, null);
    }
  });

  await t.test("Collocated comparison badge is strictly tri-state (W2-R07 & W2-R14)", () => {
    // 1. Missing sigma -> NOT_COMPARABLE (never false Discrepancy!)
    const c1 = compareSensorWithCollocatedAsmae(
      { soilMoisture: 0.342, depthCm: 15 },
      { mean: 0.32, sigma: null, status: "SCALAR_ONLY", state: { unit: "fraction" } }
    );
    assert.equal(c1.comparisonStatus, "NOT_COMPARABLE");
    assert.equal(c1.withinOneSigma, false);
    assert.ok(c1.narrative.includes("posterior uncertainty (sigma) is unavailable"));

    // 2. Consistent within 1σ -> COMPARABLE
    const c2 = compareSensorWithCollocatedAsmae(
      { soilMoisture: 0.325, depthCm: 15 },
      { mean: 0.320, sigma: 0.020, status: "QUALIFIED_RASTER", state: { unit: "fraction" } }
    );
    assert.equal(c2.comparisonStatus, "COMPARABLE");
    assert.equal(c2.withinOneSigma, true);
    assert.ok(c2.narrative.includes("lying inside the 1σ uncertainty bound"));

    // 3. True statistical divergence > 1σ -> DIVERGENT
    const c3 = compareSensorWithCollocatedAsmae(
      { soilMoisture: 0.450, depthCm: 15 },
      { mean: 0.320, sigma: 0.020, status: "QUALIFIED_RASTER", state: { unit: "fraction" } }
    );
    assert.equal(c3.comparisonStatus, "DIVERGENT");
    assert.equal(c3.withinOneSigma, false);
    assert.ok(c3.narrative.includes("diverges"));
  });

  await t.test("Retroactive admission guard strictly rejects late-arriving telemetry into historical snapshot", () => {
    const lateReading = normalizeRawReading({
      deviceId: "DEV-LATE",
      channelId: "ch_1",
      plotId: "plot-1",
      variable: "soil_moisture_vwc",
      rawValue: 30.0,
      rawUnit: "pct",
      nominalDepthCm: 15,
      deviceAcquiredAt: "2026-09-07T10:00:00Z",
      serverReceivedAt: "2026-11-16T12:00:00Z",
    });

    const historicalPub = {
      published_at: "2026-09-08T12:00:00+00:00",
      evidence_cutoff_at: "2026-09-08T12:00:00+00:00",
    };

    const check = checkRetroactivePublicationAdmission(lateReading, historicalPub);
    assert.equal(check.canAdmitRetroactively, false);
    assert.ok(check.reason.includes("Scientific boundary rejection"));
  });
});
