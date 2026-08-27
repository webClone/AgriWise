import React from "react";
import { Cpu, Satellite, Radio, CloudSun, Database, Layers, ArrowRight, Code } from "lucide-react";

/* ═══ AgriWise R2 Pass 3 — SpatialInfrastructureChapter ════════
   Systems Topology & Data Infrastructure Flow (Server HTML).
   Contains data-r2-chapter="infrastructure" attribute.
   ═══════════════════════════════════════════════════════════════ */

export default function SpatialInfrastructureChapter() {
  return (
    <section
      id="infrastructure"
      data-r2-chapter="infrastructure"
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
              background: "rgba(34, 211, 238, 0.08)",
              border: "1px solid rgba(34, 211, 238, 0.2)",
              color: "var(--evidence-observed)",
              marginBottom: "16px",
            }}
          >
            <Code size={12} /> Interoperable Systems Topology
          </div>

          <h2 className="marketing-section-title" style={{ fontSize: "clamp(2rem, 3.5vw, 3rem)" }}>
            Connects to your existing{" "}
            <strong className="marketing-gradient-text">agronomic & IT infrastructure</strong>
          </h2>

          <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
            REST & GraphQL APIs, GeoJSON spatial exports, and ISO 11783 tractor telemetry streams.
          </p>
        </div>

        {/* Systems Topology Architecture Diagram Flow */}
        <div
          className="r2-narrative-step"
          style={{
            padding: "40px",
            display: "grid",
            gridTemplateColumns: "1fr 60px 1fr 60px 1fr",
            alignItems: "center",
            gap: "16px",
          }}
        >
          {/* Data Sources Ingestion Rail */}
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Data Sources
            </div>
            <div className="r2-spatial-tag r2-tag-observed"><Satellite size={12} /> Sentinel-1/2 & Planet</div>
            <div className="r2-spatial-tag r2-tag-observed"><CloudSun size={12} /> ECMWF Weather Reanalysis</div>
            <div className="r2-spatial-tag r2-tag-observed"><Radio size={12} /> Soil & Water IoT Telemetry</div>
            <div className="r2-spatial-tag r2-tag-observed"><Database size={12} /> Soil Lab Analysis Reports</div>
          </div>

          {/* Flow Connector Arrow */}
          <div style={{ display: "flex", justifyContent: "center", color: "var(--evidence-observed)" }}>
            <ArrowRight size={24} />
          </div>

          {/* Core Engine */}
          <div style={{ padding: "24px", borderRadius: "var(--radius-lg)", background: "rgba(167, 139, 250, 0.1)", border: "1px solid rgba(167, 139, 250, 0.3)", textAlign: "center" }}>
            <Cpu size={28} color="var(--agribrain-violet)" style={{ marginBottom: "8px" }} />
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
              AgriWise Core Engine
            </h3>
            <div style={{ fontSize: "11px", color: "var(--agribrain-violet)", marginTop: "4px" }}>
              ASMAE Radiometric Closure & Provenance Graph
            </div>
          </div>

          {/* Flow Connector Arrow */}
          <div style={{ display: "flex", justifyContent: "center", color: "var(--agribrain-violet)" }}>
            <ArrowRight size={24} />
          </div>

          {/* Output Integrations */}
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Enterprise Outputs
            </div>
            <div className="r2-spatial-tag r2-tag-reconstructed"><Layers size={12} /> REST & GraphQL APIs</div>
            <div className="r2-spatial-tag r2-tag-reconstructed"><Layers size={12} /> Farmer Advisory Dashboard</div>
            <div className="r2-spatial-tag r2-tag-reconstructed"><Layers size={12} /> Bank & Insurance Portals</div>
            <div className="r2-spatial-tag r2-tag-reconstructed"><Layers size={12} /> Sovereign Ministry Dashboard</div>
          </div>
        </div>
      </div>
    </section>
  );
}
