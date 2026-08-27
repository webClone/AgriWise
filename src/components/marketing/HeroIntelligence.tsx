"use client";
import { useState, useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Reveal } from "./motion/Reveal";
import {
  AUDIENCES,
  HERO_AUDIENCES,
  type AudienceId,
} from "./data/audiences";

/* ═══ HeroIntelligence ═════════════════════════════════════════
   Rebuilt hero per the product architecture brief.

   - Permanent headline: "Agricultural intelligence,
     from every field to the entire food system."
   - No typewriter effect.
   - Role chips alter the secondary hero canvas.
   - Three CTA tiers: primary, secondary, tertiary.
   ═══════════════════════════════════════════════════════════════ */

/** Preview canvas descriptions per role */
const ROLE_PREVIEWS: Record<
  AudienceId,
  { visual: string; metrics: { label: string; value: string; color: string }[] }
> = {
  farmer: {
    visual: "Single field view — irrigation state, vegetation health, task queue",
    metrics: [
      { label: "Field Health", value: "Vegetation active", color: "var(--field-green)" },
      { label: "Soil Moisture", value: "Adequate", color: "var(--evidence-observed)" },
      { label: "Next Action", value: "Scout zone B3", color: "var(--uncertainty-amber)" },
    ],
  },
  agronomist: {
    visual: "Portfolio of assigned farms — anomalies flagged, inspection priorities",
    metrics: [
      { label: "Farms Monitored", value: "24 farms", color: "var(--evidence-observed)" },
      { label: "Anomalies", value: "3 require inspection", color: "var(--uncertainty-amber)" },
      { label: "Hypotheses", value: "2 competing explanations", color: "var(--agribrain-violet)" },
    ],
  },
  enterprise: {
    visual: "Multi-field operations — team status, equipment, yield distribution",
    metrics: [
      { label: "Active Fields", value: "147 fields", color: "var(--accent-enterprise)" },
      { label: "Operations", value: "12 teams deployed", color: "var(--field-green)" },
      { label: "Yield Outlook", value: "P50 estimate available", color: "var(--evidence-observed)" },
    ],
  },
  cooperative: {
    visual: "Member farm aggregate — harvest coordination, quality assessment",
    metrics: [
      { label: "Members", value: "86 farms", color: "var(--accent-cooperative)" },
      { label: "Harvest Window", value: "Coordinated", color: "var(--field-green)" },
      { label: "Quality", value: "Assessment active", color: "var(--uncertainty-amber)" },
    ],
  },
  bank: {
    visual: "Portfolio risk distribution — crop cycle state, yield intervals",
    metrics: [
      { label: "Portfolio", value: "340 credit lines", color: "var(--accent-bank)" },
      { label: "Crop Cycle", value: "Stage-tracked", color: "var(--field-green)" },
      { label: "Yield Range", value: "P10–P90 intervals", color: "var(--evidence-observed)" },
    ],
  },
  insurance: {
    visual: "Event footprint — affected policies, before/after evidence",
    metrics: [
      { label: "Event", value: "Drought detected", color: "var(--risk-red)" },
      { label: "Affected", value: "47 policies", color: "var(--uncertainty-amber)" },
      { label: "Evidence", value: "Temporal package ready", color: "var(--evidence-observed)" },
    ],
  },
  government: {
    visual: "National agricultural canvas — crop inventory, water, food security",
    metrics: [
      { label: "Crop Area", value: "National inventory", color: "var(--accent-government)" },
      { label: "Water Demand", value: "Regional assessment", color: "var(--evidence-observed)" },
      { label: "Food Security", value: "Production signals", color: "var(--field-green)" },
    ],
  },
  agribusiness: {
    visual: "Supply intelligence — source regions, procurement quality, timing",
    metrics: [
      { label: "Regions", value: "12 source regions", color: "var(--accent-agribusiness)" },
      { label: "Quality", value: "Assessment active", color: "var(--field-green)" },
      { label: "Outlook", value: "Commodity signals", color: "var(--evidence-observed)" },
    ],
  },
  research: {
    visual: "Research infrastructure — longitudinal datasets, experimental plots",
    metrics: [
      { label: "Datasets", value: "Multi-season", color: "var(--accent-research)" },
      { label: "Plots", value: "Experimental support", color: "var(--field-green)" },
      { label: "Uncertainty", value: "Calibrated", color: "var(--evidence-observed)" },
    ],
  },
  api: {
    visual: "API architecture — field state, evidence layers, intelligence products",
    metrics: [
      { label: "Endpoints", value: "Field intelligence", color: "var(--text-secondary)" },
      { label: "Data", value: "Evidence layers", color: "var(--evidence-observed)" },
      { label: "Products", value: "Institutional signals", color: "var(--agribrain-violet)" },
    ],
  },
};

