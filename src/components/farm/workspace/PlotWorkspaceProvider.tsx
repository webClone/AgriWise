"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";
import {
  createInitialWorkspaceState,
  workspaceReducer,
} from "./workspace-reducer";
import type {
  WorkspaceState,
  WorkspaceAction,
  PlotScope,
  SelectedEntityRef,
  EntityKind,
  TimeClockMode,
  RenderIntent,
} from "./workspace-types";

/**
 * Public workspace API exposed to UI components, inspectors, docks, and tools.
 * In accordance with P03-R4-F05, this interface exposes only controlled, safe
 * workspace actions. It strictly omits raw reducer dispatch and publication-authority
 * mutation so tool consumers cannot fabricate or tamper with scientific certification.
 */
export interface PlotWorkspacePublicApi {
  state: WorkspaceState;
  selectEntity: (entity: {
    kind: EntityKind;
    id: string | null;
    sourceSnapshotId?: string | null;
    metadata?: Record<string, unknown>;
  }) => void;
  clearSelection: () => void;
  setActiveTool: (tool: string) => void;
  setTimeCursor: (timestamp: string, mode?: TimeClockMode) => void;
  setRenderIntent: (intent: Partial<RenderIntent>) => void;
  toggleVectorVisibility: (vectorKey: string, visible?: boolean) => void;
  toggleInspector: (collapsed?: boolean) => void;
  invalidateRequests: (reason?: string) => void;
  createScopedFetch: (
    url: string,
    init?: RequestInit
  ) => Promise<{ ok: boolean; status: number; data: any; isStale: boolean }>;
}

export type PlotWorkspaceContextValue = PlotWorkspacePublicApi;

/**
 * Dedicated internal bridging authority interface.
 * Exclusively consumed by the scientific state bridge (useWorkspaceStateBridging).
 * This establishes the scientific bridge as the sole path for introducing validated
 * publication references into the UI store (P03-R4-F05).
 */
export interface PlotWorkspaceBridgeApi {
  bridgePublication: (payload: {
    snapshotId: string;
    capturedAt: string | null;
    publicationDigest: string | null;
    generationId: number;
    plotId: string;
    tenantId: string;
    cropCycleId?: string | null;
    geometryHash?: string | null;
    geometryVersion?: number | string | null;
  }) => void;
  invalidatePublication: (payload: {
    generationId: number;
    plotId: string;
    tenantId: string;
    cropCycleId?: string | null;
    geometryHash?: string | null;
    geometryVersion?: number | string | null;
  }) => void;
  syncTelemetry: (observedAt: string) => void;
  setRenderIntentActiveLens: (activeLens: string) => void;
  selectZoneEntity: (zoneId: string, snapshotId: string | null) => void;
}

const PlotWorkspaceContext = createContext<PlotWorkspacePublicApi | null>(null);
const PlotWorkspaceBridgeContext = createContext<PlotWorkspaceBridgeApi | null>(null);

export interface PlotWorkspaceProviderProps {
  scope: PlotScope;
  initialTool?: string;
  children: ReactNode;
}

