import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("R5.0 Frontend Auth & Surface Integrity Contracts", async (t) => {
  await t.test("canonicalizeQueryParams requires complete parameters", async () => {
    const { canonicalizeQueryParams } = await import("../../src/lib/agribrain/internal-service-auth-canonical.mjs");
    const q1 = canonicalizeQueryParams([["b", "2"], ["a", "1"], ["a", "0"]]);
    assert.equal(q1, "a=0&a=1&b=2");
  });

  await t.test("shared GET and POST HMAC vectors match canonical bytes exactly", async () => {
    const { buildCanonicalString, canonicalizeQueryParams, computeHmacSignature } = await import(
      "../../src/lib/agribrain/internal-service-auth-canonical.mjs"
    );
    const vectors = JSON.parse(await readFile(
      new URL("../../packages/contracts/internal_auth_test_vectors.json", import.meta.url),
      "utf8",
    ));
    for (const vector of vectors.vectors) {
      const canonical = buildCanonicalString({
        method: vector.method,
        pathname: vector.pathname,
        queryString: canonicalizeQueryParams(vector.query_params),
        tenantId: vector.tenant_id,
        farmId: vector.farm_id,
        plotId: vector.plot_id,
        bodyText: vector.body_text,
        timestamp: vector.timestamp,
        nonce: vector.nonce,
        keyVersion: vector.key_version,
      });
      assert.equal(canonical, vector.expected_canonical_string, vector.description);
      assert.equal(
        computeHmacSignature(canonical, vectors.secret),
        vector.expected_signature,
        vector.description,
      );
    }
  });

  await t.test("ESM canonical helper matches RFC 3986 percent encoding", async () => {
    const { rfc3986Encode } = await import(
      "../../src/lib/agribrain/internal-service-auth-canonical.mjs"
    );
    assert.equal(rfc3986Encode("hello world~_.-"), "hello%20world~_.-");
  });

  await t.test("render view identity is bound to exact base and overlay surface ids", async () => {
    const { buildRenderViewIdentity } = await import(
      "../../src/lib/agribrain/layer10-request-state.mjs"
    );
    const base = {
      publicationId: "pub-a",
      plotId: "plot-a",
      sourcePolicy: "asmae_diagnostic",
      mode: "water_stress",
      surfaceType: "WATER_ASMAE_CANOPY_WATER",
      surfaceId: "water-surface-a",
      overlaySurfaceType: "",
      overlaySurfaceId: "",
      overlayEnabled: false,
    };
    assert.notEqual(
      buildRenderViewIdentity(base),
      buildRenderViewIdentity({ ...base, surfaceId: "water-surface-b" }),
    );
  });

  await t.test("committed render identity fails closed without producer surface identity", async () => {
    const { hasCompleteCommittedRenderIdentity } = await import(
      "../../src/lib/agribrain/layer10-request-state.mjs"
    );
    const identity = {
      publicationId: "pub-a",
      snapshotId: "snapshot-a",
      surfaceInventoryHash: "inventory-a",
      renderAuthorizationVersion: "render-a",
      surfaceId: "surface-a",
    };
    assert.equal(hasCompleteCommittedRenderIdentity(identity), true);
    assert.equal(hasCompleteCommittedRenderIdentity({ ...identity, surfaceId: "" }), false);
    assert.equal(hasCompleteCommittedRenderIdentity({ ...identity, publicationId: "" }), false);
  });

  await t.test("durable failed job overrides stale queued UI without discarding canonical fallback", async () => {
    const {
      buildAsmaeLiveStateDetail,
      buildAsmaeRefreshFailedDetail,
      patchLayer10AsmaeFailure,
    } = await import("../../src/lib/agribrain/asmae-job-state.mjs");
    const progress = {
      terminal: true,
      status: "failed",
      publicationRelation: "failed",
      canonical_head_snapshot_id: "ASMAE-SNAPSHOT-last-good",
      durable_job: {
        job_id: "job-failed-current",
        plot_id: "plot-a",
        status: "failed",
        stage: "reintegration_failed",
        failure_code: "REINTEGRATION_NAMESPACE_MISMATCH",
        retry_classification: "permanent_contract",
      },
    };
    const live = buildAsmaeLiveStateDetail(progress, "plot-a");
    assert.equal(live.status, "failed");
    assert.equal(live.publicationRelation, "failed");
    const failure = buildAsmaeRefreshFailedDetail(progress, "plot-a");
    const previous = {
      plot_id: "plot-a",
      surfaces: [{ type: "NDVI_CLEAN", values: [[0.4]] }],
      source_policy_display_state: {
        asmaePlotState: { activeSpatialJobStatus: "queued" },
      },
    };
    const patched = patchLayer10AsmaeFailure(previous, failure);
    assert.equal(patched.source_policy_display_state.asmaePlotState.activeSpatialJobStatus, "failed");
    assert.equal(patched.source_policy_display_state.asmaePlotState.publicationRelation, "failed");
    assert.deepEqual(patched.surfaces, previous.surfaces);
  });

  await t.test("worker progress view uses the durable percentage and retains the canonical map", async () => {
    const { buildAsmaeWorkerProgressView } = await import(
      "../../src/lib/agribrain/asmae-job-state.mjs"
    );
    const view = buildAsmaeWorkerProgressView({
      plot_id: "plot-a",
      status: "running",
      terminal: false,
      publicationRelation: "in_progress",
      canonical_head_snapshot_id: "ASMAE-SNAPSHOT-last-good",
      durable_job: {
        job_id: "job-current",
        plot_id: "plot-a",
        status: "running",
        stage: "spatial_assimilation",
        progress_pct: 37,
      },
    }, "plot-a");
    assert.equal(view.visible, true);
    assert.equal(view.progressPct, 37);
    assert.equal(view.stage, "Spatial Assimilation");
    assert.equal(view.hasCanonicalFallback, true);
    assert.equal(view.failed, false);
  });

  await t.test("reintegration remains visible after worker completion until canonical publication", async () => {
    const { buildAsmaeWorkerProgressView } = await import(
      "../../src/lib/agribrain/asmae-job-state.mjs"
    );
    const pending = buildAsmaeWorkerProgressView({
      plot_id: "plot-a",
      status: "completed",
      terminal: true,
      publicationRelation: "completed_unpublished",
      durable_job: {
        job_id: "job-current",
        plot_id: "plot-a",
        status: "completed",
        stage: "downstream_reintegration",
        progress_pct: 100,
      },
    }, "plot-a");
    assert.equal(pending.visible, true);
    assert.equal(pending.awaitingPublication, true);
    assert.equal(pending.reintegrating, true);
    assert.equal(pending.progressPct, 100);

    const published = buildAsmaeWorkerProgressView({
      plot_id: "plot-a",
      status: "completed",
      terminal: true,
      publicationRelation: "published",
      durable_job: {
        job_id: "job-current",
        plot_id: "plot-a",
        status: "completed",
        stage: "complete",
        progress_pct: 100,
      },
    }, "plot-a");
    assert.equal(published.visible, false);
  });

  await t.test("recoverable stalled work is progress while terminal failure is failure", async () => {
    const {
      buildAsmaeLiveStateDetail,
      buildAsmaeWorkerProgressView,
      patchLayer10AsmaeLiveState,
    } = await import(
      "../../src/lib/agribrain/asmae-job-state.mjs"
    );
    const stalledProgress = {
      plot_id: "plot-a",
      status: "stalled",
      terminal: false,
      durable_job: {
        job_id: "job-current",
        plot_id: "plot-a",
        status: "stalled",
        stage: "downstream_reintegration_retry",
        progress_pct: 90,
      },
    };
    const stalled = buildAsmaeWorkerProgressView(stalledProgress, "plot-a");
    assert.equal(stalled.active, true);
    assert.equal(stalled.failed, false);
    assert.equal(stalled.tone, "warning");
    const stalledLive = buildAsmaeLiveStateDetail(stalledProgress, "plot-a");
    assert.equal(stalledLive.failure, null);
    const stalledPatched = patchLayer10AsmaeLiveState({
      plot_id: "plot-a",
      source_policy_display_state: {
        asmaePlotState: {
          activeSpatialJobStatus: "failed",
          spatialRefreshFailure: { failureCode: "OLD_JOB_FAILURE" },
        },
      },
    }, stalledLive);
    assert.equal(
      stalledPatched.source_policy_display_state.asmaePlotState.spatialRefreshFailure,
      undefined,
      "a recoverable successor must not retain an older terminal failure receipt",
    );

    const failed = buildAsmaeWorkerProgressView({
      plot_id: "plot-a",
      status: "failed",
      terminal: true,
      publicationRelation: "failed",
      durable_job: {
        job_id: "job-current",
        plot_id: "plot-a",
        status: "failed",
        stage: "downstream_reintegration_failed",
        progress_pct: 90,
        error: "Canonical publication validation failed",
      },
    }, "plot-a");
    assert.equal(failed.active, false);
    assert.equal(failed.failed, true);
    assert.equal(failed.tone, "failure");
    assert.match(failed.detail, /validation failed/i);

    const replaceable = buildAsmaeWorkerProgressView({
      plot_id: "plot-a",
      status: "failed",
      terminal: true,
      durable_job: {
        job_id: "job-old-build",
        plot_id: "plot-a",
        status: "failed",
        retry_eligible: true,
        retry_classification: "new_scientific_identity_required",
      },
    }, "plot-a");
    assert.equal(replaceable.retryEligible, true);
    assert.equal(replaceable.retryClassification, "new_scientific_identity_required");
  });

  await t.test("reintegration-pending status and unknown durable percentages remain truthful", async () => {
    const { buildAsmaeWorkerProgressView } = await import(
      "../../src/lib/agribrain/asmae-job-state.mjs"
    );
    const view = buildAsmaeWorkerProgressView({
      plot_id: "plot-a",
      status: "completed_reintegration_pending",
      terminal: false,
      publicationRelation: "in_progress",
      durable_job: {
        job_id: "job-current",
        plot_id: "plot-a",
        status: "completed_reintegration_pending",
        stage: "downstream_reintegration",
        progress_pct: null,
      },
    }, "plot-a");
    assert.equal(view.visible, true);
    assert.equal(view.active, true);
    assert.equal(view.reintegrating, true);
    assert.equal(view.progressPct, null, "missing progress must not be fabricated as zero");
  });

  await t.test("completion patch keeps publication pending until canonical data is visible", async () => {
    const { patchLayer10AsmaeCompletion } = await import(
      "../../src/lib/agribrain/asmae-job-state.mjs"
    );
    const previous = {
      plot_id: "plot-a",
      intelligence_snapshot_id: "snapshot-last-visible",
      surfaces: [{ type: "NDVI_CLEAN", values: [[0.4]] }],
      source_policy_display_state: {
        asmaePlotState: {
          activeSpatialJobStatus: "completed",
          publicationRelation: "completed_unpublished",
        },
      },
    };
    const patched = patchLayer10AsmaeCompletion(previous, {
      plotId: "plot-a",
      finalSnapshotId: "snapshot-new",
      publicationRelation: "published",
    });
    assert.equal(
      patched.source_policy_display_state.asmaePlotState.publicationRelation,
      "completed_unpublished",
    );
    assert.deepEqual(patched.surfaces, previous.surfaces);
  });

  await t.test("worker progress generation guard rejects stale plot responses", async () => {
    const { isCurrentAsmaeProgressResponse } = await import(
      "../../src/lib/agribrain/asmae-job-state.mjs"
    );
    assert.equal(isCurrentAsmaeProgressResponse({
      expectedPlotId: "plot-new",
      responsePlotId: "plot-new",
      expectedGeneration: 4,
      currentGeneration: 4,
      aborted: false,
    }), true);
    assert.equal(isCurrentAsmaeProgressResponse({
      expectedPlotId: "plot-new",
      responsePlotId: "plot-old",
      expectedGeneration: 4,
      currentGeneration: 4,
      aborted: false,
    }), false);
    assert.equal(isCurrentAsmaeProgressResponse({
      expectedPlotId: "plot-new",
      responsePlotId: "plot-new",
      expectedGeneration: 3,
      currentGeneration: 4,
      aborted: false,
    }), false);
  });

  await t.test("dashboard worker progress is visual and does not cover the canonical map", async () => {
    const progressSource = await readFile(
      new URL("../../src/components/farm/intelligence/PlotLoadingSequence.tsx", import.meta.url),
      "utf8",
    );
    const dashboardSource = await readFile(
      new URL("../../src/components/farm/PlotDashboard.tsx", import.meta.url),
      "utf8",
    );
    const hookSource = await readFile(
      new URL("../../src/hooks/useLayer10.ts", import.meta.url),
      "utf8",
    );
    assert.match(progressSource, /role="progressbar"/);
    assert.match(progressSource, /aria-valuenow=\{exactPercent/);
    assert.match(progressSource, /Current canonical map remains active/);
    assert.match(progressSource, /view\?\.status === "completed" && loading/);
    assert.match(progressSource, /awaitingReplacementJob/);
    assert.match(progressSource, /Waiting for the new durable worker record/);
    assert.match(progressSource, /Start replacement ASMAE run/);
    assert.match(progressSource, /onRetry/);
    assert.match(progressSource, /dispatchedCompletionRef/);
    assert.match(progressSource, /dispatchedCompletionRef\.current !== completionIdentity/);
    assert.doesNotMatch(progressSource, /ALL_DYNAMIC_STAGES|progressFraction/);
    assert.match(dashboardSource, /showAsmaeWorkerProgress/);
    assert.match(dashboardSource, /asmaeWorkerRequestError/);
    assert.match(dashboardSource, /completed_reintegration_pending/);
    assert.match(dashboardSource, /pointer-events-none/);
    assert.match(dashboardSource, /handleAsmaeWorkerRetry/);
    assert.match(hookSource, /awaitingCanonicalPublication/);
    assert.match(hookSource, /live\.publicationRelation === "published"/);
    assert.match(hookSource, /canonicalCompletionFetchRef/);
    assert.match(hookSource, /canonicalCompletionFetchRef\.current === completionIdentity/);
    assert.doesNotMatch(
      dashboardSource.slice(
        dashboardSource.indexOf("mounted && showAsmaeWorkerProgress"),
        dashboardSource.indexOf("FieldInsightBar", dashboardSource.indexOf("mounted && showAsmaeWorkerProgress")),
      ),
      /absolute inset-0|backdrop-blur-sm/,
    );
  });

  await t.test("render receipt signature is bound to publication inventory and authorization", async () => {
    const { browserRenderReceiptSignature } = await import(
      "../../src/lib/agribrain/layer10-request-state.mjs"
    );
    const receipt = {
      viewIdentity: "view-a",
      publicationId: "pub-a",
      surfaceInventoryHash: "inventory-a",
      renderAuthorizationVersion: "auth-a",
      baseMaterialization: {
        status: "rendered",
        surfaceType: "ASMAE_VIGOR",
        surfaceId: "surface-a",
        receipt: {
          publicationId: "pub-a",
          sourceId: "snapshot-a@inventory-a",
          layerId: "layer-a",
          renderKind: "diagnostic_overlay",
          mapInstanceId: "deckgl-overlay",
          snapshotId: "snapshot-a",
          surfaceInventoryHash: "inventory-a",
          renderAuthorizationVersion: "auth-a",
          surfaceId: "surface-a",
        },
      },
      overlayMaterialization: { status: "blocked_image_generation" },
      hybridOverlayMaterializations: [],
    };
    assert.notEqual(
      browserRenderReceiptSignature(receipt),
      browserRenderReceiptSignature({ ...receipt, surfaceInventoryHash: "inventory-b" }),
    );
    assert.notEqual(
      browserRenderReceiptSignature(receipt),
      browserRenderReceiptSignature({
        ...receipt,
        baseMaterialization: { ...receipt.baseMaterialization, surfaceId: "surface-b" },
      }),
    );
    assert.notEqual(
      browserRenderReceiptSignature(receipt),
      browserRenderReceiptSignature({
        ...receipt,
        hybridOverlayMaterializations: [{
          ...receipt.baseMaterialization,
          surfaceType: "CANOPY_ASMAE_VIGOR",
          surfaceId: "hybrid-vigor-a",
        }],
      }),
      "committing a hybrid overlay must change the browser render receipt",
    );
  });

  await t.test("committed surface identity controls legend quantity and units", async () => {
    const {
      resolveCommittedSurfaceLegend,
      resolveSurfaceDisplayScale,
      resolveSurfacePalette,
    } = await import(
      "../../src/lib/agribrain/surface-legend-meta.mjs"
    );
    const fallback = {
      label: "Canopy (NDVI)", unit: "NDVI", lowColor: "red", midColor: "yellow",
      highColor: "green", lowLabel: "Low", midLabel: "Mid", highLabel: "High",
      stopLabels: ["Low", "Mid", "High"],
    };
    const vigor = resolveCommittedSurfaceLegend({
      type: "CANOPY_ASMAE_VIGOR", units: "fraction",
    }, fallback);
    assert.equal(vigor.label, "ASMAE Canopy Vigor");
    assert.equal(vigor.unit, "fraction");
    assert.notEqual(vigor.label, fallback.label);

    const chlorophyll = resolveCommittedSurfaceLegend({
      type: "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY", units: "µg/cm²",
    }, fallback);
    assert.equal(chlorophyll.label, "Chlorophyll State");
    assert.equal(chlorophyll.unit, "µg/cm²");
    const diagnostic = resolveCommittedSurfaceLegend({
      type: "ASMAE_POSTERIOR_CONCENTRATION",
      units: "fraction",
      palette_id: "UNCERTAINTY_GRAY",
    }, fallback);
    assert.equal(diagnostic.label, "Asmae Posterior Concentration");
    assert.equal(diagnostic.lowColor, "#f8fafc");
    assert.deepEqual(resolveSurfacePalette({
      type: "WATER_ASMAE_CANOPY_WATER",
      palette_id: "STRESS_RED",
    }), ["#c0392b", "#f1c40f", "#1a5276"]);
    assert.deepEqual(resolveSurfacePalette({
      type: "WATER_ASMAE_CANOPY_WATER",
    }, null, "chroma"), [
      "rgb(99, 102, 241)", "rgb(236, 72, 153)", "rgb(234, 179, 8)",
    ]);

    const relativeWater = {
      type: "WATER_ASMAE_CANOPY_WATER",
      units: "fraction",
      render_range: [0, 1],
      values: [Array.from({ length: 100 }, (_, index) => index / 100)],
    };
    const displayScale = resolveSurfaceDisplayScale(relativeWater, {
      activeMode: "water_stress",
      detailMode: "farmer",
    });
    assert.equal(displayScale.policy, "field_percentile");
    assert.equal(displayScale.min, 0.02);
    assert.equal(displayScale.max, 0.98);
    assert.equal(displayScale.declaredMin, 0);
    assert.equal(displayScale.declaredMax, 1);
    assert.deepEqual(displayScale.labels, [
      "Lower in this field", "Typical in this field", "Higher in this field",
    ]);
    assert.equal(resolveCommittedSurfaceLegend(null, fallback), fallback);
  });

  await t.test("pixel sampling never promotes denied inspector authority", async () => {
    const {
      resolveCropStageLabels,
      resolvePixelInspectorCapabilities,
      resolvePixelInspectorTitle,
    } = await import("../../src/lib/agribrain/pixel-inspector-authority.mjs");
    const scoutingSurface = {
      type: "WATER_ASMAE_CANOPY_WATER",
      grounding_class: "MODEL_ASSISTED_RASTER",
      values: [[0.42, 0.48]],
      provenance: {
        prescription_driver_allowed: false,
        management_eligible: false,
      },
    };
    const denied = resolvePixelInspectorCapabilities({
      surface: scoutingSurface,
      inspectorAuthorization: { authorized: false, inspectorAllowed: false },
    });
    assert.equal(denied.canSamplePixel, true);
    assert.equal(denied.canInterpretForScouting, true);
    assert.equal(denied.canInterpretDiagnostically, false);
    assert.equal(denied.canUseForPrescription, false);

    const inspectorOnly = resolvePixelInspectorCapabilities({
      surface: scoutingSurface,
      inspectorAuthorization: { authorized: true, inspectorAllowed: true },
    });
    assert.equal(inspectorOnly.canInterpretDiagnostically, true);
    assert.equal(inspectorOnly.canUseForPrescription, false);

    assert.equal(resolvePixelInspectorTitle(
      "WATER_ASMAE_CANOPY_WATER", "water_stress",
    ), "Canopy Water State");
    assert.equal(resolvePixelInspectorTitle(
      "WATER_ASMAE_ROOT_ZONE_WATER", "water_stress",
    ), "Root-Zone Water State");
    assert.equal(resolvePixelInspectorTitle(
      "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY", "nutrient_risk",
    ), "Chlorophyll State");
    assert.equal(resolvePixelInspectorTitle(
      "WATER_STRESS_PROB", "water_stress",
    ), "Water Stress Probability");
    assert.equal(resolvePixelInspectorTitle(
      "NUTRIENT_STRESS_PROB", "nutrient_risk",
    ), "Nutrient Stress Probability");

    assert.deepEqual(resolveCropStageLabels("Tomato", "unknown"), {
      cropLabel: "Crop: Tomato",
      growthStageLabel: null,
    });
    assert.deepEqual(resolveCropStageLabels("Tomato", "flowering_stage"), {
      cropLabel: "Crop: Tomato",
      growthStageLabel: "Growth stage: flowering stage",
    });
  });

  await t.test("canonical integrity is distinct from stale publication contracts", async () => {
    const { classifyCanonicalHeadValidation } = await import(
      "../../src/lib/agribrain/layer10-request-state.mjs"
    );
    const integrity = {
      nodeValid: true,
      publicationValid: true,
      receiptValid: true,
      inventoryValid: true,
      bindingValid: true,
      lineageValid: true,
    };
    assert.equal(classifyCanonicalHeadValidation({
      ...integrity,
      schemaValid: true,
      contractValid: true,
      publicationStatusValid: true,
    }), "valid");
    assert.equal(classifyCanonicalHeadValidation({
      ...integrity,
      schemaValid: false,
      contractValid: false,
      publicationStatusValid: true,
    }), "stale");
    assert.equal(classifyCanonicalHeadValidation({
      ...integrity,
      lineageValid: false,
      schemaValid: true,
      contractValid: true,
      publicationStatusValid: true,
    }), "corrupt");
    assert.equal(classifyCanonicalHeadValidation({
      ...integrity,
      nodeValid: false,
      schemaValid: true,
      contractValid: true,
      publicationStatusValid: true,
    }), "corrupt");
  });

  await t.test("compound render attribution discloses committed experimental pixels", async () => {
    const { resolveCompoundRenderAttribution } = await import(
      "../../src/lib/agribrain/layer10-request-state.mjs"
    );
    assert.deepEqual(resolveCompoundRenderAttribution({
      baseRendered: true,
      overlayRendered: true,
      baseSourceLabel: "SATELLITE",
      baseAuthorityLabel: "OBSERVED PROVIDER DATA",
    }), {
      sourceLabel: "SATELLITE + EXPERIMENTAL",
      authorityLabel: "OBSERVED PROVIDER DATA · experimental scouting overlay",
    });
    assert.equal(resolveCompoundRenderAttribution({
      baseRendered: false,
      overlayRendered: true,
      baseSourceLabel: "SATELLITE",
      baseAuthorityLabel: "OBSERVED PROVIDER DATA",
    }).sourceLabel, "NO COMMITTED RASTER");
  });

  await t.test("phenology UI consumes only canonical Layer 10 authority", async () => {
    const { normalizeCanonicalPhenologyPublication } = await import(
      "../../src/lib/agribrain/phenology-authority.mjs"
    );
    const legacy = normalizeCanonicalPhenologyPublication({
      resolvedCropStage: "REPRODUCTIVE",
      phenologyContext: {
        phenology_source: "layer2_legacy_phenology",
        phenology_evidence_class: "legacy_l2_diagnostic",
      },
    });
    assert.equal(legacy.resolvedCropStage, "UNKNOWN");
    assert.equal(legacy.phenologyContext.phenology_receipt_valid, false);
    assert.equal(legacy.phenologyContext.phenology_source, "unavailable");
    assert.equal(
      legacy.phenologyContext.required_phenology_source,
      "layer2_canonical_phenology",
    );

    const canonical = normalizeCanonicalPhenologyPublication({
      resolvedCropStage: "REPRODUCTIVE",
      phenologyContext: {
        phenology_source: "layer2_canonical_phenology",
        phenology_authority: "diagnostic",
        phenology_evidence_class: "diagnostic",
        phenology_posterior_hash: "a".repeat(64),
        phenology_confidence: 0.72,
        phenology_receipt_valid: true,
        stage_available: true,
      },
    });
    assert.equal(canonical.resolvedCropStage, "REPRODUCTIVE");
    assert.equal(canonical.phenologyContext.phenology_receipt_valid, true);

    const hookSource = await readFile(
      new URL("../../src/hooks/useLayer10.ts", import.meta.url),
      "utf8",
    );
    const evidenceSource = await readFile(
      new URL("../../src/lib/agribrain/plot-map-evidence-state.ts", import.meta.url),
      "utf8",
    );
    const shellSource = await readFile(
      new URL("../../src/components/farm/map/PlotMapShell.tsx", import.meta.url),
      "utf8",
    );
    const contextBandSource = await readFile(
      new URL("../../src/components/farm/PlotContextBand.tsx", import.meta.url),
      "utf8",
    );
    const cropStatusSource = await readFile(
      new URL("../../src/components/farm/CurrentCropStatus.tsx", import.meta.url),
      "utf8",
    );
    const telemetrySource = await readFile(
      new URL("../../src/components/farm/RawTelemetryHub.tsx", import.meta.url),
      "utf8",
    );

    assert.match(hookSource, /canonicalCropStage: data\?\.resolved_crop_stage/);
    assert.match(hookSource, /normalizeCanonicalPhenologyPublication/);
    assert.match(evidenceSource, /resolveCanonicalPhenologyStage\(/);
    assert.doesNotMatch(evidenceSource, /resolveLegacyPhenologyStage/);
    assert.doesNotMatch(
      evidenceSource.slice(evidenceSource.indexOf("// 6. Phenology stage")),
      /stage_by_day|data\?\.crop_stage|data\?\.phenology_stage/,
    );
    assert.match(shellSource, /l10\.evidenceState\.resolvedPhenology\.stage/);
    assert.doesNotMatch(shellSource, /current\?\.crop_stage/);
    assert.doesNotMatch(contextBandSource, /cropPhenology\?\.stage|effectiveCropStage|cropStage\?:/);
    assert.match(cropStatusSource, /phenology\.posteriorHash/);
    assert.doesNotMatch(cropStatusSource, /cropPhenology|\bdap\b|gddProgress/i);
    assert.match(telemetrySource, /canonicalPhenology\.posteriorHash/);
    assert.doesNotMatch(telemetrySource, /cropPheno|DAP-based|Calendar \/ NDVI/);
  });

  await t.test("crop identity UI keeps declaration, EO group support, and species confirmation separate", async () => {
    const {
      buildCropLabelConfirmationPayload,
      getCropCandidateRankingShare,
      humanizeCropAuthority,
    } = await import("../../src/lib/agribrain/crop-identity-contract.mjs");

    assert.equal(getCropCandidateRankingShare({ ranking_share: 0.052 }), 0.052);
    assert.equal(
      getCropCandidateRankingShare({ softmax_candidate_share: 0.052 }),
      null,
      "deprecated softmax aliases must not be presented as public probabilities",
    );
    assert.equal(humanizeCropAuthority("REGISTRY_DECLARED"), "Registry declaration");

    const confirmation = buildCropLabelConfirmationPayload({
      plotId: "plot-a",
      cropCode: "Tomato",
    });
    assert.deepEqual(confirmation, {
      plotId: "plot-a",
      cropCode: "tomato",
      synthetic: false,
    });
    assert.equal("plantingDate" in confirmation, false);
    assert.equal("startDate" in confirmation, false);

    const bannerSource = await readFile(
      new URL("../../src/components/farm/intelligence/CropIdentityBanner.tsx", import.meta.url),
      "utf8",
    );
    assert.match(bannerSource, /Registry \/ confirmation authority/);
    assert.match(bannerSource, /EO group support/);
    assert.match(bannerSource, /Context-conditioned pipeline ranking/);
    assert.match(bannerSource, /not independent EO evidence/);
    assert.match(bannerSource, /Species confirmation/);
    assert.match(bannerSource, /not a calibrated species probability/);
    assert.doesNotMatch(bannerSource, /Scoring \{totalEvaluated \|\| 212\}/);
    assert.doesNotMatch(bannerSource, /plantingDate:\s*new Date/);
    assert.doesNotMatch(bannerSource, /startDate:\s*new Date/);
    assert.doesNotMatch(bannerSource, /\/api\/plots\/\$\{plotId\}\/cycle/);

    const cropLabelRouteSource = await readFile(
      new URL("../../src/app/api/agribrain/crop-label/route.ts", import.meta.url),
      "utf8",
    );
    assert.match(cropLabelRouteSource, /buildSignedInternalHeaders\(/);
    assert.match(cropLabelRouteSource, /farmId: String\(access\.plot\.farmId\)/);
    assert.match(cropLabelRouteSource, /label_source: "farmer_confirmed"/);
    assert.match(cropLabelRouteSource, /synthetic: false/);
    assert.doesNotMatch(cropLabelRouteSource, /created_by:\s*userId/);
    assert.doesNotMatch(cropLabelRouteSource, /label_source:\s*labelSource/);
  });

  await t.test("experimental fallback copy does not claim scientific certification", async () => {
    const coverageHudSource = await readFile(
      new URL("../../src/components/farm/intelligence/ResolutionCoverageHUD.tsx", import.meta.url),
      "utf8",
    );

    assert.match(
      coverageHudSource,
      /Showing committed composite advisory raster\./,
    );
    assert.doesNotMatch(coverageHudSource, /Showing certified base raster\./);
  });
});
