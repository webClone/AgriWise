"use client";

import { useEffect, useRef } from "react";
import { usePlotWorkspace } from "./PlotWorkspaceProvider";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { usePlotTelemetry } from "@/hooks/usePlotTelemetry";
import { useLayer10 } from "@/hooks/useLayer10";

/**
 * P03 State Bridging Adapter.
 * Bridges existing ParcelAssessment, Layer10, and PlotTelemetry providers
 * into the unified workspace state store without duplicating data fetching.
 */
export function useWorkspaceStateBridging() {
  const { dispatch, state, selectEntity } = usePlotWorkspace();

  // 1. Bridge ParcelAssessment (Scientific Publication Authority)
  const assessmentContext = useParcelAssessment();
  const assessment = assessmentContext?.assessment;
  const assessmentStatus = assessmentContext?.state?.status;
  const lastAssessedDigestRef = useRef<string | null>(null);

  useEffect(() => {
    // When assessment becomes unavailable, invalid, superseded or null,
    // explicitly invalidate the derived workspace publication (P03-F04)
    if (!assessment || assessmentStatus !== "ready") {
      if (lastAssessedDigestRef.current !== null) {
        lastAssessedDigestRef.current = null;
        dispatch({
          type: "SNAPSHOT_SELECTED",
          payload: {
            snapshotId: null,
            capturedAt: null,
            publicationDigest: null,
            authorityStatus: "UNAVAILABLE",
            generationId: state.generationId,
            plotId: state.plotScope.plotId,
            tenantId: state.ownerScope.tenantId,
            cropCycleId: state.plotScope.cropCycleId,
          },
        });
      }
      return;
    }

    const digest =
      assessment.identity.publicationReceiptHash ||
      assessment.identity.receiptHash ||
      assessment.identity.publicationId;
    if (digest === lastAssessedDigestRef.current) return;
    lastAssessedDigestRef.current = digest;

    dispatch({
      type: "SNAPSHOT_SELECTED",
      payload: {
        snapshotId: assessment.identity.snapshotId,
        capturedAt: assessment.identity.evidenceCutoffAt || assessment.identity.publishedAt,
        publicationDigest: digest,
        authorityStatus: "CERTIFIED",
        generationId: state.generationId,
        plotId: state.plotScope.plotId,
        tenantId: state.ownerScope.tenantId,
        cropCycleId: state.plotScope.cropCycleId,
      },
    });
  }, [
    assessment,
    assessmentStatus,
    state.generationId,
    state.plotScope.plotId,
    state.ownerScope.tenantId,
    state.plotScope.cropCycleId,
    dispatch,
  ]);

  // 2. Bridge PlotTelemetry (Live Operational Telemetry)
  const telemetryContext = usePlotTelemetry();
  const stream = telemetryContext?.stream;
  const lastTelemetryTsRef = useRef<string | null>(null);

  useEffect(() => {
    if (!stream || stream.observations.length === 0) return;
    const latest = stream.observations[stream.observations.length - 1];
    const obsTs = latest?.observedAt || latest?.validAt || null;
    if (!latest || !obsTs || obsTs === lastTelemetryTsRef.current) return;
    lastTelemetryTsRef.current = obsTs;

    // Strict P03-G03 separation:
    // Live telemetry updates operational clock ONLY; does NOT alter scientificAsOf
    dispatch({
      type: "TELEMETRY_SYNCED",
      payload: {
        observedAt: obsTs,
      },
    });
  }, [stream, dispatch]);

  // 3. Bridge Layer10 (Zone and Lens Selection)
  const layer10Context = useLayer10();
  const selectedZone = layer10Context?.selectedZone;
  const activeMode = layer10Context?.activeMode;

  useEffect(() => {
    if (selectedZone && state.selectedEntity.id !== selectedZone) {
      selectEntity({
        kind: "ZONE",
        id: selectedZone,
        sourceSnapshotId: state.publication.snapshotId,
      });
    }
  }, [selectedZone, state.selectedEntity.id, state.publication.snapshotId, selectEntity]);

  useEffect(() => {
    if (activeMode && activeMode !== state.renderIntent.activeLens) {
      dispatch({
        type: "RENDER_INTENT_SET",
        payload: { activeLens: activeMode },
      });
    }
  }, [activeMode, state.renderIntent.activeLens, dispatch]);
}
