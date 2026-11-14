"use client";

import { useState, useEffect, useCallback } from "react";
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
  pollIntervalMs: number = 30000
): UseWorkspaceEntitiesResult {
  const [entities, setEntities] = useState<WorkspaceFeatureEnvelope[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEntities = useCallback(async () => {
    if (!plotId) {
      setEntities([]);
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`/api/plots/${encodeURIComponent(plotId)}/workspace/entities`);
      if (!res.ok) {
        throw new Error(`Failed to load entities: ${res.statusText}`);
      }
      const data = await res.json();
      if (Array.isArray(data.entities)) {
        setEntities(data.entities);
        setError(null);
      } else {
        setEntities([]);
      }
    } catch (err) {
      console.error("[useWorkspaceEntities] Error fetching entities:", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [plotId]);

  useEffect(() => {
    setLoading(true);
    void fetchEntities();

    if (pollIntervalMs > 0) {
      const timer = setInterval(() => {
        void fetchEntities();
      }, pollIntervalMs);
      return () => clearInterval(timer);
    }
  }, [fetchEntities, pollIntervalMs]);

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
