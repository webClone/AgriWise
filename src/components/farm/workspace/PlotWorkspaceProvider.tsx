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

interface PlotWorkspaceContextValue {
  state: WorkspaceState;
  dispatch: React.Dispatch<WorkspaceAction>;
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

const PlotWorkspaceContext = createContext<PlotWorkspaceContextValue | null>(null);

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

  // AbortController registry tracking active generation
  const activeControllersRef = useRef<Map<number, AbortController>>(new Map());

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
  ]);

  // Clean up aborted controllers when generation increments
  useEffect(() => {
    const currentGen = state.generationId;
    activeControllersRef.current.forEach((controller, gen) => {
      if (gen < currentGen) {
        controller.abort("Workspace generation invalidated by plot/tenant switch");
        activeControllersRef.current.delete(gen);
      }
    });
  }, [state.generationId]);

  // Scoped fetch helper that automatically binds to generation, tenant and plot,
  // and discards late responses arriving after a scope transition (P03-G01)
  const createScopedFetch = useCallback(
    async (url: string, init?: RequestInit) => {
      const currentGen = state.generationId;
      const currentTenant = state.ownerScope.tenantId;
      const currentPlot = state.plotScope.plotId;

      const controller = new AbortController();
      activeControllersRef.current.set(currentGen, controller);

      const combinedSignal = init?.signal
        ? anySignal([init.signal, controller.signal])
        : controller.signal;

      try {
        const response = await fetch(url, {
          ...init,
          signal: combinedSignal,
          headers: {
            ...init?.headers,
            "x-akaloris-generation": String(currentGen),
            "x-akaloris-plot-scope": `${currentTenant}:${currentPlot}`,
          },
        });

        // Verification after response resolves:
        // Has the workspace changed scope or generation during transit?
        const isStale =
          state.generationId !== currentGen ||
          state.ownerScope.tenantId !== currentTenant ||
          state.plotScope.plotId !== currentPlot;

        let data = null;
        try {
          data = await response.json();
        } catch {
          data = null;
        }

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
        activeControllersRef.current.delete(currentGen);
      }
    },
    [state.generationId, state.ownerScope.tenantId, state.plotScope.plotId]
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

  const contextValue = useMemo<PlotWorkspaceContextValue>(
    () => ({
      state,
      dispatch,
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
      {children}
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

export function usePlotWorkspace(): PlotWorkspaceContextValue {
  const context = useContext(PlotWorkspaceContext);
  if (!context) {
    throw new Error(
      "usePlotWorkspace must be used within a PlotWorkspaceProvider"
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
