"use client";

import React, { useState } from "react";

export interface TruthEnvelopeData {
  value: any;
  unit: string;
  source_class: "PHYSICAL_RECEIVER" | "NWP_MODEL" | "SIMULATOR" | "GIS_REGISTRY" | "EPHEMERIS_PROPAGATOR" | "DEMO_PLACEHOLDER" | string;
  processing_level: "RAW_FRAME" | "SIGNAL_PARAM" | "FEATURE" | "DERIVED" | "FUSED" | string;
  identity_state: "UNIDENTIFIED" | "PROTOCOL_CONFIRMED" | "CROSS_VALIDATED" | "REGISTRY_MATCH" | "UNKNOWN" | string;
  authority_state: "RESEARCH_ONLY" | "SHADOW_MODE" | "QUALIFIED" | string;
  presentation_state: "LIVE" | "SIMULATION" | "HYPOTHESIS" | string;
  software_epoch_ref?: string;
  observed_at?: string;
  valid_for_seconds?: number;
  uncertainty?: number | null;
  decision_eligible?: boolean;
  explanation?: string;
  parent_envelope_refs?: string[];
  receipt_id_refs?: string[];
}

interface TruthEnvelopeRendererProps {
  label: string;
  envelope?: TruthEnvelopeData | null;
  fallbackValue?: any;
  fallbackUnit?: string;
  size?: "sm" | "md" | "lg";
  showDetails?: boolean;
}

