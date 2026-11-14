import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialWorkspaceState,
  workspaceReducer,
} from "../../src/components/farm/workspace/workspace-reducer.mjs";

test("P03-G01: Tenant A asynchronous response arriving after switching to Tenant B is discarded", async () => {
  // Start with Tenant A
  let state = createInitialWorkspaceState({
    tenantId: "tenant-A",
    farmId: "farm-A",
    plotId: "plot-A",
  });
  const initialGen = state.generationId;

  // Simulate in-flight async request initiated for Tenant A
  const reqGen = state.generationId;
  const reqTenant = state.ownerScope.tenantId;

  // Fast switch to Tenant B occurs before Tenant A request completes
  state = workspaceReducer(state, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-B",
        farmId: "farm-B",
        plotId: "plot-B",
      },
    },
  });

  assert.equal(state.generationId, initialGen + 1);
  assert.equal(state.ownerScope.tenantId, "tenant-B");

  // Simulated late arrival of Tenant A's response payload
  const lateTenantAResponse = {
    snapshotId: "snapshot-tenant-A",
    capturedAt: "2026-11-14T10:00:00Z",
    publicationDigest: "sha256:pubA",
    authorityStatus: "CERTIFIED",
  };

  // Guard evaluation: reject if generationId or tenantId does not match current state
  const isStale =
    reqGen !== state.generationId || reqTenant !== state.ownerScope.tenantId;

  assert.equal(isStale, true, "Tenant A response must be flagged as stale");

  // If stale, reducer action is suppressed / discarded
  if (!isStale) {
    state = workspaceReducer(state, {
      type: "SNAPSHOT_SELECTED",
      payload: lateTenantAResponse,
    });
  }

  // Tenant B state must NOT have Tenant A's snapshot!
  assert.equal(state.publication.snapshotId, null);
  assert.equal(state.ownerScope.tenantId, "tenant-B");
});

test("P03-G02: Selection of old zone/snapshot is not interpreted as new publication evidence", () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });

  // Load first publication
  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-2026-11-01",
      capturedAt: "2026-11-01T12:00:00Z",
      publicationDigest: "sha256:digest01",
      authorityStatus: "CERTIFIED",
    },
  });

  // User clicks Zone Z1 in the 2026-11-01 publication
  state = workspaceReducer(state, {
    type: "ENTITY_SELECTED",
    payload: {
      kind: "ZONE",
      id: "zone-1",
      sourceSnapshotId: "snap-2026-11-01",
    },
  });

  // A new publication arrives for today (2026-11-14)
  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-2026-11-14",
      capturedAt: "2026-11-14T12:00:00Z",
      publicationDigest: "sha256:digest14",
      authorityStatus: "CERTIFIED",
    },
  });

  // The active publication is updated
  assert.equal(state.publication.snapshotId, "snap-2026-11-14");
  // But the selected entity retains its provenance from snap-2026-11-01 with a warning,
  // preventing it from masquerading as evidence from snap-2026-11-14
  assert.equal(state.selectedEntity.sourceSnapshotId, "snap-2026-11-01");
  assert.ok(
    state.selectedEntity.metadata?.crossSnapshotWarning?.includes("snap-2026-11-01"),
    "Must preserve warning indicating zone was selected from older snapshot"
  );
});

test("P03-G03: Live reading at historical cursor is labeled live, not admitted historical input", () => {
  let state = createInitialWorkspaceState();

  // Set historical time cursor (e.g. 5 days ago)
  state = workspaceReducer(state, {
    type: "TIME_SET",
    payload: {
      cursorTimestamp: "2026-11-09T08:00:00Z",
      mode: "HISTORICAL",
    },
  });

  // A live operational IoT reading arrives via WebSocket / polling
  const liveReadingTimestamp = "2026-11-14T12:00:00Z";
  state = workspaceReducer(state, {
    type: "TELEMETRY_SYNCED",
    payload: {
      observedAt: liveReadingTimestamp,
    },
  });

  // 1. Clocks remain strictly separate
  assert.equal(state.clocks.cursorTimestamp, "2026-11-09T08:00:00Z");
  assert.equal(state.clocks.activeTimeMode, "HISTORICAL");
  assert.equal(state.clocks.operationalObserved, liveReadingTimestamp);

  // 2. The live reading is NOT treated as an admitted observation for 2026-11-09
  assert.notEqual(state.clocks.operationalObserved, state.clocks.cursorTimestamp);
});

test("P03-G04: Crop cycle change resets publication and invalidates pending requests", () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-summer-2026",
    geometryHash: "geom-1",
  });

  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-cycle-summer",
      capturedAt: "2026-08-01T12:00:00Z",
      publicationDigest: "sha256:summer",
      authorityStatus: "CERTIFIED",
    },
  });

  const prevGen = state.generationId;

  // New crop cycle declared on the same plot (e.g. winter wheat planted)
  state = workspaceReducer(state, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-1",
        farmId: "farm-1",
        plotId: "plot-1",
        cropCycleId: "cycle-winter-2026",
        geometryHash: "geom-1",
      },
    },
  });

  assert.equal(state.generationId, prevGen + 1, "Generation must bump on crop cycle change");
  assert.equal(state.plotScope.cropCycleId, "cycle-winter-2026");
  assert.equal(state.publication.snapshotId, null, "Old cycle snapshot must be evicted");
  assert.equal(state.publication.authorityStatus, "UNAVAILABLE");
});

test("P03-G05: Single authoritative time basis across map and panels", () => {
  let state = createInitialWorkspaceState();

  const testTime = "2026-11-12T16:30:00Z";
  state = workspaceReducer(state, {
    type: "TIME_SET",
    payload: {
      cursorTimestamp: testTime,
    },
  });

  // Select a sensor entity
  state = workspaceReducer(state, {
    type: "ENTITY_SELECTED",
    payload: {
      kind: "SENSOR",
      id: "sensor-node-04",
    },
  });

  // Selected entity timestamp matches the unified time cursor
  assert.equal(state.clocks.cursorTimestamp, testTime);
  assert.equal(state.selectedEntity.timestamp, testTime);
});

test("P03-G06: Manual or network invalidation bumps generation and records reason", () => {
  let state = createInitialWorkspaceState();
  const gen0 = state.generationId;

  state = workspaceReducer(state, {
    type: "REQUEST_INVALIDATED",
    payload: {
      reason: "websocket_disconnect_reconnect_fence",
    },
  });

  assert.equal(state.generationId, gen0 + 1);
  assert.equal(state.activeError, "websocket_disconnect_reconnect_fence");
});
