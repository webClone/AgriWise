/**
 * Akaloris Pass P03 — Scoped Workspace Reducer.
 * Pure, deterministic state reducer governing workspace identity, selection,
 * clocks, request generations, and scenario sandbox state.
 */

/**
 * @param {{
 *   tenantId?: string;
 *   farmId?: string;
 *   plotId?: string;
 *   cropCycleId?: string | null;
 *   geometryHash?: string | null;
 *   geometryVersion?: number | string | null;
 *   initialTool?: string;
 * }} [options]
 * @returns {import("./workspace-types").WorkspaceState}
 */
export function createInitialWorkspaceState({
  tenantId = "",
  farmId = "",
  plotId = "",
  cropCycleId = null,
  geometryHash = null,
  geometryVersion = null,
  initialTool = "map",
} = {}) {
  return {
    generationId: 1,
    ownerScope: {
      tenantId,
      farmId,
    },
    plotScope: {
      tenantId,
      farmId,
      plotId,
      cropCycleId,
      geometryHash,
      geometryVersion,
    },
    publication: {
      snapshotId: null,
      capturedAt: null,
      publicationDigest: null,
      authorityStatus: "UNAVAILABLE",
      isStale: false,
    },
    selectedEntity: {
      kind: null,
      id: null,
      sourceSnapshotId: null,
      timestamp: null,
    },
    clocks: {
      scientificAsOf: null,
      operationalObserved: null,
      forecastValidTime: null,
      scenarioSimulationTime: null,
      activeTimeMode: "LATEST",
      cursorTimestamp: null,
    },
    renderIntent: {
      activeMode: "vegetation",
      activeLens: null,
      showContours: true,
      showHatching: false,
      showGridCells: false,
      visibleVectors: {
        boundary: true,
        zones: true,
        sensors: true,
        irrigation: true,
      },
    },
    scenario: {
      isActive: false,
      scenarioId: null,
      scenarioName: null,
      modifiedForcingParameters: {},
    },
    activeTool: initialTool,
    isInspectorCollapsed: false,
    activeError: null,
  };
}

/**
 * @param {import("./workspace-types").WorkspaceState} state
 * @param {import("./workspace-types").WorkspaceAction} action
 * @returns {import("./workspace-types").WorkspaceState}
 */
