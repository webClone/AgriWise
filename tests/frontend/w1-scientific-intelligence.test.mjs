import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  ASMAE_13_STATE_ORDER,
  ASMAE_13_STATE_CATALOG,
  ASMAE_STATUS_META,
  resolveAsmaeStateAvailability,
  sampleSirePixel,
  compareSensorWithCollocatedAsmae,
} from "../../src/lib/agribrain/asmae-13-states.mjs";

import {
  ALL_CANONICAL_SCIENTIFIC_FLAGS,
  validateAuthoritativeScientificValidation,
  classifyCanonicalHeadValidation,
} from "../../src/lib/agribrain/layer10-request-state.mjs";

test("W1-A: Canonical 13 ASMAE States Catalog & Ordering Integrity", async (t) => {
  await t.test("catalog defines exactly 13 canonical states in exact physical order", () => {
    assert.equal(ASMAE_13_STATE_ORDER.length, 13);
    const expectedOrder = [
      "vigor",
      "lai",
      "chlorophyll",
      "canopy_water",
      "root_zone_water",
      "surface_wetness_event",
      "structure",
      "bare_soil_fraction",
      "salinity_stress",
      "thermal_stress",
      "biotic_confounder_risk",
      "phenology_progress",
      "stress_memory",
    ];
    assert.deepEqual(Array.from(ASMAE_13_STATE_ORDER), expectedOrder);
  });

  await t.test("every catalog state has complete scientific metadata and physical limits", () => {
    for (let i = 0; i < ASMAE_13_STATE_ORDER.length; i++) {
      const key = ASMAE_13_STATE_ORDER[i];
      const def = ASMAE_13_STATE_CATALOG[key];
      assert.ok(def, `Missing state definition for ${key}`);
      assert.equal(def.key, key);
      assert.equal(def.order, i + 1);
      assert.ok(def.name && def.name.length > 3);
      assert.ok(def.shortName && def.shortName.length > 0);
      assert.ok(def.unit && def.unit.length > 0);
      assert.ok(Array.isArray(def.range) && def.range.length === 2);
      assert.ok(def.range[0] < def.range[1]);
      assert.ok(["PRESCRIPTION_ELIGIBLE", "DIAGNOSTIC", "MONITORING_ONLY", "VISUALIZATION"].includes(def.authorityCeiling));
      assert.ok(["INDIRECTLY_CONSTRAINED", "PARTIALLY_IDENTIFIED", "HYPOTHESIS_ONLY", "NOT_IDENTIFIED"].includes(def.identifiabilityClass));
      assert.ok(Array.isArray(def.colorRamp) && def.colorRamp.length >= 3);
      assert.ok(def.description && def.description.length > 10);
      assert.ok(def.farmerQuestion && def.farmerQuestion.length > 5);
    }
  });
});

test("W1-A: Derived Availability States (4 Explicit Outcomes)", async (t) => {
  const mockRaster = {
    surface_type: "ASMAE_VIGOR",
    values: [
      [0.45, 0.50, 0.55],
      [0.60, 0.65, 0.70],
    ],
    bounds: [3.0, 36.5, 3.01, 36.51],
  };

  const mockPosterior = {
    states: {
      vigor: 0.575,
      lai: 1.700,
      root_zone_water: 0.365,
    },
    sigmas: {
      vigor: 0.05,
      lai: 0.309,
      root_zone_water: 0.162,
    },
  };

  await t.test("Outcome 1: QUALIFIED_SPATIAL when valid raster surface exists on disk", () => {
    const res = resolveAsmaeStateAvailability("vigor", [mockRaster], mockPosterior);
    assert.equal(res.status, "QUALIFIED_SPATIAL");
    assert.equal(res.canonicalStatus, "QUALIFIED_SPATIAL");
    assert.equal(res.canRenderPixels, true);
    assert.ok(res.rasterSurface !== null);
    assert.equal(res.mean, 0.575);
    assert.equal(res.min, 0.45);
    assert.equal(res.max, 0.70);
    assert.equal(res.supportClassification, "OBSERVED");
  });

  await t.test("Outcome 2: PLOT_ESTIMATE (Scalar Only) - Never fabricates fake raster grids", () => {
    // root_zone_water has scalar posterior but NO spatial raster
    const res = resolveAsmaeStateAvailability("root_zone_water", [mockRaster], mockPosterior);
    assert.equal(res.status, "PLOT_ESTIMATE");
    assert.equal(res.canonicalStatus, "PLOT_ESTIMATE");
    assert.equal(res.canRenderPixels, false);
    assert.equal(res.rasterSurface, null);
    assert.equal(res.mean, 0.365);
    assert.equal(res.sigma, 0.162);
    assert.equal(res.supportClassification, "ASSIMILATED_INDIRECT");
    assert.match(res.explanation, /withheld by truthfulness policy/);
  });

  await t.test("Outcome 3: UNAVAILABLE when neither raster nor scalar estimate exists", () => {
    const res = resolveAsmaeStateAvailability("salinity_stress", [mockRaster], mockPosterior);
    assert.equal(res.status, "UNAVAILABLE");
    assert.equal(res.canonicalStatus, "UNAVAILABLE");
    assert.equal(res.canRenderPixels, false);
    assert.equal(res.mean, null);
    assert.equal(res.sigma, null);
    assert.equal(res.supportClassification, "UNSUPPORTED");
  });

  await t.test("Outcome 4: BLOCKED when publication failed integrity or validation", () => {
    const res = resolveAsmaeStateAvailability("vigor", [mockRaster], mockPosterior, null, {
      validationState: "corrupt",
      blockReason: "Cryptographic validation failure",
    });
    assert.equal(res.status, "BLOCKED");
    assert.equal(res.canonicalStatus, "BLOCKED");
    assert.equal(res.canRenderPixels, false);
    assert.equal(res.rasterSurface, null);
    assert.match(res.explanation, /validation failure/);
  });
});

