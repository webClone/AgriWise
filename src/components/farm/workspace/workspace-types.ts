/**
 * Akaloris Pass P03 — Workspace Scope, Selection, Temporal and State Types.
 * Strictly divides presentation state from authoritative scientific data.
 */

export interface OwnerScope {
  tenantId: string;
  farmId: string;
}

export interface PlotScope {
  tenantId: string;
  farmId: string;
  plotId: string;
  cropCycleId: string | null;
  geometryHash: string | null;
  geometryVersion: number | string | null;
}

export type AuthorityStatus = "CERTIFIED" | "PENDING" | "UNAVAILABLE" | "STALE" | "DISCONNECTED";

export interface PublicationRef {
  snapshotId: string | null;
  capturedAt: string | null;
  publicationDigest: string | null;
  authorityStatus: AuthorityStatus;
  isStale?: boolean;
}

export type EntityKind = "ZONE" | "SENSOR" | "CAMERA" | "DRONE_WAYPOINT" | "EQUIPMENT" | null;

export interface SelectedEntityRef {
  kind: EntityKind;
  id: string | null;
  sourceSnapshotId: string | null;
  timestamp: string | null;
  metadata?: Record<string, unknown>;
}

export type TimeClockMode = "LATEST" | "HISTORICAL" | "FORECAST" | "SCENARIO";

export interface TimeClocks {
  /** Authoritative scientific model state / snapshot knowledge cutoff */
  scientificAsOf: string | null;
  /** Live operational telemetry observed timestamp (always labeled NOW / live) */
  operationalObserved: string | null;
  /** Forecast prediction horizon valid time */
  forecastValidTime: string | null;
  /** What-if hypothetical scenario cursor time */
  scenarioSimulationTime: string | null;
  /** Current active time mode */
  activeTimeMode: TimeClockMode;
  /** Currently selected playback timestamp */
  cursorTimestamp: string | null;
}

export interface RenderIntent {
  activeMode: string;
  activeLens: string | null;
  showContours: boolean;
  showHatching: boolean;
  showGridCells: boolean;
  visibleVectors: Record<string, boolean>;
}

export interface ScenarioState {
  isActive: boolean;
  scenarioId: string | null;
  scenarioName: string | null;
  modifiedForcingParameters?: Record<string, number>;
}

export interface WorkspaceState {
  generationId: number;
  ownerScope: OwnerScope;
  plotScope: PlotScope;
  publication: PublicationRef;
  selectedEntity: SelectedEntityRef;
  clocks: TimeClocks;
  renderIntent: RenderIntent;
  scenario: ScenarioState;
  activeTool: string;
  isInspectorCollapsed: boolean;
  activeError: string | null;
}

export type WorkspaceAction =
  | {
      type: "PLOT_CHANGED";
      payload: {
        scope: PlotScope;
        publication?: PublicationRef;
      };
    }
  | {
      type: "SNAPSHOT_SELECTED";
      payload: {
        snapshotId: string | null;
        capturedAt?: string | null;
        publicationDigest?: string | null;
        authorityStatus?: AuthorityStatus;
        generationId?: number;
        plotId?: string;
        tenantId?: string;
        cropCycleId?: string | null;
      };
    }
  | {
      type: "TIME_SET";
      payload: {
        cursorTimestamp: string;
        mode?: TimeClockMode;
      };
    }
  | {
      type: "ENTITY_SELECTED";
      payload: {
        kind: EntityKind;
        id: string | null;
        sourceSnapshotId?: string | null;
        timestamp?: string | null;
        metadata?: Record<string, unknown>;
      };
    }
  | {
      type: "ACTIVE_TOOL_CHANGED";
      payload: {
        tool: string;
      };
    }
  | {
      type: "VECTOR_VISIBILITY_SET";
      payload: {
        vectorKey: string;
        visible: boolean;
      };
    }
  | {
      type: "RENDER_INTENT_SET";
      payload: Partial<RenderIntent>;
    }
  | {
      type: "SCENARIO_STARTED";
      payload?: {
        scenarioId?: string;
        scenarioName?: string;
        parameters?: Record<string, number>;
        simulationTime?: string | null;
      };
    }
  | {
      type: "SCENARIO_ENDED";
    }
  | {
      type: "TELEMETRY_SYNCED";
      payload: {
        observedAt: string;
      };
    }
  | {
      type: "INSPECTOR_TOGGLED";
      payload?: {
        collapsed?: boolean;
      };
    }
  | {
      type: "REQUEST_INVALIDATED";
      payload: {
        reason: string;
      };
    };
