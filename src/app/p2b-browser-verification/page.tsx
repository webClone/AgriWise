"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ParcelAssessmentProvider,
  useParcelAssessment,
} from "@/hooks/useParcelAssessment";
import { useLayer10, Layer10Provider } from "@/hooks/useLayer10";
import {
  computeGeometryHash,
} from "@/lib/agribrain/parcel-assessment-contract.mjs";

interface VerificationStep {
  id: string;
  name: string;
  description: string;
  status: "idle" | "running" | "passed" | "failed";
  details?: string;
}

const MOCK_GEOMETRY = {
  type: "Polygon",
  coordinates: [[[35.1, 31.2], [35.2, 31.2], [35.2, 31.3], [35.1, 31.3], [35.1, 31.2]]],
};

const MODIFIED_GEOMETRY = {
  type: "Polygon",
  coordinates: [[[35.1, 31.2], [35.3, 31.2], [35.3, 31.4], [35.1, 31.4], [35.1, 31.2]]],
};

function buildMockPublication(overrides: Record<string, any> = {}) {
  const cutoff = "2026-10-28T06:00:00Z";
  const published = "2026-10-28T07:30:00Z";
  return {
    status: "fresh",
    available: true,
    plot_id: "plot-p01-olive",
    farm_id: "farm-haouz-central",
    tenant_id: "tenant-akaloris-01",
    publication_id: "pub-r5-98124",
    publication_run_id: "run-agribrain-87214",
    intelligence_snapshot_id: "snap-A-001",
    geometry_hash: computeGeometryHash(MOCK_GEOMETRY),
    crop_cycle_id: "cycle-2026-autumn",
    canonical_publication_receipt_hash: "receipt-a-sha256-1111111111111111111111111111111111111111111111111111111111111111",
    capturedAt: cutoff,
    evidence_cutoff_at: cutoff,
    published_at: published,
    observation_window: { start: "2026-10-20T00:00:00Z", end: "2026-10-27T23:59:59Z" },
    source_window: ["2026-10-20T00:00:00Z", "2026-10-27T23:59:59Z"],
    layer_results: {
      L0: { status: "OK", confidence: 0.95, sources: ["weather_station"] },
      L2: { status: "OK", confidence: 0.91, sources: ["sentinel2"] },
      L10: { status: "OK", confidence: 0.88, sources: ["fusion"] },
    },
    top_findings: [
      { id: "find-1", title: "Canopy vigor stable", severity: "info", description: "Vegetative index consistent across baseline." },
    ],
    quality: {
      degradation_mode: "NORMAL",
      reliability_score: 0.88,
      surfaces_generated: 4,
      zones_generated: 3,
      grid_alignment_ok: true,
      detail_conservation_ok: null,
      warnings: [],
    },
    validation: {
      nodeValid: true,
      publicationValid: true,
      receiptValid: true,
      inventoryValid: true,
      temporalBindingValid: true,
      bindingValid: true,
      lineageValid: true,
      schemaValid: true,
      contractValid: true,
      publicationStatusValid: true,
    },
    ...overrides,
  };
}

