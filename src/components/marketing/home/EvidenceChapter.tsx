import React from "react";
import { getEvidenceGraph } from "@/components/experience/scientific-run/selectors";
import { Database, ShieldCheck } from "lucide-react";

/* ═══ AgriWise R2 Pass 3 — EvidenceChapter ═════════════════════
   Multimodal Evidence Mesh (Server HTML Component).
   Contains data-r2-chapter="evidence" attribute.
   ═══════════════════════════════════════════════════════════════ */

export default function EvidenceChapter() {
  const evidenceGraph = getEvidenceGraph();

  return (
    <section
      id="evidence"
      data-r2-chapter="evidence"
      data-r2-narrative="true"
      style={{
        position: "relative",
        paddingTop: "120px",
        paddingBottom: "120px",
      }}
    >
      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        <div style={{ maxWidth: "640px", marginBottom: "48px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(34, 211, 238, 0.08)",
              border: "1px solid rgba(34, 211, 238, 0.2)",
              color: "var(--evidence-observed)",
              marginBottom: "16px",
            }}
          >
            <Database size={12} /> Multimodal Evidence Mesh
          </div>

          <h2 className="marketing-section-title" style={{ fontSize: "clamp(2rem, 3.5vw, 3rem)", margin: "0 0 16px" }}>
            Every claim is anchored in{" "}
            <strong className="marketing-gradient-text">traceable sensor evidence</strong>
          </h2>

          <p className="marketing-section-subtitle" style={{ margin: 0, textAlign: "left" }}>
            AgriBrain reconciles satellite spectroradiometry, synthetic aperture radar, weather grids, and ground probes into a single spatial evidence graph.
          </p>
        </div>

        {/* Evidence Mesh Node Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
          {evidenceGraph.nodes.slice(0, 3).map((node) => (
            <div key={node.id} className="r2-narrative-step">
              <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--evidence-observed)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
                {node.family} · {node.provider}
              </div>
              <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
                {node.label}
              </h3>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "12px" }}>
                Support: <strong style={{ color: "var(--text-primary)" }}>{node.nativeResolution}</strong> ({node.effectiveResolution})
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "var(--field-green)" }}>
                <ShieldCheck size={14} color="var(--field-green)" /> {node.measurementReality}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
