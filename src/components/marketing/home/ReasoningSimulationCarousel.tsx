"use client";

import React, { useState } from "react";
import {
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Gauge,
  Sliders,
  TrendingUp,
  Layers,
  ChevronLeft,
  ChevronRight,
  Droplets,
  Zap,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/* ═══ MODULE 02: Reasoning & Simulation Carousel ═══
   Combines:
   1. Causal Diagnosis & Pearl DAG (Why is this happening?)
   2. Counterfactual Simulation (What happens next if we intervene?)
   ═══════════════════════════════════════════════════ */

export default function ReasoningSimulationCarousel() {
  const { t, dir } = useLanguage();
  const [activeSlide, setActiveSlide] = useState<number>(0);

  // Slide 1: Diagnosis Hypotheses
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string>("water");

  // Slide 2: Simulation Branches
  const [selectedBranchId, setSelectedBranchId] = useState<string>("wait");
  const [hoveredX, setHoveredX] = useState<number | null>(null);
  const [showPhysicalVideo, setShowPhysicalVideo] = useState<boolean>(false);

  const getTrajectoryData = (xVal: number) => {
    const clampedX = Math.max(40, Math.min(770, xVal));
    const tNorm = (clampedX - 40) / 730;
    const hour = Math.round(tNorm * 72);
    let moisture = 28.0;
    let y = 100;
    let status = t.reasoning.scrubStatus.optimal;
    let statusColor = "#00E676";

    if (selectedBranchId === "wait") {
      if (tNorm < 0.36) {
        moisture = 24.5 - tNorm * 14;
        y = 100 + tNorm * 65;
        if (moisture < 20) {
          status = t.reasoning.scrubStatus.wilting;
          statusColor = "#fbbf24";
        }
      } else {
        const postT = (tNorm - 0.36) / 0.64;
        moisture = 20.0 + (1 - Math.exp(-postT * 3)) * 10.5;
        y = 125 - postT * 50;
        status = t.reasoning.scrubStatus.rainRecharged;
        statusColor = "#38bdf8";
      }
    } else if (selectedBranchId === "irrigate") {
      if (tNorm < 0.36) {
        moisture = 24.5 + tNorm * 42;
        y = 100 - tNorm * 180;
        status = t.reasoning.scrubStatus.rapidSaturation;
        statusColor = "#00D9FF";
      } else {
        moisture = 39.5 + Math.sin((tNorm - 0.36) * Math.PI) * 4.2;
        y = 35 - Math.sin((tNorm - 0.36) * Math.PI) * 20;
        status = t.reasoning.scrubStatus.rootHypoxia;
        statusColor = "#f87171";
      }
    } else {
      moisture = 25.0 + Math.sin(tNorm * Math.PI * 0.9) * 3.8;
      y = 98 - Math.sin(tNorm * Math.PI * 0.9) * 22;
      status = t.reasoning.scrubStatus.stomatalCalibrated;
      statusColor = "#00E676";
    }

    return { hour, moisture: moisture.toFixed(1), y, x: clampedX, status, statusColor };
  };

  const SLIDES = [
    {
      id: "diagnosis",
      num: t.reasoning.slides.diagnosis.num,
      badge: t.reasoning.slides.diagnosis.badge,
      title: t.reasoning.slides.diagnosis.title,
      subtitle: t.reasoning.slides.diagnosis.subtitle,
    },
    {
      id: "simulation",
      num: t.reasoning.slides.simulation.num,
      badge: t.reasoning.slides.simulation.badge,
      title: t.reasoning.slides.simulation.title,
      subtitle: t.reasoning.slides.simulation.subtitle,
    },
  ];

  const hypothesisStatic: Record<string, { probability: number; color: string }> = {
    water: { probability: 52, color: "#00E676" },
    salinity: { probability: 21, color: "#F59E0B" },
    pathogen: { probability: 14, color: "#F87171" },
    nitrogen: { probability: 8, color: "#818CF8" },
  };

  const HYPOTHESES = t.reasoning.hypotheses.map((h) => ({
    ...h,
    probability: hypothesisStatic[h.id]?.probability ?? 25,
    color: hypothesisStatic[h.id]?.color ?? "#00E676",
  }));

  const branchColors: Record<string, string> = {
    wait: "#00E676",
    irrigate: "#F59E0B",
    inspect: "#00D9FF",
  };

  const BRANCHES = t.reasoning.branches.map((b) => ({
    ...b,
    color: branchColors[b.id] ?? "#00E676",
  }));

  const selectedHypothesis = HYPOTHESES.find((h) => h.id === selectedHypothesisId) || HYPOTHESES[0];
  const selectedBranch = BRANCHES.find((b) => b.id === selectedBranchId) || BRANCHES[0];

  return (
    <section
      id="reasoning"
      className="deep-tech-lattice"
      style={{
        position: "relative",
        background: "#05070B",
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
            <span>{t.reasoning.sectionBadge}</span>
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
              {/* SLIDE 1: Causal Diagnosis & Pearl DAG */}
              {activeSlide === 0 && (
            <div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.1fr 0.9fr",
                  gap: "32px",
                  marginBottom: "28px",
                }}
                className="carousel-detail-grid"
              >
                {/* Left: Hypotheses Selector */}
                <div>
                  <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#64748B", textTransform: "uppercase", marginBottom: "12px" }}>
                    {t.reasoning.hypothesesLabel}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {HYPOTHESES.map((h) => {
                      const isSelected = h.id === selectedHypothesisId;
                      return (
                        <div
                          key={h.id}
                          onClick={() => setSelectedHypothesisId(h.id)}
                          className="hover-lift transition-smooth"
                          style={{
                            background: isSelected ? "rgba(6, 18, 12, 0.95)" : "rgba(255, 255, 255, 0.03)",
                            border: isSelected ? `1px solid ${h.color}` : "1px solid rgba(255, 255, 255, 0.08)",
                            borderRadius: "12px",
                            padding: "14px 16px",
                            cursor: "pointer",
                            boxShadow: isSelected ? `0 0 20px ${h.color}25` : "none",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                            <span
                              className="font-heading"
                              style={{ fontSize: "14px", fontWeight: 700, color: isSelected ? "#FFFFFF" : "#CBD5E1" }}
                            >
                              {h.cause}
                            </span>
                            <span style={{ fontSize: "14px", fontWeight: 800, color: h.color, fontFamily: "var(--font-mono)" }}>
                              {h.probability}%
                            </span>
                          </div>
                          <div style={{ width: "100%", height: "4px", background: "rgba(255, 255, 255, 0.06)", borderRadius: "2px", overflow: "hidden" }}>
                            <div style={{ width: `${h.probability}%`, height: "100%", background: h.color, borderRadius: "2px", transition: "width 0.6s ease" }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right: Selected Mechanism & Next Best Measurement */}
                <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                  <div
                    style={{
                      background: "rgba(5, 7, 11, 0.8)",
                      borderRadius: "12px",
                      border: `1px solid ${selectedHypothesis.color}35`,
                      padding: "20px",
                    }}
                  >
                    <div style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: selectedHypothesis.color, marginBottom: "4px" }}>
                      {t.reasoning.mechanismLabel}
                    </div>
                    <div style={{ fontSize: "16px", fontWeight: 700, color: "#FFFFFF", marginBottom: "8px" }}>
                      {selectedHypothesis.cause} ({selectedHypothesis.probability}%)
                    </div>
                    <p style={{ fontSize: "13px", color: "#CBD5E1", lineHeight: 1.5, margin: "0 0 14px" }}>
                      {selectedHypothesis.mechanism}
                    </p>
                    <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "10px 14px", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.06)", fontSize: "12px", color: "#00E676", fontWeight: 600 }}>
                      {t.reasoning.recommendedActionLabel}: {selectedHypothesis.actionIfTrue}
                    </div>
                  </div>

                  {/* Next Best Measurement */}
                  <div
                    style={{
                      background: "rgba(0, 217, 255, 0.06)",
                      border: "1px solid rgba(0, 217, 255, 0.3)",
                      borderRadius: "12px",
                      padding: "18px 20px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#00D9FF", fontSize: "11px", fontFamily: "var(--font-mono)", marginBottom: "4px" }}>
                      <Gauge size={14} />
                      <span>{t.reasoning.nextBestLabel}</span>
                    </div>
                    <div style={{ fontSize: "14px", fontWeight: 700, color: "#FFFFFF", marginBottom: "4px" }}>
                      {t.reasoning.nextBestTitle}
                    </div>
                    <div style={{ fontSize: "12px", color: "#94A3B8" }}>
                      {t.reasoning.nextBestDesc}
                    </div>
                  </div>
                </div>
              </div>

              {/* Pearl Causal DAG SVG */}
              <div
                style={{
                  background: "rgba(0, 0, 0, 0.4)",
                  borderRadius: "12px",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                  padding: "16px 20px",
                  overflowX: "auto",
                }}
              >
                <div style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "#64748B", textTransform: "uppercase", marginBottom: "8px" }}>
                  {t.reasoning.activeGraphLabel}: {selectedHypothesis.cause}
                </div>
                <svg viewBox="0 0 820 100" style={{ width: "100%", minWidth: "680px", height: "auto", display: "block" }}>
                  {/* Causal Edges */}
                  <line x1="130" y1="50" x2="240" y2="50" stroke={selectedHypothesis.color} strokeWidth="2" />
                  <circle r="3.5" fill={selectedHypothesis.color}>
                    <animate attributeName="cx" from="130" to="240" dur="1.8s" repeatCount="indefinite" />
                    <animate attributeName="cy" from="50" to="50" dur="1.8s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0;1;1;0" dur="1.8s" repeatCount="indefinite" />
                  </circle>

                  <line x1="330" y1="50" x2="440" y2="50" stroke={selectedHypothesis.color} strokeWidth="2" />
                  <circle r="3.5" fill={selectedHypothesis.color}>
                    <animate attributeName="cx" from="330" to="440" dur="1.8s" begin="0.6s" repeatCount="indefinite" />
                    <animate attributeName="cy" from="50" to="50" dur="1.8s" begin="0.6s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0;1;1;0" dur="1.8s" begin="0.6s" repeatCount="indefinite" />
                  </circle>

                  <line x1="530" y1="50" x2="640" y2="50" stroke={selectedHypothesis.color} strokeWidth="2" />
                  <circle r="3.5" fill={selectedHypothesis.color}>
                    <animate attributeName="cx" from="530" to="640" dur="1.8s" begin="1.2s" repeatCount="indefinite" />
                    <animate attributeName="cy" from="50" to="50" dur="1.8s" begin="1.2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0;1;1;0" dur="1.8s" begin="1.2s" repeatCount="indefinite" />
                  </circle>

                  <rect x="20" y="32" width="110" height="36" rx="6" fill="rgba(10, 15, 25, 0.9)" stroke="rgba(255,255,255,0.15)" />
                  <text x="75" y="54" textAnchor="middle" fill="#cbd5e1" fontSize="10" fontFamily="var(--font-mono)">{t.reasoning.graphNodes.vpd}</text>

                  <rect x="240" y="32" width="110" height="36" rx="6" fill="rgba(10, 15, 25, 0.9)" stroke={selectedHypothesis.color} strokeWidth="1.5" />
                  <text x="295" y="54" textAnchor="middle" fill={selectedHypothesis.color} fontSize="10" fontFamily="var(--font-mono)">{t.reasoning.graphNodes.matric}</text>

                  <rect x="440" y="32" width="110" height="36" rx="6" fill="rgba(10, 15, 25, 0.9)" stroke={selectedHypothesis.color} strokeWidth="1.5" />
                  <text x="495" y="54" textAnchor="middle" fill="#ffffff" fontSize="10" fontFamily="var(--font-mono)">{t.reasoning.graphNodes.stomatal}</text>

                  <rect x="640" y="32" width="130" height="36" rx="6" fill="rgba(239, 68, 68, 0.15)" stroke="#ef4444" strokeWidth="2" />
                  <text x="705" y="54" textAnchor="middle" fill="#fca5a5" fontSize="10" fontFamily="var(--font-mono)">{t.reasoning.graphNodes.thermal}</text>
                </svg>
              </div>
            </div>
          )}

          {/* SLIDE 2: Counterfactual Forward Simulation */}
          {activeSlide === 1 && (
            <div>
              {/* Branch Selectors */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: "10px",
                  marginBottom: "24px",
                }}
                className="branches-grid"
              >
                {BRANCHES.map((b) => {
                  const isSelected = b.id === selectedBranchId;
                  return (
                    <button
                      key={b.id}
                      onClick={() => setSelectedBranchId(b.id)}
                      style={{
                        background: isSelected ? "rgba(10, 15, 25, 0.95)" : "rgba(255, 255, 255, 0.02)",
                        border: isSelected ? `1px solid ${b.color}` : "1px solid rgba(255, 255, 255, 0.06)",
                        borderRadius: "12px",
                        padding: "14px 16px",
                        textAlign: "left",
                        cursor: "pointer",
                        transition: "all 0.2s ease",
                      }}
                    >
                      <div style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: isSelected ? b.color : "#64748B", fontWeight: 700 }}>
                        {b.tag}
                      </div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: isSelected ? "#FFFFFF" : "#CBD5E1", marginTop: "2px" }}>
                        {b.name}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* 72h Vadose Trajectory Simulator Chart */}
              <div
                style={{
                  background: "rgba(0, 0, 0, 0.5)",
                  borderRadius: "14px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  padding: "20px",
                  marginBottom: "20px",
                  position: "relative",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", fontSize: "11px", fontFamily: "var(--font-mono)" }}>
                  <span style={{ color: "#94A3B8" }}>{t.reasoning.chartHeader}</span>
                  <span style={{ color: selectedBranch.color, fontWeight: 700 }}>
                    {t.reasoning.chartSelected}: {selectedBranch.name}
                  </span>
                </div>

                {/* Trajectory SVG */}
                <svg
                  viewBox="0 0 800 180"
                  style={{ width: "100%", height: "auto", display: "block", cursor: "crosshair" }}
                  onMouseMove={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    const svgX = ((e.clientX - rect.left) / rect.width) * 800;
                    setHoveredX(svgX);
                  }}
                  onMouseLeave={() => setHoveredX(null)}
                >
                  {/* Optimal Band */}
                  <rect x="40" y="50" width="730" height="60" fill="rgba(0, 230, 118, 0.06)" />
                  <line x1="40" y1="50" x2="770" y2="50" stroke="#00E676" strokeWidth="1" strokeDasharray="3 3" opacity="0.3" />
                  <line x1="40" y1="110" x2="770" y2="110" stroke="#00E676" strokeWidth="1" strokeDasharray="3 3" opacity="0.3" />
                  <text x="50" y="85" fill="#00E676" fontSize="9" fontFamily="var(--font-mono)" opacity="0.7">
                    {t.reasoning.optimalBandLabel}
                  </text>

                  {/* Wilting Line */}
                  <line x1="40" y1="145" x2="770" y2="145" stroke="#fbbf24" strokeWidth="1" strokeDasharray="3 3" opacity="0.4" />
                  <text x="50" y="160" fill="#fbbf24" fontSize="9" fontFamily="var(--font-mono)" opacity="0.8">
                    {t.reasoning.wiltingLabel}
                  </text>

                  {/* Rain vertical marker */}
                  <line x1="300" y1="10" x2="300" y2="165" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2 2" opacity="0.5" />
                  <text x="306" y="24" fill="#38bdf8" fontSize="9" fontFamily="var(--font-mono)">{t.reasoning.rainLabel}</text>

                  {/* Trajectory: Wait for Rain */}
                  <path
                    d="M 40 100 C 140 115, 240 125, 300 120 C 340 85, 420 70, 520 75 C 620 80, 700 82, 770 85"
                    fill="none"
                    stroke="#00E676"
                    strokeWidth={selectedBranchId === "wait" ? 3.5 : 1.5}
                    opacity={selectedBranchId === "wait" ? 1 : 0.35}
                  />

                  {/* Trajectory: Irrigate Now */}
                  <path
                    d="M 40 100 C 100 45, 160 40, 240 45 C 300 42, 330 18, 420 22 C 500 26, 620 35, 770 45"
                    fill="none"
                    stroke="#fbbf24"
                    strokeWidth={selectedBranchId === "irrigate" ? 3.5 : 1.5}
                    opacity={selectedBranchId === "irrigate" ? 1 : 0.35}
                  />

                  {/* Trajectory: Probe Reading */}
                  <path
                    d="M 40 100 C 120 98, 200 95, 300 92 C 360 78, 440 75, 540 78 C 640 80, 710 82, 770 84"
                    fill="none"
                    stroke="#00D9FF"
                    strokeWidth={selectedBranchId === "inspect" ? 3.5 : 1.5}
                    opacity={selectedBranchId === "inspect" ? 1 : 0.35}
                  />

                  {/* Interactive Cursor Scrubber */}
                  {hoveredX !== null && (() => {
                    const data = getTrajectoryData(hoveredX);
                    return (
                      <g>
                        <line x1={data.x} y1="15" x2={data.x} y2="165" stroke="#FFFFFF" strokeWidth="1" strokeDasharray="3 3" opacity="0.75" />
                        <circle cx={data.x} cy={data.y} r="6" fill={selectedBranch.color} stroke="#FFFFFF" strokeWidth="2" />
                        <rect x={Math.min(620, Math.max(40, data.x - 70))} y="20" width="140" height="42" rx="6" fill="rgba(5, 10, 20, 0.95)" stroke={data.statusColor} strokeWidth="1" />
                        <text x={Math.min(620, Math.max(40, data.x - 70)) + 70} y="36" textAnchor="middle" fill="#FFFFFF" fontSize="10" fontWeight="700" fontFamily="var(--font-mono)" style={{ direction: "ltr" }}>
                          T+{data.hour}h · {data.moisture}% VWC
                        </text>
                        <text x={Math.min(620, Math.max(40, data.x - 70)) + 70} y="52" textAnchor="middle" fill={data.statusColor} fontSize="8" fontFamily="var(--font-mono)">
                          {data.status}
                        </text>
                      </g>
                    );
                  })()}
                </svg>
              </div>

              {/* Trade-off Rationale Box */}
              <div
                style={{
                  background: "rgba(5, 7, 11, 0.8)",
                  borderRadius: "12px",
                  border: `1px solid ${selectedBranch.color}35`,
                  padding: "16px 20px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "12px",
                }}
              >
                <div>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#FFFFFF" }}>{selectedBranch.name}</div>
                  <div style={{ fontSize: "12px", color: "#94A3B8", marginTop: "2px" }}>{selectedBranch.rationale}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <button
                    onClick={() => setShowPhysicalVideo(!showPhysicalVideo)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      background: showPhysicalVideo ? "rgba(0, 217, 255, 0.2)" : "rgba(255, 255, 255, 0.05)",
                      border: showPhysicalVideo ? "1px solid #00D9FF" : "1px solid rgba(255, 255, 255, 0.1)",
                      color: showPhysicalVideo ? "#00D9FF" : "#CBD5E1",
                      fontSize: "11px",
                      fontFamily: "var(--font-mono)",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <span>{showPhysicalVideo ? t.reasoning.videoToggle.hide : t.reasoning.videoToggle.show}</span>
                  </button>
                  <div style={{ fontSize: "15px", fontWeight: 700, color: selectedBranch.color, fontFamily: "var(--font-mono)" }}>
                    {selectedBranch.netEconomicAdvantage}
                  </div>
                </div>
              </div>

              {/* Physical Water Infiltration Video Monitor (Collapsible) */}
              {showPhysicalVideo && (
                <div
                  style={{
                    marginTop: "14px",
                    borderRadius: "12px",
                    overflow: "hidden",
                    border: "1px solid rgba(0, 217, 255, 0.3)",
                    background: "#020704",
                    position: "relative",
                  }}
                >
                  <div style={{ height: "240px", position: "relative" }}>
                    <video
                      src="/videos/irrigation-water-flux.webm"
                      autoPlay
                      loop
                      muted
                      playsInline
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                    <div
                      style={{
                        position: "absolute",
                        top: "12px",
                        left: "12px",
                        background: "rgba(4, 12, 8, 0.88)",
                        backdropFilter: "blur(12px)",
                        border: "1px solid rgba(0, 217, 255, 0.4)",
                        borderRadius: "6px",
                        padding: "6px 12px",
                        fontSize: "10px",
                        fontFamily: "var(--font-mono)",
                        color: "#00D9FF",
                      }}
                    >
                      <div style={{ fontWeight: 700 }}>{t.reasoning.videoTelemetryTitle}</div>
                      <div style={{ color: "#94A3B8", marginTop: "2px" }}>
                        {t.reasoning.videoTelemetrySubtitle}
                      </div>
                    </div>
                  </div>
                </div>
              )}
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
