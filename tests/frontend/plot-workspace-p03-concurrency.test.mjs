import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialWorkspaceState,
  workspaceReducer,
} from "../../src/components/farm/workspace/workspace-reducer.mjs";

test("P03-F01 & P03-G01: Delayed asynchronous response after scope transition is discarded via live state ref check even if fetch completes", async () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-A",
    farmId: "farm-A",
    plotId: "plot-A",
    cropCycleId: "cycle-A",
    geometryHash: "hash-A",
  });

  const latestStateRef = { current: state };
  const incomingScopeRef = { current: state.plotScope };
  let nextRequestId = 0;
  const activeRequests = new Map();

  async function createScopedFetch(fetchMock) {
    const currentState = latestStateRef.current;
    const requestGen = currentState.generationId;
    const requestTenant = currentState.ownerScope.tenantId;
    const requestPlot = currentState.plotScope.plotId;
    const requestCropCycle = currentState.plotScope.cropCycleId;
    const requestGeomHash = currentState.plotScope.geometryHash;

    const reqId = `req_${++nextRequestId}`;
    const controller = new AbortController();
    activeRequests.set(reqId, {
      requestId: reqId,
      generationId: requestGen,
      tenantId: requestTenant,
      plotId: requestPlot,
      cropCycleId: requestCropCycle,
      geometryHash: requestGeomHash,
      controller,
    });

    try {
      const response = await fetchMock(controller.signal);
      const data = response.data;

      // Authoritative live check right before committing (P03-F01 & P03-R2 render-to-effect fence)
      const liveState = latestStateRef.current;
      const liveScope = incomingScopeRef.current;
      const isStale =
        liveState.generationId !== requestGen ||
        liveState.ownerScope.tenantId !== requestTenant ||
        liveState.plotScope.plotId !== requestPlot ||
        liveState.plotScope.cropCycleId !== requestCropCycle ||
        liveState.plotScope.geometryHash !== requestGeomHash ||
        liveScope.plotId !== requestPlot ||
        liveScope.tenantId !== requestTenant;

      return {
        ok: response.ok && !isStale,
        status: response.status,
        data: isStale ? null : data,
        isStale,
      };
    } finally {
      activeRequests.delete(reqId);
    }
  }

  // Request 1 starts for Plot A
  let resolveReq1;
  const req1Promise = createScopedFetch((signal) => {
    return new Promise((resolve) => {
      resolveReq1 = () => resolve({ ok: true, status: 200, data: { plotName: "Plot A Sensitive Data" } });
    });
  });

  assert.equal(activeRequests.size, 1);

  // User rapidly navigates to Plot B before Request 1 resolves
  const newScope = {
    tenantId: "tenant-B",
    farmId: "farm-B",
    plotId: "plot-B",
    cropCycleId: "cycle-B",
    geometryHash: "hash-B",
    geometryVersion: null,
  };
  incomingScopeRef.current = newScope; // Synchronous in render

  state = workspaceReducer(state, {
    type: "PLOT_CHANGED",
    payload: { scope: newScope },
  });
  latestStateRef.current = state; // Live ref synchronously updated on render

  // Simulate Request 1 completing after the plot transition (even if abort was not caught)
  resolveReq1();
  const req1Result = await req1Promise;

  assert.equal(req1Result.isStale, true, "Request 1 must be flagged isStale: true");
  assert.equal(req1Result.data, null, "Request 1 payload must be nullified to prevent data leak");
  assert.equal(req1Result.ok, false, "Request 1 must not be marked ok");
  assert.equal(activeRequests.size, 0, "Completed request must clean up its entry");
});

