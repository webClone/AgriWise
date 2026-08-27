"use client";

import { useState } from "react";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import InstitutionalContactDialog from "./InstitutionalContactDialog";
import { type ContactIntent } from "./data/audiences";

/* ═══ EcosystemStory ══════════════════════════════════════════
   Cooperatives, Agribusiness, and Agricultural Research.
   ═══════════════════════════════════════════════════════════════ */

export default function EcosystemStory() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogIntent, setDialogIntent] = useState<ContactIntent>("cooperative");

  const openContact = (intent: ContactIntent) => {
    setDialogIntent(intent);
    setDialogOpen(true);
  };

  return (
    <section
      className="marketing-section"
      id="ecosystem"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "56px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "rgba(52, 211, 153, 0.1)",
                border: "1px solid rgba(52, 211, 153, 0.2)",
                color: "var(--accent-cooperative)",
              }}
            >
              Agricultural Ecosystem
            </div>
            <h2 className="marketing-section-title">
              Intelligence for{" "}
              <strong>cooperatives, supply chains & research</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              From member harvest coordination to supply chain procurement and longitudinal agronomic science.
            </p>
          </div>
        </Reveal>

        <StaggerContainer stagger={0.06} className="marketing-grid-3">
          {/* Cooperative */}
          <StaggerItem>
            <div className="marketing-card" style={{ height: "100%", padding: "28px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: "1.8rem", marginBottom: "12px" }} aria-hidden="true">🤝</div>
                <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--accent-cooperative)", margin: "0 0 8px" }}>
                  Agricultural Cooperatives
                </h3>
                <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: "0 0 16px" }}>
                  Coordinate harvest timing across member farms, optimize shared equipment, aggregate quality expectations, and streamline member input purchasing.
                </p>
              </div>
              <button onClick={() => openContact("cooperative")} className="marketing-cta-secondary" style={{ padding: "8px 16px", fontSize: "12px" }}>
                Explore Cooperative Intelligence →
              </button>
            </div>
          </StaggerItem>

          {/* Agribusiness */}
          <StaggerItem>
            <div className="marketing-card" style={{ height: "100%", padding: "28px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: "1.8rem", marginBottom: "12px" }} aria-hidden="true">📦</div>
                <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--accent-agribusiness)", margin: "0 0 8px" }}>
                  Agribusiness & Supply
                </h3>
                <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: "0 0 16px" }}>
                  Source-region monitoring, procurement timing, supply availability forecasting, and quality assessment based on satellite observation.
                </p>
              </div>
              <button onClick={() => openContact("agribusiness")} className="marketing-cta-secondary" style={{ padding: "8px 16px", fontSize: "12px" }}>
                Explore Supply Intelligence →
              </button>
            </div>
          </StaggerItem>

          {/* Research */}
          <StaggerItem>
            <div className="marketing-card" style={{ height: "100%", padding: "28px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: "1.8rem", marginBottom: "12px" }} aria-hidden="true">🧪</div>
                <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--accent-research)", margin: "0 0 8px" }}>
                  Research & Academia
                </h3>
                <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.6, margin: "0 0 16px" }}>
                  Longitudinal multi-season datasets, experimental plot trial tracking, causal model discovery, and calibrated uncertainty quantification.
                </p>
              </div>
              <button onClick={() => openContact("research")} className="marketing-cta-secondary" style={{ padding: "8px 16px", fontSize: "12px" }}>
                Explore Research Infrastructure →
              </button>
            </div>
          </StaggerItem>
        </StaggerContainer>

        <InstitutionalContactDialog
          isOpen={dialogOpen}
          onClose={() => setDialogOpen(false)}
          intent={dialogIntent}
        />
      </div>
    </section>
  );
}
