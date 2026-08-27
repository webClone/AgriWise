"use client";

import { useState } from "react";
import { Reveal } from "./motion/Reveal";
import InstitutionalContactDialog from "./InstitutionalContactDialog";
import { type ContactIntent } from "./data/audiences";

/* ═══ FinanceStory ═════════════════════════════════════════════
   Split experience:
   - AgriBank Credit Intelligence: Crop-cycle state, yield intervals, stress trajectory. Decision support under human supervision.
   - Insurance Risk & Claims: Satellite event footprint, temporal before/after evidence, uncertainty quantification.
   ═══════════════════════════════════════════════════════════════ */

export default function FinanceStory() {
  const [activeTab, setActiveTab] = useState<"bank" | "insurance">("bank");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogIntent, setDialogIntent] = useState<ContactIntent>("bank");

  const openContact = (intent: ContactIntent) => {
    setDialogIntent(intent);
    setDialogOpen(true);
  };

  return (
    <section
      className="marketing-section"
      id="finance"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "48px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "rgba(96, 165, 250, 0.1)",
                border: "1px solid rgba(96, 165, 250, 0.2)",
                color: "var(--accent-bank)",
              }}
            >
              Agricultural Finance & Risk
            </div>
            <h2 className="marketing-section-title">
              Evidence-backed risk intelligence for{" "}
              <strong>banks and insurers</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              Replace subjective estimation with verifiable crop-cycle evidence, temporal satellite auditing, and calibrated yield intervals under human supervision.
            </p>
          </div>
        </Reveal>

        {/* Tab switch */}
        <Reveal>
          <div style={{ display: "flex", justifyContent: "center", gap: "12px", marginBottom: "40px" }}>
            <button
              onClick={() => setActiveTab("bank")}
              aria-pressed={activeTab === "bank"}
              style={{
                padding: "10px 24px",
                borderRadius: "24px",
                border: `1px solid ${activeTab === "bank" ? "var(--accent-bank)" : "var(--border-subtle)"}`,
                background: activeTab === "bank" ? "rgba(96, 165, 250, 0.15)" : "var(--surface-elevated)",
                color: activeTab === "bank" ? "var(--accent-bank)" : "var(--text-secondary)",
                fontSize: "14px",
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              🏦 AgriBank Credit Intelligence
            </button>
            <button
              onClick={() => setActiveTab("insurance")}
              aria-pressed={activeTab === "insurance"}
              style={{
                padding: "10px 24px",
                borderRadius: "24px",
                border: `1px solid ${activeTab === "insurance" ? "var(--accent-insurance)" : "var(--border-subtle)"}`,
                background: activeTab === "insurance" ? "rgba(245, 158, 11, 0.15)" : "var(--surface-elevated)",
                color: activeTab === "insurance" ? "var(--accent-insurance)" : "var(--text-secondary)",
                fontSize: "14px",
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              🛡️ Insurance Risk & Claims
            </button>
          </div>
        </Reveal>

        {/* Content Box */}
        <Reveal key={activeTab}>
          <div
            className="marketing-card"
            style={{
              padding: "40px",
              borderColor: activeTab === "bank" ? "rgba(96, 165, 250, 0.3)" : "rgba(245, 158, 11, 0.3)",
              background: "var(--surface-elevated)",
              position: "relative",
            }}
          >
            <span className="marketing-illustrative-label" style={{ position: "absolute", top: "20px", right: "20px" }}>
              Illustrative product view
            </span>

            {activeTab === "bank" ? (
              <div>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--accent-bank)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Decision Support Under Human Supervision
                </div>
                <h3 style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-primary)", margin: "6px 0 16px" }}>
                  Agricultural credit that can see the crop cycle
                </h3>
                <p style={{ fontSize: "15px", color: "var(--text-muted)", lineHeight: 1.7, maxWidth: "720px", marginBottom: "32px" }}>
                  AgriBank intelligence monitors collateral fields throughout the crop season. It tracks phenological growth stages, verifies actual sowing dates against loan disbursement, and computes calibrated P10/P50/P90 yield distributions to support underwriting decisions.
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", marginBottom: "32px" }}>
                  {[
                    { label: "Crop Cycle Trajectory", val: "Stage 4 (Heading)", sub: "Verified via Sentinel-2" },
                    { label: "Yield Expectation Interval", val: "4.2 – 4.9 t/ha", sub: "P10/P50/P90 calibrated" },
                    { label: "Historical Stress Index", val: "Low Deficit", sub: "Zero major drought events" },
                  ].map((stat, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "16px",
                        borderRadius: "var(--radius-md)",
                        background: "rgba(96, 165, 250, 0.05)",
                        border: "1px solid rgba(96, 165, 250, 0.12)",
                      }}
                    >
                      <div style={{ fontSize: "11px", color: "var(--text-dim)", textTransform: "uppercase" }}>{stat.label}</div>
                      <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--accent-bank)", margin: "4px 0" }}>{stat.val}</div>
                      <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{stat.sub}</div>
                    </div>
                  ))}
                </div>

                <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
                  <button onClick={() => openContact("bank")} className="marketing-cta-primary" style={{ padding: "12px 24px", fontSize: "14px" }}>
                    Explore AgriBank Intelligence →
                  </button>
                  <button onClick={() => openContact("bank")} className="marketing-cta-ghost" style={{ fontSize: "13px" }}>
                    Discuss Portfolio Integration
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--accent-insurance)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Claims Evidence & Auditability
                </div>
                <h3 style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-primary)", margin: "6px 0 16px" }}>
                  From satellite event to defensible field evidence
                </h3>
                <p style={{ fontSize: "15px", color: "var(--text-muted)", lineHeight: 1.7, maxWidth: "720px", marginBottom: "32px" }}>
                  When drought, flood, or frost strikes, AgriWise identifies the spatial footprint across insured portfolios. Generates temporal before-and-after satellite evidence packages with explicit uncertainty bounds for fast, fair, and auditable claims processing.
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", marginBottom: "32px" }}>
                  {[
                    { label: "Event Footprint", val: "Frost Event (Mar 12)", sub: "3,200 ha affected" },
                    { label: "Temporal Audit", val: "T-7d vs T+3d", sub: "SAR + Thermal verification" },
                    { label: "Claims Evidence Package", val: "Verifiable PDF/JSON", sub: "Audit-ready evidence chain" },
                  ].map((stat, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "16px",
                        borderRadius: "var(--radius-md)",
                        background: "rgba(245, 158, 11, 0.05)",
                        border: "1px solid rgba(245, 158, 11, 0.12)",
                      }}
                    >
                      <div style={{ fontSize: "11px", color: "var(--text-dim)", textTransform: "uppercase" }}>{stat.label}</div>
                      <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--accent-insurance)", margin: "4px 0" }}>{stat.val}</div>
                      <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{stat.sub}</div>
                    </div>
                  ))}
                </div>

                <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
                  <button onClick={() => openContact("insurance")} className="marketing-cta-primary" style={{ padding: "12px 24px", fontSize: "14px", background: "linear-gradient(135deg, #f59e0b, #d97706)" }}>
                    Explore Insurance Risk →
                  </button>
                  <button onClick={() => openContact("insurance")} className="marketing-cta-ghost" style={{ fontSize: "13px" }}>
                    Discuss Claims & Risk API
                  </button>
                </div>
              </div>
            )}
          </div>
        </Reveal>

        <InstitutionalContactDialog
          isOpen={dialogOpen}
          onClose={() => setDialogOpen(false)}
          intent={dialogIntent}
        />
      </div>
    </section>
  );
}