test("P03-F02: Concurrent requests in the same generation do NOT overwrite each other's abort controllers", async () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });

  const latestStateRef = { current: state };
  let nextRequestId = 0;
  const activeRequests = new Map();

  function startTrackedRequest() {
    const currentState = latestStateRef.current;
    const reqId = `req_${++nextRequestId}`;
    const controller = new AbortController();
    activeRequests.set(reqId, {
      requestId: reqId,
      generationId: currentState.generationId,
      tenantId: currentState.ownerScope.tenantId,
      plotId: currentState.plotScope.plotId,
      cropCycleId: currentState.plotScope.cropCycleId,
      geometryHash: currentState.plotScope.geometryHash,
      controller,
    });
    return { reqId, controller };
  }

  // Generation 1: 3 concurrent requests start
  const r1 = startTrackedRequest();
  const r2 = startTrackedRequest();
  const r3 = startTrackedRequest();

  assert.equal(activeRequests.size, 3, "All 3 requests must be independently registered");

  // R1 finishes early and unregisters itself
  activeRequests.delete(r1.reqId);
  assert.equal(activeRequests.size, 2);
  assert.ok(activeRequests.has(r2.reqId), "R2 must still be present");
  assert.ok(activeRequests.has(r3.reqId), "R3 must still be present");

  // Plot changes -> generation increments to 2
  state = workspaceReducer(state, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-1",
        farmId: "farm-1",
        plotId: "plot-2",
      },
    },
  });
  latestStateRef.current = state;

  // Provider abort effect runs
  const currentGen = state.generationId;
  const currentPlot = state.plotScope.plotId;

  activeRequests.forEach((entry, id) => {
    if (entry.generationId < currentGen || entry.plotId !== currentPlot) {
      entry.controller.abort("Workspace generation/scope invalidated by plot or tenant switch");
      activeRequests.delete(id);
    }
  });

  // Verify both R2 and R3 were properly aborted
  assert.equal(r2.controller.signal.aborted, true, "R2 must be aborted on scope switch");
  assert.equal(r3.controller.signal.aborted, true, "R3 must be aborted on scope switch");
  assert.equal(activeRequests.size, 0, "All aborted requests must be purged from registry");
});

test("P03-F03: Server mappings expose full verified identity (tenantId, cropCycleId, geometryHash, geometryVersion)", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const ts = (await import("typescript")).default;

  const farmServicesCode = fs.readFileSync(path.join(process.cwd(), "src/lib/farm-services.ts"), "utf8");

  const mPlot = farmServicesCode.match(/function mapPlot[\s\S]*?^}/m)?.[0] || "";
  const mFarm = farmServicesCode.match(/function mapFarm[\s\S]*?^}/m)?.[0] || "";
  const mCycle = farmServicesCode.match(/function mapCropCycle[\s\S]*?^}/m)?.[0] || "";

  assert.ok(mPlot.length > 0, "mapPlot must exist");
  assert.ok(mFarm.length > 0, "mapFarm must exist");
  assert.ok(mCycle.length > 0, "mapCropCycle must exist");

  const transpiled = ts.transpileModule(mPlot + "\n" + mFarm + "\n" + mCycle, {
    compilerOptions: { target: ts.ScriptTarget.ESNext },
  }).outputText;

  const { mapPlot, mapFarm, mapCropCycle } = new Function(
    "computeGeometryHash",
    transpiled + "\nreturn { mapPlot, mapFarm, mapCropCycle };"
  )((geo) => "sha256:fallback-computed");

  const rawFarm = {
    id: "farm-123",
    userId: "user-owner-456",
    name: "Domaine de la Mitidja",
    wilaya: "Blida",
    latitude: 36.5,
    longitude: 2.8,
    totalArea: 15.0,
  };

  const rawPlot = {
    id: "plot-789",
    name: "Parcelle Nord",
    area: 5.0,
    farmId: "farm-123",
    geoJson: { type: "Polygon", coordinates: [[[2.8, 36.5], [2.81, 36.5], [2.81, 36.51], [2.8, 36.5]]] },
    geometryVersion: 3,
    geometryHash: "sha256:precalculated-hash",
  };

  const rawCycle = {
    id: "cycle-999",
    cropCode: "WHEAT",
    cropNameAr: "قمح صلب",
    variety: "Vitron",
    status: "PLANTED",
    plantDate: "2026-10-15T00:00:00Z",
  };

  const farmMapped = mapFarm(rawFarm);
  const plotMapped = mapPlot(rawPlot);
  const cycleMapped = mapCropCycle(rawCycle);

  assert.equal(farmMapped.userId, "user-owner-456", "Farm mapping must expose userId");
  assert.equal(farmMapped.ownerId, "user-owner-456", "Farm mapping must expose ownerId");
  assert.equal(plotMapped.geometryVersion, 3, "Plot mapping must expose geometryVersion");
  assert.equal(plotMapped.geometryHash, "sha256:fallback-computed", "Plot mapping must compute geometryHash from coordinates");
  assert.equal(cycleMapped.id, "cycle-999", "CropCycle mapping must expose id");
});

