"use client";

/**
 * P2-C operational telemetry owner. It deliberately never accepts a
 * ParcelAssessment or publishes evidence; ingestion is an untrusted live buffer.
 * No provider/API is polled here until a scoped authenticated endpoint exists.
 */
import {
  createContext, createElement, useCallback, useContext,
  useEffect, useRef, useState, type ReactNode,
} from "react";
import {
  appendOperationalTelemetry, createLiveTelemetryStream,
  type ScopedTelemetryObservation, type TelemetryScope,
  type LiveTelemetryStream,
} from "@/lib/agribrain/telemetry-contract";

interface PlotTelemetryContextValue {
  stream: LiveTelemetryStream;
  ingestObservation: (observation: ScopedTelemetryObservation) => void;
  clearTelemetry: () => void;
}
const PlotTelemetryContext = createContext<PlotTelemetryContextValue | null>(null);
const scopeKeyOf = (scope: TelemetryScope) =>
  [scope.tenantId, scope.farmId, scope.plotId].join("|");
const matchesScope = (stream: LiveTelemetryStream, scope: TelemetryScope) =>
  scopeKeyOf(stream.scope) === scopeKeyOf(scope);

export function PlotTelemetryProvider({
  scope, children,
}: { scope: TelemetryScope; children: ReactNode }) {
  const [stream, setStream] = useState<LiveTelemetryStream>(
    () => createLiveTelemetryStream(scope)
  );
  const scopeKey = scopeKeyOf(scope);
  const currentScopeRef = useRef(scopeKey);
  currentScopeRef.current = scopeKey;

  // Fail closed during render before the cleanup effect runs.
  const visibleStream = matchesScope(stream, scope)
    ? stream : createLiveTelemetryStream(scope);

  useEffect(() => {
    setStream(current => matchesScope(current, scope)
      ? current : createLiveTelemetryStream(scope));
  // Explicit primitive dependency: do not reset due to object identity.
  }, [scope.tenantId, scope.farmId, scope.plotId]);

  const ingestObservation = useCallback((observation: ScopedTelemetryObservation) => {
    const requestedScope = scopeKey;
    if (currentScopeRef.current !== requestedScope) return;
    setStream(current => {
      if (currentScopeRef.current !== requestedScope) return current;
      const scoped = matchesScope(current, scope)
        ? current : createLiveTelemetryStream(scope);
      return appendOperationalTelemetry(scoped, observation);
    });
  }, [scopeKey, scope.tenantId, scope.farmId, scope.plotId]);

  const clearTelemetry = useCallback(() => {
    const requestedScope = scopeKey;
    setStream(current => currentScopeRef.current !== requestedScope
      ? current : createLiveTelemetryStream(scope));
  }, [scopeKey, scope.tenantId, scope.farmId, scope.plotId]);

  return createElement(PlotTelemetryContext.Provider, {
    value: { stream: visibleStream, ingestObservation, clearTelemetry },
  }, children);
}

export function usePlotTelemetry(): PlotTelemetryContextValue {
  const ctx = useContext(PlotTelemetryContext);
  if (!ctx) throw new Error("usePlotTelemetry requires PlotTelemetryProvider");
  return ctx;
}
