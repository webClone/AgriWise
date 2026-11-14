"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";

export interface UseWorkspaceEntitiesResult {
  entities: WorkspaceFeatureEnvelope[];
  locatedEntities: WorkspaceFeatureEnvelope[];
  unlocatedEntities: WorkspaceFeatureEnvelope[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useWorkspaceEntities(
  plotId?: string | null,
  pollIntervalMs: number = 30000,
  generationId?: number
): UseWorkspaceEntitiesResult {
  const [entities, setEntities] = useState<WorkspaceFeatureEnvelope[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const activeControllerRef = useRef<AbortController | null>(null);
  const currentRequestRef = useRef<{ plotId?: string | null; generationId?: number }>({});

  const fetchEntities = useCallback(async () => {
    // Abort any ongoing fetch
    if (activeControllerRef.current) {
      activeControllerRef.current.abort();
    }

    if (!plotId) {
      setEntities([]);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    activeControllerRef.current = controller;
    const reqScope = { plotId, generationId };
    currentRequestRef.current = reqScope;

    try {
      const res = await fetch(`/api/plots/${encodeURIComponent(plotId)}/workspace/entities`, {
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`Failed to load entities: ${res.statusText}`);
      }

      const data = await res.json();

      // Guard against stale response if plot or generation changed in the meantime
      if (
        controller.signal.aborted ||
        currentRequestRef.current.plotId !== plotId ||
        currentRequestRef.current.generationId !== generationId
      ) {
        return;
      }

      if (Array.isArray(data.entities)) {
        setEntities(data.entities);
        setError(null);
      } else {
        setEntities([]);
      }
    } catch (err: any) {
      if (err?.name === "AbortError" || controller.signal.aborted) {
        // Request was aborted due to scope switch; swallow silently
        return;
      }
      console.error("[useWorkspaceEntities] Error fetching entities:", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [plotId, generationId]);

  useEffect(() => {
    // Gate P05-F04: Immediately reset stale entities when plotId or generationId changes
    setEntities([]);
    setError(null);
    setLoading(Boolean(plotId));

    void fetchEntities();

    if (pollIntervalMs > 0 && plotId) {
      const timer = setInterval(() => {
        void fetchEntities();
      }, pollIntervalMs);
      return () => {
        clearInterval(timer);
        activeControllerRef.current?.abort();
      };
    }

    return () => {
      activeControllerRef.current?.abort();
    };
  }, [fetchEntities, pollIntervalMs, plotId, generationId]);

  const locatedEntities = entities.filter(
    (e) => e.display_eligibility?.eligible_for_map_pin && e.geometry?.coordinates
  );

  const unlocatedEntities = entities.filter(
    (e) => !e.display_eligibility?.eligible_for_map_pin
  );

  return {
    entities,
    locatedEntities,
    unlocatedEntities,
    loading,
    error,
    refetch: fetchEntities,
  };
}
