"use client";

import React, { useState } from "react";
import {
  Cpu,
  Layers,
  Network,
  Box,
  Clock,
  Sparkles,
  Activity,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  Database,
  Binary,
  CheckCircle2,
  Terminal,
  Zap,
  RotateCcw,
  TrendingUp,
  BrainCircuit,
  Atom,
  ArrowRight,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/* ═══ MODULE 04: Architecture & Compounding Moat Carousel ═══
   Apple / Palantir AIP Architectural Standard
   Slide 1: The 7 Canonical Machine Layers & End-to-End Execution Pipeline DAG
   Slide 2: Continuous Learning, Compounding Moat & Omega Scientific Discovery
   ══════════════════════════════════════════════════════════════ */

interface ArchitectureLayer {
  id: string;
  code: string;
  name: string;
  tagline: string;
  role: string;
  mathematicalBasis: string;
  guarantee: string;
  provenanceLevel: string;
  color: string;
  accentRgb: string;
  status: string;
  outputs: string[];
  equation: string;
  icon: any;
}

const LAYERS_CONFIG: ArchitectureLayer[] = [
  {
    id: "agribrain",
    code: "LAYER-01",
    name: "AgriBrain Foundation Model",
    tagline: "Multimodal World Model & Simulation",
    role: "Predicts future biophysical states under hypothetical management interventions and generative scenarios.",
    mathematicalBasis: "Latent diffusion dynamics with physics-informed conservation constraints.",
    guarantee: "Strict biophysical plausibility ceiling; zero unchecked hallucinations.",
    provenanceLevel: "L5 Autonomous Reasoning",
    color: "#00E676",
    accentRgb: "0, 230, 118",
    status: "Online · 14.8M Latent Parameters",
    outputs: ["Predicted Crop Worldline", "Counterfactual Trajectories", "Uncertainty Boundary Tensor"],
    equation: "x_{t+Δt} ~ p_θ(x_{t+Δt} | x_t, u_t, w_t)  subject to  ∇·J_m = 0",
    icon: Cpu,
  },
  {
    id: "asmae",
    code: "LAYER-02",
    name: "ASMAE Engine",
    tagline: "Biophysical State Estimation & Data Assimilation",
    role: "Reconciles noisy remote sensing and soil telemetry using mass-energy conservation and radiative transfer equations.",
    mathematicalBasis: "Ensemble Kalman Inversion (EKI) & Richards Equation solver.",
    guarantee: "Conservation of mass and energy strictly enforced across the vadose zone.",
    provenanceLevel: "L4 Deterministic Physical Core",
    color: "#00D9FF",
    accentRgb: "0, 217, 255",
    status: "Converged · Residual < 0.014 kPa",
    outputs: ["Root-Zone Moisture Matrix", "Evapotranspiration Flux", "Canopy Nitrogen Density"],
    equation: "∂θ/∂t = ∇·[K(h)∇(h + z)] - S(z, t) - E_v(t)",
    icon: Activity,
  },
  {
    id: "mesia",
    code: "LAYER-03",
    name: "MESIA Perception Core",
    tagline: "Subsurface Electromagnetic Inversion",
    role: "Inverts electromagnetic responses to reconstruct soil electrical conductivity, compaction horizons, and water tables.",
    mathematicalBasis: "Maxwell wave equation inversion across multi-frequency dielectric dispersion curves.",
    guarantee: "Subsurface resolution down to -120cm without mechanical excavation.",
    provenanceLevel: "L4 Subsurface Reality",
    color: "#818CF8",
    accentRgb: "129, 140, 248",
    status: "Active · 3-Layer Dielectric Profile",
    outputs: ["Apparent Dielectric Permittivity ε_r", "Salinity Gradient EC_e", "Clay Compaction Hardpan"],
    equation: "ε*(ω) = ε_∞ + (ε_s - ε_∞)/(1 + (iωτ)^{1-α}) - iσ_dc/(ωε_0)",
    icon: Binary,
  },
  {
    id: "fieldcube",
    code: "LAYER-04",
    name: "CanonicalFieldCube",
    tagline: "4D Volumetric Physical State Column",
    role: "Uniform spatial-temporal discretization unifying disparate orbital, aerial, and probe resolutions into coherent voxels.",
    mathematicalBasis: "Spatiotemporal Riemannian manifold grid (10m horizontal × 10cm vertical × 1h time).",
    guarantee: "Continuous differentiable state representation across depth and time.",
    provenanceLevel: "L3 Normalized State",
    color: "#F59E0B",
    accentRgb: "245, 158, 11",
    status: "Continuous · 8 Vadose Strata",
    outputs: ["Volumetric Voxel Tensors", "Root Uptake Vectors", "Soil-Canopy Heat Exchange"],
    equation: "V(x, y, z, t) ∈ R^{N_vars},  z ∈ [-1.2m, +2.5m]",
    icon: Box,
  },
  {
    id: "evidencegraph",
    code: "LAYER-05",
    name: "CanonicalEvidenceGraph",
    tagline: "Cryptographically Anchored Provenance DAG",
    role: "Every raw observation (Sentinel-2, SAR, TDT probe, lab soil sample) is hashed into an immutable directed acyclic graph.",
    mathematicalBasis: "Merkle-DAG structure with SHA-256 content addressing and causal edge semantics.",
    guarantee: "Full evidentiary auditability: every recommendation traces to verifiable physical readings.",
    provenanceLevel: "L2 Immutable Ledger",
    color: "#EC4899",
    accentRgb: "236, 72, 153",
    status: "Anchored · 4,892 Cryptographic Nodes",
    outputs: ["SHA-256 Block Roots", "Sensor Calibrations", "Confidence Weight Coefficients"],
    equation: "Node_i = SHA256(Data_i || Timestamp || PrevHash)",
    icon: Database,
  },
  {
    id: "worldline",
    code: "LAYER-06",
    name: "PlotWorldline",
    tagline: "Longitudinal Multi-Season Lifecycle Ledger",
    role: "Preserves the historical trajectory of each parcel across seasons, accumulating learned soil priors and management outcomes.",
    mathematicalBasis: "Non-stationary state-space model with cumulative biophysical state transition matrices.",
    guarantee: "Never starts from zero. Every past season permanently sharpens future precision.",
    provenanceLevel: "L3 Longitudinal Memory",
    color: "#10B981",
    accentRgb: "16, 185, 129",
    status: "Active · 4-Season Calibrated Priors",
    outputs: ["Long-term Soil Carbon Trend", "Nitrogen Carryover Vector", "Calibrated K_sat Curves"],
    equation: "x_k = A_k x_{k-1} + B_k u_k + w_k,  w_k ~ N(0, Q_k)",
    icon: Clock,
  },
  {
    id: "omega",
    code: "LAYER-07",
    name: "Omega Causal Discovery Engine",
    tagline: "Automated Scientific Hypothesis & Experimentation",
    role: "Discovers novel agricultural mechanisms across thousands of parcels, generating testable hypotheses for biological anomalies.",
    mathematicalBasis: "Constraint-based causal discovery with invariant prediction and active perturbation design.",
    guarantee: "Identifies confounding variables; distinguishes correlation from causal biophysical levers.",
    provenanceLevel: "L5 Scientific Reasoning",
    color: "#A78BFA",
    accentRgb: "167, 139, 250",
    status: "Active · 12 Validated Hypotheses",
    outputs: ["Causal Directed Graphs", "Intervention Designs", "Confounder Sensitivity Bounds"],
    equation: "P(Y | do(X = x)) = ∑_z P(Y | X=x, Z=z) P(Z=z)",
    icon: Sparkles,
  },
];

interface FlywheelStep {
  step: string;
  title: string;
  action: string;
  insight: string;
  delta: string;
  badge: string;
}

const FLYWHEEL_STEPS: FlywheelStep[] = [
  {
    step: "01",
    title: "Intervention Deployed",
    action: "Farmer applies deficit irrigation (25mm) based on AgriBrain counterfactual recommendation.",
    insight: "Hypothesis: Soil moisture buffer at -40cm will bridge the 3-day heatwave without yield penalty.",
    delta: "Action timestamped into Merkle-DAG",
    badge: "DECISION DISPATCH",
  },
  {
    step: "02",
    title: "Physical Observation Assimilated",
    action: "Sentinel-2 MSI + TDT Subsurface Probes record actual canopy temperature and root water flux.",
    insight: "Canopy transpiration maintained at 3.9 mm/day; no stomatal closure detected.",
    delta: "Multi-modal telemetry reconciled in ASMAE",
    badge: "SENSORY RECONSTRUCTION",
  },
  {
    step: "03",
    title: "Residual Error Computed",
    action: "Model predicted 2.1mm daily depletion; actual physical measurement was 1.85mm.",
    insight: "The local soil horizon retains capillary water 13.8% longer than generic regional soil maps indicated.",
    delta: "Residual error: -0.25mm/day",
    badge: "PHYSICS RESIDUAL",
  },
  {
    step: "04",
    title: "Prior Calibrated in PlotWorldline",
    action: "Bayesian update alters the local saturated hydraulic conductivity K_sat from 14.2 to 12.8 cm/day.",
    insight: "The specific parcel digital twin is permanently refined. Next season's simulations will be strictly more accurate.",
    delta: "Prior uncertainty narrowed by 19.4%",
    badge: "WORLDLINE MEMORY",
  },
  {
    step: "05",
    title: "Omega Scientific Hypothesis Formulated",
    action: "Omega causal engine identifies a recurring organic matter boundary condition across neighboring plots.",
    insight: "Generates an autonomous experiment proposal to reduce nitrogen input by 8% under high organic carbon regimes.",
    delta: "New causal structural graph confirmed",
    badge: "OMEGA CAUSAL DISCOVERY",
  },
];

export default function ArchitectureLearningCarousel() {
  const { t } = useLanguage();
  const [activeSlide, setActiveSlide] = useState<number>(0);

  // Slide 1 State: Active Layer & View Mode
  const [activeLayerIndex, setActiveLayerIndex] = useState<number>(0);
  const [viewMode, setViewMode] = useState<"layers" | "pipeline">("layers");

  // Slide 2 State: Active Flywheel Step
  const [activeStepIndex, setActiveStepIndex] = useState<number>(3);

  const SLIDES = [
    {
      id: "architecture",
      num: t.architecture.slides.layers.num,
      badge: t.architecture.slides.layers.badge,
      title: t.architecture.slides.layers.title,
      subtitle: t.architecture.slides.layers.subtitle,
    },
    {
      id: "learning",
      num: t.architecture.slides.continuous.num,
      badge: t.architecture.slides.continuous.badge,
      title: t.architecture.slides.continuous.title,
      subtitle: t.architecture.slides.continuous.subtitle,
    },
  ];

  const layers = LAYERS_CONFIG.map((cfg, idx) => {
    const loc = t.architecture.layers[idx] || {};
    return {
      ...cfg,
      name: loc.name || cfg.name,
      tagline: loc.tagline || cfg.tagline,
      role: loc.role || cfg.role,
      mathematicalBasis: loc.mathematicalBasis || cfg.mathematicalBasis,
      guarantee: loc.guarantee || cfg.guarantee,
      provenanceLevel: loc.provenanceLevel || cfg.provenanceLevel,
      status: loc.status || cfg.status,
      outputs: loc.outputs || cfg.outputs,
    };
  });

  const activeLayer = layers[activeLayerIndex] || layers[0];
  const activeStep = FLYWHEEL_STEPS[activeStepIndex];

  return (
    <section
      id="architecture"
      className="deep-tech-lattice"
      style={{
        position: "relative",
        background: "#05070B",
        padding: "110px 24px 100px",
        overflow: "hidden",
        borderTop: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      {/* Background Ambient Glow */}
      <div
        style={{
          position: "absolute",
          top: "15%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "900px",
          height: "450px",
          background: "radial-gradient(circle, rgba(0, 230, 118, 0.05) 0%, rgba(0, 217, 255, 0.03) 40%, transparent 70%)",
          pointerEvents: "none",
          filter: "blur(90px)",
        }}
      />

      <div className="marketing-container" style={{ position: "relative", zIndex: 2 }}>
        {/* Top Header & Carousel Controls */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "24px",
            marginBottom: "40px",
          }}
        >
          <div style={{ maxWidth: "780px" }}>
            <div style={{ display: "inline-flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
              <span className="fiducial-badge">
                <span className="pulse-dot" />
                {SLIDES[activeSlide].badge}
              </span>
              <span
                style={{
                  fontSize: "0.75rem",
                  color: "#64748B",
                  fontFamily: "var(--font-mono, monospace)",
                  letterSpacing: "0.08em",
                }}
              >
                {SLIDES[activeSlide].num} / 02
              </span>
            </div>

            <h2
              className="apple-section-headline font-heading"
              style={{
                fontSize: "clamp(2rem, 4.5vw, 3.4rem)",
                fontWeight: 800,
                lineHeight: 1.15,
                letterSpacing: "-0.03em",
                color: "#FFFFFF",
                marginBottom: "12px",
              }}
            >
              {SLIDES[activeSlide].title}
            </h2>

            <p className="apple-section-subtitle" style={{ margin: 0, fontSize: "1.05rem", color: "#cbd5e1" }}>
              {SLIDES[activeSlide].subtitle}
            </p>
          </div>

          {/* Carousel Slide Switcher Tabs */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                display: "inline-flex",
                background: "rgba(10, 16, 26, 0.85)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "14px",
                padding: "4px",
                backdropFilter: "blur(12px)",
              }}
            >
              {SLIDES.map((slide, idx) => (
                <button
                  key={slide.id}
                  onClick={() => setActiveSlide(idx)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "8px 16px",
                    borderRadius: "10px",
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    border: "none",
                    background: activeSlide === idx ? "rgba(0, 230, 118, 0.12)" : "transparent",
                    color: activeSlide === idx ? "#00E676" : "#94A3B8",
                    transition: "all 0.2s ease",
                  }}
                >
                  <span
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: activeSlide === idx ? "#00E676" : "#475569",
                    }}
                  />
                  {slide.badge}
                </button>
              ))}
            </div>

            {/* Prev / Next Arrows */}
            <div style={{ display: "inline-flex", gap: "6px" }}>
              <button
                onClick={() => setActiveSlide((prev) => (prev === 0 ? 1 : 0))}
                aria-label="Previous Slide"
                style={{
                  width: "38px",
                  height: "38px",
                  borderRadius: "10px",
                  background: "rgba(10, 16, 26, 0.8)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "#94A3B8",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                <ChevronLeft size={18} />
              </button>
              <button
                onClick={() => setActiveSlide((prev) => (prev === 1 ? 0 : 1))}
                aria-label="Next Slide"
                style={{
                  width: "38px",
                  height: "38px",
                  borderRadius: "10px",
                  background: "rgba(10, 16, 26, 0.8)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "#94A3B8",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        </div>

        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={activeSlide}
            initial={{ opacity: 0, y: 16, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -16, filter: "blur(4px)" }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* ════════════════════════════════════════════════════════════════
                SLIDE 01: The 7 Canonical Machine Layers & Pipeline DAG
                ════════════════════════════════════════════════════════════════ */}
            {activeSlide === 0 && (
          <div>
            {/* View Mode Toggle */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "14px",
                marginBottom: "24px",
                padding: "12px 18px",
                background: "rgba(10, 16, 26, 0.65)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "14px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span
                  style={{
                    fontSize: "0.75rem",
                    color: "#94A3B8",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    fontFamily: "var(--font-mono, monospace)",
                  }}
                >
                  ARCHITECTURAL PROJECTION:
                </span>
                <span style={{ fontSize: "0.85rem", color: "#F8FAFC", fontWeight: 600 }}>
                  {viewMode === "layers" ? "7 Vertically Integrated Machine Layers" : "End-to-End Live Execution Pipeline DAG"}
                </span>
              </div>

              <div
                style={{
                  display: "inline-flex",
                  background: "rgba(0, 0, 0, 0.4)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "8px",
                  padding: "3px",
                }}
              >
                <button
                  onClick={() => setViewMode("layers")}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "6px",
                    fontSize: "0.78rem",
                    fontWeight: 600,
                    border: "none",
                    cursor: "pointer",
                    background: viewMode === "layers" ? "rgba(0, 230, 118, 0.15)" : "transparent",
                    color: viewMode === "layers" ? "#00E676" : "#94A3B8",
                    transition: "all 0.2s",
                  }}
                >
                  Layer Stack (01–07)
                </button>
                <button
                  onClick={() => setViewMode("pipeline")}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "6px",
                    fontSize: "0.78rem",
                    fontWeight: 600,
                    border: "none",
                    cursor: "pointer",
                    background: viewMode === "pipeline" ? "rgba(0, 217, 255, 0.15)" : "transparent",
                    color: viewMode === "pipeline" ? "#00D9FF" : "#94A3B8",
                    transition: "all 0.2s",
                  }}
                >
                  Pipeline DAG
                </button>
              </div>
            </div>

            {viewMode === "layers" ? (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                  gap: "24px",
                }}
              >
                {/* Left Column: Interactive Layer Stack Navigator */}
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {layers.map((layer, idx) => {
                    const isSelected = activeLayerIndex === idx;
                    const IconComponent = layer.icon;
                    return (
                      <div
                        key={layer.id}
                        onClick={() => setActiveLayerIndex(idx)}
                        className="hover-lift transition-smooth"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "14px 18px",
                          borderRadius: "12px",
                          cursor: "pointer",
                          background: isSelected
                            ? `linear-gradient(90deg, rgba(${layer.accentRgb}, 0.16) 0%, rgba(6, 18, 12, 0.9) 100%)`
                            : "rgba(6, 14, 10, 0.6)",
                          border: isSelected
                            ? `1px solid rgba(${layer.accentRgb}, 0.5)`
                            : "1px solid rgba(255, 255, 255, 0.06)",
                          boxShadow: isSelected ? `0 0 20px rgba(${layer.accentRgb}, 0.2)` : "none",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                          <div
                            style={{
                              width: "36px",
                              height: "36px",
                              borderRadius: "8px",
                              background: `rgba(${layer.accentRgb}, 0.12)`,
                              border: `1px solid rgba(${layer.accentRgb}, 0.3)`,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: layer.color,
                            }}
                          >
                            <IconComponent size={18} />
                          </div>
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <span
                                style={{
                                  fontSize: "0.68rem",
                                  fontFamily: "var(--font-mono, monospace)",
                                  color: layer.color,
                                  fontWeight: 700,
                                }}
                              >
                                {layer.code}
                              </span>
                              <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "#F8FAFC" }}>
                                {layer.name}
                              </span>
                            </div>
                            <div style={{ fontSize: "0.78rem", color: "#94A3B8" }}>{layer.tagline}</div>
                          </div>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span
                            style={{
                              fontSize: "0.7rem",
                              fontFamily: "var(--font-mono, monospace)",
                              color: isSelected ? layer.color : "#64748B",
                              background: "rgba(0, 0, 0, 0.3)",
                              padding: "2px 8px",
                              borderRadius: "4px",
                            }}
                          >
                            {layer.provenanceLevel.split(" ")[0]}
                          </span>
                          <ArrowRight
                            size={16}
                            style={{
                              color: isSelected ? layer.color : "#475569",
                              transform: isSelected ? "translateX(2px)" : "none",
                              transition: "transform 0.2s",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Right Column: Deep-Tech Architectural Specimen Card */}
                <div
                  className="intelligence-panel"
                  style={{
                    background: "rgba(10, 16, 26, 0.8)",
                    border: `1px solid rgba(${activeLayer.accentRgb}, 0.3)`,
                    borderRadius: "16px",
                    padding: "28px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    boxShadow: `0 20px 50px rgba(0, 0, 0, 0.5), 0 0 30px rgba(${activeLayer.accentRgb}, 0.08)`,
                  }}
                >
                  <div>
                    {/* Header Spec */}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        marginBottom: "20px",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                        paddingBottom: "16px",
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: "0.72rem",
                            fontFamily: "var(--font-mono, monospace)",
                            color: activeLayer.color,
                            letterSpacing: "0.1em",
                            fontWeight: 700,
                            marginBottom: "4px",
                          }}
                        >
                          {activeLayer.code} · SPECIFICATION
                        </div>
                        <h3 style={{ fontSize: "1.3rem", fontWeight: 700, color: "#F8FAFC", margin: 0 }}>
                          {activeLayer.name}
                        </h3>
                        <div style={{ fontSize: "0.85rem", color: "#94A3B8", marginTop: "2px" }}>
                          {activeLayer.tagline}
                        </div>
                      </div>

                      <div
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          background: `rgba(${activeLayer.accentRgb}, 0.12)`,
                          border: `1px solid rgba(${activeLayer.accentRgb}, 0.3)`,
                          borderRadius: "6px",
                          padding: "4px 10px",
                          fontSize: "0.72rem",
                          fontFamily: "var(--font-mono, monospace)",
                          color: activeLayer.color,
                        }}
                      >
                        <span
                          style={{
                            width: "6px",
                            height: "6px",
                            borderRadius: "50%",
                            background: activeLayer.color,
                          }}
                        />
                        {activeLayer.status}
                      </div>
                    </div>

                    {/* Operational Role */}
                    <div style={{ marginBottom: "20px" }}>
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "#94A3B8",
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                          marginBottom: "6px",
                          fontFamily: "var(--font-mono, monospace)",
                        }}
                      >
                        OPERATIONAL ROLE & SYSTEM CONTRACT
                      </div>
                      <p style={{ fontSize: "0.95rem", color: "#E2E8F0", lineHeight: 1.6, margin: 0 }}>
                        {activeLayer.role}
                      </p>
                    </div>

                    {/* Mathematical Formulation */}
                    <div
                      style={{
                        background: "rgba(0, 0, 0, 0.45)",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                        borderRadius: "10px",
                        padding: "16px",
                        marginBottom: "20px",
                        fontFamily: "var(--font-mono, monospace)",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "0.7rem",
                          color: activeLayer.color,
                          letterSpacing: "0.08em",
                          marginBottom: "8px",
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>GOVERNING FORMULATION</span>
                        <span>{activeLayer.provenanceLevel}</span>
                      </div>
                      <div
                        style={{
                          fontSize: "0.9rem",
                          color: "#F8FAFC",
                          lineHeight: 1.5,
                          background: "rgba(255, 255, 255, 0.03)",
                          padding: "10px 12px",
                          borderRadius: "6px",
                          overflowX: "auto",
                        }}
                      >
                        <code>{activeLayer.equation}</code>
                      </div>
                      <div style={{ fontSize: "0.76rem", color: "#94A3B8", marginTop: "10px", lineHeight: 1.4 }}>
                        {activeLayer.mathematicalBasis}
                      </div>
                    </div>

                    {/* Invariant Guarantee */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "10px",
                        padding: "12px 14px",
                        borderRadius: "8px",
                        background: "rgba(0, 230, 118, 0.06)",
                        border: "1px solid rgba(0, 230, 118, 0.2)",
                        marginBottom: "20px",
                      }}
                    >
                      <CheckCircle2 size={16} style={{ color: "#00E676", marginTop: "2px", flexShrink: 0 }} />
                      <div style={{ fontSize: "0.82rem", color: "#E2E8F0", lineHeight: 1.4 }}>
                        <strong style={{ color: "#00E676" }}>Formal Guarantee: </strong>
                        {activeLayer.guarantee}
                      </div>
                    </div>
                  </div>

                  {/* Output Tensors */}
                  <div>
                    <div
                      style={{
                        fontSize: "0.72rem",
                        color: "#94A3B8",
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        marginBottom: "8px",
                        fontFamily: "var(--font-mono, monospace)",
                      }}
                    >
                      DOWNSTREAM OUTPUT ARTIFACTS
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                      {activeLayer.outputs.map((out, i) => (
                        <span
                          key={i}
                          style={{
                            fontSize: "0.78rem",
                            fontFamily: "var(--font-mono, monospace)",
                            color: "#E2E8F0",
                            background: "rgba(255, 255, 255, 0.06)",
                            border: "1px solid rgba(255, 255, 255, 0.1)",
                            padding: "4px 10px",
                            borderRadius: "6px",
                          }}
                        >
                          {out}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* Pipeline DAG Projection */
              <div
                className="intelligence-panel"
                style={{
                  background: "rgba(10, 16, 26, 0.85)",
                  border: "1px solid rgba(0, 217, 255, 0.25)",
                  borderRadius: "16px",
                  padding: "32px",
                }}
              >
                <div style={{ marginBottom: "24px" }}>
                  <div
                    style={{
                      fontSize: "0.72rem",
                      fontFamily: "var(--font-mono, monospace)",
                      color: "#00D9FF",
                      letterSpacing: "0.1em",
                      fontWeight: 700,
                      marginBottom: "4px",
                    }}
                  >
                    MERKLE-ANCHORED BIOPHYSICAL PIPELINE
                  </div>
                  <h3 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#F8FAFC", margin: 0 }}>
                    Deterministic Sensor-to-Decision Dataflow DAG
                  </h3>
                  <p style={{ fontSize: "0.88rem", color: "#94A3B8", margin: "4px 0 0" }}>
                    Every recommendation is causally determined through this directed pipeline. No black-box guesses.
                  </p>
                </div>

                {/* DAG Step Grid */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "16px",
                  }}
                >
                  {[
                    {
                      step: "01",
                      name: "Multi-Modal Ingestion",
                      engine: "Sentinel-2 + Planet + TDT",
                      desc: "Raw optical reflectances, thermal infrared, SAR backscatter, and probe dielectric data.",
                      color: "#94A3B8",
                    },
                    {
                      step: "02",
                      name: "Electromagnetic Inversion",
                      engine: "MESIA Core",
                      desc: "Inverts dielectric dispersion to derive soil moisture matrix and compaction hardpan depth.",
                      color: "#818CF8",
                    },
                    {
                      step: "03",
                      name: "Biophysical State Assimilation",
                      engine: "ASMAE Engine",
                      desc: "Enforces Richards equation and mass conservation to reconcile satellite with subsurface probes.",
                      color: "#00D9FF",
                    },
                    {
                      step: "04",
                      name: "4D Spatiotemporal Column",
                      engine: "CanonicalFieldCube",
                      desc: "Constructs 10m x 10cm x 1h differentiable physical voxels spanning canopy to deep vadose.",
                      color: "#F59E0B",
                    },
                    {
                      step: "05",
                      name: "Immutable Provenance Anchoring",
                      engine: "CanonicalEvidenceGraph",
                      desc: "Cryptographically anchors all sensory observations and calibration parameters into Merkle DAG.",
                      color: "#EC4899",
                    },
                    {
                      step: "06",
                      name: "Counterfactual Simulation",
                      engine: "AgriBrain Foundation Model",
                      desc: "Simulates forward trajectories under candidate decisions (irrigate, hold, aerate) with risk bounds.",
                      color: "#00E676",
                    },
                    {
                      step: "07",
                      name: "Prescription Under Constraints",
                      engine: "Decision Optimization",
                      desc: "Generates optimal machine prescription files respecting water quotas, tariffs, and agronomic limits.",
                      color: "#34D399",
                    },
                    {
                      step: "08",
                      name: "Bayesian Prior Updating",
                      engine: "PlotWorldline & Omega",
                      desc: "Compares predicted outcome with actual observation to permanently sharpen parcel priors.",
                      color: "#A78BFA",
                    },
                  ].map((node, i) => (
                    <div
                      key={i}
                      style={{
                        background: "rgba(0, 0, 0, 0.4)",
                        border: `1px solid rgba(255, 255, 255, 0.08)`,
                        borderRadius: "12px",
                        padding: "18px",
                        position: "relative",
                        borderLeft: `3px solid ${node.color}`,
                      }}
                    >
                      <div
                        style={{
                          fontSize: "0.68rem",
                          fontFamily: "var(--font-mono, monospace)",
                          color: node.color,
                          fontWeight: 700,
                          marginBottom: "4px",
                        }}
                      >
                        STAGE {node.step} · {node.engine}
                      </div>
                      <div style={{ fontSize: "0.92rem", fontWeight: 600, color: "#F8FAFC", marginBottom: "6px" }}>
                        {node.name}
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "#94A3B8", lineHeight: 1.4 }}>
                        {node.desc}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════════
            SLIDE 02: Continuous Learning & The Compounding Moat
            ════════════════════════════════════════════════════════════════ */}
        {activeSlide === 1 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: "28px",
              alignItems: "stretch",
            }}
          >
            {/* Left Column: Interactive 5-Step Biological Flywheel */}
            <div
              className="intelligence-panel"
              style={{
                background: "rgba(10, 16, 26, 0.75)",
                border: "1px solid rgba(0, 230, 118, 0.25)",
                borderRadius: "16px",
                padding: "26px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: "0.72rem",
                    fontFamily: "var(--font-mono, monospace)",
                    color: "#00E676",
                    letterSpacing: "0.1em",
                    fontWeight: 700,
                    marginBottom: "4px",
                  }}
                >
                  THE CONTINUOUS LEARNING FLYWHEEL
                </div>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#F8FAFC", margin: "0 0 16px" }}>
                  Every Ground Reality Reconciles Into Memory
                </h3>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {FLYWHEEL_STEPS.map((s, idx) => {
                    const isSelected = activeStepIndex === idx;
                    return (
                      <div
                        key={s.step}
                        onClick={() => setActiveStepIndex(idx)}
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: "12px",
                          padding: "12px 14px",
                          borderRadius: "10px",
                          cursor: "pointer",
                          background: isSelected ? "rgba(0, 230, 118, 0.12)" : "rgba(0, 0, 0, 0.35)",
                          border: isSelected
                            ? "1px solid rgba(0, 230, 118, 0.4)"
                            : "1px solid rgba(255, 255, 255, 0.05)",
                          transition: "all 0.2s",
                        }}
                      >
                        <div
                          style={{
                            width: "28px",
                            height: "28px",
                            borderRadius: "6px",
                            background: isSelected ? "#00E676" : "rgba(255, 255, 255, 0.08)",
                            color: isSelected ? "#05070B" : "#94A3B8",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            fontFamily: "var(--font-mono, monospace)",
                            flexShrink: 0,
                          }}
                        >
                          {s.step}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                            <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#F8FAFC" }}>
                              {s.title}
                            </span>
                            <span
                              style={{
                                fontSize: "0.65rem",
                                fontFamily: "var(--font-mono, monospace)",
                                color: isSelected ? "#00E676" : "#64748B",
                              }}
                            >
                              {s.badge}
                            </span>
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "#94A3B8", marginTop: "2px", lineHeight: 1.35 }}>
                            {s.action}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Compounding Moat Metric Footer */}
              <div
                style={{
                  marginTop: "20px",
                  padding: "12px 14px",
                  borderRadius: "8px",
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.68rem", color: "#64748B", fontFamily: "var(--font-mono, monospace)" }}>
                    PARCEL WORLDLINE SHARPNESS
                  </div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 700, color: "#00E676" }}>
                    +34.2% Accuracy / Season
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.68rem", color: "#64748B", fontFamily: "var(--font-mono, monospace)" }}>
                    UNCHECKED HALLUCINATIONS
                  </div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 700, color: "#38BDF8" }}>
                    0.00% (Strict Conservation)
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Deep Inspection of the Selected Flywheel State */}
            <div
              className="intelligence-panel"
              style={{
                background: "rgba(10, 16, 26, 0.8)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "16px",
                padding: "26px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "18px",
                    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                    paddingBottom: "14px",
                  }}
                >
                  <div>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        fontFamily: "var(--font-mono, monospace)",
                        color: "#00E676",
                        fontWeight: 700,
                      }}
                    >
                      STAGE {activeStep.step} INSPECTION
                    </span>
                    <h4 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#F8FAFC", margin: "2px 0 0" }}>
                      {activeStep.title}
                    </h4>
                  </div>
                  <div
                    style={{
                      background: "rgba(0, 230, 118, 0.1)",
                      border: "1px solid rgba(0, 230, 118, 0.3)",
                      borderRadius: "6px",
                      padding: "4px 10px",
                      fontSize: "0.72rem",
                      fontFamily: "var(--font-mono, monospace)",
                      color: "#00E676",
                    }}
                  >
                    {activeStep.badge}
                  </div>
                </div>

                {/* Insight Narrative */}
                <div style={{ marginBottom: "20px" }}>
                  <div
                    style={{
                      fontSize: "0.72rem",
                      color: "#94A3B8",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      fontFamily: "var(--font-mono, monospace)",
                      marginBottom: "6px",
                    }}
                  >
                    BIOPHYSICAL REALITY GROUNDING
                  </div>
                  <p style={{ fontSize: "0.92rem", color: "#E2E8F0", lineHeight: 1.6, margin: 0 }}>
                    {activeStep.insight}
                  </p>
                </div>

                {/* Mathematical Bayesian Update Terminal */}
                <div
                  style={{
                    background: "rgba(0, 0, 0, 0.55)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "10px",
                    padding: "16px",
                    fontFamily: "var(--font-mono, monospace)",
                    marginBottom: "20px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: "10px",
                      fontSize: "0.72rem",
                      color: "#64748B",
                    }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Terminal size={14} style={{ color: "#00E676" }} />
                      CALIBRATED POSTERIOR UPDATER
                    </span>
                    <span style={{ color: "#00E676" }}>BAYESIAN_CONVERGED</span>
                  </div>

                  <div
                    style={{
                      fontSize: "0.82rem",
                      color: "#A7F3D0",
                      lineHeight: 1.6,
                      background: "rgba(255, 255, 255, 0.02)",
                      padding: "10px 12px",
                      borderRadius: "6px",
                    }}
                  >
                    <div>Prior: P(θ) ~ N(μ = 14.2 cm/d, σ² = 3.8)</div>
                    <div>Likelihood: P(y_actual | θ, u_irrigation)</div>
                    <div style={{ color: "#00E676", fontWeight: 700 }}>
                      Posterior: P(θ | y, u) ~ N(μ = 12.8 cm/d, σ² = 1.9)
                    </div>
                    <div style={{ color: "#38BDF8", marginTop: "4px" }}>
                      Variance Reduction: Δσ² = -19.4% (Permanent Moat)
                    </div>
                  </div>
                </div>

                {/* Omega Scientific Discovery Autonomous Synthesis */}
                <div
                  style={{
                    background: "linear-gradient(135deg, rgba(167, 139, 250, 0.08) 0%, rgba(10, 16, 26, 0.6) 100%)",
                    border: "1px solid rgba(167, 139, 250, 0.25)",
                    borderRadius: "10px",
                    padding: "14px 16px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                    <Sparkles size={16} style={{ color: "#A78BFA" }} />
                    <span
                      style={{
                        fontSize: "0.75rem",
                        fontFamily: "var(--font-mono, monospace)",
                        color: "#A78BFA",
                        fontWeight: 700,
                      }}
                    >
                      OMEGA AUTONOMOUS SCIENTIFIC DISCOVERY
                    </span>
                  </div>
                  <p style={{ fontSize: "0.8rem", color: "#CBD5E1", lineHeight: 1.45, margin: 0 }}>
                    Cross-referencing 3,400 adjacent parcels reveals that deficit irrigation under 2.4% soil organic
                    carbon does not induce xylem cavitation. Hypothesis promoted to candidate agronomic protocol.
                  </p>
                </div>
              </div>

              {/* State Delta Footer */}
              <div
                style={{
                  marginTop: "20px",
                  paddingTop: "14px",
                  borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#94A3B8" }}>
                  Active Audit Record: <strong style={{ color: "#F8FAFC" }}>{activeStep.delta}</strong>
                </div>
                <div
                  style={{
                    fontSize: "0.72rem",
                    fontFamily: "var(--font-mono, monospace)",
                    color: "#00E676",
                    background: "rgba(0, 230, 118, 0.1)",
                    padding: "3px 8px",
                    borderRadius: "4px",
                  }}
                >
                  MERKLE_VERIFIED
                </div>
              </div>
            </div>
          </div>
        )}
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  );
}
