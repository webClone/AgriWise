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
  GEOMETRY_CONTRACT_VERSION,
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
  canonicalPublicationToAssessment,
} from "@/lib/agribrain/parcel-assessment-contract";
import { classifyCanonicalHeadValidation } from "@/lib/agribrain/layer10-request-state.mjs";

export {
  PARCEL_ASSESSMENT_CONTRACT_VERSION,
  GEOMETRY_CONTRACT_VERSION,
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
  canonicalPublicationToAssessment,
};

export type AssessmentStatus =
  | "idle"
  | "loading"
  | "ready"
  | "unavailable"
  | "invalid"
  | "superseded"
  | "stale";

export interface ParcelAssessmentFetchOptions {
  snapshotId?: string;
  forceRefresh?: boolean;
  geometry?: unknown;
  cropCycleId?: string | null;
  tenantId?: string;
  farmId?: string;
  sourcePolicy?: string;
  visualIntensity?: string | number;
}

export interface ParcelAssessmentContextType {
  state: AssessmentState;
  assessment: ParcelAssessment | null;
  rawPublication: any | null;
  status: AssessmentStatus;
  loading: boolean;
  error: string | null;
  plotId: string | null;
  farmId: string | null;
  activeCropCycleId: string | null;
  isApplicable: boolean;
  isStale: boolean;
  staleReason: string | null;
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
    acceptedAt?: string | null;
    manifestMembership?: boolean;
  }) => boolean;
}

export const ParcelAssessmentContext = createContext<ParcelAssessmentContextType | null>(null);

