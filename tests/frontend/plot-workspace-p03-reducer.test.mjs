import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialWorkspaceState,
  workspaceReducer,
} from "../../src/components/farm/workspace/workspace-reducer.mjs";

test("P03 Reducer: createInitialWorkspaceState establishes clean scoped identity and generation 1", () => {
  const initial = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-1",
    geometryHash: "geom-hash-1",
    geometryVersion: "1.0",
    initialTool: "map",
  });

  assert.equal(initial.generationId, 1);
  assert.equal(initial.ownerScope.tenantId, "tenant-1");
  assert.equal(initial.plotScope.plotId, "plot-1");
  assert.equal(initial.plotScope.cropCycleId, "cycle-1");
  assert.equal(initial.selectedEntity.id, null);
  assert.equal(initial.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(initial.clocks.activeTimeMode, "LATEST");
  assert.equal(initial.scenario.isActive, false);
});

test("P03 Reducer: PLOT_CHANGED increments generationId and clears entity selection and scenario", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });

  // Manually attach selection and scenario to s0
  const s1 = {
    ...s0,
    selectedEntity: {
      kind: "ZONE",
      id: "zone-123",
      sourceSnapshotId: "snap-1",
      timestamp: "2026-11-10T10:00:00Z",
    },
    scenario: {
      isActive: true,
      scenarioId: "sc-1",
      scenarioName: "Drought Test",
      modifiedForcingParameters: { et0_mult: 1.5 },
    },
  };

  const action = {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-2",
        farmId: "farm-2",
        plotId: "plot-2",
        cropCycleId: "cycle-2",
        geometryHash: "geom-hash-2",
        geometryVersion: "2.0",
      },
    },
  };

  const s2 = workspaceReducer(s1, action);

  assert.equal(s2.generationId, s1.generationId + 1, "generationId must increment");
  assert.equal(s2.plotScope.plotId, "plot-2");
  assert.equal(s2.ownerScope.tenantId, "tenant-2");
  assert.equal(s2.selectedEntity.id, null, "selectedEntity must be reset");
  assert.equal(s2.scenario.isActive, false, "active scenario must be terminated on plot switch");
  assert.deepEqual(s2.scenario.modifiedForcingParameters, {});
});

test("P03 Reducer: PLOT_CHANGED with identical scope is an idempotent no-op", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-1",
    geometryHash: "gh-1",
  });

  const s1 = workspaceReducer(s0, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-1",
        farmId: "farm-1",
        plotId: "plot-1",
        cropCycleId: "cycle-1",
        geometryHash: "gh-1",
      },
    },
  });

  assert.equal(s1, s0, "Identical scope must return the exact same state reference");
  assert.equal(s1.generationId, s0.generationId);
});

test("P03 Reducer: SNAPSHOT_SELECTED sets scientificAsOf clock and preserves cross-snapshot warning", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });

  // Select an entity from snapshot 1
  const s1 = workspaceReducer(s0, {
    type: "ENTITY_SELECTED",
    payload: {
      kind: "ZONE",
      id: "zone-alpha",
      sourceSnapshotId: "snapshot-101",
    },
  });

  // New snapshot arrives (snapshot 102)
  const s2 = workspaceReducer(s1, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snapshot-102",
      capturedAt: "2026-11-14T08:00:00Z",
      publicationDigest: "sha256:pub102",
      authorityStatus: "CERTIFIED",
      generationId: s1.generationId,
      plotId: s1.plotScope.plotId,
      tenantId: s1.ownerScope.tenantId,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });

  assert.equal(s2.publication.snapshotId, "snapshot-102");
  assert.equal(s2.clocks.scientificAsOf, "2026-11-14T08:00:00Z");
  assert.equal(s2.selectedEntity.id, "zone-alpha");
  assert.ok(
    s2.selectedEntity.metadata?.crossSnapshotWarning,
    "Cross-snapshot warning must be attached when entity was chosen from an older snapshot"
  );
});

test("P03 Reducer: TIME_SET classifies historical vs latest and preserves operational clock", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });
  const s1 = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-1",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:1",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: s0.plotScope.plotId,
      tenantId: s0.ownerScope.tenantId,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });

  // Attach live telemetry timestamp
  const s2 = workspaceReducer(s1, {
    type: "TELEMETRY_SYNCED",
    payload: {
      observedAt: "2026-11-14T11:55:00Z",
    },
  });
  assert.equal(s2.clocks.operationalObserved, "2026-11-14T11:55:00Z");

  // Move time cursor back to 3 days ago
  const s3 = workspaceReducer(s2, {
    type: "TIME_SET",
    payload: {
      cursorTimestamp: "2026-11-11T12:00:00Z",
    },
  });

  assert.equal(s3.clocks.cursorTimestamp, "2026-11-11T12:00:00Z");
  assert.equal(s3.clocks.activeTimeMode, "HISTORICAL");
  // Operational observed time must remain intact!
  assert.equal(s3.clocks.operationalObserved, "2026-11-14T11:55:00Z");
});

