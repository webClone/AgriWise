import React from "react";
import { Globe, ShieldCheck } from "lucide-react";

/* ═══ AgriWise R2 Pass 3 — SpatialSovereignChapter ══════════════
   Sovereign National Crop & Water Intelligence (Server HTML).
   Contains data-r2-chapter="sovereign" attribute.
   ═══════════════════════════════════════════════════════════════ */

export default function SpatialSovereignChapter() {
  return (
    <section
      id="sovereign"
      data-r2-chapter="sovereign"
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
              background: "rgba(167, 139, 250, 0.08)",
              border: "1px solid rgba(167, 139, 250, 0.2)",
              color: "var(--accent-government)",
              marginBottom: "16px",
            }}
          >
            <Globe size={12} /> Sovereign Agriculture & Water Governance
          </div>

          <h2 className="marketing-section-title" style={{ fontSize: "clamp(2rem, 3.5vw, 3rem)", margin: "0 0 16px" }}>
            Sovereign agricultural inventory{" "}
            <strong className="marketing-gradient-text">and food security signals</strong>
          </h2>

          <p className="marketing-section-subtitle" style={{ margin: 0, textAlign: "left" }}>
            Provides ministries of agriculture and water resources with real-time crop inventory, yield forecasts, and regional irrigation demand.
          </p>
        </div>

        {/* Regional Wilaya Scenario Overlay */}
        <div className="r2-sovereign-overlay">
          <div className="r2-narrative-step">
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent-government)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Wilaya Intelligence
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
              Mitidja Plain Cereal Belt
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5, margin: 0 }}>
              Durum wheat canopy vigor and seasonal water consumption tracked across regional agricultural parcels.
            </p>
          </div>

          <div className="r2-narrative-step">
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent-government)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Wilaya Intelligence
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
              Biskra Oasis Agriculture
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5, margin: 0 }}>
              Early market garden crop monitoring and groundwater withdrawal estimation across arid production zones.
            </p>
          </div>

          <div className="r2-narrative-step">
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent-government)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Wilaya Intelligence
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
              Guelma Grain Region
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5, margin: 0 }}>
              Cereal yield trajectory prediction and crop stress anomaly detection for national strategic reserves.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