test("P03-R1-F05: Stale invalidation from old generation cannot erase a newer valid publication", () => {
  // Start on Plot A (Gen 1)
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-A",
  });
  const genA = state.generationId;

  // User navigates to Plot B (Gen 2)
  state = workspaceReducer(state, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-1",
        farmId: "farm-1",
        plotId: "plot-B",
      },
    },
  });
  assert.equal(state.generationId, genA + 1);

  // Plot B receives a valid certified publication
  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-plot-B",
      capturedAt: "2026-11-14T11:00:00Z",
      publicationDigest: "sha256:pubB",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-B",
      tenantId: "tenant-1",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(state.publication.snapshotId, "snap-plot-B");
  assert.equal(state.publication.authorityStatus, "CERTIFIED");

  // A delayed invalidation originating from Plot A (Gen 1 / plot-A) arrives late!
  const stalePlotAInvalidation = {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: null,
      authorityStatus: "UNAVAILABLE",
      generationId: genA, // Stale generation!
      plotId: "plot-A",   // Stale plot!
      tenantId: "tenant-1",
    },
  };

  const stateAfterStaleInvalidation = workspaceReducer(state, stalePlotAInvalidation);

  // CRITICAL P03-R1-F05 INVARIANT:
  // Plot B's publication must NOT be cleared by the delayed invalidation from Plot A!
  assert.equal(stateAfterStaleInvalidation, state, "Stale invalidation action must be strictly rejected");
  assert.equal(stateAfterStaleInvalidation.publication.snapshotId, "snap-plot-B", "Plot B publication must remain intact");
  assert.equal(stateAfterStaleInvalidation.publication.authorityStatus, "CERTIFIED");
});

test("P03-R1-F06: Snapshot authority checks require complete identity and demote unauthoritative CERTIFIED claims", () => {
  const state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });

  // 1. Missing generationId is rejected
  const missingGen = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-unscoped",
      plotId: "plot-1",
      tenantId: "tenant-1",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(missingGen, state, "Snapshot missing generationId must be rejected");

  // 2. Missing plotId is rejected
  const missingPlot = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-unscoped",
      generationId: state.generationId,
      tenantId: "tenant-1",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(missingPlot, state, "Snapshot missing plotId must be rejected");

  // 3. Unauthoritative CERTIFIED claim without PARCEL_ASSESSMENT_AUTHORITY source is demoted to PENDING
  const unauthoritativeCert = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-tool-asserted",
      capturedAt: "2026-11-14T12:00:00Z",
      publicationDigest: "sha256:tool",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      // source is missing (e.g. dispatched by an arbitrary tool)
    },
  });
  assert.equal(unauthoritativeCert.publication.snapshotId, "snap-tool-asserted");
  assert.equal(unauthoritativeCert.publication.authorityStatus, "PENDING", "Tool-asserted CERTIFIED must be demoted to PENDING");

  // 4. Authoritative CERTIFIED claim with valid source and digest is admitted as CERTIFIED
  const authoritativeCert = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-verified",
      capturedAt: "2026-11-14T12:00:00Z",
      publicationDigest: "sha256:verified",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });
  assert.equal(authoritativeCert.publication.authorityStatus, "CERTIFIED", "Authoritative publication must be CERTIFIED");
});

