"use client";

/**
 * Akaloris / AgriBrain — Parcel Assessment Context & Hook (Phase 2-B)
 *
 * Implements the single assessment provider contract enforcing:
 *   "One parcel assessment, one verified scientific state, many presentation views."
 *
 * Manages atomic lifecycle transitions:
 *   idle -> loading -> (ready | unavailable | invalid | superseded)
 *
 * Guarantees that map surfaces, engine cards, diagnostics, and findings
 * all derive from a single verified, deeply frozen ParcelAssessment.
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  type ReactNode,
  createElement,
} from "react";

import {
  PARCEL_ASSESSMENT_CONTRACT_VERSION,
  type ParcelAssessment,
  type ParcelAssessmentIdentity,
  type LayerResult,
  type Finding,
  type AssessmentQuality,
  type AssessmentEvidenceEvent,
  type AssessmentState,
  computeDeterministicHash,
  computeGeometryHash,
  validateAssessmentIdentity,
  createImmutableParcelAssessment,
  isLateArrivingEvidence,
  isAssessmentStaleForGeometry,
  isAssessmentStaleForCropCycle,
} from "@/lib/agribrain/parcel-assessment-contract";
import { classifyCanonicalHeadValidation } from "@/lib/agribrain/layer10-request-state.mjs";

export {
  PARCEL_ASSESSMENT_CONTRACT_VERSION,
  type ParcelAssessment,
  type ParcelAssessmentIdentity,
  type LayerResult,
  type Finding,
  type AssessmentQuality,
  type AssessmentEvidenceEvent,
  type AssessmentState,
  computeDeterministicHash,
  computeGeometryHash,
  validateAssessmentIdentity,
  createImmutableParcelAssessment,
  isLateArrivingEvidence,
  isAssessmentStaleForGeometry,
  isAssessmentStaleForCropCycle,
};

export type AssessmentStatus =
  | "idle"
  | "loading"
  | "ready"
  | "unavailable"
  | "invalid"
  | "superseded";

export interface ParcelAssessmentFetchOptions {
  snapshotId?: string;
  forceRefresh?: boolean;
  geometry?: unknown;
  cropCycleId?: string | null;
  tenantId?: string;
  farmId?: string;
  sourcePolicy?: string;
  visualIntensity?: string;
}

export interface ParcelAssessmentContextType {
  state: AssessmentState;
  assessment: ParcelAssessment | null;
  status: AssessmentStatus;
  loading: boolean;
  error: string | null;
  plotId: string | null;
  farmId: string | null;
  fetchAssessment: (
    plotId: string,
    farmId?: string,
    options?: ParcelAssessmentFetchOptions
  ) => Promise<ParcelAssessment | null>;
  isStaleForGeometry: (currentGeometry: unknown) => boolean;
  isStaleForCropCycle: (currentCropCycleId: string | null) => boolean;
  isLateArriving: (evidence: {
    observedAt?: string;
    capturedAt?: string;
    ingestedAt?: string | null;
    manifestMembership?: boolean;
  }) => boolean;
}

const ParcelAssessmentContext = createContext<ParcelAssessmentContextType | null>(null);

/**
 * Normalizes raw cacheJson from /api/agribrain/surfaces/latest into an immutable ParcelAssessment.
 */
