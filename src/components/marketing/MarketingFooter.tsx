"use client";

import React from "react";
import Link from "next/link";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/* ═══ MarketingFooter ══════════════════════════════════════════
   Localized footer for the marketing homepage.
   Real links only, powered by useLanguage().
   ═══════════════════════════════════════════════════════════════ */

export default function MarketingFooter() {
  const { t } = useLanguage();

  const sections = [
    {
      title: t.footer.platform,
      links: [
        { label: t.footer.fieldMonitoring, href: "/farm" },
        { label: t.footer.cropIntelligence, href: "/farm" },
        { label: t.footer.agribrain, href: "/agribrain" },
      ],
    },
    {
      title: t.footer.solutions,
      links: [
        { label: t.footer.farmers, href: "#solutions" },
        { label: t.footer.agronomists, href: "#solutions" },
        { label: t.footer.farmEnterprise, href: "#solutions" },
        { label: t.footer.banksInsurance, href: "#solutions" },
        { label: t.footer.government, href: "#solutions" },
      ],
    },
    {
      title: t.footer.company,
      links: [
        { label: t.footer.about, href: "#" },
        { label: t.footer.contact, href: "#" },
        { label: t.footer.privacy, href: "#" },
        { label: t.footer.terms, href: "#" },
      ],
    },
  ];

  return (
    <footer
      style={{
        borderTop: "1px solid var(--border-subtle)",
        padding: "56px 0 32px",
      }}
    >
      <div className="marketing-container">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "2fr 1fr 1fr 1fr",
            gap: "40px",
            marginBottom: "40px",
          }}
        >
          {/* Brand */}
          <div>
            <div
              style={{
                fontSize: "18px",
                fontWeight: 800,
                color: "var(--text-primary)",
                marginBottom: "12px",
              }}
            >
              Agri<span style={{ color: "var(--field-green)" }}>Wise</span>
            </div>
            <p
              style={{
                fontSize: "13px",
                color: "var(--text-dim)",
                lineHeight: 1.6,
                maxWidth: "320px",
              }}
            >
              {t.footer.slogan}
              <br />
              {t.footer.tagline}
            </p>
          </div>

          {/* Link columns */}
          {sections.map((section) => (
            <div key={section.title}>
              <h4
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "var(--text-secondary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  marginBottom: "14px",
                }}
              >
                {section.title}
              </h4>
              {section.links.map((link) => (
                <Link
                  key={link.label}
                  href={link.href}
                  style={{
                    display: "block",
                    fontSize: "13px",
                    color: "var(--text-dim)",
                    textDecoration: "none",
                    marginBottom: "8px",
                    transition: "color 0.15s ease",
                  }}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div
          style={{
            borderTop: "1px solid var(--border-subtle)",
            paddingTop: "20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--text-faint)" }}>
            🇩🇿 Built in Algeria · © {new Date().getFullYear()} AgriWise · {t.footer.rightsReserved}
          </span>
          <span style={{ fontSize: "11px", color: "var(--text-faint)" }}>
            Powered by AgriBrain · Copernicus Programme
          </span>
        </div>
      </div>
    </footer>
  );
}
