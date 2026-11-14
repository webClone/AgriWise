"use client";

import { useEffect, useRef } from "react";
import { usePlotWorkspace, usePlotWorkspaceBridge } from "./PlotWorkspaceProvider";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { usePlotTelemetry } from "@/hooks/usePlotTelemetry";
import { useLayer10 } from "@/hooks/useLayer10";

/**
 * P03 State Bridging Adapter.
 * Bridges existing ParcelAssessment, Layer10, and PlotTelemetry providers
 * into the unified workspace state store without duplicating data fetching.
 * In accordance with P03-R4-F05, this bridge is the sole authoritative pathway
 * for introducing validated scientific publications into the workspace.
 */
export function useWorkspaceStateBridging() {
  const { state } = usePlotWorkspace();
  const bridge = usePlotWorkspaceBridge();

  // 1. Bridge ParcelAssessment (Scientific Publication Authority)
  const assessmentContext = useParcelAssessment();
  const assessment = assessmentContext?.assessment;
  const assessmentStatus = assessmentContext?.state?.status;
  const lastBridgedKeyRef = useRef<string | null>(null);

  useEffect(() => {
    // When assessment becomes unavailable, invalid, superseded or null,
    // explicitly invalidate the derived workspace publication (P03-F04 & P03-R1-F05)
    if (!assessment || assessmentStatus !== "ready") {
      if (lastBridgedKeyRef.current !== null) {
        lastBridgedKeyRef.current = null;
        bridge.invalidatePublication({
          generationId: state.generationId,
          plotId: state.plotScope.plotId,
          tenantId: state.ownerScope.tenantId,
          cropCycleId: state.plotScope.cropCycleId,
          geometryHash: state.plotScope.geometryHash,
          geometryVersion: state.plotScope.geometryVersion,
        });
      }
      return;
    }

    const identity = assessment.identity;

    // Strict Scope & Identity Boundary Verification (R3-F04):
    // If incoming assessment does not match the active workspace tenant, plot, crop cycle, or canonical geometry,
    // explicitly invalidate/clear workspace publication rather than silently returning.
    const isScopeIncompatible =
      !identity ||
      identity.plotId !== state.plotScope.plotId ||
      identity.tenantId !== state.ownerScope.tenantId ||
      Boolean(state.plotScope.cropCycleId && (!identity.cropCycleId || identity.cropCycleId !== state.plotScope.cropCycleId)) ||
      Boolean(state.plotScope.geometryHash && (!identity.geometryHash || identity.geometryHash !== state.plotScope.geometryHash));

    if (isScopeIncompatible) {
      if (lastBridgedKeyRef.current !== null || state.publication.snapshotId !== null) {
        lastBridgedKeyRef.current = null;
        bridge.invalidatePublication({
          generationId: state.generationId,
          plotId: state.plotScope.plotId,
          tenantId: state.ownerScope.tenantId,
          cropCycleId: state.plotScope.cropCycleId,
          geometryHash: state.plotScope.geometryHash,
          geometryVersion: state.plotScope.geometryVersion,
        });
      }
      return;
    }

    const digest =
      identity.publicationReceiptHash ||
      identity.receiptHash ||
      identity.publicationId;

    // Deduplication composite key: generation, plot, tenant, snapshotId, geometry, and digest.
    // Ensures that when generation bumps or plot/geometry changes, a valid same-digest publication is cleanly re-published
    // into the new generation rather than silently dropped.
    const bridgedKey = `${state.generationId}|${identity.plotId}|${identity.tenantId}|${identity.snapshotId}|${identity.geometryHash || ""}|${digest}`;
    if (bridgedKey === lastBridgedKeyRef.current) return;
    lastBridgedKeyRef.current = bridgedKey;

    bridge.bridgePublication({
      snapshotId: identity.snapshotId,
      capturedAt: identity.evidenceCutoffAt || identity.publishedAt,
      publicationDigest: digest,
      generationId: state.generationId,
      plotId: identity.plotId,
      tenantId: identity.tenantId,
      cropCycleId: identity.cropCycleId || state.plotScope.cropCycleId,
      geometryHash: identity.geometryHash || state.plotScope.geometryHash,
      geometryVersion: state.plotScope.geometryVersion,
    });
  }, [
    assessment,
    assessmentStatus,
    state.generationId,
    state.plotScope.plotId,
    state.ownerScope.tenantId,
    state.plotScope.cropCycleId,
    state.plotScope.geometryHash,
    state.plotScope.geometryVersion,
    bridge,
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
    bridge.syncTelemetry(obsTs);
  }, [stream, bridge]);

  // 3. Bridge Layer10 (Zone and Lens Selection)
  const layer10Context = useLayer10();
  const selectedZone = layer10Context?.selectedZone;
  const activeMode = layer10Context?.activeMode;

  useEffect(() => {
    if (selectedZone && state.selectedEntity.id !== selectedZone) {
      bridge.selectZoneEntity(selectedZone, state.publication.snapshotId);
    }
  }, [selectedZone, state.selectedEntity.id, state.publication.snapshotId, bridge]);

  useEffect(() => {
    if (activeMode && activeMode !== state.renderIntent.activeLens) {
      bridge.setRenderIntentActiveLens(activeMode);
    }
  }, [activeMode, state.renderIntent.activeLens, bridge]);
}
