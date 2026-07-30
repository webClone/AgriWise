"use client";

import { useCallback, useEffect, useState } from "react";

export default function DevelopmentSessionBootstrap({
  plotId,
  farmId,
}: {
  plotId?: string;
  farmId: string;
}) {
  const [error, setError] = useState<string | null>(null);

  const bootstrap = useCallback(async () => {
    setError(null);
    try {
      const response = await fetch("/api/auth/dev-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-agriwise-dev-bootstrap": "plot-page",
        },
        body: JSON.stringify({ ...(plotId ? { plotId } : {}), farmId }),
        cache: "no-store",
      });
      const result = await response.json();
      if (!response.ok || result.success !== true) {
        throw new Error(result.error || "Could not create the local test session");
      }
      window.location.reload();
    } catch (bootstrapError: unknown) {
      setError(bootstrapError instanceof Error ? bootstrapError.message : "Could not create the local test session");
    }
  }, [farmId, plotId]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-200 flex items-center justify-center p-6">
      <div className="max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 text-center">
        <h1 className="text-lg font-semibold">Preparing local test session</h1>
        <p className="mt-2 text-sm text-slate-400">
          Development mode is binding this browser to the owner of the exact requested {plotId ? "plot" : "farm"}.
        </p>
        {error && (
          <>
            <p className="mt-4 text-sm text-rose-400">{error}</p>
            <button
              type="button"
              onClick={() => void bootstrap()}
              className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white"
            >
              Retry
            </button>
          </>
        )}
      </div>
    </main>
  );
}
