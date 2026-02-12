"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function RecalculateButton({ cycleId }: { cycleId: string }) {
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleRecalculate = async () => {
    if (!confirm("Are you sure? This will update future tasks based on the latest soil & weather data.")) return;
    
    setLoading(true);
    try {
      const res = await fetch(`/api/cycles/${cycleId}/recalculate`, {
        method: "POST"
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to recalculate");
      
      router.refresh(); 
      alert(data.message || "Plan updated!");
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Error updating plan.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button 
      onClick={handleRecalculate}
      disabled={loading}
      className="flex items-center gap-2 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs rounded-md shadow transition-colors"
      title="Update future tasks based on live Soil & Weather data"
    >
      {loading ? (
        <span className="animate-spin">🌀</span>
      ) : (
        <span>⚡</span>
      )}
      {loading ? "Optimizing..." : "Smart Update"}
    </button>
  );
}
