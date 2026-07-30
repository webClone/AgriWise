"use client";

import { useEffect } from "react";

export default function FarmError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Farm section error:", error);
  }, [error]);

  return (
    <div
      dir="rtl"
      style={{
        minHeight: "60vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
      }}
    >
      <div
        style={{
          textAlign: "center",
          padding: "2rem",
          borderRadius: "1rem",
          background: "rgba(239,68,68,0.05)",
          border: "1px solid rgba(239,68,68,0.2)",
          maxWidth: "420px",
        }}
      >
        <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🌾</div>
        <h2
          style={{
            color: "#1e293b",
            fontSize: "1.25rem",
            fontWeight: 600,
            marginBottom: "0.5rem",
          }}
        >
          خطأ في تحميل بيانات المزرعة
        </h2>
        <p
          style={{
            color: "#64748b",
            fontSize: "0.9rem",
            marginBottom: "1.25rem",
            lineHeight: 1.5,
          }}
        >
          لم نتمكن من تحميل بيانات المزرعة. تحقق من اتصالك بالإنترنت وحاول مرة
          أخرى.
        </p>
        <button
          onClick={reset}
          style={{
            background: "#22c55e",
            color: "#fff",
            border: "none",
            padding: "0.6rem 1.5rem",
            borderRadius: "0.5rem",
            fontSize: "0.9rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          إعادة المحاولة
        </button>
      </div>
    </div>
  );
}
