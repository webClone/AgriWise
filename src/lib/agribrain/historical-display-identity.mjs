/**
 * Atomic display-identity state machine for ASMAE causal historical time-travel.
 *
 * Ensures the displayed date badge, raster surface, uncertainty grid, state
 * summary, and sampled pixel ALWAYS belong to the same committed response
 * generation, plot, geometry, valid_time_T, knowledge_cutoff_K, archive version,
 * and active surface key — never keeping stale rasters visible under a newly
 * selected, delayed, or failed request.
 */

export function createInitialHistoricalDisplayState() {
  return {
    requestedAsOfDate: null,
    requestedKnowledgeCutoffK: null,
    requestGeneration: 0,
    loading: false,
    error: null,
    committed: null,
  };
}

export function beginHistoricalSelection(prev, asOfDate, knowledgeCutoffK = null) {
  return {
    requestedAsOfDate: asOfDate,
    requestedKnowledgeCutoffK: knowledgeCutoffK,
    requestGeneration: prev.requestGeneration + 1,
    loading: true,
    error: null,
    // Clear committed payload immediately so stale rasters never masquerade under the new date
    committed: null,
  };
}

export function resolveHistoricalSuccess(prev, params) {
  if (params.generation !== prev.requestGeneration || !prev.requestedAsOfDate) {
    return prev;
  }
  const { data } = params;
  if (data?.plot_id && data.plot_id !== params.plotId) {
    return prev;
  }
  const reqDay = prev.requestedAsOfDate.slice(0, 10);
  if (data?.as_of_date && data.as_of_date.slice(0, 10) !== reqDay) {
    return prev;
  }
  if (params.geometryHash && data?.geometry_hash && data.geometry_hash !== params.geometryHash) {
    return {
      ...prev,
      loading: false,
      error: "Historical response geometry hash mismatch with current parcel scope.",
      committed: null,
    };
  }
  if (!data?.available) {
    return {
      ...prev,
      loading: false,
      error: data?.reason || `No qualified historical observations on or before ${reqDay}.`,
      committed: null,
    };
  }
  return {
    ...prev,
    loading: false,
    error: null,
    committed: {
      identity: {
        plotId: params.plotId,
        geometryHash: String(data.geometry_hash || params.geometryHash || ""),
        validTimeT: String(data.valid_time_T || prev.requestedAsOfDate),
        knowledgeCutoffK: String(data.knowledge_cutoff_K || prev.requestedKnowledgeCutoffK || ""),
        archiveStateVersion: String(data.archive_state_version || ""),
        activeSurfaceKey: params.activeSurfaceKey,
        responseGeneration: params.generation,
      },
      data,
    },
  };
}

export function resolveHistoricalFailure(prev, params) {
  if (params.generation !== prev.requestGeneration || !prev.requestedAsOfDate) {
    return prev;
  }
  return {
    ...prev,
    loading: false,
    error: params.errorMessage || "Failed to load historical reconstruction.",
    committed: null,
  };
}

export function resetHistoricalToLive(prev) {
  return {
    requestedAsOfDate: null,
    requestedKnowledgeCutoffK: null,
    requestGeneration: prev.requestGeneration + 1,
    loading: false,
    error: null,
    committed: null,
  };
}

export function formatDisplayIdentityToken(state, plotId, activeSurfaceKey) {
  if (!state.requestedAsOfDate) {
    return `live|${plotId}|${activeSurfaceKey}|gen:${state.requestGeneration}`;
  }
  if (!state.committed) {
    return state.loading
      ? `loading|${plotId}|${state.requestedAsOfDate}|${activeSurfaceKey}|gen:${state.requestGeneration}`
      : `withheld|${plotId}|${state.requestedAsOfDate}|${activeSurfaceKey}|gen:${state.requestGeneration}`;
  }
  const id = state.committed.identity;
  return [
    id.plotId,
    id.geometryHash.slice(0, 12) || "nogh",
    id.validTimeT.slice(0, 10),
    id.knowledgeCutoffK.slice(0, 10) || "now",
    id.archiveStateVersion.slice(0, 24) || "novers",
    activeSurfaceKey,
    `gen:${id.responseGeneration}`,
  ].join("|");
}
