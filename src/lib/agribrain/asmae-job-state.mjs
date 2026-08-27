const TERMINAL_FAILURE_STATUSES = new Set(["error", "failed", "stalled", "cancelled"]);
const ACTIVE_WORKER_STATUSES = new Set([
  "queued",
  "running",
  "stalled",
  "completed_reintegration_pending",
]);

function finitePercent(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.min(100, Math.max(0, Math.round(parsed)));
}

function humanizeStage(value) {
  const raw = String(value || "").trim();
  if (!raw) return "Preparing spatial worker";
  return raw
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/**
 * Convert the namespace-validated progress response into a truthful browser
 * presentation. The percentage is always the durable worker percentage; it is
 * never inferred from a client-side animation or stage ordinal.
 */
export function buildAsmaeWorkerProgressView(progress, plotId) {
  const job = progress?.asmae_job || progress?.durable_job || {};
  const responsePlotId = String(progress?.plot_id || job?.plot_id || "");
  const expectedPlotId = String(plotId || "");
  if (expectedPlotId && responsePlotId && responsePlotId !== expectedPlotId) {
    return null;
  }

  const rawStatus = String(job?.status || progress?.status || "idle").toLowerCase();
  const status = rawStatus === "completed_reintegration_pending" ? "queued" : rawStatus;
  const stageCode = String(job?.stage || "");
  const publicationRelation = String(progress?.publicationRelation || "in_progress");
  const terminal = progress?.terminal === true;
  const failed = ["failed", "error", "cancelled"].includes(status)
    || (status === "stalled" && terminal);
  const awaitingPublication = status === "completed" && publicationRelation !== "published";
  const reintegrating = /reintegration|publication|canonical/i.test(stageCode)
    || rawStatus === "completed_reintegration_pending"
    || awaitingPublication;
  const active = ACTIVE_WORKER_STATUSES.has(rawStatus) || awaitingPublication;
  const hasCanonicalFallback = Boolean(progress?.canonical_head_snapshot_id);
  const progressPct = finitePercent(job?.progress_pct);

  let headline = "ASMAE spatial refresh";
  let detail = humanizeStage(stageCode);
  let tone = "active";

  if (failed) {
    headline = "ASMAE spatial refresh failed";
    detail = String(job?.error || job?.reason || humanizeStage(stageCode || "execution failed"));
    tone = "failure";
  } else if (status === "stalled") {
    headline = "ASMAE worker recovery in progress";
    detail = humanizeStage(stageCode || "worker stalled");
    tone = "warning";
  } else if (reintegrating) {
    headline = "Publishing ASMAE spatial evidence";
    detail = awaitingPublication
      ? "Worker complete; validating the canonical publication"
      : humanizeStage(stageCode || "downstream reintegration");
  } else if (status === "queued") {
    headline = "ASMAE spatial refresh queued";
  } else if (status === "running") {
    headline = "ASMAE spatial refresh running";
  } else if (status === "completed" && publicationRelation === "published") {
    headline = "ASMAE spatial evidence published";
    detail = "Canonical publication is ready";
    tone = "success";
  }

  return {
    visible: active || failed,
    active,
    failed,
    terminal,
    reintegrating,
    awaitingPublication,
    status,
    jobId: String(job?.job_id || ""),
    stageCode,
    stage: humanizeStage(stageCode),
    progressPct,
    publicationRelation,
    finalSnapshotId: job?.final_snapshot_id || progress?.final_snapshot_id || null,
    hasCanonicalFallback,
    retryEligible: job?.retry_eligible === true,
    retryClassification: String(job?.retry_classification || ""),
    headline,
    detail,
    tone,
  };
}

/** Guard used by polling UIs so a response from an aborted plot generation
 * cannot replace a newer plot/job view. */
export function isCurrentAsmaeProgressResponse({
  expectedPlotId,
  responsePlotId,
  expectedGeneration,
  currentGeneration,
  aborted = false,
}) {
  if (aborted || Number(expectedGeneration) !== Number(currentGeneration)) return false;
  const expected = String(expectedPlotId || "");
  const actual = String(responsePlotId || "");
  return !expected || !actual || expected === actual;
}

function failureCode(job, fallbackStatus) {
  const explicit = job?.failure_code || job?.reason;
  if (explicit) return String(explicit);
  const error = String(job?.error || "");
  const contractCode = error.match(/\b[A-Z][A-Z0-9_]{4,}\b/)?.[0];
  return contractCode || String(fallbackStatus || "ASMAE_REFRESH_FAILED").toUpperCase();
}

export function buildAsmaeRefreshFailedDetail(progress, plotId) {
  if (progress?.terminal !== true || !TERMINAL_FAILURE_STATUSES.has(String(progress?.status || "").toLowerCase())) {
    return null;
  }
  const job = progress?.asmae_job || progress?.durable_job || {};
  return {
    plotId: String(plotId || progress?.request?.plot_id || job?.plot_id || ""),
    jobId: String(job?.job_id || ""),
    failureCode: failureCode(job, progress?.status),
    failureStage: String(job?.stage || "execution_failed"),
    retryClassification: String(job?.retry_classification || "manual_review"),
    retryEligible: job?.retry_eligible === true,
    error: String(job?.error || job?.reason || "ASMAE spatial refresh failed"),
    contractVersion: String(job?.evidence_capability_contract_version || job?.scientific_identity?.evidence_capability_contract_version || ""),
    publicationRelation: String(progress?.publicationRelation || "failed"),
  };
}

export function patchLayer10AsmaeFailure(data, detail) {
  if (!data || !detail || (data.plot_id && detail.plotId && data.plot_id !== detail.plotId)) return data;
  const display = data.source_policy_display_state || {};
  const previous = display.asmaePlotState || {};
  const receipt = {
    failureCode: detail.failureCode,
    failureStage: detail.failureStage,
    retryClassification: detail.retryClassification,
    retryEligible: detail.retryEligible === true,
    error: detail.error,
    contractVersion: detail.contractVersion,
  };
  return {
    ...data,
    source_policy_display_state: {
      ...display,
      asmaePlotState: {
        ...previous,
        activeSpatialJobId: detail.jobId || previous.activeSpatialJobId || null,
        activeSpatialJobStatus: "failed",
        spatialRefreshFailure: receipt,
        publicationRelation: detail.publicationRelation || "failed",
      },
    },
  };
}

export function patchLayer10AsmaeCompletion(data, detail) {
  if (!data || !detail || (data.plot_id && detail.plotId && data.plot_id !== detail.plotId)) return data;
  const display = data.source_policy_display_state || {};
  const previous = display.asmaePlotState || {};
  return {
    ...data,
    intelligence_snapshot_id: detail.finalSnapshotId || data.intelligence_snapshot_id,
    source_policy_display_state: {
      ...display,
      asmaePlotState: {
        ...previous,
        activeSpatialJobStatus: "completed",
        spatialRefreshFailure: undefined,
      },
    },
  };
}

export function buildAsmaeLiveStateDetail(progress, plotId) {
  const job = progress?.asmae_job || progress?.durable_job;
  if (!job?.job_id || !job?.status) return null;
  const status = String(job.status).toLowerCase();
  if (!["queued", "running", "stalled", "completed_reintegration_pending", "completed", "failed", "superseded", "error", "cancelled"].includes(status)) {
    return null;
  }
  const terminalFailure = ["failed", "error", "cancelled"].includes(status)
    || (status === "stalled" && progress?.terminal === true);
  return {
    plotId: String(plotId || progress?.request?.plot_id || job.plot_id || ""),
    jobId: String(job.job_id),
    status,
    stage: String(job.stage || ""),
    progressPct: finitePercent(job.progress_pct),
    finalSnapshotId: job.final_snapshot_id || progress?.final_snapshot_id || null,
    publicationRelation: String(progress?.publicationRelation || "in_progress"),
    failure: terminalFailure ? {
      failureCode: failureCode(job, status),
      failureStage: String(job.stage || "execution_failed"),
      retryClassification: String(job.retry_classification || "manual_review"),
      retryEligible: job.retry_eligible === true,
      error: String(job.error || job.reason || "ASMAE spatial refresh failed"),
      contractVersion: String(job.evidence_capability_contract_version || job.scientific_identity?.evidence_capability_contract_version || ""),
    } : null,
  };
}

export function patchLayer10AsmaeLiveState(data, detail) {
  if (!data || !detail || (data.plot_id && detail.plotId && data.plot_id !== detail.plotId)) return data;
  const display = data.source_policy_display_state || {};
  const previous = display.asmaePlotState || {};
  const evidence = data.asmae_evidence_state || {};
  return {
    ...data,
    source_policy_display_state: {
      ...display,
      asmaePlotState: {
        ...previous,
        activeSpatialJobId: detail.jobId,
        activeSpatialJobStatus: detail.status,
        activeSpatialJobStage: detail.stage,
        activeSpatialJobProgressPct: detail.progressPct,
        publicationRelation: detail.publicationRelation,
        spatialRefreshFailure: detail.failure
          || (["queued", "running", "stalled", "completed_reintegration_pending", "completed"].includes(detail.status)
            ? undefined
            : previous.spatialRefreshFailure),
      },
    },
    asmae_evidence_state: {
      ...evidence,
      active_spatial_job_id: detail.jobId,
      active_spatial_job_status: detail.status,
      active_spatial_job_stage: detail.stage,
      active_spatial_job_progress_pct: detail.progressPct,
    },
  };
}

export function resolveAsmaeGenerationState(plotState, hasAsmaeRaster, loading) {
  if (hasAsmaeRaster) return { visible: false, disabled: true, label: "ASMAE diagnostic available" };
  const status = String(plotState?.activeSpatialJobStatus || "").toLowerCase();
  if (status === "not_eligible") {
    return { visible: true, disabled: true, label: "No executable spatial scene" };
  }
  if (loading || status === "queued" || status === "running") {
    return { visible: true, disabled: true, label: status === "running" ? "Generating ASMAE diagnostic…" : "ASMAE diagnostic queued…" };
  }
  const failure = plotState?.spatialRefreshFailure;
  if (status === "failed" && failure) {
    if (failure.retryEligible === true) {
      return { visible: true, disabled: false, label: "Start replacement ASMAE run" };
    }
    return { visible: true, disabled: true, label: `ASMAE failed · ${failure.failureCode || "manual review"}` };
  }
  return { visible: true, disabled: false, label: "Generate ASMAE diagnostic" };
}
