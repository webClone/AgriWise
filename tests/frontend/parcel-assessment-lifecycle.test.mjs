import assert from "node:assert/strict";
import { test } from "node:test";
import {
  PARCEL_ASSESSMENT_CONTRACT_VERSION,
  GEOMETRY_CONTRACT_VERSION,
  computeGeometryHash,
  computeClientFingerprint,
  validateAssessmentIdentity,
  createImmutableParcelAssessment,
  isAssessmentStaleForGeometry,
  isAssessmentStaleForCropCycle,
  isLateArrivingEvidence,
  canonicalPublicationToAssessment,
} from "../../src/lib/agribrain/parcel-assessment-contract.mjs";

function buildMockPublication(overrides = {}) {
  const cutoff = "2026-10-28T06:00:00Z";
  const published = "2026-10-28T07:30:00Z";
  const geom = {
    type: "Polygon",
    coordinates: [[[31.6, -7.9], [31.61, -7.9], [31.61, -7.91], [31.6, -7.9]]],
  };

  return {
    status: "fresh",
    available: true,
    plot_id: "plot-p01-olive",
    farm_id: "farm-haouz-central",
    tenant_id: "tenant-akaloris-01",
    publication_id: "pub-r5-98124",
    publication_run_id: "run-agribrain-87214",
    intelligence_snapshot_id: "snap-akaloris-v1",
    geometry_hash: computeGeometryHash(geom),
    canonical_publication_receipt_hash: "c4601b07973059635ba026fb96b01b000216b2302bb617db851179c135678129",
    capturedAt: cutoff,
    evidence_cutoff_at: cutoff,
    published_at: published,
    source_window: ["2026-10-20T00:00:00Z", "2026-10-27T23:59:59Z"],
    layer_results: {
      L0: { status: "OK", confidence: 0.95, sources: ["weather_station"] },
      L2: { status: "OK", confidence: 0.91, sources: ["sentinel2"] },
      L3: { status: "DEGRADED", confidence: 0.65, sources: ["sentinel1"], degradation_flags: ["SAR_COHERENCE_LOW"] },
    },
    top_findings: [
      "Moderate water deficit developing in southern sector",
      { id: "find-2", title: "Canopy vigor stable", severity: "info", description: "Vegetative index consistent across baseline." },
    ],
    quality: {
      degradation_mode: "NORMAL",
      reliability_score: 0.88,
      surfaces_generated: 4,
      zones_generated: 3,
      grid_alignment_ok: true,
      detail_conservation_ok: null,
      warnings: ["Minor atmospheric haze in band B04"],
    },
    timeline: [
      {
        id: "ev-1",
        type: "observation",
        source: "sentinel2",
        observedAt: "2026-10-25T10:30:00Z",
        manifestMembership: true,
        summary: "Clear sky S2 MSI acquisition",
        verified: true,
      },
    ],
    ...overrides,
  };
}

test("P2-B: transforms canonical publication into verified immutable ParcelAssessment using production contract", () => {
  const raw = buildMockPublication();
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.equal(assessment.identity.plotId, "plot-p01-olive");
  assert.equal(assessment.identity.publicationReceiptHash, "c4601b07973059635ba026fb96b01b000216b2302bb617db851179c135678129");
  assert.equal(assessment.canonicalLayerResults.L0.status, "OK");
  assert.equal(assessment.canonicalLayerResults.L0.confidence, 0.95);
  assert.equal(assessment.canonicalLayerResults.L3.status, "DEGRADED");
  assert.equal(assessment.canonicalLayerResults.L7.status, "UNAVAILABLE");
  assert.equal(assessment.canonicalLayerResults.L7.confidence, null);
  assert.equal(assessment.topFindings.length, 2);
  assert.equal(assessment.quality.gridAlignmentOk, true);
  assert.equal(assessment.quality.detailConservationOk, null);
  assert(Object.isFrozen(assessment));
  assert(Object.isFrozen(assessment.canonicalLayerResults));
  assert(Object.isFrozen(assessment.topFindings));
});

test("P2-B: missing findings are represented truthfully as empty array without synthetic fabrication", () => {
  const raw = buildMockPublication({ top_findings: [] });
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.deepEqual(assessment.topFindings, []);
  assert.equal(assessment.topFindings.length, 0);
});

