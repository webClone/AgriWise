import { useState, useCallback } from 'react';

/**
 * AgriBrain Analysis Hook
 * 
 * Updated to consume the unified /api/agribrain/run endpoint.
 * Previously called /api/agribrain/analyze (legacy orchestrator.py).
 * Now goes through Orchestrator v2 with mode="full".
 */

export interface AgriBrainAnalysis {
  meta: {
    plot_id: string;
    timestamp: string;
  };
  analysis: {
    summary: string;
    actions: string;
  };
  metrics: {
    yield: unknown;
    risk: unknown;
    trust: unknown;
  };
  plan: {
    actions: unknown[];
    schedule: unknown[];
  };
}

export function useAgriBrain() {
  const [analysis, setAnalysis] = useState<AgriBrainAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyzePlot = useCallback(async (plotId: string, config: Record<string, unknown> = {}) => {
    setLoading(true);
    setError(null);
    try {
      // Unified canonical route — all intelligence through Orchestrator v2
      const res = await fetch('/api/agribrain/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plotId, mode: 'full', ...config })
      });

      const json = await res.json();

      if (!res.ok || json.error) {
        throw new Error(json.error || 'Analysis Failed');
      }

      // Map canonical AgriBrainRun to legacy AgriBrainAnalysis shape
      const run = json;
      const mapped: AgriBrainAnalysis = {
        meta: {
          plot_id: run.plot_id || plotId,
          timestamp: run.audit?.timestamp_utc || new Date().toISOString(),
        },
        analysis: {
          summary: run.top_findings?.join('. ') || run.explanations?.summary?.headline || 'Analysis complete.',
          actions: run.recommendations?.map((r: { action: string }) => r.action).join('; ') || '',
        },
        metrics: {
          yield: null,
          risk: run.global_quality?.reliability || 0,
          trust: run.global_quality?.reliability || 0,
        },
        plan: {
          actions: run.unified_plan?.tasks || [],
          schedule: [],
        },
      };

      setAnalysis(mapped);
      return mapped;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  return { analyzePlot, analysis, loading, error };
}