export function PlotWorkspaceProvider({
  scope,
  initialTool = "map",
  children,
}: PlotWorkspaceProviderProps) {
  const [state, dispatch] = useReducer(
    workspaceReducer,
    createInitialWorkspaceState({ ...scope, initialTool })
  );

  // Keep an authoritative live reference to current state
  // to avoid stale closure pitfalls during asynchronous operations (P03-F01)
  const latestStateRef = useRef<WorkspaceState>(state);
  latestStateRef.current = state;

  // Track incoming verified scope props synchronously during render to close
  // the render-to-effect timing gap when plot transitions occur
  const incomingScopeRef = useRef<PlotScope>(scope);
  incomingScopeRef.current = scope;

  // Track each concurrent request by a unique ID so concurrent requests in the same
  // generation never overwrite each other's abort controllers (P03-F02)
  interface ActiveRequestEntry {
    requestId: string;
    generationId: number;
    tenantId: string;
    plotId: string;
    cropCycleId: string | null;
    geometryHash: string | null;
    controller: AbortController;
  }
  const nextRequestIdRef = useRef(0);
  const activeRequestsRef = useRef<Map<string, ActiveRequestEntry>>(new Map());

  // Detect server-passed scope changes and dispatch PLOT_CHANGED
  useEffect(() => {
    dispatch({
      type: "PLOT_CHANGED",
      payload: { scope },
    });
  }, [
    scope.tenantId,
    scope.farmId,
    scope.plotId,
    scope.cropCycleId,
    scope.geometryHash,
    scope.geometryVersion,
  ]);

  // Abort stale requests when generation increments or scope changes
  useEffect(() => {
    const currentGen = state.generationId;
    const currentTenant = state.ownerScope.tenantId;
    const currentPlot = state.plotScope.plotId;
    const currentCropCycle = state.plotScope.cropCycleId;
    const currentGeomHash = state.plotScope.geometryHash;

    activeRequestsRef.current.forEach((entry, reqId) => {
      const isStale =
        entry.generationId < currentGen ||
        entry.tenantId !== currentTenant ||
        entry.plotId !== currentPlot ||
        entry.cropCycleId !== currentCropCycle ||
        entry.geometryHash !== currentGeomHash;

      if (isStale) {
        try {
          entry.controller.abort("Workspace generation/scope invalidated by plot or tenant switch");
        } catch {
          // ignore abort errors
        }
        activeRequestsRef.current.delete(reqId);
      }
    });
  }, [
    state.generationId,
    state.ownerScope.tenantId,
    state.plotScope.plotId,
    state.plotScope.cropCycleId,
    state.plotScope.geometryHash,
  ]);

  // Clean up all active requests on unmount
  useEffect(() => {
    return () => {
      activeRequestsRef.current.forEach((entry) => {
        try {
          entry.controller.abort("PlotWorkspaceProvider unmounted");
        } catch {
          // ignore
        }
      });
      activeRequestsRef.current.clear();
    };
  }, []);

  // Scoped fetch helper that automatically binds to generation, tenant and plot,
  // tracks request-specific controllers, and discards late responses using live refs (P03-F01/P03-F02)
  const createScopedFetch = useCallback(
    async (url: string, init?: RequestInit) => {
      const currentState = latestStateRef.current;
      const requestGen = currentState.generationId;
      const requestTenant = currentState.ownerScope.tenantId;
      const requestPlot = currentState.plotScope.plotId;
      const requestCropCycle = currentState.plotScope.cropCycleId;
      const requestGeomHash = currentState.plotScope.geometryHash;

      const reqId = `req_${++nextRequestIdRef.current}_${Date.now()}`;
      const controller = new AbortController();

      activeRequestsRef.current.set(reqId, {
        requestId: reqId,
        generationId: requestGen,
        tenantId: requestTenant,
        plotId: requestPlot,
        cropCycleId: requestCropCycle,
        geometryHash: requestGeomHash,
        controller,
      });

      const combinedSignal = init?.signal
        ? anySignal([init.signal, controller.signal])
        : controller.signal;

      try {
        const response = await fetch(url, {
          ...init,
          signal: combinedSignal,
          headers: {
            ...init?.headers,
            "x-akaloris-generation": String(requestGen),
            "x-akaloris-plot-scope": `${requestTenant}:${requestPlot}`,
          },
        });

        let data = null;
        try {
          data = await response.json();
        } catch {
          data = null;
        }

        // Live check against authoritative latestStateRef AND incomingScopeRef right before returning or committing:
        const liveState = latestStateRef.current;
        const liveScope = incomingScopeRef.current;
        const isStale =
          liveState.generationId !== requestGen ||
          liveState.ownerScope.tenantId !== requestTenant ||
          liveState.plotScope.plotId !== requestPlot ||
          liveState.plotScope.cropCycleId !== requestCropCycle ||
          liveState.plotScope.geometryHash !== requestGeomHash ||
          liveScope.plotId !== requestPlot ||
          liveScope.tenantId !== requestTenant ||
          liveScope.cropCycleId !== requestCropCycle ||
          liveScope.geometryHash !== requestGeomHash;

        return {
          ok: response.ok && !isStale,
          status: response.status,
          data: isStale ? null : data,
          isStale,
        };
      } catch (err: any) {
        const isAbort = err?.name === "AbortError";
        return {
          ok: false,
          status: isAbort ? 499 : 500,
          data: null,
          isStale: true,
        };
      } finally {
        activeRequestsRef.current.delete(reqId);
      }
    },
    []
  );

  const selectEntity = useCallback(
    (entity: {
      kind: EntityKind;
      id: string | null;
      sourceSnapshotId?: string | null;
      metadata?: Record<string, unknown>;
    }) => {
      dispatch({
        type: "ENTITY_SELECTED",
        payload: {
          kind: entity.kind,
          id: entity.id,
          sourceSnapshotId: entity.sourceSnapshotId || state.publication.snapshotId,
          timestamp: state.clocks.cursorTimestamp,
          metadata: entity.metadata,
        },
      });
    },
    [state.publication.snapshotId, state.clocks.cursorTimestamp]
  );

  const clearSelection = useCallback(() => {
    dispatch({
      type: "ENTITY_SELECTED",
      payload: {
        kind: null,
        id: null,
        sourceSnapshotId: null,
        timestamp: null,
      },
    });
  }, []);

  const setActiveTool = useCallback((tool: string) => {
    dispatch({
      type: "ACTIVE_TOOL_CHANGED",
      payload: { tool },
    });
  }, []);

  const setTimeCursor = useCallback(
    (timestamp: string, mode?: TimeClockMode) => {
      dispatch({
        type: "TIME_SET",
        payload: { cursorTimestamp: timestamp, mode },
      });
    },
    []
  );

  const setRenderIntent = useCallback((intent: Partial<RenderIntent>) => {
    dispatch({
      type: "RENDER_INTENT_SET",
      payload: intent,
    });
  }, []);

  const toggleVectorVisibility = useCallback(
    (vectorKey: string, visible?: boolean) => {
      const isVisible =
        typeof visible === "boolean"
          ? visible
          : !state.renderIntent.visibleVectors[vectorKey];
      dispatch({
        type: "VECTOR_VISIBILITY_SET",
        payload: { vectorKey, visible: isVisible },
      });
    },
    [state.renderIntent.visibleVectors]
  );

  const toggleInspector = useCallback((collapsed?: boolean) => {
    dispatch({
      type: "INSPECTOR_TOGGLED",
      payload: typeof collapsed === "boolean" ? { collapsed } : undefined,
    });
  }, []);

  const invalidateRequests = useCallback((reason = "manual_invalidation") => {
    dispatch({
      type: "REQUEST_INVALIDATED",
      payload: { reason },
    });
  }, []);

  const bridgePublication = useCallback(
    (payload: {
      snapshotId: string;
      capturedAt: string | null;
      publicationDigest: string | null;
      generationId: number;
      plotId: string;
      tenantId: string;
      cropCycleId?: string | null;
      geometryHash?: string | null;
      geometryVersion?: number | string | null;
    }) => {
      dispatch({
        type: "SNAPSHOT_SELECTED",
        payload: {
          snapshotId: payload.snapshotId,
          capturedAt: payload.capturedAt,
          publicationDigest: payload.publicationDigest,
          authorityStatus: "CERTIFIED",
          generationId: payload.generationId,
          plotId: payload.plotId,
          tenantId: payload.tenantId,
          cropCycleId: payload.cropCycleId,
          geometryHash: payload.geometryHash,
          geometryVersion: payload.geometryVersion,
          source: "PARCEL_ASSESSMENT_AUTHORITY",
        },
      });
    },
    []
  );

  const invalidatePublication = useCallback(
    (payload: {
      generationId: number;
      plotId: string;
      tenantId: string;
      cropCycleId?: string | null;
      geometryHash?: string | null;
      geometryVersion?: number | string | null;
    }) => {
      dispatch({
        type: "SNAPSHOT_SELECTED",
        payload: {
          snapshotId: null,
          capturedAt: null,
          publicationDigest: null,
          authorityStatus: "UNAVAILABLE",
          generationId: payload.generationId,
          plotId: payload.plotId,
          tenantId: payload.tenantId,
          cropCycleId: payload.cropCycleId,
          geometryHash: payload.geometryHash,
          geometryVersion: payload.geometryVersion,
          source: "SYSTEM_WORKSPACE_INVALIDATION",
        },
      });
    },
    []
  );

  const syncTelemetry = useCallback((observedAt: string) => {
    dispatch({
      type: "TELEMETRY_SYNCED",
      payload: { observedAt },
    });
  }, []);

  const setRenderIntentActiveLens = useCallback((activeLens: string) => {
    dispatch({
      type: "RENDER_INTENT_SET",
      payload: { activeLens },
    });
  }, []);

  const selectZoneEntity = useCallback((zoneId: string, snapshotId: string | null) => {
    dispatch({
      type: "ENTITY_SELECTED",
      payload: {
        kind: "ZONE",
        id: zoneId,
        sourceSnapshotId: snapshotId,
        timestamp: latestStateRef.current.clocks.cursorTimestamp,
      },
    });
  }, []);

  const bridgeValue = useMemo<PlotWorkspaceBridgeApi>(
    () => ({
      bridgePublication,
      invalidatePublication,
      syncTelemetry,
      setRenderIntentActiveLens,
      selectZoneEntity,
    }),
    [
      bridgePublication,
      invalidatePublication,
      syncTelemetry,
      setRenderIntentActiveLens,
      selectZoneEntity,
    ]
  );

  const contextValue = useMemo<PlotWorkspacePublicApi>(
    () => ({
      state,
      selectEntity,
      clearSelection,
      setActiveTool,
      setTimeCursor,
      setRenderIntent,
      toggleVectorVisibility,
      toggleInspector,
      invalidateRequests,
      createScopedFetch,
    }),
    [
      state,
      selectEntity,
      clearSelection,
      setActiveTool,
      setTimeCursor,
      setRenderIntent,
      toggleVectorVisibility,
      toggleInspector,
      invalidateRequests,
      createScopedFetch,
    ]
  );

  return (
    <PlotWorkspaceContext.Provider value={contextValue}>
      <PlotWorkspaceBridgeContext.Provider value={bridgeValue}>
        {children}
      </PlotWorkspaceBridgeContext.Provider>
    </PlotWorkspaceContext.Provider>
  );
}

