"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Users,
  Tractor,
  Building2,
  Landmark,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  TrendingUp,
  Droplets,
  Sprout,
  BarChart3,
  Calendar,
  Layers,
  Sparkles,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/* ═══ SECTION 08: Built for Everyone Who Makes Agricultural Decisions ═══
   Apple Pro / Palantir Operational Standard
   The 4 Product Doors from the AgriBrain Monograph:
   1. Farmers: "Understand your field."
   2. Agricultural Enterprises: "Operate your production."
   3. Cooperatives: "Coordinate your network."
   4. Institutions & Sovereigns: "Govern the agricultural system."
   ═════════════════════════════════════════════════════════════════════ */

interface StakeholderDoor {
  id: string;
  badge: string;
  title: string;
  subtitle: string;
  tagline: string;
  coreQuestion: string;
  agriwiseAnswer: string;
  color: string;
  accentRgb: string;
  icon: any;
  kpis: { label: string; value: string; detail: string }[];
  capabilities: string[];
  ctaLabel: string;
  ctaHref: string;
  mockUI: {
    panelTitle: string;
    primaryMetric: { label: string; value: string; status: string };
    feedItems: { time: string; text: string; tag: string }[];
  };
}

const STAKEHOLDERS_CONFIG: StakeholderDoor[] = [
  {
    id: "farmers",
    badge: "PRODUCERS & AGRONOMISTS",
    title: "Farmers",
    subtitle: "Understand your field.",
    tagline: "Actionable biophysical clarity without sensor fatigue or dashboard overwhelm.",
    coreQuestion: "“Should I irrigate today, wait for tomorrow's rain, or check my root zone?”",
    agriwiseAnswer:
      "AgriWise eliminates guesswork by resolving subsurface moisture, root stress, and atmospheric evapotranspiration into one unambiguous, counterfactually tested recommendation.",
    color: "#00E676",
    accentRgb: "0, 230, 118",
    icon: Sprout,
    kpis: [
      { label: "Water Savings", value: "28–34%", detail: "Over-irrigation avoided" },
      { label: "Input Efficiency", value: "+22%", detail: "Targeted nitrogen timing" },
      { label: "Yield Volatility", value: "-40%", detail: "Drought early warning" },
    ],
    capabilities: [
      "Subsurface soil moisture down to -120cm without manual probe digging",
      "Next Best Discriminating Action recommendation whenever symptoms appear",
      "72-hour rain ensemble vs. soil reservoir deficit trade-off matrix",
      "Multi-season plot memory tracking soil organic calibration year over year",
    ],
    ctaLabel: "Start With Your Parcels",
    ctaHref: "/auth/register",
    mockUI: {
      panelTitle: "PARCEL 04-NORTH · DAILY DECISION DISPATCH",
      primaryMetric: { label: "OPTIMAL IRRIGATION WINDOW", value: "TOMORROW 05:30 AM", status: "Pareto Optimal" },
      feedItems: [
        { time: "06:14", text: "Root absorption zone at -40cm holds 26.4% moisture (36h safety buffer remaining)", tag: "Subsurface" },
        { time: "08:00", text: "Rain ensemble ECMWF indicates 68% probability of 14mm rain at T+22h", tag: "Atmosphere" },
        { time: "09:30", text: "Recommendation: Hold irrigation pump. Re-evaluate after 18:00 rain pass.", tag: "Decision" },
      ],
    },
  },
  {
    id: "enterprises",
    badge: "AGRIBUSINESS & INDUSTRIAL FARMS",
    title: "Enterprises",
    subtitle: "Operate your production at scale.",
    tagline: "Industrial-scale execution across thousands of hectares, machinery fleets, and contract supply chains.",
    coreQuestion: "“Where is our operational yield risk concentrated across our 15,000 hectares?”",
    agriwiseAnswer:
      "AgriWise unifies fleet telemetry, crop phenology, and input economics into a real-time command center, continuously benchmarking production across every management zone.",
    color: "#00D9FF",
    accentRgb: "0, 217, 255",
    icon: Tractor,
    kpis: [
      { label: "Unified Parcels", value: "14,800 ha", detail: "Across 4 enterprise hubs" },
      { label: "Yield Trajectory", value: "98.4%", detail: "Harvest variance < 3.2%" },
      { label: "Fleet Optimization", value: "+19%", detail: "Spraying and harvest routing" },
    ],
    capabilities: [
      "Multi-basin portfolio aggregation with zone-level marginal yield curves",
      "Automated work-order dispatch tied directly to biophysical thresholds",
      "Cryptographically auditable ESG & carbon-nitrogen accounting ledger",
      "Forward harvest yield curves updated weekly for commodity hedging",
    ],
    ctaLabel: "Deploy Enterprise Fleet",
    ctaHref: "/demo",
    mockUI: {
      panelTitle: "ENTERPRISE COMMAND CENTER · REGIONAL CLUSTER EAST",
      primaryMetric: { label: "AGGREGATE HARVEST FORECAST", value: "84,200 MT ± 2.1%", status: "Confidence 96%" },
      feedItems: [
        { time: "10:15", text: "Plot 18B (Sector 3): Early nitrogen deficiency detected via Sentinel MSI red-edge shift", tag: "Fleet Alert" },
        { time: "11:20", text: "Variable-rate fertigation prescription generated and dispatched to John Deere Operations Center", tag: "Automated DAG" },
        { time: "12:05", text: "Supply chain delivery window for 42,000 MT durum wheat locked with mill grain elevator", tag: "Logistics" },
      ],
    },
  },
  {
    id: "cooperatives",
    badge: "REGIONAL ALLIANCES & AGRO-DEALERS",
    title: "Cooperatives",
    subtitle: "Coordinate your network.",
    tagline: "Synchronized harvest logistics, joint input purchasing, and regional biosecurity defense.",
    coreQuestion: "“How can we protect 650 member farms from regional pathogen vectors and coordinate harvest flow?”",
    agriwiseAnswer:
      "AgriWise aggregates anonymized field cubes across the valley, tracking disease diffusion vectors and optimizing regional silo intake schedules.",
    color: "#818CF8",
    accentRgb: "129, 140, 248",
    icon: Building2,
    kpis: [
      { label: "Member Parcels", value: "650 Farms", detail: "32,000 hectares coordinated" },
      { label: "Silo Wait Times", value: "-62%", detail: "Optimized intake queues" },
      { label: "Pathogen Interception", value: "5–7 Days", detail: "Vector spread early detection" },
    ],
    capabilities: [
      "Regional epidemiological tracking for fungal spores, locusts, and rust pathogens",
      "Fair water and quota allocation across shared irrigation canal networks",
      "Collective input bulk ordering triggered by soil deficiency clustering",
      "Benchmarked agronomist advisory workflows with provenance tracing",
    ],
    ctaLabel: "Coordinate Cooperative",
    ctaHref: "/demo",
    mockUI: {
      panelTitle: "COOPERATIVE VALLEY ALLIANCE · BIOSECURITY & INTAKE",
      primaryMetric: { label: "VECTOR INTERCEPTION INDEX", value: "94.8% CONTAINED", status: "Low Spread Risk" },
      feedItems: [
        { time: "07:45", text: "Fungal rust spore vector modeled from southern border parcels; 18 member farms alerted", tag: "Pathogen Vector" },
        { time: "09:12", text: "Preventative bio-fungicide targeted application window set for 48h before humidity spike", tag: "Network Action" },
        { time: "11:30", text: "Harvest grain intake schedule auto-staggered: 240 trucks queued with zero demurrage", tag: "Silo Logistics" },
      ],
    },
  },
  {
    id: "institutions",
    badge: "GOVERNMENTS & FINANCIAL ENTITIES",
    title: "Institutions & Sovereigns",
    subtitle: "Govern the agricultural system.",
    tagline: "National food security balance sheets, water basin management, and sovereign risk underwriting.",
    coreQuestion: "“What will our national grain balance look like in 5 months, and which aquifers are depleting?”",
    agriwiseAnswer:
      "AgriWise scales the physical world model across entire river basins and nations, enabling sovereign authorities to underwrite droughts, manage strategic reserves, and guarantee food security.",
    color: "#F59E0B",
    accentRgb: "245, 158, 11",
    icon: Landmark,
    kpis: [
      { label: "National Coverage", value: "4.2M ha", detail: "Whole-territory observation" },
      { label: "Reserve Prediction", value: "4 Months", detail: "Advance food balance horizon" },
      { label: "Parametric Trust", value: "Zero Claims Fraud", detail: "Sensor-verified payouts" },
    ],
    capabilities: [
      "National food balance sheet simulation under geopolitical and climate stress",
      "Basin-wide groundwater withdrawal velocity and aquifer recharge tracking",
      "Parametric drought insurance underwriting with zero field claims inspection latency",
      "Air-gapped and sovereign cloud deployment ensuring national data sovereignty",
    ],
    ctaLabel: "Explore Sovereign Platform",
    ctaHref: "/demo",
    mockUI: {
      panelTitle: "SOVEREIGN AGRICULTURAL OVERSIGHT · NATIONAL BALANCE SHEET",
      primaryMetric: { label: "STRATEGIC GRAIN RESERVE BUFFER", value: "118 DAYS SECURE", status: "Sovereign Target Exceeded" },
      feedItems: [
        { time: "05:00", text: "National durum wheat harvest yield projected at 3.12M MT (±2.4%) across all provinces", tag: "Food Balance" },
        { time: "07:30", text: "Chéliff Aquifer Overdraft velocity reduced by 14% following precision irrigation deployment", tag: "Aquifer Governance" },
        { time: "08:45", text: "Parametric drought insurance trigger verified for 42,000 hectares: Payouts queued automatically", tag: "Parametric Risk" },
      ],
    },
  },
];

