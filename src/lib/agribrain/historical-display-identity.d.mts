export interface HistoricalDisplayIdentity {
  plotId: string;
  geometryHash: string;
  validTimeT: string;
  knowledgeCutoffK: string;
  archiveStateVersion: string;
  activeSurfaceKey: string;
  responseGeneration: number;
}

export interface HistoricalResponsePayloadShape {
  available?: boolean;
  reason?: string | null;
  plot_id?: string;
  geometry_hash?: string;
  archive_state_version?: string;
  as_of_date?: string;
  valid_time_T?: string;
  knowledge_cutoff_K?: string | null;
}

export interface HistoricalDisplayState<T extends HistoricalResponsePayloadShape = HistoricalResponsePayloadShape> {
  requestedAsOfDate: string | null;
  requestedKnowledgeCutoffK: string | null;
  requestGeneration: number;
  loading: boolean;
  error: string | null;
  committed: {
    identity: HistoricalDisplayIdentity;
    data: T;
  } | null;
}

export function createInitialHistoricalDisplayState<
  T extends HistoricalResponsePayloadShape = HistoricalResponsePayloadShape,
>(): HistoricalDisplayState<T>;

export function beginHistoricalSelection<
  T extends HistoricalResponsePayloadShape = HistoricalResponsePayloadShape,
>(
  prev: HistoricalDisplayState<T>,
  asOfDate: string,
  knowledgeCutoffK?: string | null,
): HistoricalDisplayState<T>;

export function resolveHistoricalSuccess<
  T extends HistoricalResponsePayloadShape = HistoricalResponsePayloadShape,
>(
  prev: HistoricalDisplayState<T>,
  params: {
    generation: number;
    plotId: string;
    geometryHash: string | null;
    activeSurfaceKey: string;
    data: T;
  },
): HistoricalDisplayState<T>;

export function resolveHistoricalFailure<
  T extends HistoricalResponsePayloadShape = HistoricalResponsePayloadShape,
>(
  prev: HistoricalDisplayState<T>,
  params: {
    generation: number;
    errorMessage: string;
  },
): HistoricalDisplayState<T>;

export function resetHistoricalToLive<
  T extends HistoricalResponsePayloadShape = HistoricalResponsePayloadShape,
>(prev: HistoricalDisplayState<T>): HistoricalDisplayState<T>;

export function formatDisplayIdentityToken(
  state: HistoricalDisplayState<any>,
  plotId: string,
  activeSurfaceKey: string,
): string;