export function workspaceReducer(state, action) {
  if (!action || !action.type) return state;

  switch (action.type) {
    case "PLOT_CHANGED": {
      const { scope, publication } = action.payload;
      if (!scope || !scope.plotId) return state;

      const isSamePlot =
        state.plotScope.plotId === scope.plotId &&
        state.plotScope.farmId === scope.farmId &&
        state.plotScope.tenantId === scope.tenantId &&
        (state.plotScope.cropCycleId || null) === (scope.cropCycleId || null) &&
        (state.plotScope.geometryHash || null) === (scope.geometryHash || null) &&
        (state.plotScope.geometryVersion ?? null) === (scope.geometryVersion ?? null);

      if (isSamePlot) {
        return state;
      }

      return {
        ...state,
        generationId: state.generationId + 1,
        ownerScope: {
          tenantId: scope.tenantId,
          farmId: scope.farmId,
        },
        plotScope: {
          tenantId: scope.tenantId,
          farmId: scope.farmId,
          plotId: scope.plotId,
          cropCycleId: scope.cropCycleId || null,
          geometryHash: scope.geometryHash || null,
          geometryVersion: scope.geometryVersion || null,
        },
        publication: publication || {
          snapshotId: null,
          capturedAt: null,
          publicationDigest: null,
          authorityStatus: "UNAVAILABLE",
          isStale: false,
        },
        selectedEntity: {
          kind: null,
          id: null,
          sourceSnapshotId: null,
          timestamp: null,
        },
        clocks: {
          scientificAsOf: publication?.capturedAt || null,
          operationalObserved: null,
          forecastValidTime: null,
          scenarioSimulationTime: null,
          activeTimeMode: "LATEST",
          cursorTimestamp: publication?.capturedAt || null,
        },
        scenario: {
          isActive: false,
          scenarioId: null,
          scenarioName: null,
          modifiedForcingParameters: {},
        },
        activeError: null,
      };
    }

    case "SNAPSHOT_SELECTED": {
      const {
        snapshotId,
        capturedAt,
        publicationDigest,
        authorityStatus = "UNAVAILABLE",
        generationId,
        plotId,
        tenantId,
        cropCycleId,
        geometryHash,
        geometryVersion,
        source,
      } = action.payload || {};

      // 1. Mandatory Identity & Scope Fencing (P03-R1-F05 & P03-R1-F06):
      // Every publication action (valid selection OR invalidation) MUST present complete
      // identity matching current workspace generation, tenant, and plot scope.
      // Unscoped or stale actions from previous generations/plots are strictly rejected.
      if (
        typeof generationId !== "number" ||
        generationId !== state.generationId ||
        !plotId ||
        plotId !== state.plotScope.plotId ||
        !tenantId ||
        tenantId !== state.ownerScope.tenantId
      ) {
        return state;
      }

      if (cropCycleId !== undefined && (cropCycleId || null) !== (state.plotScope.cropCycleId || null)) {
        return state;
      }

      if (
        geometryHash !== undefined &&
        state.plotScope.geometryHash &&
        (geometryHash || null) !== (state.plotScope.geometryHash || null)
      ) {
        return state;
      }

      if (
        geometryVersion !== undefined &&
        state.plotScope.geometryVersion !== null &&
        state.plotScope.geometryVersion !== undefined &&
        geometryVersion !== state.plotScope.geometryVersion
      ) {
        return state;
      }

      // 2. Snapshot Cleared / Loss of Applicability:
      if (!snapshotId) {
        return {
          ...state,
          publication: {
            snapshotId: null,
            capturedAt: null,
            publicationDigest: null,
            authorityStatus: "UNAVAILABLE",
            isStale: true,
          },
        };
      }

      // 3. Strict Scientific Authority Verification (P03-R1-F06):
      // "CERTIFIED" authority is accepted ONLY from the verified ParcelAssessment authority bridge
      // with a non-empty publication digest. Unverified or tool-asserted certifications are demoted.
      let finalAuthority = authorityStatus;
      if (finalAuthority === "CERTIFIED") {
        const isAuthoritative =
          source === "PARCEL_ASSESSMENT_AUTHORITY" &&
          typeof publicationDigest === "string" &&
          publicationDigest.trim().length > 0;

        if (!isAuthoritative) {
          finalAuthority = "PENDING";
        }
      }

      let selectedEntity = state.selectedEntity;
      // If previous entity was selected from an older snapshot, keep selection reference
      // but do NOT silently promote it to the newly selected publication
      if (selectedEntity.id && selectedEntity.sourceSnapshotId && selectedEntity.sourceSnapshotId !== snapshotId) {
        selectedEntity = {
          ...selectedEntity,
          metadata: {
            ...selectedEntity.metadata,
            crossSnapshotWarning: `Entity was selected from snapshot ${selectedEntity.sourceSnapshotId}, not active snapshot ${snapshotId}`,
          },
        };
      }

      return {
        ...state,
        publication: {
          snapshotId,
          capturedAt: capturedAt || null,
          publicationDigest: publicationDigest || null,
          authorityStatus: finalAuthority,
          isStale: false,
        },
        selectedEntity,
        clocks: {
          ...state.clocks,
          scientificAsOf: capturedAt || state.clocks.scientificAsOf,
          cursorTimestamp: state.clocks.cursorTimestamp || capturedAt || null,
        },
      };
    }

    case "TIME_SET": {
      const { cursorTimestamp, mode } = action.payload;
      if (!cursorTimestamp) return state;

      let activeTimeMode = mode || state.clocks.activeTimeMode;
      if (!mode) {
        if (state.scenario.isActive) {
          activeTimeMode = "SCENARIO";
        } else if (state.clocks.scientificAsOf && cursorTimestamp < state.clocks.scientificAsOf) {
          activeTimeMode = "HISTORICAL";
        } else {
          const referenceTime = state.clocks.operationalObserved || state.clocks.scientificAsOf;
          if (referenceTime && cursorTimestamp > referenceTime) {
            activeTimeMode = "FORECAST";
          } else {
            activeTimeMode = "LATEST";
          }
        }
      }

      return {
        ...state,
        clocks: {
          ...state.clocks,
          cursorTimestamp,
          activeTimeMode,
        },
      };
    }

    case "ENTITY_SELECTED": {
      const { kind, id, sourceSnapshotId, timestamp, metadata } = action.payload;
      return {
        ...state,
        selectedEntity: {
          kind: kind || null,
          id: id || null,
          sourceSnapshotId: sourceSnapshotId || state.publication.snapshotId,
          timestamp: timestamp || state.clocks.cursorTimestamp,
          metadata: metadata || {},
        },
      };
    }

    case "ACTIVE_TOOL_CHANGED": {
      const { tool } = action.payload;
      if (!tool || tool === state.activeTool) return state;
      return {
        ...state,
        activeTool: tool,
      };
    }

    case "VECTOR_VISIBILITY_SET": {
      const { vectorKey, visible } = action.payload;
      if (!vectorKey) return state;
      return {
        ...state,
        renderIntent: {
          ...state.renderIntent,
          visibleVectors: {
            ...state.renderIntent.visibleVectors,
            [vectorKey]: Boolean(visible),
          },
        },
      };
    }

    case "RENDER_INTENT_SET": {
      return {
        ...state,
        renderIntent: {
          ...state.renderIntent,
          ...action.payload,
        },
      };
    }

    case "SCENARIO_STARTED": {
      const {
        scenarioId = "scenario-default",
        scenarioName = "Hypothetical Scenario",
        parameters = {},
        simulationTime = null,
      } = action.payload || {};
      return {
        ...state,
        scenario: {
          isActive: true,
          scenarioId,
          scenarioName,
          modifiedForcingParameters: parameters,
        },
        clocks: {
          ...state.clocks,
          activeTimeMode: "SCENARIO",
          scenarioSimulationTime: simulationTime || state.clocks.cursorTimestamp || state.clocks.scientificAsOf || null,
        },
      };
    }

    case "SCENARIO_ENDED": {
      return {
        ...state,
        scenario: {
          isActive: false,
          scenarioId: null,
          scenarioName: null,
          modifiedForcingParameters: {},
        },
        clocks: {
          ...state.clocks,
          activeTimeMode: state.clocks.cursorTimestamp && state.clocks.scientificAsOf && state.clocks.cursorTimestamp < state.clocks.scientificAsOf
            ? "HISTORICAL"
            : "LATEST",
          scenarioSimulationTime: null,
        },
      };
    }

    case "TELEMETRY_SYNCED": {
      const { observedAt } = action.payload;
      if (!observedAt) return state;
      // Strict separation: Live telemetry updates operational clock ONLY.
      // Never alters scientificAsOf or asserts scientific publication certification.
      return {
        ...state,
        clocks: {
          ...state.clocks,
          operationalObserved: observedAt,
        },
      };
    }

    case "INSPECTOR_TOGGLED": {
      const collapsed =
        action.payload && typeof action.payload.collapsed === "boolean"
          ? action.payload.collapsed
          : !state.isInspectorCollapsed;
      return {
        ...state,
        isInspectorCollapsed: collapsed,
      };
    }

    case "REQUEST_INVALIDATED": {
      const isCertified = state.publication.authorityStatus === "CERTIFIED";
      return {
        ...state,
        generationId: state.generationId + 1,
        publication: {
          ...state.publication,
          isStale: true,
          authorityStatus: isCertified ? "CERTIFIED" : "UNAVAILABLE",
        },
        activeError: action.payload?.reason || null,
      };
    }

    default:
      return state;
  }
}
