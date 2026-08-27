"use client";

import { useState } from "react";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import InstitutionalContactDialog from "./InstitutionalContactDialog";

/* ═══ GovernmentStory ═════════════════════════════════════════
   National agricultural intelligence infrastructure:
   Crop inventory, water demand, food security, sovereign deployment.
   Full-screen cinematic section with camera zoom out concept.
   ═══════════════════════════════════════════════════════════════ */

export default function GovernmentStory() {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <section
      className="marketing-section marketing-section--full"
      id="government"
      style={{
        borderTop: "1px solid var(--border-subtle)",
        background: "linear-gradient(180deg, var(--surface-base) 0%, rgba(167, 139, 250, 0.04) 50%, var(--surface-base) 100%)",
        position: "relative",
      }}
    >
      <div className="marketing-container">
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "56px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "rgba(167, 139, 250, 0.12)",
                border: "1px solid rgba(167, 139, 250, 0.2)",
                color: "var(--accent-government)",
              }}
            >
              Sovereign Agricultural Infrastructure
            </div>
            <h2 className="marketing-section-title" style={{ fontSize: "clamp(2.2rem, 5vw, 3.8rem)" }}>
              National scale agricultural intelligence for{" "}
              <strong style={{ color: "var(--accent-government)" }}>governments & ministries</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "16px auto 0", textAlign: "center" }}>
              Monitor national crop acreage, forecast grain production, govern agricultural water allocation, track drought severity, and coordinate extension priorities with sovereign data control.
            </p>
          </div>
        </Reveal>

        {/* National Canvas Showcase */}
        <Reveal>
          <div
            className="marketing-card"
            style={{
              padding: "40px",
              borderRadius: "var(--radius-2xl)",
              borderColor: "rgba(167, 139, 250, 0.25)",
              background: "var(--surface-elevated-solid)",
              position: "relative",
              marginBottom: "48px",
            }}
          >
            <span className="marketing-illustrative-label" style={{ position: "absolute", top: "20px", right: "20px" }}>
              Illustrative product view
            </span>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "20px", marginBottom: "36px" }}>
              {[
                { label: "National Crop Inventory", val: "Acreage & Phenology", icon: "🌾" },
                { label: "Water Governance", val: "Evapotranspiration Demand", icon: "💧" },
                { label: "Food Security Signals", val: "Production Outlook", icon: "🍞" },
                { label: "Extension Priorities", val: "Targeted Field Interventions", icon: "🧑‍🌾" },
              ].map((item, i) => (
                <div
                  key={i}
                  style={{
                    padding: "20px",
                    borderRadius: "var(--radius-lg)",
                    background: "rgba(167, 139, 250, 0.05)",
                    border: "1px solid rgba(167, 139, 250, 0.12)",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: "1.8rem", marginBottom: "8px" }} aria-hidden="true">{item.icon}</div>
                  <div style={{ fontSize: "11px", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{item.label}</div>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--accent-government)", marginTop: "4px" }}>{item.val}</div>
                </div>
              ))}
            </div>

            <div style={{ padding: "24px", borderRadius: "var(--radius-lg)", background: "rgba(15, 23, 42, 0.8)", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
              <div style={{ fontSize: "13px", color: "var(--text-body)", lineHeight: 1.7, maxWidth: "780px", margin: "0 auto 20px" }}>
                Built in Algeria for national sovereignty. AgriWise can be deployed on private government cloud or on-premise infrastructure, maintaining full data sovereignty, security, and governance compliance.
              </div>
              <div style={{ display: "flex", justifyContent: "center", gap: "16px" }}>
                <button onClick={() => setDialogOpen(true)} className="marketing-cta-primary" style={{ padding: "12px 28px", fontSize: "14px", background: "linear-gradient(135deg, #a78bfa, #8b5cf6)" }}>
                  Explore Government Intelligence →
                </button>
                <button onClick={() => setDialogOpen(true)} className="marketing-cta-secondary" style={{ padding: "12px 28px", fontSize: "14px" }}>
                  Discuss Sovereign Deployment
                </button>
              </div>
            </div>
          </div>
        </Reveal>

        <InstitutionalContactDialog
          isOpen={dialogOpen}
          onClose={() => setDialogOpen(false)}
          intent="government"
          customTitle="Discuss Sovereign Agricultural Intelligence"
        />
      </div>
    </section>
  );
}