/** Component mounted inside ParcelAssessmentProvider and Layer10Provider to expose live context */
function AssessmentConsumerProbe({
  onRegisterHarness,
  onStateSample,
}: {
  onRegisterHarness: (harness: {
    fetchAssessment: (plotId: string, farmId?: string, options?: any) => Promise<any>;
    fetchLayer10: (plotId: string, farmId: string, lat?: number, lng?: number, crop?: string, options?: any) => Promise<any>;
    getAssessmentCtx: () => any;
    getLayer10Ctx: () => any;
  }) => void;
  onStateSample: (sample: any) => void;
}) {
  const assessmentCtx = useParcelAssessment();
  const l10 = useLayer10();

  useEffect(() => {
    onRegisterHarness({
      fetchAssessment: assessmentCtx.fetchAssessment,
      fetchLayer10: l10.fetchLayer10,
      getAssessmentCtx: () => assessmentCtx,
      getLayer10Ctx: () => l10,
    });
  }, [assessmentCtx, l10, onRegisterHarness]);

  useEffect(() => {
    onStateSample({
      providerStatus: assessmentCtx.status,
      providerAssessment: assessmentCtx.assessment,
      isApplicable: assessmentCtx.isApplicable,
      isStale: assessmentCtx.isStale,
      staleReason: assessmentCtx.staleReason,
      l10Data: l10.data,
      l10Loading: l10.loading,
      l10Error: l10.error,
      canUseForPrescription: l10.canUseForPrescription,
      canInterpretDiagnostically: l10.canInterpretDiagnostically,
    });
  }, [
    assessmentCtx.status,
    assessmentCtx.assessment,
    assessmentCtx.isApplicable,
    assessmentCtx.isStale,
    assessmentCtx.staleReason,
    l10.data,
    l10.loading,
    l10.error,
    l10.canUseForPrescription,
    l10.canInterpretDiagnostically,
    onStateSample,
  ]);

  return (
    <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/20 text-xs font-mono space-y-2">
      <div className="flex justify-between items-center text-emerald-400 font-semibold text-sm">
        <span>Mounted Assessment Consumer Probe</span>
        <span id="consumer-provider-status" className="px-2 py-0.5 rounded bg-emerald-900/50 text-emerald-300">
          Status: {assessmentCtx.status}
        </span>
      </div>
      <div>
        <span className="text-slate-400">Snapshot ID: </span>
        <span id="active-snapshot-id" className="text-white">
          {assessmentCtx.assessment?.identity.snapshotId || "none"}
        </span>
      </div>
      <div>
        <span className="text-slate-400">Publication Receipt: </span>
        <span id="active-receipt-hash" className="text-emerald-300 break-all">
          {assessmentCtx.assessment?.identity.publicationReceiptHash || "none"}
        </span>
      </div>
      <div>
        <span className="text-slate-400">Layer 10 Bound Receipt: </span>
        <span id="layer10-bound-receipt" className="text-cyan-300 break-all">
          {l10.data?.assessment?.identity.publicationReceiptHash || (l10.data as any)?.canonical_publication_receipt_hash || "none"}
        </span>
      </div>
      <div>
        <span className="text-slate-400">Applicability & Prescriptions: </span>
        <span id="operational-applicability-status" className={`font-semibold ${assessmentCtx.isApplicable ? "text-emerald-400" : "text-amber-400"}`}>
          isApplicable={String(assessmentCtx.isApplicable)} · canPrescribe={String(l10.canUseForPrescription)}
        </span>
      </div>
    </div>
  );
}

