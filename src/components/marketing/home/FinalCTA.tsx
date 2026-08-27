"use client";

import React, { useState } from "react";
import Link from "next/link";
import { AUDIENCES, AUDIENCE_IDS, type AudienceId, type ContactIntent } from "../data/audiences";
import InstitutionalContactDialog from "../InstitutionalContactDialog";
import { ArrowRight, User, Stethoscope, Building2, Users, Landmark, ShieldCheck, Globe, Package, TestTube, Code } from "lucide-react";

/* ═══ AgriWise R2 — FinalCTA ═══════════════════════════════════
   Final role-based CTA constellation using Lucide iconography.
   ═══════════════════════════════════════════════════════════════ */

const ROLE_ICONS: Record<string, any> = {
  farmer: User,
  agronomist: Stethoscope,
  enterprise: Building2,
  cooperative: Users,
  bank: Landmark,
  insurance: ShieldCheck,
  government: Globe,
  agribusiness: Package,
  research: TestTube,
  api: Code,
};

export default function FinalCTA() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogIntent, setDialogIntent] = useState<ContactIntent>("enterprise");

  const openContact = (intent: ContactIntent) => {
    setDialogIntent(intent);
    setDialogOpen(true);
  };

  return (
    <section
      id="cta-constellation"
      style={{
        position: "relative",
        paddingTop: "100px",
        paddingBottom: "140px",
        borderTop: "1px solid var(--border-subtle)",
        background: "linear-gradient(180deg, var(--surface-base) 0%, rgba(34, 197, 94, 0.03) 100%)",
      }}
    >
      <div className="marketing-container">
        <div style={{ textAlign: "center", marginBottom: "64px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "var(--field-green-dim)",
              border: "1px solid rgba(74, 222, 128, 0.15)",
              color: "var(--field-green)",
            }}
          >
            Launch Intelligence
          </div>
          <h2 className="marketing-section-title">
            Agricultural intelligence,{" "}
            <strong className="marketing-gradient-text">tailored to your mission</strong>
          </h2>
          <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
            Select your role below to launch field intelligence or connect with our institutional deployment team.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
          {AUDIENCE_IDS.map((roleId) => {
            const aud = AUDIENCES[roleId];
            const Icon = ROLE_ICONS[roleId] || User;
            return (
              <div
                key={roleId}
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
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
                    <Icon size={20} color={aud.color} />
                    <span style={{ fontSize: "16px", fontWeight: 700, color: aud.color }}>
                      {aud.label}
                    </span>
                  </div>
                  <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 20px" }}>
                    {aud.tagline}
                  </p>
                </div>

                <div>
                  {aud.primaryAction.type === "route" ? (
                    <Link
                      href={aud.primaryAction.href}
                      className="marketing-cta-primary"
                      style={{ width: "100%", justifyContent: "center", padding: "10px 16px", fontSize: "13px", borderRadius: "var(--radius-sm)" }}
                    >
                      {aud.primaryAction.label} <ArrowRight size={14} />
                    </Link>
                  ) : (
                    <button
                      onClick={() => openContact(roleId as ContactIntent)}
                      className="marketing-cta-primary"
                      style={{ width: "100%", justifyContent: "center", padding: "10px 16px", fontSize: "13px", borderRadius: "var(--radius-sm)" }}
                    >
                      {aud.primaryAction.label} <ArrowRight size={14} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <InstitutionalContactDialog
          isOpen={dialogOpen}
          onClose={() => setDialogOpen(false)}
          intent={dialogIntent}
        />
      </div>
    </section>
  );
}