// Polyfill/helper for combining abort signals
function anySignal(signals: AbortSignal[]): AbortSignal {
  if (typeof (AbortSignal as any).any === "function") {
    return (AbortSignal as any).any(signals);
  }
  const controller = new AbortController();
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), {
      once: true,
    });
  }
  return controller.signal;
}

export function usePlotWorkspace(): PlotWorkspacePublicApi {
  const context = useContext(PlotWorkspaceContext);
  if (!context) {
    throw new Error(
      "usePlotWorkspace must be used within a PlotWorkspaceProvider"
    );
  }
  return context;
}

export function usePlotWorkspaceBridge(): PlotWorkspaceBridgeApi {
  const context = useContext(PlotWorkspaceBridgeContext);
  if (!context) {
    throw new Error(
      "usePlotWorkspaceBridge must be used within a PlotWorkspaceProvider"
    );
  }
  return context;
}

export function usePlotWorkspaceScope(): PlotScope {
  return usePlotWorkspace().state.plotScope;
}

export function usePlotWorkspaceSelection(): SelectedEntityRef {
  return usePlotWorkspace().state.selectedEntity;
}

export function usePlotWorkspaceClocks() {
  return usePlotWorkspace().state.clocks;
}

export function usePlotWorkspaceTool() {
  const { state, setActiveTool } = usePlotWorkspace();
  return {
    activeTool: state.activeTool,
    setActiveTool,
  };
}