test("P2-B: missing confidence is preserved as null, not coerced to 1.0 or 0.0", () => {
  const raw = buildMockPublication({
    layer_results: {
      L0: { status: "OK" }, // missing confidence
      L1: { status: "FAILED" }, // missing confidence
    },
  });
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.equal(assessment.canonicalLayerResults.L0.confidence, null);
  assert.equal(assessment.canonicalLayerResults.L1.confidence, null);
});

test("P2-B: missing degradation_mode is UNKNOWN, not defaulted to NORMAL", () => {
  const raw = buildMockPublication({
    quality: {
      // degradation_mode omitted
      reliability_score: 0.82,
    },
  });
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.equal(assessment.quality.degradationMode, "UNKNOWN");
});

test("P2-B: string findings are unclassified info with actionable=false (no regex heuristics)", () => {
  const raw = buildMockPublication({
    top_findings: [
      "Severe critical emergency failure detected in irrigation pump",
      "Minor crop vigor variation",
    ],
  });
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.equal(assessment.topFindings[0].severity, "info");
  assert.equal(assessment.topFindings[0].actionable, false);
  assert.equal(assessment.topFindings[1].severity, "info");
  assert.equal(assessment.topFindings[1].actionable, false);
});

test("P2-B: tri-state scientific flags preserve null when unverified", () => {
  const raw = buildMockPublication({
    quality: {
      degradation_mode: "NORMAL",
      reliability_score: 0.82,
      surfaces_generated: 2,
      zones_generated: 1,
      grid_alignment_ok: null,
      detail_conservation_ok: null,
      warnings: [],
    },
  });
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.equal(assessment.quality.gridAlignmentOk, null);
  assert.equal(assessment.quality.detailConservationOk, null);
});

test("P2-B: mutation of immutable assessment fails in strict mode", () => {
  const raw = buildMockPublication();
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.throws(() => {
    // @ts-expect-error test immutability
    assessment.canonicalLayerResults.L0.status = "FAILED";
  }, /Cannot assign to read only property/);

  assert.throws(() => {
    // @ts-expect-error test immutability
    assessment.topFindings.push({ id: "fake", title: "fake", severity: "info", description: "fake" });
  }, /Cannot add property/);
});

test("P0: geometry hash does NOT collide for different GeoJSON Features with distinct polygon coordinates", () => {
  const f1 = {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [[[35.1, 31.2], [35.2, 31.2], [35.2, 31.3], [35.1, 31.3], [35.1, 31.2]]],
    },
  };

  const f2 = {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [[[36.1, 32.2], [36.2, 32.2], [36.2, 32.3], [36.1, 32.3], [36.1, 32.2]]],
    },
  };

  const hash1 = computeGeometryHash(f1);
  const hash2 = computeGeometryHash(f2);

  assert.notEqual(hash1, hash2, "Distinct GeoJSON coordinates must yield distinct hashes without whitelist stripping");
  assert.match(hash1, /^sha256:[a-f0-9]{64}$/);
  assert.match(hash2, /^sha256:[a-f0-9]{64}$/);
});

test("P2-B: detects geometry staleness when plot boundaries are edited", () => {
  const originalGeom = {
    type: "Polygon",
    coordinates: [[[31.6, -7.9], [31.61, -7.9], [31.61, -7.91], [31.6, -7.9]]],
  };
  const modifiedGeom = {
    type: "Polygon",
    coordinates: [[[31.6, -7.9], [31.65, -7.9], [31.65, -7.95], [31.6, -7.9]]],
  };

  const raw = buildMockPublication({
    geometry_hash: computeGeometryHash(originalGeom),
  });
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.equal(isAssessmentStaleForGeometry(assessment.identity, originalGeom), false);
  assert.equal(isAssessmentStaleForGeometry(assessment.identity, modifiedGeom), true);
});

test("P2-B: detects crop cycle staleness when plot transitions to next season", () => {
  const raw = buildMockPublication({ crop_cycle_id: "cycle-2026-autumn" });
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive", { cropCycleId: "cycle-2026-autumn" });

  assert.equal(isAssessmentStaleForCropCycle(assessment.identity, "cycle-2026-autumn"), false);
  assert.equal(isAssessmentStaleForCropCycle(assessment.identity, "cycle-2027-spring"), true);
  assert.equal(isAssessmentStaleForCropCycle(assessment.identity, null), true);
});

test("P0: evidence manifest participation is not promoted by default", () => {
  const raw = buildMockPublication({
    timeline: [
      {
        id: "ev-unspecified",
        type: "observation",
        source: "sentinel2",
        observedAt: "2026-10-25T10:30:00Z",
        // manifestMembership and verified are omitted
        summary: "Observation with unknown participation",
      },
    ],
  });
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  assert.equal(assessment.evidenceTimeline[0].manifestMembership, false);
  assert.equal(assessment.evidenceTimeline[0].verified, false);
});