export const TruthEnvelopeRenderer: React.FC<TruthEnvelopeRendererProps> = ({
  label,
  envelope,
  fallbackValue,
  fallbackUnit = "",
  size = "md",
  showDetails = false,
}) => {
  const [expanded, setExpanded] = useState(showDetails);

  if (!envelope) {
    return (
      <div style={{ background: "rgba(30, 41, 59, 0.4)", padding: "8px 12px", borderRadius: "8px", border: "1px solid rgba(100, 116, 139, 0.4)" }}>
        <div style={{ fontSize: "11px", color: "#94a3b8", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{label}</span>
          <span style={{ fontSize: "9px", padding: "1px 5px", borderRadius: "4px", background: "rgba(239, 68, 68, 0.15)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.4)" }}>
            UNCLASSIFIED
          </span>
        </div>
        <div style={{ fontSize: size === "lg" ? "20px" : size === "md" ? "16px" : "13px", fontWeight: 700, color: "#f8fafc", marginTop: "2px" }}>
          {fallbackValue !== undefined ? String(fallbackValue) : "N/A"} {fallbackUnit}
        </div>
      </div>
    );
  }

  // Visual token mappings
  const sourceColors: Record<string, { bg: string; text: string; border: string; label: string }> = {
    PHYSICAL_RECEIVER: { bg: "rgba(34, 197, 94, 0.15)", text: "#4ade80", border: "rgba(34, 197, 94, 0.4)", label: "PHYSICAL RECEIVER" },
    NWP_MODEL: { bg: "rgba(14, 165, 233, 0.15)", text: "#38bdf8", border: "rgba(14, 165, 233, 0.4)", label: "NWP MODEL / ECMWF" },
    SIMULATOR: { bg: "rgba(168, 85, 247, 0.15)", text: "#c084fc", border: "rgba(168, 85, 247, 0.4)", label: "SIMULATOR" },
    GIS_REGISTRY: { bg: "rgba(245, 158, 11, 0.15)", text: "#fbbf24", border: "rgba(245, 158, 11, 0.4)", label: "GIS REGISTRY / OSM" },
    EPHEMERIS_PROPAGATOR: { bg: "rgba(6, 182, 212, 0.15)", text: "#22d3ee", border: "rgba(6, 182, 212, 0.4)", label: "NORAD SGP4" },
    DEMO_PLACEHOLDER: { bg: "rgba(148, 163, 184, 0.15)", text: "#94a3b8", border: "rgba(148, 163, 184, 0.4)", label: "DEMO PLACEHOLDER" },
  };

  const scToken = sourceColors[envelope.source_class] || {
    bg: "rgba(148, 163, 184, 0.15)",
    text: "#cbd5e1",
    border: "rgba(148, 163, 184, 0.4)",
    label: envelope.source_class,
  };

  const isLive = envelope.presentation_state === "LIVE";
  const isSim = envelope.presentation_state === "SIMULATION";
  const isResearchOnly = envelope.authority_state === "RESEARCH_ONLY";
  const uncertaintyStr = envelope.uncertainty !== null && envelope.uncertainty !== undefined
    ? `±${envelope.uncertainty} ${envelope.unit}`
    : "Uncertainty unquantified";

  return (
    <div
      style={{
        background: "rgba(18, 26, 43, 0.8)",
        padding: size === "lg" ? "12px 16px" : "8px 12px",
        borderRadius: "10px",
        border: `1px solid ${isLive ? "rgba(34, 197, 94, 0.3)" : "rgba(56, 189, 248, 0.25)"}`,
        transition: "all 0.2s ease",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px", marginBottom: "4px" }}>
        <span style={{ fontSize: size === "sm" ? "10px" : "11px", color: "#94a3b8", fontWeight: 600 }}>{label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: "4px", flexWrap: "wrap", justifyContent: "flex-end" }}>
          {/* Presentation State Pill */}
          <span
            style={{
              fontSize: "9px",
              padding: "1px 5px",
              borderRadius: "4px",
              fontWeight: 700,
              background: isLive ? "rgba(34, 197, 94, 0.2)" : "rgba(168, 85, 247, 0.2)",
              color: isLive ? "#4ade80" : "#c084fc",
              border: isLive ? "1px solid rgba(34, 197, 94, 0.5)" : "1px dashed rgba(168, 85, 247, 0.5)",
            }}
          >
            {isLive ? "● LIVE" : isSim ? "◌ SIMULATION" : "◌ HYPOTHESIS"}
          </span>

          {/* Source Class Badge */}
          <span
            style={{
              fontSize: "9px",
              padding: "1px 5px",
              borderRadius: "4px",
              fontWeight: 600,
              background: scToken.bg,
              color: scToken.text,
              border: `1px solid ${scToken.border}`,
            }}
          >
            {scToken.label}
          </span>
        </div>
      </div>

      {/* Main Metric Value */}
      <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginTop: "2px" }}>
        <span
          style={{
            fontSize: size === "lg" ? "22px" : size === "md" ? "17px" : "14px",
            fontWeight: 800,
            color: isLive ? "#4ade80" : isSim ? "#f8fafc" : "#38bdf8",
            letterSpacing: "-0.02em",
          }}
        >
          {String(envelope.value)}
        </span>
        <span style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 600 }}>{envelope.unit}</span>
      </div>

      {/* Uncertainty & Authority Footer */}
      <div style={{ marginTop: "6px", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "10px" }}>
        <span style={{ color: "#64748b", fontFamily: "monospace" }}>
          {uncertaintyStr}
        </span>
        {isResearchOnly && (
          <span
            title="Non-actionable research proposal. Ineligible for autonomous agricultural actuation."
            style={{
              fontSize: "9px",
              color: "#f59e0b",
              background: "rgba(245, 158, 11, 0.12)",
              padding: "1px 4px",
              borderRadius: "3px",
              border: "1px solid rgba(245, 158, 11, 0.3)",
            }}
          >
            Advisory Only
          </span>
        )}
      </div>

      {/* Expandable Explanation / Lineage Drawer */}
      {envelope.explanation && (
        <div style={{ marginTop: "6px", borderTop: "1px solid rgba(51, 65, 85, 0.3)", paddingTop: "4px" }}>
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              fontSize: "9px",
              color: "#38bdf8",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <span>{expanded ? "▴ Hide Lineage" : "▾ View Scientific Lineage"}</span>
          </button>
          {expanded && (
            <div style={{ marginTop: "4px", fontSize: "10px", color: "#94a3b8", lineHeight: "1.4", background: "rgba(15, 23, 42, 0.5)", padding: "6px 8px", borderRadius: "4px" }}>
              <div>{envelope.explanation}</div>
              <div style={{ marginTop: "4px", fontSize: "9px", color: "#64748b", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <span>Level: {envelope.processing_level}</span>
                <span>Epoch: {envelope.software_epoch_ref || "mesia-r6.1"}</span>
                {envelope.parent_envelope_refs && envelope.parent_envelope_refs.length > 0 && (
                  <span>Parents: {envelope.parent_envelope_refs.join(", ")}</span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
export default TruthEnvelopeRenderer;