test("W1-B: SIRE Pixel Inspection & Geographic Sampling", async () => {
  const surface = {
    bounds: [3.0, 36.0, 4.0, 37.0],
    values: [
      [0.1, 0.2],
      [0.3, 0.4],
    ],
  };

  // Center of top-left cell: lng=3.25, lat=36.75 (north-up: row 0 is maxLat)
  const sample1 = sampleSirePixel(surface, [3.25, 36.75]);
  assert.equal(sample1.valid, true);
  assert.equal(sample1.row, 0);
  assert.equal(sample1.col, 0);
  assert.equal(sample1.value, 0.1);

  // Center of bottom-right cell: lng=3.75, lat=36.25
  const sample2 = sampleSirePixel(surface, [3.75, 36.25]);
  assert.equal(sample2.valid, true);
  assert.equal(sample2.row, 1);
  assert.equal(sample2.col, 1);
  assert.equal(sample2.value, 0.4);

  // Coordinate outside bounds fails safely
  const sampleOut = sampleSirePixel(surface, [5.0, 38.0]);
  assert.equal(sampleOut.valid, false);
  assert.equal(sampleOut.value, null);
});

test("W1-C: Collocated In-Situ Telemetry vs. ASMAE Posterior State Comparison", async () => {
  const asmaeAvail = {
    state: ASMAE_13_STATE_CATALOG.root_zone_water,
    status: "PLOT_ESTIMATE",
    canonicalStatus: "PLOT_ESTIMATE",
    mean: 0.365,
    sigma: 0.162,
    min: 0.0475,
    max: 0.6825,
    supportClassification: "ASSIMILATED_INDIRECT",
    rasterSurface: null,
    canRenderPixels: false,
    explanation: "Scalar posterior estimate",
    observationEvidence: ["Sentek FMCW probe 15cm"],
  };

  // Case 1: In-situ moisture reading 0.342 (34.2%) is within 1-sigma of 0.365 +/- 0.162
  const comp1 = compareSensorWithCollocatedAsmae({ soilMoisture: 0.342, depthCm: 15 }, asmaeAvail);
  assert.equal(comp1.sensorEpistemicClass, "OBSERVED_TELEMETRY");
  assert.equal(comp1.asmaeEpistemicClass, "SCIENTIFIC_ESTIMATE");
  assert.equal(comp1.sensorValue, 0.342);
  assert.equal(comp1.asmaeMean, 0.365);
  assert.equal(comp1.asmaeSigma, 0.162);
  assert.equal(comp1.withinOneSigma, true);
  assert.equal(comp1.withinTwoSigma, true);
  assert.match(comp1.narrative, /fully consistent/);

  // Case 2: Divergent reading 0.85 (85%) is outside 2-sigma
  const comp2 = compareSensorWithCollocatedAsmae({ soilMoisture: 0.85, depthCm: 15 }, asmaeAvail);
  assert.equal(comp2.withinOneSigma, false);
  assert.equal(comp2.withinTwoSigma, false);
  assert.match(comp2.narrative, /Local discrepancy detected/);
});