export function canonicalPublicationToAssessment(
  cacheJson: any,
  plotId: string,
  options?: ParcelAssessmentFetchOptions
): ParcelAssessment {
  if (!cacheJson || typeof cacheJson !== "object") {
    throw new Error("Cannot construct ParcelAssessment from empty payload");
  }

  // 1. Identity normalization & verification
  const rawCutoff = cacheJson.evidence_cutoff_at || cacheJson.capturedAt || cacheJson.timestamp;
  const rawPublished = cacheJson.published_at || cacheJson.capturedAt || cacheJson.timestamp;
  const cutoffIso = rawCutoff ? new Date(rawCutoff).toISOString() : new Date().toISOString();
  // Ensure publishedAt is >= evidenceCutoffAt
  let publishedIso = rawPublished ? new Date(rawPublished).toISOString() : cutoffIso;
  if (new Date(publishedIso).getTime() < new Date(cutoffIso).getTime()) {
    publishedIso = cutoffIso;
  }

  const observationStart = cacheJson.source_window?.[0]
    || cacheJson.observation_window?.start
    || cutoffIso;
  const observationEnd = cacheJson.source_window?.[1]
    || cacheJson.observation_window?.end
    || cutoffIso;

  const receipt = cacheJson.canonical_publication_receipt_hash
    || cacheJson.publication_receipt_hash
    || cacheJson.publicationReceiptHash
    || cacheJson.receiptHash
    || "";

  const geometryHash = cacheJson.geometry_hash
    || cacheJson.geometryHash
    || (options?.geometry ? computeGeometryHash(options.geometry) : "empty_geometry");

  const identity: ParcelAssessmentIdentity = {
    tenantId: options?.tenantId || cacheJson.tenant_id || cacheJson.tenantId || "default",
    farmId: options?.farmId || cacheJson.farm_id || cacheJson.farmId || "",
    plotId: String(plotId || cacheJson.plot_id || cacheJson.plotId || ""),
    cropCycleId: options?.cropCycleId ?? cacheJson.crop_cycle_id ?? cacheJson.cropCycleId ?? null,
    publicationId: String(cacheJson.publication_id || cacheJson.publicationId || ""),
    runId: String(cacheJson.publication_run_id || cacheJson.agribrain_run_id || cacheJson.run_id || cacheJson.runId || ""),
    snapshotId: String(cacheJson.intelligence_snapshot_id || cacheJson.snapshot_id || cacheJson.snapshotId || ""),
    geometryHash,
    observationWindow: {
      start: new Date(observationStart).toISOString(),
      end: new Date(observationEnd).toISOString(),
    },
    evidenceCutoffAt: cutoffIso,
    publishedAt: publishedIso,
    publicationReceiptHash: receipt,
    receiptHash: receipt,
    contractVersion: PARCEL_ASSESSMENT_CONTRACT_VERSION,
  };

  const validation = validateAssessmentIdentity(identity);
  if (!validation.valid) {
    throw new Error(`Assessment identity validation failed: ${validation.errors.join("; ")}`);
  }

  // 2. Canonical Layer Results normalization (L0 - L10)
  const rawLayerResults = cacheJson.layer_results || cacheJson.layerResults || {};
  const canonicalLayerResults: Record<string, LayerResult> = {};
  for (let i = 0; i <= 10; i++) {
    const layerId = `L${i}`;
    const rawLayer = rawLayerResults[layerId] || rawLayerResults[String(i)] || null;
    if (rawLayer) {
      const statusRaw = String(rawLayer.status || "UNAVAILABLE").toUpperCase();
      const status: LayerResult["status"] =
        statusRaw === "OK" || statusRaw === "COMPLETED" ? "OK"
        : statusRaw === "DEGRADED" ? "DEGRADED"
        : statusRaw === "FAILED" ? "FAILED"
        : statusRaw === "SKIPPED" ? "SKIPPED"
        : "UNAVAILABLE";
      canonicalLayerResults[layerId] = {
        layerId,
        status,
        confidence: typeof rawLayer.confidence === "number" && Number.isFinite(rawLayer.confidence)
          ? Math.max(0, Math.min(1, rawLayer.confidence))
          : (status === "OK" ? 1.0 : 0.0),
        sources: Array.isArray(rawLayer.sources) ? rawLayer.sources : [],
        summary: rawLayer.summary || undefined,
        flags: Array.isArray(rawLayer.flags) ? rawLayer.flags : Array.isArray(rawLayer.degradation_flags) ? rawLayer.degradation_flags : undefined,
        data: typeof rawLayer.data === "object" && rawLayer.data !== null ? rawLayer.data : undefined,
      };
    } else {
      canonicalLayerResults[layerId] = {
        layerId,
        status: "UNAVAILABLE",
        confidence: 0,
        sources: [],
      };
    }
  }

  // 3. Authoritative Surfaces
  const authoritativeSurfaces = Array.isArray(cacheJson.surfaceGrids)
    ? cacheJson.surfaceGrids
    : Array.isArray(cacheJson.surfaces)
    ? cacheJson.surfaces
    : [];

  // 4. Top Findings normalization
  const rawTopFindings = Array.isArray(cacheJson.top_findings)
    ? cacheJson.top_findings
    : Array.isArray(cacheJson.topFindings)
    ? cacheJson.topFindings
    : [];
  const topFindings: Finding[] = rawTopFindings.map((item: any, idx: number) => {
    if (typeof item === "string") {
      const isCritical = /severe|critical|failure|emergency/i.test(item);
      const isWarning = /risk|deficit|warning|attention|low/i.test(item);
      return {
        id: `finding-${idx + 1}`,
        title: item,
        severity: isCritical ? "critical" : isWarning ? "medium" : "info",
        description: item,
        actionable: isCritical || isWarning,
      };
    }
    return {
      id: String(item.id || `finding-${idx + 1}`),
      title: String(item.title || item.headline || "Finding"),
      severity: item.severity || "info",
      description: String(item.description || item.detail || item.title || ""),
      layerId: item.layerId || item.layer_id || undefined,
      actionable: Boolean(item.actionable),
      evidenceSources: Array.isArray(item.evidenceSources) ? item.evidenceSources : undefined,
    };
  });

  // 5. Assessment Quality
  const rawQuality = cacheJson.quality || {};
  const rawGlobalQuality = cacheJson.global_quality || {};
  const quality: AssessmentQuality = {
    degradationMode: String(rawQuality.degradation_mode || rawGlobalQuality.degradation_mode || "NORMAL"),
    reliabilityScore: typeof rawQuality.reliability_score === "number"
      ? rawQuality.reliability_score
      : typeof rawGlobalQuality.reliability_score === "number"
      ? rawGlobalQuality.reliability_score
      : null,
    warnings: Array.isArray(rawQuality.warnings) ? rawQuality.warnings : [],
    criticalErrors: Array.isArray(rawQuality.criticalErrors) ? rawQuality.criticalErrors : undefined,
    surfacesGenerated: Number(rawQuality.surfaces_generated ?? authoritativeSurfaces.length),
    zonesGenerated: Number(rawQuality.zones_generated ?? (Array.isArray(cacheJson.zones) ? cacheJson.zones.length : 0)),
    gridAlignmentOk: typeof rawQuality.grid_alignment_ok === "boolean"
      ? rawQuality.grid_alignment_ok
      : null,
    detailConservationOk: typeof rawQuality.detail_conservation_ok === "boolean"
      ? rawQuality.detail_conservation_ok
      : null,
  };

  // 6. Evidence Timeline
  const rawTimeline = Array.isArray(cacheJson.timeline)
    ? cacheJson.timeline
    : Array.isArray(cacheJson.evidence_timeline)
    ? cacheJson.evidence_timeline
    : [];
  const cutoffTime = new Date(identity.evidenceCutoffAt).getTime();
  const evidenceTimeline: AssessmentEvidenceEvent[] = rawTimeline.map((item: any, idx: number) => {
    const observedAt = String(item.observedAt || item.observed_at || item.capturedAt || item.timestamp || cutoffIso);
    const observedTime = new Date(observedAt).getTime();
    // Default manifestMembership is true if observed before cutoff
    const isLate = !isNaN(observedTime) && observedTime > cutoffTime;
    return {
      id: String(item.id || `evidence-${idx + 1}`),
      type: item.type || "observation",
      source: String(item.source || "satellite"),
      observedAt,
      capturedAt: observedAt,
      ingestedAt: item.ingestedAt || item.ingested_at || null,
      acceptedAt: item.acceptedAt || item.accepted_at || null,
      manifestMembership: item.manifestMembership !== undefined ? Boolean(item.manifestMembership) : !isLate,
      summary: String(item.summary || item.description || "Evidence observation"),
      verified: Boolean(item.verified !== false),
    };
  });

  return createImmutableParcelAssessment({
    identity,
    canonicalLayerResults,
    authoritativeSurfaces,
    topFindings,
    quality,
    evidenceTimeline,
  });
}

