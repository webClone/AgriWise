"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div
      dir="rtl"
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      <div
        style={{
          textAlign: "center",
          padding: "3rem",
          borderRadius: "1rem",
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.1)",
          backdropFilter: "blur(10px)",
          maxWidth: "480px",
        }}
      >
        <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>⚠️</div>
        <h2
          style={{
            color: "#f8fafc",
            fontSize: "1.5rem",
            fontWeight: 600,
            marginBottom: "0.75rem",
          }}
        >
          حدث خطأ غير متوقع
        </h2>
        <p
          style={{
            color: "#94a3b8",
            fontSize: "0.95rem",
            marginBottom: "1.5rem",
            lineHeight: 1.6,
          }}
        >
          نأسف، حدث خطأ أثناء تحميل الصفحة. يرجى المحاولة مرة أخرى.
        </p>
        {error.digest && (
          <p
            style={{
              color: "#64748b",
              fontSize: "0.75rem",
              marginBottom: "1rem",
              fontFamily: "monospace",
            }}
          >
            Error ID: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          style={{
            background: "linear-gradient(135deg, #22c55e, #16a34a)",
            color: "#fff",
            border: "none",
            padding: "0.75rem 2rem",
            borderRadius: "0.5rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer",
            transition: "opacity 0.2s",
          }}
          onMouseOver={(e) => (e.currentTarget.style.opacity = "0.9")}
          onMouseOut={(e) => (e.currentTarget.style.opacity = "1")}
        >
          إعادة المحاولة
        </button>
      </div>
    </div>
  );
}
