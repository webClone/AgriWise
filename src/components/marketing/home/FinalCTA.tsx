"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight, Globe, MapPin } from "lucide-react";
import InstitutionalContactDialog from "../InstitutionalContactDialog";
import type { ContactIntent } from "../data/audiences";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/* ═══ 07. Deployment — Category Proposition ═════════════════════
   "The intelligence layer for agricultural reality."
   
   Clean dual gateways:
   1. Field Operators & Cooperatives (Deploy Field Intelligence)
   2. Enterprises & Sovereigns (Request Technical Briefing)
   ═══════════════════════════════════════════════════════════════ */

export default function FinalCTA() {
  const { t } = useLanguage();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogIntent, setDialogIntent] = useState<ContactIntent>("enterprise");

  const openContact = (intent: ContactIntent) => {
    setDialogIntent(intent);
    setDialogOpen(true);
  };

  return (
    <section
      id="deployment"
      className="deep-tech-lattice"
      style={{
        position: "relative",
        paddingTop: "140px",
        paddingBottom: "140px",
        borderTop: "1px solid rgba(255, 255, 255, 0.08)",
        background: "linear-gradient(180deg, #05070B 0%, #060B14 50%, #05070B 100%)",
        overflow: "hidden",
      }}
    >
      {/* Subtle radial green bloom */}
      <div
        style={{
          position: "absolute",
          bottom: "-20%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "60vw",
          height: "40vh",
          background: "radial-gradient(ellipse, rgba(0, 230, 118, 0.08) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        {/* Section Headline */}
        <div style={{ maxWidth: "880px", margin: "0 auto 64px", textAlign: "center" }}>
          <div className="fiducial-badge" style={{ marginBottom: "24px" }}>
            <span className="pulse-dot" />
            <span>{t.deployment.sectionBadge}</span>
          </div>

          <h2
            className="font-heading"
            style={{
              fontSize: "clamp(2.6rem, 5.2vw, 4.6rem)",
              fontWeight: 800,
              lineHeight: 1.15,
              letterSpacing: "-0.035em",
              color: "#ffffff",
              margin: "0 0 24px",
            }}
          >
            {t.deployment.headlineMain} <br />
            <span
              style={{
                background: "linear-gradient(135deg, #00E676 0%, #00D9FF 50%, #818CF8 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              {t.deployment.headlineAccent}
            </span>
          </h2>

          <p
            style={{
              fontSize: "clamp(17px, 2vw, 21px)",
              color: "#94a3b8",
              lineHeight: 1.65,
              margin: "0 auto",
              maxWidth: "720px",
            }}
          >
            {t.deployment.subheadline}
          </p>
        </div>

        {/* Dual Gateways */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "28px",
            maxWidth: "960px",
            margin: "0 auto",
          }}
          className="deployment-grid"
        >
          {/* Gateway 1: Field Operators */}
          <div
            className="dribbble-glass-card hover-lift transition-smooth"
            style={{
              padding: "40px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              borderRadius: "24px",
              borderColor: "rgba(0, 230, 118, 0.35)",
              background: "rgba(10, 15, 25, 0.85)",
              boxShadow: "0 20px 50px -15px rgba(0, 230, 118, 0.15)",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                <MapPin size={20} color="#00E676" />
                <span className="tech-meta font-mono-telemetry" style={{ color: "#00E676", fontSize: "11px", letterSpacing: "0.1em" }}>
                  {t.deployment.fieldGateway.badge}
                </span>
              </div>

              <h3 className="font-heading" style={{ fontSize: "24px", fontWeight: 800, color: "#ffffff", margin: "0 0 12px", letterSpacing: "-0.02em" }}>
                {t.deployment.fieldGateway.title}
              </h3>

              <p style={{ fontSize: "14px", color: "#94a3b8", lineHeight: 1.6, margin: "0 0 28px" }}>
                {t.deployment.fieldGateway.desc}
              </p>
            </div>

            <div>
              <Link
                href="/farm/new"
                className="hover-lift transition-smooth"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  width: "100%",
                  padding: "16px 28px",
                  borderRadius: "14px",
                  background: "#00E676",
                  color: "#05070B",
                  fontSize: "15px",
                  fontWeight: 700,
                  textDecoration: "none",
                  boxShadow: "0 10px 30px -5px rgba(0, 230, 118, 0.45)",
                }}
              >
                <span>{t.deployment.fieldGateway.cta}</span>
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>

          {/* Gateway 2: Institutional & Sovereign */}
          <div
            className="dribbble-glass-card hover-lift transition-smooth"
            style={{
              padding: "40px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              borderRadius: "24px",
              borderColor: "rgba(0, 217, 255, 0.3)",
              background: "rgba(10, 15, 25, 0.85)",
              boxShadow: "0 20px 50px -15px rgba(0, 217, 255, 0.15)",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                <Globe size={20} color="#00D9FF" />
                <span className="tech-meta font-mono-telemetry" style={{ color: "#00D9FF", fontSize: "11px", letterSpacing: "0.1em" }}>
                  {t.deployment.enterpriseGateway.badge}
                </span>
              </div>

              <h3 className="font-heading" style={{ fontSize: "24px", fontWeight: 800, color: "#ffffff", margin: "0 0 12px", letterSpacing: "-0.02em" }}>
                {t.deployment.enterpriseGateway.title}
              </h3>

              <p style={{ fontSize: "14px", color: "#94a3b8", lineHeight: 1.6, margin: "0 0 28px" }}>
                {t.deployment.enterpriseGateway.desc}
              </p>
            </div>

            <div>
              <button
                onClick={() => openContact("enterprise")}
                className="hover-lift transition-smooth"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  width: "100%",
                  padding: "16px 28px",
                  borderRadius: "14px",
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.18)",
                  color: "#ffffff",
                  fontSize: "15px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                <span>{t.deployment.enterpriseGateway.cta}</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>

        <div
          style={{
            textAlign: "center",
            marginTop: "52px",
            fontSize: "12px",
            fontFamily: "var(--font-mono)",
            color: "#64748b",
          }}
        >
          {t.deployment.complianceNotice}
        </div>

        <InstitutionalContactDialog
          isOpen={dialogOpen}
          onClose={() => setDialogOpen(false)}
          intent={dialogIntent}
        />
      </div>

      <style>{`
        @media (max-width: 840px) {
          .deployment-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </section>
  );
}
