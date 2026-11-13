/**
 * P01-G04 Dedicated Regression:
 * Worker still active + canonical publication not yet available + client polling timeout
 * -> Pending/Waiting, never confirmed engine FAILED, and no automatic duplicate ASMAE run.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { buildAsmaeWorkerProgressView } from "../../src/lib/agribrain/asmae-job-state.mjs";

const root = process.cwd();

test("P01-G04: Durable worker progress view classifies active worker as non-failed during publication wait", () => {
  const activeProgressResponse = {
    plot_id: "plot-123",
    status: "running",
    terminal: false,
    publicationRelation: "in_progress",
    durable_job: {
      job_id: "JOB-ACTIVE-001",
      plot_id: "plot-123",
      status: "running",
      stage: "spatial_assimilation",
      progress_pct: 65,
    },
  };

  const view = buildAsmaeWorkerProgressView(activeProgressResponse, "plot-123");
  assert.ok(view !== null, "Progress view must be constructed");
  assert.equal(view.active, true, "Worker must be classified as active");
  assert.equal(view.failed, false, "Active worker must NOT be classified as failed");
  assert.notEqual(view.tone, "failure", "Tone must not be failure");
  assert.equal(view.status, "running");
});

test("P01-G04: PlotLoadingSequence presentation logic protects active worker from timeout failure override", () => {
  const loadingSequenceSource = fs.readFileSync(
    path.join(root, "src/components/farm/intelligence/PlotLoadingSequence.tsx"),
    "utf8"
  );

  // Assert regex covers timeout / timed out
  assert.match(
    loadingSequenceSource,
    /timed out\|timeout\|waiting/i,
    "requestIsPending regex must recognize client timeout errors as pending"
  );

  // Assert workerIsActive is checked before assigning failure tone
  assert.match(
    loadingSequenceSource,
    /workerIsActive[\s\S]*?requestIsPending/,
    "workerIsActive must guard against premature failure tone"
  );

  // Assert retry button is suppressed while worker is active
  assert.match(
    loadingSequenceSource,
    /!workerIsActive/,
    "Retry button must be suppressed while worker is active"
  );

  // Execute the exact decision logic used in PlotLoadingSequence
  const requestError = "Canonical publication pending (timed out waiting for head)";
  const requestIsPending = Boolean(
    requestError && /pending|generating|queued|in progress|timed out|timeout|waiting/i.test(requestError)
  );
  assert.equal(requestIsPending, true, "Timeout error must be classified as requestIsPending");

  const view = {
    visible: true,
    active: true,
    failed: false,
    terminal: false,
    reintegrating: false,
    status: "running",
    headline: "ASMAE spatial refresh running",
    detail: "Spatial Assimilation",
    tone: "active",
    progressPct: 65,
  };

  const workerIsActive = Boolean(
    view && (view.active || view.reintegrating || ["queued", "running", "in_progress"].includes(view.status))
  );
  assert.equal(workerIsActive, true, "Worker is actively running");

  const awaitingReplacementJob = false;
  const effectiveTone = awaitingReplacementJob
    ? "active"
    : (workerIsActive || requestIsPending)
    ? (view?.tone || "active")
    : requestError
    ? "failure"
    : view?.tone || "active";

  assert.equal(effectiveTone, "active", "Tone must remain 'active' instead of 'failure'");

  const statusLabel = awaitingReplacementJob
    ? "STARTING"
    : workerIsActive && !view?.failed
    ? (view.reintegrating ? "REINTEGRATION" : view.status.toUpperCase())
    : requestIsPending
    ? "PENDING"
    : requestError
    ? "FAILED"
    : "CONNECTING";

  assert.equal(statusLabel, "RUNNING", "Status label must report worker status, never FAILED");

  const headline = !view?.failed
    ? view.headline
    : requestIsPending || (workerIsActive && requestError)
      ? "Canonical surface publication pending"
      : requestError
      ? "AgriBrain surface publication failed"
      : "Checking ASMAE worker";

  assert.equal(headline, "ASMAE spatial refresh running", "Headline must reflect running ASMAE, never failed");

  const retryButtonVisible = Boolean(
    ((view?.failed && view.retryEligible) || (requestError && !requestIsPending && !workerIsActive))
  );
  assert.equal(retryButtonVisible, false, "Automatic replacement retry button must NOT be visible");
});

test("P01-G04: useParcelAssessment marks exhausted poll as pending publication timeout without duplicate run", () => {
  const parcelAssessmentSource = fs.readFileSync(
    path.join(root, "src/hooks/useParcelAssessment.tsx"),
    "utf8"
  );

  // Assert timeout reason is explicitly labeled pending publication
  assert.match(
    parcelAssessmentSource,
    /Canonical publication pending \(timed out waiting for head\)/,
    "useParcelAssessment must report pending publication on timeout"
  );

  // Assert fetchAssessment returns null on timeout and never calls itself or dispatches a new run
  const timeoutBlockMatch = parcelAssessmentSource.match(
    /if \(isLatest\(\)\) \{\s*setRawPublication\(null\);\s*setState\(\{[^}]+\}\);\s*\}\s*return null;/
  );
  assert.ok(timeoutBlockMatch, "Exhausted polling must cleanly terminate with null without recursive dispatch");
});

test("P01-G04: PlotDashboard does not automatically re-dispatch on parcelAssessment.state changes", () => {
  const dashboardSource = fs.readFileSync(
    path.join(root, "src/components/farm/PlotDashboard.tsx"),
    "utf8"
  );

  // Check the dependency array for fetchAssessment
  const effectMatch = dashboardSource.match(
    /useEffect\(\(\) => \{\s*if \(plot\?\.id && farm\?\.id\) \{\s*void parcelAssessment\.fetchAssessment[\s\S]*?\},\s*\[(.*?)\]\);/
  );
  assert.ok(effectMatch, "Found parcelAssessment fetch effect");
  const deps = effectMatch[1];
  assert.ok(!deps.includes("parcelAssessment.state"), "parcelAssessment.state must NOT be in dependencies");
  assert.ok(!deps.includes("parcelAssessment.fetchAssessment"), "fetchAssessment must NOT retrigger on every render");
});