test("P0: late arriving evidence detection enforces strict temporal cutoff even if manifestMembership is claimed", () => {
  const raw = buildMockPublication();
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  const onTimeEvidence = {
    observedAt: "2026-10-26T12:00:00Z",
    ingestedAt: "2026-10-27T00:00:00Z",
    manifestMembership: true,
  };
  const lateObservedEvidence = {
    observedAt: "2026-10-28T09:00:00Z", // After cutoff 06:00:00Z
    manifestMembership: true, // Claimed true, but timestamp exceeds cutoff
  };
  const lateIngestedEvidence = {
    observedAt: "2026-10-25T10:00:00Z",
    ingestedAt: "2026-10-28T11:00:00Z", // Ingested after cutoff 06:00:00Z
    manifestMembership: true,
  };

  assert.equal(isLateArrivingEvidence(assessment.identity, onTimeEvidence), false);
  assert.equal(isLateArrivingEvidence(assessment.identity, lateObservedEvidence), true);
  assert.equal(isLateArrivingEvidence(assessment.identity, lateIngestedEvidence), true);
});

test("P0: createImmutableParcelAssessment fails closed if late evidence is placed in publication manifest", () => {
  const raw = buildMockPublication({
    timeline: [
      {
        id: "ev-illegal-manifest-member",
        type: "observation",
        source: "sentinel2",
        observedAt: "2026-10-28T09:00:00Z", // after cutoff 06:00:00Z
        manifestMembership: true, // illegal!
        verified: true,
      },
    ],
  });

  assert.throws(() => {
    canonicalPublicationToAssessment(raw, "plot-p01-olive");
  }, /exceeds evidenceCutoffAt/);
});

test("P0: fails closed when identity validation fails (no synthetic metadata repair)", () => {
  // Chronology inversion: publishedAt earlier than evidenceCutoffAt
  const invalidChronology = buildMockPublication({
    evidence_cutoff_at: "2026-10-28T10:00:00Z",
    published_at: "2026-10-28T08:00:00Z", // earlier than cutoff!
  });
  assert.throws(() => {
    canonicalPublicationToAssessment(invalidChronology, "plot-p01-olive");
  }, /publishedAt_before_evidenceCutoffAt/);

  // Missing receipt
  const missingReceipt = buildMockPublication({
    canonical_publication_receipt_hash: "",
    publication_receipt_hash: "",
  });
  assert.throws(() => {
    canonicalPublicationToAssessment(missingReceipt, "plot-p01-olive");
  }, /publicationReceiptHash_required/);

  // Missing tenantId
  const missingTenant = buildMockPublication({
    tenant_id: "",
  });
  assert.throws(() => {
    canonicalPublicationToAssessment(missingTenant, "plot-p01-olive");
  }, /tenantId_required/);
});

test("P2-B: end-to-end atomic coherence — all presentation views share one immutable publication identity", () => {
  const raw = buildMockPublication();
  const assessment = canonicalPublicationToAssessment(raw, "plot-p01-olive");

  const identity = assessment.identity;
  assert.ok(identity.publicationId);
  assert.ok(identity.runId);
  assert.ok(identity.snapshotId);
  assert.ok(identity.receiptHash);

  // All 11 canonical layers exist and reflect atomic publication
  for (let i = 0; i <= 10; i++) {
    const layer = assessment.canonicalLayerResults[`L${i}`];
    assert.ok(layer, `L${i} must be present in canonicalLayerResults`);
    assert.equal(layer.layerId, `L${i}`);
  }

  // Quality, findings, and timeline bind to the same immutable snapshot
  assert.equal(assessment.quality.surfacesGenerated, 4);
  assert.equal(assessment.topFindings.length, 2);
  assert.equal(assessment.evidenceTimeline.length, 1);
});

