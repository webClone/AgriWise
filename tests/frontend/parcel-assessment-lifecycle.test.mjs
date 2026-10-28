import assert from "node:assert/strict";
import { test } from "node:test";
import {
  PARCEL_ASSESSMENT_CONTRACT_VERSION,
  computeGeometryHash,
  computeClientFingerprint,
  validateAssessmentIdentity,
  createImmutableParcelAssessment,
  isAssessmentStaleForGeometry,
  isAssessmentStaleForCropCycle,
  isLateArrivingEvidence,
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

// Emulate canonicalPublicationToAssessment in JS test environment
function normalizeToAssessment(raw, plotId, options = {}) {
  const cutoffIso = raw.evidence_cutoff_at || raw.capturedAt;
  const publishedIso = raw.published_at || cutoffIso;
  const geomHash = raw.geometry_hash || (options.geometry ? computeGeometryHash(options.geometry) : "empty_geometry");
  const receipt = raw.canonical_publication_receipt_hash || raw.publication_receipt_hash || "";

  const identity = {
    tenantId: options.tenantId || raw.tenant_id || "default",
    farmId: options.farmId || raw.farm_id || "",
    plotId: String(plotId || raw.plot_id || ""),
    cropCycleId: options.cropCycleId ?? raw.crop_cycle_id ?? null,
    publicationId: String(raw.publication_id || ""),
    runId: String(raw.publication_run_id || raw.agribrain_run_id || ""),
    snapshotId: String(raw.intelligence_snapshot_id || raw.snapshot_id || ""),
    geometryHash: geomHash,
    observationWindow: {
      start: raw.source_window?.[0] || cutoffIso,
      end: raw.source_window?.[1] || cutoffIso,
    },
    evidenceCutoffAt: cutoffIso,
    publishedAt: publishedIso,
    publicationReceiptHash: receipt,
    receiptHash: receipt,
    contractVersion: PARCEL_ASSESSMENT_CONTRACT_VERSION,
  };

  const validation = validateAssessmentIdentity(identity);
  if (!validation.valid) {
    throw new Error(`Assessment identity validation failed: ${validation.errors.join("; ")}`);
  }

  const rawLayerResults = raw.layer_results || {};
  const canonicalLayerResults = {};
  for (let i = 0; i <= 10; i++) {
    const layerId = `L${i}`;
    const rawLayer = rawLayerResults[layerId] || null;
    if (rawLayer) {
      canonicalLayerResults[layerId] = {
        layerId,
        status: rawLayer.status || "UNAVAILABLE",
        confidence: typeof rawLayer.confidence === "number" ? rawLayer.confidence : 1.0,
        sources: Array.isArray(rawLayer.sources) ? rawLayer.sources : [],
        flags: rawLayer.degradation_flags || rawLayer.flags || undefined,
      };
    } else {
      canonicalLayerResults[layerId] = {
        layerId,
        status: "UNAVAILABLE",
        confidence: 0,
        sources: [],
      };
    }
  }

  const topFindings = (raw.top_findings || []).map((item, idx) => {
    if (typeof item === "string") {
      return {
        id: `finding-${idx + 1}`,
        title: item,
        severity: "info",
        description: item,
        actionable: false,
      };
    }
    return {
      id: String(item.id || `finding-${idx + 1}`),
      title: item.title,
      severity: item.severity || "info",
      description: item.description || item.title,
      actionable: Boolean(item.actionable),
    };
  });

  const quality = {
    degradationMode: raw.quality?.degradation_mode || "NORMAL",
    reliabilityScore: raw.quality?.reliability_score ?? null,
    warnings: raw.quality?.warnings || [],
    surfacesGenerated: Number(raw.quality?.surfaces_generated || 0),
    zonesGenerated: Number(raw.quality?.zones_generated || 0),
    gridAlignmentOk: typeof raw.quality?.grid_alignment_ok === "boolean" ? raw.quality.grid_alignment_ok : null,
    detailConservationOk: typeof raw.quality?.detail_conservation_ok === "boolean" ? raw.quality.detail_conservation_ok : null,
  };

  const evidenceTimeline = (raw.timeline || []).map((ev, idx) => ({
    id: ev.id || `ev-${idx + 1}`,
    type: ev.type || "observation",
    source: ev.source || "unknown",
    observedAt: ev.observedAt,
    capturedAt: ev.observedAt,
    manifestMembership: Boolean(ev.manifestMembership),
    summary: ev.summary || "evidence",
    verified: Boolean(ev.verified),
  }));

  return createImmutableParcelAssessment({
    identity,
    canonicalLayerResults,
    authoritativeSurfaces: raw.surfaces || [],
    topFindings,
    quality,
    evidenceTimeline,
  });
}

test("P2-B: transforms canonical publication into verified immutable ParcelAssessment", () => {
  const raw = buildMockPublication();
  const assessment = normalizeToAssessment(raw, "plot-p01-olive");

  assert.equal(assessment.identity.plotId, "plot-p01-olive");
  assert.equal(assessment.identity.publicationReceiptHash, "c4601b07973059635ba026fb96b01b000216b2302bb617db851179c135678129");
  assert.equal(assessment.canonicalLayerResults.L0.status, "OK");
  assert.equal(assessment.canonicalLayerResults.L3.status, "DEGRADED");
  assert.equal(assessment.canonicalLayerResults.L7.status, "UNAVAILABLE");
  assert.equal(assessment.topFindings.length, 2);
  assert.equal(assessment.quality.gridAlignmentOk, true);
  assert.equal(assessment.quality.detailConservationOk, null);
  assert(Object.isFrozen(assessment));
  assert(Object.isFrozen(assessment.canonicalLayerResults));
  assert(Object.isFrozen(assessment.topFindings));
});

test("P2-B: missing findings are represented truthfully as empty array without synthetic fabrication", () => {
  const raw = buildMockPublication({ top_findings: [] });
  const assessment = normalizeToAssessment(raw, "plot-p01-olive");

  assert.deepEqual(assessment.topFindings, []);
  assert.equal(assessment.topFindings.length, 0);
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
  const assessment = normalizeToAssessment(raw, "plot-p01-olive");

  assert.equal(assessment.quality.gridAlignmentOk, null);
  assert.equal(assessment.quality.detailConservationOk, null);
});

test("P2-B: mutation of immutable assessment fails in strict mode", () => {
  const raw = buildMockPublication();
  const assessment = normalizeToAssessment(raw, "plot-p01-olive");

  assert.throws(() => {
    // @ts-expect-error test immutability
    assessment.canonicalLayerResults.L0.status = "FAILED";
  }, /Cannot assign to read only property/);

  assert.throws(() => {
    // @ts-expect-error test immutability
    assessment.topFindings.push({ id: "fake", title: "fake", severity: "info", description: "fake" });
  }, /Cannot add property/);
});

test("P2-B: detects geometry staleness when plot boundaries are edited", () => {
  const raw = buildMockPublication();
  const assessment = normalizeToAssessment(raw, "plot-p01-olive");

  const originalGeom = {
    type: "Polygon",
    coordinates: [[[31.6, -7.9], [31.61, -7.9], [31.61, -7.91], [31.6, -7.9]]],
  };
  const modifiedGeom = {
    type: "Polygon",
    coordinates: [[[31.6, -7.9], [31.65, -7.9], [31.65, -7.95], [31.6, -7.9]]],
  };

  assert.equal(isAssessmentStaleForGeometry(assessment.identity, originalGeom), false);
  assert.equal(isAssessmentStaleForGeometry(assessment.identity, modifiedGeom), true);
});

test("P2-B: detects crop cycle staleness when plot transitions to next season", () => {
  const raw = buildMockPublication();
  const assessment = normalizeToAssessment(raw, "plot-p01-olive", { cropCycleId: "cycle-2026-autumn" });

  assert.equal(isAssessmentStaleForCropCycle(assessment.identity, "cycle-2026-autumn"), false);
  assert.equal(isAssessmentStaleForCropCycle(assessment.identity, "cycle-2027-spring"), true);
  assert.equal(isAssessmentStaleForCropCycle(assessment.identity, null), true);
});

test("P2-B: late arriving evidence after publication cutoff is isolated from manifest", () => {
  const raw = buildMockPublication();
  const assessment = normalizeToAssessment(raw, "plot-p01-olive");

  const onTimeEvidence = {
    observedAt: "2026-10-26T12:00:00Z",
    manifestMembership: true,
  };
  const lateEvidence = {
    observedAt: "2026-10-28T09:00:00Z", // After cutoff 06:00:00Z
    manifestMembership: false,
  };

  assert.equal(isLateArrivingEvidence(assessment.identity, onTimeEvidence), false);
  assert.equal(isLateArrivingEvidence(assessment.identity, lateEvidence), true);
});
