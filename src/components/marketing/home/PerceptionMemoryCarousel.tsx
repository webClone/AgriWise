"use client";

import React, { useState } from "react";
import Image from "next/image";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/* ═══ MODULE 01: Perception & Memory Carousel ═══
   Combines:
   1. The Closed Cognitive Loop (Observe → Understand → Simulate → Decide → Learn)
   2. Field Memory & Multi-Season Worldline (2023–2026 Prior Calibration)
   3. Reality Split Reconstruction (Surface Orthomosaic vs Subsurface Vadose Core)
   ═════════════════════════════════════════════════ */

export default function PerceptionMemoryCarousel() {
  const { t, isRtl } = useLanguage();
  const p = t.perception;

  const [activeSlide, setActiveSlide] = useState<number>(0);

  // Slide 1: Loop stages
  const [activeStageIndex, setActiveStageIndex] = useState<number>(1);

  // Slide 2: Season index
  const [activeSeasonIndex, setActiveSeasonIndex] = useState<number>(3);

  // Slide 3: Split slider
  const [sliderPos, setSliderPos] = useState<number>(50);
  const [activePerspective, setActivePerspective] = useState<
    "compare" | "surface" | "subsurface" | "drone_video" | "growth_video" | "irrigation_video"
  >("compare");

  const SLIDES = [
    {
      id: "loop",
      num: "01",
      badge: p.slides.loop.badge,
      title: p.slides.loop.title,
      subtitle: p.slides.loop.subtitle,
    },
    {
      id: "memory",
      num: "02",
      badge: p.slides.memory.badge,
      title: p.slides.memory.title,
      subtitle: p.slides.memory.subtitle,
    },
    {
      id: "reality",
      num: "03",
      badge: p.slides.reality.badge,
      title: p.slides.reality.title,
      subtitle: p.slides.reality.subtitle,
    },
  ];

  // Loop data with distinct color coding
  const STAGE_COLORS = ["#00D9FF", "#00E676", "#818CF8", "#F59E0B", "#E879F9"];
  const LOOP_STAGES = p.stages.map((stage, idx) => ({
    ...stage,
    color: STAGE_COLORS[idx] || "#00E676",
  }));

  // Worldline seasons
  const SEASONS = p.seasonsList;


  return (
    <section
      id="perception"
      className="deep-tech-lattice"
      style={{
        position: "relative",
        background: "#05070B",
        padding: "110px 24px 100px",
        overflow: "hidden",
        borderTop: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      {/* Background glow */}
      <div
        style={{
          position: "absolute",
          top: "10%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "900px",
          height: "500px",
          background: "radial-gradient(circle, rgba(0, 230, 118, 0.07) 0%, rgba(0, 217, 255, 0.04) 50%, transparent 75%)",
          filter: "blur(120px)",
          pointerEvents: "none",
        }}
      />

      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        {/* Carousel Header & Slide Tabs */}
        <div style={{ textAlign: "center", maxWidth: "880px", margin: "0 auto 36px" }}>
          <div className="fiducial-badge" style={{ marginBottom: "20px" }}>
            <span className="pulse-dot" />
            <span>{p.sectionBadge}</span>
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
              {/* SLIDE 1: The Closed Cognitive Loop */}
              {activeSlide === 0 && (
            <div>
              {/* Step Navigation Bar */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(5, 1fr)",
                  gap: "10px",
                  marginBottom: "32px",
                }}
                className="loop-bar-grid"
              >
                {LOOP_STAGES.map((s, idx) => {
                  const isSelected = idx === activeStageIndex;
                  return (
                    <button
                      key={s.step}
                      onClick={() => setActiveStageIndex(idx)}
                      className="hover-lift transition-smooth"
                      style={{
                        background: isSelected ? "rgba(34, 197, 94, 0.16)" : "rgba(255, 255, 255, 0.03)",
                        border: isSelected ? `1px solid ${s.color}` : "1px solid rgba(255, 255, 255, 0.08)",
                        borderRadius: "12px",
                        padding: "14px 12px",
                        textAlign: isRtl ? "right" : "left",
                        cursor: "pointer",
                        boxShadow: isSelected ? `0 0 20px ${s.color}25` : "none",
                      }}
                    >
                      <div style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: isSelected ? s.color : "#64748B", fontWeight: 700 }}>
                        {p.stageLabel} {s.step}
                      </div>
                      <div
                        className="font-heading"
                        style={{ fontSize: "14px", fontWeight: 700, color: isSelected ? "#FFFFFF" : "#CBD5E1", marginTop: "2px" }}
                      >
                        {s.name}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Active Stage Deep-Dive */}
              {(() => {
                const stage = LOOP_STAGES[activeStageIndex];
                return (
                  <div
                    style={{
                      background: "rgba(5, 8, 15, 0.8)",
                      borderRadius: "16px",
                      border: `1px solid ${stage.color}40`,
                      padding: "32px",
                      display: "grid",
                      gridTemplateColumns: "1.2fr 1fr",
                      gap: "32px",
                      alignItems: "center",
                    }}
                    className="carousel-detail-grid"
                  >
                    <div>
                      <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", color: stage.color, fontSize: "11px", fontFamily: "var(--font-mono)", marginBottom: "12px" }}>
                        <span className="pulse-dot" style={{ background: stage.color }} />
                        <span>{p.stageLabel} {stage.step} / 05</span>
                      </div>
                      <h3 style={{ fontSize: "28px", fontWeight: 700, color: "#FFFFFF", marginBottom: "8px" }}>
                        {stage.name}: {stage.tagline}
                      </h3>
                      <p style={{ fontSize: "15px", color: "#CBD5E1", lineHeight: 1.6, marginBottom: "20px" }}>
                        {stage.detail}
                      </p>
                      <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", background: "rgba(255,255,255,0.03)", padding: "8px 16px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.08)" }}>
                        <CheckCircle2 size={15} style={{ color: stage.color }} />
                        <span style={{ fontSize: "13px", color: "#F1F5F9", fontFamily: "var(--font-mono)" }}>
                          {p.targetMetric}: {stage.metric}
                        </span>
                      </div>
                    </div>

                    <div
                      style={{
                        background: "rgba(0,0,0,0.4)",
                        borderRadius: "14px",
                        border: "1px solid rgba(255,255,255,0.06)",
                        padding: "24px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "14px",
                      }}
                    >
                      <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#64748B", textTransform: "uppercase" }}>
                        {p.closedGuarantee}
                      </div>
                      <div style={{ fontSize: "14px", color: "#E2E8F0", lineHeight: 1.5 }}>
                        {p.closedGuaranteeText}
                      </div>
                      <div style={{ fontSize: "12px", color: stage.color, fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                        Continuous Calibration Loop Active
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* SLIDE 2: Field Memory & Multi-Season Worldline */}
          {activeSlide === 1 && (
            <div>
              {/* Season Selector Tabs */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: "10px",
                  marginBottom: "28px",
                }}
                className="season-bar-grid"
              >
                {SEASONS.map((s, idx) => {
                  const isSelected = idx === activeSeasonIndex;
                  return (
                    <button
                      key={s.year}
                      onClick={() => setActiveSeasonIndex(idx)}
                      style={{
                        background: isSelected ? "rgba(0, 230, 118, 0.14)" : "rgba(255, 255, 255, 0.02)",
                        border: isSelected ? "1px solid #00E676" : "1px solid rgba(255, 255, 255, 0.06)",
                        borderRadius: "12px",
                        padding: "14px 16px",
                        textAlign: isRtl ? "right" : "left",
                        cursor: "pointer",
                        transition: "all 0.2s ease",
                      }}
                    >
                      <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: isSelected ? "#00E676" : "#64748B" }}>
                        {isRtl ? "موسم" : "SEASON"} {s.year}
                      </div>
                      <div style={{ fontSize: "15px", fontWeight: 700, color: isSelected ? "#FFFFFF" : "#CBD5E1", marginTop: "2px" }}>
                        {s.crop}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Active Season Detail */}
              {(() => {
                const season = SEASONS[activeSeasonIndex];
                return (
                  <div
                    style={{
                      background: "rgba(5, 8, 15, 0.8)",
                      borderRadius: "16px",
                      border: "1px solid rgba(0, 230, 118, 0.3)",
                      padding: "32px",
                      display: "grid",
                      gridTemplateColumns: "1.1fr 0.9fr",
                      gap: "32px",
                    }}
                    className="carousel-detail-grid"
                  >
                    <div>
                      <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", color: "#00E676", fontSize: "11px", fontFamily: "var(--font-mono)", marginBottom: "12px" }}>
                        <Clock size={13} />
                        <span>PLOT 402-B · {season.status}</span>
                      </div>
                      <h3 style={{ fontSize: "28px", fontWeight: 700, color: "#FFFFFF", marginBottom: "8px" }}>
                        {season.year}: {season.crop} ({season.variety})
                      </h3>
                      <p style={{ fontSize: "15px", color: "#CBD5E1", lineHeight: 1.6, marginBottom: "20px" }}>
                        <strong>Learned Prior:</strong> {season.learnedPrior}
                      </p>
                      <div style={{ fontSize: "13px", color: "#94A3B8" }}>
                        Water Applied: <span style={{ color: "#00D9FF", fontWeight: 600 }}>{season.waterUsed}</span> · Resilience Index: <span style={{ color: "#00E676", fontWeight: 600 }}>{season.resilienceScore}</span>
                      </div>
                    </div>

                    <div
                      style={{
                        background: "rgba(0, 0, 0, 0.4)",
                        borderRadius: "14px",
                        border: "1px solid rgba(255, 255, 255, 0.06)",
                        padding: "24px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "center",
                      }}
                    >
                      <div style={{ fontSize: "11px", color: "#64748B", fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>
                        REALIZED HARVEST OUTCOME
                      </div>
                      <div style={{ fontSize: "32px", fontWeight: 800, color: "#00E676", fontFamily: "var(--font-mono)", margin: "6px 0" }}>
                        {season.yieldRealized}
                      </div>
                      <div style={{ fontSize: "13px", color: "#CBD5E1" }}>
                        {season.delta}
                      </div>

                      {/* 4-Year Prior Convergence Miniature Graph */}
                      <div style={{ marginTop: "16px", paddingTop: "14px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#64748B", fontFamily: "var(--font-mono)", marginBottom: "8px" }}>
                          <span>MULTI-SEASON K_SAT CONVERGENCE</span>
                          <span style={{ color: "#00E676" }}>-19.4% UNCERTAINTY</span>
                        </div>
                        <div style={{ display: "flex", alignItems: "flex-end", gap: "8px", height: "46px" }}>
                          {[
                            { y: "2023", val: "13.4", h: "85%", active: activeSeasonIndex === 0 },
                            { y: "2024", val: "12.9", h: "75%", active: activeSeasonIndex === 1 },
                            { y: "2025", val: "12.6", h: "68%", active: activeSeasonIndex === 2 },
                            { y: "2026", val: "12.5", h: "65%", active: activeSeasonIndex === 3 },
                          ].map((bar) => (
                            <div key={bar.y} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
                              <div
                                style={{
                                  width: "100%",
                                  height: bar.h,
                                  background: bar.active ? "#00E676" : "rgba(255, 255, 255, 0.08)",
                                  borderRadius: "4px 4px 0 0",
                                  border: bar.active ? "1px solid #00E676" : "none",
                                  boxShadow: bar.active ? "0 0 10px rgba(0, 230, 118, 0.5)" : "none",
                                  transition: "all 0.3s ease",
                                }}
                              />
                              <span style={{ fontSize: "9px", fontFamily: "var(--font-mono)", color: bar.active ? "#FFFFFF" : "#64748B" }}>
                                {bar.y}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* SLIDE 3: Reality Split Reconstruction Bench */}
          {activeSlide === 2 && (
            <div>
              {/* Perspective Selector Controls */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "20px",
                  flexWrap: "wrap",
                  gap: "10px",
                }}
              >
                <div style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "#00E676", display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className="pulse-dot" style={{ width: "6px", height: "6px" }} />
                  <span>{p.realityControls.header}</span>
                </div>

                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                  <button
                    onClick={() => setActivePerspective("compare")}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "8px",
                      background: activePerspective === "compare" ? "rgba(0, 230, 118, 0.18)" : "rgba(255,255,255,0.03)",
                      border: activePerspective === "compare" ? "1px solid rgba(0, 230, 118, 0.4)" : "1px solid rgba(255,255,255,0.06)",
                      color: activePerspective === "compare" ? "#00E676" : "#94A3B8",
                      fontSize: "12px",
                      fontFamily: "var(--font-mono)",
                      cursor: "pointer",
                    }}
                  >
                    {p.realityControls.splitView} ({sliderPos}%)
                  </button>
                  <button
                    onClick={() => setActivePerspective("surface")}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "8px",
                      background: activePerspective === "surface" ? "rgba(0, 217, 255, 0.18)" : "rgba(255,255,255,0.03)",
                      border: activePerspective === "surface" ? "1px solid rgba(0, 217, 255, 0.4)" : "1px solid rgba(255,255,255,0.06)",
                      color: activePerspective === "surface" ? "#00D9FF" : "#94A3B8",
                      fontSize: "12px",
                      fontFamily: "var(--font-mono)",
                      cursor: "pointer",
                    }}
                  >
                    {p.realityControls.surface}
                  </button>
                  <button
                    onClick={() => setActivePerspective("subsurface")}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "8px",
                      background: activePerspective === "subsurface" ? "rgba(129, 140, 248, 0.18)" : "rgba(255,255,255,0.03)",
                      border: activePerspective === "subsurface" ? "1px solid rgba(129, 140, 248, 0.4)" : "1px solid rgba(255,255,255,0.06)",
                      color: activePerspective === "subsurface" ? "#818cf8" : "#94A3B8",
                      fontSize: "12px",
                      fontFamily: "var(--font-mono)",
                      cursor: "pointer",
                    }}
                  >
                    {p.realityControls.subsurface}
                  </button>
                  <button
                    onClick={() => setActivePerspective("drone_video")}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "8px",
                      background: activePerspective === "drone_video" ? "rgba(0, 230, 118, 0.22)" : "rgba(255,255,255,0.03)",
                      border: activePerspective === "drone_video" ? "1px solid #00E676" : "1px solid rgba(255,255,255,0.06)",
                      color: activePerspective === "drone_video" ? "#00E676" : "#94A3B8",
                      fontSize: "11px",
                      fontFamily: "var(--font-mono)",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <span>{p.realityControls.droneScan}</span>
                  </button>
                  <button
                    onClick={() => setActivePerspective("growth_video")}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "8px",
                      background: activePerspective === "growth_video" ? "rgba(0, 217, 255, 0.22)" : "rgba(255,255,255,0.03)",
                      border: activePerspective === "growth_video" ? "1px solid #00D9FF" : "1px solid rgba(255,255,255,0.06)",
                      color: activePerspective === "growth_video" ? "#00D9FF" : "#94A3B8",
                      fontSize: "11px",
                      fontFamily: "var(--font-mono)",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <span>{p.realityControls.growthTimelapse}</span>
                  </button>
                  <button
                    onClick={() => setActivePerspective("irrigation_video")}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "8px",
                      background: activePerspective === "irrigation_video" ? "rgba(129, 140, 248, 0.22)" : "rgba(255,255,255,0.03)",
                      border: activePerspective === "irrigation_video" ? "1px solid #818cf8" : "1px solid rgba(255,255,255,0.06)",
                      color: activePerspective === "irrigation_video" ? "#818cf8" : "#94A3B8",
                      fontSize: "11px",
                      fontFamily: "var(--font-mono)",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <span>{p.realityControls.irrigationFlux}</span>
                  </button>
                </div>
              </div>

              {/* Split Screen Visual Container */}
              <div
                style={{
                  position: "relative",
                  width: "100%",
                  height: "420px",
                  borderRadius: "14px",
                  overflow: "hidden",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  userSelect: "none",
                }}
              >
                {activePerspective === "drone_video" || activePerspective === "growth_video" || activePerspective === "irrigation_video" ? (
                  <div style={{ position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 10 }}>
                    <video
                      key={activePerspective}
                      src={
                        activePerspective === "drone_video"
                          ? "/videos/drone-field-scan.webm"
                          : activePerspective === "growth_video"
                          ? "/videos/crop-growth-timelapse.webm"
                          : "/videos/irrigation-water-flux.webm"
                      }
                      autoPlay
                      loop
                      muted
                      playsInline
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                    <div
                      style={{
                        position: "absolute",
                        top: "16px",
                        left: "16px",
                        background: "rgba(5, 10, 20, 0.88)",
                        backdropFilter: "blur(12px)",
                        border: `1px solid ${
                          activePerspective === "drone_video"
                            ? "#00E676"
                            : activePerspective === "growth_video"
                            ? "#00D9FF"
                            : "#818cf8"
                        }`,
                        borderRadius: "8px",
                        padding: "8px 14px",
                        fontSize: "11px",
                        fontFamily: "var(--font-mono)",
                        color:
                          activePerspective === "drone_video"
                            ? "#00E676"
                            : activePerspective === "growth_video"
                            ? "#00D9FF"
                            : "#818cf8",
                      }}
                    >
                      <div style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: "6px" }}>
                        <span className="pulse-dot" style={{ width: "6px", height: "6px" }} />
                        {activePerspective === "drone_video"
                          ? "CANOLA AERIAL RECONNAISSANCE (1080P STABILIZED)"
                          : activePerspective === "growth_video"
                          ? "IN SITU FRUIT PHENOTYPING TIMELAPSE"
                          : "CENTER PIVOT VARIABLE-RATE WATER FLUX"}
                      </div>
                      <div style={{ fontSize: "10px", color: "#94A3B8", marginTop: "2px" }}>
                        {activePerspective === "drone_video"
                          ? "Live Groundspeed 7.2 m/s · Multi-Spectral Ingestion · NDVI 0.86"
                          : activePerspective === "growth_video"
                          ? "Flower to Fruit Expansion +14.2%/24h · Photosynthetic Flux 22.4"
                          : "Richards Darcy Infiltration 18.4 mm/h · Wetting Front -40cm"}
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                {/* Background: Subsurface Vadose Roots (-120cm) */}
                <img
                  src="/images/deeptech/vadose-root-zone.jpg"
                  alt="Subsurface Vadose Living Roots down to -120cm"
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                  }}
                />

                {/* Subsurface Vadose Data Badge */}
                <div
                  style={{
                    position: "absolute",
                    top: "16px",
                    right: "16px",
                    background: "rgba(5, 7, 11, 0.88)",
                    backdropFilter: "blur(14px)",
                    border: "1px solid rgba(0, 230, 118, 0.35)",
                    borderRadius: "8px",
                    padding: "8px 14px",
                    fontSize: "11px",
                    fontFamily: "var(--font-mono)",
                    color: "#00E676",
                    boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
                    zIndex: 5,
                  }}
                >
                  <div style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: "6px" }}>
                    <span className="pulse-dot" style={{ width: "6px", height: "6px" }} />
                    RECONSTRUCTED VADOSE CORE
                  </div>
                  <div style={{ fontSize: "10px", color: "#94A3B8", marginTop: "2px" }}>
                    Depth: -120cm · Root Matric ψ: -38 kPa
                  </div>
                </div>

                {/* Foreground: Surface Orthomosaic clipped via clipPath */}
                {activePerspective !== "subsurface" && (
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      width: "100%",
                      height: "100%",
                      clipPath:
                        activePerspective === "compare"
                          ? `polygon(0 0, ${sliderPos}% 0, ${sliderPos}% 100%, 0 100%)`
                          : "none",
                      transition: activePerspective === "compare" ? "none" : "clip-path 0.3s ease",
                      zIndex: 3,
                    }}
                  >
                    <img
                      src="/images/deeptech/living-field.jpg"
                      alt="Surface Drone Orthomosaic"
                      style={{
                        position: "absolute",
                        inset: 0,
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                      }}
                    />

                    {/* Surface Orthomosaic Data Badge */}
                    <div
                      style={{
                        position: "absolute",
                        top: "16px",
                        left: "16px",
                        background: "rgba(5, 7, 11, 0.88)",
                        backdropFilter: "blur(14px)",
                        border: "1px solid rgba(0, 217, 255, 0.35)",
                        borderRadius: "8px",
                        padding: "8px 14px",
                        fontSize: "11px",
                        fontFamily: "var(--font-mono)",
                        color: "#00D9FF",
                        boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
                      }}
                    >
                      <div style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: "6px" }}>
                        <span className="pulse-dot" style={{ width: "6px", height: "6px", background: "#00D9FF" }} />
                        OPTICAL DRONE ORTHOMOSAIC
                      </div>
                      <div style={{ fontSize: "10px", color: "#94A3B8", marginTop: "2px" }}>
                        Resolution: 0.05m GSD · Multi-Spectral MSI
                      </div>
                    </div>
                  </div>
                )}

                {/* Vertical Divider Line & Draggable Slider */}
                {activePerspective === "compare" && (
                  <>
                    {/* Glowing vertical divider line */}
                    <div
                      style={{
                        position: "absolute",
                        top: 0,
                        bottom: 0,
                        left: `${sliderPos}%`,
                        width: "2px",
                        background: "linear-gradient(180deg, #00D9FF 0%, #00E676 50%, #00D9FF 100%)",
                        boxShadow: "0 0 12px rgba(0, 230, 118, 0.8)",
                        zIndex: 10,
                        pointerEvents: "none",
                      }}
                    />

                    {/* Range Input for dragging */}
                    <input
                      type="range"
                      min={5}
                      max={95}
                      value={sliderPos}
                      onChange={(e) => setSliderPos(Number(e.target.value))}
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        height: "100%",
                        opacity: 0,
                        cursor: "ew-resize",
                        zIndex: 20,
                        margin: 0,
                      }}
                      aria-label="Drag to compare surface observation with subsurface physics"
                    />

                    {/* Drag Handle Visual */}
                    <div
                      style={{
                        position: "absolute",
                        top: "50%",
                        left: `${sliderPos}%`,
                        transform: "translate(-50%, -50%)",
                        width: "42px",
                        height: "42px",
                        borderRadius: "50%",
                        background: "rgba(5, 10, 20, 0.95)",
                        border: "2px solid #00E676",
                        color: "#00E676",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        boxShadow: "0 0 24px rgba(0, 230, 118, 0.8), 0 4px 12px rgba(0,0,0,0.8)",
                        pointerEvents: "none",
                        zIndex: 15,
                        fontSize: "14px",
                        fontWeight: 900,
                      }}
                    >
                      ‹ ›
                    </div>
                  </>
                )}
                  </>
                )}
              </div>
            </div>
          )}
            </motion.div>
          </AnimatePresence>

          {/* Carousel Footer Arrows & Step Dots */}
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
                <ChevronLeft size={16} />
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
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