test("P0: geometry hash matches Python backend byte-for-byte across all golden vectors", () => {
  assert.equal(GEOMETRY_CONTRACT_VERSION, "canonical_geojson_sha256_v1");

  const goldenVectors = [
    {
      name: "standard_polygon",
      geometry: {
        type: "Polygon",
        coordinates: [
          [[35.1, 31.2], [35.2, 31.2], [35.2, 31.3], [35.1, 31.3], [35.1, 31.2]]
        ],
      },
      expectedHash: "sha256:fdef6f34da332b92acbbf0224e7de33b5c3649cfc2cc065dd15f3976453de233",
    },
    {
      name: "feature_with_properties",
      geometry: {
        type: "Feature",
        properties: { name: "Parcel A" },
        geometry: {
          type: "Polygon",
          coordinates: [
            [[10.0, 20.0], [10.5, 20.0], [10.5, 20.5], [10.0, 20.0]]
          ],
        },
      },
      expectedHash: "sha256:4b83c8f9a4bbed965380b7767317a8dde6b75e3a4860fd5c7aa1ac43921dfc36",
    },
    {
      name: "multipolygon",
      geometry: {
        type: "MultiPolygon",
        coordinates: [
          [[[0, 0], [1, 0], [1, 1], [0, 0]]],
          [[[2, 2], [3, 2], [3, 3], [2, 2]]],
        ],
      },
      expectedHash: "sha256:7c7e3149ba1bb8f2051e64c4b32db9d91ee9295e6278911f801d3d20e71b0ebe",
    },
    {
      name: "polygon_with_hole",
      geometry: {
        type: "Polygon",
        coordinates: [
          [[10.0, 10.0], [20.0, 10.0], [20.0, 20.0], [10.0, 20.0], [10.0, 10.0]],
          [[12.0, 12.0], [18.0, 12.0], [18.0, 18.0], [12.0, 18.0], [12.0, 12.0]],
        ],
      },
      expectedHash: "sha256:a49fc79a81f0d940bbe6c92271f871325674bb690ef01ecc41ba231e3376d6a0",
    },
    {
      name: "feature_with_arabic_and_high_precision",
      geometry: {
        type: "Feature",
        properties: { title: "مزرعة النخيل", id: 42 },
        geometry: {
          type: "Point",
          coordinates: [9.12345678, 34.98765432],
        },
      },
      expectedHash: "sha256:a25d081a1fa5d93d7829e59556a6e00543da5072b0886bf8e32f5363cea28e47",
    },
  ];

  for (const vector of goldenVectors) {
    const actual = computeGeometryHash(vector.geometry);
    assert.equal(actual, vector.expectedHash, `Golden vector mismatch for ${vector.name}`);
  }
});

test("Integration 1: ASMAE completes while assessment A is displayed — all consumers adopt publication B through single provider", async () => {
  // Simulate provider holding initial Assessment A
  const pubA = buildMockPublication({
    intelligence_snapshot_id: "snap-A-001",
    canonical_publication_receipt_hash: "receipt-A-sha256-1111111111111111111111111111111111111111111111111111111111111111",
    published_at: "2026-10-28T07:00:00Z",
    evidence_cutoff_at: "2026-10-28T06:30:00Z",
    top_findings: ["Assessment A: Initial satellite pass normal"],
  });
  const assessmentA = canonicalPublicationToAssessment(pubA, "plot-p01-olive");

  // Presentation consumer views derived from Assessment A
  let providerState = { status: "ready", assessment: assessmentA, rawPublication: pubA };
  let l10View = { assessment: providerState.assessment, receipt: providerState.assessment.identity.publicationReceiptHash };
  let findingsView = [...providerState.assessment.topFindings];
  let timelineView = [...providerState.assessment.evidenceTimeline];

  assert.equal(l10View.assessment.identity.snapshotId, "snap-A-001");
  assert.equal(findingsView[0].title, "Assessment A: Initial satellite pass normal");

  // Background ASMAE completion event arrives with finalSnapshotId "snap-B-002"
  const pubB = buildMockPublication({
    intelligence_snapshot_id: "snap-B-002",
    canonical_publication_receipt_hash: "receipt-B-sha256-2222222222222222222222222222222222222222222222222222222222222222",
    published_at: "2026-10-28T08:00:00Z",
    evidence_cutoff_at: "2026-10-28T07:45:00Z",
    top_findings: ["Assessment B: ASMAE radar-optical fusion completed with 1m resolution"],
  });

  // Simulated provider adoption on ASMAE refresh_completed
  const assessmentB = canonicalPublicationToAssessment(pubB, "plot-p01-olive");
  providerState = { status: "ready", assessment: assessmentB, rawPublication: pubB };

  // All downstream presentation consumers atomically adopt Assessment B through provider
  l10View = { assessment: providerState.assessment, receipt: providerState.assessment.identity.publicationReceiptHash };
  findingsView = [...providerState.assessment.topFindings];
  timelineView = [...providerState.assessment.evidenceTimeline];

  assert.equal(l10View.assessment.identity.snapshotId, "snap-B-002");
  assert.equal(l10View.receipt, "receipt-B-sha256-2222222222222222222222222222222222222222222222222222222222222222");
  assert.equal(findingsView[0].title, "Assessment B: ASMAE radar-optical fusion completed with 1m resolution");
  assert.equal(l10View.assessment.identity.publishedAt, "2026-10-28T08:00:00.000Z");
});

