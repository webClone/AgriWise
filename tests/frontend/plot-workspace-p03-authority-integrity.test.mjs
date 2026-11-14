import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialWorkspaceState,
  workspaceReducer,
} from "../../src/components/farm/workspace/workspace-reducer.mjs";

test("P03-R4-F05 (Gate 1): Every publicly exposed tool action is incapable of introducing or altering publication authority", () => {
  const initial = createInitialWorkspaceState({
    tenantId: "tenant-safe",
    farmId: "farm-safe",
    plotId: "plot-safe",
    cropCycleId: "cycle-autumn-2026",
    geometryHash: "gh-canonical-safe",
    geometryVersion: 1,
  });

  assert.equal(initial.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(initial.publication.snapshotId, null);
  assert.equal(initial.clocks.scientificAsOf, null);

  // 1. Tool selection
  let s = workspaceReducer(initial, {
    type: "ACTIVE_TOOL_CHANGED",
    payload: { tool: "irrigation" },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(s.publication.snapshotId, null);

  // 2. Time cursor navigation
  s = workspaceReducer(s, {
    type: "TIME_SET",
    payload: { cursorTimestamp: "2026-11-14T14:00:00Z" },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(s.clocks.scientificAsOf, null, "Time navigation must not populate scientificAsOf");

  // 3. Entity selection (attempting to pass fabricated snapshot reference)
  s = workspaceReducer(s, {
    type: "ENTITY_SELECTED",
    payload: {
      kind: "ZONE",
      id: "zone-spoofed",
      sourceSnapshotId: "snap-fabricated-cert",
      timestamp: "2026-11-14T14:00:00Z",
    },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE", "Entity selection must not elevate publication authority");
  assert.equal(s.publication.snapshotId, null);

  // 4. Clear selection
  s = workspaceReducer(s, {
    type: "ENTITY_SELECTED",
    payload: { kind: null, id: null },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");

  // 5. Render intent mutation
  s = workspaceReducer(s, {
    type: "RENDER_INTENT_SET",
    payload: { activeMode: "water", showContours: false },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");

  // 6. Vector visibility toggle
  s = workspaceReducer(s, {
    type: "VECTOR_VISIBILITY_SET",
    payload: { vectorKey: "sensors", visible: false },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");

  // 7. Inspector toggle
  s = workspaceReducer(s, {
    type: "INSPECTOR_TOGGLED",
    payload: { collapsed: true },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");

  // 8. Scenario activation / mutation
  s = workspaceReducer(s, {
    type: "SCENARIO_TOGGLED",
    payload: {
      isActive: true,
      scenarioId: "sc-test",
      scenarioName: "Dry Run",
      modifiedForcingParameters: { et0_mult: 1.2 },
    },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");

  // 9. Operational telemetry ingestion
  s = workspaceReducer(s, {
    type: "TELEMETRY_SYNCED",
    payload: { observedAt: "2026-11-14T13:30:00Z" },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(s.clocks.scientificAsOf, null, "Telemetry sync must update operational clock only");
  assert.equal(s.clocks.operationalObserved, "2026-11-14T13:30:00Z");

  // 10. Request invalidation
  s = workspaceReducer(s, {
    type: "REQUEST_INVALIDATED",
    payload: { reason: "tool_reset" },
  });
  assert.equal(s.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(s.publication.isStale, true);
});

test("P03-R4-F05 (Gate 2): PLOT_CHANGED unconditionally resets publication and rejects injected certification payloads", () => {
  // Start on Plot 1 with an established CERTIFIED publication
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-1",
    geometryHash: "gh-1",
    geometryVersion: 1,
  });

  const sPlot1Certified = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-plot-1-valid",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:valid-plot-1",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
      geometryHash: "gh-1",
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sPlot1Certified.publication.authorityStatus, "CERTIFIED");
  assert.equal(sPlot1Certified.clocks.scientificAsOf, "2026-11-14T10:00:00Z");

  // Adversarial Attempt: Switch to Plot 2 and inject a fake CERTIFIED publication in the PLOT_CHANGED payload
  const sPlot2Adversarial = workspaceReducer(sPlot1Certified, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-1",
        farmId: "farm-1",
        plotId: "plot-2",
        cropCycleId: "cycle-2",
        geometryHash: "gh-2",
        geometryVersion: 1,
      },
      publication: {
        snapshotId: "snap-spoofed-plot-2",
        capturedAt: "2026-11-14T12:00:00Z",
        publicationDigest: "sha256:spoofed",
        authorityStatus: "CERTIFIED", // INJECTED SPOOF
        isStale: false,
      },
    },
  });

  // Verification: The reducer must completely discard the injected publication
  assert.equal(sPlot2Adversarial.generationId, sPlot1Certified.generationId + 1);
  assert.equal(sPlot2Adversarial.plotScope.plotId, "plot-2");
  assert.equal(
    sPlot2Adversarial.publication.authorityStatus,
    "UNAVAILABLE",
    "PLOT_CHANGED must reset authorityStatus to UNAVAILABLE regardless of payload"
  );
  assert.equal(sPlot2Adversarial.publication.snapshotId, null);
  assert.equal(sPlot2Adversarial.publication.publicationDigest, null);
  assert.equal(sPlot2Adversarial.publication.isStale, false);
  assert.equal(
    sPlot2Adversarial.clocks.scientificAsOf,
    null,
    "scientificAsOf clock must be reset to null on plot switch"
  );
  assert.equal(sPlot2Adversarial.clocks.cursorTimestamp, null);
});

test("P03-R4-F05 (Gate 3): Scientific bridge is the sole path for introducing validated publication authority", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-1",
    geometryHash: "gh-1",
    geometryVersion: 1,
  });

  // 1. Unauthoritative CERTIFIED claim (missing source) is strictly demoted to PENDING
  const sDemotedNoSource = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-unauth-1",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:unauth",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
      geometryHash: "gh-1",
      geometryVersion: 1,
      // source is missing
    },
  });
  assert.equal(sDemotedNoSource.publication.authorityStatus, "PENDING");

  // 2. Unauthoritative source name is strictly demoted to PENDING
  const sDemotedWrongSource = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-unauth-2",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:unauth",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
      geometryHash: "gh-1",
      geometryVersion: 1,
      source: "TOOL_CONTROLLER_INJECTION",
    },
  });
  assert.equal(sDemotedWrongSource.publication.authorityStatus, "PENDING");

  // 3. Empty publication digest is strictly demoted to PENDING
  const sDemotedEmptyDigest = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-unauth-3",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "   ",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
      geometryHash: "gh-1",
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sDemotedEmptyDigest.publication.authorityStatus, "PENDING");

  // 4. Authoritative scientific bridge dispatch succeeds with CERTIFIED
  const sAuthoritative = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-auth-valid",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:authentic-digest-value",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
      geometryHash: "gh-1",
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sAuthoritative.publication.authorityStatus, "CERTIFIED");
  assert.equal(sAuthoritative.publication.snapshotId, "snap-auth-valid");
  assert.equal(sAuthoritative.clocks.scientificAsOf, "2026-11-14T10:00:00Z");
});

test("P03-R4-F05 (Gate 4): Plot switching cannot preserve publication authority or allow stale invalidations", () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-A",
    cropCycleId: "cycle-A",
    geometryHash: "gh-A",
    geometryVersion: 1,
  });

  // Plot A receives authoritative certification
  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-A-01",
      capturedAt: "2026-11-14T09:00:00Z",
      publicationDigest: "sha256:pubA",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-A",
      tenantId: "tenant-1",
      cropCycleId: "cycle-A",
      geometryHash: "gh-A",
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(state.publication.authorityStatus, "CERTIFIED");
  const genA = state.generationId;

  // Navigate to Plot B
  state = workspaceReducer(state, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-1",
        farmId: "farm-1",
        plotId: "plot-B",
        cropCycleId: "cycle-B",
        geometryHash: "gh-B",
        geometryVersion: 1,
      },
    },
  });
  assert.equal(state.generationId, genA + 1);
  assert.equal(state.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(state.publication.snapshotId, null);
  assert.equal(state.clocks.scientificAsOf, null);

  // Plot B receives authoritative certification
  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-B-01",
      capturedAt: "2026-11-14T11:00:00Z",
      publicationDigest: "sha256:pubB",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-B",
      tenantId: "tenant-1",
      cropCycleId: "cycle-B",
      geometryHash: "gh-B",
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(state.publication.authorityStatus, "CERTIFIED");

  // Late stale invalidation targeting Plot A / Gen 1 arrives late
  const staleInvalidation = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: null,
      authorityStatus: "UNAVAILABLE",
      generationId: genA,
      plotId: "plot-A",
      tenantId: "tenant-1",
      source: "SYSTEM_WORKSPACE_INVALIDATION",
    },
  });
  assert.equal(
    staleInvalidation,
    state,
    "Stale invalidation targeting prior generation and plot must be strictly rejected"
  );
  assert.equal(staleInvalidation.publication.authorityStatus, "CERTIFIED");
  assert.equal(staleInvalidation.publication.snapshotId, "snap-B-01");
});