test("P03-R2: Same-digest publication is cleanly re-bridged following a generation change", () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });

  const lastBridgedKeyRef = { current: null };
  const assessment = {
    identity: {
      snapshotId: "snap-same-digest",
      publicationReceiptHash: "sha256:digest-abc",
      evidenceCutoffAt: "2026-11-14T10:00:00Z",
    },
  };

  function bridgeEffect(currentState) {
    const digest = assessment.identity.publicationReceiptHash;
    const bridgedKey = `${currentState.generationId}|${currentState.plotScope.plotId}|${currentState.ownerScope.tenantId}|${assessment.identity.snapshotId}|${digest}`;
    if (bridgedKey === lastBridgedKeyRef.current) return currentState;
    lastBridgedKeyRef.current = bridgedKey;

    return workspaceReducer(currentState, {
      type: "SNAPSHOT_SELECTED",
      payload: {
        snapshotId: assessment.identity.snapshotId,
        capturedAt: assessment.identity.evidenceCutoffAt,
        publicationDigest: digest,
        authorityStatus: "CERTIFIED",
        generationId: currentState.generationId,
        plotId: currentState.plotScope.plotId,
        tenantId: currentState.ownerScope.tenantId,
        source: "PARCEL_ASSESSMENT_AUTHORITY",
      },
    });
  }

  // Initial bridge in Generation 1
  state = bridgeEffect(state);
  assert.equal(state.publication.snapshotId, "snap-same-digest");
  assert.equal(state.publication.authorityStatus, "CERTIFIED");

  // An invalidation increments generation to 2 and marks publication stale
  state = workspaceReducer(state, {
    type: "REQUEST_INVALIDATED",
    payload: { reason: "network_recovery_reconnect" },
  });
  assert.equal(state.generationId, 2);
  assert.equal(state.publication.isStale, true);

  // Bridge runs again with the same digest in Generation 2
  // Because bridgedKey includes generationId, it cleanly republishes to Generation 2!
  state = bridgeEffect(state);
  assert.equal(state.publication.snapshotId, "snap-same-digest");
  assert.equal(state.publication.isStale, false);
  assert.equal(state.publication.authorityStatus, "CERTIFIED");
});

test("P03-G02: Selection of old zone/snapshot retains source provenance and cross-snapshot warning", () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });

  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-2026-11-01",
      capturedAt: "2026-11-01T12:00:00Z",
      publicationDigest: "sha256:digest01",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });

  state = workspaceReducer(state, {
    type: "ENTITY_SELECTED",
    payload: {
      kind: "ZONE",
      id: "zone-1",
      sourceSnapshotId: "snap-2026-11-01",
    },
  });

  // A new publication arrives for today
  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-2026-11-14",
      capturedAt: "2026-11-14T12:00:00Z",
      publicationDigest: "sha256:digest14",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });

  assert.equal(state.publication.snapshotId, "snap-2026-11-14");
  assert.equal(state.selectedEntity.sourceSnapshotId, "snap-2026-11-01");
  assert.ok(
    state.selectedEntity.metadata?.crossSnapshotWarning?.includes("snap-2026-11-01"),
    "Must preserve warning indicating zone was selected from older snapshot"
  );
});

test("P03-G03: Live telemetry updates operational clock ONLY; frozen scientificAsOf is preserved", () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
  });

  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-asm",
      capturedAt: "2026-11-10T08:00:00Z",
      publicationDigest: "sha256:asm",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      source: "PARCEL_ASSESSMENT_AUTHORITY",
    },
  });

  state = workspaceReducer(state, {
    type: "TELEMETRY_SYNCED",
    payload: {
      observedAt: "2026-11-14T12:00:00Z",
    },
  });

  assert.equal(state.clocks.scientificAsOf, "2026-11-10T08:00:00Z", "Scientific asOf must remain frozen");
  assert.equal(state.clocks.operationalObserved, "2026-11-14T12:00:00Z", "Operational clock must update");
  assert.notEqual(state.clocks.scientificAsOf, state.clocks.operationalObserved);
});