export default function HeroIntelligence() {
  const [activeRole, setActiveRole] = useState<AudienceId>("farmer");
  const prefersReduced = useReducedMotion();
  const preview = ROLE_PREVIEWS[activeRole];
  const audience = AUDIENCES[activeRole];

  const handleRoleSelect = useCallback((role: AudienceId) => {
    setActiveRole(role);
  }, []);

  return (
    <section className="marketing-hero marketing-section" id="hero">
      <div className="marketing-container">
        {/* ── Headline ──────────────────────────────────────── */}
        <Reveal>
          <h1 className="marketing-hero__title">
            Agricultural intelligence,{" "}
            <strong className="marketing-gradient-text">
              from every field to the entire food system.
            </strong>
          </h1>
        </Reveal>

        <Reveal delay={0.1}>
          <p className="marketing-hero__description">
            AgriWise is the operational intelligence platform powered by
            AgriBrain — transforming satellite, weather, soil, sensor and field
            evidence into traceable intelligence for agriculture, risk and
            national food security.
          </p>
        </Reveal>

        {/* ── CTAs ──────────────────────────────────────────── */}
        <Reveal delay={0.2}>
          <div className="marketing-hero__actions">
            <Link href="/farm/new" className="marketing-cta-primary">
              Analyze My Field →
            </Link>
            <Link href="#solutions" className="marketing-cta-secondary">
              Explore AgriWise for Organizations →
            </Link>
          </div>
          <div style={{ marginTop: "8px" }}>
            <Link href="/agribrain" className="marketing-cta-ghost">
              Discover AgriBrain →
            </Link>
          </div>
        </Reveal>

        {/* ── Role chips ────────────────────────────────────── */}
        <Reveal delay={0.3}>
          <div className="marketing-hero__roles" role="group" aria-label="Select your role">
            {HERO_AUDIENCES.map((roleId) => {
              const aud = AUDIENCES[roleId];
              return (
                <button
                  key={roleId}
                  className={`marketing-role-chip ${activeRole === roleId ? "marketing-role-chip--active" : ""}`}
                  onClick={() => handleRoleSelect(roleId)}
                  aria-pressed={activeRole === roleId}
                  style={activeRole === roleId ? { borderColor: aud.color, color: aud.color, background: `${aud.color}10` } : {}}
                >
                  <span aria-hidden="true">{aud.icon}</span>
                  {aud.shortLabel}
                </button>
              );
            })}
          </div>
        </Reveal>

        {/* ── Hero canvas — role-responsive preview ─────────── */}
        <Reveal delay={0.4}>
          <div style={{ marginTop: "40px", position: "relative" }}>
            {/* Dashboard screenshot background */}
            <div style={{
              borderRadius: "var(--radius-xl)",
              overflow: "hidden",
              border: "1px solid var(--border-default)",
              boxShadow: "var(--shadow-hero)",
              position: "relative",
            }}>
              <Image
                src="/landing/hero.jpg"
                alt="AgriWise agricultural intelligence dashboard"
                width={1200}
                height={675}
                style={{ width: "100%", height: "auto", display: "block" }}
                priority
              />
              {/* Gradient overlay */}
              <div style={{
                position: "absolute",
                inset: 0,
                background: "linear-gradient(180deg, transparent 30%, var(--surface-base) 100%)",
                pointerEvents: "none",
                borderRadius: "var(--radius-xl)",
              }} />
            </div>

            {/* Role-specific overlay panel */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeRole}
                initial={prefersReduced ? { opacity: 1 } : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={prefersReduced ? { opacity: 1 } : { opacity: 0, y: -8 }}
                transition={{ duration: prefersReduced ? 0 : 0.35, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  position: "absolute",
                  bottom: "24px",
                  left: "24px",
                  right: "24px",
                  padding: "20px 24px",
                  borderRadius: "var(--radius-lg)",
                  background: "var(--surface-modal)",
                  backdropFilter: "blur(20px)",
                  border: `1px solid ${audience.color}20`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
                  <span style={{ fontSize: "1.2rem" }} aria-hidden="true">{audience.icon}</span>
                  <div>
                    <div style={{ fontSize: "14px", fontWeight: 700, color: audience.color }}>
                      {audience.label}
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      {audience.tagline}
                    </div>
                  </div>
                </div>

                {/* Role-specific metrics */}
                <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                  {preview.metrics.map((m, i) => (
                    <div
                      key={i}
                      style={{
                        flex: "1 1 140px",
                        padding: "10px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(15, 23, 42, 0.5)",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                        {m.label}
                      </div>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: m.color, marginTop: "2px" }}>
                        {m.value}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Role-specific CTA */}
                <div style={{ marginTop: "14px", display: "flex", alignItems: "center", gap: "12px" }}>
                  <Link
                    href={audience.primaryAction.href || "#solutions"}
                    className="marketing-cta-primary"
                    style={{ padding: "8px 20px", fontSize: "13px", borderRadius: "var(--radius-sm)" }}
                  >
                    {audience.primaryAction.label}
                  </Link>
                  {audience.secondaryAction && (
                    <Link
                      href={audience.secondaryAction.href || "#solutions"}
                      className="marketing-cta-ghost"
                      style={{ fontSize: "12px" }}
                    >
                      {audience.secondaryAction.label}
                    </Link>
                  )}
                </div>

                <span className="marketing-illustrative-label" style={{ position: "absolute", top: "12px", right: "12px" }}>
                  Illustrative product view
                </span>
              </motion.div>
            </AnimatePresence>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
