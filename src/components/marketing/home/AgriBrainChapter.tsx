import React, { useState } from "react";
import { getEvidenceGraph, getFieldCube, getWorldline } from "@/components/experience/scientific-run/selectors";
import { Network, Box, Clock, Cpu } from "lucide-react";

/* ═══ AgriWise R2 — AgriBrainChapter ═══════════════════════════
   Computational Organism revealing the 3 canonical objects:
   CanonicalEvidenceGraph, CanonicalFieldCube, and CanonicalPlotWorldline
   operating on the same frozen deterministic demonstration run.
   ═══════════════════════════════════════════════════════════════ */

export default function AgriBrainChapter() {
  const graph = getEvidenceGraph();
  const cube = getFieldCube();
  const worldline = getWorldline();

  const [activeTab, setActiveTab] = useState<"graph" | "cube" | "worldline">("graph");

  return (
    <section
      id="agribrain-organism"
      style={{
        position: "relative",
        paddingTop: "100px",
        paddingBottom: "100px",
        borderTop: "1px solid var(--border-subtle)",
      }}
    >
      <div className="marketing-container">
        <div style={{ textAlign: "center", marginBottom: "48px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(167, 139, 250, 0.08)",
              border: "1px solid rgba(167, 139, 250, 0.2)",
              color: "var(--agribrain-violet)",
            }}
          >
            Computational Organism
          </div>
          <h2 className="marketing-section-title">
            Three canonical objects of{" "}
            <strong style={{ color: "var(--agribrain-violet)" }}>agricultural truth</strong>
          </h2>
          <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
            AgriBrain coordinates three unified scientific representations over every plot.
          </p>
        </div>

        {/* Tab Selector */}
        <div style={{ display: "flex", justifyContent: "center", gap: "12px", marginBottom: "32px" }}>
          <button
            onClick={() => setActiveTab("graph")}
            aria-pressed={activeTab === "graph"}
            className="marketing-card"
            style={{
              padding: "10px 20px",
              borderRadius: "24px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              cursor: "pointer",
              borderColor: activeTab === "graph" ? "var(--evidence-observed)" : "var(--border-subtle)",
              background: activeTab === "graph" ? "rgba(34, 211, 238, 0.1)" : "var(--surface-elevated)",
              color: activeTab === "graph" ? "var(--evidence-observed)" : "var(--text-secondary)",
              fontWeight: 700,
              fontSize: "13px",
            }}
          >
            <Network size={16} /> CanonicalEvidenceGraph
          </button>

          <button
            onClick={() => setActiveTab("cube")}
            aria-pressed={activeTab === "cube"}
            className="marketing-card"
            style={{
              padding: "10px 20px",
              borderRadius: "24px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              cursor: "pointer",
              borderColor: activeTab === "cube" ? "var(--agribrain-violet)" : "var(--border-subtle)",
              background: activeTab === "cube" ? "rgba(167, 139, 250, 0.1)" : "var(--surface-elevated)",
              color: activeTab === "cube" ? "var(--agribrain-violet)" : "var(--text-secondary)",
              fontWeight: 700,
              fontSize: "13px",
            }}
          >
            <Box size={16} /> CanonicalFieldCube
          </button>

          <button
            onClick={() => setActiveTab("worldline")}
            aria-pressed={activeTab === "worldline"}
            className="marketing-card"
            style={{
              padding: "10px 20px",
              borderRadius: "24px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              cursor: "pointer",
              borderColor: activeTab === "worldline" ? "var(--field-green)" : "var(--border-subtle)",
              background: activeTab === "worldline" ? "rgba(74, 222, 128, 0.1)" : "var(--surface-elevated)",
              color: activeTab === "worldline" ? "var(--field-green)" : "var(--text-secondary)",
              fontWeight: 700,
              fontSize: "13px",
            }}
          >
            <Clock size={16} /> CanonicalPlotWorldline
          </button>
        </div>

        {/* Content Explorer Panel */}
        <div
          className="marketing-card"
          style={{
            padding: "36px",
            borderRadius: "var(--radius-xl)",
            background: "var(--surface-elevated)",
            border: "1px solid var(--border-default)",
          }}
        >
          {activeTab === "graph" && (
            <div>
              <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--evidence-observed)", textTransform: "uppercase" }}>
                Heterogeneous Provenance Graph
              </div>
              <h3 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0 12px" }}>
                CanonicalEvidenceGraph
              </h3>
              <p style={{ fontSize: "14px", color: "var(--text-muted)", lineHeight: 1.6, marginBottom: "24px" }}>
                Connects satellite acquisitions, weather reanalysis grids, soil IoT probes, and farmer logs with explicit cross-validation edges.
              </p>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
                {graph.nodes.slice(0, 3).map((node) => (
                  <div key={node.id} style={{ padding: "16px", borderRadius: "var(--radius-md)", background: "var(--surface-code)", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ fontSize: "11px", color: "var(--evidence-observed)", fontWeight: 700 }}>{node.family}</div>
                    <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0" }}>{node.label}</div>
                    <div style={{ fontSize: "11px", color: "var(--text-dim)" }}>Resolution: {node.nativeResolution}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "cube" && (
            <div>
              <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--agribrain-violet)", textTransform: "uppercase" }}>
                Multi-Layer Spatial Tensor
              </div>
              <h3 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0 12px" }}>
                CanonicalFieldCube
              </h3>
              <p style={{ fontSize: "14px", color: "var(--text-muted)", lineHeight: 1.6, marginBottom: "24px" }}>
                Encodes physiological vegetation state, soil moisture balance, and biological threat layers across sub-grid coordinates without falsely implying dense observation.
              </p>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
                {cube.cells.map((cell) => (
                  <div key={cell.voxelId} style={{ padding: "16px", borderRadius: "var(--radius-md)", background: "var(--surface-code)", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ fontSize: "11px", color: "var(--agribrain-violet)", fontWeight: 700 }}>{cell.layer}</div>
                    <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0" }}>{cell.valueLabel}</div>
                    <div style={{ fontSize: "11px", color: "var(--text-dim)" }}>Support: {cell.supportType} · Authority: {cell.authority}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "worldline" && (
            <div>
              <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--field-green)", textTransform: "uppercase" }}>
                Longitudinal Field Memory
              </div>
              <h3 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0 12px" }}>
                CanonicalPlotWorldline
              </h3>
              <p style={{ fontSize: "14px", color: "var(--text-muted)", lineHeight: 1.6, marginBottom: "24px" }}>
                Preserves a continuous temporal memory connecting sowing events, emergence, moisture anomalies, and harvest outcome ground truth.
              </p>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px" }}>
                {worldline.events.slice(0, 4).map((evt) => (
                  <div key={evt.id} style={{ padding: "16px", borderRadius: "var(--radius-md)", background: "var(--surface-code)", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ fontSize: "11px", color: "var(--field-green)", fontWeight: 700 }}>{evt.date} · {evt.stage}</div>
                    <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0" }}>{evt.title}</div>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>{evt.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
