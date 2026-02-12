"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SeedDemoButton() {
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const seedDemoData = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/seed/farms", { method: "POST" });
      const data = await res.json();
      
      if (data.success) {
        console.log("✅ Demo data created:", data);
        router.refresh();
      } else {
        console.error("❌ Seed error:", data.error);
      }
    } catch (error) {
      console.error("❌ Seed request failed:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={seedDemoData}
      disabled={loading}
      className="btn btn-secondary"
    >
      {loading ? "جاري الإنشاء..." : "🧪 بيانات تجريبية"}
    </button>
  );
}
