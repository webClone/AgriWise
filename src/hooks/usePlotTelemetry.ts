"use client";

/**
 * Owner-scoped operational telemetry. Polls persisted readings through an
 * authenticated read-only endpoint and never promotes scientific evidence.
 */
import {
  createContext, createElement, useCallback, useContext, useEffect,
  useRef, useState, type ReactNode,
} from "react";
import {
  appendOperationalTelemetry, createLiveTelemetryStream,
  TELEMETRY_CONTRACT_VERSION,
  type ScopedTelemetryObservation, type TelemetryScope,
  type LiveTelemetryStream,
} from "@/lib/agribrain/telemetry-contract";
import { validateOperationalTelemetryResponse } from "@/lib/agribrain/operational-telemetry-transport.mjs";

interface PlotTelemetryContextValue {
  stream: LiveTelemetryStream;
  ingestObservation: (observation: ScopedTelemetryObservation) => void;
  clearTelemetry: () => void;
  transportStatus: "loading" | "ready" | "unavailable";
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
  const scopeEpochRef = useRef(0);
  if (currentScopeRef.current !== scopeKey) {
    currentScopeRef.current = scopeKey;
    scopeEpochRef.current += 1;
  }
  const requestedEpoch = scopeEpochRef.current;
  const [transport, setTransport] = useState<{
    scopeKey: string;
    status: "loading" | "ready" | "unavailable";
  }>({ scopeKey, status: "loading" });

  // Fail closed during render, before the effect cleanup can run.
  const visibleStream = matchesScope(stream, scope)
    ? stream : createLiveTelemetryStream(scope);

  useEffect(() => {
    setStream(current => matchesScope(current, scope)
      ? current : createLiveTelemetryStream(scope));
  }, [scope.tenantId, scope.farmId, scope.plotId]);

  const ingestObservation = useCallback((observation: ScopedTelemetryObservation) => {
    if (currentScopeRef.current !== scopeKey || scopeEpochRef.current !== requestedEpoch) return;
    setStream(current => {
      if (currentScopeRef.current !== scopeKey || scopeEpochRef.current !== requestedEpoch) return current;
      const scoped = matchesScope(current, scope)
        ? current : createLiveTelemetryStream(scope);
      return appendOperationalTelemetry(scoped, observation);
    });
  }, [scopeKey, requestedEpoch, scope.tenantId, scope.farmId, scope.plotId]);

  const clearTelemetry = useCallback(() => {
    setStream(current =>
      currentScopeRef.current !== scopeKey || scopeEpochRef.current !== requestedEpoch
        ? current : createLiveTelemetryStream(scope));
  }, [scopeKey, requestedEpoch, scope.tenantId, scope.farmId, scope.plotId]);

  useEffect(() => {
    const requestedScope = scopeKey;
    const epoch = requestedEpoch;
    const aborter = new AbortController();
    let active = true;
    let inFlight = false;

    const poll = async () => {
      if (inFlight || !active || currentScopeRef.current !== requestedScope
        || scopeEpochRef.current !== epoch) return;
      inFlight = true;
      try {
        const response = await fetch(
          "/api/plots/" + encodeURIComponent(scope.plotId) + "/telemetry",
          { method: "GET", credentials: "same-origin", cache: "no-store", signal: aborter.signal },
        );
        if (!response.ok) throw new Error("telemetry_http_" + response.status);
        const body: unknown = await response.json();
        if (!active || aborter.signal.aborted || currentScopeRef.current !== requestedScope
          || scopeEpochRef.current !== epoch) return;
        const observations = validateOperationalTelemetryResponse(
          body, scope, TELEMETRY_CONTRACT_VERSION,
        ) as ScopedTelemetryObservation[];
        setStream(current => {
          if (!active || aborter.signal.aborted || currentScopeRef.current !== requestedScope
            || scopeEpochRef.current !== epoch) return current;
          let updated = matchesScope(current, scope)
            ? current : createLiveTelemetryStream(scope);
          for (const item of observations) updated = appendOperationalTelemetry(updated, item);
          return updated;
        });
        setTransport({ scopeKey: requestedScope, status: "ready" });
      } catch {
        if (active && !aborter.signal.aborted && currentScopeRef.current === requestedScope
          && scopeEpochRef.current === epoch) {
          setTransport({ scopeKey: requestedScope, status: "unavailable" });
        }
      } finally {
        inFlight = false;
      }
    };

    void poll();
    const interval = setInterval(() => { void poll(); }, 30_000);
    return () => {
      active = false;
      aborter.abort();
      clearInterval(interval);
    };
  }, [scopeKey, requestedEpoch, scope.tenantId, scope.farmId, scope.plotId]);

  return createElement(PlotTelemetryContext.Provider, {
    value: {
      stream: visibleStream, ingestObservation, clearTelemetry,
      transportStatus: transport.scopeKey === scopeKey ? transport.status : "loading",
    },
  }, children);
}

export function usePlotTelemetry(): PlotTelemetryContextValue {
  const ctx = useContext(PlotTelemetryContext);
  if (!ctx) throw new Error("usePlotTelemetry requires PlotTelemetryProvider");
  return ctx;
}
