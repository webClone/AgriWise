"use client";

import { useEffect, useRef, useState } from "react";
import {
  buildAsmaeLiveStateDetail,
  buildAsmaeRefreshFailedDetail,
  buildAsmaeWorkerProgressView,
  isCurrentAsmaeProgressResponse,
} from "@/lib/agribrain/asmae-job-state.mjs";

interface PlotLoadingSequenceProps {
  plotId?: string;
  /** A compact panel is used when a last-known-good publication is visible. */
  compact?: boolean;
  hasCanonicalFallback?: boolean;
  initialWorkerState?: AsmaePlotWorkerState | null;
  loading?: boolean;
  onRetry?: () => void;
  requestError?: string | null;
}

interface AsmaePlotWorkerState {
  activeSpatialJobId?: string | null;
  activeSpatialJobStatus?: string | null;
  activeSpatialJobStage?: string | null;
  activeSpatialJobProgressPct?: number | null;
  publicationRelation?: string | null;
  spatialRefreshFailure?: {
    failureCode?: string | null;
    failureStage?: string | null;
    retryClassification?: string | null;
    retryEligible?: boolean;
    error?: string | null;
  } | null;
}

interface WorkerProgressView {
  visible: boolean;
  active: boolean;
  failed: boolean;
  terminal: boolean;
  reintegrating: boolean;
  awaitingPublication: boolean;
  status: string;
  jobId: string;
  stageCode: string;
  stage: string;
  progressPct: number | null;
  publicationRelation: string;
  finalSnapshotId: string | null;
  hasCanonicalFallback: boolean;
  retryEligible: boolean;
  retryClassification: string;
  headline: string;
  detail: string;
  tone: "active" | "warning" | "failure" | "success";
}

function progressFromPlotState(plotId: string, plotState?: AsmaePlotWorkerState | null) {
  if (!plotState) return null;
  const status = String(plotState.activeSpatialJobStatus || "").toLowerCase();
  if (!status) return null;
  const failure = plotState.spatialRefreshFailure || {};
  return buildAsmaeWorkerProgressView({
    plot_id: plotId,
    status,
    terminal: ["failed", "error", "cancelled", "superseded"].includes(status),
    publicationRelation: plotState.publicationRelation || "in_progress",
    durable_job: {
      job_id: plotState.activeSpatialJobId || "",
      plot_id: plotId,
      status,
      stage: plotState.activeSpatialJobStage || failure.failureStage || "",
      progress_pct: plotState.activeSpatialJobProgressPct,
      failure_code: failure.failureCode,
      error: failure.error,
      retry_classification: failure.retryClassification,
      retry_eligible: failure.retryEligible,
    },
  }, plotId) as WorkerProgressView | null;
}

function toneClasses(tone: WorkerProgressView["tone"]) {
  if (tone === "failure") {
    return {
      border: "border-rose-400/35",
      badge: "bg-rose-400/12 text-rose-200 border-rose-400/25",
      dot: "bg-rose-400",
      bar: "from-rose-500 to-orange-400",
    };
  }
  if (tone === "warning") {
    return {
      border: "border-amber-400/35",
      badge: "bg-amber-400/12 text-amber-100 border-amber-400/25",
      dot: "bg-amber-400",
      bar: "from-amber-500 to-yellow-300",
    };
  }
  return {
    border: "border-cyan-400/30",
    badge: "bg-cyan-400/10 text-cyan-100 border-cyan-400/20",
    dot: "bg-cyan-400",
    bar: "from-cyan-500 via-indigo-400 to-emerald-400",
  };
}