test("P03 Reducer: SCENARIO_STARTED enters sandbox mode without modifying scientificAsOf clock", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });
  const s1 = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-certified",
      capturedAt: "2026-11-14T09:00:00Z",
      publicationDigest: "sha256:cert",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: s0.plotScope.plotId,
      tenantId: s0.ownerScope.tenantId,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });

  const s2 = workspaceReducer(s1, {
    type: "SCENARIO_STARTED",
    payload: {
      scenarioId: "sc-whatif-01",
      scenarioName: "Precipitation Deficit",
      parameters: { rainfall_reduction: 0.5 },
    },
  });

  assert.equal(s2.scenario.isActive, true);
  assert.equal(s2.clocks.activeTimeMode, "SCENARIO");
  assert.equal(s2.clocks.scientificAsOf, "2026-11-14T09:00:00Z", "Scientific asOf must remain untouched in scenario");

  const s3 = workspaceReducer(s2, { type: "SCENARIO_ENDED" });
  assert.equal(s3.scenario.isActive, false);
  assert.equal(s3.clocks.activeTimeMode, "LATEST");
});

test("P03 Reducer: SCENARIO_STARTED is pure and deterministic (no Date.now() or new Date() side-effects)", () => {
  const s0 = createInitialWorkspaceState();
  const action = {
    type: "SCENARIO_STARTED",
    payload: {
      scenarioId: "sc-fixed-id",
      scenarioName: "Deterministic Drought",
      parameters: { et0: 1.2 },
      simulationTime: "2026-11-14T12:00:00Z",
    },
  };

  const res1 = workspaceReducer(s0, action);
  const res2 = workspaceReducer(s0, action);

  assert.deepEqual(res1, res2, "Reducer outputs must be strictly deterministic across calls");
  assert.equal(res1.scenario.scenarioId, "sc-fixed-id");
  assert.equal(res1.clocks.scenarioSimulationTime, "2026-11-14T12:00:00Z");
});

test("P03 Reducer: SNAPSHOT_SELECTED enforces generation, plot, tenant, and crop cycle scoping", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-A",
    farmId: "farm-A",
    plotId: "plot-A",
    cropCycleId: "cycle-A",
  });

  // 1. Stale generationId must be rejected
  const sStaleGen = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-late-gen",
      generationId: s0.generationId - 1,
      plotId: "plot-A",
      tenantId: "tenant-A",
    },
  });
  assert.equal(sStaleGen, s0, "Snapshot targeting stale generationId must be rejected");

  // 2. Mismatched plotId must be rejected
  const sWrongPlot = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-wrong-plot",
      generationId: s0.generationId,
      plotId: "plot-FOREIGN",
      tenantId: "tenant-A",
    },
  });
  assert.equal(sWrongPlot, s0, "Snapshot targeting foreign plotId must be rejected");

  // 3. Mismatched tenantId must be rejected
  const sWrongTenant = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-wrong-tenant",
      generationId: s0.generationId,
      plotId: "plot-A",
      tenantId: "tenant-FOREIGN",
    },
  });
  assert.equal(sWrongTenant, s0, "Snapshot targeting foreign tenantId must be rejected");

  // 4. Mismatched cropCycleId must be rejected
  const sWrongCycle = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-wrong-cycle",
      generationId: s0.generationId,
      plotId: "plot-A",
      tenantId: "tenant-A",
      cropCycleId: "cycle-OTHER",
    },
  });
  assert.equal(sWrongCycle, s0, "Snapshot targeting foreign cropCycleId must be rejected");

  // 5. Cleared snapshot (snapshotId: null) explicitly marks UNAVAILABLE and isStale
  const sValid = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-valid",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:valid",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-A",
      tenantId: "tenant-A",
      cropCycleId: "cycle-A",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sValid.publication.snapshotId, "snap-valid");
  assert.equal(sValid.publication.authorityStatus, "CERTIFIED");

  // Invalidation with stale generation or foreign plot must be REJECTED (P03-R1-F05)
  const sStaleInvalidation = workspaceReducer(sValid, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: null,
      authorityStatus: "UNAVAILABLE",
      generationId: sValid.generationId - 1, // Stale generation
      plotId: "plot-A",
      tenantId: "tenant-A",
    },
  });
  assert.equal(sStaleInvalidation, sValid, "Stale invalidation action must be rejected without clearing publication");

  // Valid scoped invalidation clears publication
  const sCleared = workspaceReducer(sValid, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: null,
      authorityStatus: "UNAVAILABLE",
      generationId: sValid.generationId,
      plotId: "plot-A",
      tenantId: "tenant-A",
      cropCycleId: "cycle-A",
    },
  });
  assert.equal(sCleared.publication.snapshotId, null);
  assert.equal(sCleared.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(sCleared.publication.isStale, true);

  // 6. Unauthoritative CERTIFIED assertion is demoted to PENDING (P03-R1-F06)
  const sForgedCert = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-forged",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:forged",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-A",
      tenantId: "tenant-A",
      // source is missing or not PARCEL_ASSESSMENT_AUTHORITY
    },
  });
  assert.equal(sForgedCert.publication.authorityStatus, "PENDING", "Unauthoritative CERTIFIED assertion must be demoted to PENDING");
});

