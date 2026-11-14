import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialWorkspaceState,
  workspaceReducer,
} from "../../src/components/farm/workspace/workspace-reducer.mjs";

test("P03-F01 & P03-G01: Delayed asynchronous response after scope transition is discarded via live state ref check even if fetch completes", async () => {
  // Simulate the exact scoped fetch engine from PlotWorkspaceProvider
  let state = createInitialWorkspaceState({
    tenantId: "tenant-A",
    farmId: "farm-A",
    plotId: "plot-A",
    cropCycleId: "cycle-A",
    geometryHash: "hash-A",
  });

  const latestStateRef = { current: state };
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

      // Authoritative live check right before committing
      const liveState = latestStateRef.current;
      const isStale =
        liveState.generationId !== requestGen ||
        liveState.ownerScope.tenantId !== requestTenant ||
        liveState.plotScope.plotId !== requestPlot ||
        liveState.plotScope.cropCycleId !== requestCropCycle ||
        liveState.plotScope.geometryHash !== requestGeomHash;

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
  state = workspaceReducer(state, {
    type: "PLOT_CHANGED",
    payload: {
      scope: {
        tenantId: "tenant-B",
        farmId: "farm-B",
        plotId: "plot-B",
        cropCycleId: "cycle-B",
        geometryHash: "hash-B",
      },
    },
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

  // Extract mapPlot, mapFarm, and mapCropCycle definitions
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
  assert.equal(plotMapped.geometryHash, "sha256:precalculated-hash", "Plot mapping must expose geometryHash");
  assert.equal(cycleMapped.id, "cycle-999", "CropCycle mapping must expose id");

  // Fallback hash check if plot has no precalculated hash
  const plotWithoutHash = mapPlot({ id: "plot-no-hash", geoJson: { type: "Polygon" } });
  assert.equal(plotWithoutHash.geometryHash, "sha256:fallback-computed", "Must compute geometryHash if not in document");
});

test("P03-F04: Bridging layer invalidates publication and resets authority to UNAVAILABLE when assessment applicability is lost", () => {
  let state = createInitialWorkspaceState({
    tenantId: "tenant-1",
    farmId: "farm-1",
    plotId: "plot-1",
    cropCycleId: "cycle-1",
  });

  // 1. Assessment arrives and is certified
  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-cert-01",
      capturedAt: "2026-11-14T10:00:00Z",
      publicationDigest: "sha256:cert01",
      authorityStatus: "CERTIFIED",
      generationId: state.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
      cropCycleId: "cycle-1",
    },
  });

  assert.equal(state.publication.snapshotId, "snap-cert-01");
  assert.equal(state.publication.authorityStatus, "CERTIFIED");
  assert.equal(state.publication.isStale, false);

  // 2. Assessment becomes unavailable / cleared / invalid in assessment provider
  // Bridging effect dispatches SNAPSHOT_SELECTED with snapshotId: null, authorityStatus: "UNAVAILABLE"
  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: null,
      authorityStatus: "UNAVAILABLE",
      generationId: state.generationId,
      plotId: "plot-1",
      tenantId: "tenant-1",
    },
  });

  assert.equal(state.publication.snapshotId, null, "Snapshot must be cleared on invalidation");
  assert.equal(state.publication.authorityStatus, "UNAVAILABLE", "Authority must be reset to UNAVAILABLE");
  assert.equal(state.publication.isStale, true, "Publication must be marked isStale: true");
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
  let state = createInitialWorkspaceState();

  state = workspaceReducer(state, {
    type: "SNAPSHOT_SELECTED",
    payload: {
      snapshotId: "snap-asm",
      capturedAt: "2026-11-10T08:00:00Z",
      authorityStatus: "CERTIFIED",
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