export default function PlotLoadingSequence({
  plotId = "",
  compact = false,
  hasCanonicalFallback = false,
  initialWorkerState = null,
  loading = false,
  onRetry,
  requestError = null,
}: PlotLoadingSequenceProps = {}) {
  const initialView = progressFromPlotState(plotId, initialWorkerState);
  const [view, setView] = useState<WorkerProgressView | null>(initialView);
  const [transportNote, setTransportNote] = useState<string | null>(null);
  const generationRef = useRef(0);
  const dispatchedCompletionRef = useRef("");

  useEffect(() => {
    if (!plotId) return;

    const generation = generationRef.current + 1;
    generationRef.current = generation;
    const controller = new AbortController();
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const schedule = (delayMs: number) => {
      if (!stopped) timer = setTimeout(() => void poll(), delayMs);
    };

    const poll = async () => {
      if (stopped) return;
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        schedule(3000);
        return;
      }

      try {
        const response = await fetch(
          `/api/agribrain/progress?plotId=${encodeURIComponent(plotId)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            setTransportNote("Progress access requires an authenticated session");
            return;
          }
          setTransportNote("Worker progress connection interrupted; retrying");
          schedule(3000);
          return;
        }

        const progress = await response.json();
        if (!isCurrentAsmaeProgressResponse({
          expectedPlotId: plotId,
          responsePlotId: progress?.plot_id
            || progress?.asmae_job?.plot_id
            || progress?.durable_job?.plot_id,
          expectedGeneration: generation,
          currentGeneration: generationRef.current,
          aborted: controller.signal.aborted || stopped,
        })) return;

        setTransportNote(null);
        const nextView = buildAsmaeWorkerProgressView(progress, plotId) as WorkerProgressView | null;
        // A replacement request may briefly observe the previous terminal job
        // before the new durable reservation becomes visible. Keep polling in
        // that window instead of freezing the replacement UI on stale failure.
        const awaitingReplacementJob = loading && nextView?.failed === true;
        if (nextView && !awaitingReplacementJob) setView(nextView);

        const liveDetail = buildAsmaeLiveStateDetail(progress, plotId);
        if (liveDetail && !awaitingReplacementJob && typeof window !== "undefined") {
          window.dispatchEvent(
            new CustomEvent("agribrain:refresh_progress", { detail: liveDetail }),
          );
        }

        const failureDetail = buildAsmaeRefreshFailedDetail(progress, plotId);
        if (failureDetail || nextView?.failed) {
          if (awaitingReplacementJob) {
            setTransportNote("Waiting for the new durable worker record");
            schedule(1000);
            return;
          }
          if (typeof window !== "undefined" && failureDetail) {
            window.dispatchEvent(
              new CustomEvent("agribrain:refresh_failed", { detail: failureDetail }),
            );
          }
          return;
        }

        if (
          nextView?.status === "completed"
          && nextView.publicationRelation === "published"
        ) {
          const completionIdentity = [
            plotId,
            nextView.finalSnapshotId || `job:${nextView.jobId}`,
          ].join(":");
          if (
            typeof window !== "undefined"
            && dispatchedCompletionRef.current !== completionIdentity
          ) {
            // `loading` changes while the canonical snapshot is fetched and
            // restarts this polling effect. Never let the same 100% event
            // abort/restart that fetch indefinitely.
            dispatchedCompletionRef.current = completionIdentity;
            window.dispatchEvent(new CustomEvent("agribrain:refresh_completed", {
              detail: {
                plotId,
                jobId: nextView.jobId,
                finalSnapshotId: nextView.finalSnapshotId,
                publicationRelation: nextView.publicationRelation,
              },
            }));
          }
          return;
        }

        // Durable stalled jobs are recoverable. Poll more slowly while recovery
        // claims/leases settle; all other active phases stay responsive.
        schedule(nextView?.status === "stalled" ? 3000 : 1500);
      } catch (error) {
        if ((error as Error)?.name === "AbortError" || stopped) return;
        setTransportNote("Worker progress connection interrupted; retrying");
        schedule(3000);
      }
    };

    void poll();
    return () => {
      stopped = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [loading, plotId]);

  // The progress API can confirm publication before the browser has fetched and
  // committed that canonical surface. Keep the 100% state visible during that
  // final materialization request; the dashboard removes this panel only after
  // Layer 10 has committed the publication into the current map state.
  const awaitingReplacementJob = loading && view?.failed === true;
  const showDurableView = (!awaitingReplacementJob && view?.visible === true)
    || (view?.status === "completed" && loading);
  if (!showDurableView && !loading && !requestError && !transportNote) return null;

  const requestIsPending = Boolean(
    requestError && /pending|generating|queued|in progress/i.test(requestError),
  );
  const effectiveTone: WorkerProgressView["tone"] = awaitingReplacementJob
    ? "active"
    : view?.tone
    || (requestError && !requestIsPending ? "failure" : "active");
  const colors = toneClasses(effectiveTone);
  const exactPercent = awaitingReplacementJob ? null : view?.progressPct;
  const fallbackActive = hasCanonicalFallback || view?.hasCanonicalFallback === true;
  const headline = showDurableView
    ? view!.headline
    : requestIsPending
      ? "Canonical ASMAE publication pending"
      : requestError
      ? "ASMAE spatial refresh unavailable"
      : "Checking ASMAE worker";
  const detail = awaitingReplacementJob
    ? "Waiting for the new durable worker record"
    : showDurableView
    ? view!.detail
    : requestError || transportNote || "Reading the durable job record";
  const statusLabel = awaitingReplacementJob
    ? "STARTING"
    : showDurableView
    ? (view!.reintegrating ? "REINTEGRATION" : view!.status.toUpperCase())
    : "CONNECTING";

  return (
    <section
      aria-live="polite"
      aria-label="ASMAE worker progress"
      data-testid="asmae-worker-progress"
      data-worker-status={view?.status || "checking"}
      className={`pointer-events-auto overflow-hidden rounded-2xl border ${colors.border} bg-[#08111d]/94 shadow-[0_18px_70px_rgba(0,0,0,0.48)] backdrop-blur-md ${compact ? "w-[min(430px,calc(100vw-28px))]" : "w-[min(470px,calc(100vw-28px))]"}`}
    >
      <div className={`${compact ? "p-4" : "p-5"}`}>
        <div className="flex items-start gap-3">
          <div className="relative mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04]">
            <span className={`h-2.5 w-2.5 rounded-full ${colors.dot} ${effectiveTone === "active" ? "animate-pulse" : ""}`} />
            {effectiveTone === "active" && (
              <span className={`absolute h-5 w-5 rounded-full ${colors.dot} opacity-20 animate-ping`} />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="truncate text-sm font-semibold text-slate-100">{headline}</h3>
              <span className={`rounded-full border px-2 py-1 font-mono text-[9px] font-bold tracking-[0.12em] ${colors.badge}`}>
                {statusLabel}
              </span>
            </div>
            <p className="mt-1 truncate text-xs text-slate-300" title={detail}>{detail}</p>
          </div>
          <div className="min-w-11 text-right font-mono text-sm font-bold text-slate-100">
            {exactPercent == null ? "--" : `${exactPercent}%`}
          </div>
        </div>

        <div
          className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-950 ring-1 ring-white/[0.06]"
          role="progressbar"
          aria-label="ASMAE durable worker completion"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={exactPercent == null ? undefined : exactPercent}
          aria-valuetext={exactPercent == null ? "Waiting for durable progress" : `${exactPercent} percent`}
        >
          {exactPercent == null ? (
            <div className={`h-full w-1/3 animate-[pulse_1.2s_ease-in-out_infinite] rounded-full bg-gradient-to-r ${colors.bar}`} />
          ) : (
            <div
              className={`h-full rounded-full bg-gradient-to-r ${colors.bar} transition-[width] duration-500 ease-out`}
              style={{ width: `${exactPercent}%` }}
            />
          )}
        </div>

        <div className="mt-3 flex items-center justify-between gap-4 text-[10px] text-slate-400">
          <span>
            {fallbackActive
              ? "Current canonical map remains active"
              : "Basemap remains interactive while evidence is prepared"}
          </span>
          {view?.jobId && (
            <span className="shrink-0 font-mono text-slate-500">JOB {view.jobId.slice(-8)}</span>
          )}
        </div>
        {transportNote && showDurableView && (
          <p className="mt-2 text-[10px] text-amber-200/80">{transportNote}</p>
        )}
        {view?.failed && view.retryEligible && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={loading}
            className="mt-3 w-full rounded-xl border border-cyan-300/25 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-wait disabled:opacity-60"
          >
            {loading ? "Starting replacement worker…" : "Start replacement ASMAE run"}
          </button>
        )}
      </div>
    </section>
  );
}
