import assert from "node:assert/strict";
import { test } from "node:test";
import {
  PARCEL_ASSESSMENT_CONTRACT_VERSION,
  computeGeometryHash,
  computeReceiptHash,
  validateAssessmentIdentity,
  createImmutableParcelAssessment,
  isAssessmentStaleForGeometry,
  isAssessmentStaleForCropCycle,
  isLateArrivingEvidence,
} from "../../src/lib/agribrain/parcel-assessment-contract.mjs";

function buildValidIdentity(overrides = {}) {
  const base = {
    tenantId: "tenant-akaloris-01",
    farmId: "farm-haouz-central",
    plotId: "plot-p01-olive",
    cropCycleId: "cycle-2026-autumn",
    publicationId: "pub-r5-98124",
    runId: "run-agribrain-87214",
    snapshotId: "snap-akaloris-v1",
    geometryHash: computeGeometryHash({
      type: "Polygon",
      coordinates: [[[31.6, -7.9], [31.61, -7.9], [31.61, -7.91], [31.6, -7.9]]],
    }),
    observationWindow: {
      start: "2026-10-20T00:00:00Z",
      end: "2026-10-27T23:59:59Z",
    },
    evidenceCutoffAt: "2026-10-28T06:00:00Z",
    publishedAt: "2026-10-28T07:30:00Z",
    contractVersion: PARCEL_ASSESSMENT_CONTRACT_VERSION,
    ...overrides,
  };
  const receiptHash = computeReceiptHash(base);
  return { ...base, receiptHash, ...overrides };
}

test("valid parcel assessment identity passes contract validation", () => {
  const identity = buildValidIdentity();
  const result = validateAssessmentIdentity(identity);
  assert.equal(result.valid, true);
  assert.equal(result.errors.length, 0);
});

test("tampered receipt hash fails closed", () => {
  const identity = buildValidIdentity({ receiptHash: "00000000000000000000000000000000" });
  const result = validateAssessmentIdentity(identity);
  assert.equal(result.valid, false);
  assert.ok(result.errors.includes("receiptHash_mismatch"));
});

test("inverted observation window fails validation", () => {
  const identity = buildValidIdentity({
    observationWindow: {
      start: "2026-10-28T00:00:00Z",
      end: "2026-10-20T00:00:00Z",
    },
  });
  const result = validateAssessmentIdentity(identity);
  assert.equal(result.valid, false);
  assert.ok(result.errors.includes("observationWindow_start_after_end"));
});

test("publishedAt earlier than evidenceCutoffAt fails closed", () => {
  const identity = buildValidIdentity({
    evidenceCutoffAt: "2026-10-28T10:00:00Z",
    publishedAt: "2026-10-28T08:00:00Z",
  });
  const result = validateAssessmentIdentity(identity);
  assert.equal(result.valid, false);
  assert.ok(result.errors.includes("publishedAt_before_evidenceCutoffAt"));
});

test("assessment object is deeply frozen and rejects mutations", () => {
  const identity = buildValidIdentity();
  const assessment = createImmutableParcelAssessment({
    identity,
    canonicalLayerResults: {
      L4: {
        layerId: "L4",
        status: "DEGRADED",
        confidence: 0.55,
        sources: ["SoilGrids 250m", "Regional Pedological Survey"],
      },
    },
    quality: {
      degradationMode: "DEGRADED",
      reliabilityScore: 55,
      warnings: ["Soil baseline lacks field lab test"],
      surfacesGenerated: 4,
      zonesGenerated: 3,
    },
    topFindings: [
      {
        id: "f-1",
        title: "Nitrogen Deficit in Zone 2",
        severity: "medium",
        description: "Zone 2 exhibits lower NDVI correlation",
      },
    ],
  });

  assert.throws(() => {
    // @ts-expect-error test mutation
    assessment.canonicalLayerResults.L4.status = "OK";
  }, TypeError);

  assert.throws(() => {
    // @ts-expect-error test mutation
    assessment.identity.plotId = "other-plot";
  }, TypeError);

  assert.throws(() => {
    // @ts-expect-error test mutation
    assessment.topFindings.push({ id: "f-2", title: "Fake", severity: "low", description: "" });
  }, TypeError);
});

test("late-arriving observation past cutoff is rejected from published assessment", () => {
  const identity = buildValidIdentity({
    evidenceCutoffAt: "2026-10-28T06:00:00Z",
    publishedAt: "2026-10-28T07:00:00Z",
  });

  assert.throws(() => {
    createImmutableParcelAssessment({
      identity,
      canonicalLayerResults: {},
      quality: {
        degradationMode: "NORMAL",
        reliabilityScore: 90,
        warnings: [],
        surfacesGenerated: 1,
        zonesGenerated: 1,
      },
      evidenceTimeline: [
        {
          id: "obs-late-1",
          type: "observation",
          source: "Sentinel-2",
          capturedAt: "2026-10-28T06:30:00Z", // 30 mins after cutoff!
          verified: true,
          summary: "Late image",
        },
      ],
    });
  }, /Late observations cannot be part of published assessment/);
});

test("late arriving evidence detection correctly classifies new telemetry", () => {
  const identity = buildValidIdentity({
    evidenceCutoffAt: "2026-10-28T06:00:00Z",
  });
  assert.equal(isLateArrivingEvidence(identity, "2026-10-28T05:59:00Z"), false);
  assert.equal(isLateArrivingEvidence(identity, "2026-10-28T06:01:00Z"), true);
});

test("geometry change invalidates assessment reuse", () => {
  const originalPoly = {
    type: "Polygon",
    coordinates: [[[31.6, -7.9], [31.61, -7.9], [31.61, -7.91], [31.6, -7.9]]],
  };
  const identity = buildValidIdentity({
    geometryHash: computeGeometryHash(originalPoly),
  });

  assert.equal(isAssessmentStaleForGeometry(identity, originalPoly), false);

  const editedPoly = {
    type: "Polygon",
    coordinates: [[[31.6, -7.9], [31.62, -7.9], [31.62, -7.92], [31.6, -7.9]]],
  };
  assert.equal(isAssessmentStaleForGeometry(identity, editedPoly), true);
});

test("crop cycle change invalidates assessment reuse", () => {
  const identity = buildValidIdentity({
    cropCycleId: "cycle-olive-2025",
  });

  assert.equal(isAssessmentStaleForCropCycle(identity, "cycle-olive-2025"), false);
  assert.equal(isAssessmentStaleForCropCycle(identity, "cycle-wheat-2026"), true);
  assert.equal(isAssessmentStaleForCropCycle(identity, null), true);
});
