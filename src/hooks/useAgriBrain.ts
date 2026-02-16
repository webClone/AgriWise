import { useState, useCallback } from 'react';

// Layer 10.4: AgriBrain UI Hook
// Decouples analysis state from UI components.

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
    yield: any;
    risk: any;
    trust: any;
  };
  plan: {
    actions: any[];
    schedule: any[];
  };
}

export function useAgriBrain() {
  const [analysis, setAnalysis] = useState<AgriBrainAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyzePlot = useCallback(async (plotId: string, config: any = {}) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/agribrain/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plotId, config })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Analysis Failed');
      }

      setAnalysis(data);
      return data;
    } catch (err: any) {
      setError(err.message);
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  return { analyzePlot, analysis, loading, error };
}