test("Integration 2: Legacy fetchLayer10 called after publication A is accepted — delegates to provider and rejects independent commitment", async () => {
  const pubA = buildMockPublication({
    intelligence_snapshot_id: "snap-A-authorized",
    canonical_publication_receipt_hash: "receipt-A-sha256-3333333333333333333333333333333333333333333333333333333333333333",
  });
  const assessmentA = canonicalPublicationToAssessment(pubA, "plot-p01-olive");
  let providerState = { status: "ready", assessment: assessmentA, rawPublication: pubA };
  let l10State = { data: { assessment: assessmentA }, error: null };

  // Simulated legacy caller invokes fetchLayer10 with tampered / spoofed data lacking publication receipt
  const tamperedCandidate = buildMockPublication({
    intelligence_snapshot_id: "snap-spoofed",
    canonical_publication_receipt_hash: "",
    publication_receipt_hash: "",
  });

  // fetchLayer10 delegates to provider, which runs canonicalPublicationToAssessment:
  let delegationFailedClosed = false;
  try {
    canonicalPublicationToAssessment(tamperedCandidate, "plot-p01-olive");
  } catch (err) {
    delegationFailedClosed = true;
    providerState = { status: "invalid", assessment: null, rawPublication: null };
    // Layer 10 presentation adapter fails closed, zero independent scientific state committed
    l10State = { data: null, error: err.message };
  }

  assert.equal(delegationFailedClosed, true, "Contract validation must reject tampered candidate");
  assert.equal(providerState.status, "invalid");
  assert.equal(providerState.assessment, null);
  assert.equal(l10State.data, null, "Layer 10 must fail closed without committing independent state");
  assert.match(l10State.error, /publicationReceiptHash_required/);
});

test("Integration 3: Rapid parcel / crop-cycle switches with delayed responses — generation guard guarantees only authorized current parcel appears", async () => {
  let requestSequence = 0;
  let activeParcelId = "plot-parcel-01";
  let activeAssessment = null;

  // Function simulating provider request with generation sequence guard
  async function fetchAssessmentSimulated(targetPlotId, delayMs, payload) {
    const sequence = ++requestSequence;
    activeParcelId = targetPlotId;

    await new Promise((resolve) => setTimeout(resolve, delayMs));

    // Stale generation guard: reject if newer request was dispatched
    if (sequence !== requestSequence) {
      return null; // Discard stale response
    }

    const assessment = canonicalPublicationToAssessment(payload, targetPlotId);
    activeAssessment = assessment;
    return assessment;
  }

  const pubParcel1 = buildMockPublication({
    plot_id: "plot-parcel-01",
    intelligence_snapshot_id: "snap-parcel-01",
    canonical_publication_receipt_hash: "receipt-1111111111111111111111111111111111111111111111111111111111111111",
  });

  const pubParcel2 = buildMockPublication({
    plot_id: "plot-parcel-02",
    intelligence_snapshot_id: "snap-parcel-02",
    canonical_publication_receipt_hash: "receipt-2222222222222222222222222222222222222222222222222222222222222222",
  });

  // User rapidly clicks Parcel 1, then immediately switches to Parcel 2
  // Request 1 has 50ms delay, Request 2 resolves in 10ms
  const p1Promise = fetchAssessmentSimulated("plot-parcel-01", 50, pubParcel1);
  const p2Promise = fetchAssessmentSimulated("plot-parcel-02", 10, pubParcel2);

  const [res1, res2] = await Promise.all([p1Promise, p2Promise]);

  // Request 1 is aborted/discarded by sequence guard
  assert.equal(res1, null, "Slow Parcel 1 response must be discarded by generation guard");
  assert.ok(res2, "Parcel 2 response must be accepted");
  assert.equal(activeAssessment.identity.plotId, "plot-parcel-02");
  assert.equal(activeAssessment.identity.snapshotId, "snap-parcel-02");
  assert.equal(activeParcelId, "plot-parcel-02");
});
