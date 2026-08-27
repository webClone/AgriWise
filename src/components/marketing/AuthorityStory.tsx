"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import { AUTHORITY_LADDER } from "./data/capabilities";

/* ═══ AuthorityStory + ASMAE Story ═════════════════════════════
   "Not every pixel is truth." — Trust & Governance Architecture
   
   - Authority Ladder (Observed → Prescriptive)
   - ASMAE interactive slider (Native observation support ↔ model-assisted reconstructed state)
   - Explicitly shows:
     Native observation support vs ASMAE reconstructed state
     Observation closure ✓
     Model disagreement
     Effective scientific resolution
     Reconstruction ≠ direct measurement
   ═══════════════════════════════════════════════════════════════ */

export default function AuthorityStory() {
  const [activeAuthorityIndex, setActiveAuthorityIndex] = useState(0);
  const [asmaeSliderPos, setAsmaeSliderPos] = useState(50); // 0 to 100%
  const prefersReduced = useReducedMotion();

  const currentAuthority = AUTHORITY_LADDER[activeAuthorityIndex];

  return (
    <section
      className="marketing-section"
      id="authority-asmae"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        {/* ── Header ────────────────────────────────────────── */}
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "56px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "var(--agribrain-violet-dim)",
                border: "1px solid rgba(167, 139, 250, 0.15)",
                color: "var(--agribrain-violet)",
              }}
            >
              Scientific Authority & Governance
            </div>
            <h2 className="marketing-section-title">
              Not every pixel is truth.{" "}
              <strong>AgriBrain governs uncertainty.</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              AgriWise never presents raw model outputs as absolute truth. Every claim carries an explicit authority level, traceable evidence provenance, and calibrated confidence interval.
            </p>
          </div>
        </Reveal>

        {/* ── Authority Ladder ──────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "32px", marginBottom: "80px" }}>
          {/* Left: Ladder list */}
          <StaggerContainer stagger={0.06} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {AUTHORITY_LADDER.map((auth, i) => {
              const isActive = activeAuthorityIndex === i;
              return (
                <StaggerItem key={auth.id}>
                  <button
                    onClick={() => setActiveAuthorityIndex(i)}
                    className="authority-step"
                    aria-pressed={isActive}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      cursor: "pointer",
                      borderColor: isActive ? auth.color : "var(--border-subtle)",
                      background: isActive ? `${auth.color}08` : "var(--surface-elevated)",
                      transform: isActive ? "translateX(6px)" : undefined,
                    }}
                  >
                    <div
                      style={{
                        width: "12px",
                        height: "12px",
                        borderRadius: "50%",
                        background: auth.color,
                        boxShadow: isActive ? `0 0 12px ${auth.color}` : undefined,
                      }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: auth.color }}>
                        {auth.label}
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
                        Level {i + 1} Authority
                      </div>
                    </div>
                    {auth.prescriptiveAllowed ? (
                      <span
                        style={{
                          fontSize: "11px",
                          padding: "2px 8px",
                          borderRadius: "12px",
                          background: "var(--field-green-dim)",
                          color: "var(--field-green)",
                          fontWeight: 600,
                        }}
                      >
                        Prescriptive Allowed
                      </span>
                    ) : (
                      <span
                        style={{
                          fontSize: "11px",
                          padding: "2px 8px",
                          borderRadius: "12px",
                          background: "rgba(251, 191, 36, 0.1)",
                          color: "var(--uncertainty-amber)",
                          fontWeight: 600,
                        }}
                      >
                        Human Review Required
                      </span>
                    )}
                  </button>
                </StaggerItem>
              );
            })}
          </StaggerContainer>

          {/* Right: Selected level details */}
          <Reveal>
            <div
              className="marketing-card"
              style={{
                height: "100%",
                padding: "32px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                borderColor: `${currentAuthority.color}30`,
                background: "var(--surface-elevated)",
              }}
            >
              <div style={{ fontSize: "11px", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "8px" }}>
                Authority Level Definition
              </div>
              <h3 style={{ fontSize: "24px", fontWeight: 700, color: currentAuthority.color, margin: "0 0 16px" }}>
                {currentAuthority.label} State
              </h3>
              <p style={{ fontSize: "15px", color: "var(--text-body)", lineHeight: 1.7, margin: "0 0 24px" }}>
                {currentAuthority.description}
              </p>

              <div
                style={{
                  padding: "16px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--surface-code)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-secondary)", marginBottom: "6px" }}>
                  Governance Standard
                </div>
                <div style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5 }}>
                  {currentAuthority.id === "observed" && "Direct telemetry/observation. Zero model hallucination risk. Highest ground-truth weight."}
                  {currentAuthority.id === "assimilated" && "Multi-source sensor fusion with physical mass/energy balance closure constraint."}
                  {currentAuthority.id === "estimated" && "Spatiotemporal model interpolation with explicit P10/P50/P90 confidence bounds."}
                  {currentAuthority.id === "diagnostic" && "Evaluates competing physiological causes (e.g. nitrogen vs water stress) against evidence gaps."}
                  {currentAuthority.id === "advisory" && "Provides actionable choices. Explicitly abstains if evidence is insufficient."}
                  {currentAuthority.id === "prescriptive" && "Automatic field execution directive. Strictly governed under zero-harm constraints."}
                </div>
              </div>
            </div>
          </Reveal>
        </div>

        {/* ── ASMAE Interactive Demonstration ───────────────── */}
        <Reveal>
          <div style={{
            padding: "36px",
            borderRadius: "var(--radius-xl)",
            background: "var(--surface-elevated)",
            border: "1px solid var(--border-default)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px", marginBottom: "24px" }}>
              <div>
                <div
                  className="marketing-section-badge"
                  style={{
                    background: "var(--evidence-observed-dim)",
                    color: "var(--evidence-observed)",
                    border: "1px solid rgba(34, 211, 238, 0.15)",
                  }}
                >
                  ASMAE Reconstruction Engine
                </div>
                <h3 style={{ fontSize: "22px", fontWeight: 700, margin: "4px 0 0", color: "var(--text-primary)" }}>
                  Native observation support ↔ model-assisted reconstructed state
                </h3>
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-dim)", textAlign: "right" }}>
                <div>Reconstruction ≠ Direct Measurement</div>
                <div style={{ color: "var(--field-green)", fontWeight: 600 }}>Observation closure ✓</div>
              </div>
            </div>

            {/* Slider visual box */}
            <div style={{ position: "relative", borderRadius: "var(--radius-lg)", overflow: "hidden", border: "1px solid var(--border-default)", background: "#080d1a", padding: "24px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", marginBottom: "20px" }}>
                {/* Native view */}
                <div style={{
                  opacity: 1 - asmaeSliderPos / 150,
                  transition: "opacity 0.1s ease",
                  padding: "20px",
                  borderRadius: "var(--radius-md)",
                  background: "rgba(15,23,42,0.6)",
                  border: "1px solid var(--border-subtle)",
                }}>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--evidence-observed)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    Native Observation Support
                  </div>
                  <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", marginTop: "4px" }}>
                    Sentinel-2 Multispectral
                  </div>
                  <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "8px", lineHeight: 1.5 }}>
                    Native support: 10 m resolution. 5-day orbital revisit. Cloud cover or shadow gaps present raw observations.
                  </div>
                  <div style={{ marginTop: "16px", display: "flex", gap: "8px" }}>
                    <span style={{ fontSize: "11px", padding: "4px 8px", background: "rgba(34,211,238,0.1)", color: "var(--evidence-observed)", borderRadius: "4px" }}>Authority: Observed</span>
                    <span style={{ fontSize: "11px", padding: "4px 8px", background: "rgba(148,163,184,0.1)", color: "var(--text-secondary)", borderRadius: "4px" }}>Raw Support: 10m</span>
                  </div>
                </div>

                {/* ASMAE view */}
                <div style={{
                  opacity: 0.3 + (asmaeSliderPos / 100) * 0.7,
                  transition: "opacity 0.1s ease",
                  padding: "20px",
                  borderRadius: "var(--radius-md)",
                  background: "rgba(99,102,241,0.06)",
                  border: "1px solid rgba(99,102,241,0.2)",
                }}>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--agribrain-violet)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    ASMAE Reconstructed State
                  </div>
                  <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", marginTop: "4px" }}>
                    Sub-Grid Reconstructed Field
                  </div>
                  <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "8px", lineHeight: 1.5 }}>
                    Effective scientific resolution: Reconstructed boundary, temporal gap filled, observation closure verified against point soil sensors.
                  </div>
                  <div style={{ marginTop: "16px", display: "flex", gap: "8px" }}>
                    <span style={{ fontSize: "11px", padding: "4px 8px", background: "rgba(167,139,250,0.15)", color: "var(--agribrain-violet)", borderRadius: "4px" }}>Authority: Reconstructed</span>
                    <span style={{ fontSize: "11px", padding: "4px 8px", background: "rgba(74,222,128,0.1)", color: "var(--field-green)", borderRadius: "4px" }}>Uncertainty: Calibrated</span>
                  </div>
                </div>
              </div>

              {/* Slider Control */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "var(--text-muted)", marginBottom: "8px" }}>
                  <span>Raw Native Observation</span>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>Drag to inspect ASMAE Reconstruction</span>
                  <span>Model-Assisted State</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={asmaeSliderPos}
                  onChange={(e) => setAsmaeSliderPos(Number(e.target.value))}
                  aria-label="ASMAE reconstruction comparison slider"
                  style={{
                    width: "100%",
                    height: "8px",
                    borderRadius: "4px",
                    appearance: "none",
                    background: "linear-gradient(90deg, var(--evidence-observed), var(--agribrain-violet))",
                    outline: "none",
                    cursor: "pointer",
                  }}
                />
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