export default function P2BBrowserVerificationPage() {
  const [steps, setSteps] = useState<VerificationStep[]>([
    {
      id: "step-1",
      name: "Actual Mounted Provider Delegation & Latching",
      description: "Mounted Layer 10 presentation view adopts publication strictly through mounted ParcelAssessmentProvider",
      status: "idle",
    },
    {
      id: "step-2",
      name: "Atomic Publication Switching (ASMAE Event)",
      description: "When background ASMAE completes, both provider and Layer 10 simultaneously latch Publication B",
      status: "idle",
    },
    {
      id: "step-3",
      name: "Mounted Generation Guard & Superseded Race Immunity",
      description: "Rapid navigation from slow request A to fast request B discards slow response without clearing Layer 10 data",
      status: "idle",
    },
    {
      id: "step-4",
      name: "Stale Assessment Operational Gate & Prescription Disabling",
      description: "Geometry / crop-cycle mismatch transitions to stale state: disables diagnoses and prescriptions while preserving audit data",
      status: "idle",
    },
  ]);

  const [overallStatus, setOverallStatus] = useState<"pending" | "passed" | "failed">("pending");
  const harnessRef = useRef<{
    fetchAssessment: (plotId: string, farmId?: string, options?: any) => Promise<any>;
    fetchLayer10: (plotId: string, farmId: string, lat?: number, lng?: number, crop?: string, options?: any) => Promise<any>;
    getAssessmentCtx: () => any;
    getLayer10Ctx: () => any;
  } | null>(null);

  const latestSampleRef = useRef<any>(null);

  const handleRegisterHarness = useCallback((harness: any) => {
    harnessRef.current = harness;
  }, []);

  const handleStateSample = useCallback((sample: any) => {
    latestSampleRef.current = sample;
  }, []);

  const runVerificationSuite = async () => {
    setOverallStatus("pending");

    // Wait for mounted harness to be registered
    for (let i = 0; i < 20; i++) {
      if (harnessRef.current) break;
      await new Promise((r) => setTimeout(r, 50));
    }

    const harness = harnessRef.current;
    if (!harness) {
      setOverallStatus("failed");
      setSteps((prev) => prev.map((s) => ({ ...s, status: "failed", details: "Harness not mounted" })));
      return;
    }

    const originalFetch = window.fetch;

    try {
      // ── STEP 1: ACTUAL MOUNTED PROVIDER DELEGATION & LATCHING ────────────
      setSteps((prev) => prev.map((s) => (s.id === "step-1" ? { ...s, status: "running" } : s)));

      const pubA = buildMockPublication({
        intelligence_snapshot_id: "snap-A-001",
        canonical_publication_receipt_hash: "receipt-A-sha256-1111111111111111111111111111111111111111111111111111111111111111",
      });

      // Intercept fetch for surfaces/latest to return pubA
      window.fetch = async (input, init) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : "";
        if (url.includes("/api/agribrain/surfaces/latest")) {
          return new Response(JSON.stringify(pubA), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return originalFetch(input, init);
      };

      // Call fetchLayer10 on the mounted hook
      await harness.fetchLayer10("plot-p01-olive", "farm-haouz-central");
      await new Promise((r) => setTimeout(r, 100));

      const sample1 = latestSampleRef.current;
      if (sample1?.providerStatus !== "ready" || sample1?.providerAssessment?.identity.snapshotId !== "snap-A-001") {
        throw new Error(`Provider failed to latch snapshot A: status=${sample1?.providerStatus}`);
      }
      if (sample1?.l10Data?.assessment?.identity.snapshotId !== "snap-A-001") {
        throw new Error("Layer 10 did not adopt snapshot A from provider");
      }
      if (!sample1?.isApplicable || !sample1?.canUseForPrescription) {
        throw new Error("Fresh assessment must be applicable with prescription enabled");
      }

      setSteps((prev) =>
        prev.map((s) =>
          s.id === "step-1"
            ? { ...s, status: "passed", details: `Mounted Layer 10 adopted snap-A-001 through provider; isApplicable=true, canPrescribe=true` }
            : s
        )
      );

      // ── STEP 2: ATOMIC PUBLICATION SWITCHING (ASMAE EVENT) ───────────────
      setSteps((prev) => prev.map((s) => (s.id === "step-2" ? { ...s, status: "running" } : s)));

      const pubB = buildMockPublication({
        intelligence_snapshot_id: "snap-B-002",
        canonical_publication_receipt_hash: "receipt-B-sha256-2222222222222222222222222222222222222222222222222222222222222222",
        top_findings: [{ id: "find-2", title: "ASMAE 1m radar-optical fusion complete", severity: "info" }],
      });

      window.fetch = async (input, init) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : "";
        if (url.includes("/api/agribrain/surfaces/latest")) {
          return new Response(JSON.stringify(pubB), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return originalFetch(input, init);
      };

      // Execute ASMAE completion switch via mounted hook
      await harness.fetchLayer10("plot-p01-olive", "farm-haouz-central", undefined, undefined, undefined, { snapshotId: "snap-B-002" });
      await new Promise((r) => setTimeout(r, 100));

      const sample2 = latestSampleRef.current;
      if (sample2?.providerAssessment?.identity.snapshotId !== "snap-B-002") {
        throw new Error(`Provider failed to switch to snapshot B: got ${sample2?.providerAssessment?.identity.snapshotId}`);
      }
      if (sample2?.l10Data?.assessment?.identity.snapshotId !== "snap-B-002") {
        throw new Error("Layer 10 failed to switch to snapshot B");
      }

      setSteps((prev) =>
        prev.map((s) =>
          s.id === "step-2"
            ? { ...s, status: "passed", details: `Atomic switch verified: provider and Layer 10 latched snap-B-002 synchronously` }
            : s
        )
      );

      // ── STEP 3: MOUNTED GENERATION GUARD & SUPERSEDED RACE IMMUNITY ──────
      setSteps((prev) => prev.map((s) => (s.id === "step-3" ? { ...s, status: "running" } : s)));

      const pubC = buildMockPublication({
        intelligence_snapshot_id: "snap-C-fast",
        canonical_publication_receipt_hash: "receipt-C-sha256-3333333333333333333333333333333333333333333333333333333333333333",
      });

      // Request 1 has 200ms delay and fails or returns null
      // Request 2 has 20ms delay and returns pubC
      let requestCount = 0;
      window.fetch = async (input, init) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : "";
        if (url.includes("/api/agribrain/surfaces/latest")) {
          requestCount++;
          if (requestCount === 1) {
            // Slow superseded request
            await new Promise((r) => setTimeout(r, 200));
            return new Response(JSON.stringify({ available: false, reason: "superseded" }), { status: 409 });
          } else {
            // Fast newer request
            await new Promise((r) => setTimeout(r, 20));
            return new Response(JSON.stringify(pubC), { status: 200, headers: { "Content-Type": "application/json" } });
          }
        }
        return originalFetch(input, init);
      };

      // Trigger slow request
      const slowPromise = harness.fetchLayer10("plot-p01-olive", "farm-haouz-central");
      // Immediately trigger fast request
      await new Promise((r) => setTimeout(r, 10));
      const fastPromise = harness.fetchLayer10("plot-p01-olive", "farm-haouz-central");

      await Promise.all([slowPromise, fastPromise]);
      await new Promise((r) => setTimeout(r, 100));

      const sample3 = latestSampleRef.current;
      if (sample3?.l10Data?.assessment?.identity.snapshotId !== "snap-C-fast") {
        throw new Error(`Generation guard failed: slow request cleared or corrupted fast request. Active snapshot: ${sample3?.l10Data?.assessment?.identity.snapshotId}`);
      }

      setSteps((prev) =>
        prev.map((s) =>
          s.id === "step-3"
            ? { ...s, status: "passed", details: `Mounted generation guard held: slow request aborted post-await without wiping snap-C-fast` }
            : s
        )
      );

      // ── STEP 4: STALE ASSESSMENT OPERATIONAL GATE & PRESCRIPTION DISABLING
      setSteps((prev) => prev.map((s) => (s.id === "step-4" ? { ...s, status: "running" } : s)));

      // Fetch with modified geometry that causes geometry mismatch
      window.fetch = async (input, init) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : "";
        if (url.includes("/api/agribrain/surfaces/latest")) {
          return new Response(JSON.stringify(pubC), { status: 200, headers: { "Content-Type": "application/json" } });
        }
        return originalFetch(input, init);
      };

      await harness.fetchAssessment("plot-p01-olive", "farm-haouz-central", { geometry: MODIFIED_GEOMETRY });
      await new Promise((r) => setTimeout(r, 100));

      const sample4 = latestSampleRef.current;
      if (sample4?.providerStatus !== "stale") {
        throw new Error(`Expected providerStatus to be 'stale', got '${sample4?.providerStatus}'`);
      }
      if (sample4?.isApplicable !== false) {
        throw new Error("isApplicable must be false for stale assessment");
      }
      if (sample4?.canUseForPrescription !== false) {
        throw new Error("canUseForPrescription must be false under stale assessment gate");
      }
      if (sample4?.canInterpretDiagnostically !== false) {
        throw new Error("canInterpretDiagnostically must be false under stale assessment gate");
      }
      if (!sample4?.providerAssessment) {
        throw new Error("Historical assessment must be preserved in state for audit");
      }

      setSteps((prev) =>
        prev.map((s) =>
          s.id === "step-4"
            ? { ...s, status: "passed", details: `Stale gate verified: status=stale, isApplicable=false, canPrescribe=false, historical audit preserved` }
            : s
        )
      );

      setOverallStatus("passed");
      if (typeof window !== "undefined") {
        (window as any).P2B_VERIFICATION_RESULTS = {
          passed: true,
          timestamp: new Date().toISOString(),
          steps: [
            { id: "step-1", name: "Mounted Provider Delegation", status: "passed" },
            { id: "step-2", name: "Atomic Publication Switching", status: "passed" },
            { id: "step-3", name: "Mounted Generation Guard", status: "passed" },
            { id: "step-4", name: "Stale Operational Gate", status: "passed" },
          ],
        };
      }
    } catch (err: any) {
      console.error("[P2B Gate Error]", err);
      setOverallStatus("failed");
      setSteps((prev) =>
        prev.map((s) => (s.status === "running" ? { ...s, status: "failed", details: err?.message || String(err) } : s))
      );
    } finally {
      window.fetch = originalFetch;
    }
  };

  useEffect(() => {
    void runVerificationSuite();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center border-b border-slate-800 pb-4">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              Package P2-B Mounted Browser Verification Gate
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Live React provider mounting, publication switching, generation guarding, and stale isolation
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <span
              id="gate-overall-status"
              className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                overallStatus === "passed"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                  : overallStatus === "failed"
                  ? "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                  : "bg-amber-500/20 text-amber-400 border border-amber-500/40"
              }`}
            >
              {overallStatus === "passed" ? "GATE PASSED" : overallStatus === "failed" ? "GATE FAILED" : "RUNNING"}
            </span>
            <button
              id="btn-rerun-gate"
              type="button"
              onClick={() => void runVerificationSuite()}
              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs rounded border border-slate-700 text-slate-200 transition"
            >
              Rerun Gate
            </button>
          </div>
        </div>

        {/* Live Mounted Provider Container */}
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-slate-300">Active ParcelAssessmentProvider Container:</h2>
          <ParcelAssessmentProvider plotGeoJson={MOCK_GEOMETRY} cropCycleId="cycle-2026-autumn">
            <Layer10Provider plotGeoJson={MOCK_GEOMETRY}>
              <AssessmentConsumerProbe
                onRegisterHarness={handleRegisterHarness}
                onStateSample={handleStateSample}
              />
            </Layer10Provider>
          </ParcelAssessmentProvider>
        </div>

        {/* Verification Scenarios */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-300">Integration Scenarios:</h2>
          <div className="grid grid-cols-1 gap-3">
            {steps.map((step) => (
              <div
                key={step.id}
                id={step.id}
                className={`p-4 rounded-xl border transition-all ${
                  step.status === "passed"
                    ? "bg-slate-900/60 border-emerald-500/40"
                    : step.status === "failed"
                    ? "bg-slate-900/60 border-rose-500/40"
                    : step.status === "running"
                    ? "bg-slate-900/60 border-cyan-500/40"
                    : "bg-slate-900/30 border-slate-800"
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-xs font-semibold text-slate-200">{step.name}</span>
                    <p className="text-xs text-slate-400 mt-0.5">{step.description}</p>
                    {step.details && (
                      <p className="text-[11px] font-mono text-emerald-400/90 mt-2 bg-slate-950/40 p-2 rounded border border-slate-800">
                        {step.details}
                      </p>
                    )}
                  </div>
                  <span
                    id={`${step.id}-badge`}
                    className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                      step.status === "passed"
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : step.status === "failed"
                        ? "bg-rose-950 text-rose-400 border border-rose-800"
                        : step.status === "running"
                        ? "bg-cyan-950 text-cyan-400 border border-cyan-800 animate-pulse"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {step.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Active Context Information */}
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 text-xs space-y-1">
          <div className="text-slate-400">Parcel ID: <span id="active-plot-id" className="text-slate-200">plot-p01-olive</span></div>
          <div className="text-slate-400">Geometry Contract: <span className="text-slate-200">canonical_geojson_sha256_v1</span></div>
          <div className="text-slate-400">Architecture Invariant: <span className="text-emerald-400 font-semibold">One parcel assessment, one verified scientific state, many presentation views</span></div>
        </div>
      </div>
    </div>
  );
}
