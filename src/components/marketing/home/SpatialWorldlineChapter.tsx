import React from "react";
import { getWorldline } from "@/components/experience/scientific-run/selectors";
import { Clock, Calendar, ShieldCheck } from "lucide-react";

/* ═══ AgriWise R2 Pass 3 — SpatialWorldlineChapter ══════════════
   Spatial Parcel Memory Timeline (Server HTML Component).
   Contains data-r2-chapter="worldline" attribute.
   ═══════════════════════════════════════════════════════════════ */

export default function SpatialWorldlineChapter() {
  const worldline = getWorldline();

  return (
    <section
      id="worldline"
      data-r2-chapter="worldline"
      data-r2-narrative="true"
      style={{
        position: "relative",
        paddingTop: "120px",
        paddingBottom: "120px",
      }}
    >
      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        <div style={{ maxWidth: "600px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(74, 222, 128, 0.08)",
              border: "1px solid rgba(74, 222, 128, 0.2)",
              color: "var(--field-green)",
              marginBottom: "16px",
            }}
          >
            <Clock size={12} /> Temporal Field Memory
          </div>

          <h2 className="marketing-section-title" style={{ fontSize: "clamp(2rem, 3.5vw, 3rem)", margin: "0 0 16px" }}>
            AgriBrain does not inspect a single image.{" "}
            <strong className="marketing-gradient-text">It remembers the full season.</strong>
          </h2>

          <p className="marketing-section-subtitle" style={{ margin: "0 0 40px", textAlign: "left" }}>
            Longitudinal field worldline tracks phenological progression, environmental anomalies, and management interventions over Durum Wheat plot geometry.
          </p>
        </div>

        {/* Spatial Timeline Rail */}
        <div className="r2-worldline-rail">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "24px" }}>
            {worldline.events.slice(0, 4).map((evt) => (
              <div key={evt.id} className="r2-narrative-step">
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <Calendar size={14} color="var(--field-green)" />
                  <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--field-green)", fontFamily: "var(--font-mono)" }}>
                    {evt.date} · {evt.stage}
                  </span>
                </div>
                <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 6px" }}>
                  {evt.title}
                </h3>
                <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: "0 0 12px" }}>
                  {evt.description}
                </p>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "var(--text-dim)" }}>
                  <ShieldCheck size={12} color="var(--evidence-observed)" /> {evt.authority}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
