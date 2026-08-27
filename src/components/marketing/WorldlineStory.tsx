"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";

/* ═══ WorldlineStory ═══════════════════════════════════════════
   The living field / Plot Worldline — one crop season timeline:
   Sowing → Weather events → Irrigation → Stress → Interventions → Scouting → Harvest → Outcome
   
   "AgriBrain doesn't merely inspect today's image; it remembers what happened."
   ═══════════════════════════════════════════════════════════════ */

interface TimelineStep {
  date: string;
  stage: string;
  event: string;
  icon: string;
  evidenceType: string;
  authority: string;
  detail: string;
  color: string;
}

const WORLDLINE_TIMELINE: TimelineStep[] = [
  {
    date: "Nov 15",
    stage: "Sowing",
    event: "Wheat Sowing Registered",
    icon: "🌱",
    evidenceType: "Farmer Operation",
    authority: "Observed",
    detail: "Seed variety HD-2967 registered with 140 kg/ha seeding rate and initial basal NPK application.",
    color: "var(--field-green)",
  },
  {
    date: "Dec 20",
    stage: "Emergence",
    event: "Vegetation Emergence Detected",
    icon: "🛰️",
    evidenceType: "Sentinel-2 Optical",
    authority: "Assimilated",
    detail: "NDVI rise detected across 88% of plot area. Homogeneous germination pattern confirmed.",
    color: "var(--evidence-observed)",
  },
  {
    date: "Jan 14",
    stage: "Tillering",
    event: "Rainfall & Soil Moisture Event",
    icon: "🌧️",
    evidenceType: "Weather Station + Sensor",
    authority: "Observed",
    detail: "42mm rainfall event recorded. Root-zone moisture replenished to field capacity (32% VWC).",
    color: "var(--evidence-sensor)",
  },
  {
    date: "Feb 22",
    stage: "Stem Elongation",
    event: "Water Deficit Anomaly Flagged",
    icon: "⚠️",
    evidenceType: "SAR + Thermal Fusion",
    authority: "Diagnostic",
    detail: "CWSI water stress index elevated in North-East quadrant. Competing hypothesis: Soil compaction vs irrigation valve defect.",
    color: "var(--uncertainty-amber)",
  },
  {
    date: "Feb 26",
    stage: "Intervention",
    event: "Targeted Irrigation & Scouting",
    icon: "🚜",
    evidenceType: "Farmer Photo + Valve Log",
    authority: "Prescriptive Execution",
    detail: "Farmer inspected and cleared valve blockage. 25mm supplemental drip irrigation applied to Zone B.",
    color: "var(--field-green)",
  },
  {
    date: "Apr 10",
    stage: "Heading & Anthesis",
    event: "Biomass Recovery Verified",
    icon: "🌾",
    evidenceType: "Sentinel-2 + ASMAE",
    authority: "Reconstructed",
    detail: "Vegetation index recovered to historical P75 benchmark. Phenological trajectory on target.",
    color: "var(--agribrain-violet)",
  },
  {
    date: "May 30",
    stage: "Harvest",
    event: "Harvest & Yield Ground Truth",
    icon: "📊",
    evidenceType: "Measured Outcome",
    authority: "Observed",
    detail: "Harvest completed. Measured yield: 4.8 t/ha (within AgriBrain P50 forecast interval of 4.6–5.1 t/ha).",
    color: "var(--field-green)",
  },
];

export default function WorldlineStory() {
  const [selectedStep, setSelectedStep] = useState<number>(3); // Default to stress event
  const prefersReduced = useReducedMotion();
  const currentStep = WORLDLINE_TIMELINE[selectedStep];

  return (
    <section
      className="marketing-section"
      id="worldline"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        {/* ── Header ────────────────────────────────────────── */}
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "56px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "var(--field-green-dim)",
                border: "1px solid rgba(74, 222, 128, 0.15)",
                color: "var(--field-green)",
              }}
            >
              Plot Worldline
            </div>
            <h2 className="marketing-section-title">
              AgriBrain doesn't merely inspect today's image.{" "}
              <strong>It remembers the entire season.</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              Every field has a continuous memory — a worldline connecting weather history, satellite passes, sensor records, farmer operations, scouting photos, and final harvest yield.
            </p>
          </div>
        </Reveal>

        {/* ── Horizontal Scrollable Timeline Bar ───────────── */}
        <Reveal>
          <div
            style={{
              padding: "24px",
              borderRadius: "var(--radius-xl)",
              background: "var(--surface-elevated)",
              border: "1px solid var(--border-subtle)",
              marginBottom: "32px",
              overflowX: "auto",
            }}
          >
            <div style={{ display: "flex", gap: "16px", minWidth: "750px", position: "relative" }}>
              {/* Connecting line */}
              <div
                style={{
                  position: "absolute",
                  top: "36px",
                  left: "40px",
                  right: "40px",
                  height: "2px",
                  background: "linear-gradient(90deg, var(--field-green), var(--evidence-observed), var(--uncertainty-amber), var(--agribrain-violet), var(--field-green))",
                  zIndex: 0,
                }}
              />

              {WORLDLINE_TIMELINE.map((step, i) => {
                const isSelected = selectedStep === i;
                return (
                  <button
                    key={i}
                    onClick={() => setSelectedStep(i)}
                    aria-pressed={isSelected}
                    style={{
                      flex: 1,
                      zIndex: 1,
                      background: isSelected ? "var(--surface-modal)" : "var(--surface-elevated-solid)",
                      border: `1px solid ${isSelected ? step.color : "var(--border-subtle)"}`,
                      borderRadius: "var(--radius-md)",
                      padding: "16px 12px",
                      textAlign: "center",
                      cursor: "pointer",
                      transition: "all 0.2s ease",
                      boxShadow: isSelected ? `0 0 20px ${step.color}20` : undefined,
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--text-dim)", fontWeight: 700 }}>
                      {step.date}
                    </div>
                    <div style={{ fontSize: "1.5rem", margin: "6px 0" }} aria-hidden="true">
                      {step.icon}
                    </div>
                    <div style={{ fontSize: "12px", fontWeight: 700, color: isSelected ? step.color : "var(--text-primary)" }}>
                      {step.stage}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </Reveal>

        {/* ── Detail Card for Selected Event ────────────────── */}
        <Reveal>
          <motion.div
            key={selectedStep}
            initial={prefersReduced ? { opacity: 1 } : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="marketing-card"
            style={{
              padding: "32px",
              borderColor: `${currentStep.color}30`,
              background: "var(--surface-elevated)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <span style={{ fontSize: "2rem" }} aria-hidden="true">{currentStep.icon}</span>
                <div>
                  <div style={{ fontSize: "12px", fontWeight: 700, color: currentStep.color, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    {currentStep.date} · {currentStep.stage}
                  </div>
                  <h3 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)", margin: "2px 0 0" }}>
                    {currentStep.event}
                  </h3>
                </div>
              </div>

              <div style={{ display: "flex", gap: "8px" }}>
                <span style={{ fontSize: "12px", padding: "4px 10px", borderRadius: "6px", background: "var(--surface-code)", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}>
                  Evidence: {currentStep.evidenceType}
                </span>
                <span style={{ fontSize: "12px", padding: "4px 10px", borderRadius: "6px", background: `${currentStep.color}15`, color: currentStep.color, fontWeight: 600 }}>
                  Authority: {currentStep.authority}
                </span>
              </div>
            </div>

            <p style={{ fontSize: "15px", color: "var(--text-body)", lineHeight: 1.7, margin: 0 }}>
              {currentStep.detail}
            </p>
          </motion.div>
        </Reveal>
      </div>
    </section>
  );
}
