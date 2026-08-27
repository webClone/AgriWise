"use client";

import { useState } from "react";
import Link from "next/link";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import { AUDIENCES, AUDIENCE_IDS, type AudienceId, type ContactIntent } from "./data/audiences";
import InstitutionalContactDialog from "./InstitutionalContactDialog";

/* ═══ CTAConstellation ═════════════════════════════════════════
   Final role-based CTA section.
   Every stakeholder gets an explicit, tailormade next step.
   Institutional roles open InstitutionalContactDialog with prefilled role context.
   Direct app users (farmers, agronomists) route to real app routes.
   ═══════════════════════════════════════════════════════════════ */

export default function CTAConstellation() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogIntent, setDialogIntent] = useState<ContactIntent>("enterprise");

  const openContact = (intent: ContactIntent) => {
    setDialogIntent(intent);
    setDialogOpen(true);
  };

  return (
    <section
      className="marketing-section"
      id="cta-constellation"
      style={{
        borderTop: "1px solid var(--border-subtle)",
        background: "linear-gradient(180deg, var(--surface-base) 0%, rgba(34, 197, 94, 0.03) 100%)",
        paddingBottom: "120px",
      }}
    >
      <div className="marketing-container">
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "64px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "var(--field-green-dim)",
                border: "1px solid rgba(74, 222, 128, 0.15)",
                color: "var(--field-green)",
              }}
            >
              Get Started
            </div>
            <h2 className="marketing-section-title">
              Agricultural intelligence,{" "}
              <strong className="marketing-gradient-text">tailored to your mission</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              Select your role below to launch field intelligence or connect with our enterprise team.
            </p>
          </div>
        </Reveal>

        {/* 10-Role CTA Constellation Grid */}
        <StaggerContainer stagger={0.04} className="marketing-grid-3" style={{ marginBottom: "40px" }}>
          {AUDIENCE_IDS.map((roleId) => {
            const aud = AUDIENCES[roleId];
            return (
              <StaggerItem key={roleId}>
                <div
                  className="marketing-card"
                  style={{
                    padding: "24px",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    borderColor: "var(--border-subtle)",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                      <span style={{ fontSize: "1.4rem" }} aria-hidden="true">{aud.icon}</span>
                      <span style={{ fontSize: "16px", fontWeight: 700, color: aud.color }}>
                        {aud.label}
                      </span>
                    </div>
                    <p style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 16px" }}>
                      {aud.tagline}
                    </p>
                  </div>

                  <div>
                    {aud.primaryAction.type === "route" ? (
                      <Link
                        href={aud.primaryAction.href}
                        className="marketing-cta-primary"
                        style={{ width: "100%", justifyContent: "center", padding: "8px 16px", fontSize: "13px", borderRadius: "var(--radius-sm)" }}
                      >
                        {aud.primaryAction.label} →
                      </Link>
                    ) : (
                      <button
                        onClick={() => openContact(roleId as ContactIntent)}
                        className="marketing-cta-primary"
                        style={{ width: "100%", justifyContent: "center", padding: "8px 16px", fontSize: "13px", borderRadius: "var(--radius-sm)" }}
                      >
                        {aud.primaryAction.label} →
                      </button>
                    )}
                  </div>
                </div>
              </StaggerItem>
            );
          })}
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
