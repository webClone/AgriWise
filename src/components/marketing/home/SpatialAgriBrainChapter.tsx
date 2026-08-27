import React from "react";
import { Cpu, Network, Box, Clock } from "lucide-react";

/* ═══ AgriWise R2 Pass 3 — SpatialAgriBrainChapter ═════════════
   AgriBrain 3 Canonical Concepts (Server HTML Component).
   Contains data-r2-chapter="agribrain-organism" attribute.
   ═══════════════════════════════════════════════════════════════ */

export default function SpatialAgriBrainChapter() {
  return (
    <section
      id="agribrain-organism"
      data-r2-chapter="agribrain-organism"
      data-r2-narrative="true"
      style={{
        position: "relative",
        paddingTop: "120px",
        paddingBottom: "120px",
      }}
    >
      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        <div style={{ textAlign: "center", marginBottom: "56px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(167, 139, 250, 0.08)",
              border: "1px solid rgba(167, 139, 250, 0.2)",
              color: "var(--agribrain-violet)",
              marginBottom: "16px",
            }}
          >
            <Cpu size={12} /> The AgriBrain Operational Layer
          </div>

          <h2 className="marketing-section-title" style={{ fontSize: "clamp(2rem, 3.5vw, 3rem)" }}>
            Three canonical structures power{" "}
            <strong className="marketing-gradient-text">every decision</strong>
          </h2>

          <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
            AgriBrain does not produce loose text or ungrounded scores. It constructs spatial evidence graphs, volumetric field cubes, and plot worldlines.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "20px" }}>
          <div className="r2-narrative-step">
            <Network size={24} color="var(--evidence-observed)" style={{ marginBottom: "12px" }} />
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
              1. Canonical Evidence Graph
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: 0 }}>
              Links multi-source observations to physical parcel geometries with cryptographic provenance hashes and authority ceilings.
            </p>
          </div>

          <div className="r2-narrative-step">
            <Box size={24} color="var(--agribrain-violet)" style={{ marginBottom: "12px" }} />
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
              2. Canonical Field Cube
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: 0 }}>
              Multi-dimensional spatial-temporal voxels holding observed reflectance, reconstructed moisture, and model-state uncertainty.
            </p>
          </div>

          <div className="r2-narrative-step">
            <Clock size={24} color="var(--field-green)" style={{ marginBottom: "12px" }} />
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
              3. Plot Worldline Memory
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: 0 }}>
              Longitudinal parcel ledger recording phenological progression, management interventions, and verified harvest outcomes over time.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