export default function StakeholderPlatformsSection() {
  const { t } = useLanguage();
  const [activeTabId, setActiveTabId] = useState<string>("farmers");

  const stakeholders = STAKEHOLDERS_CONFIG.map((cfg, idx) => {
    const loc = t.platforms.doors[idx] || {};
    return {
      ...cfg,
      badge: loc.badge || cfg.badge,
      title: loc.title || cfg.title,
      subtitle: loc.subtitle || cfg.subtitle,
      tagline: loc.tagline || cfg.tagline,
      coreQuestion: loc.coreQuestion || cfg.coreQuestion,
      agriwiseAnswer: loc.agriwiseAnswer || cfg.agriwiseAnswer,
      kpis: loc.kpis || cfg.kpis,
      capabilities: loc.capabilities || cfg.capabilities,
      ctaLabel: loc.ctaLabel || cfg.ctaLabel,
      ctaHref: loc.ctaHref || cfg.ctaHref,
      mockUI: loc.mockUI
        ? {
            panelTitle: loc.mockUI.panelTitle || cfg.mockUI.panelTitle,
            primaryMetric: loc.mockUI.primaryMetric || cfg.mockUI.primaryMetric,
            feedItems: loc.mockUI.feedItems || cfg.mockUI.feedItems,
          }
        : cfg.mockUI,
    };
  });

  const activeStakeholder = stakeholders.find((s) => s.id === activeTabId) || stakeholders[0];
  const ActiveIcon = activeStakeholder.icon;

  return (
    <section
      id="platforms"
      className="deep-tech-lattice"
      style={{
        position: "relative",
        background: "#05070B",
        padding: "130px 24px 120px",
        overflow: "hidden",
        borderTop: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        {/* Section Header */}
        <div style={{ textAlign: "center", maxWidth: "860px", margin: "0 auto 60px" }}>
          <div className="fiducial-badge" style={{ marginBottom: "20px" }}>
            <span className="pulse-dot" />
            <span>{t.platforms.sectionBadge}</span>
          </div>

          <h2
            className="apple-section-headline font-heading"
            style={{
              fontSize: "clamp(2rem, 4.5vw, 3.4rem)",
              fontWeight: 800,
              lineHeight: 1.15,
              letterSpacing: "-0.03em",
              color: "#FFFFFF",
              margin: "0 0 16px",
            }}
          >
            {t.platforms.title}
          </h2>

          <p className="apple-section-subtitle" style={{ maxWidth: "760px", margin: "0 auto", fontSize: "16px", color: "#cbd5e1" }}>
            {t.platforms.subtitle}
          </p>
        </div>

        {/* 4 Door Tab Selectors */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "12px",
            marginBottom: "36px",
          }}
          className="stakeholder-tab-grid"
        >
          {stakeholders.map((item) => {
            const isSelected = item.id === activeTabId;
            const ItemIcon = item.icon;

            return (
              <button
                key={item.id}
                onClick={() => setActiveTabId(item.id)}
                className="hover-lift transition-smooth"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "16px 20px",
                  borderRadius: "16px",
                  background: isSelected
                    ? `linear-gradient(180deg, rgba(${item.accentRgb}, 0.18) 0%, rgba(6, 18, 12, 0.95) 100%)`
                    : "rgba(6, 14, 10, 0.6)",
                  border: isSelected
                    ? `1px solid rgba(${item.accentRgb}, 0.6)`
                    : "1px solid rgba(255, 255, 255, 0.08)",
                  cursor: "pointer",
                  textAlign: "left",
                  boxShadow: isSelected
                    ? `0 10px 30px -10px rgba(${item.accentRgb}, 0.35)`
                    : "none",
                }}
              >
                <div
                  style={{
                    width: "40px",
                    height: "40px",
                    borderRadius: "10px",
                    background: isSelected
                      ? `rgba(${item.accentRgb}, 0.25)`
                      : "rgba(255, 255, 255, 0.04)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: isSelected ? item.color : "#94A3B8",
                    flexShrink: 0,
                  }}
                >
                  <ItemIcon size={20} />
                </div>
                <div>
                  <div
                    style={{
                      fontSize: "10px",
                      fontFamily: "var(--font-mono, monospace)",
                      letterSpacing: "0.1em",
                      color: isSelected ? item.color : "#64748B",
                      textTransform: "uppercase",
                    }}
                  >
                    {item.badge}
                  </div>
                  <div
                    style={{
                      fontSize: "16px",
                      fontWeight: 700,
                      color: isSelected ? "#FFFFFF" : "#CBD5E1",
                    }}
                  >
                    {item.title}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Stakeholder Platform Detailed Panel */}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={activeTabId}
            initial={{ opacity: 0, y: 16, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -16, filter: "blur(4px)" }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            style={{
              background: "rgba(10, 14, 23, 0.85)",
              backdropFilter: "blur(24px)",
              borderRadius: "24px",
              border: `1px solid rgba(${activeStakeholder.accentRgb}, 0.3)`,
              padding: "40px",
              boxShadow: `0 30px 80px -20px rgba(${activeStakeholder.accentRgb}, 0.2)`,
              display: "grid",
              gridTemplateColumns: "1.1fr 1fr",
              gap: "40px",
              alignItems: "stretch",
            }}
            className="stakeholder-detail-grid dribbble-glass-card transition-smooth"
          >
          {/* Left Column: Mission, Question, Answer, KPIs, Capabilities */}
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
            <div>
              {/* Mission Badge */}
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "4px 12px",
                  borderRadius: "6px",
                  background: `rgba(${activeStakeholder.accentRgb}, 0.15)`,
                  border: `1px solid rgba(${activeStakeholder.accentRgb}, 0.3)`,
                  fontSize: "11px",
                  fontFamily: "var(--font-mono, monospace)",
                  color: activeStakeholder.color,
                  marginBottom: "16px",
                }}
              >
                <ActiveIcon size={13} />
                <span>{activeStakeholder.subtitle}</span>
              </div>

              <h3
                className="font-heading"
                style={{
                  fontSize: "clamp(26px, 2.8vw, 36px)",
                  fontWeight: 700,
                  color: "#FFFFFF",
                  letterSpacing: "-0.02em",
                  marginBottom: "14px",
                  lineHeight: 1.2,
                }}
              >
                {activeStakeholder.tagline}
              </h3>

              {/* The Core Question & Answer Box */}
              <div
                style={{
                  background: "rgba(0, 0, 0, 0.4)",
                  borderRadius: "14px",
                  border: "1px solid rgba(255, 255, 255, 0.07)",
                  padding: "20px",
                  marginBottom: "28px",
                }}
              >
                <div
                  style={{
                    fontSize: "14px",
                    fontWeight: 600,
                    fontStyle: "italic",
                    color: "#F1F5F9",
                    marginBottom: "10px",
                  }}
                >
                  {activeStakeholder.coreQuestion}
                </div>
                <div style={{ fontSize: "14px", color: "#94A3B8", lineHeight: 1.6 }}>
                  {activeStakeholder.agriwiseAnswer}
                </div>
              </div>

              {/* 3 Impact KPIs */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: "14px",
                  marginBottom: "28px",
                }}
              >
                {activeStakeholder.kpis.map((kpi, idx) => (
                  <div
                    key={idx}
                    className="hover-lift transition-smooth"
                    style={{
                      background: "rgba(255, 255, 255, 0.02)",
                      borderRadius: "12px",
                      border: "1px solid rgba(255, 255, 255, 0.06)",
                      padding: "14px 16px",
                    }}
                  >
                    <div
                      className="font-heading"
                      style={{
                        fontSize: "24px",
                        fontWeight: 800,
                        color: activeStakeholder.color,
                        letterSpacing: "-0.02em",
                      }}
                    >
                      {kpi.value}
                    </div>
                    <div style={{ fontSize: "12px", fontWeight: 600, color: "#E2E8F0", marginTop: "2px" }}>
                      {kpi.label}
                    </div>
                    <div style={{ fontSize: "11px", color: "#64748B", marginTop: "2px" }}>
                      {kpi.detail}
                    </div>
                  </div>
                ))}
              </div>

              {/* Capabilities List */}
              <div style={{ marginBottom: "32px" }}>
                <div
                  style={{
                    fontSize: "11px",
                    textTransform: "uppercase",
                    letterSpacing: "0.1em",
                    color: "#64748B",
                    marginBottom: "12px",
                    fontFamily: "var(--font-mono, monospace)",
                  }}
                >
                  Key Operational Capabilities
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {activeStakeholder.capabilities.map((cap, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                      <CheckCircle2
                        size={16}
                        style={{ color: activeStakeholder.color, flexShrink: 0, marginTop: "2px" }}
                      />
                      <span style={{ fontSize: "13px", color: "#CBD5E1", lineHeight: 1.5 }}>{cap}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Gateway CTA */}
            <div>
              <Link
                href={activeStakeholder.ctaHref}
                className="hover-lift transition-smooth"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "14px 28px",
                  borderRadius: "12px",
                  background: activeStakeholder.color,
                  color: "#05070B",
                  fontWeight: 700,
                  fontSize: "14px",
                  letterSpacing: "0.02em",
                  textDecoration: "none",
                  boxShadow: `0 10px 30px -8px rgba(${activeStakeholder.accentRgb}, 0.6)`,
                }}
              >
                <span>{activeStakeholder.ctaLabel}</span>
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>

          {/* Right Column: Live Operational Console Mockup */}
          <div
            className="hover-lift transition-smooth dribbble-glass-card"
            style={{
              background: "rgba(6, 10, 18, 0.95)",
              borderRadius: "18px",
              border: `1px solid rgba(${activeStakeholder.accentRgb}, 0.25)`,
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxShadow: `inset 0 1px 0 rgba(255,255,255,0.06), 0 20px 50px -15px rgba(${activeStakeholder.accentRgb}, 0.15)`,
            }}
          >
            <div>
              {/* Mock Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  paddingBottom: "16px",
                  borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                  marginBottom: "20px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: activeStakeholder.color,
                      boxShadow: `0 0 10px ${activeStakeholder.color}`,
                    }}
                  />
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      color: "#94A3B8",
                      fontFamily: "var(--font-mono, monospace)",
                    }}
                  >
                    {activeStakeholder.mockUI.panelTitle}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: "11px",
                    fontFamily: "var(--font-mono, monospace)",
                    color: "#64748B",
                  }}
                >
                  LIVE SYSTEM FEED
                </span>
              </div>

              {/* Primary Metric Banner */}
              <div
                style={{
                  background: `linear-gradient(135deg, rgba(${activeStakeholder.accentRgb}, 0.15) 0%, rgba(255,255,255,0.02) 100%)`,
                  borderRadius: "14px",
                  border: `1px solid rgba(${activeStakeholder.accentRgb}, 0.3)`,
                  padding: "20px",
                  marginBottom: "24px",
                }}
              >
                <div
                  style={{
                    fontSize: "10px",
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    color: "#94A3B8",
                    fontFamily: "var(--font-mono, monospace)",
                    marginBottom: "6px",
                  }}
                >
                  {activeStakeholder.mockUI.primaryMetric.label}
                </div>
                <div
                  className="font-heading"
                  style={{
                    fontSize: "28px",
                    fontWeight: 800,
                    color: "#FFFFFF",
                    letterSpacing: "-0.02em",
                  }}
                >
                  {activeStakeholder.mockUI.primaryMetric.value}
                </div>
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    marginTop: "8px",
                    fontSize: "11px",
                    color: activeStakeholder.color,
                    fontWeight: 600,
                  }}
                >
                  <ShieldCheck size={13} />
                  <span>{activeStakeholder.mockUI.primaryMetric.status}</span>
                </div>
              </div>

              {/* Operational Dispatch Feed */}
              <div>
                <div
                  style={{
                    fontSize: "11px",
                    textTransform: "uppercase",
                    letterSpacing: "0.1em",
                    color: "#64748B",
                    marginBottom: "12px",
                    fontFamily: "var(--font-mono, monospace)",
                  }}
                >
                  Real-Time Event Stream
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {activeStakeholder.mockUI.feedItems.map((item, idx) => (
                    <div
                      key={idx}
                      className="hover-lift transition-smooth"
                      style={{
                        background: "rgba(255, 255, 255, 0.02)",
                        borderRadius: "10px",
                        border: "1px solid rgba(255, 255, 255, 0.04)",
                        padding: "12px 14px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: "4px",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "10px",
                            fontFamily: "var(--font-mono, monospace)",
                            color: "#64748B",
                          }}
                        >
                          T-{item.time}
                        </span>
                        <span
                          style={{
                            fontSize: "10px",
                            fontFamily: "var(--font-mono, monospace)",
                            color: activeStakeholder.color,
                            background: `rgba(${activeStakeholder.accentRgb}, 0.1)`,
                            padding: "2px 8px",
                            borderRadius: "4px",
                          }}
                        >
                          {item.tag}
                        </span>
                      </div>
                      <div style={{ fontSize: "13px", color: "#CBD5E1", lineHeight: 1.4 }}>
                        {item.text}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Bottom Status Line */}
            <div
              style={{
                marginTop: "24px",
                paddingTop: "14px",
                borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: "11px",
                color: "#64748B",
                fontFamily: "var(--font-mono, monospace)",
              }}
            >
              <span>DISPATCH ENGINE: ONLINE</span>
              <span style={{ color: "#94A3B8" }}>AES-256 ENCRYPTED</span>
            </div>
          </div>
        </motion.div>
        </AnimatePresence>
      </div>
    </section>
  );
}
