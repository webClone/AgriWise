"use client";

import React, { useState } from "react";
import Image from "next/image";
import {
  Globe2,
  Landmark,
  Shield,
  Droplets,
  Wheat,
  Scale,
  Lock,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Activity,
  CheckCircle2,
  Maximize2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/* ═══ MODULE 03: Scale & Sovereign Intelligence Carousel ═══
   Combines:
   1. Fractal Scale: Microzone to River Basin
   2. Sovereign Governance: National Food Balance & Aquifer Overdraft
   ════════════════════════════════════════════════════════════ */

export default function ScaleSovereignCarousel() {
  const { t, dir } = useLanguage();
  const [activeSlide, setActiveSlide] = useState<number>(0);

  // Slide 1: Scale Tier
  const [activeTierIndex, setActiveTierIndex] = useState<number>(2);
  const [tierMediaMode, setTierMediaMode] = useState<"image" | "video">("video");

  // Slide 2: Shock simulation
  const [isSimulatingShock, setIsSimulatingShock] = useState<boolean>(false);
  const [activeSovereignPillar, setActiveSovereignPillar] = useState<number>(0);

  const SLIDES = [
    {
      id: "scale",
      num: t.scale.slides.scale.num,
      badge: t.scale.slides.scale.badge,
      title: t.scale.slides.scale.title,
      subtitle: t.scale.slides.scale.subtitle,
    },
    {
      id: "national",
      num: t.scale.slides.national.num,
      badge: t.scale.slides.national.badge,
      title: t.scale.slides.national.title,
      subtitle: t.scale.slides.national.subtitle,
    },
  ];

  const tierMediaAssets = [
    {
      image: "/images/deeptech/vadose-root-zone.jpg",
      video: "/videos/crop-growth-timelapse.webm",
    },
    {
      image: "/images/deeptech/living-field.jpg",
      video: "/videos/drone-field-scan.webm",
    },
    {
      image: "/images/deeptech/connected-farm.jpg",
      video: "/videos/autonomous-harvest.webm",
    },
    {
      image: "/images/deeptech/watershed-basin.jpg",
      video: "/videos/irrigation-water-flux.webm",
    },
    {
      image: "/images/deeptech/planetary-belt.jpg",
      video: "/videos/drone-field-scan.webm",
    },
  ];

  const TIERS = t.scale.tiers.map((tier, idx) => ({
    ...tier,
    image: tierMediaAssets[idx]?.image || "/images/deeptech/living-field.jpg",
    video: tierMediaAssets[idx]?.video || "/videos/drone-field-scan.webm",
  }));

  const sovereignColors = ["#00E676", "#00D9FF", "#F59E0B", "#818CF8"];

  const SOVEREIGN_CARDS = t.scale.sovereignCards.map((c, i) => ({
    ...c,
    color: sovereignColors[i] || "#00E676",
    metric: isSimulatingShock ? c.metricShock : c.metricNormal,
    impact: isSimulatingShock ? c.impactShock : c.impactNormal,
  }));

  const currentTier = TIERS[activeTierIndex];

  return (
    <section
      id="scale"
      className="deep-tech-lattice"
      style={{
        position: "relative",
        background: "#03060A",
        padding: "110px 24px 100px",
        overflow: "hidden",
        borderTop: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        {/* Carousel Header & Slide Tabs */}
        <div style={{ textAlign: "center", maxWidth: "880px", margin: "0 auto 36px" }}>
          <div className="fiducial-badge" style={{ marginBottom: "20px" }}>
            <span className="pulse-dot" />
            <span>{t.scale.sectionBadge}</span>
          </div>

          <h2
            className="apple-section-headline font-heading"
            style={{
              fontSize: "clamp(2rem, 4.5vw, 3.4rem)",
              fontWeight: 800,
              lineHeight: 1.1,
              letterSpacing: "-0.03em",
              color: "#FFFFFF",
              margin: "0 0 14px",
            }}
          >
            {SLIDES[activeSlide].title}
          </h2>

          <p className="apple-section-subtitle" style={{ maxWidth: "720px", margin: "0 auto 28px", fontSize: "16px", color: "#cbd5e1" }}>
            {SLIDES[activeSlide].subtitle}
          </p>

          {/* Carousel Segmented Controls */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px",
              borderRadius: "14px",
              background: "rgba(6, 18, 12, 0.85)",
              border: "1px solid rgba(34, 197, 94, 0.25)",
              backdropFilter: "blur(18px)",
              boxShadow: "0 8px 32px rgba(0, 0, 0, 0.5)",
            }}
          >
            {SLIDES.map((s, idx) => (
              <button
                key={s.id}
                onClick={() => setActiveSlide(idx)}
                className="hover-lift transition-smooth"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "9px 20px",
                  borderRadius: "10px",
                  background: activeSlide === idx ? "rgba(34, 197, 94, 0.22)" : "transparent",
                  border: activeSlide === idx ? "1px solid #22c55e" : "1px solid transparent",
                  color: activeSlide === idx ? "#22c55e" : "#94A3B8",
                  fontSize: "12px",
                  fontWeight: 700,
                  fontFamily: "var(--font-mono)",
                  cursor: "pointer",
                }}
              >
                <span style={{ opacity: 0.6 }}>{s.num}.</span>
                <span>{s.badge}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Carousel Slide Stage */}
        <div
          className="dribbble-glass-card"
          style={{
            padding: "36px",
            borderRadius: "22px",
            minHeight: "520px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            overflow: "hidden",
          }}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeSlide}
              initial={{ opacity: 0, y: 16, filter: "blur(4px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -16, filter: "blur(4px)" }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              {/* SLIDE 1: Fractal Scale Progression */}
              {activeSlide === 0 && (
            <div>
              {/* Tier Selector Bar */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(5, 1fr)",
                  gap: "10px",
                  marginBottom: "28px",
                }}
                className="scale-bar-grid"
              >
                {TIERS.map((tierItem, idx) => {
                  const isSelected = idx === activeTierIndex;
                  return (
                    <button
                      key={tierItem.name}
                      onClick={() => setActiveTierIndex(idx)}
                      className="hover-lift transition-smooth"
                      style={{
                        background: isSelected ? "rgba(34, 197, 94, 0.16)" : "rgba(255, 255, 255, 0.03)",
                        border: isSelected ? "1px solid #22c55e" : "1px solid rgba(255, 255, 255, 0.08)",
                        borderRadius: "12px",
                        padding: "12px 14px",
                        textAlign: "left",
                        cursor: "pointer",
                        boxShadow: isSelected ? "0 0 20px rgba(34, 197, 94, 0.25)" : "none",
                      }}
                    >
                      <div style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: isSelected ? "#22c55e" : "#64748B", fontWeight: 700 }}>
                        TIER 0{idx + 1}
                      </div>
                      <div
                        className="font-heading"
                        style={{ fontSize: "13px", fontWeight: 700, color: isSelected ? "#FFFFFF" : "#CBD5E1", marginTop: "2px" }}
                      >
                        {t.scale.tierNav[idx] || tierItem.name.split(" ")[0]}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Active Tier Showcase */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.1fr 1fr",
                  gap: "32px",
                  alignItems: "center",
                }}
                className="carousel-detail-grid"
              >
                <div>
                  <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#00E676", textTransform: "uppercase", marginBottom: "8px" }}>
                    {currentTier.subtitle} · {currentTier.metric}
                  </div>
                  <h3 style={{ fontSize: "28px", fontWeight: 700, color: "#FFFFFF", marginBottom: "12px" }}>
                    {currentTier.headline}
                  </h3>
                  <p style={{ fontSize: "15px", color: "#CBD5E1", lineHeight: 1.6, marginBottom: "20px" }}>
                    {currentTier.description}
                  </p>
                  <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", background: "rgba(255,255,255,0.03)", padding: "10px 16px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <CheckCircle2 size={15} style={{ color: "#00E676" }} />
                    <span style={{ fontSize: "13px", color: "#E2E8F0" }}>{t.scale.biophysicalGuarantee}</span>
                  </div>
                </div>

                {/* High-Res Photographic Asset or Live Video Stream */}
                <div>
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "6px", marginBottom: "8px" }}>
                    <button
                      onClick={() => setTierMediaMode("video")}
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        background: tierMediaMode === "video" ? "rgba(0, 230, 118, 0.2)" : "rgba(255, 255, 255, 0.04)",
                        border: tierMediaMode === "video" ? "1px solid #00E676" : "1px solid rgba(255, 255, 255, 0.08)",
                        color: tierMediaMode === "video" ? "#00E676" : "#94A3B8",
                        fontSize: "11px",
                        fontFamily: "var(--font-mono)",
                        cursor: "pointer",
                      }}
                    >
                      {t.scale.liveStreamBtn} ({currentTier.videoBadge})
                    </button>
                    <button
                      onClick={() => setTierMediaMode("image")}
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        background: tierMediaMode === "image" ? "rgba(0, 217, 255, 0.2)" : "rgba(255, 255, 255, 0.04)",
                        border: tierMediaMode === "image" ? "1px solid #00D9FF" : "1px solid rgba(255, 255, 255, 0.08)",
                        color: tierMediaMode === "image" ? "#00D9FF" : "#94A3B8",
                        fontSize: "11px",
                        fontFamily: "var(--font-mono)",
                        cursor: "pointer",
                      }}
                    >
                      {t.scale.orthoPhotoBtn}
                    </button>
                  </div>

                  <div
                    style={{
                      position: "relative",
                      width: "100%",
                      height: "300px",
                      borderRadius: "14px",
                      overflow: "hidden",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                    }}
                  >
                    {tierMediaMode === "video" && currentTier.video ? (
                      <video
                        key={currentTier.video}
                        src={currentTier.video}
                        autoPlay
                        loop
                        muted
                        playsInline
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                    ) : (
                      <img
                        src={currentTier.image}
                        alt={currentTier.headline}
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                    )}

                    <div
                      style={{
                        position: "absolute",
                        bottom: "12px",
                        right: "12px",
                        background: "rgba(5, 7, 11, 0.85)",
                        backdropFilter: "blur(10px)",
                        border: "1px solid rgba(0, 230, 118, 0.3)",
                        borderRadius: "6px",
                        padding: "4px 10px",
                        fontSize: "10px",
                        fontFamily: "var(--font-mono)",
                        color: "#00E676",
                      }}
                    >
                      {tierMediaMode === "video" ? `${t.scale.liveStreamTag}: ${currentTier.videoBadge}` : `${t.scale.scaleLevelTag}: ${currentTier.metric}`}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SLIDE 2: Sovereign & National Governance */}
          {activeSlide === 1 && (
            <div>
              {/* Sovereign Command Top Bar */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "24px",
                  paddingBottom: "16px",
                  borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                  flexWrap: "wrap",
                  gap: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", fontFamily: "var(--font-mono)", color: "#00E676" }}>
                  <span className="pulse-dot" style={{ width: "6px", height: "6px" }} />
                  <span>{t.scale.oversightActive}</span>
                </div>

                <button
                  onClick={() => setIsSimulatingShock(!isSimulatingShock)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "6px 14px",
                    borderRadius: "8px",
                    background: isSimulatingShock ? "rgba(239, 68, 68, 0.2)" : "rgba(255, 255, 255, 0.05)",
                    border: isSimulatingShock ? "1px solid #ef4444" : "1px solid rgba(255, 255, 255, 0.1)",
                    color: isSimulatingShock ? "#f87171" : "#E2E8F0",
                    fontSize: "11px",
                    fontFamily: "var(--font-mono)",
                    cursor: "pointer",
                  }}
                >
                  <AlertTriangle size={13} style={{ color: isSimulatingShock ? "#f87171" : "#fbbf24" }} />
                  <span>{isSimulatingShock ? t.scale.simulatingDroughtBtn : t.scale.simulateDroughtBtn}</span>
                </button>
              </div>

              {/* Emergency Scenario Banner */}
              {isSimulatingShock && (
                <div
                  style={{
                    marginBottom: "20px",
                    padding: "14px 20px",
                    borderRadius: "10px",
                    background: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.4)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: "10px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <AlertTriangle size={18} style={{ color: "#f87171", flexShrink: 0 }} />
                    <span style={{ fontSize: "13px", color: "#fecaca" }}>
                      <strong style={{ color: "#FFFFFF" }}>{t.scale.emergencyBannerTitle}</strong> {t.scale.emergencyBannerText}
                    </span>
                  </div>
                  <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#f87171", fontWeight: 700 }}>
                    {t.scale.stressTestBadge}
                  </span>
                </div>
              )}

              {/* 4 Sovereign Strategic Cards */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: "14px",
                }}
                className="sovereign-grid"
              >
                {SOVEREIGN_CARDS.map((c, i) => {
                  const cardColor = isSimulatingShock && (i === 0 || i === 1) ? "#f87171" : c.color;

                  return (
                    <div
                      key={c.title}
                      style={{
                        background: isSimulatingShock && (i === 0 || i === 1) ? "rgba(239, 68, 68, 0.08)" : "rgba(5, 8, 15, 0.85)",
                        borderRadius: "14px",
                        border: `1px solid ${cardColor}45`,
                        padding: "20px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        transition: "all 0.3s ease",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: cardColor, fontWeight: 700, marginBottom: "4px" }}>
                          {c.tag}
                        </div>
                        <div style={{ fontSize: "16px", fontWeight: 700, color: "#FFFFFF", marginBottom: "10px" }}>
                          {c.title}
                        </div>
                        <div style={{ fontSize: "22px", fontWeight: 800, color: cardColor, fontFamily: "var(--font-mono)", marginBottom: "4px" }}>
                          {c.metric}
                        </div>
                        <div style={{ fontSize: "12px", color: cardColor, fontWeight: 600, marginBottom: "12px" }}>
                          {c.impact}
                        </div>
                      </div>
                      <p style={{ fontSize: "12px", color: "#94A3B8", lineHeight: 1.5, margin: 0 }}>
                        {c.desc}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          </motion.div>
          </AnimatePresence>

          {/* Carousel Footer Arrows & Dots */}
          <div
            style={{
              marginTop: "28px",
              paddingTop: "20px",
              borderTop: "1px solid rgba(255, 255, 255, 0.06)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {SLIDES.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setActiveSlide(i)}
                  style={{
                    width: activeSlide === i ? "24px" : "8px",
                    height: "6px",
                    borderRadius: "3px",
                    background: activeSlide === i ? "#00E676" : "rgba(255, 255, 255, 0.2)",
                    border: "none",
                    cursor: "pointer",
                    transition: "all 0.25s ease",
                  }}
                  aria-label={`Slide ${i + 1}`}
                />
              ))}
            </div>

            <div style={{ display: "flex", gap: "8px" }}>
              <button
                onClick={() => setActiveSlide((prev) => (prev > 0 ? prev - 1 : SLIDES.length - 1))}
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "8px",
                  background: "rgba(255, 255, 255, 0.04)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  color: "#FFFFFF",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
                aria-label="Previous Slide"
              >
                <ChevronLeft size={16} className="rtl-mirror" />
              </button>
              <button
                onClick={() => setActiveSlide((prev) => (prev < SLIDES.length - 1 ? prev + 1 : 0))}
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "8px",
                  background: "rgba(255, 255, 255, 0.04)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  color: "#FFFFFF",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
                aria-label="Next Slide"
              >
                <ChevronRight size={16} className="rtl-mirror" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