export function ParcelAssessmentProvider({
  children,
  plotGeoJson,
  cropCycleId = null,
}: {
  children: ReactNode;
  plotGeoJson?: unknown;
  cropCycleId?: string | null;
}) {
  const [state, setState] = useState<AssessmentState>({ status: "idle" });
  const [rawPublication, setRawPublication] = useState<any | null>(null);
  const [currentPlotId, setCurrentPlotId] = useState<string | null>(null);
  const [currentFarmId, setCurrentFarmId] = useState<string | null>(null);

  const requestSequenceRef = useRef<number>(0);
  const activeAbortControllerRef = useRef<AbortController | null>(null);
  const plotGeoJsonRef = useRef<unknown>(plotGeoJson);
  plotGeoJsonRef.current = plotGeoJson;
  const cropCycleIdRef = useRef<string | null>(cropCycleId);
  cropCycleIdRef.current = cropCycleId;

  // Same-provider parcel edits must invalidate the previous publication immediately.
  const contextSignature = `${computeGeometryHash(plotGeoJson)}|${cropCycleId ?? ""}`;
  const contextSignatureRef = useRef(contextSignature);
  contextSignatureRef.current = contextSignature;

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
      const requestedContextSignature = contextSignatureRef.current;
      const sequence = requestSequenceRef.current + 1;
      requestSequenceRef.current = sequence;
      activeAbortControllerRef.current?.abort();
      const controller = new AbortController();
      activeAbortControllerRef.current = controller;

      setCurrentPlotId(plotId);
      if (farmId) setCurrentFarmId(farmId);

      const isLatest = () =>
        requestSequenceRef.current === sequence && !controller.signal.aborted
        && contextSignatureRef.current === requestedContextSignature;

      setState({ status: "loading" });

      try {
        if (options?.snapshotId && options?.forceRefresh) {
          throw new Error("Cannot force-refresh an immutable snapshot.");
        }

        const effectiveGeometry = options?.geometry !== undefined ? options.geometry : plotGeoJsonRef.current;
        const effectiveCropCycleId = options?.cropCycleId !== undefined
          ? options.cropCycleId
          : (cropCycleIdRef.current ?? null);

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
          setRawPublication(null);
          setState({ status: "unavailable", reason });
          return null;
        }

        if (res.status === 409 || json.reason === "canonical_head_validation_failed") {
          const reason = json.error || "Canonical publication head failed integrity validation";
          setRawPublication(null);
          setState({ status: "invalid", reason });
          return null;
        }

        const previousSnapshotId = res.ok && json.available !== false && json.status === "fresh"
          ? String(json.intelligence_snapshot_id || json.snapshot_id || json.snapshotId || "")
          : "";
        // A forced run must not adopt the pre-run cache head as a fresh computation.
        if (!options?.forceRefresh && res.ok && json.available !== false && json.status === "fresh") {
          const validation = json.validation || {};
          const validationState = classifyCanonicalHeadValidation(validation);
          if (validationState !== "valid") {
            const reason = validationState === "corrupt"
              ? "Canonical publication head integrity validation failed"
              : "Canonical publication head contract is stale";
            setRawPublication(null);
            setState({ status: "invalid", reason });
            return null;
          }

          try {
            const assessment = canonicalPublicationToAssessment(json, plotId, {
              ...options,
              geometry: effectiveGeometry,
              cropCycleId: effectiveCropCycleId,
              farmId,
            });

            if (!isLatest()) return null;

            // Enforce parcel applicability boundary:
            // An immutable assessment from an earlier geometry or crop-cycle remains available
            // for historical analysis but is quarantined (stale) for current operations.
            const isGeomStale = isAssessmentStaleForGeometry(assessment.identity, effectiveGeometry);
            const isCropCycleStale = isAssessmentStaleForCropCycle(assessment.identity, effectiveCropCycleId);
            const isApplicable = !isGeomStale && !isCropCycleStale;
            const stalenessReason = isGeomStale ? "geometry_mismatch" : isCropCycleStale ? "crop_cycle_mismatch" : null;

            // Exact immutable reads may be inspected historically. Ordinary
            // latest requests must run when the cached head is out of scope.
            if (isApplicable || options?.snapshotId) {
              setRawPublication(json);
              if (!isApplicable) {
                setState({ status: "stale", assessment, reason: stalenessReason });
              } else {
                setState({ status: "ready", assessment });
              }
              return assessment;
            }
          } catch (assessmentErr: any) {
            if (!isLatest()) return null;
            const reason = assessmentErr?.message || "Assessment identity validation failed";
            setRawPublication(null);
            setState({ status: "invalid", reason });
            return null;
          }
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
            setRawPublication(null);
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
              setRawPublication(null);
              setState({ status: "invalid", reason });
              return null;
            }

            if (pubRes.ok && pubJson.available !== false && pubJson.status === "fresh") {
              const validation = pubJson.validation || {};
              if (classifyCanonicalHeadValidation(validation) !== "valid") {
                const reason = "Canonical publication head validation is incomplete";
                setRawPublication(null);
                setState({ status: "invalid", reason });
                return null;
              }

              try {
                const assessment = canonicalPublicationToAssessment(pubJson, plotId, {
                  ...options,
                  geometry: effectiveGeometry,
                  cropCycleId: effectiveCropCycleId,
                  farmId,
                });

                if (!isLatest()) return null;

                const isGeomStale = isAssessmentStaleForGeometry(assessment.identity, effectiveGeometry);
                const isCropCycleStale = isAssessmentStaleForCropCycle(assessment.identity, effectiveCropCycleId);
                const isApplicable = !isGeomStale && !isCropCycleStale;
                const stalenessReason = isGeomStale ? "geometry_mismatch" : isCropCycleStale ? "crop_cycle_mismatch" : null;

                // A completed run must publish a head matching the requested
                // parcel context. A force refresh must adopt a new snapshot.
                if (!isApplicable || (options?.forceRefresh && previousSnapshotId
                    && assessment.identity.snapshotId === previousSnapshotId)) {
                  await new Promise<void>((resolve) => setTimeout(resolve, 500));
                  continue;
                }
                setRawPublication(pubJson);
                setState({ status: "ready", assessment });
                return assessment;
              } catch (assessmentErr: any) {
                if (!isLatest()) return null;
                const reason = assessmentErr?.message || "Assessment identity validation failed";
                setRawPublication(null);
                setState({ status: "invalid", reason });
                return null;
              }
            }

            await new Promise<void>((resolve) => setTimeout(resolve, 500));
          }

          if (isLatest()) {
            setRawPublication(null);
            setState({
              status: "unavailable",
              reason: "Canonical publication pending (timed out waiting for head)",
            });
          }
          return null;
        }

        setRawPublication(null);
        setState({ status: "unavailable", reason: json.reason || "Assessment unavailable" });
        return null;
      } catch (err: any) {
        if (!isLatest()) return null;
        if (err?.name === "AbortError") return null;
        const reason = err?.message || "Assessment retrieval failed";
        setRawPublication(null);
        setState({ status: "unavailable", reason });
        return null;
      }
    },
    []
  );

  const isStaleForGeometryFn = useCallback(
    (currentGeometry: unknown) => {
      if (state.status !== "ready" && state.status !== "stale") return false;
      return isAssessmentStaleForGeometry(state.assessment.identity, currentGeometry);
    },
    [state]
  );

  const isStaleForCropCycleFn = useCallback(
    (currentCropCycleId: string | null) => {
      if (state.status !== "ready" && state.status !== "stale") return false;
      return isAssessmentStaleForCropCycle(state.assessment.identity, currentCropCycleId);
    },
    [state]
  );

  const isLateArrivingFn = useCallback(
    (evidence: {
      observedAt?: string;
      capturedAt?: string;
      ingestedAt?: string | null;
      acceptedAt?: string | null;
      manifestMembership?: boolean;
    }) => {
      if (state.status !== "ready" && state.status !== "stale") return false;
      return isLateArrivingEvidence(state.assessment.identity, evidence);
    },
    [state]
  );

  const assessment = state.status === "ready" || state.status === "stale" ? state.assessment : null;

  // Derive operational applicability from current props, not the status
  // captured during an earlier fetch. Keep the immutable old artifact for audit.
  const contextGeometryStale = !!assessment && isAssessmentStaleForGeometry(assessment.identity, plotGeoJson);
  const contextCycleStale = !!assessment && isAssessmentStaleForCropCycle(assessment.identity, cropCycleId);
  const contextStaleReason = contextGeometryStale ? "geometry_mismatch" : contextCycleStale ? "crop_cycle_mismatch" : null;
  const projectedState: AssessmentState = assessment && contextStaleReason
    ? { status: "stale", assessment, reason: contextStaleReason }
    : state;
  const status: AssessmentStatus =
    projectedState.status === "ready" ? "ready"
    : projectedState.status === "stale" ? "stale"
    : projectedState.status === "loading" ? "loading"
    : projectedState.status === "unavailable" ? "unavailable"
    : projectedState.status === "invalid" ? "invalid"
    : projectedState.status === "superseded" ? "superseded"
    : "idle";

  const isApplicable = projectedState.status === "ready";
  const isStale = projectedState.status === "stale";
  const staleReason = projectedState.status === "stale" ? projectedState.reason : null;

  const error =
    state.status === "invalid" || state.status === "unavailable"
      ? state.reason
      : null;

  return createElement(
    ParcelAssessmentContext.Provider,
    {
      value: {
        state: projectedState,
        assessment,
        rawPublication,
        status,
        loading: state.status === "loading",
        error,
        plotId: currentPlotId,
        farmId: currentFarmId,
        activeCropCycleId: cropCycleIdRef.current,
        isApplicable,
        isStale,
        staleReason,
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