test("W1-D: Complete 11 Scientific Validation Flags Verification", async (t) => {
  await t.test("ALL_CANONICAL_SCIENTIFIC_FLAGS defines all 11 authoritative flags", () => {
    assert.equal(ALL_CANONICAL_SCIENTIFIC_FLAGS.length, 11);
    const expected = [
      "nodeValid",
      "publicationValid",
      "receiptValid",
      "inventoryValid",
      "temporalBindingValid",
      "numericalBindingValid",
      "bindingValid",
      "lineageValid",
      "schemaValid",
      "contractValid",
      "publicationStatusValid",
    ];
    assert.deepEqual(Array.from(ALL_CANONICAL_SCIENTIFIC_FLAGS), expected);
  });

  await t.test("validateAuthoritativeScientificValidation passes when all 11 flags are true", () => {
    const valid11 = {
      nodeValid: true,
      publicationValid: true,
      receiptValid: true,
      inventoryValid: true,
      temporalBindingValid: true,
      numericalBindingValid: true,
      bindingValid: true,
      lineageValid: true,
      schemaValid: true,
      contractValid: true,
      publicationStatusValid: true,
    };
    const res = validateAuthoritativeScientificValidation(valid11);
    assert.equal(res.valid, true);
    assert.equal(res.all11FlagsPresent, true);
    assert.equal(res.missingFlags.length, 0);
    assert.equal(res.failedFlags.length, 0);
    assert.equal(classifyCanonicalHeadValidation(valid11), "valid");
  });

  await t.test("classifyCanonicalHeadValidation fails closed if temporalBindingValid is false", () => {
    const invalidTemporal = {
      nodeValid: true,
      publicationValid: true,
      receiptValid: true,
      inventoryValid: true,
      temporalBindingValid: false,
      numericalBindingValid: true,
      bindingValid: true,
      lineageValid: true,
      schemaValid: true,
      contractValid: true,
      publicationStatusValid: true,
    };
    assert.equal(classifyCanonicalHeadValidation(invalidTemporal), "corrupt");
    const valRes = validateAuthoritativeScientificValidation(invalidTemporal);
    assert.equal(valRes.valid, false);
    assert.deepEqual(valRes.failedFlags, ["temporalBindingValid"]);
  });

  await t.test("classifyCanonicalHeadValidation fails closed if numericalBindingValid is false", () => {
    const invalidNumerical = {
      nodeValid: true,
      publicationValid: true,
      receiptValid: true,
      inventoryValid: true,
      temporalBindingValid: true,
      numericalBindingValid: false,
      bindingValid: true,
      lineageValid: true,
      schemaValid: true,
      contractValid: true,
      publicationStatusValid: true,
    };
    assert.equal(classifyCanonicalHeadValidation(invalidNumerical), "corrupt");
  });
});

test("W1-E: Canonical Empirical Publication L10-SNAP-MITIDJA-202609081200 Integrity", async () => {
  const receiptPath = path.resolve("services/agribrain/artifacts/plot_snapshots/6818982c1a742fa63aa6742cd5f42422/receipts/2766090d5ffa49bfac1b09be90bdc5e8.json");
  assert.ok(fs.existsSync(receiptPath), "Empirical publication receipt must exist on disk");

  const receipt = JSON.parse(fs.readFileSync(receiptPath, "utf8"));
  assert.equal(receipt.snapshot_id, "L10-SNAP-MITIDJA-202609081200");
  assert.equal(receipt.farm_id, "69ad7b6f7e6843e8234afcf6");
  assert.equal(receipt.plot_id, "6a09d9e91dd0c7ed6fce7d50");

  const pubPath = path.resolve("services/agribrain/artifacts/plot_snapshots/6818982c1a742fa63aa6742cd5f42422/publications/2766090d5ffa49bfac1b09be90bdc5e8.json");
  const pub = JSON.parse(fs.readFileSync(pubPath, "utf8"));
  assert.equal(pub.snapshot_id, "L10-SNAP-MITIDJA-202609081200");
  assert.equal(pub.evidence_cutoff_at, "2026-09-08T12:00:00+00:00");
  assert.ok(pub.observation_window && pub.observation_window.start && pub.observation_window.end);
});
