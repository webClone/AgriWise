import React from "react";
import { Landmark, ShieldAlert, Building2 } from "lucide-react";

/* ═══ AgriWise R2 Pass 3 — SpatialInstitutionalChapter ═════════
   Institutional Credit & Insurance Risk Projections (Server HTML).
   Contains data-r2-chapter="institutional" attribute.
   ═══════════════════════════════════════════════════════════════ */

export default function SpatialInstitutionalChapter() {
  return (
    <section
      id="institutional"
      data-r2-chapter="institutional"
      data-r2-narrative="true"
      style={{
        position: "relative",
        paddingTop: "120px",
        paddingBottom: "120px",
      }}
    >
      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        <div style={{ maxWidth: "620px", marginBottom: "48px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(96, 165, 250, 0.08)",
              border: "1px solid rgba(96, 165, 250, 0.2)",
              color: "var(--accent-bank)",
              marginBottom: "16px",
            }}
          >
            <Landmark size={12} /> Institutional Intelligence
          </div>

          <h2 className="marketing-section-title" style={{ fontSize: "clamp(2rem, 3.5vw, 3rem)", margin: "0 0 16px" }}>
            Evidence-backed credit & insurance{" "}
            <strong className="marketing-gradient-text">for financial capital</strong>
          </h2>

          <p className="marketing-section-subtitle" style={{ margin: 0, textAlign: "left" }}>
            Agricultural lenders and insurers monitor collateral health and verify climate claims directly against spatial field worldlines.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "24px" }}>
          <div className="r2-narrative-step">
            <Building2 size={24} color="var(--accent-bank)" style={{ marginBottom: "12px" }} />
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
              Agricultural Banking & Credit
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: 0 }}>
              Stage-tracked loan collateral monitoring, early crop stress alerts, and automated portfolio risk scoring across commercial agricultural borrowers.
            </p>
          </div>

          <div className="r2-narrative-step">
            <ShieldAlert size={24} color="var(--accent-insurance)" style={{ marginBottom: "12px" }} />
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>
              Agricultural Parametric Insurance
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: 0 }}>
              Auditable event footprints for drought, frost, and inundation. Eliminates costly manual loss adjustment through objective satellite evidence.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