test("P03 Reducer: TIME_SET classifies FORECAST when cursor is past operational telemetry", () => {
  let state = createInitialWorkspaceState();
  state = workspaceReducer(state, {
    type: "TELEMETRY_SYNCED",
    payload: { observedAt: "2026-11-14T12:00:00Z" },
  });

  // Cursor placed 6 hours into future
  state = workspaceReducer(state, {
    type: "TIME_SET",
    payload: { cursorTimestamp: "2026-11-14T18:00:00Z" },
  });

  assert.equal(state.clocks.activeTimeMode, "FORECAST");
});

test("P03 Reducer: REQUEST_INVALIDATED marks uncertified publication UNAVAILABLE and stale", () => {
  let state = createInitialWorkspaceState();
  state = {
    ...state,
    publication: {
      snapshotId: "pending-snap",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:pending",
      authorityStatus: "PENDING",
      isStale: false,
    },
  };

  const next = workspaceReducer(state, {
    type: "REQUEST_INVALIDATED",
    payload: { reason: "network_timeout" },
  });

  assert.equal(next.generationId, state.generationId + 1);
  assert.equal(next.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(next.publication.isStale, true);
  assert.equal(next.activeError, "network_timeout");
});

test("P03 Reducer: PLOT_CHANGED invalidates when geometryVersion changes", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-1",
    geometryHash: "gh-1",
    geometryVersion: 1,
  });

  const s1 = workspaceReducer(s0, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-1",
        farmId: "farm-1",
        plotId: "plot-1",
        cropCycleId: "cycle-1",
        geometryHash: "gh-1",
        geometryVersion: 2, // version incremented
      },
    },
  });

  assert.notEqual(s1, s0);
  assert.equal(s1.generationId, s0.generationId + 1, "Geometry version change must bump generation");
  assert.equal(s1.plotScope.geometryVersion, 2);
});

test("P03 Reducer: SNAPSHOT_SELECTED enforces geometryHash and geometryVersion checks", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-1",
    geometryHash: "gh-canonical-1",
    geometryVersion: 1,
  });

  // 1. Mismatched geometryHash must be rejected
  const sMismatchedHash = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-1",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:abc",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
      geometryHash: "gh-different-2", // Mismatched
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sMismatchedHash, s0, "Mismatched geometryHash must be rejected without altering state");

  // 2. Mismatched geometryVersion must be rejected
  const sMismatchedVersion = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-1",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:abc",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
      geometryHash: "gh-canonical-1",
      geometryVersion: 99, // Mismatched version
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sMismatchedVersion, s0, "Mismatched geometryVersion must be rejected without altering state");

  // 3. Matching geometryHash and geometryVersion succeeds
  const sMatching = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-1",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:abc",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
      geometryHash: "gh-canonical-1",
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.notEqual(sMatching, s0);
  assert.equal(sMatching.publication.snapshotId, "snap-1");
  assert.equal(sMatching.publication.authorityStatus, "CERTIFIED");
});

test("P03 Reducer (R3-F04): SNAPSHOT_SELECTED enforces exact cropCycleId and geometryHash equality", () => {
  const s0 = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-autumn-2026",
    geometryHash: "gh-canonical-exact",
    geometryVersion: 1,
  });

  // 1. Mismatched geometryHash when specified must be rejected
  const sMismatchedGeom = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-1",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:abc",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-autumn-2026",
      geometryHash: "gh-canonical-wrong",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sMismatchedGeom, s0, "Mismatched geometryHash must reject snapshot selection");

  // 2. Mismatched cropCycleId when specified must be rejected
  const sMismatchedCycle = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-1",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:abc",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-autumn-different",
      geometryHash: "gh-canonical-exact",
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sMismatchedCycle, s0, "Mismatched cropCycleId must reject snapshot selection");

  // 3. Invalidation action with snapshotId: null clears active publication
  const sActive = workspaceReducer(s0, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-1",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:abc",
      authorityStatus: "CERTIFIED",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-autumn-2026",
      geometryHash: "gh-canonical-exact",
      geometryVersion: 1,
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(sActive.publication.authorityStatus, "CERTIFIED");

  const sInvalidated = workspaceReducer(sActive, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: null,
      capturedAt: null,
      publicationDigest: null,
      authorityStatus: "UNAVAILABLE",
      generationId: s0.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-autumn-2026",
      geometryHash: "gh-canonical-exact",
      geometryVersion: 1,
      source: "SYSTEM_WORKSPACE_INVALIDATION",
    },
  });
  assert.equal(sInvalidated.publication.snapshotId, null);
  assert.equal(sInvalidated.publication.authorityStatus, "UNAVAILABLE");
  assert.equal(sInvalidated.publication.isStale, true);
});

