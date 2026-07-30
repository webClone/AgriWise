import test from "node:test";
import assert from "node:assert/strict";

import {
  browserRenderReceiptSignature,
  buildLayer10RequestIdentity,
  buildRenderViewIdentity,
  isLatestLayer10Request,
  normalizeSourcePolicy,
  shouldRetainLastKnownGood,
} from "../../src/lib/agribrain/layer10-request-state.mjs";

test("normalizes unknown policies without promoting authority", () => {
  assert.equal(normalizeSourcePolicy("asmae_diagnostic"), "asmae_diagnostic");
  assert.equal(normalizeSourcePolicy("production"), "satellite");
  assert.equal(normalizeSourcePolicy("production", "hybrid"), "hybrid");
  assert.equal(normalizeSourcePolicy("production", "invalid"), "satellite");
});

test("request identity binds sequence, policy, intensity, and generation mode", () => {
  const base = {
    sequence: 7,
    plotId: "plot-1",
    sourcePolicy: "satellite",
    visualIntensity: 0.4,
    experimental1m: false,
  };
  const identity = buildLayer10RequestIdentity(base);
  assert.notEqual(identity, buildLayer10RequestIdentity({ ...base, sequence: 8 }));
  assert.notEqual(identity, buildLayer10RequestIdentity({ ...base, sourcePolicy: "hybrid" }));
  assert.notEqual(identity, buildLayer10RequestIdentity({ ...base, visualIntensity: 0.45 }));
  assert.notEqual(identity, buildLayer10RequestIdentity({ ...base, experimental1m: true }));
});

test("only the active non-aborted request may commit", () => {
  assert.equal(isLatestLayer10Request(4, 4, false), true);
  assert.equal(isLatestLayer10Request(5, 4, false), false);
  assert.equal(isLatestLayer10Request(4, 4, true), false);
});

test("render view identity changes for local policy and overlay choices", () => {
  const base = {
    publicationId: "snapshot-1",
    plotId: "plot-1",
    sourcePolicy: "satellite",
    mode: "canopy",
    surfaceType: "NDVI_CLEAN",
    overlaySurfaceType: "EXPERIMENTAL_VISUAL_CANOPY",
    overlayEnabled: false,
  };
  const identity = buildRenderViewIdentity(base);
  assert.notEqual(identity, buildRenderViewIdentity({ ...base, sourcePolicy: "hybrid" }));
  assert.notEqual(identity, buildRenderViewIdentity({ ...base, overlayEnabled: true }));
  assert.notEqual(identity, buildRenderViewIdentity({ ...base, publicationId: "snapshot-2" }));
});

test("retains a complete same-plot publication for an empty degraded refresh", () => {
  const previous = { plot_id: "plot-1", surfaces: [{ type: "NDVI_CLEAN" }] };
  assert.equal(
    shouldRetainLastKnownGood(previous, { plot_id: "plot-1", surfaces: [] }, "plot-1"),
    true,
  );
  assert.equal(
    shouldRetainLastKnownGood(previous, { plot_id: "plot-2", surfaces: [] }, "plot-2"),
    false,
  );
  assert.equal(
    shouldRetainLastKnownGood(previous, { plot_id: "plot-1", surfaces: [{}] }, "plot-1"),
    false,
  );
});

test("browser receipt equality ignores timestamps but detects authority changes", () => {
  const materialization = {
    status: "rendered",
    surfaceType: "NDVI_CLEAN",
    policy: "satellite",
    mode: "canopy",
    role: "base",
    reason: "layer_created",
    layerId: "l10-surface-semantic",
    gridBounds: [1, 2, 3, 4],
    gridWidth: 2,
    gridHeight: 2,
    receipt: {
      publicationId: "snapshot-1",
      sourceId: "source-1",
      layerId: "l10-surface-semantic",
      renderKind: "full_raster",
      timestamp: "2026-01-01T00:00:00.000Z",
      mapInstanceId: "map-primary",
    },
  };
  const first = {
    viewIdentity: "view-1",
    baseMaterialization: materialization,
    overlayMaterialization: { ...materialization, role: "overlay" },
    committedAt: "2026-01-01T00:00:00.000Z",
  };
  const later = {
    ...first,
    committedAt: "2026-01-02T00:00:00.000Z",
    baseMaterialization: {
      ...materialization,
      receipt: { ...materialization.receipt, timestamp: "2026-01-02T00:00:00.000Z" },
    },
  };
  assert.equal(
    browserRenderReceiptSignature(first),
    browserRenderReceiptSignature(later),
  );
  assert.notEqual(
    browserRenderReceiptSignature(first),
    browserRenderReceiptSignature({
      ...later,
      baseMaterialization: { ...later.baseMaterialization, status: "blocked_unauthorized" },
    }),
  );
});