export function ParcelAssessmentProvider({
  children,
  plotGeoJson,
  cropCycleId = null,
}: {
  children: ReactNode;
  plotGeoJson?: unknown;
  cropCycleId?: string | null;
}) {
  const [state, setState] = useState<AssessmentState>({ status: "loading" });
  const [currentPlotId, setCurrentPlotId] = useState<string | null>(null);
  const [currentFarmId, setCurrentFarmId] = useState<string | null>(null);

  const requestSequenceRef = useRef<number>(0);
  const activeAbortControllerRef = useRef<AbortController | null>(null);
  const plotGeoJsonRef = useRef<unknown>(plotGeoJson);
  plotGeoJsonRef.current = plotGeoJson;
  const cropCycleIdRef = useRef<string | null>(cropCycleId);
  cropCycleIdRef.current = cropCycleId;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      requestSequenceRef.current += 1;
      activeAbortControllerRef.current?.abort();
      activeAbortControllerRef.current = null;
    };
  }, []);

  const fetchAssessment = useCallback(
    async (
      plotId: string,
      farmId?: string,
      options?: ParcelAssessmentFetchOptions
    ): Promise<ParcelAssessment | null> => {
      const sequence = requestSequenceRef.current + 1;
      requestSequenceRef.current = sequence;
      activeAbortControllerRef.current?.abort();
      const controller = new AbortController();
      activeAbortControllerRef.current = controller;

      setCurrentPlotId(plotId);
      if (farmId) setCurrentFarmId(farmId);

      const isLatest = () =>
        requestSequenceRef.current === sequence && !controller.signal.aborted;

      setState({ status: "loading" });

      try {
        if (options?.snapshotId && options?.forceRefresh) {
          throw new Error("Cannot force-refresh an immutable snapshot.");
        }

        const effectiveGeometry = options?.geometry !== undefined ? options.geometry : plotGeoJsonRef.current;
        const effectiveCropCycleId = options?.cropCycleId !== undefined ? options.cropCycleId : cropCycleIdRef.current;

        const res = await fetch("/api/agribrain/surfaces/latest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            plotId,
            snapshotId: options?.snapshotId,
            sourcePolicy: options?.sourcePolicy,
            visualIntensity: options?.visualIntensity,
          }),
        });

        if (!isLatest()) return null;

        const json = await res.json();
        if (!isLatest()) return null;

        if (options?.snapshotId && (!res.ok || json.available === false || json.status !== "fresh")) {
          const reason = `Exact snapshot ${options.snapshotId} unavailable or superseded: ${json.reason || res.status}`;
          setState({ status: "unavailable", reason });
          return null;
        }

        if (res.status === 409 || json.reason === "canonical_head_validation_failed") {
          const reason = json.error || "Canonical publication head failed integrity validation";
          setState({ status: "invalid", reason });
          return null;
        }

        if (res.ok && json.available !== false && json.status === "fresh") {
          const validation = json.validation || {};
          const validationState = classifyCanonicalHeadValidation(validation);
          if (validationState !== "valid") {
            const reason = validationState === "corrupt"
              ? "Canonical publication head integrity validation failed"
              : "Canonical publication head contract is stale";
            setState({ status: "invalid", reason });
            return null;
          }

          const assessment = canonicalPublicationToAssessment(json, plotId, {
            ...options,
            geometry: effectiveGeometry,
            cropCycleId: effectiveCropCycleId,
            farmId,
          });

          if (!isLatest()) return null;

          setState({ status: "ready", assessment });
          return assessment;
        }

        // Cache miss and not exact snapshot -> execute live run
        if (!options?.snapshotId) {
          const runRes = await fetch("/api/agribrain/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: controller.signal,
            body: JSON.stringify({
              plotId,
              mode: "surfaces",
              forceRefresh: options?.forceRefresh || false,
              sourcePolicy: options?.sourcePolicy,
              visualIntensity: options?.visualIntensity,
            }),
          });

          if (!isLatest()) return null;
          const runJson = await runRes.json();
          if (!isLatest()) return null;

          if (!runRes.ok || runJson.error || runJson.success === false) {
            const reason = runJson.error || "AgriBrain surfaces pipeline execution failed";
            setState({ status: "unavailable", reason });
            return null;
          }

          // Latch onto validated canonical publication head
          for (let attempt = 0; attempt < 40 && isLatest(); attempt++) {
            const pubRes = await fetch("/api/agribrain/surfaces/latest", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              cache: "no-store",
              signal: controller.signal,
              body: JSON.stringify({ plotId }),
            });
            if (!isLatest()) return null;
            const pubJson = await pubRes.json();
            if (!isLatest()) return null;

            if (pubRes.status === 409 || pubJson.reason === "canonical_head_validation_failed") {
              const reason = pubJson.error || "Canonical publication head failed integrity validation";
              setState({ status: "invalid", reason });
              return null;
            }

            if (pubRes.ok && pubJson.available !== false && pubJson.status === "fresh") {
              const validation = pubJson.validation || {};
              if (classifyCanonicalHeadValidation(validation) !== "valid") {
                const reason = "Canonical publication head validation is incomplete";
                setState({ status: "invalid", reason });
                return null;
              }

              const assessment = canonicalPublicationToAssessment(pubJson, plotId, {
                ...options,
                geometry: effectiveGeometry,
                cropCycleId: effectiveCropCycleId,
                farmId,
              });

              if (!isLatest()) return null;
              setState({ status: "ready", assessment });
              return assessment;
            }

            await new Promise<void>((resolve) => setTimeout(resolve, 500));
          }

          if (isLatest()) {
            setState({ status: "unavailable", reason: "Timed out waiting for canonical publication head" });
          }
          return null;
        }

        setState({ status: "unavailable", reason: json.reason || "Assessment unavailable" });
        return null;
      } catch (err: any) {
        if (!isLatest()) return null;
        if (err?.name === "AbortError") return null;
        const reason = err?.message || "Assessment retrieval failed";
        setState({ status: "unavailable", reason });
        return null;
      }
    },
    []
  );

  const isStaleForGeometryFn = useCallback(
    (currentGeometry: unknown) => {
      if (state.status !== "ready") return false;
      return isAssessmentStaleForGeometry(state.assessment.identity, currentGeometry);
    },
    [state]
  );

  const isStaleForCropCycleFn = useCallback(
    (currentCropCycleId: string | null) => {
      if (state.status !== "ready") return false;
      return isAssessmentStaleForCropCycle(state.assessment.identity, currentCropCycleId);
    },
    [state]
  );

  const isLateArrivingFn = useCallback(
    (evidence: {
      observedAt?: string;
      capturedAt?: string;
      ingestedAt?: string | null;
      manifestMembership?: boolean;
    }) => {
      if (state.status !== "ready") return false;
      return isLateArrivingEvidence(state.assessment.identity, evidence);
    },
    [state]
  );

  const assessment = state.status === "ready" ? state.assessment : null;
  const status: AssessmentStatus =
    state.status === "ready" ? "ready"
    : state.status === "loading" ? "loading"
    : state.status === "unavailable" ? "unavailable"
    : state.status === "invalid" ? "invalid"
    : state.status === "superseded" ? "superseded"
    : "idle";

  const error =
    state.status === "invalid" || state.status === "unavailable"
      ? state.reason
      : null;

  return createElement(
    ParcelAssessmentContext.Provider,
    {
      value: {
        state,
        assessment,
        status,
        loading: state.status === "loading",
        error,
        plotId: currentPlotId,
        farmId: currentFarmId,
        fetchAssessment,
        isStaleForGeometry: isStaleForGeometryFn,
        isStaleForCropCycle: isStaleForCropCycleFn,
        isLateArriving: isLateArrivingFn,
      },
    },
    children
  );
}

export function useParcelAssessment(): ParcelAssessmentContextType {
  const context = useContext(ParcelAssessmentContext);
  if (!context) {
    throw new Error("useParcelAssessment must be used within a ParcelAssessmentProvider");
  }
  return context;
}
